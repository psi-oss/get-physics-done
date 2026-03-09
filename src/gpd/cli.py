"""Unified GPD CLI — entry point for core workflow, sessions, and MCP tooling.

Delegates to ``gpd.core.*`` modules for all command implementations.

Usage::

    gpd state load
    gpd phase list
    gpd health --fix
    gpd init execute-phase 42

All commands support ``--raw`` for JSON output and ``--cwd`` for working directory override.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.table import Table

import gpd
from gpd.core.errors import GPDError
from gpd.mcp.cli import session_app
from gpd.mcp.pipeline import app as pipeline_app
from gpd.mcp.viewer.cli import viewer_app

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
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Key")
    table.add_column("Value")
    for k, v in d.items():
        val = json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v)
        table.add_row(str(k), val)
    console.print(table)


def _error(msg: str) -> NoReturn:
    """Print error and exit — JSON when --raw, rich text otherwise."""
    if _raw:
        console.print_json(json.dumps({"error": str(msg)}))
    else:
        console.print(f"[bold red]Error:[/] {msg}", highlight=False)
    raise typer.Exit(code=1)


def _get_cwd() -> Path:
    return _cwd.resolve()


# ─── App setup ──────────────────────────────────────────────────────────────

class _GPDTyper(typer.Typer):
    """Typer subclass that catches GPDError and prints a user-friendly message."""

    def __call__(self, *args: object, **kwargs: object) -> object:
        try:
            return super().__call__(*args, **kwargs)
        except GPDError as exc:
            if _raw:
                console.print_json(json.dumps({"error": str(exc)}))
            else:
                console.print(f"[bold red]Error:[/] {exc}", highlight=False)
            raise SystemExit(1) from None


app = _GPDTyper(
    name="gpd",
    help="GPD — Get Physics Done: unified physics research CLI",
    no_args_is_help=True,
    add_completion=True,
)

app.add_typer(session_app, name="session", help="Interactive research session with MCP orchestration")
app.add_typer(pipeline_app, name="pipeline", help="MCP-backed research pipeline stages")
app.add_typer(viewer_app, name="view", help="Frame viewer for MCP simulation outputs")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"gpd {gpd.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON for programmatic consumption"),
    cwd: str = typer.Option(".", "--cwd", help="Working directory (default: current)"),
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version", callback=_version_callback, is_eager=True
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
        patch_dict[patches[i].lstrip("-")] = patches[i + 1]
    _output(state_patch(_get_cwd(), patch_dict))


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
    except FileNotFoundError:
        return ConventionLock()
    except json.JSONDecodeError as e:
        _error(f"Malformed state.json: {e}")

    lock_data = raw.get("convention_lock", {})
    if not isinstance(lock_data, dict):
        return ConventionLock()
    return ConventionLock(**lock_data)


def _save_lock(lock: object) -> None:
    """Save ConventionLock back to state.json and regenerate STATE.md."""
    import json

    from gpd.core.constants import ProjectLayout
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = _get_cwd()
    state_path = ProjectLayout(cwd).state_json
    with file_lock(state_path):
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        raw["convention_lock"] = lock.model_dump(exclude_none=True)  # type: ignore[union-attr]
        save_state_json_locked(cwd, raw)


@convention_app.command("set")
def convention_set(
    key: str = typer.Argument(..., help="Convention key"),
    value: str = typer.Argument(..., help="Convention value"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing convention"),
) -> None:
    """Set a convention in the convention lock."""
    from gpd.core.conventions import convention_set

    lock = _load_lock()
    result = convention_set(lock, key, value, force=force)
    if result.updated:
        _save_lock(lock)
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
    from gpd.core.results import result_add

    deps = depends_on.split(",") if depends_on else []
    state = _load_state_dict()
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
    _save_state_dict(state)
    _output(res)


def _load_state_dict() -> dict:
    """Load state.json as a plain dict for commands that need raw state."""
    import json

    from gpd.core.constants import ProjectLayout

    state_path = ProjectLayout(_get_cwd()).state_json
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        _error(f"Malformed state.json: {e}")


def _save_state_dict(state: dict) -> None:
    """Save a state dict back to state.json and regenerate STATE.md."""
    from gpd.core.state import save_state_json

    save_state_json(_get_cwd(), state)


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
    from gpd.core.results import result_verify

    state = _load_state_dict()
    res = result_verify(state, result_id)
    _save_state_dict(state)
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
    from gpd.core.results import result_update

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
    state = _load_state_dict()
    _fields, updated = result_update(state, result_id, **opts)
    _save_state_dict(state)
    _output(updated)


# ═══════════════════════════════════════════════════════════════════════════
# verify — Verification suite
# ═══════════════════════════════════════════════════════════════════════════

verify_app = typer.Typer(help="Verification checks on plans, summaries, and artifacts")
app.add_typer(verify_app, name="verify")


@verify_app.command("summary")
def verify_summary(
    path: str = typer.Argument(..., help="Path to SUMMARY.md"),
    check_count: int = typer.Option(2, "--check-count", help="Number of verification checks"),
) -> None:
    """Verify a SUMMARY.md file."""
    from gpd.core.frontmatter import verify_summary

    _output(verify_summary(_get_cwd(), Path(path), check_file_count=check_count))


@verify_app.command("plan")
def verify_plan(
    path: str = typer.Argument(..., help="Path to plan file"),
) -> None:
    """Verify plan file structure."""
    from gpd.core.frontmatter import verify_plan_structure

    _output(verify_plan_structure(_get_cwd(), Path(path)))


@verify_app.command("phase")
def verify_phase(
    phase: str = typer.Argument(..., help="Phase number"),
) -> None:
    """Verify phase completeness (all plans have summaries, etc.)."""
    from gpd.core.frontmatter import verify_phase_completeness

    _output(verify_phase_completeness(_get_cwd(), phase))


@verify_app.command("references")
def verify_references(
    path: str = typer.Argument(..., help="Path to file"),
) -> None:
    """Verify all internal references resolve."""
    from gpd.core.frontmatter import verify_references

    _output(verify_references(_get_cwd(), Path(path)))


@verify_app.command("commits")
def verify_commits(
    hashes: list[str] = typer.Argument(..., help="Commit hashes to verify"),
) -> None:
    """Verify that commit hashes exist in git history."""
    from gpd.core.frontmatter import verify_commits

    _output(verify_commits(_get_cwd(), hashes))


@verify_app.command("artifacts")
def verify_artifacts(
    plan_path: str = typer.Argument(..., help="Path to plan file"),
) -> None:
    """Verify all artifacts referenced in a plan exist."""
    from gpd.core.frontmatter import verify_artifacts

    _output(verify_artifacts(_get_cwd(), Path(plan_path)))


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
    fm_content = file_path.read_text(encoding="utf-8")
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
    fm_content = file_path.read_text(encoding="utf-8")
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

    merge_data = json.loads(data)
    file_path = _get_cwd() / file
    fm_content = file_path.read_text(encoding="utf-8")
    updated = deep_merge_frontmatter(fm_content, merge_data)
    file_path.write_text(updated, encoding="utf-8")
    _output({"merged": True, "file": file})


@frontmatter_app.command("validate")
def frontmatter_validate(
    file: str = typer.Argument(..., help="Markdown file path"),
    schema: str = typer.Option(..., "--schema", help="Schema name to validate against"),
) -> None:
    """Validate frontmatter against a schema."""
    from gpd.core.frontmatter import validate_frontmatter

    file_path = _get_cwd() / file
    fm_content = file_path.read_text(encoding="utf-8")
    _output(validate_frontmatter(fm_content, schema))


# ═══════════════════════════════════════════════════════════════════════════
# health — Project health checks
# ═══════════════════════════════════════════════════════════════════════════


@app.command("health")
def health(
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues where possible"),
) -> None:
    """Run 11-check project health diagnostic."""
    from gpd.core.health import run_health

    _output(run_health(_get_cwd(), fix=fix))


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

    Uses the same resolution order as gpd.core.patterns._patterns_root:
    GPD_PATTERNS_ROOT env > GPD_DATA_DIR env > cwd/learned-patterns.
    """
    from gpd.core.patterns import _patterns_root

    return _patterns_root(specs_root=_get_cwd())


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


@init_app.command("map-theory")
def init_map_theory() -> None:
    """Assemble context for theory mapping."""
    from gpd.core.context import init_map_theory

    _output(init_map_theory(_get_cwd()))


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
    from gpd.core.extras import approximation_add

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
    state = _load_state_dict()
    res = approximation_add(state, name=name or "", **kwargs)
    _save_state_dict(state)
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
    from gpd.core.extras import uncertainty_add

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
    state = _load_state_dict()
    res = uncertainty_add(state, quantity=quantity or "", **kwargs)
    _save_state_dict(state)
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
    from gpd.core.extras import question_add

    state = _load_state_dict()
    res = question_add(state, " ".join(text))
    _save_state_dict(state)
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
    from gpd.core.extras import question_resolve

    state = _load_state_dict()
    res = question_resolve(state, " ".join(text))
    _save_state_dict(state)
    _output(res)


calculation_app = typer.Typer(help="Calculation tracking")
app.add_typer(calculation_app, name="calculation")


@calculation_app.command("add")
def calculation_add(
    text: list[str] = typer.Argument(..., help="Calculation description"),
) -> None:
    """Add a calculation to track."""
    from gpd.core.extras import calculation_add

    state = _load_state_dict()
    res = calculation_add(state, " ".join(text))
    _save_state_dict(state)
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
    from gpd.core.extras import calculation_complete

    state = _load_state_dict()
    res = calculation_complete(state, " ".join(text))
    _save_state_dict(state)
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
    from gpd.core.constants import ProjectLayout

    config_path = ProjectLayout(_get_cwd()).config_json
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        _output({"key": key, "found": False})
        return
    parts = key.split(".")
    current: object = raw
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            _output({"key": key, "found": False})
            return
    _output({"key": key, "value": current, "found": True})


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key path (dot-separated)"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value."""
    from gpd.core.constants import ProjectLayout
    from gpd.core.utils import atomic_write, file_lock

    config_path = ProjectLayout(_get_cwd()).config_json
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(config_path):
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        parts = key.split(".")
        current = raw
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            parsed = value
        current[parts[-1]] = parsed
        atomic_write(config_path, json.dumps(raw, indent=2) + "\n")
    _output({"key": key, "value": value, "updated": True})


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
        "model_profile": defaults.model_profile.value,
        "commit_docs": defaults.commit_docs,
        "search_gitignored": defaults.search_gitignored,
        "branching_strategy": defaults.branching_strategy.value,
    }
    atomic_write(config_path, json.dumps(config_dict, indent=2) + "\n")
    _output({"created": True, "path": str(config_path)})


# ═══════════════════════════════════════════════════════════════════════════
# validate — Consistency validation
# ═══════════════════════════════════════════════════════════════════════════

validate_app = typer.Typer(help="Validation checks")
app.add_typer(validate_app, name="validate")


@validate_app.command("consistency")
def validate_consistency() -> None:
    """Validate cross-phase consistency."""
    from gpd.core.health import run_health

    report = run_health(_get_cwd())
    _output(report)
    if report.overall == "fail":
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# template — Template selection and filling
# ═══════════════════════════════════════════════════════════════════════════

template_app = typer.Typer(help="Plan and document templates")
app.add_typer(template_app, name="template")


@template_app.command("select")
def template_select(
    plan_path: str = typer.Argument(..., help="Path to plan file"),
) -> None:
    """Select appropriate template for a plan."""
    from gpd.core.frontmatter import select_template

    _output(select_template(_get_cwd(), Path(plan_path)))


@template_app.command("fill")
def template_fill(
    template_type: str = typer.Argument(..., help="Template type"),
    phase: str = typer.Option(..., "--phase", help="Phase number"),
    plan: str | None = typer.Option(None, "--plan", help="Plan name"),
    name: str | None = typer.Option(None, "--name", help="Document name"),
    plan_type: str = typer.Option("execute", "--type", help="Plan type (execute/research)"),
    wave: str = typer.Option("1", "--wave", help="Wave number"),
    fields: str | None = typer.Option(None, "--fields", help="JSON fields"),
) -> None:
    """Fill a template with provided fields."""
    from gpd.core.frontmatter import TemplateFillOptions, fill_template

    parsed_fields = {}
    if fields:
        try:
            parsed_fields = json.loads(fields)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"--fields must be valid JSON: {exc}") from exc
    try:
        wave_int = int(wave)
    except ValueError:
        raise typer.BadParameter(f"--wave must be an integer, got {wave!r}") from None
    options = TemplateFillOptions(
        phase=phase,
        name=name,
        plan=plan,
        plan_type=plan_type,
        wave=wave_int,
        fields=parsed_fields or None,
    )
    _output(fill_template(_get_cwd(), template_type, options))


# ═══════════════════════════════════════════════════════════════════════════
# dependency-graph — Visual dependency graph
# ═══════════════════════════════════════════════════════════════════════════


@app.command("dependency-graph")
def dependency_graph(
    fmt: str | None = typer.Option(None, "--format", help="Output format (mermaid, dot, json)"),
    phase: str | None = typer.Option(None, "--phase", help="Filter to phase"),
    validate: bool = typer.Option(False, "--validate", help="Validate graph integrity"),
) -> None:
    """Generate a dependency graph across phases."""
    raise typer.BadParameter("dependency-graph is not yet implemented")


# ═══════════════════════════════════════════════════════════════════════════
# scaffold — File and directory scaffolding
# ═══════════════════════════════════════════════════════════════════════════


@app.command("scaffold")
def scaffold(
    scaffold_type: str = typer.Argument(..., help="Type: context, validation, verification, phase-dir"),
    phase: str | None = typer.Option(None, "--phase", help="Phase number"),
    name: str | None = typer.Option(None, "--name", help="Name for the scaffold"),
) -> None:
    """Create scaffold files (context, validation, verification) or phase directories."""
    from gpd.core.commands import cmd_scaffold

    _output(cmd_scaffold(_get_cwd(), scaffold_type, phase=phase, name=name))


# ═══════════════════════════════════════════════════════════════════════════
# history-digest — History analysis
# ═══════════════════════════════════════════════════════════════════════════


@app.command("history-digest")
def history_digest() -> None:
    """Build a digest of project history from phase SUMMARY files."""
    from gpd.core.commands import cmd_history_digest

    _output(cmd_history_digest(_get_cwd()))


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
# todo-complete — Move todo from pending to done
# ═══════════════════════════════════════════════════════════════════════════


@app.command("todo-complete")
def todo_complete(
    filename: str = typer.Argument(..., help="Todo filename in .planning/todos/pending/"),
) -> None:
    """Mark a todo as completed (move from pending/ to done/)."""
    from gpd.core.commands import cmd_todo_complete

    _output(cmd_todo_complete(_get_cwd(), filename))


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
# resolve-model — Resolve model identifier for an agent
# ═══════════════════════════════════════════════════════════════════════════


@app.command("resolve-model")
def resolve_model_cmd(
    agent_name: str = typer.Argument(..., help="Agent name (e.g. gpd-executor)"),
) -> None:
    """Resolve the model identifier for an agent in the current project."""
    from gpd.core.config import resolve_model

    _output(resolve_model(_get_cwd(), agent_name))


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
    import sys

    from gpd.core.json_utils import json_get

    stdin_text = sys.stdin.read()
    try:
        result = json_get(stdin_text, key, default=default)
    except ValueError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    console.print(result, highlight=False)


@json_app.command("keys")
def json_keys_cmd(
    key: str = typer.Argument(..., help="Dot-path to object (e.g. .waves)"),
) -> None:
    """List top-level keys of the object at the given path from stdin JSON."""
    import sys

    from gpd.core.json_utils import json_keys

    stdin_text = sys.stdin.read()
    result = json_keys(stdin_text, key)
    if result:
        console.print(result, highlight=False)


@json_app.command("list")
def json_list_cmd(
    key: str = typer.Argument(..., help="Dot-path to array or object"),
) -> None:
    """List items from the array at the given path from stdin JSON."""
    import sys

    from gpd.core.json_utils import json_list

    stdin_text = sys.stdin.read()
    result = json_list(stdin_text, key)
    if result:
        console.print(result, highlight=False)


@json_app.command("pluck")
def json_pluck_cmd(
    key: str = typer.Argument(..., help="Dot-path to array of objects"),
    field: str = typer.Argument(..., help="Field name to extract from each object"),
) -> None:
    """Extract a field from each object in the array at the given path."""
    import sys

    from gpd.core.json_utils import json_pluck

    stdin_text = sys.stdin.read()
    result = json_pluck(stdin_text, key, field)
    if result:
        console.print(result, highlight=False)


@json_app.command("set")
def json_set_cmd(
    file: str = typer.Option(..., "--file", help="Path to JSON file"),
    path: str = typer.Option(..., "--path", help="Dot-path key to set"),
    value: str = typer.Option(..., "--value", help="Value to set"),
) -> None:
    """Set a key in a JSON file (creates file if needed)."""
    from gpd.core.json_utils import json_set

    _output(json_set(file, path, value))


@json_app.command("merge-files")
def json_merge_files_cmd(
    files: list[str] = typer.Argument(..., help="JSON files to merge"),
    out: str = typer.Option(..., "--out", help="Output file path"),
) -> None:
    """Merge multiple JSON files into one (shallow dict merge)."""
    from gpd.core.json_utils import json_merge_files

    _output(json_merge_files(out, files))


@json_app.command("sum-lengths")
def json_sum_lengths_cmd(
    keys: list[str] = typer.Argument(..., help="Dot-path keys to arrays"),
) -> None:
    """Sum the lengths of arrays at the given paths from stdin JSON."""
    import sys

    from gpd.core.json_utils import json_sum_lengths

    stdin_text = sys.stdin.read()
    result = json_sum_lengths(stdin_text, keys)
    console.print(result, highlight=False)


# ═══════════════════════════════════════════════════════════════════════════
# commit — Git commit for planning files
# ═══════════════════════════════════════════════════════════════════════════


@app.command("commit")
def commit(
    message: str = typer.Argument(..., help="Commit message"),
    files: list[str] | None = typer.Option(None, "--files", help="Files to stage and commit"),
) -> None:
    """Stage planning files and create a git commit.

    If --files is not specified, stages all .planning/ changes.

    Examples::

        gpd commit "docs: update roadmap" --files .planning/ROADMAP.md
        gpd commit "wip: phase 3 progress"
    """
    from gpd.core.git_ops import cmd_commit

    result = cmd_commit(_get_cwd(), message, files=files)
    _output(result)
    if not result.committed:
        raise typer.Exit(code=1)


@app.command("pre-commit-check")
def pre_commit_check(
    files: list[str] | None = typer.Option(None, "--files", help="Files to validate"),
) -> None:
    """Run pre-commit validation on planning files.

    Checks frontmatter YAML validity and detects NaN/Inf values.

    Examples::

        gpd pre-commit-check --files .planning/ROADMAP.md .planning/STATE.md
    """
    from gpd.core.git_ops import cmd_pre_commit_check

    result = cmd_pre_commit_check(_get_cwd(), files or [])
    _output(result)
    if not result.passed:
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════
# version
# ═══════════════════════════════════════════════════════════════════════════


@app.command("version")
def version_cmd() -> None:
    """Show GPD version."""
    console.print(f"gpd {gpd.__version__}")


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


def _prompt_runtimes() -> list[str]:
    """Interactive runtime selection. Returns list of selected runtime names."""
    from rich.prompt import Prompt

    from gpd.adapters import get_adapter, list_runtimes

    runtimes = list_runtimes()
    console.print("\n[bold cyan]Select runtime(s) to install:[/]\n")
    for i, rt in enumerate(runtimes, 1):
        adapter = get_adapter(rt)
        console.print(f"  [bold]{i}[/]) {adapter.display_name} [dim]({rt})[/]")
    console.print(f"  [bold]{len(runtimes) + 1}[/]) [green]All runtimes[/]")

    choice = Prompt.ask(
        "\n[bold]Enter choice[/]",
        default="1",
    )

    try:
        idx = int(choice)
    except ValueError:
        # Try matching by name
        matched = [r for r in runtimes if choice.lower() in r.lower()]
        if matched:
            return matched
        _error(f"Invalid selection: {choice!r}")
        return []  # unreachable

    if idx == len(runtimes) + 1:
        return runtimes
    if 1 <= idx <= len(runtimes):
        return [runtimes[idx - 1]]

    _error(f"Invalid selection: {idx}")
    return []  # unreachable


def _prompt_location() -> bool:
    """Interactive location selection. Returns True for global, False for local."""
    from rich.prompt import Prompt

    console.print("\n[bold cyan]Install location:[/]\n")
    console.print("  [bold]1[/]) [green]Local[/]  — current project only [dim](./.<runtime>/)[/]")
    console.print("  [bold]2[/]) Global — all projects [dim](~/.<runtime>/)[/]")

    choice = Prompt.ask("\n[bold]Enter choice[/]", default="1")
    return choice.strip() == "2"


def _install_single_runtime(
    runtime_name: str,
    *,
    is_global: bool,
    target_dir_override: str | None = None,
) -> dict[str, object]:
    """Install GPD for a single runtime. Returns install result dict."""
    from gpd.adapters import get_adapter

    adapter = get_adapter(runtime_name)
    gpd_root = Path(__file__).parent

    if target_dir_override:
        dest = Path(target_dir_override)
    else:
        dest = adapter.resolve_target_dir(is_global, _get_cwd())

    return adapter.install(gpd_root, dest, is_global=is_global)


def _print_install_summary(results: list[tuple[str, dict[str, object]]]) -> None:
    """Print a rich summary table of install results."""
    from gpd.adapters import get_adapter

    console.print()
    table = Table(title="Install Summary", show_header=True, header_style="bold cyan")
    table.add_column("Runtime", style="bold")
    table.add_column("Target")
    table.add_column("Status")

    for runtime_name, result in results:
        adapter = get_adapter(runtime_name)
        target = str(result.get("target", ""))
        agents = result.get("agents", 0)
        commands = result.get("commands", 0)
        table.add_row(
            adapter.display_name,
            target,
            f"[green]✓[/] {agents} agents, {commands} commands",
        )

    console.print(table)

    # Post-install help hint
    if results:
        first_runtime = results[0][0]
        adapter = get_adapter(first_runtime)
        console.print(f"\n[dim]Run [bold]{adapter.help_command}[/bold] to see available commands.[/]")


@app.command("install")
def install(
    runtimes: list[str] | None = typer.Argument(
        None,
        help="Runtime(s) to install (claude-code, codex, gemini, opencode). Omit for interactive selection.",
    ),
    install_all: bool = typer.Option(False, "--all", help="Install for all supported runtimes"),
    global_install: bool = typer.Option(False, "--global", help="Install globally (~/.runtime/)"),
    local_install: bool = typer.Option(False, "--local", help="Install locally (./. runtime/)"),
    target_dir: str | None = typer.Option(None, "--target-dir", help="Override target config directory"),
    force_statusline: bool = typer.Option(False, "--force-statusline", help="Overwrite existing statusline config"),
) -> None:
    """Install GPD skills, agents, and hooks into runtime config directories.

    Run without arguments for interactive mode. Specify runtime name(s) or --all for batch mode.

    Examples::

        gpd install                        # interactive
        gpd install claude-code            # single runtime, local
        gpd install claude-code codex      # multiple runtimes
        gpd install --all --global         # all runtimes, global
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from gpd.adapters import get_adapter, list_runtimes

    if global_install and local_install:
        _error("Cannot specify both --global and --local")
        return  # unreachable

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
        selected = list(runtimes)
    else:
        # Interactive mode
        console.print(_GPD_BANNER, style="bold blue")
        console.print(f"[bold]GPD v{gpd.__version__}[/] — Get Physics Done\n")
        selected = _prompt_runtimes()

    # Resolve location
    if target_dir:
        is_global = False  # --target-dir implies a specific path
    elif global_install:
        is_global = True
    elif local_install:
        is_global = False
    elif not runtimes and not install_all:
        # Interactive mode — ask for location
        is_global = _prompt_location()
    else:
        # Non-interactive default: local
        is_global = False

    location_label = "global" if is_global else "local"
    if not _raw:
        console.print(f"\n[bold]Installing GPD ({location_label}) for: {', '.join(selected)}[/]\n")

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
                results.append((rt, result))
                progress.update(task, description=f"[green]✓[/] {adapter.display_name}")

                # Handle finish_install for adapters that support it (e.g. statusline setup)
                if hasattr(adapter, "finish_install") and "settingsPath" in result and "settings" in result:
                    should_install_statusline = True
                    adapter.finish_install(
                        result["settingsPath"],
                        result["settings"],
                        result.get("statuslineCommand", ""),
                        should_install_statusline,
                        force_statusline=force_statusline,
                    )
            except NotImplementedError:
                progress.update(task, description=f"[yellow]⊘[/] {adapter.display_name} [dim](not yet implemented)[/]")
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
    global_uninstall: bool = typer.Option(False, "--global", help="Uninstall from global config"),
    local_uninstall: bool = typer.Option(False, "--local", help="Uninstall from local config"),
    target_dir: str | None = typer.Option(None, "--target-dir", help="Override target directory (testing)"),
) -> None:
    """Remove GPD skills, agents, and hooks from runtime config directories.

    Examples::

        gpd uninstall claude-code --local
        gpd uninstall --all --global
    """
    from rich.prompt import Confirm

    from gpd.adapters import get_adapter, list_runtimes

    if global_uninstall and local_uninstall:
        _error("Cannot specify both --global and --local")
        return

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
        selected = list(runtimes)
    else:
        selected = _prompt_runtimes()

    # Resolve location (skip prompts when --target-dir is explicit)
    if target_dir:
        is_global = True  # irrelevant when target_dir is set
    elif not global_uninstall and not local_uninstall:
        is_global = _prompt_location()
    else:
        is_global = global_uninstall

    if not target_dir:
        location_label = "global" if is_global else "local"
        runtime_names = ", ".join(selected)
        if not Confirm.ask(f"Remove GPD from {runtime_names} ({location_label})?", default=False):
            console.print("[dim]Cancelled.[/]")
            raise typer.Exit()

    removed_results: list[tuple[str, dict[str, object]]] = []
    for rt in selected:
        adapter = get_adapter(rt)
        target = Path(target_dir) if target_dir else adapter.resolve_target_dir(is_global, _get_cwd())
        if not target.is_dir():
            if not _raw:
                console.print(f"  [yellow]⊘[/] {adapter.display_name} — not installed at {target}")
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


if __name__ == "__main__":
    app()
