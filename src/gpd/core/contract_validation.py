"""Validation helpers for contract-backed workflow gates."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from gpd.contracts import ResearchContract

__all__ = ["ProjectContractValidationResult", "validate_project_contract"]


class ProjectContractValidationResult(BaseModel):
    """Executable validation result for a project-scoping contract."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    question: str | None = None
    decisive_target_count: int = 0
    guidance_signal_count: int = 0
    reference_count: int = 0


def _append_duplicates(errors: list[str], kind: str, ids: list[str]) -> None:
    for item_id, count in Counter(ids).items():
        if count > 1:
            errors.append(f"duplicate {kind} id {item_id}")


def _light_contract_consistency_errors(contract: ResearchContract) -> list[str]:
    """Return cross-link errors without forcing mature-phase completeness."""

    errors: list[str] = []
    _append_duplicates(errors, "claim", [claim.id for claim in contract.claims])
    _append_duplicates(errors, "deliverable", [deliverable.id for deliverable in contract.deliverables])
    _append_duplicates(errors, "acceptance_test", [test.id for test in contract.acceptance_tests])
    _append_duplicates(errors, "reference", [reference.id for reference in contract.references])
    _append_duplicates(errors, "forbidden_proxy", [proxy.id for proxy in contract.forbidden_proxies])
    _append_duplicates(errors, "link", [link.id for link in contract.links])

    observable_ids = {observable.id for observable in contract.observables}
    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    known_subject_ids = claim_ids | deliverable_ids
    known_ids = known_subject_ids | acceptance_test_ids | reference_ids

    for must_read_ref in contract.context_intake.must_read_refs:
        if must_read_ref not in reference_ids:
            errors.append(f"context_intake.must_read_refs references unknown reference {must_read_ref}")

    for claim in contract.claims:
        for observable_id in claim.observables:
            if observable_id not in observable_ids:
                errors.append(f"claim {claim.id} references unknown observable {observable_id}")
        for deliverable_id in claim.deliverables:
            if deliverable_id not in deliverable_ids:
                errors.append(f"claim {claim.id} references unknown deliverable {deliverable_id}")
        for test_id in claim.acceptance_tests:
            if test_id not in acceptance_test_ids:
                errors.append(f"claim {claim.id} references unknown acceptance test {test_id}")
        for reference_id in claim.references:
            if reference_id not in reference_ids:
                errors.append(f"claim {claim.id} references unknown reference {reference_id}")

    for test in contract.acceptance_tests:
        if test.subject not in known_subject_ids:
            errors.append(f"acceptance test {test.id} targets unknown subject {test.subject}")
        for evidence_id in test.evidence_required:
            if evidence_id not in known_ids:
                errors.append(f"acceptance test {test.id} references unknown evidence {evidence_id}")

    for reference in contract.references:
        if reference.must_surface and not reference.required_actions:
            errors.append(f"reference {reference.id} is must_surface but missing required_actions")
        for applies_to_id in reference.applies_to:
            if applies_to_id not in known_subject_ids:
                errors.append(f"reference {reference.id} applies_to unknown target {applies_to_id}")

    for forbidden_proxy in contract.forbidden_proxies:
        if forbidden_proxy.subject not in known_subject_ids:
            errors.append(f"forbidden proxy {forbidden_proxy.id} targets unknown subject {forbidden_proxy.subject}")

    for link in contract.links:
        if link.source not in known_ids:
            errors.append(f"link {link.id} references unknown source {link.source}")
        if link.target not in known_ids:
            errors.append(f"link {link.id} references unknown target {link.target}")
        for verification_id in link.verified_by:
            if verification_id not in acceptance_test_ids:
                errors.append(f"link {link.id} references unknown acceptance test {verification_id}")

    return errors


def validate_project_contract(contract: ResearchContract | dict[str, object]) -> ProjectContractValidationResult:
    """Validate that a project-level contract is strong enough to guide planning.

    This gate is intentionally lighter than full PLAN contract validation. It
    focuses on the project-setup failure modes from FEEDBACK.md:

    - no clear question
    - no decisive target or deliverable
    - no skeptical/disconfirming path
    - user guidance not captured anywhere durable
    """

    parsed = contract if isinstance(contract, ResearchContract) else ResearchContract.model_validate(contract)
    errors: list[str] = []
    warnings: list[str] = []

    question = parsed.scope.question.strip()
    decisive_target_count = len(parsed.observables) + len(parsed.claims) + len(parsed.deliverables)
    guidance_signal_count = sum(
        bool(items)
        for items in (
            parsed.context_intake.must_read_refs,
            parsed.context_intake.must_include_prior_outputs,
            parsed.context_intake.user_asserted_anchors,
            parsed.context_intake.known_good_baselines,
            parsed.context_intake.context_gaps,
            parsed.context_intake.crucial_inputs,
        )
    )

    if not question:
        errors.append("scope.question is required")
    if not parsed.scope.in_scope:
        errors.append("scope.in_scope must name at least one project boundary or objective")
    if decisive_target_count == 0:
        errors.append("project contract must include at least one observable, claim, or deliverable")
    if not parsed.uncertainty_markers.weakest_anchors:
        errors.append("uncertainty_markers.weakest_anchors must identify what is least certain")
    if not parsed.uncertainty_markers.disconfirming_observations:
        errors.append("uncertainty_markers.disconfirming_observations must identify what would force a rethink")

    errors.extend(_light_contract_consistency_errors(parsed))

    if not parsed.acceptance_tests:
        warnings.append("no acceptance_tests recorded yet")
    if not parsed.references:
        warnings.append("no references recorded yet")
    if not parsed.forbidden_proxies:
        warnings.append("no forbidden_proxies recorded yet")
    if guidance_signal_count == 0:
        warnings.append(
            "no user guidance signals recorded yet (must_read_refs, prior outputs, anchors, baselines, gaps, or crucial inputs)"
        )

    return ProjectContractValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        question=question or None,
        decisive_target_count=decisive_target_count,
        guidance_signal_count=guidance_signal_count,
        reference_count=len(parsed.references),
    )
