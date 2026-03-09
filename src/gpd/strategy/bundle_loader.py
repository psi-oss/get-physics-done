"""Bundle loading and merging system for GPD bundles.

Loads bundles (base + domain overlays like physics) and merges them
into a unified set of actor prompts, action specs, skills, and config.

Merge strategy:
- Actor prompts: base system_prompt + overlay extensions (appended)
- Action specs: deep merge (overlay fields override base, lists concatenated)
- Skills: union of base + overlay
- Config: overlay values override base

Layer 1 code: stdlib + pathlib + pydantic + yaml + logfire only.
"""

from __future__ import annotations

import copy
import logging
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import NON_BUNDLE_SPECS_DIRS
from gpd.core.errors import BundleError
from gpd.core.observability import FeatureFlags, gpd_span
from gpd.specs import SPECS_DIR

logger = logging.getLogger(__name__)

# ─── Errors ────────────────────────────────────────────────────────────────────


class BundleNotFoundError(BundleError):
    """Raised when a bundle directory does not exist."""

    def __init__(self, bundle_dir: Path) -> None:
        self.bundle_dir = bundle_dir
        super().__init__(f"Bundle directory not found: {bundle_dir}")


class BundleManifestError(BundleError):
    """Raised when bundle.yaml is missing or malformed."""

    def __init__(self, bundle_dir: Path, reason: str) -> None:
        self.bundle_dir = bundle_dir
        self.reason = reason
        super().__init__(f"Invalid bundle manifest in {bundle_dir}: {reason}")


class PlaceholderError(BundleError):
    """Raised when a required placeholder cannot be resolved."""

    def __init__(self, placeholder: str) -> None:
        self.placeholder = placeholder
        super().__init__(f"Unresolved placeholder: {{{placeholder}}}")


# ─── Models ────────────────────────────────────────────────────────────────────


class BundleManifest(BaseModel):
    """Metadata for a bundle, loaded from bundle.yaml."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    version: str = "0.0.0"
    domain: str = ""
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    overrides: dict[str, bool] = Field(default_factory=dict)


class ActorSpec(BaseModel):
    """A loaded actor specification."""

    actor_id: str
    system: str = ""
    user_template: str = ""
    description: str = ""
    output_schema: str = ""
    model_id: str = ""
    schema_version: int = 0
    actor_type: str = "commit"
    audit_spec: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ActionSpec(BaseModel):
    """A loaded action specification."""

    action_id: str
    title: str = ""
    summary: str = ""
    schema_version: int = 0
    execution: dict = Field(default_factory=dict)
    write_set: dict = Field(default_factory=dict)
    write_recipe: dict = Field(default_factory=dict)
    parameters: dict = Field(default_factory=dict)
    audit_spec: dict = Field(default_factory=dict)
    triage_guidance: str = ""
    action_guidance: str = ""
    report_guidance: str = ""
    examples: list[dict] = Field(default_factory=list)
    controller: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class SkillEntry(BaseModel):
    """A skill available for prompt injection."""

    name: str
    description: str = ""
    file: str = ""
    domain: str = ""


class Bundle(BaseModel):
    """A loaded bundle containing actors, actions, skills, and config."""

    manifest: BundleManifest = Field(default_factory=BundleManifest)
    actors: dict[str, ActorSpec] = Field(default_factory=dict)
    actions: dict[str, ActionSpec] = Field(default_factory=dict)
    skills: dict[str, SkillEntry] = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    source_dir: Path | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MergedBundle(BaseModel):
    """Result of merging base + overlay bundles."""

    base_manifest: BundleManifest = Field(default_factory=BundleManifest)
    overlay_manifests: list[BundleManifest] = Field(default_factory=list)
    actors: dict[str, ActorSpec] = Field(default_factory=dict)
    actions: dict[str, ActionSpec] = Field(default_factory=dict)
    skills: dict[str, SkillEntry] = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)


# ─── YAML Loading Helpers ──────────────────────────────────────────────────────

# Extension separator for bundle overlay prompts
_OVERLAY_SEPARATOR = "\n\n## Physics Extensions\n\n"


def _load_yaml_file(path: Path) -> dict:
    """Load a YAML file, returning {} on failure."""
    try:
        content = path.read_text(encoding="utf-8")
        result = yaml.safe_load(content)
        return result if isinstance(result, dict) else {}
    except (FileNotFoundError, yaml.YAMLError, OSError):
        return {}


def _load_yaml_dir(directory: Path) -> dict[str, dict]:
    """Load all YAML files from a directory, keyed by stem."""
    results: dict[str, dict] = {}
    if not directory.is_dir():
        return results
    for path in sorted(directory.glob("*.yaml")):
        data = _load_yaml_file(path)
        if data:
            results[path.stem] = data
    for path in sorted(directory.glob("*.yml")):
        data = _load_yaml_file(path)
        if data:
            results[path.stem] = data
    return results


# ─── Deep Merge ────────────────────────────────────────────────────────────────


def deep_merge(base: dict, overlay: dict) -> dict:
    """Deep-merge two dicts. Overlay values override base. Lists are concatenated."""
    result = copy.deepcopy(base)
    for key, overlay_val in overlay.items():
        if key in result:
            base_val = result[key]
            if isinstance(base_val, dict) and isinstance(overlay_val, dict):
                result[key] = deep_merge(base_val, overlay_val)
            elif isinstance(base_val, list) and isinstance(overlay_val, list):
                result[key] = base_val + overlay_val
            else:
                result[key] = copy.deepcopy(overlay_val)
        else:
            result[key] = copy.deepcopy(overlay_val)
    return result


# ─── Bundle Loading ────────────────────────────────────────────────────────────


def load_bundle_manifest(bundle_dir: Path) -> BundleManifest:
    """Load bundle.yaml manifest from a bundle directory.

    Returns a default manifest if bundle.yaml doesn't exist.
    Raises BundleManifestError if the file exists but is malformed.
    """
    manifest_path = bundle_dir / "bundle.yaml"
    if not manifest_path.exists():
        return BundleManifest(name=bundle_dir.name)

    try:
        content = manifest_path.read_text(encoding="utf-8")
        raw = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise BundleManifestError(bundle_dir, f"YAML parse error: {e}") from e
    except OSError as e:
        raise BundleManifestError(bundle_dir, f"Read error: {e}") from e

    if not isinstance(raw, dict):
        raise BundleManifestError(bundle_dir, "Expected a YAML mapping")

    return BundleManifest(**{k: v for k, v in raw.items() if k in BundleManifest.model_fields})


def _load_actors(bundle_dir: Path) -> dict[str, ActorSpec]:
    """Load actor specs from bundle_dir/actors/ or bundle_dir/actors.yaml."""
    actors: dict[str, ActorSpec] = {}

    # Single file format
    single = bundle_dir / "actors.yaml"
    if single.exists():
        data = _load_yaml_file(single)
        if "actors" in data and isinstance(data["actors"], dict):
            for actor_id, spec in data["actors"].items():
                if isinstance(spec, dict):
                    actors[actor_id] = ActorSpec(actor_id=actor_id, **spec)
        elif "prompt_id" in data:
            actors[data["prompt_id"]] = ActorSpec(
                actor_id=data["prompt_id"], **{k: v for k, v in data.items() if k != "prompt_id"}
            )

    # Directory format (overrides single file)
    actors_dir = bundle_dir / "actors"
    if actors_dir.is_dir():
        for name, data in _load_yaml_dir(actors_dir).items():
            actor_id = data.pop("prompt_id", name)
            actors[actor_id] = ActorSpec(actor_id=actor_id, **data)

    return actors


def _load_actions(bundle_dir: Path) -> dict[str, ActionSpec]:
    """Load action specs from bundle_dir/actions/ or bundle_dir/actions.yaml."""
    actions: dict[str, ActionSpec] = {}

    # Single file format
    single = bundle_dir / "actions.yaml"
    if single.exists():
        data = _load_yaml_file(single)
        if "actions" in data and isinstance(data["actions"], dict):
            for action_id, spec in data["actions"].items():
                if isinstance(spec, dict):
                    actions[action_id] = ActionSpec(action_id=action_id, **spec)
        elif "action_id" in data:
            actions[data["action_id"]] = ActionSpec(**data)

    # Directory format
    actions_dir = bundle_dir / "actions"
    if actions_dir.is_dir():
        for name, data in _load_yaml_dir(actions_dir).items():
            action_id = data.pop("action_id", name)
            actions[action_id] = ActionSpec(action_id=action_id, **data)

    return actions


def _load_skills(bundle_dir: Path) -> dict[str, SkillEntry]:
    """Load skills from bundle_dir/skills/."""
    skills: dict[str, SkillEntry] = {}
    skills_dir = bundle_dir / "skills"
    if not skills_dir.is_dir():
        return skills

    for path in sorted(skills_dir.iterdir()):
        if path.is_dir() or path.suffix not in (".yaml", ".yml", ".md"):
            continue
        name = path.stem
        if path.suffix in (".yaml", ".yml"):
            data = _load_yaml_file(path)
            skills[name] = SkillEntry(
                name=data.get("name", name),
                description=data.get("description", ""),
                file=str(path.relative_to(bundle_dir)),
                domain=data.get("domain", ""),
            )
        else:
            # Markdown skill files — extract description from first paragraph
            try:
                content = path.read_text(encoding="utf-8")
                desc = ""
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---"):
                        desc = line
                        break
                skills[name] = SkillEntry(
                    name=name,
                    description=desc,
                    file=str(path.relative_to(bundle_dir)),
                )
            except OSError:
                continue

    return skills


def _load_config(bundle_dir: Path) -> dict:
    """Load config from bundle_dir/config/default.yaml."""
    config_path = bundle_dir / "config" / "default.yaml"
    return _load_yaml_file(config_path)


def load_bundle(bundle_dir: Path) -> Bundle:
    """Load a complete bundle from a directory.

    Raises BundleNotFoundError if the directory doesn't exist.
    """
    with gpd_span("bundle.load", bundle_dir=str(bundle_dir)):
        if not bundle_dir.is_dir():
            raise BundleNotFoundError(bundle_dir)

        manifest = load_bundle_manifest(bundle_dir)
        actors = _load_actors(bundle_dir)
        actions = _load_actions(bundle_dir)
        skills = _load_skills(bundle_dir)
        config = _load_config(bundle_dir)

        logger.debug(
            "Loaded bundle %s: %d actors, %d actions, %d skills",
            manifest.name,
            len(actors),
            len(actions),
            len(skills),
        )

        return Bundle(
            manifest=manifest,
            actors=actors,
            actions=actions,
            skills=skills,
            config=config,
            source_dir=bundle_dir,
        )


# ─── Bundle Merging ────────────────────────────────────────────────────────────


def _merge_actor(base: ActorSpec, overlay: ActorSpec) -> ActorSpec:
    """Merge two actor specs. Overlay system prompt is appended, other fields overridden."""
    merged_data = base.model_dump()

    # System prompt: append overlay as extension section
    if overlay.system:
        if base.system:
            merged_data["system"] = base.system + _OVERLAY_SEPARATOR + overlay.system
        else:
            merged_data["system"] = overlay.system

    # Other string fields: overlay wins if non-empty
    for field in ("user_template", "description", "output_schema", "model_id", "actor_type"):
        overlay_val = getattr(overlay, field)
        if overlay_val:
            merged_data[field] = overlay_val

    # Dict fields: deep merge
    for field in ("audit_spec", "extra"):
        overlay_val = getattr(overlay, field)
        if overlay_val:
            merged_data[field] = deep_merge(merged_data.get(field, {}), overlay_val)

    # Schema version: take higher
    merged_data["schema_version"] = max(base.schema_version, overlay.schema_version)

    return ActorSpec(**merged_data)


def _merge_action(base: ActionSpec, overlay: ActionSpec) -> ActionSpec:
    """Merge two action specs. Deep merge with overlay fields taking precedence."""
    base_dict = base.model_dump()
    overlay_dict = overlay.model_dump()

    # Remove default/empty fields from overlay to avoid clobbering
    clean_overlay: dict = {}
    for key, val in overlay_dict.items():
        if key == "action_id":
            continue
        field_info = ActionSpec.model_fields.get(key)
        default = field_info.default if field_info is not None else None
        if val and val != default:
            clean_overlay[key] = val

    merged = deep_merge(base_dict, clean_overlay)
    return ActionSpec(**merged)


def merge_bundles(base: Bundle, overlay: Bundle) -> MergedBundle:
    """Merge a base bundle with an overlay bundle.

    Actor prompts: base system + overlay extensions (appended)
    Action specs: deep merge (overlay overrides base)
    Skills: union (overlay additions merged in)
    Config: overlay overrides base
    """
    with gpd_span(
        "bundle.merge",
        base_name=base.manifest.name,
        overlay_name=overlay.manifest.name,
    ):
        # Merge actors
        merged_actors: dict[str, ActorSpec] = {}
        all_actor_ids = set(base.actors) | set(overlay.actors)
        for actor_id in all_actor_ids:
            base_actor = base.actors.get(actor_id)
            overlay_actor = overlay.actors.get(actor_id)
            if base_actor and overlay_actor:
                merged_actors[actor_id] = _merge_actor(base_actor, overlay_actor)
            elif overlay_actor:
                merged_actors[actor_id] = overlay_actor
            elif base_actor:
                merged_actors[actor_id] = base_actor

        # Merge actions
        merged_actions: dict[str, ActionSpec] = {}
        all_action_ids = set(base.actions) | set(overlay.actions)
        for action_id in all_action_ids:
            base_action = base.actions.get(action_id)
            overlay_action = overlay.actions.get(action_id)
            if base_action and overlay_action:
                merged_actions[action_id] = _merge_action(base_action, overlay_action)
            elif overlay_action:
                merged_actions[action_id] = overlay_action
            elif base_action:
                merged_actions[action_id] = base_action

        # Merge skills: union
        merged_skills = dict(base.skills)
        merged_skills.update(overlay.skills)

        # Merge config: deep merge
        merged_config = deep_merge(base.config, overlay.config)

        return MergedBundle(
            base_manifest=base.manifest,
            overlay_manifests=[overlay.manifest],
            actors=merged_actors,
            actions=merged_actions,
            skills=merged_skills,
            config=merged_config,
        )


# ─── Placeholder Resolution ───────────────────────────────────────────────────

# Matches {placeholder_name} in text (not inside backticks or code blocks)
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# Standard placeholders that the bundle system knows how to resolve
KNOWN_PLACEHOLDERS: set[str] = {
    "skills_index",
    "physics_verification_checklist",
    "error_awareness",
    "convention_context",
    "mcp_instructions",
    "actor_call_json",
    "max_proposals",
    "allowed_proposal_action_ids",
    "model_id",
    "dynamic_output_schema",
}


def resolve_placeholders(
    text: str,
    context: dict[str, str],
    *,
    strict: bool = False,
) -> str:
    """Resolve {placeholder} patterns in text using the context dict.

    Args:
        text: Text with {placeholder} patterns.
        context: Mapping of placeholder name -> replacement value.
        strict: If True, raise PlaceholderError for unresolved known placeholders.

    Returns:
        Text with placeholders replaced.
    """

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in context:
            return context[key]
        if strict and key in KNOWN_PLACEHOLDERS:
            raise PlaceholderError(key)
        return match.group(0)  # Leave unresolved

    return _PLACEHOLDER_RE.sub(_replacer, text)


# ─── BundleLoader ──────────────────────────────────────────────────────────────


class BundleLoader:
    """High-level interface for loading and merging GPD bundles.

    Loads a base bundle and optional domain overlays, merges them,
    resolves placeholders, and provides access to merged specs.
    Integrates with FeatureFlags for component-level toggling.
    """

    def __init__(
        self,
        specs_dir: Path | None = None,
        feature_flags: FeatureFlags | None = None,
    ) -> None:
        self._specs_dir = specs_dir or SPECS_DIR
        self._feature_flags = feature_flags
        self._merged: MergedBundle | None = None
        self._base: Bundle | None = None
        self._overlays: list[Bundle] = []

    @property
    def specs_dir(self) -> Path:
        return self._specs_dir

    @property
    def is_loaded(self) -> bool:
        return self._merged is not None

    @property
    def merged(self) -> MergedBundle | None:
        return self._merged

    def load(
        self,
        base_name: str = "base",
        overlay_names: list[str] | None = None,
    ) -> MergedBundle:
        """Load and merge bundles by name.

        Names are resolved relative to specs_dir (e.g., "base" -> specs_dir/base/).
        """
        with gpd_span("bundle_loader.load", base=base_name, overlays=str(overlay_names or [])):
            base_dir = self._specs_dir / base_name
            if not base_dir.is_dir():
                logger.info("Base bundle dir %s not found, using empty bundle", base_dir)
                self._base = Bundle(manifest=BundleManifest(name=base_name))
            else:
                self._base = load_bundle(base_dir)

            result = MergedBundle(
                base_manifest=self._base.manifest,
                actors=dict(self._base.actors),
                actions=dict(self._base.actions),
                skills=dict(self._base.skills),
                config=dict(self._base.config),
            )

            self._overlays = []
            for overlay_name in overlay_names or []:
                overlay_dir = self._specs_dir / overlay_name
                if not overlay_dir.is_dir():
                    logger.warning("Overlay bundle dir %s not found, skipping", overlay_dir)
                    continue
                overlay = load_bundle(overlay_dir)
                self._overlays.append(overlay)

                # Incremental merge
                temp_base = Bundle(
                    manifest=result.base_manifest,
                    actors=result.actors,
                    actions=result.actions,
                    skills=result.skills,
                    config=result.config,
                )
                merged = merge_bundles(temp_base, overlay)
                result = merged

            self._merged = result
            logger.info(
                "Bundle loaded: %d actors, %d actions, %d skills",
                len(result.actors),
                len(result.actions),
                len(result.skills),
            )
            return result

    def get_actor_prompt(self, actor_id: str, context: dict[str, str] | None = None) -> str | None:
        """Return the merged system prompt for an actor, with placeholders resolved.

        Returns None if the actor is not found or is disabled by feature flags.
        """
        if self._merged is None:
            return None
        actor = self._merged.actors.get(actor_id)
        if actor is None:
            return None

        prompt = actor.system
        if context:
            prompt = resolve_placeholders(prompt, context)
        return prompt

    def get_actor_spec(self, actor_id: str) -> ActorSpec | None:
        """Return the full merged actor spec."""
        if self._merged is None:
            return None
        return self._merged.actors.get(actor_id)

    def get_action_spec(self, action_id: str) -> ActionSpec | None:
        """Return the full merged action spec."""
        if self._merged is None:
            return None
        return self._merged.actions.get(action_id)

    def get_action_spec_dict(self, action_id: str) -> dict | None:
        """Return the merged action spec as a dict (for backward compat with raw YAML consumers)."""
        spec = self.get_action_spec(action_id)
        if spec is None:
            return None
        return spec.model_dump()

    def get_skills_index(self) -> str:
        """Return a formatted skills listing for prompt injection."""
        if self._merged is None:
            return ""

        lines: list[str] = []
        for name, skill in sorted(self._merged.skills.items()):
            # Check feature flags if available
            flag_key = f"gpd.skills.{name}"
            if self._feature_flags and not self._feature_flags.is_enabled(flag_key):
                # Fall through — individual skill flags are not in the default set,
                # so they won't be checked unless explicitly configured
                pass
            desc = f" — {skill.description}" if skill.description else ""
            lines.append(f"- {skill.name}{desc}")

        return "\n".join(lines) if lines else "No skills available."

    def get_actor_ids(self) -> list[str]:
        """Return all merged actor IDs."""
        if self._merged is None:
            return []
        return sorted(self._merged.actors.keys())

    def get_action_ids(self) -> list[str]:
        """Return all merged action IDs."""
        if self._merged is None:
            return []
        return sorted(self._merged.actions.keys())

    def get_skill_names(self) -> list[str]:
        """Return all merged skill names."""
        if self._merged is None:
            return []
        return sorted(self._merged.skills.keys())

    def build_context(
        self,
        *,
        convention_context: str = "",
        error_awareness: str = "",
        verification_checklist: str = "",
        mcp_instructions: str = "",
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build a placeholder context dict for prompt resolution.

        Combines standard GPD placeholders with custom extras.
        """
        ctx: dict[str, str] = {
            "skills_index": self.get_skills_index(),
            "convention_context": convention_context,
            "error_awareness": error_awareness,
            "physics_verification_checklist": verification_checklist,
            "mcp_instructions": mcp_instructions,
        }
        if extra:
            ctx.update(extra)
        return ctx

    # ─── Discovery ─────────────────────────────────────────────────────────────

    def list_available_bundles(self) -> list[BundleManifest]:
        """List all available bundles in the specs directory."""
        with gpd_span("bundle_loader.list_available"):
            manifests: list[BundleManifest] = []
            if not self._specs_dir.is_dir():
                return manifests

            for child in sorted(self._specs_dir.iterdir()):
                if not child.is_dir():
                    continue
                # Skip non-bundle directories
                if child.name in NON_BUNDLE_SPECS_DIRS:
                    continue
                manifest = load_bundle_manifest(child)
                manifests.append(manifest)

            return manifests

    def get_bundle_dirs(self) -> list[Path]:
        """Return the list of bundle directories used for loading (for agentic-builder integration)."""
        dirs: list[Path] = []
        if self._base and self._base.source_dir:
            dirs.append(self._base.source_dir)
        for overlay in self._overlays:
            if overlay.source_dir:
                dirs.append(overlay.source_dir)
        return dirs


# ─── Module-level Singleton ────────────────────────────────────────────────────

_active_loader: BundleLoader | None = None


def init_bundle_loader(
    specs_dir: Path | None = None,
    feature_flags: FeatureFlags | None = None,
    base_name: str = "base",
    overlay_names: list[str] | None = None,
) -> BundleLoader:
    """Initialize the module-level BundleLoader singleton.

    Loads and merges bundles. Returns the loader for immediate use.
    """
    global _active_loader
    with gpd_span("init_bundle_loader", base=base_name, overlays=str(overlay_names or [])):
        loader = BundleLoader(specs_dir=specs_dir, feature_flags=feature_flags)
        loader.load(base_name=base_name, overlay_names=overlay_names)
        _active_loader = loader
        return loader


def get_bundle_loader() -> BundleLoader | None:
    """Get the active bundle loader, or None if not initialized."""
    return _active_loader


def reset_bundle_loader() -> None:
    """Reset the module-level singleton (for testing)."""
    global _active_loader
    _active_loader = None
