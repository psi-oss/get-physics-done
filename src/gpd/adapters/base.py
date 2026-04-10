"""Base adapter ABC for runtime-specific installation surfaces."""

from __future__ import annotations

import abc
import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from gpd.adapters.install_utils import (
    AGENTS_DIR_NAME,
    CACHE_DIR_NAME,
    COMMANDS_DIR_NAME,
    FLAT_COMMANDS_DIR_NAME,
    GPD_INSTALL_DIR_NAME,
    HOOKS_DIR_NAME,
    MANIFEST_NAME,
    PATCHES_DIR_NAME,
    UPDATE_CACHE_FILENAME,
    _dir_contains_files,
    build_runtime_cli_bridge_command,
    compute_path_prefix,
    convert_tool_references_in_body,
    copy_hook_scripts,
    install_gpd_content,
    managed_hook_paths,
    pre_install_cleanup,
    process_settings_commit_attribution,
    prune_empty_ancestors,
    replace_placeholders,
    strip_sub_tags,
    translate_frontmatter_tool_names,
    validate_package_integrity,
    write_manifest,
    write_version_file,
)
from gpd.adapters.runtime_catalog import get_runtime_descriptor, get_shared_install_metadata, resolve_global_config_dir
from gpd.adapters.tool_names import (
    build_runtime_alias_map,
    reference_translation_map,
    translate_for_runtime,
)

if TYPE_CHECKING:
    from gpd.registry import AgentDef

logger = logging.getLogger(__name__)


def _managed_install_surface(target_dir: Path):
    """Return the shared managed-surface snapshot for *target_dir*."""
    from gpd.hooks.install_metadata import inspect_managed_install_surface

    return inspect_managed_install_surface(target_dir)


def _remove_gpd_flat_command_residue(flat_commands: Path, *, stop_at: Path) -> int:
    """Remove managed flat command files and prune empty command directories."""
    removed = 0
    try:
        entries = list(flat_commands.iterdir())
    except OSError:
        return 0

    for entry in entries:
        if not entry.is_file():
            continue
        if entry.name.startswith("gpd-") and entry.suffix == ".md":
            entry.unlink()
            removed += 1
    prune_empty_ancestors(flat_commands, stop_at=stop_at)
    return removed


def _has_only_agent_residue(target_dir: Path) -> bool:
    """Return whether *target_dir* contains only agent-surface residue.

    Agent installs are replaced in place and stale ``gpd-*`` agent files are
    removed during install, so an explicit target that only contains an
    ``agents/`` directory is still safe to repair without a trusted manifest.
    Richer managed surfaces such as hooks, commands, or bundled content remain
    blocked until ownership is established by a valid manifest.
    """

    if not target_dir.exists() or not target_dir.is_dir():
        return False

    surface = _managed_install_surface(target_dir)
    has_managed_hooks = any((target_dir / rel_path).is_file() for rel_path in managed_hook_paths(target_dir))
    if (
        not surface.has_managed_agents
        or surface.has_gpd_content
        or surface.has_nested_commands
        or surface.has_flat_commands
        or has_managed_hooks
    ):
        return False

    for entry in target_dir.iterdir():
        if entry.name != AGENTS_DIR_NAME:
            if not entry.is_dir():
                return False
            if _dir_contains_files(entry):
                return False
            continue
        if not entry.is_dir():
            return False

    return (target_dir / AGENTS_DIR_NAME).is_dir()


def _has_blocking_manifestless_install_surface(target_dir: Path) -> bool:
    """Return whether *target_dir* contains managed surfaces that require ownership.

    Bundled prompt content and command directories are not safe to remove or
    overwrite blindly when the authoritative manifest is missing. Agent, hook,
    cache, and local-patch residue is handled by narrower cleanup code and may
    be repaired without a manifest.
    """

    surface = _managed_install_surface(target_dir)
    if surface.has_gpd_content or surface.has_nested_commands or surface.has_flat_commands:
        return True

    has_managed_hooks = any((target_dir / rel_path).is_file() for rel_path in managed_hook_paths(target_dir))
    return surface.has_managed_agents and has_managed_hooks


class RuntimeAdapter(abc.ABC):
    """Abstract base for GPD runtime adapters."""

    tool_name_map: Mapping[str, str] = {}
    auto_discovered_tools: frozenset[str] = frozenset()
    drop_mcp_frontmatter_tools: bool = False
    strip_sub_tags_in_shared_markdown: bool = False

    @property
    @abc.abstractmethod
    def runtime_name(self) -> str:
        """Short identifier for this runtime."""

    @property
    def display_name(self) -> str:
        """Human-readable runtime name."""
        return self.runtime_descriptor.display_name

    @property
    def config_dir_name(self) -> str:
        """Name of the runtime's config directory."""
        return self.runtime_descriptor.config_dir_name

    @property
    def help_command(self) -> str:
        """Runtime-specific help command."""
        return self.format_command("help")

    @property
    def launch_command(self) -> str:
        """System-terminal command for opening this runtime."""
        return self.runtime_descriptor.launch_command

    @property
    def new_project_command(self) -> str:
        """Runtime-specific command for starting a new project."""
        return self.format_command("new-project")

    @property
    def map_research_command(self) -> str:
        """Runtime-specific command for mapping existing work."""
        return self.format_command("map-research")

    @property
    def activation_env_vars(self) -> tuple[str, ...]:
        """Environment variables that signal this runtime is active."""
        return self.runtime_descriptor.activation_env_vars

    @property
    def local_config_dir_name(self) -> str:
        """Workspace-local config directory name for this runtime."""
        return self.config_dir_name

    @property
    def install_flag(self) -> str:
        """Bootstrap installer flag for this runtime."""
        return self.runtime_descriptor.install_flag

    @property
    def selection_flags(self) -> tuple[str, ...]:
        """Public bootstrap flags accepted for selecting this runtime."""
        return self.runtime_descriptor.selection_flags

    @property
    def selection_aliases(self) -> tuple[str, ...]:
        """Interactive/runtime aliases accepted by the bootstrap installer."""
        return self.runtime_descriptor.selection_aliases

    @property
    def command_prefix(self) -> str:
        """Runtime-native command prefix."""
        return self.runtime_descriptor.command_prefix

    @property
    def public_command_surface_prefix(self) -> str:
        """Public runtime command prefix used on shared surfaces."""
        return self.runtime_descriptor.public_command_surface_prefix or self.command_prefix

    @property
    def tool_alias_map(self) -> Mapping[str, str]:
        """Runtime-native tool aliases back to canonical GPD names."""
        return build_runtime_alias_map(self.tool_name_map)

    def translate_tool_name(self, name: str) -> str:
        """Translate a canonical or runtime-native tool name to this runtime."""
        return translate_for_runtime(name, self.tool_name_map) or ""

    def translate_frontmatter_tool_name(self, name: str) -> str | None:
        """Translate a frontmatter tool token for this runtime."""
        return translate_for_runtime(
            name,
            self.tool_name_map,
            auto_discovered_tools=self.auto_discovered_tools,
            drop_mcp_frontmatter_tools=self.drop_mcp_frontmatter_tools,
        )

    def tool_reference_translation_map(self) -> dict[str, str]:
        """Canonical prompt tool references rewritten for this runtime."""
        return reference_translation_map(
            self.tool_name_map,
            auto_discovered_tools=self.auto_discovered_tools,
            drop_mcp_frontmatter_tools=self.drop_mcp_frontmatter_tools,
        )

    def translate_shared_command_references(self, content: str) -> str:
        """Rewrite shared command references for this runtime."""
        return content

    def translate_shared_markdown(
        self,
        content: str,
        path_prefix: str,
        *,
        install_scope: str | None = None,
    ) -> str:
        """Translate installed shared markdown from canonical form to this runtime."""
        content = replace_placeholders(content, path_prefix, self.runtime_name, install_scope)
        content = translate_frontmatter_tool_names(content, self.translate_frontmatter_tool_name)
        content = self.translate_shared_command_references(content)
        if self.strip_sub_tags_in_shared_markdown:
            content = strip_sub_tags(content)
        return convert_tool_references_in_body(content, self.tool_reference_translation_map())

    def project_markdown_surface(
        self,
        content: str,
        *,
        surface_kind: str,
        path_prefix: str,
        command_name: str | None = None,
    ) -> str:
        """Return the runtime-visible prompt surface for compiled shared markdown."""

        del path_prefix, command_name
        if surface_kind not in {"agent", "command"}:
            raise ValueError("surface_kind must be 'agent' or 'command'")
        return content

    def commit_attribution_config_path(self, *, explicit_config_dir: str | None = None) -> Path | None:
        """Return the runtime-owned config file that stores commit attribution.

        Runtimes expose this through their own install contract instead of a
        shared filename assumption, so the lookup stays adapter-driven.
        """
        config_dir = self.resolve_global_config_dir()
        if explicit_config_dir:
            config_dir = Path(explicit_config_dir).expanduser()
        for relpath in self.runtime_install_required_relpaths():
            relpath_path = Path(relpath)
            if relpath_path.suffix in {".json", ".jsonc", ".toml", ".yaml", ".yml"}:
                return config_dir / relpath_path
        return None

    def get_commit_attribution(self, *, explicit_config_dir: str | None = None) -> str | None:
        """Return commit attribution override for this runtime."""
        config_path = self.commit_attribution_config_path(explicit_config_dir=explicit_config_dir)
        if config_path is None:
            return None
        return process_settings_commit_attribution(config_path)

    @property
    def runtime_descriptor(self):
        """Adapter-owned metadata descriptor for this runtime."""
        return get_runtime_descriptor(self.runtime_name)

    @property
    def global_config_dir(self) -> Path:
        """Global config directory for this runtime.

        Defaults are resolved from the runtime descriptor. Most runtimes use a
        home-relative dot-directory, while descriptors with env-var or XDG
        precedence are resolved via ``resolve_global_config_dir()``.
        """
        return self.resolve_global_config_dir()

    def resolve_global_config_dir(self, *, home: Path | None = None) -> Path:
        """Resolve the runtime's global config dir."""
        return resolve_global_config_dir(self.runtime_descriptor, home=home)

    def resolve_local_config_dir(self, cwd: Path | None = None) -> Path:
        """Resolve the runtime's local config dir."""
        return Path(cwd or os.getcwd()) / self.local_config_dir_name

    def format_command(self, action: str) -> str:
        """Format a public runtime GPD command."""
        return f"{self.public_command_surface_prefix}{action}"

    @property
    def update_command(self) -> str:
        """Public bootstrap command that updates this runtime install."""
        base = get_shared_install_metadata().bootstrap_command
        return f"{base} {self.install_flag}".strip()

    def install_detection_relpaths(self) -> tuple[str, ...]:
        """Return the stable GPD-owned artifacts that identify an install.

        Shared hook/runtime selection code should rely on this minimal contract
        so detection remains resilient even when runtime-private surfaces are
        partially missing or awaiting finalization.
        """
        return (MANIFEST_NAME, GPD_INSTALL_DIR_NAME)

    def missing_install_detection_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        """Return missing stable detection artifacts relative to *target_dir*."""
        missing: list[str] = []
        for relpath in self.install_detection_relpaths():
            if not (target_dir / relpath).exists():
                missing.append(relpath)
        return tuple(missing)

    def has_detectable_install(self, target_dir: Path) -> bool:
        """Return whether *target_dir* has the stable markers of a GPD install."""
        return not self.missing_install_detection_artifacts(target_dir)

    def install_completeness_relpaths(self) -> tuple[str, ...]:
        """Return relative artifacts required for a fully usable runtime install.

        The runtime CLI bridge and repair flows use this stricter contract.
        Adapters may extend it when their installed surface requires additional
        runtime-owned files.
        """
        return (
            *self.install_detection_relpaths(),
            *self.runtime_install_required_relpaths(),
        )

    def runtime_install_required_relpaths(self) -> tuple[str, ...]:
        """Return runtime-owned artifacts required for a complete install."""
        return ()

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        """Return missing strict install artifacts relative to *target_dir*."""
        missing: list[str] = []
        for relpath in self.install_completeness_relpaths():
            if not (target_dir / relpath).exists():
                missing.append(relpath)
        return tuple(missing)

    def install_verification_relpaths(self) -> tuple[str, ...]:
        """Return artifacts that must exist before ``install()`` can return.

        Most runtimes fully materialize their usable install surface during
        ``install()`` itself, so the install-time verification defaults to the
        same artifact contract the runtime bridge enforces later. Runtimes with
        an explicit post-install finalization step may override this to defer
        checks for artifacts that are only written during finalization.
        """
        return self.install_completeness_relpaths()

    def missing_install_verification_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        """Return missing artifacts for install-time verification."""
        missing: list[str] = []
        for relpath in self.install_verification_relpaths():
            if not (target_dir / relpath).exists():
                missing.append(relpath)
        return tuple(missing)

    def has_complete_install(self, target_dir: Path) -> bool:
        """Return whether *target_dir* satisfies the shared install contract."""
        return not self.missing_install_artifacts(target_dir)

    def validate_target_runtime(self, target_dir: Path, *, action: str) -> None:
        """Validate that an explicit target belongs to this runtime's install surface."""
        self._validate_target_runtime(target_dir, action=action)

    def _has_authoritative_install_manifest(self, target_dir: Path) -> bool:
        """Return whether *target_dir* has a trusted manifest for this runtime."""
        from gpd.hooks.install_metadata import assess_install_target

        assessment = assess_install_target(target_dir, expected_runtime=self.runtime_name)
        return assessment.manifest_state == "ok" and assessment.state in {"owned_complete", "owned_incomplete"}

    def _validate_target_runtime(self, target_dir: Path, *, action: str) -> None:
        """Internal runtime-ownership validation behind the public adapter contract."""
        from gpd.hooks.install_metadata import assess_install_target

        assessment = assess_install_target(target_dir, expected_runtime=self.runtime_name)
        explicit_target = getattr(self, "_install_explicit_target", False)
        if explicit_target and assessment.manifest_state in {"corrupt", "invalid"}:
            raise RuntimeError(
                f"Refusing to {action} `{target_dir}` because its GPD manifest cannot be trusted.\n"
                "Ownership cannot be determined safely."
            )
        if assessment.state == "foreign_runtime":
            other_runtime = assessment.manifest_runtime or "unknown"
            try:
                other_runtime_label = get_runtime_descriptor(other_runtime).display_name
            except KeyError:
                other_runtime_label = other_runtime
            raise RuntimeError(
                f"Refusing to {action} `{target_dir}`.\n"
                f'Its GPD manifest belongs to {other_runtime_label} (`{other_runtime}`), '
                f"not {self.display_name} (`{self.runtime_name}`)."
            )

        if assessment.state == "untrusted_manifest":
            if (
                action.startswith("uninstall")
                and assessment.manifest_state == "missing"
                and not _has_blocking_manifestless_install_surface(target_dir)
            ):
                return
            if action.startswith("install") and _has_only_agent_residue(target_dir):
                return
            if assessment.manifest_state != "missing":
                raise RuntimeError(
                    f"Refusing to {action} `{target_dir}` because its GPD manifest cannot be trusted.\n"
                    "Ownership cannot be determined safely."
                )
            if assessment.has_managed_markers:
                raise RuntimeError(
                    f"Refusing to {action} `{target_dir}` because it already contains GPD artifacts but no manifest to establish ownership."
                )
            raise RuntimeError(
                f"Refusing to {action} `{target_dir}` because its GPD manifest cannot be trusted.\n"
                "Ownership cannot be determined safely."
            )

    def runtime_cli_bridge_command(self, target_dir: Path) -> str:
        """Return the shared runtime CLI bridge command for installed shell calls."""
        return build_runtime_cli_bridge_command(
            self.runtime_name,
            target_dir=target_dir,
            config_dir_name=self.config_dir_name,
            is_global=getattr(self, "_install_is_global", False),
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

    def _read_install_manifest(self, target_dir: Path) -> dict[str, object]:
        """Return the install manifest payload for *target_dir* when present."""
        manifest_path = target_dir / MANIFEST_NAME
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _write_install_manifest_payload(self, target_dir: Path, manifest: dict[str, object]) -> None:
        """Persist a normalized install manifest payload."""
        manifest_path = target_dir / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def _runtime_permissions_manifest_state(self, target_dir: Path) -> dict[str, object] | None:
        """Return GPD-managed runtime-permission state from the install manifest."""
        state = self._read_install_manifest(target_dir).get("gpd_runtime_permissions")
        return state if isinstance(state, dict) else None

    def _set_runtime_permissions_manifest_state(
        self,
        target_dir: Path,
        state: dict[str, object] | None,
    ) -> None:
        """Update the install manifest with GPD-managed runtime-permission state."""
        manifest = self._read_install_manifest(target_dir)
        if not manifest:
            return
        if state:
            manifest["gpd_runtime_permissions"] = state
        else:
            manifest.pop("gpd_runtime_permissions", None)
        self._write_install_manifest_payload(target_dir, manifest)

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Return runtime-specific status for autonomy/prompt alignment.

        The default implementation reports that no runtime-owned sync surface is
        available. Adapters with documented approval/permission controls should
        override this method.
        """
        return {
            "runtime": self.runtime_name,
            "desired_mode": "yolo" if autonomy == "yolo" else "default",
            "configured_mode": "unsupported",
            "config_aligned": autonomy != "yolo",
            "requires_relaunch": False,
            "managed_by_gpd": False,
            "message": f"{self.display_name} does not expose a GPD runtime-permissions sync surface.",
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Align runtime-owned approval settings with the requested autonomy mode."""
        status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
        return {
            **status,
            "changed": False,
            "sync_applied": False,
        }

    # ---------------------------------------------------------------------------
    # Template method: install pipeline
    # ---------------------------------------------------------------------------

    def install(
        self,
        gpd_root: Path,
        target_dir: Path,
        *,
        is_global: bool = False,
        explicit_target: bool = False,
    ) -> dict[str, object]:
        """Install GPD into the target runtime configuration directory.

        Template method — calls hooks in standard order.  Subclasses override
        individual ``_install_*`` hooks for runtime-specific behavior.
        Override ``install()`` itself only when the signature must change.

        Args:
            gpd_root: Root of GPD package data (commands/, agents/, specs/, hooks/).
            target_dir: The runtime's config directory to install into.
            is_global: True for global (home-dir) installs, False for local.

        Returns:
            Summary dict with at minimum: runtime, commands, agents.
        """
        from gpd.core.observability import gpd_span
        from gpd.version import __version__, version_for_gpd_root

        with gpd_span("adapter.install", runtime=self.runtime_name, target=str(target_dir)) as span:
            previous_explicit_target = getattr(self, "_install_explicit_target", False)
            previous_is_global = getattr(self, "_install_is_global", False)
            self._install_explicit_target = explicit_target
            self._install_is_global = is_global
            try:
                self._validate(gpd_root)
                self._validate_target_runtime(target_dir, action="install into")
                path_prefix = self._compute_path_prefix(target_dir, is_global)
                self._pre_cleanup(target_dir)
                install_version = version_for_gpd_root(gpd_root) or __version__

                failures: list[str] = []
                command_count = self._install_commands(gpd_root, target_dir, path_prefix, failures)
                self._install_content(gpd_root, target_dir, path_prefix, failures)
                agent_count = self._install_agents(gpd_root, target_dir, path_prefix, failures)
                self._install_version(target_dir, install_version, failures)
                self._install_hooks(gpd_root, target_dir, failures)

                if failures:
                    span.set_attribute("gpd.install_failures", ", ".join(failures))
                    raise RuntimeError(f"Installation incomplete! Failed: {', '.join(failures)}")

                extra = self._configure_runtime(target_dir, is_global)
                self._write_manifest(target_dir, install_version)
                self._verify(target_dir)

                span.set_attribute("gpd.commands_count", command_count)
                span.set_attribute("gpd.agents_count", agent_count)
                logger.info(
                    "Installed GPD for %s: %d commands, %d agents",
                    self.runtime_name,
                    command_count,
                    agent_count,
                )

                summary: dict[str, object] = {
                    "runtime": self.runtime_name,
                    "target": str(target_dir),
                    "commands": command_count,
                    "agents": agent_count,
                }
                if extra:
                    summary.update(extra)
                return summary
            finally:
                self._install_explicit_target = previous_explicit_target
                self._install_is_global = previous_is_global

    # ---------------------------------------------------------------------------
    # Install hooks — override in subclasses for runtime-specific behavior
    # ---------------------------------------------------------------------------

    def _validate(self, gpd_root: Path) -> None:
        """Validate package integrity before install."""
        validate_package_integrity(gpd_root)

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        """Compute path prefix for placeholder replacement."""
        return compute_path_prefix(
            target_dir,
            self.config_dir_name,
            is_global=is_global,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

    def _pre_cleanup(self, target_dir: Path) -> None:
        """Clean up files from previous installations."""
        pre_install_cleanup(target_dir)

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        """Install commands in runtime-specific format.

        Appends to *failures* on error.  Returns the number of commands installed.
        """
        return 0

    def _install_content(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> None:
        """Install get-physics-done/ content from specs/."""
        failures.extend(
            install_gpd_content(
                gpd_root / "specs",
                target_dir,
                path_prefix,
                self.runtime_name,
                install_scope=self._current_install_scope_flag(),
                markdown_transform=self.translate_shared_markdown,
                explicit_target=getattr(self, "_install_explicit_target", False),
            )
        )

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        """Install agents in runtime-specific format.

        Appends to *failures* on error.  Returns the number of agents installed.
        """
        return 0

    def _install_version(self, target_dir: Path, version: str, failures: list[str]) -> None:
        """Write VERSION file into the runtime install root."""
        gpd_dest = target_dir / GPD_INSTALL_DIR_NAME
        failures.extend(write_version_file(gpd_dest, version))

    def _install_hooks(self, gpd_root: Path, target_dir: Path, failures: list[str]) -> None:
        """Copy hook scripts."""
        failures.extend(copy_hook_scripts(gpd_root, target_dir))

    def _current_install_scope_flag(self) -> str:
        """Return the active install scope as a bootstrap-friendly flag."""
        return "--global" if getattr(self, "_install_is_global", False) else "--local"

    def load_runtime_agents(self, gpd_root: Path) -> tuple[AgentDef, ...]:
        """Load runtime-projected agent metadata from an install source root."""
        from gpd.registry import load_agents_from_dir

        agents = load_agents_from_dir(gpd_root / "agents")
        projected = (self.project_agent_metadata(agent) for _, agent in sorted(agents.items()))
        return tuple(projected)

    def project_agent_metadata(self, agent: AgentDef) -> AgentDef:
        """Project canonical agent metadata into runtime-specific install policy."""
        return agent

    def should_install_agent_as_discoverable_surface(self, agent: AgentDef) -> bool:
        """Return whether an agent should be installed into discoverable skill surfaces."""
        return True

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        """Runtime-specific configuration (settings, permissions, etc.).

        Returns extra data to merge into the install summary dict.
        """
        return {}

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        """Write file manifest for modification detection."""
        write_manifest(
            target_dir,
            version,
            runtime=self.runtime_name,
            install_scope=self._current_install_scope_flag(),
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

    def _verify(self, target_dir: Path) -> None:  # noqa: B027
        """Post-install verification.  Override for runtime-specific checks."""
        missing = self.missing_install_verification_artifacts(target_dir)
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"{self.display_name} install incomplete: missing {joined}")

    def finalize_install(  # noqa: B027
        self,
        install_result: dict[str, object],
        *,
        force_statusline: bool = False,
    ) -> None:
        """Apply any runtime-specific post-install finalization."""

    def _cleanup_runtime_config(self, target_dir: Path) -> list[str]:
        """Remove runtime-managed config entries outside shared GPD files."""
        return []

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from the target runtime configuration directory.

        Default implementation removes common GPD directories and files.
        Override for runtime-specific cleanup.
        """
        import shutil

        from gpd.core.observability import gpd_span
        from gpd.hooks.install_metadata import assess_install_target

        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            assessment = assess_install_target(target_dir, expected_runtime=self.runtime_name)
            self._validate_target_runtime(target_dir, action="uninstall from")
            removed: list[str] = []

            # Remove nested commands/gpd/ directory
            gpd_commands = target_dir / COMMANDS_DIR_NAME / "gpd"
            if gpd_commands.is_dir():
                shutil.rmtree(gpd_commands)
                removed.append(f"{COMMANDS_DIR_NAME}/gpd/")

            # Remove flat command/ directory used by some runtimes.
            flat_commands = target_dir / FLAT_COMMANDS_DIR_NAME
            if flat_commands.is_dir():
                removed_flat_commands = _remove_gpd_flat_command_residue(flat_commands, stop_at=target_dir)
                if removed_flat_commands:
                    removed.append(f"{removed_flat_commands} flat GPD commands")

            # Remove the shared GPD install root.
            gpd_dir = target_dir / GPD_INSTALL_DIR_NAME
            if gpd_dir.is_dir():
                shutil.rmtree(gpd_dir)
                removed.append(f"{GPD_INSTALL_DIR_NAME}/")

            # Remove gpd-*.md agent files
            agents_dir = target_dir / AGENTS_DIR_NAME
            if agents_dir.is_dir():
                agent_count = 0
                for f in agents_dir.iterdir():
                    if f.name.startswith("gpd-") and f.suffix == ".md":
                        f.unlink()
                        agent_count += 1
                if agent_count:
                    removed.append(f"{agent_count} GPD agents")

            # Remove GPD hooks
            hooks_dir = target_dir / HOOKS_DIR_NAME
            if hooks_dir.is_dir():
                hook_count = 0
                for rel_path in sorted(managed_hook_paths(target_dir)):
                    hook_path = target_dir / rel_path
                    if hook_path.is_file():
                        hook_path.unlink()
                        hook_count += 1
                if hook_count:
                    removed.append(f"{hook_count} GPD hooks")

            # Remove GPD update cache files.
            cache_dir = target_dir / CACHE_DIR_NAME
            cache_paths = (
                cache_dir / UPDATE_CACHE_FILENAME,
                cache_dir / f"{UPDATE_CACHE_FILENAME}.inflight",
            )
            removed_cache = False
            for cache_path in cache_paths:
                if cache_path.is_file():
                    cache_path.unlink()
                    removed_cache = True
            if removed_cache:
                removed.append(f"{CACHE_DIR_NAME}/{UPDATE_CACHE_FILENAME}")

            if assessment.manifest_state == "ok":
                removed.extend(self._cleanup_runtime_config(target_dir))

            # Remove file manifest
            manifest = target_dir / MANIFEST_NAME
            if manifest.exists():
                manifest.unlink()
                removed.append(MANIFEST_NAME)

            # Remove local patches directory
            patches_dir = target_dir / PATCHES_DIR_NAME
            if patches_dir.is_dir():
                shutil.rmtree(patches_dir)
                removed.append(f"{PATCHES_DIR_NAME}/")

            for path in (
                target_dir / COMMANDS_DIR_NAME,
                target_dir / FLAT_COMMANDS_DIR_NAME,
                target_dir / AGENTS_DIR_NAME,
                target_dir / HOOKS_DIR_NAME,
                target_dir / CACHE_DIR_NAME,
                target_dir,
            ):
                prune_empty_ancestors(path, stop_at=target_dir.parent)

            span.set_attribute("gpd.removed_count", len(removed))
            logger.info("Uninstalled GPD from %s: removed %d items", self.runtime_name, len(removed))

            return {"runtime": self.runtime_name, "target": str(target_dir), "removed": removed}

    def resolve_target_dir(self, is_global: bool, cwd: Path | None = None) -> Path:
        """Resolve the target directory for install/uninstall.

        Args:
            is_global: If True, use global config dir. If False, use local (cwd-relative).
            cwd: Working directory for local installs. Defaults to os.getcwd().
        """
        if is_global:
            return self.resolve_global_config_dir()
        return self.resolve_local_config_dir(cwd)


__all__ = ["RuntimeAdapter"]
