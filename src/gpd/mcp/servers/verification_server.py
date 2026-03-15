"""MCP server for GPD physics verification.

Exposes verification checks as MCP tools for solver agents to run
dimensional analysis, limiting case checks, symmetry verification,
and domain-specific checklists.

Usage:
    python -m gpd.mcp.servers.verification_server
    # or via entry point:
    gpd-mcp-verification
"""

import copy
import logging
import re
import sys
from collections.abc import Iterable

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import ResearchContract
from gpd.core.observability import gpd_span
from gpd.core.protocol_bundles import ResolvedProtocolBundle, get_protocol_bundle, render_protocol_bundle_context
from gpd.core.verification_checks import (
    ERROR_CLASS_COVERAGE,
    VERIFICATION_CHECK_IDS,
    VERIFICATION_SCHEMA_VERSION,
    get_verification_check,
    list_verification_checks,
)

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-verification")

mcp = FastMCP("gpd-verification")

_CONTRACT_CHECK_REQUEST_HINTS: dict[str, dict[str, object]] = {
    "contract.limit_recovery": {
        "required_request_fields": ["metadata.regime_label", "metadata.expected_behavior"],
        "optional_request_fields": ["binding.*", "observed.limit_passed", "observed.observed_limit", "artifact_content"],
        "request_template": {
            "binding": {},
            "metadata": {
                "regime_label": "infrared limit",
                "expected_behavior": "matches the contracted asymptotic scaling",
            },
            "observed": {
                "limit_passed": True,
                "observed_limit": "power-law slope -1",
            },
            "artifact_content": "",
        },
    },
    "contract.benchmark_reproduction": {
        "required_request_fields": [
            "metadata.source_reference_id",
            "observed.metric_value",
            "observed.threshold_value",
        ],
        "optional_request_fields": ["binding.*", "artifact_content"],
        "request_template": {
            "binding": {},
            "metadata": {
                "source_reference_id": "ref-benchmark",
            },
            "observed": {
                "metric_value": 0.008,
                "threshold_value": 0.01,
            },
            "artifact_content": "",
        },
    },
    "contract.direct_proxy_consistency": {
        "required_request_fields": [],
        "optional_request_fields": [
            "binding.*",
            "observed.proxy_only",
            "observed.direct_available",
            "observed.proxy_available",
            "observed.consistency_passed",
            "artifact_content",
        ],
        "request_template": {
            "binding": {},
            "metadata": {},
            "observed": {
                "proxy_only": False,
                "direct_available": True,
                "proxy_available": True,
                "consistency_passed": True,
            },
            "artifact_content": "",
        },
    },
    "contract.fit_family_mismatch": {
        "required_request_fields": ["metadata.declared_family", "observed.selected_family"],
        "optional_request_fields": [
            "binding.*",
            "metadata.allowed_families[]",
            "metadata.forbidden_families[]",
            "observed.competing_family_checked",
            "artifact_content",
        ],
        "request_template": {
            "binding": {},
            "metadata": {
                "declared_family": "linear",
                "allowed_families": ["linear", "quadratic"],
                "forbidden_families": [],
            },
            "observed": {
                "selected_family": "linear",
                "competing_family_checked": True,
            },
            "artifact_content": "",
        },
    },
    "contract.estimator_family_mismatch": {
        "required_request_fields": ["metadata.declared_family", "observed.selected_family"],
        "optional_request_fields": [
            "binding.*",
            "metadata.allowed_families[]",
            "metadata.forbidden_families[]",
            "observed.bias_checked",
            "observed.calibration_checked",
            "artifact_content",
        ],
        "request_template": {
            "binding": {},
            "metadata": {
                "declared_family": "bootstrap",
                "allowed_families": ["bootstrap", "jackknife"],
                "forbidden_families": [],
            },
            "observed": {
                "selected_family": "bootstrap",
                "bias_checked": True,
                "calibration_checked": True,
            },
            "artifact_content": "",
        },
    },
}


def _contract_check_request_hint(check_key: str) -> dict[str, object]:
    hint = _CONTRACT_CHECK_REQUEST_HINTS.get(check_key, {})
    return {
        "required_request_fields": list(hint.get("required_request_fields", [])),
        "optional_request_fields": list(hint.get("optional_request_fields", [])),
        "request_template": copy.deepcopy(hint.get("request_template", {})),
    }


def _normalize_optional_scalar_str(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


def _normalize_string_list(value: object) -> object:
    if not isinstance(value, list):
        return value
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if stripped:
            normalized.append(stripped)
    return normalized


def _normalize_contract_metadata(metadata: dict[str, object]) -> dict[str, object]:
    normalized = dict(metadata)
    for key in ("regime_label", "expected_behavior", "source_reference_id", "declared_family"):
        if key in normalized:
            normalized[key] = _normalize_optional_scalar_str(normalized[key])
    for key in ("allowed_families", "forbidden_families"):
        if key in normalized:
            normalized[key] = _normalize_string_list(normalized[key])
    return normalized


def _serialize_verification_check_entry(check_entry: dict[str, object]) -> dict[str, object]:
    serialized = dict(check_entry)
    if bool(serialized.get("contract_aware")):
        serialized.update(_contract_check_request_hint(str(serialized.get("check_key") or "")))
    return serialized

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
    "algebraic_qft": [
        {"check": "Wightman axioms satisfied (temperedness, spectral condition, locality)", "check_ids": "5.3,5.4"},
        {"check": "Haag-Kastler net isotony and locality verified", "check_ids": "5.3"},
        {"check": "Reeh-Schlieder property accounted for", "check_ids": "5.10"},
        {"check": "PCT theorem assumptions validated", "check_ids": "5.4"},
    ],
    "string_field_theory": [
        {"check": "BRST cohomology correctly identifies physical states", "check_ids": "5.3,5.9"},
        {"check": "Ghost number conservation at each vertex", "check_ids": "5.4"},
        {"check": "L_infinity / A_infinity relations verified", "check_ids": "5.4"},
        {"check": "Gauge invariance of observables confirmed", "check_ids": "5.3,5.9"},
    ],
    "classical_mechanics": [
        {"check": "Energy conservation (T + V = const for conservative systems)", "check_ids": "5.4"},
        {"check": "Hamilton's equations consistent with Lagrangian formulation", "check_ids": "5.3"},
        {"check": "Canonical transformation preserves Poisson brackets", "check_ids": "5.4"},
        {"check": "Action principle yields correct Euler-Lagrange equations", "check_ids": "5.3"},
    ],
}


def _error_result(message: object) -> dict[str, object]:
    """Return a stable MCP error envelope for verification tools."""
    return {
        "error": str(message),
        "schema_version": VERIFICATION_SCHEMA_VERSION,
    }


def _optional_mapping_field(request: dict[str, object], field_name: str) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Return an optional mapping payload or an MCP error envelope."""
    raw = request.get(field_name)
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, _error_result(f"{field_name} must be an object")
    return raw, None

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
    with gpd_span("mcp.verification.run_check", check_type=check_id, domain=domain):
        try:
            check_meta = get_verification_check(check_id)
            if check_meta is None:
                return _error_result(
                    f"Unknown check_id: {check_id}. Valid check ids: {list(VERIFICATION_CHECK_IDS)}"
                )

            # Get domain-specific guidance
            domain_checks = DOMAIN_CHECKLISTS.get(domain, [])
            relevant_domain_checks = [
                c
                for c in domain_checks
                if check_meta.check_id in [token.strip() for token in c.get("check_ids", "").split(",") if token.strip()]
            ]

            # Scan artifact for obvious issues
            issues: list[str] = []
            artifact_lower = artifact_content.lower()

            if check_meta.check_id == "5.1":
                # Dimensional analysis: look for common pitfalls
                if "hbar" not in artifact_content and "\\hbar" not in artifact_content:
                    if any(kw in artifact_lower for kw in ["quantum", "planck", "commutator"]):
                        issues.append("Quantum context detected but no hbar found -- check natural unit conventions")
                if re.search(r"exp\s*\([^)]*\[(?:M|L|T|Q|Theta)\]", artifact_content):
                    issues.append("Possible dimensionful argument to exponential")

            elif check_meta.check_id == "5.3":
                # Limiting cases: check if any limits are discussed
                limit_keywords = ["limit", "->", "\\to", "limiting", "reduces to", "special case"]
                has_limits = any(kw in artifact_lower for kw in limit_keywords)
                if not has_limits:
                    issues.append("No limiting case analysis found in artifact")

            elif check_meta.check_id == "5.15":
                limit_keywords = ["limit", "asymptotic", "boundary", "scaling", "regime", "\\to", "->"]
                if not any(kw in artifact_lower for kw in limit_keywords):
                    issues.append("No explicit contracted limit or asymptotic regime found in artifact")

            elif check_meta.check_id == "5.16":
                benchmark_keywords = ["benchmark", "baseline", "published", "reference", "prior work", "agreement"]
                if not any(kw in artifact_lower for kw in benchmark_keywords):
                    issues.append("No decisive benchmark or baseline comparison found in artifact")

            elif check_meta.check_id == "5.17":
                proxy_keywords = ["proxy", "surrogate", "heuristic", "loss", "trend", "qualitative"]
                direct_keywords = ["direct", "benchmark", "observable", "measured", "ground truth", "anchor"]
                if any(kw in artifact_lower for kw in proxy_keywords) and not any(
                    kw in artifact_lower for kw in direct_keywords
                ):
                    issues.append("Proxy or surrogate evidence appears without a direct anchor comparison")

            elif check_meta.check_id == "5.18":
                fit_keywords = ["fit", "regression", "extrapolat", "ansatz", "model family"]
                diagnostics = ["residual", "aic", "bic", "cross-validation", "goodness of fit", "family comparison"]
                if any(kw in artifact_lower for kw in fit_keywords) and not any(kw in artifact_lower for kw in diagnostics):
                    issues.append("Fit family is present without residual or family-selection diagnostics")

            elif check_meta.check_id == "5.19":
                estimator_keywords = ["estimator", "bootstrap", "jackknife", "posterior", "bayesian", "reweight"]
                diagnostics = ["bias", "variance", "consistency", "calibration", "ess", "autocorrelation"]
                if any(kw in artifact_lower for kw in estimator_keywords) and not any(
                    kw in artifact_lower for kw in diagnostics
                ):
                    issues.append("Estimator family is present without bias/variance or calibration diagnostics")

            result = _serialize_verification_check_entry(check_meta.model_dump())
            result.update(
                {
                    "schema_version": VERIFICATION_SCHEMA_VERSION,
                    "check_name": check_meta.name,
                    "domain": domain,
                    "domain_specific_checks": relevant_domain_checks,
                    "automated_issues": issues,
                    "artifact_length": len(artifact_content),
                    "guidance": (
                        f"Run check {check_meta.check_id} ({check_meta.name}) for domain '{domain}'. "
                        f"This check catches: {check_meta.catches}."
                    ),
                }
            )
            return result
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


def _truthy(value: object) -> bool:
    return value in (True, "true", "True", 1, "1", "yes", "YES")


def _binding_values_for_target(binding: dict[str, object], target: str) -> list[str]:
    values: list[str] = []
    for key in (f"{target}_id", f"{target}_ids"):
        raw = binding.get(key)
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped:
                values.append(stripped)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    stripped = item.strip()
                    if stripped:
                        values.append(stripped)
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _contract_ids_for_target(contract: ResearchContract, target: str) -> set[str]:
    if target == "observable":
        return {observable.id for observable in contract.observables}
    if target == "claim":
        return {claim.id for claim in contract.claims}
    if target == "deliverable":
        return {deliverable.id for deliverable in contract.deliverables}
    if target == "acceptance_test":
        return {test.id for test in contract.acceptance_tests}
    if target == "reference":
        return {reference.id for reference in contract.references}
    if target == "forbidden_proxy":
        return {proxy.id for proxy in contract.forbidden_proxies}
    return set()


def _collect_binding_context(
    *,
    check_targets: Iterable[str],
    binding: dict[str, object],
    contract: ResearchContract | None,
) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """Return valid binding ids by target, user-facing issues, and contract impacts."""

    valid_by_target: dict[str, list[str]] = {}
    binding_issues: list[str] = []
    contract_impacts: list[str] = []

    for target in check_targets:
        values = _binding_values_for_target(binding, target)
        if not values:
            continue
        if contract is None:
            valid_by_target[target] = values
            contract_impacts.extend(values)
            continue

        known_ids = _contract_ids_for_target(contract, target)
        valid_values = [value for value in values if value in known_ids]
        unknown_values = [value for value in values if value not in known_ids]
        if valid_values:
            valid_by_target[target] = valid_values
            contract_impacts.extend(valid_values)
        if unknown_values:
            suffix = "id" if len(unknown_values) == 1 else "ids"
            binding_issues.append(
                f"binding.{target}_{suffix} references unknown contract {target} {', '.join(unknown_values)}"
            )

    return valid_by_target, binding_issues, contract_impacts


def _unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _benchmark_reference_candidates(
    contract: ResearchContract,
    binding_ids: dict[str, list[str]],
) -> list[str]:
    benchmark_refs = [
        reference
        for reference in contract.references
        if reference.role == "benchmark" or "compare" in reference.required_actions
    ]
    references_by_id = {reference.id: reference for reference in benchmark_refs}
    claims_by_id = {claim.id: claim for claim in contract.claims}
    tests_by_id = {test.id: test for test in contract.acceptance_tests}

    explicit_reference_ids = [
        reference_id for reference_id in binding_ids.get("reference", []) if reference_id in references_by_id
    ]
    if explicit_reference_ids:
        return _unique_strings(explicit_reference_ids)

    candidate_claim_ids: set[str] = set(binding_ids.get("claim", []))
    candidate_subject_ids: set[str] = set(binding_ids.get("deliverable", []))
    candidate_subject_ids.update(candidate_claim_ids)

    for test_id in binding_ids.get("acceptance_test", []):
        test = tests_by_id.get(test_id)
        if test is None:
            continue
        candidate_subject_ids.add(test.subject)
        candidate_claim_ids.add(test.subject)
        for evidence_id in test.evidence_required:
            if evidence_id in references_by_id:
                explicit_reference_ids.append(evidence_id)

    if explicit_reference_ids:
        return _unique_strings(explicit_reference_ids)

    candidate_reference_ids: list[str] = []
    for claim_id in candidate_claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        candidate_reference_ids.extend(
            reference_id for reference_id in claim.references if reference_id in references_by_id
        )

    for reference in benchmark_refs:
        if candidate_subject_ids and set(reference.applies_to).intersection(candidate_subject_ids):
            candidate_reference_ids.append(reference.id)

    if candidate_reference_ids:
        return _unique_strings(candidate_reference_ids)

    if not binding_ids and len(benchmark_refs) == 1:
        return [benchmark_refs[0].id]

    return []


def _limit_regime_candidates(contract: ResearchContract, binding_ids: dict[str, list[str]]) -> list[str]:
    observables_by_id = {observable.id: observable for observable in contract.observables}
    claims_by_id = {claim.id: claim for claim in contract.claims}
    tests_by_id = {test.id: test for test in contract.acceptance_tests}

    candidate_regimes: list[str] = []
    for observable_id in binding_ids.get("observable", []):
        observable = observables_by_id.get(observable_id)
        if observable is not None and observable.regime:
            candidate_regimes.append(observable.regime)

    claim_ids = list(binding_ids.get("claim", []))
    for test_id in binding_ids.get("acceptance_test", []):
        test = tests_by_id.get(test_id)
        if test is not None:
            claim_ids.append(test.subject)

    for claim_id in _unique_strings(claim_ids):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        for observable_id in claim.observables:
            observable = observables_by_id.get(observable_id)
            if observable is not None and observable.regime:
                candidate_regimes.append(observable.regime)

    candidate_regimes = _unique_strings(candidate_regimes)
    if candidate_regimes:
        return candidate_regimes

    global_regimes = _unique_strings(
        observable.regime for observable in contract.observables if observable.regime
    )
    if not binding_ids and len(global_regimes) == 1:
        return global_regimes
    return []


def _validate_benchmark_reference_binding(
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    source_reference_id: object,
) -> tuple[str | None, str | None]:
    """Validate that a benchmark anchor exists and matches the bound contract context."""

    source_reference_id = _normalize_optional_scalar_str(source_reference_id)
    if not isinstance(source_reference_id, str) or not source_reference_id:
        return None, None
    if contract is None:
        return source_reference_id, None
    if source_reference_id not in _contract_ids_for_target(contract, "reference"):
        return None, f"metadata.source_reference_id references unknown contract reference {source_reference_id}"

    candidates = _benchmark_reference_candidates(contract, binding_ids)
    if binding_ids and candidates and source_reference_id not in candidates:
        expected = ", ".join(candidates)
        return None, (
            "metadata.source_reference_id does not match the bound contract context; "
            f"expected one of {expected}"
        )
    return source_reference_id, None


def _validate_limit_regime_binding(
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    regime_label: object,
) -> tuple[str | None, str | None]:
    """Validate that a regime label matches the bound contract context when known."""

    regime_label = _normalize_optional_scalar_str(regime_label)
    if not isinstance(regime_label, str) or not regime_label:
        return None, None
    if contract is None:
        return regime_label, None

    candidates = _limit_regime_candidates(contract, binding_ids)
    if binding_ids and candidates and regime_label not in candidates:
        expected = ", ".join(candidates)
        return None, (
            "metadata.regime_label does not match the bound contract context; "
            f"expected one of {expected}"
        )
    return regime_label, None


def _with_contract_policy_defaults(
    check_key: str,
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    metadata: dict[str, object],
) -> dict[str, object]:
    """Fill contract-check metadata from structured contract policy when missing."""

    if contract is None:
        return metadata

    enriched = dict(metadata)
    if check_key == "contract.benchmark_reproduction" and not enriched.get("source_reference_id"):
        candidates = _benchmark_reference_candidates(contract, binding_ids)
        if len(candidates) == 1:
            enriched["source_reference_id"] = candidates[0]

    if check_key == "contract.fit_family_mismatch":
        if not enriched.get("allowed_families") and contract.approach_policy.allowed_fit_families:
            enriched["allowed_families"] = list(contract.approach_policy.allowed_fit_families)
        if not enriched.get("forbidden_families") and contract.approach_policy.forbidden_fit_families:
            enriched["forbidden_families"] = list(contract.approach_policy.forbidden_fit_families)

    if check_key == "contract.estimator_family_mismatch":
        if not enriched.get("allowed_families") and contract.approach_policy.allowed_estimator_families:
            enriched["allowed_families"] = list(contract.approach_policy.allowed_estimator_families)
        if not enriched.get("forbidden_families") and contract.approach_policy.forbidden_estimator_families:
            enriched["forbidden_families"] = list(contract.approach_policy.forbidden_estimator_families)

    if check_key == "contract.limit_recovery":
        if not enriched.get("regime_label"):
            candidates = _limit_regime_candidates(contract, binding_ids)
            if len(candidates) == 1:
                enriched["regime_label"] = candidates[0]

    return enriched


@mcp.tool()
def run_contract_check(request: dict) -> dict:
    """Run a contract-aware verification check using structured metadata."""

    with gpd_span("mcp.verification.run_contract_check"):
        try:
            check_id = str(request.get("check_key") or request.get("check_id") or "").strip()
            if not check_id:
                return _error_result("Missing check_key or check_id")

            check_meta = get_verification_check(check_id)
            if check_meta is None:
                return _error_result(f"Unknown contract check: {check_id}")
            if not check_meta.contract_aware:
                return _error_result(f"Check {check_id} is not contract-aware")

            contract_raw, error = _optional_mapping_field(request, "contract")
            if error is not None:
                return error
            binding_raw, error = _optional_mapping_field(request, "binding")
            if error is not None:
                return error
            metadata_raw, error = _optional_mapping_field(request, "metadata")
            if error is not None:
                return error
            observed_raw, error = _optional_mapping_field(request, "observed")
            if error is not None:
                return error

            contract = None
            if contract_raw is not None:
                try:
                    contract = ResearchContract.model_validate(contract_raw)
                except Exception as exc:  # pragma: no cover - pydantic version specifics
                    return _error_result(f"Invalid contract payload: {exc}")

            binding = binding_raw or {}
            metadata = _normalize_contract_metadata(metadata_raw or {})
            observed = observed_raw or {}
            artifact_content = str(request.get("artifact_content") or "")
            binding_ids, binding_issues, contract_impacts = _collect_binding_context(
                check_targets=check_meta.binding_targets,
                binding=binding,
                contract=contract,
            )
            metadata = _with_contract_policy_defaults(
                check_meta.check_key,
                contract=contract,
                binding_ids=binding_ids,
                metadata=metadata,
            )

            missing_inputs: list[str] = []
            automated_issues: list[str] = []
            metrics: dict[str, object] = {}
            status = "insufficient_evidence"
            evidence_directness = "metadata_only"
            automated_issues.extend(binding_issues)

            if check_meta.check_key == "contract.limit_recovery":
                regime_label = metadata.get("regime_label")
                expected_behavior = _normalize_optional_scalar_str(metadata.get("expected_behavior"))
                regime_label, regime_issue = _validate_limit_regime_binding(
                    contract=contract,
                    binding_ids=binding_ids,
                    regime_label=regime_label,
                )
                if regime_issue:
                    automated_issues.append(regime_issue)
                if not regime_label:
                    missing_inputs.append("metadata.regime_label")
                if not expected_behavior:
                    missing_inputs.append("metadata.expected_behavior")
                limit_passed = observed.get("limit_passed")
                observed_limit = observed.get("observed_limit")
                metrics["regime_label"] = regime_label
                metrics["observed_limit"] = observed_limit
                if limit_passed is True and not missing_inputs:
                    status = "pass"
                    evidence_directness = "direct"
                elif limit_passed is False and not missing_inputs:
                    automated_issues.append("Observed limit behavior does not match the contracted asymptotic expectation")
                    status = "fail"
                    evidence_directness = "direct"
                elif artifact_content and any(token in artifact_content.lower() for token in ["limit", "asymptotic", "scaling", "boundary"]):
                    status = "warning"
                    evidence_directness = "mixed"
                elif not missing_inputs:
                    automated_issues.append("No direct limit or asymptotic evidence was supplied")
                    status = "fail"

            elif check_meta.check_key == "contract.benchmark_reproduction":
                source_reference_id = metadata.get("source_reference_id")
                metric_value = observed.get("metric_value")
                threshold_value = observed.get("threshold_value")
                source_reference_id, source_reference_issue = _validate_benchmark_reference_binding(
                    contract=contract,
                    binding_ids=binding_ids,
                    source_reference_id=source_reference_id,
                )
                if source_reference_issue:
                    automated_issues.append(source_reference_issue)
                if not source_reference_id:
                    missing_inputs.append("metadata.source_reference_id")
                if metric_value is None:
                    missing_inputs.append("observed.metric_value")
                if threshold_value is None:
                    missing_inputs.append("observed.threshold_value")
                metrics["source_reference_id"] = source_reference_id
                metrics["metric_value"] = metric_value
                metrics["threshold_value"] = threshold_value
                if (
                    isinstance(metric_value, (int, float))
                    and isinstance(threshold_value, (int, float))
                    and source_reference_id
                ):
                    evidence_directness = "direct"
                    if metric_value <= threshold_value:
                        status = "pass"
                    else:
                        automated_issues.append("Benchmark comparison exceeds the allowed tolerance")
                        status = "fail"
                elif artifact_content and any(token in artifact_content.lower() for token in ["benchmark", "baseline", "published", "reference"]):
                    status = "warning"
                    evidence_directness = "mixed"

            elif check_meta.check_key == "contract.direct_proxy_consistency":
                proxy_only = _truthy(observed.get("proxy_only"))
                direct_available = _truthy(observed.get("direct_available"))
                proxy_available = _truthy(observed.get("proxy_available"))
                consistency_passed = observed.get("consistency_passed")
                metrics.update(
                    {
                        "proxy_only": proxy_only,
                        "direct_available": direct_available,
                        "proxy_available": proxy_available,
                        "consistency_passed": consistency_passed,
                    }
                )
                if proxy_only or (proxy_available and not direct_available):
                    automated_issues.append("Proxy evidence was supplied without a decisive direct observable")
                    status = "fail"
                    evidence_directness = "proxy"
                elif direct_available and proxy_available and consistency_passed is True:
                    status = "pass"
                    evidence_directness = "mixed"
                elif direct_available and proxy_available and consistency_passed is False:
                    automated_issues.append("Direct and proxy evidence disagree")
                    status = "fail"
                    evidence_directness = "mixed"
                elif direct_available:
                    status = "warning"
                    evidence_directness = "direct"

            elif check_meta.check_key == "contract.fit_family_mismatch":
                declared_family = _normalize_optional_scalar_str(metadata.get("declared_family"))
                selected_family = observed.get("selected_family")
                allowed = {str(item) for item in metadata.get("allowed_families", []) if isinstance(item, str)}
                forbidden = {str(item) for item in metadata.get("forbidden_families", []) if isinstance(item, str)}
                competing_checked = observed.get("competing_family_checked")
                if not declared_family:
                    missing_inputs.append("metadata.declared_family")
                if selected_family is None:
                    missing_inputs.append("observed.selected_family")
                metrics.update(
                    {
                        "declared_family": declared_family,
                        "selected_family": selected_family,
                        "allowed_families": sorted(allowed),
                        "forbidden_families": sorted(forbidden),
                        "competing_family_checked": competing_checked,
                    }
                )
                evidence_directness = "direct"
                if isinstance(selected_family, str) and selected_family in forbidden:
                    automated_issues.append("Selected fit family is explicitly forbidden")
                    status = "fail"
                elif allowed and isinstance(selected_family, str) and selected_family not in allowed:
                    automated_issues.append("Selected fit family is outside the allowed family set")
                    status = "fail"
                elif isinstance(selected_family, str) and declared_family and selected_family != declared_family:
                    automated_issues.append("Selected fit family does not match the contracted family")
                    status = "fail"
                elif isinstance(selected_family, str) and competing_checked is False:
                    automated_issues.append("Fit family was not compared against competing families")
                    status = "warning"
                elif isinstance(selected_family, str) and declared_family:
                    status = "pass"

            elif check_meta.check_key == "contract.estimator_family_mismatch":
                declared_family = _normalize_optional_scalar_str(metadata.get("declared_family"))
                selected_family = observed.get("selected_family")
                allowed = {str(item) for item in metadata.get("allowed_families", []) if isinstance(item, str)}
                forbidden = {str(item) for item in metadata.get("forbidden_families", []) if isinstance(item, str)}
                bias_checked = observed.get("bias_checked")
                calibration_checked = observed.get("calibration_checked")
                if not declared_family:
                    missing_inputs.append("metadata.declared_family")
                if selected_family is None:
                    missing_inputs.append("observed.selected_family")
                metrics.update(
                    {
                        "declared_family": declared_family,
                        "selected_family": selected_family,
                        "allowed_families": sorted(allowed),
                        "forbidden_families": sorted(forbidden),
                        "bias_checked": bias_checked,
                        "calibration_checked": calibration_checked,
                    }
                )
                evidence_directness = "direct"
                if isinstance(selected_family, str) and selected_family in forbidden:
                    automated_issues.append("Selected estimator family is explicitly forbidden")
                    status = "fail"
                elif allowed and isinstance(selected_family, str) and selected_family not in allowed:
                    automated_issues.append("Selected estimator family is outside the allowed family set")
                    status = "fail"
                elif isinstance(selected_family, str) and declared_family and selected_family != declared_family:
                    automated_issues.append("Selected estimator family does not match the contracted family")
                    status = "fail"
                elif isinstance(selected_family, str) and (bias_checked is False or calibration_checked is False):
                    automated_issues.append("Estimator family is missing bias or calibration diagnostics")
                    status = "warning"
                elif (
                    isinstance(selected_family, str)
                    and declared_family
                    and bias_checked is True
                    and calibration_checked is True
                ):
                    status = "pass"

            if contract is not None:
                metrics["contract_claim_count"] = len(contract.claims)
                metrics["contract_deliverable_count"] = len(contract.deliverables)
            if binding_issues and status != "insufficient_evidence":
                automated_issues.append("Binding validation issues prevent a decisive contract-aware verdict")
                status = "insufficient_evidence"
                evidence_directness = "mixed" if artifact_content else "metadata_only"

            return {
                "schema_version": VERIFICATION_SCHEMA_VERSION,
                "check_id": check_meta.check_id,
                "check_key": check_meta.check_key,
                "check_name": check_meta.name,
                "check_class": check_meta.check_class,
                "contract_aware": check_meta.contract_aware,
                "binding_targets": check_meta.binding_targets,
                "status": status,
                "evidence_directness": evidence_directness,
                "binding": binding,
                "missing_inputs": missing_inputs,
                "automated_issues": automated_issues,
                "metrics": metrics,
                "contract_impacts": contract_impacts,
                "guidance": check_meta.oracle_hint,
            }
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


@mcp.tool()
def suggest_contract_checks(contract: dict, active_checks: list[str] | None = None) -> dict:
    """Suggest generic contract-aware checks from a project or phase contract."""

    with gpd_span("mcp.verification.suggest_contract_checks"):
        try:
            parsed = ResearchContract.model_validate(contract)
            active = set(active_checks or [])
            suggestions: list[dict[str, object]] = []

            def _add(check_key: str, reason: str) -> None:
                meta = get_verification_check(check_key)
                if meta is None:
                    return
                request_hint = _contract_check_request_hint(meta.check_key)
                suggestions.append(
                    {
                        "check_id": meta.check_id,
                        "check_key": meta.check_key,
                        "name": meta.name,
                        "reason": reason,
                        "already_active": meta.check_id in active or meta.check_key in active,
                        "binding_targets": meta.binding_targets,
                        **request_hint,
                    }
                )

            if any(test.kind == "benchmark" for test in parsed.acceptance_tests) or any(
                reference.role == "benchmark" or "compare" in reference.required_actions for reference in parsed.references
            ):
                _add(
                    "contract.benchmark_reproduction",
                    "Benchmark-style acceptance tests or benchmark anchors are present",
                )

            if parsed.forbidden_proxies:
                _add("contract.direct_proxy_consistency", "Forbidden proxies require direct-vs-proxy checks")

            if any(observable.regime for observable in parsed.observables) or any(
                keyword in " ".join([test.procedure, test.pass_condition]).lower()
                for test in parsed.acceptance_tests
                for keyword in ("limit", "asymptotic", "boundary", "scaling")
            ):
                _add("contract.limit_recovery", "Contract mentions regimes or limit-like acceptance behavior")

            if any(
                keyword in " ".join([test.procedure, test.pass_condition]).lower()
                for test in parsed.acceptance_tests
                for keyword in ("fit", "residual", "extrapolat", "ansatz")
            ) or parsed.approach_policy.allowed_fit_families or parsed.approach_policy.forbidden_fit_families:
                _add("contract.fit_family_mismatch", "Acceptance tests mention fitting or extrapolation families")

            if any(
                keyword in " ".join([test.procedure, test.pass_condition]).lower()
                for test in parsed.acceptance_tests
                for keyword in ("estimator", "bootstrap", "jackknife", "posterior", "bias", "variance")
            ) or parsed.approach_policy.allowed_estimator_families or parsed.approach_policy.forbidden_estimator_families:
                _add(
                    "contract.estimator_family_mismatch",
                    "Acceptance tests mention estimator-family assumptions",
                )

            return {
                "schema_version": VERIFICATION_SCHEMA_VERSION,
                "suggested_checks": suggestions,
                "suggested_count": len(suggestions),
            }
        except Exception as exc:  # pragma: no cover - defensive envelope
            if isinstance(exc, PydanticValidationError):
                return _error_result(f"Invalid contract payload: {exc}")
            return _error_result(exc)


@mcp.tool()
def get_checklist(domain: str) -> dict:
    """Return the domain-specific verification checklist.

    Provides the complete list of checks recommended for a physics domain,
    including which universal checks (5.1-5.14) each maps to.
    """
    with gpd_span("mcp.verification.checklist", domain=domain):
        try:
            checklist = DOMAIN_CHECKLISTS.get(domain)
            if checklist is None:
                return {
                    "found": False,
                    "schema_version": VERIFICATION_SCHEMA_VERSION,
                    "domain": domain,
                    "available_domains": sorted(DOMAIN_CHECKLISTS.keys()),
                    "message": f"No checklist for domain '{domain}'.",
                }

            # Also include the universal checks
            universal = [_serialize_verification_check_entry(entry) for entry in list_verification_checks()]

            return {
                "found": True,
                "schema_version": VERIFICATION_SCHEMA_VERSION,
                "domain": domain,
                "domain_checks": checklist,
                "domain_check_count": len(checklist),
                "universal_checks": universal,
                "universal_check_count": len(universal),
            }
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


@mcp.tool()
def get_bundle_checklist(bundle_ids: list[str]) -> dict:
    """Return additive verifier checklist extensions for selected protocol bundles."""
    with gpd_span("mcp.verification.bundle_checklist", bundle_count=len(bundle_ids)):
        try:
            bundles: list[dict[str, object]] = []
            resolved_bundles: list[ResolvedProtocolBundle] = []
            checklist: list[dict[str, object]] = []
            missing_bundle_ids: list[str] = []

            for bundle_id in bundle_ids:
                bundle = get_protocol_bundle(bundle_id)
                if bundle is None:
                    missing_bundle_ids.append(bundle_id)
                    continue

                verification_domain_paths = [asset.path for asset in bundle.assets.verification_domains]
                bundle_payload = {
                    "bundle_id": bundle.bundle_id,
                    "title": bundle.title,
                    "summary": bundle.summary,
                    "asset_paths": [asset.path for _role, asset in bundle.assets.iter_assets()],
                    "verification_domains": verification_domain_paths,
                    "verifier_extensions": [extension.model_dump(mode="json") for extension in bundle.verifier_extensions],
                }
                bundles.append(bundle_payload)
                resolved_bundles.append(
                    ResolvedProtocolBundle(
                        bundle_id=bundle.bundle_id,
                        title=bundle.title,
                        summary=bundle.summary,
                        score=0,
                        matched_tags=[],
                        matched_terms=[],
                        selection_tags=bundle.selection_tags,
                        assets=bundle.assets,
                        anchor_prompts=bundle.anchor_prompts,
                        reference_prompts=bundle.reference_prompts,
                        estimator_policies=bundle.estimator_policies,
                        decisive_artifact_guidance=bundle.decisive_artifact_guidance,
                        verifier_extensions=bundle.verifier_extensions,
                    )
                )

                for extension in bundle.verifier_extensions:
                    checklist.append(
                        {
                            "bundle_id": bundle.bundle_id,
                            "bundle_title": bundle.title,
                            "name": extension.name,
                            "rationale": extension.rationale,
                            "check_ids": extension.check_ids,
                        }
                    )

            return {
                "found": bool(bundles),
                "schema_version": VERIFICATION_SCHEMA_VERSION,
                "bundle_count": len(bundles),
                "bundles": bundles,
                "protocol_bundle_context": render_protocol_bundle_context(resolved_bundles),
                "bundle_check_count": len(checklist),
                "bundle_checks": checklist,
                "missing_bundle_ids": missing_bundle_ids,
            }
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


@mcp.tool()
def dimensional_check(expressions: list[str]) -> dict:
    """Verify dimensional consistency of physics expressions.

    Each expression should be in the format "LHS = RHS" where dimensions
    are annotated with [M], [L], [T], [Q], [Theta] notation.

    Example: "[M][L]^2[T]^-2 = [M][L]^2[T]^-2" (energy = energy)
    """
    with gpd_span("mcp.verification.dimensional_check"):
        return _dimensional_check_inner(expressions)


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

    all_valid = bool(results) and all(r.get("valid", False) for r in results)
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
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
    with gpd_span("mcp.verification.limiting_case"):
        return _limiting_case_inner(expression, limits)


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
        "schema_version": VERIFICATION_SCHEMA_VERSION,
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
    with gpd_span("mcp.verification.symmetry_check"):
        return _symmetry_check_inner(expression, symmetries)


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
            key_clean = key.replace(" ", "").replace("-", "").replace("_", "")
            if key_clean == sym_lower:
                strategy = strat
                matched_type = key
                break
            if len(sym_lower) >= 3 and (key_clean in sym_lower or sym_lower in key_clean):
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
        "schema_version": VERIFICATION_SCHEMA_VERSION,
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
    with gpd_span("mcp.verification.coverage"):
        return _coverage_inner(error_class_ids, active_checks)


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
                    "name": "Unknown",
                    "required_checks": [],
                    "active_checks": [],
                    "domains": [],
                    "missing_checks": [],
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
        "schema_version": VERIFICATION_SCHEMA_VERSION,
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
