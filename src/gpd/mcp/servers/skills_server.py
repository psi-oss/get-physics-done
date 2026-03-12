"""MCP server for GPD skill discovery and routing.

Reads skill definitions from the shared GPD registry and provides discovery,
content retrieval, auto-routing, and prompt injection support.

Usage:
    python -m gpd.mcp.servers.skills_server
    # or via entry point:
    gpd-mcp-skills
"""

import logging
import re
import sys

from mcp.server.fastmcp import FastMCP

from gpd import registry as content_registry
from gpd.core.errors import GPDError
from gpd.core.observability import gpd_span

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-skills")

mcp = FastMCP("gpd-skills")


def _load_skill_index() -> list[content_registry.SkillDef]:
    """Load available skills from the canonical commands/agents registry.
    """
    return [content_registry.get_skill(name) for name in content_registry.list_skills()]


def _resolve_skill(name: str) -> content_registry.SkillDef | None:
    """Resolve a canonical skill name or registry key to a skill record."""
    try:
        return content_registry.get_skill(name)
    except KeyError:
        return None


def _public_skill(skill: content_registry.SkillDef) -> dict[str, str]:
    return {
        "name": skill.name,
        "category": skill.category,
        "description": skill.description,
    }


def _skill_index_label(skill: content_registry.SkillDef) -> str:
    """Render a skill label without presenting agent skills as runtime commands."""
    if skill.source_kind == "command":
        return f"/{skill.name.replace('gpd-', 'gpd:')}"
    return skill.name


def _resolve_skill_content(content: str) -> str:
    """Resolve runtime path placeholders to the local package paths."""
    specs_path = content_registry.SPECS_DIR.resolve().as_posix()
    agents_path = content_registry.AGENTS_DIR.resolve().as_posix()
    return content.replace("{GPD_INSTALL_DIR}", specs_path).replace("{GPD_AGENTS_DIR}", agents_path)


@mcp.tool()
def list_skills(category: str | None = None) -> dict:
    """List available GPD skills with optional category filter.

    Skills are organized by category: execution, planning, verification,
    debugging, research, paper, analysis, diagnostics, management, etc.

    Args:
        category: Optional category to filter by.
    """
    with gpd_span("mcp.skills.list", category=category or ""):
        try:
            skills = [_public_skill(skill) for skill in _load_skill_index()]
            all_categories = sorted({s["category"] for s in skills})
            if category:
                skills = [s for s in skills if s["category"] == category]

            categories = all_categories
            return {
                "skills": skills,
                "count": len(skills),
                "categories": categories,
            }
        except (GPDError, OSError, ValueError, TimeoutError) as e:
            return {"error": str(e)}


@mcp.tool()
def get_skill(name: str) -> dict:
    """Get the full content of a specific skill definition.

    Returns the skill prompt and metadata for injection into agent context.

    Args:
        name: Skill name (e.g., "gpd-execute-phase", "gpd-plan-phase").
    """
    with gpd_span("mcp.skills.get", skill_name=name):
        try:
            skill = _resolve_skill(name)
            if skill is None:
                return {
                    "error": f"Skill {name!r} not found",
                    "available": [entry.name for entry in _load_skill_index()[:10]],
                }

            return {
                "name": skill.name,
                "category": skill.category,
                "content": _resolve_skill_content(skill.content),
                "file_count": 1,
            }
        except (GPDError, OSError, ValueError, TimeoutError) as e:
            return {"error": str(e)}


@mcp.tool()
def route_skill(task_description: str) -> dict:
    """Auto-select the best GPD skill for a given task description.

    Uses keyword matching to suggest the most relevant skill(s) for
    the described task.

    Args:
        task_description: Natural language description of what needs to be done.
    """
    with gpd_span("mcp.skills.route"):
        try:
            skills = _load_skill_index()
            if not skills:
                return {"error": "No skills available", "suggestion": None}
            available_names = {skill.name for skill in skills}
            normalized_task = re.sub(r"[^a-z0-9\s-]", "", task_description.lower()).strip()

            if "gpd-suggest-next" in available_names and any(
                phrase in normalized_task
                for phrase in (
                    "what should i do next",
                    "what do i do next",
                    "what next",
                    "next step",
                    "next steps",
                )
            ):
                return {
                    "suggestion": "gpd-suggest-next",
                    "confidence": 0.95,
                    "alternatives": [name for name in ("gpd-progress", "gpd-plan-phase") if name in available_names],
                    "task_description": task_description,
                }

            # Keyword scoring
            words = set(normalized_task.split())

            # Direct command mentions (e.g., "execute phase", "plan phase")
            command_keywords: dict[str, list[str]] = {
                "gpd-execute-phase": ["execute", "run", "implement", "build", "code"],
                "gpd-plan-phase": ["plan", "design", "architect", "strategy"],
                "gpd-verify-work": ["verify", "check", "validate", "test"],
                "gpd-debug": ["debug", "fix", "investigate", "error", "bug"],
                "gpd-new-project": ["new", "create", "initialize", "start", "project"],
                "gpd-write-paper": ["write", "paper", "draft", "manuscript"],
                "gpd-peer-review": ["peer", "referee", "reviewer", "manuscript"],
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
                "gpd-slides": ["slides", "slide", "presentation", "deck", "talk", "seminar", "beamer", "pptx"],
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

            fallback = "gpd-help" if "gpd-help" in available_names else skills[0].name

            return {
                "suggestion": fallback,
                "confidence": 0.1,
                "alternatives": [name for name in ("gpd-progress", "gpd-discover") if name in available_names],
                "task_description": task_description,
                "note": "No strong match found — try your runtime's GPD help command for available commands",
            }
        except (GPDError, OSError, ValueError, TimeoutError) as e:
            return {"error": str(e)}


@mcp.tool()
def get_skill_index() -> dict:
    """Return a formatted skill index for actor prompt injection.

    Returns a compact summary suitable for injecting into LLM context
    to make it aware of available GPD capabilities.
    """
    with gpd_span("mcp.skills.index"):
        try:
            skills = _load_skill_index()
            by_category: dict[str, list[str]] = {}
            for skill in skills:
                cat = skill.category
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(_skill_index_label(skill))

            lines = ["# Available GPD Skills", ""]
            for cat in sorted(by_category):
                lines.append(f"## {cat.title()}")
                for name in sorted(by_category[cat]):
                    lines.append(f"- {name}")
                lines.append("")

            return {
                "index_text": "\n".join(lines),
                "total_skills": len(skills),
                "categories": sorted(by_category),
            }
        except (GPDError, OSError, ValueError, TimeoutError) as e:
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-skills MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Skills MCP Server")


if __name__ == "__main__":
    main()
