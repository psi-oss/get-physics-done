"""MCP server for GPD project state management.

Thin MCP wrapper around gpd.core.state, gpd.core.config, and
gpd.core.health. Exposes state queries, phase info, progress, and
health validation as MCP tools for solver agents.

Usage:
    python -m gpd.mcp.servers.state_server
    # or via entry point:
    gpd-mcp-state
"""

from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import WithJsonSchema

from gpd.core.commands import cmd_apply_return_updates
from gpd.core.config import load_config
from gpd.core.errors import GPDError
from gpd.core.health import run_health
from gpd.core.observability import gpd_span
from gpd.core.phases import progress_render
from gpd.core.root_resolution import resolve_project_root
from gpd.core.state import (
    _project_contract_runtime_payload_for_state,
    peek_state_json,
    state_advance_plan,
    state_validate,
)
from gpd.core.utils import is_phase_complete, matching_phase_artifact_count
from gpd.mcp.servers import (
    ABSOLUTE_PROJECT_DIR_SCHEMA,
    configure_mcp_logging,
    resolve_absolute_project_dir,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)

logger = configure_mcp_logging("gpd-state")

mcp = FastMCP("gpd-state")

AbsoluteProjectDirInput = Annotated[str, WithJsonSchema(ABSOLUTE_PROJECT_DIR_SCHEMA)]


def load_state_json(cwd: Path) -> dict | None:
    """Return visible project state for MCP consumers.

    Keep a module-local loader so tool behavior and test patch points stay
    stable even when the underlying state read path evolves.
    """

    project_root = resolve_project_root(cwd, require_layout=True) or cwd.expanduser().resolve(strict=False)

    state_obj, _issues, state_source = peek_state_json(
        project_root,
        recover_intent=False,
        surface_blocked_project_contract=True,
        acquire_lock=False,
    )
    if state_obj is None:
        return None

    project_contract_load_info, project_contract_validation, project_contract_gate = _project_contract_runtime_payload_for_state(
        project_root,
        state_obj=state_obj,
        state_source=state_source,
    )
    merged_state = dict(state_obj)
    merged_state.pop("session", None)
    merged_state["project_contract_load_info"] = project_contract_load_info
    merged_state["project_contract_validation"] = project_contract_validation
    merged_state["project_contract_gate"] = project_contract_gate
    return merged_state


def apply_return_updates(project_dir: AbsoluteProjectDirInput, file_path: str | Path) -> dict:
    """Apply a validated child-return envelope through the canonical state adapter.

    This keeps the canonical apply-return path available from the state server
    module without changing the published MCP tool surface in this lane.
    """

    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.apply_return_updates"):
        try:
            resolved = cwd / Path(file_path)
            return stable_mcp_response(cmd_apply_return_updates(cwd, resolved).model_dump())
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def get_state(project_dir: AbsoluteProjectDirInput) -> dict:
    """Get the current project state.

    Returns the structured project state from `state.json`.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.get", phase=""):
        try:
            state_obj = load_state_json(cwd)
            if state_obj is None:
                return stable_mcp_error(
                    "No project state found. Run 'gpd init new-project' to initialize a GPD project state."
                )
            return stable_mcp_response(state_obj)
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def get_phase_info(project_dir: AbsoluteProjectDirInput, phase: str) -> dict:
    """Get detailed information about a specific phase.

    Args:
        project_dir: Absolute path to the project root directory.
        phase: Phase number (e.g., "01", "02.1").
    """
    from gpd.core.phases import find_phase

    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.phase_info", phase=phase):
        try:
            info = find_phase(cwd, phase)
            if info is None:
                return stable_mcp_error(f"Phase {phase} not found")
            plan_count = len(info.plans)
            summary_count = matching_phase_artifact_count(info.plans, info.summaries)
            return stable_mcp_response(
                {
                    "phase_number": info.phase_number,
                    "phase_name": info.phase_name,
                    "directory": info.directory,
                    "phase_slug": info.phase_slug,
                    "plan_count": plan_count,
                    "summary_count": summary_count,
                    "complete": is_phase_complete(plan_count, summary_count),
                }
            )
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def advance_plan(project_dir: AbsoluteProjectDirInput) -> dict:
    """Advance the project state to the next plan.

    Updates the current plan counter and related state fields.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.advance_plan"):
        try:
            return stable_mcp_response(state_advance_plan(cwd).model_dump())
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def get_progress(project_dir: AbsoluteProjectDirInput) -> dict:
    """Get overall project progress summary.

    Returns the computed progress summary without surfacing checkpoint shelf
    artifacts. Works even when STATE.md is missing.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.progress"):
        try:
            return stable_mcp_response(progress_render(cwd, "json").model_dump())
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def validate_state(project_dir: AbsoluteProjectDirInput) -> dict:
    """Run comprehensive state validation checks.

    Validates state.json against STATE.md, checks schema completeness,
    convention lock, phase format, and more. Returns issues and warnings.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.validate"):
        try:
            result = state_validate(cwd)
            return stable_mcp_response(result.model_dump())
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def run_health_check(project_dir: AbsoluteProjectDirInput, fix: bool = False) -> dict:
    """Run the full project health dashboard.

    Checks environment, project structure, storage-path policy, state validity,
    compaction, roadmap consistency, orphans, conventions, frontmatter,
    return envelopes, config, checkpoint tags, and git status.

    Args:
        project_dir: Absolute path to the project root directory.
        fix: If True, attempt auto-fixes for common issues.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.health", fix=str(fix)):
        try:
            report = run_health(cwd, fix=fix)
            return stable_mcp_response(report.model_dump())
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def get_config(project_dir: AbsoluteProjectDirInput) -> dict:
    """Get the project GPD configuration.

    Returns the resolved config including model profile, autonomy mode,
    research mode, workflow toggles, and branching strategy.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.state.config"):
        try:
            config = load_config(cwd)
            return stable_mcp_response(config.model_dump())
        except (GPDError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-state MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD State MCP Server")


tighten_registered_tool_contracts(mcp)


if __name__ == "__main__":
    main()
