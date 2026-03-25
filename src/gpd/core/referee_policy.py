"""Machine-readable recommendation policy for staged peer review."""

from __future__ import annotations

import json
import posixpath
import re
from collections import Counter
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.mcp.paper.models import (
    ClaimIndex,
    ReviewConfidence,
    ReviewIssueId,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    ReviewLedger,
    ReviewRecommendation,
    StageReviewReport,
)

__all__ = [
    "ReviewAdequacy",
    "RefereeDecisionInput",
    "RefereeDecisionReport",
    "evaluate_referee_decision",
    "validate_stage_review_artifact_file",
    "validate_stage_review_artifact_alignment",
]


class ReviewAdequacy(StrEnum):
    """Qualitative adequacy scale used by the final meta-referee."""

    strong = "strong"
    adequate = "adequate"
    weak = "weak"
    insufficient = "insufficient"


class RefereeDecisionInput(BaseModel):
    """Typed summary of the final staged-review adjudication."""

    model_config = ConfigDict(extra="forbid")

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
    blocking_issue_ids: list[ReviewIssueId] = Field(default_factory=list)


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
_STRICT_STAGE_ARTIFACT_IDS = ("reader", "literature", "math", "physics", "interestingness")
_STRICT_STAGE_ARTIFACT_RE = re.compile(
    r"^STAGE-(?P<stage_id>reader|literature|math|physics|interestingness)(?P<round_suffix>-R(?P<round>\d+))?\.json$"
)
_STRICT_REFEREE_DECISION_FIELDS = tuple(RefereeDecisionInput.model_fields)


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


def _load_review_json_artifact(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{path.as_posix()} does not exist") from exc
    except OSError as exc:
        raise ValueError(f"failed to read {path.as_posix()}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.as_posix()} is not valid JSON: {exc}") from exc


def _format_model_errors(exc: PydanticValidationError, *, label: str) -> str:
    parts: list[str] = []
    for error in exc.errors()[:5]:
        location = ".".join(str(part) for part in error.get("loc", ())) or label
        message = error.get("msg", "validation error")
        parts.append(f"{label}.{location}: {message}")
    return "; ".join(parts) or f"{label} validation failed"


def _canonical_stage_artifact_details(stage_artifact_path: Path) -> tuple[str, str, int] | None:
    match = _STRICT_STAGE_ARTIFACT_RE.fullmatch(stage_artifact_path.name)
    if match is None:
        return None
    round_text = match.group("round")
    round_number = int(round_text) if round_text else 1
    return match.group("stage_id"), match.group("round_suffix") or "", round_number


def _claim_index_path_for_round(stage_artifact_path: Path, *, round_suffix: str) -> Path:
    return stage_artifact_path.with_name(f"CLAIMS{round_suffix}.json")


def _round_suffix_for_round(round_number: int) -> str:
    return "" if round_number <= 1 else f"-R{round_number}"


def _canonical_stage_artifact_name(stage_id: str, round_number: int) -> str:
    return f"STAGE-{stage_id}{_round_suffix_for_round(round_number)}.json"


def _load_claim_index_for_stage_artifact(stage_artifact_path: Path, *, round_suffix: str) -> tuple[ClaimIndex | None, list[str]]:
    claim_index_path = _claim_index_path_for_round(stage_artifact_path, round_suffix=round_suffix)
    if not claim_index_path.exists():
        return None, [f"matching claim index is missing: {claim_index_path.as_posix()}"]

    try:
        payload = _load_review_json_artifact(claim_index_path)
        return ClaimIndex.model_validate(payload), []
    except ValueError as exc:
        return None, [f"matching claim index could not be loaded: {exc}"]
    except PydanticValidationError as exc:
        return None, [
            "matching claim index is invalid: "
            + _format_model_errors(exc, label=claim_index_path.name)
        ]


def validate_stage_review_artifact_alignment(
    stage_report: StageReviewReport,
    *,
    artifact_path: Path,
    claim_index: ClaimIndex | None,
    expected_manuscript_path: str | None = None,
    require_claim_index_error: bool = True,
) -> list[str]:
    """Return semantic alignment errors for a stage-review artifact."""

    details = _canonical_stage_artifact_details(artifact_path)
    round_suffix = details[1] if details is not None else _round_suffix_for_round(stage_report.round)
    errors: list[str] = []

    if details is not None:
        expected_stage_id, _expected_round_suffix, expected_round = details
        if stage_report.stage_id != expected_stage_id:
            errors.append(
                f"{artifact_path.name} stage_id does not match filename ({stage_report.stage_id} != {expected_stage_id})"
            )
        if stage_report.stage_kind.value != expected_stage_id:
            errors.append(
                f"{artifact_path.name} stage_kind does not match filename ({stage_report.stage_kind.value} != {expected_stage_id})"
            )
        if stage_report.round != expected_round:
            errors.append(
                f"{artifact_path.name} round does not match filename suffix ({stage_report.round} != {expected_round})"
            )

    if expected_manuscript_path and _normalize_path_label(stage_report.manuscript_path) != _normalize_path_label(expected_manuscript_path):
        errors.append(f"{artifact_path.name} manuscript_path does not match the referee decision manuscript_path")

    if claim_index is None:
        if not require_claim_index_error:
            return errors
        errors.append(
            f"{artifact_path.name} requires matching {_claim_index_path_for_round(artifact_path, round_suffix=round_suffix).name}"
        )
        return errors

    normalized_stage_path = _normalize_path_label(stage_report.manuscript_path)
    normalized_claim_path = _normalize_path_label(claim_index.manuscript_path)
    if normalized_stage_path != normalized_claim_path:
        errors.append(
            f"{artifact_path.name} manuscript_path does not match the matching claim index ({stage_report.manuscript_path} != {claim_index.manuscript_path})"
        )
    if stage_report.manuscript_sha256 != claim_index.manuscript_sha256:
        errors.append(
            f"{artifact_path.name} manuscript_sha256 does not match the matching claim index ({stage_report.manuscript_sha256} != {claim_index.manuscript_sha256})"
        )

    claim_ids = [claim.claim_id for claim in claim_index.claims]
    duplicate_claim_ids = sorted(claim_id for claim_id, count in Counter(claim_ids).items() if count > 1)
    if duplicate_claim_ids:
        errors.append(
            "matching claim index contains duplicate claim IDs: " + ", ".join(duplicate_claim_ids)
        )

    known_claim_ids = set(claim_ids)
    unknown_claims_reviewed = sorted(claim_id for claim_id in set(stage_report.claims_reviewed) if claim_id not in known_claim_ids)
    if unknown_claims_reviewed:
        errors.append(
            f"{artifact_path.name} claims_reviewed not found in the matching claim index: "
            + ", ".join(unknown_claims_reviewed)
        )

    finding_claim_ids = sorted(
        {
            claim_id
            for finding in stage_report.findings
            for claim_id in finding.claim_ids
            if claim_id not in known_claim_ids
        }
    )
    if finding_claim_ids:
        errors.append(
            f"{artifact_path.name} finding claim_ids not found in the matching claim index: "
            + ", ".join(finding_claim_ids)
        )

    return errors


def _strict_stage_artifact_errors(stage_artifacts: list[str]) -> list[str]:
    """Return strict-mode errors for the canonical staged peer-review artifact set."""

    seen_stage_ids: set[str] = set()
    round_suffixes: set[str] = set()
    invalid_stage_artifacts: list[str] = []

    for artifact_path in stage_artifacts:
        match = _STRICT_STAGE_ARTIFACT_RE.fullmatch(Path(artifact_path.strip()).name)
        if match is None:
            invalid_stage_artifacts.append(artifact_path)
            continue
        seen_stage_ids.add(match.group("stage_id"))
        round_suffixes.add(match.group("round_suffix") or "")

    missing_stage_ids = [stage_id for stage_id in _STRICT_STAGE_ARTIFACT_IDS if stage_id not in seen_stage_ids]
    errors: list[str] = []
    if missing_stage_ids:
        errors.append(
            "Strict staged peer review requires the canonical five specialist stage artifacts: missing "
            + ", ".join(f"STAGE-{stage_id}.json" for stage_id in missing_stage_ids)
        )
    if invalid_stage_artifacts:
        errors.append(
            "Strict staged peer review rejects noncanonical stage artifacts: "
            + ", ".join(invalid_stage_artifacts)
        )
    if len(round_suffixes) > 1:
        errors.append("Strict staged peer review requires all specialist stage artifacts to use the same round suffix.")
    return errors


def _strict_referee_decision_field_errors(data: RefereeDecisionInput) -> list[str]:
    """Return strict-mode errors for omitted referee-decision policy inputs."""

    missing_fields = [field_name for field_name in _STRICT_REFEREE_DECISION_FIELDS if field_name not in data.model_fields_set]
    if not missing_fields:
        return []
    return [
        "Strict staged peer review requires explicit referee-decision fields; omitted defaults are not allowed: "
        + ", ".join(missing_fields)
    ]


def _normalize_path_label(path_text: str) -> str:
    normalized = path_text.strip().replace("\\", "/")
    if not normalized:
        return ""
    return posixpath.normpath(normalized)


def _review_ledger_consistency_errors(data: RefereeDecisionInput, review_ledger: ReviewLedger) -> list[str]:
    errors: list[str] = []

    normalized_decision_path = _normalize_path_label(data.manuscript_path) if data.manuscript_path.strip() else ""
    normalized_ledger_path = _normalize_path_label(review_ledger.manuscript_path) if review_ledger.manuscript_path.strip() else ""
    if not normalized_ledger_path:
        errors.append("review ledger manuscript_path must be non-empty")
    if normalized_decision_path and normalized_ledger_path and normalized_decision_path != normalized_ledger_path:
        errors.append("referee decision manuscript_path does not match review ledger manuscript_path")

    mismatched_round_artifacts: list[str] = []
    for artifact_name in data.stage_artifacts:
        details = _canonical_stage_artifact_details(Path(artifact_name.strip()))
        if details is None:
            continue
        _stage_id, _round_suffix, artifact_round = details
        if artifact_round != review_ledger.round:
            mismatched_round_artifacts.append(f"{artifact_name} (round {artifact_round})")
    if mismatched_round_artifacts:
        errors.append(
            "stage_artifacts round does not match review ledger round "
            f"({review_ledger.round}): " + ", ".join(mismatched_round_artifacts)
        )

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


def _strict_stage_artifact_consistency_errors(
    stage_artifacts: list[str],
    *,
    project_root: Path | None,
    expected_manuscript_path: str | None,
) -> list[str]:
    if project_root is None:
        return []

    errors: list[str] = []
    for artifact_name in stage_artifacts:
        artifact_path = Path(artifact_name)
        if not artifact_path.is_absolute():
            artifact_path = project_root / artifact_path

        if not artifact_path.exists():
            continue

        errors.extend(
            validate_stage_review_artifact_file(
                artifact_path,
                expected_manuscript_path=expected_manuscript_path,
            )
        )

    return errors


def validate_stage_review_artifact_file(
    artifact_path: Path,
    *,
    expected_manuscript_path: str | None = None,
) -> list[str]:
    """Return semantic validation errors for a stage-review file."""

    details = _canonical_stage_artifact_details(artifact_path)
    errors: list[str] = []
    try:
        payload = _load_review_json_artifact(artifact_path)
        stage_report = StageReviewReport.model_validate(payload)
    except ValueError as exc:
        return [f"{artifact_path.name} could not be loaded: {exc}"]
    except PydanticValidationError as exc:
        return [
            f"{artifact_path.name} is not a valid StageReviewReport: "
            + _format_model_errors(exc, label=artifact_path.name)
        ]

    round_suffix = details[1] if details is not None else _round_suffix_for_round(stage_report.round)
    if details is None:
        errors.append(
            f"{artifact_path.name} must use canonical filename "
            f"{_canonical_stage_artifact_name(stage_report.stage_id, stage_report.round)}"
        )

    claim_index, claim_index_errors = _load_claim_index_for_stage_artifact(
        artifact_path,
        round_suffix=round_suffix,
    )
    errors.extend(claim_index_errors)
    errors.extend(
        validate_stage_review_artifact_alignment(
            stage_report,
            artifact_path=artifact_path,
            claim_index=claim_index,
            expected_manuscript_path=expected_manuscript_path,
            require_claim_index_error=not claim_index_errors,
        )
    )
    return errors


def evaluate_referee_decision(
    data: RefereeDecisionInput,
    *,
    strict: bool = False,
    require_explicit_inputs: bool = False,
    review_ledger: ReviewLedger | None = None,
    project_root: Path | None = None,
) -> RefereeDecisionReport:
    """Evaluate whether a final recommendation is consistent with hard referee gates."""

    allowed = ReviewRecommendation.accept
    reasons: list[str] = []
    warnings: list[str] = []
    high_impact = _is_high_impact(data.target_journal)
    consistency_errors: list[str] = []

    if strict:
        if not data.manuscript_path.strip():
            consistency_errors.append(
                "Strict staged peer review requires a non-empty manuscript_path in the referee decision."
            )
            allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)
        if require_explicit_inputs:
            strict_field_errors = _strict_referee_decision_field_errors(data)
            if strict_field_errors:
                consistency_errors.extend(strict_field_errors)
                allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)
        strict_stage_errors = _strict_stage_artifact_errors(data.stage_artifacts)
        if strict_stage_errors:
            consistency_errors.extend(strict_stage_errors)
            allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)
        strict_stage_consistency_errors = _strict_stage_artifact_consistency_errors(
            data.stage_artifacts,
            project_root=project_root,
            expected_manuscript_path=data.manuscript_path.strip() or None,
        )
        if strict_stage_consistency_errors:
            consistency_errors.extend(strict_stage_consistency_errors)
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
