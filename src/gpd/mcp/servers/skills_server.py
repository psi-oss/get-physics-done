"""MCP server for GPD skill discovery and routing.

Reads skill definitions from specs/skills/ and provides discovery,
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
from gpd.core.utils import safe_read_file
from gpd.specs import SPECS_DIR

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-skills")

mcp = FastMCP("gpd-skills")

SKILLS_DIR = SPECS_DIR / "skills"

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
}


def _infer_category(skill_name: str) -> str:
    """Infer category from skill name using prefix matching."""
    for prefix, cat in _CATEGORY_MAP.items():
        if skill_name.startswith(prefix):
            return cat
    return "other"


def _load_skill_index() -> list[dict[str, str]]:
    """Load the list of available skills from the skills directory."""
    if not SKILLS_DIR.is_dir():
        return []

    skills: list[dict[str, str]] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("gpd-"):
            continue
        name = entry.name
        # Try to read the first few lines for a description
        desc = ""
        prompt_file = entry / "prompt.md"
        if not prompt_file.exists():
            # Some skills may use a different file
            md_files = list(entry.glob("*.md"))
            if md_files:
                prompt_file = md_files[0]

        if prompt_file.exists():
            content = safe_read_file(prompt_file)
            if content:
                # Extract first non-empty, non-heading line as description
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---"):
                        desc = line[:200]
                        break

        skills.append(
            {
                "name": name,
                "category": _infer_category(name),
                "description": desc,
            }
        )
    return skills


@mcp.tool()
def list_skills(category: str | None = None) -> dict:
    """List available GPD skills with optional category filter.

    Skills are organized by category: execution, planning, verification,
    debugging, research, paper, analysis, diagnostics, management, etc.

    Args:
        category: Optional category to filter by.
    """
    with gpd_span("mcp.skills.list", category=category or ""):
        skills = _load_skill_index()
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
        skill_dir = SKILLS_DIR / name
        if not skill_dir.is_dir():
            return {
                "error": f"Skill {name!r} not found",
                "available": [d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and d.name.startswith("gpd-")][:10],
            }

        # Collect all markdown files in the skill directory
        content_parts: list[str] = []
        for md_file in sorted(skill_dir.glob("*.md")):
            text = safe_read_file(md_file)
            if text:
                content_parts.append(text)

        content = "\n\n---\n\n".join(content_parts) if content_parts else ""
        return {
            "name": name,
            "category": _infer_category(name),
            "content": content,
            "file_count": len(content_parts),
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

        return {
            "suggestion": "gpd-help",
            "confidence": 0.1,
            "alternatives": ["gpd-progress", "gpd-discover"],
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
        skills = _load_skill_index()
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
