"""GPD configuration loading and model tier system.

Layer 1 code: stdlib + pydantic only.
"""

from __future__ import annotations

import json
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from gpd.core.constants import PLANNING_DIR_NAME, ProjectLayout
from gpd.core.errors import ConfigError
from gpd.core.observability import instrument_gpd_function

__all__ = [
    "AGENT_DEFAULT_TIERS",
    "ConfigError",
    "MODEL_PROFILES",
    "AutonomyMode",
    "BranchingStrategy",
    "GPDProjectConfig",
    "ModelProfile",
    "ModelTier",
    "ResearchMode",
    "load_config",
    "resolve_agent_tier",
    "resolve_tier",
    "resolve_model",
]

# ─── Enums ──────────────────────────────────────────────────────────────────────


class AutonomyMode(StrEnum):
    """How much human oversight the system requires."""

    BABYSIT = "babysit"
    BALANCED = "balanced"
    YOLO = "yolo"


class ResearchMode(StrEnum):
    """Exploration vs exploitation tradeoff."""

    EXPLORE = "explore"
    BALANCED = "balanced"
    EXPLOIT = "exploit"
    ADAPTIVE = "adaptive"


class ModelProfile(StrEnum):
    """Research profile controlling model tier assignments."""

    DEEP_THEORY = "deep-theory"
    NUMERICAL = "numerical"
    EXPLORATORY = "exploratory"
    REVIEW = "review"
    PAPER_WRITING = "paper-writing"


class ModelTier(StrEnum):
    """Capability tier for model selection."""

    TIER_1 = "tier-1"
    TIER_2 = "tier-2"
    TIER_3 = "tier-3"


_VALID_MODEL_TIER_VALUES = frozenset(tier.value for tier in ModelTier)


@lru_cache(maxsize=1)
def _valid_runtime_names() -> frozenset[str]:
    catalog_path = Path(__file__).resolve().parents[1] / "adapters" / "runtime_catalog.json"
    entries = json.loads(catalog_path.read_text(encoding="utf-8"))
    return frozenset(
        runtime_name
        for entry in entries
        if isinstance(entry, dict)
        for runtime_name in [str(entry.get("runtime_name", "")).strip()]
        if runtime_name
    )


class BranchingStrategy(StrEnum):
    """Git branching strategy for phases."""

    NONE = "none"
    PER_PHASE = "per-phase"
    PER_MILESTONE = "per-milestone"


# ─── Model Profiles ─────────────────────────────────────────────────────────────

# Maps agent_name -> profile -> tier. Matches model-profiles.md reference exactly.
MODEL_PROFILES: dict[str, dict[str, ModelTier]] = {
    "gpd-planner": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-roadmapper": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-executor": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-phase-researcher": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-project-researcher": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_3,
    },
    "gpd-research-synthesizer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-debugger": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-research-mapper": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_3,
        "exploratory": ModelTier.TIER_3,
        "review": ModelTier.TIER_3,
        "paper-writing": ModelTier.TIER_3,
    },
    "gpd-verifier": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-plan-checker": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-consistency-checker": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-paper-writer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-literature-reviewer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-bibliographer": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_3,
        "exploratory": ModelTier.TIER_3,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-explainer": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-review-reader": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-review-literature": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_1,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_2,
    },
    "gpd-review-math": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-review-physics": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-review-significance": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-referee": {
        "deep-theory": ModelTier.TIER_1,
        "numerical": ModelTier.TIER_2,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_1,
        "paper-writing": ModelTier.TIER_1,
    },
    "gpd-experiment-designer": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_1,
        "exploratory": ModelTier.TIER_2,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_3,
    },
    "gpd-notation-coordinator": {
        "deep-theory": ModelTier.TIER_2,
        "numerical": ModelTier.TIER_3,
        "exploratory": ModelTier.TIER_3,
        "review": ModelTier.TIER_2,
        "paper-writing": ModelTier.TIER_2,
    },
}

# Default tier per agent (profile-independent fallback)
AGENT_DEFAULT_TIERS: dict[str, ModelTier] = {
    "gpd-planner": ModelTier.TIER_1,
    "gpd-roadmapper": ModelTier.TIER_1,
    "gpd-executor": ModelTier.TIER_2,
    "gpd-phase-researcher": ModelTier.TIER_2,
    "gpd-project-researcher": ModelTier.TIER_2,
    "gpd-research-synthesizer": ModelTier.TIER_2,
    "gpd-debugger": ModelTier.TIER_1,
    "gpd-research-mapper": ModelTier.TIER_3,
    "gpd-verifier": ModelTier.TIER_1,
    "gpd-plan-checker": ModelTier.TIER_1,
    "gpd-consistency-checker": ModelTier.TIER_1,
    "gpd-paper-writer": ModelTier.TIER_2,
    "gpd-literature-reviewer": ModelTier.TIER_2,
    "gpd-bibliographer": ModelTier.TIER_2,
    "gpd-explainer": ModelTier.TIER_2,
    "gpd-review-reader": ModelTier.TIER_2,
    "gpd-review-literature": ModelTier.TIER_1,
    "gpd-review-math": ModelTier.TIER_1,
    "gpd-review-physics": ModelTier.TIER_1,
    "gpd-review-significance": ModelTier.TIER_1,
    "gpd-referee": ModelTier.TIER_1,
    "gpd-experiment-designer": ModelTier.TIER_2,
    "gpd-notation-coordinator": ModelTier.TIER_2,
}

# ─── Config Model ───────────────────────────────────────────────────────────────


class GPDProjectConfig(BaseModel):
    """Configuration for a GPD project, loaded from .gpd/config.json.

    Named GPDProjectConfig to distinguish it from other shared project
    contracts. This model controls project-level workflow settings
    (model profile, autonomy, git strategy, etc.).
    """

    model_profile: ModelProfile = ModelProfile.REVIEW
    autonomy: AutonomyMode = AutonomyMode.BALANCED
    research_mode: ResearchMode = ResearchMode.BALANCED

    # Workflow toggles
    commit_docs: bool = True
    research: bool = True
    plan_checker: bool = True
    verifier: bool = True
    parallelization: bool = True

    # Git settings
    branching_strategy: BranchingStrategy = BranchingStrategy.NONE
    phase_branch_template: str = "gpd/phase-{phase}-{slug}"
    milestone_branch_template: str = "gpd/{milestone}-{slug}"

    # Optional overrides
    model_overrides: dict[str, dict[str, str]] | None = Field(default=None)

    @field_validator("model_overrides")
    @classmethod
    def _validate_model_overrides(cls, value: dict[str, dict[str, str]] | None) -> dict[str, dict[str, str]] | None:
        """Validate runtime-scoped tier override mappings."""
        if value is None:
            return None

        normalized: dict[str, dict[str, str]] = {}
        valid_runtime_names = _valid_runtime_names()
        supported_runtimes = ", ".join(sorted(valid_runtime_names))
        supported_tiers = ", ".join(sorted(_VALID_MODEL_TIER_VALUES))

        for runtime, tier_map in value.items():
            if runtime not in valid_runtime_names:
                raise ValueError(
                    f"model_overrides contains unknown runtime {runtime!r}; "
                    f"expected one of: {supported_runtimes}"
                )
            if not isinstance(tier_map, dict):
                raise TypeError(f"model_overrides[{runtime!r}] must be an object mapping tiers to model ids")

            normalized_runtime: dict[str, str] = {}
            for tier, model in tier_map.items():
                if tier not in _VALID_MODEL_TIER_VALUES:
                    raise ValueError(
                        f"model_overrides[{runtime!r}] contains unknown tier {tier!r}; "
                        f"expected one of: {supported_tiers}"
                    )
                if not isinstance(model, str) or not model.strip():
                    raise ValueError(
                        f"model_overrides[{runtime!r}][{tier!r}] must be a non-empty string"
                    )
                normalized_runtime[tier] = model.strip()

            if normalized_runtime:
                normalized[runtime] = normalized_runtime

        return normalized or None


# ─── Config Loading ─────────────────────────────────────────────────────────────

_CONFIG_DEFAULTS = GPDProjectConfig()


def _get_nested(parsed: dict, key: str, section: str | None = None, field: str | None = None) -> object:
    """Get a config value with optional nested section fallback."""
    if key in parsed:
        return parsed[key]
    if section and field and section in parsed and isinstance(parsed[section], dict):
        if field in parsed[section]:
            return parsed[section][field]
    return None


_ALLOWED_CONFIG_ROOT_KEYS = frozenset(
    {
        "autonomy",
        "branching_strategy",
        "commit_docs",
        "git",
        "milestone_branch_template",
        "model_overrides",
        "model_profile",
        "parallelization",
        "phase_branch_template",
        "plan_checker",
        "planning",
        "research",
        "research_mode",
        "verifier",
        "workflow",
    }
)

_ALLOWED_CONFIG_SECTION_KEYS = {
    "git": frozenset({"branching_strategy", "milestone_branch_template", "phase_branch_template"}),
    "planning": frozenset({"commit_docs"}),
    "workflow": frozenset({"plan_checker", "research", "verifier"}),
}


def _unsupported_config_keys(parsed: dict[str, object]) -> list[str]:
    """Return unsupported config.json keys using the current schema only."""
    unsupported: list[str] = []

    for key, value in parsed.items():
        if key not in _ALLOWED_CONFIG_ROOT_KEYS:
            unsupported.append(key)
            continue

        if key == "parallelization" and isinstance(value, dict):
            if value:
                unsupported.extend(f"parallelization.{nested_key}" for nested_key in value)
            else:
                unsupported.append("parallelization")
            continue

        allowed_nested = _ALLOWED_CONFIG_SECTION_KEYS.get(key)
        if allowed_nested is None or not isinstance(value, dict):
            continue

        unsupported.extend(
            f"{key}.{nested_key}"
            for nested_key in value
            if nested_key not in allowed_nested
        )

    return sorted(unsupported)


@instrument_gpd_function("config.load")
def load_config(project_dir: Path) -> GPDProjectConfig:
    """Load GPD config from .gpd/config.json with defaults.

    Raises on malformed JSON. Returns defaults if file doesn't exist.
    """
    config_path = ProjectLayout(project_dir).config_json
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return GPDProjectConfig()
    except (PermissionError, UnicodeDecodeError, OSError) as exc:
        raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Malformed config.json: {e}. Fix or delete {PLANNING_DIR_NAME}/config.json") from e

    if not isinstance(parsed, dict):
        raise ConfigError("config.json must be a JSON object")

    unsupported_keys = _unsupported_config_keys(parsed)
    if unsupported_keys:
        raise ConfigError(
            "Unsupported config.json keys: "
            + ", ".join(f"`{key}`" for key in unsupported_keys)
            + f". Update {PLANNING_DIR_NAME}/config.json to the current schema."
        )

    try:
        return GPDProjectConfig(
            model_profile=_coalesce(
                _get_nested(parsed, "model_profile"),
                _CONFIG_DEFAULTS.model_profile,
            ),
            autonomy=_coalesce(
                _get_nested(parsed, "autonomy"),
                _CONFIG_DEFAULTS.autonomy,
            ),
            research_mode=_coalesce(
                _get_nested(parsed, "research_mode"),
                _CONFIG_DEFAULTS.research_mode,
            ),
            commit_docs=_coalesce(
                _get_nested(parsed, "commit_docs", section="planning", field="commit_docs"),
                _CONFIG_DEFAULTS.commit_docs,
            ),
            branching_strategy=_coalesce(
                _get_nested(parsed, "branching_strategy", section="git", field="branching_strategy"),
                _CONFIG_DEFAULTS.branching_strategy,
            ),
            phase_branch_template=_coalesce(
                _get_nested(parsed, "phase_branch_template", section="git", field="phase_branch_template"),
                _CONFIG_DEFAULTS.phase_branch_template,
            ),
            milestone_branch_template=_coalesce(
                _get_nested(parsed, "milestone_branch_template", section="git", field="milestone_branch_template"),
                _CONFIG_DEFAULTS.milestone_branch_template,
            ),
            research=_coalesce(
                _get_nested(parsed, "research", section="workflow", field="research"),
                _CONFIG_DEFAULTS.research,
            ),
            plan_checker=_coalesce(
                _get_nested(parsed, "plan_checker", section="workflow", field="plan_checker"),
                _CONFIG_DEFAULTS.plan_checker,
            ),
            verifier=_coalesce(
                _get_nested(parsed, "verifier", section="workflow", field="verifier"),
                _CONFIG_DEFAULTS.verifier,
            ),
            parallelization=_coalesce(
                _get_nested(parsed, "parallelization"),
                _CONFIG_DEFAULTS.parallelization,
            ),
            model_overrides=_coalesce(
                _get_nested(parsed, "model_overrides"),
                None,
            ),
        )
    except (ValueError, TypeError) as e:
        raise ConfigError(
            f"Invalid config.json values: {e}. Fix or delete {PLANNING_DIR_NAME}/config.json"
        ) from e


def _coalesce(value: object, default: object) -> object:
    """Return value if not None, else default."""
    return value if value is not None else default


# ─── Model Resolution ───────────────────────────────────────────────────────────


@instrument_gpd_function("config.resolve_tier")
def resolve_agent_tier(agent_name: str, profile: ModelProfile | str) -> ModelTier:
    """Resolve the model tier for an agent given a model profile.

    Falls back to the agent's default tier, then to TIER_2.
    """
    profile_str = profile.value if isinstance(profile, ModelProfile) else profile
    agent_profiles = MODEL_PROFILES.get(agent_name)
    if agent_profiles:
        tier = agent_profiles.get(profile_str)
        if tier:
            return tier
        # Try "review" as fallback profile
        tier = agent_profiles.get("review")
        if tier:
            return tier
    return AGENT_DEFAULT_TIERS.get(agent_name, ModelTier.TIER_2)


@instrument_gpd_function("config.resolve_project_tier")
def resolve_tier(project_dir: Path, agent_name: str) -> ModelTier:
    """Resolve the abstract model tier for an agent in a project."""
    config = load_config(project_dir)
    return resolve_agent_tier(agent_name, config.model_profile)


@instrument_gpd_function("config.resolve_model")
def resolve_model(project_dir: Path, agent_name: str, runtime: str | None = None) -> str | None:
    """Resolve the runtime-specific model override for an agent in a project.

    Returns the concrete model name when the current runtime has an explicit
    override for the agent's resolved tier. Returns ``None`` when no override is
    configured so the caller can omit the runtime model parameter and let the
    platform use its own default model.
    """
    if not runtime:
        return None

    config = load_config(project_dir)
    tier = resolve_agent_tier(agent_name, config.model_profile).value
    runtime_overrides = (config.model_overrides or {}).get(runtime)
    if not runtime_overrides:
        return None
    return runtime_overrides.get(tier)
