"""Base adapter ABC — defines the interface all runtime adapters must implement."""

from __future__ import annotations

import abc
import logging
import os
from pathlib import Path

from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    compute_path_prefix,
    copy_hook_scripts,
    install_gpd_content,
    pre_install_cleanup,
    validate_package_integrity,
    write_manifest,
    write_version_file,
)

logger = logging.getLogger(__name__)


class RuntimeAdapter(abc.ABC):
    """Abstract base for GPD runtime adapters.

    Each adapter knows how to install GPD content and runtime configuration
    for a specific AI agent (Claude Code, Codex, Gemini CLI, OpenCode).

    The ``install()`` method implements a **template method** pattern:
    ``_validate → _compute_path_prefix → _pre_cleanup → _install_commands →
    _install_content → _install_agents → _install_version → _install_hooks →
    _configure_runtime → _write_manifest → _verify``.
    Subclasses override individual ``_install_*`` hooks for runtime-specific
    behavior.  Override ``install()`` itself only when the signature must change
    (e.g. Codex ``skills_dir``).
    """

    @property
    @abc.abstractmethod
    def runtime_name(self) -> str:
        """Short identifier for this runtime (e.g. ``'claude-code'``)."""

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable runtime name (e.g. ``'Claude Code'``)."""

    @property
    @abc.abstractmethod
    def config_dir_name(self) -> str:
        """Name of the runtime's config directory (e.g. ``'.claude'``)."""

    @property
    def help_command(self) -> str:
        """Runtime-specific help command."""
        return self.format_command("help")

    @property
    def activation_env_vars(self) -> tuple[str, ...]:
        """Environment variables that signal this runtime is active."""
        return ()

    @property
    def local_config_dir_name(self) -> str:
        """Workspace-local config directory name for this runtime."""
        return self.config_dir_name

    @property
    def install_flag(self) -> str:
        """Bootstrap installer flag for this runtime."""
        return f"--{self.runtime_name}"

    @property
    def global_config_dir(self) -> Path:
        """Global config directory for this runtime.

        Default: ``~/.<config_dir_name>``. Override for runtimes with
        environment variable precedence chains (XDG, etc.).
        """
        return self.resolve_global_config_dir()

    def resolve_global_config_dir(self, *, home: Path | None = None) -> Path:
        """Resolve the runtime's global config dir."""
        return (home or Path.home()) / self.config_dir_name

    def resolve_local_config_dir(self, cwd: Path | None = None) -> Path:
        """Resolve the runtime's local config dir."""
        return Path(cwd or os.getcwd()) / self.local_config_dir_name

    def format_command(self, action: str) -> str:
        """Format a runtime-native GPD command."""
        return f"/gpd:{action}"

    @property
    def update_command(self) -> str:
        """Public bootstrap command that updates this runtime install."""
        base = "npx -y github:physicalsuperintelligence/get-physics-done"
        return f"{base} {self.install_flag}".strip()

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
        from gpd import __version__
        from gpd.core.observability import gpd_span

        with gpd_span("adapter.install", runtime=self.runtime_name, target=str(target_dir)) as span:
            previous_explicit_target = getattr(self, "_install_explicit_target", False)
            self._install_explicit_target = explicit_target
            try:
                self._validate(gpd_root)
                path_prefix = self._compute_path_prefix(target_dir, is_global)
                self._pre_cleanup(target_dir)

                failures: list[str] = []
                command_count = self._install_commands(gpd_root, target_dir, path_prefix, failures)
                self._install_content(gpd_root, target_dir, path_prefix, failures)
                agent_count = self._install_agents(gpd_root, target_dir, path_prefix, failures)
                self._install_version(target_dir, __version__, failures)
                self._install_hooks(gpd_root, target_dir, failures)

                if failures:
                    span.set_attribute("gpd.install_failures", ", ".join(failures))
                    raise RuntimeError(f"Installation incomplete! Failed: {', '.join(failures)}")

                extra = self._configure_runtime(target_dir, is_global)
                self._write_manifest(target_dir, __version__)
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
        failures.extend(install_gpd_content(gpd_root / "specs", target_dir, path_prefix, self.runtime_name))

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        """Install agents in runtime-specific format.

        Appends to *failures* on error.  Returns the number of agents installed.
        """
        return 0

    def _install_version(self, target_dir: Path, version: str, failures: list[str]) -> None:
        """Write VERSION file into get-physics-done/."""
        gpd_dest = target_dir / "get-physics-done"
        failures.extend(write_version_file(gpd_dest, version))

    def _install_hooks(self, gpd_root: Path, target_dir: Path, failures: list[str]) -> None:
        """Copy hook scripts."""
        failures.extend(copy_hook_scripts(gpd_root, target_dir))

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        """Runtime-specific configuration (settings, permissions, etc.).

        Returns extra data to merge into the install summary dict.
        """
        return {}

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        """Write file manifest for modification detection."""
        write_manifest(target_dir, version)

    def _verify(self, target_dir: Path) -> None:  # noqa: B027
        """Post-install verification.  Override for runtime-specific checks."""

    def finalize_install(
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

        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            removed: list[str] = []

            # Remove commands/gpd/ directory
            gpd_commands = target_dir / "commands" / "gpd"
            if gpd_commands.is_dir():
                shutil.rmtree(gpd_commands)
                removed.append("commands/gpd/")

            # Remove get-physics-done/ directory
            gpd_dir = target_dir / "get-physics-done"
            if gpd_dir.is_dir():
                shutil.rmtree(gpd_dir)
                removed.append("get-physics-done/")

            # Remove gpd-*.md agent files
            agents_dir = target_dir / "agents"
            if agents_dir.is_dir():
                agent_count = 0
                for f in agents_dir.iterdir():
                    if f.name.startswith("gpd-") and f.suffix == ".md":
                        f.unlink()
                        agent_count += 1
                if agent_count:
                    removed.append(f"{agent_count} GPD agents")

            # Remove GPD hooks
            hooks_dir = target_dir / "hooks"
            if hooks_dir.is_dir():
                hook_count = 0
                for hook_path in hooks_dir.iterdir():
                    if not hook_path.is_file():
                        continue
                    if hook_path.name in HOOK_SCRIPTS.values():
                        hook_path.unlink()
                        hook_count += 1
                if hook_count:
                    removed.append(f"{hook_count} GPD hooks")

            removed.extend(self._cleanup_runtime_config(target_dir))

            # Remove file manifest
            manifest = target_dir / "gpd-file-manifest.json"
            if manifest.exists():
                manifest.unlink()
                removed.append("gpd-file-manifest.json")

            # Remove local patches directory
            patches_dir = target_dir / "gpd-local-patches"
            if patches_dir.is_dir():
                shutil.rmtree(patches_dir)
                removed.append("gpd-local-patches/")

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
