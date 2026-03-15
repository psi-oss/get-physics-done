"""Next-action intelligence for GPD research projects.

Analyzes current project state and returns prioritized recommendations for next steps.

Layer 1 code: stdlib + pathlib + json + dataclasses only.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from gpd.core.constants import (
    LITERATURE_DIR_NAME,
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    RESEARCH_SUFFIX,
    ROADMAP_FILENAME,
    STANDALONE_PLAN,
    STANDALONE_RESEARCH,
    STANDALONE_SUMMARY,
    STANDALONE_VERIFICATION,
    STATE_JSON_FILENAME,
    SUMMARY_SUFFIX,
    TODOS_DIR_NAME,
    VERIFICATION_SUFFIX,
)
from gpd.core.utils import (
    is_phase_complete as _is_phase_complete,
)
from gpd.core.utils import (
    phase_sort_key as _phase_sort_key,
)
from gpd.core.utils import (
    phase_unpad as _phase_unpad,
)

logger = logging.getLogger(__name__)

__all__ = [
    "Recommendation",
    "SuggestContext",
    "SuggestResult",
    "suggest_next",
]

# ─── Constants ────────────────────────────────────────────────────────────────

CORE_CONVENTIONS = ("metric_signature", "natural_units", "coordinate_system")

# Paper search paths relative to cwd
PAPER_PATHS = ("paper/main.tex", "manuscript/main.tex", "draft/main.tex")


# ─── Data Models ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A single prioritized next-action recommendation."""

    action: str
    priority: int
    reason: str
    command: str
    phase: str | None = None


@dataclass(slots=True)
class _MutableRecommendation:
    """Internal mutable recommendation for priority adjustment."""

    action: str
    priority: int
    reason: str
    command: str
    phase: str | None = None

    def freeze(self) -> Recommendation:
        return Recommendation(
            action=self.action,
            priority=self.priority,
            reason=self.reason,
            command=self.command,
            phase=self.phase,
        )


@dataclass(frozen=True, slots=True)
class SuggestContext:
    """Contextual information gathered during analysis."""

    current_phase: str | None = None
    status: str | None = None
    progress_percent: float = 0.0
    paused_at: str | None = None
    phase_count: int = 0
    completed_phases: int = 0
    active_blockers: int = 0
    unverified_results: int = 0
    open_questions: int = 0
    active_calculations: int = 0
    pending_todos: int = 0
    missing_conventions: tuple[str, ...] = ()
    has_paper: bool = False
    has_literature_review: bool = False
    has_referee_report: bool = False
    autonomy: str = "balanced"
    research_mode: str = "balanced"
    adaptive_approach_locked: bool = False


@dataclass(frozen=True, slots=True)
class SuggestResult:
    """Complete suggestion output with recommendations and context."""

    suggestions: list[Recommendation]
    total_suggestions: int
    suggestion_count: int
    top_action: Recommendation | None
    context: SuggestContext


@dataclass(frozen=True, slots=True)
class _PhaseAnalysis:
    """Internal analysis of a single phase directory."""

    number: str
    name: str | None
    status: str  # "complete", "in_progress", "researched", "pending"
    plan_count: int
    summary_count: int
    incomplete_count: int
    has_research: bool
    has_verification: bool


# ─── Internal Helpers ─────────────────────────────────────────────────────────


def _planning_dir(cwd: Path) -> Path:
    return cwd / PLANNING_DIR_NAME


def _path_exists(cwd: Path, relative: str) -> bool:
    return (cwd / relative).exists()


def _is_plan_file(name: str) -> bool:
    return name.endswith(PLAN_SUFFIX) or name == STANDALONE_PLAN


def _is_summary_file(name: str) -> bool:
    return name.endswith(SUMMARY_SUFFIX) or name == STANDALONE_SUMMARY


def _is_research_file(name: str) -> bool:
    return name.endswith(RESEARCH_SUFFIX) or name == STANDALONE_RESEARCH


def _is_verification_file(name: str) -> bool:
    return name.endswith(VERIFICATION_SUFFIX) or name == STANDALONE_VERIFICATION






def _load_config(cwd: Path) -> dict[str, object]:
    """Load project config.json, preserving canonical validation behavior.

    Missing config files still resolve to defaults via
    :func:`gpd.core.config.load_config`. Malformed files and removed keys are
    intentionally surfaced to callers instead of being silently masked here.
    """
    from gpd.core.config import load_config as _load_config_canonical

    cfg = _load_config_canonical(cwd)
    return {
        "autonomy": str(cfg.autonomy.value),
        "research_mode": str(cfg.research_mode.value),
    }


def _format_command(action: str, *, cwd: Path | None = None) -> str:
    """Format a GPD command name."""
    try:
        from gpd.adapters import get_adapter
        from gpd.hooks.runtime_detect import (
            RUNTIME_UNKNOWN,
            detect_active_runtime_with_gpd_install,
        )

        runtime = detect_active_runtime_with_gpd_install(cwd=cwd)
        if runtime == RUNTIME_UNKNOWN:
            return f"gpd {action}"
        return get_adapter(runtime).format_command(action)
    except Exception:
        return f"gpd {action}"


def _scan_phases(cwd: Path) -> list[_PhaseAnalysis]:
    """Scan all phase directories and return analysis of each."""
    phases_dir = _planning_dir(cwd) / PHASES_DIR_NAME
    if not phases_dir.is_dir():
        return []

    try:
        dir_names = sorted(
            [d.name for d in phases_dir.iterdir() if d.is_dir()],
            key=_phase_sort_key,
        )
    except OSError:
        return []

    results: list[_PhaseAnalysis] = []
    for dir_name in dir_names:
        match = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", dir_name)
        phase_number = match.group(1) if match else dir_name
        phase_name = match.group(2) if match and match.group(2) else None

        phase_path = phases_dir / dir_name
        try:
            files = [f.name for f in phase_path.iterdir() if f.is_file()]
        except OSError:
            continue

        plans = [f for f in files if _is_plan_file(f)]
        summaries = [f for f in files if _is_summary_file(f)]
        has_research = any(_is_research_file(f) for f in files)
        has_verification = any(_is_verification_file(f) for f in files)

        plan_count = len(plans)
        summary_count = len(summaries)
        complete = _is_phase_complete(plan_count, summary_count)

        if complete:
            status = "complete"
        elif plan_count > 0:
            status = "in_progress"
        elif has_research:
            status = "researched"
        else:
            status = "pending"

        results.append(
            _PhaseAnalysis(
                number=phase_number,
                name=phase_name,
                status=status,
                plan_count=plan_count,
                summary_count=summary_count,
                incomplete_count=max(0, plan_count - summary_count),
                has_research=has_research,
                has_verification=has_verification,
            )
        )

    return results



def _phase_label(phase: _PhaseAnalysis) -> str:
    """Format a phase number + optional name for display."""
    if phase.name:
        return f"{phase.number} ({phase.name})"
    return phase.number


def _filter_unresolved(items: list[object]) -> list[object]:
    """Filter a list of strings/dicts keeping only unresolved entries."""
    result: list[object] = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and not item.get("resolved", False):
            result.append(item)
    return result


def _item_text(item: object, fallback_keys: tuple[str, ...] = ("text",)) -> str:
    """Extract display text from a string or dict item."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in fallback_keys:
            val = item.get(key)
            if val and isinstance(val, str):
                return val
    return "unnamed"


def _result_has_verification_evidence(result: dict[str, object]) -> bool:
    """Return whether a result has any verification signal."""
    return result.get("verified") is True or bool(result.get("verification_records"))


def _resolve_unverified_result_phase(
    unverified_results: list[dict[str, object]],
    phase_analysis: list[_PhaseAnalysis],
) -> str | None:
    """Return one runnable phase number for unverified results when unambiguous."""
    known_phases = {_phase_unpad(phase.number): phase.number for phase in phase_analysis}
    resolved_phases: list[str] = []
    for result in unverified_results:
        raw_phase = result.get("phase")
        if raw_phase is None:
            continue
        phase = known_phases.get(_phase_unpad(str(raw_phase)))
        if phase and phase not in resolved_phases:
            resolved_phases.append(phase)

    if len(resolved_phases) == 1:
        return resolved_phases[0]
    return None


def _count_pending_todos(cwd: Path) -> int:
    """Count .md files in .gpd/todos/pending/."""
    pending_dir = _planning_dir(cwd) / TODOS_DIR_NAME / "pending"
    if not pending_dir.is_dir():
        return 0
    return sum(1 for f in pending_dir.iterdir() if f.is_file() and f.suffix == ".md")


def _has_literature_review(cwd: Path) -> bool:
    """Check if any literature review files exist."""
    lit_dir = _planning_dir(cwd) / LITERATURE_DIR_NAME
    if not lit_dir.is_dir():
        return False
    return any(f.name.endswith("-REVIEW.md") for f in lit_dir.iterdir() if f.is_file())


def _has_referee_report(cwd: Path) -> bool:
    """Check if any referee report files exist."""
    candidate_dirs = (_planning_dir(cwd), _planning_dir(cwd) / "paper")
    for directory in candidate_dirs:
        if directory.is_dir() and any(f.name.startswith("REFEREE-REPORT") for f in directory.iterdir() if f.is_file()):
            return True
    return False


def _has_paper(cwd: Path) -> bool:
    """Check if a paper draft exists at any known path."""
    return any((cwd / p).exists() for p in PAPER_PATHS)


def _has_adaptive_lock_signal(cwd: Path) -> bool:
    """Return whether project artifacts show decisive evidence or an explicit approach lock."""

    phases_dir = _planning_dir(cwd) / PHASES_DIR_NAME
    if not phases_dir.is_dir():
        return False

    explicit_lock_markers = (
        "approach_lock: true",
        "approach_locked: true",
        "approach_validated: true",
    )
    decisive_pass_re = re.compile(r"subject_role:\s*decisive[\s\S]{0,400}?verdict:\s*pass\b", re.IGNORECASE)
    decisive_failure_re = re.compile(r"subject_role:\s*decisive[\s\S]{0,400}?verdict:\s*(?:tension|fail)\b", re.IGNORECASE)
    passed_status_re = re.compile(r"^status:\s*passed\b", re.IGNORECASE | re.MULTILINE)
    for path in sorted(phases_dir.rglob("*.md")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.casefold()
        if any(marker in lowered for marker in explicit_lock_markers):
            return True
        if (
            "comparison_verdicts:" in lowered
            and passed_status_re.search(text)
            and decisive_pass_re.search(text)
            and not decisive_failure_re.search(text)
        ):
            return True
    return False


# ─── Priority Adjustments ────────────────────────────────────────────────────


def _apply_mode_adjustments(
    suggestions: list[_MutableRecommendation],
    config: dict[str, object],
    *,
    adaptive_approach_locked: bool,
) -> None:
    """Adjust priorities based on research_mode and autonomy settings."""
    research_mode = config.get("research_mode", "balanced")
    autonomy = config.get("autonomy", "balanced")

    for s in suggestions:
        # Research mode adjustments
        if research_mode == "explore":
            if s.action == "discuss-phase":
                s.priority = max(1, s.priority - 2)
            if s.action == "address-questions":
                s.priority = max(1, s.priority - 1)
        elif research_mode == "exploit":
            if s.action == "execute-phase":
                s.priority = max(1, s.priority - 1)
            if s.action == "verify-work":
                s.priority = max(1, s.priority - 1)
        elif research_mode == "adaptive":
            if adaptive_approach_locked:
                if s.action == "execute-phase":
                    s.priority = max(1, s.priority - 1)
                if s.action == "verify-work":
                    s.priority = max(1, s.priority - 1)
            else:
                if s.action == "discuss-phase":
                    s.priority = max(1, s.priority - 1)

        # Autonomy adjustments
        if autonomy == "supervised" and s.action in ("execute-phase", "continue-calculations"):
            s.priority += 1
        if autonomy == "yolo" and s.action == "execute-phase":
            s.priority = max(1, s.priority - 1)


# ─── Main Entry Point ────────────────────────────────────────────────────────


def suggest_next(cwd: Path, *, limit: int = 5) -> SuggestResult:
    """Analyze project state and return prioritized next-action recommendations.

    Scans the project for: paused work, blockers, phase status, unverified results,
    open questions, active calculations, pending todos, convention gaps, paper pipeline
    state, and returns up to ``limit`` prioritized recommendations.

    Args:
        cwd: Project root directory.
        limit: Maximum number of suggestions to return.

    Returns:
        SuggestResult with prioritized suggestions and project context.
    """
    suggestions: list[_MutableRecommendation] = []
    ctx_kwargs: dict[str, object] = {}
    def format_command(action):
        return _format_command(action, cwd=cwd)

    # ── 0. Check project existence ──────────────────────────────────────
    project_exists = _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}")
    roadmap_exists = _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}")

    if not project_exists:
        only = Recommendation(
            action="new-project",
            priority=1,
            command=format_command("new-project"),
            reason="No PROJECT.md found — initialize a new research project first",
        )
        return SuggestResult(
            suggestions=[only],
            total_suggestions=1,
            suggestion_count=1,
            top_action=only,
            context=SuggestContext(),
        )

    # ── 1. Load state + config ──────────────────────────────────────────
    state = _load_state_json_safe(cwd)
    config = _load_config(cwd)

    if state:
        position = state.get("position") or {}
        _raw_phase = position.get("current_phase")
        ctx_kwargs["current_phase"] = str(_raw_phase) if _raw_phase is not None else None
        ctx_kwargs["status"] = position.get("status")
        ctx_kwargs["progress_percent"] = position.get("progress_percent", 0)
        ctx_kwargs["paused_at"] = position.get("paused_at")

    # ── 2. Check for paused work (highest priority) ─────────────────────
    if state:
        position = state.get("position") or {}
        if position.get("paused_at") or str(position.get("status", "")).strip().lower() == "paused":
            paused_at = position.get("paused_at", "")
            reason = "Work was paused"
            if paused_at:
                reason += f" at {paused_at}"
            reason += " — resume to restore context"
            suggestions.append(
                _MutableRecommendation(
                    action="resume",
                    priority=1,
                    command=format_command("resume-work"),
                    reason=reason,
                )
            )

    # ── 3. Check for blockers ───────────────────────────────────────────
    if state:
        raw_blockers = state.get("blockers") or []
        blockers = _filter_unresolved(raw_blockers)
        if blockers:
            ctx_kwargs["active_blockers"] = len(blockers)
            texts = [_item_text(b, ("text", "description")) for b in blockers[:3]]
            suggestions.append(
                _MutableRecommendation(
                    action="resolve-blockers",
                    priority=2,
                    command=format_command("debug"),
                    reason=f"{len(blockers)} unresolved blocker(s): {'; '.join(texts)}",
                )
            )

    # ── 4. Scan phases ──────────────────────────────────────────────────
    phase_analysis = _scan_phases(cwd)
    current_phase: _PhaseAnalysis | None = None
    next_unplanned: _PhaseAnalysis | None = None
    next_pending: _PhaseAnalysis | None = None
    all_complete = True

    for pa in phase_analysis:
        if pa.status != "complete":
            all_complete = False
        if not current_phase and pa.status == "in_progress":
            current_phase = pa
        if not next_unplanned and pa.status == "researched":
            next_unplanned = pa
        if not next_pending and pa.status == "pending":
            next_pending = pa

    if not phase_analysis:
        all_complete = False

    ctx_kwargs["phase_count"] = len(phase_analysis)
    ctx_kwargs["completed_phases"] = sum(1 for p in phase_analysis if p.status == "complete")

    # ── 5. Phase-based suggestions ──────────────────────────────────────

    # 5a. Execute incomplete plans in current phase
    if current_phase:
        suggestions.append(
            _MutableRecommendation(
                action="execute-phase",
                priority=3,
                command=f"{format_command('execute-phase')} {current_phase.number}",
                reason=(
                    f"Phase {_phase_label(current_phase)} has "
                    f"{current_phase.incomplete_count} incomplete plan(s) — continue execution"
                ),
                phase=current_phase.number,
            )
        )

    # 5b. Verify completed phase that lacks verification
    unverified_complete = next(
        (p for p in phase_analysis if p.status == "complete" and not p.has_verification),
        None,
    )
    if unverified_complete:
        suggestions.append(
            _MutableRecommendation(
                action="verify-work",
                priority=4,
                command=f"{format_command('verify-work')} {unverified_complete.number}",
                reason=f"Phase {unverified_complete.number} is complete but unverified — run verification",
                phase=unverified_complete.number,
            )
        )

    # 5c. Plan a researched phase
    if next_unplanned:
        suggestions.append(
            _MutableRecommendation(
                action="plan-phase",
                priority=5,
                command=f"{format_command('plan-phase')} {next_unplanned.number}",
                reason=(f"Phase {_phase_label(next_unplanned)} has research but no plans — create execution plan"),
                phase=next_unplanned.number,
            )
        )

    # 5d. Discover/research next pending phase
    if next_pending:
        suggestions.append(
            _MutableRecommendation(
                action="discuss-phase",
                priority=6,
                command=f"{format_command('discuss-phase')} {next_pending.number}",
                reason=f"Phase {_phase_label(next_pending)} is pending — start with phase discussion",
                phase=next_pending.number,
            )
        )

    # ── 6. Unverified results ───────────────────────────────────────────
    if state:
        raw_results = state.get("intermediate_results") or []
        unverified = [r for r in raw_results if isinstance(r, dict) and not _result_has_verification_evidence(r)]
        if unverified:
            ctx_kwargs["unverified_results"] = len(unverified)
            ids = [r.get("id", "unnamed") for r in unverified[:3]]
            suffix = "..." if len(unverified) > 3 else ""
            verify_phase = _resolve_unverified_result_phase(unverified, phase_analysis)
            if verify_phase is not None:
                suggestions.append(
                    _MutableRecommendation(
                        action="verify-results",
                        priority=5,
                        command=f"{format_command('verify-work')} {verify_phase}",
                        reason=f"{len(unverified)} unverified result(s): {', '.join(str(i) for i in ids)}{suffix}",
                        phase=verify_phase,
                    )
                )

    # ── 7. Open questions ───────────────────────────────────────────────
    if state:
        raw_questions = state.get("open_questions") or []
        open_questions = _filter_unresolved(raw_questions)
        if open_questions:
            ctx_kwargs["open_questions"] = len(open_questions)
            texts = [_item_text(q, ("text", "question")) for q in open_questions[:2]]
            suggestions.append(
                _MutableRecommendation(
                    action="address-questions",
                    priority=7,
                    command=format_command("check-todos"),
                    reason=f"{len(open_questions)} open question(s) — {'; '.join(texts)}",
                )
            )

    # ── 8. Active calculations ──────────────────────────────────────────
    if state:
        raw_calcs = state.get("active_calculations") or []
        active_calcs = [
            c for c in raw_calcs if isinstance(c, str) or (isinstance(c, dict) and not c.get("completed", False))
        ]
        if active_calcs:
            ctx_kwargs["active_calculations"] = len(active_calcs)
            suggestions.append(
                _MutableRecommendation(
                    action="continue-calculations",
                    priority=4,
                    command=format_command("progress"),
                    reason=f"{len(active_calcs)} active calculation(s) in progress — check status",
                )
            )

    # ── 9. Pending todos ────────────────────────────────────────────────
    todo_count = _count_pending_todos(cwd)
    if todo_count > 0:
        ctx_kwargs["pending_todos"] = todo_count
        suggestions.append(
            _MutableRecommendation(
                action="review-todos",
                priority=8,
                command=format_command("check-todos"),
                reason=f"{todo_count} pending todo(s) — review and prioritize",
            )
        )

    # ── 10. Convention gaps ─────────────────────────────────────────────
    if state:
        convention_lock = state.get("convention_lock")
        if isinstance(convention_lock, dict):
            from gpd.core.conventions import is_bogus_value

            missing = [k for k in CORE_CONVENTIONS if not convention_lock.get(k) or is_bogus_value(convention_lock.get(k))]
            if missing:
                ctx_kwargs["missing_conventions"] = tuple(missing)
                suggestions.append(
                    _MutableRecommendation(
                        action="set-conventions",
                        priority=6,
                        command=format_command("validate-conventions"),
                        reason=f"Core conventions not set: {', '.join(missing)} — define before calculations",
                    )
                )

    # ── 11. No roadmap yet ──────────────────────────────────────────────
    if not roadmap_exists:
        suggestions.append(
            _MutableRecommendation(
                action="new-milestone",
                priority=2,
                command=format_command("new-milestone"),
                reason="No ROADMAP.md found — create milestone roadmap",
            )
        )

    # ── 12. All phases complete → milestone audit ───────────────────────
    if all_complete and phase_analysis:
        suggestions.append(
            _MutableRecommendation(
                action="audit-milestone",
                priority=3,
                command=format_command("audit-milestone"),
                reason=f"All {len(phase_analysis)} phases complete — audit milestone for gaps",
            )
        )

    # ── 13. Paper pipeline awareness ────────────────────────────────────
    has_paper_flag = _has_paper(cwd)
    has_lit_review = _has_literature_review(cwd)
    has_referee = _has_referee_report(cwd)

    ctx_kwargs["has_paper"] = has_paper_flag
    ctx_kwargs["has_literature_review"] = has_lit_review
    ctx_kwargs["has_referee_report"] = has_referee

    # 13a. All phases complete + verified → suggest paper writing
    if all_complete and phase_analysis and not has_paper_flag:
        all_verified = all(p.has_verification for p in phase_analysis)
        if all_verified:
            suggestions.append(
                _MutableRecommendation(
                    action="write-paper",
                    priority=3,
                    command=format_command("write-paper"),
                    reason=(f"All {len(phase_analysis)} phases complete and verified — ready to write paper"),
                )
            )
        if not has_lit_review:
            suggestions.append(
                _MutableRecommendation(
                    action="literature-review",
                    priority=4,
                    command=format_command("literature-review"),
                    reason=(
                        "No literature review found — recommended before paper writing for comprehensive citations"
                    ),
                )
            )

    # 13b. Paper exists → suggest submission or referee response
    if has_paper_flag:
        if has_referee:
            suggestions.append(
                _MutableRecommendation(
                    action="respond-to-referees",
                    priority=2,
                    command=format_command("respond-to-referees"),
                    reason="Referee report exists — respond to referee comments and revise manuscript",
                )
            )
        else:
            suggestions.append(
                _MutableRecommendation(
                    action="peer-review",
                    priority=4,
                    command=format_command("peer-review"),
                    reason="Paper draft exists — run standalone peer review before submission packaging",
                )
            )
            suggestions.append(
                _MutableRecommendation(
                    action="arxiv-submission",
                    priority=5,
                    command=format_command("arxiv-submission"),
                    reason=(
                        "Paper draft exists — prepare for arXiv submission "
                        "(validates LaTeX, flattens bibliography, packages)"
                    ),
                )
            )

    # ── 14. No phases at all → need to plan ─────────────────────────────
    if not phase_analysis and roadmap_exists:
        suggestions.append(
            _MutableRecommendation(
                action="plan-first-phase",
                priority=3,
                command=f"{format_command('discuss-phase')} 1",
                reason="Roadmap exists but no phases created — start with phase 1",
            )
        )

    # ── Mode-aware priority adjustments ─────────────────────────────────
    autonomy_val = str(config.get("autonomy", "balanced"))
    research_mode_val = str(config.get("research_mode", "balanced"))
    ctx_kwargs["autonomy"] = autonomy_val
    ctx_kwargs["research_mode"] = research_mode_val
    adaptive_approach_locked = _has_adaptive_lock_signal(cwd) if research_mode_val == "adaptive" else False
    ctx_kwargs["adaptive_approach_locked"] = adaptive_approach_locked
    _apply_mode_adjustments(suggestions, config, adaptive_approach_locked=adaptive_approach_locked)

    # ── Sort by priority ────────────────────────────────────────────────
    suggestions.sort(key=lambda s: s.priority)

    # ── Limit output ────────────────────────────────────────────────────
    limited = suggestions[:limit]
    frozen = [s.freeze() for s in limited]

    context = SuggestContext(**{k: v for k, v in ctx_kwargs.items() if v is not None})

    return SuggestResult(
        suggestions=frozen,
        total_suggestions=len(suggestions),
        suggestion_count=len(frozen),
        top_action=frozen[0] if frozen else None,
        context=context,
    )


def _load_state_json_safe(cwd: Path) -> dict[str, object] | None:
    """Load state.json without depending on the full state module's recovery logic.

    Tries ``gpd.core.state.load_state_json`` if available; falls back to direct read.
    """
    try:
        from gpd.core.state import load_state_json

        return load_state_json(cwd)
    except (FileNotFoundError, OSError, ImportError):
        logger.debug("suggest: state load failed", exc_info=True)

    # Fallback: direct JSON read
    state_path = cwd / PLANNING_DIR_NAME / STATE_JSON_FILENAME
    try:
        raw = state_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        logger.debug("suggest: state load failed", exc_info=True)
    return None
