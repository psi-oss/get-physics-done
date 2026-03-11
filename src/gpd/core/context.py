"""Context assembly for AI agent commands.

Each function gathers project state and produces a structured dict consumed by agent prompts.

Delegates to :mod:`gpd.core.config` for configuration loading and model-tier
resolution so that defaults and model profiles are defined in exactly one place.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from gpd.adapters import iter_adapters
from gpd.core.config import (
    GPDProjectConfig,
    resolve_agent_tier,
    resolve_model as _resolve_model_canonical,
)
from gpd.core.config import (
    load_config as _load_config_structured,
)
from gpd.core.constants import (
    AGENT_ID_FILENAME,
    CONFIG_FILENAME,
    CONTEXT_SUFFIX,
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    RESEARCH_SUFFIX,
    ROADMAP_FILENAME,
    STANDALONE_CONTEXT,
    STANDALONE_PLAN,
    STANDALONE_RESEARCH,
    STANDALONE_SUMMARY,
    STANDALONE_VALIDATION,
    STANDALONE_VERIFICATION,
    STATE_MD_FILENAME,
    SUMMARY_SUFFIX,
    VALIDATION_SUFFIX,
    VERIFICATION_SUFFIX,
)
from gpd.core.errors import ValidationError
from gpd.core.utils import (
    generate_slug as _generate_slug_impl,
)
from gpd.core.utils import (
    phase_sort_key as _phase_sort_key,
)
from gpd.core.utils import (
    is_phase_complete as _is_phase_complete,
)
from gpd.core.utils import (
    phase_normalize as _phase_normalize_impl,
)
from gpd.core.utils import (
    safe_read_file as _safe_read_file,
)
from gpd.core.utils import (
    safe_read_file_truncated as _safe_read_file_truncated,
)

logger = logging.getLogger(__name__)


# Research file extensions for project detection.
_RESEARCH_EXTENSIONS = frozenset({".tex", ".ipynb", ".py", ".jl", ".f90"})
_RUNTIME_CONFIG_DIRS = frozenset(adapter.local_config_dir_name for adapter in iter_adapters())

# Directories to skip when scanning for research files.
_IGNORE_DIRS = frozenset(
    {
        ".git",
        PLANNING_DIR_NAME,
        *_RUNTIME_CONFIG_DIRS,
        ".config",
        ".venv",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".vscode",
        ".idea",
        "node_modules",
        "__pycache__",
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


def _path_exists(cwd: Path, target: str) -> bool:
    """Check if a relative path exists under cwd."""
    return (cwd / target).exists()


def _generate_slug(text: str | None) -> str | None:
    """Generate a URL-friendly slug from text.

    Thin wrapper around :func:`gpd.core.utils.generate_slug` that also
    accepts ``None`` (returning ``None`` immediately).
    """
    if not text:
        return None
    return _generate_slug_impl(text)


def _normalize_phase_name(phase: str) -> str:
    """Pad top-level phase number to 2 digits. E.g. '3' -> '03', '3.1' -> '03.1'.

    Delegates to :func:`gpd.core.utils.phase_normalize`.
    """
    return _phase_normalize_impl(phase)



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
    match = re.search(rf"^{re.escape(field)}:[ \t]*(.+)$", content, re.MULTILINE)
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
        "branching_strategy": str(cfg.branching_strategy.value),
        "phase_branch_template": cfg.phase_branch_template,
        "milestone_branch_template": cfg.milestone_branch_template,
        "research": cfg.research,
        "plan_checker": cfg.plan_checker,
        "verifier": cfg.verifier,
        "parallelization": cfg.parallelization,
    }
    if cfg.model_map:
        d["model_map"] = cfg.model_map
    return d


def load_config(cwd: Path) -> dict:
    """Load .gpd/config.json with defaults.

    Delegates to :func:`gpd.core.config.load_config` (the canonical
    implementation) and converts the result to a plain dict for context
    assembly callers.

    Raises :class:`~gpd.core.errors.ConfigError` on malformed JSON.
    """
    cfg = _load_config_structured(cwd)
    return _config_to_dict(cfg)


# ─── Resolve Model ────────────────────────────────────────────────────────────

# Core returns tier strings (e.g. "tier-1", "tier-2"). Adapters translate
# these to provider-specific model names at install time.


def _resolve_model(cwd: Path, agent_type: str, config: dict | None = None) -> str:
    """Resolve the model identifier for a given agent type based on config profile.

    Delegates to :func:`gpd.core.config.resolve_model` when no pre-loaded
    config dict is available.  When *config* is supplied (the common path
    inside context assemblers), we still delegate tier resolution to
    :func:`gpd.core.config.resolve_agent_tier` and then apply the
    ``model_map`` override exactly as the canonical implementation does.

    Args:
        cwd: Project root directory.
        agent_type: Agent name (e.g. "gpd-executor").
        config: Pre-loaded config dict. If None, loads from disk via
            the canonical :func:`gpd.core.config.resolve_model`.
    """
    if config is None:
        return _resolve_model_canonical(cwd, agent_type)
    profile = config.get("model_profile", str(GPDProjectConfig.model_fields["model_profile"].default.value))
    tier = resolve_agent_tier(agent_type, profile).value
    model_map = config.get("model_map")
    if model_map and isinstance(model_map, dict) and tier in model_map:
        return model_map[tier]
    return tier


# ─── Phase Info Helper ────────────────────────────────────────────────────────


def _try_find_phase(cwd: Path, phase: str) -> dict | None:
    """Attempt to find phase info. Returns a plain dict or None."""
    from gpd.core.phases import find_phase

    result = find_phase(cwd, phase)
    if result is None:
        return None
    return result.model_dump()


def _try_get_milestone_info(cwd: Path) -> dict:
    """Get milestone info from the canonical phases module."""
    from gpd.core.phases import get_milestone_info

    result = get_milestone_info(cwd)
    return result.model_dump()


# ─── Platform Detection ──────────────────────────────────────────────────────


def _detect_platform() -> str:
    """Detect the active AI runtime, if any."""
    try:
        from gpd.hooks.runtime_detect import detect_active_runtime

        return detect_active_runtime()
    except Exception:
        return "unknown"


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
        raise ValidationError(
            "phase is required for init execute-phase. "
            "Provide a phase identifier such as '1', '03', or '3.1'."
        )

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
        raise ValidationError(
            "phase is required for init plan-phase. "
            "Provide a phase identifier such as '1', '03', or '3.1'."
        )

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
        result["context_content"] = _find_phase_artifact(phase_dir, CONTEXT_SUFFIX, STANDALONE_CONTEXT)
    if "research" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["research_content"] = _find_phase_artifact(phase_dir, RESEARCH_SUFFIX, STANDALONE_RESEARCH)
    if "verification" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["verification_content"] = _find_phase_artifact(phase_dir, VERIFICATION_SUFFIX, STANDALONE_VERIFICATION)
    if "validation" in includes and phase_info and phase_info.get("directory"):
        phase_dir = cwd / phase_info["directory"]
        result["validation_content"] = _find_phase_artifact(phase_dir, VALIDATION_SUFFIX, STANDALONE_VALIDATION)

    return result


def init_new_project(cwd: Path) -> dict:
    """Assemble context for new project creation."""
    config = load_config(cwd)

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
    except (FileNotFoundError, PermissionError):
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
        "quick_dir": f"{PLANNING_DIR_NAME}/quick",
        "task_dir": f"{PLANNING_DIR_NAME}/quick/{next_num}-{slug}" if slug else None,
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
    agent_id_file = cwd / PLANNING_DIR_NAME / AGENT_ID_FILENAME
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
        raise ValidationError(
            "phase is required for init verify-work. "
            "Provide a phase identifier such as '1', '03', or '3.1'."
        )

    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    return {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
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
            try:
                content = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
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
                    "path": f"{PLANNING_DIR_NAME}/todos/pending/{f.name}",
                }
            )
    except (FileNotFoundError, PermissionError):
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
        "pending_todos": todos,
        "area_filter": area,
        # Paths
        "pending_dir": f"{PLANNING_DIR_NAME}/todos/pending",
        "done_dir": f"{PLANNING_DIR_NAME}/todos/done",
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
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
    phase_count = 0
    completed_phases = 0
    try:
        for d in sorted(phases_dir.iterdir()):
            if not d.is_dir():
                continue
            phase_count += 1
            phase_files = [f.name for f in d.iterdir() if f.is_file()]
            plans = [f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
            summaries = [f for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]
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
        "parallelization": config["parallelization"],
        # Paths
        "research_map_dir": f"{PLANNING_DIR_NAME}/research-map",
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
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
    phases: list[dict[str, object]] = []
    current_phase: dict[str, object] | None = None
    next_phase: dict[str, object] | None = None

    try:
        dirs = sorted(
            (d.name for d in phases_dir.iterdir() if d.is_dir()),
            key=_phase_sort_key,
        )
        for dir_name in dirs:
            dir_match = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", dir_name)
            phase_number = dir_match.group(1) if dir_match else dir_name
            phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None

            phase_path = phases_dir / dir_name
            phase_files = [f.name for f in phase_path.iterdir() if f.is_file()]

            plans = [f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
            summaries = [f for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]
            has_research = any(f.endswith(RESEARCH_SUFFIX) or f == STANDALONE_RESEARCH for f in phase_files)

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
                "directory": f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/{dir_name}",
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
        if status_match and status_match.group(1).strip().lower() == "paused":
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
