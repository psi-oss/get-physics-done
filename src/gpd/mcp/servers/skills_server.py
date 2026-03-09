"""MCP server for GPD skill discovery and routing.

Reads skill definitions from the shared GPD registry and provides discovery,
content retrieval, auto-routing, and prompt injection support.

Usage:
    python -m gpd.mcp.servers.skills_server
    # or via entry point:
    gpd-mcp-skills
"""

from __future__ import annotations

import logging
import re
import sys

from mcp.server.fastmcp import FastMCP

from gpd.core.observability import gpd_span
from gpd.registry import get_command, list_commands

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-skills")

mcp = FastMCP("gpd-skills")

# Category mapping: skill name prefix -> category
_CATEGORY_MAP: dict[str, str] = {
    "gpd-execute": "execution",
    "gpd-plan": "planning",
    "gpd-verify": "verification",
    "gpd-debug": "debugging",
    "gpd-new": "project",
    "gpd-write": "paper",
    "gpd-paper": "paper",
    "gpd-literature": "research",
    "gpd-research": "research",
    "gpd-discover": "research",
    "gpd-map": "exploration",
    "gpd-show": "exploration",
    "gpd-progress": "status",
    "gpd-health": "diagnostics",
    "gpd-validate": "verification",
    "gpd-check": "verification",
    "gpd-audit": "verification",
    "gpd-add": "management",
    "gpd-insert": "management",
    "gpd-remove": "management",
    "gpd-merge": "management",
    "gpd-complete": "management",
    "gpd-compact": "management",
    "gpd-pause": "session",
    "gpd-resume": "session",
    "gpd-record": "management",
    "gpd-export": "output",
    "gpd-arxiv": "output",
    "gpd-graph": "visualization",
    "gpd-decisions": "status",
    "gpd-error": "diagnostics",
    "gpd-sensitivity": "analysis",
    "gpd-numerical": "analysis",
    "gpd-dimensional": "analysis",
    "gpd-limiting": "analysis",
    "gpd-parameter": "analysis",
    "gpd-compare": "analysis",
    "gpd-derive": "computation",
    "gpd-cost": "diagnostics",
    "gpd-set": "configuration",
    "gpd-settings": "configuration",
    "gpd-update": "management",
    "gpd-undo": "management",
    "gpd-sync": "management",
    "gpd-branch": "management",
    "gpd-respond": "paper",
    "gpd-reapply": "management",
    "gpd-regression": "verification",
    "gpd-quick": "execution",
    "gpd-help": "help",
    "gpd-suggest": "help",
    # Full-name entries for skills not captured by prefix matching
    "gpd-bibliographer": "research",
    "gpd-consistency-checker": "verification",
    "gpd-discuss-phase": "planning",
    "gpd-estimate-cost": "diagnostics",
    "gpd-executor": "execution",
    "gpd-experiment-designer": "planning",
    "gpd-list-phase-assumptions": "planning",
    "gpd-notation-coordinator": "verification",
    "gpd-phase-researcher": "research",
    "gpd-project-researcher": "research",
    "gpd-referee": "paper",
    "gpd-revise-phase": "management",
    "gpd-roadmapper": "planning",
    "gpd-theory-mapper": "exploration",
    "gpd-verifier": "verification",
}


def _infer_category(skill_name: str) -> str:
    """Infer category from skill name using prefix matching."""
    for prefix, cat in _CATEGORY_MAP.items():
        if skill_name.startswith(prefix):
            return cat
    return "other"


def _canonical_skill_name(registry_name: str, source: str) -> str:
    """Map registry command names to the canonical gpd-* skill namespace."""
    if source == "commands" and not registry_name.startswith("gpd-"):
        return f"gpd-{registry_name}"
    return registry_name


def _load_skill_index() -> list[dict[str, str]]:
    """Load available skills from the canonical GPD command registry.

    The registry already applies the intended precedence:
    ``commands/`` overrides legacy ``specs/skills/`` entries with the same
    logical command. This keeps the MCP skills surface aligned with the rest
    of the stack instead of serving stale specs-only content.
    """
    skills: list[dict[str, str]] = []
    for registry_name in list_commands():
        command = get_command(registry_name)
        skill_name = _canonical_skill_name(registry_name, command.source)
        if not skill_name.startswith("gpd-"):
            continue
        skills.append(
            {
                "name": skill_name,
                "category": _infer_category(skill_name),
                "description": command.description,
                "registry_name": registry_name,
            }
        )
    skills.sort(key=lambda item: item["name"])
    return skills


def _resolve_skill(name: str) -> dict[str, str] | None:
    """Resolve a canonical skill name or registry key to a skill record."""
    for skill in _load_skill_index():
        if name == skill["name"] or name == skill["registry_name"]:
            return skill
    return None


def _public_skill(skill: dict[str, str]) -> dict[str, str]:
    return {
        "name": skill["name"],
        "category": skill["category"],
        "description": skill["description"],
    }


@mcp.tool()
def list_skills(category: str | None = None) -> dict:
    """List available GPD skills with optional category filter.

    Skills are organized by category: execution, planning, verification,
    debugging, research, paper, analysis, diagnostics, management, etc.

    Args:
        category: Optional category to filter by.
    """
    with gpd_span("mcp.skills.list", category=category or ""):
        skills = [_public_skill(skill) for skill in _load_skill_index()]
        if category:
            skills = [s for s in skills if s["category"] == category]

        categories = sorted({s["category"] for s in skills})
        return {
            "skills": skills,
            "count": len(skills),
            "categories": categories,
        }


@mcp.tool()
def get_skill(name: str) -> dict:
    """Get the full content of a specific skill definition.

    Returns the skill prompt and metadata for injection into agent context.

    Args:
        name: Skill name (e.g., "gpd-execute-phase", "gpd-plan-phase").
    """
    with gpd_span("mcp.skills.get", skill_name=name):
        skill = _resolve_skill(name)
        if skill is None:
            return {
                "error": f"Skill {name!r} not found",
                "available": [entry["name"] for entry in _load_skill_index()[:10]],
            }

        command = get_command(skill["registry_name"])

        return {
            "name": skill["name"],
            "category": skill["category"],
            "content": command.content,
            "file_count": 1,
        }


@mcp.tool()
def route_skill(task_description: str) -> dict:
    """Auto-select the best GPD skill for a given task description.

    Uses keyword matching to suggest the most relevant skill(s) for
    the described task.

    Args:
        task_description: Natural language description of what needs to be done.
    """
    with gpd_span("mcp.skills.route"):
        skills = _load_skill_index()
        if not skills:
            return {"error": "No skills available", "suggestion": None}
        available_names = {skill["name"] for skill in skills}

        # Keyword scoring
        words = set(re.sub(r"[^a-z0-9\s-]", "", task_description.lower()).split())

        # Direct command mentions (e.g., "execute phase", "plan phase")
        command_keywords: dict[str, list[str]] = {
            "gpd-execute-phase": ["execute", "run", "implement", "build", "code"],
            "gpd-plan-phase": ["plan", "design", "architect", "strategy"],
            "gpd-verify-work": ["verify", "check", "validate", "test"],
            "gpd-debug": ["debug", "fix", "investigate", "error", "bug"],
            "gpd-new-project": ["new", "create", "initialize", "start", "project"],
            "gpd-write-paper": ["write", "paper", "draft", "manuscript"],
            "gpd-literature-review": ["literature", "review", "papers", "citations", "references"],
            "gpd-progress": ["progress", "status", "where", "current"],
            "gpd-derive-equation": ["derive", "equation", "calculate", "computation"],
            "gpd-discover": ["discover", "explore", "survey", "methods"],
            "gpd-health": ["health", "diagnostic", "doctor"],
            "gpd-validate-conventions": ["convention", "conventions", "notation"],
            "gpd-quick": ["quick", "fast", "simple"],
            "gpd-resume-work": ["resume", "continue", "pick up"],
            "gpd-pause-work": ["pause", "stop", "break"],
            "gpd-export": ["export", "html", "latex", "zip"],
            "gpd-dimensional-analysis": ["dimensional", "dimensions", "units"],
            "gpd-limiting-cases": ["limiting", "limit", "asymptotic"],
            "gpd-sensitivity-analysis": ["sensitivity", "parameter", "uncertainty"],
            "gpd-numerical-convergence": ["convergence", "numerical", "accuracy"],
        }

        scored: list[tuple[int, str]] = []
        for skill_name, keywords in command_keywords.items():
            if skill_name not in available_names:
                continue
            score = sum(1 for kw in keywords if kw in words)
            if score > 0:
                scored.append((score, skill_name))

        scored.sort(key=lambda x: -x[0])

        if scored:
            best = scored[0][1]
            alternatives = [s for _, s in scored[1:4]]
            return {
                "suggestion": best,
                "confidence": min(scored[0][0] / 3.0, 1.0),
                "alternatives": alternatives,
                "task_description": task_description,
            }

        fallback = "gpd-help" if "gpd-help" in available_names else skills[0]["name"]

        return {
            "suggestion": fallback,
            "confidence": 0.1,
            "alternatives": [name for name in ("gpd-progress", "gpd-discover") if name in available_names],
            "task_description": task_description,
            "note": "No strong match found — try /gpd:help for available commands",
        }


@mcp.tool()
def get_skill_index() -> dict:
    """Return a formatted skill index for actor prompt injection.

    Returns a compact summary suitable for injecting into LLM context
    to make it aware of available GPD capabilities.
    """
    with gpd_span("mcp.skills.index"):
        skills = [_public_skill(skill) for skill in _load_skill_index()]
        by_category: dict[str, list[str]] = {}
        for s in skills:
            cat = s["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(s["name"])

        lines = ["# Available GPD Skills", ""]
        for cat in sorted(by_category):
            lines.append(f"## {cat.title()}")
            for name in sorted(by_category[cat]):
                lines.append(f"- /{name.replace('gpd-', 'gpd:')}")
            lines.append("")

        return {
            "index_text": "\n".join(lines),
            "total_skills": len(skills),
            "categories": sorted(by_category),
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-skills MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Skills MCP Server")


if __name__ == "__main__":
    main()
