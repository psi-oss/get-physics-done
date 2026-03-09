"""MCP server for GPD project state management.

Thin MCP wrapper around gpd.core.state, gpd.core.config, and
gpd.core.health. Exposes state queries, phase info, progress, and
health validation as MCP tools for solver agents.

Usage:
    python -m gpd.mcp.servers.state_server
    # or via entry point:
    gpd-mcp-state
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from gpd.core.config import load_config
from gpd.core.health import run_health
from gpd.core.observability import gpd_span
from gpd.core.state import (
    state_advance_plan,
    state_get,
    state_update_progress,
    state_validate,
)

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-state")

mcp = FastMCP("gpd-state")


@mcp.tool()
def get_state(project_dir: str) -> dict:
    """Get the current project state.

    Returns the full state object including position, convention lock,
    decisions, blockers, and session info.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = Path(project_dir)
    with gpd_span("mcp.state.get", phase=""):
        result = state_get(cwd)
        return result.model_dump()


@mcp.tool()
def get_phase_info(project_dir: str, phase: str) -> dict:
    """Get detailed information about a specific phase.

    Args:
        project_dir: Absolute path to the project root directory.
        phase: Phase number (e.g., "01", "02.1").
    """
    from gpd.core.phases import find_phase

    cwd = Path(project_dir)
    with gpd_span("mcp.state.phase_info", phase=phase):
        info = find_phase(cwd, phase)
        if info is None:
            return {"error": f"Phase {phase} not found"}
        plan_count = len(info.plans)
        summary_count = len(info.summaries)
        return {
            "phase_number": info.phase_number,
            "phase_name": info.phase_name,
            "directory": info.directory,
            "phase_slug": info.phase_slug,
            "plan_count": plan_count,
            "summary_count": summary_count,
            "complete": plan_count > 0 and summary_count >= plan_count,
        }


@mcp.tool()
def advance_plan(project_dir: str) -> dict:
    """Advance the project state to the next plan.

    Updates the current plan counter and related state fields.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = Path(project_dir)
    with gpd_span("mcp.state.advance_plan"):
        return state_advance_plan(cwd).model_dump()


@mcp.tool()
def get_progress(project_dir: str) -> dict:
    """Get overall project progress summary.

    Updates progress_percent based on completed phases and returns
    the current state.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = Path(project_dir)
    with gpd_span("mcp.state.progress"):
        return state_update_progress(cwd).model_dump()


@mcp.tool()
def validate_state(project_dir: str) -> dict:
    """Run comprehensive state validation checks.

    Validates state.json against STATE.md, checks schema completeness,
    convention lock, phase format, and more. Returns issues and warnings.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = Path(project_dir)
    with gpd_span("mcp.state.validate"):
        result = state_validate(cwd)
        return result.model_dump()


@mcp.tool()
def run_health_check(project_dir: str, fix: bool = False) -> dict:
    """Run the full 11-check health dashboard.

    Checks environment, project structure, state validity, compaction,
    roadmap consistency, orphans, conventions, frontmatter, return
    envelopes, config, and git status.

    Args:
        project_dir: Absolute path to the project root directory.
        fix: If True, attempt auto-fixes for common issues.
    """
    cwd = Path(project_dir)
    with gpd_span("mcp.state.health", fix=str(fix)):
        report = run_health(cwd, fix=fix)
        return report.model_dump()


@mcp.tool()
def get_config(project_dir: str) -> dict:
    """Get the project GPD configuration.

    Returns the resolved config including model profile, autonomy mode,
    research mode, workflow toggles, and branching strategy.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = Path(project_dir)
    with gpd_span("mcp.state.config"):
        config = load_config(cwd)
        return config.model_dump()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-state MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD State MCP Server")


if __name__ == "__main__":
    main()
