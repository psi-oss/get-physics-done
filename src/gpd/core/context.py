"""Context assembly for AI agent commands.

Ported from experiments/get-physics-done/get-physics-done/src/commands.js (cmdInit* functions).
Each function gathers project state and produces a structured dict consumed by agent prompts.

Layer 1 code: stdlib + pathlib only (no framework imports).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum chars to include when embedding file contents in context.
MAX_INCLUDE_CHARS = int(os.environ.get("GPD_MAX_INCLUDE_CHARS", "20000"))

# Research file extensions for project detection.
_RESEARCH_EXTENSIONS = frozenset({".tex", ".ipynb", ".py", ".jl", ".f90"})

# Directories to skip when scanning for research files.
_IGNORE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        ".planning",
        ".claude",
        ".opencode",
        "get-physics-done",
        "agents",
        "command",
        "hooks",
    }
)

_SENTINEL = object()

__all__ = [
    "init_execute_phase",
    "init_map_theory",
    "init_milestone_op",
    "init_new_milestone",
    "init_new_project",
    "init_phase_op",
    "init_plan_phase",
    "init_progress",
    "init_quick",
    "init_resume",
    "init_todos",
    "init_verify_work",
    "load_config",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _safe_read_file(filepath: Path) -> str | None:
    """Read a file, returning None if it doesn't exist."""
    try:
        return filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _safe_read_file_truncated(filepath: Path, max_chars: int = 0) -> str | None:
    """Read a file, truncating if it exceeds max_chars."""
    content = _safe_read_file(filepath)
    if content is None:
        return None
    limit = max_chars or MAX_INCLUDE_CHARS
    if len(content) <= limit:
        return content
    return (
        content[:limit]
        + f"\n\n...truncated ({len(content)} chars total, showing first {limit}). "
        + "Use Read tool for full content."
    )


def _path_exists(cwd: Path, target: str) -> bool:
    """Check if a relative path exists under cwd."""
    return (cwd / target).exists()


def _generate_slug(text: str | None) -> str | None:
    """Generate a URL-friendly slug from text."""
    if not text:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or None


def _normalize_phase_name(phase: str) -> str:
    """Pad top-level phase number to 2 digits. E.g. '3' -> '03', '3.1' -> '03.1'."""
    match = re.match(r"^(\d+(?:\.\d+)*)", phase)
    if not match:
        return phase
    parts = match.group(1).split(".")
    normalized = []
    for i, p in enumerate(parts):
        try:
            v = int(p)
            normalized.append(str(v).zfill(2) if i == 0 else str(v))
        except ValueError:
            normalized.append(p)
    return ".".join(normalized)


def _is_phase_complete(plan_count: int, summary_count: int) -> bool:
    """A phase is complete when it has plans and all have matching summaries."""
    return plan_count > 0 and summary_count >= plan_count


def _find_phase_artifact(phase_dir: Path, suffix: str, standalone: str) -> str | None:
    """Find file content matching a suffix pattern in a phase directory (truncated)."""
    if not phase_dir.is_dir():
        return None
    for f in sorted(phase_dir.iterdir()):
        if f.is_file() and (f.name.endswith(suffix) or f.name == standalone):
            return _safe_read_file_truncated(f)
    return None


def _compute_branch_name(
    config: dict,
    phase_number: str | None,
    phase_slug: str | None,
    milestone_version: str,
    milestone_slug: str | None,
) -> str | None:
    """Compute the git branch name based on branching strategy."""
    strategy = config.get("branching_strategy", "none")
    if strategy == "phase" and phase_number:
        template = config.get("phase_branch_template", "gpd/phase-{phase}-{slug}")
        return template.replace("{phase}", phase_number).replace("{slug}", phase_slug or "phase")
    if strategy == "milestone":
        template = config.get("milestone_branch_template", "gpd/{milestone}-{slug}")
        return template.replace("{milestone}", milestone_version).replace("{slug}", milestone_slug or "milestone")
    return None


def _extract_frontmatter_field(content: str, field: str) -> str | None:
    """Extract a bare field: value from frontmatter-like content."""
    match = re.search(rf"^{re.escape(field)}:\s*(.+)$", content, re.MULTILINE)
    if not match:
        return None
    val = match.group(1).strip()
    # Strip surrounding quotes
    if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
        val = val[1:-1]
    return val or None


# ─── Config Loader ────────────────────────────────────────────────────────────


def load_config(cwd: Path) -> dict:
    """Load .planning/config.json with defaults. Mirrors JS loadConfig."""
    defaults: dict[str, object] = {
        "model_profile": "review",
        "autonomy": "guided",
        "research_mode": "balanced",
        "commit_docs": True,
        "search_gitignored": False,
        "branching_strategy": "none",
        "phase_branch_template": "gpd/phase-{phase}-{slug}",
        "milestone_branch_template": "gpd/{milestone}-{slug}",
        "research": True,
        "plan_checker": True,
        "verifier": True,
        "parallelization": True,
        "brave_search": False,
    }

    config_path = cwd / ".planning" / "config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(defaults)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Malformed config.json: {exc}. Fix or delete .planning/config.json") from exc

    def _get(key: str, section: str | None = None, field: str | None = None) -> object:
        """Look up key at top level, then in nested section. Returns _SENTINEL if not found."""
        if key in raw and raw[key] is not None:
            return raw[key]
        if section and field and section in raw and isinstance(raw[section], dict):
            v = raw[section].get(field)
            if v is not None:
                return v
        return _SENTINEL

    def _coalesce(val: object, default: object) -> object:
        return default if val is _SENTINEL else val

    # Parallelization can be bool or {enabled: bool}
    par_raw = _get("parallelization")
    if isinstance(par_raw, bool):
        parallelization = par_raw
    elif isinstance(par_raw, dict) and "enabled" in par_raw:
        parallelization = par_raw["enabled"]
    else:
        parallelization = defaults["parallelization"]

    # Autonomy with backward compat for old "mode" field
    autonomy_raw = _get("autonomy")
    if autonomy_raw is not _SENTINEL:
        autonomy = autonomy_raw
    else:
        mode = _get("mode")
        if mode == "yolo":
            autonomy = "yolo"
        elif mode == "interactive":
            autonomy = "supervised"
        else:
            autonomy = defaults["autonomy"]

    # Plan checker with backward compat for workflow.plan_check
    plan_checker_raw = _get("plan_checker", "workflow", "plan_checker")
    if plan_checker_raw is _SENTINEL:
        # Try legacy key
        if isinstance(raw.get("workflow"), dict) and "plan_check" in raw["workflow"]:
            plan_checker = raw["workflow"]["plan_check"]
        else:
            plan_checker = defaults["plan_checker"]
    else:
        plan_checker = plan_checker_raw

    return {
        "model_profile": _coalesce(_get("model_profile"), defaults["model_profile"]),
        "autonomy": autonomy,
        "research_mode": _coalesce(_get("research_mode"), defaults["research_mode"]),
        "commit_docs": _coalesce(_get("commit_docs", "planning", "commit_docs"), defaults["commit_docs"]),
        "search_gitignored": _coalesce(
            _get("search_gitignored", "planning", "search_gitignored"), defaults["search_gitignored"]
        ),
        "branching_strategy": _coalesce(
            _get("branching_strategy", "git", "branching_strategy"), defaults["branching_strategy"]
        ),
        "phase_branch_template": _coalesce(
            _get("phase_branch_template", "git", "phase_branch_template"), defaults["phase_branch_template"]
        ),
        "milestone_branch_template": _coalesce(
            _get("milestone_branch_template", "git", "milestone_branch_template"),
            defaults["milestone_branch_template"],
        ),
        "research": _coalesce(_get("research", "workflow", "research"), defaults["research"]),
        "plan_checker": plan_checker,
        "verifier": _coalesce(_get("verifier", "workflow", "verifier"), defaults["verifier"]),
        "parallelization": parallelization,
        "brave_search": _coalesce(_get("brave_search"), defaults["brave_search"]),
    }


# ─── Resolve Model ────────────────────────────────────────────────────────────

# Core returns tier strings (e.g. "tier-1", "tier-2"). Adapters translate
# these to provider-specific model names at install time.

# Agent type → profile → tier mapping (subset used by context assembly).
_MODEL_PROFILES: dict[str, dict[str, str]] = {
    "gpd-executor": {"review": "tier-2", "deep-theory": "tier-1", "numerical": "tier-2", "budget": "tier-3"},
    "gpd-verifier": {"review": "tier-2", "deep-theory": "tier-1", "numerical": "tier-2", "budget": "tier-3"},
    "gpd-phase-researcher": {"review": "tier-2", "deep-theory": "tier-1", "numerical": "tier-2", "budget": "tier-3"},
    "gpd-planner": {"review": "tier-2", "deep-theory": "tier-1", "numerical": "tier-2", "budget": "tier-3"},
    "gpd-plan-checker": {"review": "tier-3", "deep-theory": "tier-2", "numerical": "tier-3", "budget": "tier-3"},
    "gpd-project-researcher": {"review": "tier-2", "deep-theory": "tier-1", "numerical": "tier-2", "budget": "tier-3"},
    "gpd-research-synthesizer": {
        "review": "tier-2",
        "deep-theory": "tier-1",
        "numerical": "tier-2",
        "budget": "tier-3",
    },
    "gpd-roadmapper": {"review": "tier-2", "deep-theory": "tier-1", "numerical": "tier-2", "budget": "tier-3"},
    "gpd-theory-mapper": {"review": "tier-2", "deep-theory": "tier-1", "numerical": "tier-2", "budget": "tier-3"},
}


def _resolve_model(cwd: Path, agent_type: str) -> str:
    """Resolve the model identifier for a given agent type based on config profile."""
    config = load_config(cwd)
    profile = config.get("model_profile", "review")
    agent_models = _MODEL_PROFILES.get(agent_type)
    tier = "tier-2"
    if agent_models:
        tier = agent_models.get(profile) or agent_models.get("review", "tier-2")
    model_map = None
    # Config may have a custom model_map
    config_path = cwd / ".planning" / "config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        model_map = raw.get("model_map")
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass
    if model_map and isinstance(model_map, dict) and tier in model_map:
        return model_map[tier]
    return tier


# ─── Phase Info Helper ────────────────────────────────────────────────────────

# We use gpd.core.phases.find_phase and get_milestone_info when available,
# but provide a lightweight fallback to avoid circular imports during initial boot.


def _try_find_phase(cwd: Path, phase: str) -> dict | None:
    """Attempt to find phase info. Returns a plain dict or None."""
    try:
        from gpd.core.phases import find_phase

        result = find_phase(cwd, phase)
        if result is None:
            return None
        return result.model_dump()
    except ImportError:
        return _find_phase_fallback(cwd, phase)


def _find_phase_fallback(cwd: Path, phase: str) -> dict | None:
    """Minimal phase discovery without the full phases module."""
    phases_dir = cwd / ".planning" / "phases"
    if not phases_dir.is_dir():
        return None

    # Normalize: strip leading zeros for matching
    normalized = re.sub(r"^0+(\d)", r"\1", phase.strip())

    for d in sorted(phases_dir.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        if name == normalized or name.startswith(normalized + "-") or name.startswith(normalized + "."):
            dir_match = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", name)
            phase_number = dir_match.group(1) if dir_match else normalized
            phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None
            phase_slug = _generate_slug(phase_name) if phase_name else None

            phase_files = sorted(f.name for f in d.iterdir() if f.is_file())
            plans = [f for f in phase_files if f.endswith("-PLAN.md") or f == "PLAN.md"]
            summaries = [f for f in phase_files if f.endswith("-SUMMARY.md") or f == "SUMMARY.md"]
            has_research = any(f.endswith("-RESEARCH.md") or f == "RESEARCH.md" for f in phase_files)
            has_context = any(f.endswith("-CONTEXT.md") or f == "CONTEXT.md" for f in phase_files)
            has_verification = any(f.endswith("-VERIFICATION.md") or f == "VERIFICATION.md" for f in phase_files)
            has_validation = any(f.endswith("-VALIDATION.md") or f == "VALIDATION.md" for f in phase_files)

            # Incomplete plans: plans without matching summaries
            summary_prefixes = set()
            for s in summaries:
                prefix = s.removesuffix("-SUMMARY.md") if s.endswith("-SUMMARY.md") else ""
                summary_prefixes.add(prefix)
            incomplete_plans = []
            for p in plans:
                prefix = p.removesuffix("-PLAN.md") if p.endswith("-PLAN.md") else ""
                if prefix not in summary_prefixes:
                    incomplete_plans.append(p)

            return {
                "found": True,
                "directory": f".planning/phases/{name}",
                "phase_number": phase_number,
                "phase_name": phase_name,
                "phase_slug": phase_slug,
                "plans": plans,
                "summaries": summaries,
                "incomplete_plans": incomplete_plans,
                "has_research": has_research,
                "has_context": has_context,
                "has_verification": has_verification,
                "has_validation": has_validation,
            }
    return None


def _try_get_milestone_info(cwd: Path) -> dict:
    """Get milestone info, falling back to defaults."""
    try:
        from gpd.core.phases import get_milestone_info

        result = get_milestone_info(cwd)
        return result.model_dump()
    except ImportError:
        return _get_milestone_fallback(cwd)


def _get_milestone_fallback(cwd: Path) -> dict:
    """Minimal milestone extraction without the full phases module."""
    roadmap_path = cwd / ".planning" / "ROADMAP.md"
    content = _safe_read_file(roadmap_path)
    if content is None:
        return {"version": "v1.0", "name": "milestone"}
    version_match = re.search(r"v(\d+\.\d+)", content)
    name_match = re.search(r"## .*v\d+\.\d+[:\s]+([^\n(]+)", content)
    return {
        "version": version_match.group(0) if version_match else "v1.0",
        "name": name_match.group(1).strip() if name_match else "milestone",
    }


# ─── Platform Detection ──────────────────────────────────────────────────────


def _detect_platform() -> str:
    """Detect the AI coding platform (claude, codex, gemini, etc.)."""
    if os.environ.get("CODEX_CLI"):
        return "codex"
    if os.environ.get("GEMINI_CLI"):
        return "gemini"
    if os.environ.get("CLAUDE_CODE"):
        return "claude"
    return "unknown"  # No known platform detected


_PLATFORM = _detect_platform()


# ─── Context Assemblers ──────────────────────────────────────────────────────


def init_execute_phase(cwd: Path, phase: str, includes: set[str] | None = None) -> dict:
    """Assemble context for phase execution.

    Args:
        cwd: Project root directory.
        phase: Phase identifier (e.g. "3", "03", "3.1").
        includes: Optional set of file sections to embed (state, config, roadmap).
    """
    if not phase:
        raise ValueError("phase required for init execute-phase")

    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)
    milestone = _try_get_milestone_info(cwd)

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor"),
        "verifier_model": _resolve_model(cwd, "gpd-verifier"),
        # Config flags
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "parallelization": config["parallelization"],
        "branching_strategy": config["branching_strategy"],
        "phase_branch_template": config["phase_branch_template"],
        "milestone_branch_template": config["milestone_branch_template"],
        "verifier_enabled": config["verifier"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        # Plan inventory
        "plans": phase_info["plans"] if phase_info else [],
        "summaries": phase_info.get("summaries", []) if phase_info else [],
        "incomplete_plans": phase_info.get("incomplete_plans", []) if phase_info else [],
        "plan_count": len(phase_info["plans"]) if phase_info else 0,
        "incomplete_count": len(phase_info.get("incomplete_plans", [])) if phase_info else 0,
        # Branch name
        "branch_name": _compute_branch_name(
            config,
            phase_info.get("phase_number") if phase_info else None,
            phase_info.get("phase_slug") if phase_info else None,
            milestone["version"],
            _generate_slug(milestone["name"]),
        ),
        # Milestone info
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        "milestone_slug": _generate_slug(milestone["name"]),
        # File existence
        "state_exists": _path_exists(cwd, ".planning/STATE.md"),
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        "config_exists": _path_exists(cwd, ".planning/config.json"),
        # Platform
        "platform": _PLATFORM,
    }

    # Include file contents if requested
    planning = cwd / ".planning"
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / "STATE.md")
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / "config.json")
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / "ROADMAP.md")

    return result


def init_plan_phase(cwd: Path, phase: str, includes: set[str] | None = None) -> dict:
    """Assemble context for phase planning.

    Args:
        cwd: Project root directory.
        phase: Phase identifier.
        includes: Optional set of file sections to embed
                  (state, roadmap, requirements, context, research, verification, validation).
    """
    if not phase:
        raise ValueError("phase required for init plan-phase")

    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    result: dict[str, object] = {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-phase-researcher"),
        "planner_model": _resolve_model(cwd, "gpd-planner"),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker"),
        # Workflow flags
        "research_enabled": config["research"],
        "plan_checker_enabled": config["plan_checker"],
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        "padded_phase": _normalize_phase_name(phase_info["phase_number"]) if phase_info else None,
        # Existing artifacts
        "has_research": phase_info.get("has_research", False) if phase_info else False,
        "has_context": phase_info.get("has_context", False) if phase_info else False,
        "has_plans": len(phase_info.get("plans", [])) > 0 if phase_info else False,
        "plan_count": len(phase_info.get("plans", [])) if phase_info else 0,
        # Environment
        "planning_exists": _path_exists(cwd, ".planning"),
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        # Platform
        "platform": _PLATFORM,
    }

    # Include file contents
    planning = cwd / ".planning"
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / "STATE.md")
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / "ROADMAP.md")
    if "requirements" in includes:
        result["requirements_content"] = _safe_read_file_truncated(planning / "REQUIREMENTS.md")
    if "context" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["context_content"] = _find_phase_artifact(phase_dir, "-CONTEXT.md", "CONTEXT.md")
    if "research" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["research_content"] = _find_phase_artifact(phase_dir, "-RESEARCH.md", "RESEARCH.md")
    if "verification" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["verification_content"] = _find_phase_artifact(phase_dir, "-VERIFICATION.md", "VERIFICATION.md")
    if "validation" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["validation_content"] = _find_phase_artifact(phase_dir, "-VALIDATION.md", "VALIDATION.md")

    return result


def init_new_project(cwd: Path) -> dict:
    """Assemble context for new project creation."""
    config = load_config(cwd)

    # Detect Brave Search API key
    brave_key_file = Path.home() / ".gpd" / "brave_api_key"
    has_brave_search = bool(os.environ.get("BRAVE_API_KEY") or brave_key_file.exists())

    # Detect existing research files (walk up to depth 3, max 5 files)
    has_research_files = False
    found_count = 0

    def _walk(directory: Path, depth: int) -> None:
        nonlocal has_research_files, found_count
        if depth > 3 or found_count >= 5:
            return
        try:
            entries = sorted(directory.iterdir())
        except (PermissionError, FileNotFoundError):
            return
        for entry in entries:
            if found_count >= 5:
                return
            if entry.name in _IGNORE_DIRS:
                continue
            if entry.is_dir():
                _walk(entry, depth + 1)
            elif entry.is_file() and entry.suffix in _RESEARCH_EXTENSIONS:
                found_count += 1
                has_research_files = True

    _walk(cwd, 0)

    has_project_manifest = (
        _path_exists(cwd, "requirements.txt")
        or _path_exists(cwd, "pyproject.toml")
        or _path_exists(cwd, "Makefile")
        or _path_exists(cwd, "main.tex")
    )

    return {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-project-researcher"),
        "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer"),
        "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper"),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Existing state
        "project_exists": _path_exists(cwd, ".planning/PROJECT.md"),
        "has_theory_map": _path_exists(cwd, ".planning/research-map"),
        "planning_exists": _path_exists(cwd, ".planning"),
        # Existing project detection
        "has_research_files": has_research_files,
        "has_project_manifest": has_project_manifest,
        "has_existing_project": has_research_files or has_project_manifest,
        "needs_theory_map": (has_research_files or has_project_manifest)
        and not _path_exists(cwd, ".planning/research-map"),
        # Git state
        "has_git": _path_exists(cwd, ".git"),
        # Enhanced search
        "brave_search_available": has_brave_search,
        # Platform
        "platform": _PLATFORM,
    }


def init_new_milestone(cwd: Path) -> dict:
    """Assemble context for new milestone creation."""
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)

    return {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-project-researcher"),
        "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer"),
        "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper"),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "research_enabled": config["research"],
        # Current milestone
        "current_milestone": milestone["version"],
        "current_milestone_name": milestone["name"],
        # File existence
        "project_exists": _path_exists(cwd, ".planning/PROJECT.md"),
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        "state_exists": _path_exists(cwd, ".planning/STATE.md"),
        # Platform
        "platform": _PLATFORM,
    }


def init_quick(cwd: Path, description: str | None = None) -> dict:
    """Assemble context for quick task execution."""
    config = load_config(cwd)
    now = datetime.now(UTC)
    slug = _generate_slug(description)
    if slug:
        slug = slug[:40]

    # Find next quick task number
    quick_dir = cwd / ".planning" / "quick"
    next_num = 1
    try:
        existing = []
        for entry in quick_dir.iterdir():
            match = re.match(r"^(\d+)-", entry.name)
            if match:
                existing.append(int(match.group(1)))
        if existing:
            next_num = max(existing) + 1
    except FileNotFoundError:
        pass

    return {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner"),
        "executor_model": _resolve_model(cwd, "gpd-executor"),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Quick task info
        "next_num": next_num,
        "slug": slug,
        "description": description,
        # Timestamps
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        # Paths
        "quick_dir": ".planning/quick",
        "task_dir": f".planning/quick/{next_num}-{slug}" if slug else None,
        # File existence
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        "planning_exists": _path_exists(cwd, ".planning"),
        # Platform
        "platform": _PLATFORM,
    }


def init_resume(cwd: Path) -> dict:
    """Assemble context for resuming work."""
    config = load_config(cwd)

    # Check for interrupted agent
    interrupted_agent_id = None
    agent_id_file = cwd / ".planning" / "current-agent-id.txt"
    try:
        interrupted_agent_id = agent_id_file.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        pass

    return {
        # File existence
        "state_exists": _path_exists(cwd, ".planning/STATE.md"),
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        "project_exists": _path_exists(cwd, ".planning/PROJECT.md"),
        "planning_exists": _path_exists(cwd, ".planning"),
        # Agent state
        "has_interrupted_agent": interrupted_agent_id is not None,
        "interrupted_agent_id": interrupted_agent_id,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Platform
        "platform": _PLATFORM,
    }


def init_verify_work(cwd: Path, phase: str) -> dict:
    """Assemble context for work verification."""
    if not phase:
        raise ValueError("phase required for init verify-work")

    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    return {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner"),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker"),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        # Existing artifacts
        "has_verification": phase_info.get("has_verification", False) if phase_info else False,
        "has_validation": phase_info.get("has_validation", False) if phase_info else False,
        # Platform
        "platform": _PLATFORM,
    }


def init_phase_op(cwd: Path, phase: str | None = None, includes: set[str] | None = None) -> dict:
    """Assemble context for generic phase operations (parameter sweep, etc.)."""
    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase) if phase else None

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor"),
        "verifier_model": _resolve_model(cwd, "gpd-verifier"),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "brave_search": config["brave_search"],
        "parallelization": config["parallelization"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        "padded_phase": _normalize_phase_name(phase_info["phase_number"]) if phase_info else None,
        # Existing artifacts
        "has_research": phase_info.get("has_research", False) if phase_info else False,
        "has_context": phase_info.get("has_context", False) if phase_info else False,
        "has_plans": len(phase_info.get("plans", [])) > 0 if phase_info else False,
        "has_verification": phase_info.get("has_verification", False) if phase_info else False,
        "has_validation": phase_info.get("has_validation", False) if phase_info else False,
        "plan_count": len(phase_info.get("plans", [])) if phase_info else 0,
        # File existence
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        "state_exists": _path_exists(cwd, ".planning/STATE.md"),
        "planning_exists": _path_exists(cwd, ".planning"),
        # Platform
        "platform": _PLATFORM,
    }

    planning = cwd / ".planning"
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / "STATE.md")
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / "config.json")
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / "ROADMAP.md")

    return result


def init_todos(cwd: Path, area: str | None = None) -> dict:
    """Assemble context for todo management."""
    config = load_config(cwd)
    now = datetime.now(UTC)

    pending_dir = cwd / ".planning" / "todos" / "pending"
    todos: list[dict[str, str]] = []

    try:
        for f in sorted(pending_dir.iterdir()):
            if not f.is_file() or not f.name.endswith(".md"):
                continue
            content = f.read_text(encoding="utf-8")
            title = _extract_frontmatter_field(content, "title") or "Untitled"
            todo_area = _extract_frontmatter_field(content, "area") or "general"
            created = _extract_frontmatter_field(content, "created") or "unknown"

            if area and todo_area != area:
                continue

            todos.append(
                {
                    "file": f.name,
                    "created": created,
                    "title": title,
                    "area": todo_area,
                    "path": f".planning/todos/pending/{f.name}",
                }
            )
    except FileNotFoundError:
        pass

    return {
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Timestamps
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        # Todo inventory
        "todo_count": len(todos),
        "todos": todos,
        "area_filter": area,
        # Paths
        "pending_dir": ".planning/todos/pending",
        "done_dir": ".planning/todos/done",
        # File existence
        "planning_exists": _path_exists(cwd, ".planning"),
        "todos_dir_exists": _path_exists(cwd, ".planning/todos"),
        "pending_dir_exists": _path_exists(cwd, ".planning/todos/pending"),
        # Platform
        "platform": _PLATFORM,
    }


def init_milestone_op(cwd: Path) -> dict:
    """Assemble context for milestone operations (complete, archive, etc.)."""
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)

    # Count phases
    phases_dir = cwd / ".planning" / "phases"
    phase_count = 0
    completed_phases = 0
    try:
        for d in sorted(phases_dir.iterdir()):
            if not d.is_dir():
                continue
            phase_count += 1
            phase_files = [f.name for f in d.iterdir() if f.is_file()]
            plans = [f for f in phase_files if f.endswith("-PLAN.md") or f == "PLAN.md"]
            summaries = [f for f in phase_files if f.endswith("-SUMMARY.md") or f == "SUMMARY.md"]
            if _is_phase_complete(len(plans), len(summaries)):
                completed_phases += 1
    except FileNotFoundError:
        pass

    # Check archived milestones
    milestones_dir = cwd / ".planning" / "milestones"
    archived_milestones: list[str] = []
    try:
        archived_milestones = sorted(d.name for d in milestones_dir.iterdir() if d.is_dir())
    except FileNotFoundError:
        pass

    return {
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "branching_strategy": config["branching_strategy"],
        "phase_branch_template": config["phase_branch_template"],
        "milestone_branch_template": config["milestone_branch_template"],
        # Current milestone
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        "milestone_slug": _generate_slug(milestone["name"]),
        # Phase counts
        "phase_count": phase_count,
        "completed_phases": completed_phases,
        "all_phases_complete": phase_count > 0 and phase_count == completed_phases,
        # Archive
        "archived_milestones": archived_milestones,
        "archive_count": len(archived_milestones),
        # File existence
        "project_exists": _path_exists(cwd, ".planning/PROJECT.md"),
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        "state_exists": _path_exists(cwd, ".planning/STATE.md"),
        "milestones_exists": _path_exists(cwd, ".planning/milestones"),
        "phases_dir_exists": _path_exists(cwd, ".planning/phases"),
        # Platform
        "platform": _PLATFORM,
    }


def init_map_theory(cwd: Path) -> dict:
    """Assemble context for theory mapping."""
    config = load_config(cwd)

    # Check for existing research maps
    research_map_dir = cwd / ".planning" / "research-map"
    existing_maps: list[str] = []
    try:
        existing_maps = sorted(f.name for f in research_map_dir.iterdir() if f.is_file() and f.name.endswith(".md"))
    except FileNotFoundError:
        pass

    return {
        # Models
        "mapper_model": _resolve_model(cwd, "gpd-theory-mapper"),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "search_gitignored": config["search_gitignored"],
        "parallelization": config["parallelization"],
        # Paths
        "research_map_dir": ".planning/research-map",
        # Existing maps
        "existing_maps": existing_maps,
        "has_maps": len(existing_maps) > 0,
        # File existence
        "planning_exists": _path_exists(cwd, ".planning"),
        "research_map_dir_exists": _path_exists(cwd, ".planning/research-map"),
        # Platform
        "platform": _PLATFORM,
    }


def init_progress(cwd: Path, includes: set[str] | None = None) -> dict:
    """Assemble context for progress checking.

    Args:
        cwd: Project root directory.
        includes: Optional set of file sections to embed (state, roadmap, project, config).
    """
    includes = includes or set()
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)

    # Analyze phases
    phases_dir = cwd / ".planning" / "phases"
    phases: list[dict[str, object]] = []
    current_phase: dict[str, object] | None = None
    next_phase: dict[str, object] | None = None

    try:
        dirs = sorted(
            (d.name for d in phases_dir.iterdir() if d.is_dir()),
            key=lambda n: [int(x) if x.isdigit() else x for x in re.split(r"[.\-]", n)],
        )
        for dir_name in dirs:
            dir_match = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", dir_name)
            phase_number = dir_match.group(1) if dir_match else dir_name
            phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None

            phase_path = phases_dir / dir_name
            phase_files = [f.name for f in phase_path.iterdir() if f.is_file()]

            plans = [f for f in phase_files if f.endswith("-PLAN.md") or f == "PLAN.md"]
            summaries = [f for f in phase_files if f.endswith("-SUMMARY.md") or f == "SUMMARY.md"]
            has_research = any(f.endswith("-RESEARCH.md") or f == "RESEARCH.md" for f in phase_files)

            if _is_phase_complete(len(plans), len(summaries)):
                status = "complete"
            elif plans:
                status = "in_progress"
            elif has_research:
                status = "researched"
            else:
                status = "pending"

            phase_entry: dict[str, object] = {
                "number": phase_number,
                "name": phase_name,
                "directory": f".planning/phases/{dir_name}",
                "status": status,
                "plan_count": len(plans),
                "summary_count": len(summaries),
                "has_research": has_research,
            }
            phases.append(phase_entry)

            if current_phase is None and status in ("in_progress", "researched"):
                current_phase = phase_entry
            if next_phase is None and status == "pending":
                next_phase = phase_entry
    except FileNotFoundError:
        pass

    # Check for paused work
    paused_at: str | None = None
    state_content = _safe_read_file(cwd / ".planning" / "STATE.md")
    if state_content:
        status_match = re.search(r"\*\*Status:\*\*\s*(.+)", state_content)
        if status_match and status_match.group(1).strip() == "Paused":
            stopped_match = re.search(r"\*\*Stopped at:\*\*\s*(.+)", state_content)
            paused_at = stopped_match.group(1).strip() if stopped_match else "true"

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor"),
        "planner_model": _resolve_model(cwd, "gpd-planner"),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Milestone
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        # Phase overview
        "phases": phases,
        "phase_count": len(phases),
        "completed_count": sum(1 for p in phases if p["status"] == "complete"),
        "in_progress_count": sum(1 for p in phases if p["status"] == "in_progress"),
        # Current state
        "current_phase": current_phase,
        "next_phase": next_phase,
        "paused_at": paused_at,
        "has_work_in_progress": current_phase is not None,
        # File existence
        "project_exists": _path_exists(cwd, ".planning/PROJECT.md"),
        "roadmap_exists": _path_exists(cwd, ".planning/ROADMAP.md"),
        "state_exists": _path_exists(cwd, ".planning/STATE.md"),
        # Platform
        "platform": _PLATFORM,
    }

    # Include file contents
    planning = cwd / ".planning"
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / "STATE.md")
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / "ROADMAP.md")
    if "project" in includes:
        result["project_content"] = _safe_read_file_truncated(planning / "PROJECT.md")
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / "config.json")

    return result
