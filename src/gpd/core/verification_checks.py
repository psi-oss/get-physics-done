"""Canonical verification registry for GPD physics checks.

This module is the single executable source of truth for:

- universal verification checks
- stable check metadata exposed by MCP servers
- error-class to check coverage mappings used for gap analysis

Prompts and workflow prose may describe richer behavior, but any machine-facing
surface should consume this registry rather than duplicating check metadata.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "VERIFICATION_SCHEMA_VERSION",
    "VerificationCheckDef",
    "ErrorClassCoverageDef",
    "VERIFICATION_CHECK_DEFS",
    "VERIFICATION_CHECKS",
    "VERIFICATION_CHECK_IDS",
    "ERROR_CLASS_COVERAGE_DEFS",
    "ERROR_CLASS_COVERAGE",
    "get_verification_check",
    "list_verification_checks",
    "get_error_class_coverage",
]


VERIFICATION_SCHEMA_VERSION = 1


class VerificationCheckDef(BaseModel):
    """Stable machine-facing definition for one universal verification check."""

    model_config = ConfigDict(frozen=True)

    check_id: str
    name: str
    description: str
    tier: int
    catches: str
    evidence_kind: Literal["computational", "structural", "hybrid"]
    machine_supported: bool = True
    oracle_hint: str


class ErrorClassCoverageDef(BaseModel):
    """Stable mapping from an error class to its primary verification checks."""

    model_config = ConfigDict(frozen=True)

    error_class_id: int
    name: str
    primary_checks: list[str]
    domains: list[str]


VERIFICATION_CHECK_DEFS: tuple[VerificationCheckDef, ...] = (
    VerificationCheckDef(
        check_id="5.1",
        name="Dimensional analysis",
        description="Verify all terms have matching dimensions; units propagate correctly",
        tier=1,
        catches="Wrong powers of c, hbar, k_B; natural unit leaks into SI",
        evidence_kind="computational",
        oracle_hint="Track dimensions term-by-term or compare annotated dimensional forms.",
    ),
    VerificationCheckDef(
        check_id="5.2",
        name="Numerical spot-check",
        description="Substitute known parameter values and verify result",
        tier=1,
        catches="Hallucinated identities, wrong coefficients",
        evidence_kind="computational",
        oracle_hint="Evaluate at independently known parameter points and compare within tolerance.",
    ),
    VerificationCheckDef(
        check_id="5.3",
        name="Limiting cases",
        description="General result must reduce to known special cases",
        tier=1,
        catches="General result that does not reduce to known limits",
        evidence_kind="hybrid",
        oracle_hint="Apply symbolic or numerical limits and compare to benchmark forms.",
    ),
    VerificationCheckDef(
        check_id="5.4",
        name="Conservation laws",
        description="Energy/momentum/charge/probability conservation verified",
        tier=2,
        catches="Conservation law violations in dynamics or numerics",
        evidence_kind="computational",
        oracle_hint="Evaluate conserved quantities across time steps, configurations, or channels.",
    ),
    VerificationCheckDef(
        check_id="5.5",
        name="Numerical convergence",
        description="Result converges with refinement; correct convergence order",
        tier=2,
        catches="Unconverged results reported as final",
        evidence_kind="computational",
        oracle_hint="Run multiple resolutions and estimate convergence order or stability.",
    ),
    VerificationCheckDef(
        check_id="5.6",
        name="Cross-check with literature",
        description="Compare against published results or independent derivation",
        tier=2,
        catches="Systematic errors invisible to internal checks",
        evidence_kind="hybrid",
        oracle_hint="Compare against vetted benchmark values, references, or an independent derivation.",
    ),
    VerificationCheckDef(
        check_id="5.7",
        name="Order-of-magnitude estimation",
        description="Result within expected orders of magnitude of estimate",
        tier=2,
        catches="Results off by powers of 10",
        evidence_kind="computational",
        oracle_hint="Estimate scale independently and compare magnitude bands.",
    ),
    VerificationCheckDef(
        check_id="5.8",
        name="Physical plausibility",
        description="Positive probabilities, causal signals, stable systems",
        tier=2,
        catches="Negative probabilities, superluminal signals",
        evidence_kind="hybrid",
        oracle_hint="Check physical bounds, positivity, stability, or causal support.",
    ),
    VerificationCheckDef(
        check_id="5.9",
        name="Ward identities / sum rules",
        description="Gauge invariance and spectral weight constraints satisfied",
        tier=3,
        catches="Broken gauge invariance; missing spectral weight",
        evidence_kind="computational",
        oracle_hint="Evaluate the relevant identity or sum rule numerically or symbolically.",
    ),
    VerificationCheckDef(
        check_id="5.10",
        name="Unitarity bounds",
        description="Scattering amplitudes respect unitarity; |S| <= 1",
        tier=3,
        catches="Cross sections violating Froissart bound",
        evidence_kind="computational",
        oracle_hint="Check S-matrix, partial waves, or related unitarity bounds.",
    ),
    VerificationCheckDef(
        check_id="5.11",
        name="Causality constraints",
        description="Retarded Green's functions vanish for t<0; correct analyticity",
        tier=3,
        catches="Acausal response functions",
        evidence_kind="hybrid",
        oracle_hint="Verify support, analyticity, or retardation conditions directly.",
    ),
    VerificationCheckDef(
        check_id="5.12",
        name="Positivity constraints",
        description="Spectral weight, cross sections, density matrices are non-negative",
        tier=3,
        catches="Negative spectral weight, non-PSD density matrix",
        evidence_kind="computational",
        oracle_hint="Check positivity or PSD conditions over the relevant domain.",
    ),
    VerificationCheckDef(
        check_id="5.13",
        name="Kramers-Kronig consistency",
        description="Real/imaginary parts of response functions consistent",
        tier=4,
        catches="Inconsistent analytic continuation",
        evidence_kind="computational",
        oracle_hint="Reconstruct one part from the other and compare error.",
    ),
    VerificationCheckDef(
        check_id="5.14",
        name="Statistical validation",
        description="Autocorrelation, thermalization, error estimation for stochastic methods",
        tier=4,
        catches="Underestimated errors from autocorrelation",
        evidence_kind="computational",
        oracle_hint="Check thermalization, autocorrelation, ESS, and uncertainty estimation.",
    ),
)


VERIFICATION_CHECKS: dict[str, dict[str, object]] = {
    spec.check_id: spec.model_dump(exclude={"check_id"}) for spec in VERIFICATION_CHECK_DEFS
}

VERIFICATION_CHECK_IDS: tuple[str, ...] = tuple(spec.check_id for spec in VERIFICATION_CHECK_DEFS)


ERROR_CLASS_COVERAGE_DEFS: tuple[ErrorClassCoverageDef, ...] = (
    ErrorClassCoverageDef(
        error_class_id=1,
        name="Wrong CG coefficients",
        primary_checks=["5.2"],
        domains=["qft", "nuclear_particle"],
    ),
    ErrorClassCoverageDef(
        error_class_id=2,
        name="N-particle symmetrization",
        primary_checks=["5.3"],
        domains=["stat_mech", "qft"],
    ),
    ErrorClassCoverageDef(
        error_class_id=3,
        name="Green's function confusion",
        primary_checks=["5.13", "5.14"],
        domains=["condensed_matter", "qft"],
    ),
    ErrorClassCoverageDef(
        error_class_id=5,
        name="Incorrect asymptotic expansions",
        primary_checks=["5.3"],
        domains=["qft", "mathematical_physics"],
    ),
    ErrorClassCoverageDef(
        error_class_id=7,
        name="Wrong phase conventions",
        primary_checks=["5.2", "5.3"],
        domains=["qft"],
    ),
    ErrorClassCoverageDef(
        error_class_id=9,
        name="Incorrect thermal field theory",
        primary_checks=["5.13", "5.14"],
        domains=["qft", "stat_mech"],
    ),
    ErrorClassCoverageDef(
        error_class_id=11,
        name="Hallucinated identities",
        primary_checks=["5.2"],
        domains=["mathematical_physics"],
    ),
    ErrorClassCoverageDef(
        error_class_id=13,
        name="Boundary condition hallucination",
        primary_checks=["5.3"],
        domains=["mathematical_physics"],
    ),
    ErrorClassCoverageDef(
        error_class_id=15,
        name="Dimensional analysis failures",
        primary_checks=["5.1"],
        domains=["all"],
    ),
    ErrorClassCoverageDef(
        error_class_id=33,
        name="Natural unit restoration errors",
        primary_checks=["5.1"],
        domains=["all"],
    ),
    ErrorClassCoverageDef(
        error_class_id=37,
        name="Metric signature inconsistency",
        primary_checks=["5.1", "5.3"],
        domains=["qft", "gr_cosmology"],
    ),
    ErrorClassCoverageDef(
        error_class_id=52,
        name="NR constraint violation",
        primary_checks=["5.8", "5.5"],
        domains=["gr_cosmology"],
    ),
    ErrorClassCoverageDef(
        error_class_id=63,
        name="GW template mismatch",
        primary_checks=["5.6", "5.2"],
        domains=["gr_cosmology"],
    ),
    ErrorClassCoverageDef(
        error_class_id=71,
        name="Missing Berry phase",
        primary_checks=["5.3", "5.4"],
        domains=["condensed_matter", "amo"],
    ),
    ErrorClassCoverageDef(
        error_class_id=87,
        name="Wrong reconnection topology",
        primary_checks=["5.6", "5.8"],
        domains=["fluid_plasma"],
    ),
)


ERROR_CLASS_COVERAGE: dict[int, dict[str, object]] = {
    spec.error_class_id: spec.model_dump(exclude={"error_class_id"}) for spec in ERROR_CLASS_COVERAGE_DEFS
}


_VERIFICATION_CHECK_INDEX = {spec.check_id: spec for spec in VERIFICATION_CHECK_DEFS}
_ERROR_CLASS_COVERAGE_INDEX = {spec.error_class_id: spec for spec in ERROR_CLASS_COVERAGE_DEFS}


def get_verification_check(check_id: str) -> VerificationCheckDef | None:
    """Return the canonical definition for a verification check."""
    return _VERIFICATION_CHECK_INDEX.get(check_id)


def list_verification_checks() -> list[dict[str, object]]:
    """Return the full universal verification registry as serializable dicts."""
    return [spec.model_dump() for spec in VERIFICATION_CHECK_DEFS]


def get_error_class_coverage(error_class_id: int) -> ErrorClassCoverageDef | None:
    """Return canonical coverage metadata for an error class."""
    return _ERROR_CLASS_COVERAGE_INDEX.get(error_class_id)
