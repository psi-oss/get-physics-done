"""Shared verification contract visibility and strictness text."""

from __future__ import annotations

VERIFICATION_SERVER_DESCRIPTION_INTRO = (
    "GPD physics verification checks. Tools for running contract-aware checks, "
    "dimensional analysis, domain and bundle-specific checklists, limiting case checks, "
    "symmetry verification, and coverage gap analysis."
)
VERIFICATION_CONTRACT_SURFACE_SUMMARY_TEXT = (
    "Contract-aware requests follow the `contract` schema. "
    "Always run `suggest_contract_checks(...)` to gather the per-check request metadata before "
    "calling `run_contract_check(...)`, and never invent grounding or proof artifacts."
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
VERIFICATION_REQUEST_CONSTRAINT_FIELD_NAMES = (
    "required_request_fields",
    "schema_required_request_fields",
    "schema_required_request_anyof_fields",
    "optional_request_fields",
    "supported_binding_fields",
    "request_template",
)
VERIFICATION_REQUEST_CONSTRAINT_FIELD_TEXT = ", ".join(
    f"`{field_name}`" for field_name in VERIFICATION_REQUEST_CONSTRAINT_FIELD_NAMES
)
VERIFICATION_BINDING_FIELD_TEXT = ", ".join(f"`{field}`" for field in VERIFICATION_BINDING_FIELD_NAMES)
VERIFICATION_RUN_CONTRACT_CHECK_REQUEST_SHAPE_TEXT = (
    "`run_contract_check` takes `{request: {check_key, contract?, binding?, metadata?, observed?, "
    "artifact_content?}, project_dir?}`. Fill `request_template` values from `suggest_contract_checks`; "
    "replace every `<replace-with-...>` sentinel before execution."
)

PROJECT_CONTRACT_APPROVAL_REQUIREMENTS = (
    "`schema_version` must be integer `1`.",
    "`scope.question` is required and `scope.in_scope[]` must name a boundary or objective.",
    "Include at least one decisive `observables[]`, `claims[]`, or `deliverables[]` item.",
    "`context_intake` must contain a concrete anchor; placeholder-only text does not count.",
    "`uncertainty_markers.weakest_anchors[]` and `uncertainty_markers.disconfirming_observations[]` must be non-empty.",
    "If `references[]` is the only grounding, one reference must set `must_surface=true` with `applies_to[]`, concrete `required_actions[]`, and a usable `locator`.",
    "Approved contracts need concrete grounding from an anchor, reference, prior output, or baseline; never fabricate missing evidence.",
)

PROJECT_CONTRACT_APPROVAL_CHECKLIST_TEXT = "Approval checklist: " + " ".join(
    f"{index}) {requirement}"
    for index, requirement in enumerate(PROJECT_CONTRACT_APPROVAL_REQUIREMENTS, start=1)
)

_VERIFICATION_CONTRACT_POLICY_CLAUSES = (
    "Require `schema_version` to be the integer `1` in every payload.",
    f"Use {VERIFICATION_REQUEST_CONSTRAINT_FIELD_TEXT} plus {VERIFICATION_BINDING_FIELD_TEXT} to describe each per-check request.",
    "Proof-oriented checks need an authoritative contract payload before execution.",
    "Schemas are closed at every level; unknown keys, non-objects, blank strings, or malformed "
    "members trigger hard errors; normalization only tolerates singletons and case drift.",
    "Project-style contract payloads must make `scope.question`, non-empty `scope.in_scope`, "
    "`context_intake`, and `uncertainty_markers` model-visible before validation; downstream validators do not infer them.",
    PROJECT_CONTRACT_APPROVAL_CHECKLIST_TEXT,
    "Non-scoping, non-exploratory plans require claims, deliverables, acceptance tests, "
    "non-empty `forbidden_proxies`, and either grounded references or explicit context anchors; "
    "scoping-only contracts may omit claims only when they preserve a target, unresolved question, or grounding input.",
    "When `references[]` exists without other grounding, one anchor must set `must_surface=true`, "
    "include `applies_to[]` coverage, concrete `required_actions[]`, and workflow-only `carry_forward_to[]` scope labels.",
    "IDs must stay unique and never reuse a target ID across claims, deliverables, acceptance tests, or references when that would blur resolution.",
    "Contract context must match metadata defaults and declared metadata fields such as benchmark anchors, regimes, and families.",
    "Missing concrete grounding, evidence, prior outputs, references, baselines, or proof artifacts are blockers and must not be fabricated.",
    "Proof checks must omit or exactly match derived metadata keys `metadata.expected_behavior`, "
    "`metadata.claim_statement`, `metadata.hypothesis_ids`, `metadata.theorem_parameter_symbols`, and `metadata.conclusion_clause_ids`.",
    "Call `suggest_contract_checks(...)` before every `run_contract_check(...)`, using its metadata to populate the request template entries.",
    VERIFICATION_RUN_CONTRACT_CHECK_REQUEST_SHAPE_TEXT,
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
