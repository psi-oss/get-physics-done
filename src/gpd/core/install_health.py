"""Install health diagnostics and repair utilities.

Provides a structured health check for GPD runtime installs that can be
used both from the CLI (``gpd install-health``) and programmatically from
hooks. The :func:`check_install_health` function returns a detailed report
of what is present, what is missing, and whether auto-repair is possible.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class InstallHealthReport:
    """Structured report of an install's health."""

    config_dir: str
    runtime: str | None = None
    install_scope: str | None = None
    is_healthy: bool = False
    manifest_status: str = "unknown"
    missing_artifacts: list[str] = field(default_factory=list)
    present_artifacts: list[str] = field(default_factory=list)
    repair_command: str | None = None
    can_auto_repair: bool = False
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "config_dir": self.config_dir,
            "runtime": self.runtime,
            "install_scope": self.install_scope,
            "is_healthy": self.is_healthy,
            "manifest_status": self.manifest_status,
            "missing_artifacts": self.missing_artifacts,
            "present_artifacts": self.present_artifacts,
            "repair_command": self.repair_command,
            "can_auto_repair": self.can_auto_repair,
            "details": self.details,
        }


def check_install_health(
    config_dir: Path,
    *,
    verbose: bool = False,
) -> InstallHealthReport:
    """Check the health of a GPD install at the given config directory.

    Returns a structured report with details about what is present,
    what is missing, and how to repair.
    """
    from gpd.adapters.install_utils import GPD_INSTALL_DIR_NAME, MANIFEST_NAME
    from gpd.hooks.install_metadata import (
        install_scope_from_manifest,
        installed_update_command,
        load_install_manifest_runtime_status,
    )

    report = InstallHealthReport(config_dir=str(config_dir))

    # Check manifest.
    manifest_state, manifest, runtime = load_install_manifest_runtime_status(config_dir)
    report.manifest_status = manifest_state

    if manifest_state != "ok":
        report.missing_artifacts.append(MANIFEST_NAME)
        report.details["manifest_error"] = manifest_state
        return report

    report.runtime = runtime
    report.install_scope = install_scope_from_manifest(config_dir)
    report.repair_command = installed_update_command(config_dir)

    if runtime is None:
        report.missing_artifacts.append(f"{MANIFEST_NAME} (no runtime)")
        return report

    # Get the adapter and check artifacts.
    try:
        from gpd.adapters import get_adapter

        adapter = get_adapter(runtime)
    except KeyError:
        report.missing_artifacts.append(f"adapter:{runtime}")
        report.details["error"] = f"Unknown runtime: {runtime}"
        return report

    # Check all install artifacts.
    missing_artifacts = list(adapter.missing_install_artifacts(config_dir))
    completeness_relpaths = adapter.install_completeness_relpaths()
    for relpath in completeness_relpaths:
        if relpath in missing_artifacts:
            report.missing_artifacts.append(relpath)
        else:
            report.present_artifacts.append(relpath)

    # Extra checks for key surfaces.
    commands_dir = config_dir / "commands" / "gpd"
    if commands_dir.is_dir():
        command_count = sum(1 for f in commands_dir.rglob("*.md") if f.is_file())
        report.details["command_files"] = command_count
        if command_count == 0:
            report.missing_artifacts.append("commands/gpd (empty)")
    else:
        report.missing_artifacts.append("commands/gpd")

    agents_dir = config_dir / "agents"
    if agents_dir.is_dir():
        agent_count = sum(1 for f in agents_dir.iterdir() if f.is_file() and f.name.startswith("gpd-"))
        report.details["agent_files"] = agent_count
    else:
        report.details["agent_files"] = 0

    hooks_dir = config_dir / "hooks"
    if hooks_dir.is_dir():
        hook_count = sum(1 for f in hooks_dir.iterdir() if f.is_file() and f.suffix == ".py")
        report.details["hook_files"] = hook_count
    else:
        report.details["hook_files"] = 0

    gpd_content_dir = config_dir / GPD_INSTALL_DIR_NAME
    if gpd_content_dir.is_dir():
        report.details["content_dir_exists"] = True
    else:
        report.details["content_dir_exists"] = False

    # Check settings.json for hooks wiring.
    settings_path = config_dir / "settings.json"
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = settings.get("hooks", {})
            session_start = hooks.get("SessionStart", []) if isinstance(hooks, dict) else []
            report.details["session_start_hooks"] = len(session_start) if isinstance(session_start, list) else 0
            report.details["has_settings"] = True
        except (OSError, json.JSONDecodeError):
            report.details["has_settings"] = False
            report.details["settings_error"] = "corrupt"
    else:
        report.details["has_settings"] = False

    report.is_healthy = len(report.missing_artifacts) == 0

    # Can auto-repair if manifest is intact (we know the runtime and scope).
    report.can_auto_repair = (
        manifest_state == "ok"
        and runtime is not None
        and report.install_scope is not None
    )

    return report


def format_health_report(report: InstallHealthReport) -> str:
    """Format an install health report as a human-readable string."""
    lines: list[str] = []
    status = "HEALTHY" if report.is_healthy else "DAMAGED"
    lines.append(f"Install Status: {status}")
    lines.append(f"Config Dir: {report.config_dir}")

    if report.runtime:
        lines.append(f"Runtime: {report.runtime}")
    if report.install_scope:
        lines.append(f"Scope: {report.install_scope}")
    lines.append(f"Manifest: {report.manifest_status}")

    if report.present_artifacts:
        lines.append(f"Present: {', '.join(report.present_artifacts)}")
    if report.missing_artifacts:
        lines.append(f"Missing: {', '.join(report.missing_artifacts)}")

    for key, value in report.details.items():
        lines.append(f"  {key}: {value}")

    if not report.is_healthy and report.repair_command:
        lines.append(f"Repair: {report.repair_command}")
    elif not report.is_healthy:
        lines.append("Repair: npx -y get-physics-done")

    return "\n".join(lines)
