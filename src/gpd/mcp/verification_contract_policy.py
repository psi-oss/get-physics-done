"""Shared verification contract visibility and strictness text."""

from __future__ import annotations

VERIFICATION_CONTRACT_POLICY_TEXT = (
    "contract payloads whose `schema_version` is required and must equal `1`. "
    "The contract payload `schema_version` is required and must equal `1`; contract payload ``schema_version`` "
    "is required and must equal ``1``. "
    "``request.check_key`` is required, must be non-empty, and `run_contract_check` uses "
    "`request.check_key` as its sole top-level identifier and rejects `check_id` there. "
    "Contract-aware tools expose the exact request shape through `required_request_fields`, "
    "`schema_required_request_fields`, `schema_required_request_anyof_fields`, "
    "`optional_request_fields`, `supported_binding_fields`, and `request_template`, and surface the supported "
    "binding fields `binding.observable_ids`, `binding.claim_ids`, `binding.deliverable_ids`, "
    "`binding.acceptance_test_ids`, `binding.reference_ids`, and `binding.forbidden_proxy_ids`. "
    "Proof-oriented checks require an authoritative contract payload. "
    "The payload is a hard schema boundary: unknown top-level keys, non-object sections, blank strings, and "
    "malformed members are hard errors, while the shared parser still normalizes recoverable singleton-string/list "
    "drift and closed-enum case drift. "
    "Plan-style contract payloads require non-empty `context_intake` and explicit `uncertainty_markers.weakest_anchors` "
    "plus `uncertainty_markers.disconfirming_observations`; non-scoping non-exploratory plans also require claims, "
    "deliverables, `acceptance_tests`, non-empty `forbidden_proxies`, and either `references` or explicit grounding "
    "context, while scoping-only contracts may omit claims only when they still preserve at least one target, "
    "unresolved question, or grounding input. When `references` are present, at least one "
    "`references[].must_surface=true` anchor is required, ``references[].must_surface`` requires non-empty "
    "``applies_to`` and ``required_actions`` lists, and ``references[].must_surface`` anchors to carry non-empty "
    "``applies_to`` and ``required_actions`` lists. ``references[].carry_forward_to`` uses workflow scope labels "
    "only, never contract IDs, and ``references[].carry_forward_to`` entries are workflow scope labels only. These "
    "live semantic integrity rules reject target IDs reused across contract kinds when that "
    "would make resolution ambiguous or target resolution ambiguous; same-kind IDs must be unique. contract context "
    "consistent with metadata defaults and "
    "explicit metadata fields; contract context must stay consistent with metadata defaults and explicit metadata "
    "fields, so benchmark anchors, regime labels, and family selections cannot contradict the resolved binding. For "
    "proof-oriented checks, contract-derived metadata fields must be omitted or "
    "match the resolved defaults exactly, including `metadata.expected_behavior`, `metadata.claim_statement`, "
    "`metadata.hypothesis_ids`, `metadata.theorem_parameter_symbols`, and `metadata.conclusion_clause_ids`."
)


def verification_contract_policy_text() -> str:
    """Return the shared verification contract policy text."""

    return VERIFICATION_CONTRACT_POLICY_TEXT
