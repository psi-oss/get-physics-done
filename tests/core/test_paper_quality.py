from __future__ import annotations

from gpd.core.paper_quality import (
    BinaryCheck,
    CitationsQualityInput,
    CompletenessQualityInput,
    ConventionsQualityInput,
    CoverageMetric,
    EquationsQualityInput,
    FiguresQualityInput,
    PaperQualityInput,
    VerificationConfidence,
    VerificationQualityInput,
    ResultsQualityInput,
    score_paper_quality,
)


def _full_metric(total: int) -> CoverageMetric:
    return CoverageMetric(satisfied=total, total=total)


def test_score_paper_quality_full_prd_ready():
    report = score_paper_quality(
        PaperQualityInput(
            title="Rigorous Test Paper",
            journal="prd",
            equations=EquationsQualityInput(
                labeled=_full_metric(10),
                symbols_defined=_full_metric(10),
                dimensionally_verified=_full_metric(8),
                limiting_cases_verified=_full_metric(8),
            ),
            figures=FiguresQualityInput(
                axes_labeled_with_units=_full_metric(4),
                error_bars_present=_full_metric(4),
                referenced_in_text=_full_metric(4),
                captions_self_contained=_full_metric(4),
                colorblind_safe=_full_metric(4),
            ),
            citations=CitationsQualityInput(
                citation_keys_resolve=_full_metric(12),
                missing_placeholders=BinaryCheck(passed=True),
                key_prior_work_cited=BinaryCheck(passed=True),
                hallucination_free=BinaryCheck(passed=True),
            ),
            conventions=ConventionsQualityInput(
                convention_lock_complete=BinaryCheck(passed=True),
                assert_convention_coverage=_full_metric(6),
                notation_consistent=BinaryCheck(passed=True),
            ),
            verification=VerificationQualityInput(
                report_passed=BinaryCheck(passed=True),
                must_haves_verified=_full_metric(5),
                key_result_confidences=[
                    VerificationConfidence.independently_confirmed,
                    VerificationConfidence.independently_confirmed,
                ],
            ),
            completeness=CompletenessQualityInput(
                abstract_written_last=BinaryCheck(passed=True),
                required_sections_present=_full_metric(7),
                placeholders_cleared=BinaryCheck(passed=True),
                supplemental_cross_referenced=BinaryCheck(passed=True),
            ),
            results=ResultsQualityInput(
                uncertainties_present=_full_metric(6),
                comparison_with_prior_work_present=BinaryCheck(passed=True),
                physical_interpretation_present=BinaryCheck(passed=True),
            ),
            journal_extra_checks={"convergence_three_points": True},
        )
    )

    assert report.base_score == 100.0
    assert report.adjusted_score == 100.0
    assert report.ready_for_submission is True
    assert report.minimum_submission_score == 75.0
    assert report.blocking_issues == []


def test_score_paper_quality_flags_blockers():
    report = score_paper_quality(
        PaperQualityInput(
            title="Blocked Paper",
            journal="jhep",
            equations=EquationsQualityInput(
                labeled=_full_metric(2),
                symbols_defined=_full_metric(2),
                dimensionally_verified=_full_metric(2),
                limiting_cases_verified=_full_metric(2),
            ),
            figures=FiguresQualityInput(
                axes_labeled_with_units=_full_metric(1),
                error_bars_present=_full_metric(1),
                referenced_in_text=_full_metric(1),
                captions_self_contained=_full_metric(1),
                colorblind_safe=_full_metric(1),
            ),
            citations=CitationsQualityInput(
                citation_keys_resolve=CoverageMetric(satisfied=3, total=5),
                missing_placeholders=BinaryCheck(passed=False),
                key_prior_work_cited=BinaryCheck(passed=False),
                hallucination_free=BinaryCheck(passed=False),
            ),
            conventions=ConventionsQualityInput(
                convention_lock_complete=BinaryCheck(passed=True),
                assert_convention_coverage=_full_metric(2),
                notation_consistent=BinaryCheck(passed=True),
            ),
            verification=VerificationQualityInput(
                report_passed=BinaryCheck(passed=False),
                must_haves_verified=CoverageMetric(satisfied=2, total=5),
                key_result_confidences=[
                    VerificationConfidence.unreliable,
                    VerificationConfidence.structurally_present,
                ],
            ),
            completeness=CompletenessQualityInput(
                abstract_written_last=BinaryCheck(passed=True),
                required_sections_present=_full_metric(3),
                placeholders_cleared=BinaryCheck(passed=False),
                supplemental_cross_referenced=BinaryCheck(passed=False),
            ),
            results=ResultsQualityInput(
                uncertainties_present=CoverageMetric(satisfied=1, total=4),
                comparison_with_prior_work_present=BinaryCheck(passed=False),
                physical_interpretation_present=BinaryCheck(passed=False),
            ),
        )
    )

    assert report.ready_for_submission is False
    blocking_checks = {issue.check for issue in report.blocking_issues}
    assert "missing_placeholders" in blocking_checks
    assert "report_passed" in blocking_checks
    assert "no_unreliable_results" in blocking_checks


def test_score_paper_quality_applies_journal_adjustments():
    common_input = PaperQualityInput(
        title="Accessible Paper",
        journal="prl",
        equations=EquationsQualityInput(
            labeled=_full_metric(4),
            symbols_defined=_full_metric(4),
            dimensionally_verified=_full_metric(4),
            limiting_cases_verified=_full_metric(4),
        ),
        figures=FiguresQualityInput(
            axes_labeled_with_units=_full_metric(2),
            error_bars_present=_full_metric(2),
            referenced_in_text=_full_metric(2),
            captions_self_contained=_full_metric(2),
            colorblind_safe=_full_metric(2),
        ),
        citations=CitationsQualityInput(
            citation_keys_resolve=_full_metric(4),
            missing_placeholders=BinaryCheck(passed=True),
            key_prior_work_cited=BinaryCheck(passed=True),
            hallucination_free=BinaryCheck(passed=True),
        ),
        conventions=ConventionsQualityInput(
            convention_lock_complete=BinaryCheck(passed=True),
            assert_convention_coverage=_full_metric(2),
            notation_consistent=BinaryCheck(passed=True),
        ),
        verification=VerificationQualityInput(
            report_passed=BinaryCheck(passed=True),
            must_haves_verified=_full_metric(3),
            key_result_confidences=[VerificationConfidence.independently_confirmed],
        ),
        completeness=CompletenessQualityInput(
            abstract_written_last=BinaryCheck(passed=True),
            required_sections_present=_full_metric(4),
            placeholders_cleared=BinaryCheck(passed=True),
            supplemental_cross_referenced=BinaryCheck(passed=True),
        ),
        results=ResultsQualityInput(
            uncertainties_present=_full_metric(3),
            comparison_with_prior_work_present=BinaryCheck(passed=True),
            physical_interpretation_present=BinaryCheck(passed=True),
        ),
        journal_extra_checks={"abstract_broad_significance": False},
    )
    report_without_extra = score_paper_quality(common_input)
    report_with_extra = score_paper_quality(
        common_input.model_copy(update={"journal_extra_checks": {"abstract_broad_significance": True}})
    )

    assert report_with_extra.adjusted_score > report_without_extra.adjusted_score
    assert report_with_extra.minimum_submission_score == 85.0
