from __future__ import annotations

from pathlib import Path

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
    ReviewPanelBundle,
    ReviewRecommendation,
    ReviewStageKind,
    ReviewSupportStatus,
    StageReviewReport,
)
from gpd.mcp.paper.review_artifacts import (
    read_claim_index,
    read_referee_decision,
    read_review_ledger,
    read_review_panel_bundle,
    read_stage_review_report,
    write_claim_index,
    write_referee_decision,
    write_review_ledger,
    write_review_panel_bundle,
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
        stage_artifacts=[".gpd/review/STAGE-interestingness.json"],
        novelty="adequate",
        significance="weak",
        venue_fit="adequate",
        blocking_issue_ids=["REF-001"],
    )
    bundle = ReviewPanelBundle(
        manuscript_path="paper/main.tex",
        claim_index_path=".gpd/review/CLAIMS.json",
        stage_reports=[".gpd/review/STAGE-interestingness.json"],
        review_ledger_path=".gpd/review/REVIEW-LEDGER.json",
        decision_path=".gpd/review/REFEREE-DECISION.json",
        final_recommendation=ReviewRecommendation.major_revision,
        final_confidence=ReviewConfidence.high,
        final_report_path=".gpd/REFEREE-REPORT.md",
        final_report_tex_path=".gpd/REFEREE-REPORT.tex",
    )

    claims_path = tmp_path / "CLAIMS.json"
    stage_path = tmp_path / "STAGE-interestingness.json"
    ledger_path = tmp_path / "REVIEW-LEDGER.json"
    decision_path = tmp_path / "REFEREE-DECISION.json"
    bundle_path = tmp_path / "PANEL-BUNDLE.json"

    write_claim_index(claim_index, claims_path)
    write_stage_review_report(stage_report, stage_path)
    write_review_ledger(ledger, ledger_path)
    write_referee_decision(decision, decision_path)
    write_review_panel_bundle(bundle, bundle_path)

    assert read_claim_index(claims_path) == claim_index
    assert read_stage_review_report(stage_path) == stage_report
    assert read_review_ledger(ledger_path) == ledger
    assert read_referee_decision(decision_path) == decision
    assert read_review_panel_bundle(bundle_path) == bundle
