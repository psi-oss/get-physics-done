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
import os
import posixpath
import re
import shlex
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.table import Table
from rich.text import Text

from gpd.command_labels import canonical_command_label
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
    ENV_GPD_DISABLE_CHECKOUT_REEXEC,
    HOME_DATA_DIR_NAME,
    RECENT_PROJECTS_DIR_NAME,
    RECENT_PROJECTS_INDEX_FILENAME,
)
from gpd.core.errors import ConfigError, GPDError
from gpd.hooks.runtime_detect import detect_runtime_for_gpd_use, normalize_runtime_name

if TYPE_CHECKING:
    from gpd.mcp.paper.models import PaperConfig

# ─── Output helpers ─────────────────────────────────────────────────────────

console = Console()
err_console = Console(stderr=True)

# Global state threaded through typer context
_raw: bool = False
_cwd: Path = Path(".")
def _output(data: object) -> None:
    """Print result — JSON when --raw, rich text otherwise."""
    if _raw:
        if data is None:
            console.print_json(json.dumps({"result": None}))
        elif isinstance(data, (list, tuple)):
            items = [
                item.model_dump(mode="json", by_alias=True) if hasattr(item, "model_dump") else
                dataclasses.asdict(item) if dataclasses.is_dataclass(item) and not isinstance(item, type) else
                item
                for item in data
            ]
            console.print_json(json.dumps(items, default=str))
        elif hasattr(data, "model_dump"):
            console.print_json(json.dumps(data.model_dump(mode="json", by_alias=True), default=str))
        elif dataclasses.is_dataclass(data) and not isinstance(data, type):
            console.print_json(json.dumps(dataclasses.asdict(data), default=str))
        elif isinstance(data, dict):
            console.print_json(json.dumps(data, default=str))
        else:
            console.print_json(json.dumps({"result": str(data)}, default=str))
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
            console.print(str(data))


def _pretty_print(d: dict) -> None:
    """Render a dict as a rich table."""
    table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    table.add_column("Key")
    table.add_column("Value")
    for k, v in d.items():
        val = json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v)
        table.add_row(str(k), val)
    console.print(table)


def _error(msg: str) -> NoReturn:
    """Print error and exit — JSON when --raw, rich text otherwise."""
    if _raw:
        err_console.print_json(json.dumps({"error": str(msg)}))
    else:
        err_console.print(f"[bold red]Error:[/] {msg}", highlight=False)
    raise typer.Exit(code=1)


def _get_cwd() -> Path:
    return _cwd.resolve()


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
    from gpd.version import checkout_root

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
        env["PYTHONPATH"] = os.pathsep.join([checkout_src, *existing_pythonpath]) if existing_pythonpath else checkout_src
    env[ENV_GPD_DISABLE_CHECKOUT_REEXEC] = "1"
    os.execve(sys.executable, [sys.executable, "-m", "gpd.cli", *effective_argv], env)


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

    resolved_target = target_path.resolve(strict=False)
    resolved_cwd = _get_cwd().expanduser().resolve(strict=False)
    resolved_home = Path.home().expanduser().resolve(strict=False)

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
    validated_surface: str = "public_runtime_command_surface"
    local_cli_equivalence_guaranteed: bool = False
    dispatch_note: str = ""


@dataclasses.dataclass(frozen=True)
class PublicationReviewArtifacts:
    """Latest staged publication-review artifacts discovered under GPD/review."""

    round_number: int
    round_suffix: str
    review_ledger: Path | None
    referee_decision: Path | None


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
    validated_surface: str = "public_runtime_command_surface"
    local_cli_equivalence_guaranteed: bool = False
    dispatch_note: str = ""


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
    except Exception:
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
        console.print_json(json.dumps({"result": value}))
    else:
        console.print(value)


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
        console.print_json(json.dumps(data, default=str))
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
                err_console.print_json(json.dumps({"error": msg}))
            else:
                err_console.print(f"[bold red]Error:[/] {msg}", highlight=False)
            raise SystemExit(1) from None
        except GPDError as exc:
            if _raw:
                err_console.print_json(json.dumps({"error": str(exc)}))
            else:
                err_console.print(f"[bold red]Error:[/] {exc}", highlight=False)
            raise SystemExit(1) from None
        except TimeoutError as exc:
            if _raw:
                err_console.print_json(json.dumps({"error": str(exc)}))
            else:
                err_console.print(f"[bold red]Error:[/] {exc}", highlight=False)
            raise SystemExit(1) from None
        except SystemExit:
            raise
        except Exception:
            raise


app = _GPDTyper(
    name="gpd",
    help="GPD — Get Physics Done: local install, readiness, validation, permissions, observability, and diagnostics CLI",
    no_args_is_help=True,
    add_completion=True,
    epilog=(
        "Primary research workflow commands run inside an installed runtime surface, not the local `gpd` CLI.\n"
        "Use `gpd install <runtime>` to install GPD, then open that runtime and run its GPD help command there.\n\n"
        "Use the local CLI for install, readiness checks, permissions, observability, validation, and diagnostics.\n"
        "Examples:\n"
        "  gpd install <runtime> --local\n"
        "  gpd doctor --runtime <runtime> --local\n"
        "  gpd permissions status --runtime <runtime> --autonomy balanced\n"
        "  gpd observe execution\n"
        "  gpd resume --recent\n"
        "  gpd validate command-context gpd:new-project"
    ),
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

    _output(state_load(_get_cwd()))


@state_app.command("get")
def state_get(
    section: str | None = typer.Argument(None, help="State section to retrieve"),
) -> None:
    """Get a specific state section or the full state."""
    from gpd.core.state import state_get

    _output(state_get(_get_cwd(), section))


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
    _output(state_patch(_get_cwd(), patch_dict))


@state_app.command("set-project-contract")
def state_set_project_contract_cmd(
    source: str = typer.Argument(..., help="Path to a JSON file containing the project contract, or '-' for stdin"),
) -> None:
    """Persist the canonical project contract into state.json."""
    from gpd.core.contract_validation import validate_project_contract
    from gpd.core.state import state_set_project_contract

    contract_data = _load_json_document(source)

    validation = validate_project_contract(contract_data, mode="draft", project_root=_get_cwd())
    if not validation.valid:
        _output(validation)
        raise typer.Exit(code=1)

    result = state_set_project_contract(_get_cwd(), contract_data)
    _output(result)
    if not result.updated and result.reason and result.reason.startswith("Project contract failed scoping validation:"):
        raise typer.Exit(code=1)


@state_app.command("update")
def state_update(
    field: str = typer.Argument(..., help="Field name to update"),
    value: str = typer.Argument(..., help="New value"),
) -> None:
    """Update a single state field."""
    from gpd.core.state import state_update

    _output(state_update(_get_cwd(), field, value))


@state_app.command("advance")
def state_advance() -> None:
    """Advance to the next plan in current phase."""
    from gpd.core.state import state_advance_plan

    _output(state_advance_plan(_get_cwd()))


@state_app.command("compact")
def state_compact() -> None:
    """Archive old state entries to keep STATE.md concise."""
    from gpd.core.state import state_compact

    _output(state_compact(_get_cwd()))


@state_app.command("snapshot")
def state_snapshot() -> None:
    """Return a fast read-only snapshot of current state for progress and routing."""
    from gpd.core.state import state_snapshot

    _output(state_snapshot(_get_cwd()))


@state_app.command("validate")
def state_validate() -> None:
    """Validate state consistency and schema compliance."""
    from gpd.core.state import state_validate

    result = state_validate(_get_cwd())
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

    _output(state_record_metric(_get_cwd(), phase=phase, plan=plan, duration=duration, tasks=tasks, files=files))


@state_app.command("update-progress")
def state_update_progress() -> None:
    """Recalculate progress percentage from phase completion."""
    from gpd.core.state import state_update_progress

    _output(state_update_progress(_get_cwd()))


@state_app.command("add-decision")
def state_add_decision(
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    summary: str | None = typer.Option(None, "--summary", help="Decision summary"),
    rationale: str = typer.Option("", "--rationale", help="Decision rationale"),
) -> None:
    """Record a research decision."""
    from gpd.core.state import state_add_decision

    _output(state_add_decision(_get_cwd(), phase=phase, summary=summary, rationale=rationale))


@state_app.command("add-blocker")
def state_add_blocker(
    text: str = typer.Option(..., "--text", help="Blocker description"),
) -> None:
    """Record a blocker."""
    from gpd.core.state import state_add_blocker

    _output(state_add_blocker(_get_cwd(), text))


@state_app.command("resolve-blocker")
def state_resolve_blocker(
    text: str = typer.Option(..., "--text", help="Blocker description to resolve"),
) -> None:
    """Mark a blocker as resolved."""
    from gpd.core.state import state_resolve_blocker

    _output(state_resolve_blocker(_get_cwd(), text))


@state_app.command("record-session")
def state_record_session(
    stopped_at: str | None = typer.Option(None, "--stopped-at", help="Stop timestamp"),
    resume_file: str | None = typer.Option(None, "--resume-file", help="Resume context file"),
) -> None:
    """Record a session boundary for context tracking."""
    from gpd.core.state import state_record_session

    _output(state_record_session(_get_cwd(), stopped_at=stopped_at, resume_file=resume_file))


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

    _output(roadmap_get_phase(_get_cwd(), phase_num))


@roadmap_app.command("analyze")
def roadmap_analyze() -> None:
    """Analyze roadmap structure, dependencies, and coverage."""
    from gpd.core.phases import roadmap_analyze

    _output(roadmap_analyze(_get_cwd()))


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


_RECENT_PROJECTS_INDEX_FILENAMES = (RECENT_PROJECTS_INDEX_FILENAME,)


def _resume_status_message(payload: dict[str, object]) -> str:
    """Return a concise human summary of resume readiness for this workspace."""
    segment_candidates = [
        candidate for candidate in payload.get("segment_candidates", []) if isinstance(candidate, dict)
    ]
    if segment_candidates and all(
        str(candidate.get("source") or "").strip() == "session_resume_file"
        and str(candidate.get("status") or "").strip() == "missing"
        for candidate in segment_candidates
    ):
        return "Session continuity metadata exists, but the recorded handoff file is missing."
    if not bool(payload.get("planning_exists")):
        return "No GPD planning directory is present in this workspace."
    if not any(bool(payload.get(key)) for key in ("state_exists", "roadmap_exists", "project_exists")):
        return "Planning scaffolding exists, but there is no recoverable project state yet."
    if payload.get("resume_mode") == "bounded_segment":
        return "A bounded execution segment is resumable from the current workspace state."
    if payload.get("resume_mode") == "interrupted_agent":
        return "An interrupted agent marker is present, but no bounded resume segment is active."
    if isinstance(payload.get("segment_candidates"), list) and payload["segment_candidates"]:
        return "Recovery context is available, but no live bounded segment is currently resumable."
    if bool(payload.get("has_live_execution")):
        return "Live execution telemetry exists, but it does not expose a portable resume target."
    return "No recent local recovery target is currently recorded."


def _resume_recent_hint(payload: dict[str, object]) -> str | None:
    """Return a cross-project recovery hint when the current workspace has nothing to resume."""
    if bool(payload.get("planning_exists")) and any(
        bool(payload.get(key)) for key in ("state_exists", "roadmap_exists", "project_exists")
    ):
        return None
    return "If this is the wrong workspace, run `gpd resume --recent` to search other recent projects on this machine."


def _resume_mode_label(value: object) -> str:
    """Format a resume mode for human-facing CLI output."""
    if not isinstance(value, str) or not value.strip():
        return "none"
    return value.replace("_", " ")


def _resume_candidate_source_label(source: object) -> str:
    """Map internal resume candidate sources to concise user-facing labels."""
    labels = {
        "current_execution": "Live execution",
        "session_resume_file": "Session handoff",
        "interrupted_agent": "Interrupted agent",
    }
    source_text = str(source).strip() if source is not None else ""
    return labels.get(source_text, source_text or "Unknown")


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


def _resume_candidate_notes(
    candidate: dict[str, object],
    *,
    active_execution: dict[str, object] | None,
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

    last_result_label = candidate.get("last_result_label")
    if isinstance(last_result_label, str) and last_result_label.strip():
        notes.append(f"last result: {last_result_label.strip()}")

    if bool(candidate.get("first_result_gate_pending")):
        notes.append("first-result gate pending")
    if bool(candidate.get("pre_fanout_review_pending")):
        notes.append("pre-fanout review pending")
    if bool(candidate.get("skeptical_requestioning_required")):
        notes.append("skeptical re-questioning required")
    if bool(candidate.get("downstream_locked")):
        notes.append("downstream locked")

    if active_execution is not None:
        current_task = active_execution.get("current_task")
        current_task_index = active_execution.get("current_task_index")
        current_task_total = active_execution.get("current_task_total")
        if isinstance(current_task, str) and current_task.strip():
            if current_task_index is not None and current_task_total is not None:
                notes.append(f"task {current_task_index}/{current_task_total}: {current_task.strip()}")
            else:
                notes.append(current_task.strip())

        updated_at = active_execution.get("updated_at")
        if isinstance(updated_at, str) and updated_at.strip():
            notes.append(f"updated {updated_at.strip()}")

    if not notes:
        source = str(candidate.get("source") or "").strip()
        status = str(candidate.get("status") or "").strip()
        if source == "session_resume_file" and status == "missing":
            return "Recorded in session continuity metadata, but the handoff file is missing from this workspace."
        if source == "session_resume_file":
            return "Recorded in session continuity metadata."
        if source == "interrupted_agent":
            return "Interrupted agent marker only; inspect agent output before continuing."
        return "No additional resume notes recorded."
    return "; ".join(notes[:5])


def _recent_project_resume_file_state(project_root: object, resume_file: object) -> tuple[bool | None, str | None]:
    """Return whether a recent-project handoff file is still usable."""
    if not isinstance(project_root, str) or not project_root.strip():
        return None, None
    if not isinstance(resume_file, str) or not resume_file.strip():
        return None, None

    project_path = Path(project_root).expanduser()
    if not project_path.exists() or not project_path.is_dir():
        return None, None

    resolved_project = project_path.resolve(strict=False)
    candidate = Path(resume_file).expanduser()
    resolved_target = candidate.resolve(strict=False) if candidate.is_absolute() else (project_path / candidate).resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_project)
    except ValueError:
        return False, "resume file outside project root"
    if not resolved_target.exists():
        return False, "resume file missing"
    if not resolved_target.is_file():
        return False, "resume file is not a file"
    return True, None


def _recent_projects_data_root() -> Path:
    """Return the machine-local home data root for cross-project recovery metadata."""
    return Path.home() / HOME_DATA_DIR_NAME


def _recent_projects_index_paths() -> list[Path]:
    """Return candidate index paths for recent-project recovery data."""
    root = _recent_projects_data_root() / RECENT_PROJECTS_DIR_NAME
    return [root / filename for filename in _RECENT_PROJECTS_INDEX_FILENAMES]


def _recent_project_text(payload: dict[str, object], *keys: str) -> str | None:
    """Return the first non-empty string value among *keys*."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _coerce_recent_project_rows(payload: object) -> list[dict[str, object]]:
    """Normalize a recent-project payload into a list of row dictionaries."""
    if payload is None:
        return []

    data = payload
    if hasattr(data, "model_dump"):
        try:
            data = data.model_dump(mode="json")  # type: ignore[assignment]
        except Exception:
            return []

    if isinstance(data, dict):
        for key in ("projects", "rows", "entries"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in (_normalize_recent_project_row(row) for row in value) if item is not None]
        return [item for item in (_normalize_recent_project_row(data),) if item is not None]

    if isinstance(data, list):
        normalized_rows: list[dict[str, object]] = []
        for row in data:
            row_payload = row
            if hasattr(row_payload, "model_dump"):
                try:
                    row_payload = row_payload.model_dump(mode="json")
                except Exception:
                    continue
            normalized = _normalize_recent_project_row(row_payload)
            if normalized is not None:
                normalized_rows.append(normalized)
        return normalized_rows

    return []


def _normalize_recent_project_row(row: object) -> dict[str, object] | None:
    """Normalize one recent-project row without dropping missing entries."""
    if not isinstance(row, dict):
        return None

    normalized = dict(row)
    project_root = _recent_project_text(normalized, "project_root", "workspace_root", "cwd", "path")
    if project_root is not None:
        normalized["project_root"] = project_root
        project_path = Path(project_root).expanduser()
        normalized["workspace"] = _format_display_path(project_path)
        normalized["available"] = project_path.exists()
        normalized["missing"] = not normalized["available"]
        normalized["command"] = normalized.get("command") or (
            f"gpd --cwd {shlex.quote(str(project_path.resolve(strict=False)))} resume"
            if project_path.is_absolute()
            else None
        )
    else:
        normalized["project_root"] = None
        normalized["workspace"] = "unknown"
        normalized["available"] = False
        normalized["missing"] = True
        normalized["command"] = normalized.get("command") or None

    last_session_at = _recent_project_text(
        normalized,
        "last_session_at",
        "last_seen_at",
        "last_event_at",
        "updated_at",
        "started_at",
    )
    if last_session_at is not None:
        normalized["last_session_at"] = last_session_at

    stopped_at = _recent_project_text(normalized, "stopped_at")
    if stopped_at is not None:
        normalized["stopped_at"] = stopped_at

    resume_file = _recent_project_text(normalized, "resume_file")
    if resume_file is not None:
        normalized["resume_file"] = resume_file
    resume_file_available, resume_file_reason = _recent_project_resume_file_state(
        normalized.get("project_root"),
        normalized.get("resume_file"),
    )
    if resume_file_available is not None:
        normalized["resume_file_available"] = resume_file_available
    if resume_file_reason is not None:
        normalized["resume_file_reason"] = resume_file_reason

    status = _recent_project_text(normalized, "status", "state")
    if not bool(normalized["available"]):
        status = "unavailable"
    elif status is None:
        if bool(normalized.get("resumable")):
            status = "resumable"
        else:
            status = "recent"
    normalized["status"] = status

    resumable_value = normalized.get("resumable")
    if resumable_value is None:
        resumable_value = normalized.get("can_resume")
    if resumable_value is None:
        resumable_value = bool(normalized.get("resume_file"))
    normalized["resumable"] = (
        bool(resumable_value)
        and bool(normalized["available"])
        and normalized.get("resume_file_available") is not False
    )

    return normalized


def _recent_project_sort_key(row: dict[str, object]) -> tuple[int, str, str]:
    """Sort resumable rows first, then by most recent session timestamp."""
    resumable_rank = 0 if bool(row.get("resumable")) else 1
    timestamp = _recent_project_text(
        row,
        "last_session_at",
        "last_seen_at",
        "last_event_at",
        "updated_at",
        "started_at",
    ) or ""
    workspace = str(row.get("workspace") or row.get("project_root") or "")
    return resumable_rank, timestamp, workspace


def _load_recent_projects_rows() -> list[dict[str, object]]:
    """Load the recent-project index, preferring the shared helper module when present."""
    try:
        from gpd.core import recent_projects as recent_projects_module
    except Exception:
        recent_projects_module = None

    if recent_projects_module is not None:
        for attr_name, arg_sets in (
            ("list_recent_projects", ((),)),
            ("load_recent_projects", ((),)),
            ("load_recent_projects_index", ((),)),
            ("get_recent_projects", ((),)),
        ):
            loader = getattr(recent_projects_module, attr_name, None)
            if not callable(loader):
                continue
            for args in arg_sets:
                try:
                    payload = loader(*args)
                except TypeError:
                    continue
                except Exception:
                    continue
                rows = _coerce_recent_project_rows(payload)
                if rows:
                    rows.sort(key=_recent_project_sort_key, reverse=True)
                    rows.sort(key=lambda row: 0 if bool(row.get("resumable")) else 1)
                    return rows

    rows: list[dict[str, object]] = []
    for index_path in _recent_projects_index_paths():
        try:
            raw = index_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        except OSError:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        rows = _coerce_recent_project_rows(payload)
        if rows:
            break

    rows.sort(key=_recent_project_sort_key, reverse=True)
    rows.sort(key=lambda row: 0 if bool(row.get("resumable")) else 1)
    return rows


def _resume_recent_project_command(row: dict[str, object]) -> str:
    """Return the exact command to inspect one recent project."""
    project_root = row.get("project_root")
    if not isinstance(project_root, str) or not project_root.strip():
        return "unavailable"
    project_path = Path(project_root).expanduser().resolve(strict=False)
    return f"gpd --cwd {shlex.quote(str(project_path))} resume"


def _render_recent_resume_summary(rows: list[dict[str, object]]) -> None:
    """Render the recent-project picker for cross-project recovery."""
    console.print("[bold]Recent Projects[/]")
    console.print("[dim]Machine-local recovery index. Select a project and then run the exact command shown in the table.[/]")
    console.print()

    if not rows:
        console.print("[dim]No recent projects are recorded on this machine yet.[/]")
        console.print("[dim]Run `gpd resume` inside a project first, or wait for session continuity to be recorded.[/]")
        return

    table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("Workspace")
    table.add_column("Last session")
    table.add_column("Stopped at")
    table.add_column("Resumable")
    table.add_column("Status")
    table.add_column("Command")
    for idx, row in enumerate(rows, start=1):
        table.add_row(
            str(idx),
            str(row.get("workspace") or _format_display_path(str(row.get("project_root") or "")) or "unknown"),
            str(row.get("last_session_at") or row.get("last_seen_at") or row.get("last_event_at") or "—"),
            str(row.get("stopped_at") or "—"),
            "yes" if bool(row.get("resumable")) else "no",
            str(row.get("status") or "unknown"),
            _resume_recent_project_command(row),
        )
    console.print(table)


def _render_resume_summary(payload: dict[str, object]) -> None:
    """Render a read-only local recovery summary for humans."""
    candidates = payload.get("segment_candidates")
    segment_candidates = [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []
    active_execution_raw = payload.get("active_execution_segment")
    active_execution = active_execution_raw if isinstance(active_execution_raw, dict) else None

    console.print("[bold]Resume Summary[/]")
    console.print("[dim]Read-only local recovery snapshot for this workspace.[/]")
    console.print()

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style=f"bold {_INSTALL_ACCENT_COLOR}")
    summary.add_column()
    summary.add_row("Workspace", _format_display_path(_get_cwd()))
    summary.add_row("Status", _resume_status_message(payload))
    summary.add_row("Resume mode", _resume_mode_label(payload.get("resume_mode")))
    summary.add_row("Candidates", str(len(segment_candidates)))
    summary.add_row("Live execution", "yes" if bool(payload.get("has_live_execution")) else "no")
    summary.add_row("Autonomy", str(payload.get("autonomy") or "unknown"))
    summary.add_row("Research mode", str(payload.get("research_mode") or "unknown"))

    paused_at = payload.get("execution_paused_at")
    if isinstance(paused_at, str) and paused_at.strip():
        summary.add_row("Paused at", paused_at.strip())

    primary_resume_file = payload.get("execution_resume_file")
    if isinstance(primary_resume_file, str) and primary_resume_file.strip():
        summary.add_row("Primary pointer", _format_display_path(primary_resume_file.strip()))

    console.print(summary)

    machine_change_notice = payload.get("machine_change_notice")
    notices: list[str] = []
    if isinstance(machine_change_notice, str) and machine_change_notice.strip():
        notices.append(machine_change_notice.strip())

    if active_execution is not None:
        if bool(active_execution.get("waiting_for_review")):
            notices.append("Execution is currently waiting for review before continuation.")
        if bool(payload.get("execution_pre_fanout_review_pending")):
            notices.append("Pre-fanout review is still pending.")
        if bool(payload.get("execution_skeptical_requestioning_required")):
            notices.append("Skeptical re-questioning is required before downstream work.")
        if bool(payload.get("execution_downstream_locked")):
            notices.append("Downstream work remains locked by the current execution snapshot.")
        blocked_reason = active_execution.get("blocked_reason")
        if isinstance(blocked_reason, str) and blocked_reason.strip():
            notices.append(f"Execution is blocked: {blocked_reason.strip()}")
    missing_session_resume_file = payload.get("missing_session_resume_file")
    if isinstance(missing_session_resume_file, str) and missing_session_resume_file.strip():
        notices.append(
            "Recorded session handoff is missing: "
            f"{_format_display_path(missing_session_resume_file.strip())}."
        )

    if notices:
        console.print()
        console.print("[bold]Notices[/]")
        for notice in notices:
            console.print(f"- {notice}")

    console.print()
    console.print("[bold]Resume Candidates[/]")
    if segment_candidates:
        table = Table(show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
        table.add_column("#", justify="right", no_wrap=True)
        table.add_column("Source")
        table.add_column("Status")
        table.add_column("Phase/Plan")
        table.add_column("Target")
        table.add_column("Notes")
        for idx, candidate in enumerate(segment_candidates, start=1):
            candidate_execution = active_execution if candidate.get("source") == "current_execution" else None
            status = str(candidate.get("status") or "unknown").strip().replace("_", " ")
            table.add_row(
                str(idx),
                _resume_candidate_source_label(candidate.get("source")),
                status or "unknown",
                _resume_candidate_phase_plan(candidate),
                _resume_candidate_target(candidate),
                _resume_candidate_notes(candidate, active_execution=candidate_execution),
            )
        console.print(table)
    else:
        console.print(
            "[dim]No resumable execution segment, session handoff, or interrupted-agent marker is currently recorded.[/]"
        )

    console.print()
    console.print("[bold]References[/]")
    console.print("- `gpd resume` is the public local recovery surface.")
    console.print("- `gpd init resume` remains the machine-readable backend used by runtime resume workflows.")
    console.print("- `gpd observe sessions --last 5` shows recent local observability sessions.")
    hint = _resume_recent_hint(payload)
    if hint is not None:
        console.print(f"- {hint}")

    try:
        from gpd.adapters import get_adapter

        runtime_name = detect_runtime_for_gpd_use(cwd=_get_cwd())
        runtime_resume_command = get_adapter(runtime_name).format_command("resume-work")
    except Exception:
        runtime_resume_command = None
    if isinstance(runtime_resume_command, str) and runtime_resume_command.strip():
        console.print(f"- `{runtime_resume_command}` is the guided in-runtime continuation surface.")


@app.command("resume")
def resume(
    recent: bool = typer.Option(
        False,
        "--recent",
        help="List recent GPD projects on this machine instead of the current workspace recovery summary",
    ),
) -> None:
    """Summarize local recovery state or list machine-local recent projects."""
    if recent:
        rows = _load_recent_projects_rows()
        if _raw:
            _output({"count": len(rows), "projects": rows})
            return
        _render_recent_resume_summary(rows)
        return

    from gpd.core.context import init_resume

    payload = init_resume(_get_cwd())
    if _raw:
        _output(payload)
        return
    _render_resume_summary(payload)


# ═══════════════════════════════════════════════════════════════════════════
# progress — Progress rendering
# ═══════════════════════════════════════════════════════════════════════════


@app.command("progress")
def progress(
    fmt: str = typer.Argument("json", help="Format: json, bar, or table"),
) -> None:
    """Render progress in the specified format."""
    from gpd.core.phases import progress_render

    _output(progress_render(_get_cwd(), fmt))


# ═══════════════════════════════════════════════════════════════════════════
# convention — Convention lock management
# ═══════════════════════════════════════════════════════════════════════════

convention_app = typer.Typer(help="Convention lock (notation, units, sign conventions)")
app.add_typer(convention_app, name="convention")


def _load_lock():  # noqa: ANN202 — returns ConventionLock (imported inside)
    """Load ConventionLock from state.json in the current working directory."""
    import json

    from gpd.contracts import ConventionLock
    from gpd.core.constants import ProjectLayout

    state_path = ProjectLayout(_get_cwd()).state_json
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except OSError:
        return ConventionLock()
    except json.JSONDecodeError as e:
        _error(f"Malformed state.json: {e}")

    lock_data = raw.get("convention_lock", {})
    if not isinstance(lock_data, dict):
        return ConventionLock()
    return ConventionLock(**lock_data)



@convention_app.command("set")
def convention_set(
    key: str = typer.Argument(..., help="Convention key"),
    value: str = typer.Argument(..., help="Convention value"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing convention"),
) -> None:
    """Set a convention in the convention lock."""
    import json as _json

    from gpd.contracts import ConventionLock
    from gpd.core.constants import ProjectLayout
    from gpd.core.conventions import convention_set
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    # Perform the entire read-modify-write under a single file lock to avoid
    # the TOCTOU race that existed when _load_lock() ran before _save_lock().
    with file_lock(state_path):
        try:
            raw = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            raw = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")

        lock_data = raw.get("convention_lock", {})
        if not isinstance(lock_data, dict):
            lock_data = {}
        lock = ConventionLock(**lock_data)

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


# ═══════════════════════════════════════════════════════════════════════════
# result — Intermediate result tracking
# ═══════════════════════════════════════════════════════════════════════════

result_app = typer.Typer(help="Intermediate results with dependency tracking")
app.add_typer(result_app, name="result")


@result_app.command("add")
def result_add(
    id: str | None = typer.Option(None, "--id", help="Result ID"),
    equation: str | None = typer.Option(None, "--equation", help="LaTeX equation"),
    description: str | None = typer.Option(None, "--description", help="Description"),
    units: str | None = typer.Option(None, "--units", help="Physical units"),
    validity: str | None = typer.Option(None, "--validity", help="Validity range"),
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    depends_on: str | None = typer.Option(None, "--depends-on", help="Comma-separated dependency IDs"),
    verified: bool = typer.Option(False, "--verified", help="Mark as verified"),
) -> None:
    """Add an intermediate result to the results registry."""
    import json as _json

    from gpd.core.constants import ProjectLayout
    from gpd.core.results import result_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    deps = depends_on.split(",") if depends_on else []
    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
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


def _load_state_dict() -> dict:
    """Load state.json as a plain dict for commands that need raw state."""
    import json

    from gpd.core.constants import ProjectLayout

    state_path = ProjectLayout(_get_cwd()).state_json
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except json.JSONDecodeError as e:
        _error(f"Malformed state.json: {e}")
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
    result_id: str = typer.Argument(..., help="Result ID"),
) -> None:
    """Show BFS dependency graph for a result."""
    from gpd.core.results import result_deps

    _output(result_deps(_load_state_dict(), result_id))


@result_app.command("verify")
def result_verify(
    result_id: str = typer.Argument(..., help="Result ID to mark verified"),
) -> None:
    """Mark a result as verified."""
    import json as _json

    from gpd.core.constants import ProjectLayout
    from gpd.core.results import result_verify
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
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
    depends_on: str | None = typer.Option(None, "--depends-on", help="Comma-separated dependency IDs"),
    verified: bool | None = typer.Option(None, "--verified/--no-verified", help="Mark as verified or un-verify"),
) -> None:
    """Update an existing result."""
    import json as _json

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
        opts["depends_on"] = depends_on.split(",")
    if verified is not None:
        opts["verified"] = verified

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
        _fields, updated = result_update(state, result_id, **opts)
        save_state_json_locked(cwd, state)
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

    report = run_health(_get_cwd(), fix=fix)
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
) -> None:
    """Check GPD installation and environment health, or inspect runtime readiness."""
    from gpd.core.health import run_doctor
    from gpd.specs import SPECS_DIR

    if global_install and local_install:
        _error("Cannot specify both --global and --local")

    if runtime is None:
        if global_install or local_install or target_dir is not None:
            _error("--runtime is required when using --global, --local, or --target-dir")
        _output(run_doctor(specs_dir=SPECS_DIR))
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
    _output(
        run_doctor(
            specs_dir=SPECS_DIR,
            runtime=normalized_runtime,
            install_scope=install_scope,
            target_dir=resolved_target,
            cwd=_get_cwd(),
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
) -> None:
    """Search across phases by provides/requires/text."""
    from gpd.core.query import query as query_search

    _output(
        query_search(
            _get_cwd(),
            provides=provides,
            requires=requires,
            affects=affects,
            equation=equation,
            text=text,
            phase_range=phase_range,
        )
    )


@query_app.command("deps")
def query_deps(
    identifier: str = typer.Argument(..., help="Result identifier to trace dependencies for"),
) -> None:
    """Show what provides and requires a given result identifier."""
    from gpd.core.query import query_deps

    _output(query_deps(_get_cwd(), identifier))


@query_app.command("assumptions")
def query_assumptions(
    assumption: list[str] = typer.Argument(None, help="Assumption text to search for"),
) -> None:
    """Search for assumptions across phases."""
    from gpd.core.query import query_assumptions

    text = " ".join(assumption) if assumption else ""
    if not text.strip():
        _error("Usage: gpd query assumptions <search-term>")
    _output(query_assumptions(_get_cwd(), text))


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
    _output(suggest_next(_get_cwd(), **kwargs))


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
    blocked_reason: str | None
    review_reason: str | None
    last_update_at: str | None
    last_update_age: str | None
    last_update_age_minutes: float | None
    resume_file: str | None
    suggested_next_commands: list[ObserveExecutionSuggestion]
    current_execution: dict[str, object] | None = None

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

    suggested_next_commands: list[ObserveExecutionSuggestion] = []
    if not visibility.has_live_execution:
        suggested_next_commands.extend(
            [
                ObserveExecutionSuggestion(
                    command="gpd observe sessions --last 5",
                    reason="Inspect recent local observability sessions",
                ),
                ObserveExecutionSuggestion(
                    command="gpd progress --brief",
                    reason="Check workspace-level progress separately from live execution telemetry",
                ),
            ]
        )
    else:
        if status_classification in {"blocked", "waiting", "paused-or-resumable"} or visibility.possibly_stalled:
            suggested_next_commands.append(
                ObserveExecutionSuggestion(
                    command="gpd resume",
                    reason="Review the current local recovery snapshot and the best resumable target",
                )
            )
        suggested_next_commands.extend(
            [
                ObserveExecutionSuggestion(
                    command="gpd observe show --last 20",
                    reason="Inspect the recent observability event trail for this workspace",
                ),
                ObserveExecutionSuggestion(
                    command="gpd observe sessions --last 5",
                    reason="Compare recent observability sessions and their command history",
                ),
                ObserveExecutionSuggestion(
                    command="gpd progress --brief",
                    reason="Check phase-level progress separately from live execution state",
                ),
            ]
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
        blocked_reason=visibility.blocked_reason,
        review_reason=visibility.review_reason,
        last_update_at=visibility.last_updated_at,
        last_update_age=visibility.last_updated_age_label,
        last_update_age_minutes=visibility.last_updated_age_minutes,
        resume_file=visibility.resume_file,
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
    summary.add_row("Waiting reason", result.waiting_reason or "—")
    summary.add_row("Blocked reason", result.blocked_reason or "—")
    summary.add_row("Review reason", result.review_reason or "—")
    summary.add_row("Last update age", result.last_update_age or "unknown")
    if result.resume_file:
        summary.add_row("Resume file", _format_display_path(result.resume_file))
    console.print(summary)

    console.print()
    console.print("[bold]Suggested next commands[/]")
    for suggestion in result.suggested_next_commands:
        console.print(f"- {suggestion.command} — {suggestion.reason}")

    if not result.found:
        console.print()
        console.print("[dim]No live execution snapshot is currently recorded for this workspace.[/]")
    elif result.possibly_stalled:
        console.print()
        console.print(
            f"[yellow]This execution is possibly stalled.[/] It is still marked active and has not updated for at least {result.stale_after_minutes} minutes."
        )


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
) -> None:
    """Assemble context for executing a phase."""
    from gpd.core.context import init_execute_phase

    includes = _parse_init_include_option(
        include,
        command_name="gpd init execute-phase",
        allowed=_INIT_EXECUTE_PHASE_INCLUDES,
    )
    _output(init_execute_phase(_get_cwd(), phase, includes=includes))


@init_app.command("plan-phase")
def init_plan_phase(
    phase: str | None = typer.Argument(None, help="Phase number"),
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
) -> None:
    """Assemble context for planning a phase."""
    from gpd.core.context import init_plan_phase

    includes = _parse_init_include_option(
        include,
        command_name="gpd init plan-phase",
        allowed=_INIT_PLAN_PHASE_INCLUDES,
    )
    _output(init_plan_phase(_get_cwd(), phase, includes=includes))


@init_app.command("new-project")
def init_new_project() -> None:
    """Assemble context for starting a new project."""
    from gpd.core.context import init_new_project

    _output(init_new_project(_get_cwd()))


@init_app.command("new-milestone")
def init_new_milestone() -> None:
    """Assemble context for starting a new milestone."""
    from gpd.core.context import init_new_milestone

    _output(init_new_milestone(_get_cwd()))


@init_app.command("quick")
def init_quick(
    description: list[str] = typer.Argument(None, help="Task description"),
) -> None:
    """Assemble context for a quick task."""
    from gpd.core.context import init_quick

    text = " ".join(description) if description else None
    _output(init_quick(_get_cwd(), description=text))


@init_app.command("resume")
def init_resume() -> None:
    """Assemble context for resuming previous work."""
    from gpd.core.context import init_resume

    _output(init_resume(_get_cwd()))


@init_app.command("verify-work")
def init_verify_work(
    phase: str | None = typer.Argument(None, help="Phase to verify"),
) -> None:
    """Assemble context for verifying completed work."""
    from gpd.core.context import init_verify_work

    _output(init_verify_work(_get_cwd(), phase))


@init_app.command("progress")
def init_progress(
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
) -> None:
    """Assemble context for progress review."""
    from gpd.core.context import init_progress

    includes = _parse_init_include_option(
        include,
        command_name="gpd init progress",
        allowed=_INIT_PROGRESS_INCLUDES,
    )
    _output(init_progress(_get_cwd(), includes=includes))


@init_app.command("map-research")
def init_map_research() -> None:
    """Assemble context for research mapping."""
    from gpd.core.context import init_map_research

    _output(init_map_research(_get_cwd()))


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
) -> None:
    """Assemble context for generic phase operations."""
    from gpd.core.context import init_phase_op

    includes = _parse_init_include_option(
        include,
        command_name="gpd init phase-op",
        allowed=_INIT_PHASE_OP_INCLUDES,
    )
    _output(init_phase_op(_get_cwd(), phase, includes))


@init_app.command("milestone-op")
def init_milestone_op() -> None:
    """Assemble context for milestone operations."""
    from gpd.core.context import init_milestone_op

    _output(init_milestone_op(_get_cwd()))


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
    import json as _json

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
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
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
    import json as _json

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
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
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
    import json as _json

    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import question_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
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
) -> None:
    """Mark a question as resolved."""
    import json as _json

    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import question_resolve
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
        res = question_resolve(state, " ".join(text))
        save_state_json_locked(cwd, state)
    _output(res)


calculation_app = typer.Typer(help="Calculation tracking")
app.add_typer(calculation_app, name="calculation")


@calculation_app.command("add")
def calculation_add(
    text: list[str] = typer.Argument(..., help="Calculation description"),
) -> None:
    """Add a calculation to track."""
    import json as _json

    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import calculation_add
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
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
    import json as _json

    from gpd.core.constants import ProjectLayout
    from gpd.core.extras import calculation_complete
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json

    with file_lock(state_path):
        try:
            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except OSError:
            state = {}
        except _json.JSONDecodeError as e:
            _error(f"Malformed state.json: {e}")
        res = calculation_complete(state, " ".join(text))
        save_state_json_locked(cwd, state)
    _output(res)


# ═══════════════════════════════════════════════════════════════════════════
# config — Configuration management
# ═══════════════════════════════════════════════════════════════════════════

config_app = typer.Typer(help="GPD configuration")
app.add_typer(config_app, name="config")


class _PermissionsResolutionError(RuntimeError):
    """Internal error used to report non-fatal permissions resolution failures."""


def _raise_permissions_resolution_error(message: str, *, strict: bool) -> None:
    """Raise a permissions-resolution error, surfacing it only when requested."""
    if strict:
        _error(message)
    raise _PermissionsResolutionError(message)


def _resolve_permissions_runtime_name(runtime: str | None, *, strict: bool = True) -> str:
    """Resolve the runtime to use for permission status/sync commands."""
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_active_runtime

    supported = _supported_runtime_names()
    if runtime is not None:
        normalized = normalize_runtime_name(runtime)
        if normalized is None or normalized not in supported:
            _raise_permissions_resolution_error(
                f"Unknown runtime {runtime!r}. Supported: {', '.join(supported)}",
                strict=strict,
            )
        return normalized

    detected = detect_active_runtime(cwd=_get_cwd())
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
    if target_dir:
        resolved = _resolve_cli_target_dir(target_dir)
        try:
            adapter.validate_target_runtime(resolved, action=action)
        except RuntimeError as exc:
            _error(str(exc))
    else:
        install_target = detect_runtime_install_target(runtime_name, cwd=_get_cwd())
        if install_target is not None:
            resolved = install_target.config_dir
        else:
            install_scope = detect_install_scope(runtime_name, cwd=_get_cwd())
            if install_scope == "global":
                resolved = adapter.resolve_target_dir(True, _get_cwd())
            elif install_scope == "local":
                resolved = adapter.resolve_target_dir(False, _get_cwd())
            else:
                local_target = adapter.resolve_target_dir(False, _get_cwd())
                global_target = adapter.resolve_target_dir(True, _get_cwd())
                if adapter.has_complete_install(local_target):
                    resolved = local_target
                elif adapter.has_complete_install(global_target):
                    resolved = global_target
                else:
                    _raise_permissions_resolution_error(
                        f"No GPD install found for runtime {runtime_name!r}. Run `gpd install {runtime_name}` first.",
                        strict=strict,
                    )

    if not adapter.has_complete_install(resolved):
        _raise_permissions_resolution_error(
            f"No complete GPD install found at {_format_display_path(resolved)}.",
            strict=strict,
        )
    return resolved


def _runtime_permissions_payload(
    *,
    runtime: str | None,
    autonomy: str | None,
    target_dir: str | None,
    apply_sync: bool,
    strict: bool,
) -> dict[str, object]:
    """Return runtime-permissions status or sync payload for the selected runtime."""
    from gpd.adapters import get_adapter
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN

    try:
        runtime_name = _resolve_permissions_runtime_name(runtime, strict=strict)
    except _PermissionsResolutionError as exc:
        return {
            "runtime": None,
            "target": None,
            "sync_applied": False,
            "changed": False,
            "message": str(exc),
        }

    if runtime is None and runtime_name == RUNTIME_UNKNOWN:
        if strict:
            _error("No active runtime was detected. Pass --runtime explicitly.")
        return {
            "runtime": None,
            "target": None,
            "sync_applied": False,
            "changed": False,
            "message": "No active runtime was detected. Run `gpd permissions sync --runtime <name>` after installing GPD into a runtime.",
        }

    try:
        resolved_target_dir = _resolve_permissions_target_dir(
            runtime_name,
            target_dir=target_dir,
            strict=strict,
            action=("sync" if apply_sync else "inspect") + " runtime permissions on",
        )
    except _PermissionsResolutionError as exc:
        return {
            "runtime": runtime_name,
            "target": None if target_dir is None else str(_resolve_cli_target_dir(target_dir)),
            "sync_applied": False,
            "changed": False,
            "message": str(exc),
        }

    adapter = get_adapter(runtime_name)
    autonomy_value = _resolve_permissions_autonomy(autonomy, strict=strict)
    payload = (
        adapter.sync_runtime_permissions(resolved_target_dir, autonomy=autonomy_value)
        if apply_sync
        else adapter.runtime_permissions_status(resolved_target_dir, autonomy=autonomy_value)
    )
    return {
        "runtime": runtime_name,
        "target": str(resolved_target_dir),
        "autonomy": autonomy_value,
        **payload,
    }


def _permissions_status_payload(
    *,
    runtime: str | None,
    autonomy: str | None,
    target_dir: str | None,
) -> dict[str, object]:
    """Return a status payload annotated for unattended-readiness checks."""
    payload = _runtime_permissions_payload(
        runtime=runtime,
        autonomy=autonomy,
        target_dir=target_dir,
        apply_sync=False,
        strict=True,
    )
    ready = (
        bool(payload.get("runtime"))
        and bool(payload.get("target"))
        and bool(payload.get("config_aligned", False))
        and not bool(payload.get("requires_relaunch", False))
    )

    if ready:
        readiness = "ready"
        readiness_message = "Runtime permissions are ready for unattended use."
    elif bool(payload.get("requires_relaunch", False)):
        readiness = "relaunch-required"
        readiness_message = "Runtime permissions are aligned, but the runtime must be relaunched before unattended use."
    elif "config_aligned" in payload:
        readiness = "not-ready"
        readiness_message = "Runtime permissions are not ready for unattended use under the requested autonomy."
    else:
        readiness = "unresolved"
        readiness_message = str(payload.get("message") or "Runtime permissions are not ready for unattended use.")

    next_step = payload.get("next_step")
    if not isinstance(next_step, str) or not next_step.strip():
        next_step = None
    if next_step is None:
        runtime_name = payload.get("runtime")
        autonomy_value = payload.get("autonomy")
        if readiness == "relaunch-required" and isinstance(runtime_name, str) and runtime_name:
            next_step = f"Exit and relaunch {runtime_name} before treating unattended use as ready."
        elif (
            readiness == "not-ready"
            and isinstance(runtime_name, str)
            and runtime_name
            and isinstance(autonomy_value, str)
            and autonomy_value
        ):
            next_step = (
                "Use `gpd:settings` inside the runtime for guided changes, or run "
                f"`gpd permissions sync --runtime {runtime_name} --autonomy {autonomy_value}` "
                "from your normal system terminal."
            )
        elif readiness == "unresolved" and runtime is None:
            next_step = "Pass `--runtime <name>` to inspect a specific installed runtime."

    return {
        **payload,
        "readiness": readiness,
        "ready": ready,
        "readiness_message": readiness_message,
        "next_step": next_step,
    }


permissions_app = typer.Typer(help="Runtime permission readiness and sync")
app.add_typer(permissions_app, name="permissions")


@permissions_app.command("status")
def permissions_status(
    runtime: str | None = typer.Option(None, "--runtime", help="Runtime name to inspect"),
    autonomy: str | None = typer.Option(None, "--autonomy", help="Autonomy to compare against"),
    target_dir: str | None = typer.Option(None, "--target-dir", help="Explicit runtime config directory"),
) -> None:
    """Check whether a runtime install is ready for unattended use under the requested autonomy."""
    _output(_permissions_status_payload(runtime=runtime, autonomy=autonomy, target_dir=target_dir))


@permissions_app.command("sync")
def permissions_sync(
    runtime: str | None = typer.Option(None, "--runtime", help="Runtime name to update"),
    autonomy: str | None = typer.Option(None, "--autonomy", help="Autonomy to apply"),
    target_dir: str | None = typer.Option(None, "--target-dir", help="Explicit runtime config directory"),
) -> None:
    """Advanced: persist runtime-owned permission settings for the requested autonomy. Use `gpd:settings` for guided changes."""
    _output(
        _runtime_permissions_payload(
            runtime=runtime,
            autonomy=autonomy,
            target_dir=target_dir,
            apply_sync=True,
            strict=True,
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
        result["guided_path"] = "Use `gpd:settings` inside the runtime for guided autonomy changes."
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


def _find_manuscript_main(cwd: Path) -> Path | None:
    """Locate the primary manuscript entry point if one exists."""
    for rel_path in ("paper/main.tex", "manuscript/main.tex", "draft/main.tex"):
        candidate = cwd / rel_path
        if candidate.exists():
            return candidate
    return None


def _resolve_review_preflight_manuscript(
    cwd: Path,
    subject: str | None,
    *,
    allow_markdown: bool = True,
) -> tuple[Path | None, str]:
    """Resolve a review-preflight manuscript target from an explicit subject or defaults."""
    if subject:
        target = Path(subject)
        if not target.is_absolute():
            target = cwd / target

        if not target.exists():
            return None, f"missing explicit manuscript target {_format_display_path(target)}"

        if target.is_file():
            if target.suffix == ".tex" or (allow_markdown and target.suffix == ".md"):
                return target, f"{_format_display_path(target)} present"
            if target.suffix == ".md":
                return None, f"explicit manuscript target must be a .tex file: {_format_display_path(target)}"
            return None, f"explicit manuscript target must be a .tex or .md file: {_format_display_path(target)}"

        if target.is_dir():
            candidates = [target / "main.tex"]
            if allow_markdown:
                candidates.append(target / "main.md")
            candidate = _first_existing_path(*candidates)
            if candidate is not None:
                return candidate, f"{_format_display_path(target)} resolved to {_format_display_path(candidate)}"
            if not allow_markdown and (target / "main.md").exists():
                return (
                    None,
                    f"expected main.tex under {_format_display_path(target)} for LaTeX-only submission "
                    f"(found {_format_display_path(target / 'main.md')})",
                )
            return None, f"no manuscript entry point found under {_format_display_path(target)}"

    manuscript = _find_manuscript_main(cwd)
    if manuscript is not None:
        return manuscript, f"{_format_display_path(manuscript)} present"
    return None, "no paper/main.tex, manuscript/main.tex, or draft/main.tex found"


def _resolve_review_preflight_publication_artifact(manuscript: Path, *filenames: str) -> Path | None:
    """Resolve review artifacts only from the active manuscript directory."""
    return _first_existing_path(*(manuscript.parent / filename for filename in filenames))


_REVIEW_LEDGER_FILENAME_RE = re.compile(r"^REVIEW-LEDGER(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_REFEREE_DECISION_FILENAME_RE = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")


def _review_artifact_round(path: Path, *, pattern: re.Pattern[str]) -> tuple[int, str] | None:
    match = pattern.fullmatch(path.name)
    if match is None:
        return None
    round_text = match.group("round")
    round_number = int(round_text) if round_text else 1
    return round_number, match.group("round_suffix") or ""


def _latest_publication_review_artifacts(review_dir: Path) -> PublicationReviewArtifacts | None:
    """Return the latest round-specific review-ledger/decision pair, if any."""
    ledger_by_round: dict[int, Path] = {}
    decision_by_round: dict[int, Path] = {}

    for path in sorted(review_dir.glob("REVIEW-LEDGER*.json")):
        details = _review_artifact_round(path, pattern=_REVIEW_LEDGER_FILENAME_RE)
        if details is not None:
            ledger_by_round[details[0]] = path

    for path in sorted(review_dir.glob("REFEREE-DECISION*.json")):
        details = _review_artifact_round(path, pattern=_REFEREE_DECISION_FILENAME_RE)
        if details is not None:
            decision_by_round[details[0]] = path

    all_rounds = sorted({*ledger_by_round, *decision_by_round}, reverse=True)
    if not all_rounds:
        return None

    round_number = all_rounds[0]
    return PublicationReviewArtifacts(
        round_number=round_number,
        round_suffix="" if round_number <= 1 else f"-R{round_number}",
        review_ledger=ledger_by_round.get(round_number),
        referee_decision=decision_by_round.get(round_number),
    )


def _normalize_review_path_label(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    return posixpath.normpath(normalized)


def _manuscript_matches_review_artifact_path(artifact_path: str, manuscript: Path, *, cwd: Path) -> bool:
    normalized_artifact_path = _normalize_review_path_label(artifact_path)
    if not normalized_artifact_path:
        return False

    resolved_manuscript = manuscript.expanduser().resolve(strict=False)
    resolved_cwd = cwd.expanduser().resolve(strict=False)
    candidates = {
        _normalize_review_path_label(resolved_manuscript.as_posix()),
        _normalize_review_path_label(manuscript.as_posix()),
    }
    try:
        candidates.add(_normalize_review_path_label(resolved_manuscript.relative_to(resolved_cwd).as_posix()))
    except ValueError:
        pass
    return normalized_artifact_path in candidates


_REVIEW_PRECHECK_BLOCKING_CONDITIONS: dict[str, tuple[str, ...]] = {
    "project_state": ("missing project state",),
    "state_integrity": ("degraded review integrity",),
    "roadmap": ("missing roadmap",),
    "conventions": ("missing conventions",),
    "research_artifacts": ("no research artifacts",),
    "summary_frontmatter": ("degraded review integrity",),
    "verification_frontmatter": ("degraded review integrity",),
    "manuscript": ("missing manuscript",),
    "compiled_manuscript": ("missing compiled manuscript",),
    "referee_report_source": ("missing referee report source when provided as a path",),
    "phase_lookup": ("missing phase artifacts",),
    "phase_summaries": ("missing phase artifacts",),
    "publication_review_outcome": ("peer-review recommendation blocks submission when staged review artifacts are present",),
}

_REVIEW_PRECHECK_REQUIRED_EVIDENCE: dict[str, tuple[str, ...]] = {
    "research_artifacts": ("phase summaries or milestone digest",),
    "verification_reports": ("verification reports",),
    "artifact_manifest": ("artifact manifest",),
    "bibliography_audit": ("bibliography audit",),
    "bibliography_audit_clean": ("bibliography audit",),
    "review_ledger": ("peer-review review ledger when available",),
    "review_ledger_valid": ("peer-review review ledger when available",),
    "referee_decision": ("peer-review referee decision when available",),
    "referee_decision_valid": ("peer-review referee decision when available",),
    "referee_report_source": ("referee report source when provided as a path",),
    "reproducibility_manifest": ("reproducibility manifest",),
    "reproducibility_ready": ("reproducibility manifest",),
}

_PHASE_EXECUTED_STATUSES = {
    "phase complete — ready for verification",
    "verifying",
    "complete",
    "milestone complete",
}


def _normalized_contract_entries(values: list[str]) -> set[str]:
    """Normalize review-contract strings for case-insensitive membership checks."""
    return {value.strip().lower() for value in values if value and value.strip()}


def _review_preflight_check_is_blocking(contract: object, check_name: str) -> bool:
    """Return True when the typed review contract marks a check as hard-blocking."""
    blocking_conditions = _normalized_contract_entries(getattr(contract, "blocking_conditions", []))
    required_evidence = _normalized_contract_entries(getattr(contract, "required_evidence", []))

    return (
        any(alias in blocking_conditions for alias in _REVIEW_PRECHECK_BLOCKING_CONDITIONS.get(check_name, ()))
        or any(alias in required_evidence for alias in _REVIEW_PRECHECK_REQUIRED_EVIDENCE.get(check_name, ()))
    )


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
                f'required_state=phase_executed satisfied for current phase {current_phase} '
                f'(status "{current_status}")'
            )
        expected_statuses = "Phase complete — ready for verification, Verifying, Complete, or Milestone complete"
        return False, (
            f"required_state=phase_executed expects current phase {current_phase} to be in one of: "
            f'{expected_statuses}; found "{current_status or "unknown"}"'
        )

    resolved_phase_info = phase_info if phase_info is not None else (find_phase(cwd, target_phase) if target_phase else None)
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


_PUBLICATION_BLOCKER_PATTERNS = (
    re.compile(r"\bpublication\b"),
    re.compile(r"\b(arxiv|submission|manuscript)\b"),
    re.compile(r"\b(peer review|peer-review|review round|referee)\b"),
    re.compile(r"\b(journal|venue)\b"),
)


def _looks_like_publication_blocker(text: str) -> bool:
    """Return True when text clearly refers to publication/review readiness."""
    lowered = text.casefold().strip()
    return any(pattern.search(lowered) for pattern in _PUBLICATION_BLOCKER_PATTERNS)


def _current_publication_blockers(cwd: Path) -> list[str]:
    """Return unresolved publication blockers from state.json."""
    from gpd.core.state import load_state_json

    state_obj = load_state_json(cwd)
    if not isinstance(state_obj, dict):
        return []

    raw_blockers = state_obj.get("blockers") or []
    blockers: list[str] = []
    for item in raw_blockers:
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            lowered = text.lower()
            if "[resolved]" in lowered or "~~" in text:
                continue
            if _looks_like_publication_blocker(text):
                blockers.append(text)
        elif isinstance(item, dict) and not item.get("resolved", False):
            text = str(item.get("text") or item.get("description") or "").strip()
            labels = " ".join(
                str(item.get(key) or "").strip()
                for key in ("kind", "type", "category", "tag", "scope")
                if str(item.get(key) or "").strip()
            )
            if text and (_looks_like_publication_blocker(text) or (labels and _looks_like_publication_blocker(labels))):
                blockers.append(text)
    return blockers


def _has_any_phase_summary(phases_dir: Path) -> bool:
    """Return True when any numbered or standalone summary exists."""
    if not phases_dir.exists():
        return False
    return any(path.is_file() for path in phases_dir.rglob("*SUMMARY.md"))


def _validate_phase_artifacts(phases_dir: Path, schema_name: str) -> list[str]:
    """Return per-file frontmatter validation failures for phase artifacts."""
    from gpd.core.frontmatter import validate_frontmatter

    if not phases_dir.exists():
        return []

    suffix = "*SUMMARY.md" if schema_name == "summary" else "*VERIFICATION.md"
    failures: list[str] = []
    for path in sorted(phases_dir.rglob(suffix)):
        try:
            content = path.read_text(encoding="utf-8")
            validation = validate_frontmatter(content, schema_name, source_path=path)
        except Exception as exc:  # pragma: no cover - defensive file parsing guard
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
    except OSError as exc:
        raise GPDError(f"Failed to read text input from {source}: {exc}") from exc


def _project_root_for_json_input(input_path: str) -> Path:
    """Return the best project-root anchor for a JSON artifact input path."""

    cwd = _get_cwd()
    if input_path == "-":
        return cwd

    target = Path(input_path)
    if not target.is_absolute():
        return cwd

    resolved = target.expanduser().resolve(strict=False)
    for base in (resolved.parent, *resolved.parent.parents):
        if (base / "GPD").is_dir():
            return base
    return cwd


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
        _get_cwd() / "references" / f"{bib_stem}.bib",
    )
    return _first_existing_path(*candidates)


def _default_paper_output_dir(config_file: Path) -> Path:
    """Resolve the default durable output directory for a paper build."""
    return config_file.resolve(strict=False).parent


def _reject_legacy_paper_config_location(config_file: Path) -> None:
    """Reject removed paper-config locations under internal planning storage."""
    resolved_config = config_file.resolve(strict=False)
    project_root = _get_cwd().resolve(strict=False)
    for legacy_config_root in (project_root / "GPD" / "paper", project_root / ".gpd" / "paper"):
        try:
            resolved_config.relative_to(legacy_config_root)
        except ValueError:
            continue
        planning_dir_name = legacy_config_root.parent.name
        raise GPDError(
            f"Paper configs under `{planning_dir_name}/paper/` are no longer supported. "
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


_PROJECT_AWARE_EXPLICIT_INPUTS: dict[str, tuple[list[str], Callable[[str | None], bool]]] = {
    "gpd:compare-experiment": (["prediction, dataset path, or phase identifier"], _has_simple_positional_inputs),
    "gpd:compare-results": (["phase, artifact, or comparison target"], _has_simple_positional_inputs),
    "gpd:derive-equation": (["equation or topic to derive"], _has_simple_positional_inputs),
    "gpd:dimensional-analysis": (["phase number or file path"], _has_simple_positional_inputs),
    "gpd:discover": (["phase number or standalone topic"], _has_discover_explicit_inputs),
    "gpd:explain": (["concept, result, method, notation, or paper"], _has_simple_positional_inputs),
    "gpd:limiting-cases": (["phase number or file path"], _has_simple_positional_inputs),
    "gpd:literature-review": (["topic or research question"], _has_simple_positional_inputs),
    "gpd:numerical-convergence": (["phase number or file path"], _has_simple_positional_inputs),
    "gpd:sensitivity-analysis": (["--target quantity", "--params p1,p2,..."], _has_sensitivity_explicit_inputs),
}


def _build_project_aware_guidance(explicit_inputs: list[str], *, init_command: str) -> str:
    """Render the standardized project-aware guidance string."""
    init_guidance = f"initialize a project with `{init_command}` in the runtime surface or `gpd init new-project` in the local CLI"
    if not explicit_inputs:
        return f"Either provide explicit inputs for this command, or {init_guidance}."
    if len(explicit_inputs) == 1:
        requirement_text = explicit_inputs[0]
    elif len(explicit_inputs) == 2:
        requirement_text = f"{explicit_inputs[0]} and {explicit_inputs[1]}"
    else:
        requirement_text = ", ".join(explicit_inputs[:-1]) + f", and {explicit_inputs[-1]}"
    return f"Either provide {requirement_text} explicitly, or {init_guidance}."


def _active_runtime_command_prefix(*, cwd: Path | None = None) -> str | None:
    """Return the public command prefix for the active runtime, if available."""
    from gpd.adapters import get_adapter

    try:
        runtime_name = detect_runtime_for_gpd_use(cwd=cwd or _get_cwd())
        return get_adapter(runtime_name).command_prefix
    except Exception:
        return None


def _validated_runtime_surface(*, cwd: Path | None = None) -> str:
    """Return the machine-readable surface label for the active runtime command prefix."""
    prefix = _active_runtime_command_prefix(cwd=cwd)
    if not prefix:
        return "public_runtime_command_surface"
    if prefix.startswith("/"):
        return "public_runtime_slash_command"
    if prefix.startswith("$"):
        return "public_runtime_dollar_command"
    return "public_runtime_command_surface"


def _active_runtime_command_family(*, cwd: Path | None = None) -> str:
    """Return the runtime-native public command family, if it can be resolved."""
    prefix = _active_runtime_command_prefix(cwd=cwd)
    return f"{prefix}*" if prefix else "the active runtime command surface"


def _active_runtime_new_project_command(*, cwd: Path | None = None) -> str:
    """Return the runtime-native new-project command, if it can be resolved."""
    prefix = _active_runtime_command_prefix(cwd=cwd)
    return f"{prefix}new-project" if prefix else "the active runtime's `new-project` command"


def _runtime_surface_dispatch_note(*, cwd: Path | None = None) -> str:
    """Render the standardized runtime-surface note for preflight payloads."""
    family = _active_runtime_command_family(cwd=cwd)
    if family == "the active runtime command surface":
        surface_text = family
    else:
        surface_text = f"the public `{family}` runtime command surface"
    return (
        f"This preflight validates {surface_text} from the command registry. "
        "It does not guarantee a same-name local `gpd` subcommand exists."
    )


def _unique_preserving_order(values: list[str]) -> list[str]:
    """Return unique strings from *values* without reordering first appearances."""
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _canonical_command_name(command_name: str) -> str:
    """Normalize a CLI command name to the registry's public gpd:name form."""
    return canonical_command_label(command_name)


def _resolve_registry_command(command_name: str) -> tuple[object, str]:
    """Resolve a command name through the registry and preserve its public name."""
    from gpd import registry as content_registry

    command = content_registry.get_command(command_name)
    return command, _canonical_command_name(command_name)


def _build_command_context_preflight(
    command_name: str,
    *,
    arguments: str | None = None,
) -> CommandContextPreflightResult:
    """Evaluate whether a command can run in the current workspace context."""
    from gpd.core.constants import ProjectLayout

    cwd = _get_cwd()
    layout = ProjectLayout(cwd)
    command, public_command_name = _resolve_registry_command(command_name)
    project_exists = layout.project_md.exists()
    dispatch_note = _runtime_surface_dispatch_note(cwd=cwd)
    init_command = _active_runtime_new_project_command(cwd=cwd)

    checks: list[CommandContextCheck] = []

    def add_check(name: str, passed: bool, detail: str, *, blocking: bool = True) -> None:
        checks.append(CommandContextCheck(name=name, passed=passed, detail=detail, blocking=blocking))

    add_check("context_mode", True, f"context_mode={command.context_mode}", blocking=False)

    if command.context_mode == "global":
        add_check("project_context", True, "command runs without project context", blocking=False)
        return CommandContextPreflightResult(
            command=public_command_name,
            context_mode=command.context_mode,
            passed=True,
            project_exists=project_exists,
            explicit_inputs=[],
            guidance="",
            checks=checks,
            validated_surface=_validated_runtime_surface(cwd=cwd),
            dispatch_note=dispatch_note,
        )

    if command.context_mode == "projectless":
        add_check(
            "project_context",
            True,
            (
                "initialized project detected"
                if project_exists
                else "no initialized project required"
            ),
            blocking=False,
        )
        return CommandContextPreflightResult(
            command=public_command_name,
            context_mode=command.context_mode,
            passed=True,
            project_exists=project_exists,
            explicit_inputs=[],
            guidance="",
            checks=checks,
            validated_surface=_validated_runtime_surface(cwd=cwd),
            dispatch_note=dispatch_note,
        )

    if command.context_mode == "project-required":
        add_check(
            "project_exists",
            project_exists,
            (
                f"{_format_display_path(layout.project_md)} present"
                if project_exists
                else f"missing {_format_display_path(layout.project_md)}"
            ),
        )
        guidance = (
            ""
            if project_exists
            else (
                "This command requires an initialized GPD project. "
                f"Use `{init_command}` in the runtime surface or `gpd init new-project` in the local CLI."
            )
        )
        return CommandContextPreflightResult(
            command=public_command_name,
            context_mode=command.context_mode,
            passed=project_exists,
            project_exists=project_exists,
            explicit_inputs=[],
            guidance=guidance,
            checks=checks,
            validated_surface=_validated_runtime_surface(cwd=cwd),
            dispatch_note=dispatch_note,
        )

    explicit_inputs, predicate = _PROJECT_AWARE_EXPLICIT_INPUTS.get(
        command.name,
        ([command.argument_hint.strip()] if command.argument_hint.strip() else ["explicit command inputs"], _has_simple_positional_inputs),
    )
    explicit_inputs_ok = predicate(arguments)
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
        explicit_inputs_ok,
        (
            "explicit standalone inputs detected"
            if explicit_inputs_ok
            else f"missing explicit standalone inputs ({', '.join(explicit_inputs)})"
        ),
        blocking=not project_exists,
    )
    passed = project_exists or explicit_inputs_ok
    guidance = "" if passed else _build_project_aware_guidance(explicit_inputs, init_command=init_command)
    return CommandContextPreflightResult(
        command=public_command_name,
        context_mode=command.context_mode,
        passed=passed,
        project_exists=project_exists,
        explicit_inputs=explicit_inputs,
        guidance=guidance,
        checks=checks,
        validated_surface=_validated_runtime_surface(cwd=cwd),
        dispatch_note=dispatch_note,
    )


def _build_review_preflight(
    command_name: str,
    *,
    subject: str | None = None,
    strict: bool = False,
) -> ReviewPreflightResult:
    """Evaluate lightweight filesystem/state prerequisites for a review command."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.phases import find_phase
    from gpd.core.state import state_validate

    cwd = _get_cwd()
    layout = ProjectLayout(cwd)
    command, public_command_name = _resolve_registry_command(command_name)
    contract = command.review_contract
    if contract is None:
        raise GPDError(f"Command {public_command_name} does not expose a review contract")

    checks: list[ReviewPreflightCheck] = []
    phase_subject = subject
    if phase_subject is None and "phase_artifacts" in contract.preflight_checks:
        phase_subject = _current_review_phase_subject(cwd)
    phase_info = find_phase(cwd, phase_subject) if phase_subject and "phase_artifacts" in contract.preflight_checks else None

    def add_check(name: str, passed: bool, detail: str, *, blocking: bool | None = None) -> None:
        checks.append(
            ReviewPreflightCheck(
                name=name,
                passed=passed,
                detail=detail,
                blocking=_review_preflight_check_is_blocking(contract, name) if blocking is None else blocking,
            )
        )

    context_preflight = _build_command_context_preflight(command_name, arguments=subject)
    context_detail = context_preflight.guidance or f"context_mode={command.context_mode}"
    if context_preflight.dispatch_note:
        context_detail = f"{context_detail}; {context_preflight.dispatch_note}"
    add_check(
        "command_context",
        context_preflight.passed,
        context_detail,
        blocking=True,
    )

    if "project_state" in contract.preflight_checks:
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
            validation = state_validate(cwd, integrity_mode="review")
            detail = f"integrity_status={validation.integrity_status}"
            if validation.issues:
                detail = f"{detail}; {'; '.join(validation.issues)}"
            add_check("state_integrity", validation.valid, detail)

    if "roadmap" in contract.preflight_checks:
        add_check(
            "roadmap",
            layout.roadmap.exists(),
            (
                f"{_format_display_path(layout.roadmap)} present"
                if layout.roadmap.exists()
                else f"missing {_format_display_path(layout.roadmap)}"
            ),
        )

    if "conventions" in contract.preflight_checks:
        add_check(
            "conventions",
            layout.conventions_md.exists(),
            (
                f"{_format_display_path(layout.conventions_md)} present"
                if layout.conventions_md.exists()
                else f"missing {_format_display_path(layout.conventions_md)}"
            ),
        )

    if "research_artifacts" in contract.preflight_checks:
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
            )
        if strict:
            verification_exists = layout.phases_dir.exists() and any(layout.phases_dir.rglob("*VERIFICATION.md"))
            add_check(
                "verification_reports",
                verification_exists,
                "verification reports present" if verification_exists else "no verification reports found",
            )
            if verification_exists:
                verification_failures = _validate_phase_artifacts(layout.phases_dir, "verification")
                add_check(
                    "verification_frontmatter",
                    not verification_failures,
                    "all verification reports satisfy the verification schema"
                    if not verification_failures
                    else "; ".join(verification_failures[:3]),
                )

    if "manuscript" in contract.preflight_checks:
        manuscript, manuscript_detail = (
            _resolve_review_preflight_manuscript(
                cwd,
                subject,
                allow_markdown=command.name != "gpd:arxiv-submission",
            )
            if command.name in {"gpd:peer-review", "gpd:arxiv-submission"}
            else (
                _find_manuscript_main(cwd),
                "",
            )
        )
        if command.name == "gpd:write-paper" and manuscript is None:
            manuscript_passed = True
            manuscript_detail = (
                "no paper/main.tex, manuscript/main.tex, or draft/main.tex found; "
                "fresh bootstrap is allowed and will scaffold ./paper/main.tex"
            )
        else:
            manuscript_passed = manuscript is not None
        add_check(
            "manuscript",
            manuscript_passed,
            manuscript_detail
            if command.name in {"gpd:peer-review", "gpd:arxiv-submission"}
            else (
                manuscript_detail
                if command.name == "gpd:write-paper" and manuscript is None
                else (
                    f"{_format_display_path(manuscript)} present"
                    if manuscript is not None
                    else "no paper/main.tex, manuscript/main.tex, or draft/main.tex found"
                )
            ),
        )
        if subject and command.name == "gpd:respond-to-referees" and subject != "paste":
            report_path = Path(subject)
            if not report_path.is_absolute():
                report_path = cwd / report_path
            add_check(
                "referee_report_source",
                report_path.exists(),
                (
                    f"{_format_display_path(report_path)} present"
                    if report_path.exists()
                    else f"missing {_format_display_path(report_path)}"
                ),
        )
        if strict and manuscript is not None and command.name in {
            "gpd:peer-review",
            "gpd:write-paper",
            "gpd:arxiv-submission",
        }:
            artifact_manifest = _resolve_review_preflight_publication_artifact(
                manuscript,
                "ARTIFACT-MANIFEST.json",
            )
            bibliography_audit = _resolve_review_preflight_publication_artifact(
                manuscript,
                "BIBLIOGRAPHY-AUDIT.json",
            )
            reproducibility_manifest = _resolve_review_preflight_publication_artifact(
                manuscript,
                "reproducibility-manifest.json",
                "REPRODUCIBILITY-MANIFEST.json",
            )
            artifact_manifest_detail = "no ARTIFACT-MANIFEST.json found near the manuscript"
            artifact_manifest_passed = artifact_manifest is not None
            if artifact_manifest is not None:
                artifact_manifest_detail = f"{_format_display_path(artifact_manifest)} present"
                if strict:
                    from gpd.mcp.paper.models import ArtifactManifest

                    try:
                        artifact_manifest_payload = json.loads(artifact_manifest.read_text(encoding="utf-8"))
                        ArtifactManifest.model_validate(artifact_manifest_payload)
                    except OSError as exc:
                        artifact_manifest_passed = False
                        artifact_manifest_detail = f"could not read artifact manifest: {exc}"
                    except json.JSONDecodeError as exc:
                        artifact_manifest_passed = False
                        artifact_manifest_detail = f"could not parse artifact manifest: {exc}"
                    except PydanticValidationError as exc:
                        artifact_manifest_passed = False
                        artifact_manifest_detail = (
                            "artifact manifest is invalid: "
                            + "; ".join(_format_pydantic_schema_error(error, root_label="artifact_manifest") for error in exc.errors()[:3])
                        )
            add_check(
                "artifact_manifest",
                artifact_manifest_passed,
                artifact_manifest_detail,
            )
            add_check(
                "bibliography_audit",
                bibliography_audit is not None,
                (
                    f"{_format_display_path(bibliography_audit)} present"
                    if bibliography_audit is not None
                    else "no BIBLIOGRAPHY-AUDIT.json found near the manuscript"
                ),
            )
            if command.name == "gpd:arxiv-submission":
                compiled_manuscript = manuscript.with_suffix(".pdf")
                add_check(
                    "compiled_manuscript",
                    compiled_manuscript.exists(),
                    (
                        f"{_format_display_path(compiled_manuscript)} present"
                        if compiled_manuscript.exists()
                        else f"missing compiled manuscript {_format_display_path(compiled_manuscript)}"
                    ),
                    blocking=True,
                )
                publication_blockers = _current_publication_blockers(cwd)
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
                latest_review_artifacts = _latest_publication_review_artifacts(layout.gpd / "review")
                if latest_review_artifacts is not None:
                    ledger_path = latest_review_artifacts.review_ledger
                    decision_path = latest_review_artifacts.referee_decision
                    round_label = (
                        f"round {latest_review_artifacts.round_number}"
                        if latest_review_artifacts.round_number > 1
                        else "round 1"
                    )
                    add_check(
                        "review_ledger",
                        ledger_path is not None,
                        (
                            f"{_format_display_path(ledger_path)} present for latest staged review {round_label}"
                            if ledger_path is not None
                            else f"missing REVIEW-LEDGER{latest_review_artifacts.round_suffix}.json for latest staged review {round_label}"
                        ),
                    )
                    add_check(
                        "referee_decision",
                        decision_path is not None,
                        (
                            f"{_format_display_path(decision_path)} present for latest staged review {round_label}"
                            if decision_path is not None
                            else f"missing REFEREE-DECISION{latest_review_artifacts.round_suffix}.json for latest staged review {round_label}"
                        ),
                    )

                    review_ledger = None
                    if ledger_path is not None:
                        from gpd.mcp.paper.review_artifacts import read_review_ledger

                        try:
                            review_ledger = read_review_ledger(ledger_path)
                        except (OSError, json.JSONDecodeError) as exc:
                            add_check("review_ledger_valid", False, f"could not parse review ledger: {exc}")
                        except PydanticValidationError as exc:
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
                            review_ledger_valid = _manuscript_matches_review_artifact_path(
                                review_ledger.manuscript_path,
                                manuscript,
                                cwd=cwd,
                            )
                            add_check(
                                "review_ledger_valid",
                                review_ledger_valid,
                                (
                                    "review ledger manuscript_path matches the active submission manuscript"
                                    if review_ledger_valid
                                    else "review ledger manuscript_path does not match the active submission manuscript"
                                ),
                            )

                    if decision_path is not None:
                        from gpd.core.referee_policy import evaluate_referee_decision
                        from gpd.mcp.paper.models import ReviewRecommendation
                        from gpd.mcp.paper.review_artifacts import read_referee_decision

                        try:
                            decision = read_referee_decision(decision_path)
                        except (OSError, json.JSONDecodeError) as exc:
                            add_check("referee_decision_valid", False, f"could not parse referee decision: {exc}")
                        except PydanticValidationError as exc:
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
                                    project_root=cwd,
                                )
                                decision_reasons.extend(report.reasons)
                            if not _manuscript_matches_review_artifact_path(decision.manuscript_path, manuscript, cwd=cwd):
                                decision_reasons.append(
                                    "referee decision manuscript_path does not match the active submission manuscript"
                                )

                            decision_valid = not decision_reasons
                            add_check(
                                "referee_decision_valid",
                                decision_valid,
                                (
                                    "referee decision is valid for the active submission manuscript"
                                    if decision_valid
                                    else "; ".join(decision_reasons[:3])
                                ),
                            )
                            if decision_valid:
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
                                )
            if command.name in {"gpd:peer-review", "gpd:write-paper"}:
                add_check(
                    "reproducibility_manifest",
                    reproducibility_manifest is not None,
                    (
                        f"{_format_display_path(reproducibility_manifest)} present"
                        if reproducibility_manifest is not None
                        else "no reproducibility manifest found near the manuscript"
                    ),
                )
            if strict and command.name == "gpd:peer-review" and bibliography_audit is not None:
                from gpd.mcp.paper.bibliography import BibliographyAudit

                try:
                    audit_payload = json.loads(bibliography_audit.read_text(encoding="utf-8"))
                    audit = BibliographyAudit.model_validate(audit_payload)
                except (OSError, json.JSONDecodeError) as exc:
                    add_check("bibliography_audit_clean", False, f"could not parse bibliography audit: {exc}")
                except PydanticValidationError as exc:
                    add_check(
                        "bibliography_audit_clean",
                        False,
                        "bibliography audit is invalid: "
                        + "; ".join(_format_pydantic_schema_error(error, root_label="bibliography_audit") for error in exc.errors()[:3]),
                    )
                else:
                    clean = (
                        audit.resolved_sources == audit.total_sources
                        and audit.partial_sources == 0
                        and audit.unverified_sources == 0
                        and audit.failed_sources == 0
                    )
                    add_check(
                        "bibliography_audit_clean",
                        clean,
                        (
                            "all bibliography sources resolved and verified"
                            if clean
                            else "bibliography audit still has unresolved, partial, unverified, or failed sources"
                        ),
                    )
            if (
                strict
                and command.name in {"gpd:peer-review", "gpd:write-paper"}
                and reproducibility_manifest is not None
            ):
                from gpd.core.reproducibility import validate_reproducibility_manifest

                try:
                    repro_payload = json.loads(reproducibility_manifest.read_text(encoding="utf-8"))
                    repro_validation = validate_reproducibility_manifest(repro_payload)
                except Exception as exc:  # pragma: no cover - defensive parsing guard
                    add_check("reproducibility_ready", False, f"could not validate reproducibility manifest: {exc}")
                else:
                    ready = repro_validation.valid and repro_validation.ready_for_review and not repro_validation.warnings
                    detail = (
                        "reproducibility manifest is review-ready"
                        if ready
                        else (
                            f"valid={repro_validation.valid}, ready_for_review={repro_validation.ready_for_review}, "
                            f"warnings={len(repro_validation.warnings)}, issues={len(repro_validation.issues)}"
                        )
                    )
                    add_check("reproducibility_ready", ready, detail)

    if "phase_artifacts" in contract.preflight_checks:
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
                )
        else:
            summary_exists = bool(getattr(phase_info, "summaries", [])) if phase_info is not None else _has_any_phase_summary(layout.phases_dir)
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
            )

    required_state_check = _evaluate_review_required_state(contract, cwd=cwd, subject=subject, phase_info=phase_info)
    if required_state_check is not None:
        add_check("required_state", required_state_check[0], required_state_check[1], blocking=True)

    passed = all(check.passed or not check.blocking for check in checks)
    return ReviewPreflightResult(
        command=public_command_name,
        review_mode=contract.review_mode,
        strict=strict,
        passed=passed,
        checks=checks,
        required_outputs=contract.required_outputs,
        required_evidence=contract.required_evidence,
        blocking_conditions=contract.blocking_conditions,
        validated_surface=context_preflight.validated_surface,
        local_cli_equivalence_guaranteed=context_preflight.local_cli_equivalence_guaranteed,
        dispatch_note=context_preflight.dispatch_note,
    )


@validate_app.command("consistency")
def validate_consistency() -> None:
    """Validate cross-phase consistency."""
    from gpd.core.health import run_health

    report = run_health(_get_cwd())
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
            "context_mode": command.context_mode,
            "review_contract": dataclasses.asdict(command.review_contract),
        }
    )


@validate_app.command("review-preflight")
def validate_review_preflight(
    command_name: str = typer.Argument(..., help="Command registry key or gpd:name"),
    subject: str | None = typer.Argument(None, help="Optional phase number or report path"),
    strict: bool = typer.Option(False, "--strict", help="Enable stricter evidence-oriented checks"),
) -> None:
    """Run lightweight executable preflight checks for review-grade workflows."""
    result = _build_review_preflight(command_name, subject=subject, strict=strict)
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


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
        report = score_paper_quality(build_paper_quality_input(Path(from_project)))
    else:
        if not input_path:
            _error("Provide a PaperQualityInput path or use --from-project <root>")
        payload = _load_json_document(input_path)
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
    """Validate a project-scoping contract before downstream artifact generation."""
    from gpd.core.contract_validation import validate_project_contract

    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"draft", "approved"}:
        raise GPDError(f"Invalid --mode {mode!r}. Expected 'draft' or 'approved'.")

    payload = _load_json_document(input_path)
    project_root = _get_cwd() if input_path == "-" else Path(input_path).expanduser().resolve(strict=False).parent
    result = validate_project_contract(payload, mode=normalized_mode, project_root=project_root)
    _output(result)
    if not result.valid:
        raise typer.Exit(code=1)


@validate_app.command("plan-contract")
def validate_plan_contract_cmd(
    input_path: str = typer.Argument(..., help="Path to a PLAN.md file"),
) -> None:
    """Validate PLAN frontmatter, including the contract block and cross-links."""

    _run_frontmatter_validation(input_path, "plan")


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
    """Validate VERIFICATION frontmatter and contract-result alignment."""

    _run_frontmatter_validation(input_path, "verification")


@validate_app.command("review-claim-index")
def validate_review_claim_index_cmd(
    input_path: str = typer.Argument(..., help="Path to a claim-index JSON file, or '-' for stdin"),
) -> None:
    """Validate a staged peer-review claim index."""
    from gpd.mcp.paper.models import ClaimIndex

    payload = _load_json_document(input_path)
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
    from gpd.core.referee_policy import validate_stage_review_artifact_file
    from gpd.mcp.paper.models import StageReviewReport

    payload = _load_json_document(input_path)
    try:
        stage_report = StageReviewReport.model_validate(payload)
    except PydanticValidationError as exc:
        _raise_pydantic_schema_error(
            label="review-stage-report",
            exc=exc,
            schema_reference="references/publication/peer-review-panel.md",
        )
    if input_path != "-":
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

    payload = _load_json_document(input_path)
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

    payload = _load_json_document(input_path)
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
        ledger_payload = _load_json_document(ledger_path)
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
) -> None:
    """Validate a machine-readable reproducibility manifest."""
    from gpd.core.kernel import print_verdict
    from gpd.core.reproducibility import (
        ReproducibilityManifest,
        build_reproducibility_kernel_verdict,
        validate_reproducibility_manifest,
    )

    payload = _load_json_document(input_path)
    result = validate_reproducibility_manifest(payload)
    if not kernel_verdict:
        _output(result)
    else:
        manifest_obj: ReproducibilityManifest | None = None
        if isinstance(payload, dict):
            try:
                manifest_obj = ReproducibilityManifest.model_validate(payload)
            except PydanticValidationError:
                manifest_obj = None

        verdict = (
            build_reproducibility_kernel_verdict(manifest_obj, validation=result)
            if manifest_obj is not None
            else None
        )

        if _raw:
            _output(
                {
                    "validation": result.model_dump(mode="json"),
                    "kernel_verdict": verdict,
                }
            )
        else:
            _output(result)
            if verdict is not None:
                console.print()
                print_verdict(verdict, domain="Reproducibility")
    if not result.valid or (strict and (not result.ready_for_review or bool(result.warnings))):
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# history-digest — History analysis
# ═══════════════════════════════════════════════════════════════════════════


@app.command("history-digest")
def history_digest() -> None:
    """Build a digest of project history from phase SUMMARY files."""
    from gpd.core.commands import cmd_history_digest

    _output(cmd_history_digest(_get_cwd()))


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

    result = cmd_regression_check(_get_cwd(), phase=phase, quick=quick)
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
) -> None:
    """Build a paper from the canonical mcp.paper JSON config surface."""

    from gpd.core.storage_paths import DurableOutputKind, ProjectStorageLayout
    from gpd.mcp.paper.bibliography import CitationSource
    from gpd.mcp.paper.compiler import build_paper

    config_file = _resolve_existing_input_path(
        config_path,
        candidates=(
            "paper/PAPER-CONFIG.json",
            "paper/paper-config.json",
            "manuscript/PAPER-CONFIG.json",
            "manuscript/paper-config.json",
            "draft/PAPER-CONFIG.json",
            "draft/paper-config.json",
        ),
        label="paper config",
    )
    _reject_legacy_paper_config_location(config_file)
    raw_config = _load_json_document(str(config_file))
    if not isinstance(raw_config, dict):
        raise GPDError(f"Paper config must be a JSON object: {_format_display_path(config_file)}")

    paper_config = _resolve_paper_config_paths(raw_config, base_dir=config_file.parent)
    output_path = Path(output_dir) if output_dir else _default_paper_output_dir(config_file)
    if not output_path.is_absolute():
        output_path = _get_cwd() / output_path
    output_path = output_path.resolve(strict=False)
    storage_layout = ProjectStorageLayout(_get_cwd())
    storage_layout.validate_final_output(output_path)
    storage_check = storage_layout.check_user_output(
        output_path,
        preferred_kinds=(
            DurableOutputKind.PAPER,
            DurableOutputKind.MANUSCRIPT,
            DurableOutputKind.DRAFT,
        ),
    )

    bib_source = _resolve_bibliography_path(
        explicit_path=bibliography,
        config_path=config_file,
        output_dir=output_path,
        bib_stem=paper_config.bib_file.removesuffix(".bib"),
    )
    bib_data = None
    if bib_source is not None:
        from pybtex.database import parse_file
        try:
            bib_data = parse_file(str(bib_source))
        except Exception as exc:  # noqa: BLE001
            raise GPDError(f"Failed to parse bibliography { _format_display_path(bib_source) }: {exc}") from exc

    citation_payload = None
    citation_source_path: Path | None = None
    if citation_sources is not None:
        citation_source_path = _resolve_existing_input_path(citation_sources, candidates=(), label="citation sources")
        raw_sources = _load_json_document(str(citation_source_path))
        if not isinstance(raw_sources, list):
            raise GPDError(f"Citation sources must be a JSON array: {_format_display_path(citation_source_path)}")
        citation_payload = [CitationSource.model_validate(item) for item in raw_sources]

    result = asyncio.run(
        build_paper(
            paper_config,
            output_path,
            bib_data=bib_data,
            citation_sources=citation_payload,
            enrich_bibliography=enrich_bibliography,
        )
    )

    payload = {
        "config_path": _format_display_path(config_file),
        "output_dir": _format_display_path(output_path),
        "tex_path": _format_display_path(output_path / "main.tex"),
        "bibliography_source": _format_display_path(bib_source),
        "citation_sources_path": _format_display_path(citation_source_path),
        "manifest_path": _format_display_path(result.manifest_path),
        "bibliography_audit_path": _format_display_path(result.bibliography_audit_path),
        "pdf_path": _format_display_path(result.pdf_path),
        "success": result.success,
        "error_count": len(result.errors),
        "errors": result.errors,
        "warnings": list(storage_check.warnings),
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
) -> None:
    """Resolve the runtime-specific model override for an agent.

    Prints nothing when no override is configured so callers can omit the
    runtime model parameter and let the platform use its default model.
    """
    from gpd.core.config import resolve_model, validate_agent_name
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
    adapters = {
        runtime: _get_adapter_or_error(runtime, action=f"{action} runtime selection")
        for runtime in runtimes
    }
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
    console.print(_render_install_option_line(1, "Local", "current project only", local_example, label_width=label_width))
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
    table = Table(title="Install Summary", title_style=f"italic {_INSTALL_ACCENT_COLOR}", show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
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
        next_step_entries: list[tuple[str, str, str, str, str]] = []
        seen_runtime_names: set[str] = set()
        for runtime_name, _result in results:
            if runtime_name in seen_runtime_names:
                continue
            seen_runtime_names.add(runtime_name)
            adapter = _get_adapter_or_error(runtime_name, action="install summary")
            next_step_entries.append(
                (
                    adapter.display_name,
                    adapter.launch_command,
                    adapter.help_command,
                    adapter.new_project_command,
                    adapter.map_research_command,
                )
            )

        console.print()
        console.print("[bold]Next steps[/]")
        if len(next_step_entries) == 1:
            single_runtime_name, single_result = results[0]
            display_name, launch_command, help_command, new_project_command, map_research_command = next_step_entries[0]
            resume_work_command = _get_adapter_or_error(single_runtime_name, action="install summary").format_command("resume-work")
            target_value = single_result.get("target")
            doctor_scope = (
                "global"
                if target_value and _target_dir_matches_global(single_runtime_name, str(target_value), action="install summary")
                else "local"
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
                "3. Start with "
                f"[{_INSTALL_ACCENT_COLOR} bold]{new_project_command}[/] for a new project "
                "or "
                f"[{_INSTALL_ACCENT_COLOR} bold]{map_research_command}[/] for existing work, "
                "or "
                f"[{_INSTALL_ACCENT_COLOR} bold]{resume_work_command}[/] to continue paused work.",
                soft_wrap=True,
            )
            console.print()
            console.print(
                "   Fast bootstrap: use "
                f"[{_INSTALL_ACCENT_COLOR} bold]{new_project_command} --minimal[/] "
                "for the shortest onboarding path.",
                soft_wrap=True,
            )
            console.print(
                "4. Use [bold]gpd --help[/] for local install, readiness, validation, permissions, observability, and diagnostics. "
                f"Use [{_INSTALL_ACCENT_COLOR} bold]{help_command}[/] inside {display_name} for workflow help.",
                soft_wrap=True,
            )
            console.print(
                "5. Verify or troubleshoot this machine with "
                f"[bold]gpd doctor --runtime {single_runtime_name} --{doctor_scope}[/].",
                soft_wrap=True,
            )
            console.print(
                "6. After startup, use the runtime `settings` command to review autonomy, workflow defaults, and model-cost posture. "
                "The safest starting point is `review` plus runtime defaults.",
                soft_wrap=True,
            )
            console.print(
                "7. If you plan to use paper/manuscript workflows, rerun "
                f"[bold]gpd doctor --runtime {single_runtime_name} --{doctor_scope}[/] "
                "and check the `Optional Workflow Add-ons` and `LaTeX Toolchain` rows before publication work.",
                soft_wrap=True,
            )
        else:
            for display_name, launch_command, help_command, new_project_command, map_research_command in next_step_entries:
                console.print(
                    f"- {display_name} "
                    f"([{_INSTALL_ACCENT_COLOR} bold]{launch_command}[/]), then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{help_command}[/], then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{new_project_command}[/] "
                    f"or [{_INSTALL_ACCENT_COLOR} bold]{map_research_command}[/]. "
                    f"Quick bootstrap: [{_INSTALL_ACCENT_COLOR} bold]{new_project_command} --minimal[/]",
                    soft_wrap=True,
                )
            console.print(
                "\nUse [bold]gpd --help[/] for local install, readiness, validation, permissions, observability, and diagnostics.",
                soft_wrap=True,
            )
            console.print(
                "Run [bold]gpd doctor --runtime <runtime> --local|--global[/] for a focused readiness check.",
                soft_wrap=True,
            )
            console.print(
                "After startup, use the runtime `settings` command to review autonomy, workflow defaults, and model-cost posture. "
                "The safest starting point is `review` plus runtime defaults.",
                soft_wrap=True,
            )
            console.print(
                "For paper/manuscript workflows, rerun "
                "[bold]gpd doctor --runtime <runtime> --local|--global[/] "
                "and check the `Optional Workflow Add-ons` and `LaTeX Toolchain` rows before publication work.",
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


def _doctor_check_messages(check: object, field_names: tuple[str, ...]) -> list[str]:
    """Collect normalized issue/warning text from one doctor check payload."""
    messages: list[str] = []
    for field_name in field_names:
        field_value = getattr(check, field_name, None)
        if not isinstance(field_value, list):
            continue
        for item in field_value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized:
                messages.append(normalized)
    return messages


def _doctor_blocker_messages(report: object) -> list[str]:
    """Extract blocking readiness messages from a doctor report."""
    from gpd.core.health import extract_doctor_blockers

    seen: set[str] = set()
    blockers: list[str] = []
    for check in extract_doctor_blockers(report):
        messages = _doctor_check_messages(check, ("issues", "warnings"))
        if not messages:
            label = str(getattr(check, "label", "") or "").strip() or "Readiness Check"
            messages = [f"{label}: readiness check failed."]
        for message in messages:
            if message not in seen:
                seen.add(message)
                blockers.append(message)
    return blockers


def _doctor_advisory_messages(report: object) -> list[str]:
    """Extract advisory readiness messages from a doctor report."""
    summary = getattr(report, "summary", None)
    if getattr(summary, "warn", 0) <= 0:
        return []

    seen: set[str] = set()
    advisories: list[str] = []
    for check in getattr(report, "checks", []):
        if getattr(check, "status", None) != "warn":
            continue
        for message in _doctor_check_messages(check, ("issues", "warnings")):
            if message not in seen:
                seen.add(message)
                advisories.append(message)
    return advisories


def _runtime_doctor_hint(runtime_name: str, *, install_scope: str, target_dir: Path | None) -> str:
    """Build the exact doctor command that inspects one install target."""
    parts = ["gpd", "doctor", "--runtime", runtime_name, f"--{install_scope}"]
    if target_dir is not None:
        parts.extend(["--target-dir", str(target_dir)])
    return " ".join(shlex.quote(part) for part in parts)


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
        if getattr(report, "overall", None) == CheckStatus.FAIL and not blocker_messages:
            blocker_messages = ["Runtime readiness reported a failure without blocking details."]

        if blocker_messages:
            failures.append((runtime_name, blocker_messages))
            continue

        advisory_messages = _doctor_advisory_messages(report)
        if advisory_messages:
            advisories[runtime_name] = advisory_messages

    return failures, advisories


@app.command("install")
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
) -> None:
    """Install GPD skills, agents, and hooks into runtime config directories.

    Run without arguments for interactive mode. Specify runtime name(s) or --all for batch mode.

    Examples::

        gpd install                        # interactive
        gpd install <runtime>              # single runtime, local
        gpd install <runtime-a> <runtime-b>
        gpd install --all --global         # all runtimes, global
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    if global_install and local_install:
        _error("Cannot specify both --global and --local")
        return  # unreachable
    _validate_all_runtime_selection("install", runtimes, install_all)

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
        from gpd.version import resolve_active_version

        if not _raw:
            console.print(_GPD_BANNER, style=f"bold {_INSTALL_LOGO_COLOR}")
            console.print()
            header_line, attribution_line = _format_install_header_lines(resolve_active_version(_get_cwd()))
            console.print(header_line, style=f"bold {_INSTALL_TITLE_COLOR}", markup=False, highlight=False)
            console.print(attribution_line, style=f"dim {_INSTALL_META_COLOR}", markup=False, highlight=False)
            console.print()
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
                f"`{_runtime_doctor_hint(runtime_name, install_scope=install_scope, target_dir=resolved_target_override)}`"
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
        target = _resolve_cli_target_dir(target_dir) if target_dir else adapter.resolve_target_dir(is_global, _get_cwd())
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


def entrypoint() -> int | None:
    """Console-script and ``python -m`` entrypoint with checkout preference."""
    _maybe_reexec_from_checkout()
    return app(args=_normalize_global_cli_options(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(entrypoint())
