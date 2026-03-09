"""Context assembly for AI agent commands.

Each function gathers project state and produces a structured dict consumed by agent prompts.

Delegates to :mod:`gpd.core.config` for configuration loading and model-tier
resolution so that defaults and model profiles are defined in exactly one place.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from gpd.core.config import (
    GPDProjectConfig,
    resolve_agent_tier,
)
from gpd.core.config import (
    load_config as _load_config_structured,
)
from gpd.core.constants import (
    CONFIG_FILENAME,
    DEFAULT_MAX_INCLUDE_CHARS,
    ENV_MAX_INCLUDE_CHARS,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    ROADMAP_FILENAME,
    STATE_MD_FILENAME,
)
from gpd.core.errors import ValidationError

logger = logging.getLogger(__name__)

# Maximum chars to include when embedding file contents in context.
MAX_INCLUDE_CHARS = int(os.environ.get(ENV_MAX_INCLUDE_CHARS, str(DEFAULT_MAX_INCLUDE_CHARS)))


# Research file extensions for project detection.
_RESEARCH_EXTENSIONS = frozenset({".tex", ".ipynb", ".py", ".jl", ".f90"})

# Directories to skip when scanning for research files.
_IGNORE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        PLANNING_DIR_NAME,
        ".claude",
        ".codex",
        ".gemini",
        ".opencode",
        ".config",
        "get-physics-done",
        "agents",
        "command",
        "hooks",
    }
)

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
    """Read a file, returning None if it doesn't exist or can't be read."""
    try:
        return filepath.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
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
    if strategy in ("per-phase", "phase") and phase_number:
        template = config.get("phase_branch_template", "gpd/phase-{phase}-{slug}")
        return template.replace("{phase}", phase_number).replace("{slug}", phase_slug or "phase")
    if strategy in ("per-milestone", "milestone"):
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


def _config_to_dict(cfg: GPDProjectConfig) -> dict:
    """Convert a :class:`GPDProjectConfig` to the plain-dict format used by context callers.

    StrEnum values are converted to plain strings so that downstream template
    code (which does string comparisons) keeps working.
    """
    d: dict[str, object] = {
        "model_profile": str(cfg.model_profile.value),
        "autonomy": str(cfg.autonomy.value),
        "research_mode": str(cfg.research_mode.value),
        "commit_docs": cfg.commit_docs,
        "search_gitignored": cfg.search_gitignored,
        "branching_strategy": str(cfg.branching_strategy.value),
        "phase_branch_template": cfg.phase_branch_template,
        "milestone_branch_template": cfg.milestone_branch_template,
        "research": cfg.research,
        "plan_checker": cfg.plan_checker,
        "verifier": cfg.verifier,
        "parallelization": cfg.parallelization,
        "brave_search": cfg.brave_search,
    }
    if cfg.model_map:
        d["model_map"] = cfg.model_map
    return d


def load_config(cwd: Path) -> dict:
    """Load .planning/config.json with defaults.

    Delegates to :func:`gpd.core.config.load_config` (the canonical
    implementation) and converts the result to a plain dict for backward
    compatibility with existing context-assembly callers.

    Raises :class:`~gpd.core.errors.ConfigError` on malformed JSON.
    ``ConfigError`` inherits from both ``GPDError`` and ``ValueError``,
    so existing ``except ValueError`` handlers continue to work.
    """
    cfg = _load_config_structured(cwd)
    return _config_to_dict(cfg)


# ─── Resolve Model ────────────────────────────────────────────────────────────

# Core returns tier strings (e.g. "tier-1", "tier-2"). Adapters translate
# these to provider-specific model names at install time.


def _resolve_model(cwd: Path, agent_type: str, config: dict | None = None) -> str:
    """Resolve the model identifier for a given agent type based on config profile.

    Delegates tier resolution to :func:`gpd.core.config.resolve_agent_tier`
    which owns the canonical ``MODEL_PROFILES`` table.

    Args:
        cwd: Project root directory.
        agent_type: Agent name (e.g. "gpd-executor").
        config: Pre-loaded config dict. If None, loads from disk (slower).
    """
    if config is None:
        config = load_config(cwd)
    profile = config.get("model_profile", "review")
    tier = resolve_agent_tier(agent_type, profile).value
    model_map = config.get("model_map")
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
    phases_dir = cwd / PLANNING_DIR_NAME / "phases"
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
    roadmap_path = cwd / PLANNING_DIR_NAME / ROADMAP_FILENAME
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
    """Detect the AI agent platform (claude, codex, gemini, etc.)."""
    if os.environ.get("CODEX_CLI"):
        return "codex"
    if os.environ.get("GEMINI_CLI"):
        return "gemini"
    if os.environ.get("CLAUDE_CODE"):
        return "claude"
    return "unknown"  # No known platform detected


_PLATFORM = _detect_platform()


# ─── Context Assemblers ──────────────────────────────────────────────────────


def init_execute_phase(cwd: Path, phase: str | None, includes: set[str] | None = None) -> dict:
    """Assemble context for phase execution.

    Args:
        cwd: Project root directory.
        phase: Phase identifier (e.g. "3", "03", "3.1").
        includes: Optional set of file sections to embed (state, config, roadmap).
    """
    if not phase:
        raise ValidationError("phase required for init execute-phase")

    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)
    milestone = _try_get_milestone_info(cwd)

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
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
        "state_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "config_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{CONFIG_FILENAME}"),
        # Platform
        "platform": _PLATFORM,
    }

    # Include file contents if requested
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)

    return result


def init_plan_phase(cwd: Path, phase: str | None, includes: set[str] | None = None) -> dict:
    """Assemble context for phase planning.

    Args:
        cwd: Project root directory.
        phase: Phase identifier.
        includes: Optional set of file sections to embed
                  (state, roadmap, requirements, context, research, verification, validation).
    """
    if not phase:
        raise ValidationError("phase required for init plan-phase")

    includes = includes or set()
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    result: dict[str, object] = {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-phase-researcher", config),
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker", config),
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
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        # Platform
        "platform": _PLATFORM,
    }

    # Include file contents
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
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
        "researcher_model": _resolve_model(cwd, "gpd-project-researcher", config),
        "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer", config),
        "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Existing state
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "has_theory_map": _path_exists(cwd, f"{PLANNING_DIR_NAME}/research-map"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Existing project detection
        "has_research_files": has_research_files,
        "has_project_manifest": has_project_manifest,
        "has_existing_project": has_research_files or has_project_manifest,
        "needs_theory_map": (has_research_files or has_project_manifest)
        and not _path_exists(cwd, f"{PLANNING_DIR_NAME}/research-map"),
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
        "researcher_model": _resolve_model(cwd, "gpd-project-researcher", config),
        "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer", config),
        "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "research_enabled": config["research"],
        # Current milestone
        "current_milestone": milestone["version"],
        "current_milestone_name": milestone["name"],
        # File existence
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}"),
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
    quick_dir = cwd / PLANNING_DIR_NAME / "quick"
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
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
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
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Platform
        "platform": _PLATFORM,
    }


def init_resume(cwd: Path) -> dict:
    """Assemble context for resuming work."""
    config = load_config(cwd)

    # Check for interrupted agent
    interrupted_agent_id = None
    agent_id_file = cwd / PLANNING_DIR_NAME / "current-agent-id.txt"
    try:
        interrupted_agent_id = agent_id_file.read_text(encoding="utf-8").strip() or None
    except (FileNotFoundError, OSError):
        pass

    return {
        # File existence
        "state_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
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


def init_verify_work(cwd: Path, phase: str | None) -> dict:
    """Assemble context for work verification."""
    if not phase:
        raise ValidationError("phase required for init verify-work")

    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    return {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker", config),
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
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
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
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Platform
        "platform": _PLATFORM,
    }

    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)

    return result


def init_todos(cwd: Path, area: str | None = None) -> dict:
    """Assemble context for todo management."""
    config = load_config(cwd)
    now = datetime.now(UTC)

    pending_dir = cwd / PLANNING_DIR_NAME / "todos" / "pending"
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
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "todos_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/todos"),
        "pending_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/todos/pending"),
        # Platform
        "platform": _PLATFORM,
    }


def init_milestone_op(cwd: Path) -> dict:
    """Assemble context for milestone operations (complete, archive, etc.)."""
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)

    # Count phases
    phases_dir = cwd / PLANNING_DIR_NAME / "phases"
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
    milestones_dir = cwd / PLANNING_DIR_NAME / "milestones"
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
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}"),
        "milestones_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/milestones"),
        "phases_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/phases"),
        # Platform
        "platform": _PLATFORM,
    }


def init_map_theory(cwd: Path) -> dict:
    """Assemble context for theory mapping."""
    config = load_config(cwd)

    # Check for existing research maps
    research_map_dir = cwd / PLANNING_DIR_NAME / "research-map"
    existing_maps: list[str] = []
    try:
        existing_maps = sorted(f.name for f in research_map_dir.iterdir() if f.is_file() and f.name.endswith(".md"))
    except FileNotFoundError:
        pass

    return {
        # Models
        "mapper_model": _resolve_model(cwd, "gpd-theory-mapper", config),
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
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "research_map_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/research-map"),
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
    phases_dir = cwd / PLANNING_DIR_NAME / "phases"
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
    state_content = _safe_read_file(cwd / PLANNING_DIR_NAME / STATE_MD_FILENAME)
    if state_content:
        status_match = re.search(r"\*\*Status:\*\*\s*(.+)", state_content)
        if status_match and status_match.group(1).strip() == "Paused":
            stopped_match = re.search(r"\*\*Stopped at:\*\*\s*(.+)", state_content)
            paused_at = stopped_match.group(1).strip() if stopped_match else "true"

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
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
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}"),
        # Platform
        "platform": _PLATFORM,
    }

    # Include file contents
    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if "project" in includes:
        result["project_content"] = _safe_read_file_truncated(planning / PROJECT_FILENAME)
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)

    return result
