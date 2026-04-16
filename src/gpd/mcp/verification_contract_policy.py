"""Shared verification contract visibility and strictness text."""

from __future__ import annotations

VERIFICATION_SERVER_DESCRIPTION_INTRO = (
    "GPD physics verification checks. Tools for running contract-aware checks, "
    "dimensional analysis, domain and bundle-specific checklists, limiting case checks, "
    "symmetry verification, and coverage gap analysis."
)
VERIFICATION_CONTRACT_SURFACE_SUMMARY_TEXT = (
    "Contract-aware request surfaces are closed and schema-driven. The full contract payload "
    "rules live on the `contract` input schema. Proof-oriented checks still require an "
    "authoritative contract payload. Missing grounding, evidence, or proof artifacts stay explicit "
    "and must not be invented. Use `suggest_contract_checks(...)` to surface the exact per-check "
    "request metadata before calling `run_contract_check(...)`."
)

VERIFICATION_BINDING_TARGETS = (
    "observable",
    "claim",
    "deliverable",
    "acceptance_test",
    "reference",
    "forbidden_proxy",
)
VERIFICATION_BINDING_FIELD_NAMES = tuple(f"binding.{target}_ids" for target in VERIFICATION_BINDING_TARGETS)

_VERIFICATION_CONTRACT_POLICY_CLAUSES = (
    "Validate contract payloads whose `schema_version` is required and must equal `1`.",
    "Use `required_request_fields`, `schema_required_request_fields`, "
    "`schema_required_request_anyof_fields`, `optional_request_fields`, "
    "`supported_binding_fields`, and `request_template` as the exact per-check request "
    "shape; the supported binding fields are the canonical plural id arrays "
    + ", ".join(f"`{field}`" for field in VERIFICATION_BINDING_FIELD_NAMES)
    + ".",
    "Proof-oriented checks require an authoritative contract payload.",
    "Nested object schemas are closed at every level: unknown top-level or nested keys, "
    "non-object sections, blank strings, and malformed members are hard errors; "
    "recoverable normalization is limited to singleton string/list drift and "
    "closed-enum case drift.",
    "Plan-style contracts need non-empty `context_intake`, explicit non-empty "
    "`uncertainty_markers.weakest_anchors` and "
    "`uncertainty_markers.disconfirming_observations`, and project-scoping payloads "
    "must keep non-empty `scope.in_scope`.",
    "Non-scoping, non-exploratory plans require claims, deliverables, "
    "`acceptance_tests`, non-empty `forbidden_proxies`, and either `references` or "
    "explicit grounding context; scoping-only contracts may omit claims only when they "
    "still preserve a target, unresolved question, or grounding input.",
    "When `references[]` is present and no other concrete grounding exists, at least one "
    "`references[].must_surface=true` anchor is required and its absence is a blocker; "
    "otherwise missing `must_surface=true` is a non-blocking warning that should be repaired. "
    "`references[].carry_forward_to` uses workflow scope labels only, never contract IDs, "
    "and `references[].must_surface` requires non-empty `applies_to` and "
    "`required_actions` lists.",
    "Same-kind IDs must be unique, and target IDs must not be reused across "
    "claim/deliverable/acceptance-test/reference kinds when that would make resolution ambiguous.",
    "Contract context must stay consistent with metadata defaults and explicit metadata fields, "
    "so benchmark anchors, regime labels, and family selections cannot contradict it.",
    "Missing grounding, evidence, prior outputs, or proof artifacts are blockers to surface explicitly, "
    "never invitations to invent replacement content or inferred completion state.",
    "For proof-oriented checks, omit or exactly match derived "
    "`metadata.expected_behavior`, `metadata.claim_statement`, "
    "`metadata.hypothesis_ids`, `metadata.theorem_parameter_symbols`, and "
    "`metadata.conclusion_clause_ids`.",
)

VERIFICATION_CONTRACT_POLICY_TEXT = "Contract payload rules: " + " ".join(
    f"{index}) {clause}"
    for index, clause in enumerate(_VERIFICATION_CONTRACT_POLICY_CLAUSES, start=1)
)


def verification_contract_policy_text() -> str:
    """Return the shared verification contract policy text."""

    return VERIFICATION_CONTRACT_POLICY_TEXT


def verification_contract_surface_summary_text() -> str:
    """Return the concise shared summary for public tool and server descriptions."""

    return VERIFICATION_CONTRACT_SURFACE_SUMMARY_TEXT


def verification_server_description() -> str:
    """Return the public verification server description."""

    return f"{VERIFICATION_SERVER_DESCRIPTION_INTRO} {VERIFICATION_CONTRACT_SURFACE_SUMMARY_TEXT}"
