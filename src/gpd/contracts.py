"""GPD contracts -- shared data types for conventions, planning, and verification."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError

__all__ = [
    "ConventionLock",
    "VerificationEvidence",
    "ContractEvidenceStatus",
    "ContractEvidenceEntry",
    "ContractResultEntry",
    "ContractReferenceActionStatus",
    "ContractReferenceUsage",
    "ContractForbiddenProxyStatus",
    "ContractForbiddenProxyResult",
    "ContractResults",
    "SuggestedContractCheck",
    "ComparisonVerdict",
    "ContractScope",
    "ContractContextIntake",
    "ContractApproachPolicy",
    "ContractObservable",
    "ContractClaim",
    "ContractDeliverable",
    "ContractAcceptanceTest",
    "ContractReference",
    "ContractForbiddenProxy",
    "ContractLink",
    "ContractUncertaintyMarkers",
    "ResearchContract",
    "contract_from_data",
]


def _normalize_optional_str(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_required_str(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped
    return value


def _normalize_string_list(value: object) -> object:
    if not isinstance(value, list):
        return value
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            normalized.append(item)
            continue
        stripped = item.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        normalized.append(stripped)
    return normalized


def _normalize_mapping_field(value: object) -> object:
    if value is None or value == []:
        return {}
    return value


class ConventionLock(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    metric_signature: str | None = None
    fourier_convention: str | None = None
    natural_units: str | None = None
    gauge_choice: str | None = None
    regularization_scheme: str | None = None
    renormalization_scheme: str | None = None
    coordinate_system: str | None = None
    spin_basis: str | None = None
    state_normalization: str | None = None
    coupling_convention: str | None = None
    index_positioning: str | None = None
    time_ordering: str | None = None
    commutation_convention: str | None = None
    levi_civita_sign: str | None = None
    generator_normalization: str | None = None
    covariant_derivative_sign: str | None = None
    gamma_matrix_convention: str | None = None
    creation_annihilation_order: str | None = None
    custom_conventions: dict[str, str] = Field(default_factory=dict)


class VerificationEvidence(BaseModel):
    """Structured provenance for a verification event attached to a result."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    verified_at: str | None = None
    verifier: str | None = None
    method: str = "manual"
    confidence: Literal["high", "medium", "low", "unreliable"] = "medium"
    evidence_path: str | None = None
    trace_id: str | None = None
    commit_sha: str | None = None
    notes: str | None = None
    claim_id: str | None = None
    deliverable_id: str | None = None
    acceptance_test_id: str | None = None
    reference_id: str | None = None

    @field_validator("claim_id", "deliverable_id", "acceptance_test_id", "reference_id", mode="before")
    @classmethod
    def _normalize_optional_contract_id(cls, value: object) -> object:
        return _normalize_optional_str(value)


ContractEvidenceStatus = Literal["passed", "partial", "failed", "blocked", "not_attempted"]


class ContractEvidenceEntry(BaseModel):
    """Structured evidence item tied back to contract IDs."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    summary: str | None = None
    evidence: list[VerificationEvidence] = Field(default_factory=list)
    notes: str | None = None


class ContractResultEntry(ContractEvidenceEntry):
    """Execution or verification outcome for a contract subject."""

    status: ContractEvidenceStatus = "not_attempted"
    linked_ids: list[str] = Field(default_factory=list)
    path: str | None = None

    @field_validator("linked_ids", mode="before")
    @classmethod
    def _normalize_linked_ids(cls, value: object) -> object:
        return _normalize_string_list(value)


ContractReferenceActionStatus = Literal["completed", "missing", "not_applicable"]


class ContractReferenceUsage(BaseModel):
    """Status for required actions on a contract reference anchor."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: ContractReferenceActionStatus = "missing"
    completed_actions: list[str] = Field(default_factory=list)
    missing_actions: list[str] = Field(default_factory=list)
    summary: str | None = None
    evidence: list[VerificationEvidence] = Field(default_factory=list)


ContractForbiddenProxyStatus = Literal["rejected", "violated", "unresolved", "not_applicable"]


class ContractForbiddenProxyResult(BaseModel):
    """Status for a forbidden-proxy guardrail."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: ContractForbiddenProxyStatus = "unresolved"
    notes: str | None = None
    evidence: list[VerificationEvidence] = Field(default_factory=list)


class ContractResults(BaseModel):
    """Execution-facing outcome ledger keyed to canonical contract IDs."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    claims: dict[str, ContractResultEntry] = Field(default_factory=dict)
    deliverables: dict[str, ContractResultEntry] = Field(default_factory=dict)
    acceptance_tests: dict[str, ContractResultEntry] = Field(default_factory=dict)
    references: dict[str, ContractReferenceUsage] = Field(default_factory=dict)
    forbidden_proxies: dict[str, ContractForbiddenProxyResult] = Field(default_factory=dict)
    uncertainty_markers: ContractUncertaintyMarkers = Field(default_factory=lambda: ContractUncertaintyMarkers())

    @field_validator(
        "claims",
        "deliverables",
        "acceptance_tests",
        "references",
        "forbidden_proxies",
        mode="before",
    )
    @classmethod
    def _normalize_mapping_sections(cls, value: object) -> object:
        return _normalize_mapping_field(value)


class SuggestedContractCheck(BaseModel):
    """Structured gap to add when the contract is missing decisive verification."""

    model_config = ConfigDict(validate_assignment=True, extra="allow")

    check: str
    reason: str
    suggested_subject_kind: Literal["claim", "deliverable", "acceptance_test", "reference"] | None = None
    suggested_subject_id: str | None = None
    evidence_path: str | None = None

    @field_validator("check", "reason", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("suggested_subject_kind", mode="before")
    @classmethod
    def _normalize_optional_kind(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @field_validator("suggested_subject_id", "evidence_path", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_str(value)


class ComparisonVerdict(BaseModel):
    """Machine-readable verdict for an internal or external comparison."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    subject_id: str
    subject_kind: Literal["claim", "deliverable", "acceptance_test", "reference", "artifact", "other"] = "other"
    subject_role: Literal["decisive", "supporting", "supplemental", "other"] = "other"
    reference_id: str | None = None
    comparison_kind: Literal["benchmark", "prior_work", "experiment", "cross_method", "baseline", "other"] = "other"
    metric: str | None = None
    threshold: str | None = None
    verdict: Literal["pass", "tension", "fail", "inconclusive"] = "inconclusive"
    recommended_action: str | None = None
    notes: str | None = None

    @field_validator("subject_id", mode="before")
    @classmethod
    def _normalize_subject_id(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("reference_id", "metric", "threshold", "recommended_action", "notes", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_str(value)


class ContractScope(BaseModel):
    """High-level problem boundary for a project or phase."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    question: str
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

    @field_validator("question", mode="before")
    @classmethod
    def _normalize_question(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("in_scope", "out_of_scope", "unresolved_questions", mode="before")
    @classmethod
    def _normalize_scope_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractContextIntake(BaseModel):
    """Inputs the user says must stay visible during execution."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    must_read_refs: list[str] = Field(default_factory=list)
    must_include_prior_outputs: list[str] = Field(default_factory=list)
    user_asserted_anchors: list[str] = Field(default_factory=list)
    known_good_baselines: list[str] = Field(default_factory=list)
    context_gaps: list[str] = Field(default_factory=list)
    crucial_inputs: list[str] = Field(default_factory=list)

    @field_validator(
        "must_read_refs",
        "must_include_prior_outputs",
        "user_asserted_anchors",
        "known_good_baselines",
        "context_gaps",
        "crucial_inputs",
        mode="before",
    )
    @classmethod
    def _normalize_intake_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractApproachPolicy(BaseModel):
    """Representation, estimator, and rethink guardrails that must survive downstream."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    formulations: list[str] = Field(default_factory=list)
    allowed_estimator_families: list[str] = Field(default_factory=list)
    forbidden_estimator_families: list[str] = Field(default_factory=list)
    allowed_fit_families: list[str] = Field(default_factory=list)
    forbidden_fit_families: list[str] = Field(default_factory=list)
    stop_and_rethink_conditions: list[str] = Field(default_factory=list)

    @field_validator(
        "formulations",
        "allowed_estimator_families",
        "forbidden_estimator_families",
        "allowed_fit_families",
        "forbidden_fit_families",
        "stop_and_rethink_conditions",
        mode="before",
    )
    @classmethod
    def _normalize_policy_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractObservable(BaseModel):
    """A target quantity or behavior the work needs to establish."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    name: str
    kind: Literal["scalar", "curve", "map", "classification", "proof_obligation", "other"] = "other"
    definition: str
    regime: str | None = None
    units: str | None = None

    @field_validator("id", "name", "definition", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("regime", "units", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_str(value)


class ContractClaim(BaseModel):
    """A statement the phase must establish."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    statement: str
    observables: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_tests: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @field_validator("id", "statement", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("observables", "deliverables", "acceptance_tests", "references", mode="before")
    @classmethod
    def _normalize_id_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractDeliverable(BaseModel):
    """An artifact the phase must produce."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    kind: Literal["figure", "table", "dataset", "data", "derivation", "code", "note", "report", "other"] = "other"
    path: str | None = None
    description: str
    must_contain: list[str] = Field(default_factory=list)

    @field_validator("id", "description", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("path", mode="before")
    @classmethod
    def _normalize_optional_path(cls, value: object) -> object:
        return _normalize_optional_str(value)

    @field_validator("must_contain", mode="before")
    @classmethod
    def _normalize_must_contain(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractAcceptanceTest(BaseModel):
    """A concrete check proving whether a claim or deliverable succeeded."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    subject: str
    kind: Literal[
        "existence",
        "schema",
        "benchmark",
        "consistency",
        "cross_method",
        "limiting_case",
        "symmetry",
        "dimensional_analysis",
        "convergence",
        "oracle",
        "proxy",
        "reproducibility",
        "human_review",
        "other",
    ] = "other"
    procedure: str
    pass_condition: str
    evidence_required: list[str] = Field(default_factory=list)
    automation: Literal["automated", "hybrid", "human"] = "hybrid"

    @field_validator("id", "subject", "procedure", "pass_condition", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("evidence_required", mode="before")
    @classmethod
    def _normalize_evidence_required(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractReference(BaseModel):
    """A literature, dataset, or artifact anchor the workflow must respect."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    kind: Literal["paper", "dataset", "prior_artifact", "spec", "user_anchor", "other"] = "other"
    locator: str
    aliases: list[str] = Field(default_factory=list)
    role: Literal["definition", "benchmark", "method", "must_consider", "background", "other"] = "other"
    why_it_matters: str
    applies_to: list[str] = Field(default_factory=list)
    carry_forward_to: list[str] = Field(default_factory=list)
    must_surface: bool = False
    required_actions: list[Literal["read", "use", "compare", "cite", "avoid"]] = Field(default_factory=list)

    @field_validator("id", "locator", "why_it_matters", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("aliases", "applies_to", "carry_forward_to", mode="before")
    @classmethod
    def _normalize_reference_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractForbiddenProxy(BaseModel):
    """A proxy or shortcut that should not be accepted as success."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    subject: str
    proxy: str
    reason: str

    @field_validator("id", "subject", "proxy", "reason", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)


class ContractLink(BaseModel):
    """A machine-readable dependency from one contract node to another."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    source: str
    target: str
    relation: Literal["supports", "computes", "visualizes", "benchmarks", "depends_on", "evaluated_by", "other"] = "other"
    verified_by: list[str] = Field(default_factory=list)

    @field_validator("id", "source", "target", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_str(value)

    @field_validator("verified_by", mode="before")
    @classmethod
    def _normalize_verified_by(cls, value: object) -> object:
        return _normalize_string_list(value)


class ContractUncertaintyMarkers(BaseModel):
    """Structured skepticism markers carried alongside the contract."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    weakest_anchors: list[str] = Field(default_factory=list)
    unvalidated_assumptions: list[str] = Field(default_factory=list)
    competing_explanations: list[str] = Field(default_factory=list)
    disconfirming_observations: list[str] = Field(default_factory=list)

    @field_validator(
        "weakest_anchors",
        "unvalidated_assumptions",
        "competing_explanations",
        "disconfirming_observations",
        mode="before",
    )
    @classmethod
    def _normalize_uncertainty_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class ResearchContract(BaseModel):
    """Canonical contract shared across planning, execution, and verification."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    schema_version: Literal[1] = 1
    scope: ContractScope
    context_intake: ContractContextIntake = Field(default_factory=ContractContextIntake)
    approach_policy: ContractApproachPolicy = Field(default_factory=ContractApproachPolicy)
    observables: list[ContractObservable] = Field(default_factory=list)
    claims: list[ContractClaim] = Field(default_factory=list)
    deliverables: list[ContractDeliverable] = Field(default_factory=list)
    acceptance_tests: list[ContractAcceptanceTest] = Field(default_factory=list)
    references: list[ContractReference] = Field(default_factory=list)
    forbidden_proxies: list[ContractForbiddenProxy] = Field(default_factory=list)
    links: list[ContractLink] = Field(default_factory=list)
    uncertainty_markers: ContractUncertaintyMarkers = Field(default_factory=ContractUncertaintyMarkers)


def contract_from_data(data: object) -> ResearchContract | None:
    """Return a validated :class:`ResearchContract` when *data* is a mapping.

    Malformed mappings degrade to ``None`` so callers can treat this helper as a
    safe probe instead of an exception boundary.
    """

    if not isinstance(data, dict):
        return None
    try:
        return ResearchContract.model_validate(data)
    except PydanticValidationError:
        return None
