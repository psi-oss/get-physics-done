"""GPD contracts -- shared data types for conventions, planning, and verification."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ConventionLock",
    "VerificationEvidence",
    "ContractScope",
    "ContractContextIntake",
    "ContractObservable",
    "ContractClaim",
    "ContractDeliverable",
    "ContractAcceptanceTest",
    "ContractReference",
    "ContractForbiddenProxy",
    "ContractLink",
    "ContractUncertaintyMarkers",
    "ResearchContract",
    "LegacyMustHaveArtifact",
    "LegacyMustHaveLink",
    "LegacyMustHaves",
    "contract_from_data",
    "contract_to_legacy_must_haves",
]


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

    model_config = ConfigDict(validate_assignment=True)

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


class ContractScope(BaseModel):
    """High-level problem boundary for a project or phase."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    question: str
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class ContractContextIntake(BaseModel):
    """Inputs the user says must stay visible during execution."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    must_read_refs: list[str] = Field(default_factory=list)
    must_include_prior_outputs: list[str] = Field(default_factory=list)
    user_asserted_anchors: list[str] = Field(default_factory=list)
    known_good_baselines: list[str] = Field(default_factory=list)
    context_gaps: list[str] = Field(default_factory=list)
    crucial_inputs: list[str] = Field(default_factory=list)


class ContractObservable(BaseModel):
    """A target quantity or behavior the work needs to establish."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    name: str
    kind: Literal["scalar", "curve", "map", "classification", "proof_obligation", "other"] = "other"
    definition: str
    regime: str | None = None
    units: str | None = None


class ContractClaim(BaseModel):
    """A statement the phase must establish."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    statement: str
    observables: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_tests: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class ContractDeliverable(BaseModel):
    """An artifact the phase must produce."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    kind: Literal["figure", "table", "dataset", "derivation", "code", "note", "report", "other"] = "other"
    path: str | None = None
    description: str
    must_contain: list[str] = Field(default_factory=list)


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
        "reproducibility",
        "human_review",
        "other",
    ] = "other"
    procedure: str
    pass_condition: str
    evidence_required: list[str] = Field(default_factory=list)
    automation: Literal["automated", "hybrid", "human"] = "hybrid"


class ContractReference(BaseModel):
    """A literature, dataset, or artifact anchor the workflow must respect."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    kind: Literal["paper", "dataset", "prior_artifact", "spec", "user_anchor", "other"] = "other"
    locator: str
    role: Literal["definition", "benchmark", "method", "must_consider", "background", "other"] = "other"
    why_it_matters: str
    applies_to: list[str] = Field(default_factory=list)
    must_surface: bool = False
    required_actions: list[Literal["read", "use", "compare", "cite", "avoid"]] = Field(default_factory=list)


class ContractForbiddenProxy(BaseModel):
    """A proxy or shortcut that should not be accepted as success."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    subject: str
    proxy: str
    reason: str


class ContractLink(BaseModel):
    """A machine-readable dependency from one contract node to another."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    id: str
    source: str
    target: str
    relation: Literal["supports", "computes", "visualizes", "benchmarks", "depends_on", "other"] = "other"
    verified_by: list[str] = Field(default_factory=list)


class ContractUncertaintyMarkers(BaseModel):
    """Structured skepticism markers carried alongside the contract."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    weakest_anchors: list[str] = Field(default_factory=list)
    unvalidated_assumptions: list[str] = Field(default_factory=list)
    competing_explanations: list[str] = Field(default_factory=list)
    disconfirming_observations: list[str] = Field(default_factory=list)


class ResearchContract(BaseModel):
    """Canonical contract shared across planning, execution, and verification."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    schema_version: int = 1
    scope: ContractScope
    context_intake: ContractContextIntake = Field(default_factory=ContractContextIntake)
    observables: list[ContractObservable] = Field(default_factory=list)
    claims: list[ContractClaim] = Field(default_factory=list)
    deliverables: list[ContractDeliverable] = Field(default_factory=list)
    acceptance_tests: list[ContractAcceptanceTest] = Field(default_factory=list)
    references: list[ContractReference] = Field(default_factory=list)
    forbidden_proxies: list[ContractForbiddenProxy] = Field(default_factory=list)
    links: list[ContractLink] = Field(default_factory=list)
    uncertainty_markers: ContractUncertaintyMarkers = Field(default_factory=ContractUncertaintyMarkers)


class LegacyMustHaveArtifact(BaseModel):
    """Compatibility view for old PLAN.md frontmatter consumers."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    path: str
    provides: str
    physics_check: str | None = None


class LegacyMustHaveLink(BaseModel):
    """Compatibility view for old PLAN.md frontmatter consumers."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid", populate_by_name=True)

    source: str = Field(alias="from")
    to: str
    via: str
    check: str | None = None


class LegacyMustHaves(BaseModel):
    """Compatibility surface derived from the canonical contract."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    truths: list[str] = Field(default_factory=list)
    artifacts: list[LegacyMustHaveArtifact] = Field(default_factory=list)
    key_links: list[LegacyMustHaveLink] = Field(default_factory=list)


def contract_from_data(data: object) -> ResearchContract | None:
    """Return a validated :class:`ResearchContract` when *data* is a mapping."""

    if not isinstance(data, dict):
        return None
    return ResearchContract.model_validate(data)


def contract_to_legacy_must_haves(contract: ResearchContract | dict[str, object]) -> LegacyMustHaves:
    """Derive the legacy ``must_haves`` structure from the canonical contract."""

    parsed = contract if isinstance(contract, ResearchContract) else ResearchContract.model_validate(contract)

    claims_by_deliverable: dict[str, list[ContractClaim]] = {}
    for claim in parsed.claims:
        for deliverable_id in claim.deliverables:
            claims_by_deliverable.setdefault(deliverable_id, []).append(claim)

    artifacts: list[LegacyMustHaveArtifact] = []
    for deliverable in parsed.deliverables:
        if not deliverable.path:
            continue

        relevant_tests: list[str] = []
        related_claim_ids = {claim.id for claim in claims_by_deliverable.get(deliverable.id, [])}
        for test in parsed.acceptance_tests:
            if (
                test.subject == deliverable.id
                or test.subject in related_claim_ids
                or deliverable.id in test.evidence_required
            ):
                relevant_tests.append(test.pass_condition or test.procedure or test.id)

        artifacts.append(
            LegacyMustHaveArtifact(
                path=deliverable.path,
                provides=deliverable.description,
                physics_check="; ".join(dict.fromkeys(relevant_tests)) or None,
            )
        )

    key_links = [
        LegacyMustHaveLink(
            **{
                "from": link.source,
                "to": link.target,
                "via": link.relation.replace("_", " "),
                "check": ", ".join(link.verified_by) or None,
            }
        )
        for link in parsed.links
    ]

    return LegacyMustHaves(
        truths=[claim.statement for claim in parsed.claims],
        artifacts=artifacts,
        key_links=key_links,
    )
