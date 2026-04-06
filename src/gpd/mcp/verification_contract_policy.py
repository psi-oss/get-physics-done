"""Shared verification contract visibility and strictness text."""

from __future__ import annotations

VERIFICATION_SERVER_DESCRIPTION_INTRO = (
    "GPD physics verification checks. Tools for running contract-aware checks, "
    "dimensional analysis, domain and bundle-specific checklists, limiting case checks, "
    "symmetry verification, and coverage gap analysis."
)

VERIFICATION_CONTRACT_POLICY_TEXT = (
    "Contract-aware tools accept project or phase contract payloads whose `schema_version` "
    "is required and must equal `1`. They expose the exact request shape through "
    "`required_request_fields`, `schema_required_request_fields`, "
    "`schema_required_request_anyof_fields`, `optional_request_fields`, "
    "`supported_binding_fields`, and `request_template`, and surface the supported "
    "binding fields `binding.observable_ids`, `binding.claim_ids`, "
    "`binding.deliverable_ids`, `binding.acceptance_test_ids`, `binding.reference_ids`, "
    "and `binding.forbidden_proxy_ids`. Proof-oriented checks require an authoritative "
    "contract payload. The payload is a hard schema boundary: unknown top-level keys, "
    "non-object sections, blank strings, and malformed members are hard errors, while "
    "the shared parser still normalizes recoverable singleton-string/list drift and "
    "closed-enum case drift. For plan-style contract payloads, `context_intake` must be "
    "non-empty, `uncertainty_markers.weakest_anchors` and "
    "`uncertainty_markers.disconfirming_observations` must stay explicit, and "
    "non-scoping non-exploratory plans require claims, deliverables, "
    "`acceptance_tests`, non-empty `forbidden_proxies`, and either `references` or "
    "explicit grounding context; scoping-only contracts may omit claims only when they "
    "still preserve at least one target, unresolved question, or grounding input. When "
    "`references` are present, at least one `references[].must_surface=true` anchor is "
    "required. Same-kind IDs must be unique; target IDs must not be reused across "
    "claim/deliverable/acceptance-test/reference kinds when that would make resolution "
    "ambiguous. `references[].carry_forward_to` uses workflow scope labels only, never "
    "contract IDs. `references[].must_surface` requires non-empty `applies_to` and "
    "`required_actions` lists. Contract context must stay consistent with metadata "
    "defaults and explicit metadata fields, so benchmark anchors, regime labels, and "
    "family selections cannot contradict the resolved binding. For proof-oriented checks, "
    "contract-derived metadata fields must be omitted or match the resolved defaults "
    "exactly, including `metadata.expected_behavior`, `metadata.claim_statement`, "
    "`metadata.hypothesis_ids`, `metadata.theorem_parameter_symbols`, and "
    "`metadata.conclusion_clause_ids`."
)


def verification_contract_policy_text() -> str:
    """Return the shared verification contract policy text."""

    return VERIFICATION_CONTRACT_POLICY_TEXT


def verification_server_description() -> str:
    """Return the public verification server description."""

    return f"{VERIFICATION_SERVER_DESCRIPTION_INTRO} {VERIFICATION_CONTRACT_POLICY_TEXT}"
