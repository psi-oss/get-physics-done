"""Validation helpers for contract-backed workflow gates."""

from __future__ import annotations

import hashlib
from itertools import zip_longest
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from gpd.contracts import (
    ContractAcceptanceTest,
    ContractDeliverable,
    ResearchContract,
    _has_concrete_grounding_entries,
    _has_concrete_must_surface_reference,
    _is_concrete_reference_locator,
    _is_context_intake_locator_grounding,
    _is_project_artifact_path,
    _split_missing_must_surface_anchor_findings,
    collect_contract_integrity_errors,
    collect_proof_bearing_claim_integrity_errors,
    is_placeholder_only_guidance_text,
    parse_project_contract_data_salvage,
)
from gpd.core.kernel import _content_address
from gpd.core.project_contract_schema import (
    _collect_list_shape_drift_errors,
    _format_schema_error,
    _has_authoritative_scalar_schema_findings,
    _project_contract_schema_version_missing_error,
    is_authoritative_project_contract_schema_finding,
    is_repair_relevant_project_contract_schema_finding,
    salvage_project_contract,
    split_project_contract_schema_findings,
)
from gpd.core.utils import dedupe_preserve_order

__all__ = [
    "ProjectContractValidationResult",
    "_collect_list_shape_drift_errors",
    "_format_schema_error",
    "_has_authoritative_scalar_schema_findings",
    "claim_deliverable_alignment_summary",
    "context_guidance_fingerprint",
    "contract_fingerprint",
    "is_authoritative_project_contract_schema_finding",
    "is_repair_relevant_project_contract_schema_finding",
    "salvage_project_contract",
    "split_project_contract_schema_findings",
    "validate_project_contract",
]


class ProjectContractValidationResult(BaseModel):
    """Executable validation result for a project-scoping contract."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    question: str | None = None
    decisive_target_count: int = 0
    guidance_signal_count: int = 0
    reference_count: int = 0
    mode: Literal["draft", "approved"] = "draft"


_CLAIM_ALIGNMENT_MISSING_DELIVERABLE = "(no linked deliverable)"
_CLAIM_ALIGNMENT_MISSING_ACCEPTANCE_TEST = "(no linked acceptance test)"


def claim_deliverable_alignment_summary(
    contract: ResearchContract,
) -> list[tuple[str, str, str]]:
    """Return ``(claim.statement, deliverable.description, acceptance_test.pass_condition)`` rows, zip-longest-joined per claim with ``"(no linked …)"`` sentinels when unlinked."""

    deliverables_by_id: dict[str, ContractDeliverable] = {
        deliverable.id: deliverable for deliverable in contract.deliverables
    }
    acceptance_tests_by_id: dict[str, ContractAcceptanceTest] = {
        test.id: test for test in contract.acceptance_tests
    }

    rows: list[tuple[str, str, str]] = []
    for claim in contract.claims:
        linked_deliverables: list[str] = []
        for deliverable_id in claim.deliverables:
            deliverable = deliverables_by_id.get(deliverable_id)
            if deliverable is not None:
                linked_deliverables.append(deliverable.description)
        linked_tests: list[str] = []
        for test_id in claim.acceptance_tests:
            test = acceptance_tests_by_id.get(test_id)
            if test is not None:
                linked_tests.append(test.pass_condition)

        if not linked_deliverables and not linked_tests:
            rows.append(
                (
                    claim.statement,
                    _CLAIM_ALIGNMENT_MISSING_DELIVERABLE,
                    _CLAIM_ALIGNMENT_MISSING_ACCEPTANCE_TEST,
                )
            )
            continue

        for deliverable_description, pass_condition in zip_longest(
            linked_deliverables,
            linked_tests,
            fillvalue="",
        ):
            rows.append(
                (
                    claim.statement,
                    deliverable_description or _CLAIM_ALIGNMENT_MISSING_DELIVERABLE,
                    pass_condition or _CLAIM_ALIGNMENT_MISSING_ACCEPTANCE_TEST,
                )
            )

    return rows


def contract_fingerprint(contract: ResearchContract) -> str:
    """Return a stable ``"sha256:<hex>"`` fingerprint for ``contract`` (canonical JSON hash; mirrors :func:`gpd.core.kernel._content_address`)."""

    return _content_address(contract.model_dump(mode="json"))


def context_guidance_fingerprint(context_text: str) -> str:
    """Return a stable ``"sha256:<hex>"`` fingerprint for raw CONTEXT text."""

    encoded = context_text.encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _light_contract_consistency_errors(contract: ResearchContract) -> list[str]:
    """Return cross-link errors without forcing mature-phase completeness."""

    errors: list[str] = collect_contract_integrity_errors(contract)

    observable_ids = {observable.id for observable in contract.observables}
    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    forbidden_proxy_ids = {forbidden_proxy.id for forbidden_proxy in contract.forbidden_proxies}
    link_ids = {link.id for link in contract.links}
    known_subject_ids = claim_ids | deliverable_ids
    known_ids = known_subject_ids | acceptance_test_ids | reference_ids
    link_endpoint_ids = known_ids | observable_ids | forbidden_proxy_ids | link_ids

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
        if reference.must_surface and not reference.applies_to:
            errors.append(f"reference {reference.id} is must_surface but missing applies_to")
        for applies_to_id in reference.applies_to:
            if applies_to_id not in known_subject_ids:
                errors.append(f"reference {reference.id} applies_to unknown target {applies_to_id}")

    for forbidden_proxy in contract.forbidden_proxies:
        if forbidden_proxy.subject not in known_subject_ids:
            errors.append(f"forbidden proxy {forbidden_proxy.id} targets unknown subject {forbidden_proxy.subject}")

    for link in contract.links:
        if link.source not in link_endpoint_ids:
            errors.append(f"link {link.id} references unknown source {link.source}")
        if link.target not in link_endpoint_ids:
            errors.append(f"link {link.id} references unknown target {link.target}")
        for verification_id in link.verified_by:
            if verification_id not in acceptance_test_ids:
                errors.append(f"link {link.id} references unknown acceptance test {verification_id}")

    return errors


def _must_read_ref_counts_as_guidance(
    contract: ResearchContract,
    reference_id: str,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether one must-read reference is concrete enough to guide planning."""

    for reference in contract.references:
        if reference.id != reference_id:
            continue
        return _is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        )
    return False


def _has_approved_grounding_signal(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether approved-mode grounding is explicitly captured.

    Prior outputs count here because the new-project scoping gate allows a
    concrete carry-forward output to serve as the grounding anchor for early
    planning, even before a literature benchmark or baseline is confirmed.
    """

    return any(
        (
            _has_concrete_must_surface_reference(
                contract,
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.must_include_prior_outputs,
                field_name="must_include_prior_outputs",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.user_asserted_anchors,
                field_name="user_asserted_anchors",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.known_good_baselines,
                field_name="known_good_baselines",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
        )
    )


def _has_non_reference_grounding_signal(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether grounding is explicitly supplied outside references."""

    return any(
        (
            _has_concrete_grounding_entries(
                contract.context_intake.must_include_prior_outputs,
                field_name="must_include_prior_outputs",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.user_asserted_anchors,
                field_name="user_asserted_anchors",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.known_good_baselines,
                field_name="known_good_baselines",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
        )
    )


def _prior_output_counts_as_guidance(
    value: str,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether *value* is durable prior-output guidance."""

    return _is_project_artifact_path(value, project_root=project_root)


def _has_meaningful_guidance_text(values: list[str]) -> bool:
    """Return whether *values* contain non-placeholder textual guidance."""

    return any(not is_placeholder_only_guidance_text(value) for value in values)


def _guidance_signal_flags(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> dict[str, bool]:
    """Return per-field guidance presence using semantic, not merely non-empty, signals."""

    return {
        "must_read_refs": any(
            _must_read_ref_counts_as_guidance(contract, reference_id, project_root=project_root)
            for reference_id in contract.context_intake.must_read_refs
        ),
        "must_include_prior_outputs": any(
            _prior_output_counts_as_guidance(value, project_root=project_root)
            for value in contract.context_intake.must_include_prior_outputs
        ),
        "user_asserted_anchors": any(
            _is_context_intake_locator_grounding(
                value, project_root=project_root, require_existing_project_artifacts=True
            )
            for value in contract.context_intake.user_asserted_anchors
        ),
        "known_good_baselines": any(
            _is_context_intake_locator_grounding(
                value, project_root=project_root, require_existing_project_artifacts=True
            )
            for value in contract.context_intake.known_good_baselines
        ),
        "context_gaps": _has_meaningful_guidance_text(contract.context_intake.context_gaps),
        "crucial_inputs": _has_meaningful_guidance_text(contract.context_intake.crucial_inputs),
    }


def _context_intake_guidance_warnings(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Return targeted warnings for non-durable context-intake guidance entries."""

    warnings: list[str] = []

    for value in contract.context_intake.must_include_prior_outputs:
        if _prior_output_counts_as_guidance(value, project_root=project_root):
            continue
        if project_root is not None:
            warnings.append(
                f"context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact: {value}"
            )
            continue
        warnings.append(
            f"context_intake.must_include_prior_outputs entry is not an explicit project artifact path: {value}"
        )

    for field_name, values in (
        ("user_asserted_anchors", contract.context_intake.user_asserted_anchors),
        ("known_good_baselines", contract.context_intake.known_good_baselines),
    ):
        for value in values:
            if _is_context_intake_locator_grounding(
                value,
                project_root=project_root,
                require_existing_project_artifacts=True,
            ):
                continue
            if _is_project_artifact_path(value, project_root=None):
                if project_root is None:
                    warnings.append(
                        f"context_intake.{field_name} entry requires a resolved project_root "
                        f"to verify artifact grounding: {value}"
                    )
                else:
                    warnings.append(
                        f"context_intake.{field_name} entry does not resolve to a project-local artifact: {value}"
                    )
                continue
            warnings.append(
                f"context_intake.{field_name} entry is not concrete enough to preserve as durable guidance: {value}"
            )

    for field_name, values in (
        ("context_gaps", contract.context_intake.context_gaps),
        ("crucial_inputs", contract.context_intake.crucial_inputs),
    ):
        for value in values:
            if not is_placeholder_only_guidance_text(value):
                continue
            warnings.append(
                f"context_intake.{field_name} entry is only a placeholder and does not preserve actionable guidance: {value}"
            )

    return warnings


def _must_surface_locator_warnings(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Return targeted warnings for non-concrete must-surface reference locators."""

    warnings: list[str] = []
    for reference in contract.references:
        if not reference.must_surface:
            continue
        if _is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        ):
            continue
        warnings.append(
            f"reference {reference.id} is must_surface but locator is not concrete enough to ground validation"
        )
    return warnings


def _concrete_must_surface_targets(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> set[str]:
    """Return subject ids covered by concrete must-surface references."""

    targets: set[str] = set()
    for reference in contract.references:
        if not reference.must_surface:
            continue
        if not _is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        ):
            continue
        targets.update(reference.applies_to)
    return targets


def _split_approved_mode_must_surface_locator_findings(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Return approved-mode must-surface locator errors and warnings.

    Placeholder must-surface references stay warnings only when another
    approved grounding path already covers the same scoped obligation or a
    non-reference grounding signal makes the contract globally grounded.
    """

    errors: list[str] = []
    warnings: list[str] = []
    has_global_non_reference_grounding = _has_non_reference_grounding_signal(contract, project_root=project_root)
    concrete_targets = _concrete_must_surface_targets(contract, project_root=project_root)

    for reference in contract.references:
        if not reference.must_surface:
            continue
        if _is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        ):
            continue

        finding = f"reference {reference.id} is must_surface but locator is not concrete enough to ground validation"
        if has_global_non_reference_grounding:
            warnings.append(finding)
            continue
        if not reference.applies_to:
            errors.append(finding)
            continue
        if any(target not in concrete_targets for target in reference.applies_to):
            errors.append(finding)
            continue
        warnings.append(finding)

    return errors, warnings


def validate_project_contract(
    contract: ResearchContract | dict[str, object],
    *,
    mode: Literal["draft", "approved"] = "draft",
    project_root: Path | None = None,
) -> ProjectContractValidationResult:
    """Validate that a project-level contract is strong enough to guide planning.

    This gate is intentionally lighter than full PLAN contract validation. It
    focuses on the project-setup failure modes from FEEDBACK.md:

    - no clear question
    - no decisive target or deliverable
    - no skeptical/disconfirming path
    - user guidance not captured anywhere durable
    """

    if isinstance(contract, ResearchContract):
        contract_payload: object = contract.model_dump(mode="python", warnings=False)
    else:
        contract_payload = contract

    salvage_result = parse_project_contract_data_salvage(contract_payload)
    parsed = salvage_result.contract
    schema_warnings = dedupe_preserve_order(salvage_result.recoverable_errors)
    schema_errors = dedupe_preserve_order(salvage_result.blocking_errors)
    schema_version_error = _project_contract_schema_version_missing_error(contract_payload)
    if schema_version_error is not None:
        schema_errors = dedupe_preserve_order([schema_version_error, *schema_errors])
    if parsed is None:
        return ProjectContractValidationResult(
            valid=False,
            errors=schema_errors or ["project contract could not be normalized"],
            warnings=schema_warnings,
            mode=mode,
        )

    question = parsed.scope.question.strip()
    decisive_target_count = len(parsed.observables) + len(parsed.claims) + len(parsed.deliverables)
    guidance_signal_count = sum(_guidance_signal_flags(parsed, project_root=project_root).values())
    reference_count = len(parsed.references)

    if schema_errors:
        return ProjectContractValidationResult(
            valid=False,
            errors=schema_errors,
            warnings=schema_warnings,
            question=question or None,
            decisive_target_count=decisive_target_count,
            guidance_signal_count=guidance_signal_count,
            reference_count=reference_count,
            mode=mode,
        )

    errors: list[str] = []
    warnings: list[str] = list(schema_warnings)

    if not question:
        errors.append("scope.question is required")
    if not parsed.scope.in_scope:
        errors.append("scope.in_scope must include at least one non-empty string")
    if decisive_target_count == 0:
        errors.append("project contract must include at least one observable, claim, or deliverable")
    if not parsed.uncertainty_markers.weakest_anchors:
        errors.append("uncertainty_markers.weakest_anchors must identify what is least certain")
    if not parsed.uncertainty_markers.disconfirming_observations:
        errors.append("uncertainty_markers.disconfirming_observations must identify what would force a rethink")

    errors.extend(_light_contract_consistency_errors(parsed))
    errors.extend(collect_proof_bearing_claim_integrity_errors(parsed))

    warnings.extend(_context_intake_guidance_warnings(parsed, project_root=project_root))
    if mode == "approved":
        must_surface_locator_errors, must_surface_locator_warnings = _split_approved_mode_must_surface_locator_findings(
            parsed,
            project_root=project_root,
        )
        errors.extend(must_surface_locator_errors)
        warnings.extend(must_surface_locator_warnings)
    else:
        warnings.extend(_must_surface_locator_warnings(parsed, project_root=project_root))

    reference_anchor_errors, reference_anchor_warnings = _split_missing_must_surface_anchor_findings(
        parsed,
        project_root=project_root,
        mode=mode,
    )
    errors.extend(reference_anchor_errors)
    warnings.extend(reference_anchor_warnings)

    if (
        mode == "approved"
        and decisive_target_count > 0
        and not _has_approved_grounding_signal(
            parsed,
            project_root=project_root,
        )
    ):
        errors.append(
            "approved project contract requires at least one concrete anchor/reference/prior-output/baseline; explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own"
        )

    if not parsed.acceptance_tests:
        warnings.append("no acceptance_tests recorded yet")
    if not parsed.references:
        warnings.append("no references recorded yet")
    if not parsed.forbidden_proxies:
        warnings.append("no forbidden_proxies recorded yet")
    if guidance_signal_count == 0:
        errors.append("context_intake must not be empty")

    return ProjectContractValidationResult(
        valid=not errors,
        errors=dedupe_preserve_order(errors),
        warnings=dedupe_preserve_order(warnings),
        question=question or None,
        decisive_target_count=decisive_target_count,
        guidance_signal_count=guidance_signal_count,
        reference_count=reference_count,
        mode=mode,
    )
