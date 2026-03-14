"""Machine-readable paper quality scoring primitives."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "Severity",
    "CoverageMetric",
    "BinaryCheck",
    "VerificationConfidence",
    "EquationsQualityInput",
    "FiguresQualityInput",
    "CitationsQualityInput",
    "ConventionsQualityInput",
    "VerificationQualityInput",
    "CompletenessQualityInput",
    "ResultsQualityInput",
    "PaperQualityInput",
    "PaperQualityIssue",
    "CategoryScore",
    "PaperQualityReport",
    "score_paper_quality",
]


class Severity(StrEnum):
    blocker = "blocker"
    major = "major"
    minor = "minor"


class VerificationConfidence(StrEnum):
    independently_confirmed = "INDEPENDENTLY CONFIRMED"
    structurally_present = "STRUCTURALLY PRESENT"
    unable_to_verify = "UNABLE TO VERIFY"
    unreliable = "UNRELIABLE"


class CoverageMetric(BaseModel):
    """Coverage for checks that apply to N items."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    satisfied: int = 0
    total: int = 0
    not_applicable: bool = False

    @model_validator(mode="after")
    def _validate_bounds(self) -> CoverageMetric:
        if self.satisfied < 0 or self.total < 0:
            raise ValueError("coverage metrics must be non-negative")
        if self.satisfied > self.total:
            raise ValueError("satisfied cannot exceed total")
        return self

    @property
    def ratio(self) -> float:
        if self.not_applicable:
            return 1.0
        if self.total <= 0:
            return 0.0
        return self.satisfied / self.total


class BinaryCheck(BaseModel):
    """A boolean review gate with optional N/A semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool = False
    not_applicable: bool = False

    @property
    def ratio(self) -> float:
        return 1.0 if (self.passed or self.not_applicable) else 0.0


class EquationsQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    labeled: CoverageMetric = Field(default_factory=CoverageMetric)
    symbols_defined: CoverageMetric = Field(default_factory=CoverageMetric)
    dimensionally_verified: CoverageMetric = Field(default_factory=CoverageMetric)
    limiting_cases_verified: CoverageMetric = Field(default_factory=CoverageMetric)


class FiguresQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    axes_labeled_with_units: CoverageMetric = Field(default_factory=CoverageMetric)
    error_bars_present: CoverageMetric = Field(default_factory=CoverageMetric)
    referenced_in_text: CoverageMetric = Field(default_factory=CoverageMetric)
    captions_self_contained: CoverageMetric = Field(default_factory=CoverageMetric)
    colorblind_safe: CoverageMetric = Field(default_factory=CoverageMetric)
    decisive_artifacts_labeled_with_units: CoverageMetric = Field(
        default_factory=lambda: CoverageMetric(not_applicable=True)
    )
    decisive_artifacts_uncertainty_qualified: CoverageMetric = Field(
        default_factory=lambda: CoverageMetric(not_applicable=True)
    )
    decisive_artifacts_referenced_in_text: CoverageMetric = Field(
        default_factory=lambda: CoverageMetric(not_applicable=True)
    )
    decisive_artifact_roles_clear: CoverageMetric = Field(
        default_factory=lambda: CoverageMetric(not_applicable=True)
    )


class CitationsQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    citation_keys_resolve: CoverageMetric = Field(default_factory=CoverageMetric)
    missing_placeholders: BinaryCheck = Field(default_factory=BinaryCheck)
    key_prior_work_cited: BinaryCheck = Field(default_factory=BinaryCheck)
    hallucination_free: BinaryCheck = Field(default_factory=BinaryCheck)


class ConventionsQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    convention_lock_complete: BinaryCheck = Field(default_factory=BinaryCheck)
    assert_convention_coverage: CoverageMetric = Field(default_factory=CoverageMetric)
    notation_consistent: BinaryCheck = Field(default_factory=BinaryCheck)


class VerificationQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_passed: BinaryCheck = Field(default_factory=BinaryCheck)
    contract_targets_verified: CoverageMetric = Field(default_factory=lambda: CoverageMetric(not_applicable=True))
    key_result_confidences: list[VerificationConfidence] = Field(default_factory=list)


class CompletenessQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    abstract_written_last: BinaryCheck = Field(default_factory=BinaryCheck)
    required_sections_present: CoverageMetric = Field(default_factory=CoverageMetric)
    placeholders_cleared: BinaryCheck = Field(default_factory=BinaryCheck)
    supplemental_cross_referenced: BinaryCheck = Field(default_factory=BinaryCheck)


class ResultsQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    uncertainties_present: CoverageMetric = Field(default_factory=CoverageMetric)
    comparison_with_prior_work_present: BinaryCheck = Field(default_factory=BinaryCheck)
    physical_interpretation_present: BinaryCheck = Field(default_factory=BinaryCheck)
    decisive_artifacts_with_explicit_verdicts: CoverageMetric = Field(
        default_factory=lambda: CoverageMetric(not_applicable=True)
    )
    decisive_artifacts_benchmark_anchored: CoverageMetric = Field(
        default_factory=lambda: CoverageMetric(not_applicable=True)
    )
    decisive_comparison_failures_scoped: BinaryCheck = Field(default_factory=lambda: BinaryCheck(not_applicable=True))


class PaperQualityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = ""
    journal: str = "generic"
    equations: EquationsQualityInput = Field(default_factory=EquationsQualityInput)
    figures: FiguresQualityInput = Field(default_factory=FiguresQualityInput)
    citations: CitationsQualityInput = Field(default_factory=CitationsQualityInput)
    conventions: ConventionsQualityInput = Field(default_factory=ConventionsQualityInput)
    verification: VerificationQualityInput = Field(default_factory=VerificationQualityInput)
    completeness: CompletenessQualityInput = Field(default_factory=CompletenessQualityInput)
    results: ResultsQualityInput = Field(default_factory=ResultsQualityInput)
    journal_extra_checks: dict[str, bool] = Field(default_factory=dict)


class PaperQualityIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    check: str
    severity: Severity
    summary: str
    blocking: bool = False


class CategoryScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    score: float
    max_score: float
    checks: dict[str, float] = Field(default_factory=dict)


class PaperQualityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    journal: str
    categories: dict[str, CategoryScore]
    base_score: float
    adjusted_score: float
    minimum_submission_score: float
    status: str
    ready_for_submission: bool
    issues: list[PaperQualityIssue] = Field(default_factory=list)
    blocking_issues: list[PaperQualityIssue] = Field(default_factory=list)


CATEGORY_MAX: dict[str, float] = {
    "equations": 20.0,
    "figures": 15.0,
    "citations": 10.0,
    "conventions": 15.0,
    "verification": 20.0,
    "completeness": 10.0,
    "results": 10.0,
}


JOURNAL_RULES: dict[str, dict[str, object]] = {
    "generic": {
        "minimum": 80.0,
        "multipliers": {},
        "extra_check": None,
        "extra_points": 0.0,
    },
    "prl": {
        "minimum": 85.0,
        "multipliers": {"results": 1.5, "completeness": 1.3, "conventions": 0.7},
        "extra_check": "abstract_broad_significance",
        "extra_points": 5.0,
    },
    "prd": {
        "minimum": 75.0,
        "multipliers": {"equations": 1.2, "verification": 1.3, "figures": 1.0},
        "extra_check": "convergence_three_points",
        "extra_points": 5.0,
    },
    "prb": {
        "minimum": 75.0,
        "multipliers": {"equations": 1.2, "verification": 1.3, "figures": 1.0},
        "extra_check": "convergence_three_points",
        "extra_points": 5.0,
    },
    "prc": {
        "minimum": 75.0,
        "multipliers": {"equations": 1.2, "verification": 1.3, "figures": 1.0},
        "extra_check": "convergence_three_points",
        "extra_points": 5.0,
    },
    "jhep": {
        "minimum": 80.0,
        "multipliers": {"equations": 1.4, "conventions": 1.5, "citations": 1.2},
        "extra_check": "feynman_diagrams_listed",
        "extra_points": 5.0,
    },
    "nature": {
        "minimum": 90.0,
        "multipliers": {"results": 1.5, "completeness": 1.3, "equations": 0.5},
        "extra_check": "abstract_accessible_outside_subfield",
        "extra_points": 5.0,
    },
    "nature_physics": {
        "minimum": 90.0,
        "multipliers": {"results": 1.5, "completeness": 1.3, "equations": 0.5},
        "extra_check": "abstract_accessible_outside_subfield",
        "extra_points": 5.0,
    },
    "apj": {
        "minimum": 75.0,
        "multipliers": {"results": 1.3, "citations": 1.2, "figures": 1.3},
        "extra_check": "software_statement_present",
        "extra_points": 3.0,
    },
}


def _ratio_points(ratio: float, full_points: float) -> float:
    if ratio >= 1.0:
        return full_points
    if ratio >= 0.8:
        return full_points / 2.0
    return 0.0


def _metric_is_explicit(metric: CoverageMetric) -> bool:
    return metric.not_applicable is False or metric.total > 0


def _metric_or_fallback(primary: CoverageMetric, fallback: CoverageMetric) -> CoverageMetric:
    return primary if _metric_is_explicit(primary) else fallback


def _confidence_ratio(confidences: list[VerificationConfidence]) -> float:
    if not confidences:
        return 0.0
    weights = {
        VerificationConfidence.independently_confirmed: 1.0,
        VerificationConfidence.structurally_present: 0.6,
        VerificationConfidence.unable_to_verify: 0.2,
        VerificationConfidence.unreliable: 0.0,
    }
    return sum(weights[c] for c in confidences) / len(confidences)


def _status_for_score(score: float) -> str:
    if score >= 90:
        return "publication_ready"
    if score >= 80:
        return "nearly_ready"
    if score >= 70:
        return "needs_work"
    if score >= 60:
        return "significant_gaps"
    return "not_ready"


def _metric_issue(category: str, check: str, points: float, max_points: float, summary: str) -> PaperQualityIssue | None:
    if points >= max_points:
        return None
    severity = Severity.major if points == 0 else Severity.minor
    return PaperQualityIssue(category=category, check=check, severity=severity, summary=summary)


def score_paper_quality(data: PaperQualityInput) -> PaperQualityReport:
    """Score a paper against machine-readable quality criteria."""

    issues: list[PaperQualityIssue] = []

    decisive_labels = _metric_or_fallback(
        data.figures.decisive_artifacts_labeled_with_units,
        data.figures.axes_labeled_with_units,
    )
    decisive_uncertainty = _metric_or_fallback(
        data.figures.decisive_artifacts_uncertainty_qualified,
        data.figures.error_bars_present,
    )
    decisive_references = _metric_or_fallback(
        data.figures.decisive_artifacts_referenced_in_text,
        data.figures.referenced_in_text,
    )
    decisive_result_ratios: list[float] = []
    if _metric_is_explicit(data.results.decisive_artifacts_with_explicit_verdicts):
        decisive_result_ratios.append(data.results.decisive_artifacts_with_explicit_verdicts.ratio)
    if _metric_is_explicit(data.results.decisive_artifacts_benchmark_anchored):
        decisive_result_ratios.append(data.results.decisive_artifacts_benchmark_anchored.ratio)
    if not data.results.decisive_comparison_failures_scoped.not_applicable:
        decisive_result_ratios.append(data.results.decisive_comparison_failures_scoped.ratio)
    comparison_ratio = (
        min(decisive_result_ratios)
        if decisive_result_ratios
        else data.results.comparison_with_prior_work_present.ratio
    )

    eq_checks = {
        "labeled": _ratio_points(data.equations.labeled.ratio, 4.0),
        "symbols_defined": _ratio_points(data.equations.symbols_defined.ratio, 4.0),
        "dimensionally_verified": _ratio_points(data.equations.dimensionally_verified.ratio, 6.0),
        "limiting_cases_verified": _ratio_points(data.equations.limiting_cases_verified.ratio, 6.0),
    }
    figures_checks = {
        "axes_labeled_with_units": _ratio_points(decisive_labels.ratio, 3.0),
        "error_bars_present": _ratio_points(decisive_uncertainty.ratio, 4.0),
        "referenced_in_text": _ratio_points(decisive_references.ratio, 2.0),
        "captions_self_contained": _ratio_points(data.figures.captions_self_contained.ratio, 3.0),
        "colorblind_safe": _ratio_points(data.figures.colorblind_safe.ratio, 1.0),
        "decisive_artifact_roles_clear": _ratio_points(data.figures.decisive_artifact_roles_clear.ratio, 2.0),
    }
    citation_checks = {
        "citation_keys_resolve": _ratio_points(data.citations.citation_keys_resolve.ratio, 3.0),
        "missing_placeholders": 3.0 * data.citations.missing_placeholders.ratio,
        "key_prior_work_cited": 2.0 * data.citations.key_prior_work_cited.ratio,
        "hallucination_free": 2.0 * data.citations.hallucination_free.ratio,
    }
    convention_checks = {
        "convention_lock_complete": 5.0 * data.conventions.convention_lock_complete.ratio,
        "assert_convention_coverage": _ratio_points(data.conventions.assert_convention_coverage.ratio, 5.0),
        "notation_consistent": 5.0 * data.conventions.notation_consistent.ratio,
    }

    unreliable_count = sum(1 for c in data.verification.key_result_confidences if c == VerificationConfidence.unreliable)
    verification_checks = {
        "report_passed": 5.0 * data.verification.report_passed.ratio,
        "contract_targets_verified": _ratio_points(data.verification.contract_targets_verified.ratio, 5.0),
        "key_result_confidence": 5.0 * _confidence_ratio(data.verification.key_result_confidences),
        "no_unreliable_results": 5.0 if unreliable_count == 0 else 0.0,
    }
    completeness_checks = {
        "abstract_written_last": 2.0 * data.completeness.abstract_written_last.ratio,
        "required_sections_present": _ratio_points(data.completeness.required_sections_present.ratio, 3.0),
        "placeholders_cleared": 3.0 * data.completeness.placeholders_cleared.ratio,
        "supplemental_cross_referenced": 2.0 * data.completeness.supplemental_cross_referenced.ratio,
    }
    results_checks = {
        "uncertainties_present": _ratio_points(data.results.uncertainties_present.ratio, 4.0),
        "comparison_with_prior_work_present": 3.0 * comparison_ratio,
        "physical_interpretation_present": 3.0 * data.results.physical_interpretation_present.ratio,
    }

    categories = {
        "equations": CategoryScore(name="equations", score=sum(eq_checks.values()), max_score=CATEGORY_MAX["equations"], checks=eq_checks),
        "figures": CategoryScore(name="figures", score=sum(figures_checks.values()), max_score=CATEGORY_MAX["figures"], checks=figures_checks),
        "citations": CategoryScore(
            name="citations",
            score=sum(citation_checks.values()),
            max_score=CATEGORY_MAX["citations"],
            checks=citation_checks,
        ),
        "conventions": CategoryScore(
            name="conventions",
            score=sum(convention_checks.values()),
            max_score=CATEGORY_MAX["conventions"],
            checks=convention_checks,
        ),
        "verification": CategoryScore(
            name="verification",
            score=sum(verification_checks.values()),
            max_score=CATEGORY_MAX["verification"],
            checks=verification_checks,
        ),
        "completeness": CategoryScore(
            name="completeness",
            score=sum(completeness_checks.values()),
            max_score=CATEGORY_MAX["completeness"],
            checks=completeness_checks,
        ),
        "results": CategoryScore(name="results", score=sum(results_checks.values()), max_score=CATEGORY_MAX["results"], checks=results_checks),
    }

    issues.extend(
        issue
        for issue in [
            _metric_issue("equations", "labeled", eq_checks["labeled"], 4.0, "Displayed equations are missing labels."),
            _metric_issue(
                "equations",
                "symbols_defined",
                eq_checks["symbols_defined"],
                4.0,
                "Not all symbols are defined at first use.",
            ),
            _metric_issue(
                "equations",
                "dimensionally_verified",
                eq_checks["dimensionally_verified"],
                6.0,
                "Dimensional analysis coverage is incomplete.",
            ),
            _metric_issue(
                "equations",
                "limiting_cases_verified",
                eq_checks["limiting_cases_verified"],
                6.0,
                "Limiting case coverage is incomplete.",
            ),
            _metric_issue(
                "citations",
                "missing_placeholders",
                citation_checks["missing_placeholders"],
                3.0,
                "Placeholder citations remain in the manuscript.",
            ),
            _metric_issue(
                "citations",
                "hallucination_free",
                citation_checks["hallucination_free"],
                2.0,
                "Citation audit is incomplete or unresolved.",
            ),
            _metric_issue(
                "verification",
                "report_passed",
                verification_checks["report_passed"],
                5.0,
                "Verification report is missing or not passed.",
            ),
            _metric_issue(
                "verification",
                "contract_targets_verified",
                verification_checks["contract_targets_verified"],
                5.0,
                "Not all contract-defined targets are verified.",
            ),
            _metric_issue(
                "figures",
                "decisive_artifact_roles_clear",
                figures_checks["decisive_artifact_roles_clear"],
                2.0,
                "Decisive figures or tables are not clearly marked as such.",
            ),
            _metric_issue(
                "results",
                "comparison_with_prior_work_present",
                results_checks["comparison_with_prior_work_present"],
                3.0,
                "Decisive comparison coverage is incomplete.",
            ),
            _metric_issue(
                "completeness",
                "placeholders_cleared",
                completeness_checks["placeholders_cleared"],
                3.0,
                "TODO/FIXME/PENDING placeholders remain.",
            ),
            _metric_issue(
                "results",
                "uncertainties_present",
                results_checks["uncertainties_present"],
                4.0,
                "Key numerical results are missing uncertainties.",
            ),
        ]
        if issue is not None
    )

    blockers: list[PaperQualityIssue] = []
    if not data.citations.missing_placeholders.passed and not data.citations.missing_placeholders.not_applicable:
        blockers.append(
            PaperQualityIssue(
                category="citations",
                check="missing_placeholders",
                severity=Severity.blocker,
                summary="Unresolved MISSING: citations remain.",
                blocking=True,
            )
        )
    if unreliable_count > 0:
        blockers.append(
            PaperQualityIssue(
                category="verification",
                check="no_unreliable_results",
                severity=Severity.blocker,
                summary="At least one key result is marked UNRELIABLE.",
                blocking=True,
            )
        )
    if not data.verification.report_passed.passed and not data.verification.report_passed.not_applicable:
        blockers.append(
            PaperQualityIssue(
                category="verification",
                check="report_passed",
                severity=Severity.blocker,
                summary="Verification status is not passed.",
                blocking=True,
            )
        )
    if (
        _metric_is_explicit(data.results.decisive_artifacts_with_explicit_verdicts)
        and data.results.decisive_artifacts_with_explicit_verdicts.total > 0
        and data.results.decisive_artifacts_with_explicit_verdicts.satisfied
        < data.results.decisive_artifacts_with_explicit_verdicts.total
    ):
        blockers.append(
            PaperQualityIssue(
                category="results",
                check="decisive_artifacts_with_explicit_verdicts",
                severity=Severity.blocker,
                summary="Decisive artifacts are missing explicit comparison verdicts.",
                blocking=True,
            )
        )
    if (
        not data.results.decisive_comparison_failures_scoped.not_applicable
        and not data.results.decisive_comparison_failures_scoped.passed
    ):
        blockers.append(
            PaperQualityIssue(
                category="results",
                check="decisive_comparison_failures_scoped",
                severity=Severity.blocker,
                summary="Decisive comparison failures or tensions are not explicitly scoped.",
                blocking=True,
            )
        )

    base_score = round(sum(category.score for category in categories.values()), 2)

    journal_key = data.journal.lower().replace(" ", "_")
    journal_rule = JOURNAL_RULES.get(journal_key, JOURNAL_RULES["generic"])
    multipliers = journal_rule["multipliers"]

    adjusted_total = 0.0
    adjusted_max = 0.0
    for category_name, category in categories.items():
        multiplier = float(multipliers.get(category_name, 1.0))
        adjusted_total += category.score * multiplier
        adjusted_max += category.max_score * multiplier

    extra_check = journal_rule["extra_check"]
    extra_points = float(journal_rule["extra_points"])
    if extra_check:
        adjusted_max += extra_points
        if data.journal_extra_checks.get(str(extra_check), False):
            adjusted_total += extra_points
        else:
            issues.append(
                PaperQualityIssue(
                    category="journal_specific",
                    check=str(extra_check),
                    severity=Severity.minor,
                    summary=f"Journal-specific check '{extra_check}' is not satisfied.",
                )
            )

    adjusted_score = round(100.0 * adjusted_total / adjusted_max, 2) if adjusted_max else 0.0
    minimum_submission_score = float(journal_rule["minimum"])
    ready = adjusted_score >= minimum_submission_score and not blockers

    return PaperQualityReport(
        title=data.title,
        journal=data.journal,
        categories=categories,
        base_score=base_score,
        adjusted_score=adjusted_score,
        minimum_submission_score=minimum_submission_score,
        status=_status_for_score(adjusted_score),
        ready_for_submission=ready,
        issues=issues,
        blocking_issues=blockers,
    )
