"""Machine-readable recommendation policy for staged peer review."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.mcp.paper.models import (
    ReviewConfidence,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    ReviewLedger,
    ReviewRecommendation,
)

__all__ = [
    "ReviewAdequacy",
    "RefereeDecisionInput",
    "RefereeDecisionReport",
    "evaluate_referee_decision",
]


class ReviewAdequacy(StrEnum):
    """Qualitative adequacy scale used by the final meta-referee."""

    strong = "strong"
    adequate = "adequate"
    weak = "weak"
    insufficient = "insufficient"


class RefereeDecisionInput(BaseModel):
    """Typed summary of the final staged-review adjudication."""

    manuscript_path: str = ""
    target_journal: str = "unspecified"
    final_recommendation: ReviewRecommendation
    final_confidence: ReviewConfidence = ReviewConfidence.medium
    stage_artifacts: list[str] = Field(default_factory=list)
    central_claims_supported: bool = True
    claim_scope_proportionate_to_evidence: bool = True
    physical_assumptions_justified: bool = True
    unsupported_claims_are_central: bool = False
    reframing_possible_without_new_results: bool = True
    mathematical_correctness: ReviewAdequacy = ReviewAdequacy.adequate
    novelty: ReviewAdequacy = ReviewAdequacy.adequate
    significance: ReviewAdequacy = ReviewAdequacy.adequate
    venue_fit: ReviewAdequacy = ReviewAdequacy.adequate
    literature_positioning: ReviewAdequacy = ReviewAdequacy.adequate
    unresolved_major_issues: int = Field(default=0, ge=0)
    unresolved_minor_issues: int = Field(default=0, ge=0)
    blocking_issue_ids: list[str] = Field(default_factory=list)


class RefereeDecisionReport(BaseModel):
    """Validation report for a referee recommendation."""

    manuscript_path: str = ""
    target_journal: str
    proposed_recommendation: ReviewRecommendation
    most_positive_allowed_recommendation: ReviewRecommendation
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


_RECOMMENDATION_ORDER: dict[ReviewRecommendation, int] = {
    ReviewRecommendation.accept: 0,
    ReviewRecommendation.minor_revision: 1,
    ReviewRecommendation.major_revision: 2,
    ReviewRecommendation.reject: 3,
}

_ADEQUACY_ORDER: dict[ReviewAdequacy, int] = {
    ReviewAdequacy.strong: 0,
    ReviewAdequacy.adequate: 1,
    ReviewAdequacy.weak: 2,
    ReviewAdequacy.insufficient: 3,
}

_HIGH_IMPACT_JOURNALS = {"prl", "nature", "nature_physics"}


def _worse_recommendation(left: ReviewRecommendation, right: ReviewRecommendation) -> ReviewRecommendation:
    return left if _RECOMMENDATION_ORDER.get(left, 99) >= _RECOMMENDATION_ORDER.get(right, 99) else right


def _is_high_impact(journal: str) -> bool:
    return journal.strip().lower().replace(" ", "_") in _HIGH_IMPACT_JOURNALS


def _at_or_below(value: ReviewAdequacy, floor: ReviewAdequacy) -> bool:
    return _ADEQUACY_ORDER.get(value, 99) >= _ADEQUACY_ORDER.get(floor, 99)


def _missing_stage_artifacts(stage_artifacts: list[str], *, project_root: Path | None) -> list[str]:
    if project_root is None:
        return []

    resolved_root = project_root.resolve(strict=False)
    missing: list[str] = []
    for artifact_path in stage_artifacts:
        target = Path(artifact_path)
        if not target.is_absolute():
            target = project_root / target
        resolved_target = target.resolve(strict=False)
        if not resolved_target.is_relative_to(resolved_root) or not target.exists():
            missing.append(artifact_path)
    return missing


def _normalize_path_label(path_text: str) -> str:
    return Path(path_text.strip()).as_posix()


def _review_ledger_consistency_errors(data: RefereeDecisionInput, review_ledger: ReviewLedger) -> list[str]:
    errors: list[str] = []

    normalized_decision_path = _normalize_path_label(data.manuscript_path) if data.manuscript_path.strip() else ""
    normalized_ledger_path = _normalize_path_label(review_ledger.manuscript_path) if review_ledger.manuscript_path.strip() else ""
    if normalized_decision_path and normalized_ledger_path and normalized_decision_path != normalized_ledger_path:
        errors.append("referee decision manuscript_path does not match review ledger manuscript_path")

    issue_ids = [issue.issue_id for issue in review_ledger.issues]
    duplicate_issue_ids = sorted(issue_id for issue_id, count in Counter(issue_ids).items() if count > 1)
    if duplicate_issue_ids:
        errors.append("review ledger contains duplicate issue IDs: " + ", ".join(duplicate_issue_ids))

    ledger_issue_ids = set(issue_ids)
    blocking_issue_ids = set(data.blocking_issue_ids)
    unknown_blocking_issue_ids = sorted(blocking_issue_ids - ledger_issue_ids)
    if unknown_blocking_issue_ids:
        errors.append("blocking_issue_ids not found in review ledger: " + ", ".join(unknown_blocking_issue_ids))

    unresolved_blocking_issue_ids = sorted(
        issue.issue_id
        for issue in review_ledger.issues
        if issue.blocking and issue.status != ReviewIssueStatus.resolved
    )
    missing_blocking_issue_ids = [issue_id for issue_id in unresolved_blocking_issue_ids if issue_id not in blocking_issue_ids]
    if missing_blocking_issue_ids:
        errors.append(
            "unresolved blocking review-ledger issues missing from blocking_issue_ids: "
            + ", ".join(missing_blocking_issue_ids)
        )

    unresolved_major_issues = sum(
        1
        for issue in review_ledger.issues
        if issue.severity in {ReviewIssueSeverity.critical, ReviewIssueSeverity.major}
        and issue.status != ReviewIssueStatus.resolved
    )
    if data.unresolved_major_issues != unresolved_major_issues:
        errors.append(
            "unresolved_major_issues does not match review ledger count "
            f"({data.unresolved_major_issues} != {unresolved_major_issues})"
        )

    unresolved_minor_issues = sum(
        1
        for issue in review_ledger.issues
        if issue.severity == ReviewIssueSeverity.minor and issue.status != ReviewIssueStatus.resolved
    )
    if data.unresolved_minor_issues != unresolved_minor_issues:
        errors.append(
            "unresolved_minor_issues does not match review ledger count "
            f"({data.unresolved_minor_issues} != {unresolved_minor_issues})"
        )

    return errors


def evaluate_referee_decision(
    data: RefereeDecisionInput,
    *,
    strict: bool = False,
    review_ledger: ReviewLedger | None = None,
    project_root: Path | None = None,
) -> RefereeDecisionReport:
    """Evaluate whether a final recommendation is consistent with hard referee gates."""

    allowed = ReviewRecommendation.accept
    reasons: list[str] = []
    warnings: list[str] = []
    high_impact = _is_high_impact(data.target_journal)
    consistency_errors: list[str] = []

    if strict and len(data.stage_artifacts) < 5:
        consistency_errors.append("Strict staged peer review requires at least five specialist stage artifacts before adjudication.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)
    elif not data.stage_artifacts:
        warnings.append("No staged review artifacts were listed in the final decision input.")

    missing_stage_artifacts = _missing_stage_artifacts(data.stage_artifacts, project_root=project_root)
    if missing_stage_artifacts:
        consistency_errors.append("listed staged review artifacts do not exist: " + ", ".join(missing_stage_artifacts))

    if not data.central_claims_supported:
        reasons.append("Central manuscript claims are not directly supported by the available evidence.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)

    if not data.claim_scope_proportionate_to_evidence:
        if data.unsupported_claims_are_central or high_impact or not data.reframing_possible_without_new_results:
            reasons.append("Claim scope outruns the evidence in a way that requires rejection rather than polishing.")
            allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
        else:
            reasons.append("Claim scope must be materially narrowed before the manuscript can be reconsidered.")
            allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if not data.physical_assumptions_justified:
        if data.unsupported_claims_are_central and not data.reframing_possible_without_new_results:
            reasons.append("Physical assumptions adjacent to the main claims are unjustified and not salvageable by reframing alone.")
            allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
        else:
            reasons.append("Physical assumptions adjacent to the mathematics require substantive justification or restriction.")
            allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if _at_or_below(data.significance, ReviewAdequacy.insufficient):
        reasons.append("Physical significance is insufficient for publication in the current framing.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
    elif _at_or_below(data.significance, ReviewAdequacy.weak):
        reasons.append(
            "Weak physical significance cannot be handled as a minor revision; the contribution must be reframed or rejected."
        )
        allowed = _worse_recommendation(
            allowed,
            ReviewRecommendation.reject if high_impact or not data.reframing_possible_without_new_results else ReviewRecommendation.major_revision,
        )

    if _at_or_below(data.novelty, ReviewAdequacy.insufficient):
        reasons.append("Novelty positioning is insufficient or contradicted by prior work.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
    elif _at_or_below(data.novelty, ReviewAdequacy.weak):
        reasons.append("Weak or poorly positioned novelty requires at least a major revision.")
        allowed = _worse_recommendation(
            allowed,
            ReviewRecommendation.reject if high_impact or not data.reframing_possible_without_new_results else ReviewRecommendation.major_revision,
        )

    if _at_or_below(data.venue_fit, ReviewAdequacy.insufficient):
        reasons.append("The manuscript is fundamentally mismatched to the target venue.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
    elif _at_or_below(data.venue_fit, ReviewAdequacy.weak):
        reasons.append("Venue fit is too weak for acceptance without major reframing.")
        allowed = _worse_recommendation(
            allowed,
            ReviewRecommendation.reject if high_impact or not data.reframing_possible_without_new_results else ReviewRecommendation.major_revision,
        )

    if _at_or_below(data.literature_positioning, ReviewAdequacy.insufficient):
        reasons.append("Literature positioning is incomplete enough to undermine the review recommendation.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)
    elif _at_or_below(data.literature_positioning, ReviewAdequacy.weak):
        reasons.append("Literature comparison remains too weak for anything better than major revision.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if _at_or_below(data.mathematical_correctness, ReviewAdequacy.insufficient):
        reasons.append("Mathematical correctness is insufficient for publication.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
    elif _at_or_below(data.mathematical_correctness, ReviewAdequacy.weak):
        reasons.append("Mathematical issues remain unresolved at a level incompatible with minor revision.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if data.blocking_issue_ids:
        reasons.append("Blocking referee issues remain open.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if data.unresolved_major_issues > 0:
        reasons.append("Unresolved major issues remain in the referee ledger.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if data.unresolved_minor_issues > 0:
        allowed = _worse_recommendation(allowed, ReviewRecommendation.minor_revision)

    if review_ledger is not None:
        consistency_errors.extend(_review_ledger_consistency_errors(data, review_ledger))

    recommendation_valid = _RECOMMENDATION_ORDER.get(data.final_recommendation, 99) >= _RECOMMENDATION_ORDER.get(allowed, 99)
    valid = recommendation_valid and not consistency_errors

    if not recommendation_valid:
        reasons.append(
            f"Proposed recommendation `{data.final_recommendation}` is too favorable; the most positive allowed outcome is `{allowed}`."
        )
    reasons = consistency_errors + reasons

    return RefereeDecisionReport(
        manuscript_path=data.manuscript_path,
        target_journal=data.target_journal,
        proposed_recommendation=data.final_recommendation,
        most_positive_allowed_recommendation=allowed,
        valid=valid,
        reasons=reasons,
        warnings=warnings,
    )
