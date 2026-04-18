"""Machine-readable recommendation policy for staged peer review."""

from __future__ import annotations

import json
import re
from collections import Counter
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pydantic import ValidationError as PydanticValidationError

from gpd.core.publication_review_paths import normalize_review_path_label, review_artifact_round
from gpd.mcp.paper.models import (
    ClaimIndex,
    ProofAuditStatus,
    ReviewConfidence,
    ReviewIssueId,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    ReviewLedger,
    ReviewRecommendation,
    ReviewStageKind,
    StageReviewReport,
)

__all__ = [
    "ReviewAdequacy",
    "RefereeDecisionInput",
    "RefereeDecisionReport",
    "evaluate_referee_decision",
    "validate_stage_review_artifact_payload",
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
    central_claims_supported: StrictBool = True
    claim_scope_proportionate_to_evidence: StrictBool = True
    physical_assumptions_justified: StrictBool = True
    proof_audit_coverage_complete: StrictBool = False
    theorem_proof_alignment_adequate: StrictBool = False
    unsupported_claims_are_central: StrictBool = False
    reframing_possible_without_new_results: StrictBool = True
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
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.as_posix()} is not valid UTF-8 JSON: {exc}") from exc
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
    round_details = review_artifact_round(stage_artifact_path, pattern=_STRICT_STAGE_ARTIFACT_RE)
    if round_details is None:
        return None
    round_number, round_suffix = round_details
    return match.group("stage_id"), round_suffix, round_number


def _claim_index_path_for_round(stage_artifact_path: Path, *, round_suffix: str) -> Path:
    return stage_artifact_path.with_name(f"CLAIMS{round_suffix}.json")


def _round_suffix_for_round(round_number: int) -> str:
    return "" if round_number <= 1 else f"-R{round_number}"


def _canonical_stage_artifact_name(stage_id: str, round_number: int) -> str:
    return f"STAGE-{stage_id}{_round_suffix_for_round(round_number)}.json"


def _load_claim_index_for_stage_artifact(
    stage_artifact_path: Path, *, round_suffix: str
) -> tuple[ClaimIndex | None, list[str]]:
    claim_index_path = _claim_index_path_for_round(stage_artifact_path, round_suffix=round_suffix)
    if not claim_index_path.exists():
        return None, [f"matching claim index is missing: {claim_index_path.as_posix()}"]

    try:
        payload = _load_review_json_artifact(claim_index_path)
        return ClaimIndex.model_validate(payload), []
    except ValueError as exc:
        return None, [f"matching claim index could not be loaded: {exc}"]
    except PydanticValidationError as exc:
        return None, ["matching claim index is invalid: " + _format_model_errors(exc, label=claim_index_path.name)]


def validate_stage_review_artifact_alignment(
    stage_report: StageReviewReport,
    *,
    artifact_path: Path,
    claim_index: ClaimIndex | None,
    expected_manuscript_path: str | None = None,
    expected_manuscript_sha256: str | None = None,
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

    if expected_manuscript_path and normalize_review_path_label(
        stage_report.manuscript_path
    ) != normalize_review_path_label(expected_manuscript_path):
        errors.append(f"{artifact_path.name} manuscript_path does not match the referee decision manuscript_path")
    if expected_manuscript_sha256 and stage_report.manuscript_sha256 != expected_manuscript_sha256:
        errors.append(f"{artifact_path.name} manuscript_sha256 does not match the active manuscript snapshot")

    if claim_index is None:
        if not require_claim_index_error:
            return errors
        errors.append(
            f"{artifact_path.name} requires matching {_claim_index_path_for_round(artifact_path, round_suffix=round_suffix).name}"
        )
        return errors

    normalized_stage_path = normalize_review_path_label(stage_report.manuscript_path)
    normalized_claim_path = normalize_review_path_label(claim_index.manuscript_path)
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
        errors.append("matching claim index contains duplicate claim IDs: " + ", ".join(duplicate_claim_ids))

    known_claim_ids = set(claim_ids)
    unknown_claims_reviewed = sorted(
        claim_id for claim_id in set(stage_report.claims_reviewed) if claim_id not in known_claim_ids
    )
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

    proof_audit_claim_ids = [audit.claim_id for audit in stage_report.proof_audits]
    unknown_proof_audit_claim_ids = sorted(
        claim_id for claim_id in set(proof_audit_claim_ids) if claim_id not in known_claim_ids
    )
    if unknown_proof_audit_claim_ids:
        errors.append(
            f"{artifact_path.name} proof_audits claim_id values not found in the matching claim index: "
            + ", ".join(unknown_proof_audit_claim_ids)
        )

    proof_audit_claim_ids_not_reviewed = sorted(
        claim_id for claim_id in set(proof_audit_claim_ids) if claim_id not in set(stage_report.claims_reviewed)
    )
    if proof_audit_claim_ids_not_reviewed:
        errors.append(
            f"{artifact_path.name} proof_audits must only reference claims_reviewed entries: "
            + ", ".join(proof_audit_claim_ids_not_reviewed)
        )

    if stage_report.stage_kind == ReviewStageKind.math:
        claims_by_id = {claim.claim_id: claim for claim in claim_index.claims}
        theorem_bearing_claim_ids = {claim.claim_id for claim in claim_index.claims if claim.theorem_bearing}
        unreviewed_theorem_claim_ids = sorted(
            claim_id for claim_id in theorem_bearing_claim_ids if claim_id not in set(stage_report.claims_reviewed)
        )
        if unreviewed_theorem_claim_ids:
            errors.append(
                f"{artifact_path.name} theorem-bearing claims must appear in claims_reviewed: "
                + ", ".join(unreviewed_theorem_claim_ids)
            )

        missing_proof_audits = sorted(
            claim_id for claim_id in theorem_bearing_claim_ids if claim_id not in set(proof_audit_claim_ids)
        )
        if missing_proof_audits:
            errors.append(
                f"{artifact_path.name} theorem-bearing claims must have proof_audits: "
                + ", ".join(missing_proof_audits)
            )

        not_applicable_theorem_audits = sorted(
            audit.claim_id
            for audit in stage_report.proof_audits
            if audit.claim_id in theorem_bearing_claim_ids and audit.alignment_status == ProofAuditStatus.not_applicable
        )
        if not_applicable_theorem_audits:
            errors.append(
                f"{artifact_path.name} theorem-bearing proof_audits cannot use alignment_status `not_applicable`: "
                + ", ".join(not_applicable_theorem_audits)
            )

        for audit in stage_report.proof_audits:
            if audit.claim_id not in theorem_bearing_claim_ids:
                continue
            claim = claims_by_id.get(audit.claim_id)
            if claim is None:
                continue
            if not audit.proof_locations:
                errors.append(
                    f"{artifact_path.name} theorem-bearing proof_audit {audit.claim_id} must include proof_locations"
                )
            missing_checked_assumptions = sorted(
                set(claim.theorem_assumptions) - set(audit.theorem_assumptions_checked)
            )
            if missing_checked_assumptions and audit.alignment_status == ProofAuditStatus.aligned:
                errors.append(
                    f"{artifact_path.name} aligned proof_audit {audit.claim_id} is missing theorem_assumptions_checked coverage: "
                    + ", ".join(missing_checked_assumptions)
                )
            missing_checked_parameters = sorted(set(claim.theorem_parameters) - set(audit.theorem_parameters_checked))
            if missing_checked_parameters and audit.alignment_status == ProofAuditStatus.aligned:
                errors.append(
                    f"{artifact_path.name} aligned proof_audit {audit.claim_id} is missing theorem_parameters_checked coverage: "
                    + ", ".join(missing_checked_parameters)
                )

        theorem_proof_gap_claim_ids = sorted(
            audit.claim_id
            for audit in stage_report.proof_audits
            if audit.alignment_status in {ProofAuditStatus.partially_aligned, ProofAuditStatus.misaligned}
            or audit.uncovered_assumptions
            or audit.uncovered_parameters
            or audit.coverage_gaps
        )
        if theorem_proof_gap_claim_ids and stage_report.recommendation_ceiling in {
            ReviewRecommendation.accept,
            ReviewRecommendation.minor_revision,
        }:
            errors.append(
                f"{artifact_path.name} recommendation_ceiling cannot exceed `major_revision` when proof_audits report theorem-to-proof gaps: "
                + ", ".join(theorem_proof_gap_claim_ids)
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
            "Strict staged peer review rejects noncanonical stage artifacts: " + ", ".join(invalid_stage_artifacts)
        )
    if len(round_suffixes) > 1:
        errors.append("Strict staged peer review requires all specialist stage artifacts to use the same round suffix.")
    return errors


def _strict_referee_decision_field_errors(data: RefereeDecisionInput) -> list[str]:
    """Return strict-mode errors for omitted referee-decision policy inputs."""

    missing_fields = [
        field_name for field_name in _STRICT_REFEREE_DECISION_FIELDS if field_name not in data.model_fields_set
    ]
    if not missing_fields:
        return []
    return [
        "Strict staged peer review requires explicit referee-decision fields; omitted defaults are not allowed: "
        + ", ".join(missing_fields)
    ]


def _review_ledger_consistency_errors(data: RefereeDecisionInput, review_ledger: ReviewLedger) -> list[str]:
    errors: list[str] = []

    normalized_decision_path = normalize_review_path_label(data.manuscript_path) if data.manuscript_path.strip() else ""
    normalized_ledger_path = (
        normalize_review_path_label(review_ledger.manuscript_path) if review_ledger.manuscript_path.strip() else ""
    )
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
    missing_blocking_issue_ids = [
        issue_id for issue_id in unresolved_blocking_issue_ids if issue_id not in blocking_issue_ids
    ]
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
    expected_manuscript_sha256: str | None = None,
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
                expected_manuscript_sha256=expected_manuscript_sha256,
            )
        )

    return errors


def _strict_proof_redteam_errors(
    data: RefereeDecisionInput,
    *,
    project_root: Path | None,
) -> list[str]:
    if project_root is None:
        return []

    math_artifact_name = next(
        (
            artifact_name
            for artifact_name in data.stage_artifacts
            if Path(artifact_name.strip()).name.startswith("STAGE-math")
        ),
        None,
    )
    if math_artifact_name is None:
        return []

    math_artifact_path = Path(math_artifact_name)
    if not math_artifact_path.is_absolute():
        math_artifact_path = project_root / math_artifact_path
    if not math_artifact_path.exists():
        return []

    details = _canonical_stage_artifact_details(math_artifact_path)
    if details is None:
        return []
    _stage_id, round_suffix, round_number = details

    try:
        stage_report = StageReviewReport.model_validate(_load_review_json_artifact(math_artifact_path))
    except (ValueError, PydanticValidationError):
        return []

    claim_index_path = math_artifact_path.with_name(f"CLAIMS{round_suffix}.json")
    try:
        claim_index = ClaimIndex.model_validate(_load_review_json_artifact(claim_index_path))
    except (ValueError, PydanticValidationError):
        return []

    theorem_claim_ids = sorted(claim.claim_id for claim in claim_index.claims if claim.theorem_bearing)
    if not theorem_claim_ids:
        return []

    proof_redteam_path = math_artifact_path.with_name(f"PROOF-REDTEAM{round_suffix}.md")
    errors: list[str] = []
    if not proof_redteam_path.exists():
        errors.append(
            f"strict referee validation requires {proof_redteam_path.name} for theorem-bearing manuscript review"
        )
        actual_proof_audit_coverage_complete = False
        actual_theorem_proof_alignment_adequate = False
    else:
        expected_proof_artifact_paths = sorted(
            {
                claim.artifact_path
                for claim in claim_index.claims
                if claim.claim_id in theorem_claim_ids and claim.artifact_path.strip()
            }
        )
        if data.manuscript_path.strip() and data.manuscript_path.strip() not in expected_proof_artifact_paths:
            expected_proof_artifact_paths.append(data.manuscript_path.strip())
        from gpd.core.proof_review import _read_proof_redteam_status

        proof_redteam_status, proof_redteam_error = _read_proof_redteam_status(
            proof_redteam_path,
            project_root=project_root,
            expected_manuscript_path=data.manuscript_path.strip() or None,
            expected_manuscript_sha256=stage_report.manuscript_sha256,
            expected_round=round_number,
            expected_claim_ids=tuple(theorem_claim_ids),
            expected_proof_artifact_paths=tuple(expected_proof_artifact_paths),
        )
        if proof_redteam_error is not None:
            errors.append(f"{proof_redteam_path.name} is invalid: {proof_redteam_error}")
        elif proof_redteam_status != "passed":
            errors.append(f"{proof_redteam_path.name} must report `status: passed` for theorem-bearing review")

        theorem_audits = [audit for audit in stage_report.proof_audits if audit.claim_id in theorem_claim_ids]
        actual_proof_audit_coverage_complete = len(theorem_audits) == len(theorem_claim_ids) and all(
            not audit.uncovered_assumptions and not audit.uncovered_parameters and not audit.coverage_gaps
            for audit in theorem_audits
        )
        actual_theorem_proof_alignment_adequate = (
            proof_redteam_error is None
            and proof_redteam_status == "passed"
            and len(theorem_audits) == len(theorem_claim_ids)
            and all(audit.alignment_status == ProofAuditStatus.aligned for audit in theorem_audits)
        )

    if data.proof_audit_coverage_complete and not actual_proof_audit_coverage_complete:
        errors.append(
            "referee decision sets proof_audit_coverage_complete=true without complete theorem-proof coverage"
        )
    if data.theorem_proof_alignment_adequate and not actual_theorem_proof_alignment_adequate:
        errors.append(
            "referee decision sets theorem_proof_alignment_adequate=true without a passed proof redteam and aligned theorem audits"
        )

    return errors


def validate_stage_review_artifact_file(
    artifact_path: Path,
    *,
    expected_manuscript_path: str | None = None,
    expected_manuscript_sha256: str | None = None,
) -> list[str]:
    """Return semantic validation errors for a stage-review file."""

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

    return validate_stage_review_artifact_payload(
        stage_report,
        artifact_path=artifact_path,
        expected_manuscript_path=expected_manuscript_path,
        expected_manuscript_sha256=expected_manuscript_sha256,
    )


def validate_stage_review_artifact_payload(
    stage_report: StageReviewReport,
    *,
    artifact_path: Path,
    expected_manuscript_path: str | None = None,
    expected_manuscript_sha256: str | None = None,
) -> list[str]:
    """Return semantic validation errors for one typed stage-review artifact."""

    details = _canonical_stage_artifact_details(artifact_path)
    errors: list[str] = []
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
            expected_manuscript_sha256=expected_manuscript_sha256,
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
    expected_manuscript_sha256: str | None = None,
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
            expected_manuscript_sha256=expected_manuscript_sha256,
        )
        if strict_stage_consistency_errors:
            consistency_errors.extend(strict_stage_consistency_errors)
            allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)
        strict_proof_redteam_errors = _strict_proof_redteam_errors(
            data,
            project_root=project_root,
        )
        if strict_proof_redteam_errors:
            consistency_errors.extend(strict_proof_redteam_errors)
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
            reasons.append(
                "Physical assumptions adjacent to the main claims are unjustified and not salvageable by reframing alone."
            )
            allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
        else:
            reasons.append(
                "Physical assumptions adjacent to the mathematics require substantive justification or restriction."
            )
            allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if not data.proof_audit_coverage_complete:
        reasons.append("Central theorem-bearing claims are missing explicit proof-audit coverage.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.major_revision)

    if not data.theorem_proof_alignment_adequate:
        if (
            data.unsupported_claims_are_central
            or not data.central_claims_supported
            or not data.reframing_possible_without_new_results
        ):
            reasons.append("Theorem statements and proofs are misaligned on explicit assumptions or parameters.")
            allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
        else:
            reasons.append("Theorem statements and proofs are not yet aligned on explicit assumptions or parameters.")
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
            ReviewRecommendation.reject
            if high_impact or not data.reframing_possible_without_new_results
            else ReviewRecommendation.major_revision,
        )

    if _at_or_below(data.novelty, ReviewAdequacy.insufficient):
        reasons.append("Novelty positioning is insufficient or contradicted by prior work.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
    elif _at_or_below(data.novelty, ReviewAdequacy.weak):
        reasons.append("Weak or poorly positioned novelty requires at least a major revision.")
        allowed = _worse_recommendation(
            allowed,
            ReviewRecommendation.reject
            if high_impact or not data.reframing_possible_without_new_results
            else ReviewRecommendation.major_revision,
        )

    if _at_or_below(data.venue_fit, ReviewAdequacy.insufficient):
        reasons.append("The manuscript is fundamentally mismatched to the target venue.")
        allowed = _worse_recommendation(allowed, ReviewRecommendation.reject)
    elif _at_or_below(data.venue_fit, ReviewAdequacy.weak):
        reasons.append("Venue fit is too weak for acceptance without major reframing.")
        allowed = _worse_recommendation(
            allowed,
            ReviewRecommendation.reject
            if high_impact or not data.reframing_possible_without_new_results
            else ReviewRecommendation.major_revision,
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

    recommendation_valid = _RECOMMENDATION_ORDER.get(data.final_recommendation, 99) >= _RECOMMENDATION_ORDER.get(
        allowed, 99
    )
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
