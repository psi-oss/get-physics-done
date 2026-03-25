from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.core.referee_policy import RefereeDecisionInput
from gpd.mcp.paper.models import (
    ClaimIndex,
    ClaimRecord,
    ClaimType,
    ReviewConfidence,
    ReviewFinding,
    ReviewIssue,
    ReviewIssueSeverity,
    ReviewLedger,
    ReviewRecommendation,
    ReviewStageKind,
    ReviewSupportStatus,
    StageReviewReport,
)
from gpd.mcp.paper.review_artifacts import (
    read_claim_index,
    read_referee_decision,
    read_review_ledger,
    read_stage_review_report,
    write_claim_index,
    write_referee_decision,
    write_review_ledger,
    write_stage_review_report,
)


def test_review_artifact_round_trip(tmp_path: Path) -> None:
    claim_index = ClaimIndex(
        manuscript_path="paper/main.tex",
        manuscript_sha256="a" * 64,
        claims=[
            ClaimRecord(
                claim_id="CLM-001",
                claim_type=ClaimType.significance,
                text="The result has broad impact.",
                artifact_path="paper/main.tex",
                section="Conclusion",
            )
        ],
    )
    stage_report = StageReviewReport(
        stage_id="interestingness",
        stage_kind=ReviewStageKind.interestingness,
        manuscript_path="paper/main.tex",
        manuscript_sha256="a" * 64,
        claims_reviewed=["CLM-001"],
        summary="Impact claim is overstated.",
        strengths=["Mathematics is internally consistent."],
        findings=[
            ReviewFinding(
                issue_id="REF-001",
                claim_ids=["CLM-001"],
                severity=ReviewIssueSeverity.major,
                summary="Broad-impact claim is unsupported.",
                evidence_refs=["paper/main.tex#Conclusion"],
                support_status=ReviewSupportStatus.unsupported,
                blocking=True,
                required_action="Narrow the significance claim to the demonstrated regime.",
            )
        ],
        confidence=ReviewConfidence.high,
        recommendation_ceiling=ReviewRecommendation.major_revision,
    )
    ledger = ReviewLedger(
        manuscript_path="paper/main.tex",
        issues=[
            ReviewIssue(
                issue_id="REF-001",
                opened_by_stage=ReviewStageKind.interestingness,
                severity=ReviewIssueSeverity.major,
                blocking=True,
                claim_ids=["CLM-001"],
                summary="Broad-impact claim is unsupported.",
                required_action="Rewrite the abstract and conclusion.",
            )
        ],
    )
    decision = RefereeDecisionInput(
        manuscript_path="paper/main.tex",
        target_journal="jhep",
        final_recommendation=ReviewRecommendation.major_revision,
        final_confidence=ReviewConfidence.high,
        stage_artifacts=["GPD/review/STAGE-interestingness.json"],
        novelty="adequate",
        significance="weak",
        venue_fit="adequate",
        blocking_issue_ids=["REF-001"],
    )

    claims_path = tmp_path / "CLAIMS.json"
    stage_path = tmp_path / "STAGE-interestingness.json"
    ledger_path = tmp_path / "REVIEW-LEDGER.json"
    decision_path = tmp_path / "REFEREE-DECISION.json"

    write_claim_index(claim_index, claims_path)
    write_stage_review_report(stage_report, stage_path)
    write_review_ledger(ledger, ledger_path)
    write_referee_decision(decision, decision_path)

    assert read_claim_index(claims_path) == claim_index
    assert read_stage_review_report(stage_path) == stage_report
    assert read_review_ledger(ledger_path) == ledger
    assert read_referee_decision(decision_path) == decision


def test_claim_index_rejects_invalid_sha256(tmp_path: Path) -> None:
    claims_path = tmp_path / "CLAIMS.json"
    claims_path.write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "abc123",
                "claims": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_claim_index(claims_path)


def test_claim_index_rejects_uppercase_sha256(tmp_path: Path) -> None:
    claims_path = tmp_path / "CLAIMS.json"
    claims_path.write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "A" * 64,
                "claims": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_claim_index(claims_path)


def test_claim_index_rejects_blank_manuscript_path(tmp_path: Path) -> None:
    claims_path = tmp_path / "CLAIMS.json"
    claims_path.write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": "   ",
                "manuscript_sha256": "a" * 64,
                "claims": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_claim_index(claims_path)


def test_stage_review_report_requires_issue_ids(tmp_path: Path) -> None:
    stage_path = tmp_path / "STAGE-reader.json"
    stage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "reader",
                "stage_kind": "reader",
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "a" * 64,
                "claims_reviewed": ["CLM-001"],
                "summary": "Summary",
                "strengths": [],
                "findings": [
                    {
                        "claim_ids": ["CLM-001"],
                        "severity": "major",
                        "summary": "Missing issue ID.",
                    }
                ],
                "confidence": "medium",
                "recommendation_ceiling": "major_revision",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_stage_review_report(stage_path)


def test_stage_review_report_rejects_blank_manuscript_path(tmp_path: Path) -> None:
    stage_path = tmp_path / "STAGE-reader.json"
    stage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "reader",
                "stage_kind": "reader",
                "manuscript_path": "   ",
                "manuscript_sha256": "a" * 64,
                "claims_reviewed": ["CLM-001"],
                "summary": "Summary",
                "strengths": [],
                "findings": [],
                "confidence": "medium",
                "recommendation_ceiling": "major_revision",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_stage_review_report(stage_path)


def test_stage_review_report_requires_stage_id_to_match_stage_kind(tmp_path: Path) -> None:
    stage_path = tmp_path / "STAGE-reader.json"
    stage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "literature",
                "stage_kind": "reader",
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "a" * 64,
                "claims_reviewed": ["CLM-001"],
                "summary": "Summary",
                "strengths": [],
                "findings": [],
                "confidence": "medium",
                "recommendation_ceiling": "major_revision",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="stage_id must equal stage_kind"):
        read_stage_review_report(stage_path)


def test_review_ledger_rejects_unexpected_extra_fields(tmp_path: Path) -> None:
    ledger_path = tmp_path / "REVIEW-LEDGER.json"
    ledger_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "manuscript_path": "paper/main.tex",
                "issues": [
                    {
                        "issue_id": "REF-001",
                        "opened_by_stage": "physics",
                        "severity": "major",
                        "summary": "A remaining issue.",
                        "status": "open",
                        "unexpected": "boom",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_review_ledger(ledger_path)


def test_review_ledger_rejects_invalid_issue_and_claim_id_formats(tmp_path: Path) -> None:
    ledger_path = tmp_path / "REVIEW-LEDGER.json"
    ledger_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "manuscript_path": "paper/main.tex",
                "issues": [
                    {
                        "issue_id": "ISSUE-001",
                        "opened_by_stage": "physics",
                        "severity": "major",
                        "claim_ids": ["claim-001"],
                        "summary": "A remaining issue.",
                        "status": "open",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_review_ledger(ledger_path)


@pytest.mark.parametrize(
    ("model_cls", "kwargs"),
    [
        (
            ClaimIndex,
            {
                "version": 2,
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "a" * 64,
                "claims": [],
            },
        ),
        (
            StageReviewReport,
            {
                "version": 2,
                "round": 1,
                "stage_id": "reader",
                "stage_kind": ReviewStageKind.reader,
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "a" * 64,
                "claims_reviewed": [],
                "summary": "Summary",
                "strengths": [],
                "findings": [],
                "confidence": ReviewConfidence.medium,
                "recommendation_ceiling": ReviewRecommendation.major_revision,
            },
        ),
        (
            ReviewLedger,
            {
                "version": 2,
                "round": 1,
                "manuscript_path": "paper/main.tex",
                "issues": [],
            },
        ),
    ],
)
def test_review_artifacts_pin_version_to_one(model_cls, kwargs) -> None:
    with pytest.raises(ValidationError):
        model_cls(**kwargs)


@pytest.mark.parametrize(
    ("model_cls", "kwargs"),
    [
        (
            StageReviewReport,
            {
                "version": 1,
                "round": 0,
                "stage_id": "reader",
                "stage_kind": ReviewStageKind.reader,
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "a" * 64,
                "claims_reviewed": [],
                "summary": "Summary",
                "strengths": [],
                "findings": [],
                "confidence": ReviewConfidence.medium,
                "recommendation_ceiling": ReviewRecommendation.major_revision,
            },
        ),
        (
            ReviewLedger,
            {
                "version": 1,
                "round": 0,
                "manuscript_path": "paper/main.tex",
                "issues": [],
            },
        ),
    ],
)
def test_review_artifacts_require_positive_round_numbers(model_cls, kwargs) -> None:
    with pytest.raises(ValidationError):
        model_cls(**kwargs)


def test_read_referee_decision_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    decision_path = tmp_path / "REFEREE-DECISION.json"
    decision_path.write_text(
        json.dumps(
            {
                "manuscript_path": "paper/main.tex",
                "target_journal": "jhep",
                "final_recommendation": "major_revision",
                "unexpected": "boom",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_referee_decision(decision_path)


def test_read_referee_decision_rejects_malformed_blocking_issue_ids(tmp_path: Path) -> None:
    decision_path = tmp_path / "REFEREE-DECISION.json"
    decision_path.write_text(
        json.dumps(
            {
                "manuscript_path": "paper/main.tex",
                "target_journal": "jhep",
                "final_recommendation": "major_revision",
                "blocking_issue_ids": ["REF-001", "not-a-ref"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_referee_decision(decision_path)
