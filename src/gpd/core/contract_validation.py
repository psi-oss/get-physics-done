"""Validation helpers for contract-backed workflow gates."""

from __future__ import annotations

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
