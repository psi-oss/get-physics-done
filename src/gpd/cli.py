"""Unified GPD CLI — entry point for core workflow and MCP tooling.

Delegates to ``gpd.core.*`` modules for all command implementations.

Usage::

    gpd state load
    gpd phase list
    gpd health --fix
    gpd init execute-phase 42

All commands support ``--raw`` for JSON output and ``--cwd`` for working directory override.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import re
import sys
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.table import Table
from rich.text import Text

from gpd.adapters.base import INSTALL_ROLLBACK_RESULT_KEY as _INSTALL_RESULT_ROLLBACK_KEY
from gpd.adapters.runtime_catalog import list_runtime_names, normalize_runtime_name
from gpd.command_labels import canonical_command_label, validated_public_command_prefix
from gpd.core import artifact_writers as _artifact_writers
from gpd.core import install_cli_support as _install_cli_support
from gpd.core import install_readiness_support as _install_readiness_support
from gpd.core import permissions_cli_support as _permissions_cli_support
from gpd.core import recent_project_presentation as _recent_project_presentation
from gpd.core import resume_presentation as _resume_presentation
from gpd.core import runtime_targeting as _runtime_targeting
from gpd.core.artifact_command_payloads import (
    call_proof_redteam_finalizer as _call_proof_redteam_finalizer,
)
from gpd.core.artifact_command_payloads import (
    call_proof_redteam_skeleton_builder as _call_proof_redteam_skeleton_builder,
)
from gpd.core.artifact_command_payloads import (
    call_verification_report_finalizer as _call_verification_report_finalizer,
)
from gpd.core.artifact_command_payloads import (
    call_verification_report_skeleton_builder as _call_verification_report_skeleton_builder,
)
from gpd.core.artifact_command_payloads import (
    callable_accepts_kwarg as _callable_accepts_kwarg,
)
from gpd.core.artifact_command_payloads import (
    jsonable_value as _jsonable_value,
)
from gpd.core.artifact_command_payloads import (
    mapping_payload as _mapping_payload,
)
from gpd.core.artifact_command_payloads import (
    validation_result_is_valid as _validation_result_is_valid,
)
from gpd.core.artifact_text import (
    ArtifactTextError,
    load_artifact_text_surface,
    materialize_artifact_text_surface,
    probe_artifact_text_surface,
)
from gpd.core.cli_args import (
    normalize_root_global_cli_options as _normalize_root_global_cli_options,
)
from gpd.core.cli_args import (
    resolve_root_global_cli_cwd_from_argv as _resolve_root_global_cli_cwd_from_argv,
)
from gpd.core.cli_args import (
    split_root_global_cli_options as _split_root_global_cli_options,
)
from gpd.core.command_arguments import (
    _PROJECT_AWARE_EXPLICIT_INPUT_PREDICATES as _CORE_PROJECT_AWARE_EXPLICIT_INPUT_PREDICATES,
)
from gpd.core.command_preflight import (
    CommandContextPreflightResult,
    CommandLookupError,
    CommandRuntimeSurfaceMetadata,
    _publication_subject_preflight_policy,
    _review_preflight_publication_routing,
    build_command_lookup_error_payload,
    command_label_lookup_and_arguments,
    format_command_lookup_error,
)
from gpd.core.command_preflight import (
    build_command_context_preflight as _core_build_command_context_preflight,
)
from gpd.core.command_preflight import (
    command_preflight_cwd as _core_command_preflight_cwd,
)
from gpd.core.command_preflight import (
    resolve_registry_command as _core_resolve_registry_command,
)
from gpd.core.command_subjects import (
    ResolvedCommandSubject,
    _build_resolved_command_subject,
    _command_allows_manuscript_bootstrap,
    _command_effective_context_mode,
    _command_explicit_manuscript_argument,
    _command_explicit_manuscript_subject_uses_supported_roots,
    _command_explicit_manuscript_suffixes,
    _command_referee_report_arguments,
    _command_requires_compiled_manuscript,
    _command_supports_explicit_manuscript_subject,
    _resolve_review_knowledge_target,
    _resolve_review_preflight_manuscript,
    _resolve_subject_path,
    _supported_manuscript_root_for_target,
)
from gpd.core.constants import (
    CONFIG_FILENAME,
    ENV_DATA_DIR,
    ENV_GPD_DISABLE_CHECKOUT_REEXEC,
    HOME_DATA_DIR_NAME,
    PLANNING_DIR_NAME,
    PUBLICATION_DIR_NAME,
    PUBLICATION_MANUSCRIPT_DIR_NAME,
)
from gpd.core.errors import ConfigError, GPDError
from gpd.core.manuscript_artifacts import (
    locate_publication_artifact,
    resolve_current_manuscript_resolution,
)
from gpd.core.peer_review_mode import (
    PEER_REVIEW_PROJECT_BACKED_MODE,
    PeerReviewModeResolution,
    resolve_peer_review_mode_details,
)
from gpd.core.project_reentry import (
    ProjectReentryResolution,
    resolve_project_reentry,
)
from gpd.core.proof_review import (
    manuscript_requires_theorem_bearing_review,
    resolve_manuscript_proof_review_status,
    resolve_phase_proof_review_status,
)
from gpd.core.public_surface_contract import (
    local_cli_bridge_commands,
    local_cli_doctor_local_command,
    local_cli_install_local_example_command,
    local_cli_plan_preflight_command,
    local_cli_resume_command,
    local_cli_resume_recent_command,
    local_cli_validate_command_context_command,
)
from gpd.core.publication_review_paths import (
    manuscript_matches_review_artifact_path,
)
from gpd.core.publication_rounds import (
    PublicationResponseRoundArtifacts,
    PublicationReviewRoundArtifacts,
)
from gpd.core.publication_rounds import (
    publication_lineage_search_roots as _core_publication_lineage_search_roots,
)
from gpd.core.publication_rounds import (
    publication_response_round_path_maps as _core_publication_response_round_path_maps,
)
from gpd.core.publication_rounds import (
    publication_review_round_artifacts as _core_publication_review_round_artifacts,
)
from gpd.core.publication_rounds import (
    publication_review_round_path_maps as _core_publication_review_round_path_maps,
)
from gpd.core.publication_rounds import (
    resolve_latest_publication_response_round_artifacts as _core_resolve_latest_publication_response_round_artifacts,
)
from gpd.core.publication_rounds import (
    resolve_latest_publication_review_round_artifacts as _core_resolve_latest_publication_review_round_artifacts,
)
from gpd.core.publication_runtime import (
    publication_blockers_for_project,
    publication_response_freshness_status,
)
from gpd.core.recovery_advice import (
    RecoveryAdvice,
    build_recovery_advice,
    serialize_recovery_advice,
)
from gpd.core.resume_surface import (
    build_resume_presentation_lanes,
    canonicalize_resume_public_payload,
    lookup_resume_surface_value,
    resume_candidate_kind,
    resume_candidate_kind_from_source,
)
from gpd.core.root_resolution import RootResolutionPolicy, resolve_project_root
from gpd.core.runtime_command_surfaces import (
    format_active_runtime_command,
    resolve_active_runtime_descriptor,
)
from gpd.core.surface_phrases import (
    cost_inspect_action,
    recovery_action_lines,
    tangent_branch_later_follow_up_lines,
)
from gpd.core.utils import normalize_ascii_slug
from gpd.core.workflow_presets import (
    get_workflow_preset,
    list_workflow_presets,
    preview_workflow_preset_application,
)
from gpd.mcp.managed_integrations import WOLFRAM_MANAGED_INTEGRATION

if TYPE_CHECKING:
    from gpd.core.constants import ProjectLayout
    from gpd.core.health import UnattendedReadinessResult
    from gpd.mcp.paper.bibliography import CitationSource
    from gpd.mcp.paper.models import PaperConfig
    from gpd.registry import ReviewContractConditionalRequirement

# ─── Output helpers ─────────────────────────────────────────────────────────

# On Windows, Rich Console emits Unicode characters (em-dash, arrows) that
# cp1252 cannot encode. Reconfigure stdout/stderr to UTF-8 before Console
# objects are created so both CLI and test imports benefit.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass

console = Console()
err_console = Console(stderr=True)
logger = logging.getLogger(__name__)

# Global state threaded through typer context
_raw: bool = False
_cwd: Path = Path(".")
_PROJECT_AWARE_EXPLICIT_INPUT_PREDICATES = _CORE_PROJECT_AWARE_EXPLICIT_INPUT_PREDICATES


def _emit_raw_json(data: object, *, err: bool = False) -> None:
    """Emit literal JSON without Rich syntax styling."""
    typer.echo(json.dumps(data, default=str, indent=2), err=err)


def _output(data: object) -> None:
    """Print result — JSON when --raw, rich text otherwise."""
    if _raw:
        if data is None:
            _emit_raw_json({"result": None})
        elif isinstance(data, (list, tuple)):
            items = [
                item.model_dump(mode="json", by_alias=True)
                if hasattr(item, "model_dump")
                else dataclasses.asdict(item)
                if dataclasses.is_dataclass(item) and not isinstance(item, type)
                else item
                for item in data
            ]
            _emit_raw_json(items)
        elif hasattr(data, "model_dump"):
            _emit_raw_json(data.model_dump(mode="json", by_alias=True))
        elif dataclasses.is_dataclass(data) and not isinstance(data, type):
            _emit_raw_json(dataclasses.asdict(data))
        elif isinstance(data, dict):
            _emit_raw_json(data)
        else:
            _emit_raw_json({"result": str(data)})
    else:
        if data is None:
            return  # nothing to display
        elif isinstance(data, (list, tuple)):
            for item in data:
                _output(item)
        elif hasattr(data, "model_dump"):
            _pretty_print(data.model_dump(mode="json", by_alias=True))
        elif dataclasses.is_dataclass(data) and not isinstance(data, type):
            _pretty_print(dataclasses.asdict(data))
        elif isinstance(data, dict):
            _pretty_print(data)
        else:
            console.print(str(data), highlight=False)


def _stdout_is_interactive() -> bool:
    stream = getattr(sys, "stdout", None)
    if stream is None:
        return False
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _pretty_print(d: dict) -> None:
    """Render a dict as a rich table."""
    table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    table.add_column("Key")
    table.add_column("Value")
    for k, v in d.items():
        if k == "failure_reasons" and isinstance(v, dict):
            # Render each failure reason as its own row for readability
            for fk, fv in v.items():
                table.add_row(Text(f"  reason: {fk}"), Text(str(fv)))
        elif isinstance(v, (dict, list)):
            val = json.dumps(v, default=str)
            table.add_row(Text(str(k)), Text(val))
        else:
            table.add_row(Text(str(k)), Text(str(v)))
    console.print(table)


def _error(msg: str) -> NoReturn:
    """Print error and exit — JSON when --raw, rich text otherwise."""
    if _raw:
        _emit_raw_json({"error": str(msg)}, err=True)
    else:
        err_console.print(f"[bold red]Error:[/] {msg}", highlight=False)
    raise typer.Exit(code=1)


def _get_cwd() -> Path:
    return _cwd.resolve()


def _resolve_path_from_effective_cwd(path_text: str) -> Path:
    """Resolve a CLI path argument against the effective global ``--cwd``."""

    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = _get_cwd() / path
    return path.resolve(strict=False)


def _migrate_planning_files(cwd: Path) -> None:
    """Auto-migrate ROADMAP.md / PROJECT.md from root into GPD/ if needed."""
    from gpd.core.project_files import migrate_root_planning_files

    migrate_root_planning_files(cwd)


def _status_command_reentry(cwd: Path | None = None) -> ProjectReentryResolution:
    """Resolve the shared re-entry contract for recovery/status commands."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    return resolve_project_reentry(workspace_cwd)


def _status_command_cwd(cwd: Path | None = None) -> Path:
    """Resolve the effective cwd for read-only status/recovery commands."""
    resolution = _status_command_reentry(cwd)
    if resolution.resolved_project_root is not None:
        return resolution.resolved_project_root
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    return workspace_cwd


def _progress_command_cwd(cwd: Path | None = None) -> Path:
    """Resolve the effective cwd for progress/recovery commands."""

    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    if resolve_project_root(workspace_cwd, require_layout=True) is None:
        resolution = _status_command_reentry(workspace_cwd)
        if resolution.resolved_project_root is not None:
            return resolution.resolved_project_root
        return workspace_cwd
    return _status_command_cwd(workspace_cwd)


def _state_command_cwd(cwd: Path | None = None) -> Path:
    """Resolve the effective cwd for state and project-contract commands."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    resolved = _project_anchor_cwd(workspace_cwd)
    if resolved is not None:
        _migrate_planning_files(resolved)
        return resolved
    _migrate_planning_files(workspace_cwd)
    resolved = _project_anchor_cwd(workspace_cwd)
    if resolved is not None:
        return resolved
    return workspace_cwd


def _project_anchor_cwd(cwd: Path | None = None) -> Path | None:
    """Return the nearest visible ``GPD/`` anchor without requiring a complete layout."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    resolved = resolve_project_root(workspace_cwd)
    if resolved is None or not (resolved / PLANNING_DIR_NAME).is_dir():
        return None
    return resolved


def _read_only_project_scoped_cwd(cwd: Path | None = None) -> Path:
    """Resolve a project root for read-only commands without migration writes."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    resolved = _project_anchor_cwd(workspace_cwd)
    return resolved if resolved is not None else workspace_cwd


def _read_only_marker_backed_project_scoped_cwd(cwd: Path | None = None) -> Path:
    """Resolve only marker-backed project roots for read-only validation probes."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    resolved = resolve_project_root(workspace_cwd, require_layout=True)
    return resolved if resolved is not None else workspace_cwd


def _config_project_scoped_cwd(cwd: Path | None = None) -> Path:
    """Resolve the nearest canonical project root for config files without migration writes."""
    from gpd.core.constants import REQUIRED_PLANNING_DIRS, REQUIRED_PLANNING_FILES

    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    config_only_candidate: Path | None = None
    for candidate in (workspace_cwd, *workspace_cwd.parents):
        planning_dir = candidate / PLANNING_DIR_NAME
        if not planning_dir.is_dir():
            if (candidate / ".git").exists() or (candidate / ".hg").exists():
                break
            continue
        if any((planning_dir / name).exists() for name in REQUIRED_PLANNING_FILES) or any(
            (planning_dir / name).is_dir() for name in REQUIRED_PLANNING_DIRS
        ):
            return candidate
        if config_only_candidate is None and (planning_dir / CONFIG_FILENAME).exists():
            config_only_candidate = candidate
        if (candidate / ".git").exists() or (candidate / ".hg").exists():
            break
    if config_only_candidate is not None:
        return config_only_candidate
    resolved = resolve_project_root(workspace_cwd, require_layout=True)
    return resolved if resolved is not None else workspace_cwd


def _project_scoped_cwd(cwd: Path | None = None) -> Path:
    """Resolve the nearest project-owned ``GPD/`` anchor for project-scoped preflights."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    resolved = _project_anchor_cwd(workspace_cwd)
    if resolved is not None:
        _migrate_planning_files(resolved)
        return resolved
    _migrate_planning_files(workspace_cwd)
    resolved = _project_anchor_cwd(workspace_cwd)
    return resolved if resolved is not None else workspace_cwd


def _resolve_return_file_path(file_path: str, *, launch_cwd: Path, project_root: Path) -> Path:
    """Resolve a child-return file path using CLI launch cwd before project root."""
    raw_path = Path(file_path).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve(strict=False)

    launch_candidate = (launch_cwd / raw_path).resolve(strict=False)
    project_candidate = (project_root / raw_path).resolve(strict=False)
    for candidate in (launch_candidate, project_candidate):
        if candidate.exists():
            return candidate
    return launch_candidate


def _workspace_locked_cwd(cwd: Path | None = None) -> Path:
    """Resolve the effective cwd without walking up to an ancestor project root."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    ancestor_root = resolve_project_root(workspace_cwd, require_layout=True)
    if ancestor_root is not None and ancestor_root != workspace_cwd:
        return workspace_cwd
    _migrate_planning_files(workspace_cwd)
    resolved = resolve_project_root(
        workspace_cwd,
        require_layout=True,
        policy=RootResolutionPolicy.WORKSPACE_LOCKED,
    )
    return resolved if resolved is not None else workspace_cwd


def _split_global_cli_options(argv: list[str]) -> tuple[list[str], list[str]]:
    """Partition root-global CLI options from the rest of the argv stream."""
    return _split_root_global_cli_options(argv)


def _normalize_global_cli_options(argv: list[str]) -> list[str]:
    """Move root-global options to the front of the argv stream."""
    return _normalize_root_global_cli_options(argv)


def _resolve_cli_cwd_from_argv(argv: list[str]) -> Path:
    """Resolve the effective CLI cwd from raw argv before Typer parses it."""
    return _resolve_root_global_cli_cwd_from_argv(argv)


def _maybe_reexec_from_checkout(argv: list[str] | None = None) -> None:
    """Re-exec through the nearest checkout when launched from an installed package."""
    from gpd.version import checkout_root, current_python_executable, resolve_checkout_python

    if os.environ.get(ENV_GPD_DISABLE_CHECKOUT_REEXEC) == "1":
        return

    effective_argv = list(sys.argv[1:] if argv is None else argv)
    root = checkout_root(_resolve_cli_cwd_from_argv(effective_argv))
    if root is None:
        return

    checkout_gpd = (root / "src" / "gpd").resolve(strict=False)
    active_gpd = Path(__file__).resolve().parent
    if active_gpd == checkout_gpd:
        return

    env = os.environ.copy()
    checkout_src = str((root / "src").resolve(strict=False))
    existing_pythonpath = [entry for entry in env.get("PYTHONPATH", "").split(os.pathsep) if entry]
    if checkout_src not in existing_pythonpath:
        env["PYTHONPATH"] = (
            os.pathsep.join([checkout_src, *existing_pythonpath]) if existing_pythonpath else checkout_src
        )
    env[ENV_GPD_DISABLE_CHECKOUT_REEXEC] = "1"
    active_python = current_python_executable()
    checkout_python = resolve_checkout_python(root, fallback=active_python) or active_python
    if checkout_python is None:
        return
    os.execve(checkout_python, [checkout_python, "-m", "gpd.cli", *effective_argv], env)


def _format_display_path(target: str | Path | None) -> str:
    """Format a path for concise, user-facing CLI output."""
    if target is None:
        return ""

    raw_target = str(target)
    if not raw_target:
        return ""

    target_path = Path(raw_target).expanduser()
    if not target_path.is_absolute():
        target_path = _get_cwd() / target_path

    try:
        resolved_target = target_path.resolve(strict=False)
    except OSError:
        return target_path.as_posix()
    try:
        resolved_cwd = _get_cwd().expanduser().resolve(strict=False)
    except OSError:
        resolved_cwd = _get_cwd().expanduser()
    try:
        resolved_home = Path.home().expanduser().resolve(strict=False)
    except OSError:
        return resolved_target.as_posix()

    try:
        relative_to_cwd = resolved_target.relative_to(resolved_cwd)
    except ValueError:
        pass
    else:
        relative_text = relative_to_cwd.as_posix()
        return "." if relative_text in ("", ".") else f"./{relative_text}"

    try:
        relative_to_home = resolved_target.relative_to(resolved_home)
    except ValueError:
        return resolved_target.as_posix()

    relative_text = relative_to_home.as_posix()
    return "~" if relative_text in ("", ".") else f"~/{relative_text}"


def _format_display_path_from_cwd(target: str | Path | None, *, cwd: Path) -> str:
    """Format a path relative to a specific cwd, even when the path is a sibling or ancestor."""
    if target is None:
        return ""

    raw_target = str(target)
    if not raw_target:
        return ""

    target_path = Path(raw_target).expanduser()
    if not target_path.is_absolute():
        target_path = cwd.expanduser() / target_path

    try:
        resolved_target = target_path.resolve(strict=False)
    except OSError:
        return target_path.as_posix()
    try:
        resolved_cwd = cwd.expanduser().resolve(strict=False)
    except OSError:
        resolved_cwd = cwd.expanduser()

    try:
        relative = resolved_target.relative_to(resolved_cwd)
    except ValueError:
        if resolved_target.anchor and resolved_target.anchor == resolved_cwd.anchor:
            relative_text = os.path.relpath(resolved_target, resolved_cwd)
            return "." if relative_text in ("", ".") else Path(relative_text).as_posix()
        return _format_display_path(resolved_target)

    relative_text = relative.as_posix()
    return "." if relative_text in ("", ".") else f"./{relative_text}"


@dataclasses.dataclass(frozen=True)
class ReviewPreflightCheck:
    """One executable preflight check for a review command."""

    name: str
    passed: bool
    blocking: bool
    detail: str


@dataclasses.dataclass(frozen=True)
class ReviewPreflightResult:
    """Summary of preflight readiness for a review-grade command."""

    command: str
    review_mode: str
    strict: bool
    passed: bool
    checks: list[ReviewPreflightCheck]
    required_outputs: list[str]
    required_evidence: list[str]
    blocking_conditions: list[str]
    conditional_requirements: list[ReviewContractConditionalRequirement]
    active_conditional_requirements: list[ReviewContractConditionalRequirement]
    effective_required_evidence: list[str]
    effective_blocking_conditions: list[str]
    resolved_mode: str = ""
    mode_reason: str = ""
    validated_surface: str = "public_runtime_command_surface"
    public_runtime_command_prefix: str = ""
    local_cli_equivalence_guaranteed: bool = False
    dispatch_note: str = ""
    resolved_subject: ResolvedCommandSubject | None = None
    publication_subject_slug: str | None = None
    publication_lane_kind: str | None = None
    managed_publication_root: str | None = None
    selected_publication_root: str | None = None
    selected_review_root: str | None = None
    manuscript_root: str | None = None
    manuscript_entrypoint: str | None = None


def _format_runtime_list(runtime_names: list[str]) -> str:
    """Render runtime identifiers as human-friendly names."""
    display_names = [
        _get_adapter_or_error(runtime_name, action="runtime formatting").display_name for runtime_name in runtime_names
    ]
    if not display_names:
        return "no runtimes"
    if len(display_names) == 1:
        return display_names[0]
    if len(display_names) == 2:
        return f"{display_names[0]} and {display_names[1]}"
    return f"{', '.join(display_names[:-1])}, and {display_names[-1]}"


def _supported_runtime_names() -> list[str]:
    """Return runtime ids from the loaded adapter registry."""
    from gpd.adapters import list_runtimes

    try:
        return list_runtimes()
    except RuntimeError:
        return []


def _runtime_override_help() -> str:
    """Build runtime option help from adapter metadata."""
    supported = _supported_runtime_names()
    if not supported:
        return "Runtime name override"
    return f"Runtime name override ({', '.join(supported)})"


def _list_runtimes_or_error(*, action: str) -> list[str]:
    """Return supported runtime ids or emit a stable CLI error."""
    from gpd.adapters import list_runtimes

    try:
        return list_runtimes()
    except Exception as exc:
        _error(f"Runtime catalog unavailable during {action}: {exc}")
        return []  # unreachable


def _get_adapter_or_error(runtime_name: str, *, action: str):
    """Return a runtime adapter or emit a stable CLI error."""
    from gpd.adapters import get_adapter

    try:
        return get_adapter(runtime_name)
    except KeyError:
        supported = _supported_runtime_names()
        supported_suffix = f" Supported: {', '.join(supported)}" if supported else ""
        _error(f"Unknown runtime {runtime_name!r}.{supported_suffix}")
        return None  # unreachable
    except Exception as exc:
        _error(f"Runtime adapter unavailable for {runtime_name!r} during {action}: {exc}")
        return None  # unreachable


def _normalize_runtime_selection(runtimes: list[str], *, action: str) -> list[str]:
    """Resolve runtime aliases to canonical runtime ids for non-interactive flows."""
    supported = _list_runtimes_or_error(action=action)
    supported_set = set(supported)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_runtime in runtimes:
        canonical_runtime = normalize_runtime_name(raw_runtime) or raw_runtime.strip()
        if canonical_runtime not in supported_set:
            _error(f"Unknown runtime {raw_runtime!r}. Supported: {', '.join(supported)}")
        if canonical_runtime in seen:
            continue
        seen.add(canonical_runtime)
        normalized.append(canonical_runtime)
    return normalized


def _print_version(*, ctx: typer.Context | None = None) -> None:
    """Emit the CLI version using the active raw/non-raw output contract."""
    from gpd.version import resolve_active_version

    cwd = _get_cwd()
    if ctx is not None:
        raw_cwd = ctx.params.get("cwd")
        if isinstance(raw_cwd, str) and raw_cwd.strip():
            cwd = Path(raw_cwd)

    value = f"gpd {resolve_active_version(cwd)}"
    raw_requested = False
    if ctx is not None:
        meta_raw = ctx.meta.get("raw_requested")
        if isinstance(meta_raw, bool):
            raw_requested = meta_raw
    if not raw_requested:
        raw_requested = _raw
    if raw_requested:
        _emit_raw_json({"result": value})
    else:
        console.print(value, highlight=False)


def _raw_option_callback(ctx: typer.Context, _: typer.CallbackParam, value: bool) -> bool:
    """Capture --raw early enough for the eager --version option."""
    global _raw  # noqa: PLW0603
    ctx.meta["raw_requested"] = value
    _raw = value
    return value


def _version_option_callback(ctx: typer.Context, _: typer.CallbackParam, value: bool) -> bool:
    """Handle --version before Typer requires a subcommand."""
    if value:
        _print_version(ctx=ctx)
        raise typer.Exit()
    return value


def _json_cli_output(data: object) -> None:
    """Emit literal JSON for the lightweight JSON subcommands."""
    if _raw:
        _emit_raw_json(data)
    else:
        console.print(data, highlight=False)


def _format_pydantic_schema_error(error: dict[str, object], *, root_label: str) -> str:
    """Return a concise, user-facing schema error."""

    location = ".".join(str(part) for part in error.get("loc", ()) if str(part))
    label = f"{root_label}.{location}" if location else root_label
    message = str(error.get("msg", "validation failed")).strip() or "validation failed"
    input_value = error.get("input")

    if message == "Field required":
        return f"{label} is required"
    if "valid dictionary" in message.lower():
        return f"{label} must be an object, not {type(input_value).__name__}"
    if "valid list" in message.lower():
        return f"{label} must be an array, not {type(input_value).__name__}"
    return f"{label}: {message}"


def _raise_pydantic_schema_error(
    *,
    label: str,
    exc: PydanticValidationError,
    schema_reference: str | None = None,
) -> NoReturn:
    """Render Pydantic payload errors without a traceback and exit."""

    rendered: list[str] = []
    seen: set[str] = set()
    for error in exc.errors():
        formatted = _format_pydantic_schema_error(error, root_label=label)
        if formatted in seen:
            continue
        seen.add(formatted)
        rendered.append(formatted)

    message = "; ".join(rendered[:5]) or f"{label} validation failed"
    if len(rendered) > 5:
        message += f" (+{len(rendered) - 5} more)"
    if schema_reference:
        message += f". See `{schema_reference}`"
    _error(message)


def _model_dump_with_schema_reference(result: object, *, schema_reference: str) -> dict[str, object]:
    """Return a JSON-serializable validation payload with schema guidance attached."""

    if hasattr(result, "model_dump"):
        payload = result.model_dump(mode="json")
    elif dataclasses.is_dataclass(result):
        payload = dataclasses.asdict(result)
    elif isinstance(result, dict):
        payload = dict(result)
    else:
        payload = {"result": result}

    payload["schema_reference"] = schema_reference
    return payload


def _prefer_anchored_project_contract_validation(anchored_result: object, unanchored_result: object) -> bool:
    """Return whether the anchored validation is more specific than the generic fallback."""

    anchored_valid = getattr(anchored_result, "valid", None)
    unanchored_valid = getattr(unanchored_result, "valid", None)
    if anchored_valid != unanchored_valid:
        return True

    anchored_errors = getattr(anchored_result, "errors", None)
    unanchored_errors = getattr(unanchored_result, "errors", None)
    if anchored_errors != unanchored_errors:
        return True

    anchored_warnings = getattr(anchored_result, "warnings", None)
    unanchored_warnings = getattr(unanchored_result, "warnings", None)
    return anchored_warnings != unanchored_warnings


def _collect_file_option_args(ctx: typer.Context, files: list[str] | None) -> list[str]:
    """Return normalized file args, allowing multiple paths after one ``--files``."""

    normalized_files = list(files or [])
    extra_args = [str(arg).strip() for arg in ctx.args if str(arg).strip()]
    if not extra_args:
        return normalized_files

    unexpected_options = [arg for arg in extra_args if arg.startswith("-")]
    if unexpected_options:
        _error("Unexpected option(s): " + " ".join(unexpected_options))

    if files is None:
        _error("Unexpected extra arguments. If these are file paths, pass them after --files.")

    normalized_files.extend(extra_args)
    return normalized_files


def _emit_observability_event(
    cwd: Path,
    *,
    category: str,
    name: str,
    action: str = "log",
    status: str = "ok",
    command: str | None = None,
    phase: str | None = None,
    plan: str | None = None,
    session_id: str | None = None,
    data: dict[str, object] | None = None,
    end_session: bool = False,
) -> object:
    from gpd.core.observability import observe_event

    result = observe_event(
        cwd.resolve(strict=False),
        category=category,
        name=name,
        action=action,
        status=status,
        command=command,
        phase=phase,
        plan=plan,
        session_id=session_id,
        data=data,
        end_session=end_session,
    )
    if hasattr(result, "recorded") and result.recorded is False:
        raise GPDError("Local observability unavailable for this working directory")
    return result


def _filter_observability_events(
    cwd: Path,
    *,
    session: str | None = None,
    category: str | None = None,
    name: str | None = None,
    action: str | None = None,
    status: str | None = None,
    command: str | None = None,
    phase: str | None = None,
    plan: str | None = None,
    last: int | None = None,
) -> dict[str, object]:
    from gpd.core.observability import show_events

    return show_events(
        cwd,
        session=session,
        category=category,
        name=name,
        action=action,
        status=status,
        command=command,
        phase=phase,
        plan=plan,
        last=last,
    ).model_dump(mode="json")


def _filter_observability_sessions(
    cwd: Path,
    *,
    status: str | None = None,
    command: str | None = None,
    last: int | None = None,
) -> dict[str, object]:
    from gpd.core.observability import list_sessions

    sessions = list_sessions(cwd, command=command, last=last).model_dump(mode="json")
    if status:
        filtered = [session_info for session_info in sessions["sessions"] if str(session_info.get("status")) == status]
        return {"count": len(filtered), "sessions": filtered}
    return sessions


# ─── App setup ──────────────────────────────────────────────────────────────


class _GPDTyper(typer.Typer):
    """Typer subclass that catches GPDError and prints a user-friendly message."""

    def __call__(self, *args: object, **kwargs: object) -> object:
        global _raw, _cwd  # noqa: PLW0603
        _raw = False
        _cwd = Path(".")
        normalized_kwargs = dict(kwargs)
        raw_args = normalized_kwargs.get("args")
        if raw_args is None and not args:
            raw_args = sys.argv[1:]
        if raw_args is not None:
            normalized_kwargs["args"] = _normalize_global_cli_options([str(arg) for arg in raw_args])
        try:
            return super().__call__(*args, **normalized_kwargs)
        except KeyError as exc:
            msg = f"Internal error (missing key): {exc}"
            if _raw:
                _emit_raw_json({"error": msg}, err=True)
            else:
                err_console.print(f"[bold red]Error:[/] {msg}", highlight=False)
            raise SystemExit(1) from None
        except GPDError as exc:
            if _raw:
                _emit_raw_json({"error": str(exc)}, err=True)
            else:
                err_console.print(f"[bold red]Error:[/] {exc}", highlight=False)
            raise SystemExit(1) from None
        except TimeoutError as exc:
            if _raw:
                _emit_raw_json({"error": str(exc)}, err=True)
            else:
                err_console.print(f"[bold red]Error:[/] {exc}", highlight=False)
            raise SystemExit(1) from None
        except SystemExit:
            raise
        except Exception:
            raise


def _cli_epilog() -> str:
    return (
        "Primary research workflow commands run inside an installed runtime surface, not the local `gpd` CLI.\n"
        f"Use `{local_cli_install_local_example_command()}` to install GPD, then open that runtime and run its GPD help command there.\n\n"
        "Use the local CLI for install, readiness checks, permissions, observability, validation, and diagnostics.\n"
        "Examples:\n"
        f"  {local_cli_install_local_example_command()}\n"
        f"  {local_cli_doctor_local_command()}\n"
        + "".join(f"  {command}\n" for command in local_cli_bridge_commands())
        + f"  {local_cli_validate_command_context_command()}"
    )


app = _GPDTyper(
    name="gpd",
    help="GPD local bridge: local install, readiness, validation, permissions, observability, recovery, cost, presets, diagnostics, and shared Wolfram integration CLI",
    no_args_is_help=True,
    add_completion=True,
    epilog=_cli_epilog(),
)


@app.callback()
def main(
    _ctx: typer.Context,
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Output raw JSON for programmatic consumption",
        callback=_raw_option_callback,
        is_eager=True,
    ),
    cwd: str = typer.Option(".", "--cwd", help="Working directory (default: current)"),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version",
        callback=_version_option_callback,
        is_eager=True,
    ),
) -> None:
    """GPD — Get Physics Done."""
    global _raw, _cwd  # noqa: PLW0603
    _raw = raw
    _cwd = Path(cwd)


@app.command("help")
def help_bridge(
    command_name: str | None = typer.Option(
        None,
        "--command",
        help="Runtime command slug or label to inspect, for example new-project or gpd:new-project",
    ),
    all_commands: bool = typer.Option(False, "--all", help="Include the compact command index"),
    minimal: bool = typer.Option(False, "--minimal", help="Return the minimal command-specific payload"),
) -> None:
    """Machine-readable bridge for the installed runtime help surface."""
    from gpd.core.help_renderer import (
        DETAILED_HELP_FOLLOW_UP,
        command_detail_payload,
        command_groups_payload,
        command_index_payload,
        format_detailed_help_follow_up,
        format_help_all_command,
        render_command_detail_markdown,
        render_command_index_markdown,
        render_default_help_markdown,
        render_quick_start_markdown,
    )

    runtime_cwd = _get_cwd()
    runtime_surface = _command_runtime_surface_metadata(cwd=runtime_cwd)
    active_public_prefix = runtime_surface.public_runtime_command_prefix
    public_prefix = active_public_prefix or "gpd:"
    canonical_default_help_markdown = render_default_help_markdown()
    default_help_markdown = render_default_help_markdown(public_prefix=public_prefix)
    canonical_quick_start_markdown = render_quick_start_markdown()
    quick_start_markdown = render_quick_start_markdown(public_prefix=public_prefix)
    canonical_command_index_markdown = render_command_index_markdown()
    command_index_markdown = render_command_index_markdown(public_prefix=public_prefix)
    payload: dict[str, object] = {
        "command": "gpd:help",
        "surface": "local_cli_raw_help_bridge",
        "validated_surface": runtime_surface.validated_surface,
        "public_runtime_command_prefix": active_public_prefix,
        "local_cli_equivalence_guaranteed": False,
        "dispatch_note": (
            "Runtime commands are installed into configured agent surfaces; "
            "this local bridge exposes registry metadata for automation."
        ),
        "default_sections": ["quick_start_extract", "wrapper_owned_all_hint"],
        "quick_start": {
            "heading": "Quick Start",
            "markdown": default_help_markdown,
            "canonical_markdown": canonical_default_help_markdown,
        },
        "recommended_commands": [format_help_all_command(public_prefix=public_prefix)],
        "canonical_recommended_commands": ["gpd:help --all"],
        "read_only": True,
    }
    if command_name:
        canonical = canonical_command_label(command_name)
        try:
            detail_payload = command_detail_payload(canonical, minimal=minimal, include_markdown=True)
        except KeyError:
            lookup_payload = build_command_lookup_error_payload(
                command_name,
                runtime_surface_metadata=runtime_surface,
            )
            payload.update(dataclasses.asdict(lookup_payload))
            _output(payload)
            raise typer.Exit(code=1) from None
        canonical_detail_markdown = detail_payload.get("detail_markdown")
        detail_payload["detail_markdown"] = render_command_detail_markdown(canonical, public_prefix=public_prefix)
        if isinstance(canonical_detail_markdown, str):
            detail_payload["canonical_detail_markdown"] = canonical_detail_markdown
        preflight = _build_command_context_preflight(canonical)
        preflight_payload = dataclasses.asdict(preflight) if dataclasses.is_dataclass(preflight) else preflight
        payload.update(
            {
                "ok": True,
                "requested_command": command_name,
                **detail_payload,
                "command_context": preflight_payload,
            }
        )
    elif all_commands:
        payload.update(
            {
                "ok": True,
                "rendered_sections": ["quick_start", "command_index", "detailed_help_follow_up"],
                "quick_start": {
                    "heading": "Quick Start",
                    "markdown": quick_start_markdown,
                    "canonical_markdown": canonical_quick_start_markdown,
                },
                "command_index_markdown": command_index_markdown,
                "canonical_command_index_markdown": canonical_command_index_markdown,
                "command_groups": command_groups_payload(),
                "detailed_help_follow_up": format_detailed_help_follow_up(public_prefix=public_prefix),
                "canonical_detailed_help_follow_up": DETAILED_HELP_FOLLOW_UP,
                "command_index": command_index_payload(),
            }
        )
    else:
        payload["ok"] = True
    _output(payload)


# ═══════════════════════════════════════════════════════════════════════════
# state — STATE.md and state.json management
# ═══════════════════════════════════════════════════════════════════════════

state_app = typer.Typer(help="State management (STATE.md + state.json)")
app.add_typer(state_app, name="state")


@state_app.command("load")
def state_load() -> None:
    """Load and display current research state."""
    from gpd.core.state import state_load_readonly

    _output(state_load_readonly(_read_only_project_scoped_cwd()))


@state_app.command("get")
def state_get(
    section: str | None = typer.Argument(None, help="State section to retrieve"),
    include: str | None = typer.Option(
        None,
        "--include",
        help=(
            "Comma-separated structured state sections to return as JSON "
            "(position, session, continuation, handoff, project_reference)."
        ),
    ),
) -> None:
    """Get a specific state section or the full state."""
    from gpd.core.state import _session_display_from_continuation
    from gpd.core.state import state_get_readonly as core_state_get
    from gpd.core.state import state_load_readonly as core_state_load

    if include is not None:
        if section is not None:
            _error("state get accepts either a positional section or --include, not both")
        allowed = {"position", "session", "continuation", "handoff", "project_reference", "project"}
        includes: list[str] = []
        for raw_token in include.split(","):
            token = raw_token.strip().replace("-", "_")
            if not token:
                continue
            if token not in allowed:
                supported = ", ".join(sorted(allowed - {"project"}))
                _error(f"Unknown --include value for state get: {token}. Allowed values: {supported}.")
            canonical = "project_reference" if token == "project" else token
            if canonical not in includes:
                includes.append(canonical)
        if not includes:
            _error("state get --include requires at least one non-empty value")

        state_obj = core_state_load(_read_only_project_scoped_cwd()).state
        state_payload = state_obj if isinstance(state_obj, dict) else {}
        continuation = state_payload.get("continuation")
        payload: dict[str, object] = {}
        for token in includes:
            if token == "session":
                payload[token] = _session_display_from_continuation(continuation)
            elif token == "handoff":
                payload[token] = continuation.get("handoff") if isinstance(continuation, dict) else {}
            else:
                payload[token] = state_payload.get(token) or {}
        _output(payload)
        return

    _output(core_state_get(_read_only_project_scoped_cwd(), section))


@state_app.command("patch")
def state_patch(
    patches: list[str] = typer.Argument(..., help="Key-value pairs: key1 value1 key2 value2 ..."),
) -> None:
    """Patch multiple state fields at once."""
    from gpd.core.state import state_patch

    if len(patches) % 2 != 0:
        _error("state patch requires key-value pairs (even number of arguments)")
    patch_dict: dict[str, str] = {}
    for i in range(0, len(patches), 2):
        key = patches[i].lstrip("-")
        if not key:
            _error(f"Invalid empty key after stripping dashes: {patches[i]!r}")
        patch_dict[key] = patches[i + 1]
    _output(state_patch(_state_command_cwd(), patch_dict))


@state_app.command("set-project-contract")
def state_set_project_contract_cmd(
    source: str = typer.Argument(..., help="Path to a JSON file containing the project contract, or '-' for stdin"),
) -> None:
    """Persist the canonical project contract into state.json."""
    from gpd.contracts import parse_project_contract_data_strict
    from gpd.core.contract_validation import validate_project_contract
    from gpd.core.state import StateUpdateResult, state_set_project_contract

    contract_data = _load_json_document(source)
    project_root = _state_command_cwd()
    strict_result = parse_project_contract_data_strict(contract_data)
    if strict_result.contract is None or strict_result.errors:
        result = StateUpdateResult(
            updated=False,
            reason="Invalid project contract schema: "
            + "; ".join(list(strict_result.errors) or ["project contract could not be normalized"]),
            schema_reference="templates/project-contract-schema.md",
        )
        _output(result)
        raise typer.Exit(code=1)

    validation = validate_project_contract(strict_result.contract, mode="approved", project_root=project_root)
    if not validation.valid:
        if _raw:
            _emit_raw_json(
                _model_dump_with_schema_reference(
                    validation,
                    schema_reference="templates/project-contract-schema.md",
                ),
                err=True,
            )
        else:
            _output(validation)
        raise typer.Exit(code=1)

    result = state_set_project_contract(project_root, strict_result.contract)
    _output(result)
    if not result.updated and not result.unchanged:
        raise typer.Exit(code=1)


@state_app.command("update")
def state_update(
    field: str = typer.Argument(..., help="Field name to update"),
    value: str = typer.Argument(..., help="New value"),
) -> None:
    """Update a single state field."""
    from gpd.core.state import state_update

    _output(state_update(_state_command_cwd(), field, value))


@state_app.command("advance")
def state_advance() -> None:
    """Advance to the next plan in current phase."""
    from gpd.core.state import state_advance_plan

    _output(state_advance_plan(_state_command_cwd()))


@state_app.command("compact")
def state_compact() -> None:
    """Archive old state entries to keep STATE.md concise."""
    from gpd.core.state import state_compact

    _output(state_compact(_state_command_cwd()))


@state_app.command("snapshot")
def state_snapshot() -> None:
    """Return a fast read-only snapshot of current state for progress and routing."""
    from gpd.core.state import state_snapshot

    _output(state_snapshot(_read_only_project_scoped_cwd()))


@state_app.command("active-hypothesis")
def state_active_hypothesis() -> None:
    """Extract the active hypothesis branch note from STATE.md, if present."""
    from gpd.core.state import state_get_readonly as state_get

    result = state_get(_read_only_project_scoped_cwd(), "Active Hypothesis")
    section = result.value or ""
    if result.error or not section.strip():
        _output(
            {
                "found": False,
                "branch": None,
                "branch_slug": None,
                "section": None,
                "error": result.error or "Active Hypothesis section not found",
            }
        )
        return

    branch_match = re.search(r"^\*\*Branch:\*\*\s*(?:hypothesis/)?([^\s]+)", section, re.IGNORECASE | re.MULTILINE)
    if not branch_match:
        _output(
            {
                "found": False,
                "branch": None,
                "branch_slug": None,
                "section": section,
                "error": "Active Hypothesis section is missing a hypothesis branch",
            }
        )
        return

    branch_slug = branch_match.group(1).strip()
    _output(
        {
            "found": True,
            "branch": f"hypothesis/{branch_slug}",
            "branch_slug": branch_slug,
            "section": section,
        }
    )


@state_app.command("validate")
def state_validate() -> None:
    """Validate state consistency and schema compliance."""
    from gpd.core.state import state_validate as core_state_validate

    result = core_state_validate(
        _read_only_marker_backed_project_scoped_cwd(), recover_intent=False, acquire_lock=False
    )
    _output(result)
    if hasattr(result, "valid") and not result.valid:
        raise typer.Exit(code=1)


@state_app.command("repair-sync")
def state_repair_sync() -> None:
    """Repair STATE.md/state.json using the recovery-aware backend path."""
    from gpd.core.state import state_repair_sync as core_state_repair_sync

    result = core_state_repair_sync(_state_command_cwd())
    _output(result)
    if not result.repaired:
        raise typer.Exit(code=1)


@state_app.command("record-metric")
def state_record_metric(
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    plan: str | None = typer.Option(None, "--plan", help="Plan name"),
    duration: str | None = typer.Option(None, "--duration", help="Duration"),
    tasks: str | None = typer.Option(None, "--tasks", help="Task count"),
    files: str | None = typer.Option(None, "--files", help="File count"),
) -> None:
    """Record execution metric for a phase/plan."""
    from gpd.core.state import state_record_metric

    _output(
        state_record_metric(_state_command_cwd(), phase=phase, plan=plan, duration=duration, tasks=tasks, files=files)
    )


@state_app.command("update-progress")
def state_update_progress() -> None:
    """Recalculate progress percentage from phase completion."""
    from gpd.core.state import state_update_progress

    _output(state_update_progress(_state_command_cwd()))


@state_app.command("add-decision")
def state_add_decision(
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    summary: str | None = typer.Option(None, "--summary", help="Decision summary"),
    rationale: str = typer.Option("", "--rationale", help="Decision rationale"),
) -> None:
    """Record a research decision."""
    from gpd.core.state import state_add_decision

    _output(state_add_decision(_state_command_cwd(), phase=phase, summary=summary, rationale=rationale))


@state_app.command("add-blocker")
def state_add_blocker(
    text: str = typer.Option(..., "--text", help="Blocker description"),
) -> None:
    """Record a blocker."""
    from gpd.core.state import state_add_blocker

    _output(state_add_blocker(_state_command_cwd(), text))


@state_app.command("resolve-blocker")
def state_resolve_blocker(
    text: str = typer.Option(..., "--text", help="Blocker description to resolve"),
) -> None:
    """Mark a blocker as resolved."""
    from gpd.core.state import state_resolve_blocker

    _output(state_resolve_blocker(_state_command_cwd(), text))


@state_app.command("record-verification")
def state_record_verification(
    phase: str = typer.Option(..., "--phase", help="Phase number to record verification for"),
    status: str | None = typer.Option(
        None,
        "--status",
        help=(
            "Administrative override outcome (passed|failed). Requires --admin-status-override. "
            "If omitted, read canonical VERIFICATION.md frontmatter and fail closed on missing, "
            "malformed, or unknown status."
        ),
    ),
    admin_status_override: bool = typer.Option(
        False,
        "--admin-status-override",
        help="Allow --status to bypass canonical VERIFICATION.md frontmatter for administrative repair.",
    ),
) -> None:
    """Atomically advance STATE.md past verification after a VERIFICATION.md result."""
    from gpd.core.state import state_record_verification

    result = state_record_verification(
        _state_command_cwd(),
        phase=phase,
        status=status,
        admin_override=admin_status_override,
    )
    payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    _output(payload)
    if isinstance(payload, dict) and payload.get("error"):
        raise typer.Exit(code=1)


@state_app.command("record-session")
def state_record_session(
    stopped_at: str | None = typer.Option(None, "--stopped-at", help="Stop timestamp"),
    resume_file: str | None = typer.Option(None, "--resume-file", help="Resume context file"),
    last_result_id: str | None = typer.Option(
        None, "--last-result-id", help="Latest canonical result ID to carry forward"
    ),
) -> None:
    """Record a session boundary for context tracking."""
    from gpd.core.state import state_record_session

    result = state_record_session(
        _state_command_cwd(),
        stopped_at=stopped_at,
        resume_file=resume_file,
        last_result_id=last_result_id,
    )
    payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    _output(payload)
    if isinstance(payload, dict) and payload.get("error"):
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# contract — Machine contract alignment confirmation gate
# ═══════════════════════════════════════════════════════════════════════════

contract_app = typer.Typer(help="Machine-contract alignment gate (claim-deliverable precheck)")
app.add_typer(contract_app, name="contract")


def _require_project_root(cwd: Path, *, command_label: str) -> Path:
    """Require a visible GPD project root; ``command_label`` is the noun used in the error."""
    workspace_cwd = cwd.expanduser().resolve(strict=False)
    project_root = _project_anchor_cwd(workspace_cwd)
    if project_root is None:
        _error(
            f"{command_label} require a real GPD project root. "
            "Run the command from inside a project with a GPD/ layout."
        )
    return project_root


def _load_authoritative_project_contract_or_error(
    project_root: Path,
) -> tuple[object, dict[str, object], dict[str, object], dict[str, object]]:
    """Load the current contract for alignment commands, failing closed on non-authority."""
    from gpd.core.errors import StateError
    from gpd.core.state import _load_authoritative_project_contract_for_runtime_context

    try:
        return _load_authoritative_project_contract_for_runtime_context(project_root)
    except StateError as exc:
        _error(str(exc))


@contract_app.command("record-alignment")
def contract_record_alignment(
    contract_hash: str = typer.Option(
        ..., "--contract-hash", help="Fingerprint of the machine contract that was reviewed."
    ),
    context_hash: str = typer.Option(
        ..., "--context-hash", help="Fingerprint of the phase CONTEXT.md text that was reviewed."
    ),
) -> None:
    """Persist operator confirmation that the claim-deliverable alignment was reviewed."""
    from gpd.core.errors import StateError
    from gpd.core.state import state_record_contract_alignment

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    try:
        state_record_contract_alignment(
            project_root,
            contract_hash=contract_hash,
            context_hash=context_hash,
        )
    except StateError as exc:
        _error(str(exc))
    if _raw:
        _emit_raw_json({"result": "recorded"})
    else:
        typer.echo("recorded")


@contract_app.command("alignment-status")
def contract_alignment_status() -> None:
    """Print the persisted claim-deliverable alignment confirmation as JSON."""
    from gpd.core.state import state_load_readonly

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    load_result = state_load_readonly(project_root)
    state_obj = load_result.state if isinstance(load_result.state, dict) else {}
    alignment = state_obj.get("contract_alignment") or {}
    payload = {
        "confirmed_at": alignment.get("confirmed_at"),
        "confirmed_contract_hash": alignment.get("confirmed_contract_hash"),
        "confirmed_context_hash": alignment.get("confirmed_context_hash"),
    }
    _emit_raw_json(payload)


@contract_app.command("fingerprint")
def contract_fingerprint_cmd() -> None:
    """Print the canonical sha256 fingerprint of the current machine contract."""
    from gpd.core.contract_validation import contract_fingerprint

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    contract, _load_info, _validation, _gate = _load_authoritative_project_contract_or_error(project_root)
    _output(contract_fingerprint(contract))


@contract_app.command("context-fingerprint")
def contract_context_fingerprint_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to the CONTEXT.md file. Defaults to the active phase's CONTEXT.md.",
    ),
) -> None:
    """Print the sha256 fingerprint of a CONTEXT.md file's text."""
    from gpd.core.constants import CONTEXT_SUFFIX, STANDALONE_CONTEXT
    from gpd.core.context import _find_phase_artifact_path
    from gpd.core.contract_validation import context_guidance_fingerprint
    from gpd.core.phases import find_phase
    from gpd.core.state import state_load_readonly

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    if path is None:
        state_obj = state_load_readonly(project_root).state
        current_phase = state_obj.get("position", {}).get("current_phase") if isinstance(state_obj, dict) else None
        if current_phase is None:
            _error(
                "No CONTEXT.md could be resolved: state.position.current_phase is "
                "unset. Pass an explicit path as the argument."
            )
        phase_info = find_phase(project_root, str(current_phase))
        if phase_info is None:
            _error(f"No CONTEXT.md could be resolved: phase {current_phase!r} not found.")
        phase_dir = project_root / phase_info.directory
        resolved = _find_phase_artifact_path(phase_dir, CONTEXT_SUFFIX, STANDALONE_CONTEXT)
        if resolved is None:
            _error(f"No CONTEXT.md found under {phase_dir}.")
    else:
        resolved = path.expanduser()
        if not resolved.is_absolute():
            resolved = _get_cwd() / resolved
        resolved = resolved.resolve(strict=False)
        if not resolved.is_file():
            _error(f"CONTEXT file not found: {resolved}")
    _output(context_guidance_fingerprint(resolved.read_text(encoding="utf-8")))


@contract_app.command("alignment-summary")
def contract_alignment_summary_cmd() -> None:
    """Print the claim-deliverable alignment row projection as JSON."""
    from gpd.core.contract_validation import claim_deliverable_alignment_summary

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    contract, _load_info, _validation, _gate = _load_authoritative_project_contract_or_error(project_root)
    rows = [
        {"claim": claim, "deliverable": deliverable, "acceptance_test": acceptance}
        for claim, deliverable, acceptance in claim_deliverable_alignment_summary(contract)
    ]
    _emit_raw_json({"rows": rows})


# ═══════════════════════════════════════════════════════════════════════════
# phase — Phase lifecycle management
# ═══════════════════════════════════════════════════════════════════════════

phase_app = typer.Typer(help="Phase lifecycle (add, remove, complete, etc.)")
app.add_typer(phase_app, name="phase")
phase_checkpoint_app = typer.Typer(help="Wave rollback checkpoint tag helpers")
phase_app.add_typer(phase_checkpoint_app, name="checkpoint")


@phase_checkpoint_app.command("create")
def phase_checkpoint_create(
    phase_num: str = typer.Option(..., "--phase", help="Phase number for the checkpoint tag"),
    wave_num: str = typer.Option(..., "--wave", help="Wave number for the checkpoint tag"),
    namespace: str = typer.Option("phase", "--namespace", help="Checkpoint namespace: phase or sweep"),
) -> None:
    """Create a helper-owned rollback checkpoint tag before wave execution."""
    from gpd.core.wave_checkpoints import create_wave_checkpoint

    try:
        result = create_wave_checkpoint(
            _project_scoped_cwd(),
            phase=phase_num,
            wave=wave_num,
            namespace=namespace,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        _error(str(exc))
    _output(result)
    if not result.safe_to_execute_wave:
        raise typer.Exit(code=1)


@phase_checkpoint_app.command("list")
def phase_checkpoint_list(
    phase_num: str = typer.Option(..., "--phase", help="Phase number for checkpoint inventory"),
    namespace: str = typer.Option("phase", "--namespace", help="Checkpoint namespace: phase or sweep"),
) -> None:
    """List helper-owned rollback checkpoint tags for a phase."""
    from gpd.core.wave_checkpoints import list_wave_checkpoints

    try:
        result = list_wave_checkpoints(
            _read_only_project_scoped_cwd(),
            phase=phase_num,
            namespace=namespace,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        _error(str(exc))
    _output(result)
    if result.errors:
        raise typer.Exit(code=1)


@phase_checkpoint_app.command("cleanup")
def phase_checkpoint_cleanup(
    phase_num: str = typer.Option(..., "--phase", help="Phase number for checkpoint cleanup"),
    namespace: str = typer.Option("phase", "--namespace", help="Checkpoint namespace: phase or sweep"),
    policy: str = typer.Option(
        "preserve-on-failure",
        "--policy",
        help="Cleanup policy: preserve-on-failure or successful-closeout",
    ),
) -> None:
    """Delete helper-owned rollback checkpoint tags only when policy allows it."""
    from gpd.core.wave_checkpoints import cleanup_wave_checkpoints

    try:
        result = cleanup_wave_checkpoints(
            _project_scoped_cwd(),
            phase=phase_num,
            namespace=namespace,  # type: ignore[arg-type]
            policy=policy,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        _error(str(exc))
    _output(result)
    if result.errors:
        raise typer.Exit(code=1)


@phase_app.command("list")
def phase_list(
    file_type: str | None = typer.Option(None, "--type", help="File type filter"),
    phase: str | None = typer.Option(None, "--phase", help="Phase filter"),
) -> None:
    """List phases and their files."""
    from gpd.core.phases import list_phase_files, list_phases

    cwd = _read_only_project_scoped_cwd()
    if file_type or phase:
        _output(list_phase_files(cwd, file_type=file_type or "plan", phase=phase))
    else:
        _output(list_phases(cwd))


@phase_app.command("add")
def phase_add(
    description: list[str] = typer.Argument(..., help="Phase description"),
) -> None:
    """Add a new phase to the end of the roadmap."""
    from gpd.core.phases import phase_add

    _output(phase_add(_project_scoped_cwd(), " ".join(description)))


@phase_app.command("insert")
def phase_insert(
    after_phase: str = typer.Argument(..., help="Phase number to insert after"),
    description: list[str] = typer.Argument(..., help="Phase description"),
) -> None:
    """Insert a new phase after an existing one."""
    from gpd.core.phases import phase_insert

    _output(phase_insert(_project_scoped_cwd(), after_phase, " ".join(description)))


@phase_app.command("remove")
def phase_remove(
    phase_num: str = typer.Argument(..., help="Phase number to remove"),
    force: bool = typer.Option(False, "--force", help="Force removal even if completed"),
) -> None:
    """Remove a phase from the roadmap."""
    from gpd.core.phases import phase_remove

    _output(phase_remove(_project_scoped_cwd(), phase_num, force=force))


@phase_app.command("complete")
def phase_complete(
    phase_num: str = typer.Argument(..., help="Phase number to mark complete"),
) -> None:
    """Mark a phase as complete."""
    from gpd.core.phases import phase_complete

    _output(phase_complete(_project_scoped_cwd(), phase_num))


@phase_app.command("closeout-readiness")
def phase_closeout_readiness_cmd(
    phase_num: str = typer.Argument(..., help="Phase number to check"),
    require_verification: bool = typer.Option(
        True,
        "--require-verification/--no-require-verification",
        help="Require canonical verification frontmatter status: passed",
    ),
) -> None:
    """Check whether a phase is ready for closeout without mutating state."""
    from gpd.core.phase_closeout import phase_closeout_readiness, phase_closeout_readiness_payload

    result = phase_closeout_readiness(
        _read_only_project_scoped_cwd(),
        phase_num,
        require_verification=require_verification,
    )
    if _raw:
        _emit_raw_json(phase_closeout_readiness_payload(result))
    else:
        _output(result)
    if not result.ready:
        raise typer.Exit(code=1)


@phase_app.command("index")
def phase_plan_index(
    phase_num: str = typer.Argument(..., help="Phase number"),
) -> None:
    """Show plan index for a phase (plans, waves, dependencies)."""
    from gpd.core.phases import phase_plan_index

    _output(phase_plan_index(_read_only_project_scoped_cwd(), phase_num))


@phase_app.command("find")
def phase_find(
    phase_num: str = typer.Argument(..., help="Phase number to find"),
) -> None:
    """Find a phase directory and its metadata."""
    from gpd.core.phases import find_phase

    result = find_phase(_read_only_project_scoped_cwd(), phase_num)
    if result is None:
        _error(f"Phase {phase_num} not found")
    _output(result)


@phase_app.command("next-decimal")
def phase_next_decimal(
    base_phase: str = typer.Argument(..., help="Base phase number"),
) -> None:
    """Get the next available decimal phase number (e.g. 42 → 42.1)."""
    from gpd.core.phases import next_decimal_phase

    _output(next_decimal_phase(_read_only_project_scoped_cwd(), base_phase))


@phase_app.command("normalize")
def phase_normalize_cmd(
    phase_num: str = typer.Argument(..., help="Phase number to normalize"),
) -> None:
    """Normalize a phase number to canonical zero-padded form."""
    from gpd.core.utils import phase_normalize

    _output(phase_normalize(phase_num))


@phase_app.command("validate-waves")
def phase_validate_waves(
    phase_num: str = typer.Argument(..., help="Phase number to validate"),
) -> None:
    """Validate wave dependencies within a phase."""
    from gpd.core.phases import validate_phase_waves

    result = validate_phase_waves(_read_only_project_scoped_cwd(), phase_num)
    _output(result)
    validation = getattr(result, "validation", None)
    if getattr(validation, "valid", True) is False:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# roadmap — Roadmap analysis
# ═══════════════════════════════════════════════════════════════════════════

roadmap_app = typer.Typer(help="Roadmap analysis and phase lookup")
app.add_typer(roadmap_app, name="roadmap")


@roadmap_app.command("get-phase")
def roadmap_get_phase(
    phase_num: str = typer.Argument(..., help="Phase number"),
) -> None:
    """Get detailed roadmap entry for a phase."""
    from gpd.core.phases import roadmap_get_phase

    _output(roadmap_get_phase(_project_scoped_cwd(), phase_num))


@roadmap_app.command("analyze")
def roadmap_analyze() -> None:
    """Analyze roadmap structure, dependencies, and coverage."""
    from gpd.core.phases import roadmap_analyze

    _output(roadmap_analyze(_project_scoped_cwd()))


# ═══════════════════════════════════════════════════════════════════════════
# milestone — Milestone management
# ═══════════════════════════════════════════════════════════════════════════

milestone_app = typer.Typer(help="Milestone lifecycle")
app.add_typer(milestone_app, name="milestone")


@milestone_app.command("complete")
def milestone_complete(
    version: str = typer.Argument(..., help="Milestone version (e.g. v1.0)"),
    name: str | None = typer.Option(None, "--name", help="Milestone name"),
) -> None:
    """Archive a completed milestone."""
    from gpd.core.phases import milestone_complete

    _output(milestone_complete(_project_scoped_cwd(), version, name=name))


# ═══════════════════════════════════════════════════════════════════════════
# resume — Read-only recovery summary
# ═══════════════════════════════════════════════════════════════════════════


def _resume_status_message(payload: dict[str, object], *, recovery_advice: RecoveryAdvice) -> str:
    """Return a concise human summary of resume readiness for this workspace."""
    return _resume_presentation.resume_status_message(payload, recovery_advice=recovery_advice)


def _resume_recent_hint(payload: dict[str, object]) -> str | None:
    """Return a cross-project recovery hint when the current workspace has nothing to resume."""
    if _payload_flag(payload, "planning_exists") and any(
        _payload_flag(payload, key) for key in ("state_exists", "roadmap_exists", "project_exists")
    ):
        return None
    return f"If this is the wrong workspace, run `{local_cli_resume_recent_command()}` to search other recent projects on this machine."


def _resume_runtime_commands(*, cwd: Path | None = None) -> tuple[str | None, str | None]:
    """Return runtime-specific resume/suggest commands when they can be resolved."""
    try:
        from gpd.adapters import get_adapter
        from gpd.hooks.runtime_detect import (
            RUNTIME_UNKNOWN,
            detect_runtime_for_gpd_use,
            detect_runtime_install_target,
        )

        runtime_name = detect_runtime_for_gpd_use(cwd=cwd or _get_cwd())
        if (
            not isinstance(runtime_name, str)
            or not runtime_name.strip()
            or runtime_name == RUNTIME_UNKNOWN
            or detect_runtime_install_target(runtime_name, cwd=cwd or _get_cwd()) is None
        ):
            return None, None
        adapter = get_adapter(runtime_name)
        resume_work_command = str(adapter.format_command("resume-work")).strip()
        suggest_next_command = str(adapter.format_command("suggest-next")).strip()
        return resume_work_command or None, suggest_next_command or None
    except Exception as exc:
        logger.warning(
            "Failed to resolve runtime-specific resume commands for %s: %s",
            cwd or _get_cwd(),
            exc,
            exc_info=True,
        )
        return None, None


def _resume_recovery_advice(
    *,
    resume_payload: dict[str, object] | None = None,
    recent_rows: list[dict[str, object]] | None = None,
    force_recent: bool = False,
    cwd: Path | None = None,
):
    """Return the shared recovery-orientation contract with resolved runtime commands."""
    resume_work_command, suggest_next_command = _resume_runtime_commands(cwd=cwd)
    return build_recovery_advice(
        cwd or _get_cwd(),
        recent_rows=recent_rows,
        resume_payload=resume_payload,
        continue_command=resume_work_command,
        fast_next_command=suggest_next_command,
        force_recent=force_recent,
    )


def _resume_mode_label(value: object) -> str:
    """Format a resume mode for human-facing CLI output."""
    return _resume_presentation.resume_mode_label(value)


def _resume_status_label(status: object) -> str:
    """Return a canonical human label for one recovery status."""
    return _resume_presentation.resume_status_label(status)


def _project_root_source_label(source: object, *, auto_selected: bool = False) -> str:
    """Map a project-root source to a plain-language re-entry label."""
    return _resume_presentation.project_root_source_label(source, auto_selected=auto_selected)


def _resume_candidate_canonical_kind(candidate: dict[str, object]) -> str:
    """Return the canonical family name for one resume candidate."""
    return resume_candidate_kind(candidate) or "unknown"


def _resume_candidate_kind_label(candidate: dict[str, object]) -> str:
    """Map one resume candidate to a user-facing kind label."""
    return _resume_presentation.resume_candidate_kind_label(candidate)


def _resume_candidate_kind(source: object, *, status: object) -> str:
    """Return a stable machine label for the candidate concept."""
    source_text = str(source).strip() if source is not None else ""
    _ = str(status).strip() if status is not None else ""
    return resume_candidate_kind_from_source(source_text) or "unknown"


def _resume_origin_label(origin: object) -> str:
    """Map one canonical resume origin to a user-facing label."""
    return _resume_presentation.resume_origin_label(origin)


def _public_resume_origin_family(
    origin: object,
    *,
    source: object = None,
    active_execution: dict[str, object] | None = None,
    current_execution: dict[str, object] | None = None,
) -> str | None:
    """Collapse internal resume-origin tokens into the public resume-origin families."""
    return _resume_presentation.public_resume_origin_family(
        origin,
        source=source,
        active_execution=active_execution,
        current_execution=current_execution,
    )


def _resume_authoritative_active_execution(
    payload: dict[str, object],
) -> dict[str, object] | None:
    """Return the bounded segment only when it comes from canonical continuation."""
    return _resume_presentation.resume_authoritative_active_execution(payload)


def _resume_candidate_phase_plan(candidate: dict[str, object]) -> str:
    """Format phase/plan context for one resume candidate."""
    return _resume_presentation.resume_candidate_phase_plan(candidate)


def _resume_surface_value(
    payload: dict[str, object],
    key: str,
) -> object | None:
    """Return one canonical resume field from the payload."""
    return lookup_resume_surface_value(payload, key)


def _strict_bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _payload_flag(payload: dict[str, object], key: str) -> bool:
    return _strict_bool_value(payload.get(key)) is True


def _resume_visible_candidates(payload: dict[str, object]) -> list[dict[str, object]]:
    """Return the canonical candidate list to render."""
    return _resume_presentation.resume_visible_candidates(payload)


def _resume_candidate_target(candidate: dict[str, object]) -> str:
    """Format the primary target/pointer for one resume candidate."""
    return _resume_presentation.resume_candidate_target(candidate, cwd=_get_cwd())


def _resume_candidate_rerun_anchor(candidate: dict[str, object]) -> str | None:
    """Return the canonical rerun anchor note for one candidate, if any."""
    return _resume_presentation.resume_candidate_rerun_anchor(candidate)


def _resume_result_payload(value: object) -> dict[str, object] | None:
    """Normalize a hydrated result payload into a plain dictionary."""
    return _resume_presentation.resume_result_payload(value)


def _resume_result_summary(result: Mapping[str, object] | None, *, include_id: bool = True) -> str | None:
    """Render a concise human summary for one hydrated intermediate result."""
    return _resume_presentation.resume_result_summary(result, include_id=include_id)


def _resume_candidate_last_result(
    candidate: dict[str, object],
    *,
    payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    """Return the hydrated last-result payload for one candidate, if available."""
    return _resume_presentation.resume_candidate_last_result(candidate, payload=payload)


def _resume_active_result(
    payload: dict[str, object],
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the most relevant hydrated result for the current resume view."""
    return _resume_presentation.resume_active_result(payload, candidates)


def _resume_candidate_origin(
    candidate: dict[str, object],
    *,
    active_execution: dict[str, object] | None,
    current_execution: dict[str, object] | None,
) -> tuple[str, str]:
    """Return a machine label and human summary for one candidate origin."""
    return _resume_presentation.resume_candidate_origin(
        candidate,
        active_execution=active_execution,
        current_execution=current_execution,
    )


def _recent_project_label(row: dict[str, object]) -> str | None:
    """Return an optional human label for one recent-project row."""
    return _recent_project_presentation.recent_project_label(row)


def _recent_project_summary(row: dict[str, object]) -> str | None:
    """Return an optional human summary for one recent-project row."""
    return _recent_project_presentation.recent_project_summary(row)


def _recent_project_current_state(row: dict[str, object]) -> str | None:
    """Return an optional phase/status/progress summary for one recent-project row."""
    return _recent_project_presentation.recent_project_current_state(row)


def _recent_project_selection_reason(row: dict[str, object]) -> str:
    """Return a plain-language explanation for why a recent-project row is shown."""
    return _recent_project_presentation.recent_project_selection_reason(row)


def _resume_candidate_notes(
    candidate: dict[str, object],
    *,
    payload: dict[str, object] | None = None,
    active_execution: dict[str, object] | None = None,
    current_execution: dict[str, object] | None = None,
) -> str:
    """Render the most relevant resume notes for one candidate."""
    return _resume_presentation.resume_candidate_notes(
        candidate,
        payload=payload,
        active_execution=active_execution,
        current_execution=current_execution,
    )


def _resume_candidate_projection(
    candidate: dict[str, object],
    *,
    payload: dict[str, object] | None = None,
    active_execution: dict[str, object] | None = None,
    current_execution: dict[str, object] | None = None,
) -> dict[str, object]:
    """Project one raw candidate into a canonical recovery view."""
    return _resume_presentation.resume_candidate_projection(
        candidate,
        payload=payload,
        active_execution=active_execution,
        current_execution=current_execution,
        cwd=_get_cwd(),
    )


def _recent_project_resume_file_state(project_root: object, resume_file: object) -> tuple[bool | None, str | None]:
    """Return whether a recent-project handoff file is still usable."""
    return _recent_project_presentation.recent_project_resume_file_state(project_root, resume_file)


def _recent_projects_data_root() -> Path:
    """Return the machine-local home data root for cross-project recovery metadata."""
    configured = os.environ.get(ENV_DATA_DIR, "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / HOME_DATA_DIR_NAME


def _recent_project_text(payload: dict[str, object], *keys: str) -> str | None:
    """Return the first non-empty string value among *keys*."""
    return _recent_project_presentation.recent_project_text(payload, *keys)


def _normalize_recent_project_row(row: object) -> dict[str, object] | None:
    """Project one canonical recent-project row into the CLI display shape."""
    return _recent_project_presentation.normalize_recent_project_row(row, cwd=_get_cwd())


def _recent_project_sort_key(row: dict[str, object]) -> tuple[int, int, int, int, int, str, str]:
    """Sort recent rows by recovery strength first, then by recency."""
    return _recent_project_presentation.recent_project_row_sort_key(row)


def _load_recent_projects_rows(*, last: int | None = None) -> list[dict[str, object]]:
    """Load the recent-project index, preferring the shared helper module when present."""
    from gpd.core.recent_projects import RecentProjectsError

    try:
        return _recent_project_presentation.load_recent_project_display_rows(
            data_root=_recent_projects_data_root(),
            last=last,
            cwd=_get_cwd(),
        )
    except (RecentProjectsError, ValueError) as exc:
        raise GPDError(str(exc)) from exc


def _resume_recent_project_command(row: dict[str, object]) -> str:
    """Return the exact command to reopen one recent project."""
    return _recent_project_presentation.recent_project_resume_command(row)


def _resume_recent_project_notes(row: dict[str, object]) -> str:
    """Return a concise availability/resumability note for one recent project row."""
    return _recent_project_presentation.recent_project_notes(row)


def _recent_project_recovery_view(row: dict[str, object]) -> dict[str, object] | None:
    """Return a canonical recovery summary for one recent-project row when available."""
    return _recent_project_presentation.recent_project_recovery_view(
        row,
        recovery_advice_builder=lambda cwd, **kwargs: _resume_recovery_advice(
            resume_payload=dict(kwargs.get("resume_payload") or {}),
            recent_rows=list(kwargs.get("recent_rows") or []),
            cwd=cwd,
        ),
    )


def _annotate_recent_project_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Add canonical recovery summaries to recent-project rows while keeping existing fields."""
    return _recent_project_presentation.annotate_recent_project_rows(
        rows,
        recovery_advice_builder=lambda cwd, **kwargs: _resume_recovery_advice(
            resume_payload=dict(kwargs.get("resume_payload") or {}),
            recent_rows=list(kwargs.get("recent_rows") or []),
            cwd=cwd,
        ),
    )


def _resume_follow_up_actions(recovery_advice: RecoveryAdvice) -> list[str]:
    """Render recovery follow-up lines from the shared structured action contract."""
    return recovery_action_lines(
        actions=recovery_advice.actions,
        mode=recovery_advice.mode,
        include_primary=False,
    )


def _resume_augmented_payload(payload: dict[str, object], *, cwd: Path | None = None) -> dict[str, object]:
    """Augment the raw resume payload with canonical recovery projections."""
    public_payload = canonicalize_resume_public_payload(payload)
    recovery_advice = _resume_recovery_advice(resume_payload=public_payload, recent_rows=[], cwd=cwd)
    return _resume_presentation.resume_augmented_payload(
        public_payload,
        recovery_advice=recovery_advice,
        cwd=cwd or _get_cwd(),
    )


def _render_recent_resume_summary(rows: list[dict[str, object]]) -> None:
    """Render the recent-project picker for cross-project recovery."""
    for line in _recent_project_presentation.build_recent_resume_summary_lines(
        rows,
        local_resume_command=local_cli_resume_command(),
    ):
        console.print(line)


def _render_resume_summary(payload: dict[str, object]) -> None:
    """Render a read-only local recovery summary for humans."""
    public_payload = canonicalize_resume_public_payload(payload)
    recovery_advice = _resume_recovery_advice(resume_payload=public_payload, recent_rows=[])

    console.print("[bold]Resume Summary[/]")
    console.print("[dim]Read-only local recovery snapshot for this workspace.[/]")
    console.print()

    recovery_advice_payload = serialize_recovery_advice(recovery_advice)
    for lane in build_resume_presentation_lanes(
        public_payload,
        recovery_advice=recovery_advice_payload,
        local_resume_command=local_cli_resume_command(),
        recent_resume_command=local_cli_resume_recent_command(),
        raw_resume_command="gpd --raw resume",
    ):
        console.print(
            Text.assemble(
                (f"{lane['label']}: ", f"bold {_INSTALL_ACCENT_COLOR}"),
                lane["value"],
            ),
            highlight=False,
            soft_wrap=True,
        )


@app.command("resume")
def resume(
    recent: bool = typer.Option(
        False,
        "--recent",
        help="Show machine-local recent projects with path, label, and recovery evidence instead of the current workspace recovery summary",
    ),
) -> None:
    """Summarize local recovery state or list machine-local recent projects."""
    if recent:
        try:
            rows = _annotate_recent_project_rows(_load_recent_projects_rows(last=20))
        except GPDError as exc:
            _error(str(exc))
        recovery_advice = _resume_recovery_advice(recent_rows=rows, force_recent=True)
        if _raw:
            _output(
                {
                    "count": len(rows),
                    "projects": rows,
                    "recovery_advice": serialize_recovery_advice(recovery_advice),
                }
            )
            return
        _render_recent_resume_summary(rows)
        return

    from gpd.core.context import init_resume

    payload = init_resume(_get_cwd())
    if _raw:
        _output(_resume_augmented_payload(payload, cwd=_get_cwd()))
        return
    _render_resume_summary(payload)


# ═══════════════════════════════════════════════════════════════════════════
# progress — Progress rendering
# ═══════════════════════════════════════════════════════════════════════════


def _progress_watch_sleep(seconds: float) -> None:
    """Sleep for ``seconds`` seconds. Module-local shim for monkeypatching in tests."""
    import time

    time.sleep(seconds)


def _is_idle(result: object) -> bool:
    """Return True when ``result`` reports no active live execution.

    A project with execution preferences set but no running session yields a
    live_execution shell whose populated fields are all None; treat that as
    idle so --exit-on-idle triggers cleanly.
    """
    live = getattr(result, "live_execution", None)
    if live is None:
        return True
    live_fields = (
        "phase",
        "plan",
        "wave",
        "current_task",
        "current_task_index",
        "current_task_total",
        "segment_status",
        "waiting_reason",
        "last_result_label",
        "last_artifact_path",
        "last_updated_age_label",
    )
    return all(getattr(live, name, None) is None for name in live_fields)


def _progress_watch_live_table(result: object) -> Table:
    """Build a rich ``Table`` for a single watch-loop tick (TTY branch)."""
    table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    table.add_column("Field")
    table.add_column("Value")
    live = getattr(result, "live_execution", None)
    if live is None:
        table.add_row("live_execution", "No active execution")
        return table
    fields = (
        "phase",
        "plan",
        "wave",
        "current_task",
        "current_task_index",
        "current_task_total",
        "segment_status",
        "waiting_reason",
        "last_artifact_path",
        "last_result_label",
        "last_updated_age_label",
        "strict_wait",
        "never_interrupt_running_workers",
        "never_auto_close_child_agents",
    )
    for name in fields:
        value = getattr(live, name, None)
        table.add_row(name, "" if value is None else str(value))
    return table


def _collect_watch_signals(layout: ProjectLayout) -> list[Path]:
    """Return the filesystem paths whose mtimes gate a progress-watch redraw."""
    return [
        layout.state_json,
        layout.current_observability_execution,
        layout.execution_lineage_head,
        layout.execution_lineage_ledger,
    ]


def _run_progress_watch_loop(
    cwd: Path,
    fmt: str,
    interval: float,
    exit_on_idle: bool,
    *,
    raw_mode: bool = False,
    _max_ticks: int | None = None,
) -> None:
    """Poll the execution signal files and redraw progress at ``interval`` cadence.

    First tick always renders. Subsequent ticks render only when at least one
    signal file's ``st_mtime_ns`` changed since the previous snapshot, or when
    ``_max_ticks`` forces loop exit first.

    Private parameter ``_max_ticks`` is a test hook — when set, the loop exits
    after the requested number of iterations regardless of mtime or idle state.
    """
    import contextlib

    from gpd.core.constants import ProjectLayout
    from gpd.core.phases import progress_render

    layout = ProjectLayout(cwd)
    signal_paths = _collect_watch_signals(layout)
    _unset = object()
    last_mtimes: dict[Path, int | None | object] = dict.fromkeys(signal_paths, _unset)

    def _should_redraw() -> bool:
        changed = False
        for path in signal_paths:
            try:
                mtime: int | None = path.stat().st_mtime_ns
            except OSError:
                mtime = None
            if last_mtimes[path] is _unset or last_mtimes[path] != mtime:
                last_mtimes[path] = mtime
                changed = True
        return changed

    live_cm: object
    first: object | None
    if _stdout_is_interactive() and not raw_mode:
        from rich.live import Live

        _should_redraw()  # prime
        first = progress_render(cwd, fmt)
        live_cm = Live(
            _progress_watch_live_table(first),
            console=console,
            refresh_per_second=4,
        )

        def render(result: object) -> None:
            live_cm.update(_progress_watch_live_table(result))  # type: ignore[attr-defined]
    else:
        live_cm = contextlib.nullcontext()
        first = None

        def render(result: object) -> None:
            payload = result.model_dump(mode="json", by_alias=True)
            typer.echo(json.dumps(payload, ensure_ascii=False, default=str))

    with live_cm:  # type: ignore[attr-defined]
        if first is None:
            _should_redraw()
            first = progress_render(cwd, fmt)
            render(first)
        if exit_on_idle and _is_idle(first):
            return
        tick = 0
        while True:
            tick += 1
            if _max_ticks is not None and tick >= _max_ticks:
                return
            _progress_watch_sleep(interval)
            if _should_redraw():
                result = progress_render(cwd, fmt)
                render(result)
                if exit_on_idle and _is_idle(result):
                    return


@app.command("progress")
def progress(
    fmt: str = typer.Argument(
        "json",
        help="Format: json, bar, or table (overridden to 'json' when --watch is set)",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        "-w",
        help=(
            "Poll for updates and redraw a live execution view. "
            "The positional fmt is overridden to 'json' while watching."
        ),
    ),
    interval: float = typer.Option(
        10.0,
        "--interval",
        help="Redraw interval in seconds.",
        min=0.1,
    ),
    exit_on_idle: bool = typer.Option(
        False,
        "--exit-on-idle",
        help="Exit when no live execution is detected (for scripting).",
    ),
) -> None:
    """Render progress in the specified format."""
    from gpd.core.phases import progress_render

    cwd = _progress_command_cwd()
    if not watch:
        _output(progress_render(cwd, fmt))
        return
    if fmt != "json":
        err_console.print(f"[dim]--watch overrides fmt={fmt!r} → 'json' for live execution rendering.[/dim]")
        fmt = "json"
    try:
        _run_progress_watch_loop(cwd, fmt, interval, exit_on_idle, raw_mode=_raw)
    except KeyboardInterrupt:
        return


# ═══════════════════════════════════════════════════════════════════════════
# convention — Convention lock management
# ═══════════════════════════════════════════════════════════════════════════

convention_app = typer.Typer(help="Convention lock (notation, units, sign conventions)")
app.add_typer(convention_app, name="convention")


def _load_lock():  # noqa: ANN202 — returns ConventionLock (imported inside)
    """Load ConventionLock from recoverable project state in the current working directory."""
    from gpd.core.errors import ConventionError

    cwd = _get_cwd()
    try:
        raw = _load_convention_state_snapshot(cwd)
    except ConventionError as exc:
        _error(str(exc))
    try:
        from gpd.core.conventions import convention_lock_from_state_payload

        return convention_lock_from_state_payload(raw, source_label="state.json")
    except ConventionError as exc:
        _error(str(exc))


def _load_convention_state_snapshot(cwd: Path) -> dict[str, object] | None:
    """Load the state snapshot used by convention CLI surfaces."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.errors import ConventionError
    from gpd.core.state import _load_state_json_with_integrity_issues

    layout = ProjectLayout(cwd)
    raw_state, _issues, source = _load_state_json_with_integrity_issues(
        cwd,
        persist_recovery=False,
        recover_intent=False,
        acquire_lock=False,
    )
    if raw_state is None:
        if layout.state_json.exists():
            raise ConventionError("Malformed state.json: expected a JSON object")
        return None
    if layout.state_json.exists() and source != "state.json":
        raise ConventionError(f"Malformed state.json: recovered snapshot from {source} is not accepted")
    return raw_state


@convention_app.command("set")
def convention_set(
    key: str = typer.Argument(..., help="Convention key"),
    value: str = typer.Argument(..., help="Convention value"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing convention"),
) -> None:
    """Set a convention in the convention lock."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.conventions import convention_lock_from_state_payload, convention_set
    from gpd.core.errors import ConventionError
    from gpd.core.state import default_state_dict, save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    # Perform the entire read-modify-write under a single file lock to avoid
    # the TOCTOU race that existed when _load_lock() ran before _save_lock().
    with file_lock(state_path):
        try:
            raw = _load_convention_state_snapshot(cwd)
        except ConventionError as exc:
            _error(str(exc))
        if raw is None:
            raw = default_state_dict()
        try:
            lock = convention_lock_from_state_payload(raw, source_label="state.json")
        except ConventionError as exc:
            _error(str(exc))

        result = convention_set(lock, key, value, force=force)
        if result.updated:
            raw["convention_lock"] = lock.model_dump(exclude_none=True)
            save_state_json_locked(cwd, raw)

    _output(result)


@convention_app.command("list")
def convention_list() -> None:
    """List all active conventions."""
    from gpd.core.conventions import convention_list

    _output(convention_list(_load_lock()))


@convention_app.command("diff")
def convention_diff(
    phase1: str | None = typer.Argument(None, help="First phase"),
    phase2: str | None = typer.Argument(None, help="Second phase"),
) -> None:
    """Show convention differences between phases."""
    from gpd.core.conventions import convention_diff_phases

    _output(convention_diff_phases(_get_cwd(), phase1, phase2))


@convention_app.command("check")
def convention_check() -> None:
    """Check convention consistency across phases."""
    from gpd.core.conventions import convention_check

    _output(convention_check(_load_lock()))


@convention_app.command("vocabulary")
def convention_vocabulary() -> None:
    """Dump the canonical machine-label vocabulary.

    Returns the snake_case keys (e.g. ``metric_signature``) that downstream
    agents and structured outputs must use, paired with their human-readable
    labels. Agents that generate structured outputs (scorecards, consistency
    checks, readiness audits) MUST pick labels from this table rather than
    inventing ad-hoc keys like ``source_status``.
    """
    from gpd.core.conventions import CONVENTION_LABELS, KNOWN_CONVENTIONS

    _output(
        {
            "known_conventions": list(KNOWN_CONVENTIONS),
            "labels": dict(CONVENTION_LABELS),
        }
    )


@convention_app.command("validate-assert")
def convention_validate_assert(
    file: str = typer.Argument(..., help="Path to the derivation file whose ASSERT_CONVENTION lines are checked"),
    project_dir: str | None = typer.Option(
        None,
        "--project-dir",
        help="Project root whose state.json convention lock is used. Defaults to the effective --cwd.",
    ),
    lock: str | None = typer.Option(
        None,
        "--lock",
        help="Path to a JSON convention lock. Mutually exclusive with --project-dir.",
    ),
) -> None:
    """Verify ASSERT_CONVENTION lines in a file against a convention lock."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.convention_checks import assert_convention_validate_payload, load_lock_from_project
    from gpd.core.errors import ConventionError

    if lock is not None and project_dir is not None:
        _error("Pass either --lock or --project-dir, not both.")

    _target, file_content = _load_text_document_or_error(file)

    if lock is not None:
        lock_document = _read_json_payload_argument(lock, option_label="--lock")
        if not isinstance(lock_document, dict):
            _error(f"Convention lock must be a JSON object: {lock}")
        lock_data: dict[str, object] = lock_document
    else:
        lock_root = _resolve_path_from_effective_cwd(project_dir) if project_dir is not None else _get_cwd()
        # Fail closed: without a state file there is no lock to assert against, and an
        # implicit empty lock would let every ASSERT_CONVENTION line pass vacuously.
        layout = ProjectLayout(lock_root)
        if not any(path.exists() for path in (layout.state_json, layout.state_json_backup, layout.state_md)):
            _emit_error_envelope(
                f"No convention lock is resolvable from {_format_display_path(lock_root)}: "
                "pass --lock <file|-> or run inside a GPD project that has state.json."
            )
        try:
            lock_data = load_lock_from_project(str(lock_root)).model_dump(exclude_none=True)
        except ConventionError as exc:
            _error(f"Could not resolve a convention lock from {_format_display_path(lock_root)}: {exc}")

    payload = assert_convention_validate_payload(file_content, lock_data)
    _output(payload)
    if payload.get("error") is not None or payload.get("valid") is not True:
        raise typer.Exit(code=1)


@convention_app.command("subfield-defaults")
def convention_subfield_defaults(
    domain: str = typer.Argument(..., help="Physics subfield domain key (e.g. qft, condensed_matter)"),
) -> None:
    """Show the recommended default conventions for a physics subfield."""
    from gpd.core.convention_checks import subfield_defaults_payload

    _emit_contract_check_payload(subfield_defaults_payload(domain))


# ═══════════════════════════════════════════════════════════════════════════
# result — Intermediate result tracking
# ═══════════════════════════════════════════════════════════════════════════

result_app = typer.Typer(help="Intermediate results with dependency tracking")
app.add_typer(result_app, name="result")


def _split_depends_on_option(depends_on: list[str] | str | None) -> list[str] | None:
    """Parse dependency IDs from repeated flags or comma-separated strings.

    Accepts ``list[str]`` (Typer multi-value), a single comma-separated
    ``str``, or ``None``.  Returns a flat list or ``None``.
    """
    if depends_on is None:
        return None
    items: list[str] = []
    source = depends_on if isinstance(depends_on, list) else [depends_on]
    for entry in source:
        items.extend(tok.strip() for tok in entry.split(","))
    result = [tok for tok in items if tok]
    return result or None


def _load_mutation_state_snapshot(cwd: Path) -> dict[str, object]:
    """Load one mutable state snapshot through the recovery-aware mutation path."""
    from gpd.core.state import _load_state_snapshot_for_mutation, _recover_intent_locked

    _recover_intent_locked(cwd)
    state = _load_state_snapshot_for_mutation(cwd, recover_intent=False)
    return state if isinstance(state, dict) else {}


def _resolve_derived_result_id(
    state: dict,
    *,
    result_id: str | None,
    derivation_slug: str | None,
    phase: str | None,
    equation: str | None,
    description: str | None,
) -> str | None:
    """Resolve a stable result ID for a derivation-oriented persistence request."""
    resolved_id = result_id.strip() if isinstance(result_id, str) else None
    if resolved_id:
        return resolved_id

    slug_source = derivation_slug or description or equation
    if not slug_source:
        return None

    from gpd.core.utils import generate_slug, phase_normalize

    slug = generate_slug(slug_source)
    if slug is None:
        return None

    resolved_phase = phase
    if resolved_phase is None:
        position = state.get("position", {})
        if isinstance(position, dict):
            current_phase = position.get("current_phase")
            if current_phase is not None:
                resolved_phase = str(current_phase)
    if resolved_phase is None:
        resolved_phase = "0"

    return f"R-{phase_normalize(str(resolved_phase)).replace('.', '_')}-{slug[:48]}"


def _sync_execution_visibility_projection(cwd: Path, *, state_obj: dict[str, object]) -> None:
    """Best-effort observability projection that never invents new execution state."""
    from gpd.core import observability as _observability

    helper = getattr(_observability, "sync_execution_visibility_from_canonical_continuation", None)
    if not callable(helper):
        return

    try:
        helper(cwd, state_obj=state_obj)
    except Exception as exc:
        logger.warning("Failed to sync execution visibility projection for %s: %s", cwd, exc, exc_info=True)


@result_app.command("add")
def result_add(
    id: str | None = typer.Option(None, "--id", help="Result ID"),
    equation: str | None = typer.Option(None, "--equation", help="LaTeX equation"),
    description: str | None = typer.Option(None, "--description", help="Description"),
    units: str | None = typer.Option(None, "--units", help="Physical units"),
    validity: str | None = typer.Option(None, "--validity", help="Validity range"),
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    depends_on: list[str] | None = typer.Option(None, "--depends-on", help="Dependency result ID (repeatable)"),
    verified: bool = typer.Option(False, "--verified", help="Mark as verified"),
) -> None:
    """Add an intermediate result to the results registry."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.results import result_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    deps = _split_depends_on_option(depends_on) or []
    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        res = result_add(
            state,
            result_id=id,
            equation=equation,
            description=description,
            units=units,
            validity=validity,
            phase=phase,
            depends_on=deps,
            verified=verified,
        )
        save_state_json_locked(cwd, state)
    _output(res)


@result_app.command("persist-derived")
def result_persist_derived(
    id: str | None = typer.Option(None, "--id", help="Stable result ID to reuse when present"),
    derivation_slug: str | None = typer.Option(
        None,
        "--derivation-slug",
        help="Slug for the derivation; used to derive a stable result ID when `--id` is absent",
    ),
    equation: str | None = typer.Option(None, "--equation", help="LaTeX equation"),
    description: str | None = typer.Option(None, "--description", help="Description"),
    units: str | None = typer.Option(None, "--units", help="Physical units"),
    validity: str | None = typer.Option(None, "--validity", help="Validity range"),
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    depends_on: list[str] | None = typer.Option(None, "--depends-on", help="Dependency result ID (repeatable)"),
    verified: bool | None = typer.Option(None, "--verified/--no-verified", help="Mark as verified or un-verify"),
) -> None:
    """Persist a derivation result through the canonical registry writer path."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.results import result_upsert_derived as _result_upsert_derived
    from gpd.core.state import (
        peek_state_json,
        save_state_json_locked,
    )
    from gpd.core.state import (
        state_carry_forward_continuation_last_result_id as _state_carry_forward_continuation_last_result_id,
    )
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    layout = ProjectLayout(cwd)
    state_path = layout.state_json

    preflight_state, _preflight_issues, _preflight_source = peek_state_json(cwd)
    if preflight_state is None:
        _output(
            {
                "status": "skipped",
                "reason": "no_recoverable_project_state",
                "state_exists": False,
                "recoverable_state_exists": False,
            }
        )
        return

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd) or preflight_state
        if not isinstance(state, dict):
            _error(f"state.json must be a JSON object, got {type(state).__name__}")

        resolved_id = _resolve_derived_result_id(
            state,
            result_id=id,
            derivation_slug=derivation_slug,
            phase=phase,
            equation=equation,
            description=description,
        )
        res = _result_upsert_derived(
            state,
            result_id=resolved_id,
            derivation_slug=derivation_slug,
            equation=equation,
            description=description,
            units=units,
            validity=validity,
            phase=phase,
            depends_on=_split_depends_on_option(depends_on),
            verified=verified,
        )
        payload = res.model_dump(mode="json")
        actual_result_id = payload["result"]["id"]
        continuity_result = _state_carry_forward_continuation_last_result_id(
            cwd,
            actual_result_id,
            state_obj=state,
        )
        continuity_recorded = bool(getattr(continuity_result, "updated", False))
        save_state_json_locked(cwd, state)

    _sync_execution_visibility_projection(cwd, state_obj=state)

    _output(
        {
            "status": "persisted",
            "requested_result_id": resolved_id,
            "result_id": actual_result_id,
            "requested_result_redirected": resolved_id is not None and actual_result_id != resolved_id,
            "continuity_last_result_id": actual_result_id,
            "continuity_recorded": continuity_recorded,
            **payload,
        }
    )


def _load_state_dict(cwd: Path | None = None) -> dict:
    """Load project state as a plain dictionary for read-only commands.

    This path is intentionally non-mutating so read-only surfaces do not create
    lockfiles, recovery writes, or nested stub directories when probing nested
    workspaces.
    """

    from gpd.core.state import peek_state_json

    project_cwd = _read_only_project_scoped_cwd(cwd)
    data, _issues, _state_source = peek_state_json(
        project_cwd,
        recover_intent=False,
        surface_blocked_project_contract=True,
        acquire_lock=False,
    )
    if data is None:
        return {}
    if not isinstance(data, dict):
        _error(f"state.json must be a JSON object, got {type(data).__name__}")
    return data


@result_app.command("list")
def result_list(
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase"),
    verified: bool = typer.Option(False, "--verified", help="Show only verified"),
    unverified: bool = typer.Option(False, "--unverified", help="Show only unverified"),
) -> None:
    """List intermediate results."""
    from gpd.core.results import result_list

    if verified and unverified:
        _error("--verified and --unverified are mutually exclusive")
    _output(result_list(_load_state_dict(), phase=phase, verified=verified, unverified=unverified))


@result_app.command("deps")
def result_deps(
    result_id: str = typer.Argument(..., help="Canonical result ID"),
) -> None:
    """Trace the direct and transitive upstream dependency chain for a canonical result."""
    from gpd.core.results import result_deps

    try:
        deps = result_deps(_load_state_dict(), result_id)
    except GPDError as exc:
        _error(str(exc))

    if _raw:
        _emit_raw_json(deps.model_dump(mode="json", by_alias=True))
        return

    _print_result_deps(deps)


@result_app.command("downstream")
def result_downstream(
    result_id: str = typer.Argument(..., help="Canonical result ID"),
) -> None:
    """Show the direct and transitive dependents of a canonical result."""
    from gpd.core.results import result_downstream

    try:
        downstream = result_downstream(_load_state_dict(), result_id)
    except GPDError as exc:
        _error(str(exc))

    if _raw:
        _emit_raw_json(downstream.model_dump(mode="json", by_alias=True))
        return

    _print_result_downstream(downstream)


def _print_result_show_dependencies(
    title: str,
    dependencies: list[object],
    *,
    empty_message: str,
) -> None:
    """Render a dependency chain for the result inspection surface."""
    console.print()
    console.print(Text(title, style=f"bold {_INSTALL_ACCENT_COLOR}"))
    if not dependencies:
        console.print(Text(empty_message, style="dim"))
        return

    table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    table.add_column("ID", style="bold")
    table.add_column("Type")
    table.add_column("Phase")
    table.add_column("Verified")
    table.add_column("Summary", overflow="fold")

    for dependency in dependencies:
        if getattr(dependency, "missing", False):
            table.add_row(
                str(getattr(dependency, "id", "—")),
                "missing",
                "—",
                "—",
                "dependency not found",
            )
            continue

        equation = getattr(dependency, "equation", None)
        description = getattr(dependency, "description", None)
        summary_parts = [part for part in (equation, description) if part]
        summary = " | ".join(summary_parts) if summary_parts else "—"
        table.add_row(
            str(getattr(dependency, "id", "—")),
            "result",
            str(getattr(dependency, "phase", None) or "—"),
            "yes" if getattr(dependency, "verified", False) else "no",
            summary,
        )

    console.print(table)


def _print_result_deps(result_deps: object) -> None:
    """Render one canonical result with direct and transitive dependencies."""
    result = getattr(result_deps, "result", None)
    if result is None:
        console.print(Text("Result unavailable", style="bold red"))
        return

    console.rule(f"Result {result.id}")
    _print_result_summary(result)

    _print_result_show_dependencies(
        "Direct dependencies",
        list(getattr(result_deps, "direct_deps", []) or []),
        empty_message="No direct dependencies",
    )
    _print_result_show_dependencies(
        "Transitive dependencies",
        list(getattr(result_deps, "transitive_deps", []) or []),
        empty_message="No transitive dependencies",
    )


def _print_result_summary(result: object) -> None:
    """Render the common summary table used by result inspection commands."""
    if result is None:
        console.print(Text("Result unavailable", style="bold red"))
        return

    summary = Table(show_header=False, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    summary.add_column("Field", style=f"bold {_INSTALL_ACCENT_COLOR}")
    summary.add_column("Value", overflow="fold")
    summary.add_row("Equation", result.equation or "—")
    summary.add_row("Description", result.description or "—")
    summary.add_row("Units", result.units or "—")
    summary.add_row("Validity", result.validity or "—")
    summary.add_row("Phase", result.phase or "—")
    summary.add_row("Verified", "yes" if result.verified else "no")
    summary.add_row("Declared deps", ", ".join(result.depends_on) if result.depends_on else "—")
    console.print(summary)


def _print_result_downstream(result_downstream: object) -> None:
    """Render one canonical result with direct and transitive dependents."""
    result = getattr(result_downstream, "result", None)
    if result is None:
        console.print(Text("Result unavailable", style="bold red"))
        return

    console.rule(f"Result {result.id}")
    _print_result_summary(result)

    _print_result_show_dependencies(
        "Direct dependents",
        list(getattr(result_downstream, "direct_dependents", []) or []),
        empty_message="No direct dependents",
    )
    _print_result_show_dependencies(
        "Transitive dependents",
        list(getattr(result_downstream, "transitive_dependents", []) or []),
        empty_message="No transitive dependents",
    )


def _print_result_show(result_deps: object) -> None:
    """Render one canonical result with direct and transitive dependencies."""
    _print_result_deps(result_deps)


@result_app.command("search")
def result_search(
    term: str | None = typer.Argument(None, help="Optional positional text search term"),
    id: str | None = typer.Option(None, "--id", help="Exact result ID"),
    text: str | None = typer.Option(None, "--text", help="Search id, equation, and description"),
    equation: str | None = typer.Option(None, "--equation", help="Search by equation"),
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase"),
    depends_on: str | None = typer.Option(
        None,
        "--depends-on",
        help="Match results that depend on this result ID directly or transitively",
    ),
    verified: bool = typer.Option(False, "--verified", help="Show only verified"),
    unverified: bool = typer.Option(False, "--unverified", help="Show only unverified"),
) -> None:
    """Search intermediate results in the canonical registry."""
    from gpd.core.results import result_search

    if verified and unverified:
        _error("--verified and --unverified are mutually exclusive")
    if term is not None:
        if text is not None:
            _error("Use either a positional search term or --text, not both")
        text = term

    _output(
        result_search(
            _load_state_dict(),
            id=id,
            text=text,
            equation=equation,
            phase=phase,
            depends_on=depends_on,
            verified=verified if verified else None,
            unverified=unverified if unverified else None,
        )
    )


@result_app.command("show")
def result_show(
    result_id: str = typer.Argument(..., help="Canonical result ID"),
) -> None:
    """Show a canonical result and its direct/transitive dependency chain."""
    from gpd.core.results import result_deps

    try:
        deps = result_deps(_load_state_dict(), result_id)
    except GPDError as exc:
        _error(str(exc))

    if _raw:
        _emit_raw_json(deps.model_dump(mode="json", by_alias=True))
        return

    _print_result_show(deps)


@result_app.command("upsert")
def result_upsert(
    id: str | None = typer.Option(None, "--id", help="Stable result ID to reuse when present"),
    equation: str | None = typer.Option(None, "--equation", help="LaTeX equation"),
    description: str | None = typer.Option(None, "--description", help="Description"),
    units: str | None = typer.Option(None, "--units", help="Physical units"),
    validity: str | None = typer.Option(None, "--validity", help="Validity range"),
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    depends_on: list[str] | None = typer.Option(None, "--depends-on", help="Dependency result ID (repeatable)"),
    verified: bool | None = typer.Option(None, "--verified/--no-verified", help="Mark as verified or un-verify"),
) -> None:
    """Add or update a canonical result by explicit ID or exact equation match."""

    from gpd.core.constants import ProjectLayout
    from gpd.core.results import result_upsert as _result_upsert
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        res = _result_upsert(
            state,
            result_id=id,
            equation=equation,
            description=description,
            units=units,
            validity=validity,
            phase=phase,
            depends_on=_split_depends_on_option(depends_on),
            verified=verified,
        )
        save_state_json_locked(cwd, state)
        _sync_execution_visibility_projection(cwd, state_obj=state)
    _output(res)


@result_app.command("verify")
def result_verify(
    result_id: str = typer.Argument(..., help="Result ID to mark verified"),
) -> None:
    """Mark a result as verified."""

    from gpd.core.constants import ProjectLayout
    from gpd.core.results import result_verify
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        res = result_verify(state, result_id)
        save_state_json_locked(cwd, state)
    _output(res)


@result_app.command("update")
def result_update(
    result_id: str = typer.Argument(..., help="Result ID to update"),
    equation: str | None = typer.Option(None, "--equation", help="LaTeX equation"),
    description: str | None = typer.Option(None, "--description", help="Description"),
    units: str | None = typer.Option(None, "--units", help="Physical units"),
    validity: str | None = typer.Option(None, "--validity", help="Validity range"),
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    depends_on: list[str] | None = typer.Option(None, "--depends-on", help="Dependency result ID (repeatable)"),
    verified: bool | None = typer.Option(None, "--verified/--no-verified", help="Mark as verified or un-verify"),
) -> None:
    """Update an existing result."""

    from gpd.core.constants import ProjectLayout
    from gpd.core.results import result_update
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    opts: dict[str, object] = {}
    if equation is not None:
        opts["equation"] = equation
    if description is not None:
        opts["description"] = description
    if units is not None:
        opts["units"] = units
    if validity is not None:
        opts["validity"] = validity
    if phase is not None:
        opts["phase"] = phase
    if depends_on is not None:
        opts["depends_on"] = _split_depends_on_option(depends_on) or []
    if verified is not None:
        opts["verified"] = verified

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        _fields, updated = result_update(state, result_id, **opts)
        save_state_json_locked(cwd, state)
        _sync_execution_visibility_projection(cwd, state_obj=state)
    _output(updated)


# ═══════════════════════════════════════════════════════════════════════════
# verify — Verification suite
# ═══════════════════════════════════════════════════════════════════════════

verify_app = typer.Typer(help="Verification checks on plans, summaries, and artifacts")
app.add_typer(verify_app, name="verify")


@verify_app.command("summary")
def verify_summary(
    path: str = typer.Argument(..., help="Path to SUMMARY.md"),
    check_count: int = typer.Option(2, "--check-count", help="Max file references to spot-check for existence"),
) -> None:
    """Verify a SUMMARY.md file."""
    from gpd.core.frontmatter import verify_summary

    result = verify_summary(_get_cwd(), Path(path), check_file_count=check_count)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


@verify_app.command("plan")
def verify_plan(
    path: str = typer.Argument(..., help="Path to plan file"),
) -> None:
    """Verify plan file structure."""
    from gpd.core.frontmatter import verify_plan_structure

    result = verify_plan_structure(_get_cwd(), Path(path))
    _output(result)
    if not result.valid:
        raise typer.Exit(code=1)


@verify_app.command("phase")
def verify_phase(
    phase: str = typer.Argument(..., help="Phase number"),
) -> None:
    """Verify phase completeness (all plans have summaries, etc.)."""
    from gpd.core.frontmatter import verify_phase_completeness

    result = verify_phase_completeness(_get_cwd(), phase)
    _output(result)
    if not result.complete:
        raise typer.Exit(code=1)


@verify_app.command("references")
def verify_references(
    path: str = typer.Argument(..., help="Path to file"),
) -> None:
    """Verify all internal references resolve."""
    from gpd.core.frontmatter import verify_references

    result = verify_references(_get_cwd(), Path(path))
    _output(result)
    if not result.valid:
        raise typer.Exit(code=1)


@verify_app.command("commits")
def verify_commits(
    hashes: list[str] = typer.Argument(..., help="Commit hashes to verify"),
) -> None:
    """Verify that commit hashes exist in git history."""
    from gpd.core.frontmatter import verify_commits

    result = verify_commits(_get_cwd(), hashes)
    _output(result)
    if not result.all_valid:
        raise typer.Exit(code=1)


@verify_app.command("artifacts")
def verify_artifacts(
    plan_path: str = typer.Argument(..., help="Path to plan file"),
) -> None:
    """Verify all artifacts referenced in a plan exist."""
    from gpd.core.frontmatter import verify_artifacts

    result = verify_artifacts(_get_cwd(), Path(plan_path))
    _output(result)
    if not result.all_passed:
        raise typer.Exit(code=1)


def _read_json_payload_argument(source: str, *, option_label: str) -> object:
    """Load a JSON payload from a file or piped stdin, refusing an interactive stdin."""

    if source == "-" and sys.stdin.isatty():
        _error(f"Usage: {option_label} - requires JSON piped on stdin. Pass a file path instead.")
    return _load_json_document_or_error(source)


def _resolve_optional_project_dir(project_dir: str | None) -> str | None:
    """Return the absolute project root a contract-aware check should resolve anchors against."""

    if project_dir is None:
        return None
    return str(_resolve_path_from_effective_cwd(project_dir))


def _emit_error_envelope(message: str) -> NoReturn:
    """Emit the stable error envelope on stdout and exit 1, matching the MCP tool contract."""

    from gpd.core.envelopes import stable_mcp_error

    _output(stable_mcp_error(message))
    raise typer.Exit(code=1)


def _emit_contract_check_payload(payload: dict[str, object], *, failed: bool = False) -> None:
    """Emit a tool envelope and fail the command on an error, a failed lookup, or a caller-detected failure."""

    _output(payload)
    if failed or payload.get("error") is not None or payload.get("found") is False:
        raise typer.Exit(code=1)


def _split_repeatable_csv_option(values: list[str] | None) -> list[str]:
    """Flatten a repeatable option whose values may also be comma-separated."""

    flattened: list[str] = []
    for value in values or []:
        flattened.extend(item.strip() for item in value.split(",") if item.strip())
    return flattened


@verify_app.command("contract-check")
def verify_contract_check(
    payload: str | None = typer.Option(
        None,
        "--payload",
        help="Path to a run-contract-check request JSON file, or '-' for stdin",
    ),
    project_dir: str | None = typer.Option(
        None,
        "--project-dir",
        help="Project root used to resolve contract anchors and prior-output paths",
    ),
    schema: bool = typer.Option(
        False,
        "--schema",
        help="Print the contract-check payload model's pydantic JSON schema and exit without running a check.",
    ),
) -> None:
    """Run one contract-aware verification check from a structured request payload.

    Exits 1 when the check result reports `status: fail`, so CI callers can gate on `$?`.
    """
    from gpd.core.contract_checks import RunContractCheckRequest, run_contract_check

    if schema:
        _output(RunContractCheckRequest.model_json_schema())
        return
    if payload is None:
        _error("Usage: --payload <file|-> is required unless --schema is passed.")

    request = _read_json_payload_argument(payload, option_label="--payload")
    result = run_contract_check(request, _resolve_optional_project_dir(project_dir))
    _emit_contract_check_payload(result, failed=result.get("status") == "fail")


@verify_app.command("suggest-checks")
def verify_suggest_checks(
    contract: str = typer.Option(
        ...,
        "--contract",
        help="Path to a project or phase contract JSON file, or '-' for stdin",
    ),
    active_checks: list[str] | None = typer.Option(
        None,
        "--active-checks",
        help="Already-enabled check ids or check keys as a comma-separated list; repeat the option for several.",
    ),
    project_dir: str | None = typer.Option(
        None,
        "--project-dir",
        help="Project root used to resolve contract anchors and prior-output paths",
    ),
) -> None:
    """Suggest contract-aware checks for a schema-validated contract."""
    from gpd.core.contract_checks import suggest_contract_checks

    contract_payload = _read_json_payload_argument(contract, option_label="--contract")
    split_active_checks = _split_repeatable_csv_option(active_checks)
    _emit_contract_check_payload(
        suggest_contract_checks(
            contract_payload,
            split_active_checks or None,
            _resolve_optional_project_dir(project_dir),
        )
    )


@verify_app.command("bundle-checklist")
def verify_bundle_checklist(
    bundle_ids: list[str] = typer.Argument(..., help="Protocol bundle ids to expand into verifier checklist items"),
) -> None:
    """Show additive verifier checklist extensions for the selected protocol bundles.

    Exits 1 when any requested bundle id is unknown, so callers can gate on `$?`.
    """
    from gpd.core.contract_checks import get_bundle_checklist

    result = get_bundle_checklist(list(bundle_ids))
    _emit_contract_check_payload(result, failed=bool(result.get("missing_bundle_ids")))


@verify_app.command("checklist")
def verify_checklist(
    domain: str = typer.Argument(..., help="Physics domain key (e.g. qft, condensed_matter)"),
) -> None:
    """Show the domain-specific verification checklist and the universal checks."""
    from gpd.core.contract_checks import get_checklist

    _emit_contract_check_payload(get_checklist(domain))


@verify_app.command("coverage")
def verify_coverage(
    error_classes: list[str] = typer.Option(
        ...,
        "--error-classes",
        help="Error class ids as a comma-separated list; repeat the option for several.",
    ),
    active_checks: list[str] = typer.Option(
        ...,
        "--active-checks",
        help="Active check ids as a comma-separated list; repeat the option for several.",
    ),
) -> None:
    """Show which error classes the active verification checks cover."""
    from gpd.core.contract_checks import get_verification_coverage

    raw_error_classes = _split_repeatable_csv_option(error_classes)
    if not raw_error_classes:
        _error("Usage: --error-classes requires at least one error class id.")
    # ``isdecimal`` (not ``isdigit``) is what ``int()`` actually accepts: it rejects
    # superscripts like "²" as well as signed forms such as "-5" and a bare "-".
    non_numeric = [item for item in raw_error_classes if not item.isdecimal()]
    if non_numeric:
        _emit_error_envelope(
            f"--error-classes must be non-negative integer error class ids; got {', '.join(non_numeric)}"
        )
    error_class_ids = list(dict.fromkeys(int(item) for item in raw_error_classes))
    _emit_contract_check_payload(
        get_verification_coverage(error_class_ids, _split_repeatable_csv_option(active_checks))
    )


# ═══════════════════════════════════════════════════════════════════════════
# refs — Read-only physics reference catalogs (error classes, protocols)
# ═══════════════════════════════════════════════════════════════════════════

refs_app = typer.Typer(help="Read-only physics reference catalogs (error classes, protocols)")
app.add_typer(refs_app, name="refs")


@refs_app.command("errors")
def refs_errors(
    domain: str | None = typer.Option(None, "--domain", help="Filter the listing to one error-catalog domain"),
    error_id: int | None = typer.Option(None, "--id", help="Show one error class by numeric id"),
    detection: bool = typer.Option(False, "--detection", help="With --id, show the detection strategy instead"),
    traceability: bool = typer.Option(False, "--traceability", help="With --id, show the check coverage instead"),
) -> None:
    """List physics error classes, or inspect one class by id."""
    from gpd.core import error_catalog
    from gpd.core.envelopes import stable_mcp_response

    if detection and traceability:
        _error("Pass either --detection or --traceability, not both.")
    if (detection or traceability) and error_id is None:
        _error("--detection and --traceability require --id.")
    if domain is not None and error_id is not None:
        _error("Pass either --domain or --id, not both.")

    try:
        store = error_catalog.get_error_store()
        if error_id is None:
            payload = error_catalog.list_error_classes(store, error_catalog.normalize_error_domain(domain))
        elif detection:
            payload = error_catalog.get_detection_strategy(store, error_id)
        elif traceability:
            payload = error_catalog.get_traceability(store, error_id)
        else:
            payload = error_catalog.get_error_class(store, error_id)
    except (OSError, ValueError, KeyError) as exc:
        _emit_error_envelope(str(exc))

    _emit_contract_check_payload(stable_mcp_response(payload))


@refs_app.command("protocols")
def refs_protocols(
    domain: str | None = typer.Option(None, "--domain", help="Filter the listing to one protocol domain"),
    name: str | None = typer.Option(None, "--name", help="Show one protocol by name (the .md file stem)"),
    route: str | None = typer.Option(None, "--route", help="Auto-select protocols for a computation description"),
    checkpoints: str | None = typer.Option(
        None, "--checkpoints", help="Show the verification checkpoints for one protocol"
    ),
) -> None:
    """List physics computation protocols, or inspect, route, or checkpoint one."""
    from gpd.core.envelopes import stable_mcp_response
    from gpd.core.protocol_catalog import (
        available_protocol_names,
        get_protocol_store,
        protocol_checkpoints_payload,
        protocol_detail_payload,
        protocol_listing_payload,
        protocol_route_payload,
    )

    selectors = [selector for selector in (name, route, checkpoints) if selector is not None]
    if len(selectors) > 1:
        _error("Pass at most one of --name, --route, or --checkpoints.")
    if domain is not None and selectors:
        _error("Pass either --domain or one of --name, --route, or --checkpoints, not both.")
    for option_label, value in (("--name", name), ("--route", route), ("--checkpoints", checkpoints)):
        if value is not None and not value.strip():
            _error(f"{option_label} requires a non-empty value.")

    try:
        store = get_protocol_store()
        if name is not None:
            payload = protocol_detail_payload(store, name)
            if payload is None:
                _output(
                    stable_mcp_response(
                        {"available": available_protocol_names(store)},
                        error=f"Protocol '{name}' not found",
                    )
                )
                raise typer.Exit(code=1)
        elif checkpoints is not None:
            payload = protocol_checkpoints_payload(store, checkpoints)
            if payload is None:
                _output(
                    stable_mcp_response(
                        {"available": available_protocol_names(store)},
                        error=f"Protocol '{checkpoints}' not found",
                    )
                )
                raise typer.Exit(code=1)
        elif route is not None:
            payload = protocol_route_payload(store, route)
        else:
            payload = protocol_listing_payload(store, domain)
    except (OSError, ValueError, KeyError) as exc:
        _emit_error_envelope(str(exc))

    _emit_contract_check_payload(stable_mcp_response(payload))


# ═══════════════════════════════════════════════════════════════════════════
# frontmatter — YAML frontmatter CRUD
# ═══════════════════════════════════════════════════════════════════════════

frontmatter_app = typer.Typer(help="YAML frontmatter operations on markdown files")
app.add_typer(frontmatter_app, name="frontmatter")


@frontmatter_app.command("get")
def frontmatter_get(
    file: str = typer.Argument(..., help="Markdown file path"),
    field: str | None = typer.Option(None, "--field", help="Specific field to get"),
) -> None:
    """Get frontmatter from a markdown file."""
    from gpd.core.frontmatter import extract_frontmatter

    file_path = _get_cwd() / file
    try:
        fm_content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _error(f"File not found: {file}")
    meta, _ = extract_frontmatter(fm_content)
    if field:
        _output(meta.get(field))
    else:
        _output(meta)


@frontmatter_app.command("set")
def frontmatter_set(
    file: str = typer.Argument(..., help="Markdown file path"),
    field: str = typer.Option(..., "--field", help="Field name"),
    value: str | None = typer.Option(None, "--value", help="Field value (omit to clear)"),
) -> None:
    """Set a frontmatter field."""
    from gpd.core.frontmatter import splice_frontmatter

    file_path = _get_cwd() / file
    try:
        fm_content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _error(f"File not found: {file}")
    updated = splice_frontmatter(fm_content, {field: value})
    file_path.write_text(updated, encoding="utf-8")
    _output({"updated": field, "value": value})


@frontmatter_app.command("merge")
def frontmatter_merge(
    file: str = typer.Argument(..., help="Markdown file path"),
    data: str = typer.Option(..., "--data", help="JSON data to merge"),
) -> None:
    """Merge JSON data into frontmatter."""
    from gpd.core.frontmatter import deep_merge_frontmatter

    try:
        merge_data = json.loads(data)
    except json.JSONDecodeError as e:
        _error(f"Malformed JSON in --data: {e}")
    file_path = _get_cwd() / file
    try:
        fm_content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _error(f"File not found: {file}")
    updated = deep_merge_frontmatter(fm_content, merge_data)
    file_path.write_text(updated, encoding="utf-8")
    _output({"merged": True, "file": file})


@frontmatter_app.command("validate")
def frontmatter_validate(
    file: str = typer.Argument(..., help="Markdown file path"),
    schema: str = typer.Option(..., "--schema", help="Schema name to validate against"),
) -> None:
    """Validate frontmatter against a schema."""
    _run_frontmatter_validation(file, schema)


def _run_frontmatter_validation(file: str, schema: str) -> None:
    """Validate one markdown file against a named frontmatter schema."""

    from gpd.core.frontmatter import validate_frontmatter

    file_path, fm_content = _load_text_document(file)
    result = validate_frontmatter(fm_content, schema, source_path=file_path)
    _output(result)
    if not result.valid:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# health — Project health checks
# ═══════════════════════════════════════════════════════════════════════════


@app.command("health")
def health(
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues where possible"),
) -> None:
    """Run the project health diagnostic."""
    from gpd.core.health import run_health

    cwd = _project_scoped_cwd() if fix else _read_only_project_scoped_cwd()
    report = run_health(cwd, fix=fix)
    _output(report)
    if report.overall == "fail":
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# doctor — Environment diagnostics
# ═══════════════════════════════════════════════════════════════════════════


@app.command("doctor")
def doctor(
    runtime: str | None = typer.Option(None, "--runtime", help=_runtime_override_help()),
    global_install: bool = typer.Option(False, "--global", help="Check the runtime's global install target"),
    local_install: bool = typer.Option(False, "--local", help="Check the runtime's local install target (default)"),
    target_dir: str | None = typer.Option(
        None,
        "--target-dir",
        help="Override the runtime config directory to inspect",
    ),
    live_executable_probes: bool = typer.Option(
        False,
        "--live-executable-probes",
        help="Run cheap local executable probes such as `pdflatex --version`, `tectonic --version`, or `wolframscript -version`",
    ),
) -> None:
    """Check GPD installation and environment health, or inspect runtime readiness."""
    from gpd.core.health import run_doctor
    from gpd.specs import SPECS_DIR

    if global_install and local_install:
        _error("Cannot specify both --global and --local")

    if runtime is None:
        if global_install or local_install or target_dir is not None:
            _error("--runtime is required when using --global, --local, or --target-dir")
        _output(run_doctor(specs_dir=SPECS_DIR, live_executable_probes=live_executable_probes))
        return

    normalized_runtime = _normalize_runtime_selection([runtime], action="doctor")[0]
    resolved_target = _resolve_cli_target_dir(target_dir) if target_dir is not None else None
    install_scope = (
        "global"
        if global_install
        else "local"
        if local_install
        else "global"
        if target_dir and _target_dir_matches_global(normalized_runtime, target_dir, action="doctor")
        else "local"
    )
    if target_dir is None and not global_install and not local_install:
        resolved_target = _get_adapter_or_error(normalized_runtime, action="doctor").resolve_target_dir(
            False, _get_cwd()
        )
    _output(
        run_doctor(
            specs_dir=SPECS_DIR,
            runtime=normalized_runtime,
            install_scope=install_scope,
            target_dir=resolved_target,
            cwd=_get_cwd(),
            live_executable_probes=live_executable_probes,
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# diagnostics — Read-only source diagnostics
# ═══════════════════════════════════════════════════════════════════════════

diagnostics_app = typer.Typer(help="Read-only source and prompt diagnostics")
app.add_typer(diagnostics_app, name="diagnostics")

_PROMPT_DIAGNOSTIC_FORMATS = frozenset({"table", "markdown", "dashboard", "json"})
_PROMPT_DIAGNOSTIC_SURFACES = ("command", "agent", "workflow")


def _normalize_prompt_diagnostic_format(output_format: str) -> str:
    normalized = output_format.strip().casefold()
    if normalized not in _PROMPT_DIAGNOSTIC_FORMATS:
        allowed = ", ".join(sorted(_PROMPT_DIAGNOSTIC_FORMATS))
        _error(f"Unknown diagnostics prompt-surface --format {output_format!r}. Supported: {allowed}")
    return normalized


def _normalize_prompt_diagnostic_surfaces(surface: str) -> tuple[str, ...]:
    normalized = surface.strip().casefold()
    if normalized == "all":
        return _PROMPT_DIAGNOSTIC_SURFACES
    if normalized not in _PROMPT_DIAGNOSTIC_SURFACES:
        allowed = ", ".join((*_PROMPT_DIAGNOSTIC_SURFACES, "all"))
        _error(f"Unknown diagnostics prompt-surface --surface {surface!r}. Supported: {allowed}")
    return (normalized,)


def _normalize_prompt_diagnostic_runtime_names(
    runtime: str,
    *,
    include_runtime_projections: bool,
) -> tuple[str, ...]:
    if not include_runtime_projections:
        return ()

    normalized = runtime.strip().casefold()
    if normalized == "all":
        return tuple(list_runtime_names())

    canonical_runtime = normalize_runtime_name(runtime)
    supported = set(list_runtime_names())
    if canonical_runtime is None or canonical_runtime not in supported:
        allowed = ", ".join((*list_runtime_names(), "all"))
        _error(f"Unknown diagnostics prompt-surface --runtime {runtime!r}. Supported: {allowed}")
    return (canonical_runtime,)


def _print_prompt_diagnostic_rendered(rendered: object) -> None:
    if rendered is None:
        return
    if isinstance(rendered, str):
        console.out(rendered, highlight=False, end="")
        return
    console.print(rendered)


def _prompt_diagnostic_repo_root() -> Path:
    """Return the source checkout root that owns the packaged prompt files."""

    package_dir = Path(__file__).resolve().parent
    if package_dir.parent.name == "src":
        return package_dir.parent.parent
    return package_dir


@diagnostics_app.command("prompt-surface")
def diagnostics_prompt_surface(
    output_format: str = typer.Option(
        "table",
        "--format",
        help="Output format for non-raw display: table, markdown, dashboard, or json.",
    ),
    surface: str = typer.Option(
        "all",
        "--surface",
        help="Prompt source surface to report: command, agent, workflow, or all.",
    ),
    runtime: str = typer.Option(
        "all",
        "--runtime",
        help="Runtime projection to include: all or a runtime id/alias.",
    ),
    top: int = typer.Option(20, "--top", help="Number of largest or highest-pressure rows to display."),
    include_runtime_projections: bool = typer.Option(
        True,
        "--runtime-projections/--no-runtime-projections",
        help="Include final runtime-projected prompt-size metrics.",
    ),
    include_tests: bool = typer.Option(
        False,
        "--include-tests",
        help="Include advisory prompt-facing test exactness diagnostics.",
    ),
) -> None:
    """Report read-only diagnostics for GPD prompt and runtime surfaces."""
    normalized_format = _normalize_prompt_diagnostic_format(output_format)
    surfaces = _normalize_prompt_diagnostic_surfaces(surface)
    runtime_names = _normalize_prompt_diagnostic_runtime_names(
        runtime,
        include_runtime_projections=include_runtime_projections,
    )
    if top < 1:
        _error("diagnostics prompt-surface --top must be >= 1")

    from gpd.core import prompt_diagnostics

    report = prompt_diagnostics.build_prompt_surface_report(
        _prompt_diagnostic_repo_root(),
        surfaces=surfaces,
        runtime_names=runtime_names,
        include_tests=include_tests,
        top=top,
        include_runtime_projections=include_runtime_projections,
    )

    payload = prompt_diagnostics.report_to_dict(report, top=top)
    if _raw:
        _output(payload)
        return
    if normalized_format == "json":
        _emit_raw_json(payload)
        return
    if normalized_format == "dashboard":
        from gpd.core import prompt_surface_dashboard

        _print_prompt_diagnostic_rendered(prompt_surface_dashboard.render_prompt_surface_dashboard(report, top))
        return
    if normalized_format == "markdown":
        _print_prompt_diagnostic_rendered(prompt_diagnostics.render_prompt_surface_markdown(report, top))
        return
    _print_prompt_diagnostic_rendered(prompt_diagnostics.render_prompt_surface_table(report, top))


# ═══════════════════════════════════════════════════════════════════════════
# query — Cross-phase dependency and search
# ═══════════════════════════════════════════════════════════════════════════

query_app = typer.Typer(help="Cross-phase search and dependency tracing")
app.add_typer(query_app, name="query")


@query_app.command("search")
def query_search(
    provides: str | None = typer.Option(None, "--provides", help="Search by provides"),
    requires: str | None = typer.Option(None, "--requires", help="Search by requires"),
    affects: str | None = typer.Option(None, "--affects", help="Search by affects"),
    equation: str | None = typer.Option(None, "--equation", help="Search by equation"),
    text: str | None = typer.Option(None, "--text", help="Full-text search"),
    phase_range: str | None = typer.Option(None, "--phase-range", help="Phase range filter (e.g. 10-20)"),
    scope: str = typer.Option("summary", "--scope", help="Search scope: summary (default), phase, all"),
) -> None:
    """Search across phases by provides/requires/text."""
    from gpd.core.query import query as query_search

    _output(
        query_search(
            _project_scoped_cwd(),
            provides=provides,
            requires=requires,
            affects=affects,
            equation=equation,
            text=text,
            phase_range=phase_range,
            scope=scope,
        )
    )


@query_app.command("deps")
def query_deps(
    identifier: str = typer.Argument(..., help="Result identifier to trace dependencies for"),
) -> None:
    """Show what provides and requires a given result identifier."""
    from gpd.core.query import query_deps

    _output(query_deps(_project_scoped_cwd(), identifier))


@query_app.command("assumptions")
def query_assumptions(
    assumption: list[str] = typer.Argument(None, help="Assumption text to search for"),
) -> None:
    """Search for assumptions across phases."""
    from gpd.core.query import query_assumptions

    text = " ".join(assumption) if assumption else ""
    if not text.strip():
        _error("Usage: gpd query assumptions <search-term>")
    _output(query_assumptions(_project_scoped_cwd(), text))


# ═══════════════════════════════════════════════════════════════════════════
# suggest — Next-action intelligence
# ═══════════════════════════════════════════════════════════════════════════


@app.command("suggest")
def suggest(
    limit: int | None = typer.Option(None, "--limit", help="Max suggestions to return"),
) -> None:
    """Suggest what to do next based on project state."""
    from gpd.core.suggest import suggest_next

    kwargs: dict[str, int] = {}
    if limit is not None:
        kwargs["limit"] = limit
    suggest_cwd = _read_only_project_scoped_cwd()
    _output(suggest_next(suggest_cwd, **kwargs))


@app.command("suggest-next")
def suggest_next_bridge(
    limit: int | None = typer.Option(None, "--limit", help="Max suggestions to return"),
) -> None:
    """Alias for the runtime suggest-next command on the local raw bridge."""
    suggest(limit=limit)


# ═══════════════════════════════════════════════════════════════════════════
# pattern — Error pattern library
# ═══════════════════════════════════════════════════════════════════════════

pattern_app = typer.Typer(help="Error pattern library (8 categories, 13 domains)")
app.add_typer(pattern_app, name="pattern")


def _resolve_patterns_root() -> Path:
    """Resolve pattern library root respecting GPD_PATTERNS_ROOT env var.

    Uses the same resolution order as gpd.core.patterns.patterns_root:
    GPD_PATTERNS_ROOT env > GPD_DATA_DIR env > ~/.gpd/learned-patterns.
    """
    from gpd.core.patterns import patterns_root

    return patterns_root(specs_root=_get_cwd())


@pattern_app.command("init")
def pattern_init() -> None:
    """Initialize the error pattern library."""
    from gpd.core.patterns import pattern_init

    _output({"path": str(pattern_init(root=_resolve_patterns_root()))})


@pattern_app.command("add")
def pattern_add(
    domain: str | None = typer.Option(None, "--domain", help="Physics domain"),
    category: str | None = typer.Option(None, "--category", help="Error category"),
    severity: str | None = typer.Option(None, "--severity", help="Severity level"),
    title: str | None = typer.Option(None, "--title", help="Pattern title"),
    description: str | None = typer.Option(None, "--description", help="Pattern description"),
    detection: str | None = typer.Option(None, "--detection", help="How to detect"),
    prevention: str | None = typer.Option(None, "--prevention", help="How to prevent"),
    example: str | None = typer.Option(None, "--example", help="Example"),
    test_value: str | None = typer.Option(None, "--test-value", help="Test value"),
) -> None:
    """Add a new error pattern."""
    from gpd.core.patterns import pattern_add

    _output(
        pattern_add(
            domain=domain or "",
            title=title or "",
            category=category or "conceptual-error",
            severity=severity or "medium",
            description=description or "",
            detection=detection or "",
            prevention=prevention or "",
            example=example or "",
            test_value=test_value or "",
            root=_resolve_patterns_root(),
        )
    )


@pattern_app.command("list")
def pattern_list(
    domain: str | None = typer.Option(None, "--domain", help="Filter by domain"),
    category: str | None = typer.Option(None, "--category", help="Filter by category"),
    severity: str | None = typer.Option(None, "--severity", help="Filter by severity"),
) -> None:
    """List error patterns with optional filters."""
    from gpd.core.patterns import pattern_list

    _output(pattern_list(domain=domain, category=category, severity=severity, root=_resolve_patterns_root()))


@pattern_app.command("search")
def pattern_search(
    query: list[str] = typer.Argument(..., help="Search query"),
) -> None:
    """Search error patterns by text."""
    from gpd.core.patterns import pattern_search

    _output(pattern_search(" ".join(query), root=_resolve_patterns_root()))


@pattern_app.command("promote")
def pattern_promote(
    pattern_id: str = typer.Argument(..., help="Pattern ID to promote"),
) -> None:
    """Promote a pattern's confidence level (single_observation -> confirmed -> systematic)."""
    from gpd.core.patterns import pattern_promote

    _output(pattern_promote(pattern_id, root=_resolve_patterns_root()))


@pattern_app.command("seed")
def pattern_seed() -> None:
    """Seed the pattern library with common physics error patterns."""
    from gpd.core.patterns import pattern_seed

    _output(pattern_seed(root=_resolve_patterns_root()))


# ═══════════════════════════════════════════════════════════════════════════
# trace — JSONL execution tracing
# ═══════════════════════════════════════════════════════════════════════════

trace_app = typer.Typer(help="Trace inspection and recording: show is read-only; start/log/stop write trace state")
app.add_typer(trace_app, name="trace")


@trace_app.command("start")
def trace_start(
    phase: str = typer.Argument(..., help="Phase number"),
    plan: str = typer.Argument(..., help="Plan name"),
) -> None:
    """Start a new trace session (writes trace state)."""
    from gpd.core.trace import trace_start

    _output(trace_start(_get_cwd(), phase, plan))


@trace_app.command("log")
def trace_log(
    event: str = typer.Argument(..., help="Event type"),
    data: str | None = typer.Option(None, "--data", help="JSON event data"),
) -> None:
    """Record an event to the active trace (writes trace log)."""
    from gpd.core.trace import trace_log

    parsed_data = None
    if data:
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            parsed_data = {"raw": data}
    _output(trace_log(_get_cwd(), event, data=parsed_data))


@trace_app.command("stop")
def trace_stop() -> None:
    """Stop the active trace session (writes trace and observability state)."""
    from gpd.core.trace import trace_stop

    _output(trace_stop(_get_cwd()))


@trace_app.command("show")
def trace_show(
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase"),
    plan: str | None = typer.Option(None, "--plan", help="Filter by plan"),
    event_type: str | None = typer.Option(None, "--type", help="Filter by event type"),
    last: int | None = typer.Option(None, "--last", help="Show last N events"),
) -> None:
    """Inspect trace events with optional filters without modifying project state."""
    from gpd.core.trace import trace_show

    _output(trace_show(_get_cwd(), phase=phase, plan=plan, event_type=event_type, last=last))


# ═══════════════════════════════════════════════════════════════════════════
# observe — Local observability logs
# ═══════════════════════════════════════════════════════════════════════════


@dataclasses.dataclass(frozen=True)
class ObserveExecutionSuggestion:
    """One suggested follow-up command for a live execution snapshot."""

    command: str
    reason: str


@dataclasses.dataclass(frozen=True)
class ObserveExecutionResult:
    """Read-only execution snapshot for local CLI inspection."""

    found: bool
    workspace: str
    phase: str | None
    plan: str | None
    status_classification: str
    current_state: str | None
    assessment: str
    possibly_stalled: bool
    stale_after_minutes: int
    current_task: str | None
    waiting_reason: str | None
    waiting_reason_label: str | None
    blocked_reason: str | None
    blocked_reason_label: str | None
    review_reason: str | None
    tangent_summary: str | None
    tangent_decision: str | None
    tangent_decision_label: str | None
    tangent_pending: bool
    tangent_follow_up: list[str]
    last_update_at: str | None
    last_update_age: str | None
    last_update_age_minutes: float | None
    resume_file: str | None
    next_check_command: str | None
    next_check_reason: str | None
    suggested_next_steps: list[str]
    suggested_next_commands: list[ObserveExecutionSuggestion]
    current_execution: dict[str, object] | None = None


def _observe_execution_status_note(result: ObserveExecutionResult) -> str | None:
    """Return a short human note that clarifies the live execution state."""
    if not result.found:
        return None
    if result.possibly_stalled:
        return (
            f"[yellow]This execution is possibly stalled.[/] It is still marked active and has not updated for at least "
            f"{result.stale_after_minutes} minutes."
        )
    if result.status_classification == "waiting":
        return "[cyan]This execution is waiting on review or another gate.[/] It is not currently treated as stalled."
    if result.status_classification == "paused-or-resumable":
        return f"[cyan]This execution is paused or resumable.[/] Use `{local_cli_resume_command()}` to inspect the best recovery target."
    if result.status_classification == "blocked":
        return f"[yellow]This execution is blocked.[/] Use `{local_cli_resume_command()}` and the recent event trail to inspect the blocker context."
    return None


def _observe_execution_tangent_follow_up(
    *,
    tangent_summary: str | None,
    tangent_decision: str | None,
    tangent_pending: bool,
) -> list[str]:
    if not tangent_summary:
        return []
    if tangent_pending:
        return [
            "Use the runtime `tangent` command to choose stay / quick / defer / branch for this alternative path.",
            "Use the runtime `branch-hypothesis` command only after that explicit choice.",
        ]
    if tangent_decision == "branch_later":
        return tangent_branch_later_follow_up_lines()
    if tangent_decision == "defer":
        return [
            "This tangent was classified as capture and defer. Keep the current run bounded unless you intentionally reopen it."
        ]
    if tangent_decision == "pursue_now":
        return [
            "This tangent is approved to pursue now within the current bounded stop. Keep the side investigation explicit and limited."
        ]
    if tangent_decision == "ignore":
        return ["This tangent was classified as stay on the main path. Keep the current run bounded."]
    return []


def _observe_execution_payload() -> ObserveExecutionResult:
    """Build the read-only execution snapshot for the local CLI surface."""
    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(_get_cwd())
    if visibility is None:
        visibility = derive_execution_visibility(Path.cwd())
    if visibility is None:
        raise GPDError("Local observability unavailable for this working directory")

    status_classification = str(visibility.status_classification or "idle")
    current_state = status_classification.replace("-", " ")
    assessment = str(visibility.assessment or status_classification).replace("-", " ")
    suggested_next_steps = [str(step).strip() for step in visibility.suggested_next_steps if str(step).strip()]
    suggested_next_commands = [
        ObserveExecutionSuggestion(command=item.command, reason=item.reason)
        for item in visibility.suggested_next_commands
        if item.command.strip() and item.reason.strip()
    ]
    next_check = suggested_next_commands[0] if suggested_next_commands else None
    tangent_follow_up = _observe_execution_tangent_follow_up(
        tangent_summary=visibility.tangent_summary,
        tangent_decision=visibility.tangent_decision,
        tangent_pending=visibility.tangent_pending,
    )

    return ObserveExecutionResult(
        found=visibility.has_live_execution,
        workspace=_format_display_path(visibility.workspace_root or _get_cwd()),
        phase=visibility.phase,
        plan=visibility.plan,
        status_classification=status_classification,
        current_state=current_state,
        assessment=assessment,
        possibly_stalled=visibility.possibly_stalled,
        stale_after_minutes=visibility.stale_after_minutes,
        current_task=visibility.current_task,
        waiting_reason=visibility.waiting_reason,
        waiting_reason_label=visibility.waiting_reason_label,
        blocked_reason=visibility.blocked_reason,
        blocked_reason_label=visibility.blocked_reason_label,
        review_reason=visibility.review_reason,
        tangent_summary=visibility.tangent_summary,
        tangent_decision=visibility.tangent_decision,
        tangent_decision_label=visibility.tangent_decision_label,
        tangent_pending=visibility.tangent_pending,
        tangent_follow_up=tangent_follow_up,
        last_update_at=visibility.last_updated_at,
        last_update_age=visibility.last_updated_age_label,
        last_update_age_minutes=visibility.last_updated_age_minutes,
        resume_file=visibility.resume_file,
        next_check_command=next_check.command if next_check is not None else None,
        next_check_reason=next_check.reason if next_check is not None else None,
        suggested_next_steps=suggested_next_steps,
        suggested_next_commands=suggested_next_commands,
        current_execution=visibility.current_execution,
    )


def _render_observe_execution(result: ObserveExecutionResult) -> None:
    """Render a human-friendly local execution snapshot."""
    console.print("[bold]Execution Status[/]")
    console.print("[dim]Read-only local snapshot from core observability.[/]")
    console.print()

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style=f"bold {_INSTALL_ACCENT_COLOR}")
    summary.add_column()
    summary.add_row("Workspace", result.workspace)
    if result.phase or result.plan:
        phase_plan = " / ".join(part for part in (result.phase, result.plan) if part)
        summary.add_row("Phase/Plan", phase_plan or "—")
    summary.add_row("Current state", result.current_state or "unknown")
    summary.add_row("Assessment", result.assessment)
    summary.add_row("Current task", result.current_task or "—")
    summary.add_row("Waiting reason", result.waiting_reason_label or result.waiting_reason or "—")
    summary.add_row("Blocked reason", result.blocked_reason_label or result.blocked_reason or "—")
    summary.add_row("Review reason", result.review_reason or "—")
    if result.tangent_summary:
        summary.add_row("Tangent proposal", result.tangent_summary)
        summary.add_row("Tangent decision", result.tangent_decision_label or "pending explicit choice")
    summary.add_row("Last update age", result.last_update_age or "unknown")
    if result.resume_file:
        summary.add_row("Resume file", _format_display_path(result.resume_file))
    console.print(summary)

    status_note = _observe_execution_status_note(result)
    if status_note:
        console.print()
        console.print(status_note)

    if result.next_check_command:
        console.print()
        console.print("[bold]Check next[/]")
        console.print(f"- {result.next_check_command} — {result.next_check_reason}")

    if len(result.suggested_next_commands) > 1:
        console.print()
        console.print("[bold]Other read-only checks[/]")
        for suggestion in result.suggested_next_commands[1:]:
            console.print(f"- {suggestion.command} — {suggestion.reason}")

    if result.tangent_follow_up:
        console.print()
        console.print("[bold]Tangent follow-up[/]")
        for line in result.tangent_follow_up:
            console.print(f"- {line}")

    if not result.found:
        console.print()
        console.print("[dim]No live execution snapshot is currently recorded for this workspace.[/]")


observe_app = typer.Typer(help="Inspect local observability; event/export are the subcommands that write files")
app.add_typer(observe_app, name="observe")


@observe_app.command("execution")
def observe_execution() -> None:
    """Show the current local execution status without modifying project state."""
    result = _observe_execution_payload()
    if _raw:
        _output(result)
        return
    _render_observe_execution(result)


@observe_app.command("sessions")
def observe_sessions(
    status: str | None = typer.Option(None, "--status", help="Filter by session status"),
    command: str | None = typer.Option(None, "--command", help="Filter by command label"),
    last: int | None = typer.Option(None, "--last", help="Show most recent N sessions"),
) -> None:
    """List recorded local observability sessions without modifying project state."""
    _output(_filter_observability_sessions(_get_cwd(), status=status, command=command, last=last))


@observe_app.command("event")
def observe_event(
    category: str = typer.Argument(..., help="Event category"),
    name: str = typer.Argument(..., help="Event name"),
    action: str = typer.Option("log", "--action", help="Event action"),
    status: str = typer.Option("ok", "--status", help="Event status"),
    command: str | None = typer.Option(None, "--command", help="Associated command label"),
    phase: str | None = typer.Option(None, "--phase", help="Associated phase"),
    plan: str | None = typer.Option(None, "--plan", help="Associated plan"),
    session: str | None = typer.Option(None, "--session", help="Explicit session id"),
    data: str | None = typer.Option(None, "--data", help="JSON event payload"),
) -> None:
    """Record one local observability event (writes session logs)."""
    parsed_data = None
    if data:
        try:
            raw_data = json.loads(data)
        except json.JSONDecodeError:
            parsed_data = {"raw": data}
        else:
            parsed_data = raw_data if isinstance(raw_data, dict) else {"value": raw_data}
    _output(
        _emit_observability_event(
            _get_cwd(),
            category=category,
            name=name,
            action=action,
            status=status,
            command=command,
            phase=phase,
            plan=plan,
            session_id=session,
            data=parsed_data,
            end_session=action in {"finish", "error", "stop"},
        )
    )


@observe_app.command("show")
def observe_show(
    session: str | None = typer.Option(None, "--session", help="Filter by session id"),
    category: str | None = typer.Option(None, "--category", help="Filter by event category"),
    name: str | None = typer.Option(None, "--name", help="Filter by event name"),
    action: str | None = typer.Option(None, "--action", help="Filter by event action"),
    status: str | None = typer.Option(None, "--status", help="Filter by event status"),
    command: str | None = typer.Option(None, "--command", help="Filter by command label"),
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase"),
    plan: str | None = typer.Option(None, "--plan", help="Filter by plan"),
    last: int | None = typer.Option(None, "--last", help="Show last N matching events"),
) -> None:
    """Inspect local observability events with optional filters without modifying project state."""
    _output(
        _filter_observability_events(
            _get_cwd(),
            session=session,
            category=category,
            name=name,
            action=action,
            status=status,
            command=command,
            phase=phase,
            plan=plan,
            last=last,
        )
    )


@observe_app.command("export")
def observe_export(
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="Directory to write exported files"),
    session: str | None = typer.Option(None, "--session", help="Export only this session"),
    category: str | None = typer.Option(None, "--category", help="Filter events by category"),
    command: str | None = typer.Option(None, "--command", help="Filter by command label"),
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase"),
    last: int | None = typer.Option(None, "--last", help="Export only the last N sessions"),
    format: str = typer.Option("jsonl", "--format", "-f", help="Output format: jsonl, json, or markdown"),
    no_traces: bool = typer.Option(False, "--no-traces", help="Exclude execution traces from export"),
) -> None:
    """Export session logs and traces to files (writes export files)."""
    from gpd.core.observability import export_logs

    resolved_output_dir = str(_resolve_cli_target_dir(output_dir)) if output_dir is not None else None
    result = export_logs(
        _get_cwd(),
        output_dir=resolved_output_dir,
        session=session,
        category=category,
        command=command,
        phase=phase,
        last=last,
        include_traces=not no_traces,
        format=format,
    )
    if not result.exported:
        raise GPDError(result.reason or "Export failed")
    _output(result)


# ═══════════════════════════════════════════════════════════════════════════
# cost — Machine-local usage and cost summaries
# ═══════════════════════════════════════════════════════════════════════════


def _format_cost_tokens(value: int) -> str:
    return f"{value:,}"


def _format_cost_money(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"${value:,.4f}"


def _format_profile_tier_mix(value: object) -> str:
    if not isinstance(value, dict):
        return "unknown"
    parts: list[str] = []
    for tier in ("tier-1", "tier-2", "tier-3"):
        count = value.get(tier)
        if isinstance(count, int) and count > 0:
            parts.append(f"{tier}={count}")
    return ", ".join(parts) if parts else "unknown"


def _profile_tier_mix_interpretation() -> str:
    return "Advisory only; counts profile-to-tier assignments, not measured runtime model usage or spend."


def _format_guardrail_state(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    return value.replace("_", " ")


def _format_runtime_capability_value(summary: object, *keys: str) -> str:
    capabilities = getattr(summary, "active_runtime_capabilities", {}) or {}
    if not isinstance(capabilities, dict):
        return "unknown"
    for key in keys:
        value = capabilities.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _cost_summary_project_root(summary: object) -> str | None:
    project_rollup = getattr(summary, "project", None)
    project_root = getattr(project_rollup, "project_root", None)
    if isinstance(project_root, str) and project_root.strip():
        return project_root.strip()
    return None


def _cost_next_action(advisory: dict[str, object]) -> str | None:
    state = str(advisory.get("state", "") or "").strip()
    if state in {"at_or_over_budget", "near_budget", "mixed"}:
        return cost_inspect_action()
    return None


def _cost_advisory(summary: object) -> dict[str, object] | None:
    from gpd.core.costs import resolve_cost_advisory

    structured_advisory = resolve_cost_advisory(summary)
    if structured_advisory is None:
        return None

    advisory = structured_advisory.model_dump(mode="json")
    if not isinstance(advisory, dict):
        return None
    next_action = _cost_next_action(advisory)
    if next_action is not None:
        advisory["next_action"] = next_action
    return advisory


def _cost_summary_payload(summary: object) -> dict[str, object]:
    if not hasattr(summary, "model_dump"):
        return {}
    payload = summary.model_dump(mode="json")
    if not isinstance(payload, dict):
        return {}
    project_root = _cost_summary_project_root(summary)
    if project_root is not None:
        payload["project_root"] = project_root
    advisory = _cost_advisory(summary)
    if advisory is not None:
        payload["advisory"] = advisory
    return payload


def _render_cost_rollup(
    label: str, rollup: object, *, project_root: str | None = None, session_id: str | None = None
) -> None:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style=f"bold {_INSTALL_ACCENT_COLOR}")
    summary.add_column()
    if project_root:
        summary.add_row("Project", _format_display_path(project_root))
    if session_id:
        summary.add_row("Session", session_id)
    summary.add_row("Usage status", str(getattr(rollup, "usage_status", "unavailable")))
    summary.add_row("Cost status", str(getattr(rollup, "cost_status", "unavailable")))
    summary.add_row("Interpretation", str(getattr(rollup, "interpretation", "unknown")))
    summary.add_row("Records", str(int(getattr(rollup, "record_count", 0) or 0)))
    summary.add_row("Input tokens", _format_cost_tokens(int(getattr(rollup, "input_tokens", 0) or 0)))
    summary.add_row("Output tokens", _format_cost_tokens(int(getattr(rollup, "output_tokens", 0) or 0)))
    summary.add_row("Total tokens", _format_cost_tokens(int(getattr(rollup, "total_tokens", 0) or 0)))
    summary.add_row("Cached input tokens", _format_cost_tokens(int(getattr(rollup, "cached_input_tokens", 0) or 0)))
    summary.add_row(
        "Cache write tokens",
        _format_cost_tokens(int(getattr(rollup, "cache_write_input_tokens", 0) or 0)),
    )
    summary.add_row("USD cost", _format_cost_money(getattr(rollup, "cost_usd", None)))
    summary.add_row("Last recorded", str(getattr(rollup, "last_recorded_at", None) or "—"))
    runtimes = ", ".join(getattr(rollup, "runtimes", []) or []) or "—"
    models = ", ".join(getattr(rollup, "models", []) or []) or "—"
    summary.add_row("Runtimes", runtimes)
    summary.add_row("Models", models)
    console.print(f"[bold]{label}[/]")
    console.print(summary)


def _render_budget_guardrails(summary: object) -> None:
    thresholds = list(getattr(summary, "budget_thresholds", []) or [])
    console.print("[bold]Budget guardrails[/]")
    if not thresholds:
        console.print("[dim]No optional USD budget guardrails are configured for this workspace.[/]")
        console.print()
        return

    table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    table.add_column("Scope")
    table.add_column("Budget")
    table.add_column("Spent")
    table.add_column("Remaining")
    table.add_column("Used")
    table.add_column("Comparison")
    table.add_column("Exact")
    table.add_column("State")
    for threshold in thresholds:
        percent_used = getattr(threshold, "percent_used", None)
        table.add_row(
            str(getattr(threshold, "scope", "unknown")),
            _format_cost_money(getattr(threshold, "budget_usd", None)),
            _format_cost_money(getattr(threshold, "spent_usd", None)),
            _format_cost_money(getattr(threshold, "remaining_usd", None)),
            "—" if percent_used is None else f"{percent_used:.2f}%",
            str(getattr(threshold, "cost_status", "unavailable")),
            "yes" if bool(getattr(threshold, "comparison_exact", False)) else "no",
            _format_guardrail_state(getattr(threshold, "state", "unavailable")),
        )
    console.print(table)
    console.print(
        "[dim]Optional USD guardrails compare recorded machine-local USD against configured project/session budgets. "
        "They stay advisory only, may be partial or estimated when telemetry is missing, and never stop work automatically.[/]"
    )
    for threshold in thresholds:
        message = getattr(threshold, "message", None)
        if isinstance(message, str) and message.strip():
            console.print(f"[dim]- {message.strip()}[/]")
    console.print()


def _render_cost_summary(summary: object, *, last_sessions: int) -> None:
    console.print("[bold]Cost Summary[/]")
    console.print(
        "[dim]Read-only machine-local usage/cost summary. GPD reports measured telemetry when available and clearly labels estimates or unavailable values.[/]"
    )
    console.print()

    project_rollup = getattr(summary, "project", None)
    if int(getattr(project_rollup, "record_count", 0) or 0) == 0:
        console.print(
            "[dim]No measured usage telemetry is recorded for this workspace yet. "
            "GPD records usage only when the runtime emits token or cost payloads.[/]"
        )
        console.print()

    model_table = Table.grid(padding=(0, 2))
    model_table.add_column(style=f"bold {_INSTALL_ACCENT_COLOR}")
    model_table.add_column()
    model_table.add_row("Project", _format_display_path(str(_cost_summary_project_root(summary) or _get_cwd())))
    model_table.add_row("Active runtime", str(getattr(summary, "active_runtime", None) or "unknown"))
    telemetry_completeness = _format_runtime_capability_value(summary, "telemetry_completeness")
    telemetry_source = _format_runtime_capability_value(summary, "telemetry_source")
    if telemetry_completeness == "none":
        telemetry_label = "none"
    elif telemetry_source not in {"unknown", "none"}:
        telemetry_label = f"{telemetry_completeness} via {telemetry_source}"
    else:
        telemetry_label = telemetry_completeness
    model_table.add_row("Telemetry support", telemetry_label)
    model_table.add_row("Model profile", str(getattr(summary, "model_profile", None) or "unknown"))
    model_table.add_row("Runtime model selection", str(getattr(summary, "runtime_model_selection", None) or "unknown"))
    profile_tier_mix = _format_profile_tier_mix(getattr(summary, "profile_tier_mix", None))
    model_table.add_row("Profile tier mix", profile_tier_mix)
    model_table.add_row("Current session", str(getattr(summary, "current_session_id", None) or "none"))
    pricing_snapshot_configured = bool(getattr(summary, "pricing_snapshot_configured", False))
    snapshot_state = "configured" if pricing_snapshot_configured else "not configured"
    snapshot_source = getattr(summary, "pricing_snapshot_source", None)
    snapshot_as_of = getattr(summary, "pricing_snapshot_as_of", None)
    if snapshot_source or snapshot_as_of:
        extra = ", ".join(part for part in (snapshot_source, snapshot_as_of) if part)
        snapshot_state = f"{snapshot_state} ({extra})"
    model_table.add_row("Pricing snapshot", snapshot_state)
    console.print("[bold]Current posture[/]")
    console.print(model_table)
    if profile_tier_mix != "unknown":
        console.print(f"[dim]{_profile_tier_mix_interpretation()}[/]")
    console.print()

    _render_budget_guardrails(summary)

    advisory = _cost_advisory(summary)
    if advisory is not None and advisory.get("scope") is None:
        console.print("[bold]Advisory[/]")
        console.print(f"[dim]{advisory['message']}[/]")
        next_action = advisory.get("next_action")
        if isinstance(next_action, str) and next_action.strip():
            console.print(f"[dim]- {next_action.strip()}[/]")
        console.print()

    project_rollup = summary.project
    _render_cost_rollup("Current project", project_rollup, project_root=project_rollup.project_root)
    console.print()

    current_session = getattr(summary, "current_session", None)
    if current_session is not None:
        _render_cost_rollup(
            "Current session",
            current_session,
            project_root=getattr(current_session, "project_root", None),
            session_id=getattr(current_session, "session_id", None),
        )
        console.print()

    recent_sessions = list(getattr(summary, "recent_sessions", []) or [])
    if recent_sessions:
        console.print(f"[bold]Recent sessions[/] [dim](last {last_sessions})[/]")
        table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
        table.add_column("Session")
        table.add_column("Project")
        table.add_column("Usage")
        table.add_column("Cost")
        table.add_column("Interpretation")
        table.add_column("Total Tokens")
        table.add_column("USD")
        table.add_column("Last Recorded")
        for row in recent_sessions:
            table.add_row(
                str(getattr(row, "session_id", "")),
                _format_display_path(str(getattr(row, "project_root", "") or ""))
                if getattr(row, "project_root", None)
                else "—",
                str(getattr(row, "usage_status", "unavailable")),
                str(getattr(row, "cost_status", "unavailable")),
                str(getattr(row, "interpretation", "unknown")),
                _format_cost_tokens(int(getattr(row, "total_tokens", 0) or 0)),
                _format_cost_money(getattr(row, "cost_usd", None)),
                str(getattr(row, "last_recorded_at", None) or "—"),
            )
        console.print(table)
        console.print()

    guidance = list(getattr(summary, "guidance", []) or [])
    if guidance:
        console.print("[bold]Guidance[/]")
        for item in guidance:
            console.print(f"- {item}")


@app.command("cost")
def cost(
    last_sessions: int = typer.Option(5, "--last-sessions", help="Show the most recent N recorded usage sessions"),
) -> None:
    """Show machine-local usage and cost summaries for the current project and recent sessions."""
    from gpd.core.costs import build_cost_summary

    summary = build_cost_summary(_get_cwd(), last_sessions=last_sessions)
    if _raw:
        payload = _cost_summary_payload(summary)
        payload["profile_tier_mix_interpretation"] = _profile_tier_mix_interpretation()
        _output(payload)
        return
    _render_cost_summary(summary, last_sessions=max(last_sessions, 0))


# ═══════════════════════════════════════════════════════════════════════════
# stage — Read-only staged workflow metadata
# ═══════════════════════════════════════════════════════════════════════════

stage_app = typer.Typer(help="Read-only staged workflow metadata")
app.add_typer(stage_app, name="stage")


@stage_app.command("field-access")
def stage_field_access(
    workflow_id: str = typer.Argument(..., help="Workflow id, for example plan-phase"),
    stage: str = typer.Option(..., "--stage", help="Stage id from the workflow stage manifest"),
    style: str = typer.Option(
        "instruction",
        "--style",
        help="Output style: instruction, json, or shell",
    ),
    alias: list[str] | None = typer.Option(
        None,
        "--alias",
        help="Alias binding to expose, as ALIAS=field or field. Repeatable.",
    ),
    payload_var: str = typer.Option(
        "INIT",
        "--payload-var",
        help="Shell payload variable name used only with --style shell",
    ),
) -> None:
    """Expose manifest-selected staged-init field access metadata."""
    from gpd.core.staged_field_access import build_staged_field_access

    try:
        access = build_staged_field_access(
            workflow_id,
            stage_id=stage,
            style=style,
            alias_specs=alias,
            payload_variable=payload_var,
        )
    except ValueError as exc:
        _error(str(exc))
    _output(access.to_payload())


# ═══════════════════════════════════════════════════════════════════════════
# command — Read-only command-context metadata
# ═══════════════════════════════════════════════════════════════════════════

command_app = typer.Typer(help="Read-only command-context metadata")
app.add_typer(command_app, name="command")


@command_app.command("field-access")
def command_field_access(
    command_name: str = typer.Argument(..., help="Command registry key or gpd:name"),
    style: str = typer.Option(
        "instruction",
        "--style",
        help="Output style: instruction or json",
    ),
) -> None:
    """Expose selected command-context field access metadata."""
    from gpd.core.command_field_access import build_command_field_access

    try:
        access = build_command_field_access(command_name, style=style)
    except ValueError as exc:
        _error(str(exc))
    _output(access.to_payload())


# ═══════════════════════════════════════════════════════════════════════════
# init — Workflow context assembly
# ═══════════════════════════════════════════════════════════════════════════

init_app = typer.Typer(help="Assemble context for AI agent workflows")
app.add_typer(init_app, name="init")

_INIT_EXECUTE_PHASE_INCLUDES = frozenset({"config", "roadmap", "state"})
_INIT_PLAN_PHASE_INCLUDES = frozenset(
    {"context", "requirements", "research", "roadmap", "state", "validation", "verification"}
)
_INIT_PHASE_OP_INCLUDES = frozenset({"config", "roadmap", "state"})
_INIT_PROGRESS_INCLUDES = frozenset({"config", "project", "protocols", "references", "roadmap", "state"})


def _parse_init_include_option(
    include: str | None,
    *,
    command_name: str,
    allowed: frozenset[str],
) -> set[str]:
    """Normalize comma-separated init includes and reject unknown tokens."""
    if include is None:
        return set()

    includes = {token.strip() for token in include.split(",") if token.strip()}
    unknown = sorted(includes - allowed)
    if unknown:
        _error(
            f"Unknown --include value(s) for {command_name}: {', '.join(unknown)}. "
            f"Allowed values: {', '.join(sorted(allowed))}."
        )
    return includes


@init_app.command("autonomous")
def init_autonomous(
    argument: list[str] = typer.Argument(
        None,
        help="Optional autonomous launch arguments.",
    ),
    from_phase: str | None = typer.Option(
        None,
        "--from",
        help="Start from this roadmap phase instead of the first incomplete phase.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged autonomous context for a specific stage id.",
    ),
) -> None:
    """Assemble context for autonomous milestone execution."""
    from gpd.core.context import init_autonomous

    argument_text = " ".join(argument) if argument else None
    try:
        payload = init_autonomous(_get_cwd(), argument_input=argument_text, stage=stage, from_phase=from_phase)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("execute-phase")
def init_execute_phase(
    phase: str | None = typer.Argument(None, help="Phase number"),
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged execute-phase context for a specific stage id.",
    ),
) -> None:
    """Assemble context for executing a phase."""
    from gpd.core.context import init_execute_phase

    includes = _parse_init_include_option(
        include,
        command_name="gpd init execute-phase",
        allowed=_INIT_EXECUTE_PHASE_INCLUDES,
    )
    try:
        _output(init_execute_phase(_get_cwd(), phase, includes=includes, stage=stage))
    except ValueError as exc:
        _error(str(exc))


@init_app.command("plan-phase")
def init_plan_phase(
    phase: str | None = typer.Argument(None, help="Phase number"),
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged plan-phase context for a specific stage id.",
    ),
) -> None:
    """Assemble context for planning a phase."""
    from gpd.core.context import init_plan_phase

    includes = _parse_init_include_option(
        include,
        command_name="gpd init plan-phase",
        allowed=_INIT_PLAN_PHASE_INCLUDES,
    )
    try:
        _output(init_plan_phase(_get_cwd(), phase, includes=includes, stage=stage))
    except ValueError as exc:
        _error(str(exc))


@init_app.command("new-project")
def init_new_project(
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged new-project context for a specific stage id.",
    ),
) -> None:
    """Assemble context for starting a new project."""
    from gpd.core.context import init_new_project as _init_new_project

    try:
        if stage is None:
            payload = _init_new_project(_get_cwd())
        else:
            payload = _init_new_project(_get_cwd(), stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("start-context")
def init_start_context() -> None:
    """Assemble thin context for the start chooser."""
    from gpd.core.context import init_start_context as _init_start_context

    try:
        payload = _init_start_context(_get_cwd())
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("new-milestone")
def init_new_milestone(
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged new-milestone context for a specific stage id.",
    ),
) -> None:
    """Assemble context for starting a new milestone."""
    from gpd.core.context import init_new_milestone

    try:
        payload = init_new_milestone(_get_cwd(), stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("write-paper")
def init_write_paper(
    subject: list[str] = typer.Argument(
        None,
        help="Optional normalized write-paper launch payload.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged write-paper context for a specific stage id.",
    ),
) -> None:
    """Assemble context for manuscript authoring."""
    from gpd.core.context import init_write_paper

    subject_text = " ".join(subject) if subject else None
    try:
        payload = init_write_paper(_get_cwd(), subject=subject_text, stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("peer-review")
def init_peer_review(
    subject: str | None = typer.Argument(
        None,
        help="Optional explicit review target path for peer-review context resolution.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged peer-review context for a specific stage id.",
    ),
) -> None:
    """Assemble context for manuscript peer review."""
    from gpd.core.context import init_peer_review

    try:
        payload = init_peer_review(_get_cwd(), subject=subject, stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("respond-to-referees")
def init_respond_to_referees(
    subject: list[str] = typer.Argument(
        None,
        help="Optional normalized manuscript/report intake string for response-round context resolution.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged respond-to-referees context for a specific stage id.",
    ),
) -> None:
    """Assemble context for responding to referee reports."""
    from gpd.core.context import init_respond_to_referees

    subject_text = " ".join(subject) if subject else None
    try:
        payload = init_respond_to_referees(_get_cwd(), subject=subject_text, stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("arxiv-submission")
def init_arxiv_submission(
    subject: list[str] = typer.Argument(
        None,
        help="Optional explicit manuscript root or .tex entrypoint for staged submission context.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged arxiv-submission context for a specific stage id.",
    ),
) -> None:
    """Assemble context for arXiv submission packaging."""
    from gpd.core.context import init_arxiv_submission

    subject_text = " ".join(subject) if subject else None
    try:
        kwargs: dict[str, object] = {"stage": stage}
        if subject_text is not None:
            kwargs["subject"] = subject_text
        payload = init_arxiv_submission(_get_cwd(), **kwargs)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("quick")
def init_quick(
    description: list[str] = typer.Argument(None, help="Task description"),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged quick context for a specific stage id.",
    ),
) -> None:
    """Assemble context for a quick task."""
    from gpd.core.context import init_quick

    text = " ".join(description) if description else None
    try:
        payload = init_quick(_get_cwd(), description=text, stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("literature-review")
def init_literature_review(
    topic: list[str] = typer.Argument(None, help="Topic or research question"),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged literature-review context for a specific stage id.",
    ),
) -> None:
    """Assemble context for literature review orchestration."""
    from gpd.core.context import init_literature_review

    text = " ".join(topic) if topic else None
    try:
        payload = init_literature_review(_get_cwd(), topic=text, stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


def _emit_init_resume(stage: str | None) -> None:
    from gpd.core.context import init_resume

    try:
        payload = init_resume(_get_cwd(), stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("resume")
def init_resume(
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged resume-work context for a specific stage id.",
    ),
) -> None:
    """Assemble context for resuming previous work."""
    _emit_init_resume(stage)


@init_app.command("resume-work")
def init_resume_work(
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged resume-work context for a specific stage id.",
    ),
) -> None:
    """Alias for gpd init resume."""
    _emit_init_resume(stage)


@init_app.command("sync-state")
def init_sync_state(
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged sync-state context for a specific stage id.",
    ),
) -> None:
    """Assemble context for state reconciliation."""
    from gpd.core.context import init_sync_state

    try:
        payload = init_sync_state(_get_cwd(), stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("verify-work")
def init_verify_work(
    phase: str | None = typer.Argument(None, help="Phase to verify"),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged verify-work context for a specific stage id.",
    ),
) -> None:
    """Assemble context for verifying completed work."""
    from gpd.core.context import init_verify_work

    try:
        if stage is None:
            payload = init_verify_work(_get_cwd(), phase)
        else:
            payload = init_verify_work(_get_cwd(), phase, stage=stage)
    except (GPDError, ValueError) as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("progress")
def init_progress(
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
    project_reentry: bool = typer.Option(
        True,
        "--project-reentry/--no-project-reentry",
        help="Resolve project recovery context before assembling progress",
    ),
) -> None:
    """Assemble context for progress review."""
    from gpd.core.context import init_progress

    includes = _parse_init_include_option(
        include,
        command_name="gpd init progress",
        allowed=_INIT_PROGRESS_INCLUDES,
    )
    _output(init_progress(_get_cwd(), includes=includes, include_project_reentry=project_reentry))


@init_app.command("map-research")
def init_map_research(
    focus: str | None = typer.Argument(
        None,
        help="Optional specific area to emphasize in the research map.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged map-research context for a specific stage id.",
    ),
) -> None:
    """Assemble context for research mapping."""
    from gpd.core.context import init_map_research

    try:
        payload = init_map_research(_get_cwd(), focus=focus, stage=stage)
    except ValueError as exc:
        _error(str(exc))
    _output(payload)


@init_app.command("todos")
def init_todos(
    area: str | None = typer.Argument(None, help="Area to filter todos"),
) -> None:
    """Assemble context for todo review."""
    from gpd.core.context import init_todos

    _output(init_todos(_get_cwd(), area))


@init_app.command("phase-op")
def init_phase_op(
    phase: str | None = typer.Argument(None, help="Phase number"),
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged research-phase context for a specific stage id.",
    ),
) -> None:
    """Assemble context for generic phase operations."""
    from gpd.core.context import init_phase_op

    includes = _parse_init_include_option(
        include,
        command_name="gpd init phase-op",
        allowed=_INIT_PHASE_OP_INCLUDES,
    )
    try:
        _output(init_phase_op(_get_cwd(), phase, includes, stage=stage))
    except ValueError as exc:
        _error(str(exc))


@init_app.command("research-phase")
def init_research_phase(
    phase: str | None = typer.Argument(None, help="Phase number"),
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged research-phase context for a specific stage id.",
    ),
) -> None:
    """Assemble context for phase research."""
    from gpd.core.context import init_research_phase

    includes = _parse_init_include_option(
        include,
        command_name="gpd init research-phase",
        allowed=_INIT_PHASE_OP_INCLUDES,
    )
    try:
        _output(init_research_phase(_get_cwd(), phase, includes, stage=stage))
    except ValueError as exc:
        _error(str(exc))


@init_app.command("milestone-op")
def init_milestone_op() -> None:
    """Assemble context for milestone operations."""
    from gpd.core.context import init_milestone_op

    _output(init_milestone_op(_get_cwd()))


# ═══════════════════════════════════════════════════════════════════════════
# presets — Workflow preset surface
# ═══════════════════════════════════════════════════════════════════════════

presets_app = typer.Typer(help="Workflow presets for local CLI preview and application")
app.add_typer(presets_app, name="presets")


@presets_app.command("list")
def presets_list() -> None:
    """List the central workflow preset registry."""
    if _raw:
        _json_cli_output([dataclasses.asdict(preset) for preset in list_workflow_presets()])
        return
    _print_workflow_preset_list()


@presets_app.command("show")
def presets_show(
    preset_name: str = typer.Argument(..., help="Workflow preset name"),
) -> None:
    """Show one preset from the central workflow preset registry."""
    if _raw:
        preset = get_workflow_preset(preset_name)
        if preset is None:
            supported = ", ".join(preset.id for preset in list_workflow_presets())
            _error(f"Unknown workflow preset {preset_name!r}. Supported: {supported}")
        _json_cli_output(dataclasses.asdict(preset))
        return
    _print_workflow_preset_details(preset_name)


@presets_app.command("apply")
def presets_apply(
    preset_name: str = typer.Argument(..., help="Workflow preset name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show a diff-oriented preview without writing it"),
) -> None:
    """Apply a workflow preset to GPD/config.json."""
    from contextlib import nullcontext

    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write, file_lock

    preset = get_workflow_preset(preset_name)
    if preset is None:
        supported = ", ".join(preset.id for preset in list_workflow_presets())
        _error(f"Unknown workflow preset {preset_name!r}. Supported: {supported}")

    project_cwd = _config_project_scoped_cwd()
    config_path = ProjectLayout(project_cwd).config_json
    with nullcontext() if dry_run else file_lock(config_path):
        try:
            raw_text = config_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raw: dict[str, object] = {}
        except OSError as exc:
            _error(f"Cannot read config.json: {exc}")
        else:
            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                _error(f"Malformed config.json: {exc}")

        if not isinstance(raw, dict):
            _error("config.json must be a JSON object")

        try:
            preview = preview_workflow_preset_application(raw, preset_name)
        except (ConfigError, ValueError) as exc:
            _error(str(exc))

        if not dry_run:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(config_path, json.dumps(preview.updated_config, indent=2) + "\n")

    result: dict[str, object] = {
        "preset": preview.preset_id,
        "label": preview.label,
        "dry_run": dry_run,
        "config_path": str(config_path),
        "applied_keys": list(preview.applied_keys),
        "changed_keys": list(preview.changed_keys),
        "unchanged_keys": list(preview.unchanged_keys),
        "ignored_keys": list(preview.ignored_guidance_only_keys),
    }
    if dry_run:
        result["changes"] = [dataclasses.asdict(change) for change in preview.changes]
        result["resulting_config"] = preview.updated_config
    else:
        result["updated"] = True
    _output(result)


# ═══════════════════════════════════════════════════════════════════════════
# extras — Approximations, uncertainties, questions, calculations
# ═══════════════════════════════════════════════════════════════════════════

approx_app = typer.Typer(help="Approximation tracking and validity checks")
app.add_typer(approx_app, name="approximation")


@approx_app.command("add")
def approximation_add(
    name: str | None = typer.Argument(None, help="Approximation name"),
    validity_range: str | None = typer.Option(None, "--validity-range", help="Validity range"),
    controlling_param: str | None = typer.Option(None, "--controlling-param", help="Controlling parameter"),
    current_value: str | None = typer.Option(None, "--current-value", help="Current value"),
    status: str | None = typer.Option(None, "--status", help="Status"),
) -> None:
    """Add an approximation to track."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import approximation_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    # Filter None values so core function defaults ("", "valid") take effect
    kwargs: dict[str, str] = {}
    if validity_range is not None:
        kwargs["validity_range"] = validity_range
    if controlling_param is not None:
        kwargs["controlling_param"] = controlling_param
    if current_value is not None:
        kwargs["current_value"] = current_value
    if status is not None:
        kwargs["status"] = status

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        res = approximation_add(state, name=name or "", **kwargs)
        save_state_json_locked(cwd, state)
    _output(res)


@approx_app.command("list")
def approximation_list() -> None:
    """List all tracked approximations."""
    from gpd.core.extras import approximation_list

    _output(approximation_list(_load_state_dict()))


@approx_app.command("check")
def approximation_check() -> None:
    """Check validity of all approximations."""
    from gpd.core.extras import approximation_check

    _output(approximation_check(_load_state_dict()))


uncertainty_app = typer.Typer(help="Uncertainty propagation tracking")
app.add_typer(uncertainty_app, name="uncertainty")


@uncertainty_app.command("add")
def uncertainty_add(
    quantity: str | None = typer.Argument(None, help="Physical quantity"),
    value: str | None = typer.Option(None, "--value", help="Value"),
    uncertainty: str | None = typer.Option(None, "--uncertainty", help="Uncertainty"),
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    method: str | None = typer.Option(None, "--method", help="Method used"),
) -> None:
    """Add an uncertainty measurement."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import uncertainty_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    # Filter None values so core function defaults ("") take effect
    kwargs: dict[str, str] = {}
    if value is not None:
        kwargs["value"] = value
    if uncertainty is not None:
        kwargs["uncertainty"] = uncertainty
    if phase is not None:
        kwargs["phase"] = phase
    if method is not None:
        kwargs["method"] = method

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        res = uncertainty_add(state, quantity=quantity or "", **kwargs)
        save_state_json_locked(cwd, state)
    _output(res)


@uncertainty_app.command("list")
def uncertainty_list() -> None:
    """List all tracked uncertainties."""
    from gpd.core.extras import uncertainty_list

    _output(uncertainty_list(_load_state_dict()))


question_app = typer.Typer(help="Open research questions")
app.add_typer(question_app, name="question")


@question_app.command("add")
def question_add(
    text: list[str] = typer.Argument(..., help="Question text"),
) -> None:
    """Add an open research question."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import question_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        res = question_add(state, " ".join(text))
        save_state_json_locked(cwd, state)
    _output(res)


@question_app.command("list")
def question_list() -> None:
    """List open research questions."""
    from gpd.core.extras import question_list

    _output(question_list(_load_state_dict()))


@question_app.command("resolve")
def question_resolve(
    text: list[str] = typer.Argument(..., help="Question text to resolve"),
    answer: str | None = typer.Option(None, "--answer", "-a", help="Answer text to record with the resolved question"),
) -> None:
    """Mark a question as resolved, optionally recording the answer."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import question_resolve
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        joined = " ".join(text)
        res = question_resolve(state, joined, answer=answer)
        if res == 0:
            _error(f'No open question matching "{joined}". Pass the question text (or a unique substring), not an ID.')
        save_state_json_locked(cwd, state)
    _output(res)


calculation_app = typer.Typer(help="Calculation tracking")
app.add_typer(calculation_app, name="calculation")


@calculation_app.command("add")
def calculation_add(
    text: list[str] = typer.Argument(..., help="Calculation description"),
) -> None:
    """Add a calculation to track."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import calculation_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        res = calculation_add(state, " ".join(text))
        save_state_json_locked(cwd, state)
    _output(res)


@calculation_app.command("list")
def calculation_list() -> None:
    """List tracked calculations."""
    from gpd.core.extras import calculation_list

    _output(calculation_list(_load_state_dict()))


@calculation_app.command("complete")
def calculation_complete(
    text: list[str] = typer.Argument(..., help="Calculation to mark complete"),
) -> None:
    """Mark a calculation as complete."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import calculation_complete
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        state = _load_mutation_state_snapshot(cwd)
        joined = " ".join(text)
        res = calculation_complete(state, joined)
        if res == 0:
            _error(
                f'No active calculation matching "{joined}". '
                "Pass the calculation text (or a unique substring), not an ID."
            )
        save_state_json_locked(cwd, state)
    _output(res)


# ═══════════════════════════════════════════════════════════════════════════
# config — Configuration management
# ═══════════════════════════════════════════════════════════════════════════

config_app = typer.Typer(help="GPD configuration")
app.add_typer(config_app, name="config")


_WOLFRAM_INTEGRATION_NAME = WOLFRAM_MANAGED_INTEGRATION.integration_id
_INSTALL_RESULT_ADAPTER_KEY = "__gpd_install_adapter_instance__"


def _integrations_config_path(cwd: Path) -> Path:
    """Return the per-project shared-integration config path."""
    project_root = _require_project_root(cwd, command_label="gpd integrations")
    return WOLFRAM_MANAGED_INTEGRATION.project_config_path(project_root)


def _update_wolfram_integration_state(cwd: Path, *, enabled: bool) -> dict[str, object]:
    """Persist the Wolfram integration override in the project-local config file."""
    from gpd.core.utils import atomic_write, file_lock

    project_root = _require_project_root(cwd, command_label="gpd integrations")
    config_path = _integrations_config_path(project_root)
    with file_lock(config_path):
        try:
            payload = WOLFRAM_MANAGED_INTEGRATION.project_payload(project_root)
            WOLFRAM_MANAGED_INTEGRATION.project_record(project_root)
        except RuntimeError as exc:
            _error(str(exc))
        updated: dict[str, object] = {"enabled": enabled}
        payload[_WOLFRAM_INTEGRATION_NAME] = updated
        config_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(config_path, json.dumps(payload, indent=2) + "\n")

    try:
        ready = WOLFRAM_MANAGED_INTEGRATION.is_configured(cwd=project_root)
        endpoint = WOLFRAM_MANAGED_INTEGRATION.resolved_endpoint(cwd=project_root)
    except RuntimeError as exc:
        _error(str(exc))

    return {
        "integration": _WOLFRAM_INTEGRATION_NAME,
        "config_path": str(config_path),
        "configured": True,
        "enabled": enabled,
        "ready": ready,
        "endpoint": endpoint,
        "api_key_env": WOLFRAM_MANAGED_INTEGRATION.api_key_env_var,
        "scope": "project-local",
        "plan_readiness_command": local_cli_plan_preflight_command(),
    }


def _wolfram_integration_status_payload(cwd: Path) -> dict[str, object]:
    """Return the effective project-local status payload for the Wolfram integration."""
    project_root = _require_project_root(cwd, command_label="gpd integrations")
    config_path = _integrations_config_path(project_root)
    try:
        record = WOLFRAM_MANAGED_INTEGRATION.project_record(project_root)
        enabled = WOLFRAM_MANAGED_INTEGRATION.project_enabled(project_root)
        ready = WOLFRAM_MANAGED_INTEGRATION.is_configured(cwd=project_root)
        endpoint = WOLFRAM_MANAGED_INTEGRATION.resolved_endpoint(cwd=project_root)
    except RuntimeError as exc:
        _error(str(exc))

    configured = record is not None
    api_key_present = WOLFRAM_MANAGED_INTEGRATION.api_key_present()
    missing_api_key_env_vars = list(WOLFRAM_MANAGED_INTEGRATION.missing_api_key_env_vars())
    api_key_recovery = WOLFRAM_MANAGED_INTEGRATION.api_key_recovery_message()
    state = "ready" if ready else "disabled" if not enabled else "missing-api-key"
    if not enabled:
        next_step = "Run `gpd integrations enable wolfram` to re-enable the shared Wolfram bridge for this project."
    elif ready:
        next_step = f"Use `{local_cli_plan_preflight_command()}` to verify whether a specific plan can run."
    elif api_key_recovery:
        next_step = (
            f"{api_key_recovery} This makes the shared Wolfram bridge available, "
            "or run `gpd integrations disable wolfram` to suppress it for this project."
        )
    else:
        next_step = (
            f"Set `{WOLFRAM_MANAGED_INTEGRATION.api_key_env_var}` to make the shared Wolfram bridge available, "
            "or run `gpd integrations disable wolfram` to suppress it for this project."
        )
    projected_server = WOLFRAM_MANAGED_INTEGRATION.projected_server_entry(cwd=project_root) if ready else None
    projection_status = "projected" if ready else "disabled" if not enabled else "blocked_missing_api_key"

    return {
        "integration": _WOLFRAM_INTEGRATION_NAME,
        "managed_server_key": WOLFRAM_MANAGED_INTEGRATION.managed_server_key,
        "bridge_command": WOLFRAM_MANAGED_INTEGRATION.bridge_command,
        "bridge_module": WOLFRAM_MANAGED_INTEGRATION.bridge_module,
        "configured": configured,
        "enabled": enabled,
        "ready": ready,
        "state": state,
        "projection_status": projection_status,
        "projected_server": projected_server,
        "config_path": str(config_path),
        "scope": "project-local",
        "endpoint": endpoint,
        "api_key_env": WOLFRAM_MANAGED_INTEGRATION.api_key_env_var,
        "api_key_env_vars": list(WOLFRAM_MANAGED_INTEGRATION.api_key_env_vars),
        "api_key_present": api_key_present,
        "missing_api_key_env_vars": missing_api_key_env_vars,
        "api_key_recovery": api_key_recovery,
        "plan_readiness_command": local_cli_plan_preflight_command(),
        "next_step": next_step,
        "local_mathematica_note": (
            "Local Mathematica / Wolfram Language installs are separate from this shared optional integration."
        ),
    }


integrations_app = typer.Typer(help="Optional shared capability integrations")
app.add_typer(integrations_app, name="integrations")


def _resolve_wolfram_integration_name(integration: str) -> str:
    """Resolve and validate the supported shared integration name."""
    normalized = integration.strip().lower()
    if normalized != _WOLFRAM_INTEGRATION_NAME:
        _error(f"Unknown integration {integration!r}. Supported: {_WOLFRAM_INTEGRATION_NAME}")
    return normalized


@integrations_app.command("status")
def integrations_status(
    integration: str = typer.Argument(..., help="Integration name (currently only wolfram)"),
) -> None:
    """Show the effective project-local status of a shared optional integration."""
    _resolve_wolfram_integration_name(integration)
    _output(_wolfram_integration_status_payload(_get_cwd()))


@integrations_app.command("enable")
def integrations_enable(
    integration: str = typer.Argument(..., help="Integration name (currently only wolfram)"),
) -> None:
    """Enable the shared optional integration for the current project."""
    _resolve_wolfram_integration_name(integration)
    _output(_update_wolfram_integration_state(_get_cwd(), enabled=True))


@integrations_app.command("disable")
def integrations_disable(
    integration: str = typer.Argument(..., help="Integration name (currently only wolfram)"),
) -> None:
    """Disable the shared optional integration for the current project."""
    _resolve_wolfram_integration_name(integration)
    _output(_update_wolfram_integration_state(_get_cwd(), enabled=False))


_PermissionsResolutionError = _permissions_cli_support.PermissionsResolutionError


def _raise_permissions_resolution_error(message: str, *, strict: bool) -> None:
    """Raise a permissions-resolution error, surfacing it only when requested."""
    if strict:
        _error(message)
    raise _PermissionsResolutionError(message)


def _resolve_permissions_runtime_name(
    runtime: str | None,
    *,
    strict: bool = True,
    prefer_installed_runtime: bool = False,
) -> str:
    """Resolve the runtime to use for permission status/sync commands."""
    return _permissions_cli_support.resolve_permissions_runtime_name(
        runtime,
        cwd=_get_cwd(),
        strict=strict,
        prefer_installed_runtime=prefer_installed_runtime,
        supported_runtime_names=_supported_runtime_names,
        normalize_runtime_name=normalize_runtime_name,
        error=_error,
    )


def _resolve_permissions_autonomy(autonomy: str | None, *, strict: bool = True) -> str:
    """Resolve the autonomy value used for runtime-permission sync."""
    return _permissions_cli_support.resolve_permissions_autonomy(
        autonomy,
        cwd=_get_cwd(),
        strict=strict,
        error=_error,
    )


def _permissions_install_target_assessment(runtime_name: str, target_dir: Path):
    """Return the shared install-state assessment for a permissions target."""
    return _permissions_cli_support.permissions_install_target_assessment(runtime_name, target_dir)


def _permissions_install_target_error_message(
    runtime_name: str,
    assessment,
    *,
    action: str,
) -> str:
    """Return a user-facing error message for a non-complete permissions target."""
    return _permissions_cli_support.permissions_install_target_error_message(
        runtime_name,
        assessment,
        action=action,
        cwd=_get_cwd(),
    )


def _resolve_permissions_target_dir(
    runtime_name: str,
    *,
    target_dir: str | None,
    strict: bool = True,
    action: str = "inspect runtime permissions on",
) -> Path:
    """Resolve the installed config directory targeted by a permissions command."""
    return _permissions_cli_support.resolve_permissions_target_dir(
        runtime_name,
        target_dir=target_dir,
        cwd=_get_cwd(),
        strict=strict,
        action=action,
        target_assessment_resolver=_permissions_install_target_assessment,
        error=_error,
    )


def _annotate_permissions_payload(payload: dict[str, object]) -> dict[str, object]:
    """Attach structured capability and evidence metadata to a permissions payload."""
    return _permissions_cli_support.annotate_permissions_payload(payload, requested_runtime=None)


def _runtime_permissions_payload(
    *,
    runtime: str | None,
    autonomy: str | None,
    target_dir: str | None,
    apply_sync: bool,
    strict: bool,
    prefer_installed_runtime: bool = False,
) -> dict[str, object]:
    """Return runtime-permissions status or sync payload for the selected runtime."""
    return _permissions_cli_support.runtime_permissions_payload(
        runtime=runtime,
        autonomy=autonomy,
        target_dir=target_dir,
        apply_sync=apply_sync,
        strict=strict,
        cwd=_get_cwd(),
        prefer_installed_runtime=prefer_installed_runtime,
        runtime_name_resolver=lambda value, **kwargs: _resolve_permissions_runtime_name(
            value,
            strict=bool(kwargs.get("strict", True)),
            prefer_installed_runtime=bool(kwargs.get("prefer_installed_runtime", False)),
        ),
        target_dir_resolver=lambda value, **kwargs: _resolve_permissions_target_dir(
            value,
            target_dir=kwargs.get("target_dir"),
            strict=bool(kwargs.get("strict", True)),
            action=str(kwargs.get("action") or "inspect runtime permissions on"),
        ),
        autonomy_resolver=lambda value, **kwargs: _resolve_permissions_autonomy(
            value,
            strict=bool(kwargs.get("strict", True)),
        ),
        payload_annotator=lambda payload, requested_runtime=None: _annotate_permissions_payload(payload),
    )


def _permissions_status_payload(
    *,
    runtime: str | None,
    autonomy: str | None,
    target_dir: str | None,
) -> dict[str, object]:
    """Return a status payload annotated for unattended-readiness checks."""
    return _permissions_cli_support.permissions_status_payload(
        runtime=runtime,
        autonomy=autonomy,
        target_dir=target_dir,
        cwd=_get_cwd(),
        runtime_permissions_payload_func=lambda **kwargs: _runtime_permissions_payload(
            runtime=kwargs.get("runtime"),
            autonomy=kwargs.get("autonomy"),
            target_dir=kwargs.get("target_dir"),
            apply_sync=bool(kwargs.get("apply_sync", False)),
            strict=bool(kwargs.get("strict", True)),
            prefer_installed_runtime=bool(kwargs.get("prefer_installed_runtime", False)),
        ),
    )


permissions_app = typer.Typer(
    help="Runtime permission readiness and sync. Use the active runtime's `settings` command for guided runtime changes."
)
app.add_typer(permissions_app, name="permissions")


@permissions_app.command("status")
def permissions_status(
    runtime: str | None = typer.Option(None, "--runtime", help="Runtime name to inspect"),
    autonomy: str | None = typer.Option(None, "--autonomy", help="Autonomy to compare against"),
    target_dir: str | None = typer.Option(None, "--target-dir", help="Explicit runtime config directory"),
) -> None:
    """Check whether a runtime install is ready for unattended use under the requested autonomy."""
    _output(_permissions_status_payload(runtime=runtime, autonomy=autonomy, target_dir=target_dir))


@permissions_app.command(
    "sync",
    help=(
        "Advanced: persist runtime-owned permission settings for the requested autonomy. "
        "Use the active runtime's `settings` command for guided runtime changes."
    ),
)
def permissions_sync(
    runtime: str | None = typer.Option(None, "--runtime", help="Runtime name to update"),
    autonomy: str | None = typer.Option(None, "--autonomy", help="Autonomy to apply"),
    target_dir: str | None = typer.Option(None, "--target-dir", help="Explicit runtime config directory"),
) -> None:
    """Advanced: persist runtime-owned permission settings for the requested autonomy."""
    _output(
        _runtime_permissions_payload(
            runtime=runtime,
            autonomy=autonomy,
            target_dir=target_dir,
            apply_sync=True,
            strict=True,
            prefer_installed_runtime=True,
        )
    )


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Config key path (dot-separated)"),
) -> None:
    """Get a configuration value."""
    try:
        from gpd.core.config import effective_config_value, load_config

        config = load_config(_config_project_scoped_cwd())
        found, value = effective_config_value(config, key)
    except ConfigError as exc:
        _error(str(exc))
    if not found:
        _output({"key": key, "found": False})
        return
    _output({"key": key, "value": value, "found": True})


_NULLABLE_CONFIG_VALUE_KEYS = frozenset({"project_usd_budget", "session_usd_budget"})
_MODEL_OVERRIDE_TIERS = ("tier-1", "tier-2", "tier-3")


def _parse_config_set_value(canonical_key: str | None, raw_value: str) -> object:
    """Parse a CLI config value, including prompt-friendly nullable clears."""
    if canonical_key in _NULLABLE_CONFIG_VALUE_KEYS and raw_value.strip().lower() in {"", "none"}:
        return None
    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, ValueError):
        return raw_value


def _normalize_tier_model_value(raw_value: str) -> str | None:
    """Return a model id, or None when the tier should use the runtime default."""
    stripped = raw_value.strip()
    normalized_clear_token = " ".join(stripped.casefold().replace("-", " ").replace("_", " ").split())
    if not stripped or normalized_clear_token in {"none", "runtime default"}:
        return None
    return stripped


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key path (dot-separated)"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value (advanced local override)."""
    from gpd.core.config import apply_config_update, canonical_config_key, effective_config_value, load_config
    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write, file_lock

    project_cwd = _config_project_scoped_cwd()
    config_path = ProjectLayout(project_cwd).config_json
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(config_path):
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raw = {}
        except json.JSONDecodeError as e:
            _error(f"Malformed config.json: {e}")
        except OSError as exc:
            _error(f"Cannot read config.json: {exc}")
        if not isinstance(raw, dict):
            _error("config.json must be a JSON object")
        parsed = _parse_config_set_value(canonical_config_key(key), value)
        try:
            updated_config, canonical_key = apply_config_update(raw, key, parsed)
        except ConfigError as exc:
            _error(str(exc))
        atomic_write(config_path, json.dumps(updated_config, indent=2) + "\n")

    config = load_config(project_cwd)
    _found, effective_value = effective_config_value(config, key)
    result: dict[str, object] = {"key": key, "canonical_key": canonical_key, "value": effective_value, "updated": True}
    if canonical_key == "autonomy":
        result["guided_path"] = (
            f"Use `{_active_runtime_settings_command(cwd=project_cwd)}` inside the runtime for guided autonomy changes."
        )
        result["runtime_permissions"] = None
    _output(result)


@config_app.command("set-tier-models")
def config_set_tier_models(
    runtime: str = typer.Option(..., "--runtime", help="Runtime whose tier model overrides should be updated"),
    tier_1: str | None = typer.Option(None, "--tier-1", help="Exact tier-1 model id; blank/none clears tier 1"),
    tier_2: str | None = typer.Option(None, "--tier-2", help="Exact tier-2 model id; blank/none clears tier 2"),
    tier_3: str | None = typer.Option(None, "--tier-3", help="Exact tier-3 model id; blank/none clears tier 3"),
    clear: bool = typer.Option(False, "--clear", help="Clear all tier model overrides for the selected runtime"),
) -> None:
    """Update model_overrides for one runtime without touching other runtime maps."""
    from gpd.core.config import apply_config_update, effective_config_value, effective_raw_config_value, load_config
    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write, file_lock

    runtime_name = normalize_runtime_name(runtime)
    if runtime_name is None:
        _error(f"Unknown runtime {runtime!r}. Supported runtimes: {', '.join(sorted(list_runtime_names()))}")

    requested_tiers = {"tier-1": tier_1, "tier-2": tier_2, "tier-3": tier_3}
    supplied_tiers = {tier: value for tier, value in requested_tiers.items() if value is not None}
    if clear and supplied_tiers:
        _error("Use either --clear or tier model options, not both.")
    if not clear and not supplied_tiers:
        _error("Provide at least one of --tier-1, --tier-2, --tier-3, or --clear.")

    project_cwd = _config_project_scoped_cwd()
    config_path = ProjectLayout(project_cwd).config_json
    config_path.parent.mkdir(parents=True, exist_ok=True)
    changed_tiers: list[str] = []
    cleared_tiers: list[str] = []
    with file_lock(config_path):
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raw = {}
        except json.JSONDecodeError as e:
            _error(f"Malformed config.json: {e}")
        except OSError as exc:
            _error(f"Cannot read config.json: {exc}")
        if not isinstance(raw, dict):
            _error("config.json must be a JSON object")

        try:
            _found, current_effective = effective_raw_config_value(raw, "model_overrides")
        except ConfigError as exc:
            _error(str(exc))
        current_overrides = current_effective if isinstance(current_effective, dict) else {}
        next_overrides: dict[str, dict[str, str]] = {
            str(existing_runtime): dict(tier_map)
            for existing_runtime, tier_map in current_overrides.items()
            if isinstance(tier_map, dict)
        }

        if clear:
            cleared_tiers = sorted(next_overrides.get(runtime_name, {}))
            next_overrides.pop(runtime_name, None)
        else:
            runtime_overrides = dict(next_overrides.get(runtime_name, {}))
            for tier in _MODEL_OVERRIDE_TIERS:
                raw_model = requested_tiers[tier]
                if raw_model is None:
                    continue
                model = _normalize_tier_model_value(raw_model)
                if model is None:
                    if tier in runtime_overrides:
                        cleared_tiers.append(tier)
                    runtime_overrides.pop(tier, None)
                    continue
                runtime_overrides[tier] = model
                changed_tiers.append(tier)

            if runtime_overrides:
                next_overrides[runtime_name] = runtime_overrides
            else:
                next_overrides.pop(runtime_name, None)

        try:
            updated_config, canonical_key = apply_config_update(
                raw,
                "model_overrides",
                next_overrides or None,
            )
        except ConfigError as exc:
            _error(str(exc))
        atomic_write(config_path, json.dumps(updated_config, indent=2) + "\n")

    config = load_config(project_cwd)
    _found, effective_value = effective_config_value(config, canonical_key)
    runtime_model_overrides = None
    if isinstance(effective_value, dict):
        runtime_model_overrides = effective_value.get(runtime_name)
    _output(
        {
            "runtime": runtime_name,
            "updated": True,
            "cleared": clear,
            "changed_tiers": changed_tiers,
            "cleared_tiers": cleared_tiers,
            "model_overrides": effective_value,
            "runtime_model_overrides": runtime_model_overrides,
        }
    )


@config_app.command("ensure-section")
def config_ensure_section() -> None:
    """Ensure config directory structure exists."""
    from gpd.core.config import GPDProjectConfig
    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write

    config_path = ProjectLayout(_config_project_scoped_cwd()).config_json
    if config_path.exists():
        _output({"created": False, "path": str(config_path)})
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    defaults = GPDProjectConfig()
    config_dict = {
        "autonomy": defaults.autonomy.value,
        "execution": {
            "review_cadence": defaults.review_cadence.value,
            "max_unattended_minutes_per_plan": defaults.max_unattended_minutes_per_plan,
            "max_unattended_minutes_per_wave": defaults.max_unattended_minutes_per_wave,
            "checkpoint_after_n_tasks": defaults.checkpoint_after_n_tasks,
            "checkpoint_after_first_load_bearing_result": defaults.checkpoint_after_first_load_bearing_result,
            "checkpoint_before_downstream_dependent_tasks": defaults.checkpoint_before_downstream_dependent_tasks,
        },
        "research_mode": defaults.research_mode.value,
        "commit_docs": defaults.commit_docs,
        "parallelization": defaults.parallelization,
        "model_profile": defaults.model_profile.value,
        "workflow": {
            "research": defaults.research,
            "plan_checker": defaults.plan_checker,
            "verifier": defaults.verifier,
        },
        "git": {
            "branching_strategy": defaults.branching_strategy.value,
            "phase_branch_template": defaults.phase_branch_template,
            "milestone_branch_template": defaults.milestone_branch_template,
        },
    }
    atomic_write(config_path, json.dumps(config_dict, indent=2) + "\n")
    _output({"created": True, "path": str(config_path)})


# ═══════════════════════════════════════════════════════════════════════════
# validate — Consistency validation
# ═══════════════════════════════════════════════════════════════════════════

validate_app = typer.Typer(help="Validation checks")
app.add_typer(validate_app, name="validate")

verification_report_app = typer.Typer(help="Verification report skeleton helpers")
app.add_typer(verification_report_app, name="verification-report")

proof_redteam_app = typer.Typer(help="Proof-redteam artifact helpers")
app.add_typer(proof_redteam_app, name="proof-redteam")

return_app = typer.Typer(help="gpd_return envelope helpers")
app.add_typer(return_app, name="return")


def _resolve_launch_or_project_relative_path(
    subject: str | None, *, launch_cwd: Path, project_cwd: Path
) -> Path | None:
    """Resolve a launch argument relative to launch cwd first, then project root."""
    launch_candidate = _resolve_subject_path(subject, base=launch_cwd)
    if launch_candidate is None or launch_candidate.exists() or Path(str(subject or "")).is_absolute():
        return launch_candidate
    project_candidate = _resolve_subject_path(subject, base=project_cwd)
    if project_candidate is not None and project_candidate.exists():
        return project_candidate
    return launch_candidate


def _resolve_review_preflight_publication_artifact(manuscript: Path, *filenames: str) -> Path | None:
    """Resolve review artifacts only from the active manuscript directory."""
    return locate_publication_artifact(manuscript, *filenames)


@dataclasses.dataclass(frozen=True)
class ManuscriptPublicationArtifacts:
    """Publication artifacts resolved beside the active manuscript."""

    artifact_manifest: Path | None = None
    bibliography_audit: Path | None = None
    reproducibility_manifest: Path | None = None


def _publication_lineage_search_roots(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Return candidate publication-root and review-root search paths for one manuscript subject."""

    return _core_publication_lineage_search_roots(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=True,
    )


def _publication_review_round_path_maps(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> tuple[dict[int, Path], dict[int, Path]]:
    """Return staged review-artifact maps rooted at the manuscript's publication lineage."""

    return _core_publication_review_round_path_maps(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=True,
    )


def _publication_response_round_path_maps(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> tuple[dict[int, Path], dict[int, Path]]:
    """Return paired response-artifact maps rooted at the manuscript's publication lineage."""

    return _core_publication_response_round_path_maps(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=True,
    )


def _publication_review_round_artifacts(
    round_number: int,
    *,
    review_ledger_by_round: dict[int, Path],
    referee_decision_by_round: dict[int, Path],
) -> PublicationReviewRoundArtifacts:
    """Return one staged review round bundle from precomputed round maps."""

    return _core_publication_review_round_artifacts(
        round_number=round_number,
        review_ledger_by_round=review_ledger_by_round,
        referee_decision_by_round=referee_decision_by_round,
    )


def _resolve_latest_publication_review_round_artifacts(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> PublicationReviewRoundArtifacts | None:
    """Return the newest staged review round without enforcing manuscript-path matching."""

    return _core_resolve_latest_publication_review_round_artifacts(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=True,
    )


def _resolve_latest_publication_response_round_artifacts(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> PublicationResponseRoundArtifacts | None:
    """Return the newest paired-response round without assuming fresh review clearance exists."""

    return _core_resolve_latest_publication_response_round_artifacts(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=True,
    )


def _resolve_review_preflight_publication_artifacts(manuscript: Path) -> ManuscriptPublicationArtifacts:
    """Resolve the standard manuscript-local publication artifacts."""
    return ManuscriptPublicationArtifacts(
        artifact_manifest=_resolve_review_preflight_publication_artifact(manuscript, "ARTIFACT-MANIFEST.json"),
        bibliography_audit=_resolve_review_preflight_publication_artifact(manuscript, "BIBLIOGRAPHY-AUDIT.json"),
        reproducibility_manifest=_resolve_review_preflight_publication_artifact(
            manuscript, "reproducibility-manifest.json"
        ),
    )


def _validate_artifact_manifest_semantics(
    artifact_manifest: Path,
    manuscript: Path,
    *,
    require_freshness: bool = True,
) -> tuple[bool, str]:
    """Validate artifact-manifest structure and manuscript freshness."""
    from gpd.mcp.paper.artifact_manifest import (
        validate_artifact_manifest_freshness,
        validate_artifact_manifest_integrity,
    )
    from gpd.mcp.paper.models import ArtifactManifest

    detail = f"{_format_display_path(artifact_manifest)} present"
    try:
        artifact_manifest_payload = json.loads(artifact_manifest.read_text(encoding="utf-8"))
        artifact_manifest_model = ArtifactManifest.model_validate(artifact_manifest_payload)
        failed_build_artifacts = [
            artifact
            for artifact in artifact_manifest_model.artifacts
            if isinstance(artifact.metadata, dict) and artifact.metadata.get("build_success") is False
        ]
        if failed_build_artifacts:
            failed_artifact = failed_build_artifacts[0]
            failure_stage = failed_artifact.metadata.get("failure_stage", "unknown")
            return False, f"artifact manifest records failed paper build at {failure_stage} stage"
        if require_freshness:
            artifact_manifest_freshness = validate_artifact_manifest_freshness(
                artifact_manifest_model,
                manuscript,
            )
            if not artifact_manifest_freshness.fresh:
                return False, "artifact manifest is stale: " + artifact_manifest_freshness.detail
        selected_manifest_manuscript = manuscript if manuscript.suffix.lower() in {".tex", ".md"} else None
        artifact_manifest_integrity = validate_artifact_manifest_integrity(
            artifact_manifest_model,
            artifact_manifest.parent,
            selected_manuscript_path=selected_manifest_manuscript,
        )
        if not artifact_manifest_integrity.passed:
            return False, "artifact manifest integrity failed: " + artifact_manifest_integrity.detail
    except OSError as exc:
        return False, f"could not read artifact manifest: {exc}"
    except UnicodeDecodeError as exc:
        return False, f"artifact manifest is not valid UTF-8: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"could not parse artifact manifest: {exc}"
    except PydanticValidationError as exc:
        return False, "artifact manifest is invalid: " + "; ".join(
            _format_pydantic_schema_error(error, root_label="artifact_manifest") for error in exc.errors()[:3]
        )
    return True, detail


def _validate_bibliography_audit_semantics(bibliography_audit: Path) -> tuple[bool, str]:
    """Validate bibliography-audit structure and publication semantics."""
    from gpd.mcp.paper.bibliography import BibliographyAudit

    try:
        audit_payload = json.loads(bibliography_audit.read_text(encoding="utf-8"))
    except OSError as exc:
        return False, f"could not read bibliography audit: {exc}"
    except UnicodeDecodeError as exc:
        return False, f"bibliography audit is not valid UTF-8: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"could not parse bibliography audit: {exc}"

    try:
        audit = BibliographyAudit.model_validate(audit_payload)
    except PydanticValidationError as exc:
        return (
            False,
            "bibliography audit is invalid: "
            + "; ".join(
                _format_pydantic_schema_error(error, root_label="bibliography_audit") for error in exc.errors()[:3]
            ),
        )

    clean = (
        audit.resolved_sources == audit.total_sources
        and audit.partial_sources == 0
        and audit.unverified_sources == 0
        and audit.failed_sources == 0
    )
    return (
        clean,
        (
            "all bibliography sources resolved and verified"
            if clean
            else "bibliography audit still has unresolved, partial, unverified, or failed sources"
        ),
    )


_PHASE_EXECUTED_STATUSES = {
    "phase complete — ready for verification",
    "verifying",
    "complete",
    "milestone complete",
}


def _requires_theorem_bearing_manuscript_review(
    project_cwd: Path,
    manuscript: Path | None,
) -> bool:
    """Return whether theorem-bearing proof review must be enforced."""

    return manuscript is not None and manuscript_requires_theorem_bearing_review(project_cwd, manuscript)


def _review_contract_declared_preflight_checks(contract: object) -> set[str]:
    """Return every preflight check declared directly or conditionally on one review contract."""

    declared_checks = set(getattr(contract, "preflight_checks", []) or [])
    for requirement in list(getattr(contract, "conditional_requirements", []) or []):
        declared_checks.update(list(getattr(requirement, "preflight_checks", []) or []))
        declared_checks.update(list(getattr(requirement, "blocking_preflight_checks", []) or []))
    return declared_checks


def _review_contract_requests_check(contract: object, check_name: str) -> bool:
    """Return whether the review contract explicitly asks the CLI to execute one check."""

    return check_name in _review_contract_declared_preflight_checks(contract)


def _review_contract_active_requested_preflight_checks(
    contract: object,
    active_conditional_requirements: list[ReviewContractConditionalRequirement] | None = None,
) -> set[str]:
    """Return the preflight checks active for the current resolved review context."""

    active_checks = set(getattr(contract, "preflight_checks", []) or [])
    for requirement in list(active_conditional_requirements or []):
        active_checks.update(list(getattr(requirement, "preflight_checks", []) or []))
        active_checks.update(list(getattr(requirement, "blocking_preflight_checks", []) or []))
    return active_checks


def _review_preflight_check_is_blocking(
    contract: object,
    check_name: str,
    *,
    conditional_blocking_preflight_checks: set[str] | None = None,
) -> bool:
    """Return True when the typed review contract marks a check as hard-blocking."""

    declared_preflight_checks = set(getattr(contract, "preflight_checks", []) or [])
    return check_name in declared_preflight_checks or check_name in (conditional_blocking_preflight_checks or set())


def _review_contract_active_conditional_requirements(
    contract: object,
    *,
    project_cwd: Path,
    manuscript: Path | None,
    resolved_mode: str = "",
) -> list[object]:
    """Return conditionals whose trigger is active for the current manuscript."""

    active_requirements: list[object] = []
    for requirement in list(getattr(contract, "conditional_requirements", []) or []):
        when = str(getattr(requirement, "when", "") or "").strip()
        if when == "project-backed manuscript review":
            if resolved_mode == "project-backed manuscript review":
                active_requirements.append(requirement)
            continue
        if when == "standalone explicit-artifact review":
            if resolved_mode == "standalone explicit-artifact review":
                active_requirements.append(requirement)
            continue
        if when in {
            "theorem-bearing claims are present",
            "theorem-bearing manuscripts are present",
        }:
            if _requires_theorem_bearing_manuscript_review(project_cwd, manuscript):
                active_requirements.append(requirement)
    return active_requirements


def _effective_review_contract_strings(
    base_values: Collection[str],
    active_requirements: Collection[object],
    attribute_name: str,
) -> list[str]:
    """Return a deduplicated list of active review-contract string requirements."""

    effective_values: list[str] = []
    seen: set[str] = set()
    for value in list(base_values):
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            effective_values.append(normalized)
    for requirement in active_requirements:
        for value in list(getattr(requirement, attribute_name, []) or []):
            normalized = str(value).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                effective_values.append(normalized)
    return effective_values


def _evaluate_review_required_state(
    contract: object,
    *,
    cwd: Path,
    subject: str | None,
    phase_info: object | None,
) -> tuple[bool, str] | None:
    """Evaluate review_contract.required_state in a way that matches phase-scoped workflows."""
    from gpd.core.phases import find_phase
    from gpd.core.state import load_state_json_readonly
    from gpd.core.utils import phase_normalize

    required_state = str(getattr(contract, "required_state", "") or "").strip()
    if not required_state:
        return None
    if required_state != "phase_executed":
        return False, f'unhandled required_state="{required_state}"'

    state_obj = load_state_json_readonly(cwd)
    if not isinstance(state_obj, dict):
        return False, "required_state=phase_executed could not load state.json"

    position = state_obj.get("position")
    if not isinstance(position, dict):
        return False, "required_state=phase_executed could not read position from state.json"

    current_phase = phase_normalize(str(position.get("current_phase") or "")).strip()
    current_status = str(position.get("status") or "").strip()
    current_status_normalized = current_status.lower()

    target_phase = ""
    if phase_info is not None:
        target_phase = str(getattr(phase_info, "phase_number", "") or "").strip()
    elif subject:
        target_phase = phase_normalize(subject).strip()
    elif current_phase:
        target_phase = current_phase

    if target_phase and current_phase and target_phase == current_phase:
        if current_status_normalized in _PHASE_EXECUTED_STATUSES:
            return True, (
                f'required_state=phase_executed satisfied for current phase {current_phase} (status "{current_status}")'
            )
        expected_statuses = "Phase complete — ready for verification, Verifying, Complete, or Milestone complete"
        return False, (
            f"required_state=phase_executed expects current phase {current_phase} to be in one of: "
            f'{expected_statuses}; found "{current_status or "unknown"}"'
        )

    resolved_phase_info = (
        phase_info if phase_info is not None else (find_phase(cwd, target_phase) if target_phase else None)
    )
    if resolved_phase_info is not None:
        summary_count = len(getattr(resolved_phase_info, "summaries", []))
        has_verification = bool(getattr(resolved_phase_info, "has_verification", False))
        if summary_count or has_verification:
            detail = (
                f'required_state=phase_executed satisfied for phase "{resolved_phase_info.phase_number}" '
                f"via {summary_count} summary artifact(s)"
                if summary_count
                else f'required_state=phase_executed satisfied for phase "{resolved_phase_info.phase_number}" '
                "via existing verification artifacts"
            )
            if current_phase and target_phase and current_phase != target_phase:
                detail = f"{detail}; current state is focused on phase {current_phase}"
            return True, detail

    if target_phase:
        return False, f'required_state=phase_executed is not satisfied for phase "{target_phase}"'
    return False, "required_state=phase_executed could not determine a target phase"


def _current_review_phase_subject(cwd: Path) -> str | None:
    """Return the current phase number from state.json for phase-scoped review preflights."""
    from gpd.core.state import load_state_json_readonly
    from gpd.core.utils import phase_normalize

    state_obj = load_state_json_readonly(cwd)
    if not isinstance(state_obj, dict):
        return None
    position = state_obj.get("position")
    if not isinstance(position, dict):
        return None
    current_phase = phase_normalize(str(position.get("current_phase") or "")).strip()
    return current_phase or None


def _has_any_phase_summary(phases_dir: Path) -> bool:
    """Return True when any numbered or standalone summary exists."""
    if not phases_dir.exists():
        return False
    return any(path.is_file() for path in phases_dir.rglob("*SUMMARY.md"))


def _validate_phase_artifacts(phases_dir: Path, schema_name: str) -> list[str]:
    """Return per-file frontmatter validation failures for phase artifacts."""
    from gpd.core.frontmatter import FrontmatterParseError, FrontmatterValidationError, validate_frontmatter

    if not phases_dir.exists():
        return []

    suffix = "*SUMMARY.md" if schema_name == "summary" else "*VERIFICATION.md"
    failures: list[str] = []
    for path in sorted(phases_dir.rglob(suffix)):
        try:
            content = path.read_text(encoding="utf-8")
            validation = validate_frontmatter(content, schema_name, source_path=path)
        except (OSError, UnicodeDecodeError, FrontmatterParseError, FrontmatterValidationError) as exc:
            failures.append(f"{_format_display_path(path)}: could not validate frontmatter ({exc})")
            continue
        if validation.valid:
            continue
        detail_parts = [*validation.missing, *validation.errors]
        detail = "; ".join(detail_parts[:3]) if detail_parts else "frontmatter invalid"
        failures.append(f"{_format_display_path(path)}: {detail}")
    return failures


def _first_existing_path(*candidates: Path) -> Path | None:
    """Return the first existing path from *candidates*, if any."""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_json_document(input_path: str) -> object:
    """Load a JSON document from a file path or stdin marker ``-``."""

    if input_path == "-":
        raw = sys.stdin.read()
        source = "stdin"
    else:
        target = Path(input_path)
        if not target.is_absolute():
            target = _get_cwd() / target
        source = _format_display_path(target)
        try:
            raw = target.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise GPDError(f"JSON input not found: {source}") from exc
        except UnicodeDecodeError as exc:
            raise GPDError(f"JSON input is not valid UTF-8: {source}: {exc}") from exc
        except OSError as exc:
            raise GPDError(f"Failed to read JSON input from {source}: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GPDError(f"Invalid JSON from {source}: {exc}") from exc


def _load_text_document(input_path: str) -> tuple[Path, str]:
    """Load a UTF-8 text document relative to the effective CLI cwd."""

    target = Path(input_path)
    if not target.is_absolute():
        target = _get_cwd() / target
    source = _format_display_path(target)
    try:
        return target, target.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GPDError(f"Text input not found: {source}") from exc
    except UnicodeDecodeError as exc:
        raise GPDError(f"Text input is not valid UTF-8: {source}: {exc}") from exc
    except OSError as exc:
        raise GPDError(f"Failed to read text input from {source}: {exc}") from exc


def _load_json_document_or_error(input_path: str) -> object:
    """Load JSON input and emit the standard CLI error envelope on failure."""

    try:
        return _load_json_document(input_path)
    except GPDError as exc:
        _error(str(exc))


def _load_text_document_or_error(input_path: str) -> tuple[Path, str]:
    """Load text input and emit the standard CLI error envelope on failure."""

    try:
        return _load_text_document(input_path)
    except GPDError as exc:
        _error(str(exc))


def _manifest_reference_root_for_path_checks(input_path: str) -> Path:
    """Return the root used for manifest-local referenced-path checks."""

    if input_path == "-":
        return _get_cwd()
    return _resolve_path_from_effective_cwd(input_path).parent


def _project_root_for_json_input(input_path: str) -> Path:
    """Return the best project-root anchor for a JSON artifact input path."""

    cwd = _get_cwd()
    if input_path == "-":
        return cwd

    target = Path(input_path)
    resolved = (cwd / target if not target.is_absolute() else target.expanduser()).resolve(strict=False)
    anchored_root = resolve_project_root(resolved.parent, require_layout=True)
    if anchored_root is not None:
        return anchored_root
    return resolved.parent


def _enclosing_project_root_for_json_input(input_path: str) -> Path | None:
    """Return the enclosing project root for a JSON artifact, if one exists."""

    cwd = _get_cwd()
    if input_path == "-":
        return resolve_project_root(cwd, require_layout=True)

    target = Path(input_path)
    resolved = (cwd / target if not target.is_absolute() else target.expanduser()).resolve(strict=False)
    return resolve_project_root(resolved.parent, require_layout=True)


def _resolve_existing_input_path(input_path: str | None, *, candidates: tuple[str, ...], label: str) -> Path:
    """Resolve an explicit or default input path under the current cwd."""
    if input_path:
        target = Path(input_path)
        if not target.is_absolute():
            target = _get_cwd() / target
        if not target.exists():
            raise GPDError(f"{label} not found: {_format_display_path(target)}")
        return target

    resolved = _first_existing_path(*(_get_cwd() / candidate for candidate in candidates))
    if resolved is not None:
        return resolved

    searched = ", ".join(candidates)
    raise GPDError(f"No {label} found. Searched: {searched}")


def _resolve_default_paper_config_path(*, project_root: Path | None = None) -> Path:
    """Resolve the default paper config without silently preferring one supported root over another."""
    cwd = (project_root or _project_scoped_cwd()).expanduser().resolve(strict=False)
    candidates = tuple(cwd / root / "PAPER-CONFIG.json" for root in ("paper", "manuscript", "draft"))
    existing = [path for path in candidates if path.exists()]
    if len(existing) == 1:
        return existing[0]
    if not existing:
        resolution = resolve_current_manuscript_resolution(cwd, allow_markdown=True)
        if resolution.status == "resolved" and resolution.manuscript_root is not None:
            resolved_config = resolution.manuscript_root / "PAPER-CONFIG.json"
            if resolved_config.exists():
                return resolved_config
        searched = ", ".join(f"{root}/PAPER-CONFIG.json" for root in ("paper", "manuscript", "draft"))
        raise GPDError(f"No paper config found. Searched: {searched}")

    resolution = resolve_current_manuscript_resolution(cwd, allow_markdown=True)
    if resolution.status == "resolved" and resolution.manuscript_root is not None:
        resolved_config = resolution.manuscript_root / "PAPER-CONFIG.json"
        if resolved_config in existing:
            return resolved_config

    discovered = ", ".join(_format_display_path(path) for path in existing)
    raise GPDError(
        "Ambiguous paper config across supported manuscript roots. "
        f"Found: {discovered}. Pass an explicit config path or fix the manuscript-root ambiguity first."
    )


def _managed_publication_manuscript_output_policy(
    *,
    project_root: Path,
    manuscript_config_path: Path,
):
    """Return the narrow managed manuscript output policy for one config path, when applicable."""
    from gpd.core.storage_paths import ManagedOutputPolicy

    manuscript_root = _supported_manuscript_root_for_target(project_root, manuscript_config_path)
    if manuscript_root is None:
        return None
    try:
        relative_root = manuscript_root.resolve(strict=False).relative_to(project_root.resolve(strict=False))
    except ValueError:
        return None
    if (
        len(relative_root.parts) != 4
        or relative_root.parts[0] != PLANNING_DIR_NAME
        or relative_root.parts[1] != PUBLICATION_DIR_NAME
        or relative_root.parts[3] != PUBLICATION_MANUSCRIPT_DIR_NAME
    ):
        return None
    return ManagedOutputPolicy.gpd_subtree(
        PUBLICATION_DIR_NAME,
        relative_root.parts[2],
        PUBLICATION_MANUSCRIPT_DIR_NAME,
    )


def _resolve_paper_config_paths(config: object, *, base_dir: Path) -> PaperConfig:
    """Resolve relative figure paths in a PaperConfig against its config file directory."""
    from gpd.mcp.paper.models import FigureRef, PaperConfig

    paper_config = PaperConfig.model_validate(config)
    if not paper_config.figures:
        return paper_config

    resolved_figures: list[FigureRef] = []
    for figure in paper_config.figures:
        resolved_path = figure.path if figure.path.is_absolute() else (base_dir / figure.path).resolve(strict=False)
        resolved_figures.append(figure.model_copy(update={"path": resolved_path}))
    return paper_config.model_copy(update={"figures": resolved_figures})


def _resolve_bibliography_path(
    *,
    explicit_path: str | None,
    config_path: Path,
    output_dir: Path,
    bib_stem: str,
    project_root: Path,
) -> Path | None:
    """Resolve an optional bibliography source path for a paper build."""
    if explicit_path:
        target = Path(explicit_path)
        if not target.is_absolute():
            target = _get_cwd() / target
        if not target.exists():
            raise GPDError(f"Bibliography file not found: {_format_display_path(target)}")
        return target

    candidates = (
        config_path.parent / f"{bib_stem}.bib",
        output_dir / f"{bib_stem}.bib",
        project_root / "references" / f"{bib_stem}.bib",
    )
    return _first_existing_path(*candidates)


def _citation_source_bound_stems(paper_config: PaperConfig) -> frozenset[str]:
    """Return filename stems that explicitly bind citation sources to this paper build."""

    from gpd.mcp.paper.models import derive_output_filename

    stems: set[str] = set()
    output_stem = derive_output_filename(paper_config).strip()
    if output_stem:
        stems.add(output_stem.casefold())
        stems.add(output_stem.replace("_", "-").casefold())
    title_slug = normalize_ascii_slug(paper_config.title)
    if title_slug:
        stems.add(title_slug.casefold())
        stems.add(title_slug.replace("-", "_").casefold())
    return frozenset(stem for stem in stems if stem)


def _discover_literature_review_citation_sources(
    project_root: Path,
    *,
    paper_config: PaperConfig,
) -> tuple[Path | None, str | None]:
    """Return a citation-source sidecar only when its filename binds to the paper build."""

    literature_dir = project_root / "GPD" / "literature"
    if not literature_dir.is_dir():
        return None, None

    matches = sorted(path for path in literature_dir.rglob("*-CITATION-SOURCES.json") if path.is_file())
    if not matches:
        return None, None
    bound_stems = _citation_source_bound_stems(paper_config)
    bound_matches = [path for path in matches if path.name[: -len("-CITATION-SOURCES.json")].casefold() in bound_stems]
    if len(bound_matches) == 1:
        return bound_matches[0], None
    if len(bound_matches) > 1:
        preview = ", ".join(_format_display_path(path) for path in bound_matches[:3])
        remaining = len(bound_matches) - 3
        suffix = f", ... (+{remaining} more)" if remaining > 0 else ""
        return (
            None,
            "Multiple bound literature-review citation-source sidecars found; "
            f"pass --citation-sources explicitly: {preview}{suffix}",
        )

    preview = ", ".join(_format_display_path(path) for path in matches[:3])
    remaining = len(matches) - 3
    suffix = f", ... (+{remaining} more)" if remaining > 0 else ""
    if len(matches) == 1:
        warning = (
            "Ignoring unbound literature-review citation-source sidecar; "
            "pass --citation-sources explicitly to use it: "
            f"{preview}"
        )
    else:
        warning = (
            "Multiple literature-review citation-source sidecars found; "
            "pass --citation-sources explicitly: "
            f"{preview}{suffix}"
        )
    return None, warning


def _load_citation_sources_payload(citation_source_path: Path) -> list[CitationSource]:
    """Load a CitationSource[] payload from JSON."""
    from gpd.mcp.paper.bibliography import parse_citation_source_sidecar_payload

    raw_sources = _load_json_document(str(citation_source_path))
    try:
        return parse_citation_source_sidecar_payload(
            raw_sources,
            source_path=_format_display_path(citation_source_path),
        )
    except ValueError as exc:
        raise GPDError(f"Invalid citation source in {_format_display_path(citation_source_path)}: {exc}") from exc


def _paper_build_reference_bibtex_bridge(result: object) -> list[dict[str, str]]:
    """Return the emitted reference_id -> bibtex_key bridge for a paper build."""
    preferred_mapping = getattr(result, "reference_bibtex_keys", None)
    if isinstance(preferred_mapping, dict):
        bridge: list[dict[str, str]] = []
        for reference_id, bibtex_key in preferred_mapping.items():
            if not isinstance(reference_id, str) or not reference_id.strip():
                continue
            if not isinstance(bibtex_key, str) or not bibtex_key.strip():
                continue
            bridge.append({"reference_id": reference_id.strip(), "bibtex_key": bibtex_key.strip()})
        if bridge:
            return bridge

    bibliography_audit = getattr(result, "bibliography_audit", None)
    if bibliography_audit is None:
        return []

    bridge = []
    seen_reference_ids: set[str] = set()
    for entry in getattr(bibliography_audit, "entries", []) or []:
        reference_id = getattr(entry, "reference_id", None)
        bibtex_key = getattr(entry, "key", None)
        if not isinstance(reference_id, str) or not reference_id.strip():
            continue
        if not isinstance(bibtex_key, str) or not bibtex_key.strip():
            continue
        normalized_reference_id = reference_id.strip()
        if normalized_reference_id in seen_reference_ids:
            continue
        bridge.append({"reference_id": normalized_reference_id, "bibtex_key": bibtex_key.strip()})
        seen_reference_ids.add(normalized_reference_id)
    return bridge


def _paper_build_toolchain_payload() -> dict[str, object]:
    """Return the paper-build toolchain contract payload."""
    from gpd.mcp.paper.compiler import detect_latex_toolchain

    latex_status = detect_latex_toolchain()
    toolchain = latex_status.model_dump(mode="python")
    latexmk_available = bool(toolchain["latexmk_available"])
    bibtex_available = bool(toolchain["bibtex_available"])
    kpsewhich_available = bool(toolchain["kpsewhich_available"])

    warnings = list(toolchain.get("warnings", [])) if isinstance(toolchain.get("warnings"), list) else []
    if latex_status.available and not latexmk_available:
        warnings.append("latexmk not found; repeated LaTeX passes may be degraded.")
    if latex_status.available and not bibtex_available:
        bibtex_warning = (
            "bibtex not found; bibliography-free builds may still work, but citation-bearing builds and "
            "submission prep can fail without bibtex."
        )
        if bibtex_warning not in warnings:
            warnings.append(bibtex_warning)
    if latex_status.available and not kpsewhich_available:
        warnings.append("kpsewhich not found; TeX resource checks may be best-effort only.")

    toolchain["warnings"] = warnings
    return toolchain


def _default_paper_output_dir(config_file: Path) -> Path:
    """Resolve the default durable output directory for a paper build."""
    return config_file.resolve(strict=False).parent


def _reject_internal_paper_config_location(config_file: Path, *, project_root: Path | None = None) -> None:
    """Reject removed paper-config locations under internal planning storage."""
    resolved_config = config_file.resolve(strict=False)
    project_root = (project_root or _project_scoped_cwd()).resolve(strict=False)
    internal_config_root = project_root / "GPD" / "paper"
    try:
        resolved_config.relative_to(internal_config_root)
    except ValueError:
        return
    raise GPDError(
        "Paper configs under `GPD/paper/` are not supported. Move the config to `paper/`, `manuscript/`, or `draft/`."
    )


def detect_runtime_for_gpd_use(*, cwd: Path | None = None, home: Path | None = None) -> str | None:
    """Resolve the installed-surface runtime via the hook-owned detector."""
    from gpd.hooks.runtime_detect import detect_runtime_for_gpd_use as _detect_runtime_for_gpd_use

    return _detect_runtime_for_gpd_use(cwd=cwd, home=home)


def _active_runtime_command_prefix(*, cwd: Path | None = None) -> str | None:
    """Return the public command prefix for the active runtime, if available."""
    descriptor = resolve_active_runtime_descriptor(
        cwd=cwd or _get_cwd(),
        detect_runtime=detect_runtime_for_gpd_use,
    )
    if descriptor is None:
        return None
    return validated_public_command_prefix(descriptor)


def _active_runtime_validated_surface(*, cwd: Path | None = None) -> str | None:
    """Return the machine-readable public command surface for the active runtime."""
    descriptor = resolve_active_runtime_descriptor(
        cwd=cwd or _get_cwd(),
        detect_runtime=detect_runtime_for_gpd_use,
    )
    if descriptor is None:
        return None
    return descriptor.validated_command_surface


def _active_runtime_settings_command(*, cwd: Path | None = None) -> str:
    """Return the active runtime's settings command, or a runtime-surface-neutral fallback."""
    return format_active_runtime_command(
        "settings",
        cwd=cwd or _get_cwd(),
        detect_runtime=detect_runtime_for_gpd_use,
        fallback="the active runtime's `settings` command",
    )


def _validated_runtime_surface(*, cwd: Path | None = None) -> str:
    """Return the machine-readable surface label for the active runtime."""
    return _active_runtime_validated_surface(cwd=cwd) or "public_runtime_command_surface"


def _active_runtime_command_family(*, cwd: Path | None = None) -> str:
    """Return the runtime-native public command prefix, if it can be resolved."""
    family = _active_runtime_command_prefix(cwd=cwd)
    return family if family else "the active runtime command surface"


def _active_runtime_new_project_command(*, cwd: Path | None = None) -> str:
    """Return the runtime-native new-project command, if it can be resolved."""
    return format_active_runtime_command(
        "new-project",
        cwd=cwd or _get_cwd(),
        detect_runtime=detect_runtime_for_gpd_use,
        fallback="the active runtime's `new-project` command",
    )


def _runtime_surface_dispatch_note(*, cwd: Path | None = None) -> str:
    """Render the standardized runtime-surface note for preflight payloads."""
    family = _active_runtime_command_family(cwd=cwd)
    if family == "the active runtime command surface":
        surface_text = family
    else:
        surface_text = f"the public command surface rooted at `{family}`"
    return (
        f"This preflight validates {surface_text} from the command registry. "
        "It does not guarantee a same-name local `gpd` subcommand exists."
    )


def _command_runtime_surface_metadata(*, cwd: Path | None = None) -> CommandRuntimeSurfaceMetadata:
    resolved_cwd = cwd or _get_cwd()
    return CommandRuntimeSurfaceMetadata(
        validated_surface=_validated_runtime_surface(cwd=resolved_cwd),
        public_runtime_command_prefix=_active_runtime_command_prefix(cwd=resolved_cwd) or "",
        init_command=_active_runtime_new_project_command(cwd=resolved_cwd),
        dispatch_note=_runtime_surface_dispatch_note(cwd=resolved_cwd),
    )


def _canonical_command_name(command_name: str) -> str:
    """Normalize a CLI command name to the registry's public gpd:name form."""
    return canonical_command_label(command_name)


def _resolve_registry_command(command_name: str) -> tuple[object, str]:
    """Resolve a command name through the registry and preserve its public name."""
    return _core_resolve_registry_command(command_name)


def _path_is_within_supported_manuscript_root(project_root: Path, target: Path) -> bool:
    """Return whether *target* lives under a supported manuscript root in *project_root*."""
    return _supported_manuscript_root_for_target(project_root, target) is not None


def _peer_review_mode_resolution(
    project_root: Path,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
) -> PeerReviewModeResolution:
    """Return the resolved peer-review intake mode plus target details."""

    return resolve_peer_review_mode_details(project_root, subject, workspace_cwd=workspace_cwd)


def _peer_review_resolved_mode(
    project_root: Path,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
) -> tuple[str, str]:
    """Return the resolved peer-review intake mode and the reason it was selected."""
    resolution = _peer_review_mode_resolution(project_root, subject, workspace_cwd=workspace_cwd)
    return resolution.resolved_mode, resolution.mode_reason


def _peer_review_artifact_text_surface_ready(
    manuscript: Path,
    *,
    probe: object | None = None,
    verify_generated_surface: bool = False,
) -> tuple[bool, str]:
    """Return whether one peer-review artifact can be converted into review text."""

    try:
        readiness_probe = probe if probe is not None else probe_artifact_text_surface(manuscript)
    except ArtifactTextError as exc:
        return False, str(exc)

    detail = readiness_probe.detail
    for path in (readiness_probe.surface_path, readiness_probe.helper_path):
        if path is None:
            continue
        display_path = _format_display_path(path)
        detail = detail.replace(path.as_posix(), display_path).replace(str(path), display_path)
    if verify_generated_surface and readiness_probe.ready and readiness_probe.surface_kind == "generated":
        try:
            load_artifact_text_surface(manuscript)
        except ArtifactTextError as exc:
            return False, str(exc)
    return readiness_probe.ready, detail


def _build_command_context_preflight(
    command_name: str,
    *,
    arguments: str | None = None,
) -> CommandContextPreflightResult:
    cwd = _get_cwd()
    runtime_surface = _command_runtime_surface_metadata(cwd=cwd)
    return _core_build_command_context_preflight(
        command_name,
        cwd=cwd,
        arguments=arguments,
        command_resolver=_resolve_registry_command,
        project_reentry_resolver=_status_command_reentry,
        runtime_surface_metadata=runtime_surface,
    )


def _build_review_preflight(
    command_name: str,
    *,
    subject: str | None = None,
    strict: bool = False,
) -> ReviewPreflightResult:
    """Evaluate lightweight filesystem/state prerequisites for a review command."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.knowledge_runtime import KnowledgeDocRuntimeRecord, discover_knowledge_docs
    from gpd.core.phases import find_phase
    from gpd.core.state import state_validate

    cwd = _get_cwd()
    command_name, subject = command_label_lookup_and_arguments(command_name, subject)
    command, public_command_name = _resolve_registry_command(command_name)
    project_cwd = _core_command_preflight_cwd(
        command,
        cwd=cwd,
        project_reentry_resolver=_status_command_reentry,
    )
    layout = ProjectLayout(project_cwd)
    contract = command.review_contract
    if contract is None:
        raise GPDError(f"Command {public_command_name} does not expose a review contract")
    resolved_mode = ""
    mode_reason = ""
    standalone_peer_review_mode = False

    checks: list[ReviewPreflightCheck] = []
    phase_subject = subject
    if phase_subject is None and _review_contract_requests_check(contract, "phase_artifacts"):
        phase_subject = _current_review_phase_subject(project_cwd)
    phase_info = (
        find_phase(project_cwd, phase_subject)
        if phase_subject and _review_contract_requests_check(contract, "phase_artifacts")
        else None
    )
    manuscript: Path | None = None
    active_conditional_requirements: list[ReviewContractConditionalRequirement] = []
    conditional_blocking_preflight_checks: set[str] = set()
    active_requested_preflight_checks = _review_contract_active_requested_preflight_checks(contract)

    def requested_review_check(check_name: str) -> bool:
        return check_name in active_requested_preflight_checks

    def add_check(name: str, passed: bool, detail: str, *, blocking: bool | None = None) -> None:
        checks.append(
            ReviewPreflightCheck(
                name=name,
                passed=passed,
                detail=detail,
                blocking=(
                    _review_preflight_check_is_blocking(
                        contract,
                        name,
                        conditional_blocking_preflight_checks=conditional_blocking_preflight_checks,
                    )
                    if blocking is None
                    else blocking
                ),
            )
        )

    context_preflight = _build_command_context_preflight(command_name, arguments=subject)
    resolved_subject = context_preflight.resolved_subject or _build_resolved_command_subject(
        project_cwd,
        command,
        subject,
        workspace_cwd=cwd,
        project_root_source="workspace" if layout.project_md.exists() else None,
        project_root_auto_selected=False,
        reentry_mode="current-workspace" if layout.project_md.exists() else None,
    )
    subject_preflight_policy = _publication_subject_preflight_policy(
        command,
        resolved_subject=resolved_subject,
    )
    knowledge_inventory = None
    knowledge_record: KnowledgeDocRuntimeRecord | None = None
    knowledge_target_path: Path | None = None
    knowledge_target_id: str | None = None

    def load_knowledge_context() -> tuple[Path | None, str | None, KnowledgeDocRuntimeRecord | None]:
        nonlocal knowledge_inventory, knowledge_record, knowledge_target_path, knowledge_target_id
        if knowledge_inventory is not None:
            return knowledge_target_path, knowledge_target_id, knowledge_record

        knowledge_inventory = discover_knowledge_docs(project_cwd)
        if (
            resolved_subject is not None
            and resolved_subject.subject_kind == "knowledge_document"
            and resolved_subject.target_path is not None
        ):
            knowledge_target_path = resolved_subject.target_path.resolve(strict=False)
        elif isinstance(subject, str) and subject.strip():
            status, candidate_path, _detail = _resolve_review_knowledge_target(
                project_cwd,
                subject,
                workspace_cwd=cwd,
            )
            if status in {"resolved", "missing", "invalid"} and candidate_path is not None:
                knowledge_target_path = candidate_path.resolve(strict=False)

        if knowledge_target_path is not None and knowledge_target_path.stem.startswith("K-"):
            knowledge_target_id = knowledge_target_path.stem

        if knowledge_target_path is not None:
            try:
                relative_path = knowledge_target_path.relative_to(project_cwd.resolve(strict=False)).as_posix()
            except ValueError:
                relative_path = None
            if relative_path is not None:
                knowledge_record = knowledge_inventory.by_path().get(relative_path)
        if knowledge_record is None and knowledge_target_id:
            knowledge_record = knowledge_inventory.by_id().get(knowledge_target_id)
        return knowledge_target_path, knowledge_target_id, knowledge_record

    def knowledge_target_warnings(target_path: Path | None) -> list[str]:
        if knowledge_inventory is None or target_path is None:
            return []
        try:
            relative_path = target_path.relative_to(project_cwd.resolve(strict=False)).as_posix()
        except ValueError:
            return []
        return [warning for warning in knowledge_inventory.warnings if relative_path in warning]

    effective_required_outputs = (
        list(subject_preflight_policy.required_outputs)
        if subject_preflight_policy.required_outputs
        else list(contract.required_outputs)
    )
    effective_required_evidence = (
        list(subject_preflight_policy.required_evidence)
        if subject_preflight_policy.required_evidence
        else list(contract.required_evidence)
    )
    effective_blocking_conditions = (
        list(subject_preflight_policy.blocking_conditions)
        if subject_preflight_policy.blocking_conditions
        else list(contract.blocking_conditions)
    )
    context_detail = context_preflight.guidance or f"context_mode={_command_effective_context_mode(command)}"
    if context_preflight.resolved_mode:
        context_detail = f"{context_detail}; resolved_mode={context_preflight.resolved_mode}"
    if context_preflight.mode_reason:
        context_detail = f"{context_detail}; {context_preflight.mode_reason}"
    if context_preflight.dispatch_note:
        context_detail = f"{context_detail}; {context_preflight.dispatch_note}"
    if command.name == "gpd:peer-review":
        resolved_mode, mode_reason = _peer_review_resolved_mode(project_cwd, subject, workspace_cwd=cwd)
        standalone_peer_review_mode = resolved_mode != PEER_REVIEW_PROJECT_BACKED_MODE
        active_conditional_requirements = _review_contract_active_conditional_requirements(
            contract,
            project_cwd=project_cwd,
            manuscript=None,
            resolved_mode=resolved_mode,
        )
        conditional_blocking_preflight_checks = {
            check_name
            for requirement in active_conditional_requirements
            for check_name in list(getattr(requirement, "blocking_preflight_checks", []) or [])
        }
        active_requested_preflight_checks = _review_contract_active_requested_preflight_checks(
            contract,
            active_conditional_requirements,
        )
    add_check(
        "command_context",
        context_preflight.passed,
        context_detail,
        blocking=_review_preflight_check_is_blocking(contract, "command_context"),
    )

    if str(getattr(command, "name", "") or "") == "gpd:review-knowledge":
        state_files_present = layout.state_json.exists() and layout.state_md.exists()
        detail = (
            f"{_format_display_path(layout.state_json)} and {_format_display_path(layout.state_md)} present as optional background context"
            if state_files_present
            else "current-workspace knowledge review: project state is advisory background context only"
        )
        add_check("project_state", True, detail, blocking=False)

    if "knowledge_target" in contract.preflight_checks:
        target_path, target_id, _record = load_knowledge_context()
        target_passed = (
            resolved_subject is not None
            and resolved_subject.subject_kind == "knowledge_document"
            and resolved_subject.status == "resolved"
        )
        detail = (
            resolved_subject.detail
            if resolved_subject is not None and resolved_subject.subject_kind == "knowledge_document"
            else (
                f"canonical knowledge target {_format_display_path(target_path)}"
                if target_path is not None
                else (
                    f"canonical knowledge id {target_id}"
                    if target_id
                    else "missing explicit canonical knowledge target"
                )
            )
        )
        add_check("knowledge_target", target_passed, detail)

    if "knowledge_document" in contract.preflight_checks:
        target_path, target_id, record = load_knowledge_context()
        document_exists = record is not None
        target_warnings = knowledge_target_warnings(target_path)
        detail = (
            f"{_format_display_path(target_path)} present and parsed"
            if record is not None and target_path is not None
            else (
                f"{_format_display_path(target_path)} present but failed strict parsing: {'; '.join(target_warnings)}"
                if target_path is not None and target_path.exists() and target_warnings
                else (
                    f"{_format_display_path(target_path)} present but failed strict parsing"
                    if target_path is not None and target_path.exists()
                    else (
                        f"missing canonical knowledge document {_format_display_path(target_path)}"
                        if target_path is not None
                        else (
                            f"missing canonical knowledge document for {target_id}"
                            if target_id
                            else "missing canonical knowledge document"
                        )
                    )
                )
            )
        )
        add_check("knowledge_document", document_exists, detail)

    if "knowledge_review_freshness" in contract.preflight_checks:
        _target_path, _target_id, record = load_knowledge_context()
        freshness_passed = True
        detail = "no prior approved review freshness requirement"
        if record is not None and record.status == "stable":
            freshness_passed = bool(record.review_fresh) and record.stale is False
            detail = (
                "approved review evidence is fresh"
                if freshness_passed
                else "stable knowledge document has stale or missing approved review evidence"
            )
        add_check("knowledge_review_freshness", freshness_passed, detail)

    if requested_review_check("project_state"):
        optional_detail = subject_preflight_policy.detail("project_state")
        if optional_detail is not None:
            add_check(
                "project_state",
                True,
                optional_detail,
                blocking=False,
            )
        elif standalone_peer_review_mode:
            add_check(
                "project_state",
                True,
                "external artifact review: project state is optional",
                blocking=False,
            )
        else:
            state_ok = layout.state_json.exists() and layout.state_md.exists()
            add_check(
                "project_state",
                state_ok,
                (
                    f"state.json={layout.state_json.exists()}, STATE.md={layout.state_md.exists()}"
                    if not state_ok
                    else f"{_format_display_path(layout.state_json)} and {_format_display_path(layout.state_md)} present"
                ),
            )
            if strict:
                validation = state_validate(project_cwd, integrity_mode="review")
                detail = f"integrity_status={validation.integrity_status}"
                if validation.issues:
                    detail = f"{detail}; {'; '.join(validation.issues)}"
                add_check("state_integrity", validation.valid, detail, blocking=True)

    if requested_review_check("roadmap"):
        optional_detail = subject_preflight_policy.detail("roadmap")
        if optional_detail is not None:
            add_check("roadmap", True, optional_detail, blocking=False)
        elif standalone_peer_review_mode:
            add_check("roadmap", True, "external artifact review: roadmap is optional", blocking=False)
        else:
            add_check(
                "roadmap",
                layout.roadmap.exists(),
                (
                    f"{_format_display_path(layout.roadmap)} present"
                    if layout.roadmap.exists()
                    else f"missing {_format_display_path(layout.roadmap)}"
                ),
            )

    if requested_review_check("conventions"):
        optional_detail = subject_preflight_policy.detail("conventions")
        if optional_detail is not None:
            add_check("conventions", True, optional_detail, blocking=False)
        elif standalone_peer_review_mode:
            add_check("conventions", True, "external artifact review: project conventions are optional", blocking=False)
        else:
            add_check(
                "conventions",
                layout.conventions_md.exists(),
                (
                    f"{_format_display_path(layout.conventions_md)} present"
                    if layout.conventions_md.exists()
                    else f"missing {_format_display_path(layout.conventions_md)}"
                ),
            )

    if requested_review_check("research_artifacts"):
        optional_detail = subject_preflight_policy.detail("research_artifacts")
        if optional_detail is not None:
            add_check(
                "research_artifacts",
                True,
                optional_detail,
                blocking=False,
            )
            if requested_review_check("verification_reports"):
                add_check(
                    "verification_reports",
                    True,
                    subject_preflight_policy.detail("verification_reports") or "verification reports are optional",
                    blocking=False,
                )
        elif standalone_peer_review_mode:
            add_check(
                "research_artifacts",
                True,
                "external artifact review: research artifacts are optional",
                blocking=False,
            )
            if requested_review_check("verification_reports"):
                add_check(
                    "verification_reports",
                    True,
                    "external artifact review: verification reports are optional",
                    blocking=False,
                )
        else:
            digest_exists = layout.milestones_dir.exists() and any(layout.milestones_dir.rglob("RESEARCH-DIGEST.md"))
            summary_exists = _has_any_phase_summary(layout.phases_dir)
            passed = digest_exists or summary_exists
            detail = "milestone digest or phase summaries present" if passed else "no digest or phase summaries found"
            add_check("research_artifacts", passed, detail)
            if strict and summary_exists:
                summary_failures = _validate_phase_artifacts(layout.phases_dir, "summary")
                add_check(
                    "summary_frontmatter",
                    not summary_failures,
                    "all phase summaries satisfy the summary schema"
                    if not summary_failures
                    else "; ".join(summary_failures[:3]),
                    blocking=True,
                )
            verification_reports_requested = requested_review_check("verification_reports")
            if verification_reports_requested:
                verification_exists = layout.phases_dir.exists() and any(layout.phases_dir.rglob("*VERIFICATION.md"))
                add_check(
                    "verification_reports",
                    verification_exists,
                    "verification reports present" if verification_exists else "no verification reports found",
                )
                if strict and verification_exists:
                    verification_failures = _validate_phase_artifacts(layout.phases_dir, "verification")
                    add_check(
                        "verification_frontmatter",
                        not verification_failures,
                        "all verification reports satisfy the verification schema"
                        if not verification_failures
                        else "; ".join(verification_failures[:3]),
                        blocking=True,
                    )

    if requested_review_check("manuscript"):
        allow_markdown = not _command_requires_compiled_manuscript(command)
        supports_explicit_manuscript_subject = _command_supports_explicit_manuscript_subject(command)
        explicit_manuscript_subject = _command_explicit_manuscript_argument(command, subject)
        if supports_explicit_manuscript_subject:
            manuscript, manuscript_detail = _resolve_review_preflight_manuscript(
                project_cwd,
                explicit_manuscript_subject,
                allow_markdown=allow_markdown,
                allowed_suffixes=_command_explicit_manuscript_suffixes(command),
                restrict_to_supported_roots=_command_explicit_manuscript_subject_uses_supported_roots(command),
                workspace_cwd=cwd,
            )
            manuscript_passed = manuscript is not None
        else:
            manuscript_detail = (
                resolved_subject.detail
                if resolved_subject is not None
                else "manuscript subject could not be resolved from command context"
            )
            manuscript = (
                resolved_subject.target_path
                if (
                    resolved_subject is not None
                    and resolved_subject.subject_kind == "manuscript"
                    and resolved_subject.status == "resolved"
                    and resolved_subject.target_path is not None
                    and resolved_subject.target_path.is_file()
                )
                else None
            )
            manuscript_passed = resolved_subject is not None and resolved_subject.status in {"resolved", "bootstrap"}
            if _command_requires_compiled_manuscript(command):
                manuscript_passed = manuscript is not None
        if (
            manuscript is not None
            and command.name == "gpd:peer-review"
            and manuscript.suffix.lower()
            in {
                ".pdf",
                ".docx",
                ".csv",
                ".tsv",
                ".xlsx",
                ".xlsm",
            }
        ):
            intake_ready, intake_detail = _peer_review_artifact_text_surface_ready(
                manuscript,
                verify_generated_surface=strict and subject is not None,
            )
            manuscript_passed = manuscript_passed and intake_ready
            if intake_ready:
                manuscript_detail = f"{_format_display_path(manuscript)} present; {intake_detail}"
            else:
                manuscript_detail = intake_detail
        add_check(
            "manuscript",
            manuscript_passed,
            manuscript_detail,
        )
        report_arguments = _command_referee_report_arguments(command, subject)
        if report_arguments:
            report_paths = tuple(
                (
                    _resolve_launch_or_project_relative_path(report, launch_cwd=cwd, project_cwd=project_cwd)
                    or (cwd / report).resolve(strict=False)
                )
                for report in report_arguments
            )
            add_check(
                "referee_report_source",
                all(path.exists() for path in report_paths),
                "; ".join(
                    (
                        f"{_format_display_path(path)} present"
                        if path.exists()
                        else f"missing {_format_display_path(path)}"
                    )
                    for path in report_paths
                ),
            )
        if manuscript is not None:
            if list(getattr(contract, "conditional_requirements", []) or []):
                active_conditional_requirements = _review_contract_active_conditional_requirements(
                    contract,
                    project_cwd=project_cwd,
                    manuscript=manuscript,
                    resolved_mode=resolved_mode,
                )
                conditional_blocking_preflight_checks = {
                    check_name
                    for requirement in active_conditional_requirements
                    for check_name in list(getattr(requirement, "blocking_preflight_checks", []) or [])
                }
                active_requested_preflight_checks = _review_contract_active_requested_preflight_checks(
                    contract,
                    active_conditional_requirements,
                )
            requested_publication_checks = {
                check_name
                for check_name in (
                    "artifact_manifest",
                    "bibliography_audit",
                    "compiled_manuscript",
                    "publication_blockers",
                    "review_ledger",
                    "review_ledger_valid",
                    "referee_decision",
                    "referee_decision_valid",
                    "publication_review_outcome",
                    "reproducibility_manifest",
                    "manuscript_proof_review",
                )
                if requested_review_check(check_name)
            }
            publication_artifacts = _resolve_review_preflight_publication_artifacts(manuscript)
            optional_external_artifact_manifest = (
                "artifact_manifest" not in requested_publication_checks
                and command.name == "gpd:peer-review"
                and standalone_peer_review_mode
                and publication_artifacts.artifact_manifest is not None
            )
            if optional_external_artifact_manifest:
                artifact_manifest_passed, artifact_manifest_detail = _validate_artifact_manifest_semantics(
                    publication_artifacts.artifact_manifest,
                    manuscript,
                    require_freshness=False,
                )
                if not artifact_manifest_passed:
                    add_check("artifact_manifest", False, artifact_manifest_detail, blocking=True)
            if requested_publication_checks:
                artifact_manifest = publication_artifacts.artifact_manifest
                bibliography_audit = publication_artifacts.bibliography_audit
                reproducibility_manifest = publication_artifacts.reproducibility_manifest

                if "artifact_manifest" in requested_publication_checks:
                    artifact_manifest_missing = artifact_manifest is None
                    artifact_manifest_detail = subject_preflight_policy.missing_detail(
                        "artifact_manifest",
                        default=(
                            "no ARTIFACT-MANIFEST.json found near the manuscript"
                            if not standalone_peer_review_mode
                            else "no ARTIFACT-MANIFEST.json found near the manuscript; external artifact review can proceed without it"
                        ),
                    )
                    artifact_manifest_passed = (
                        artifact_manifest is not None
                        or standalone_peer_review_mode
                        or subject_preflight_policy.passes_when_missing("artifact_manifest")
                    )
                    if artifact_manifest is not None:
                        artifact_manifest_passed, artifact_manifest_detail = _validate_artifact_manifest_semantics(
                            artifact_manifest,
                            manuscript,
                        )
                    add_check(
                        "artifact_manifest",
                        artifact_manifest_passed,
                        artifact_manifest_detail,
                        blocking=subject_preflight_policy.blocking(
                            "artifact_manifest",
                            missing=artifact_manifest_missing,
                            default=not standalone_peer_review_mode
                            or (artifact_manifest is not None and not artifact_manifest_passed),
                        ),
                    )

                if "bibliography_audit" in requested_publication_checks:
                    bibliography_missing = bibliography_audit is None
                    bibliography_missing_detail = subject_preflight_policy.missing_detail(
                        "bibliography_audit",
                        default=(
                            "no BIBLIOGRAPHY-AUDIT.json found near the manuscript"
                            if not standalone_peer_review_mode
                            else "no BIBLIOGRAPHY-AUDIT.json found near the manuscript; external artifact review can proceed without it"
                        ),
                    )
                    add_check(
                        "bibliography_audit",
                        bibliography_audit is not None
                        or standalone_peer_review_mode
                        or subject_preflight_policy.passes_when_missing("bibliography_audit"),
                        (
                            f"{_format_display_path(bibliography_audit)} present"
                            if bibliography_audit is not None
                            else bibliography_missing_detail
                        ),
                        blocking=subject_preflight_policy.blocking(
                            "bibliography_audit",
                            missing=bibliography_missing,
                            default=not standalone_peer_review_mode,
                        ),
                    )

                if "compiled_manuscript" in requested_publication_checks:
                    compiled_manuscript = manuscript.with_suffix(".pdf")
                    compiled_manuscript_missing = not compiled_manuscript.exists()
                    add_check(
                        "compiled_manuscript",
                        compiled_manuscript.exists()
                        or subject_preflight_policy.passes_when_missing("compiled_manuscript"),
                        (
                            f"{_format_display_path(compiled_manuscript)} present"
                            if compiled_manuscript.exists()
                            else f"missing compiled manuscript {_format_display_path(compiled_manuscript)}"
                        ),
                        blocking=subject_preflight_policy.blocking(
                            "compiled_manuscript",
                            missing=compiled_manuscript_missing,
                            default=True,
                        ),
                    )

                if "publication_blockers" in requested_publication_checks:
                    if subject_preflight_policy.relaxes("publication_blockers"):
                        add_check(
                            "publication_blockers",
                            True,
                            subject_preflight_policy.missing_detail(
                                "publication_blockers",
                                default="publication blockers are optional for this intake",
                            ),
                            blocking=False,
                        )
                    else:
                        publication_blockers = publication_blockers_for_project(project_cwd)
                        add_check(
                            "publication_blockers",
                            not publication_blockers,
                            (
                                "no unresolved publication blockers"
                                if not publication_blockers
                                else f"{len(publication_blockers)} unresolved publication blocker(s): "
                                + "; ".join(publication_blockers[:3])
                            ),
                            blocking=True,
                        )

                review_ledger = None
                review_checks_requested = requested_publication_checks.intersection(
                    {
                        "review_ledger",
                        "review_ledger_valid",
                        "referee_decision",
                        "referee_decision_valid",
                        "publication_review_outcome",
                    }
                )
                if review_checks_requested:
                    review_ledger_by_round, referee_decision_by_round = _publication_review_round_path_maps(
                        project_cwd,
                        manuscript=manuscript,
                    )
                    latest_review_round = _resolve_latest_publication_review_round_artifacts(
                        project_cwd,
                        manuscript=manuscript,
                    )
                    latest_response_round = _resolve_latest_publication_response_round_artifacts(
                        project_cwd,
                        manuscript=manuscript,
                    )
                    required_review_round = latest_review_round
                    response_freshness = publication_response_freshness_status(
                        latest_review_round=(
                            latest_review_round.round_number if latest_review_round is not None else None
                        ),
                        latest_response_round=(
                            latest_response_round.round_number if latest_response_round is not None else None
                        ),
                    )
                    if response_freshness.requires_fresh_review:
                        add_check(
                            "response_freshness",
                            False,
                            f"{response_freshness.detail}; checkpoint=response_gate",
                            blocking=True,
                        )
                    if (
                        response_freshness.requires_fresh_review
                        and response_freshness.required_review_round is not None
                    ):
                        required_review_round = _publication_review_round_artifacts(
                            response_freshness.required_review_round,
                            review_ledger_by_round=review_ledger_by_round,
                            referee_decision_by_round=referee_decision_by_round,
                        )

                    if required_review_round is None:
                        if "review_ledger" in review_checks_requested:
                            add_check(
                                "review_ledger",
                                False,
                                "missing REVIEW-LEDGER{round_suffix}.json for the required staged publication review",
                                blocking=True,
                            )
                        if "referee_decision" in review_checks_requested:
                            add_check(
                                "referee_decision",
                                False,
                                "missing REFEREE-DECISION{round_suffix}.json for the required staged publication review",
                                blocking=True,
                            )
                    else:
                        ledger_path = required_review_round.review_ledger
                        decision_path = required_review_round.referee_decision
                        review_ledger_manuscript_valid = False
                        review_ledger_round_valid = False
                        round_label = (
                            f"round {required_review_round.round_number}"
                            if required_review_round.round_number > 1
                            else "round 1"
                        )
                        response_round_detail = response_freshness.review_preflight_detail
                        if "review_ledger" in review_checks_requested:
                            add_check(
                                "review_ledger",
                                ledger_path is not None,
                                (
                                    f"{_format_display_path(ledger_path)} present for latest staged review {round_label}"
                                    if ledger_path is not None
                                    else (
                                        f"missing REVIEW-LEDGER{required_review_round.round_suffix}.json "
                                        f"for latest staged review {round_label}{response_round_detail}"
                                    )
                                ),
                                blocking=True,
                            )
                        if "referee_decision" in review_checks_requested:
                            add_check(
                                "referee_decision",
                                decision_path is not None,
                                (
                                    f"{_format_display_path(decision_path)} present for latest staged review {round_label}"
                                    if decision_path is not None
                                    else (
                                        f"missing REFEREE-DECISION{required_review_round.round_suffix}.json "
                                        f"for latest staged review {round_label}{response_round_detail}"
                                    )
                                ),
                                blocking=True,
                            )

                        if ledger_path is not None and review_checks_requested.intersection(
                            {"review_ledger_valid", "referee_decision_valid", "publication_review_outcome"}
                        ):
                            from gpd.mcp.paper.review_artifacts import read_review_ledger

                            try:
                                review_ledger = read_review_ledger(ledger_path)
                            except (OSError, json.JSONDecodeError) as exc:
                                if "review_ledger_valid" in review_checks_requested:
                                    add_check("review_ledger_valid", False, f"could not parse review ledger: {exc}")
                            except PydanticValidationError as exc:
                                if "review_ledger_valid" in review_checks_requested:
                                    add_check(
                                        "review_ledger_valid",
                                        False,
                                        "review ledger is invalid: "
                                        + "; ".join(
                                            _format_pydantic_schema_error(error, root_label="review_ledger")
                                            for error in exc.errors()[:3]
                                        ),
                                    )
                            else:
                                review_ledger_manuscript_valid = manuscript_matches_review_artifact_path(
                                    review_ledger.manuscript_path,
                                    manuscript,
                                    cwd=project_cwd,
                                )
                                review_ledger_round_valid = review_ledger.round == required_review_round.round_number
                                if "review_ledger_valid" in review_checks_requested:
                                    review_ledger_reasons: list[str] = []
                                    if not review_ledger_manuscript_valid:
                                        review_ledger_reasons.append(
                                            "review ledger manuscript_path does not match the active submission manuscript"
                                        )
                                    if not review_ledger_round_valid:
                                        review_ledger_reasons.append(
                                            f"review ledger round {review_ledger.round} does not match required review {round_label}"
                                        )
                                    add_check(
                                        "review_ledger_valid",
                                        not review_ledger_reasons,
                                        (
                                            "review ledger manuscript_path matches the active submission manuscript"
                                            if not review_ledger_reasons
                                            else "; ".join(review_ledger_reasons)
                                        ),
                                        blocking=True,
                                    )

                        if decision_path is not None and review_checks_requested.intersection(
                            {"referee_decision_valid", "publication_review_outcome"}
                        ):
                            from gpd.core.referee_policy import evaluate_referee_decision
                            from gpd.core.reproducibility import compute_sha256
                            from gpd.mcp.paper.models import ReviewRecommendation
                            from gpd.mcp.paper.review_artifacts import read_referee_decision

                            try:
                                decision = read_referee_decision(decision_path)
                            except (OSError, json.JSONDecodeError) as exc:
                                if "referee_decision_valid" in review_checks_requested:
                                    add_check(
                                        "referee_decision_valid",
                                        False,
                                        f"could not parse referee decision: {exc}",
                                    )
                            except PydanticValidationError as exc:
                                if "referee_decision_valid" in review_checks_requested:
                                    add_check(
                                        "referee_decision_valid",
                                        False,
                                        "referee decision is invalid: "
                                        + "; ".join(
                                            _format_pydantic_schema_error(error, root_label="referee_decision")
                                            for error in exc.errors()[:3]
                                        ),
                                    )
                            else:
                                decision_reasons: list[str] = []
                                manuscript_matches_decision = manuscript_matches_review_artifact_path(
                                    decision.manuscript_path,
                                    manuscript,
                                    cwd=project_cwd,
                                )
                                if review_ledger is None:
                                    decision_reasons.append(
                                        "referee decision cannot be validated without the matching review ledger"
                                    )
                                elif not review_ledger_manuscript_valid:
                                    decision_reasons.append(
                                        "referee decision cannot be validated against a review ledger whose manuscript_path does not match the active submission manuscript"
                                    )
                                elif not review_ledger_round_valid:
                                    decision_reasons.append(
                                        f"referee decision cannot be validated against a review ledger whose embedded round does not match required review {round_label}"
                                    )
                                else:
                                    report = evaluate_referee_decision(
                                        decision,
                                        strict=True,
                                        require_explicit_inputs=True,
                                        review_ledger=review_ledger,
                                        project_root=project_cwd,
                                        expected_manuscript_sha256=(
                                            compute_sha256(manuscript) if manuscript_matches_decision else None
                                        ),
                                    )
                                    decision_reasons.extend(report.reasons)
                                if not manuscript_matches_decision:
                                    decision_reasons.append(
                                        "referee decision manuscript_path does not match the active submission manuscript"
                                    )

                                decision_valid = not decision_reasons
                                if "referee_decision_valid" in review_checks_requested:
                                    add_check(
                                        "referee_decision_valid",
                                        decision_valid,
                                        (
                                            "referee decision is valid for the active submission manuscript"
                                            if decision_valid
                                            else "; ".join(decision_reasons[:3])
                                        ),
                                        blocking=True,
                                    )
                                if decision_valid and "publication_review_outcome" in review_checks_requested:
                                    submission_ready = (
                                        decision.final_recommendation
                                        in {ReviewRecommendation.accept, ReviewRecommendation.minor_revision}
                                        and not decision.blocking_issue_ids
                                    )
                                    add_check(
                                        "publication_review_outcome",
                                        submission_ready,
                                        (
                                            "latest staged peer-review recommendation clears submission packaging"
                                            if submission_ready
                                            else (
                                                "latest staged peer-review recommendation requires more revision: "
                                                f"{decision.final_recommendation.value}"
                                                + (
                                                    f"; unresolved blocking issues: {', '.join(decision.blocking_issue_ids)}"
                                                    if decision.blocking_issue_ids
                                                    else ""
                                                )
                                            )
                                        ),
                                        blocking=True,
                                    )

                if "reproducibility_manifest" in requested_publication_checks:
                    reproducibility_missing = reproducibility_manifest is None
                    reproducibility_missing_detail = subject_preflight_policy.missing_detail(
                        "reproducibility_manifest",
                        default=(
                            "no reproducibility manifest found near the manuscript"
                            if not standalone_peer_review_mode
                            else "no reproducibility manifest found near the manuscript; external artifact review can proceed without it"
                        ),
                    )
                    add_check(
                        "reproducibility_manifest",
                        reproducibility_manifest is not None
                        or standalone_peer_review_mode
                        or subject_preflight_policy.passes_when_missing("reproducibility_manifest"),
                        (
                            f"{_format_display_path(reproducibility_manifest)} present"
                            if reproducibility_manifest is not None
                            else reproducibility_missing_detail
                        ),
                        blocking=subject_preflight_policy.blocking(
                            "reproducibility_manifest",
                            missing=reproducibility_missing,
                            default=not standalone_peer_review_mode,
                        ),
                    )

                if "manuscript_proof_review" in requested_publication_checks:
                    if standalone_peer_review_mode or subject_preflight_policy.relaxes("manuscript_proof_review"):
                        manuscript_proof_review_passed = True
                        manuscript_proof_review_blocking = False
                        manuscript_proof_review_detail = subject_preflight_policy.missing_detail(
                            "manuscript_proof_review",
                            default="prior staged manuscript proof review is optional for this intake",
                        )
                    else:
                        manuscript_proof_review = resolve_manuscript_proof_review_status(
                            project_cwd,
                            manuscript,
                            persist_manifest=command.name != "gpd:arxiv-submission",
                        )
                        theorem_bearing_review_required = _requires_theorem_bearing_manuscript_review(
                            project_cwd, manuscript
                        )
                        manuscript_proof_review_passed = (
                            manuscript_proof_review.can_rely_on_prior_review
                            or manuscript_proof_review.state == "not_reviewed"
                        )
                        manuscript_proof_review_blocking = False
                        manuscript_proof_review_detail = manuscript_proof_review.detail
                        if _command_requires_compiled_manuscript(command):
                            if "manuscript_proof_review" in conditional_blocking_preflight_checks:
                                manuscript_proof_review_passed = manuscript_proof_review.can_rely_on_prior_review
                                manuscript_proof_review_blocking = True
                            else:
                                manuscript_proof_review_passed = True
                                manuscript_proof_review_detail = (
                                    "no theorem-bearing claims were detected in the latest matching staged claim inventory "
                                    "or staged math review; manuscript proof review is not required for submission"
                                )
                        elif _command_allows_manuscript_bootstrap(command):
                            manuscript_proof_review_passed = manuscript_proof_review.can_rely_on_prior_review
                            manuscript_proof_review_blocking = False
                            if theorem_bearing_review_required and not manuscript_proof_review_passed:
                                manuscript_proof_review_detail = (
                                    manuscript_proof_review.detail
                                    + "; write-paper will run its own staged proof-review loop"
                                )
                    add_check(
                        "manuscript_proof_review",
                        manuscript_proof_review_passed,
                        manuscript_proof_review_detail,
                        blocking=manuscript_proof_review_blocking,
                    )

                if strict and bibliography_audit is not None and "bibliography_audit" in requested_publication_checks:
                    clean, detail = _validate_bibliography_audit_semantics(bibliography_audit)
                    add_check(
                        "bibliography_audit_clean",
                        clean,
                        detail,
                        blocking=subject_preflight_policy.blocking(
                            "bibliography_audit_clean",
                            default=not standalone_peer_review_mode,
                        ),
                    )
                if (
                    strict
                    and reproducibility_manifest is not None
                    and "reproducibility_manifest" in requested_publication_checks
                ):
                    from gpd.core.reproducibility import validate_reproducibility_manifest

                    try:
                        repro_payload = json.loads(reproducibility_manifest.read_text(encoding="utf-8"))
                        repro_validation = validate_reproducibility_manifest(repro_payload)
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                        add_check(
                            "reproducibility_ready",
                            False,
                            f"could not validate reproducibility manifest: {exc}",
                            blocking=subject_preflight_policy.blocking(
                                "reproducibility_ready",
                                default=not standalone_peer_review_mode,
                            ),
                        )
                    else:
                        ready = (
                            repro_validation.valid
                            and repro_validation.ready_for_review
                            and not repro_validation.warnings
                        )
                        detail = (
                            "reproducibility manifest is review-ready"
                            if ready
                            else (
                                f"valid={repro_validation.valid}, ready_for_review={repro_validation.ready_for_review}, "
                                f"warnings={len(repro_validation.warnings)}, issues={len(repro_validation.issues)}"
                            )
                        )
                        add_check(
                            "reproducibility_ready",
                            ready,
                            detail,
                            blocking=subject_preflight_policy.blocking(
                                "reproducibility_ready",
                                default=not standalone_peer_review_mode,
                            ),
                        )

    if requested_review_check("phase_artifacts"):
        if subject:
            phase_exists = phase_info is not None
            add_check(
                "phase_lookup",
                phase_exists,
                (
                    f'phase "{subject}" found in {_format_display_path(layout.phases_dir)}'
                    if phase_exists
                    else f'phase "{subject}" not found'
                ),
                blocking=True,
            )
            if phase_exists:
                summary_exists = bool(phase_info.summaries)
                add_check(
                    "phase_summaries",
                    summary_exists,
                    (
                        f'phase "{subject}" has {len(phase_info.summaries)} summary file(s)'
                        if summary_exists
                        else f'phase "{subject}" has no SUMMARY artifacts'
                    ),
                    blocking=True,
                )
        else:
            summary_exists = (
                bool(getattr(phase_info, "summaries", []))
                if phase_info is not None
                else _has_any_phase_summary(layout.phases_dir)
            )
            add_check(
                "phase_summaries",
                summary_exists,
                (
                    f'current phase "{phase_info.phase_number}" has {len(phase_info.summaries)} summary file(s)'
                    if phase_info is not None and summary_exists
                    else (
                        f'current phase "{phase_info.phase_number}" has no SUMMARY artifacts'
                        if phase_info is not None
                        else ("phase summaries present" if summary_exists else "no phase summaries found")
                    )
                ),
                blocking=True,
            )
        if command.name == "gpd:verify-work" and phase_info is not None:
            phase_proof_review = resolve_phase_proof_review_status(
                project_cwd,
                project_cwd / phase_info.directory,
            )
            add_check(
                "phase_proof_review",
                phase_proof_review.can_rely_on_prior_review or phase_proof_review.state == "not_reviewed",
                phase_proof_review.detail,
                blocking=False,
            )

    required_state_check = _evaluate_review_required_state(contract, cwd=cwd, subject=subject, phase_info=phase_info)
    if required_state_check is not None:
        add_check("required_state", required_state_check[0], required_state_check[1], blocking=True)

    effective_required_outputs = _effective_review_contract_strings(
        list(subject_preflight_policy.required_outputs)
        if subject_preflight_policy.required_outputs
        else list(getattr(contract, "required_outputs", []) or []),
        active_conditional_requirements,
        "required_outputs",
    )
    effective_required_evidence = _effective_review_contract_strings(
        list(subject_preflight_policy.required_evidence)
        if subject_preflight_policy.required_evidence
        else list(getattr(contract, "required_evidence", []) or []),
        active_conditional_requirements,
        "required_evidence",
    )
    effective_blocking_conditions = _effective_review_contract_strings(
        list(subject_preflight_policy.blocking_conditions)
        if subject_preflight_policy.blocking_conditions
        else list(getattr(contract, "blocking_conditions", []) or []),
        active_conditional_requirements,
        "blocking_conditions",
    )
    publication_routing = _review_preflight_publication_routing(
        project_root=project_cwd,
        command=command,
        resolved_subject=resolved_subject,
        manuscript=manuscript,
        context_preflight=context_preflight,
    )
    passed = all(check.passed or not check.blocking for check in checks)
    return ReviewPreflightResult(
        command=public_command_name,
        review_mode=contract.review_mode,
        strict=strict,
        passed=passed,
        checks=checks,
        required_outputs=effective_required_outputs,
        required_evidence=effective_required_evidence,
        blocking_conditions=effective_blocking_conditions,
        conditional_requirements=list(contract.conditional_requirements),
        active_conditional_requirements=active_conditional_requirements,
        effective_required_evidence=effective_required_evidence,
        effective_blocking_conditions=effective_blocking_conditions,
        resolved_mode=resolved_mode,
        mode_reason=mode_reason,
        validated_surface=context_preflight.validated_surface,
        public_runtime_command_prefix=context_preflight.public_runtime_command_prefix,
        local_cli_equivalence_guaranteed=context_preflight.local_cli_equivalence_guaranteed,
        dispatch_note=context_preflight.dispatch_note,
        resolved_subject=resolved_subject,
        publication_subject_slug=publication_routing["publication_subject_slug"],
        publication_lane_kind=publication_routing["publication_lane_kind"],
        managed_publication_root=publication_routing["managed_publication_root"],
        selected_publication_root=publication_routing["selected_publication_root"],
        selected_review_root=publication_routing["selected_review_root"],
        manuscript_root=publication_routing["manuscript_root"],
        manuscript_entrypoint=publication_routing["manuscript_entrypoint"],
    )


@validate_app.command("consistency")
def validate_consistency() -> None:
    """Validate cross-phase consistency."""
    from gpd.core.health import run_health

    report = run_health(_read_only_project_scoped_cwd())
    _output(report)
    if report.overall == "fail":
        raise typer.Exit(code=1)


@validate_app.command("command-context", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def validate_command_context(
    ctx: typer.Context,
    command_name: str = typer.Argument(..., help="Command registry key or gpd:name"),
) -> None:
    """Run centralized command-context preflight based on command metadata."""
    arguments = " ".join(str(arg) for arg in ctx.args) or None
    try:
        result = _build_command_context_preflight(command_name, arguments=arguments)
    except CommandLookupError as exc:
        requested_command = " ".join(part for part in (command_name, arguments or "") if part)
        lookup_payload = build_command_lookup_error_payload(
            requested_command,
            runtime_surface_metadata=_command_runtime_surface_metadata(cwd=_get_cwd()),
        )
        if _raw:
            _output(dataclasses.asdict(lookup_payload))
        else:
            err_console.print(f"[bold red]Error:[/] {format_command_lookup_error(lookup_payload)}", highlight=False)
        raise typer.Exit(code=1) from exc
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


@validate_app.command("unattended-readiness")
def validate_unattended_readiness_cmd(
    runtime: str = typer.Option(..., "--runtime", help=_runtime_override_help()),
    autonomy: str | None = typer.Option(None, "--autonomy", help="Autonomy to compare against"),
    global_install: bool = typer.Option(False, "--global", help="Check the runtime's global install target"),
    local_install: bool = typer.Option(False, "--local", help="Check the runtime's local install target (default)"),
    target_dir: str | None = typer.Option(
        None,
        "--target-dir",
        help="Override the runtime config directory to inspect",
    ),
    live_executable_probes: bool = typer.Option(
        False,
        "--live-executable-probes",
        help="Run cheap local executable probes such as `pdflatex --version`, `tectonic --version`, or `wolframscript -version`",
    ),
) -> None:
    """Check whether one runtime surface is ready for unattended use."""
    result = _build_unattended_readiness(
        runtime=runtime,
        autonomy=autonomy,
        global_install=global_install,
        local_install=local_install,
        target_dir=target_dir,
        live_executable_probes=live_executable_probes,
    )
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


@validate_app.command("review-contract")
def validate_review_contract(
    command_name: str = typer.Argument(..., help="Command registry key or gpd:name"),
) -> None:
    """Show the typed review contract for a review-grade command."""
    command, public_command_name = _resolve_registry_command(command_name)
    if command.review_contract is None:
        _error(f"Command {public_command_name} has no review contract")
    _output(
        {
            "command": public_command_name,
            "context_mode": _command_effective_context_mode(command),
            "review_contract": dataclasses.asdict(command.review_contract),
        }
    )


@validate_app.command("review-preflight", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def validate_review_preflight(
    ctx: typer.Context,
    command_name: str = typer.Argument(..., help="Command registry key or gpd:name"),
    subject: str | None = typer.Argument(
        None,
        help="Optional phase number, manuscript target, or referee report source",
    ),
    strict: bool = typer.Option(False, "--strict", help="Enable stricter evidence-oriented checks"),
) -> None:
    """Run lightweight executable preflight checks for review-grade workflows."""
    arguments: list[str] = []
    if subject is not None:
        arguments.append(subject)
    arguments.extend(str(arg) for arg in ctx.args)
    result = _build_review_preflight(command_name, subject=" ".join(arguments) or None, strict=strict)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


def _project_local_artifact_ref(path: Path) -> str | None:
    return _artifact_writers.project_local_artifact_ref(path)


def _verification_report_plan_contract_ref(plan_path: Path) -> str:
    return _artifact_writers.verification_report_plan_contract_ref(plan_path)


def _normalize_verification_report_skeleton_status(status: str) -> str:
    return _artifact_writers.normalize_verification_report_skeleton_status(status)


def _normalize_verification_report_skeleton_output(
    raw_payload: object,
    *,
    plan_path: Path,
    plan_contract_ref: str,
    target_status: str,
) -> dict[str, object]:
    return _artifact_writers.normalize_verification_report_skeleton_output(
        raw_payload,
        plan_path=plan_path,
        plan_contract_ref=plan_contract_ref,
        target_status=target_status,
    )


def _normalize_verification_report_skeleton_format(output_format: str) -> str:
    return _artifact_writers.normalize_verification_report_skeleton_format(output_format)


def _project_local_gpd_ref(path_value: object) -> str | None:
    return _artifact_writers.project_local_gpd_ref(path_value)


def _render_verification_report_frontmatter_yaml(
    frontmatter: object,
    *,
    target_report_ref: str | None = None,
) -> str:
    return _artifact_writers.render_verification_report_frontmatter_yaml(
        frontmatter,
        target_report_ref=target_report_ref,
    )


def _ensure_frontmatter_block(frontmatter_yaml: object) -> str:
    return _artifact_writers.ensure_frontmatter_block(frontmatter_yaml)


def _body_markdown_starts_with_frontmatter(body_markdown: str) -> bool:
    return _artifact_writers.body_markdown_starts_with_frontmatter(body_markdown)


def _verification_report_artifact_ref(payload: Mapping[str, object]) -> str:
    return _artifact_writers.verification_report_artifact_ref(payload)


def _verification_report_validation_commands(payload: Mapping[str, object]) -> list[str]:
    return _artifact_writers.verification_report_validation_commands(payload)


def _verification_report_authoring_rules() -> list[str]:
    return _artifact_writers.verification_report_authoring_rules()


def _render_verification_report_markdown_draft(payload: Mapping[str, object]) -> str:
    return _artifact_writers.render_verification_report_markdown_draft(payload)


def _emit_verification_report_skeleton(payload: Mapping[str, object], *, output_format: str) -> None:
    if _raw or output_format == "json":
        _emit_raw_json(dict(payload))
        return
    if output_format == "frontmatter":
        typer.echo(_ensure_frontmatter_block(payload.get("frontmatter_yaml")), nl=False)
        return
    markdown_draft = payload.get("markdown_draft")
    if not isinstance(markdown_draft, str) or not markdown_draft.strip():
        markdown_draft = _render_verification_report_markdown_draft(payload)
    typer.echo(markdown_draft.rstrip() + "\n", nl=False)


def _normalize_verification_report_validate_mode(validate_mode: str | None, *, has_body_file: bool) -> str:
    return _artifact_writers.normalize_verification_report_validate_mode(validate_mode, has_body_file=has_body_file)


def _normalize_verification_report_finalize_validate_mode(validate_mode: str | None) -> str:
    return _artifact_writers.normalize_verification_report_finalize_validate_mode(validate_mode)


def _normalize_verification_report_verified(verified: str | None) -> str | None:
    return _artifact_writers.normalize_verification_report_verified(verified)


def _normalize_verification_report_score(score: str | None) -> str | None:
    return _artifact_writers.normalize_verification_report_score(score)


def _verification_report_output_target(
    output_path: str | None,
    *,
    payload: Mapping[str, object],
    plan_path: Path,
) -> Path:
    return _artifact_writers.verification_report_output_target(
        output_path,
        payload=payload,
        plan_path=plan_path,
        launch_cwd=_get_cwd(),
    )


def _verification_report_validation_commands_for_ref(report_ref: str) -> list[str]:
    return _artifact_writers.verification_report_validation_commands_for_ref(report_ref)


def _verification_report_warning_list(payload: Mapping[str, object], *, validate_mode: str) -> list[str]:
    return _artifact_writers.verification_report_warning_list(payload, validate_mode=validate_mode)


def _render_verification_report_markdown_candidate(frontmatter_yaml: str, body_markdown: str) -> str:
    return _artifact_writers.render_verification_report_markdown_candidate(frontmatter_yaml, body_markdown)


def _render_verification_report_candidate(
    payload: Mapping[str, object],
    *,
    target_report_ref: str,
    body_markdown: str | None,
    verified: str | None,
    score: str | None,
) -> tuple[str, dict[str, object]]:
    return _artifact_writers.render_verification_report_candidate(
        payload,
        target_report_ref=target_report_ref,
        body_markdown=body_markdown,
        verified=verified,
        score=score,
    )


def _verification_report_validation_not_run(mode: str, error: str) -> dict[str, object]:
    return _artifact_writers.verification_report_validation_not_run(mode, error)


def _artifact_target_ref(target_path: Path) -> str:
    return _artifact_writers.artifact_target_ref(target_path)


def _artifact_write_blocker(
    target_path: Path,
    *,
    force: bool,
    target_exists: bool | None = None,
    existing_requires_force: bool = True,
) -> str | None:
    return _artifact_writers.artifact_write_blocker(
        target_path,
        force=force,
        target_exists=target_exists,
        existing_requires_force=existing_requires_force,
        display_path=_format_display_path,
    )


def _atomic_write_artifact_error(target_path: Path, content: str) -> str | None:
    return _artifact_writers.atomic_write_artifact_error(target_path, content)


def _emit_raw_json_and_exit(payload: Mapping[str, object]) -> NoReturn:
    _emit_raw_json(dict(payload))
    raise typer.Exit(code=1)


def _verification_report_write_payload(
    *,
    target_path: Path,
    target_ref: str,
    force: bool,
    body_path: Path | None,
    warnings: list[str],
    validation_commands: list[str],
    patch_file_path: Path | None = None,
) -> dict[str, object]:
    return _artifact_writers.verification_report_write_payload(
        target_path=target_path,
        target_ref=target_ref,
        force=force,
        body_path=body_path,
        warnings=warnings,
        validation_commands=validation_commands,
        patch_file_path=patch_file_path,
    )


def _emit_verification_report_not_run(
    write_payload: dict[str, object],
    *,
    mode: str,
    error: str,
) -> NoReturn:
    write_payload["validation"] = _verification_report_validation_not_run(mode, error)
    _emit_raw_json_and_exit(write_payload)


def _verification_report_write_recovery(
    *,
    plan_path: Path,
    target_path: Path,
    body_path: Path | None,
    validate_mode: str,
    force: bool,
    status: str,
    verified: str | None,
    score: str | None,
) -> dict[str, object]:
    return _artifact_writers.verification_report_write_recovery(
        plan_path=plan_path,
        target_path=target_path,
        body_path=body_path,
        validate_mode=validate_mode,
        force=force,
        status=status,
        verified=verified,
        score=score,
        display_path=_format_display_path,
    )


def _verification_report_finalize_recovery(
    *,
    plan_path: Path,
    patch_path: Path,
    target_path: Path,
    body_path: Path,
    validate_mode: str,
    force: bool,
) -> dict[str, object]:
    return _artifact_writers.verification_report_finalize_recovery(
        plan_path=plan_path,
        patch_path=patch_path,
        target_path=target_path,
        body_path=body_path,
        validate_mode=validate_mode,
        force=force,
        display_path=_format_display_path,
    )


def _validate_verification_report_candidate(
    content: str,
    *,
    source_path: Path,
    mode: str,
) -> dict[str, object]:
    return _artifact_writers.validate_verification_report_candidate(content, source_path=source_path, mode=mode)


def _verification_report_finalized_markdown(payload: Mapping[str, object]) -> str:
    return _artifact_writers.verification_report_finalized_markdown(payload)


def _normalize_proof_redteam_skeleton_status(status: str) -> str:
    return _artifact_writers.normalize_proof_redteam_skeleton_status(status)


def _normalize_proof_redteam_claim_id(claim_id: str) -> str:
    return _artifact_writers.normalize_proof_redteam_claim_id(claim_id)


def _normalize_optional_proof_redteam_claim_text(claim_text: str | None) -> str | None:
    return _artifact_writers.normalize_optional_proof_redteam_claim_text(claim_text)


def _normalize_proof_redteam_proof_artifact_paths(proof_artifact_paths: list[str] | None) -> list[str]:
    return _artifact_writers.normalize_proof_redteam_proof_artifact_paths(proof_artifact_paths)


def _normalize_required_proof_redteam_claim_text(claim_text: str) -> str:
    return _artifact_writers.normalize_required_proof_redteam_claim_text(claim_text)


def _normalize_proof_redteam_reviewed_at(reviewed_at: str | None) -> str | None:
    return _artifact_writers.normalize_proof_redteam_reviewed_at(reviewed_at)


def _normalize_single_proof_redteam_artifact_path(proof_artifact_path: str) -> str:
    return _artifact_writers.normalize_single_proof_redteam_artifact_path(proof_artifact_path)


def _resolve_proof_redteam_proof_artifact_path(
    proof_artifact_path: str,
    *,
    project_root: Path,
    artifact_dir: Path,
) -> Path | None:
    return _artifact_writers.resolve_proof_redteam_proof_artifact_path(
        proof_artifact_path,
        project_root=project_root,
        artifact_dir=artifact_dir,
    )


def _proof_redteam_validation_commands_for_ref(artifact_ref: str) -> list[str]:
    return _artifact_writers.proof_redteam_validation_commands_for_ref(artifact_ref)


def _proof_redteam_finalize_validation_commands_for_ref(artifact_ref: str) -> list[str]:
    return _artifact_writers.proof_redteam_finalize_validation_commands_for_ref(artifact_ref)


def _proof_redteam_artifact_ref_from_payload(payload: Mapping[str, object]) -> str:
    return _artifact_writers.proof_redteam_artifact_ref_from_payload(payload)


def _normalize_proof_redteam_skeleton_output(
    raw_payload: object,
    *,
    claim_id: str,
    claim_text: str | None,
    target_status: str,
) -> dict[str, object]:
    return _artifact_writers.normalize_proof_redteam_skeleton_output(
        raw_payload,
        claim_id=claim_id,
        claim_text=claim_text,
        target_status=target_status,
    )


def _emit_proof_redteam_skeleton(payload: Mapping[str, object]) -> None:
    if _raw:
        _emit_raw_json(dict(payload))
        return
    markdown_draft = payload.get("markdown_draft")
    if not isinstance(markdown_draft, str) or not markdown_draft.strip():
        raise GPDError("proof-redteam skeleton payload is missing markdown_draft")
    typer.echo(markdown_draft.rstrip() + "\n", nl=False)


def _proof_redteam_finalize_output_target(input_path: Path, output_path: str | None) -> Path:
    return _artifact_writers.proof_redteam_finalize_output_target(
        input_path,
        output_path,
        launch_cwd=_get_cwd(),
    )


def _proof_redteam_finalize_not_run(
    error: str,
    *,
    input_path: Path,
    target_path: Path,
    force: bool,
) -> dict[str, object]:
    return _artifact_writers.proof_redteam_finalize_not_run(
        error,
        input_path=input_path,
        target_path=target_path,
        force=force,
    )


def _proof_redteam_finalized_markdown(payload: Mapping[str, object]) -> str | None:
    return _artifact_writers.proof_redteam_finalized_markdown(payload)


def _return_status_help_list(*, include_any: bool = False) -> str:
    from gpd.core.return_contract import RETURN_STATUS_ORDER

    statuses = [*RETURN_STATUS_ORDER]
    if include_any:
        statuses.append("any")
    return ", ".join(statuses)


def _return_required_status_error() -> str:
    return f"required status must be one of: {_return_status_help_list(include_any=True)}"


def _normalize_return_classify_required_status(require_status: str) -> str | None:
    if not isinstance(require_status, str):
        raise GPDError("required status must be a string")
    normalized = require_status.strip().lower()
    if normalized == "any":
        return None
    from gpd.core.return_contract import normalize_return_status

    try:
        return normalize_return_status(require_status, field_name="required status")
    except ValueError as exc:
        raise GPDError(_return_required_status_error()) from exc


def _classify_return_markdown(content: str, *, require_status: str | None = None) -> dict[str, object]:
    from gpd.core.return_repair_classifier import classify_gpd_return_repair

    raw_payload = classify_gpd_return_repair(content, require_status=require_status)
    payload = _mapping_payload(raw_payload, label="return classifier")
    payload.setdefault("mutated", False)
    payload.setdefault("mutates", False)
    return payload


def _return_classification_passed(payload: Mapping[str, object]) -> bool:
    for key in ("passed", "valid", "ok"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return True


def _return_profiles_payload(*, role: str | None, status: str | None) -> dict[str, object]:
    from gpd.core.return_skeleton import list_gpd_return_profiles

    raw_payload = list_gpd_return_profiles(role=role, status=status)
    payload = _mapping_payload(raw_payload, label="return profiles provider")
    payload.setdefault("mutated", False)
    payload.setdefault("mutates", False)
    return payload


def _normalize_return_skeleton_format(output_format: str) -> str:
    normalized = output_format.strip().lower()
    if normalized not in {"markdown", "yaml", "json"}:
        raise GPDError("return skeleton --format must be one of: markdown, yaml, json")
    return normalized


def _normalize_return_skeleton_output(raw_payload: object) -> dict[str, object]:
    normalized = _mapping_payload(raw_payload, label="return skeleton builder")
    envelope = normalized.get("envelope")
    if not isinstance(envelope, Mapping):
        raise GPDError("return skeleton payload is missing envelope")
    if "yaml_payload" not in normalized:
        from gpd.core.return_skeleton import render_gpd_return_yaml

        normalized["yaml_payload"] = render_gpd_return_yaml(envelope)
    if "markdown" not in normalized:
        from gpd.core.return_skeleton import render_gpd_return_markdown

        normalized["markdown"] = render_gpd_return_markdown(envelope)
    return normalized


def _emit_return_skeleton(payload: Mapping[str, object], *, output_format: str) -> None:
    if _raw or output_format == "json":
        _emit_raw_json(dict(payload))
        return
    if output_format == "yaml":
        yaml_payload = payload.get("yaml_payload")
        if not isinstance(yaml_payload, str) or not yaml_payload.strip():
            raise GPDError("return skeleton payload is missing yaml_payload")
        typer.echo(yaml_payload.rstrip() + "\n", nl=False)
        return
    markdown = payload.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise GPDError("return skeleton payload is missing markdown")
    typer.echo(markdown.rstrip() + "\n", nl=False)


def _read_return_skeleton_files_from(files_from: str | None) -> list[str]:
    """Read newline-delimited ``files_written`` seed entries for return skeletons."""

    if files_from is None:
        return []
    source = files_from.strip()
    if not source:
        raise GPDError("return skeleton --files-from must be a path or '-'")
    if source == "-":
        content = sys.stdin.read()
    else:
        _, content = _load_text_document_or_error(source)
    return [line.strip() for line in content.splitlines() if line.strip()]


@return_app.command("skeleton")
def return_skeleton_cmd(
    role: str = typer.Option(..., "--role", help="Return role profile to render."),
    status: str = typer.Option(
        "completed",
        "--status",
        help=f"Canonical gpd_return status to render: {_return_status_help_list()}.",
    ),
    output_format: str = typer.Option(
        "markdown",
        "--format",
        help="Output mode for non-raw use: markdown, yaml, or json.",
    ),
    files_written: list[str] | None = typer.Option(
        None,
        "--file",
        help="Seed one gpd_return.files_written entry. Repeatable.",
    ),
    files_from: str | None = typer.Option(
        None,
        "--files-from",
        help="Read newline-delimited gpd_return.files_written entries from a path or '-' for stdin.",
    ),
    issues: list[str] | None = typer.Option(
        None,
        "--issue",
        help="Seed one gpd_return.issues entry. Repeatable.",
    ),
    next_actions: list[str] | None = typer.Option(
        None,
        "--next-action",
        help="Seed one gpd_return.next_actions entry. Repeatable.",
    ),
    phase: str | None = typer.Option(None, "--phase", help="Optional role-local phase value."),
    plan: str | None = typer.Option(None, "--plan", help="Optional role-local plan value."),
    include_applicator_fields: bool = typer.Option(
        False,
        "--include-applicator-fields",
        help="Include durable continuation fields when the skeleton can be applicator-ready.",
    ),
    include_checkpoint_intent: bool = typer.Option(
        False,
        "--include-checkpoint-intent",
        help="Include child-owned checkpoint intent fields for checkpoint skeletons.",
    ),
    checkpoint_reason: str | None = typer.Option(
        None,
        "--checkpoint-reason",
        help="Seed checkpoint_intent.checkpoint_reason when checkpoint intent is included.",
    ),
    checkpoint_waiting_reason: str | None = typer.Option(
        None,
        "--checkpoint-waiting-reason",
        help="Seed checkpoint_intent.waiting_reason when checkpoint intent is included.",
    ),
    resume_file: str | None = typer.Option(
        None,
        "--resume-file",
        help="Project-relative existing resume file for checkpoint applicator skeletons.",
    ),
) -> None:
    """Render a read-only canonical gpd_return skeleton."""

    try:
        normalized_format = _normalize_return_skeleton_format(output_format)
    except GPDError as exc:
        _error(str(exc))

    from gpd.core.return_skeleton import build_gpd_return_skeleton

    project_root = _read_only_project_scoped_cwd(_get_cwd())
    try:
        seeded_files = [*(files_written or []), *_read_return_skeleton_files_from(files_from)]
        raw_payload = build_gpd_return_skeleton(
            role=role,
            status=status,
            files_written=seeded_files,
            issues=issues or [],
            next_actions=next_actions or [],
            phase=phase,
            plan=plan,
            include_applicator_fields=include_applicator_fields,
            include_checkpoint_intent=include_checkpoint_intent,
            checkpoint_reason=checkpoint_reason,
            checkpoint_waiting_reason=checkpoint_waiting_reason,
            resume_file=resume_file,
            project_root=project_root,
        )
        payload = _normalize_return_skeleton_output(raw_payload)
        _emit_return_skeleton(payload, output_format=normalized_format)
    except ValueError as exc:
        _error(str(exc))
    except GPDError as exc:
        _error(str(exc))


@return_app.command("classify")
def return_classify_cmd(
    input_path: str = typer.Argument(..., help="Path to a file containing a gpd_return YAML block, or '-' for stdin"),
    require_status: str = typer.Option(
        "any",
        "--require-status",
        help=f"Require a return status: {_return_status_help_list(include_any=True)}.",
    ),
) -> None:
    """Classify one child-return envelope without repairing or mutating it."""

    try:
        normalized_required_status = _normalize_return_classify_required_status(require_status)
    except GPDError as exc:
        _error(str(exc))

    launch_cwd = _get_cwd()
    project_root = _read_only_project_scoped_cwd(launch_cwd)
    if input_path == "-":
        content = sys.stdin.read()
    else:
        resolved = _resolve_return_file_path(input_path, launch_cwd=launch_cwd, project_root=project_root)
        _, content = _load_text_document_or_error(str(resolved))

    try:
        payload = _classify_return_markdown(
            content,
            require_status=normalized_required_status,
        )
    except (GPDError, ValueError) as exc:
        _error(str(exc))

    _output(payload)
    if not _return_classification_passed(payload):
        raise typer.Exit(code=1)


@return_app.command("profiles")
def return_profiles_cmd(
    role: str | None = typer.Option(None, "--role", help="Limit output to one return role profile."),
    status: str | None = typer.Option(None, "--status", help="Limit status metadata to one gpd_return status."),
) -> None:
    """List read-only role/profile metadata for gpd_return skeletons."""

    try:
        payload = _return_profiles_payload(role=role, status=status)
    except (GPDError, ValueError) as exc:
        _error(str(exc))
    _output(payload)


def _proof_redteam_output_target(output_path: str | None) -> Path:
    return _artifact_writers.proof_redteam_output_target(output_path, launch_cwd=_get_cwd())


def _proof_redteam_write_not_run(error: str, *, target_path: Path, force: bool) -> dict[str, object]:
    return _artifact_writers.proof_redteam_write_not_run(error, target_path=target_path, force=force)


@proof_redteam_app.command("skeleton")
def proof_redteam_skeleton_cmd(
    claim_id: str = typer.Option(..., "--claim-id", help="Claim or theorem id under proof-redteam review."),
    claim_text: str | None = typer.Option(None, "--claim-text", help="Exact claim text to seed the skeleton."),
    status: str = typer.Option(
        "gaps_found",
        "--status",
        help="Target proof-redteam status for the skeleton: gaps_found or human_needed.",
    ),
    proof_artifact_paths: list[str] | None = typer.Option(
        None,
        "--proof-artifact-path",
        "--proof-artifact",
        help="Proof artifact path to bind in frontmatter. Repeatable.",
    ),
    write: bool = typer.Option(
        False, "--write", help="Write the rendered PROOF-REDTEAM artifact instead of only printing it."
    ),
    output_path: str | None = typer.Option(None, "--output", help="Target PROOF-REDTEAM.md path for --write."),
    force: bool = typer.Option(False, "--force", help="Allow --write to replace an existing target."),
) -> None:
    """Build a conservative proof-redteam artifact skeleton."""

    try:
        normalized_claim_id = _normalize_proof_redteam_claim_id(claim_id)
        normalized_claim_text = _normalize_optional_proof_redteam_claim_text(claim_text)
        normalized_status = _normalize_proof_redteam_skeleton_status(status)
        normalized_proof_artifact_paths = _normalize_proof_redteam_proof_artifact_paths(proof_artifact_paths)
    except GPDError as exc:
        _error(str(exc))

    if output_path is not None and not write:
        _error("proof-redteam skeleton --output requires --write")

    from gpd.core.proof_redteam import build_proof_redteam_skeleton

    try:
        raw_payload = _call_proof_redteam_skeleton_builder(
            build_proof_redteam_skeleton,
            claim_id=normalized_claim_id,
            claim_text=normalized_claim_text,
            status=normalized_status,
            proof_artifact_paths=normalized_proof_artifact_paths,
        )
        payload = _normalize_proof_redteam_skeleton_output(
            raw_payload,
            claim_id=normalized_claim_id,
            claim_text=normalized_claim_text,
            target_status=normalized_status,
        )
    except ValueError as exc:
        _error(str(exc))
    except GPDError as exc:
        _error(str(exc))

    if not write:
        try:
            _emit_proof_redteam_skeleton(payload)
        except GPDError as exc:
            _error(str(exc))
        return

    try:
        target_path = _proof_redteam_output_target(output_path)
    except GPDError as exc:
        _error(str(exc))
    target_ref = _artifact_target_ref(target_path)
    validation_commands = _proof_redteam_validation_commands_for_ref(target_ref)
    markdown_draft = payload["markdown_draft"]
    assert isinstance(markdown_draft, str)
    target_exists = target_path.exists()
    blocker = _artifact_write_blocker(target_path, force=force, target_exists=target_exists)
    if blocker is not None:
        _emit_raw_json_and_exit(
            _proof_redteam_write_not_run(
                blocker,
                target_path=target_path,
                force=force,
            )
        )

    write_error = _atomic_write_artifact_error(target_path, markdown_draft.rstrip() + "\n")
    if write_error is not None:
        _emit_raw_json_and_exit(
            _proof_redteam_write_not_run(
                write_error,
                target_path=target_path,
                force=force,
            )
        )
    _emit_raw_json(
        {
            "written": True,
            "target_path": str(target_path),
            "target_ref": target_ref,
            "replaced": target_exists,
            "force": force,
            "validation_commands": validation_commands,
        }
    )


@proof_redteam_app.command("finalize")
def proof_redteam_finalize_cmd(
    input_path: str = typer.Argument(..., help="Path to the PROOF-REDTEAM.md draft to finalize."),
    claim_id: str = typer.Option(..., "--claim-id", help="Claim or theorem id under proof-redteam review."),
    claim_text: str = typer.Option(..., "--claim-text", help="Exact claim statement to hash and bind."),
    proof_artifact_path: str = typer.Option(
        ...,
        "--proof-artifact-path",
        "--proof-artifact",
        help="Proof artifact path to hash and bind.",
    ),
    reviewed_at: str | None = typer.Option(None, "--reviewed-at", help="Reviewer timestamp to record."),
    output_path: str | None = typer.Option(
        None,
        "--output",
        help="Target PROOF-REDTEAM.md path. Defaults to finalizing the input path in place.",
    ),
    force: bool = typer.Option(False, "--force", help="Allow --output to replace an existing separate target."),
) -> None:
    """Finalize a passed proof-redteam artifact through the core finalizer."""

    try:
        normalized_claim_id = _normalize_proof_redteam_claim_id(claim_id)
        normalized_claim_text = _normalize_required_proof_redteam_claim_text(claim_text)
        normalized_proof_artifact_path = _normalize_single_proof_redteam_artifact_path(proof_artifact_path)
        normalized_reviewed_at = _normalize_proof_redteam_reviewed_at(reviewed_at)
    except GPDError as exc:
        _error(str(exc))

    file_path, _ = _load_text_document_or_error(input_path)
    project_root = resolve_project_root(file_path.parent, require_layout=True) or _require_project_root(
        _get_cwd(),
        command_label="gpd proof-redteam finalize",
    )

    try:
        target_path = _proof_redteam_finalize_output_target(file_path, output_path)
    except GPDError as exc:
        _error(str(exc))
    target_ref = _artifact_target_ref(target_path)
    validation_commands = _proof_redteam_finalize_validation_commands_for_ref(target_ref)
    input_resolved = file_path.resolve(strict=False)
    target_is_input = target_path == input_resolved
    target_exists = target_path.exists()

    resolved_proof_artifact_path = _resolve_proof_redteam_proof_artifact_path(
        normalized_proof_artifact_path,
        project_root=project_root,
        artifact_dir=target_path.parent,
    )
    if resolved_proof_artifact_path is None:
        _error(
            "proof-redteam finalize --proof-artifact-path does not resolve to a readable file: "
            f"{normalized_proof_artifact_path}"
        )

    blocker = _artifact_write_blocker(
        target_path,
        force=force,
        target_exists=target_exists,
        existing_requires_force=not target_is_input,
    )
    if blocker is not None:
        _emit_raw_json_and_exit(
            _proof_redteam_finalize_not_run(
                blocker,
                input_path=file_path,
                target_path=target_path,
                force=force,
            )
        )

    from gpd.core.proof_redteam import finalize_proof_redteam_artifact

    try:
        raw_payload = _call_proof_redteam_finalizer(
            finalize_proof_redteam_artifact,
            path=file_path,
            project_root=project_root,
            claim_id=normalized_claim_id,
            claim_text=normalized_claim_text,
            proof_artifact_path=normalized_proof_artifact_path,
            reviewed_at=normalized_reviewed_at,
            output_path=target_path,
        )
        payload = _mapping_payload(raw_payload, label="proof-redteam finalizer")
    except (ValueError, PydanticValidationError) as exc:
        _error(str(exc))
    except GPDError as exc:
        _error(str(exc))

    payload.setdefault("input_path", str(file_path))
    payload["target_path"] = str(target_path)
    payload["target_ref"] = target_ref
    payload["validation_commands"] = validation_commands
    payload["force"] = force
    payload.setdefault("proof_artifact_path", normalized_proof_artifact_path)
    payload.setdefault("proof_artifact_resolved_path", str(resolved_proof_artifact_path))

    if not _validation_result_is_valid(payload):
        payload["written"] = False
        payload.setdefault("replaced", False)
        _emit_raw_json_and_exit(payload)

    markdown = _proof_redteam_finalized_markdown(payload)
    if markdown is not None:
        write_error = _atomic_write_artifact_error(target_path, markdown)
        if write_error is not None:
            failure = _proof_redteam_finalize_not_run(
                write_error,
                input_path=file_path,
                target_path=target_path,
                force=force,
            )
            failure.update({key: value for key, value in payload.items() if key not in failure})
            _emit_raw_json_and_exit(failure)
        payload["written"] = True
        payload["replaced"] = target_exists
    else:
        payload["written"] = bool(payload.get("written", target_path.exists()))
        payload["replaced"] = bool(payload.get("replaced", target_exists and not target_is_input))

    _emit_raw_json(payload)


@verification_report_app.command("skeleton")
def verification_report_skeleton_cmd(
    input_path: str = typer.Argument(..., help="Path to a contract-backed PLAN.md file"),
    status: str = typer.Option(
        "gaps_found",
        "--status",
        help="Target VERIFICATION status for the skeleton; only gaps_found is supported.",
    ),
    output_format: str = typer.Option(
        "markdown",
        "--format",
        help="Output mode for non-raw use: markdown, frontmatter, or json.",
    ),
    write: bool = typer.Option(
        False, "--write", help="Write the rendered VERIFICATION report instead of only printing it."
    ),
    output_path: str | None = typer.Option(None, "--output", help="Target VERIFICATION.md path for --write."),
    force: bool = typer.Option(False, "--force", help="Allow --write to replace an existing target."),
    body_file: str | None = typer.Option(
        None, "--body-file", help="Markdown body file to compose below generated frontmatter."
    ),
    verified: str | None = typer.Option(
        None, "--verified", help="Override verified timestamp; use 'now' for current UTC."
    ),
    score: str | None = typer.Option(None, "--score", help="Override the generated score string."),
    validate_mode: str | None = typer.Option(
        None,
        "--validate",
        help="Validation mode for --write: none, frontmatter, or contract. Defaults to contract with --body-file, otherwise frontmatter.",
    ),
) -> None:
    """Build a typed VERIFICATION frontmatter skeleton, optionally writing a validated report."""

    from gpd.core.frontmatter import (
        FrontmatterParseError,
        FrontmatterValidationError,
        parse_contract_block,
        validate_frontmatter,
    )

    try:
        normalized_status = _normalize_verification_report_skeleton_status(status)
        normalized_format = _normalize_verification_report_skeleton_format(output_format)
        normalized_verified = _normalize_verification_report_verified(verified)
        normalized_score = _normalize_verification_report_score(score)
        normalized_validate_mode = _normalize_verification_report_validate_mode(
            validate_mode,
            has_body_file=body_file is not None,
        )
    except GPDError as exc:
        _error(str(exc))
    file_path, content = _load_text_document_or_error(input_path)
    body_path: Path | None = None
    body_markdown: str | None = None
    if body_file is not None:
        body_path, body_markdown = _load_text_document_or_error(body_file)
        if _body_markdown_starts_with_frontmatter(body_markdown):
            _error(
                "verification-report skeleton --body-file must be body-only Markdown; "
                f"remove YAML frontmatter from {_format_display_path(body_path)}"
            )
    try:
        plan_validation = validate_frontmatter(content, "plan", source_path=file_path)
        if not plan_validation.valid:
            diagnostics = [*plan_validation.missing, *plan_validation.errors]
            detail = "; ".join(diagnostics[:3]) if diagnostics else "invalid plan frontmatter"
            _error(f"verification-report skeleton requires a valid PLAN.md: {detail}")
        contract = parse_contract_block(content, source_path=file_path)
    except (FrontmatterParseError, FrontmatterValidationError) as exc:
        _error(str(exc))
    if contract is None:
        _error("PLAN frontmatter does not contain a contract block")

    plan_contract_ref = _verification_report_plan_contract_ref(file_path)
    from gpd.core.verification_report import build_verification_report_skeleton

    try:
        raw_payload = _call_verification_report_skeleton_builder(
            build_verification_report_skeleton,
            contract=contract,
            plan_path=file_path,
            plan_contract_ref=plan_contract_ref,
            status=normalized_status,
            verified=normalized_verified,
            score=normalized_score,
        )
    except ValueError as exc:
        _error(str(exc))
    try:
        payload = _normalize_verification_report_skeleton_output(
            raw_payload,
            plan_path=file_path,
            plan_contract_ref=plan_contract_ref,
            target_status=normalized_status,
        )
    except GPDError as exc:
        _error(str(exc))

    if (
        write
        or output_path is not None
        or body_markdown is not None
        or normalized_verified is not None
        or normalized_score is not None
    ):
        target_path = _verification_report_output_target(output_path, payload=payload, plan_path=file_path)
        target_ref = _artifact_target_ref(target_path)
        validation_commands = _verification_report_validation_commands_for_ref(target_ref)
        try:
            candidate, rendered_payload = _render_verification_report_candidate(
                payload,
                target_report_ref=target_ref,
                body_markdown=body_markdown,
                verified=normalized_verified,
                score=normalized_score,
            )
        except GPDError as exc:
            _error(str(exc))

        rendered_payload["target_report_path"] = str(target_path)
        rendered_payload["target_report_ref"] = target_ref
        rendered_payload["validation_commands"] = validation_commands
        if not write:
            _emit_verification_report_skeleton(rendered_payload, output_format=normalized_format)
            return

        warnings = _verification_report_warning_list(rendered_payload, validate_mode=normalized_validate_mode)
        target_exists = target_path.exists()
        write_payload = _verification_report_write_payload(
            target_path=target_path,
            target_ref=target_ref,
            force=force,
            body_path=body_path,
            warnings=warnings,
            validation_commands=validation_commands,
        )
        blocker = _artifact_write_blocker(target_path, force=force, target_exists=target_exists)
        if blocker is not None:
            _emit_verification_report_not_run(write_payload, mode=normalized_validate_mode, error=blocker)

        validation = _validate_verification_report_candidate(
            candidate,
            source_path=target_path,
            mode=normalized_validate_mode,
        )
        write_payload["validation"] = validation
        if not validation.get("valid"):
            if normalized_validate_mode == "contract":
                write_payload["recovery"] = _verification_report_write_recovery(
                    plan_path=file_path,
                    target_path=target_path,
                    body_path=body_path,
                    validate_mode=normalized_validate_mode,
                    force=force,
                    status=normalized_status,
                    verified=normalized_verified,
                    score=normalized_score,
                )
            _emit_raw_json_and_exit(write_payload)

        write_error = _atomic_write_artifact_error(target_path, candidate)
        if write_error is not None:
            _emit_verification_report_not_run(
                write_payload,
                mode=normalized_validate_mode,
                error=write_error,
            )
        write_payload["written"] = True
        write_payload["replaced"] = target_exists
        _emit_raw_json(write_payload)
        return

    _emit_verification_report_skeleton(payload, output_format=normalized_format)


@verification_report_app.command("finalize")
def verification_report_finalize_cmd(
    input_path: str = typer.Argument(..., help="Path to a contract-backed PLAN.md file."),
    patch_path: str = typer.Option(..., "--patch", help="Typed outcome patch JSON file."),
    body_file: str = typer.Option(..., "--body-file", help="Body-only Markdown evidence file."),
    output_path: str = typer.Option(..., "--output", help="Target VERIFICATION.md path."),
    validate_mode: str | None = typer.Option(
        "contract",
        "--validate",
        help="Validation mode before write. Phase 4 finalization requires contract.",
    ),
    force: bool = typer.Option(False, "--force", help="Allow replacing an existing target."),
) -> None:
    """Finalize a VERIFICATION report from a typed outcome patch and body evidence."""

    from gpd.core.frontmatter import (
        FrontmatterParseError,
        FrontmatterValidationError,
        parse_contract_block,
        validate_frontmatter,
    )

    try:
        normalized_validate_mode = _normalize_verification_report_finalize_validate_mode(validate_mode)
    except GPDError as exc:
        _error(str(exc))

    file_path, content = _load_text_document_or_error(input_path)
    body_path, body_markdown = _load_text_document_or_error(body_file)
    if _body_markdown_starts_with_frontmatter(body_markdown):
        _error(
            "verification-report finalize --body-file must be body-only Markdown; "
            f"remove YAML frontmatter from {_format_display_path(body_path)}"
        )
    patch_document = _load_json_document_or_error(patch_path)
    if not isinstance(patch_document, Mapping):
        _error("verification-report finalize --patch must contain a JSON object")
    patch_file_path = _resolve_path_from_effective_cwd(patch_path) if patch_path != "-" else Path("-")

    try:
        plan_validation = validate_frontmatter(content, "plan", source_path=file_path)
        if not plan_validation.valid:
            diagnostics = [*plan_validation.missing, *plan_validation.errors]
            detail = "; ".join(diagnostics[:3]) if diagnostics else "invalid plan frontmatter"
            _error(f"verification-report finalize requires a valid PLAN.md: {detail}")
        contract = parse_contract_block(content, source_path=file_path)
    except (FrontmatterParseError, FrontmatterValidationError) as exc:
        _error(str(exc))
    if contract is None:
        _error("PLAN frontmatter does not contain a contract block")

    target_path = _verification_report_output_target(output_path, payload={}, plan_path=file_path)
    target_ref = _artifact_target_ref(target_path)
    validation_commands = _verification_report_validation_commands_for_ref(target_ref)
    warnings: list[str] = []
    target_exists = target_path.exists()
    write_payload = _verification_report_write_payload(
        target_path=target_path,
        target_ref=target_ref,
        force=force,
        body_path=body_path,
        warnings=warnings,
        validation_commands=validation_commands,
        patch_file_path=patch_file_path,
    )
    blocker = _artifact_write_blocker(target_path, force=force, target_exists=target_exists)
    if blocker is not None:
        _emit_verification_report_not_run(write_payload, mode=normalized_validate_mode, error=blocker)

    plan_contract_ref = _verification_report_plan_contract_ref(file_path)
    from gpd.core.verification_report import finalize_verification_report

    try:
        raw_payload = _call_verification_report_finalizer(
            finalize_verification_report,
            contract=contract,
            outcome_patch=patch_document,
            body_markdown=body_markdown,
            plan_path=file_path,
            plan_contract_ref=plan_contract_ref,
            target_report_ref=target_ref,
            source_path=target_path,
            validation_mode=normalized_validate_mode,
        )
        payload = _mapping_payload(raw_payload, label="verification-report finalizer")
        candidate = _verification_report_finalized_markdown(payload)
    except (ValueError, PydanticValidationError) as exc:
        _error(str(exc))
    except GPDError as exc:
        _error(str(exc))

    core_validation = _jsonable_value(payload.get("validation"))
    validation = _validate_verification_report_candidate(
        candidate,
        source_path=target_path,
        mode=normalized_validate_mode,
    )
    if isinstance(core_validation, Mapping) and not _validation_result_is_valid(core_validation):
        validation = dict(core_validation)
    write_payload["validation"] = validation
    raw_warnings = payload.get("warnings")
    if isinstance(raw_warnings, list):
        warnings.extend(str(item) for item in raw_warnings if str(item).strip())
    write_payload["warnings"] = warnings
    for key in ("frontmatter_yaml", "target_status", "status", "plan_contract_ref"):
        if key in payload:
            write_payload[key] = payload[key]

    if not validation.get("valid"):
        write_payload["recovery"] = _verification_report_finalize_recovery(
            plan_path=file_path,
            patch_path=patch_file_path,
            target_path=target_path,
            body_path=body_path,
            validate_mode=normalized_validate_mode,
            force=force,
        )
        _emit_raw_json_and_exit(write_payload)

    write_error = _atomic_write_artifact_error(target_path, candidate)
    if write_error is not None:
        _emit_verification_report_not_run(
            write_payload,
            mode=normalized_validate_mode,
            error=write_error,
        )
    write_payload["written"] = True
    write_payload["replaced"] = target_exists
    _emit_raw_json(write_payload)


@validate_app.command("arxiv-package", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def validate_arxiv_package_cmd(
    ctx: typer.Context,
    subject: str | None = typer.Argument(
        None,
        help="Optional manuscript root or .tex entrypoint to pass through arxiv-submission preflight",
    ),
    submission_dir: str | None = typer.Option(
        None,
        "--submission-dir",
        help="Prepared arXiv submission tree to validate; defaults to the managed package root submission directory",
    ),
    tarball: str | None = typer.Option(
        None,
        "--tarball",
        help="arxiv-submission.tar.gz path to validate; defaults to the managed package root tarball",
    ),
    materialize: bool = typer.Option(
        False,
        "--materialize",
        help="Create arxiv-submission.tar.gz from the validated submission tree before tarball checks",
    ),
) -> None:
    """Validate a managed arXiv submission tree/tarball after strict review preflight."""

    from gpd.core.arxiv_package import validate_arxiv_package

    arguments: list[str] = []
    if subject is not None:
        arguments.append(subject)
    arguments.extend(str(arg) for arg in ctx.args)
    subject_text = " ".join(arguments) or None

    review_preflight = _build_review_preflight("arxiv-submission", subject=subject_text, strict=True)
    if not review_preflight.passed:
        _output(
            {
                "passed": False,
                "preflight_passed": False,
                "checks": [
                    {
                        "name": "strict_review_preflight",
                        "passed": False,
                        "blocking": True,
                        "detail": "strict arxiv-submission review preflight failed",
                    }
                ],
                "review_preflight": dataclasses.asdict(review_preflight),
            }
        )
        raise typer.Exit(code=1)

    project_root = _require_project_root(_get_cwd(), command_label="gpd validate arxiv-package")
    if review_preflight.resolved_subject is not None:
        project_root = (
            review_preflight.resolved_subject.resolved_project_root
            or review_preflight.resolved_subject.context_root
            or project_root
        )

    if not review_preflight.publication_subject_slug or not review_preflight.manuscript_entrypoint:
        _output(
            {
                "passed": False,
                "preflight_passed": True,
                "checks": [
                    {
                        "name": "strict_review_preflight_routing",
                        "passed": False,
                        "blocking": True,
                        "detail": "strict preflight did not emit publication_subject_slug and manuscript_entrypoint",
                    }
                ],
                "review_preflight": dataclasses.asdict(review_preflight),
            }
        )
        raise typer.Exit(code=1)

    result = validate_arxiv_package(
        project_root=project_root,
        subject_slug=review_preflight.publication_subject_slug,
        manuscript_entrypoint=review_preflight.manuscript_entrypoint,
        submission_dir=submission_dir,
        tarball=tarball,
        materialize=materialize,
    )
    payload = dataclasses.asdict(result)
    payload["preflight_passed"] = True
    payload["review_preflight"] = {
        "command": review_preflight.command,
        "strict": review_preflight.strict,
        "publication_subject_slug": review_preflight.publication_subject_slug,
        "managed_publication_root": review_preflight.managed_publication_root,
        "selected_publication_root": review_preflight.selected_publication_root,
        "selected_review_root": review_preflight.selected_review_root,
        "manuscript_root": review_preflight.manuscript_root,
        "manuscript_entrypoint": review_preflight.manuscript_entrypoint,
    }
    _output(payload)
    if not result.passed:
        raise typer.Exit(code=1)


@validate_app.command(
    "lifecycle-contract-gate", context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def validate_lifecycle_contract_gate(
    ctx: typer.Context,
    command_name: str = typer.Argument(..., help="Lifecycle command being gated"),
    subject: str | None = typer.Argument(None, help="Optional phase or lifecycle subject"),
) -> None:
    """Fail closed unless the current project contract gate is authoritative."""
    from gpd.core.state import project_contract_authority_status

    command = command_name.removeprefix("gpd:").strip()
    if command not in {"plan-phase", "execute-phase", "verify-work"}:
        _error(
            f"lifecycle-contract-gate only supports plan-phase, execute-phase, and verify-work (got {command_name!r})"
        )
    arguments: list[str] = []
    if subject is not None:
        arguments.append(subject)
    arguments.extend(str(arg) for arg in ctx.args)

    project_root = _require_project_root(_get_cwd(), command_label="gpd validate lifecycle-contract-gate")
    payload = {
        "command": command,
        "subject": " ".join(arguments) or None,
        **project_contract_authority_status(project_root),
    }
    _output(payload)
    if payload.get("passed") is not True:
        raise typer.Exit(code=1)


@validate_app.command("artifact-text")
def validate_artifact_text_cmd(
    input_path: str = typer.Argument(..., help="Path to an artifact that should expose a readable text surface"),
    output_path: str | None = typer.Option(
        None,
        "--output",
        help="Optional path for the materialized UTF-8 text surface",
    ),
) -> None:
    """Validate or materialize a readable text surface for one external artifact."""

    source_path = Path(input_path)
    if not source_path.is_absolute():
        source_path = _get_cwd() / source_path
    source_path = source_path.resolve(strict=False)
    if not source_path.exists():
        _error(f"Artifact input not found: {_format_display_path(source_path)}")
    if not source_path.is_file():
        _error(f"Artifact input must be a file: {_format_display_path(source_path)}")

    try:
        probe = probe_artifact_text_surface(source_path)
    except ArtifactTextError as exc:
        _error(str(exc))
    if not probe.ready:
        _error(probe.detail)

    if output_path is None:
        _output(
            {
                "input_path": str(source_path),
                "ready": probe.ready,
                "detail": _peer_review_artifact_text_surface_ready(source_path, probe=probe)[1],
                "surface_kind": probe.surface_kind,
            }
        )
        return

    materialized_output = Path(output_path)
    if not materialized_output.is_absolute():
        materialized_output = _get_cwd() / materialized_output
    materialized_output = materialized_output.resolve(strict=False)
    if materialized_output == source_path:
        _error("--output must differ from the source artifact path")

    try:
        result = materialize_artifact_text_surface(source_path, materialized_output)
    except ArtifactTextError as exc:
        _error(str(exc))

    _output(
        {
            "input_path": str(result.source_path),
            "output_path": str(result.output_path),
            "detail": _peer_review_artifact_text_surface_ready(source_path, probe=probe)[1],
            "surface_kind": result.surface_kind,
            "text_length": result.text_length,
        }
    )


@validate_app.command("paper-quality")
def validate_paper_quality(
    input_path: str | None = typer.Argument(None, help="Path to a paper-quality JSON file, or '-' for stdin"),
    from_project: str | None = typer.Option(
        None,
        "--from-project",
        help="Build the PaperQualityInput directly from project artifacts at this root",
    ),
) -> None:
    """Score a machine-readable paper-quality manifest and fail on blockers."""
    from gpd.core.paper_quality import PaperQualityInput, score_paper_quality
    from gpd.core.paper_quality_artifacts import build_paper_quality_input

    if from_project:
        project_root = _resolve_path_from_effective_cwd(from_project)
        manuscript_resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=True)
        if manuscript_resolution.status != "resolved":
            raise GPDError(
                "validate paper-quality --from-project requires exactly one resolved manuscript root; "
                f"found {manuscript_resolution.status}: {manuscript_resolution.detail}"
            )
        report = score_paper_quality(build_paper_quality_input(project_root))
    else:
        if not input_path:
            _error("Provide a PaperQualityInput path or use --from-project <root>")
        payload = _load_json_document_or_error(input_path)
        try:
            paper_quality_input = PaperQualityInput.model_validate(payload)
        except PydanticValidationError as exc:
            _raise_pydantic_schema_error(
                label="paper-quality input",
                exc=exc,
                schema_reference="templates/paper/paper-quality-input-schema.md",
            )
        report = score_paper_quality(paper_quality_input)
    _output(report)
    if not report.ready_for_submission:
        raise typer.Exit(code=1)


@validate_app.command("project-contract")
def validate_project_contract_cmd(
    input_path: str = typer.Argument(..., help="Path to a project contract JSON file, or '-' for stdin"),
    mode: str = typer.Option("approved", "--mode", help="Validation mode: approved or draft"),
) -> None:
    """Validate a project-scoping contract before downstream artifact generation, including proof-obligation observables."""
    from gpd.contracts import parse_project_contract_data_strict
    from gpd.core.contract_validation import ProjectContractValidationResult, validate_project_contract

    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"draft", "approved"}:
        raise GPDError(f"Invalid --mode {mode!r}. Expected 'draft' or 'approved'.")

    payload = _load_json_document_or_error(input_path)
    if input_path == "-":
        workspace_cwd = _state_command_cwd()
        stdin_inside_project = (workspace_cwd / "GPD").is_dir()
        anchored_project_root = workspace_cwd if stdin_inside_project else None
        prefer_filesystem_anchor = False
    else:
        anchored_project_root = _enclosing_project_root_for_json_input(input_path)
        stdin_inside_project = False
        prefer_filesystem_anchor = anchored_project_root is not None
    strict_result = parse_project_contract_data_strict(payload)
    if strict_result.contract is None or strict_result.errors:
        result = ProjectContractValidationResult(
            valid=False,
            errors=list(strict_result.errors) or ["project contract could not be normalized"],
            warnings=[],
            mode=normalized_mode,
        )
    else:
        if prefer_filesystem_anchor and anchored_project_root is not None:
            result = validate_project_contract(
                strict_result.contract,
                mode=normalized_mode,
                project_root=anchored_project_root,
            )
        elif stdin_inside_project:
            unanchored_result = validate_project_contract(
                strict_result.contract, mode=normalized_mode, project_root=None
            )
            anchored_result = validate_project_contract(
                strict_result.contract,
                mode=normalized_mode,
                project_root=anchored_project_root,
            )
            result = (
                anchored_result
                if _prefer_anchored_project_contract_validation(anchored_result, unanchored_result)
                else unanchored_result
            )
        else:
            unanchored_result = validate_project_contract(
                strict_result.contract, mode=normalized_mode, project_root=None
            )
            if anchored_project_root is None:
                result = unanchored_result
            else:
                anchored_result = validate_project_contract(
                    strict_result.contract,
                    mode=normalized_mode,
                    project_root=anchored_project_root,
                )
                result = anchored_result if anchored_result.valid != unanchored_result.valid else unanchored_result
    if not result.valid:
        schema_reference = "templates/project-contract-schema.md"
        if _raw:
            _emit_raw_json(
                _model_dump_with_schema_reference(
                    result,
                    schema_reference=schema_reference,
                ),
                err=True,
            )
        else:
            _output(_model_dump_with_schema_reference(result, schema_reference=schema_reference))
        raise typer.Exit(code=1)
    _output(result)


@validate_app.command("plan-contract")
def validate_plan_contract_cmd(
    input_path: str = typer.Argument(..., help="Path to a PLAN.md file"),
) -> None:
    """Validate PLAN frontmatter, including the contract block and cross-links."""

    _run_frontmatter_validation(input_path, "plan")


@validate_app.command("plan-preflight")
def validate_plan_preflight_cmd(
    input_path: str = typer.Argument(..., help="Path to a PLAN.md file"),
) -> None:
    """Check optional specialized-tool requirements declared by a PLAN."""

    from gpd.core.tool_preflight import build_plan_tool_preflight

    file_path, _ = _load_text_document_or_error(input_path)
    result = build_plan_tool_preflight(file_path)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


@validate_app.command("summary-contract")
def validate_summary_contract_cmd(
    input_path: str = typer.Argument(..., help="Path to a SUMMARY.md file"),
) -> None:
    """Validate SUMMARY frontmatter and contract-result alignment."""

    _run_frontmatter_validation(input_path, "summary")


@validate_app.command("verification-contract")
def validate_verification_contract_cmd(
    input_path: str = typer.Argument(..., help="Path to a VERIFICATION.md file"),
) -> None:
    """Validate VERIFICATION frontmatter and contract-result alignment, stale proof-audit blockers when recorded, and oracle evidence."""

    from gpd.core.correctness_validators import validate_verification_oracle_evidence
    from gpd.core.frontmatter import validate_frontmatter

    file_path, content = _load_text_document_or_error(input_path)
    schema_result = validate_frontmatter(content, "verification", source_path=file_path)
    oracle_result = validate_verification_oracle_evidence(content, source_path=file_path)
    errors = [*schema_result.errors, *oracle_result.errors]
    result = {
        "valid": len(schema_result.missing) == 0 and not errors,
        "missing": schema_result.missing,
        "present": schema_result.present,
        "errors": errors,
        "schema_name": schema_result.schema_name,
        "oracle_evidence_count": oracle_result.evidence_count,
    }
    _output(result)
    if not result["valid"]:
        raise typer.Exit(code=1)


@validate_app.command("proof-redteam")
def validate_proof_redteam_cmd(
    input_path: str = typer.Argument(..., help="Path to a PROOF-REDTEAM.md artifact"),
) -> None:
    """Validate a proof-redteam artifact with the public proof audit validator."""

    file_path, _ = _load_text_document_or_error(input_path)
    project_root = resolve_project_root(file_path.parent, require_layout=True) or _require_project_root(
        _get_cwd(),
        command_label="gpd validate proof-redteam",
    )
    from gpd.core.proof_redteam import validate_proof_redteam_artifact

    result = validate_proof_redteam_artifact(file_path, project_root=project_root)
    _output(result)
    if not _validation_result_is_valid(result):
        raise typer.Exit(code=1)


@validate_app.command("comparison-contract")
def validate_comparison_contract_cmd(
    input_path: str = typer.Argument(..., help="Path to a GPD/comparisons/*-COMPARISON.md file"),
) -> None:
    """Validate standalone comparison artifact frontmatter and comparison_verdicts."""

    from gpd.core.correctness_validators import validate_comparison_contract

    file_path, content = _load_text_document_or_error(input_path)
    result = validate_comparison_contract(content, source_path=file_path)
    _output(result)
    if not result.valid:
        raise typer.Exit(code=1)


@validate_app.command("handoff-artifacts")
def validate_handoff_artifacts_cmd(
    input_path: str = typer.Argument(..., help="Path to a file containing a gpd_return YAML block, or '-' for stdin"),
    expected: list[str] | None = typer.Option(
        None,
        "--expected",
        help="Expected artifact path that must exist and be named in gpd_return.files_written. Repeatable.",
    ),
    expected_glob: list[str] | None = typer.Option(
        None,
        "--expected-glob",
        help="Glob pattern that must match at least one gpd_return.files_written entry. Repeatable.",
    ),
    allowed_root: list[str] | None = typer.Option(
        None,
        "--allowed-root",
        help="Allowed project-local artifact root. Repeatable. Defaults to the project root.",
    ),
    required_suffix: list[str] | None = typer.Option(
        None,
        "--required-suffix",
        help="Required suffix for each checked artifact path. Repeatable.",
    ),
    require_files_written: bool = typer.Option(
        False,
        "--require-files-written",
        help="Fail when gpd_return.files_written is empty.",
    ),
    require_status: str | None = typer.Option(
        None,
        "--require-status",
        help="Require a canonical gpd_return.status value, for example completed for success gates.",
    ),
    fresh_after: str | None = typer.Option(
        None,
        "--fresh-after",
        help="ISO 8601 timestamp; checked artifacts must be modified at or after this time.",
    ),
    classify: bool = typer.Option(
        False,
        "--classify",
        help="Include structured failure classes when the core handoff validator supports them.",
    ),
) -> None:
    """Validate that a spawned-agent return names real, fresh, in-scope artifacts."""
    from gpd.core.handoff_artifacts import parse_fresh_after, validate_handoff_artifacts_markdown

    launch_cwd = _get_cwd()
    project_root = _read_only_project_scoped_cwd(launch_cwd)
    if input_path == "-":
        content = sys.stdin.read()
    else:
        resolved = _resolve_return_file_path(input_path, launch_cwd=launch_cwd, project_root=project_root)
        _, content = _load_text_document_or_error(str(resolved))
    try:
        freshness_cutoff = parse_fresh_after(fresh_after)
    except ValueError as exc:
        _error(str(exc))

    kwargs: dict[str, object] = {
        "expected_artifacts": expected or [],
        "expected_globs": expected_glob or [],
        "allowed_roots": allowed_root or [],
        "required_suffixes": required_suffix or [],
        "require_files_written": require_files_written,
        "require_status": require_status,
        "fresh_after": freshness_cutoff,
    }
    if classify and _callable_accepts_kwarg(validate_handoff_artifacts_markdown, "classify"):
        kwargs["classify"] = True
    elif classify and _callable_accepts_kwarg(validate_handoff_artifacts_markdown, "include_classification"):
        kwargs["include_classification"] = True

    result = validate_handoff_artifacts_markdown(project_root, content, **kwargs)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


def _load_child_handoff_documents(
    *,
    gate_path: str,
    return_file: str,
    launch_cwd: Path,
    project_root: Path,
) -> tuple[str, str]:
    """Load child gate and return content, supporting one combined stdin stream."""

    if gate_path == "-" and return_file == "-":
        content = sys.stdin.read()
        return content, content

    if gate_path == "-":
        gate_content = sys.stdin.read()
    else:
        resolved_gate = _resolve_return_file_path(gate_path, launch_cwd=launch_cwd, project_root=project_root)
        _, gate_content = _load_text_document_or_error(str(resolved_gate))

    if return_file == "-":
        return_content = sys.stdin.read()
    else:
        resolved_return = _resolve_return_file_path(return_file, launch_cwd=launch_cwd, project_root=project_root)
        _, return_content = _load_text_document_or_error(str(resolved_return))

    return gate_content, return_content


@validate_app.command("child-handoff")
def validate_child_handoff_cmd(
    gate_path: str = typer.Option(
        ...,
        "--gate",
        help="Path to a child_gate YAML block, or '-' for stdin.",
    ),
    return_file: str = typer.Option(
        ...,
        "--return-file",
        help="Path to a file containing a gpd_return YAML block, or '-' for stdin.",
    ),
    fresh_after: str | None = typer.Option(
        None,
        "--fresh-after",
        help="ISO 8601 timestamp; checked artifacts must be modified at or after this time.",
    ),
) -> None:
    """Validate a child_gate tuple and child return without running applicators."""

    from gpd.core.child_handoff import parse_child_gate_markdown, validate_child_handoff
    from gpd.core.handoff_artifacts import parse_fresh_after

    launch_cwd = _get_cwd()
    project_root = _read_only_project_scoped_cwd(launch_cwd)
    gate_content, return_content = _load_child_handoff_documents(
        gate_path=gate_path,
        return_file=return_file,
        launch_cwd=launch_cwd,
        project_root=project_root,
    )
    try:
        gate = parse_child_gate_markdown(gate_content)
        freshness_cutoff = parse_fresh_after(fresh_after)
        result = validate_child_handoff(
            project_root,
            return_content,
            gate,
            fresh_after=freshness_cutoff,
        )
    except ValueError as exc:
        _error(str(exc))

    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


@validate_app.command("review-claim-index")
def validate_review_claim_index_cmd(
    input_path: str = typer.Argument(..., help="Path to a claim-index JSON file, or '-' for stdin"),
) -> None:
    """Validate a staged peer-review claim index."""
    from gpd.mcp.paper.models import ClaimIndex

    payload = _load_json_document_or_error(input_path)
    try:
        claim_index = ClaimIndex.model_validate(payload)
    except PydanticValidationError as exc:
        _raise_pydantic_schema_error(
            label="review-claim-index",
            exc=exc,
            schema_reference="references/publication/peer-review-panel.md",
        )
    _output(claim_index)


@validate_app.command("review-stage-report")
def validate_review_stage_report_cmd(
    input_path: str = typer.Argument(..., help="Path to a stage-review JSON file, or '-' for stdin"),
) -> None:
    """Validate a staged peer-review report."""
    from gpd.core.referee_policy import (
        validate_stage_review_artifact_file,
        validate_stage_review_artifact_payload,
    )
    from gpd.mcp.paper.models import StageReviewReport

    payload = _load_json_document_or_error(input_path)
    try:
        stage_report = StageReviewReport.model_validate(payload)
    except PydanticValidationError as exc:
        _raise_pydantic_schema_error(
            label="review-stage-report",
            exc=exc,
            schema_reference="references/publication/peer-review-panel.md",
        )
    if input_path == "-":
        artifact_path = (
            _get_cwd()
            / "GPD"
            / "review"
            / f"STAGE-{stage_report.stage_id}{'' if stage_report.round <= 1 else f'-R{stage_report.round}'}.json"
        )
        semantic_errors = validate_stage_review_artifact_payload(stage_report, artifact_path=artifact_path)
    else:
        artifact_path = Path(input_path)
        if not artifact_path.is_absolute():
            artifact_path = _get_cwd() / artifact_path
        semantic_errors = validate_stage_review_artifact_file(
            artifact_path,
            claim_index_fallback_root=_get_cwd() / "GPD" / "review",
        )
    if semantic_errors:
        message = "; ".join(semantic_errors[:5])
        if len(semantic_errors) > 5:
            message += f" (+{len(semantic_errors) - 5} more)"
        message += ". See `references/publication/peer-review-panel.md`"
        _error(message)
    _output(stage_report)


@validate_app.command("review-ledger")
def validate_review_ledger_cmd(
    input_path: str = typer.Argument(..., help="Path to a review-ledger JSON file, or '-' for stdin"),
) -> None:
    """Validate a staged peer-review issue ledger."""
    from gpd.mcp.paper.models import ReviewLedger

    payload = _load_json_document_or_error(input_path)
    try:
        ledger = ReviewLedger.model_validate(payload)
    except PydanticValidationError as exc:
        _raise_pydantic_schema_error(
            label="review-ledger",
            exc=exc,
            schema_reference="templates/paper/review-ledger-schema.md",
        )
    _output(ledger)


@validate_app.command("referee-decision")
def validate_referee_decision(
    input_path: str = typer.Argument(..., help="Path to a referee-decision JSON file, or '-' for stdin"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Require staged peer-review artifact coverage, recommendation-floor consistency, and explicit policy-driving inputs for all journals",
    ),
    ledger_path: str | None = typer.Option(
        None,
        "--ledger",
        help="Optional path to the matching review-ledger JSON for cross-artifact consistency checks",
    ),
) -> None:
    """Validate a staged peer-review decision against hard recommendation gates."""
    from gpd.core.referee_policy import RefereeDecisionInput, evaluate_referee_decision
    from gpd.mcp.paper.models import ReviewLedger

    if input_path == "-" and ledger_path == "-":
        _error("Cannot read both referee-decision and review-ledger from stdin in the same command.")
    if strict and ledger_path is None:
        _error("Strict referee-decision validation requires --ledger with the matching review-ledger JSON.")

    payload = _load_json_document_or_error(input_path)
    try:
        decision = RefereeDecisionInput.model_validate(payload)
    except PydanticValidationError as exc:
        _raise_pydantic_schema_error(
            label="referee-decision",
            exc=exc,
            schema_reference="templates/paper/referee-decision-schema.md",
        )

    review_ledger = None
    if ledger_path is not None:
        ledger_payload = _load_json_document_or_error(ledger_path)
        try:
            review_ledger = ReviewLedger.model_validate(ledger_payload)
        except PydanticValidationError as exc:
            _raise_pydantic_schema_error(
                label="review-ledger",
                exc=exc,
                schema_reference="templates/paper/review-ledger-schema.md",
            )

    report = evaluate_referee_decision(
        decision,
        strict=strict,
        require_explicit_inputs=strict,
        review_ledger=review_ledger,
        project_root=_project_root_for_json_input(input_path),
    )
    _output(report)
    if not report.valid:
        raise typer.Exit(code=1)


@validate_app.command("reproducibility-manifest")
def validate_reproducibility_manifest_cmd(
    input_path: str = typer.Argument(..., help="Path to a reproducibility-manifest JSON file, or '-' for stdin"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Require review-ready coverage in addition to structural validity",
    ),
    kernel_verdict: bool = typer.Option(
        False,
        "--kernel-verdict",
        help="Also emit a content-addressed kernel verdict for structurally valid manifests.",
    ),
    check_paths: bool = typer.Option(
        False,
        "--check-paths/--no-check-paths",
        help="Verify that referenced dataset, script, and output paths exist under the project root.",
    ),
) -> None:
    """Validate a machine-readable reproducibility manifest."""
    from gpd.core.kernel import print_verdict
    from gpd.core.reproducibility import (
        ReproducibilityManifest,
        build_reproducibility_kernel_verdict,
        validate_reproducibility_manifest,
    )

    payload = _load_json_document_or_error(input_path)
    project_root_for_check = _manifest_reference_root_for_path_checks(input_path) if check_paths else None
    result = validate_reproducibility_manifest(payload, project_root=project_root_for_check)
    result_payload = result.model_dump(mode="json")
    result_payload["reproducibility_ready"] = result_payload.pop("ready_for_review")
    failure = not result.valid or (strict and not result.ready_for_review)
    if not kernel_verdict:
        if _raw and failure:
            failure_payload = dict(result_payload)
            failure_payload["schema_reference"] = "templates/paper/reproducibility-manifest.md"
            _emit_raw_json(failure_payload, err=True)
        else:
            _output(result_payload if _raw else result)
    else:
        manifest_obj: ReproducibilityManifest | None = None
        if isinstance(payload, dict):
            try:
                manifest_obj = ReproducibilityManifest.model_validate(payload)
            except PydanticValidationError:
                manifest_obj = None

        verdict = (
            build_reproducibility_kernel_verdict(manifest_obj, validation=result) if manifest_obj is not None else None
        )

        if _raw:
            if failure:
                validation_payload = dict(result_payload)
                validation_payload["schema_reference"] = "templates/paper/reproducibility-manifest.md"
                _emit_raw_json(
                    {
                        "validation": validation_payload,
                        "kernel_verdict": verdict,
                    },
                    err=True,
                )
            else:
                _output(
                    {
                        "validation": result_payload,
                        "kernel_verdict": verdict,
                    }
                )
        else:
            _output(result)
            if verdict is not None:
                console.print()
                print_verdict(verdict, domain="Reproducibility")
    if failure:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# history-digest — History analysis
# ═══════════════════════════════════════════════════════════════════════════


@app.command("history-digest")
def history_digest() -> None:
    """Build a digest of project history from phase SUMMARY files."""
    from gpd.core.commands import cmd_history_digest

    _output(cmd_history_digest(_project_scoped_cwd()))


@app.command("sync-phase-checkpoints")
def sync_phase_checkpoints() -> None:
    """Generate checkpoint notes under GPD/ from phase summaries."""
    from gpd.core.checkpoints import sync_phase_checkpoints

    _output(sync_phase_checkpoints(_project_scoped_cwd()))


# ═══════════════════════════════════════════════════════════════════════════
# summary-extract — Summary extraction
# ═══════════════════════════════════════════════════════════════════════════


@app.command("summary-extract")
def summary_extract(
    summary_path: str = typer.Argument(..., help="Path to SUMMARY.md file (relative to cwd)"),
    field: list[str] | None = typer.Option(None, "--field", help="Specific fields to extract"),
) -> None:
    """Extract structured data from a SUMMARY.md file."""
    from gpd.core.commands import cmd_summary_extract

    _output(cmd_summary_extract(_get_cwd(), summary_path, fields=field))


# ═══════════════════════════════════════════════════════════════════════════
# regression-check — Cross-phase regression detection
# ═══════════════════════════════════════════════════════════════════════════


@app.command("regression-check")
def regression_check(
    phase: str | None = typer.Argument(None, help="Optional phase number to limit scope"),
    quick: bool = typer.Option(False, "--quick", help="Only check most recent 2 completed phases"),
) -> None:
    """Check for regressions across completed phases, optionally limited to one phase."""
    from gpd.core.commands import cmd_regression_check

    result = cmd_regression_check(_project_scoped_cwd(), phase=phase, quick=quick)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# validate-return — gpd_return envelope validation
# ═══════════════════════════════════════════════════════════════════════════


@app.command("validate-return")
def validate_return(
    file_path: str = typer.Argument(..., help="Path to file containing gpd_return YAML block"),
) -> None:
    """Validate a gpd_return YAML block in a file."""
    from gpd.core.commands import cmd_validate_return

    launch_cwd = _get_cwd()
    project_root = _read_only_project_scoped_cwd(launch_cwd)
    resolved = _resolve_return_file_path(file_path, launch_cwd=launch_cwd, project_root=project_root)
    result = cmd_validate_return(resolved)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("apply-return-updates")
def apply_return_updates(
    file_path: str = typer.Argument(..., help="Path to file containing gpd_return YAML block"),
    checkpoint_resume_file: str | None = typer.Option(
        None,
        "--checkpoint-resume-file",
        help="Parent-owned project-relative resume file for checkpoint-intent application.",
    ),
) -> None:
    """Validate one gpd_return envelope and apply its durable child-return updates."""
    from gpd.core.commands import cmd_apply_return_updates

    launch_cwd = _get_cwd()
    project_root = _project_scoped_cwd(launch_cwd)
    resolved = _resolve_return_file_path(file_path, launch_cwd=launch_cwd, project_root=project_root)
    kwargs: dict[str, object] = {}
    if checkpoint_resume_file is not None:
        if not _callable_accepts_kwarg(cmd_apply_return_updates, "checkpoint_resume_file"):
            _error("--checkpoint-resume-file requires core cmd_apply_return_updates checkpoint_resume_file support")
        kwargs["checkpoint_resume_file"] = checkpoint_resume_file
    result = cmd_apply_return_updates(project_root, resolved, **kwargs)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# paper-build — Canonical paper package entry point
# ═══════════════════════════════════════════════════════════════════════════


@app.command("paper-build")
def paper_build(
    config_path: str | None = typer.Argument(
        None,
        help="Path to a PaperConfig JSON file. Defaults to paper/, manuscript/, or draft/ candidates.",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Directory for emitted manuscript artifacts. Defaults to the config directory.",
    ),
    bibliography: str | None = typer.Option(
        None,
        "--bibliography",
        help="Optional .bib file to ingest before building the manuscript.",
    ),
    citation_sources: str | None = typer.Option(
        None,
        "--citation-sources",
        help="Optional JSON file containing a CitationSource array for bibliography generation/audit.",
    ),
    enrich_bibliography: bool = typer.Option(
        True,
        "--enrich-bibliography/--no-enrich-bibliography",
        help="Allow bibliography enrichment when citation sources are provided.",
    ),
    minimal: bool = typer.Option(
        False,
        "--minimal",
        help=(
            "Suppress all sidecars (ARTIFACT-MANIFEST.json, BIBLIOGRAPHY-AUDIT.json). "
            "Only .tex, .bib, and figures/ land in the output directory."
        ),
    ),
) -> None:
    """Build a paper from the canonical mcp.paper JSON config surface."""

    from gpd.core.storage_paths import DurableOutputKind, ProjectStorageLayout
    from gpd.mcp.paper.compiler import build_paper
    from gpd.mcp.paper.models import derive_output_filename

    cwd = _get_cwd()
    project_root = _project_scoped_cwd(cwd)
    config_file = (
        _resolve_existing_input_path(config_path, candidates=(), label="paper config")
        if config_path
        else _resolve_default_paper_config_path(project_root=project_root)
    )
    _reject_internal_paper_config_location(config_file, project_root=project_root)
    raw_config = _load_json_document(str(config_file))
    if not isinstance(raw_config, dict):
        raise GPDError(f"Paper config must be a JSON object: {_format_display_path(config_file)}")

    paper_config = _resolve_paper_config_paths(raw_config, base_dir=config_file.parent)
    output_path = Path(output_dir) if output_dir else _default_paper_output_dir(config_file)
    if not output_path.is_absolute():
        output_path = cwd / output_path
    output_path = output_path.resolve(strict=False)
    resolved_config_root = config_file.resolve(strict=False)
    storage_root = project_root if resolved_config_root.is_relative_to(project_root) else resolved_config_root.parent
    storage_layout = ProjectStorageLayout(storage_root)
    managed_output_policies = tuple(
        policy
        for policy in (
            _managed_publication_manuscript_output_policy(
                project_root=project_root, manuscript_config_path=config_file
            ),
        )
        if policy is not None
    )
    storage_layout.validate_final_output(output_path, managed_output_policies=managed_output_policies)
    storage_check = storage_layout.check_user_output(
        output_path,
        preferred_kinds=(
            DurableOutputKind.PAPER,
            DurableOutputKind.MANUSCRIPT,
            DurableOutputKind.DRAFT,
        ),
        managed_output_policies=managed_output_policies,
    )

    bib_source = _resolve_bibliography_path(
        explicit_path=bibliography,
        config_path=config_file,
        output_dir=output_path,
        bib_stem=paper_config.bib_file.removesuffix(".bib"),
        project_root=project_root,
    )
    bib_data = None
    if bib_source is not None:
        from pybtex.database import parse_file

        try:
            bib_data = parse_file(str(bib_source))
        except Exception as exc:  # noqa: BLE001
            raise GPDError(f"Failed to parse bibliography {_format_display_path(bib_source)}: {exc}") from exc

    citation_payload = None
    citation_source_path: Path | None = None
    citation_source_warning: str | None = None
    if citation_sources is not None:
        citation_source_path = _resolve_existing_input_path(citation_sources, candidates=(), label="citation sources")
        try:
            citation_payload = _load_citation_sources_payload(citation_source_path)
        except GPDError as exc:
            _error(str(exc))

    toolchain = _paper_build_toolchain_payload()

    # Sidecar routing: strict review and arXiv preflight read manuscript-local
    # manifest/audit sidecars from the resolved output directory. --minimal
    # suppresses sidecars entirely.
    artifact_manifest_output_path: Path | None = None
    bibliography_audit_output_path: Path | None = None
    if minimal:
        paper_sidecar_root: Path | None = None
        emit_artifact = False
        emit_bib_audit = False
    else:
        emit_artifact = True
        emit_bib_audit = True
        paper_sidecar_root = None

    if citation_sources is None:
        citation_source_path, citation_source_warning = _discover_literature_review_citation_sources(
            project_root,
            paper_config=paper_config,
        )
        if citation_source_path is not None:
            try:
                citation_payload = _load_citation_sources_payload(citation_source_path)
            except GPDError as exc:
                _error(str(exc))

    result = asyncio.run(
        build_paper(
            paper_config,
            output_path,
            bib_data=bib_data,
            citation_sources=citation_payload,
            enrich_bibliography=enrich_bibliography,
            sidecar_root=paper_sidecar_root,
            artifact_manifest_output_path=artifact_manifest_output_path,
            bibliography_audit_output_path=bibliography_audit_output_path,
            emit_artifact_manifest=emit_artifact,
            emit_bibliography_audit=emit_bib_audit,
        )
    )
    result_tex_path = result.tex_path if isinstance(result.tex_path, Path) else None
    if result_tex_path is None:
        result_tex_path = output_path / f"{derive_output_filename(paper_config)}.tex"

    payload = {
        "config_path": _format_display_path_from_cwd(config_file, cwd=cwd),
        "output_dir": _format_display_path_from_cwd(output_path, cwd=cwd),
        "tex_path": _format_display_path_from_cwd(result_tex_path, cwd=cwd),
        "bibliography_source": _format_display_path_from_cwd(bib_source, cwd=cwd),
        "citation_sources_path": _format_display_path_from_cwd(citation_source_path, cwd=cwd),
        "reference_bibtex_bridge": _paper_build_reference_bibtex_bridge(result),
        "manifest_path": _format_display_path_from_cwd(result.manifest_path, cwd=cwd),
        "bibliography_audit_path": _format_display_path_from_cwd(result.bibliography_audit_path, cwd=cwd),
        "pdf_path": _format_display_path_from_cwd(result.pdf_path, cwd=cwd),
        "success": result.success,
        "error_count": len(result.errors),
        "errors": result.errors,
        "toolchain": toolchain,
        "mode": {
            "minimal": minimal,
            "sidecar_root": _format_display_path_from_cwd(paper_sidecar_root, cwd=cwd)
            if paper_sidecar_root is not None
            else None,
        },
        "warnings": list(storage_check.warnings)
        + [warning for warning in toolchain["warnings"] if warning not in storage_check.warnings]
        + ([citation_source_warning] if citation_source_warning else [])
        + list(getattr(result, "citation_warnings", [])),
    }
    _output(payload)
    if not result.success:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# timestamp — Current timestamp utility
# ═══════════════════════════════════════════════════════════════════════════


@app.command("timestamp")
def timestamp(
    fmt: str = typer.Argument("full", help="Format: date, filename, or full"),
) -> None:
    """Return current timestamp in the requested format."""
    from gpd.core.commands import cmd_current_timestamp

    _output(cmd_current_timestamp(fmt))


# ═══════════════════════════════════════════════════════════════════════════
# slug — Generate URL-safe slug
# ═══════════════════════════════════════════════════════════════════════════


@app.command("slug")
def slug(
    text: str = typer.Argument(..., help="Text to convert to a slug"),
) -> None:
    """Generate a URL-safe slug from text."""
    from gpd.core.commands import cmd_generate_slug

    _output(cmd_generate_slug(text))


# ═══════════════════════════════════════════════════════════════════════════
# resolve-tier / resolve-model — Agent tier + runtime model resolution
# ═══════════════════════════════════════════════════════════════════════════


@app.command("resolve-tier")
def resolve_tier_cmd(
    agent_name: str = typer.Argument(..., help="Agent name (e.g. gpd-executor)"),
) -> None:
    """Resolve the abstract model tier for an agent in the current project."""
    from gpd.core.config import resolve_tier, validate_agent_name

    try:
        validate_agent_name(agent_name)
        _output(resolve_tier(_get_cwd(), agent_name))
    except ConfigError as exc:
        _error(str(exc))


@app.command("resolve-model")
def resolve_model_cmd(
    agent_name: str = typer.Argument(..., help="Agent name (e.g. gpd-executor)"),
    runtime: str | None = typer.Option(
        None,
        "--runtime",
        help=_runtime_override_help(),
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Explain the resolved tier/runtime and why the command may print nothing.",
    ),
) -> None:
    """Resolve the runtime-specific model override for an agent.

    Prints nothing when no override is configured so callers can omit the
    runtime model parameter and let the platform use its default model. Use
    --explain for a human-readable explanation without changing shell-safe
    default stdout behavior.
    """
    from gpd.core.config import resolve_model, resolve_tier, validate_agent_name
    from gpd.core.context import _detect_platform as detect_context_runtime
    from gpd.core.context import _resolve_model as resolve_context_model

    supported_runtimes = _supported_runtime_names()
    if runtime is not None:
        canonical_runtime = normalize_runtime_name(runtime)
        if canonical_runtime is None:
            supported = ", ".join(supported_runtimes)
            _error(f"Unknown runtime {runtime!r}. Supported: {supported}")
        runtime = canonical_runtime
    if runtime is not None and supported_runtimes and runtime not in supported_runtimes:
        supported = ", ".join(supported_runtimes)
        _error(f"Unknown runtime {runtime!r}. Supported: {supported}")

    try:
        validate_agent_name(agent_name)
        resolved_model = (
            resolve_model(_get_cwd(), agent_name, runtime=runtime)
            if runtime is not None
            else resolve_context_model(_get_cwd(), agent_name)
        )
        if explain:
            effective_runtime = (
                runtime if runtime is not None else normalize_runtime_name(detect_context_runtime(_get_cwd()))
            )
            tier = resolve_tier(_get_cwd(), agent_name).value
            if resolved_model is not None:
                detail = (
                    f"Resolved explicit model override for runtime {effective_runtime!r} at {tier}; "
                    f"the command emits {resolved_model!r}."
                )
            elif effective_runtime is None:
                detail = (
                    "No active runtime could be resolved, so no runtime-specific override can be selected. "
                    "Omit the model parameter and let the platform use its default model."
                )
            else:
                detail = (
                    f"No explicit model override is configured for runtime {effective_runtime!r} at {tier}. "
                    "The command stays silent by default so shell wrappers can omit the model parameter "
                    "and use the platform default."
                )
            _output(
                {
                    "agent_name": agent_name,
                    "tier": tier,
                    "runtime": effective_runtime,
                    "runtime_source": "explicit" if runtime is not None else "detected",
                    "resolved_model": resolved_model,
                    "override_configured": resolved_model is not None,
                    "uses_runtime_default": resolved_model is None,
                    "detail": detail,
                }
            )
            return
        if resolved_model is None and _stdout_is_interactive():
            console.print(
                "[dim]No explicit model override is configured. Use `gpd resolve-model "
                f"{agent_name} --explain` for details.[/dim]"
            )
            return
        _output(resolved_model)
    except ConfigError as exc:
        _error(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# verify-path — Path existence check
# ═══════════════════════════════════════════════════════════════════════════


@app.command("verify-path")
def verify_path(
    target_path: str = typer.Argument(..., help="Path to verify (relative or absolute)"),
) -> None:
    """Verify whether a file or directory path exists."""
    from gpd.core.commands import cmd_verify_path_exists

    result = cmd_verify_path_exists(_get_cwd(), target_path)
    _output(result)
    if not result.exists:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# json — lightweight JSON manipulation (jq-lite)
# ═══════════════════════════════════════════════════════════════════════════

json_app = typer.Typer(help="JSON manipulation utilities (jq-lite)")
app.add_typer(json_app, name="json")


@json_app.command("get")
def json_get_cmd(
    key: str = typer.Argument(..., help="Dot-path key (e.g. .section, .directories[-1])"),
    default: str | None = typer.Option(None, "--default", help="Default value if key is missing"),
) -> None:
    """Read a value from stdin JSON at the given dot-path key."""

    from gpd.core.json_utils import json_get

    stdin_text = sys.stdin.read()
    try:
        result = json_get(stdin_text, key, default=default)
    except ValueError as exc:
        _error(str(exc))
    _json_cli_output(result)


@json_app.command("keys")
def json_keys_cmd(
    key: str = typer.Argument(..., help="Dot-path to object (e.g. .waves)"),
) -> None:
    """List top-level keys of the object at the given path from stdin JSON."""

    from gpd.core.json_utils import json_keys

    stdin_text = sys.stdin.read()
    result = json_keys(stdin_text, key)
    _json_cli_output(result)


@json_app.command("list")
def json_list_cmd(
    key: str = typer.Argument(..., help="Dot-path to array or object"),
) -> None:
    """List items from the array at the given path from stdin JSON."""

    from gpd.core.json_utils import json_list

    stdin_text = sys.stdin.read()
    result = json_list(stdin_text, key)
    _json_cli_output(result)


@json_app.command("pluck")
def json_pluck_cmd(
    key: str = typer.Argument(..., help="Dot-path to array of objects"),
    field: str = typer.Argument(..., help="Field name to extract from each object"),
) -> None:
    """Extract a field from each object in the array at the given path."""

    from gpd.core.json_utils import json_pluck

    stdin_text = sys.stdin.read()
    result = json_pluck(stdin_text, key, field)
    _json_cli_output(result)


@json_app.command("set")
def json_set_cmd(
    file: str = typer.Option(..., "--file", help="Path to JSON file"),
    path: str = typer.Option(..., "--path", help="Dot-path key to set"),
    value: str = typer.Option(..., "--value", help="Value to set"),
) -> None:
    """Set a key in a JSON file (creates file if needed)."""
    from gpd.core.json_utils import json_set

    _json_cli_output(json_set(str(_get_cwd() / file), path, value))


@json_app.command("merge-files")
def json_merge_files_cmd(
    files: list[str] = typer.Argument(..., help="JSON files to merge"),
    out: str = typer.Option(..., "--out", help="Output file path"),
) -> None:
    """Merge multiple JSON files into one (shallow dict merge)."""
    from gpd.core.json_utils import json_merge_files

    cwd = _get_cwd()
    _json_cli_output(json_merge_files(str(cwd / out), [str(cwd / f) for f in files]))


@json_app.command("sum-lengths")
def json_sum_lengths_cmd(
    keys: list[str] = typer.Argument(..., help="Dot-path keys to arrays"),
) -> None:
    """Sum the lengths of arrays at the given paths from stdin JSON."""

    from gpd.core.json_utils import json_sum_lengths

    stdin_text = sys.stdin.read()
    result = json_sum_lengths(stdin_text, keys)
    _json_cli_output(result)


# ═══════════════════════════════════════════════════════════════════════════
# commit — Git commit for planning files
# ═══════════════════════════════════════════════════════════════════════════


@app.command("commit", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def commit(
    ctx: typer.Context,
    message: str = typer.Argument(..., help="Commit message"),
    files: list[str] | None = typer.Option(None, "--files", help="Files to stage and commit"),
) -> None:
    """Stage planning files and create a git commit.

    If --files is not specified, stages all GPD/ changes.
    Skips cleanly when commit_docs is disabled for the project.

    Examples::

        gpd commit "docs: update roadmap" --files GPD/ROADMAP.md
        gpd commit "docs: initialize research project" --files GPD/PROJECT.md GPD/state.json
        gpd commit "wip: phase 3 progress"
    """
    from gpd.core.git_ops import cmd_commit

    result = cmd_commit(_get_cwd(), message, files=_collect_file_option_args(ctx, files) or None)
    _output(result)
    if not result.committed and not getattr(result, "skipped", False):
        raise typer.Exit(code=1)


@app.command("pre-commit-check", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def pre_commit_check(
    ctx: typer.Context,
    files: list[str] | None = typer.Option(None, "--files", help="Files to validate"),
) -> None:
    """Run pre-commit validation on planning files.

    Checks storage-path policy, frontmatter YAML validity, and NaN/Inf values.
    If --files is omitted, validates the currently staged files.

    Examples::

        gpd pre-commit-check --files GPD/ROADMAP.md GPD/STATE.md
    """
    from gpd.core.git_ops import cmd_pre_commit_check

    result = cmd_pre_commit_check(_get_cwd(), _collect_file_option_args(ctx, files))
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# version
# ═══════════════════════════════════════════════════════════════════════════


@app.command("version")
def version_cmd() -> None:
    """Show GPD version."""
    _print_version()


# ═══════════════════════════════════════════════════════════════════════════
# install — Install GPD into a runtime
# ═══════════════════════════════════════════════════════════════════════════

_INSTALL_ACCENT_COLOR = _install_cli_support.INSTALL_ACCENT_COLOR
_INSTALL_TARGET_DIR_HELP = (
    "Override the runtime config directory; defaults to local scope unless the path resolves to that runtime's "
    "canonical global config dir"
)
_ENV_BOOTSTRAP_EMBEDDED_INSTALL = "GPD_BOOTSTRAP_EMBEDDED_INSTALL"


def _format_install_header_lines(version: str) -> tuple[str, str]:
    """Return the branded header shown during interactive install."""
    return _install_cli_support.format_install_header_lines(version)


def _print_install_header(version: str) -> None:
    """Render the branded install banner for human-facing install flows."""
    _install_cli_support.print_install_header(version, console=console)


def _render_install_option_line(index: int, label: str, *details: str, label_width: int | None = None) -> Text:
    """Return a single-line formatted install menu option."""
    return _install_cli_support.render_install_option_line(index, label, *details, label_width=label_width)


def _render_install_choice_prompt() -> Text:
    """Return the shared interactive prompt label for install menus."""
    return _install_cli_support.render_install_choice_prompt()


def _prompt_runtimes(*, action: str = "install") -> list[str]:
    """Interactive runtime selection. Returns list of selected runtime names."""
    from rich.prompt import Prompt

    runtimes = _list_runtimes_or_error(action=f"{action} runtime selection")
    try:
        return _install_cli_support.prompt_runtimes(
            action=action,
            runtime_names=runtimes,
            adapter_lookup=lambda runtime: _get_adapter_or_error(runtime, action=f"{action} runtime selection"),
            normalize_runtime_name=normalize_runtime_name,
            console=console,
            prompt_ask=Prompt.ask,
        )
    except _install_cli_support.InstallSelectionError as exc:
        _error(str(exc))
        return []  # unreachable


def _location_example(runtimes: list[str], *, is_global: bool, action: str) -> str:
    """Return a representative install location example for the selected runtime set."""
    return _install_cli_support.location_example(
        runtimes,
        is_global=is_global,
        action=action,
        cwd=_get_cwd(),
        adapter_lookup=lambda runtime: _get_adapter_or_error(runtime, action=f"{action} location selection"),
    )


def _prompt_location(runtimes: list[str], *, action: str = "install") -> bool:
    """Interactive location selection. Returns True for global, False for local."""
    from rich.prompt import Prompt

    try:
        return _install_cli_support.prompt_location(
            runtimes,
            action=action,
            cwd=_get_cwd(),
            adapter_lookup=lambda runtime: _get_adapter_or_error(runtime, action=f"{action} location selection"),
            console=console,
            prompt_ask=Prompt.ask,
        )
    except _install_cli_support.InstallSelectionError as exc:
        _error(str(exc))
        return False  # unreachable


def _install_single_runtime(
    runtime_name: str,
    *,
    is_global: bool,
    target_dir_override: str | None = None,
) -> dict[str, object]:
    """Install GPD for a single runtime. Returns install result dict."""
    from contextlib import nullcontext

    from gpd.version import resolve_install_gpd_root

    adapter = _get_adapter_or_error(runtime_name, action="install")
    gpd_root = resolve_install_gpd_root(_get_cwd())

    if target_dir_override:
        dest = _resolve_cli_target_dir(target_dir_override)
    else:
        dest = adapter.resolve_target_dir(is_global, _get_cwd())

    defer_rollback = getattr(adapter, "defer_install_rollback_discard", None)
    rollback_context = defer_rollback() if callable(defer_rollback) else nullcontext()
    with rollback_context:
        result = adapter.install(
            gpd_root,
            dest,
            is_global=is_global,
            explicit_target=target_dir_override is not None,
        )
    install_rollback = result.pop(_INSTALL_RESULT_ROLLBACK_KEY, None)
    result[_INSTALL_RESULT_ADAPTER_KEY] = adapter
    if install_rollback is not None:
        result[_INSTALL_RESULT_ROLLBACK_KEY] = install_rollback
    return result


def _install_repair_command(
    runtime_name: str,
    *,
    target_dir: Path,
    is_global: bool,
    explicit_target: bool,
) -> str:
    """Return a deterministic repair command for a CLI install target."""
    from gpd.adapters.install_utils import build_runtime_install_repair_command

    return build_runtime_install_repair_command(
        runtime_name,
        install_scope="global" if is_global else "local",
        target_dir=target_dir,
        explicit_target=explicit_target,
    )


def _mark_install_incomplete_after_rollback_failure(
    *,
    runtime_name: str,
    target_dir: Path,
    reason: str,
    repair_command: str,
) -> str:
    """Best-effort marker for install targets that could not be rolled back."""
    from gpd.adapters.install_utils import MANIFEST_NAME

    if not target_dir.exists():
        return "Rollback failed, but the target no longer exists; rerun install after fixing the error."
    marker_path = target_dir / "gpd-install-incomplete.json"
    try:
        manifest_path = target_dir / MANIFEST_NAME
        if manifest_path.exists() or manifest_path.is_symlink():
            manifest_path.unlink()
        marker_path.write_text(
            json.dumps(
                {
                    "status": "incomplete",
                    "runtime": runtime_name,
                    "reason": reason,
                    "repair_command": repair_command,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception as marker_exc:  # noqa: BLE001
        return (
            "Rollback failed and GPD could not mark the target incomplete "
            f"({marker_exc}). Inspect {target_dir} before using it."
        )
    return (
        f"Rollback failed; GPD removed the install manifest and wrote {marker_path} so the target is not treated "
        "as a complete install. Inspect the target, then rerun the repair command."
    )


def _restore_install_after_finalize_failure(
    *,
    runtime_name: str,
    target_dir: Path,
    is_global: bool,
    explicit_target: bool,
    rollback: object | None,
    error: Exception,
) -> str:
    """Rollback a CLI install whose adapter finalization failed."""
    if rollback is None:
        return str(error)

    repair_command = _install_repair_command(
        runtime_name,
        target_dir=target_dir,
        is_global=is_global,
        explicit_target=explicit_target,
    )
    try:
        rollback.restore()
    except Exception as rollback_exc:  # noqa: BLE001
        incomplete_message = _mark_install_incomplete_after_rollback_failure(
            runtime_name=runtime_name,
            target_dir=target_dir,
            reason=f"finalize_install failed: {error}; rollback failed: {rollback_exc}",
            repair_command=repair_command,
        )
        return (
            f"{error} Rollback of partial install at {_format_display_path(target_dir)} failed: {rollback_exc}. "
            f"{incomplete_message} Repair command: `{repair_command}`"
        )

    return (
        f"{error} Rolled back partial install at {_format_display_path(target_dir)}. "
        f"After fixing the finalize error, rerun: `{repair_command}`"
    )


def _discard_install_rollback(rollback: object | None) -> None:
    """Discard a deferred install rollback snapshot after finalization succeeds."""
    if rollback is None:
        return
    discard = getattr(rollback, "discard", None)
    if callable(discard):
        try:
            discard()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to discard install rollback snapshot")


def _print_install_summary(
    results: list[tuple[str, dict[str, object]]],
    *,
    include_next_steps: bool = True,
) -> None:
    """Print a rich summary table of install results."""
    _install_cli_support.print_install_summary(
        results,
        cwd=_get_cwd(),
        console=console,
        adapter_lookup=lambda runtime: _get_adapter_or_error(runtime, action="install summary"),
        include_next_steps=include_next_steps,
    )


def _validate_all_runtime_selection(action: str, runtimes: list[str] | None, use_all: bool) -> None:
    """Reject ambiguous runtime selection between explicit args and --all."""
    if use_all and runtimes:
        _error(f"Cannot combine explicit runtimes with --all for {action}")


def _validate_target_dir_runtime_selection(action: str, runtimes: list[str], target_dir: str | None) -> None:
    """Reject explicit target-dir usage when multiple runtimes are selected."""
    try:
        _runtime_targeting.validate_target_dir_runtime_selection(action, runtimes, target_dir)
    except _runtime_targeting.RuntimeTargetingError as exc:
        _error(str(exc))


def _resolve_cli_target_dir(target_dir: str) -> Path:
    """Resolve a CLI target-dir argument relative to the active --cwd."""
    return _runtime_targeting.resolve_cli_target_dir(target_dir, cwd=_get_cwd())


def _target_dir_matches_global(runtime_name: str, target_dir: str, *, action: str) -> bool:
    """Return whether an explicit target-dir names the runtime's canonical global dir."""
    return _runtime_targeting.target_dir_matches_global(
        runtime_name,
        target_dir,
        cwd=_get_cwd(),
        action=action,
        adapter_lookup=lambda runtime: _get_adapter_or_error(runtime, action=action),
    )


def _resolve_detected_runtime_target(runtime_name: str) -> tuple[Path | None, str | None]:
    """Return the concrete installed runtime target when one can be detected."""
    return _runtime_targeting.resolve_detected_runtime_target(
        runtime_name,
        cwd=_get_cwd(),
        adapter_lookup=lambda runtime: _get_adapter_or_error(runtime, action="inspect runtime readiness"),
    )


def _install_summary_local_cli_bridge_line() -> str:
    """Return the concise local-CLI bridge follow-up for install summaries.

    The richer settings guidance stays in bootstrap/help surfaces that render
    post_start_settings_note() and post_start_settings_recommendation().
    """
    return _install_cli_support.install_summary_local_cli_bridge_line()


def _print_workflow_preset_list() -> None:
    """Render the workflow preset registry as a table."""
    presets = list_workflow_presets()
    table = Table(
        title="Workflow Presets",
        title_style=f"italic {_INSTALL_ACCENT_COLOR}",
        show_header=True,
        header_style=f"bold {_INSTALL_ACCENT_COLOR}",
    )
    table.add_column("Preset", style="bold")
    table.add_column("Label")
    table.add_column("Ready workflows")
    table.add_column("Description")
    table.add_column("Required checks")

    for preset in presets:
        workflows = ", ".join(preset.ready_workflows) if preset.ready_workflows else "—"
        requirements = ", ".join(preset.required_checks) if preset.required_checks else "—"
        table.add_row(preset.id, preset.label, workflows, preset.description, requirements)

    console.print(table)


def _print_workflow_preset_details(preset_name: str) -> None:
    """Render one workflow preset from the central contract."""
    preset = get_workflow_preset(preset_name)
    if preset is None:
        supported = ", ".join(preset.id for preset in list_workflow_presets())
        _error(f"Unknown workflow preset {preset_name!r}. Supported: {supported}")

    _pretty_print(dataclasses.asdict(preset))


def _doctor_blocker_messages(report: object) -> list[str]:
    """Extract blocking doctor messages from a report-like object."""
    return _install_readiness_support.doctor_blocker_messages(report)


def _doctor_advisory_messages(report: object) -> list[str]:
    """Extract advisory doctor warnings from a report-like object."""
    return _install_readiness_support.doctor_advisory_messages(report)


def _install_repairable_runtime_target_messages(report: object, runtime_name: str) -> list[str]:
    """Return install-preflight messages for same-runtime incomplete targets."""
    return _install_readiness_support.install_repairable_runtime_target_messages(report, runtime_name)


def _build_unattended_readiness(
    *,
    runtime: str,
    autonomy: str | None,
    global_install: bool,
    local_install: bool,
    target_dir: str | None,
    live_executable_probes: bool,
) -> UnattendedReadinessResult:
    """Compose doctor and permissions status into one unattended-readiness verdict."""
    from gpd.specs import SPECS_DIR

    try:
        return _install_readiness_support.build_unattended_readiness(
            runtime=runtime,
            autonomy=autonomy,
            global_install=global_install,
            local_install=local_install,
            target_dir=target_dir,
            live_executable_probes=live_executable_probes,
            cwd=_get_cwd(),
            normalize_runtime_selection=_normalize_runtime_selection,
            validated_surface=_validated_runtime_surface(cwd=_get_cwd()),
            specs_dir=SPECS_DIR,
            target_dir_matches_global_func=lambda runtime_name, target, cwd, action: _target_dir_matches_global(
                runtime_name,
                target,
                action=action,
            ),
            resolve_detected_runtime_target_func=lambda runtime_name, cwd: _resolve_detected_runtime_target(
                runtime_name
            ),
            permissions_status_payload_func=lambda **kwargs: _permissions_status_payload(
                runtime=kwargs.get("runtime"),
                autonomy=kwargs.get("autonomy"),
                target_dir=kwargs.get("target_dir"),
            ),
        )
    except _install_readiness_support.InstallReadinessError as exc:
        _error(str(exc))
        raise


def _run_install_readiness_preflight(
    runtimes: list[str],
    *,
    install_scope: str,
    target_dir: Path | None,
) -> tuple[list[tuple[str, list[str]]], dict[str, list[str]]]:
    """Run doctor-led readiness checks before mutating runtime install targets."""
    from gpd.specs import SPECS_DIR

    return _install_readiness_support.run_install_readiness_preflight(
        runtimes,
        install_scope=install_scope,
        target_dir=target_dir,
        cwd=_get_cwd(),
        specs_dir=SPECS_DIR,
    )


def _install_command_doc() -> str:
    return (
        "Install GPD skills, agents, and hooks into runtime config directories.\n\n"
        "Run without arguments for interactive mode. Specify runtime name(s) or --all for batch mode.\n\n"
        "Examples::\n\n"
        "    gpd install                        # interactive\n"
        f"    {local_cli_install_local_example_command()}              # single runtime, local\n"
        "    gpd install <runtime-a> <runtime-b>\n"
        "    gpd install --all --global         # all runtimes, global\n"
    )


@app.command("install", help=_install_command_doc())
def install(
    runtimes: list[str] | None = typer.Argument(
        None,
        help="Runtime(s) to install. Omit for interactive selection.",
    ),
    install_all: bool = typer.Option(False, "--all", help="Install for all supported runtimes"),
    local_install: bool = typer.Option(False, "--local", help="Install into the local runtime config dir"),
    global_install: bool = typer.Option(False, "--global", help="Install into the global runtime config dir"),
    target_dir: str | None = typer.Option(None, "--target-dir", help=_INSTALL_TARGET_DIR_HELP),
    force_statusline: bool = typer.Option(False, "--force-statusline", help="Overwrite existing statusline config"),
    skip_readiness_check: bool = typer.Option(
        False, "--skip-readiness-check", help="Skip runtime readiness preflight (for embedded/sidecar use)"
    ),
) -> None:
    """Install GPD skills, agents, and hooks into runtime config directories."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from gpd.core.health import runtime_doctor_hint
    from gpd.version import resolve_active_version

    if global_install and local_install:
        _error("Cannot specify both --global and --local")
        return  # unreachable
    _validate_all_runtime_selection("install", runtimes, install_all)

    embedded_bootstrap_install = os.environ.get(_ENV_BOOTSTRAP_EMBEDDED_INSTALL) == "1"

    if not _raw and not embedded_bootstrap_install:
        _print_install_header(resolve_active_version(_get_cwd()))

    # Resolve which runtimes to install
    selected: list[str]
    if install_all:
        selected = _list_runtimes_or_error(action="install")
    elif runtimes:
        selected = _normalize_runtime_selection(list(runtimes), action="install")
    elif _raw:
        _error("Raw install requires one or more runtimes or --all")
    else:
        # Interactive mode
        selected = _prompt_runtimes()

    _validate_target_dir_runtime_selection("install", selected, target_dir)

    # Resolve location
    if target_dir:
        if global_install:
            is_global = True
        elif local_install:
            is_global = False
        else:
            is_global = _target_dir_matches_global(selected[0], target_dir, action="install")
    elif global_install:
        is_global = True
    elif local_install:
        is_global = False
    elif _raw:
        _error("Raw install requires --local, --global, or --target-dir")
    elif not runtimes and not install_all:
        # Interactive mode — ask for location
        is_global = _prompt_location(selected)
    else:
        # Non-interactive default: local
        is_global = False

    location_label = "global" if is_global else "local"
    install_scope = "global" if is_global else "local"
    resolved_target_override = _resolve_cli_target_dir(target_dir) if target_dir else None

    preflight_failures: list[tuple[str, list[str]]] = []
    preflight_advisories: dict[str, list[str]] = {}
    if not skip_readiness_check:
        preflight_failures, preflight_advisories = _run_install_readiness_preflight(
            selected,
            install_scope=install_scope,
            target_dir=resolved_target_override,
        )
    if preflight_failures:
        if _raw:
            _output(
                {
                    "installed": [],
                    "failed": [
                        {"runtime": runtime_name, "error": "; ".join(messages)}
                        for runtime_name, messages in preflight_failures
                    ],
                }
            )
        else:
            console.print(f"\n[bold]Runtime readiness preflight for: {_format_runtime_list(selected)}[/]")
            console.print()
            err_console.print("[bold red]Error:[/] Runtime readiness preflight failed.", highlight=False)
            for runtime_name, messages in preflight_failures:
                display_name = _get_adapter_or_error(runtime_name, action="install readiness").display_name
                for message in messages:
                    err_console.print(f"- {display_name}: {message}", highlight=False)
            doctor_hints = ", ".join(
                f"`{runtime_doctor_hint(runtime_name, install_scope=install_scope, target_dir=resolved_target_override)}`"
                for runtime_name, _messages in preflight_failures
            )
            console.print(
                f"Fix the blocking readiness issue(s) above, then rerun `gpd install`. Inspect directly with {doctor_hints}.",
                soft_wrap=True,
            )
        raise typer.Exit(code=1)

    if not _raw and not (skip_readiness_check and embedded_bootstrap_install):
        console.print(f"\n[bold]Runtime readiness preflight for: {_format_runtime_list(selected)}[/]")
        if skip_readiness_check:
            for runtime_name in selected:
                display_name = _get_adapter_or_error(runtime_name, action="install readiness").display_name
                console.print(f"- {display_name}: readiness check skipped.")
        else:
            for runtime_name in selected:
                display_name = _get_adapter_or_error(runtime_name, action="install readiness").display_name
                advisories = preflight_advisories.get(runtime_name, [])
                if advisories:
                    console.print(f"- {display_name}: readiness check passed with advisories.")
                    for advisory in advisories:
                        console.print(f"  - {advisory}")
                else:
                    console.print(f"- {display_name}: readiness check passed.")
        console.print()
        console.print(f"\n[bold]Installing GPD ({location_label}) for: {_format_runtime_list(selected)}[/]\n")

    # Install each runtime with progress
    results: list[tuple[str, dict[str, object]]] = []
    failures: list[tuple[str, str]] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=_raw,
    ) as progress:
        for rt in selected:
            adapter = _get_adapter_or_error(rt, action="install")
            task = progress.add_task(f"Installing {adapter.display_name}...", total=None)
            try:
                result = _install_single_runtime(rt, is_global=is_global, target_dir_override=target_dir)
                install_adapter = result.pop(_INSTALL_RESULT_ADAPTER_KEY, adapter)
                install_rollback = result.pop(_INSTALL_RESULT_ROLLBACK_KEY, None)
                result_target = Path(str(result.get("target") or adapter.resolve_target_dir(is_global, _get_cwd())))
                try:
                    install_adapter.finalize_install(result, force_statusline=force_statusline)
                except Exception as exc:
                    failure_message = _restore_install_after_finalize_failure(
                        runtime_name=rt,
                        target_dir=result_target,
                        is_global=is_global,
                        explicit_target=target_dir is not None,
                        rollback=install_rollback,
                        error=exc,
                    )
                    raise RuntimeError(failure_message) from exc
                _discard_install_rollback(install_rollback)
                results.append((rt, result))
                progress.update(task, description=f"[green]✓[/] {adapter.display_name}")
            except Exception as exc:
                failures.append((rt, str(exc)))
                progress.update(task, description=f"[red]✗[/] {adapter.display_name}: {exc}")

    if _raw:
        _output(
            {
                "installed": [{"runtime": rt, **res} for rt, res in results],
                "failed": [{"runtime": rt, "error": err} for rt, err in failures],
            }
        )
    else:
        _print_install_summary(results, include_next_steps=not failures)

    if failures:
        if not _raw:
            console.print()
            err_console.print("[bold red]Install failures:[/]", highlight=False)
            for rt, err in failures:
                adapter = _get_adapter_or_error(rt, action="install failure reporting")
                err_console.print(f"- {adapter.display_name} ({rt}): {err}", highlight=False, soft_wrap=True)
        raise typer.Exit(code=1)


install.__doc__ = _install_command_doc()


# ═══════════════════════════════════════════════════════════════════════════
# uninstall — Remove GPD from a runtime
# ═══════════════════════════════════════════════════════════════════════════


@app.command("uninstall")
def uninstall(
    runtimes: list[str] | None = typer.Argument(
        None,
        help="Runtime(s) to uninstall. Omit for interactive selection.",
    ),
    uninstall_all: bool = typer.Option(False, "--all", help="Uninstall from all runtimes"),
    local_uninstall: bool = typer.Option(False, "--local", help="Uninstall from local config"),
    global_uninstall: bool = typer.Option(False, "--global", help="Uninstall from global config"),
    target_dir: str | None = typer.Option(None, "--target-dir", help=_INSTALL_TARGET_DIR_HELP),
    assume_yes: bool = typer.Option(
        False,
        "--yes",
        "--force",
        "-y",
        help="Confirm uninstall without prompting",
    ),
) -> None:
    """Remove GPD skills, agents, and hooks from runtime config directories.

    Examples::

        gpd uninstall <runtime> --local
        gpd uninstall --all --global
    """
    from rich.prompt import Confirm

    if global_uninstall and local_uninstall:
        _error("Cannot specify both --global and --local")
        return
    _validate_all_runtime_selection("uninstall", runtimes, uninstall_all)

    # Resolve runtimes
    selected: list[str]
    if uninstall_all:
        selected = _list_runtimes_or_error(action="uninstall")
    elif runtimes:
        selected = _normalize_runtime_selection(list(runtimes), action="uninstall")
    elif _raw:
        _error("Raw uninstall requires one or more runtimes or --all")
    else:
        selected = _prompt_runtimes(action="uninstall")

    _validate_target_dir_runtime_selection("uninstall", selected, target_dir)

    # Resolve location (skip prompts when --target-dir is explicit)
    if target_dir:
        if global_uninstall:
            is_global = True
        elif local_uninstall:
            is_global = False
        else:
            is_global = _target_dir_matches_global(selected[0], target_dir, action="uninstall")
    elif global_uninstall:
        is_global = True
    elif local_uninstall:
        is_global = False
    elif _raw:
        _error("Raw uninstall requires --local, --global, or --target-dir")
    elif not global_uninstall and not local_uninstall:
        is_global = _prompt_location(selected, action="uninstall")
    else:
        is_global = global_uninstall

    if not _raw and not assume_yes:
        location_label = "global" if is_global else "local"
        runtime_names = _format_runtime_list(selected)
        if target_dir:
            resolved_target = _resolve_cli_target_dir(target_dir)
            confirm_message = f"Remove GPD from {runtime_names} at {_format_display_path(resolved_target)}?"
        else:
            confirm_message = f"Remove GPD from {runtime_names} ({location_label})?"
        if not Confirm.ask(confirm_message, default=False):
            console.print("[dim]Cancelled.[/]")
            raise typer.Exit()

    uninstall_results: list[dict[str, object]] = []
    failures = False
    for rt in selected:
        try:
            from gpd.adapters import get_adapter

            adapter = get_adapter(rt)
        except KeyError:
            supported = _supported_runtime_names()
            supported_suffix = f" Supported: {', '.join(supported)}" if supported else ""
            error_text = f"Unknown runtime {rt!r}.{supported_suffix}"
            failures = True
            outcome = {"runtime": rt, "status": "failed", "target": target_dir or "", "error": error_text}
            if not _raw:
                console.print(f"  [red]✗[/] {rt} — {error_text}", soft_wrap=True)
            uninstall_results.append(outcome)
            continue
        except Exception as exc:
            error_text = f"Runtime adapter unavailable for {rt!r} during uninstall: {exc}"
            failures = True
            outcome = {"runtime": rt, "status": "failed", "target": target_dir or "", "error": error_text}
            if not _raw:
                console.print(f"  [red]✗[/] {rt} — {error_text}", soft_wrap=True)
            uninstall_results.append(outcome)
            continue
        target = (
            _resolve_cli_target_dir(target_dir) if target_dir else adapter.resolve_target_dir(is_global, _get_cwd())
        )
        target_missing_before = not target.is_dir()
        try:
            result = adapter.uninstall(target)
        except Exception as exc:
            failures = True
            outcome = {
                "runtime": rt,
                "status": "failed",
                "target": str(target),
                "error": str(exc),
            }
            if not _raw:
                console.print(f"  [red]✗[/] {adapter.display_name} — {exc}", soft_wrap=True)
            uninstall_results.append(outcome)
            continue
        removed_items = list(result.get("removed", []))
        status = "removed" if removed_items else "skipped"
        outcome = {
            "runtime": rt,
            "target": str(target),
            **result,
            "status": status,
        }
        if not removed_items:
            outcome["reason"] = (
                f"not installed at {_format_display_path(target)}" if target_missing_before else "nothing to remove"
            )
        if not _raw:
            if removed_items:
                console.print(
                    f"  [green]✓[/] {adapter.display_name} — removed: {', '.join(str(r) for r in removed_items)}"
                )
            elif target_missing_before:
                console.print(
                    f"  [yellow]⊘[/] {adapter.display_name} — not installed at {_format_display_path(target)}",
                    soft_wrap=True,
                )
            else:
                console.print(f"  [dim]⊘[/] {adapter.display_name} — nothing to remove")
        uninstall_results.append(outcome)

    if _raw:
        _output({"uninstalled": uninstall_results})
    if failures:
        raise typer.Exit(code=1)


@app.command("mcp-serve", help="Launch a GPD MCP server by name (for sidecar/binary mode).")
def mcp_serve(
    server: str = typer.Argument(
        ...,
        help="Server name (e.g., conventions, errors, patterns, protocols, skills, state, verification, arxiv).",
    ),
) -> None:
    """Launch a specific GPD MCP server via stdio transport."""
    import importlib

    from gpd.mcp.builtin_servers import _BUILTIN_SERVERS
    from gpd.mcp.managed_integrations import list_managed_integrations

    requested_server = server.strip()
    managed_aliases = {
        alias: integration
        for integration in list_managed_integrations().values()
        for alias in (integration.integration_id, integration.managed_server_key)
        if alias
    }
    prefixed_server = requested_server if requested_server.startswith("gpd-") else f"gpd-{requested_server}"
    managed_integration = managed_aliases.get(requested_server) or managed_aliases.get(prefixed_server)
    if managed_integration is not None:
        module_path = getattr(managed_integration, "bridge_module", None)
        if not isinstance(module_path, str) or not module_path.strip():
            raise typer.BadParameter(
                f"Managed server {managed_integration.managed_server_key} has no descriptor module path "
                f"for {managed_integration.bridge_command}"
            )
        module_path = module_path.strip()
        sys.argv = [sys.argv[0]]
        mod = importlib.import_module(module_path)
        mod.main()
        return

    # Accept both "conventions" and "gpd-conventions"
    server = prefixed_server

    if server not in _BUILTIN_SERVERS:
        managed_server_keys = {integration.managed_server_key for integration in managed_aliases.values()}
        available = ", ".join(sorted(set(_BUILTIN_SERVERS.keys()) | managed_server_keys))
        raise typer.BadParameter(f"Unknown server: {server}. Available: {available}")

    entry = _BUILTIN_SERVERS[server]
    args = entry.get("args", [])
    if len(args) >= 2 and args[0] == "-m":
        module_path = args[1]
    else:
        raise typer.BadParameter(f"Server {server} has no module path")

    # Clean argv so the server's argparse sees no leftover args
    sys.argv = [sys.argv[0]]

    mod = importlib.import_module(module_path)
    mod.main()


@app.command("list-servers", help="List available MCP servers as JSON config for runtime integration.")
def list_servers(
    json_output: bool = typer.Option(True, "--json/--text", help="Output as JSON (default) or text."),
    binary_path: str = typer.Option(None, "--binary", help="Override binary path in command arrays."),
) -> None:
    """Emit runtime-compatible MCP server config JSON from the builtin registry."""
    import json as json_mod

    from gpd.mcp.builtin_servers import build_mcp_servers_dict, merge_managed_mcp_servers
    from gpd.mcp.managed_integrations import projected_managed_optional_mcp_servers

    servers: dict[str, dict[str, object]] = build_mcp_servers_dict(python_path=sys.executable)
    managed_servers = projected_managed_optional_mcp_servers(cwd=_read_only_project_scoped_cwd())
    if managed_servers:
        servers = merge_managed_mcp_servers(servers, managed_servers)

    sidecar = binary_path or (sys.executable if getattr(sys, "frozen", False) else None)
    if sidecar:
        servers = {
            name: {
                "command": sidecar,
                "args": ["mcp-serve", name.removeprefix("gpd-")],
                **({"env": entry["env"]} if isinstance(entry.get("env"), dict) and entry["env"] else {}),
            }
            for name, entry in servers.items()
        }

    if json_output:
        typer.echo(json_mod.dumps(servers, indent=2))
    else:
        for name in sorted(servers):
            typer.echo(f"  {name}")


def entrypoint() -> int | None:
    """Console-script and ``python -m`` entrypoint with checkout preference."""
    _maybe_reexec_from_checkout()
    return app(args=_normalize_global_cli_options(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(entrypoint())
