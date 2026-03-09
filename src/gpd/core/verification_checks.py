"""Registry of the 14 universal physics verification checks.

This is pure domain data used by the MCP verification server (for tool
endpoints) and available for any strategy layer integration.
Lives in core/ so consumers don't need to import each other.

Source: verification-quick-reference.md (specs/physics/verification/)
"""

from __future__ import annotations

VERIFICATION_CHECKS: dict[str, dict[str, object]] = {
    "5.1": {
        "name": "Dimensional analysis",
        "description": "Verify all terms have matching dimensions; units propagate correctly",
        "tier": 1,
        "catches": "Wrong powers of c, hbar, k_B; natural unit leaks into SI",
    },
    "5.2": {
        "name": "Numerical spot-check",
        "description": "Substitute known parameter values and verify result",
        "tier": 1,
        "catches": "Hallucinated identities, wrong coefficients",
    },
    "5.3": {
        "name": "Limiting cases",
        "description": "General result must reduce to known special cases",
        "tier": 1,
        "catches": "General result that doesn't reduce to known limits",
    },
    "5.4": {
        "name": "Conservation laws",
        "description": "Energy/momentum/charge/probability conservation verified",
        "tier": 2,
        "catches": "Conservation law violations in dynamics or numerics",
    },
    "5.5": {
        "name": "Numerical convergence",
        "description": "Result converges with refinement; correct convergence order",
        "tier": 2,
        "catches": "Unconverged results reported as final",
    },
    "5.6": {
        "name": "Cross-check with literature",
        "description": "Compare against published results or independent derivation",
        "tier": 2,
        "catches": "Systematic errors invisible to internal checks",
    },
    "5.7": {
        "name": "Order-of-magnitude estimation",
        "description": "Result within expected orders of magnitude of estimate",
        "tier": 2,
        "catches": "Results off by powers of 10",
    },
    "5.8": {
        "name": "Physical plausibility",
        "description": "Positive probabilities, causal signals, stable systems",
        "tier": 2,
        "catches": "Negative probabilities, superluminal signals",
    },
    "5.9": {
        "name": "Ward identities / sum rules",
        "description": "Gauge invariance and spectral weight constraints satisfied",
        "tier": 3,
        "catches": "Broken gauge invariance; missing spectral weight",
    },
    "5.10": {
        "name": "Unitarity bounds",
        "description": "Scattering amplitudes respect unitarity; |S| <= 1",
        "tier": 3,
        "catches": "Cross sections violating Froissart bound",
    },
    "5.11": {
        "name": "Causality constraints",
        "description": "Retarded Green's functions vanish for t<0; correct analyticity",
        "tier": 3,
        "catches": "Acausal response functions",
    },
    "5.12": {
        "name": "Positivity constraints",
        "description": "Spectral weight, cross sections, density matrices are non-negative",
        "tier": 3,
        "catches": "Negative spectral weight, non-PSD density matrix",
    },
    "5.13": {
        "name": "Kramers-Kronig consistency",
        "description": "Real/imaginary parts of response functions consistent",
        "tier": 4,
        "catches": "Inconsistent analytic continuation",
    },
    "5.14": {
        "name": "Statistical validation",
        "description": "Autocorrelation, thermalization, error estimation for stochastic methods",
        "tier": 4,
        "catches": "Underestimated errors from autocorrelation",
    },
}
