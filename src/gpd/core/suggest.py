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

from pydantic import ValidationError as PydanticValidationError

from gpd.command_labels import canonical_command_label
from gpd.contracts import ConventionLock
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
    STATE_JSON_FILENAME,
    SUMMARY_SUFFIX,
    TODOS_DIR_NAME,
    VERIFICATION_SUFFIX,
)
from gpd.core.manuscript_artifacts import (
    locate_publication_artifact,
    resolve_current_manuscript_artifacts,
    resolve_current_manuscript_resolution,
)
from gpd.core.phases import _milestone_completion_snapshot
from gpd.core.proof_review import (
    manuscript_requires_theorem_bearing_review,
    resolve_manuscript_proof_review_status,
)
from gpd.core.public_surface_contract import recovery_local_snapshot_command
from gpd.core.publication_review_paths import (
    manuscript_matches_review_artifact_path,
    review_artifact_round,
)
from gpd.core.reproducibility import compute_sha256
from gpd.core.runtime_command_surfaces import format_active_runtime_command
from gpd.core.utils import (
    is_phase_complete as _is_phase_complete,
)
from gpd.core.utils import matching_phase_artifact_count as _matching_phase_artifact_count
from gpd.core.utils import (
    phase_sort_key as _phase_sort_key,
)
from gpd.core.utils import (
    phase_unpad as _phase_unpad,
)
from gpd.mcp.paper.bibliography import BibliographyAudit
from gpd.mcp.paper.models import ArtifactManifest

logger = logging.getLogger(__name__)

__all__ = [
    "Recommendation",
    "SuggestContext",
    "SuggestResult",
    "suggest_next",
]

# ─── Constants ────────────────────────────────────────────────────────────────

CORE_CONVENTIONS = ("metric_signature", "natural_units", "coordinate_system")
_REVIEW_LEDGER_FILENAME_RE = re.compile(r"^REVIEW-LEDGER(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_REFEREE_DECISION_FILENAME_RE = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")


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
    return name.endswith(VERIFICATION_SUFFIX)






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


_LOCAL_CLI_INIT_COMMANDS: dict[str, str] = {
    "check-todos": "todos",
    "execute-phase": "execute-phase",
    "map-research": "map-research",
    "milestone-op": "milestone-op",
    "new-milestone": "new-milestone",
    "new-project": "new-project",
    "phase-op": "phase-op",
    "plan-phase": "plan-phase",
    "quick": "quick",
    "resume": "resume",
    "resume-work": "resume",
    "verify-work": "verify-work",
}

_LOCAL_CLI_PUBLIC_COMMANDS: dict[str, str] = {
    # Resume is a user-facing recovery command even when the local CLI still
    # routes most workflow assembly through `gpd init ...`.
    "resume": recovery_local_snapshot_command(),
    "resume-work": recovery_local_snapshot_command(),
    "progress": "gpd progress",
}


def _format_local_cli_command(action: str) -> str:
    """Format the best available local CLI equivalent for a workflow action."""
    public_command = _LOCAL_CLI_PUBLIC_COMMANDS.get(action)
    if public_command is not None:
        return public_command
    init_action = _LOCAL_CLI_INIT_COMMANDS.get(action)
    if init_action is not None:
        return f"gpd init {init_action}"
    return canonical_command_label(action)


def _format_command(action: str, *, cwd: Path | None = None) -> str:
    """Format a GPD command name."""
    try:
        formatted = format_active_runtime_command(action, cwd=cwd, fallback=None)
    except Exception:
        formatted = None
    return formatted if formatted is not None else _format_local_cli_command(action)


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
        summary_count = _matching_phase_artifact_count(plans, summaries)
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
    """Count .md files in GPD/todos/pending/."""
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


def _has_author_response(cwd: Path) -> bool:
    responses_dir = _planning_dir(cwd)
    if not responses_dir.is_dir():
        return False
    return any(path.is_file() for path in responses_dir.glob("AUTHOR-RESPONSE*.md"))


def _latest_referee_decision_recommendation(cwd: Path) -> str | None:
    review_dir = _planning_dir(cwd) / "review"
    if not review_dir.is_dir():
        return None

    decision_by_round: dict[int, Path] = {}
    for path in sorted(review_dir.glob("REFEREE-DECISION*.json")):
        details = review_artifact_round(path, pattern=_REFEREE_DECISION_FILENAME_RE)
        if details is not None:
            decision_by_round[details[0]] = path

    if not decision_by_round:
        return None

    latest_round = max(decision_by_round)
    try:
        payload = json.loads(decision_by_round[latest_round].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    recommendation = payload.get("final_recommendation")
    if not isinstance(recommendation, str):
        return None
    normalized = recommendation.strip().lower()
    return normalized or None


def _latest_publication_review_package(review_dir: Path) -> tuple[Path, Path] | None:
    ledger_by_round: dict[int, Path] = {}
    decision_by_round: dict[int, Path] = {}

    for path in sorted(review_dir.glob("REVIEW-LEDGER*.json")):
        details = review_artifact_round(path, pattern=_REVIEW_LEDGER_FILENAME_RE)
        if details is not None:
            ledger_by_round[details[0]] = path
    for path in sorted(review_dir.glob("REFEREE-DECISION*.json")):
        details = review_artifact_round(path, pattern=_REFEREE_DECISION_FILENAME_RE)
        if details is not None:
            decision_by_round[details[0]] = path

    if not ledger_by_round or not decision_by_round:
        return None

    latest_round = max({*ledger_by_round.keys(), *decision_by_round.keys()})
    ledger_path = ledger_by_round.get(latest_round)
    decision_path = decision_by_round.get(latest_round)
    if ledger_path is None or decision_path is None:
        return None
    return ledger_path, decision_path


def _manuscript_has_submission_support_artifacts(cwd: Path, manuscript_entrypoint: Path | None) -> bool:
    if manuscript_entrypoint is None or manuscript_entrypoint.suffix != ".tex":
        return False

    artifacts = resolve_current_manuscript_artifacts(cwd, allow_markdown=True)
    if artifacts.manuscript_entrypoint is None:
        return False
    if artifacts.manuscript_entrypoint.resolve(strict=False) != manuscript_entrypoint.resolve(strict=False):
        return False
    if artifacts.artifact_manifest is None or artifacts.bibliography_audit is None:
        return False

    try:
        ArtifactManifest.model_validate(json.loads(artifacts.artifact_manifest.read_text(encoding="utf-8")))
        bibliography_audit = BibliographyAudit.model_validate(
            json.loads(artifacts.bibliography_audit.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError, PydanticValidationError):
        return False
    if not (
        bibliography_audit.resolved_sources == bibliography_audit.total_sources
        and bibliography_audit.partial_sources == 0
        and bibliography_audit.unverified_sources == 0
        and bibliography_audit.failed_sources == 0
    ):
        return False

    if artifacts.reproducibility_manifest is None:
        return False
    if not _reproducibility_manifest_is_ready(artifacts.reproducibility_manifest):
        return False

    compiled_manuscript = locate_publication_artifact(
        manuscript_entrypoint,
        manuscript_entrypoint.with_suffix(".pdf").name,
    )
    return compiled_manuscript is not None and compiled_manuscript.exists()


def _reproducibility_manifest_is_ready(reproducibility_manifest: Path) -> bool:
    try:
        payload = json.loads(reproducibility_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    from gpd.core.reproducibility import validate_reproducibility_manifest

    validation = validate_reproducibility_manifest(payload)
    return validation.valid and validation.ready_for_review and not validation.warnings


def _current_publication_blockers(cwd: Path) -> list[str]:
    state = _load_state_json_safe(cwd) or {}
    raw_blockers = state.get("blockers") or []
    blockers: list[str] = []
    for item in _filter_unresolved(raw_blockers):
        text = _item_text(item, ("text", "description")).strip()
        if text:
            blockers.append(text)
    return blockers


def _publication_review_package_allows_submission(cwd: Path, manuscript_entrypoint: Path | None) -> bool:
    if manuscript_entrypoint is None or manuscript_entrypoint.suffix != ".tex":
        return False

    review_dir = _planning_dir(cwd) / "review"
    if not review_dir.is_dir():
        return False

    latest_package = _latest_publication_review_package(review_dir)
    if latest_package is None:
        return False

    ledger_path, decision_path = latest_package
    try:
        from gpd.core.referee_policy import evaluate_referee_decision
        from gpd.mcp.paper.review_artifacts import read_referee_decision, read_review_ledger

        review_ledger = read_review_ledger(ledger_path)
        decision = read_referee_decision(decision_path)
        if not manuscript_matches_review_artifact_path(review_ledger.manuscript_path, manuscript_entrypoint, cwd=cwd):
            return False
        manuscript_matches_decision = manuscript_matches_review_artifact_path(
            decision.manuscript_path,
            manuscript_entrypoint,
            cwd=cwd,
        )
        if not manuscript_matches_decision:
            return False
        report = evaluate_referee_decision(
            decision,
            strict=True,
            require_explicit_inputs=True,
            review_ledger=review_ledger,
            project_root=cwd,
            expected_manuscript_sha256=compute_sha256(manuscript_entrypoint),
        )
    except (OSError, json.JSONDecodeError, PydanticValidationError):
        return False
    except ValueError:
        return False
    if not report.valid:
        return False
    if decision.final_recommendation not in {"accept", "minor_revision"}:
        return False
    return not decision.blocking_issue_ids and _manuscript_has_submission_support_artifacts(cwd, manuscript_entrypoint)


def _conventions_are_ready(cwd: Path) -> bool:
    state = _load_state_json_safe(cwd) or {}
    convention_lock = state.get("convention_lock")
    if not isinstance(convention_lock, dict):
        return False
    from gpd.core.conventions import is_bogus_value

    return all(convention_lock.get(key) and not is_bogus_value(convention_lock.get(key)) for key in CORE_CONVENTIONS)


def _missing_conventions_from_state(state: dict[str, object]) -> tuple[str, ...]:
    """Return canonical missing convention keys from a loaded state payload."""
    convention_lock = state.get("convention_lock")
    if not isinstance(convention_lock, dict):
        return ()

    try:
        lock = ConventionLock.model_validate(convention_lock)
    except PydanticValidationError:
        return ()

    from gpd.core.conventions import convention_check

    return tuple(entry.key for entry in convention_check(lock).missing)


def _format_missing_conventions_reason(missing: tuple[str, ...]) -> str:
    """Format a readable missing-convention recommendation without truncating the count."""
    from gpd.core.conventions import CONVENTION_LABELS

    labels = [CONVENTION_LABELS.get(key, key.replace("_", " ").title()) for key in missing]
    preview_count = min(4, len(labels))
    preview = ", ".join(labels[:preview_count])
    if len(labels) > preview_count:
        preview += f", and {len(labels) - preview_count} more"
    plural = "field" if len(labels) == 1 else "fields"
    return f"{len(labels)} convention {plural} missing: {preview} — define before calculations"


def _publication_submission_is_strictly_ready(cwd: Path, manuscript_entrypoint: Path | None) -> bool:
    if manuscript_entrypoint is None:
        return False
    if _current_publication_blockers(cwd):
        return False
    if not _conventions_are_ready(cwd):
        return False
    if not _publication_review_package_allows_submission(cwd, manuscript_entrypoint):
        return False
    return _manuscript_submission_proof_review_is_fresh(cwd, manuscript_entrypoint)


def _manuscript_submission_proof_review_is_fresh(
    cwd: Path,
    manuscript_entrypoint: Path | None,
) -> bool:
    if manuscript_entrypoint is None:
        return True

    if not manuscript_requires_theorem_bearing_review(cwd, manuscript_entrypoint):
        return True

    proof_review_status = resolve_manuscript_proof_review_status(cwd, manuscript_entrypoint)
    return proof_review_status.can_rely_on_prior_review and proof_review_status.state == "fresh"


def _has_referee_report(cwd: Path) -> bool:
    """Check for canonical referee report files in `GPD/` only."""

    reports_dir = _planning_dir(cwd)
    if not reports_dir.is_dir():
        return False
    if _has_author_response(cwd) and _latest_referee_decision_recommendation(cwd) == "accept":
        return False
    return any(f.is_file() for f in reports_dir.glob("REFEREE-REPORT*.md"))


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
    manuscript_resolution = resolve_current_manuscript_resolution(cwd, allow_markdown=True)
    manuscript_entrypoint = manuscript_resolution.manuscript_entrypoint if manuscript_resolution.status == "resolved" else None
    manuscript_state_is_blocked = manuscript_resolution.status in {"ambiguous", "invalid"}

    if not project_exists and manuscript_entrypoint is None:
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

    for pa in phase_analysis:
        if not current_phase and pa.status == "in_progress":
            current_phase = pa
        if not next_unplanned and pa.status == "researched":
            next_unplanned = pa
        if not next_pending and pa.status == "pending":
            next_pending = pa

    milestone_snapshot = _milestone_completion_snapshot(cwd)
    all_complete = milestone_snapshot.all_phases_complete
    ctx_kwargs["phase_count"] = milestone_snapshot.phase_count
    ctx_kwargs["completed_phases"] = milestone_snapshot.completed_phases

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
    if state and not any(s.action == "resume" for s in suggestions):
        missing = _missing_conventions_from_state(state)
        if missing:
            ctx_kwargs["missing_conventions"] = missing
            suggestions.append(
                _MutableRecommendation(
                    action="set-conventions",
                    priority=6,
                    command=format_command("validate-conventions"),
                    reason=_format_missing_conventions_reason(missing),
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
    has_paper_flag = manuscript_entrypoint is not None
    has_latex_manuscript = manuscript_entrypoint is not None and manuscript_entrypoint.suffix == ".tex"
    has_lit_review = _has_literature_review(cwd)
    has_referee = _has_referee_report(cwd)
    submission_ready_review = _publication_submission_is_strictly_ready(cwd, manuscript_entrypoint)

    ctx_kwargs["has_paper"] = has_paper_flag
    ctx_kwargs["has_literature_review"] = has_lit_review
    ctx_kwargs["has_referee_report"] = has_referee

    # 13a. All phases complete + verified → suggest paper writing
    if all_complete and phase_analysis and not has_paper_flag and not manuscript_state_is_blocked:
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
        if submission_ready_review and has_latex_manuscript:
            suggestions.append(
                _MutableRecommendation(
                    action="arxiv-submission",
                    priority=3,
                    command=format_command("arxiv-submission"),
                    reason=(
                        "Latest peer-review decision clears submission packaging — prepare the LaTeX manuscript for arXiv"
                    ),
                )
            )
        elif has_referee:
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
