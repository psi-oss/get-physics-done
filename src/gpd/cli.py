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

from gpd.core.constants import ENV_GPD_DISABLE_CHECKOUT_REEXEC
from gpd.core.errors import ConfigError, GPDError

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
    """Partition root-global CLI options from the rest of the argv stream.

    This keeps ``--raw`` and ``--cwd`` usable even when agents append them after
    the subcommand, while still respecting the ``--`` end-of-options marker.
    """
    global_args: list[str] = []
    remaining_args: list[str] = []
    passthrough = False
    index = 0

    while index < len(argv):
        arg = str(argv[index])
        if passthrough:
            remaining_args.append(arg)
            index += 1
            continue

        if arg == "--":
            passthrough = True
            remaining_args.append(arg)
            index += 1
            continue

        if arg == "--raw":
            global_args.append(arg)
            index += 1
            continue

        if arg == "--cwd":
            global_args.append(arg)
            if index + 1 < len(argv):
                global_args.append(str(argv[index + 1]))
                index += 2
            else:
                index += 1
            continue

        if arg.startswith("--cwd="):
            global_args.append(arg)
            index += 1
            continue

        remaining_args.append(arg)
        index += 1

    return global_args, remaining_args


def _normalize_global_cli_options(argv: list[str]) -> list[str]:
    """Move root-global options to the front of the argv stream."""
    global_args, remaining_args = _split_global_cli_options(argv)
    return [*global_args, *remaining_args]


def _resolve_cli_cwd_from_argv(argv: list[str]) -> Path:
    """Resolve the effective CLI cwd from raw argv before Typer parses it."""
    raw_cwd = "."
    global_args, _ = _split_global_cli_options(argv)
    for index, arg in enumerate(global_args):
        if arg == "--cwd" and index + 1 < len(global_args):
            raw_cwd = global_args[index + 1]
            break
        if arg.startswith("--cwd="):
            raw_cwd = arg.split("=", 1)[1]
            break

    candidate = Path(raw_cwd).expanduser()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    return (Path.cwd() / candidate).resolve(strict=False)


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


def _format_runtime_list(runtime_names: list[str]) -> str:
    """Render runtime identifiers as human-friendly names."""
    from gpd.adapters import get_adapter

    display_names = [get_adapter(runtime_name).display_name for runtime_name in runtime_names]
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
    help="GPD — Get Physics Done: unified physics research CLI",
    no_args_is_help=True,
    add_completion=True,
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

    validation = validate_project_contract(contract_data, mode="approved")
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
def doctor() -> None:
    """Check GPD installation and environment health."""
    from gpd.core.health import run_doctor
    from gpd.specs import SPECS_DIR

    _output(run_doctor(specs_dir=SPECS_DIR))


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

observe_app = typer.Typer(help="Inspect local observability sessions and events")
app.add_typer(observe_app, name="observe")


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


@init_app.command("execute-phase")
def init_execute_phase(
    phase: str | None = typer.Argument(None, help="Phase number"),
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
) -> None:
    """Assemble context for executing a phase."""
    from gpd.core.context import init_execute_phase

    includes = set(include.split(",")) if include else set()
    _output(init_execute_phase(_get_cwd(), phase, includes=includes))


@init_app.command("plan-phase")
def init_plan_phase(
    phase: str | None = typer.Argument(None, help="Phase number"),
    include: str | None = typer.Option(None, "--include", help="Additional context includes"),
) -> None:
    """Assemble context for planning a phase."""
    from gpd.core.context import init_plan_phase

    includes = set(include.split(",")) if include else set()
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

    includes = set(include.split(",")) if include else set()
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

    includes = set(include.split(",")) if include else set()
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
    """Set a configuration value."""
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
    _output({"key": key, "canonical_key": canonical_key, "value": effective_value, "updated": True})


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


def _resolve_review_preflight_manuscript(cwd: Path, subject: str | None) -> tuple[Path | None, str]:
    """Resolve a review-preflight manuscript target from an explicit subject or defaults."""
    if subject:
        target = Path(subject)
        if not target.is_absolute():
            target = cwd / target

        if not target.exists():
            return None, f"missing explicit manuscript target {_format_display_path(target)}"

        if target.is_file():
            if target.suffix in {".tex", ".md"}:
                return target, f"{_format_display_path(target)} present"
            return None, f"explicit manuscript target must be a .tex or .md file: {_format_display_path(target)}"

        if target.is_dir():
            candidate = _first_existing_path(target / "main.tex", target / "main.md")
            if candidate is None:
                direct_files = sorted(
                    path for path in target.iterdir() if path.is_file() and path.suffix in {".tex", ".md"}
                )
                if direct_files:
                    candidate = direct_files[0]
            if candidate is not None:
                return candidate, f"{_format_display_path(target)} resolved to {_format_display_path(candidate)}"
            return None, f"no manuscript entry point found under {_format_display_path(target)}"

    manuscript = _find_manuscript_main(cwd)
    if manuscript is not None:
        return manuscript, f"{_format_display_path(manuscript)} present"
    return None, "no paper/main.tex, manuscript/main.tex, or draft/main.tex found"


_REVIEW_PRECHECK_BLOCKING_CONDITIONS: dict[str, tuple[str, ...]] = {
    "project_state": ("missing project state",),
    "state_integrity": ("degraded review integrity",),
    "roadmap": ("missing roadmap",),
    "conventions": ("missing conventions",),
    "research_artifacts": ("no research artifacts",),
    "summary_frontmatter": ("degraded review integrity",),
    "verification_frontmatter": ("degraded review integrity",),
    "manuscript": ("missing manuscript",),
    "phase_lookup": ("missing phase artifacts",),
    "phase_summaries": ("missing phase artifacts",),
}

_REVIEW_PRECHECK_REQUIRED_EVIDENCE: dict[str, tuple[str, ...]] = {
    "research_artifacts": ("phase summaries or milestone digest",),
    "verification_reports": ("verification reports",),
    "artifact_manifest": ("artifact manifest",),
    "bibliography_audit": ("bibliography audit",),
    "bibliography_audit_clean": ("bibliography audit",),
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
    from gpd.core.storage_paths import ProjectStorageLayout

    legacy_config_root = ProjectStorageLayout(_get_cwd()).internal_root / "paper"
    resolved_config = config_file.resolve(strict=False)
    try:
        resolved_config.relative_to(legacy_config_root)
    except ValueError:
        return
    raise GPDError(
        "Paper configs under `.gpd/paper/` are no longer supported. "
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


def _build_project_aware_guidance(explicit_inputs: list[str]) -> str:
    """Render the standardized project-aware guidance string."""
    if not explicit_inputs:
        return "Either provide explicit inputs for this command, or run `gpd init new-project`."
    if len(explicit_inputs) == 1:
        requirement_text = explicit_inputs[0]
    elif len(explicit_inputs) == 2:
        requirement_text = f"{explicit_inputs[0]} and {explicit_inputs[1]}"
    else:
        requirement_text = ", ".join(explicit_inputs[:-1]) + f", and {explicit_inputs[-1]}"
    return f"Either provide {requirement_text} explicitly, or run `gpd init new-project`."


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
    normalized = command_name.strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    return normalized if normalized.startswith("gpd:") else f"gpd:{normalized}"


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
            else "This command requires an initialized GPD project. Run `gpd init new-project`."
        )
        return CommandContextPreflightResult(
            command=public_command_name,
            context_mode=command.context_mode,
            passed=project_exists,
            project_exists=project_exists,
            explicit_inputs=[],
            guidance=guidance,
            checks=checks,
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
    guidance = "" if passed else _build_project_aware_guidance(explicit_inputs)
    return CommandContextPreflightResult(
        command=public_command_name,
        context_mode=command.context_mode,
        passed=passed,
        project_exists=project_exists,
        explicit_inputs=explicit_inputs,
        guidance=guidance,
        checks=checks,
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
    add_check(
        "command_context",
        context_preflight.passed,
        context_preflight.guidance or f"context_mode={command.context_mode}",
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
            _resolve_review_preflight_manuscript(cwd, subject)
            if command.name in {"gpd:peer-review", "gpd:arxiv-submission"}
            else (
                _find_manuscript_main(cwd),
                "",
            )
        )
        add_check(
            "manuscript",
            manuscript is not None,
            manuscript_detail
            if command.name in {"gpd:peer-review", "gpd:arxiv-submission"}
            else (
                f"{_format_display_path(manuscript)} present"
                if manuscript is not None
                else "no paper/main.tex, manuscript/main.tex, or draft/main.tex found"
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
                blocking=True,
            )
        if strict and manuscript is not None:
            artifact_manifest = _first_existing_path(
                manuscript.parent / "ARTIFACT-MANIFEST.json",
                cwd / ".gpd" / "paper" / "ARTIFACT-MANIFEST.json",
            )
            bibliography_audit = _first_existing_path(
                manuscript.parent / "BIBLIOGRAPHY-AUDIT.json",
                cwd / ".gpd" / "paper" / "BIBLIOGRAPHY-AUDIT.json",
            )
            reproducibility_manifest = _first_existing_path(
                manuscript.parent / "reproducibility-manifest.json",
                manuscript.parent / "REPRODUCIBILITY-MANIFEST.json",
                cwd / ".gpd" / "paper" / "reproducibility-manifest.json",
            )
            add_check(
                "artifact_manifest",
                artifact_manifest is not None,
                (
                    f"{_format_display_path(artifact_manifest)} present"
                    if artifact_manifest is not None
                    else "no ARTIFACT-MANIFEST.json found near the manuscript"
                ),
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
                try:
                    audit_payload = json.loads(bibliography_audit.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    add_check("bibliography_audit_clean", False, f"could not parse bibliography audit: {exc}")
                else:
                    clean = (
                        int(audit_payload.get("resolved_sources", 0)) == int(audit_payload.get("total_sources", 0))
                        and int(audit_payload.get("partial_sources", 0)) == 0
                        and int(audit_payload.get("unverified_sources", 0)) == 0
                        and int(audit_payload.get("failed_sources", 0)) == 0
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
    result = validate_project_contract(payload, mode=normalized_mode)
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
        help="Require staged peer-review artifact coverage in addition to recommendation-floor consistency",
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
        review_ledger=review_ledger,
        project_root=_get_cwd(),
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
    """Generate root-facing checkpoint notes from phase summaries."""
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
    quick: bool = typer.Option(False, "--quick", help="Only check most recent 2 completed phases"),
) -> None:
    """Check for regressions across completed phases."""
    from gpd.core.commands import cmd_regression_check

    result = cmd_regression_check(_get_cwd(), quick=quick)
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
    from gpd.hooks.runtime_detect import detect_runtime_for_gpd_use

    supported_runtimes = _supported_runtime_names()
    if runtime is not None and supported_runtimes and runtime not in supported_runtimes:
        supported = ", ".join(supported_runtimes)
        _error(f"Unknown runtime {runtime!r}. Supported: {supported}")

    active_runtime = runtime or detect_runtime_for_gpd_use(cwd=_get_cwd())
    try:
        validate_agent_name(agent_name)
        _output(resolve_model(_get_cwd(), agent_name, runtime=active_runtime))
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

    If --files is not specified, stages all .gpd/ changes.
    Skips cleanly when commit_docs is disabled for the project.

    Examples::

        gpd commit "docs: update roadmap" --files .gpd/ROADMAP.md
        gpd commit "docs: initialize research project" --files .gpd/PROJECT.md .gpd/state.json
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

        gpd pre-commit-check --files .gpd/ROADMAP.md .gpd/STATE.md
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

    from gpd.adapters import get_adapter, list_runtimes

    runtimes = list_runtimes()
    adapters = {runtime: get_adapter(runtime) for runtime in runtimes}
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


def _location_example(runtimes: list[str], *, is_global: bool) -> str:
    """Return a representative install location example for the selected runtime set."""
    if len(runtimes) != 1:
        return "one config dir per runtime"

    from gpd.adapters import get_adapter

    adapter = get_adapter(runtimes[0])
    target = adapter.resolve_target_dir(is_global, _get_cwd())
    return _format_display_path(target)


def _prompt_location(runtimes: list[str], *, action: str = "install") -> bool:
    """Interactive location selection. Returns True for global, False for local."""
    from rich.prompt import Prompt

    label = "Install" if action == "install" else "Uninstall"
    local_example = _location_example(runtimes, is_global=False)
    global_example = _location_example(runtimes, is_global=True)
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
    from gpd.adapters import get_adapter
    from gpd.version import resolve_install_gpd_root

    adapter = get_adapter(runtime_name)
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
    from gpd.adapters import get_adapter

    console.print()
    table = Table(title="Install Summary", title_style=f"italic {_INSTALL_ACCENT_COLOR}", show_header=True, header_style=f"bold {_INSTALL_ACCENT_COLOR}")
    table.add_column("Runtime", style="bold")
    table.add_column("Target")
    table.add_column("Status")

    for runtime_name, result in results:
        adapter = get_adapter(runtime_name)
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
            adapter = get_adapter(runtime_name)
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
            display_name, launch_command, help_command, new_project_command, map_research_command = next_step_entries[0]
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
                f"[{_INSTALL_ACCENT_COLOR} bold]{map_research_command}[/] for existing work.",
                soft_wrap=True,
            )
        else:
            for display_name, launch_command, help_command, new_project_command, map_research_command in next_step_entries:
                console.print(
                    f"- {display_name} "
                    f"([{_INSTALL_ACCENT_COLOR} bold]{launch_command}[/]), then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{help_command}[/], then "
                    f"[{_INSTALL_ACCENT_COLOR} bold]{new_project_command}[/] "
                    f"or [{_INSTALL_ACCENT_COLOR} bold]{map_research_command}[/]",
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
        return resolved
    return _get_cwd() / resolved


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

    from gpd.adapters import get_adapter, list_runtimes

    if global_install and local_install:
        _error("Cannot specify both --global and --local")
        return  # unreachable
    _validate_all_runtime_selection("install", runtimes, install_all)

    # Resolve which runtimes to install
    selected: list[str]
    if install_all:
        selected = list_runtimes()
    elif runtimes:
        # Validate all runtime names
        supported = list_runtimes()
        for rt in runtimes:
            if rt not in supported:
                _error(f"Unknown runtime {rt!r}. Supported: {', '.join(supported)}")
                return  # unreachable
        selected = _unique_preserving_order(list(runtimes))
    else:
        # Interactive mode
        from gpd.version import resolve_active_version

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
        is_global = False  # --target-dir implies a specific path
    elif global_install:
        is_global = True
    elif local_install:
        is_global = False
    elif not runtimes and not install_all:
        # Interactive mode — ask for location
        is_global = _prompt_location(selected)
    else:
        # Non-interactive default: local
        is_global = False

    location_label = "global" if is_global else "local"
    if not _raw:
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
            adapter = get_adapter(rt)
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

    from gpd.adapters import get_adapter, list_runtimes

    if global_uninstall and local_uninstall:
        _error("Cannot specify both --global and --local")
        return
    _validate_all_runtime_selection("uninstall", runtimes, uninstall_all)

    # Resolve runtimes
    selected: list[str]
    if uninstall_all:
        selected = list_runtimes()
    elif runtimes:
        supported = list_runtimes()
        for rt in runtimes:
            if rt not in supported:
                _error(f"Unknown runtime {rt!r}. Supported: {', '.join(supported)}")
                return
        selected = _unique_preserving_order(list(runtimes))
    else:
        selected = _prompt_runtimes(action="uninstall")

    _validate_target_dir_runtime_selection("uninstall", selected, target_dir)

    # Resolve location (skip prompts when --target-dir is explicit)
    if target_dir:
        is_global = True  # irrelevant when target_dir is set
    elif not global_uninstall and not local_uninstall:
        is_global = _prompt_location(selected, action="uninstall")
    else:
        is_global = global_uninstall

    if not target_dir:
        location_label = "global" if is_global else "local"
        runtime_names = _format_runtime_list(selected)
        if not Confirm.ask(f"Remove GPD from {runtime_names} ({location_label})?", default=False):
            console.print("[dim]Cancelled.[/]")
            raise typer.Exit()

    removed_results: list[tuple[str, dict[str, object]]] = []
    for rt in selected:
        adapter = get_adapter(rt)
        target = _resolve_cli_target_dir(target_dir) if target_dir else adapter.resolve_target_dir(is_global, _get_cwd())
        if not target.is_dir():
            if not _raw:
                console.print(f"  [yellow]⊘[/] {adapter.display_name} — not installed at {_format_display_path(target)}")
            continue
        result = adapter.uninstall(target)
        removed_items = result.get("removed", [])
        if not _raw:
            if removed_items:
                console.print(
                    f"  [green]✓[/] {adapter.display_name} — removed: {', '.join(str(r) for r in removed_items)}"
                )
            else:
                console.print(f"  [dim]⊘[/] {adapter.display_name} — nothing to remove")
        removed_results.append((rt, result))

    if _raw:
        _output({"uninstalled": [{"runtime": rt, **res} for rt, res in removed_results]})


def entrypoint() -> int | None:
    """Console-script and ``python -m`` entrypoint with checkout preference."""
    _maybe_reexec_from_checkout()
    return app(args=_normalize_global_cli_options(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(entrypoint())
