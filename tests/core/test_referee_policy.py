from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.core.referee_policy import RefereeDecisionInput, ReviewAdequacy, evaluate_referee_decision
from gpd.mcp.paper.models import (
    ReviewIssue,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    ReviewLedger,
    ReviewRecommendation,
    ReviewStageKind,
)


def test_prl_weak_significance_cannot_receive_minor_revision():
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="prl",
            final_recommendation=ReviewRecommendation.minor_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
            significance=ReviewAdequacy.weak,
            novelty=ReviewAdequacy.adequate,
            venue_fit=ReviewAdequacy.weak,
        ),
        strict=True,
    )

    assert report.valid is False
    assert report.most_positive_allowed_recommendation == ReviewRecommendation.reject


def test_fixable_overclaim_caps_standard_venue_at_major_revision():
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
            claim_scope_proportionate_to_evidence=False,
            reframing_possible_without_new_results=True,
            significance=ReviewAdequacy.weak,
            novelty=ReviewAdequacy.adequate,
            venue_fit=ReviewAdequacy.adequate,
        ),
        strict=True,
    )

    assert report.valid is True
    assert report.most_positive_allowed_recommendation == ReviewRecommendation.major_revision


def test_minor_revision_allowed_only_for_minor_follow_up():
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="prd",
            final_recommendation=ReviewRecommendation.minor_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
            unresolved_minor_issues=2,
            novelty=ReviewAdequacy.adequate,
            significance=ReviewAdequacy.adequate,
            venue_fit=ReviewAdequacy.adequate,
            literature_positioning=ReviewAdequacy.adequate,
        ),
        strict=True,
    )

    assert report.valid is True
    assert report.most_positive_allowed_recommendation == ReviewRecommendation.minor_revision


def test_review_ledger_consistency_rejects_unknown_blocking_issue_ids():
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
            blocking_issue_ids=["REF-999"],
        ),
        strict=True,
        review_ledger=ReviewLedger(
            manuscript_path="paper/main.tex",
            issues=[
                ReviewIssue(
                    issue_id="REF-001",
                    opened_by_stage=ReviewStageKind.physics,
                    severity=ReviewIssueSeverity.major,
                    blocking=True,
                    summary="Evidence is incomplete.",
                    status=ReviewIssueStatus.open,
                )
            ],
        ),
    )

    assert report.valid is False
    assert any("blocking_issue_ids not found in review ledger" in reason for reason in report.reasons)


def test_review_ledger_rejects_blank_manuscript_path() -> None:
    with pytest.raises(ValidationError):
        ReviewLedger(
            manuscript_path="   ",
            issues=[],
        )


def test_review_ledger_consistency_rejects_blank_manuscript_path_from_model_construct() -> None:
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
        ),
        strict=True,
        review_ledger=ReviewLedger.model_construct(
            round=1,
            manuscript_path="",
            issues=[],
        ),
    )

    assert report.valid is False
    assert any("review ledger manuscript_path must be non-empty" in reason for reason in report.reasons)


def test_missing_stage_artifacts_reject_decision_when_project_root_supplied(tmp_path: Path):
    review_dir = tmp_path / "GPD" / "review"
    review_dir.mkdir(parents=True)
    for artifact_name in ("STAGE-reader.json", "STAGE-literature.json", "STAGE-math.json"):
        (review_dir / artifact_name).write_text("{}", encoding="utf-8")

    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[
                "GPD/review/STAGE-reader.json",
                "GPD/review/STAGE-literature.json",
                "GPD/review/STAGE-math.json",
                "GPD/review/STAGE-physics.json",
                "GPD/review/STAGE-interestingness.json",
            ],
        ),
        strict=True,
        project_root=tmp_path,
    )

    assert report.valid is False
    assert any("listed staged review artifacts do not exist" in reason for reason in report.reasons)


def test_unresolved_critical_ledger_issues_count_toward_major_issue_total():
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
            unresolved_major_issues=0,
        ),
        strict=True,
        review_ledger=ReviewLedger(
            manuscript_path="paper/main.tex",
            issues=[
                ReviewIssue(
                    issue_id="REF-CRIT",
                    opened_by_stage=ReviewStageKind.physics,
                    severity=ReviewIssueSeverity.critical,
                    blocking=False,
                    summary="A critical unresolved issue remains.",
                    status=ReviewIssueStatus.open,
                )
            ],
        ),
    )

    assert report.valid is False
    assert any("unresolved_major_issues does not match review ledger count" in reason for reason in report.reasons)


@pytest.mark.parametrize("manuscript_path", ["./paper//main.tex", "paper/../paper/main.tex"])
def test_manuscript_path_comparison_normalizes_equivalent_paths(manuscript_path: str):
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path=manuscript_path,
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
        ),
        strict=True,
        review_ledger=ReviewLedger(
            manuscript_path="paper/main.tex",
            issues=[],
        ),
    )

    assert report.valid is True


def test_review_ledger_round_mismatch_rejects_stage_artifacts() -> None:
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[
                f"GPD/review/STAGE-{name}-R2.json" for name in ("reader", "literature", "math", "physics", "interestingness")
            ],
        ),
        strict=True,
        review_ledger=ReviewLedger(
            round=1,
            manuscript_path="paper/main.tex",
            issues=[],
        ),
    )

    assert report.valid is False
    assert any("stage_artifacts round does not match review ledger round" in reason for reason in report.reasons)


def test_strict_review_requires_at_least_five_stage_artifacts() -> None:
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[f"GPD/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics")],
        ),
        strict=True,
    )

    assert report.valid is False
    assert any("canonical five specialist stage artifacts" in reason for reason in report.reasons)


def test_strict_review_rejects_noncanonical_stage_artifact_filenames() -> None:
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[
                "GPD/review/STAGE-reader-v2.json",
                "GPD/review/STAGE-literature-v2.json",
                "GPD/review/STAGE-math-v2.json",
                "GPD/review/STAGE-physics-v2.json",
                "GPD/review/STAGE-interestingness-v2.json",
            ],
        ),
        strict=True,
    )

    assert report.valid is False
    assert any("canonical five specialist stage artifacts" in reason for reason in report.reasons)


def test_strict_review_rejects_canonical_five_plus_invalid_extra_stage_artifact() -> None:
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[
                "GPD/review/STAGE-reader.json",
                "GPD/review/STAGE-literature.json",
                "GPD/review/STAGE-math.json",
                "GPD/review/STAGE-physics.json",
                "GPD/review/STAGE-interestingness.json",
                "GPD/review/STAGE-meta.json",
            ],
        ),
        strict=True,
    )

    assert report.valid is False
    assert any("rejects noncanonical stage artifacts" in reason for reason in report.reasons)
    assert any("STAGE-meta.json" in reason for reason in report.reasons)


def test_strict_review_rejects_mixed_stage_round_suffixes() -> None:
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            stage_artifacts=[
                "GPD/review/STAGE-reader-R2.json",
                "GPD/review/STAGE-literature-R2.json",
                "GPD/review/STAGE-math-R2.json",
                "GPD/review/STAGE-physics.json",
                "GPD/review/STAGE-interestingness.json",
            ],
        ),
        strict=True,
    )

    assert report.valid is False
    assert any("same round suffix" in reason for reason in report.reasons)


@pytest.mark.parametrize("field_name", ["unresolved_major_issues", "unresolved_minor_issues"])
def test_referee_decision_counts_must_be_non_negative(field_name: str) -> None:
    with pytest.raises(ValidationError):
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="jhep",
            final_recommendation=ReviewRecommendation.major_revision,
            **{field_name: -1},
        )


def test_referee_decision_input_rejects_unknown_top_level_keys() -> None:
    with pytest.raises(ValidationError):
        RefereeDecisionInput.model_validate(
            {
                "manuscript_path": "paper/main.tex",
                "target_journal": "jhep",
                "final_recommendation": "major_revision",
                "unexpected": "boom",
            }
        )


@pytest.mark.parametrize(
    "blocking_issue_ids",
    [
        ["REF-001", "not-a-ref"],
        [""],
    ],
)
def test_referee_decision_input_rejects_malformed_blocking_issue_ids(
    blocking_issue_ids: list[str],
) -> None:
    with pytest.raises(ValidationError):
        RefereeDecisionInput.model_validate(
            {
                "manuscript_path": "paper/main.tex",
                "target_journal": "jhep",
                "final_recommendation": "major_revision",
                "blocking_issue_ids": blocking_issue_ids,
            }
        )
