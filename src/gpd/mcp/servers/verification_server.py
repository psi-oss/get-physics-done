"""MCP server for GPD physics verification.

Exposes verification checks as MCP tools for solver agents to run
dimensional analysis, limiting case checks, symmetry verification,
and domain-specific checklists.

Usage:
    python -m gpd.mcp.servers.verification_server
    # or via entry point:
    gpd-mcp-verification
"""

from __future__ import annotations

import logging
import re
import sys

from mcp.server.fastmcp import FastMCP

from gpd.core.observability import gpd_span
from gpd.core.verification_checks import VERIFICATION_CHECKS

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-verification")

mcp = FastMCP("gpd-verification")

# ─── Domain Checklists ────────────────────────────────────────────────────────

DOMAIN_CHECKLISTS: dict[str, list[dict[str, str]]] = {
    "qft": [
        {"check": "Ward identities after vertex corrections", "check_ids": "5.9"},
        {"check": "Optical theorem after amplitude computation", "check_ids": "5.10"},
        {"check": "Gauge independence (compute in two gauges)", "check_ids": "5.3,5.9"},
        {"check": "UV divergence structure matches power counting", "check_ids": "5.1,5.8"},
        {"check": "Crossing symmetry of scattering amplitudes", "check_ids": "5.10"},
        {"check": "Mandelstam variables: s + t + u = sum(m^2)", "check_ids": "5.2"},
    ],
    "condensed_matter": [
        {"check": "f-sum rule for optical conductivity", "check_ids": "5.9"},
        {"check": "Luttinger theorem (Fermi surface volume = electron count)", "check_ids": "5.4"},
        {"check": "Kramers-Kronig for all response functions", "check_ids": "5.13"},
        {"check": "Goldstone modes match broken symmetry count", "check_ids": "5.3,5.4"},
        {"check": "Spectral weight positive everywhere", "check_ids": "5.12"},
    ],
    "stat_mech": [
        {"check": "Z -> (number of states) at high T", "check_ids": "5.3"},
        {"check": "Critical exponents match universality class", "check_ids": "5.6"},
        {"check": "Finite-size scaling collapse with correct exponents", "check_ids": "5.5"},
        {"check": "Detailed balance: W(A->B)P_eq(A) = W(B->A)P_eq(B)", "check_ids": "5.4"},
        {"check": "C_V >= 0 (thermodynamic stability)", "check_ids": "5.8"},
        {"check": "S -> 0 as T -> 0 (third law)", "check_ids": "5.3"},
    ],
    "gr_cosmology": [
        {"check": "Friedmann + continuity equations consistent", "check_ids": "5.4"},
        {"check": "Comoving vs physical distance factors of (1+z)", "check_ids": "5.1"},
        {"check": "Bianchi identity satisfied", "check_ids": "5.4"},
        {"check": "Energy conditions respected or explicitly violated", "check_ids": "5.8"},
        {"check": "Geodesic equation consistent with metric", "check_ids": "5.3"},
    ],
    "amo": [
        {"check": "Selection rules from angular momentum coupling", "check_ids": "5.4"},
        {"check": "Transition rates obey sum rules", "check_ids": "5.9"},
        {"check": "Dipole matrix elements have correct parity", "check_ids": "5.3"},
        {"check": "Oscillator strengths positive and sum to Z", "check_ids": "5.12,5.9"},
    ],
    "nuclear_particle": [
        {"check": "Cross section satisfies optical theorem", "check_ids": "5.10"},
        {"check": "Isospin quantum numbers conserved", "check_ids": "5.4"},
        {"check": "Branching ratios sum to 1", "check_ids": "5.8"},
        {"check": "Decay widths positive", "check_ids": "5.12"},
    ],
    "quantum_info": [
        {"check": "Tr(rho) = 1, eigenvalues in [0,1], rho = rho^dag", "check_ids": "5.4,5.12"},
        {"check": "Quantum channels are CPTP (Choi matrix PSD)", "check_ids": "5.12"},
        {"check": "Fidelity F in [0,1]", "check_ids": "5.8"},
        {"check": "No-cloning: apparent cloning must violate unitarity", "check_ids": "5.10"},
        {"check": "Entanglement entropy non-negative", "check_ids": "5.12"},
    ],
    "fluid_plasma": [
        {"check": "CFL condition satisfied", "check_ids": "5.5"},
        {"check": "Debye length resolved by grid", "check_ids": "5.5"},
        {"check": "Energy conservation to integrator tolerance", "check_ids": "5.4"},
        {"check": "Reynolds number appropriate for model", "check_ids": "5.8"},
        {"check": "Divergence-free magnetic field maintained", "check_ids": "5.4"},
    ],
    "mathematical_physics": [
        {"check": "Analyticity structure correct (poles, cuts, sheets)", "check_ids": "5.11"},
        {"check": "Index theorem / topological invariant computed", "check_ids": "5.4"},
        {"check": "Symmetry group representation correct", "check_ids": "5.3"},
    ],
    "astrophysics": [
        {"check": "Eddington luminosity limit respected", "check_ids": "5.8"},
        {"check": "Virial theorem applied correctly", "check_ids": "5.4"},
        {"check": "Optical depth integral convergent", "check_ids": "5.5"},
    ],
    "soft_matter": [
        {"check": "Fluctuation-dissipation theorem satisfied", "check_ids": "5.9"},
        {"check": "Free energy extensive in system size", "check_ids": "5.1,5.3"},
        {"check": "Diffusion coefficient positive", "check_ids": "5.12"},
    ],
}

# ─── Error Class Catalog (104 classes) ────────────────────────────────────────

# Map error class IDs to detection checks. From verification-gap-analysis.md.
ERROR_CLASS_COVERAGE: dict[int, dict[str, object]] = {
    1: {"name": "Wrong CG coefficients", "primary_checks": ["5.2"], "domains": ["qft", "nuclear_particle"]},
    2: {"name": "N-particle symmetrization", "primary_checks": ["5.3"], "domains": ["stat_mech", "qft"]},
    3: {
        "name": "Green's function confusion",
        "primary_checks": ["5.13", "5.14"],
        "domains": ["condensed_matter", "qft"],
    },
    5: {
        "name": "Incorrect asymptotic expansions",
        "primary_checks": ["5.3"],
        "domains": ["qft", "mathematical_physics"],
    },
    7: {"name": "Wrong phase conventions", "primary_checks": ["5.2", "5.3"], "domains": ["qft"]},
    9: {"name": "Incorrect thermal field theory", "primary_checks": ["5.13", "5.14"], "domains": ["qft", "stat_mech"]},
    11: {"name": "Hallucinated identities", "primary_checks": ["5.2"], "domains": ["mathematical_physics"]},
    13: {"name": "Boundary condition hallucination", "primary_checks": ["5.3"], "domains": ["mathematical_physics"]},
    15: {"name": "Dimensional analysis failures", "primary_checks": ["5.1"], "domains": ["all"]},
    33: {"name": "Natural unit restoration errors", "primary_checks": ["5.1"], "domains": ["all"]},
    37: {
        "name": "Metric signature inconsistency",
        "primary_checks": ["5.1", "5.3"],
        "domains": ["qft", "gr_cosmology"],
    },
    52: {"name": "NR constraint violation", "primary_checks": ["5.8", "5.5"], "domains": ["gr_cosmology"]},
    63: {"name": "GW template mismatch", "primary_checks": ["5.6", "5.2"], "domains": ["gr_cosmology"]},
    71: {"name": "Missing Berry phase", "primary_checks": ["5.3", "5.4"], "domains": ["condensed_matter", "amo"]},
    87: {"name": "Wrong reconnection topology", "primary_checks": ["5.6", "5.8"], "domains": ["fluid_plasma"]},
}

# ─── Dimension Parsing ────────────────────────────────────────────────────────

# Base dimensions: [M], [L], [T], [Q], [Theta]
_DIM_PATTERN = re.compile(r"\[([MLTQ]|Theta)\](?:\^([+-]?\d+))?")


def _parse_dimensions(expr: str) -> dict[str, int]:
    """Parse a dimensional expression like '[M][L]^2[T]^-2' into {M: 1, L: 2, T: -2}."""
    dims: dict[str, int] = {"M": 0, "L": 0, "T": 0, "Q": 0, "Theta": 0}
    for match in _DIM_PATTERN.finditer(expr):
        dim = match.group(1)
        power = int(match.group(2)) if match.group(2) else 1
        dims[dim] += power
    return dims


def _dims_equal(a: dict[str, int], b: dict[str, int]) -> bool:
    """Check if two dimensional dicts are equal."""
    all_keys = set(a.keys()) | set(b.keys())
    return all(a.get(k, 0) == b.get(k, 0) for k in all_keys)


# ─── MCP Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
def run_check(check_id: str, domain: str, artifact_content: str) -> dict:
    """Run a specific verification check on an artifact.

    Returns the check result with evidence and confidence.
    The actual physics verification is performed by the calling agent;
    this tool provides the check specification, what to look for,
    and structured result formatting.

    Args:
        check_id: Check identifier (e.g., "5.1", "5.3")
        domain: Physics domain for domain-specific guidance
        artifact_content: The content to verify (derivation, code, etc.)
    """
    try:
        with gpd_span("mcp.verification.run_check", check_type=check_id, domain=domain):
            check_meta = VERIFICATION_CHECKS.get(check_id)
            if check_meta is None:
                return {"error": f"Unknown check_id: {check_id}. Valid: {list(VERIFICATION_CHECKS.keys())}"}

            # Get domain-specific guidance
            domain_checks = DOMAIN_CHECKLISTS.get(domain, [])
            relevant_domain_checks = [c for c in domain_checks if check_id in c.get("check_ids", "").split(",")]

            # Scan artifact for obvious issues
            issues: list[str] = []

            if check_id == "5.1":
                # Dimensional analysis: look for common pitfalls
                if "hbar" not in artifact_content and "\\hbar" not in artifact_content:
                    if any(kw in artifact_content.lower() for kw in ["quantum", "planck", "commutator"]):
                        issues.append("Quantum context detected but no hbar found -- check natural unit conventions")
                if re.search(r"exp\s*\([^)]*\[", artifact_content):
                    issues.append("Possible dimensionful argument to exponential")

            elif check_id == "5.3":
                # Limiting cases: check if any limits are discussed
                limit_keywords = ["limit", "->", "\\to", "limiting", "reduces to", "special case"]
                has_limits = any(kw in artifact_content.lower() for kw in limit_keywords)
                if not has_limits:
                    issues.append("No limiting case analysis found in artifact")

            return {
                "check_id": check_id,
                "check_name": check_meta["name"],
                "tier": check_meta["tier"],
                "description": check_meta["description"],
                "catches": check_meta["catches"],
                "domain": domain,
                "domain_specific_checks": relevant_domain_checks,
                "automated_issues": issues,
                "artifact_length": len(artifact_content),
                "guidance": (
                    f"Run check {check_id} ({check_meta['name']}) for domain '{domain}'. "
                    f"This check catches: {check_meta['catches']}."
                ),
            }
    except Exception as exc:
        logger.warning("run_check failed: %s", exc)
        return {"error": str(exc)}


@mcp.tool()
def get_checklist(domain: str) -> dict:
    """Return the domain-specific verification checklist.

    Provides the complete list of checks recommended for a physics domain,
    including which universal checks (5.1-5.14) each maps to.
    """
    try:
        with gpd_span("mcp.verification.checklist", domain=domain):
            checklist = DOMAIN_CHECKLISTS.get(domain)
            if checklist is None:
                return {
                    "found": False,
                    "domain": domain,
                    "available_domains": sorted(DOMAIN_CHECKLISTS.keys()),
                    "message": f"No checklist for domain '{domain}'.",
                }

            # Also include the universal checks
            universal = [{"check_id": k, **v} for k, v in VERIFICATION_CHECKS.items()]

            return {
                "found": True,
                "domain": domain,
                "domain_checks": checklist,
                "domain_check_count": len(checklist),
                "universal_checks": universal,
                "universal_check_count": len(universal),
            }
    except Exception as exc:
        logger.warning("get_checklist failed: %s", exc)
        return {"error": str(exc)}


@mcp.tool()
def dimensional_check(expressions: list[str]) -> dict:
    """Verify dimensional consistency of physics expressions.

    Each expression should be in the format "LHS = RHS" where dimensions
    are annotated with [M], [L], [T], [Q], [Theta] notation.

    Example: "[M][L]^2[T]^-2 = [M][L]^2[T]^-2" (energy = energy)
    """
    try:
        with gpd_span("mcp.verification.dimensional_check"):
            return _dimensional_check_inner(expressions)
    except Exception as exc:
        logger.warning("dimensional_check failed: %s", exc)
        return {"error": str(exc)}


def _dimensional_check_inner(expressions: list[str]) -> dict:
    results: list[dict[str, object]] = []

    for expr in expressions:
        if "=" not in expr:
            results.append(
                {
                    "expression": expr,
                    "valid": False,
                    "error": "Expression must contain '=' to compare dimensions",
                }
            )
            continue

        parts = expr.split("=", 1)
        lhs_str = parts[0].strip()
        rhs_str = parts[1].strip()

        lhs_dims = _parse_dimensions(lhs_str)
        rhs_dims = _parse_dimensions(rhs_str)

        no_annotations = all(v == 0 for v in lhs_dims.values()) and all(
            v == 0 for v in rhs_dims.values()
        )
        match = _dims_equal(lhs_dims, rhs_dims)
        result: dict[str, object] = {
            "expression": expr,
            "valid": match and not no_annotations,
            "no_dimensions_found": no_annotations,
            "lhs_dimensions": {k: v for k, v in lhs_dims.items() if v != 0},
            "rhs_dimensions": {k: v for k, v in rhs_dims.items() if v != 0},
        }
        if no_annotations:
            result["note"] = (
                "No dimension annotations found — cannot verify"
            )
        elif not match:
            mismatches = {}
            for dim in set(lhs_dims.keys()) | set(rhs_dims.keys()):
                lv = lhs_dims.get(dim, 0)
                rv = rhs_dims.get(dim, 0)
                if lv != rv:
                    mismatches[dim] = {"lhs": lv, "rhs": rv, "diff": lv - rv}
            result["mismatches"] = mismatches
        results.append(result)

    all_valid = all(r.get("valid", False) for r in results)
    return {
        "all_consistent": all_valid,
        "checked_count": len(results),
        "results": results,
    }


@mcp.tool()
def limiting_case_check(expression: str, limits: dict[str, str]) -> dict:
    """Verify that an expression reduces to known results in specified limits.

    This is a structural check -- it validates that the limit analysis
    has been documented. The actual mathematical verification should be
    performed by a CAS (SymPy) via the code execution MCP server.

    Args:
        expression: The general expression being checked
        limits: Dict mapping limit descriptions to expected results.
                E.g., {"hbar -> 0": "classical Hamilton-Jacobi",
                       "c -> infinity": "non-relativistic Schrodinger"}
    """
    try:
        with gpd_span("mcp.verification.limiting_case"):
            return _limiting_case_inner(expression, limits)
    except Exception as exc:
        logger.warning("limiting_case_check failed: %s", exc)
        return {"error": str(exc)}


def _limiting_case_inner(expression: str, limits: dict[str, str]) -> dict:
    results: list[dict[str, object]] = []
    standard_limits = {
        "classical": "hbar -> 0",
        "non-relativistic": "v/c -> 0 or c -> infinity",
        "weak-coupling": "g -> 0",
        "high-temperature": "T -> infinity",
        "low-temperature": "T -> 0",
        "continuum": "a -> 0 (lattice spacing)",
        "thermodynamic": "N -> infinity",
        "flat-space": "R_{mu nu} -> 0",
    }

    for limit_desc, expected_result in limits.items():
        # Check if this is a standard limit type
        limit_type = None
        for stype, sdesc in standard_limits.items():
            if stype in limit_desc.lower() or sdesc.lower() in limit_desc.lower():
                limit_type = stype
                break

        results.append(
            {
                "limit": limit_desc,
                "expected": expected_result,
                "limit_type": limit_type,
                "status": "documented",
                "guidance": (
                    f"Verify: apply limit '{limit_desc}' to the expression. "
                    f"Result should reduce to: {expected_result}. "
                    "Use SymPy sympy.limit() or series expansion for rigorous check."
                ),
            }
        )

    # Suggest missing standard limits based on expression content
    suggestions: list[str] = []
    expr_lower = expression.lower()
    if "hbar" in expr_lower or "\\hbar" in expr_lower:
        if not any("classical" in key.lower() or "hbar" in key.lower() for key in limits):
            suggestions.append("Consider checking classical limit (hbar -> 0)")
    if any(kw in expr_lower for kw in ["gamma", "lorentz", "relativistic", "c^2"]):
        if not any("non-rel" in key.lower() or "c ->" in key.lower() for key in limits):
            suggestions.append("Consider checking non-relativistic limit (c -> infinity)")
    if any(kw in expr_lower for kw in ["coupling", "alpha", "g^2", "perturbat"]):
        if not any("weak" in key.lower() or "g ->" in key.lower() for key in limits):
            suggestions.append("Consider checking weak-coupling limit (g -> 0)")

    return {
        "expression_length": len(expression),
        "limits_checked": len(results),
        "results": results,
        "suggestions": suggestions,
    }


@mcp.tool()
def symmetry_check(expression: str, symmetries: list[str]) -> dict:
    """Verify that an expression respects specified symmetries.

    Structural check that symmetry analysis has been documented.
    Actual verification should use CAS or explicit transformation.

    Args:
        expression: The expression to check
        symmetries: List of symmetries to verify. E.g.,
                    ["Lorentz invariance", "gauge invariance", "parity"]
    """
    try:
        with gpd_span("mcp.verification.symmetry_check"):
            return _symmetry_check_inner(expression, symmetries)
    except Exception as exc:
        logger.warning("symmetry_check failed: %s", exc)
        return {"error": str(exc)}


def _symmetry_check_inner(expression: str, symmetries: list[str]) -> dict:
    # Map common symmetry names to verification strategies
    symmetry_strategies: dict[str, str] = {
        "lorentz": "Express result in manifestly covariant form (4-vectors, invariants s,t,u)",
        "gauge": "Compute same observable in two different gauges; results must agree",
        "parity": "Apply x -> -x and check even/odd behavior matches expectation",
        "time-reversal": "Apply t -> -t and check behavior",
        "cpt": "Apply combined C, P, T transformation; must be invariant in local QFT",
        "conformal": "Check power-law behavior at critical points; verify Ward identities",
        "chiral": "Check left-right decomposition; verify axial current conservation/anomaly",
        "rotational": "Express in spherical harmonics or check angular momentum conservation",
        "translational": "Verify momentum conservation / spatial homogeneity",
        "scale": "Check dimensionless ratios are scale-independent",
        "particle-exchange": "Verify bosonic (symmetric) or fermionic (antisymmetric) behavior",
        "charge-conjugation": "Check particle <-> antiparticle symmetry",
        "su(3)": "Verify color singlet nature of observables",
        "su(2)": "Verify isospin quantum numbers",
        "u(1)": "Verify charge conservation",
    }

    results: list[dict[str, object]] = []
    for sym in symmetries:
        sym_lower = sym.lower().replace(" ", "").replace("-", "").replace("_", "")

        strategy = None
        matched_type = None
        for key, strat in symmetry_strategies.items():
            if key.replace(" ", "").replace("-", "").replace("_", "") in sym_lower or sym_lower in key:
                strategy = strat
                matched_type = key
                break

        results.append(
            {
                "symmetry": sym,
                "matched_type": matched_type,
                "strategy": strategy or f"Apply {sym} transformation to expression and verify expected behavior",
                "status": "requires_verification",
            }
        )

    return {
        "expression_length": len(expression),
        "symmetries_checked": len(results),
        "results": results,
    }


@mcp.tool()
def get_verification_coverage(error_class_ids: list[int], active_checks: list[str]) -> dict:
    """Return gap analysis: which error classes are covered by active checks.

    Maps error class IDs against the set of verification checks that are
    currently active (determined by profile). Identifies gaps where error
    classes have no active detection.

    Args:
        error_class_ids: List of error class IDs to check coverage for
        active_checks: List of active check IDs (e.g., ["5.1", "5.2", "5.3"])
    """
    try:
        with gpd_span("mcp.verification.coverage"):
            return _coverage_inner(error_class_ids, active_checks)
    except Exception as exc:
        logger.warning("get_verification_coverage failed: %s", exc)
        return {"error": str(exc)}


def _coverage_inner(error_class_ids: list[int], active_checks: list[str]) -> dict:
    covered: list[dict[str, object]] = []
    uncovered: list[dict[str, object]] = []
    partial: list[dict[str, object]] = []

    for ec_id in error_class_ids:
        ec_meta = ERROR_CLASS_COVERAGE.get(ec_id)
        if ec_meta is None:
            uncovered.append(
                {
                    "error_class_id": ec_id,
                    "status": "unknown",
                    "message": f"Error class {ec_id} not in coverage database",
                }
            )
            continue

        primary = ec_meta["primary_checks"]
        active_primary = [c for c in primary if c in active_checks]

        entry: dict[str, object] = {
            "error_class_id": ec_id,
            "name": ec_meta["name"],
            "required_checks": primary,
            "active_checks": active_primary,
            "domains": ec_meta["domains"],
        }

        if len(active_primary) == len(primary):
            entry["status"] = "covered"
            covered.append(entry)
        elif len(active_primary) > 0:
            entry["status"] = "partial"
            entry["missing_checks"] = [c for c in primary if c not in active_checks]
            partial.append(entry)
        else:
            entry["status"] = "uncovered"
            entry["missing_checks"] = primary
            uncovered.append(entry)

    total = len(error_class_ids)
    covered_count = len(covered)
    coverage_percent = round(covered_count / total * 100, 1) if total > 0 else 0.0

    return {
        "total_classes": total,
        "covered": covered_count,
        "partial": len(partial),
        "uncovered": len(uncovered),
        "coverage_percent": coverage_percent,
        "covered_classes": covered,
        "partial_classes": partial,
        "uncovered_classes": uncovered,
        "active_checks": active_checks,
        "recommendation": (
            "Full coverage"
            if len(uncovered) == 0 and len(partial) == 0
            else (
                f"{len(partial)} error classes have partial coverage. "
                f"Consider enabling checks: {sorted({c for p in partial for c in p.get('missing_checks', [])})}"
            )
            if len(uncovered) == 0
            else (
                f"{len(uncovered)} error classes have no active detection. "
                f"Consider enabling checks: {sorted({c for u in uncovered for c in u.get('missing_checks', [])} | {c for p in partial for c in p.get('missing_checks', [])})}"
            )
        ),
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the gpd-verification MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Verification MCP Server")


if __name__ == "__main__":
    main()
