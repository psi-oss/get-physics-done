from __future__ import annotations

from gpd.core.referee_policy import RefereeDecisionInput, ReviewAdequacy, evaluate_referee_decision
from gpd.mcp.paper.models import ReviewRecommendation


def test_prl_weak_significance_cannot_receive_minor_revision():
    report = evaluate_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            target_journal="prl",
            final_recommendation=ReviewRecommendation.minor_revision,
            stage_artifacts=[f".gpd/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
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
            stage_artifacts=[f".gpd/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
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
            stage_artifacts=[f".gpd/review/STAGE-{name}.json" for name in ("reader", "literature", "math", "physics", "interestingness")],
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
