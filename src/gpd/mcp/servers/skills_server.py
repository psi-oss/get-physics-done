"""MCP server for the canonical GPD skill index.

Reads shared skill definitions from the GPD registry and provides discovery,
content retrieval, auto-routing, and prompt injection support. Runtime
adapters may project different installed or discoverable surfaces, but they
all derive from this shared index.

Usage:
    python -m gpd.mcp.servers.skills_server
    # or via entry point:
    gpd-mcp-skills
"""

import dataclasses
import logging
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from gpd import registry as content_registry
from gpd.core.errors import GPDError
from gpd.core.observability import gpd_span

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-skills")

mcp = FastMCP("gpd-skills")

_MARKDOWN_REFERENCE_RE = re.compile(r"@?(?P<path>/[^\s`\"')]+\.md)")
_REFERENCE_ROOTS = tuple(
    root.resolve().as_posix()
    for root in (content_registry.SPECS_DIR, content_registry.AGENTS_DIR, content_registry.COMMANDS_DIR)
)
_CONTRACT_REFERENCE_NAMES = {
    "contract-results-schema.md",
    "peer-review-panel.md",
    "reproducibility-manifest.md",
    "summary.md",
    "verification-report.md",
}


def _load_skill_index() -> list[content_registry.SkillDef]:
    """Load the canonical registry/MCP skill index from shared commands and agents."""
    return [content_registry.get_skill(name) for name in content_registry.list_skills()]


def _resolve_skill(name: str) -> content_registry.SkillDef | None:
    """Resolve a public label, canonical skill name, or registry key to a skill record."""
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
    """Resolve shared path placeholders to local package paths for returned content."""
    specs_path = content_registry.SPECS_DIR.resolve().as_posix()
    agents_path = content_registry.AGENTS_DIR.resolve().as_posix()
    return content.replace("{GPD_INSTALL_DIR}", specs_path).replace("{GPD_AGENTS_DIR}", agents_path)


def _reference_kind(path: str) -> str:
    if path.startswith(content_registry.AGENTS_DIR.resolve().as_posix()):
        return "agent"
    if path.startswith(content_registry.COMMANDS_DIR.resolve().as_posix()):
        return "command"
    if "/templates/" in path:
        return "template"
    if "/workflows/" in path:
        return "workflow"
    if "/references/" in path:
        return "reference"
    if "/bundles/" in path:
        return "bundle"
    return "spec"


def _extract_referenced_files(content: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    seen: set[str] = set()
    visited_docs: set[str] = set()

    def _collect(markdown: str) -> None:
        for match in _MARKDOWN_REFERENCE_RE.finditer(markdown):
            path = match.group("path").rstrip(".,:;")
            if not any(path == root or path.startswith(root + "/") for root in _REFERENCE_ROOTS):
                continue
            if path not in seen:
                seen.add(path)
                references.append({"path": path, "kind": _reference_kind(path)})
            if path in visited_docs:
                continue
            visited_docs.add(path)
            referenced_path = Path(path)
            if referenced_path.suffix != ".md" or not referenced_path.exists():
                continue
            try:
                nested = _resolve_skill_content(referenced_path.read_text(encoding="utf-8"))
            except OSError:
                continue
            _collect(nested)

    _collect(content)
    return references


def _is_schema_reference(path: str) -> bool:
    name = Path(path).name
    return name.endswith("-schema.md") or name in {
        "summary.md",
        "verification-report.md",
        "contract-results-schema.md",
    }


def _is_contract_reference(path: str) -> bool:
    name = Path(path).name
    return _is_schema_reference(path) or name in _CONTRACT_REFERENCE_NAMES


@mcp.tool()
def list_skills(category: str | None = None) -> dict:
    """List canonical GPD skills with optional category filter.

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
    """Get the full content of a canonical skill definition.

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

            content = _resolve_skill_content(skill.content)
            referenced_files = _extract_referenced_files(content)
            template_references = [entry["path"] for entry in referenced_files if entry["kind"] == "template"]
            schema_references = [path for path in template_references if _is_schema_reference(path)]
            contract_references = [entry["path"] for entry in referenced_files if _is_contract_reference(entry["path"])]
            payload = {
                "name": skill.name,
                "category": skill.category,
                "content": content,
                "file_count": 1,
                "referenced_files": referenced_files,
                "reference_count": len(referenced_files),
                "template_references": template_references,
                "schema_references": schema_references,
                "contract_references": contract_references,
                "loading_hint": (
                    "Load schema_references, contract_references, and other referenced_files before asking a model to emit validated artifacts."
                    if referenced_files
                    else "No external markdown dependencies detected in the canonical skill body."
                ),
            }
            if skill.source_kind == "command":
                command = content_registry.get_command(skill.registry_name)
                payload.update(
                    {
                        "context_mode": command.context_mode,
                        "argument_hint": command.argument_hint,
                        "allowed_tools": command.allowed_tools,
                        "review_contract": (
                            dataclasses.asdict(command.review_contract) if command.review_contract is not None else None
                        ),
                    }
                )
            return payload
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
                score = 0
                for kw in keywords:
                    normalized_kw = re.sub(r"[^a-z0-9\s-]", "", kw.lower()).strip()
                    if not normalized_kw:
                        continue
                    if " " in normalized_kw:
                        if normalized_kw in normalized_task:
                            score += 2
                    elif normalized_kw in words:
                        score += 1
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
    """Return a formatted canonical skill index for actor prompt injection.

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
