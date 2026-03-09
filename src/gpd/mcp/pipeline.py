"""Pipeline CLI subcommands for GPD+ research orchestration.

Each subcommand wraps an existing module, runs it, and outputs structured JSON
to stdout. The hosting runtime invokes these via Bash tool calls. The system prompt
drives the AI agent through the pipeline step by step.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from pydantic import BaseModel

app = typer.Typer(name="pipeline", help="GPD+ research pipeline stages")


class DiscoveredTool(BaseModel):
    """Typed contract for enriched tool data flowing from discover to plan stage.

    Prevents regression of the FIX-01 field name mismatch (name vs mcp).
    Pydantic validation at construction time catches any field name issues.
    """

    name: str
    reason: str
    priority: int
    description: str = ""
    overview: str = ""
    domains: list[str] = []
    status: str = "unknown"
    operations: list[str] = []


def _json_out(data: dict) -> None:
    """Write JSON to stdout and exit cleanly."""
    json.dump(data, sys.stdout, indent=2, default=str)
    print()  # noqa: T201


def _json_err(error: str) -> None:
    """Write error JSON to stdout and exit with code 1."""
    json.dump({"error": error}, sys.stdout, indent=2)
    print()  # noqa: T201
    raise typer.Exit(code=1)


@app.command()
def discover(
    query: str = typer.Argument(..., help="Physics research question"),
) -> None:
    """Discover and select MCP tools for a research question.

    Runs ToolCatalog + PhysicsRouter + ToolSelectionAgent.
    Outputs JSON with selected tools, categories, reasoning, and confidence.
    """
    try:
        from gpd.mcp.discovery.catalog import ToolCatalog
        from gpd.mcp.discovery.router import PhysicsRouter
        from gpd.mcp.discovery.selector import ToolSelectionAgent
        from gpd.mcp.discovery.sources import load_sources_config

        config = load_sources_config()
        catalog = ToolCatalog(config)
        selector = ToolSelectionAgent()
        router = PhysicsRouter(catalog, selector=selector)

        selection = asyncio.run(router.route_and_select(query))

        # Look up full ToolEntry metadata for each selected tool so the
        # planner knows what each MCP can actually do (operations, domains, etc.)
        all_tools = catalog.get_all_tools()

        enriched_tools = []
        for t in selection.tools:
            entry = all_tools.get(t.mcp)
            tool = DiscoveredTool(
                name=t.mcp,
                reason=t.reason,
                priority=t.priority,
                description=entry.description if entry else "",
                overview=entry.overview if entry else "",
                domains=entry.domains if entry else [],
                status=entry.status.value if entry else "unknown",
                operations=[
                    f"{op.get('name', '')}: {op.get('desc', '')}" for op in (entry.tools[:10] if entry else [])
                ],
            )
            enriched_tools.append(tool.model_dump())

        # Full catalog display: ALL tools with metadata for sortable table
        full_catalog = catalog.get_full_catalog_display()

        # Start background refresh for non-blocking status updates
        catalog.background_refresh()

        _json_out(
            {
                "tools": enriched_tools,
                "reasoning": selection.reasoning,
                "physics_categories": selection.physics_categories,
                "confidence": selection.confidence,
                "tool_count": len(selection.tools),
                "full_catalog": full_catalog,
                "catalog_size": len(full_catalog),
            }
        )
    except Exception as exc:
        _json_err(f"Discovery failed: {exc}")


@app.command()
def plan(
    query: str = typer.Option(..., "--query", "-q", help="Research question"),
    tools_file: Path = typer.Option(..., "--tools-file", "-t", help="JSON file with selected tools"),
    work_dir: Path = typer.Option(..., "--work-dir", "-w", help="Session work directory"),
) -> None:
    """Generate a research milestone DAG from a query and selected tools.

    Runs ResearchPlanner.generate_plan().
    Outputs JSON with the full plan including milestones, costs, and approval gates.
    """
    try:
        tools_data = json.loads(tools_file.read_text(encoding="utf-8"))
        available_tools = tools_data if isinstance(tools_data, list) else tools_data.get("tools", [])

        from gpd.mcp.research.cost_estimator import format_three_level_cost_display
        from gpd.mcp.research.planner import ResearchPlanner

        # Build tool_metadata_registry from CostProfile (populated during discovery, Plan 02-01)
        tool_metadata_registry: dict[str, dict[str, object]] = {}
        for tool in available_tools:
            tool_name = tool.get("name", "")
            if not tool_name:
                continue
            # Read cost profile fields if present (populated by catalog enrichment)
            cp = tool.get("cost_profile", {}) if isinstance(tool.get("cost_profile"), dict) else {}
            tool_metadata_registry[tool_name] = {
                "gpu_type": tool.get("gpu_type", cp.get("gpu_type", "CPU")),
                "estimated_seconds": tool.get("est_seconds", cp.get("estimated_seconds", 30.0)),
                "domains": tool.get("domains", []),
            }

        planner = ResearchPlanner()
        plan_result = asyncio.run(
            planner.generate_plan(
                query=query,
                available_tools=available_tools,
                tool_metadata_registry=tool_metadata_registry,
            )
        )

        # Save plan to work dir for later stages
        work_dir.mkdir(parents=True, exist_ok=True)
        plan_path = work_dir / "plan.json"
        plan_path.write_text(plan_result.model_dump_json(indent=2), encoding="utf-8")

        _json_out(
            {
                "plan_id": plan_result.plan_id,
                "query": plan_result.query,
                "reasoning": plan_result.reasoning,
                "milestone_count": len(plan_result.milestones),
                "milestones": [
                    {
                        "id": m.milestone_id,
                        "description": m.description,
                        "depends_on": m.depends_on,
                        "tools": m.tools,
                        "is_critical": m.is_critical,
                        "approval_gate": m.approval_gate.value,
                        "cost_range": list(m.cost_estimate.estimated_cost_range),
                    }
                    for m in plan_result.milestones
                ],
                "execution_order": plan_result.get_execution_order(),
                "total_cost_range": list(plan_result.total_cost_estimate.estimated_cost_range),
                "cost_breakdown": format_three_level_cost_display(plan_result),
                "plan_file": str(plan_path),
            }
        )
    except Exception as exc:
        _json_err(f"Planning failed: {exc}")


@app.command()
def execute(
    plan_file: Path = typer.Option(..., "--plan-file", "-p", help="Path to plan.json"),
    milestone: str = typer.Option(..., "--milestone", "-m", help="Milestone ID to execute"),
    work_dir: Path = typer.Option(..., "--work-dir", "-w", help="Session work directory"),
) -> None:
    """Execute a single milestone from a research plan.

    Runs execute_milestone_with_recovery() for the specified milestone.
    Outputs JSON with the result including tool outputs and error info.
    """
    try:
        from gpd.mcp.research.error_recovery import execute_milestone_with_recovery
        from gpd.mcp.research.schemas import MilestoneResult, ResearchPlan

        plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
        research_plan = ResearchPlan.model_validate(plan_data)

        # Find the target milestone
        milestone_map = {m.milestone_id: m for m in research_plan.milestones}
        target = milestone_map.get(milestone)
        if target is None:
            _json_err(f"Milestone '{milestone}' not found in plan. Available: {list(milestone_map.keys())}")
            return

        # Load prior results from work dir
        results_dir = work_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        prior_results: dict[str, MilestoneResult] = {}
        for result_file in results_dir.glob("*.json"):
            result_data = json.loads(result_file.read_text(encoding="utf-8"))
            mr = MilestoneResult.model_validate(result_data)
            prior_results[mr.milestone_id] = mr

        # Execute with recovery
        result = asyncio.run(
            execute_milestone_with_recovery(
                milestone=target,
                prior_results=prior_results,
                tool_router=None,  # No custom tool routing; uses MCP tools directly
            )
        )

        # Save result
        result_path = results_dir / f"{milestone}.json"
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        _json_out(
            {
                "milestone_id": result.milestone_id,
                "is_error": result.is_error,
                "error_message": result.error_message,
                "result_summary": result.result_summary,
                "citations": result.citations,
                "attempt_count": result.attempt_count,
                "elapsed_seconds": result.elapsed_seconds,
                "tool_outputs": result.tool_outputs,
                "result_file": str(result_path),
            }
        )
    except Exception as exc:
        _json_err(f"Execution failed: {exc}")


@app.command()
def paper(
    work_dir: Path = typer.Option(..., "--work-dir", "-w", help="Session work directory"),
    title: str = typer.Option(..., "--title", help="Paper title"),
    abstract: str = typer.Option("", "--abstract", help="Paper abstract"),
    journal: str = typer.Option("prl", "--journal", "-j", help="Target journal (prl, nature, mnras, apj, jfm)"),
) -> None:
    """Generate LaTeX paper from research results.

    Runs PaperGenerator with all milestone results from work_dir/results/.
    Outputs JSON with paths to generated LaTeX files.
    """
    try:
        from gpd.mcp.paper.generator import generate_paper
        from gpd.mcp.paper.models import Author
        from gpd.mcp.research.schemas import MilestoneResult

        # Load all results
        results_dir = work_dir / "results"
        results: list[MilestoneResult] = []
        if results_dir.exists():
            for result_file in sorted(results_dir.glob("*.json")):
                data = json.loads(result_file.read_text(encoding="utf-8"))
                results.append(MilestoneResult.model_validate(data))

        # Build research summary from results
        summaries = [r.result_summary for r in results if r.result_summary and not r.is_error]
        research_summary = "\n\n".join(summaries) if summaries else "No results available."

        # Generate paper
        config = asyncio.run(
            generate_paper(
                research_summary=research_summary,
                title=title,
                authors=[Author(name="GPD+ Research Agent", affiliation="Automated")],
                abstract=abstract,
                figures=[],
                citations=[],
                journal=journal,
            )
        )

        # Write to work dir
        paper_dir = work_dir / "paper"
        paper_dir.mkdir(parents=True, exist_ok=True)

        from gpd.mcp.paper.template_registry import render_paper

        tex_content = render_paper(config)
        tex_path = paper_dir / "paper.tex"
        tex_path.write_text(tex_content, encoding="utf-8")

        _json_out(
            {
                "tex_path": str(tex_path),
                "paper_dir": str(paper_dir),
                "section_count": len(config.sections),
                "sections": [s.title for s in config.sections],
                "journal": journal,
            }
        )
    except Exception as exc:
        _json_err(f"Paper generation failed: {exc}")


@app.command("compile")
def compile_cmd(
    paper_dir: Path = typer.Option(..., "--paper-dir", help="Directory containing paper.tex"),
) -> None:
    """Compile LaTeX paper to PDF.

    Runs latexmk (or manual multi-pass) on paper.tex.
    Outputs JSON with the PDF path or compilation errors.
    """
    try:
        from gpd.mcp.paper.compiler import compile_paper

        tex_path = paper_dir / "paper.tex"
        if not tex_path.exists():
            _json_err(f"paper.tex not found in {paper_dir}")
            return

        result = asyncio.run(compile_paper(tex_path, paper_dir))

        _json_out(
            {
                "success": result.success,
                "pdf_path": str(result.pdf_path) if result.pdf_path else None,
                "error": result.error,
            }
        )
    except Exception as exc:
        _json_err(f"Compilation failed: {exc}")


@app.command("fix-mcps")
def fix_mcps(
    mcps: list[str] = typer.Argument(None, help="Specific MCP names to check (default: sample of 3)"),
) -> None:
    """Diagnose Modal MCP deployment health.

    Checks Modal connectivity and tests whether physics MCP services are
    deployed and reachable. Outputs JSON diagnostics so Claude can delegate
    fixes to the MCP Builder.

    This does NOT fix anything locally — all fixes go through the MCP Builder
    which handles validation, redeployment, and Modal service management.
    """
    import os

    try:
        import modal
    except ImportError:
        _json_err("modal package not installed. Run: uv pip install modal")
        return

    env = os.environ.get("MODAL_ENVIRONMENT", "experiments")

    # Check Modal credentials
    try:
        _ = modal.config._profile  # noqa: SLF001 — lightweight credential check
    except Exception:
        _json_out(
            {
                "modal_connected": False,
                "modal_env": env,
                "error": "Modal credentials not configured. Run: modal token set",
                "action": "Configure Modal credentials, then use MCP Builder to validate deployments.",
                "test_results": {},
            }
        )
        return

    # Determine which MCPs to test
    if not mcps:
        mcps = ["qutip", "sandpile", "lammps"]

    test_results: dict[str, dict] = {}
    for mcp_name in mcps:
        # Modal naming convention: gpd-mcp-{name}, {Name}Service
        app_name = f"gpd-mcp-{mcp_name.replace('_', '-')}"
        # Build class name: "qe_epw" → "QeEpwService"
        class_name = "".join(part.capitalize() for part in mcp_name.split("_")) + "Service"
        try:
            cls = modal.Cls.from_name(app_name, class_name, environment_name=env)
            cls.hydrate()  # Forces server-side validation of deployment
            test_results[mcp_name] = {"status": "found", "app": app_name, "class": class_name}
        except Exception as exc:
            error_type = type(exc).__name__
            test_results[mcp_name] = {
                "status": "not_found",
                "app": app_name,
                "class": class_name,
                "error": f"{error_type}: {exc}",
            }

    found = [name for name, r in test_results.items() if r["status"] == "found"]
    broken = [name for name, r in test_results.items() if r["status"] != "found"]

    action = None
    if broken:
        broken_details = "; ".join(f"{name}: {test_results[name]['error']}" for name in broken)
        action = f"Use MCP Builder to redeploy these failing MCPs: {', '.join(broken)}. Details: {broken_details}"

    _json_out(
        {
            "modal_connected": len(found) > 0 or len(broken) == 0,
            "modal_env": env,
            "tested_count": len(mcps),
            "found_count": len(found),
            "broken_count": len(broken),
            "found": found,
            "broken": broken,
            "test_results": test_results,
            "action": action,
        }
    )
