from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.referee_policy import RefereeDecisionInput, ReviewAdequacy, evaluate_referee_decision
from gpd.mcp.paper.models import (
    ClaimIndex,
    ClaimRecord,
    ClaimType,
    ReviewConfidence,
    ReviewFinding,
    ReviewIssueSeverity,
    ReviewLedger,
    ReviewRecommendation,
    ReviewStageKind,
    StageReviewReport,
)

runner = CliRunner()
CANONICAL_STAGE_ARTIFACTS = [
    "GPD/review/STAGE-reader.json",
    "GPD/review/STAGE-literature.json",
    "GPD/review/STAGE-math.json",
    "GPD/review/STAGE-physics.json",
    "GPD/review/STAGE-interestingness.json",
]
REVIEW_STAGE_ORDER = (
    ReviewStageKind.reader,
    ReviewStageKind.literature,
    ReviewStageKind.math,
    ReviewStageKind.physics,
    ReviewStageKind.interestingness,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_claim_index(
    review_dir: Path,
    *,
    manuscript_path: str,
    manuscript_sha256: str = "a" * 64,
    round_suffix: str = "",
) -> None:
    claim_index = ClaimIndex(
        manuscript_path=manuscript_path,
        manuscript_sha256=manuscript_sha256,
        claims=[
            ClaimRecord(
                claim_id="CLM-001",
                claim_type=ClaimType.main_result,
                text="The manuscript makes one main claim.",
                artifact_path=manuscript_path,
                section="Conclusion",
            )
        ],
    )
    _write_json(review_dir / f"CLAIMS{round_suffix}.json", claim_index.model_dump(mode="json"))


def _write_stage_review_report_artifact(
    review_dir: Path,
    *,
    stage_kind: ReviewStageKind,
    manuscript_path: str,
    round_number: int = 1,
    manuscript_sha256: str = "a" * 64,
) -> None:
    round_suffix = "" if round_number == 1 else f"-R{round_number}"
    stage_report = StageReviewReport(
        version=1,
        round=round_number,
        stage_id=stage_kind.value,
        stage_kind=stage_kind,
        manuscript_path=manuscript_path,
        manuscript_sha256=manuscript_sha256,
        claims_reviewed=["CLM-001"],
        summary=f"{stage_kind.value} review summary.",
        strengths=["The staged artifact is aligned."],
        findings=[
            ReviewFinding(
                issue_id="REF-001",
                claim_ids=["CLM-001"],
                severity=ReviewIssueSeverity.minor,
                summary="Minor refinement suggested.",
                evidence_refs=[f"{manuscript_path}#Conclusion"],
            )
        ],
        confidence=ReviewConfidence.medium,
        recommendation_ceiling=ReviewRecommendation.major_revision,
    )
    _write_json(
        review_dir / f"STAGE-{stage_kind.value}{round_suffix}.json",
        stage_report.model_dump(mode="json"),
    )


def _write_canonical_stage_artifacts(project_root: Path, *, manuscript_path: str = "paper/main.tex", round_number: int = 1) -> None:
    review_dir = project_root / "GPD" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    round_suffix = "" if round_number == 1 else f"-R{round_number}"
    _write_claim_index(review_dir, manuscript_path=manuscript_path, round_suffix=round_suffix)
    for stage_kind in REVIEW_STAGE_ORDER:
        _write_stage_review_report_artifact(
            review_dir,
            stage_kind=stage_kind,
            manuscript_path=manuscript_path,
            round_number=round_number,
        )


def test_validate_review_claim_index_accepts_canonical_payload(tmp_path: Path) -> None:
    claim_index_path = tmp_path / "CLAIMS.json"
    claim_index = ClaimIndex(
        manuscript_path="paper/main.tex",
        manuscript_sha256="a" * 64,
        claims=[
            ClaimRecord(
                claim_id="CLM-001",
                claim_type=ClaimType.significance,
                text="The result has broad significance.",
                artifact_path="paper/main.tex",
                section="Conclusion",
            )
        ],
    )
    _write_json(claim_index_path, claim_index.model_dump(mode="json"))

    result = runner.invoke(app, ["--raw", "validate", "review-claim-index", str(claim_index_path)], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["claims"][0]["claim_id"] == "CLM-001"
    assert payload["claims"][0]["claim_type"] == "significance"


def test_validate_review_claim_index_reports_required_field_errors(tmp_path: Path) -> None:
    claim_index_path = tmp_path / "CLAIMS.json"
    claim_index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": "paper/main.tex",
                "claims": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "review-claim-index", str(claim_index_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "review-claim-index.manuscript_sha256 is required" in payload["error"]
    assert "references/publication/peer-review-panel.md" in payload["error"]


def test_validate_review_claim_index_rejects_blank_manuscript_path(tmp_path: Path) -> None:
    claim_index_path = tmp_path / "CLAIMS.json"
    claim_index_path.write_text(
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

    result = runner.invoke(app, ["--raw", "validate", "review-claim-index", str(claim_index_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "review-claim-index.manuscript_path" in payload["error"]


def test_validate_review_stage_report_accepts_canonical_payload(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "STAGE-reader.json"
    _write_claim_index(tmp_path, manuscript_path="paper/main.tex")
    stage_report = StageReviewReport(
        version=1,
        round=1,
        stage_id=ReviewStageKind.reader.value,
        stage_kind=ReviewStageKind.reader,
        manuscript_path="paper/main.tex",
        manuscript_sha256="a" * 64,
        claims_reviewed=["CLM-001"],
        summary="The manuscript claims are clearly extracted.",
        strengths=["The narrative is internally coherent."],
        findings=[
            ReviewFinding(
                issue_id="REF-001",
                claim_ids=["CLM-001"],
                severity=ReviewIssueSeverity.major,
                summary="The main claim is overstated.",
                evidence_refs=["paper/main.tex#Conclusion"],
            )
        ],
        confidence=ReviewConfidence.medium,
        recommendation_ceiling=ReviewRecommendation.major_revision,
    )
    _write_json(stage_report_path, stage_report.model_dump(mode="json"))

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["stage_id"] == "reader"
    assert payload["stage_kind"] == "reader"
    assert payload["recommendation_ceiling"] == "major_revision"


def test_validate_review_stage_report_rejects_noncanonical_filename(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "reader-output.json"
    _write_claim_index(tmp_path, manuscript_path="paper/main.tex")
    stage_report = StageReviewReport(
        version=1,
        round=1,
        stage_id=ReviewStageKind.reader.value,
        stage_kind=ReviewStageKind.reader,
        manuscript_path="paper/main.tex",
        manuscript_sha256="a" * 64,
        claims_reviewed=["CLM-001"],
        summary="The manuscript claims are clearly extracted.",
        strengths=[],
        findings=[],
        confidence=ReviewConfidence.medium,
        recommendation_ceiling=ReviewRecommendation.major_revision,
    )
    _write_json(stage_report_path, stage_report.model_dump(mode="json"))

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "must use canonical filename STAGE-reader.json" in payload["error"]


def test_validate_review_stage_report_rejects_unknown_claim_ids_against_matching_claim_index(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "STAGE-reader.json"
    _write_claim_index(tmp_path, manuscript_path="paper/main.tex")
    stage_report = StageReviewReport(
        version=1,
        round=1,
        stage_id=ReviewStageKind.reader.value,
        stage_kind=ReviewStageKind.reader,
        manuscript_path="paper/main.tex",
        manuscript_sha256="a" * 64,
        claims_reviewed=["CLM-404"],
        summary="The manuscript claims are clearly extracted.",
        strengths=[],
        findings=[],
        confidence=ReviewConfidence.medium,
        recommendation_ceiling=ReviewRecommendation.major_revision,
    )
    _write_json(stage_report_path, stage_report.model_dump(mode="json"))

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "claims_reviewed not found in the matching claim index" in payload["error"]


def test_validate_review_stage_report_rejects_filename_round_mismatch(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "STAGE-reader-R2.json"
    _write_claim_index(tmp_path, manuscript_path="paper/main.tex", round_suffix="-R2")
    stage_report = StageReviewReport(
        version=1,
        round=1,
        stage_id=ReviewStageKind.reader.value,
        stage_kind=ReviewStageKind.reader,
        manuscript_path="paper/main.tex",
        manuscript_sha256="a" * 64,
        claims_reviewed=["CLM-001"],
        summary="The manuscript claims are clearly extracted.",
        strengths=[],
        findings=[],
        confidence=ReviewConfidence.medium,
        recommendation_ceiling=ReviewRecommendation.major_revision,
    )
    _write_json(stage_report_path, stage_report.model_dump(mode="json"))

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "round does not match filename suffix" in payload["error"]


def test_validate_review_stage_report_rejects_uppercase_sha256(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "STAGE-reader.json"
    _write_claim_index(tmp_path, manuscript_path="paper/main.tex", manuscript_sha256="a" * 64)
    stage_report_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "reader",
                "stage_kind": "reader",
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "A" * 64,
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

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "review-stage-report.manuscript_sha256" in payload["error"]


def test_validate_review_stage_report_reports_required_field_errors(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "STAGE-reader.json"
    stage_report_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "reader",
                "stage_kind": "reader",
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "a" * 64,
                "strengths": [],
                "findings": [],
                "confidence": "medium",
                "recommendation_ceiling": "major_revision",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "review-stage-report.summary is required" in payload["error"]
    assert "references/publication/peer-review-panel.md" in payload["error"]


def test_validate_review_stage_report_rejects_blank_manuscript_path(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "STAGE-reader.json"
    _write_claim_index(tmp_path, manuscript_path="paper/main.tex")
    stage_report_path.write_text(
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

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "review-stage-report.manuscript_path" in payload["error"]


def test_validate_review_stage_report_reports_stage_kind_mismatch(tmp_path: Path) -> None:
    stage_report_path = tmp_path / "STAGE-reader.json"
    stage_report_path.write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "reader",
                "stage_kind": "literature",
                "manuscript_path": "paper/main.tex",
                "manuscript_sha256": "a" * 64,
                "claims_reviewed": [],
                "summary": "The manuscript claims are clearly extracted.",
                "strengths": [],
                "findings": [],
                "confidence": "medium",
                "recommendation_ceiling": "major_revision",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "review-stage-report", str(stage_report_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "stage_id must equal stage_kind" in payload["error"]


def test_validate_review_ledger_accepts_canonical_payload(tmp_path: Path) -> None:
    ledger_path = tmp_path / "REVIEW-LEDGER.json"
    ledger = ReviewLedger(
        round=1,
        manuscript_path="paper/main.tex",
        issues=[],
    )
    _write_json(ledger_path, ledger.model_dump(mode="json"))

    result = runner.invoke(app, ["--raw", "validate", "review-ledger", str(ledger_path)], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["manuscript_path"] == "paper/main.tex"


def test_validate_review_ledger_rejects_blank_manuscript_path(tmp_path: Path) -> None:
    ledger_path = tmp_path / "REVIEW-LEDGER.json"
    _write_json(
        ledger_path,
        {
            "version": 1,
            "round": 1,
            "manuscript_path": "   ",
            "issues": [],
        },
    )

    result = runner.invoke(app, ["--raw", "validate", "review-ledger", str(ledger_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "review-ledger.manuscript_path" in payload["error"]


def test_validate_referee_decision_strict_requires_explicit_policy_fields(tmp_path: Path, monkeypatch) -> None:
    _write_canonical_stage_artifacts(tmp_path)
    monkeypatch.chdir(tmp_path)

    decision = RefereeDecisionInput(
        manuscript_path="paper/main.tex",
        target_journal="prl",
        final_recommendation=ReviewRecommendation.major_revision,
        final_confidence=ReviewConfidence.high,
        stage_artifacts=list(CANONICAL_STAGE_ARTIFACTS),
        central_claims_supported=True,
        claim_scope_proportionate_to_evidence=True,
        physical_assumptions_justified=True,
        unsupported_claims_are_central=False,
        reframing_possible_without_new_results=True,
        mathematical_correctness=ReviewAdequacy.adequate,
        novelty=ReviewAdequacy.adequate,
        significance=ReviewAdequacy.adequate,
        venue_fit=ReviewAdequacy.adequate,
        literature_positioning=ReviewAdequacy.adequate,
        unresolved_major_issues=0,
        unresolved_minor_issues=0,
        blocking_issue_ids=[],
    )
    payload = decision.model_dump(mode="json")
    payload.pop("final_confidence")
    decision_path = tmp_path / "referee-decision.json"
    _write_json(decision_path, payload)

    result = runner.invoke(
        app,
        ["--raw", "validate", "referee-decision", str(decision_path), "--strict"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["most_positive_allowed_recommendation"] == "major_revision"
    assert any("final_confidence" in reason for reason in payload["reasons"])


def test_validate_referee_decision_strict_requires_explicit_policy_fields_for_standard_venue(
    tmp_path: Path, monkeypatch
) -> None:
    _write_canonical_stage_artifacts(tmp_path)
    monkeypatch.chdir(tmp_path)

    decision = RefereeDecisionInput(
        manuscript_path="paper/main.tex",
        target_journal="jhep",
        final_recommendation=ReviewRecommendation.major_revision,
        final_confidence=ReviewConfidence.high,
        stage_artifacts=list(CANONICAL_STAGE_ARTIFACTS),
        central_claims_supported=True,
        claim_scope_proportionate_to_evidence=True,
        physical_assumptions_justified=True,
        unsupported_claims_are_central=False,
        reframing_possible_without_new_results=True,
        mathematical_correctness=ReviewAdequacy.adequate,
        novelty=ReviewAdequacy.adequate,
        significance=ReviewAdequacy.adequate,
        venue_fit=ReviewAdequacy.adequate,
        literature_positioning=ReviewAdequacy.adequate,
        unresolved_major_issues=0,
        unresolved_minor_issues=0,
        blocking_issue_ids=[],
    )
    payload = decision.model_dump(mode="json")
    payload.pop("final_confidence")
    decision_path = tmp_path / "referee-decision-jhep.json"
    _write_json(decision_path, payload)

    result = runner.invoke(
        app,
        ["--raw", "validate", "referee-decision", str(decision_path), "--strict"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["most_positive_allowed_recommendation"] == "major_revision"
    assert any("final_confidence" in reason for reason in payload["reasons"])


def test_validate_referee_decision_strict_rejects_blank_manuscript_path(tmp_path: Path, monkeypatch) -> None:
    _write_canonical_stage_artifacts(tmp_path)
    monkeypatch.chdir(tmp_path)

    decision_path = tmp_path / "referee-decision.json"
    _write_json(
        decision_path,
        {
            "manuscript_path": "",
            "target_journal": "jhep",
            "final_recommendation": "major_revision",
            "final_confidence": "high",
            "stage_artifacts": list(CANONICAL_STAGE_ARTIFACTS),
            "central_claims_supported": True,
            "claim_scope_proportionate_to_evidence": True,
            "physical_assumptions_justified": True,
            "unsupported_claims_are_central": False,
            "reframing_possible_without_new_results": True,
            "mathematical_correctness": "adequate",
            "novelty": "adequate",
            "significance": "adequate",
            "venue_fit": "adequate",
            "literature_positioning": "adequate",
            "unresolved_major_issues": 0,
            "unresolved_minor_issues": 0,
            "blocking_issue_ids": [],
        },
    )

    result = runner.invoke(
        app,
        ["--raw", "validate", "referee-decision", str(decision_path), "--strict"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert any("non-empty manuscript_path" in reason for reason in payload["reasons"])


def test_validate_referee_decision_strict_rejects_blank_review_ledger_manuscript_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_canonical_stage_artifacts(tmp_path)
    monkeypatch.chdir(tmp_path)

    decision = RefereeDecisionInput(
        manuscript_path="paper/main.tex",
        target_journal="jhep",
        final_recommendation=ReviewRecommendation.major_revision,
        final_confidence=ReviewConfidence.high,
        stage_artifacts=list(CANONICAL_STAGE_ARTIFACTS),
        central_claims_supported=True,
        claim_scope_proportionate_to_evidence=True,
        physical_assumptions_justified=True,
        unsupported_claims_are_central=False,
        reframing_possible_without_new_results=True,
        mathematical_correctness=ReviewAdequacy.adequate,
        novelty=ReviewAdequacy.adequate,
        significance=ReviewAdequacy.adequate,
        venue_fit=ReviewAdequacy.adequate,
        literature_positioning=ReviewAdequacy.adequate,
        unresolved_major_issues=0,
        unresolved_minor_issues=0,
        blocking_issue_ids=[],
    )
    decision_path = tmp_path / "referee-decision.json"
    _write_json(decision_path, decision.model_dump(mode="json"))
    ledger_path = tmp_path / "review-ledger.json"
    _write_json(
        ledger_path,
        {
            "version": 1,
            "round": 1,
            "manuscript_path": "",
            "issues": [],
        },
    )

    result = runner.invoke(
        app,
        ["--raw", "validate", "referee-decision", str(decision_path), "--strict", "--ledger", str(ledger_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert "review-ledger.manuscript_path" in payload["error"]


def test_validate_referee_decision_strict_rejects_stage_artifact_claim_index_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_canonical_stage_artifacts(tmp_path)
    monkeypatch.chdir(tmp_path)
    claim_index_path = tmp_path / "GPD" / "review" / "CLAIMS.json"
    claim_index = json.loads(claim_index_path.read_text(encoding="utf-8"))
    claim_index["manuscript_sha256"] = "b" * 64
    claim_index_path.write_text(json.dumps(claim_index, indent=2), encoding="utf-8")

    decision = RefereeDecisionInput(
        manuscript_path="paper/main.tex",
        target_journal="jhep",
        final_recommendation=ReviewRecommendation.major_revision,
        final_confidence=ReviewConfidence.high,
        stage_artifacts=list(CANONICAL_STAGE_ARTIFACTS),
        central_claims_supported=True,
        claim_scope_proportionate_to_evidence=True,
        physical_assumptions_justified=True,
        unsupported_claims_are_central=False,
        reframing_possible_without_new_results=True,
        mathematical_correctness=ReviewAdequacy.adequate,
        novelty=ReviewAdequacy.adequate,
        significance=ReviewAdequacy.adequate,
        venue_fit=ReviewAdequacy.adequate,
        literature_positioning=ReviewAdequacy.adequate,
        unresolved_major_issues=0,
        unresolved_minor_issues=0,
        blocking_issue_ids=[],
    )
    decision_path = tmp_path / "referee-decision.json"
    _write_json(decision_path, decision.model_dump(mode="json"))

    result = runner.invoke(
        app,
        ["--raw", "validate", "referee-decision", str(decision_path), "--strict"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert any("manuscript_sha256 does not match the matching claim index" in reason for reason in payload["reasons"])


def test_validate_referee_decision_strict_anchors_relative_stage_artifacts_to_absolute_decision_project_root(
    tmp_path: Path,
) -> None:
    _write_canonical_stage_artifacts(tmp_path)
    outside_cwd = tmp_path.parent / f"{tmp_path.name}-outside-cwd"
    outside_cwd.mkdir(parents=True, exist_ok=True)

    decision = RefereeDecisionInput(
        manuscript_path="paper/main.tex",
        target_journal="jhep",
        final_recommendation=ReviewRecommendation.major_revision,
        final_confidence=ReviewConfidence.high,
        stage_artifacts=list(CANONICAL_STAGE_ARTIFACTS),
        central_claims_supported=True,
        claim_scope_proportionate_to_evidence=True,
        physical_assumptions_justified=True,
        unsupported_claims_are_central=False,
        reframing_possible_without_new_results=True,
        mathematical_correctness=ReviewAdequacy.adequate,
        novelty=ReviewAdequacy.adequate,
        significance=ReviewAdequacy.adequate,
        venue_fit=ReviewAdequacy.adequate,
        literature_positioning=ReviewAdequacy.adequate,
        unresolved_major_issues=0,
        unresolved_minor_issues=0,
        blocking_issue_ids=[],
    )
    decision_path = tmp_path / "GPD" / "review" / "REFEREE-DECISION.json"
    _write_json(decision_path, decision.model_dump(mode="json"))

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(outside_cwd),
            "validate",
            "referee-decision",
            str(decision_path),
            "--strict",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True


def test_evaluate_referee_decision_strict_rejects_omitted_defaults_in_model_construct() -> None:
    explicit_values = {
        "manuscript_path": "paper/main.tex",
        "target_journal": "prl",
        "final_recommendation": ReviewRecommendation.major_revision,
        "final_confidence": ReviewConfidence.high,
        "stage_artifacts": list(CANONICAL_STAGE_ARTIFACTS),
        "central_claims_supported": True,
        "claim_scope_proportionate_to_evidence": True,
        "physical_assumptions_justified": True,
        "unsupported_claims_are_central": False,
        "reframing_possible_without_new_results": True,
        "mathematical_correctness": ReviewAdequacy.adequate,
        "novelty": ReviewAdequacy.adequate,
        "significance": ReviewAdequacy.adequate,
        "venue_fit": ReviewAdequacy.adequate,
        "literature_positioning": ReviewAdequacy.adequate,
        "unresolved_major_issues": 0,
        "unresolved_minor_issues": 0,
        "blocking_issue_ids": [],
    }
    decision = RefereeDecisionInput.model_construct(
        _fields_set=set(explicit_values) - {"final_confidence"},
        **explicit_values,
    )

    report = evaluate_referee_decision(decision, strict=True, require_explicit_inputs=True)

    assert report.valid is False
    assert report.most_positive_allowed_recommendation == ReviewRecommendation.major_revision
    assert any("final_confidence" in reason for reason in report.reasons)


def test_evaluate_referee_decision_strict_rejects_omitted_defaults_for_standard_venue() -> None:
    explicit_values = {
        "manuscript_path": "paper/main.tex",
        "target_journal": "jhep",
        "final_recommendation": ReviewRecommendation.major_revision,
        "final_confidence": ReviewConfidence.high,
        "stage_artifacts": list(CANONICAL_STAGE_ARTIFACTS),
        "central_claims_supported": True,
        "claim_scope_proportionate_to_evidence": True,
        "physical_assumptions_justified": True,
        "unsupported_claims_are_central": False,
        "reframing_possible_without_new_results": True,
        "mathematical_correctness": ReviewAdequacy.adequate,
        "novelty": ReviewAdequacy.adequate,
        "significance": ReviewAdequacy.adequate,
        "venue_fit": ReviewAdequacy.adequate,
        "literature_positioning": ReviewAdequacy.adequate,
        "unresolved_major_issues": 0,
        "unresolved_minor_issues": 0,
        "blocking_issue_ids": [],
    }
    decision = RefereeDecisionInput.model_construct(
        _fields_set=set(explicit_values) - {"final_confidence"},
        **explicit_values,
    )

    report = evaluate_referee_decision(decision, strict=True, require_explicit_inputs=True)

    assert report.valid is False
    assert report.most_positive_allowed_recommendation == ReviewRecommendation.major_revision
    assert any("final_confidence" in reason for reason in report.reasons)
