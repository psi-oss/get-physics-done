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
import glob
import hashlib
import json
import logging
import os
import re
import shlex
import sys
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.table import Table
from rich.text import Text

from gpd.adapters.runtime_catalog import normalize_runtime_name
from gpd.command_labels import canonical_command_label, validated_public_command_prefix
from gpd.core.artifact_text import (
    DIGEST_KNOWLEDGE_SOURCE_SUFFIXES,
    PEER_REVIEW_ARTIFACT_SUFFIXES,
    ArtifactTextError,
    load_artifact_text_surface,
    materialize_artifact_text_surface,
    probe_artifact_text_surface,
)
from gpd.core.arxiv_source_download import normalize_arxiv_id
from gpd.core.cli_args import (
    normalize_root_global_cli_options as _normalize_root_global_cli_options,
)
from gpd.core.cli_args import (
    resolve_root_global_cli_cwd_from_argv as _resolve_root_global_cli_cwd_from_argv,
)
from gpd.core.cli_args import (
    split_root_global_cli_options as _split_root_global_cli_options,
)
from gpd.core.constants import (
    ENV_DATA_DIR,
    ENV_GPD_DISABLE_CHECKOUT_REEXEC,
    HOME_DATA_DIR_NAME,
    PLANNING_DIR_NAME,
    PUBLICATION_DIR_NAME,
    PUBLICATION_MANUSCRIPT_DIR_NAME,
)
from gpd.core.errors import ConfigError, GPDError
from gpd.core.manuscript_artifacts import (
    _resolve_manuscript_entrypoint_from_root_resolution as resolve_manuscript_entrypoint_from_root_resolution,
)
from gpd.core.manuscript_artifacts import (
    locate_publication_artifact,
    resolve_current_manuscript_resolution,
)
from gpd.core.onboarding_surfaces import (
    beginner_onboarding_hub_url,
    beginner_startup_ladder_text,
)
from gpd.core.peer_review_mode import (
    PEER_REVIEW_INVALID_SUBJECT_MODE,
    PEER_REVIEW_PROJECT_BACKED_MODE,
    PeerReviewModeResolution,
    resolve_peer_review_mode_details,
)
from gpd.core.project_reentry import (
    ProjectReentryResolution,
    _candidate_from_recent_row,
    _candidate_sort_key,
    recoverable_project_context,
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
    local_cli_help_command,
    local_cli_install_local_example_command,
    local_cli_permissions_sync_command,
    local_cli_plan_preflight_command,
    local_cli_resume_command,
    local_cli_resume_recent_command,
    local_cli_validate_command_context_command,
)
from gpd.core.publication_review_paths import (
    manuscript_matches_review_artifact_path,
    review_artifact_round,
    review_round_suffix,
)
from gpd.core.publication_runtime import (
    publication_blockers_for_project,
)
from gpd.core.recovery_advice import (
    RecoveryAdvice,
    build_recovery_advice,
    serialize_recovery_advice,
)
from gpd.core.resume_surface import (
    canonicalize_resume_public_payload,
    lookup_resume_surface_list,
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
    recovery_ladder_note,
    recovery_recent_action,
    recovery_resume_action,
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
    from gpd.mcp.paper.models import PaperConfig, WritePaperAuthoringInput
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
                table.add_row(f"  reason: {fk}", str(fv))
        elif isinstance(v, (dict, list)):
            val = json.dumps(v, default=str)
            table.add_row(str(k), val)
        else:
            table.add_row(str(k), str(v))
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


def _state_command_cwd(cwd: Path | None = None) -> Path:
    """Resolve the effective cwd for state and project-contract commands."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    _migrate_planning_files(workspace_cwd)
    resolved = resolve_project_root(workspace_cwd, require_layout=True)
    if resolved is not None:
        return resolved
    return workspace_cwd


def _read_only_project_scoped_cwd(cwd: Path | None = None) -> Path:
    """Resolve a project root for read-only commands without migration writes."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    resolved = resolve_project_root(workspace_cwd, require_layout=True)
    return resolved if resolved is not None else workspace_cwd


def _project_scoped_cwd(cwd: Path | None = None) -> Path:
    """Resolve the nearest verified project root for project-scoped preflights."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    _migrate_planning_files(workspace_cwd)
    resolved = resolve_project_root(workspace_cwd, require_layout=True)
    return resolved if resolved is not None else workspace_cwd


def _workspace_locked_cwd(cwd: Path | None = None) -> Path:
    """Resolve the effective cwd without walking up to an ancestor project root."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    _migrate_planning_files(workspace_cwd)
    resolved = resolve_project_root(
        workspace_cwd,
        require_layout=True,
        policy=RootResolutionPolicy.WORKSPACE_LOCKED,
    )
    return resolved if resolved is not None else workspace_cwd


def _command_preflight_cwd(
    command: object,
    *,
    cwd: Path | None = None,
    arguments: str | None = None,
) -> Path:
    """Resolve the authoritative preflight root for one command."""
    workspace_cwd = (cwd or _get_cwd()).expanduser().resolve(strict=False)
    if _command_supports_project_reentry(command):
        return _status_command_cwd(workspace_cwd)

    command_name = str(getattr(command, "name", "") or "")
    if command_name == "gpd:write-paper":
        return _workspace_locked_cwd(workspace_cwd)

    return _project_scoped_cwd(workspace_cwd)


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
class ResolvedCommandSubject:
    """Shared command-subject resolution envelope for CLI preflight consumers."""

    command: str
    workspace_root: Path
    resolved_project_root: Path | None
    context_root: Path
    target_path: Path | None
    target_root: Path | None
    subject_kind: str
    ownership_mode: str
    status: str
    exists: bool
    explicit_input: bool = False
    project_root_source: str | None = None
    project_root_auto_selected: bool = False
    reentry_mode: str | None = None
    ancestor_walked_up: bool = False
    detail: str = ""


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


@dataclasses.dataclass(frozen=True)
class CommandContextCheck:
    """One executable context check for a command."""

    name: str
    passed: bool
    blocking: bool
    detail: str


@dataclasses.dataclass(frozen=True)
class CommandContextPreflightResult:
    """Summary of whether a command can run in the current workspace context."""

    command: str
    context_mode: str
    passed: bool
    project_exists: bool
    explicit_inputs: list[str]
    guidance: str
    checks: list[CommandContextCheck]
    resolved_mode: str = ""
    mode_reason: str = ""
    validated_surface: str = "public_runtime_command_surface"
    public_runtime_command_prefix: str = ""
    local_cli_equivalence_guaranteed: bool = False
    dispatch_note: str = ""
    resolved_subject: ResolvedCommandSubject | None = None


@dataclasses.dataclass(frozen=True)
class ResolvedManuscriptTarget:
    """Structured manuscript-target resolution details for publication commands."""

    status: str
    manuscript: Path | None
    manuscript_root: Path | None
    requested_target: Path | None
    detail: str


@dataclasses.dataclass(frozen=True)
class WritePaperExternalAuthoringIntakeResolution:
    """Validated external-authoring intake details for bounded ``gpd:write-paper`` bootstrap."""

    status: str
    intake_path: Path | None
    manuscript_root: Path | None
    intake_root: Path | None
    subject_slug: str | None
    manifest: WritePaperAuthoringInput | None = None
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class ManuscriptIntakePolicy:
    """Static manuscript-subject intake rules for one command."""

    allowed_suffixes: frozenset[str]
    allow_external_targets: bool = False
    allow_interactive_standalone_intake: bool = False
    interactive_standalone_detail: str = ""


@dataclasses.dataclass(frozen=True)
class PublicationSubjectPreflightPolicy:
    """Publication preflight relaxations and scope overrides derived from the active subject."""

    active_scopes: frozenset[str] = frozenset()
    relaxed_checks: frozenset[str] = frozenset()
    optional_checks: frozenset[str] = frozenset()
    detail_overrides: Mapping[str, str] = dataclasses.field(default_factory=dict)
    required_outputs: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    blocking_conditions: tuple[str, ...] = ()

    def relaxes(self, check_name: str) -> bool:
        return check_name in self.relaxed_checks

    def makes_missing_optional(self, check_name: str) -> bool:
        return check_name in self.optional_checks

    def passes_when_missing(self, check_name: str) -> bool:
        return self.relaxes(check_name) or self.makes_missing_optional(check_name)

    def detail(self, check_name: str) -> str | None:
        return self.detail_overrides.get(check_name)

    def blocking(self, check_name: str, *, missing: bool = False, default: bool = True) -> bool:
        if self.relaxes(check_name):
            return False
        if missing and self.makes_missing_optional(check_name):
            return False
        return default

    def missing_detail(self, check_name: str, *, default: str) -> str:
        detail = self.detail(check_name)
        return detail if detail is not None else default


_SUPPORTED_MANUSCRIPT_ROOT_NAMES = frozenset({"paper", "manuscript", "draft"})
_DEFAULT_PUBLICATION_EXTERNAL_SUFFIXES = frozenset({".txt", ".pdf"})
_PUBLICATION_INTERACTIVE_STANDALONE_DETAIL = (
    "no explicit review target supplied; interactive intake can prompt for a specific artifact path "
    "or use the current GPD project when available"
)
_EXTERNAL_ARTIFACT_RELAXED_CHECKS = frozenset(
    {
        "project_state",
        "roadmap",
        "conventions",
        "research_artifacts",
        "verification_reports",
        "manuscript_proof_review",
    }
)
_EXTERNAL_ARTIFACT_OPTIONAL_CHECKS = frozenset(
    {
        "artifact_manifest",
        "bibliography_audit",
        "bibliography_audit_clean",
        "reproducibility_manifest",
        "reproducibility_ready",
    }
)
_EXTERNAL_ARTIFACT_OPTIONAL_DETAILS = {
    "project_state": "external artifact review: project state is optional and is not required to start review",
    "roadmap": "external artifact review: roadmap is optional",
    "conventions": "external artifact review: project conventions are optional",
    "research_artifacts": "external artifact review: phase summaries or milestone digests are optional",
    "verification_reports": "external artifact review: verification reports are optional",
    "artifact_manifest": "no ARTIFACT-MANIFEST.json found near the manuscript; external artifact review can proceed without it",
    "bibliography_audit": "no BIBLIOGRAPHY-AUDIT.json found near the manuscript; external artifact review can proceed without it",
    "reproducibility_manifest": (
        "no reproducibility manifest found near the manuscript; external artifact review can proceed without it"
    ),
    "manuscript_proof_review": (
        "prior staged manuscript proof review is optional in external artifact mode; "
        "theorem-bearing claims will be audited in this review round if detected"
    ),
}
_WRITE_PAPER_EXTERNAL_AUTHORING_EXPLICIT_INPUTS = ["--intake path/to/write-paper-authoring-input.json"]
_WRITE_PAPER_EXTERNAL_AUTHORING_DETAIL = (
    "external authoring outside a project requires `--intake path/to/write-paper-authoring-input.json`"
)
_WRITE_PAPER_EXTERNAL_AUTHORING_OPTIONAL_DETAILS = {
    "project_state": "external authoring intake: project state is optional because the intake manifest is authoritative",
    "roadmap": "external authoring intake: roadmap is optional because the intake manifest supplies the draft scope",
    "conventions": "external authoring intake: project conventions are optional before the manuscript exists",
    "research_artifacts": (
        "external authoring intake: milestone digests and phase summaries are optional because claims and evidence "
        "come from the intake manifest"
    ),
    "verification_reports": (
        "external authoring intake: project verification reports are optional because claim-to-evidence bindings come "
        "from the intake manifest"
    ),
    "artifact_manifest": (
        "no ARTIFACT-MANIFEST.json found yet; the external authoring lane emits it after manuscript scaffolding"
    ),
    "bibliography_audit": (
        "no BIBLIOGRAPHY-AUDIT.json found yet; the external authoring lane emits it after bibliography scaffolding"
    ),
    "bibliography_audit_clean": "bibliography audit cleanliness is optional before the first external-authoring draft",
    "reproducibility_manifest": (
        "no reproducibility manifest found yet; the external authoring lane emits it after manuscript scaffolding"
    ),
    "reproducibility_ready": "reproducibility readiness is optional before the first external-authoring draft",
    "manuscript_proof_review": (
        "prior staged manuscript proof review is optional before the first external-authoring draft; "
        "proof review begins after the manuscript is authored"
    ),
}


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


# ═══════════════════════════════════════════════════════════════════════════
# state — STATE.md and state.json management
# ═══════════════════════════════════════════════════════════════════════════

state_app = typer.Typer(help="State management (STATE.md + state.json)")
app.add_typer(state_app, name="state")


@state_app.command("load")
def state_load() -> None:
    """Load and display current research state."""
    from gpd.core.state import state_load

    _output(state_load(_read_only_project_scoped_cwd()))


@state_app.command("get")
def state_get(
    section: str | None = typer.Argument(None, help="State section to retrieve"),
) -> None:
    """Get a specific state section or the full state."""
    from gpd.core.state import state_get

    _output(state_get(_read_only_project_scoped_cwd(), section))


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
    from gpd.core.state import state_get

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
    from gpd.core.state import state_validate

    result = state_validate(_state_command_cwd())
    _output(result)
    if hasattr(result, "valid") and not result.valid:
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
        help="Verification outcome (passed|failed). If omitted, read from VERIFICATION.md frontmatter.",
    ),
) -> None:
    """Atomically advance STATE.md past verification after a VERIFICATION.md result."""
    from gpd.core.state import state_record_verification

    result = state_record_verification(_state_command_cwd(), phase=phase, status=status)
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
    """Require a verified GPD project root; ``command_label`` is the noun used in the error."""
    workspace_cwd = cwd.expanduser().resolve(strict=False)
    project_root = resolve_project_root(workspace_cwd, require_layout=True)
    if project_root is None:
        _error(
            f"{command_label} require a real GPD project root. "
            "Run the command from inside a project with a GPD/ layout."
        )
    return project_root


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
    from gpd.core.state import state_record_contract_alignment

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    state_record_contract_alignment(
        project_root,
        contract_hash=contract_hash,
        context_hash=context_hash,
    )
    if _raw:
        _emit_raw_json({"result": "recorded"})
    else:
        typer.echo("recorded")


@contract_app.command("alignment-status")
def contract_alignment_status() -> None:
    """Print the persisted claim-deliverable alignment confirmation as JSON."""
    from gpd.core.state import state_load

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    load_result = state_load(project_root)
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
    from gpd.core.state import _load_project_contract_for_runtime_context

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    contract, _load_info = _load_project_contract_for_runtime_context(project_root)
    if contract is None:
        _error("No project contract is available; cannot fingerprint.")
    typer.echo(contract_fingerprint(contract))


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
    from gpd.core.state import state_load

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    if path is None:
        state_obj = state_load(project_root).state
        current_phase = (
            state_obj.get("position", {}).get("current_phase")
            if isinstance(state_obj, dict)
            else None
        )
        if current_phase is None:
            _error(
                "No CONTEXT.md could be resolved: state.position.current_phase is "
                "unset. Pass an explicit path as the argument."
            )
        phase_info = find_phase(project_root, str(current_phase))
        if phase_info is None:
            _error(
                f"No CONTEXT.md could be resolved: phase {current_phase!r} not found."
            )
        phase_dir = project_root / phase_info.directory
        resolved = _find_phase_artifact_path(phase_dir, CONTEXT_SUFFIX, STANDALONE_CONTEXT)
        if resolved is None:
            _error(f"No CONTEXT.md found under {phase_dir}.")
    else:
        resolved = path.expanduser().resolve(strict=False)
        if not resolved.is_file():
            _error(f"CONTEXT file not found: {resolved}")
    typer.echo(context_guidance_fingerprint(resolved.read_text(encoding="utf-8")))


@contract_app.command("alignment-summary")
def contract_alignment_summary_cmd() -> None:
    """Print the claim-deliverable alignment row projection as JSON."""
    from gpd.core.contract_validation import claim_deliverable_alignment_summary
    from gpd.core.state import _load_project_contract_for_runtime_context

    project_root = _require_project_root(_get_cwd(), command_label="gpd contract commands")
    contract, _load_info = _load_project_contract_for_runtime_context(project_root)
    if contract is None:
        _error("No project contract is available; cannot render alignment summary.")
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


@phase_app.command("list")
def phase_list(
    file_type: str | None = typer.Option(None, "--type", help="File type filter"),
    phase: str | None = typer.Option(None, "--phase", help="Phase filter"),
) -> None:
    """List phases and their files."""
    from gpd.core.phases import list_phase_files, list_phases

    if file_type or phase:
        _output(list_phase_files(_get_cwd(), file_type=file_type or "plan", phase=phase))
    else:
        _output(list_phases(_get_cwd()))


@phase_app.command("add")
def phase_add(
    description: list[str] = typer.Argument(..., help="Phase description"),
) -> None:
    """Add a new phase to the end of the roadmap."""
    from gpd.core.phases import phase_add

    _output(phase_add(_get_cwd(), " ".join(description)))


@phase_app.command("insert")
def phase_insert(
    after_phase: str = typer.Argument(..., help="Phase number to insert after"),
    description: list[str] = typer.Argument(..., help="Phase description"),
) -> None:
    """Insert a new phase after an existing one."""
    from gpd.core.phases import phase_insert

    _output(phase_insert(_get_cwd(), after_phase, " ".join(description)))


@phase_app.command("remove")
def phase_remove(
    phase_num: str = typer.Argument(..., help="Phase number to remove"),
    force: bool = typer.Option(False, "--force", help="Force removal even if completed"),
) -> None:
    """Remove a phase from the roadmap."""
    from gpd.core.phases import phase_remove

    _output(phase_remove(_get_cwd(), phase_num, force=force))


@phase_app.command("complete")
def phase_complete(
    phase_num: str = typer.Argument(..., help="Phase number to mark complete"),
) -> None:
    """Mark a phase as complete."""
    from gpd.core.phases import phase_complete

    _output(phase_complete(_get_cwd(), phase_num))


@phase_app.command("index")
def phase_plan_index(
    phase_num: str = typer.Argument(..., help="Phase number"),
) -> None:
    """Show plan index for a phase (plans, waves, dependencies)."""
    from gpd.core.phases import phase_plan_index

    _output(phase_plan_index(_get_cwd(), phase_num))


@phase_app.command("find")
def phase_find(
    phase_num: str = typer.Argument(..., help="Phase number to find"),
) -> None:
    """Find a phase directory and its metadata."""
    from gpd.core.phases import find_phase

    result = find_phase(_get_cwd(), phase_num)
    if result is None:
        _error(f"Phase {phase_num} not found")
    _output(result)


@phase_app.command("next-decimal")
def phase_next_decimal(
    base_phase: str = typer.Argument(..., help="Base phase number"),
) -> None:
    """Get the next available decimal phase number (e.g. 42 → 42.1)."""
    from gpd.core.phases import next_decimal_phase

    _output(next_decimal_phase(_get_cwd(), base_phase))


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

    result = validate_phase_waves(_get_cwd(), phase_num)
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

    _output(milestone_complete(_get_cwd(), version, name=name))


# ═══════════════════════════════════════════════════════════════════════════
# resume — Read-only recovery summary
# ═══════════════════════════════════════════════════════════════════════════


def _resume_status_message(payload: dict[str, object], *, recovery_advice: RecoveryAdvice) -> str:
    """Return a concise human summary of resume readiness for this workspace."""
    auto_selected = _payload_flag(payload, "project_root_auto_selected")
    if not _payload_flag(payload, "planning_exists"):
        return "No GPD planning directory is present in this workspace."
    if not any(_payload_flag(payload, key) for key in ("state_exists", "roadmap_exists", "project_exists")):
        return "Planning scaffolding exists, but there is no recoverable project state yet."

    if recovery_advice.status == "bounded-segment":
        if auto_selected:
            return "A bounded segment is resumable from an auto-selected recent project."
        return "A bounded segment is resumable from the current workspace state."
    if recovery_advice.status == "interrupted-agent":
        return "An interrupted agent marker is present, but no bounded resume segment is active."
    if recovery_advice.status == "session-handoff":
        return "A continuity handoff is available, but no resumable bounded segment is currently active."
    if recovery_advice.status == "missing-handoff":
        return "Canonical recovery metadata exists, but the continuity handoff file is missing."
    if recovery_advice.status == "live-execution":
        return "A live execution snapshot exists, but it is advisory only and does not expose a portable bounded-segment target."
    if recovery_advice.status == "workspace-recovery" and recovery_advice.machine_change_notice:
        return "A machine change was detected, but the project state is portable and does not require repair."
    if recovery_advice.status == "workspace-recovery":
        return "Current workspace has recorded recovery context to inspect."
    if recovery_advice.machine_change_notice:
        return "A machine change was detected, but the project state is portable and does not require repair."
    return "No recent local recovery target is currently recorded."


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
    if not isinstance(value, str) or not value.strip():
        return "none"
    return value.replace("_", " ")


def _resume_status_label(status: object) -> str:
    """Return a canonical human label for one recovery status."""
    labels = {
        "bounded-segment": "Bounded segment",
        "interrupted-agent": "Interrupted agent",
        "session-handoff": "Continuity handoff",
        "missing-handoff": "Missing continuity handoff",
        "live-execution": "Advisory live execution",
        "workspace-recovery": "Recovery context",
        "recent-projects": "Recent projects",
        "recovery-error": "Recovery error",
        "no-recovery": "No recovery target",
    }
    status_text = str(status).strip() if status is not None else ""
    return labels.get(status_text, status_text.replace("_", " ") if status_text else "Unknown")


def _project_root_source_label(source: object, *, auto_selected: bool = False) -> str:
    """Map a project-root source to a plain-language re-entry label."""
    labels = {
        "current_workspace": "current workspace",
        "workspace": "current workspace",
        "recent_project": "machine-local recent-project index",
    }
    source_text = str(source).strip() if source is not None else ""
    label = labels.get(source_text, source_text.replace("_", " ") if source_text else "unknown")
    if source_text == "recent_project":
        if auto_selected:
            return f"auto-selected recent project (unique recoverable match from the {label})"
        return f"recent project selected explicitly from the {label}"
    return label


def _resume_candidate_canonical_kind(candidate: dict[str, object]) -> str:
    """Return the canonical family name for one resume candidate."""
    return resume_candidate_kind(candidate) or "unknown"


def _resume_candidate_kind_label(candidate: dict[str, object]) -> str:
    """Map one resume candidate to a user-facing kind label."""
    kind = _resume_candidate_canonical_kind(candidate)
    labels = {
        "bounded_segment": "Bounded segment",
        "continuity_handoff": "Continuity handoff",
        "interrupted_agent": "Interrupted agent",
    }
    return labels.get(kind, kind.replace("_", " ") if kind else "unknown")


def _resume_candidate_kind(source: object, *, status: object) -> str:
    """Return a stable machine label for the candidate concept."""
    source_text = str(source).strip() if source is not None else ""
    _ = str(status).strip() if status is not None else ""
    return resume_candidate_kind_from_source(source_text) or "unknown"


def _resume_origin_label(origin: object) -> str:
    """Map one canonical resume origin to a user-facing label."""
    labels = {
        "canonical_continuation": "canonical continuation",
        "derived_execution_head": "derived execution head",
        "interrupted_agent": "interrupted agent",
    }
    origin_text = str(origin).strip() if origin is not None else ""
    if not origin_text:
        return "Unknown"
    return labels.get(origin_text, "Unknown")


def _public_resume_origin_family(
    origin: object,
    *,
    source: object = None,
    active_execution: dict[str, object] | None = None,
    current_execution: dict[str, object] | None = None,
) -> str | None:
    """Collapse internal resume-origin tokens into the public resume-origin families."""

    origin_text = str(origin).strip() if origin is not None else ""
    if origin_text in {"canonical_continuation", "derived_execution_head", "interrupted_agent"}:
        return origin_text

    normalized_source = str(source).strip() if source is not None else ""

    if normalized_source == "current_execution":
        return "canonical_continuation" if isinstance(active_execution, dict) else "derived_execution_head"
    if normalized_source == "session_resume_file":
        return "canonical_continuation"
    if normalized_source == "interrupted_agent":
        return "interrupted_agent"

    if origin_text == "current_execution":
        return "canonical_continuation" if isinstance(active_execution, dict) else "derived_execution_head"
    if origin_text == "session_resume_file":
        return "canonical_continuation"
    if origin_text in {"continuation.bounded_segment", "continuation.handoff"}:
        return "canonical_continuation"
    if origin_text == "interrupted_agent_marker":
        return "interrupted_agent"
    return None


def _resume_authoritative_active_execution(
    payload: dict[str, object],
) -> dict[str, object] | None:
    """Return the bounded segment only when it comes from canonical continuation."""
    active_bounded_segment_raw = _resume_surface_value(payload, "active_bounded_segment")
    if not isinstance(active_bounded_segment_raw, dict):
        return None

    active_origin = payload.get("active_resume_origin")
    if not isinstance(active_origin, str) or not active_origin.strip():
        active_origin = _resume_surface_value(payload, "active_resume_origin")

    if str(active_origin).strip() in {"canonical_continuation", "continuation.bounded_segment"}:
        return active_bounded_segment_raw
    return None


def _resume_candidate_phase_plan(candidate: dict[str, object]) -> str:
    """Format phase/plan context for one resume candidate."""
    phase = candidate.get("phase")
    plan = candidate.get("plan")
    phase_text = str(phase).strip() if phase is not None else ""
    plan_text = str(plan).strip() if plan is not None else ""
    if phase_text and plan_text:
        return f"{phase_text} / {plan_text}"
    if phase_text:
        return phase_text
    if plan_text:
        return plan_text
    return "—"


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
    candidates = lookup_resume_surface_list(payload, "resume_candidates")
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def _resume_candidate_target(candidate: dict[str, object]) -> str:
    """Format the primary target/pointer for one resume candidate."""
    source = str(candidate.get("source") or "").strip()
    if source == "interrupted_agent":
        agent_id = candidate.get("agent_id")
        return str(agent_id).strip() if agent_id is not None and str(agent_id).strip() else "—"

    resume_file = candidate.get("resume_file")
    if isinstance(resume_file, str) and resume_file.strip():
        return _format_display_path(resume_file.strip())
    return "—"


def _resume_candidate_rerun_anchor(candidate: dict[str, object]) -> str | None:
    """Return the canonical rerun anchor note for one candidate, if any."""
    last_result_id = candidate.get("last_result_id")
    last_result_label = candidate.get("last_result_label")
    if not isinstance(last_result_id, str) or not last_result_id.strip():
        if isinstance(last_result_label, str) and last_result_label.strip():
            return f"last result: {last_result_label.strip()}"
        return None

    last_result_id_text = last_result_id.strip()
    if isinstance(last_result_label, str) and last_result_label.strip():
        return f"rerun anchor: {last_result_label.strip()} ({last_result_id_text})"
    return f"rerun anchor: {last_result_id_text}"


def _resume_result_payload(value: object) -> dict[str, object] | None:
    """Normalize a hydrated result payload into a plain dictionary."""
    if hasattr(value, "model_dump"):
        try:
            value = value.model_dump(mode="json")
        except Exception:
            return None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _resume_result_summary(result: Mapping[str, object] | None, *, include_id: bool = True) -> str | None:
    """Render a concise human summary for one hydrated intermediate result."""
    if not isinstance(result, Mapping):
        return None

    result_id = _recent_project_text(result, "id")
    description = _recent_project_text(result, "description", "label", "name", "title")
    equation = _recent_project_text(result, "equation")
    if description and equation:
        summary = f"{description} [{equation}]"
    elif description:
        summary = description
    elif equation:
        summary = equation
    elif result_id:
        summary = result_id
    else:
        return None

    if include_id and result_id and summary != result_id:
        summary = f"{summary} ({result_id})"
    if _strict_bool_value(result.get("verified")) is True or bool(result.get("verification_records")):
        summary = f"{summary} · verified"
    return summary


def _resume_candidate_last_result(
    candidate: dict[str, object],
    *,
    payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    """Return the hydrated last-result payload for one candidate, if available."""
    result = _resume_result_payload(candidate.get("last_result"))
    if result is not None:
        return result

    if payload is None:
        return None

    last_result_id = _recent_project_text(candidate, "last_result_id")
    if not isinstance(last_result_id, str) or not last_result_id.strip():
        return None

    active_result = _resume_result_payload(_resume_surface_value(payload, "active_resume_result"))
    if active_result is not None and _recent_project_text(active_result, "id") == last_result_id:
        return active_result

    derived_results = _resume_surface_value(payload, "derived_intermediate_results")
    if isinstance(derived_results, list):
        for item in derived_results:
            result = _resume_result_payload(item)
            if result is not None and _recent_project_text(result, "id") == last_result_id:
                return result

    return None


def _resume_active_result(
    payload: dict[str, object],
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the most relevant hydrated result for the current resume view."""
    active_result = _resume_result_payload(_resume_surface_value(payload, "active_resume_result"))
    if active_result is not None:
        return active_result

    for candidate in candidates:
        result = _resume_candidate_last_result(candidate, payload=payload)
        if result is not None:
            return result

    return None


def _resume_candidate_origin(
    candidate: dict[str, object],
    *,
    active_execution: dict[str, object] | None,
    current_execution: dict[str, object] | None,
) -> tuple[str, str]:
    """Return a machine label and human summary for one candidate origin."""
    origin = candidate.get("origin")
    source = str(candidate.get("source") or "").strip()
    public_origin = _public_resume_origin_family(
        origin,
        source=source,
        active_execution=active_execution,
        current_execution=current_execution,
    )
    if public_origin is not None and source != "current_execution":
        return public_origin, _resume_origin_label(public_origin)
    status = str(candidate.get("status") or "").strip()
    if source == "current_execution":
        active_resume = (
            str(active_execution.get("resume_file")).strip()
            if isinstance(active_execution, dict) and active_execution.get("resume_file") is not None
            else ""
        )
        current_resume = (
            str(current_execution.get("resume_file")).strip()
            if isinstance(current_execution, dict) and current_execution.get("resume_file") is not None
            else ""
        )
        if isinstance(active_execution, dict):
            if active_resume and current_resume and active_resume != current_resume:
                return (
                    "canonical_continuation",
                    "canonical continuation; current execution points at a different handoff file",
                )
            return ("canonical_continuation", "canonical continuation")
        if isinstance(current_execution, dict):
            return ("derived_execution_head", "derived execution head")
        return ("derived_execution_head", "derived execution head")
    if source == "session_resume_file":
        if status == "missing":
            return ("canonical_continuation", "canonical continuation; handoff file missing")
        return ("canonical_continuation", "canonical continuation")
    if source == "interrupted_agent":
        return ("interrupted_agent", "interrupted-agent marker")
    return ("unknown", "unknown origin")


def _recent_project_label(row: dict[str, object]) -> str | None:
    """Return an optional human label for one recent-project row."""
    return _recent_project_text(row, "label", "title", "project_label", "project_title", "name")


def _recent_project_summary(row: dict[str, object]) -> str | None:
    """Return an optional human summary for one recent-project row."""
    return _recent_project_text(row, "summary", "project_summary", "description", "project_description")


def _recent_project_current_state(row: dict[str, object]) -> str | None:
    """Return an optional phase/status/progress summary for one recent-project row."""
    current_phase = row.get("current_phase")
    if isinstance(current_phase, dict):
        phase = _recent_project_text(current_phase, "phase", "id", "number", "name", "title")
        phase_label = _recent_project_text(current_phase, "label", "name", "title")
        status = _recent_project_text(current_phase, "status", "state")
        progress = _recent_project_text(current_phase, "progress", "progress_summary", "summary")
        pieces: list[str] = []
        if phase and phase_label and phase_label != phase:
            pieces.append(f"phase {phase} ({phase_label})")
        elif phase_label:
            pieces.append(phase_label)
        elif phase:
            pieces.append(f"phase {phase}" if not phase.lower().startswith("phase") else phase)
        if status is not None:
            pieces.append(status.replace("_", " "))
        if progress is not None:
            pieces.append(progress)
        return " · ".join(pieces) if pieces else None

    phase = _recent_project_text(row, "current_phase", "phase")
    phase_label = _recent_project_text(row, "current_phase_name", "phase_name")
    status = _recent_project_text(row, "project_status", "status")
    progress = _recent_project_text(row, "progress", "progress_summary", "phase_progress")
    pieces: list[str] = []
    if phase and phase_label and phase_label != phase:
        pieces.append(f"phase {phase} ({phase_label})")
    elif phase_label:
        pieces.append(phase_label)
    elif phase:
        pieces.append(f"phase {phase}" if not phase.lower().startswith("phase") else phase)
    if status is not None and status.replace("_", " ") not in {"recent", "resumable", "unavailable"}:
        pieces.append(status.replace("_", " "))
    if progress is not None:
        pieces.append(progress)
    return " · ".join(pieces) if pieces else None


def _recent_project_selection_reason(row: dict[str, object]) -> str:
    """Return a plain-language explanation for why a recent-project row is shown."""
    if _strict_bool_value(row.get("available")) is not True:
        reason = row.get("availability_reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
        return "shown because the project root is missing on this machine"
    if _strict_bool_value(row.get("resumable")) is True:
        reason = row.get("resume_file_reason")
        if isinstance(reason, str) and reason.strip():
            return f"shown because it still has a usable handoff target ({reason.strip()})"
        return "shown because it still has a usable handoff target"
    resume_file = row.get("resume_file")
    if isinstance(resume_file, str) and resume_file.strip():
        return "shown because the checkout is available, but the recorded handoff is not currently usable"
    return "shown because the checkout is available, but no recovery handoff is recorded"


def _resume_candidate_notes(
    candidate: dict[str, object],
    *,
    payload: dict[str, object] | None = None,
    active_execution: dict[str, object] | None = None,
    current_execution: dict[str, object] | None = None,
) -> str:
    """Render the most relevant resume notes for one candidate."""
    notes: list[str] = []

    checkpoint_reason = candidate.get("checkpoint_reason")
    if isinstance(checkpoint_reason, str) and checkpoint_reason.strip():
        notes.append(f"checkpoint: {checkpoint_reason.strip().replace('_', ' ')}")

    waiting_reason = candidate.get("waiting_reason")
    if isinstance(waiting_reason, str) and waiting_reason.strip():
        notes.append(waiting_reason.strip())

    blocked_reason = candidate.get("blocked_reason")
    if isinstance(blocked_reason, str) and blocked_reason.strip():
        notes.append(f"blocked: {blocked_reason.strip()}")

    hydrated_result = _resume_candidate_last_result(candidate, payload=payload)
    if hydrated_result is not None:
        hydrated_summary = _resume_result_summary(hydrated_result)
        if hydrated_summary is not None:
            notes.append(f"result: {hydrated_summary}")
    else:
        rerun_anchor = _resume_candidate_rerun_anchor(candidate)
        if rerun_anchor is not None:
            notes.append(rerun_anchor)

    if _strict_bool_value(candidate.get("first_result_gate_pending")) is True:
        notes.append("first-result gate pending")
    if _strict_bool_value(candidate.get("pre_fanout_review_pending")) is True:
        notes.append("pre-fanout review pending")
    if _strict_bool_value(candidate.get("skeptical_requestioning_required")) is True:
        notes.append("skeptical re-questioning required")
    if _strict_bool_value(candidate.get("downstream_locked")) is True:
        notes.append("downstream locked")

    execution_view = current_execution or active_execution
    if execution_view is not None:
        current_task = execution_view.get("current_task")
        current_task_index = execution_view.get("current_task_index")
        current_task_total = execution_view.get("current_task_total")
        if isinstance(current_task, str) and current_task.strip():
            if current_task_index is not None and current_task_total is not None:
                notes.append(f"task {current_task_index}/{current_task_total}: {current_task.strip()}")
            else:
                notes.append(current_task.strip())

        updated_at = execution_view.get("updated_at")
        if isinstance(updated_at, str) and updated_at.strip():
            notes.append(f"updated {updated_at.strip()}")

    if not notes:
        kind = _resume_candidate_canonical_kind(candidate)
        status = str(candidate.get("status") or "").strip()
        if kind == "continuity_handoff" and status == "missing":
            return "Recorded in canonical continuation state, but the handoff file is missing from this workspace."
        if kind == "continuity_handoff":
            return "Recorded in canonical continuation state."
        if kind == "interrupted_agent":
            return "Interrupted agent marker only; inspect agent output before continuing."
        return "No additional resume notes recorded."
    return "; ".join(notes[:5])


def _resume_candidate_projection(
    candidate: dict[str, object],
    *,
    payload: dict[str, object] | None = None,
    active_execution: dict[str, object] | None = None,
    current_execution: dict[str, object] | None = None,
) -> dict[str, object]:
    """Project one raw candidate into a canonical recovery view."""
    origin, origin_label = _resume_candidate_origin(
        candidate,
        active_execution=active_execution,
        current_execution=current_execution,
    )
    status = str(candidate.get("status") or "unknown").strip() or "unknown"
    kind = _resume_candidate_canonical_kind(candidate)
    if kind == "unknown":
        kind = _resume_candidate_kind(candidate.get("source"), status=status)
    return {
        "kind": kind,
        "kind_label": _resume_candidate_kind_label(candidate),
        "status": status,
        "status_label": status.replace("_", " "),
        "origin": origin,
        "origin_label": origin_label,
        "phase_plan": _resume_candidate_phase_plan(candidate),
        "target": _resume_candidate_target(candidate),
        "notes": _resume_candidate_notes(
            candidate,
            payload=payload,
            active_execution=active_execution,
            current_execution=current_execution,
        ),
        "source": candidate.get("source"),
        "resume_file": candidate.get("resume_file"),
        "resumable": candidate.get("resumable"),
        "advisory": candidate.get("advisory"),
    }


def _recent_project_resume_file_state(project_root: object, resume_file: object) -> tuple[bool | None, str | None]:
    """Return whether a recent-project handoff file is still usable."""
    if not isinstance(project_root, str) or not project_root.strip():
        return None, None
    if not isinstance(resume_file, str) or not resume_file.strip():
        return None, None

    project_path = Path(project_root).expanduser()
    try:
        project_exists = project_path.exists()
        project_is_dir = project_path.is_dir()
    except OSError:
        return False, "project unavailable on this machine"
    if not project_exists or not project_is_dir:
        return None, None

    try:
        resolved_project = project_path.resolve(strict=False)
    except OSError:
        return False, "project unavailable on this machine"
    candidate = Path(resume_file).expanduser()
    try:
        resolved_target = (
            candidate.resolve(strict=False) if candidate.is_absolute() else (project_path / candidate).resolve(strict=False)
        )
    except OSError:
        return False, "resume file unavailable"
    try:
        resolved_target.relative_to(resolved_project)
    except ValueError:
        return False, "resume file outside project root"
    try:
        target_exists = resolved_target.exists()
        target_is_file = resolved_target.is_file()
    except OSError:
        return False, "resume file unavailable"
    if not target_exists:
        return False, "resume file missing"
    if not target_is_file:
        return False, "resume file is not a file"
    return True, None


def _recent_projects_data_root() -> Path:
    """Return the machine-local home data root for cross-project recovery metadata."""
    configured = os.environ.get(ENV_DATA_DIR, "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / HOME_DATA_DIR_NAME


def _recent_project_text(payload: dict[str, object], *keys: str) -> str | None:
    """Return the first non-empty string value among *keys*."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _normalize_recent_project_row(row: object) -> dict[str, object] | None:
    """Project one canonical recent-project row into the CLI display shape."""
    if not isinstance(row, dict):
        return None

    from gpd.core.recent_projects import RecentProjectEntry

    project_root = _recent_project_text(row, "project_root")
    if project_root is None:
        unexpected_fields = sorted(key for key in row if key not in RecentProjectEntry.model_fields)
        if unexpected_fields:
            formatted = ", ".join(unexpected_fields)
            raise ValueError(f"recent-project row contains unexpected field(s): {formatted}")
        return None

    project_path = Path(project_root).expanduser()
    available_value = row.get("available")
    if isinstance(available_value, bool):
        available = available_value
        derived_availability_reason = None
    else:
        try:
            available = project_path.is_dir()
        except OSError:
            available = False
            derived_availability_reason = "project unavailable on this machine"
        else:
            if available:
                derived_availability_reason = None
            else:
                try:
                    project_exists = project_path.exists()
                except OSError:
                    derived_availability_reason = "project unavailable on this machine"
                else:
                    derived_availability_reason = "project root is not a directory" if project_exists else "project root missing"
    normalized: dict[str, object] = {
        "project_root": project_root,
        "workspace": _format_display_path(project_path),
        "available": available,
        "missing": not available,
    }
    if not available:
        normalized["command"] = "unavailable"
    elif project_path.is_absolute():
        try:
            resolved_project_path = project_path.resolve(strict=False)
        except OSError:
            normalized["command"] = "unavailable"
        else:
            normalized["command"] = f"gpd --cwd {shlex.quote(str(resolved_project_path))} resume"
    else:
        normalized["command"] = None

    for key in (
        "schema_version",
        "last_session_at",
        "last_seen_at",
        "stopped_at",
        "resume_file",
        "resume_file_available",
        "resume_file_reason",
        "status",
        "resumable",
        "availability_reason",
        "last_result_id",
        "resume_target_kind",
        "resume_target_recorded_at",
        "hostname",
        "platform",
        "source_kind",
        "source_session_id",
        "source_segment_id",
        "source_transition_id",
        "source_event_id",
        "source_recorded_at",
        "recovery_phase",
        "recovery_plan",
    ):
        if key in row:
            normalized[key] = row[key]
    if derived_availability_reason is not None and not normalized.get("availability_reason"):
        normalized["availability_reason"] = derived_availability_reason

    resume_file_available, resume_file_reason = _recent_project_resume_file_state(
        normalized.get("project_root"),
        normalized.get("resume_file"),
    )
    if resume_file_available is not None:
        normalized["resume_file_available"] = resume_file_available
    if resume_file_reason is not None:
        normalized["resume_file_reason"] = resume_file_reason

    resumable_value = normalized.get("resumable")
    if resumable_value is None:
        resumable_value = normalized.get("resume_file") if isinstance(normalized.get("resume_file"), str) else False
    else:
        resumable_value = _strict_bool_value(resumable_value) is True
    normalized["resumable"] = (
        bool(resumable_value)
        and _strict_bool_value(normalized["available"]) is True
        and normalized.get("resume_file_available") is not False
    )
    status = _recent_project_text(normalized, "status")
    if _strict_bool_value(normalized["available"]) is not True:
        status = "unavailable"
    elif status is None:
        status = "resumable" if normalized["resumable"] else "recent"
    normalized["status"] = status

    return normalized


def _recent_project_sort_key(row: dict[str, object]) -> tuple[int, int, int, int, str, str]:
    """Sort recent rows by recovery strength first, then by recency."""
    candidate = _candidate_from_recent_row(row)
    if candidate is None:
        return (0, 0, 0, 0, "", "")
    return _candidate_sort_key(candidate)


def _load_recent_projects_rows(*, last: int | None = None) -> list[dict[str, object]]:
    """Load the recent-project index, preferring the shared helper module when present."""
    from gpd.core.recent_projects import RecentProjectsError, list_recent_projects

    try:
        raw_rows = list_recent_projects(_recent_projects_data_root(), last=last)
    except RecentProjectsError as exc:
        raise GPDError(str(exc)) from exc

    rows: list[dict[str, object]] = []
    for row in raw_rows:
        row_payload = row.model_dump(mode="json") if hasattr(row, "model_dump") else row
        try:
            normalized = _normalize_recent_project_row(row_payload)
        except ValueError as exc:
            raise GPDError(str(exc)) from exc
        if normalized is None:
            raise GPDError("recent-project cache returned a malformed canonical row")
        rows.append(normalized)

    rows.sort(key=_recent_project_sort_key, reverse=True)
    return rows


def _resume_recent_project_command(row: dict[str, object]) -> str:
    """Return the exact command to reopen one recent project."""
    project_root = row.get("project_root")
    if not isinstance(project_root, str) or not project_root.strip():
        return "unavailable"
    if row.get("available") is not True:
        return "unavailable"
    try:
        project_path = Path(project_root).expanduser().resolve(strict=False)
    except OSError:
        return "unavailable"
    return f"gpd --cwd {shlex.quote(str(project_path))} resume"


def _resume_recent_project_notes(row: dict[str, object]) -> str:
    """Return a concise availability/resumability note for one recent project row."""
    recovery_note = _recent_project_text(row, "recovery_note")
    if recovery_note is not None:
        return recovery_note
    if _strict_bool_value(row.get("available")) is not True:
        reason = row.get("availability_reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
        return "project unavailable on this machine"
    if _strict_bool_value(row.get("resumable")) is True:
        return "ready to reopen"
    reason = row.get("resume_file_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return "continue from local recovery state"


def _recent_project_recovery_view(row: dict[str, object]) -> dict[str, object] | None:
    """Return a canonical recovery summary for one recent-project row when available."""
    project_root = row.get("project_root")
    if not isinstance(project_root, str) or not project_root.strip():
        return None

    try:
        project_path = Path(project_root).expanduser().resolve(strict=False)
        project_exists = project_path.exists()
        project_is_dir = project_path.is_dir()
    except OSError:
        project_path = Path(project_root).expanduser()
        project_exists = False
        project_is_dir = False
    if not project_exists or not project_is_dir:
        return {
            "recovery_status": "no-recovery",
            "recovery_status_label": "Unavailable checkout",
            "recovery_note": "project unavailable on this machine",
        }

    try:
        state_exists, roadmap_exists, project_exists = recoverable_project_context(project_path)
    except OSError:
        return {
            "recovery_status": "no-recovery",
            "recovery_status_label": "Unavailable checkout",
            "recovery_note": "project unavailable on this machine",
        }
    if not (state_exists or roadmap_exists or project_exists):
        return None

    try:
        from gpd.core.context import init_resume

        payload = init_resume(project_path)
        advice = _resume_recovery_advice(resume_payload=payload, recent_rows=[], cwd=project_path)
    except Exception as exc:
        error_message = str(exc).strip() or type(exc).__name__
        return {
            "recovery_status": "recovery-error",
            "recovery_status_label": _resume_status_label("recovery-error"),
            "recovery_note": f"Recovery metadata could not be inspected: {error_message}",
            "recovery_error": error_message,
            "recovery_error_type": type(exc).__name__,
        }

    public_payload = canonicalize_resume_public_payload(payload)
    view: dict[str, str] = {
        "recovery_status": advice.status,
        "recovery_status_label": _resume_status_label(advice.status),
        "recovery_note": _resume_status_message(public_payload, recovery_advice=advice),
    }
    primary_resume_file = _resume_surface_value(public_payload, "active_resume_pointer")
    if isinstance(primary_resume_file, str) and primary_resume_file.strip():
        view["recovery_target"] = _format_display_path(primary_resume_file.strip())
    execution_source = _resume_surface_value(public_payload, "active_resume_origin")
    public_origin = _public_resume_origin_family(execution_source, active_execution=None, current_execution=None)
    if public_origin is not None:
        view["recovery_origin"] = _resume_origin_label(public_origin)
    return view


def _annotate_recent_project_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Add canonical recovery summaries to recent-project rows while keeping existing fields."""
    annotated: list[dict[str, object]] = []
    for row in rows:
        payload = dict(row)
        recovery_view = _recent_project_recovery_view(payload)
        if recovery_view is not None:
            payload.update(recovery_view)
        annotated.append(payload)
    return annotated


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
    derived_execution_head_raw = _resume_surface_value(public_payload, "derived_execution_head")
    derived_execution_head = derived_execution_head_raw if isinstance(derived_execution_head_raw, dict) else None
    active_execution = _resume_authoritative_active_execution(public_payload)
    current_execution = derived_execution_head
    active_resume_kind = public_payload.get("active_resume_kind")
    if isinstance(active_resume_kind, str) and active_resume_kind.strip():
        active_resume_kind = _resume_candidate_canonical_kind({"kind": active_resume_kind})
    segment_candidates = _resume_visible_candidates(public_payload)
    projected_candidates = [
        _resume_candidate_projection(
            candidate,
            payload=public_payload,
            active_execution=active_execution
            if _resume_candidate_canonical_kind(candidate) == "bounded_segment"
            else None,
            current_execution=current_execution
            if _resume_candidate_canonical_kind(candidate) == "bounded_segment"
            else None,
        )
        for candidate in segment_candidates
    ]
    active_resume_result = _resume_active_result(public_payload, segment_candidates)
    augmented = dict(public_payload)
    active_resume_origin = augmented.get("active_resume_origin")
    if isinstance(active_resume_origin, str) and active_resume_origin.strip():
        public_active_origin = _public_resume_origin_family(
            active_resume_origin,
            active_execution=active_execution,
            current_execution=current_execution,
        )
        if public_active_origin is not None:
            augmented["active_resume_origin"] = public_active_origin
    normalized_resume_candidates: list[dict[str, object]] = []
    for candidate in list(augmented.get("resume_candidates") or []):
        if not isinstance(candidate, dict):
            continue
        normalized_candidate = dict(candidate)
        candidate_origin = normalized_candidate.get("origin")
        public_candidate_origin = _public_resume_origin_family(
            candidate_origin,
            source=normalized_candidate.get("source"),
            active_execution=active_execution
            if _resume_candidate_canonical_kind(normalized_candidate) == "bounded_segment"
            else None,
            current_execution=current_execution
            if _resume_candidate_canonical_kind(normalized_candidate) == "bounded_segment"
            else None,
        )
        if public_candidate_origin is not None:
            normalized_candidate["origin"] = public_candidate_origin
        normalized_resume_candidates.append(normalized_candidate)
    augmented["resume_candidates"] = normalized_resume_candidates
    augmented["recovery_status"] = recovery_advice.status
    augmented["recovery_status_label"] = _resume_status_label(recovery_advice.status)
    augmented["recovery_summary"] = _resume_status_message(public_payload, recovery_advice=recovery_advice)
    augmented["active_resume_kind_label"] = _resume_mode_label(active_resume_kind)
    recovery_advice_payload = serialize_recovery_advice(recovery_advice)
    advice_origin = recovery_advice_payload.get("active_resume_origin")
    if isinstance(advice_origin, str) and advice_origin.strip():
        public_advice_origin = _public_resume_origin_family(
            advice_origin,
            active_execution=active_execution,
            current_execution=current_execution,
        )
        if public_advice_origin is not None:
            recovery_advice_payload["active_resume_origin"] = public_advice_origin
    augmented["recovery_advice"] = recovery_advice_payload
    augmented["recovery_candidates"] = projected_candidates
    if active_resume_result is not None and "active_resume_result_summary" not in augmented:
        active_resume_result_summary = _resume_result_summary(active_resume_result)
        if active_resume_result_summary is not None:
            augmented["active_resume_result_summary"] = active_resume_result_summary
    if projected_candidates:
        augmented["primary_recovery_target"] = projected_candidates[0]
    return augmented


def _render_recent_resume_summary(rows: list[dict[str, object]]) -> None:
    """Render the recent-project picker for cross-project recovery."""
    console.print("[bold]Recent Projects[/]")
    console.print(
        "[dim]Machine-local recovery index. Recent projects are ordered by recovery strength, then recency. A single recoverable match can auto-select; otherwise choose explicitly with the command shown for each row.[/]"
    )
    console.print()

    if not rows:
        console.print("[dim]No recent projects are recorded on this machine yet.[/]")
        console.print(
            f"[dim]Run `{local_cli_resume_command()}` inside a project first, or wait for session continuity to be recorded.[/]"
        )
        return

    for idx, row in enumerate(rows, start=1):
        label = _recent_project_label(row)
        summary = _recent_project_summary(row)
        current_state = _recent_project_current_state(row)
        console.print(
            f"[bold]{idx}.[/] "
            f"{str(row.get('workspace') or _format_display_path(str(row.get('project_root') or '')) or 'unknown')}"
        )
        if label is not None:
            console.print(f"   Label: {label}")
        if summary is not None:
            console.print(f"   Summary: {summary}")
        if current_state is not None:
            console.print(f"   Current: {current_state}")
        console.print(f"   Last session: {str(row.get('last_session_at') or row.get('last_seen_at') or '—')}")
        console.print(f"   Stopped at: {str(row.get('stopped_at') or '—')}")
        recovery_label = _recent_project_text(row, "recovery_status_label")
        if recovery_label is not None:
            console.print(f"   Recovery: {recovery_label}")
        console.print(f"   Resumable: {'yes' if _strict_bool_value(row.get('resumable')) is True else 'no'}")
        console.print(f"   Why shown: {_recent_project_selection_reason(row)}")
        console.print(f"   Notes: {_resume_recent_project_notes(row)}")
        console.print(f"   Resume: {_resume_recent_project_command(row)}")
        console.print()
    console.print()
    console.print("[bold]Next here[/]")
    console.print("- Select a workspace above, then continue there with `resume-work`.")
    console.print("- After resuming, `suggest-next` is the fastest next action.")


def _render_resume_summary(payload: dict[str, object]) -> None:
    """Render a read-only local recovery summary for humans."""
    public_payload = canonicalize_resume_public_payload(payload)
    active_execution = _resume_authoritative_active_execution(public_payload)
    current_execution_raw = _resume_surface_value(public_payload, "derived_execution_head")
    current_execution = current_execution_raw if isinstance(current_execution_raw, dict) else None
    recovery_advice = _resume_recovery_advice(resume_payload=public_payload, recent_rows=[])
    segment_candidates = _resume_visible_candidates(public_payload)

    console.print("[bold]Resume Summary[/]")
    console.print("[dim]Read-only local recovery snapshot for this workspace.[/]")
    console.print()

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style=f"bold {_INSTALL_ACCENT_COLOR}")
    summary.add_column()
    workspace_root = public_payload.get("workspace_root")
    project_root = public_payload.get("project_root")
    project_label = _recent_project_text(public_payload, "project_label", "project_title", "project_name")
    project_summary = _recent_project_text(public_payload, "project_summary", "summary", "description")
    summary.add_row("Workspace", _format_display_path(str(workspace_root or _get_cwd())))
    if isinstance(project_root, str) and project_root.strip():
        summary.add_row("Project", _format_display_path(project_root.strip()))
    if isinstance(project_label, str) and project_label.strip():
        summary.add_row("Project label", project_label.strip())
    if isinstance(project_summary, str) and project_summary.strip():
        summary.add_row("Project summary", project_summary.strip())
    if _payload_flag(public_payload, "project_root_auto_selected"):
        summary.add_row(
            "Re-entry",
            _project_root_source_label(public_payload.get("project_root_source"), auto_selected=True),
        )
    elif (
        isinstance(public_payload.get("project_root_source"), str)
        and str(public_payload.get("project_root_source")).strip()
    ):
        summary.add_row(
            "Re-entry",
            _project_root_source_label(public_payload.get("project_root_source"), auto_selected=False),
        )
    summary.add_row("Status", _resume_status_message(public_payload, recovery_advice=recovery_advice))
    summary.add_row("Recovery", _resume_status_label(recovery_advice.status))
    active_resume_kind = public_payload.get("active_resume_kind")
    if isinstance(active_resume_kind, str) and active_resume_kind.strip():
        active_resume_kind = _resume_candidate_canonical_kind({"kind": active_resume_kind})
    summary.add_row("Primary resume kind", _resume_mode_label(active_resume_kind))
    summary.add_row("Candidates", str(len(segment_candidates)))
    summary.add_row("Live execution", "yes" if _payload_flag(public_payload, "has_live_execution") else "no")
    summary.add_row("Autonomy", str(public_payload.get("autonomy") or "unknown"))
    summary.add_row("Research mode", str(public_payload.get("research_mode") or "unknown"))

    paused_at = public_payload.get("execution_paused_at")
    if isinstance(paused_at, str) and paused_at.strip():
        summary.add_row("Paused at", paused_at.strip())

    primary_resume_file = _resume_surface_value(public_payload, "active_resume_pointer")
    if isinstance(primary_resume_file, str) and primary_resume_file.strip():
        summary.add_row("Primary pointer", _format_display_path(primary_resume_file.strip()))

    active_resume_result = _resume_active_result(public_payload, segment_candidates)
    active_resume_result_summary = _resume_result_summary(active_resume_result)
    if active_resume_result_summary is not None:
        summary.add_row("Resume result", active_resume_result_summary)

    console.print(summary)

    machine_change_notice = public_payload.get("machine_change_notice")
    notices: list[str] = []
    if isinstance(machine_change_notice, str) and machine_change_notice.strip():
        notices.append(machine_change_notice.strip())

    if active_execution is not None:
        if bool(active_execution.get("waiting_for_review")):
            notices.append("Execution is currently waiting for review before continuation.")
        if bool(public_payload.get("execution_pre_fanout_review_pending")):
            notices.append("Pre-fanout review is still pending.")
        if bool(public_payload.get("execution_skeptical_requestioning_required")):
            notices.append("Skeptical re-questioning is required before downstream work.")
        if bool(public_payload.get("execution_downstream_locked")):
            notices.append("Downstream work remains locked by the current execution snapshot.")
        blocked_reason = active_execution.get("blocked_reason")
        if isinstance(blocked_reason, str) and blocked_reason.strip():
            notices.append(f"Execution is blocked: {blocked_reason.strip()}")
    missing_continuity_handoff = _resume_surface_value(public_payload, "missing_continuity_handoff_file")
    if isinstance(missing_continuity_handoff, str) and missing_continuity_handoff.strip():
        notices.append(
            f"Projected continuity handoff is missing: {_format_display_path(missing_continuity_handoff.strip())}."
        )

    if notices:
        console.print()
        console.print("[bold]Notices[/]")
        for notice in notices:
            console.print(f"- {notice}")

    console.print()
    console.print("[bold]Resume Candidates[/]")
    console.print("[dim]Canonical candidate kinds: bounded_segment, continuity_handoff, interrupted_agent.[/]")
    if segment_candidates:
        table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
        table.add_column("#", justify="right", no_wrap=True)
        table.add_column("Kind")
        table.add_column("Status")
        table.add_column("Phase/Plan")
        table.add_column("Target")
        table.add_column("Origin")
        table.add_column("Notes")
        for idx, candidate in enumerate(segment_candidates, start=1):
            projected_candidate = _resume_candidate_projection(
                candidate,
                payload=public_payload,
                active_execution=active_execution
                if _resume_candidate_canonical_kind(candidate) == "bounded_segment"
                else None,
                current_execution=current_execution
                if _resume_candidate_canonical_kind(candidate) == "bounded_segment"
                else None,
            )
            table.add_row(
                str(idx),
                str(projected_candidate["kind"]),
                str(projected_candidate["status"]),
                str(projected_candidate["phase_plan"]),
                str(projected_candidate["target"]),
                str(projected_candidate["origin_label"]),
                str(projected_candidate["notes"]),
            )
        console.print(table)
    else:
        console.print(
            "[dim]No bounded_segment, continuity_handoff, or interrupted_agent candidate is currently recorded.[/]"
        )

    console.print()
    console.print("[bold]Recovery ladder[/]")
    console.print(f"- {recovery_resume_action()}")
    console.print(f"- {recovery_recent_action()}")
    console.print("- `gpd --raw resume` is the machine-readable local recovery surface.")
    hint = _resume_recent_hint(public_payload)
    if hint is not None:
        console.print(f"- {hint}")

    for line in _resume_follow_up_actions(recovery_advice):
        console.print(f"- {line}")


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
    if _stdout_is_interactive():
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

    cwd = _read_only_project_scoped_cwd()
    if not watch:
        _output(progress_render(cwd, fmt))
        return
    if fmt != "json":
        err_console.print(
            f"[dim]--watch overrides fmt={fmt!r} → 'json' for live execution rendering.[/dim]"
        )
        fmt = "json"
    try:
        _run_progress_watch_loop(cwd, fmt, interval, exit_on_idle)
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

    project_cwd = _project_scoped_cwd(cwd)
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

    report = run_health(_project_scoped_cwd(), fix=fix)
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

trace_app = typer.Typer(help="JSONL execution tracing for debugging and audit")
app.add_typer(trace_app, name="trace")


@trace_app.command("start")
def trace_start(
    phase: str = typer.Argument(..., help="Phase number"),
    plan: str = typer.Argument(..., help="Plan name"),
) -> None:
    """Start a new trace session."""
    from gpd.core.trace import trace_start

    _output(trace_start(_get_cwd(), phase, plan))


@trace_app.command("log")
def trace_log(
    event: str = typer.Argument(..., help="Event type"),
    data: str | None = typer.Option(None, "--data", help="JSON event data"),
) -> None:
    """Log an event to the active trace."""
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
    """Stop the active trace session."""
    from gpd.core.trace import trace_stop

    _output(trace_stop(_get_cwd()))


@trace_app.command("show")
def trace_show(
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase"),
    plan: str | None = typer.Option(None, "--plan", help="Filter by plan"),
    event_type: str | None = typer.Option(None, "--type", help="Filter by event type"),
    last: int | None = typer.Option(None, "--last", help="Show last N events"),
) -> None:
    """Show trace events with optional filters."""
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


observe_app = typer.Typer(help="Inspect local observability sessions, live execution status, and events")
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
    """List recorded local observability sessions."""
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
    """Append one local observability event."""
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
    """Show local observability events with optional filters."""
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
    """Export session logs and traces to files."""
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
# init — Workflow context assembly
# ═══════════════════════════════════════════════════════════════════════════

init_app = typer.Typer(help="Assemble context for AI agent workflows")
app.add_typer(init_app, name="init")

_INIT_EXECUTE_PHASE_INCLUDES = frozenset({"config", "roadmap", "state"})
_INIT_PLAN_PHASE_INCLUDES = frozenset(
    {"context", "requirements", "research", "roadmap", "state", "validation", "verification"}
)
_INIT_PHASE_OP_INCLUDES = frozenset({"config", "roadmap", "state"})
_INIT_PROGRESS_INCLUDES = frozenset({"config", "project", "roadmap", "state"})


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
    _output(init_execute_phase(_get_cwd(), phase, includes=includes, stage=stage))


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
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged write-paper context for a specific stage id.",
    ),
) -> None:
    """Assemble context for manuscript authoring."""
    from gpd.core.context import init_write_paper

    try:
        payload = init_write_paper(_get_cwd(), stage=stage)
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


@init_app.command("resume")
def init_resume(
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged resume-work context for a specific stage id.",
    ),
) -> None:
    """Assemble context for resuming previous work."""
    from gpd.core.context import init_resume

    _output(init_resume(_get_cwd(), stage=stage))


@init_app.command("sync-state")
def init_sync_state(
    prefer: str | None = typer.Option(
        None,
        "--prefer",
        help="Preferred mirrored-field authority for sync-state: md or json.",
    ),
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged sync-state context for a specific stage id.",
    ),
) -> None:
    """Assemble context for state reconciliation."""
    from gpd.core.context import init_sync_state

    try:
        payload = init_sync_state(_get_cwd(), prefer_mode=prefer, stage=stage)
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

    if stage is None:
        _output(init_verify_work(_get_cwd(), phase))
    else:
        _output(init_verify_work(_get_cwd(), phase, stage=stage))


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
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Load the staged map-research context for a specific stage id.",
    ),
) -> None:
    """Assemble context for research mapping."""
    from gpd.core.context import init_map_research

    try:
        payload = init_map_research(_get_cwd(), stage=stage)
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
    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write, file_lock

    preset = get_workflow_preset(preset_name)
    if preset is None:
        supported = ", ".join(preset.id for preset in list_workflow_presets())
        _error(f"Unknown workflow preset {preset_name!r}. Supported: {supported}")

    config_path = ProjectLayout(_get_cwd()).config_json
    with file_lock(config_path):
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
            current = WOLFRAM_MANAGED_INTEGRATION.project_record(project_root) or {}
        except RuntimeError as exc:
            _error(str(exc))
        updated: dict[str, object] = {"enabled": enabled}
        endpoint = current.get("endpoint")
        if isinstance(endpoint, str) and endpoint and endpoint != WOLFRAM_MANAGED_INTEGRATION.default_endpoint:
            updated["endpoint"] = endpoint
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
    state = "ready" if ready else "disabled" if not enabled else "missing-api-key"
    if not enabled:
        next_step = "Run `gpd integrations enable wolfram` to re-enable the shared Wolfram bridge for this project."
    elif ready:
        next_step = f"Use `{local_cli_plan_preflight_command()}` to verify whether a specific plan can run."
    else:
        next_step = (
            f"Set `{WOLFRAM_MANAGED_INTEGRATION.api_key_env_var}` to make the shared Wolfram bridge available, "
            "or run `gpd integrations disable wolfram` to suppress it for this project."
        )

    return {
        "integration": _WOLFRAM_INTEGRATION_NAME,
        "configured": configured,
        "enabled": enabled,
        "ready": ready,
        "state": state,
        "config_path": str(config_path),
        "scope": "project-local",
        "endpoint": endpoint,
        "api_key_env": WOLFRAM_MANAGED_INTEGRATION.api_key_env_var,
        "api_key_present": api_key_present,
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


class _PermissionsResolutionError(RuntimeError):
    """Internal error used to report non-fatal permissions resolution failures."""


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
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        detect_active_runtime,
        detect_runtime_for_gpd_use,
    )

    supported = _supported_runtime_names()
    if runtime is not None:
        normalized = normalize_runtime_name(runtime)
        if normalized is None or normalized not in supported:
            _raise_permissions_resolution_error(
                f"Unknown runtime {runtime!r}. Supported: {', '.join(supported)}",
                strict=strict,
            )
        return normalized

    detected = (
        detect_runtime_for_gpd_use(cwd=_get_cwd())
        if prefer_installed_runtime
        else detect_active_runtime(cwd=_get_cwd())
    )
    if detected == RUNTIME_UNKNOWN:
        _raise_permissions_resolution_error("No active runtime was detected. Pass --runtime explicitly.", strict=strict)
    return detected


def _resolve_permissions_autonomy(autonomy: str | None, *, strict: bool = True) -> str:
    """Resolve the autonomy value used for runtime-permission sync."""
    from gpd.core.config import AutonomyMode, load_config

    if autonomy is None:
        return load_config(_get_cwd()).autonomy.value

    normalized = autonomy.strip().lower()
    valid_values = {mode.value for mode in AutonomyMode}
    if normalized not in valid_values:
        _raise_permissions_resolution_error(
            f"Unknown autonomy {autonomy!r}. Supported: {', '.join(sorted(valid_values))}",
            strict=strict,
        )
    return normalized


def _permissions_install_target_assessment(runtime_name: str, target_dir: Path):
    """Return the shared install-state assessment for a permissions target."""
    from gpd.hooks.install_metadata import assess_install_target

    return assess_install_target(target_dir, expected_runtime=runtime_name)


def _permissions_install_target_error_message(
    runtime_name: str,
    assessment,
    *,
    action: str,
) -> str:
    """Return a user-facing error message for a non-complete permissions target."""
    target = _format_display_path(assessment.config_dir)
    if assessment.state == "owned_incomplete":
        missing = ", ".join(f"`{relpath}`" for relpath in assessment.missing_install_artifacts)
        missing_message = f" Missing artifacts: {missing}." if missing else ""
        return (
            f"Found an incomplete GPD install for runtime {runtime_name!r} at {target}.{missing_message} "
            f"Repair the install before you {action}."
        )
    if assessment.state == "foreign_runtime":
        other_runtime = assessment.manifest_runtime or "unknown"
        return (
            f"Found a GPD install at {target}, but its manifest belongs to runtime {other_runtime!r}, "
            f"not {runtime_name!r}."
        )
    if assessment.state == "untrusted_manifest":
        return (
            f"Found a managed GPD surface at {target}, but its manifest state is {assessment.manifest_state!r}. "
            "Repair or reinstall it before using permissions."
        )
    return f"No GPD install found for runtime {runtime_name!r}. Run `gpd install {runtime_name}` first."


def _resolve_permissions_target_dir(
    runtime_name: str,
    *,
    target_dir: str | None,
    strict: bool = True,
    action: str = "inspect runtime permissions on",
) -> Path:
    """Resolve the installed config directory targeted by a permissions command."""
    from gpd.adapters import get_adapter
    from gpd.hooks.runtime_detect import detect_install_scope, detect_runtime_install_target

    adapter = get_adapter(runtime_name)
    assessment = None
    if target_dir:
        resolved = _resolve_cli_target_dir(target_dir)
        try:
            adapter.validate_target_runtime(resolved, action=action)
        except RuntimeError as exc:
            _error(str(exc))
        assessment = _permissions_install_target_assessment(runtime_name, resolved)
    else:
        install_target = detect_runtime_install_target(runtime_name, cwd=_get_cwd())
        if install_target is not None:
            resolved = install_target.config_dir
            assessment = _permissions_install_target_assessment(runtime_name, resolved)
        else:
            install_scope = detect_install_scope(runtime_name, cwd=_get_cwd())
            if install_scope == "global":
                resolved = adapter.resolve_target_dir(True, _get_cwd())
                assessment = _permissions_install_target_assessment(runtime_name, resolved)
            elif install_scope == "local":
                resolved = adapter.resolve_target_dir(False, _get_cwd())
                assessment = _permissions_install_target_assessment(runtime_name, resolved)
            else:
                local_target = adapter.resolve_target_dir(False, _get_cwd())
                global_target = adapter.resolve_target_dir(True, _get_cwd())
                local_assessment = _permissions_install_target_assessment(runtime_name, local_target)
                global_assessment = _permissions_install_target_assessment(runtime_name, global_target)
                candidate_assessments = (local_assessment, global_assessment)
                complete_assessment = next(
                    (candidate for candidate in candidate_assessments if candidate.state == "owned_complete"),
                    None,
                )
                if complete_assessment is not None:
                    resolved = complete_assessment.config_dir
                    assessment = complete_assessment
                else:
                    informative_assessment = next(
                        (
                            candidate
                            for candidate in candidate_assessments
                            if candidate.state not in {"absent", "clean"}
                        ),
                        None,
                    )
                    if informative_assessment is None:
                        _raise_permissions_resolution_error(
                            f"No GPD install found for runtime {runtime_name!r}. Run `gpd install {runtime_name}` first.",
                            strict=strict,
                        )
                    resolved = informative_assessment.config_dir
                    assessment = informative_assessment

    if assessment is None:
        assessment = _permissions_install_target_assessment(runtime_name, resolved)

    if assessment.state in {"absent", "clean"} and adapter.has_complete_install(resolved):
        return resolved

    if assessment.state != "owned_complete":
        _raise_permissions_resolution_error(
            _permissions_install_target_error_message(runtime_name, assessment, action=action),
            strict=strict,
        )
    return resolved


def _annotate_permissions_payload(payload: dict[str, object]) -> dict[str, object]:
    """Attach structured capability and evidence metadata to a permissions payload."""
    from gpd.core.health import annotate_permissions_payload

    annotated = annotate_permissions_payload(payload, requested_runtime=None)
    capability_payload = annotated.get("capabilities")
    if not isinstance(capability_payload, dict):
        capability_payload = {}
        annotated["capabilities"] = capability_payload

    capability_payload.update(
        {
            "child_artifact_persistence_reliability": "unknown",
            "supports_structured_child_results": False,
            "continuation_surface": "unknown",
            "checkpoint_stop_semantics": "unknown",
            "supports_runtime_session_payload_attribution": False,
            "supports_agent_payload_attribution": False,
        }
    )

    runtime_name = annotated.get("runtime")
    if not isinstance(runtime_name, str) or not runtime_name.strip():
        return annotated

    try:
        from gpd.adapters.runtime_catalog import get_runtime_capabilities
    except Exception:
        return annotated

    try:
        capabilities = get_runtime_capabilities(runtime_name)
    except KeyError:
        return annotated

    capability_payload.update(
        {
            "child_artifact_persistence_reliability": capabilities.child_artifact_persistence_reliability,
            "supports_structured_child_results": capabilities.supports_structured_child_results,
            "continuation_surface": capabilities.continuation_surface,
            "checkpoint_stop_semantics": capabilities.checkpoint_stop_semantics,
            "supports_runtime_session_payload_attribution": capabilities.supports_runtime_session_payload_attribution,
            "supports_agent_payload_attribution": capabilities.supports_agent_payload_attribution,
        }
    )
    return annotated


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
    from gpd.adapters import get_adapter
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN

    try:
        runtime_name = _resolve_permissions_runtime_name(
            runtime,
            strict=strict,
            prefer_installed_runtime=prefer_installed_runtime,
        )
    except _PermissionsResolutionError as exc:
        return _annotate_permissions_payload(
            {
                "runtime": None,
                "target": None,
                "sync_applied": False,
                "changed": False,
                "message": str(exc),
            }
        )

    if runtime is None and runtime_name == RUNTIME_UNKNOWN:
        if strict:
            _error("No active runtime was detected. Pass --runtime explicitly.")
        return _annotate_permissions_payload(
            {
                "runtime": None,
                "target": None,
                "sync_applied": False,
                "changed": False,
                "message": (
                    "No active runtime was detected. "
                    f"Run `{local_cli_permissions_sync_command()}` after installing GPD into a runtime."
                ),
            }
        )

    try:
        resolved_target_dir = _resolve_permissions_target_dir(
            runtime_name,
            target_dir=target_dir,
            strict=strict,
            action=("sync" if apply_sync else "inspect") + " runtime permissions on",
        )
    except _PermissionsResolutionError as exc:
        return _annotate_permissions_payload(
            {
                "runtime": runtime_name,
                "target": None if target_dir is None else str(_resolve_cli_target_dir(target_dir)),
                "sync_applied": False,
                "changed": False,
                "message": str(exc),
            }
        )

    adapter = get_adapter(runtime_name)

    autonomy_value = _resolve_permissions_autonomy(autonomy, strict=strict)
    payload = (
        adapter.sync_runtime_permissions(resolved_target_dir, autonomy=autonomy_value)
        if apply_sync
        else adapter.runtime_permissions_status(resolved_target_dir, autonomy=autonomy_value)
    )
    return _annotate_permissions_payload(
        {
            "runtime": runtime_name,
            "target": str(resolved_target_dir),
            "autonomy": autonomy_value,
            **payload,
        }
    )


def _permissions_status_payload(
    *,
    runtime: str | None,
    autonomy: str | None,
    target_dir: str | None,
) -> dict[str, object]:
    """Return a status payload annotated for unattended-readiness checks."""
    from gpd.core.health import normalize_permissions_readiness_payload

    payload = _runtime_permissions_payload(
        runtime=runtime,
        autonomy=autonomy,
        target_dir=target_dir,
        apply_sync=False,
        strict=True,
        prefer_installed_runtime=True,
    )
    return normalize_permissions_readiness_payload(
        payload,
        requested_runtime=runtime,
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

        config = load_config(_get_cwd())
        found, value = effective_config_value(config, key)
    except ConfigError as exc:
        _error(str(exc))
    if not found:
        _output({"key": key, "found": False})
        return
    _output({"key": key, "value": value, "found": True})


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key path (dot-separated)"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value (advanced local override)."""
    from gpd.core.config import apply_config_update, effective_config_value, load_config
    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write, file_lock

    config_path = ProjectLayout(_get_cwd()).config_json
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
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            parsed = value
        try:
            updated_config, canonical_key = apply_config_update(raw, key, parsed)
        except ConfigError as exc:
            _error(str(exc))
        atomic_write(config_path, json.dumps(updated_config, indent=2) + "\n")

    config = load_config(_get_cwd())
    _found, effective_value = effective_config_value(config, key)
    result: dict[str, object] = {"key": key, "canonical_key": canonical_key, "value": effective_value, "updated": True}
    if canonical_key == "autonomy":
        result["guided_path"] = (
            f"Use `{_active_runtime_settings_command(cwd=_get_cwd())}` inside the runtime for guided autonomy changes."
        )
        result["runtime_permissions"] = _runtime_permissions_payload(
            runtime=None,
            autonomy=str(effective_value),
            target_dir=None,
            apply_sync=True,
            strict=False,
        )
    _output(result)


@config_app.command("ensure-section")
def config_ensure_section() -> None:
    """Ensure config directory structure exists."""
    from gpd.core.config import GPDProjectConfig
    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write

    config_path = ProjectLayout(_get_cwd()).config_json
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


def _resolve_subject_path(subject: str | None, *, base: Path) -> Path | None:
    """Resolve one raw subject string relative to *base* when possible."""
    if not isinstance(subject, str) or not subject.strip():
        return None
    target = Path(subject)
    if not target.is_absolute():
        target = base / target
    return target.resolve(strict=False)


def _subject_is_relative_to(target: Path, base: Path) -> bool:
    """Return whether *target* stays under *base* after normalization."""
    try:
        target.resolve(strict=False).relative_to(base.resolve(strict=False))
    except ValueError:
        return False
    return True


def _normalized_allowed_manuscript_suffixes(
    *,
    allow_markdown: bool,
    allowed_suffixes: Collection[str] | None = None,
) -> set[str]:
    """Return normalized explicit manuscript suffixes for one command."""
    normalized_allowed_suffixes = {
        suffix.lower()
        for suffix in (
            allowed_suffixes if allowed_suffixes is not None else ({".tex", ".md"} if allow_markdown else {".tex"})
        )
    }
    return normalized_allowed_suffixes or {".tex"}


def _allowed_manuscript_suffix_message(allowed_suffixes: Collection[str]) -> str:
    """Return a user-facing suffix description for manuscript target errors."""
    ordered_suffixes = [suffix for suffix in (".tex", ".md", ".txt", ".pdf") if suffix in allowed_suffixes]
    extras = sorted(suffix for suffix in allowed_suffixes if suffix not in {".tex", ".md", ".txt", ".pdf"})
    ordered_suffixes.extend(extras)
    if ordered_suffixes == [".tex"]:
        return ".tex file"
    if len(ordered_suffixes) == 2:
        return f"{ordered_suffixes[0]} or {ordered_suffixes[1]} file"
    return ", ".join(ordered_suffixes[:-1]) + f", or {ordered_suffixes[-1]} file"


def _supported_manuscript_root_for_target(project_root: Path, target: Path) -> Path | None:
    """Return the canonical manuscript root that owns *target*, when supported."""
    from gpd.core.constants import ProjectLayout

    try:
        relative = target.resolve(strict=False).relative_to(project_root.resolve(strict=False))
    except ValueError:
        return None

    if relative.parts and relative.parts[0] in _SUPPORTED_MANUSCRIPT_ROOT_NAMES:
        return project_root / relative.parts[0]

    if (
        len(relative.parts) >= 4
        and relative.parts[0] == PLANNING_DIR_NAME
        and relative.parts[1] == PUBLICATION_DIR_NAME
        and relative.parts[2]
        and relative.parts[3] == PUBLICATION_MANUSCRIPT_DIR_NAME
    ):
        return ProjectLayout(project_root).publication_manuscript_dir(relative.parts[2])

    return None


def _supported_explicit_manuscript_target(project_root: Path, target: Path) -> bool:
    """Return whether *target* stays under a supported manuscript root."""
    return _supported_manuscript_root_for_target(project_root, target) is not None


def _supported_root_resolution_for_target(
    project_root: Path,
    target: Path,
    *,
    allow_markdown: bool,
) -> tuple[Path, object] | tuple[None, None]:
    """Resolve the owning manuscript root for *target* when it stays under supported roots."""
    manuscript_root = _supported_manuscript_root_for_target(project_root, target)
    if manuscript_root is None:
        return None, None
    return manuscript_root, resolve_manuscript_entrypoint_from_root_resolution(
        manuscript_root,
        allow_markdown=allow_markdown,
    )


def _resolve_review_preflight_manuscript_target(
    cwd: Path,
    subject: str | None,
    *,
    allow_markdown: bool = True,
    restrict_to_supported_roots: bool = False,
    workspace_cwd: Path | None = None,
    allowed_suffixes: Collection[str] | None = None,
) -> ResolvedManuscriptTarget:
    """Resolve a review-preflight manuscript target with structured status details."""

    project_root = cwd.resolve(strict=False)
    subject_base = (workspace_cwd or cwd).resolve(strict=False)
    normalized_allowed_suffixes = _normalized_allowed_manuscript_suffixes(
        allow_markdown=allow_markdown,
        allowed_suffixes=allowed_suffixes,
    )
    requested_target = _resolve_subject_path(subject, base=subject_base)

    if requested_target is not None:
        target_is_supported_root = _supported_explicit_manuscript_target(project_root, requested_target)
        if restrict_to_supported_roots and not target_is_supported_root:
            return ResolvedManuscriptTarget(
                status="invalid",
                manuscript=None,
                manuscript_root=requested_target if requested_target.is_dir() else requested_target.parent,
                requested_target=requested_target,
                detail=(
                    "explicit manuscript target must stay under `paper/`, `manuscript/`, `draft/`, "
                    "or `GPD/publication/<subject_slug>/manuscript/` inside the current project"
                ),
            )
        if not requested_target.exists():
            return ResolvedManuscriptTarget(
                status="missing",
                manuscript=None,
                manuscript_root=requested_target if requested_target.suffix == "" else requested_target.parent,
                requested_target=requested_target,
                detail=f"missing explicit manuscript target {_format_display_path(requested_target)}",
            )
        if requested_target.is_file():
            target_suffix = requested_target.suffix.lower()
            if target_suffix in normalized_allowed_suffixes:
                if target_suffix in {".tex", ".md"}:
                    manuscript_root, root_resolution = _supported_root_resolution_for_target(
                        project_root,
                        requested_target,
                        allow_markdown=allow_markdown,
                    )
                    if manuscript_root is not None and root_resolution is not None:
                        if root_resolution.status != "resolved" or root_resolution.manuscript_entrypoint is None:
                            return ResolvedManuscriptTarget(
                                status=root_resolution.status,
                                manuscript=None,
                                manuscript_root=manuscript_root,
                                requested_target=requested_target,
                                detail=(
                                    f"{_format_display_path(manuscript_root)} is ambiguous or inconsistent: "
                                    f"{root_resolution.detail}"
                                ),
                            )
                        if root_resolution.manuscript_entrypoint.resolve(strict=False) != requested_target.resolve(
                            strict=False
                        ):
                            return ResolvedManuscriptTarget(
                                status="invalid",
                                manuscript=None,
                                manuscript_root=manuscript_root,
                                requested_target=requested_target,
                                detail=(
                                    f"{_format_display_path(requested_target)} does not match the resolved manuscript "
                                    f"entrypoint {_format_display_path(root_resolution.manuscript_entrypoint)} under "
                                    f"{_format_display_path(manuscript_root)}"
                                ),
                            )
                return ResolvedManuscriptTarget(
                    status="resolved",
                    manuscript=requested_target,
                    manuscript_root=requested_target.parent,
                    requested_target=requested_target,
                    detail=f"{_format_display_path(requested_target)} present",
                )
            if target_suffix == ".md" and normalized_allowed_suffixes == {".tex"}:
                return ResolvedManuscriptTarget(
                    status="invalid",
                    manuscript=None,
                    manuscript_root=requested_target.parent,
                    requested_target=requested_target,
                    detail=f"explicit manuscript target must be a .tex file: {_format_display_path(requested_target)}",
                )
            return ResolvedManuscriptTarget(
                status="invalid",
                manuscript=None,
                manuscript_root=requested_target.parent,
                requested_target=requested_target,
                detail=(
                    "explicit manuscript target must be a "
                    f"{_allowed_manuscript_suffix_message(normalized_allowed_suffixes)}: "
                    f"{_format_display_path(requested_target)}"
                ),
            )

        if requested_target.is_dir():
            manuscript_root, root_resolution = _supported_root_resolution_for_target(
                project_root,
                requested_target,
                allow_markdown=allow_markdown,
            )
            resolution = (
                root_resolution
                if manuscript_root is not None and root_resolution is not None
                else resolve_manuscript_entrypoint_from_root_resolution(requested_target, allow_markdown=allow_markdown)
            )
            if resolution.status == "resolved" and resolution.manuscript_entrypoint is not None:
                if manuscript_root is not None and manuscript_root != requested_target:
                    resolved_entrypoint = resolution.manuscript_entrypoint.resolve(strict=False)
                    if not _subject_is_relative_to(resolved_entrypoint, requested_target):
                        return ResolvedManuscriptTarget(
                            status="invalid",
                            manuscript=None,
                            manuscript_root=manuscript_root,
                            requested_target=requested_target,
                            detail=(
                                f"{_format_display_path(requested_target)} does not contain the resolved manuscript "
                                f"entrypoint {_format_display_path(resolution.manuscript_entrypoint)} under "
                                f"{_format_display_path(manuscript_root)}"
                            ),
                        )
                return ResolvedManuscriptTarget(
                    status="resolved",
                    manuscript=resolution.manuscript_entrypoint,
                    manuscript_root=resolution.manuscript_root,
                    requested_target=requested_target,
                    detail=(
                        f"{_format_display_path(requested_target)} resolved to "
                        f"{_format_display_path(resolution.manuscript_entrypoint)}"
                    ),
                )
            if resolution.status == "missing":
                return ResolvedManuscriptTarget(
                    status="missing",
                    manuscript=None,
                    manuscript_root=resolution.manuscript_root,
                    requested_target=requested_target,
                    detail=f"no manuscript entry point found under {_format_display_path(requested_target)}",
                )
            return ResolvedManuscriptTarget(
                status=resolution.status,
                manuscript=None,
                manuscript_root=resolution.manuscript_root,
                requested_target=requested_target,
                detail=f"{_format_display_path(requested_target)} is ambiguous or inconsistent: {resolution.detail}",
            )

    resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=allow_markdown)
    manuscript = resolution.manuscript_entrypoint
    if manuscript is not None and resolution.status == "resolved":
        return ResolvedManuscriptTarget(
            status="resolved",
            manuscript=manuscript,
            manuscript_root=resolution.manuscript_root,
            requested_target=None,
            detail=f"{_format_display_path(manuscript)} present",
        )
    if allow_markdown:
        if resolution.status == "missing":
            return ResolvedManuscriptTarget(
                status="missing",
                manuscript=None,
                manuscript_root=resolution.manuscript_root,
                requested_target=None,
                detail=(
                    "no manuscript entrypoint found under paper/, manuscript/, or draft/ "
                    "(expected ARTIFACT-MANIFEST.json or PAPER-CONFIG.json-derived output)"
                ),
            )
        return ResolvedManuscriptTarget(
            status=resolution.status,
            manuscript=None,
            manuscript_root=resolution.manuscript_root,
            requested_target=None,
            detail=f"ambiguous or inconsistent manuscript roots: {resolution.detail}",
        )
    if resolution.status == "missing":
        return ResolvedManuscriptTarget(
            status="missing",
            manuscript=None,
            manuscript_root=resolution.manuscript_root,
            requested_target=None,
            detail="no LaTeX manuscript entrypoint found under paper/, manuscript/, or draft/",
        )
    return ResolvedManuscriptTarget(
        status=resolution.status,
        manuscript=None,
        manuscript_root=resolution.manuscript_root,
        requested_target=None,
        detail=f"ambiguous or inconsistent manuscript roots: {resolution.detail}",
    )


def _resolve_review_preflight_manuscript(
    cwd: Path,
    subject: str | None,
    *,
    allow_markdown: bool = True,
    restrict_to_supported_roots: bool = False,
    workspace_cwd: Path | None = None,
    allowed_suffixes: Collection[str] | None = None,
) -> tuple[Path | None, str]:
    """Resolve a review-preflight manuscript target from an explicit subject or defaults."""

    resolution = _resolve_review_preflight_manuscript_target(
        cwd,
        subject,
        allow_markdown=allow_markdown,
        restrict_to_supported_roots=restrict_to_supported_roots,
        workspace_cwd=workspace_cwd,
        allowed_suffixes=allowed_suffixes,
    )
    return resolution.manuscript, resolution.detail


def _resolve_review_preflight_publication_artifact(manuscript: Path, *filenames: str) -> Path | None:
    """Resolve review artifacts only from the active manuscript directory."""
    return locate_publication_artifact(manuscript, *filenames)


@dataclasses.dataclass(frozen=True)
class ManuscriptPublicationArtifacts:
    """Publication artifacts resolved beside the active manuscript."""

    artifact_manifest: Path | None = None
    bibliography_audit: Path | None = None
    reproducibility_manifest: Path | None = None


@dataclasses.dataclass(frozen=True)
class PublicationReviewRoundArtifacts:
    """Latest review-round artifacts, even when they no longer match the active manuscript."""

    round_number: int
    round_suffix: str
    review_ledger: Path | None
    referee_decision: Path | None


@dataclasses.dataclass(frozen=True)
class PublicationResponseRoundArtifacts:
    """Latest response-round artifacts without assuming fresh staged review exists."""

    round_number: int
    round_suffix: str
    author_response: Path | None
    referee_response: Path | None


_REVIEW_LEDGER_FILENAME_RE = re.compile(r"^REVIEW-LEDGER(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_REFEREE_DECISION_FILENAME_RE = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_AUTHOR_RESPONSE_FILENAME_RE = re.compile(r"^AUTHOR-RESPONSE(?P<round_suffix>-R(?P<round>\d+))?\.md$")
_REFEREE_RESPONSE_FILENAME_RE = re.compile(r"^REFEREE_RESPONSE(?P<round_suffix>-R(?P<round>\d+))?\.md$")


def _managed_publication_root_for_target(project_root: Path, target: Path) -> Path | None:
    """Return the managed publication root for one target under ``GPD/publication/<slug>/manuscript``."""

    from gpd.core.constants import ProjectLayout

    manuscript_root = _supported_manuscript_root_for_target(project_root, target)
    if manuscript_root is None:
        return None
    try:
        relative_root = manuscript_root.resolve(strict=False).relative_to(project_root.resolve(strict=False))
    except ValueError:
        return None
    if (
        len(relative_root.parts) >= 4
        and relative_root.parts[0] == PLANNING_DIR_NAME
        and relative_root.parts[1] == PUBLICATION_DIR_NAME
        and relative_root.parts[2]
        and relative_root.parts[3] == PUBLICATION_MANUSCRIPT_DIR_NAME
    ):
        return ProjectLayout(project_root).publication_subject_dir(relative_root.parts[2])
    return None


def _publication_lineage_search_roots(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Return candidate publication-root and review-root search paths for one manuscript subject."""

    planning_dir = project_root / PLANNING_DIR_NAME
    publication_roots: list[Path] = [planning_dir]
    review_roots: list[Path] = [planning_dir / "review"]

    if manuscript is None:
        return tuple(publication_roots), tuple(review_roots)

    managed_publication_root = _managed_publication_root_for_target(project_root, manuscript)
    if managed_publication_root is not None:
        publication_roots.append(managed_publication_root)
        review_roots.append(managed_publication_root / "review")
        return tuple(dict.fromkeys(publication_roots)), tuple(dict.fromkeys(review_roots))

    if _supported_manuscript_root_for_target(project_root, manuscript) is None:
        from gpd.core.constants import ProjectLayout

        subject_root = ProjectLayout(project_root).publication_subject_dir(
            _publication_subject_slug_for_manuscript_entrypoint(project_root, manuscript)
        )
        publication_roots.insert(0, subject_root)
        review_roots.insert(0, subject_root / "review")

    return tuple(dict.fromkeys(publication_roots)), tuple(dict.fromkeys(review_roots))


def _round_file_map(
    *search_roots: Path,
    filename_pattern: re.Pattern[str],
    glob_pattern: str,
) -> dict[int, Path]:
    """Return one round-number-to-path map across ordered search roots."""

    round_map: dict[int, Path] = {}
    for root in search_roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob(glob_pattern)):
            round_info = review_artifact_round(path, pattern=filename_pattern)
            if round_info is None:
                continue
            round_number, _round_suffix = round_info
            round_map.setdefault(round_number, path)
    return round_map


def _latest_round_number(*round_maps: dict[int, Path]) -> int | None:
    """Return the latest round number present across one or more artifact maps."""

    round_numbers = {round_number for round_map in round_maps for round_number in round_map}
    return max(round_numbers) if round_numbers else None


def _publication_review_round_path_maps(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> tuple[dict[int, Path], dict[int, Path]]:
    """Return staged review-artifact maps rooted at the manuscript's publication lineage."""

    _publication_roots, review_roots = _publication_lineage_search_roots(project_root, manuscript=manuscript)
    return (
        _round_file_map(
            *review_roots,
            filename_pattern=_REVIEW_LEDGER_FILENAME_RE,
            glob_pattern="REVIEW-LEDGER*.json",
        ),
        _round_file_map(
            *review_roots,
            filename_pattern=_REFEREE_DECISION_FILENAME_RE,
            glob_pattern="REFEREE-DECISION*.json",
        ),
    )


def _publication_response_round_path_maps(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> tuple[dict[int, Path], dict[int, Path]]:
    """Return paired response-artifact maps rooted at the manuscript's publication lineage."""

    publication_roots, review_roots = _publication_lineage_search_roots(project_root, manuscript=manuscript)
    return (
        _round_file_map(
            *publication_roots,
            filename_pattern=_AUTHOR_RESPONSE_FILENAME_RE,
            glob_pattern="AUTHOR-RESPONSE*.md",
        ),
        _round_file_map(
            *review_roots,
            filename_pattern=_REFEREE_RESPONSE_FILENAME_RE,
            glob_pattern="REFEREE_RESPONSE*.md",
        ),
    )


def _publication_review_round_artifacts(
    round_number: int,
    *,
    review_ledger_by_round: dict[int, Path],
    referee_decision_by_round: dict[int, Path],
) -> PublicationReviewRoundArtifacts:
    """Return one staged review round bundle from precomputed round maps."""

    return PublicationReviewRoundArtifacts(
        round_number=round_number,
        round_suffix=review_round_suffix(round_number),
        review_ledger=review_ledger_by_round.get(round_number),
        referee_decision=referee_decision_by_round.get(round_number),
    )


def _resolve_latest_publication_review_round_artifacts(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> PublicationReviewRoundArtifacts | None:
    """Return the newest staged review round without enforcing manuscript-path matching."""

    review_ledger_by_round, referee_decision_by_round = _publication_review_round_path_maps(
        project_root,
        manuscript=manuscript,
    )
    round_number = _latest_round_number(review_ledger_by_round, referee_decision_by_round)
    if round_number is None:
        return None
    return _publication_review_round_artifacts(
        round_number,
        review_ledger_by_round=review_ledger_by_round,
        referee_decision_by_round=referee_decision_by_round,
    )


def _resolve_latest_publication_response_round_artifacts(
    project_root: Path,
    *,
    manuscript: Path | None = None,
) -> PublicationResponseRoundArtifacts | None:
    """Return the newest paired-response round without assuming fresh review clearance exists."""

    author_response_by_round, referee_response_by_round = _publication_response_round_path_maps(
        project_root,
        manuscript=manuscript,
    )
    round_number = _latest_round_number(author_response_by_round, referee_response_by_round)
    if round_number is None:
        return None
    return PublicationResponseRoundArtifacts(
        round_number=round_number,
        round_suffix=review_round_suffix(round_number),
        author_response=author_response_by_round.get(round_number),
        referee_response=referee_response_by_round.get(round_number),
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
    from gpd.core.state import load_state_json
    from gpd.core.utils import phase_normalize

    required_state = str(getattr(contract, "required_state", "") or "").strip()
    if not required_state:
        return None
    if required_state != "phase_executed":
        return False, f'unhandled required_state="{required_state}"'

    state_obj = load_state_json(cwd)
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
    from gpd.core.state import load_state_json
    from gpd.core.utils import phase_normalize

    state_obj = load_state_json(cwd)
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


def _project_root_for_json_input(input_path: str) -> Path:
    """Return the best project-root anchor for a JSON artifact input path."""

    cwd = _get_cwd()
    if input_path == "-":
        return cwd

    target = Path(input_path)
    if not target.is_absolute():
        resolved = (cwd / target).resolve(strict=False)
        for base in (resolved.parent, *resolved.parent.parents):
            if (base / "GPD").is_dir():
                return base
        return resolved.parent

    resolved = target.expanduser().resolve(strict=False)
    immediate_parent = resolved.parent
    if (immediate_parent / "GPD").is_dir():
        return immediate_parent

    for base in immediate_parent.parents:
        gpd_dir = (base / "GPD").resolve(strict=False)
        if not gpd_dir.is_dir():
            continue
        try:
            resolved.relative_to(gpd_dir)
        except ValueError:
            continue
        return base
    return resolved.parent


def _enclosing_project_root_for_json_input(input_path: str) -> Path | None:
    """Return the enclosing project root for a JSON artifact, if one exists."""

    cwd = _get_cwd()
    if input_path == "-":
        return cwd if (cwd / "GPD").is_dir() else None

    target = Path(input_path)
    if not target.is_absolute():
        resolved = (cwd / target).resolve(strict=False)
        for base in (resolved.parent, *resolved.parent.parents):
            if (base / "GPD").is_dir():
                return base
        return None

    resolved = target.expanduser().resolve(strict=False)
    immediate_parent = resolved.parent
    if (immediate_parent / "GPD").is_dir():
        return immediate_parent

    for base in immediate_parent.parents:
        gpd_dir = (base / "GPD").resolve(strict=False)
        if not gpd_dir.is_dir():
            continue
        try:
            resolved.relative_to(gpd_dir)
        except ValueError:
            continue
        return base
    return None


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


def _discover_literature_review_citation_sources(project_root: Path) -> tuple[Path | None, str | None]:
    """Return a single literature-review citation-source sidecar if it is unambiguous."""
    literature_dir = project_root / "GPD" / "literature"
    legacy_research_dir = project_root / "GPD" / "research"
    if literature_dir.is_dir():
        search_dir = literature_dir
    elif legacy_research_dir.is_dir():
        search_dir = legacy_research_dir
    else:
        return None, None

    matches = sorted(path for path in search_dir.rglob("*-CITATION-SOURCES.json") if path.is_file())
    if not matches:
        return None, None
    if len(matches) == 1:
        return matches[0], None

    preview = ", ".join(_format_display_path(path) for path in matches[:3])
    remaining = len(matches) - 3
    suffix = f", ... (+{remaining} more)" if remaining > 0 else ""
    warning = (
        f"Multiple {'literature-review' if search_dir == literature_dir else 'legacy research'} citation-source sidecars found; "
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


def _reject_legacy_paper_config_location(config_file: Path, *, project_root: Path | None = None) -> None:
    """Reject removed paper-config locations under internal planning storage."""
    resolved_config = config_file.resolve(strict=False)
    project_root = (project_root or _project_scoped_cwd()).resolve(strict=False)
    for legacy_config_root in (project_root / "GPD" / "paper", project_root / ".gpd" / "paper"):
        try:
            resolved_config.relative_to(legacy_config_root)
        except ValueError:
            continue
        planning_dir_name = legacy_config_root.parent.name
        raise GPDError(
            f"Paper configs under `{planning_dir_name}/paper/` are not supported. "
            "Move the config to `paper/`, `manuscript/`, or `draft/`."
        )


def _split_command_arguments(arguments: str | None) -> list[str]:
    """Split a raw command argument string into shell-like tokens."""
    if not arguments:
        return []
    try:
        return shlex.split(arguments)
    except ValueError:
        return arguments.split()


def _flag_values(arguments: str | None, *flags: str) -> list[str]:
    """Return non-empty values supplied to one or more long flags."""
    tokens = _split_command_arguments(arguments)
    values: list[str] = []
    skip_next = False
    flag_set = set(flags)

    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            break
        if token in flag_set:
            skip_next = True
            if index + 1 >= len(tokens):
                continue
            next_token = tokens[index + 1].strip()
            if next_token and not next_token.startswith("-"):
                values.append(next_token)
            continue
        matched_flag = next((flag for flag in flags if token.startswith(f"{flag}=")), None)
        if matched_flag is None:
            continue
        value = token.partition("=")[2].strip()
        if value:
            values.append(value)

    return values


def _write_paper_external_authoring_intake_argument(arguments: str | None) -> str | None:
    """Return the explicit ``--intake`` manifest path supplied to ``gpd:write-paper``."""

    flagged = _flag_values(arguments, "--intake")
    return flagged[-1] if flagged else None


def _write_paper_external_authoring_subject_slug(manifest: WritePaperAuthoringInput) -> str:
    """Return the managed publication subject slug for one external-authoring intake."""

    explicit_slug = str(getattr(manifest, "subject_slug", "") or "").strip()
    if explicit_slug:
        return explicit_slug
    derived_slug = normalize_ascii_slug(str(getattr(manifest, "title", "") or "")) or "paper"
    return derived_slug[:48].rstrip("-") or "paper"


def _resolve_write_paper_external_authoring_intake(
    project_root: Path,
    arguments: str | None,
    *,
    workspace_cwd: Path | None = None,
) -> WritePaperExternalAuthoringIntakeResolution | None:
    """Validate the bounded external-authoring intake manifest for ``gpd:write-paper``."""

    from gpd.mcp.paper.models import WritePaperAuthoringInput

    intake_argument = _write_paper_external_authoring_intake_argument(arguments)
    if intake_argument is None:
        return None

    workspace_root = (workspace_cwd or project_root).resolve(strict=False)
    intake_path = (_resolve_subject_path(intake_argument, base=workspace_root) or (workspace_root / intake_argument)).resolve(
        strict=False
    )
    if intake_path.suffix.lower() != ".json":
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper `--intake` must point to a JSON file: {_format_display_path(intake_path)}",
        )
    if not intake_path.exists():
        return WritePaperExternalAuthoringIntakeResolution(
            status="missing",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"missing write-paper intake manifest {_format_display_path(intake_path)}",
        )
    if intake_path.is_dir():
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper `--intake` must point to a JSON file, not a directory: {_format_display_path(intake_path)}",
        )

    try:
        payload = _load_json_document(str(intake_path))
    except GPDError as exc:
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"could not load write-paper intake manifest: {exc}",
        )
    if not isinstance(payload, dict):
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper intake manifest must be a JSON object: {_format_display_path(intake_path)}",
        )

    try:
        manifest = WritePaperAuthoringInput.model_validate(payload)
    except PydanticValidationError as exc:
        details = "; ".join(
            _format_pydantic_schema_error(error, root_label="write_paper_authoring_input")
            for error in exc.errors()[:3]
        )
        return WritePaperExternalAuthoringIntakeResolution(
            status="invalid",
            intake_path=intake_path,
            manuscript_root=None,
            intake_root=None,
            subject_slug=None,
            detail=f"write-paper intake manifest is invalid: {details}",
        )

    subject_slug = _write_paper_external_authoring_subject_slug(manifest)
    publication_root = (
        project_root.resolve(strict=False)
        / PLANNING_DIR_NAME
        / PUBLICATION_DIR_NAME
        / subject_slug
    )
    manuscript_root = publication_root / PUBLICATION_MANUSCRIPT_DIR_NAME
    intake_root = publication_root / "intake"
    return WritePaperExternalAuthoringIntakeResolution(
        status="resolved",
        intake_path=intake_path,
        manuscript_root=manuscript_root,
        intake_root=intake_root,
        subject_slug=subject_slug,
        manifest=manifest,
        detail=(
            f"validated external authoring intake {_format_display_path(intake_path)}; "
            f"managed manuscript bootstrap will use {_format_display_path(manuscript_root)}"
        ),
    )


def _has_write_paper_external_authoring_intake(arguments: str | None) -> bool:
    """Return whether ``gpd:write-paper`` received an explicit ``--intake`` flag."""

    return _write_paper_external_authoring_intake_argument(arguments) is not None


def _has_flag_value(tokens: list[str], flag: str) -> bool:
    """Return True when ``flag`` is present with a non-empty value."""
    for index, token in enumerate(tokens):
        if token == flag:
            if index + 1 < len(tokens):
                next_token = tokens[index + 1]
                if next_token and not next_token.startswith("-"):
                    return True
        elif token.startswith(f"{flag}="):
            return bool(token.partition("=")[2].strip())
    return False


def _positional_tokens(arguments: str | None, *, flags_with_values: tuple[str, ...] = ()) -> list[str]:
    """Extract positional tokens after removing known long-option/value pairs."""
    tokens = _split_command_arguments(arguments)
    positionals: list[str] = []
    skip_next = False
    value_flags = set(flags_with_values)

    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            return positionals + tokens[index + 1 :]
        if token in value_flags:
            skip_next = True
            continue
        if any(token.startswith(f"{flag}=") for flag in value_flags):
            continue
        if token.startswith("--"):
            continue
        positionals.append(token)

    return positionals


def _has_discover_explicit_inputs(arguments: str | None) -> bool:
    """Discover standalone mode needs either a phase number or a topic."""
    return bool(_positional_tokens(arguments, flags_with_values=("--depth", "-d")))


def _has_simple_positional_inputs(arguments: str | None) -> bool:
    """Generic detector for commands satisfied by any positional topic/target."""
    return bool(_positional_tokens(arguments))


def _has_sensitivity_explicit_inputs(arguments: str | None) -> bool:
    """Sensitivity analysis standalone mode requires both target and parameter list."""
    tokens = _split_command_arguments(arguments)
    return _has_flag_value(tokens, "--target") and _has_flag_value(tokens, "--params")


def _looks_like_parameter_sweep_anchor_token(token: str) -> bool:
    """Return True for a standalone/current-workspace parameter-sweep compute anchor."""
    if not token or token.startswith("-"):
        return False
    if token.isdigit():
        return False
    if token.startswith(("./", "../", "~/", "/", "@")):
        return True
    if os.sep in token or (os.altsep is not None and os.altsep in token):
        return True
    if Path(token).suffix:
        return True
    return any(character.isalpha() for character in token)


def _has_parameter_sweep_explicit_inputs(arguments: str | None) -> bool:
    """Parameter-sweep standalone mode needs param/range flags plus a non-phase compute anchor."""
    tokens = _split_command_arguments(arguments)
    if not (_has_flag_value(tokens, "--param") and _has_flag_value(tokens, "--range")):
        return False
    positionals = _positional_tokens(arguments, flags_with_values=("--param", "--range"))
    return any(_looks_like_parameter_sweep_anchor_token(token) for token in positionals)


_DIGEST_KNOWLEDGE_PATH_SUFFIXES = DIGEST_KNOWLEDGE_SOURCE_SUFFIXES


def _looks_like_digest_knowledge_topic_token(token: str) -> bool:
    """Return True for a non-empty topic-like token."""
    if not token or token.startswith("-"):
        return False
    if _looks_like_digest_knowledge_path_token(token) or _looks_like_digest_knowledge_arxiv_token(token):
        return False
    return any(character.isalpha() for character in token)


def _looks_like_digest_knowledge_path_token(token: str) -> bool:
    """Return True for a token that looks like an explicit path input."""
    if not token or token.startswith("-"):
        return False
    if token.startswith(("./", "../", "~/", "/", "@")):
        return True
    if os.sep in token or (os.altsep is not None and os.altsep in token):
        return True
    return Path(token).suffix.lower() in _DIGEST_KNOWLEDGE_PATH_SUFFIXES


def _looks_like_digest_knowledge_arxiv_token(token: str) -> bool:
    """Return True for a token that normalizes as an arXiv identifier."""
    if not token or token.startswith("-"):
        return False
    try:
        normalize_arxiv_id(token)
    except ValueError:
        return False
    return True


def _looks_like_review_knowledge_id_token(token: str) -> bool:
    """Return True for a canonical knowledge identifier token."""
    if not token or token.startswith("-") or not token.startswith("K-"):
        return False
    slug = token[2:]
    return bool(slug) and normalize_ascii_slug(slug) == slug


def _looks_like_review_knowledge_path_token(token: str) -> bool:
    """Return True for an explicit knowledge-document path token."""
    if not token or token.startswith("-"):
        return False
    if not _looks_like_digest_knowledge_path_token(token):
        return False
    path = Path(token)
    if not (
        path.suffix.lower() == ".md"
        and path.stem.startswith("K-")
        and normalize_ascii_slug(path.stem[2:]) == path.stem[2:]
    ):
        return False

    normalized_parts = [part for part in path.as_posix().split("/") if part not in {"", "."}]
    if path.is_absolute():
        return len(normalized_parts) >= 3 and normalized_parts[-3:-1] == ["GPD", "knowledge"]
    return len(normalized_parts) >= 3 and normalized_parts[:2] == ["GPD", "knowledge"]


def _has_digest_knowledge_explicit_inputs(arguments: str | None) -> bool:
    """Digest-knowledge standalone mode needs an explicit topic, path, or arXiv input."""
    tokens = _split_command_arguments(arguments)
    return any(
        _looks_like_digest_knowledge_topic_token(token)
        or _looks_like_digest_knowledge_path_token(token)
        or _looks_like_digest_knowledge_arxiv_token(token)
        for token in tokens
    )


def _has_review_knowledge_explicit_inputs(arguments: str | None) -> bool:
    """Review-knowledge standalone mode needs an explicit knowledge path or canonical knowledge id."""
    tokens = _split_command_arguments(arguments)
    return any(
        _looks_like_review_knowledge_path_token(token) or _looks_like_review_knowledge_id_token(token)
        for token in tokens
    )


_PROJECT_AWARE_EXPLICIT_INPUTS: dict[str, tuple[list[str], Callable[[str | None], bool]]] = {
    "gpd:compare-experiment": (
        ["prediction, dataset path, phase identifier, or comparison target"],
        _has_simple_positional_inputs,
    ),
    "gpd:compare-results": (
        ["comparison target, phase, artifact path, or source-a vs source-b"],
        _has_simple_positional_inputs,
    ),
    "gpd:derive-equation": (["equation or topic to derive"], _has_simple_positional_inputs),
    "gpd:dimensional-analysis": (["phase number or file path"], _has_simple_positional_inputs),
    "gpd:discover": (["phase number or standalone topic"], _has_discover_explicit_inputs),
    "gpd:explain": (["concept, result, method, notation, or paper"], _has_simple_positional_inputs),
    "gpd:digest-knowledge": (
        ["knowledge document path", "source path", "arxiv id", "topic"],
        _has_digest_knowledge_explicit_inputs,
    ),
    "gpd:review-knowledge": (
        ["knowledge document path or canonical K-* knowledge id"],
        _has_review_knowledge_explicit_inputs,
    ),
    "gpd:limiting-cases": (["phase number or file path"], _has_simple_positional_inputs),
    "gpd:literature-review": (["topic or research question"], _has_simple_positional_inputs),
    "gpd:numerical-convergence": (["phase number or file path"], _has_simple_positional_inputs),
    "gpd:parameter-sweep": (
        ["computation anchor or file path", "--param name", "--range start:end:steps"],
        _has_parameter_sweep_explicit_inputs,
    ),
    "gpd:sensitivity-analysis": (["--target quantity", "--params p1,p2,..."], _has_sensitivity_explicit_inputs),
    "gpd:write-paper": (_WRITE_PAPER_EXTERNAL_AUTHORING_EXPLICIT_INPUTS, _has_write_paper_external_authoring_intake),
}


def _build_project_aware_guidance(explicit_inputs: list[str], *, init_command: str) -> str:
    """Render the standardized project-aware guidance string."""
    init_guidance = (
        f"initialize a project with `{init_command}` in the runtime surface or `gpd init new-project` in the local CLI"
    )
    if not explicit_inputs:
        return f"Either provide explicit inputs for this command, or {init_guidance}."
    if len(explicit_inputs) == 1:
        requirement_text = explicit_inputs[0]
    elif len(explicit_inputs) == 2:
        requirement_text = f"{explicit_inputs[0]} and {explicit_inputs[1]}"
    else:
        requirement_text = ", ".join(explicit_inputs[:-1]) + f", and {explicit_inputs[-1]}"
    return f"Either provide {requirement_text} explicitly, or {init_guidance}."


def _build_recoverable_workspace_guidance(*, init_command: str) -> str:
    """Render the standardized recovery guidance string for project-required commands."""
    return (
        "This command requires a recoverable GPD workspace. "
        f"Open the right project, use `{local_cli_resume_recent_command()}` to rediscover it, or "
        f"initialize a new project with `{init_command}` in the runtime surface or `gpd init new-project` in the local CLI."
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


def _command_review_contract(command: object) -> object | None:
    return getattr(command, "review_contract", None)


def _command_review_mode(command: object) -> str:
    return str(getattr(_command_review_contract(command), "review_mode", "") or "").strip()


def _command_subject_policy(command: object) -> object | None:
    command_policy = getattr(command, "command_policy", None)
    return getattr(command_policy, "subject_policy", None)


def _command_supporting_context_policy(command: object) -> object | None:
    command_policy = getattr(command, "command_policy", None)
    return getattr(command_policy, "supporting_context_policy", None)


def _command_policy_string_list(policy: object | None, field_name: str) -> list[str]:
    if policy is None:
        return []
    raw_value = getattr(policy, field_name, None)
    if not isinstance(raw_value, tuple | list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in raw_value:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _command_policy_bool(policy: object | None, field_name: str) -> bool | None:
    if policy is None:
        return None
    value = getattr(policy, field_name, None)
    return value if isinstance(value, bool) else None


def _command_output_policy(command: object) -> object | None:
    command_policy = getattr(command, "command_policy", None)
    return getattr(command_policy, "output_policy", None)


def _command_subject_policy_string(command: object, field_name: str) -> str:
    subject_policy = _command_subject_policy(command)
    value = getattr(subject_policy, field_name, None) if subject_policy is not None else None
    return str(value or "").strip()


def _command_subject_resolution_mode(command: object) -> str:
    return _command_subject_policy_string(command, "resolution_mode")


def _command_subject_kind(command: object) -> str:
    return _command_subject_policy_string(command, "subject_kind")


def _command_has_typed_subject_policy(command: object) -> bool:
    return _command_subject_policy(command) is not None


def _command_effective_context_mode(command: object) -> str:
    """Return the runtime-authoritative context mode for one command."""
    if _command_review_mode(command) == "publication":
        supporting_context_policy = _command_supporting_context_policy(command)
        project_context_mode = str(getattr(supporting_context_policy, "project_context_mode", "") or "").strip()
        if project_context_mode:
            return project_context_mode
    return str(getattr(command, "context_mode", "project-required") or "project-required")


def _command_effective_project_reentry_mode(command: object) -> str:
    """Return the runtime-authoritative project re-entry mode for one command."""
    if _command_review_mode(command) == "publication":
        supporting_context_policy = _command_supporting_context_policy(command)
        project_reentry_mode = str(getattr(supporting_context_policy, "project_reentry_mode", "") or "").strip()
        if project_reentry_mode:
            return project_reentry_mode
    return "allowed" if bool(getattr(command, "project_reentry_capable", False)) else "disallowed"


_PUBLICATION_INPUT_KIND_LABELS = {
    "artifact_path": ["external artifact path"],
    "authoring_intake_manifest": _WRITE_PAPER_EXTERNAL_AUTHORING_EXPLICIT_INPUTS,
    "manuscript_path": ["manuscript path"],
    "manuscript_root": ["paper directory or managed manuscript root"],
    "paste": ["`paste`"],
    "paste_referee_report": ["`paste`"],
    "publication_artifact_path": ["external artifact path"],
    "referee_report_path": ["path to referee report"],
    "referee_report_source": ["path to referee report"],
}


def _publication_input_kind_labels(input_kind: str) -> list[str]:
    canonical = re.sub(r"[^a-z0-9]+", "_", input_kind.casefold()).strip("_")
    labels = _PUBLICATION_INPUT_KIND_LABELS.get(canonical)
    if labels is not None:
        return labels
    return [input_kind.replace("_", " ")]


def _command_explicit_input_labels_from_policy(command: object) -> list[str]:
    subject_policy = _command_subject_policy(command)
    labels: list[str] = []
    seen: set[str] = set()
    for input_kind in _command_policy_string_list(subject_policy, "explicit_input_kinds"):
        for label in _publication_input_kind_labels(input_kind):
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
    return labels


def _command_required_file_patterns(command: object) -> list[str]:
    """Return runtime-authoritative required file patterns for one command."""
    if _command_review_mode(command) == "publication":
        supporting_context_policy = _command_supporting_context_policy(command)
        if supporting_context_policy is not None:
            return _command_policy_string_list(supporting_context_policy, "required_file_patterns")
    requires = getattr(command, "requires", None)
    if not isinstance(requires, Mapping):
        return []
    raw_patterns = requires.get("files")
    if isinstance(raw_patterns, str):
        candidates = [raw_patterns]
    elif isinstance(raw_patterns, list):
        candidates = [item for item in raw_patterns if isinstance(item, str)]
    else:
        return []
    return [pattern.strip() for pattern in candidates if pattern.strip()]


def _command_required_files_present(
    project_root: Path,
    command: object,
) -> tuple[bool, list[str], list[str]]:
    """Return whether command-required files exist under *project_root*.

    Literal file requirements are conjunctive: every declared path must exist.
    Globbed requirements are alternative surfaces: if one or more glob patterns
    are declared, at least one of them must match.
    """
    patterns = _command_required_file_patterns(command)
    if not patterns:
        return True, [], []

    matched_literals: list[str] = []
    matched_globs: list[str] = []
    missing_literals: list[str] = []
    missing_globs: list[str] = []
    for pattern in patterns:
        if glob.has_magic(pattern):
            try:
                if any(project_root.glob(pattern)):
                    matched_globs.append(pattern)
                else:
                    missing_globs.append(pattern)
            except ValueError:
                missing_globs.append(pattern)
            continue

        candidate = Path(pattern)
        resolved = candidate if candidate.is_absolute() else project_root / candidate
        if resolved.exists():
            matched_literals.append(pattern)
        else:
            missing_literals.append(pattern)

    glob_passed = not missing_globs or bool(matched_globs)
    passed = not missing_literals and glob_passed
    matched = [*matched_literals, *matched_globs]
    missing = [*missing_literals, *missing_globs]
    return passed, matched, missing


def _command_explicit_manuscript_subject_kinds(command: object) -> set[str]:
    """Return explicit input kinds that can carry a manuscript subject."""
    subject_policy = _command_subject_policy(command)
    return set(_command_policy_string_list(subject_policy, "explicit_input_kinds")).intersection(
        {"artifact_path", "manuscript_path", "manuscript_root", "publication_artifact_path"}
    )


def _command_supports_positional_manuscript_subject(command: object) -> bool:
    """Return whether one command reads a positional argument as manuscript input."""
    contract = getattr(command, "review_contract", None)
    if not _command_requires_manuscript_context(command):
        return False
    if _review_contract_requests_check(contract, "referee_report_source"):
        return False
    return bool(_command_explicit_manuscript_subject_kinds(command) or _command_required_file_patterns(command))


def _command_supports_explicit_manuscript_subject(command: object) -> bool:
    """Return whether one command accepts manuscript-subject intake in any form."""
    if not _command_requires_manuscript_context(command):
        return False
    return bool(_command_explicit_manuscript_subject_kinds(command) or _command_required_file_patterns(command))


def _command_explicit_manuscript_argument(command: object, arguments: str | None) -> str | None:
    """Extract an explicit manuscript target from command arguments when present."""
    if not isinstance(arguments, str) or not arguments.strip():
        return None

    flagged = _flag_values(arguments, "--manuscript")
    if flagged:
        return flagged[-1]

    if not _command_supports_positional_manuscript_subject(command):
        return None

    positionals = _positional_tokens(arguments, flags_with_values=("--manuscript", "--report"))
    return positionals[0] if positionals else None


def _command_referee_report_arguments(command: object, arguments: str | None) -> tuple[str, ...]:
    """Extract explicit referee-report sources from command arguments when present."""
    contract = getattr(command, "review_contract", None)
    if not _review_contract_requests_check(contract, "referee_report_source"):
        return ()
    if not isinstance(arguments, str) or not arguments.strip():
        return ()

    flagged = tuple(value for value in _flag_values(arguments, "--report") if value and value != "paste")
    if flagged:
        return flagged

    positionals = _positional_tokens(arguments, flags_with_values=("--manuscript", "--report"))
    return tuple(token for token in positionals if token and token != "paste")


def _command_required_files_override_detail(
    project_root: Path,
    command: object,
    arguments: str | None,
    *,
    workspace_cwd: Path | None = None,
    resolved_subject: ResolvedCommandSubject | None = None,
) -> str | None:
    """Return a detail string when explicit review inputs satisfy required-file gating."""
    if not _command_supports_explicit_manuscript_subject(command):
        return None
    if resolved_subject is not None:
        if (
            not resolved_subject.explicit_input
            or resolved_subject.subject_kind != "manuscript"
            or resolved_subject.status != "resolved"
            or resolved_subject.ownership_mode not in {"project_backed", "project_reentry_selected"}
            or resolved_subject.target_path is None
            or resolved_subject.target_path.is_dir()
        ):
            return None
        return (
            "explicit manuscript target satisfies command context: "
            f"{_format_display_path(resolved_subject.target_path)}"
        )
    if not isinstance(arguments, str) or not arguments.strip():
        return None

    manuscript_argument = _command_explicit_manuscript_argument(command, arguments)
    if manuscript_argument is None:
        return None

    manuscript, _ = _resolve_review_preflight_manuscript(
        project_root,
        manuscript_argument,
        allow_markdown=not _command_requires_compiled_manuscript(command),
        restrict_to_supported_roots=_command_explicit_manuscript_subject_uses_supported_roots(command),
        workspace_cwd=workspace_cwd,
        allowed_suffixes=_command_explicit_manuscript_suffixes(command),
    )
    if manuscript is None:
        return None
    return f"explicit manuscript target satisfies command context: {_format_display_path(manuscript)}"


def _command_requires_manuscript_context(command: object) -> bool:
    """Return whether command context should use canonical manuscript resolution."""
    contract = getattr(command, "review_contract", None)
    preflight_checks = getattr(contract, "preflight_checks", ())
    return isinstance(preflight_checks, tuple | list) and "manuscript" in preflight_checks


def _command_requires_compiled_manuscript(command: object) -> bool:
    """Return whether manuscript checks must resolve to a compiled-submission surface."""
    contract = getattr(command, "review_contract", None)
    return _review_contract_requests_check(contract, "compiled_manuscript")


def _command_manuscript_intake_policy(command: object) -> ManuscriptIntakePolicy:
    """Return manuscript-target intake rules derived from command metadata."""
    subject_policy = _command_subject_policy(command)
    allowed_suffixes = set(_command_policy_string_list(subject_policy, "allowed_suffixes"))
    if not allowed_suffixes:
        allowed_suffixes = {".tex"}
        if not _command_requires_compiled_manuscript(command):
            allowed_suffixes.add(".md")
    allow_external_targets = _command_policy_bool(subject_policy, "allow_external_subjects")
    allow_interactive_without_subject = _command_policy_bool(
        subject_policy,
        "allow_interactive_without_subject",
    )
    return ManuscriptIntakePolicy(
        allowed_suffixes=frozenset(allowed_suffixes),
        allow_external_targets=bool(allow_external_targets),
        allow_interactive_standalone_intake=bool(allow_interactive_without_subject),
        interactive_standalone_detail=(
            _PUBLICATION_INTERACTIVE_STANDALONE_DETAIL if allow_interactive_without_subject else ""
        ),
    )


def _command_explicit_manuscript_suffixes(command: object) -> frozenset[str]:
    """Return the allowed explicit manuscript suffixes for one command."""
    allowed_suffixes = _command_manuscript_intake_policy(command).allowed_suffixes
    if getattr(command, "name", "") == "gpd:peer-review" and allowed_suffixes <= {".tex", ".md"}:
        return PEER_REVIEW_ARTIFACT_SUFFIXES
    return allowed_suffixes


def _command_allows_external_manuscript_targets(command: object) -> bool:
    """Return whether a command may accept explicit manuscript targets outside supported roots."""
    return _command_manuscript_intake_policy(command).allow_external_targets


def _command_allows_interactive_standalone_intake(command: object) -> bool:
    """Return whether a project-aware command may prompt for standalone inputs after launch."""
    return _command_manuscript_intake_policy(command).allow_interactive_standalone_intake


def _command_explicit_manuscript_subject_uses_supported_roots(command: object) -> bool:
    """Return whether explicit manuscript arguments must stay under supported manuscript roots."""
    if not _command_supports_explicit_manuscript_subject(command):
        return False
    if _command_allows_external_manuscript_targets(command):
        return False
    subject_policy = _command_subject_policy(command)
    supported_roots = {root for root in _command_policy_string_list(subject_policy, "supported_roots") if root}
    if not supported_roots:
        supported_roots = {
            Path(pattern).parts[0] for pattern in _command_required_file_patterns(command) if Path(pattern).parts
        }
    return bool(supported_roots) and supported_roots <= _SUPPORTED_MANUSCRIPT_ROOT_NAMES


def _command_allows_manuscript_bootstrap(command: object) -> bool:
    """Return whether missing manuscript roots are expected to be bootstrapped."""
    subject_policy = _command_subject_policy(command)
    bootstrap_allowed = _command_policy_bool(subject_policy, "bootstrap_allowed")
    if bootstrap_allowed is not None:
        return bootstrap_allowed
    contract = getattr(command, "review_contract", None)
    if getattr(command, "name", "") == "gpd:peer-review":
        return False
    return (
        _command_requires_manuscript_context(command)
        and not _command_required_file_patterns(command)
        and not _review_contract_requests_check(contract, "compiled_manuscript")
        and not _review_contract_requests_check(contract, "referee_report_source")
    )


def _command_allows_interactive_subject_intake(command: object) -> bool:
    """Return whether a command may launch without a concrete subject and ask interactively."""
    if _command_requires_manuscript_context(command):
        return _command_allows_interactive_standalone_intake(command)
    subject_policy = _command_subject_policy(command)
    return bool(_command_policy_bool(subject_policy, "allow_interactive_without_subject"))


def _command_interactive_subject_detail(command: object, explicit_inputs: list[str]) -> str:
    """Return the standardized detail string for interactive subject intake."""
    if _command_requires_manuscript_context(command):
        return _command_manuscript_intake_policy(command).interactive_standalone_detail
    if not explicit_inputs:
        explicit_inputs = ["a concrete subject"]
    if len(explicit_inputs) == 1:
        subject_text = explicit_inputs[0]
    elif len(explicit_inputs) == 2:
        subject_text = f"{explicit_inputs[0]} or {explicit_inputs[1]}"
    else:
        subject_text = ", ".join(explicit_inputs[:-1]) + f", or {explicit_inputs[-1]}"
    return f"no explicit subject supplied; interactive intake can prompt for {subject_text}"


def _resolved_subject_manuscript_entrypoint(
    resolved_subject: ResolvedCommandSubject | None,
) -> Path | None:
    """Return the resolved manuscript file for subject-scoped commands."""
    if (
        resolved_subject is None
        or resolved_subject.subject_kind != "manuscript"
        or resolved_subject.status != "resolved"
        or resolved_subject.target_path is None
        or resolved_subject.target_path.is_dir()
    ):
        return None
    return resolved_subject.target_path


def _publication_subject_slug_for_manuscript_entrypoint(
    project_root: Path,
    manuscript_entrypoint: Path,
) -> str:
    """Return the managed publication slug for one manuscript entrypoint."""
    manuscript_root = _supported_manuscript_root_for_target(project_root, manuscript_entrypoint)
    if manuscript_root is not None:
        try:
            relative_root = manuscript_root.resolve(strict=False).relative_to(project_root.resolve(strict=False))
        except ValueError:
            relative_root = None
        if (
            relative_root is not None
            and len(relative_root.parts) == 4
            and relative_root.parts[0] == PLANNING_DIR_NAME
            and relative_root.parts[1] == PUBLICATION_DIR_NAME
            and relative_root.parts[3] == PUBLICATION_MANUSCRIPT_DIR_NAME
        ):
            return relative_root.parts[2]

    resolved_root = project_root.resolve(strict=False)
    resolved_entrypoint = manuscript_entrypoint.resolve(strict=False)
    try:
        label = resolved_entrypoint.relative_to(resolved_root).as_posix()
    except ValueError:
        label = resolved_entrypoint.as_posix()
    slug_source = label[: -len(resolved_entrypoint.suffix)] if resolved_entrypoint.suffix else label
    slug = normalize_ascii_slug(slug_source.replace("/", "-")) or "manuscript"
    slug = slug[:48].rstrip("-") or "manuscript"
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def _command_managed_output_bindings(
    *,
    project_root: Path,
    resolved_subject: ResolvedCommandSubject | None,
) -> dict[str, str]:
    """Return dynamic managed-output subtree bindings for the active subject."""
    manuscript_entrypoint = _resolved_subject_manuscript_entrypoint(resolved_subject)
    if manuscript_entrypoint is None:
        return {}
    return {
        "subject_slug": _publication_subject_slug_for_manuscript_entrypoint(project_root, manuscript_entrypoint)
    }


def _command_managed_output_policy(
    command: object,
    *,
    project_root: Path | None = None,
    resolved_subject: ResolvedCommandSubject | None = None,
):
    """Return a storage-path managed-output policy derived from command metadata, when available."""
    from gpd.core.storage_paths import (
        ManagedOutputClass,
        ManagedOutputMatchMode,
        ManagedOutputPolicy,
        ManagedOutputRootKind,
        StageArtifactPolicy,
    )

    output_policy = _command_output_policy(command)
    if output_policy is None:
        return None

    managed_root_raw = str(getattr(output_policy, "managed_root_kind", "") or "").strip().casefold()
    if not managed_root_raw:
        return None
    if managed_root_raw in {"gpd", "gpd_managed_durable", "gpd_internal_other"}:
        managed_root_kind = ManagedOutputRootKind.GPD
        output_class = ManagedOutputClass.GPD_MANAGED_DURABLE
    elif managed_root_raw in {"project", "user_export_durable", "project_local_other"}:
        managed_root_kind = ManagedOutputRootKind.PROJECT
        output_class = ManagedOutputClass.USER_EXPORT_DURABLE
    else:
        return None

    subtree = str(getattr(output_policy, "default_output_subtree", "") or "").strip()
    if not subtree:
        return None
    subtree = subtree.replace("\\", "/")
    if managed_root_kind == ManagedOutputRootKind.GPD:
        if subtree == PLANNING_DIR_NAME:
            subtree = ""
        elif subtree.startswith(f"{PLANNING_DIR_NAME}/"):
            subtree = subtree[len(PLANNING_DIR_NAME) + 1 :]
    elif managed_root_kind == ManagedOutputRootKind.PROJECT and subtree.startswith("./"):
        subtree = subtree[2:]
    subtree_components = tuple(component for component in subtree.split("/") if component and component != ".")

    stage_policy_raw = str(getattr(output_policy, "stage_artifact_policy", "") or "").strip().casefold()
    stage_artifact_policy = (
        StageArtifactPolicy.ALLOWED if stage_policy_raw in {"allowed", "gpd_owned_outputs_only"} else StageArtifactPolicy.DISALLOWED
    )

    output_mode = str(getattr(output_policy, "output_mode", "") or "").strip().casefold()
    match_mode = ManagedOutputMatchMode.EXACT if output_mode == "exact" else ManagedOutputMatchMode.SUBTREE

    try:
        policy = ManagedOutputPolicy(
            output_class=output_class,
            managed_root_kind=managed_root_kind,
            default_output_subtree=subtree_components,
            match_mode=match_mode,
            stage_artifact_policy=stage_artifact_policy,
        )
    except ValueError:
        return None

    if not any(re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", component) for component in policy.default_output_subtree):
        return policy
    if project_root is None:
        return None
    try:
        return policy.bind_output_subtree_placeholders(
            _command_managed_output_bindings(project_root=project_root, resolved_subject=resolved_subject)
        )
    except ValueError:
        return None


def _command_managed_output_root(
    command: object,
    *,
    project_root: Path,
    resolved_subject: ResolvedCommandSubject | None = None,
) -> Path | None:
    """Return the effective managed output root for one command, when typed policy declares it."""
    from gpd.core.storage_paths import ProjectStorageLayout

    policy = _command_managed_output_policy(
        command,
        project_root=project_root,
        resolved_subject=resolved_subject,
    )
    if policy is None:
        return None
    return ProjectStorageLayout(project_root).managed_output_path(policy)


def _command_managed_output_context_root(
    *,
    workspace_root: Path,
    context_root: Path,
    project_exists: bool,
) -> Path:
    """Choose the root that owns managed outputs for one command-context preflight."""
    return context_root if project_exists else workspace_root


def _command_manuscript_bootstrap_detail() -> str:
    """Return the canonical bootstrap detail for manuscript-scaffolding commands."""
    return (
        "no manuscript entrypoint found under paper/, manuscript/, or draft/; "
        "fresh bootstrap is allowed and will scaffold a topic-specific manuscript stem under ./paper/"
    )


def _resolved_project_root_for_subject(context_root: Path) -> Path | None:
    """Return the project root bound to one subject-resolution context, if any."""
    from gpd.core.constants import ProjectLayout

    candidate = context_root.resolve(strict=False)
    return candidate if ProjectLayout(candidate).project_md.exists() else None


def _command_subject_base_ownership_mode(
    *,
    resolved_project_root: Path | None,
    project_root_source: str | None,
    project_root_auto_selected: bool,
) -> str:
    """Return the default subject ownership mode before explicit-target overrides."""
    if (
        resolved_project_root is not None
        and project_root_auto_selected
        and str(project_root_source or "").strip() == "recent_project"
    ):
        return "project_reentry_selected"
    if resolved_project_root is not None:
        return "project_backed"
    return "workspace_locked"


def _resolve_review_knowledge_target(
    context_root: Path,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
) -> tuple[str, Path | None, str]:
    """Resolve one canonical review-knowledge target under ``GPD/knowledge``."""
    workspace_root = (workspace_cwd or context_root).resolve(strict=False)
    if not isinstance(subject, str) or not subject.strip():
        return "missing", None, "missing explicit knowledge target"

    tokens = _split_command_arguments(subject)
    candidate = next((token for token in tokens if token and not token.startswith("-")), "")
    if not candidate:
        return "missing", None, "missing explicit knowledge target"

    knowledge_dir = context_root / "GPD" / "knowledge"
    if _looks_like_review_knowledge_id_token(candidate):
        target_path = (knowledge_dir / f"{candidate}.md").resolve(strict=False)
        return "resolved", target_path, f"canonical knowledge id resolves to {_format_display_path(target_path)}"

    if not _looks_like_digest_knowledge_path_token(candidate):
        return "invalid", None, "review target must be a canonical K-* id or GPD/knowledge/{knowledge_id}.md path"

    target_path = (_resolve_subject_path(candidate, base=workspace_root) or (workspace_root / candidate)).resolve(strict=False)
    try:
        relative = target_path.relative_to(context_root.resolve(strict=False))
    except ValueError:
        return "invalid", target_path, "review target must resolve under the current workspace's GPD/knowledge/"

    if not (
        len(relative.parts) == 3
        and relative.parts[0] == "GPD"
        and relative.parts[1] == "knowledge"
        and target_path.suffix.lower() == ".md"
        and target_path.stem.startswith("K-")
        and normalize_ascii_slug(target_path.stem[2:]) == target_path.stem[2:]
    ):
        return "invalid", target_path, "review target must resolve to canonical GPD/knowledge/{knowledge_id}.md"
    return "resolved", target_path, f"canonical knowledge target {_format_display_path(target_path)}"


def _nonpublication_subject_ownership_mode(
    *,
    target_path: Path | None,
    resolved_project_root: Path | None,
    base_ownership_mode: str,
) -> str:
    """Return ownership mode for a non-publication resolved subject."""
    if target_path is None:
        return base_ownership_mode
    if resolved_project_root is None:
        return "workspace_locked"
    try:
        target_path.resolve(strict=False).relative_to(resolved_project_root.resolve(strict=False))
    except ValueError:
        return "external_subject"
    return base_ownership_mode


def _build_nonpublication_resolved_command_subject(
    project_root: Path,
    command: object,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
    project_root_source: str | None = None,
    project_root_auto_selected: bool = False,
    reentry_mode: str | None = None,
) -> ResolvedCommandSubject | None:
    """Resolve the shared subject envelope for typed non-publication commands."""
    if _command_requires_manuscript_context(command):
        return None
    resolution_mode = _command_subject_resolution_mode(command)
    if not resolution_mode:
        return None

    workspace_root = (workspace_cwd or project_root).resolve(strict=False)
    context_root = project_root.resolve(strict=False)
    resolved_project_root = _resolved_project_root_for_subject(context_root)
    resolved_project_root_source = project_root_source or ("workspace" if resolved_project_root is not None else None)
    ancestor_walked_up = (
        resolved_project_root is not None
        and resolved_project_root != workspace_root
        and _subject_is_relative_to(workspace_root, resolved_project_root)
    )
    base_ownership_mode = _command_subject_base_ownership_mode(
        resolved_project_root=resolved_project_root,
        project_root_source=resolved_project_root_source,
        project_root_auto_selected=project_root_auto_selected,
    )
    explicit_inputs = _command_explicit_input_labels_from_policy(command)
    subject_kind = _command_subject_kind(command) or "subject"

    if (
        not (isinstance(subject, str) and subject.strip())
        and _command_allows_interactive_subject_intake(command)
    ):
        return ResolvedCommandSubject(
            command=str(getattr(command, "name", "") or ""),
            workspace_root=workspace_root,
            resolved_project_root=resolved_project_root,
            context_root=context_root,
            target_path=None,
            target_root=None,
            subject_kind=subject_kind,
            ownership_mode=base_ownership_mode,
            status="interactive",
            exists=False,
            explicit_input=False,
            project_root_source=resolved_project_root_source,
            project_root_auto_selected=project_root_auto_selected,
            reentry_mode=reentry_mode,
            ancestor_walked_up=ancestor_walked_up,
            detail=_command_interactive_subject_detail(command, explicit_inputs),
        )

    tokens: list[str]
    if resolution_mode == "phase_or_topic":
        tokens = _positional_tokens(subject, flags_with_values=("--depth", "-d"))
    else:
        tokens = _positional_tokens(subject)
    if not tokens:
        if _command_allows_interactive_subject_intake(command):
            return ResolvedCommandSubject(
                command=str(getattr(command, "name", "") or ""),
                workspace_root=workspace_root,
                resolved_project_root=resolved_project_root,
                context_root=context_root,
                target_path=None,
                target_root=None,
                subject_kind=subject_kind,
                ownership_mode=base_ownership_mode,
                status="interactive",
                exists=False,
                explicit_input=False,
                project_root_source=resolved_project_root_source,
                project_root_auto_selected=project_root_auto_selected,
                reentry_mode=reentry_mode,
                ancestor_walked_up=ancestor_walked_up,
                detail=_command_interactive_subject_detail(command, explicit_inputs),
            )
        return ResolvedCommandSubject(
            command=str(getattr(command, "name", "") or ""),
            workspace_root=workspace_root,
            resolved_project_root=resolved_project_root,
            context_root=context_root,
            target_path=None,
            target_root=None,
            subject_kind=subject_kind,
            ownership_mode=base_ownership_mode,
            status="missing",
            exists=False,
            explicit_input=False,
            project_root_source=resolved_project_root_source,
            project_root_auto_selected=project_root_auto_selected,
            reentry_mode=reentry_mode,
            ancestor_walked_up=ancestor_walked_up,
            detail=f"missing explicit subject ({', '.join(explicit_inputs or ['subject'])})",
        )

    target_path: Path | None = None
    target_root: Path | None = None
    detail = "explicit subject supplied"
    status = "resolved"

    if resolution_mode in {"knowledge_review_target", "explicit_current_workspace_canonical_target"}:
        status, target_path, detail = _resolve_review_knowledge_target(
            context_root,
            subject,
            workspace_cwd=workspace_root,
        )
        if target_path is not None:
            target_root = target_path.parent
    elif resolution_mode == "knowledge_input":
        first = tokens[0]
        if _looks_like_digest_knowledge_path_token(first):
            target_path = (_resolve_subject_path(first, base=workspace_root) or (workspace_root / first)).resolve(strict=False)
            target_root = target_path if target_path.is_dir() else target_path.parent
            detail = f"explicit knowledge input path {_format_display_path(target_path)}"
        elif _looks_like_digest_knowledge_arxiv_token(first):
            detail = f"explicit arXiv knowledge input {first}"
        else:
            detail = "explicit knowledge topic supplied"
    elif resolution_mode in {"compare_subject", "compare_experiment_subject"}:
        first = tokens[0]
        if _looks_like_digest_knowledge_path_token(first):
            target_path = (_resolve_subject_path(first, base=workspace_root) or (workspace_root / first)).resolve(strict=False)
            target_root = target_path if target_path.is_dir() else target_path.parent
            detail = f"explicit comparison target {_format_display_path(target_path)}"
        else:
            detail = "explicit comparison target supplied"
    elif resolution_mode == "explanation_input":
        first = tokens[0]
        if _looks_like_digest_knowledge_path_token(first):
            target_path = (_resolve_subject_path(first, base=workspace_root) or (workspace_root / first)).resolve(strict=False)
            target_root = target_path if target_path.is_dir() else target_path.parent
            detail = f"explicit explanation anchor {_format_display_path(target_path)}"
        else:
            detail = "explicit explanation subject supplied"
    elif resolution_mode == "phase_or_topic":
        first = tokens[0]
        if re.fullmatch(r"\d+(?:\.\d+)*", first):
            subject_kind = "phase"
            detail = f"explicit phase subject {first}"
        else:
            detail = "explicit discovery topic supplied"
    elif resolution_mode == "literature_topic":
        detail = "explicit literature-review topic supplied"

    ownership_mode = _nonpublication_subject_ownership_mode(
        target_path=target_path,
        resolved_project_root=resolved_project_root,
        base_ownership_mode=base_ownership_mode,
    )

    return ResolvedCommandSubject(
        command=str(getattr(command, "name", "") or ""),
        workspace_root=workspace_root,
        resolved_project_root=resolved_project_root,
        context_root=context_root,
        target_path=target_path,
        target_root=target_root,
        subject_kind=subject_kind,
        ownership_mode=ownership_mode,
        status=status,
        exists=target_path.exists() if target_path is not None else False,
        explicit_input=True,
        project_root_source=resolved_project_root_source,
        project_root_auto_selected=project_root_auto_selected,
        reentry_mode=reentry_mode,
        ancestor_walked_up=ancestor_walked_up,
        detail=detail,
    )


def _build_resolved_command_subject(
    project_root: Path,
    command: object,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
    project_root_source: str | None = None,
    project_root_auto_selected: bool = False,
    reentry_mode: str | None = None,
) -> ResolvedCommandSubject | None:
    """Resolve the shared subject envelope for publication/manuscript-aware commands."""
    from gpd.core.constants import ProjectLayout

    generic_resolution = _build_nonpublication_resolved_command_subject(
        project_root,
        command,
        subject,
        workspace_cwd=workspace_cwd,
        project_root_source=project_root_source,
        project_root_auto_selected=project_root_auto_selected,
        reentry_mode=reentry_mode,
    )
    if generic_resolution is not None:
        return generic_resolution

    if not _command_requires_manuscript_context(command):
        return None

    workspace_root = (workspace_cwd or project_root).resolve(strict=False)
    context_root = project_root.resolve(strict=False)
    resolved_project_root = _resolved_project_root_for_subject(context_root)
    resolved_project_root_source = project_root_source or ("workspace" if resolved_project_root is not None else None)
    ancestor_walked_up = (
        resolved_project_root is not None
        and resolved_project_root != workspace_root
        and _subject_is_relative_to(workspace_root, resolved_project_root)
    )
    base_ownership_mode = _command_subject_base_ownership_mode(
        resolved_project_root=resolved_project_root,
        project_root_source=resolved_project_root_source,
        project_root_auto_selected=project_root_auto_selected,
    )
    if str(getattr(command, "name", "") or "") == "gpd:write-paper" and resolved_project_root is None:
        intake_resolution = _resolve_write_paper_external_authoring_intake(
            context_root,
            subject,
            workspace_cwd=workspace_root,
        )
        if intake_resolution is None:
            return ResolvedCommandSubject(
                command=str(getattr(command, "name", "") or ""),
                workspace_root=workspace_root,
                resolved_project_root=resolved_project_root,
                context_root=context_root,
                target_path=None,
                target_root=None,
                subject_kind="publication",
                ownership_mode=base_ownership_mode,
                status="missing",
                exists=False,
                explicit_input=False,
                project_root_source=resolved_project_root_source,
                project_root_auto_selected=project_root_auto_selected,
                reentry_mode=reentry_mode,
                ancestor_walked_up=ancestor_walked_up,
                detail=_WRITE_PAPER_EXTERNAL_AUTHORING_DETAIL,
            )

        intake_target_root = (
            intake_resolution.manuscript_root
            or intake_resolution.intake_root
            or (
                intake_resolution.intake_path.parent
                if intake_resolution.intake_path is not None
                else None
            )
        )
        if intake_resolution.status == "resolved":
            return ResolvedCommandSubject(
                command=str(getattr(command, "name", "") or ""),
                workspace_root=workspace_root,
                resolved_project_root=resolved_project_root,
                context_root=context_root,
                target_path=intake_resolution.intake_path,
                target_root=intake_resolution.manuscript_root,
                subject_kind="publication",
                ownership_mode="external_authoring_intake",
                status="bootstrap",
                exists=intake_resolution.intake_path is not None and intake_resolution.intake_path.exists(),
                explicit_input=True,
                project_root_source=resolved_project_root_source,
                project_root_auto_selected=project_root_auto_selected,
                reentry_mode=reentry_mode,
                ancestor_walked_up=ancestor_walked_up,
                detail=intake_resolution.detail,
            )

        return ResolvedCommandSubject(
            command=str(getattr(command, "name", "") or ""),
            workspace_root=workspace_root,
            resolved_project_root=resolved_project_root,
            context_root=context_root,
            target_path=intake_resolution.intake_path,
            target_root=intake_target_root,
            subject_kind="publication",
            ownership_mode="external_authoring_intake",
            status=intake_resolution.status,
            exists=intake_resolution.intake_path is not None and intake_resolution.intake_path.exists(),
            explicit_input=True,
            project_root_source=resolved_project_root_source,
            project_root_auto_selected=project_root_auto_selected,
            reentry_mode=reentry_mode,
            ancestor_walked_up=ancestor_walked_up,
            detail=intake_resolution.detail,
        )
    manuscript_subject = _command_explicit_manuscript_argument(command, subject)

    if (
        _command_supports_explicit_manuscript_subject(command)
        and not (isinstance(subject, str) and subject.strip())
        and _command_allows_interactive_standalone_intake(command)
        and not ProjectLayout(context_root).project_md.exists()
    ):
        return ResolvedCommandSubject(
            command=str(getattr(command, "name", "") or ""),
            workspace_root=workspace_root,
            resolved_project_root=resolved_project_root,
            context_root=context_root,
            target_path=None,
            target_root=None,
            subject_kind="manuscript",
            ownership_mode=base_ownership_mode,
            status="interactive",
            exists=False,
            explicit_input=False,
            project_root_source=resolved_project_root_source,
            project_root_auto_selected=project_root_auto_selected,
            reentry_mode=reentry_mode,
            ancestor_walked_up=ancestor_walked_up,
            detail=_command_manuscript_intake_policy(command).interactive_standalone_detail,
        )

    target_resolution = _resolve_review_preflight_manuscript_target(
        context_root,
        manuscript_subject if _command_supports_explicit_manuscript_subject(command) else None,
        allow_markdown=not _command_requires_compiled_manuscript(command),
        restrict_to_supported_roots=_command_explicit_manuscript_subject_uses_supported_roots(command),
        workspace_cwd=workspace_root,
        allowed_suffixes=_command_explicit_manuscript_suffixes(command),
    )
    target_path = target_resolution.manuscript or target_resolution.requested_target
    target_root = target_resolution.manuscript_root
    if target_root is None and target_path is not None:
        target_root = target_path if target_path.is_dir() else target_path.parent

    status = target_resolution.status
    detail = target_resolution.detail
    if (
        _command_allows_manuscript_bootstrap(command)
        and target_resolution.requested_target is None
        and status == "missing"
    ):
        status = "bootstrap"
        detail = _command_manuscript_bootstrap_detail()
        target_root = context_root / "paper"

    ownership_mode = base_ownership_mode
    ownership_target = target_resolution.manuscript or target_resolution.requested_target
    if ownership_target is not None and (
        resolved_project_root is None
        or not _path_is_within_supported_manuscript_root(resolved_project_root, ownership_target)
    ):
        ownership_mode = "external_artifact"

    return ResolvedCommandSubject(
        command=str(getattr(command, "name", "") or ""),
        workspace_root=workspace_root,
        resolved_project_root=resolved_project_root,
        context_root=context_root,
        target_path=target_path,
        target_root=target_root,
        subject_kind="manuscript",
        ownership_mode=ownership_mode,
        status=status,
        exists=target_path.exists() if target_path is not None else False,
        explicit_input=target_resolution.requested_target is not None,
        project_root_source=resolved_project_root_source,
        project_root_auto_selected=project_root_auto_selected,
        reentry_mode=reentry_mode,
        ancestor_walked_up=ancestor_walked_up,
        detail=detail,
    )


def _command_context_manuscript_check(
    project_root: Path,
    command: object,
    arguments: str | None,
    *,
    workspace_cwd: Path | None = None,
    resolved_subject: ResolvedCommandSubject | None = None,
) -> tuple[bool, str] | None:
    """Return a canonical manuscript-context check for publication commands."""
    if not _command_requires_manuscript_context(command):
        return None
    subject_resolution = resolved_subject or _build_resolved_command_subject(
        project_root,
        command,
        arguments,
        workspace_cwd=workspace_cwd,
    )
    if subject_resolution is None:
        return None
    return subject_resolution.status in {"resolved", "bootstrap"}, subject_resolution.detail


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


def _canonical_command_name(command_name: str) -> str:
    """Normalize a CLI command name to the registry's public gpd:name form."""
    return canonical_command_label(command_name)


def _command_supports_project_reentry(command: object) -> bool:
    """Return whether one registry command can recover a project root before execution."""
    project_reentry_mode = _command_effective_project_reentry_mode(command).casefold()
    return project_reentry_mode not in {"", "disallowed", "false", "none"}


def _resolve_registry_command(command_name: str) -> tuple[object, str]:
    """Resolve a command name through the registry and preserve its public name."""
    from gpd import registry as content_registry

    command = content_registry.get_command(command_name)
    return command, _canonical_command_name(command_name)


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


def _normalize_review_scope_selector(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _resolved_subject_scope_selectors(resolved_subject: ResolvedCommandSubject | None) -> frozenset[str]:
    if resolved_subject is None:
        return frozenset()

    selectors: set[str] = set()
    ownership_mode = _normalize_review_scope_selector(resolved_subject.ownership_mode)
    if ownership_mode:
        selectors.add(ownership_mode)
    status = _normalize_review_scope_selector(resolved_subject.status)
    if status:
        selectors.add(status)
    if resolved_subject.explicit_input:
        selectors.add("explicit_input")
        if resolved_subject.subject_kind == "manuscript":
            selectors.add("explicit_manuscript")
    if resolved_subject.ancestor_walked_up:
        selectors.add("ancestor_project")
    if resolved_subject.ownership_mode in {"project_backed", "project_reentry_selected"}:
        selectors.add("project_backed")
    if resolved_subject.ownership_mode == "external_artifact":
        selectors.update(
            {
                "explicit_artifact",
                "explicit_external_manuscript",
                "explicit_external_subject",
                "external_artifact",
            }
        )
    if resolved_subject.ownership_mode == "external_authoring_intake":
        selectors.update(
            {
                "external_authoring_intake",
                "explicit_intake_manifest",
                "authoring_intake",
            }
        )
    if resolved_subject.status == "interactive":
        selectors.update({"interactive", "interactive_standalone"})
    return frozenset(selectors)


def _active_review_contract_scope_variants(
    contract: object,
    *,
    resolved_subject: ResolvedCommandSubject | None,
) -> list[object]:
    active_selectors = _resolved_subject_scope_selectors(resolved_subject)
    active_variants: list[object] = []
    for variant in list(getattr(contract, "scope_variants", []) or []):
        scope = _normalize_review_scope_selector(str(getattr(variant, "scope", "") or ""))
        if scope and scope in active_selectors:
            active_variants.append(variant)
    return active_variants


def _effective_review_contract_scope_overrides(
    contract: object,
    *,
    active_scope_variants: list[object],
) -> tuple[list[str], list[str], list[str]]:
    required_outputs = list(getattr(contract, "required_outputs", []) or [])
    required_evidence = list(getattr(contract, "required_evidence", []) or [])
    blocking_conditions = list(getattr(contract, "blocking_conditions", []) or [])
    for variant in active_scope_variants:
        outputs_override = list(getattr(variant, "required_outputs_override", []) or [])
        if outputs_override:
            required_outputs = outputs_override
        evidence_override = list(getattr(variant, "required_evidence_override", []) or [])
        if evidence_override:
            required_evidence = evidence_override
        blocking_override = list(getattr(variant, "blocking_conditions_override", []) or [])
        if blocking_override:
            blocking_conditions = blocking_override
    return required_outputs, required_evidence, blocking_conditions


def _publication_subject_preflight_policy(
    command: object,
    *,
    resolved_subject: ResolvedCommandSubject | None,
) -> PublicationSubjectPreflightPolicy:
    """Return publication preflight relaxations derived from the shared subject envelope."""
    contract = _command_review_contract(command)
    if _command_review_mode(command) != "publication":
        return PublicationSubjectPreflightPolicy()

    active_scopes = _resolved_subject_scope_selectors(resolved_subject)
    active_scope_variants = _active_review_contract_scope_variants(
        contract,
        resolved_subject=resolved_subject,
    )
    relaxed_checks: set[str] = set()
    optional_checks: set[str] = set()
    detail_overrides: dict[str, str] = {}
    for variant in active_scope_variants:
        relaxed_checks.update(list(getattr(variant, "relaxed_preflight_checks", []) or []))
        optional_checks.update(list(getattr(variant, "optional_preflight_checks", []) or []))

    if active_scopes.intersection({"external_authoring_intake", "explicit_intake_manifest", "authoring_intake"}):
        for check_name, detail in _WRITE_PAPER_EXTERNAL_AUTHORING_OPTIONAL_DETAILS.items():
            if check_name in relaxed_checks or check_name in optional_checks:
                detail_overrides.setdefault(check_name, detail)

    if active_scopes.intersection({"explicit_artifact", "external_artifact"}):
        for check_name, detail in _EXTERNAL_ARTIFACT_OPTIONAL_DETAILS.items():
            if check_name in relaxed_checks or check_name in optional_checks:
                detail_overrides.setdefault(check_name, detail)

    required_outputs, required_evidence, blocking_conditions = _effective_review_contract_scope_overrides(
        contract,
        active_scope_variants=active_scope_variants,
    )
    return PublicationSubjectPreflightPolicy(
        active_scopes=active_scopes,
        relaxed_checks=frozenset(relaxed_checks),
        optional_checks=frozenset(optional_checks),
        detail_overrides=detail_overrides,
        required_outputs=tuple(required_outputs),
        required_evidence=tuple(required_evidence),
        blocking_conditions=tuple(blocking_conditions),
    )


def _peer_review_standalone_artifact_mode(
    project_root: Path,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
) -> bool:
    """Return whether peer-review should treat the current request as external-artifact mode."""
    return _peer_review_mode_resolution(project_root, subject, workspace_cwd=workspace_cwd).standalone_artifact_mode


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
    """Evaluate whether a command can run in the current workspace context."""
    from gpd.core.constants import ProjectLayout

    cwd = _get_cwd()
    command, public_command_name = _resolve_registry_command(command_name)
    context_cwd = _command_preflight_cwd(command, cwd=cwd, arguments=arguments)
    layout = ProjectLayout(context_cwd)
    project_exists = layout.project_md.exists()
    dispatch_note = _runtime_surface_dispatch_note(cwd=cwd)
    init_command = _active_runtime_new_project_command(cwd=cwd)
    effective_context_mode = _command_effective_context_mode(command)

    checks: list[CommandContextCheck] = []

    def add_check(name: str, passed: bool, detail: str, *, blocking: bool = True) -> None:
        checks.append(CommandContextCheck(name=name, passed=passed, detail=detail, blocking=blocking))

    add_check("context_mode", True, f"context_mode={effective_context_mode}", blocking=False)

    if effective_context_mode == "global":
        add_check("project_context", True, "command runs without project context", blocking=False)
        return CommandContextPreflightResult(
            command=public_command_name,
            context_mode=effective_context_mode,
            passed=True,
            project_exists=project_exists,
            explicit_inputs=[],
            guidance="",
            checks=checks,
            validated_surface=_validated_runtime_surface(cwd=cwd),
            public_runtime_command_prefix=_active_runtime_command_prefix(cwd=cwd) or "",
            dispatch_note=dispatch_note,
        )

    if effective_context_mode == "projectless":
        add_check(
            "project_context",
            True,
            ("initialized project detected" if project_exists else "no initialized project required"),
            blocking=False,
        )
        return CommandContextPreflightResult(
            command=public_command_name,
            context_mode=effective_context_mode,
            passed=True,
            project_exists=project_exists,
            explicit_inputs=[],
            guidance="",
            checks=checks,
            validated_surface=_validated_runtime_surface(cwd=cwd),
            public_runtime_command_prefix=_active_runtime_command_prefix(cwd=cwd) or "",
            dispatch_note=dispatch_note,
        )

    if effective_context_mode == "project-required":
        required_file_patterns = _command_required_file_patterns(command)
        if _command_supports_project_reentry(command):
            reentry = _status_command_reentry(cwd)
            selected_root = reentry.resolved_project_root or context_cwd
            layout = ProjectLayout(selected_root)
            state_exists, roadmap_exists, project_exists = recoverable_project_context(selected_root)
            resolved_subject = _build_resolved_command_subject(
                selected_root,
                command,
                arguments,
                workspace_cwd=cwd,
                project_root_source=reentry.source or "workspace",
                project_root_auto_selected=reentry.auto_selected,
                reentry_mode=reentry.mode,
            )
            if reentry.auto_selected and reentry.project_root:
                add_check(
                    "project_reentry",
                    True,
                    f"auto-selected recoverable recent project {_format_display_path(reentry.project_root)}",
                    blocking=False,
                )
            elif reentry.requires_user_selection:
                add_check(
                    "project_reentry",
                    False,
                    "multiple recoverable recent projects are available; explicit selection required",
                    blocking=False,
                )
            elif reentry.has_current_workspace_candidate:
                add_check(
                    "project_reentry",
                    True,
                    "current workspace or ancestor project root is recoverable",
                    blocking=False,
                )
            else:
                add_check(
                    "project_reentry",
                    False,
                    "no recoverable current-workspace or uniquely recoverable recent-project target found",
                    blocking=False,
                )
            add_check(
                "state_exists",
                state_exists,
                (
                    "recoverable state present"
                    if state_exists
                    else f"missing {_format_display_path(layout.state_json)} and {_format_display_path(layout.state_md)}"
                ),
                blocking=False,
            )
            add_check(
                "roadmap_exists",
                roadmap_exists,
                (
                    f"{_format_display_path(layout.roadmap)} present"
                    if roadmap_exists
                    else f"missing {_format_display_path(layout.roadmap)}"
                ),
                blocking=False,
            )
            add_check(
                "project_exists",
                project_exists,
                (
                    f"{_format_display_path(layout.project_md)} present"
                    if project_exists
                    else f"missing {_format_display_path(layout.project_md)}"
                ),
                blocking=False,
            )
            required_files_present = True
            matched_patterns: list[str] = []
            missing_patterns: list[str] = []
            manuscript_context_passed = True
            manuscript_context_detail = ""
            if required_file_patterns:
                required_files_present, matched_patterns, missing_patterns = _command_required_files_present(
                    selected_root,
                    command,
                )
                override_detail = None
                if not required_files_present:
                    override_detail = _command_required_files_override_detail(
                        selected_root,
                        command,
                        arguments,
                        workspace_cwd=cwd,
                        resolved_subject=resolved_subject,
                    )
                    if override_detail is not None:
                        required_files_present = True
                        matched_patterns = [override_detail]
                        missing_patterns = []
                add_check(
                    "required_files",
                    required_files_present,
                    (
                        override_detail
                        if required_files_present and override_detail is not None
                        else "matching required files present: " + ", ".join(matched_patterns)
                        if required_files_present
                        else "missing required files or unmatched patterns: " + ", ".join(missing_patterns)
                    ),
                    blocking=False,
                )
            manuscript_context = _command_context_manuscript_check(
                selected_root,
                command,
                arguments,
                workspace_cwd=cwd,
                resolved_subject=resolved_subject,
            )
            if manuscript_context is not None:
                manuscript_context_passed, manuscript_context_detail = manuscript_context
                add_check(
                    "manuscript",
                    manuscript_context_passed,
                    manuscript_context_detail,
                    blocking=False,
                )
            recoverable = (
                (state_exists or roadmap_exists or project_exists)
                and required_files_present
                and manuscript_context_passed
                and not reentry.requires_user_selection
            )
            guidance = (
                ""
                if recoverable
                else (
                    "This command found multiple recoverable recent GPD projects and will not switch silently. "
                    f"Use `{local_cli_resume_recent_command()}` to pick the right project explicitly, then reopen it in the runtime."
                    if reentry.requires_user_selection
                    else (
                        _build_recoverable_workspace_guidance(init_command=init_command)
                        if not (state_exists or roadmap_exists or project_exists)
                        else manuscript_context_detail
                        if not manuscript_context_passed
                        else "This command requires one of the declared required files: "
                        + ", ".join(required_file_patterns)
                    )
                )
            )
            return CommandContextPreflightResult(
                command=public_command_name,
                context_mode=effective_context_mode,
                passed=recoverable,
                project_exists=project_exists,
                explicit_inputs=[],
                guidance=guidance,
                checks=checks,
                validated_surface=_validated_runtime_surface(cwd=cwd),
                public_runtime_command_prefix=_active_runtime_command_prefix(cwd=cwd) or "",
                dispatch_note=dispatch_note,
                resolved_subject=resolved_subject,
            )
        add_check(
            "project_exists",
            project_exists,
            (
                f"{_format_display_path(layout.project_md)} present"
                if project_exists
                else f"missing {_format_display_path(layout.project_md)}"
            ),
        )
        required_file_patterns = _command_required_file_patterns(command)
        resolved_subject = _build_resolved_command_subject(
            context_cwd,
            command,
            arguments,
            workspace_cwd=cwd,
            project_root_source="workspace",
            project_root_auto_selected=False,
            reentry_mode="current-workspace" if project_exists else None,
        )
        manuscript_context = _command_context_manuscript_check(
            context_cwd,
            command,
            arguments,
            workspace_cwd=cwd,
            resolved_subject=resolved_subject,
        )
        if required_file_patterns:
            required_files_present, matched_patterns, missing_patterns = _command_required_files_present(
                context_cwd,
                command,
            )
            override_detail = None
            if not required_files_present:
                override_detail = _command_required_files_override_detail(
                    context_cwd,
                    command,
                    arguments,
                    workspace_cwd=cwd,
                    resolved_subject=resolved_subject,
                )
                if override_detail is not None:
                    required_files_present = True
                    matched_patterns = [override_detail]
                    missing_patterns = []
            add_check(
                "required_files",
                required_files_present,
                (
                    override_detail
                    if required_files_present and override_detail is not None
                    else "matching required files present: " + ", ".join(matched_patterns)
                    if required_files_present
                    else "missing required files or unmatched patterns: " + ", ".join(missing_patterns)
                ),
            )
        else:
            required_files_present = True
        manuscript_context_passed = True
        manuscript_context_detail = ""
        if manuscript_context is not None:
            manuscript_context_passed, manuscript_context_detail = manuscript_context
            add_check(
                "manuscript",
                manuscript_context_passed,
                manuscript_context_detail,
            )
        passed = project_exists and required_files_present and manuscript_context_passed
        guidance = (
            ""
            if passed
            else (
                "This command requires an initialized GPD project."
                if not project_exists
                else manuscript_context_detail
                if not manuscript_context_passed
                else "This command requires one of the declared required files: " + ", ".join(required_file_patterns)
            )
        )
        return CommandContextPreflightResult(
            command=public_command_name,
            context_mode=effective_context_mode,
            passed=passed,
            project_exists=project_exists,
            explicit_inputs=[],
            guidance=guidance,
            checks=checks,
            validated_surface=_validated_runtime_surface(cwd=cwd),
            public_runtime_command_prefix=_active_runtime_command_prefix(cwd=cwd) or "",
            dispatch_note=dispatch_note,
            resolved_subject=resolved_subject,
        )

    explicit_inputs = _command_explicit_input_labels_from_policy(command)
    predicate: Callable[[str | None], bool] = _has_simple_positional_inputs
    project_aware_override = _PROJECT_AWARE_EXPLICIT_INPUTS.get(str(getattr(command, "name", "") or ""))
    if project_aware_override is not None:
        explicit_inputs, predicate = project_aware_override
    elif not explicit_inputs:
        explicit_inputs, predicate = _PROJECT_AWARE_EXPLICIT_INPUTS.get(
            command.name,
            (
                [command.argument_hint.strip()] if command.argument_hint.strip() else ["explicit command inputs"],
                _has_simple_positional_inputs,
            ),
        )
    resolved_subject = _build_resolved_command_subject(
        context_cwd,
        command,
        arguments,
        workspace_cwd=cwd,
        project_root_source="workspace" if project_exists else None,
        project_root_auto_selected=False,
        reentry_mode="current-workspace" if project_exists else None,
    )
    resolved_mode = ""
    mode_reason = ""
    explicit_inputs_detail = "explicit standalone inputs detected"
    peer_review_has_explicit_target = command.name == "gpd:peer-review" and _has_simple_positional_inputs(arguments)
    if resolved_subject is not None and not _command_requires_manuscript_context(command):
        explicit_inputs_ok = resolved_subject.status == "resolved"
        interactive_intake_allowed = resolved_subject.status == "interactive"
    else:
        explicit_inputs_ok = predicate(arguments)
        if (
            str(getattr(command, "name", "") or "") == "gpd:write-paper"
            and _has_write_paper_external_authoring_intake(arguments)
        ):
            explicit_inputs_ok = bool(
                resolved_subject is not None
                and resolved_subject.ownership_mode == "external_authoring_intake"
                and resolved_subject.status in {"resolved", "bootstrap"}
            )
        if command.name == "gpd:peer-review":
            peer_review_mode = _peer_review_mode_resolution(context_cwd, arguments, workspace_cwd=cwd)
            resolved_mode = peer_review_mode.resolved_mode
            mode_reason = peer_review_mode.mode_reason
            if peer_review_has_explicit_target:
                explicit_inputs_ok = peer_review_mode.resolved_mode != PEER_REVIEW_INVALID_SUBJECT_MODE
                explicit_inputs_detail = (
                    peer_review_mode.resolution_detail
                    if explicit_inputs_ok
                    else f"invalid explicit review target: {peer_review_mode.mode_reason}"
                )
        interactive_intake_allowed = (
            _command_allows_interactive_subject_intake(command)
            and not explicit_inputs_ok
            and not _has_simple_positional_inputs(arguments)
        )
    subject_required = _command_has_typed_subject_policy(command)
    subject_context_ready = resolved_subject is not None and resolved_subject.status in {"resolved", "bootstrap"}
    project_context_satisfies = project_exists and (
        not subject_required or explicit_inputs_ok or interactive_intake_allowed or subject_context_ready
    )
    add_check(
        "project_exists",
        project_exists,
        (
            f"{_format_display_path(layout.project_md)} present"
            if project_exists
            else f"missing {_format_display_path(layout.project_md)}"
        ),
        blocking=False,
    )
    add_check(
        "explicit_inputs",
        explicit_inputs_ok or interactive_intake_allowed,
        (
            "validated external authoring intake manifest"
            if (
                explicit_inputs_ok
                and str(getattr(command, "name", "") or "") == "gpd:write-paper"
                and _has_write_paper_external_authoring_intake(arguments)
            )
            else "explicit standalone inputs detected"
            if explicit_inputs_ok
            else resolved_subject.detail
            if (
                str(getattr(command, "name", "") or "") == "gpd:write-paper"
                and _has_write_paper_external_authoring_intake(arguments)
                and resolved_subject is not None
                and resolved_subject.ownership_mode == "external_authoring_intake"
            )
            else explicit_inputs_detail
            if explicit_inputs_ok or (command.name == "gpd:peer-review" and peer_review_has_explicit_target)
            else (
                _command_interactive_subject_detail(command, explicit_inputs)
                if interactive_intake_allowed
                else f"missing explicit standalone inputs ({', '.join(explicit_inputs)})"
            )
        ),
        blocking=(
            peer_review_has_explicit_target
            if command.name == "gpd:peer-review"
            else not project_exists and not interactive_intake_allowed
        ),
    )
    passed = (
        explicit_inputs_ok
        if command.name == "gpd:peer-review" and peer_review_has_explicit_target
        else project_exists or explicit_inputs_ok or interactive_intake_allowed
    )
    guidance = (
        ""
        if passed
        else (
            explicit_inputs_detail
            if command.name == "gpd:peer-review" and peer_review_has_explicit_target and not explicit_inputs_ok
            else _build_project_aware_guidance(explicit_inputs, init_command=init_command)
        )
    )
    managed_output_context_root = _command_managed_output_context_root(
        workspace_root=cwd,
        context_root=context_cwd,
        project_exists=project_exists,
    )
    managed_output_root = _command_managed_output_root(
        command,
        project_root=managed_output_context_root,
        resolved_subject=resolved_subject,
    )
    if managed_output_root is not None:
        add_check(
            "managed_output_root",
            True,
            f"GPD-authored outputs resolve under {_format_display_path(managed_output_root)}",
            blocking=False,
        )
    passed = project_context_satisfies or explicit_inputs_ok or interactive_intake_allowed
    guidance = "" if passed else _build_project_aware_guidance(explicit_inputs, init_command=init_command)
    if command.name == "gpd:peer-review" and peer_review_has_explicit_target and not explicit_inputs_ok:
        guidance = explicit_inputs_detail
    return CommandContextPreflightResult(
        command=public_command_name,
        context_mode=effective_context_mode,
        passed=passed,
        project_exists=project_exists,
        explicit_inputs=explicit_inputs,
        guidance=guidance,
        checks=checks,
        resolved_mode=resolved_mode,
        mode_reason=mode_reason,
        validated_surface=_validated_runtime_surface(cwd=cwd),
        public_runtime_command_prefix=_active_runtime_command_prefix(cwd=cwd) or "",
        dispatch_note=dispatch_note,
        resolved_subject=resolved_subject,
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
    command, public_command_name = _resolve_registry_command(command_name)
    project_cwd = _command_preflight_cwd(command, cwd=cwd, arguments=subject)
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
                (_resolve_subject_path(report, base=project_cwd) or (project_cwd / report).resolve(strict=False))
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
            if requested_publication_checks:
                publication_artifacts = _resolve_review_preflight_publication_artifacts(manuscript)
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
                        artifact_manifest_detail = f"{_format_display_path(artifact_manifest)} present"
                        from gpd.mcp.paper.models import ArtifactManifest

                        try:
                            artifact_manifest_payload = json.loads(artifact_manifest.read_text(encoding="utf-8"))
                            ArtifactManifest.model_validate(artifact_manifest_payload)
                        except OSError as exc:
                            artifact_manifest_passed = False
                            artifact_manifest_detail = f"could not read artifact manifest: {exc}"
                        except UnicodeDecodeError as exc:
                            artifact_manifest_passed = False
                            artifact_manifest_detail = f"artifact manifest is not valid UTF-8: {exc}"
                        except json.JSONDecodeError as exc:
                            artifact_manifest_passed = False
                            artifact_manifest_detail = f"could not parse artifact manifest: {exc}"
                        except PydanticValidationError as exc:
                            artifact_manifest_passed = False
                            artifact_manifest_detail = "artifact manifest is invalid: " + "; ".join(
                                _format_pydantic_schema_error(error, root_label="artifact_manifest")
                                for error in exc.errors()[:3]
                            )
                    add_check(
                        "artifact_manifest",
                        artifact_manifest_passed,
                        artifact_manifest_detail,
                        blocking=subject_preflight_policy.blocking(
                            "artifact_manifest",
                            missing=artifact_manifest_missing,
                            default=not standalone_peer_review_mode,
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
                    response_round_requires_fresh_review = False
                    if latest_response_round is not None and (
                        required_review_round is None
                        or latest_response_round.round_number > required_review_round.round_number
                    ):
                        required_review_round = _publication_review_round_artifacts(
                            latest_response_round.round_number,
                            review_ledger_by_round=review_ledger_by_round,
                            referee_decision_by_round=referee_decision_by_round,
                        )
                        response_round_requires_fresh_review = True

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
                        round_label = (
                            f"round {required_review_round.round_number}"
                            if required_review_round.round_number > 1
                            else "round 1"
                        )
                        response_round_detail = (
                            f"; latest response artifacts already reached {round_label}"
                            if response_round_requires_fresh_review
                            else ""
                        )
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
                                review_ledger_valid = manuscript_matches_review_artifact_path(
                                    review_ledger.manuscript_path,
                                    manuscript,
                                    cwd=project_cwd,
                                )
                                if "review_ledger_valid" in review_checks_requested:
                                    add_check(
                                        "review_ledger_valid",
                                        review_ledger_valid,
                                        (
                                            "review ledger manuscript_path matches the active submission manuscript"
                                            if review_ledger_valid
                                            else "review ledger manuscript_path does not match the active submission manuscript"
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
                            persist_manifest=True,
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
    )


@validate_app.command("consistency")
def validate_consistency() -> None:
    """Validate cross-phase consistency."""
    from gpd.core.health import run_health

    report = run_health(_project_scoped_cwd())
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
    result = _build_command_context_preflight(command_name, arguments=arguments)
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
        project_root = Path(from_project)
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
    """Validate VERIFICATION frontmatter and contract-result alignment, including stale proof-audit blockers when recorded."""

    _run_frontmatter_validation(input_path, "verification")


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
        semantic_errors = validate_stage_review_artifact_file(artifact_path)
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
    project_root_for_check = _get_cwd() if check_paths else None
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

    _output(sync_phase_checkpoints(_get_cwd()))


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

    resolved = _get_cwd() / file_path
    result = cmd_validate_return(resolved)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("apply-return-updates")
def apply_return_updates(
    file_path: str = typer.Argument(..., help="Path to file containing gpd_return YAML block"),
) -> None:
    """Validate one gpd_return envelope and apply its durable child-return updates."""
    from gpd.core.commands import cmd_apply_return_updates

    resolved = _get_cwd() / file_path
    result = cmd_apply_return_updates(_get_cwd(), resolved)
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
        help="Suppress all sidecars (ARTIFACT-MANIFEST.json, BIBLIOGRAPHY-AUDIT.json). Only .tex, .bib, and figures/ land in the output directory.",
    ),
    with_provenance: bool = typer.Option(
        False,
        "--with-provenance",
        help="Write ARTIFACT-MANIFEST.json into the paper root instead of the hidden .paper-meta/ subdirectory.",
    ),
    with_audits: bool = typer.Option(
        False,
        "--with-audits",
        help="Write BIBLIOGRAPHY-AUDIT.json into the paper root instead of the hidden .paper-meta/ subdirectory.",
    ),
    with_review_sidecars: bool = typer.Option(
        False,
        "--with-review-sidecars",
        help="Keep review-oriented sidecars (proof-review, readiness) in the paper root when agents write them; off by default.",
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
    _reject_legacy_paper_config_location(config_file, project_root=project_root)
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
        for policy in (_managed_publication_manuscript_output_policy(project_root=project_root, manuscript_config_path=config_file),)
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
    else:
        citation_source_path, citation_source_warning = _discover_literature_review_citation_sources(project_root)
        if citation_source_path is not None:
            try:
                citation_payload = _load_citation_sources_payload(citation_source_path)
            except GPDError as exc:
                _error(str(exc))

    toolchain = _paper_build_toolchain_payload()

    # Sidecar routing: default sidecars to paper/.paper-meta/ so the manuscript
    # root only contains .tex, .bib, and figures/. --with-provenance promotes
    # ARTIFACT-MANIFEST.json back up; --with-audits promotes BIBLIOGRAPHY-AUDIT.json.
    # --minimal suppresses sidecars entirely.
    if minimal:
        paper_sidecar_root: Path | None = None
        emit_artifact = False
        emit_bib_audit = False
    else:
        if with_provenance and with_audits:
            paper_sidecar_root = None  # sidecars go flat into the paper root
        else:
            paper_sidecar_root = output_path / ".paper-meta"
        emit_artifact = True
        emit_bib_audit = True
        # When only one of the flags is set, move that specific file into the
        # paper root by pre-creating the manifest path via build_paper's
        # default (output_dir) semantics. Because build_paper's signature
        # accepts a single sidecar_root, selective promotion is done by
        # repointing the whole root when both flags are set; otherwise keep
        # sidecars under .paper-meta/ and let callers copy a specific file up
        # if needed.

    result = asyncio.run(
        build_paper(
            paper_config,
            output_path,
            bib_data=bib_data,
            citation_sources=citation_payload,
            enrich_bibliography=enrich_bibliography,
            sidecar_root=paper_sidecar_root,
            emit_artifact_manifest=emit_artifact,
            emit_bibliography_audit=emit_bib_audit,
        )
    )
    # with_review_sidecars is currently advisory — the review-sidecar writers
    # live in agent-authored workflows. Surface the preference in the payload
    # so downstream agents can honor it.

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
            "with_provenance": with_provenance,
            "with_audits": with_audits,
            "with_review_sidecars": with_review_sidecars,
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
            effective_runtime = runtime if runtime is not None else normalize_runtime_name(detect_context_runtime(_get_cwd()))
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

_GPD_BANNER = r"""
 ██████╗ ██████╗ ██████╗
██╔════╝ ██╔══██╗██╔══██╗
██║  ███╗██████╔╝██║  ██║
██║   ██║██╔═══╝ ██║  ██║
╚██████╔╝██║     ██████╔╝
 ╚═════╝ ╚═╝     ╚═════╝
"""

_GPD_DISPLAY_NAME = "Get Physics Done"
_GPD_OWNER = "Physical Superintelligence PBC"
_GPD_OWNER_SHORT = "PSI"
_GPD_COPYRIGHT_YEAR = 2026
_INSTALL_LOGO_COLOR = "#F3F0E8"
_INSTALL_TITLE_COLOR = "#F7F4ED"
_INSTALL_META_COLOR = "#9E988C"
_INSTALL_ACCENT_COLOR = "#D8C7A3"


def _format_install_header_lines(version: str) -> tuple[str, str]:
    """Return the branded header shown during interactive install."""
    return (
        f"GPD v{version} - {_GPD_DISPLAY_NAME}",
        f"© {_GPD_COPYRIGHT_YEAR} {_GPD_OWNER} ({_GPD_OWNER_SHORT})",
    )


def _print_install_header(version: str) -> None:
    """Render the branded install banner for human-facing install flows."""
    console.print(_GPD_BANNER, style=f"bold {_INSTALL_LOGO_COLOR}")
    console.print()
    header_line, attribution_line = _format_install_header_lines(version)
    console.print(header_line, style=f"bold {_INSTALL_TITLE_COLOR}", markup=False, highlight=False)
    console.print(attribution_line, style=f"dim {_INSTALL_META_COLOR}", markup=False, highlight=False)
    console.print()


def _render_install_option_line(index: int, label: str, *details: str, label_width: int | None = None) -> Text:
    """Return a single-line formatted install menu option."""
    rendered = Text("  ")
    rendered.append(f"[{index}]", style=f"bold {_INSTALL_ACCENT_COLOR}")
    rendered.append(" ")
    rendered.append(label.ljust(label_width or len(label)), style=f"bold {_INSTALL_TITLE_COLOR}")
    filtered_details = [detail for detail in details if detail]
    if filtered_details:
        rendered.append("  ")
        for detail_index, detail in enumerate(filtered_details):
            if detail_index:
                rendered.append(" ")
            rendered.append("·", style=f"bold {_INSTALL_ACCENT_COLOR}")
            rendered.append(" ")
            rendered.append(detail, style=f"dim {_INSTALL_META_COLOR}")
    return rendered


def _render_install_choice_prompt() -> Text:
    """Return the shared interactive prompt label for install menus."""
    rendered = Text()
    rendered.append("Enter choice", style=f"bold {_INSTALL_TITLE_COLOR}")
    rendered.append(" [1]", style=f"dim {_INSTALL_META_COLOR}")
    return rendered


def _prompt_runtimes(*, action: str = "install") -> list[str]:
    """Interactive runtime selection. Returns list of selected runtime names."""
    from rich.prompt import Prompt

    runtimes = _list_runtimes_or_error(action=f"{action} runtime selection")
    adapters = {runtime: _get_adapter_or_error(runtime, action=f"{action} runtime selection") for runtime in runtimes}
    label_width = max(len(adapter.display_name) for adapter in adapters.values())
    all_label = "All runtimes"
    label_width = max(label_width, len(all_label))
    console.print(f"\n[bold {_INSTALL_TITLE_COLOR}]Select runtime(s) to {action}[/]\n")
    for i, rt in enumerate(runtimes, 1):
        adapter = adapters[rt]
        console.print(_render_install_option_line(i, adapter.display_name, rt, label_width=label_width))
    console.print(_render_install_option_line(len(runtimes) + 1, all_label, label_width=label_width))

    console.print()
    choice = Prompt.ask(_render_install_choice_prompt(), default="1", show_default=False)

    try:
        idx = int(choice)
    except ValueError:
        canonical_runtime = normalize_runtime_name(choice)
        if canonical_runtime in adapters:
            return [canonical_runtime]

        normalized = choice.strip().casefold()
        exact_matches = [
            runtime_name
            for runtime_name, adapter in adapters.items()
            if normalized
            in {
                runtime_name.casefold(),
                adapter.display_name.casefold(),
                *(alias.casefold() for alias in adapter.selection_aliases),
            }
        ]
        if len(exact_matches) == 1:
            return exact_matches

        fuzzy_matches = [
            runtime_name
            for runtime_name, adapter in adapters.items()
            if normalized
            and any(
                normalized in candidate
                for candidate in (
                    runtime_name.casefold(),
                    adapter.display_name.casefold(),
                    *(alias.casefold() for alias in adapter.selection_aliases),
                )
            )
        ]
        if len(fuzzy_matches) == 1:
            return fuzzy_matches
        if len(fuzzy_matches) > 1:
            _error(f"Ambiguous selection: {choice!r}. Matches: {', '.join(fuzzy_matches)}")
        _error(f"Invalid selection: {choice!r}")
        return []  # unreachable

    if idx == len(runtimes) + 1:
        return runtimes
    if 1 <= idx <= len(runtimes):
        return [runtimes[idx - 1]]

    _error(f"Invalid selection: {idx}")
    return []  # unreachable


def _location_example(runtimes: list[str], *, is_global: bool, action: str) -> str:
    """Return a representative install location example for the selected runtime set."""
    if len(runtimes) != 1:
        return "one config dir per runtime"

    adapter = _get_adapter_or_error(runtimes[0], action=f"{action} location selection")
    target = adapter.resolve_target_dir(is_global, _get_cwd())
    return _format_display_path(target)


def _prompt_location(runtimes: list[str], *, action: str = "install") -> bool:
    """Interactive location selection. Returns True for global, False for local."""
    from rich.prompt import Prompt

    label = "Install" if action == "install" else "Uninstall"
    local_example = _location_example(runtimes, is_global=False, action=action)
    global_example = _location_example(runtimes, is_global=True, action=action)
    label_width = max(len("Local"), len("Global"))
    console.print(f"\n[bold {_INSTALL_TITLE_COLOR}]{label} location[/]\n")
    console.print(
        _render_install_option_line(1, "Local", "current project only", local_example, label_width=label_width)
    )
    console.print(_render_install_option_line(2, "Global", "all projects", global_example, label_width=label_width))

    console.print()
    choice = Prompt.ask(_render_install_choice_prompt(), default="1", show_default=False)
    normalized = choice.strip().lower()
    if normalized in {"1", "local"}:
        return False
    if normalized in {"2", "global"}:
        return True
    _error(f"Invalid selection: {choice!r}")
    return False  # unreachable


def _install_single_runtime(
    runtime_name: str,
    *,
    is_global: bool,
    target_dir_override: str | None = None,
) -> dict[str, object]:
    """Install GPD for a single runtime. Returns install result dict."""
    from gpd.version import resolve_install_gpd_root

    adapter = _get_adapter_or_error(runtime_name, action="install")
    gpd_root = resolve_install_gpd_root(_get_cwd())

    if target_dir_override:
        dest = _resolve_cli_target_dir(target_dir_override)
    else:
        dest = adapter.resolve_target_dir(is_global, _get_cwd())

    return adapter.install(
        gpd_root,
        dest,
        is_global=is_global,
        explicit_target=target_dir_override is not None,
    )


def _print_install_summary(results: list[tuple[str, dict[str, object]]]) -> None:
    """Print a rich summary table of install results."""
    console.print()
    table = Table(
        title="Install Summary",
        title_style=f"italic {_INSTALL_ACCENT_COLOR}",
        show_header=True,
        header_style=f"bold {_INSTALL_ACCENT_COLOR}",
    )
    table.add_column("Runtime", style="bold")
    table.add_column("Target")
    table.add_column("Status")

    for runtime_name, result in results:
        adapter = _get_adapter_or_error(runtime_name, action="install summary")
        target = _format_display_path(result.get("target"))
        agents = result.get("agents", 0)
        commands = result.get("commands", 0)
        table.add_row(
            adapter.display_name,
            target,
            f"[green]✓[/] {agents} agents, {commands} commands",
        )

    console.print(table)

    # Post-install next steps
    if results:
        next_step_entries: list[tuple[str, str, str, str, str, str, str, str]] = []
        seen_runtime_names: set[str] = set()
        for runtime_name, _result in results:
            if runtime_name in seen_runtime_names:
                continue
            seen_runtime_names.add(runtime_name)
            adapter = _get_adapter_or_error(runtime_name, action="install summary")
            next_step_entries.append(
                (
                    runtime_name,
                    adapter.display_name,
                    adapter.launch_command,
                    adapter.help_command,
                    adapter.format_command("start"),
                    adapter.format_command("tour"),
                    adapter.new_project_command,
                    adapter.map_research_command,
                )
            )

        console.print()
        console.print("[bold]Startup checklist[/]")
        console.print(
            f"Beginner Onboarding Hub: {beginner_onboarding_hub_url()}",
            soft_wrap=True,
        )
        console.print(
            f"First-run order: {beginner_startup_ladder_text()}",
            soft_wrap=True,
        )
        if len(next_step_entries) == 1:
            single_runtime_name, _ = results[0]
            (
                _runtime_name,
                display_name,
                launch_command,
                help_command,
                start_command,
                tour_command,
                new_project_command,
                map_research_command,
            ) = next_step_entries[0]
            resume_work_command = _get_adapter_or_error(single_runtime_name, action="install summary").format_command(
                "resume-work"
            )
            suggest_next_command = _get_adapter_or_error(single_runtime_name, action="install summary").format_command(
                "suggest-next"
            )
            pause_work_command = _get_adapter_or_error(single_runtime_name, action="install summary").format_command(
                "pause-work"
            )
            console.print(
                f"1. Open [bold]{display_name}[/] from your system terminal "
                f"([{_INSTALL_ACCENT_COLOR} bold]{launch_command}[/]).",
                soft_wrap=True,
            )
            console.print(
                f"2. Run [{_INSTALL_ACCENT_COLOR} bold]{help_command}[/] for the command list.",
                soft_wrap=True,
            )
            console.print(
                "3. Run "
                f"[{_INSTALL_ACCENT_COLOR} bold]{start_command}[/] if you're not sure what fits this folder yet. "
                "Run "
                f"[{_INSTALL_ACCENT_COLOR} bold]{tour_command}[/] if you want a read-only overview of the broader command surface first.",
                soft_wrap=True,
            )
            console.print(
                "4. Then use "
                f"[{_INSTALL_ACCENT_COLOR} bold]{new_project_command}[/] for a new project "
                "or "
                f"[{_INSTALL_ACCENT_COLOR} bold]{map_research_command}[/] for existing work.",
                soft_wrap=True,
            )
            console.print(
                "5. Fast bootstrap: use "
                f"[{_INSTALL_ACCENT_COLOR} bold]{new_project_command} --minimal[/] "
                "for the shortest onboarding path.",
                soft_wrap=True,
            )
            console.print(
                "6. When you return later, use "
                f"[{_INSTALL_ACCENT_COLOR} bold]{resume_work_command}[/] after reopening the right workspace. "
                f"{recovery_ladder_note(resume_work_phrase=f'`{resume_work_command}`', suggest_next_phrase=f'`{suggest_next_command}`', pause_work_phrase=f'`{pause_work_command}`')}",
                soft_wrap=True,
            )
            console.print(
                f"7. {_install_summary_local_cli_bridge_line()}",
                soft_wrap=True,
            )
        else:
            runtime_lines: list[str] = []
            for (
                runtime_name,
                display_name,
                launch_command,
                help_command,
                start_command,
                tour_command,
                new_project_command,
                map_research_command,
            ) in next_step_entries:
                resume_work_command = _get_adapter_or_error(runtime_name, action="install summary").format_command(
                    "resume-work"
                )
                runtime_lines.append(
                    f"- {display_name} "
                    f"([{_INSTALL_ACCENT_COLOR} bold]{launch_command}[/]): "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{help_command}[/], then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{start_command}[/], then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{tour_command}[/], then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{new_project_command}[/] for new work or "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{map_research_command}[/] for existing work, then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{resume_work_command}[/] when you return later."
                )
            for line in runtime_lines:
                console.print(line, soft_wrap=True)
            console.print(
                f"Fast bootstrap: use [bold]{next_step_entries[0][6]} --minimal[/] for the shortest onboarding path.",
                soft_wrap=True,
            )
            console.print(
                recovery_ladder_note(
                    resume_work_phrase="your runtime-specific `resume-work` command",
                    suggest_next_phrase="your runtime-specific `suggest-next` command",
                    pause_work_phrase="your runtime-specific `pause-work` command",
                ),
                soft_wrap=True,
            )
            console.print(
                _install_summary_local_cli_bridge_line(),
                soft_wrap=True,
            )
        console.print()


def _validate_all_runtime_selection(action: str, runtimes: list[str] | None, use_all: bool) -> None:
    """Reject ambiguous runtime selection between explicit args and --all."""
    if use_all and runtimes:
        _error(f"Cannot combine explicit runtimes with --all for {action}")


def _validate_target_dir_runtime_selection(action: str, runtimes: list[str], target_dir: str | None) -> None:
    """Reject explicit target-dir usage when multiple runtimes are selected."""
    if target_dir and len(runtimes) != 1:
        _error(f"--target-dir requires exactly one runtime for {action}")


def _resolve_cli_target_dir(target_dir: str) -> Path:
    """Resolve a CLI target-dir argument relative to the active --cwd."""
    resolved = Path(target_dir).expanduser()
    if resolved.is_absolute():
        return resolved.resolve(strict=False)
    return (_get_cwd() / resolved).resolve(strict=False)


def _target_dir_matches_global(runtime_name: str, target_dir: str, *, action: str) -> bool:
    """Return whether an explicit target-dir names the runtime's canonical global dir."""
    adapter = _get_adapter_or_error(runtime_name, action=action)
    resolved_target = _resolve_cli_target_dir(target_dir)
    resolve_target_dir = getattr(adapter, "resolve_target_dir", None)
    if not callable(resolve_target_dir):
        return False
    try:
        canonical_global_target = resolve_target_dir(True, _get_cwd())
    except (AttributeError, TypeError, ValueError):
        return False
    return resolved_target == canonical_global_target.expanduser().resolve(strict=False)


def _resolve_detected_runtime_target(runtime_name: str) -> tuple[Path | None, str | None]:
    """Return the concrete installed runtime target when one can be detected."""
    from gpd.hooks.runtime_detect import detect_install_scope, detect_runtime_install_target

    install_target = detect_runtime_install_target(runtime_name, cwd=_get_cwd())
    if install_target is not None:
        return install_target.config_dir, install_target.install_scope

    install_scope = detect_install_scope(runtime_name, cwd=_get_cwd())
    if install_scope == "global":
        adapter = _get_adapter_or_error(runtime_name, action="inspect runtime readiness")
        return adapter.resolve_target_dir(True, _get_cwd()), "global"
    if install_scope == "local":
        adapter = _get_adapter_or_error(runtime_name, action="inspect runtime readiness")
        return adapter.resolve_target_dir(False, _get_cwd()), "local"
    return None, None


def _install_summary_local_cli_bridge_line() -> str:
    """Return the concise local-CLI bridge follow-up for install summaries.

    The richer settings guidance stays in bootstrap/help surfaces that render
    post_start_settings_note() and post_start_settings_recommendation().
    """
    return f"Use [bold]{local_cli_help_command()}[/] for local diagnostics and later setup."


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
    messages: list[str] = []
    seen: set[str] = set()

    for check in getattr(report, "checks", []) or []:
        status = getattr(check, "status", None)
        issues = [str(issue) for issue in getattr(check, "issues", []) or [] if str(issue).strip()]
        if str(status) != "fail":
            continue
        if not issues:
            label = str(getattr(check, "label", "Runtime readiness")).strip() or "Runtime readiness"
            issues = [f"{label}: readiness check failed."]
        for issue in issues:
            if issue not in seen:
                seen.add(issue)
                messages.append(issue)

    return messages


def _doctor_advisory_messages(report: object) -> list[str]:
    """Extract advisory doctor warnings from a report-like object."""
    messages: list[str] = []
    seen: set[str] = set()

    for check in getattr(report, "checks", []) or []:
        warnings = [str(item) for item in getattr(check, "warnings", []) or [] if str(item).strip()]
        for warning in warnings:
            if warning not in seen:
                seen.add(warning)
                messages.append(warning)

    return messages


def _install_repairable_runtime_target_messages(report: object, runtime_name: str) -> list[str]:
    """Return install-preflight messages for same-runtime incomplete targets."""
    messages: list[str] = []
    canonical_runtime = normalize_runtime_name(runtime_name) or runtime_name

    for check in getattr(report, "checks", []) or []:
        if str(getattr(check, "status", None)) != "fail":
            continue
        if str(getattr(check, "label", "")).strip() != "Runtime Config Target":
            continue
        details = getattr(check, "details", {}) or {}
        if not isinstance(details, dict) or details.get("install_state") != "owned_incomplete":
            continue
        target_assessment = details.get("target_assessment")
        assessment_payload = target_assessment if isinstance(target_assessment, dict) else details
        manifest_runtime = normalize_runtime_name(str(assessment_payload.get("manifest_runtime") or "")) or None
        expected_runtime = normalize_runtime_name(str(assessment_payload.get("expected_runtime") or "")) or canonical_runtime
        if manifest_runtime not in {None, canonical_runtime} or expected_runtime != canonical_runtime:
            continue
        issues = [str(issue) for issue in getattr(check, "issues", []) or [] if str(issue).strip()]
        messages.extend(issues or ["Incomplete same-runtime GPD install will be repaired during install."])

    return messages


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
    from gpd.core.health import build_unattended_readiness_result, run_doctor
    from gpd.specs import SPECS_DIR

    if global_install and local_install:
        _error("Cannot specify both --global and --local")

    normalized_runtime = _normalize_runtime_selection([runtime], action="validate unattended-readiness")[0]
    resolved_target = _resolve_cli_target_dir(target_dir) if target_dir is not None else None
    install_scope = (
        "global"
        if global_install
        else "local"
        if local_install
        else "global"
        if target_dir
        and _target_dir_matches_global(normalized_runtime, target_dir, action="validate unattended-readiness")
        else "local"
    )
    if target_dir is None and not global_install and not local_install:
        detected_target, detected_scope = _resolve_detected_runtime_target(normalized_runtime)
        if detected_target is not None and detected_scope is not None:
            resolved_target = detected_target
            install_scope = detected_scope

    if resolved_target is not None:
        permissions_target = str(resolved_target)
    else:
        adapter = _get_adapter_or_error(normalized_runtime, action="validate unattended-readiness")
        permissions_target = str(adapter.resolve_target_dir(install_scope == "global", _get_cwd()))

    doctor_report = run_doctor(
        specs_dir=SPECS_DIR,
        runtime=normalized_runtime,
        install_scope=install_scope,
        target_dir=resolved_target,
        cwd=_get_cwd(),
        live_executable_probes=live_executable_probes,
    )
    permissions_payload = _permissions_status_payload(
        runtime=normalized_runtime,
        autonomy=autonomy,
        target_dir=permissions_target,
    )

    return build_unattended_readiness_result(
        runtime=normalized_runtime,
        autonomy=autonomy,
        install_scope=install_scope,
        target_dir=resolved_target,
        doctor_report=doctor_report,
        permissions_payload=permissions_payload,
        live_executable_probes=live_executable_probes,
        validated_surface=_validated_runtime_surface(cwd=_get_cwd()),
    )


def _run_install_readiness_preflight(
    runtimes: list[str],
    *,
    install_scope: str,
    target_dir: Path | None,
) -> tuple[list[tuple[str, list[str]]], dict[str, list[str]]]:
    """Run doctor-led readiness checks before mutating runtime install targets."""
    from gpd.core.health import CheckStatus, run_doctor
    from gpd.specs import SPECS_DIR

    failures: list[tuple[str, list[str]]] = []
    advisories: dict[str, list[str]] = {}

    for runtime_name in runtimes:
        try:
            report = run_doctor(
                specs_dir=SPECS_DIR,
                runtime=runtime_name,
                install_scope=install_scope,
                target_dir=target_dir,
                cwd=_get_cwd(),
            )
        except Exception as exc:
            failures.append((runtime_name, [str(exc)]))
            continue

        blocker_messages = _doctor_blocker_messages(report)
        repairable_messages = _install_repairable_runtime_target_messages(report, runtime_name)
        if repairable_messages:
            repairable_set = set(repairable_messages)
            blocker_messages = [message for message in blocker_messages if message not in repairable_set]
        if getattr(report, "overall", None) == CheckStatus.FAIL and not blocker_messages and not repairable_messages:
            blocker_messages = ["Runtime readiness reported a failure without blocking details."]

        if blocker_messages:
            failures.append((runtime_name, blocker_messages))
            continue

        advisory_messages = _doctor_advisory_messages(report)
        advisory_messages.extend(repairable_messages)
        if advisory_messages:
            advisories[runtime_name] = list(dict.fromkeys(advisory_messages))

    return failures, advisories


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
    target_dir: str | None = typer.Option(None, "--target-dir", help="Override target config directory"),
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

    if not _raw:
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

    if not _raw:
        console.print(f"\n[bold]Runtime readiness preflight for: {_format_runtime_list(selected)}[/]")
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
                adapter.finalize_install(result, force_statusline=force_statusline)
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
        _print_install_summary(results)

    if failures:
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
    target_dir: str | None = typer.Option(None, "--target-dir", help="Override target directory (testing)"),
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

    if not _raw and not target_dir:
        location_label = "global" if is_global else "local"
        runtime_names = _format_runtime_list(selected)
        if not Confirm.ask(f"Remove GPD from {runtime_names} ({location_label})?", default=False):
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
        if not target.is_dir():
            outcome = {
                "runtime": rt,
                "status": "skipped",
                "target": str(target),
                "reason": f"not installed at {_format_display_path(target)}",
            }
            if not _raw:
                console.print(
                    f"  [yellow]⊘[/] {adapter.display_name} — not installed at {_format_display_path(target)}",
                    soft_wrap=True,
                )
            uninstall_results.append(outcome)
            continue
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
            outcome["reason"] = "nothing to remove"
        if not _raw:
            if removed_items:
                console.print(
                    f"  [green]✓[/] {adapter.display_name} — removed: {', '.join(str(r) for r in removed_items)}"
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

    # Accept both "conventions" and "gpd-conventions"
    if not server.startswith("gpd-"):
        server = f"gpd-{server}"

    if server not in _BUILTIN_SERVERS:
        available = ", ".join(sorted(_BUILTIN_SERVERS.keys()))
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
    import importlib
    import json as json_mod

    from gpd.mcp.builtin_servers import _BUILTIN_SERVERS

    sidecar = binary_path or (sys.executable if getattr(sys, "frozen", False) else None)
    servers: dict[str, object] = {}

    for name, entry in _BUILTIN_SERVERS.items():
        # Skip optional servers whose deps are missing
        module_check = entry.get("module_check")
        if module_check:
            try:
                importlib.import_module(module_check)
            except ImportError:
                continue

        short_name = name.removeprefix("gpd-")

        if sidecar:
            # Binary mode: use the sidecar binary
            cmd = [sidecar, "mcp-serve", short_name]
        else:
            # Python mode: use python -m
            cmd = [sys.executable, "-m", entry["args"][1]]

        server_entry: dict[str, object] = {
            "type": "local",
            "command": cmd,
            "enabled": True,
        }
        env = entry.get("env")
        if env:
            server_entry["environment"] = env

        servers[name] = server_entry

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
