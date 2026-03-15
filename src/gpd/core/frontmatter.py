"""Frontmatter parsing, schema validation, and verification helpers.

Core operations:
  extract_frontmatter / reconstruct_frontmatter / splice_frontmatter — YAML CRUD
  validate_frontmatter — schema enforcement for plan/summary/verification files
  verify_* — verification suite (summary, plan structure, phase, references, commits, artifacts)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import ComparisonVerdict, ContractResults, ResearchContract, SuggestedContractCheck
from gpd.core.constants import (
    PLAN_SUFFIX,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    SUMMARY_SUFFIX,
)
from gpd.core.errors import GPDError
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import safe_read_file

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Exceptions
    "FrontmatterParseError",
    "FrontmatterValidationError",
    # Core parsing
    "extract_frontmatter",
    "reconstruct_frontmatter",
    "splice_frontmatter",
    "deep_merge_frontmatter",
    "parse_contract_block",
    # Schema validation
    "FRONTMATTER_SCHEMAS",
    "FrontmatterValidation",
    "validate_frontmatter",
    # Verification result types
    "FileCheckResult",
    "SummaryVerification",
    "TaskInfo",
    "PlanValidation",
    "PhaseCompleteness",
    "ReferenceVerification",
    "CommitVerification",
    "ArtifactCheck",
    "ArtifactVerification",
    # Verification implementations
    "verify_summary",
    "verify_plan_structure",
    "verify_phase_completeness",
    "verify_references",
    "verify_commits",
    "verify_artifacts",
]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FrontmatterParseError(GPDError, ValueError):
    """YAML frontmatter block is syntactically invalid."""


class FrontmatterValidationError(GPDError, ValueError):
    """Frontmatter fails schema validation."""


# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)")
_EMPTY_FRONTMATTER_RE = re.compile(r"^---\r?\n---(?:\r?\n|$)")

# Matches the full frontmatter block (including empty) for replacement operations.
# Uses a lookahead so the trailing newline is preserved for the caller to reattach.
_FRONTMATTER_BLOCK_RE = re.compile(r"^---\r?\n(?:[\s\S]*?\r?\n)?---(?=\r?\n|$)")


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown content.

    Returns ``(meta, body)`` where *meta* is the parsed YAML dict and *body*
    is everything after the closing ``---`` delimiter.

    If no frontmatter block is found, returns ``({}, content)``.

    Raises:
        FrontmatterParseError: If the YAML inside the ``---`` block is malformed.
    """
    clean = content.lstrip("\ufeff")  # strip BOM

    match = _FRONTMATTER_RE.match(clean)
    if match:
        yaml_str = match.group(1)
        body = clean[match.end() :]
        try:
            meta = yaml.safe_load(yaml_str)
            if meta is None:
                meta = {}
        except yaml.YAMLError as exc:
            raise FrontmatterParseError(str(exc)) from exc
        if not isinstance(meta, dict):
            raise FrontmatterParseError(f"Expected mapping, got {type(meta).__name__}")
        return meta, body

    # Empty frontmatter (---\n---)
    match = _EMPTY_FRONTMATTER_RE.match(clean)
    if match:
        return {}, clean[match.end() :]

    # No frontmatter at all
    return {}, clean


def _dump_yaml(meta: dict) -> str:
    """Dump *meta* to a YAML string (without ``---`` delimiters)."""
    return yaml.dump(
        meta,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=999999,
    ).rstrip()


def reconstruct_frontmatter(meta: dict, body: str) -> str:
    """Rebuild full markdown from *meta* dict and *body* text.

    Always uses ``\\n`` line endings regardless of input.
    """
    yaml_str = _dump_yaml(meta)
    return f"---\n{yaml_str}\n---\n\n{body}"


def splice_frontmatter(content: str, updates: dict) -> str:
    """Replace frontmatter fields in *content* with values from *updates*.

    Preserves the body and detects CRLF vs LF line endings from the original
    content.  If *content* has no frontmatter block, one is prepended.
    """
    meta, body = extract_frontmatter(content)
    meta.update(updates)

    eol = "\r\n" if "\r\n" in content else "\n"
    yaml_str = _dump_yaml(meta)

    clean = content.lstrip("\ufeff")
    fm_match = _FRONTMATTER_BLOCK_RE.match(clean)
    if fm_match:
        return f"---{eol}{yaml_str}{eol}---" + clean[fm_match.end() :]
    return f"---{eol}{yaml_str}{eol}---{eol}{eol}" + clean


def deep_merge_frontmatter(content: str, merge_data: dict) -> str:
    """Merge *merge_data* into existing frontmatter (one level deep).

    For each key in *merge_data*: if both the existing value and the new
    value are plain dicts (not lists or other types), their top-level
    entries are merged via ``dict.update`` — nested sub-dicts within those
    values are **not** merged recursively; they are replaced wholesale.
    For all other types the new value overwrites the existing one.
    """
    meta, _ = extract_frontmatter(content)
    for key, val in merge_data.items():
        existing = meta.get(key)
        if isinstance(val, dict) and isinstance(existing, dict):
            existing.update(val)
        else:
            meta[key] = val

    eol = "\r\n" if "\r\n" in content else "\n"
    yaml_str = _dump_yaml(meta)

    clean = content.lstrip("\ufeff")
    fm_match = _FRONTMATTER_BLOCK_RE.match(clean)
    if fm_match:
        return f"---{eol}{yaml_str}{eol}---" + clean[fm_match.end() :]
    return f"---{eol}{yaml_str}{eol}---{eol}{eol}" + clean


def parse_contract_block(content: str) -> ResearchContract | None:
    """Extract and validate the optional ``contract`` block from frontmatter."""

    meta, _ = extract_frontmatter(content)
    if "contract" not in meta:
        return None
    contract_data = meta.get("contract")
    if not isinstance(contract_data, dict):
        raise FrontmatterValidationError("Invalid contract frontmatter: expected an object")
    try:
        contract = ResearchContract.model_validate(contract_data)
    except PydanticValidationError as exc:
        raise FrontmatterValidationError(f"Invalid contract frontmatter: {exc}") from exc
    issues = _validate_plan_contract(contract)
    if issues:
        raise FrontmatterValidationError(
            "Invalid contract frontmatter: " + "; ".join(issues)
        )
    return contract


# ---------------------------------------------------------------------------
# Schema definitions and validation
# ---------------------------------------------------------------------------

FRONTMATTER_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "plan": {
        "required": [
            "phase",
            "plan",
            "type",
            "wave",
            "depends_on",
            "files_modified",
            "interactive",
            "contract",
        ],
    },
    "summary": {
        "required": ["phase", "plan", "depth", "provides", "completed"],
    },
    "verification": {
        "required": ["phase", "verified", "status", "score"],
    },
}

UNSUPPORTED_FRONTMATTER_FIELDS: dict[str, dict[str, str]] = {
    "plan": {
        "must_haves": "must_haves is not part of the contract-first plan schema; encode verification targets in contract claims, deliverables, links, references, and acceptance_tests",
    },
    "summary": {
        "verification_inputs": "verification_inputs is not part of the contract-first summary schema; use contract_results and comparison_verdicts instead",
        "contract_evidence": "contract_evidence is not part of the contract-first summary schema; use contract_results instead",
    },
    "verification": {
        "verification_inputs": "verification_inputs is not part of the contract-first verification schema; use contract_results and comparison_verdicts instead",
        "contract_evidence": "contract_evidence is not part of the contract-first verification schema; use contract_results instead",
    },
}


class FrontmatterValidation(BaseModel):
    """Result of frontmatter schema validation."""

    valid: bool
    missing: list[str] = Field(default_factory=list)
    present: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    schema_name: str = ""


def _resolve_field(meta: dict, name: str) -> str | None:
    """Return *name* when present in *meta*, otherwise ``None``."""
    return name if name in meta else None


def _has_contract_grounding_context(contract: ResearchContract) -> bool:
    """Return whether the contract carries explicit grounding outside references."""

    return any(
        (
            contract.context_intake.must_include_prior_outputs,
            contract.context_intake.user_asserted_anchors,
            contract.context_intake.known_good_baselines,
            contract.context_intake.context_gaps,
            contract.context_intake.crucial_inputs,
            contract.approach_policy.formulations,
            contract.approach_policy.stop_and_rethink_conditions,
        )
    )


def _is_scoping_contract(contract: ResearchContract) -> bool:
    """Return whether the contract is still framing the work rather than proving it."""

    return (
        not contract.claims
        and not contract.acceptance_tests
        and (
            bool(contract.observables)
            or bool(contract.deliverables)
            or bool(contract.scope.unresolved_questions)
            or _has_contract_grounding_context(contract)
        )
    )


def _is_exploratory_contract(contract: ResearchContract) -> bool:
    """Return whether the contract semantics describe setup/exploratory work."""

    exploratory_test_kinds = {
        "existence",
        "schema",
        "human_review",
        "consistency",
        "limiting_case",
        "symmetry",
        "dimensional_analysis",
        "convergence",
        "other",
    }
    exploratory_deliverable_kinds = {"code", "note", "report", "derivation", "figure", "table", "dataset", "data", "other"}

    return (
        not _is_scoping_contract(contract)
        and (bool(contract.acceptance_tests) or _has_contract_grounding_context(contract))
        and all(test.kind in exploratory_test_kinds for test in contract.acceptance_tests)
        and all(deliverable.kind in exploratory_deliverable_kinds for deliverable in contract.deliverables)
    )


def _validate_plan_contract(contract: ResearchContract) -> list[str]:
    """Return completeness issues for contract-backed PLAN.md frontmatter."""
    issues: list[str] = []
    scoping_contract = _is_scoping_contract(contract)
    exploratory_contract = _is_exploratory_contract(contract)

    if not contract.claims and not scoping_contract:
        issues.append("missing claims")
    if not contract.deliverables and not scoping_contract:
        issues.append("missing deliverables")
    if not contract.acceptance_tests and not scoping_contract:
        issues.append("missing acceptance_tests")
    if not contract.references and not (_has_contract_grounding_context(contract) or exploratory_contract or scoping_contract):
        issues.append("missing references or explicit grounding context")
    if not contract.forbidden_proxies and not (exploratory_contract or scoping_contract):
        issues.append("missing forbidden_proxies")
    if not contract.uncertainty_markers.weakest_anchors:
        issues.append("missing uncertainty_markers.weakest_anchors")
    if not contract.uncertainty_markers.disconfirming_observations:
        issues.append("missing uncertainty_markers.disconfirming_observations")
    if scoping_contract and not (
        contract.observables
        or contract.deliverables
        or contract.scope.unresolved_questions
        or _has_contract_grounding_context(contract)
    ):
        issues.append("scoping contracts must preserve at least one target, open question, or carry-forward input")

    def _append_duplicate_ids(kind: str, ids: list[str]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for item_id in ids:
            if item_id in seen:
                duplicates.add(item_id)
            seen.add(item_id)
        for duplicate in sorted(duplicates):
            issues.append(f"duplicate {kind} id {duplicate}")

    _append_duplicate_ids("claim", [claim.id for claim in contract.claims])
    _append_duplicate_ids("deliverable", [deliverable.id for deliverable in contract.deliverables])
    _append_duplicate_ids("acceptance_test", [test.id for test in contract.acceptance_tests])
    _append_duplicate_ids("reference", [reference.id for reference in contract.references])
    _append_duplicate_ids("forbidden_proxy", [proxy.id for proxy in contract.forbidden_proxies])
    _append_duplicate_ids("link", [link.id for link in contract.links])

    observable_ids = {observable.id for observable in contract.observables}
    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    known_ids = claim_ids | deliverable_ids | acceptance_test_ids | reference_ids

    if contract.references and not any(reference.must_surface for reference in contract.references):
        issues.append("references must include at least one must_surface=true anchor")
    for must_read_ref in contract.context_intake.must_read_refs:
        if must_read_ref not in reference_ids:
            issues.append(f"context_intake.must_read_refs references unknown reference {must_read_ref}")

    for claim in contract.claims:
        if not claim.deliverables:
            issues.append(f"claim {claim.id} missing deliverables")
        if not claim.acceptance_tests:
            issues.append(f"claim {claim.id} missing acceptance_tests")
        for observable_id in claim.observables:
            if observable_id not in observable_ids:
                issues.append(f"claim {claim.id} references unknown observable {observable_id}")
        for deliverable_id in claim.deliverables:
            if deliverable_id not in deliverable_ids:
                issues.append(f"claim {claim.id} references unknown deliverable {deliverable_id}")
        for test_id in claim.acceptance_tests:
            if test_id not in acceptance_test_ids:
                issues.append(f"claim {claim.id} references unknown acceptance test {test_id}")
        for reference_id in claim.references:
            if reference_id not in reference_ids:
                issues.append(f"claim {claim.id} references unknown reference {reference_id}")

    for test in contract.acceptance_tests:
        if test.subject not in claim_ids and test.subject not in deliverable_ids:
            issues.append(f"acceptance test {test.id} targets unknown subject {test.subject}")
        for evidence_id in test.evidence_required:
            if evidence_id not in known_ids:
                issues.append(f"acceptance test {test.id} references unknown evidence {evidence_id}")

    for reference in contract.references:
        if reference.must_surface and not reference.required_actions:
            issues.append(f"reference {reference.id} is must_surface but missing required_actions")
        if reference.must_surface and not reference.applies_to:
            issues.append(f"reference {reference.id} is must_surface but missing applies_to")
        for applies_to_id in reference.applies_to:
            if applies_to_id not in claim_ids and applies_to_id not in deliverable_ids:
                issues.append(f"reference {reference.id} applies_to unknown target {applies_to_id}")

    for forbidden_proxy in contract.forbidden_proxies:
        if forbidden_proxy.subject not in claim_ids and forbidden_proxy.subject not in deliverable_ids:
            issues.append(
                f"forbidden proxy {forbidden_proxy.id} targets unknown subject {forbidden_proxy.subject}"
            )

    for link in contract.links:
        if link.source not in known_ids:
            issues.append(f"link {link.id} references unknown source {link.source}")
        if link.target not in known_ids:
            issues.append(f"link {link.id} references unknown target {link.target}")
        for verification_id in link.verified_by:
            if verification_id not in acceptance_test_ids:
                issues.append(f"link {link.id} references unknown acceptance test {verification_id}")

    return issues


def _parse_contract_results(meta: dict) -> ContractResults | None:
    """Parse a summary contract-results block when present."""
    raw = meta.get("contract_results")
    if raw is None:
        return None
    return ContractResults.model_validate(raw)


def _parse_comparison_verdicts(meta: dict) -> list[ComparisonVerdict]:
    """Parse the optional summary comparison-verdict ledger."""
    raw = meta.get("comparison_verdicts")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("expected a list")
    return [ComparisonVerdict.model_validate(entry) for entry in raw]


def _parse_suggested_contract_checks(meta: dict) -> list[SuggestedContractCheck]:
    """Parse the optional structured verification suggestions."""
    raw = meta.get("suggested_contract_checks")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("expected a list")
    suggestions: list[SuggestedContractCheck] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("entries must be objects")
        suggestions.append(SuggestedContractCheck.model_validate(item))
    return suggestions


def _unsupported_frontmatter_errors(schema_name: str, meta: dict[str, object]) -> list[str]:
    """Return explicit errors for unsupported frontmatter fields."""
    return [
        f"{unsupported_field}: {message}"
        for unsupported_field, message in UNSUPPORTED_FRONTMATTER_FIELDS.get(schema_name, {}).items()
        if unsupported_field in meta
    ]


def _summary_contract_errors(
    contract: ResearchContract,
    contract_results: ContractResults,
    comparison_verdicts: list[ComparisonVerdict],
) -> list[str]:
    """Return summary-to-contract alignment issues for a contract-backed plan."""

    errors: list[str] = []

    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    forbidden_proxy_ids = {proxy.id for proxy in contract.forbidden_proxies}
    known_contract_ids = claim_ids | deliverable_ids | acceptance_test_ids | reference_ids | forbidden_proxy_ids
    known_subject_ids = claim_ids | deliverable_ids | acceptance_test_ids | reference_ids
    subject_kind_by_id = {
        **dict.fromkeys(claim_ids, "claim"),
        **dict.fromkeys(deliverable_ids, "deliverable"),
        **dict.fromkeys(acceptance_test_ids, "acceptance_test"),
        **dict.fromkeys(reference_ids, "reference"),
    }

    def _unknown(actual: set[str], expected: set[str], label: str) -> None:
        for item_id in sorted(actual - expected):
            errors.append(f"Unknown {label} contract_results entry: {item_id}")

    def _missing(actual: set[str], expected: set[str], label: str) -> None:
        for item_id in sorted(expected - actual):
            errors.append(f"Missing {label} contract_results entry: {item_id}")

    def _check_linked_ids(label: str, entry_id: str, linked_ids: list[str]) -> None:
        for linked_id in linked_ids:
            if linked_id not in known_contract_ids:
                errors.append(f"{label} {entry_id} linked_ids references unknown contract id {linked_id}")

    def _check_evidence_bindings(
        label: str,
        entry_id: str,
        evidence_items: list[object],
    ) -> None:
        for evidence in evidence_items:
            if evidence.claim_id is not None and evidence.claim_id not in claim_ids:
                errors.append(f"{label} {entry_id} evidence references unknown claim_id {evidence.claim_id}")
            if evidence.deliverable_id is not None and evidence.deliverable_id not in deliverable_ids:
                errors.append(
                    f"{label} {entry_id} evidence references unknown deliverable_id {evidence.deliverable_id}"
                )
            if evidence.acceptance_test_id is not None and evidence.acceptance_test_id not in acceptance_test_ids:
                errors.append(
                    f"{label} {entry_id} evidence references unknown acceptance_test_id {evidence.acceptance_test_id}"
                )
            if evidence.reference_id is not None and evidence.reference_id not in reference_ids:
                errors.append(f"{label} {entry_id} evidence references unknown reference_id {evidence.reference_id}")

    _unknown(set(contract_results.claims), claim_ids, "claim")
    _unknown(set(contract_results.deliverables), deliverable_ids, "deliverable")
    _unknown(set(contract_results.acceptance_tests), acceptance_test_ids, "acceptance_test")
    _unknown(set(contract_results.references), reference_ids, "reference")
    _unknown(set(contract_results.forbidden_proxies), forbidden_proxy_ids, "forbidden_proxy")
    _missing(set(contract_results.claims), claim_ids, "claim")
    _missing(set(contract_results.deliverables), deliverable_ids, "deliverable")
    _missing(set(contract_results.acceptance_tests), acceptance_test_ids, "acceptance_test")
    _missing(set(contract_results.references), reference_ids, "reference")
    _missing(set(contract_results.forbidden_proxies), forbidden_proxy_ids, "forbidden_proxy")

    for claim_id, entry in contract_results.claims.items():
        if claim_id not in claim_ids:
            continue
        _check_linked_ids("claim", claim_id, entry.linked_ids)
        _check_evidence_bindings("claim", claim_id, entry.evidence)
    for deliverable_id, entry in contract_results.deliverables.items():
        if deliverable_id not in deliverable_ids:
            continue
        _check_linked_ids("deliverable", deliverable_id, entry.linked_ids)
        _check_evidence_bindings("deliverable", deliverable_id, entry.evidence)
    for test_id, entry in contract_results.acceptance_tests.items():
        if test_id not in acceptance_test_ids:
            continue
        _check_linked_ids("acceptance_test", test_id, entry.linked_ids)
        _check_evidence_bindings("acceptance_test", test_id, entry.evidence)
    for reference_id, usage in contract_results.references.items():
        if reference_id not in reference_ids:
            continue
        _check_evidence_bindings("reference", reference_id, usage.evidence)
    for proxy_id, result in contract_results.forbidden_proxies.items():
        if proxy_id not in forbidden_proxy_ids:
            continue
        _check_evidence_bindings("forbidden_proxy", proxy_id, result.evidence)

    for reference in contract.references:
        usage = contract_results.references.get(reference.id)
        if reference.must_surface and usage is None:
            errors.append(f"Missing must_surface reference coverage in summary: {reference.id}")
            continue
        if usage is None:
            continue
        completed = set(usage.completed_actions)
        missing = set(reference.required_actions) - completed
        if reference.must_surface and missing:
            errors.append(
                f"Reference {reference.id} missing required_actions in summary: {', '.join(sorted(missing))}"
            )

    for verdict in comparison_verdicts:
        if verdict.subject_id not in known_subject_ids:
            errors.append(f"comparison_verdict references unknown subject_id {verdict.subject_id}")
        expected_subject_kind = subject_kind_by_id.get(verdict.subject_id)
        if expected_subject_kind is not None and verdict.subject_kind != expected_subject_kind:
            errors.append(
                "comparison_verdict for "
                f"{verdict.subject_id} has subject_kind {verdict.subject_kind} but contract id is a {expected_subject_kind}"
            )
        if verdict.reference_id is not None and verdict.reference_id not in reference_ids:
            errors.append(f"comparison_verdict references unknown reference_id {verdict.reference_id}")
        if verdict.subject_id in contract_results.claims:
            claim_status = contract_results.claims[verdict.subject_id].status
            if claim_status == "passed" and verdict.verdict in {"fail", "tension", "inconclusive"}:
                errors.append(
                    f"comparison_verdict for claim {verdict.subject_id} contradicts passed contract_results status"
                )
            if claim_status in {"failed", "blocked"} and verdict.verdict == "pass":
                errors.append(
                    f"comparison_verdict for claim {verdict.subject_id} contradicts failed contract_results status"
                )
        if verdict.subject_id in contract_results.deliverables:
            deliverable_status = contract_results.deliverables[verdict.subject_id].status
            if deliverable_status == "passed" and verdict.verdict in {"fail", "tension", "inconclusive"}:
                errors.append(
                    "comparison_verdict for deliverable "
                    f"{verdict.subject_id} contradicts passed contract_results status"
                )
            if deliverable_status in {"failed", "blocked"} and verdict.verdict == "pass":
                errors.append(
                    "comparison_verdict for deliverable "
                    f"{verdict.subject_id} contradicts failed contract_results status"
                )
        if verdict.subject_id in contract_results.acceptance_tests:
            test_status = contract_results.acceptance_tests[verdict.subject_id].status
            if test_status == "passed" and verdict.verdict in {"fail", "tension", "inconclusive"}:
                errors.append(
                    "comparison_verdict for acceptance_test "
                    f"{verdict.subject_id} contradicts passed contract_results status"
                )
            if test_status in {"failed", "blocked"} and verdict.verdict == "pass":
                errors.append(
                    "comparison_verdict for acceptance_test "
                    f"{verdict.subject_id} contradicts failed contract_results status"
                )

    decisive_comparison_groups: list[tuple[set[str], str]] = []
    for test in contract.acceptance_tests:
        if test.kind not in {"benchmark", "cross_method"}:
            continue
        result = contract_results.acceptance_tests.get(test.id)
        linked_ids = set(result.linked_ids) if result is not None else set()
        decisive_comparison_groups.append(({test.id, test.subject, *linked_ids}, f"acceptance test {test.id}"))
    for reference in contract.references:
        if reference.role != "benchmark" and "compare" not in reference.required_actions:
            continue
        decisive_comparison_groups.append(({reference.id, *reference.applies_to}, f"reference {reference.id}"))

    verdict_subject_ids = {verdict.subject_id for verdict in comparison_verdicts}
    for subject_ids, source in decisive_comparison_groups:
        if not subject_ids.intersection(verdict_subject_ids):
            errors.append(f"Missing decisive comparison_verdict for {source}")

    return errors


def _verification_contract_errors(
    contract: ResearchContract,
    contract_results: ContractResults,
    comparison_verdicts: list[ComparisonVerdict],
    suggested_contract_checks: list[SuggestedContractCheck],
) -> list[str]:
    """Return verification-specific alignment issues for contract-backed plans."""

    errors = _summary_contract_errors(contract, contract_results, comparison_verdicts)

    decisive_incomplete = False
    for test in contract.acceptance_tests:
        if test.kind not in {"benchmark", "cross_method"}:
            continue
        result = contract_results.acceptance_tests.get(test.id)
        if result is None or result.status in {"partial", "not_attempted"}:
            decisive_incomplete = True
            break
    if not decisive_incomplete:
        for reference in contract.references:
            if reference.role != "benchmark" and "compare" not in reference.required_actions:
                continue
            usage = contract_results.references.get(reference.id)
            if usage is None or usage.status != "completed" or "compare" not in usage.completed_actions:
                decisive_incomplete = True
                break

    missing_decisive_coverage = decisive_incomplete or any(
        "Missing decisive comparison_verdict" in error for error in errors
    )
    if missing_decisive_coverage and not suggested_contract_checks:
        errors.append(
            "suggested_contract_checks: required when decisive benchmark/cross-method checks remain missing, partial, or incomplete"
        )

    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    subject_kind_by_id = {
        **dict.fromkeys(claim_ids, "claim"),
        **dict.fromkeys(deliverable_ids, "deliverable"),
        **dict.fromkeys(acceptance_test_ids, "acceptance_test"),
        **dict.fromkeys(reference_ids, "reference"),
    }
    valid_ids_by_kind = {
        "claim": claim_ids,
        "deliverable": deliverable_ids,
        "acceptance_test": acceptance_test_ids,
        "reference": reference_ids,
    }

    for index, check in enumerate(suggested_contract_checks):
        has_kind = check.suggested_subject_kind is not None
        has_id = check.suggested_subject_id is not None
        if has_kind != has_id:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] must provide suggested_subject_kind and suggested_subject_id together"
            )
            continue
        if not has_kind or check.suggested_subject_kind is None or check.suggested_subject_id is None:
            continue
        expected_kind = subject_kind_by_id.get(check.suggested_subject_id)
        if expected_kind is None:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] references unknown {check.suggested_subject_kind} id {check.suggested_subject_id}"
            )
            continue
        if expected_kind != check.suggested_subject_kind:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] references {check.suggested_subject_id} as {check.suggested_subject_kind},"
                f" but the contract declares it as {expected_kind}"
            )
            continue
        if check.suggested_subject_id not in valid_ids_by_kind[check.suggested_subject_kind]:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] references unknown {check.suggested_subject_kind} id {check.suggested_subject_id}"
            )

    return errors


def _verification_status_errors(
    verification_status: object,
    contract_results: ContractResults,
    suggested_contract_checks: list[SuggestedContractCheck],
) -> list[str]:
    """Return contradictions between the declared verification status and the machine ledger."""

    if str(verification_status or "").strip() != "passed":
        return []

    errors: list[str] = []
    if suggested_contract_checks:
        errors.append("status: passed is inconsistent with non-empty suggested_contract_checks")

    non_passed_subjects = [
        f"claim {entry_id}"
        for entry_id, entry in contract_results.claims.items()
        if entry.status != "passed"
    ]
    non_passed_subjects.extend(
        f"deliverable {entry_id}"
        for entry_id, entry in contract_results.deliverables.items()
        if entry.status != "passed"
    )
    non_passed_subjects.extend(
        f"acceptance_test {entry_id}"
        for entry_id, entry in contract_results.acceptance_tests.items()
        if entry.status != "passed"
    )
    if non_passed_subjects:
        errors.append(
            "status: passed is inconsistent with non-passed contract_results targets: "
            + ", ".join(sorted(non_passed_subjects))
        )

    unresolved_proxies = [
        proxy_id
        for proxy_id, result in contract_results.forbidden_proxies.items()
        if result.status not in {"rejected", "not_applicable"}
    ]
    if unresolved_proxies:
        errors.append(
            "status: passed is inconsistent with unresolved forbidden_proxies: "
            + ", ".join(sorted(unresolved_proxies))
        )

    return errors


def _frontmatter_identity_matches(candidate_meta: dict[str, object], artifact_meta: dict[str, object]) -> bool:
    """Return whether a candidate PLAN frontmatter matches artifact phase/plan identity."""

    for key in ("phase", "plan"):
        expected = artifact_meta.get(key)
        if expected is None:
            continue
        actual = candidate_meta.get(key)
        if actual is None or str(actual).strip() != str(expected).strip():
            return False
    return True


def _find_matching_plan_contract(summary_dir: Path, summary_meta: dict) -> ResearchContract | None:
    """Return the sibling plan contract for a summary when one can be resolved."""

    plan_contract_ref = summary_meta.get("plan_contract_ref")
    if isinstance(plan_contract_ref, str):
        plan_ref_path = plan_contract_ref.split("#", 1)[0].strip()
        if plan_ref_path:
            relative_plan_path = Path(plan_ref_path[2:] if plan_ref_path.startswith("./") else plan_ref_path)
            candidates: list[Path]
            if relative_plan_path.is_absolute():
                candidates = [relative_plan_path]
            else:
                candidates = [summary_dir / relative_plan_path]
                candidates.extend(parent / relative_plan_path for parent in summary_dir.parents)

            for candidate in candidates:
                if not candidate.exists():
                    continue
                content = safe_read_file(candidate)
                if content is None:
                    continue
                try:
                    meta, _body = extract_frontmatter(content)
                except FrontmatterParseError:
                    continue
                if not _frontmatter_identity_matches(meta, summary_meta):
                    continue
                contract_data = meta.get("contract")
                if isinstance(contract_data, dict):
                    try:
                        return ResearchContract.model_validate(contract_data)
                    except PydanticValidationError:
                        return None
                return None
            return None

    summary_plan = summary_meta.get("plan")
    if summary_plan is None:
        return None

    for candidate in sorted(summary_dir.iterdir()):
        if not candidate.is_file() or not (candidate.name.endswith(PLAN_SUFFIX) or candidate.name == STANDALONE_PLAN):
            continue
        content = safe_read_file(candidate)
        if content is None:
            continue
        try:
            meta, _body = extract_frontmatter(content)
        except FrontmatterParseError:
            continue
        if not _frontmatter_identity_matches(meta, summary_meta):
            continue
        if str(meta.get("plan", "")).strip() != str(summary_plan).strip():
            continue
        contract_data = meta.get("contract")
        if not isinstance(contract_data, dict):
            continue
        try:
            return ResearchContract.model_validate(contract_data)
        except PydanticValidationError:
            return None
    return None


@instrument_gpd_function("frontmatter.validate")
def validate_frontmatter(content: str, schema_name: str, source_path: Path | None = None) -> FrontmatterValidation:
    """Validate frontmatter against a named schema.

    Raises:
        FrontmatterParseError: On malformed YAML.
        FrontmatterValidationError: If *schema_name* is unknown.
    """
    schema = FRONTMATTER_SCHEMAS.get(schema_name)
    if schema is None:
        available = ", ".join(FRONTMATTER_SCHEMAS)
        raise FrontmatterValidationError(f"Unknown schema: {schema_name}. Available: {available}")

    meta, _ = extract_frontmatter(content)  # may raise FrontmatterParseError
    required = schema["required"]

    missing = [f for f in required if _resolve_field(meta, f) is None]
    present = [f for f in required if _resolve_field(meta, f) is not None]
    errors: list[str] = []

    errors.extend(_unsupported_frontmatter_errors(schema_name, meta))

    if isinstance(meta.get("contract"), dict):
        try:
            contract = ResearchContract.model_validate(meta["contract"])
        except PydanticValidationError as exc:
            errors.append(f"contract: {exc}")
        else:
            if schema_name == "plan":
                errors.extend(f"contract: {issue}" for issue in _validate_plan_contract(contract))

    if schema_name in {"summary", "verification"}:
        plan_contract_ref = meta.get("plan_contract_ref")
        if plan_contract_ref is not None and not isinstance(plan_contract_ref, str):
            errors.append("plan_contract_ref: expected a string")
        if (meta.get("contract_results") is not None or meta.get("comparison_verdicts") is not None) and not isinstance(
            plan_contract_ref, str
        ):
            errors.append("plan_contract_ref: required when contract_results or comparison_verdicts are present")

        contract_results = None
        comparison_verdicts: list[ComparisonVerdict] = []
        suggested_contract_checks: list[SuggestedContractCheck] = []
        try:
            contract_results = _parse_contract_results(meta)
        except (PydanticValidationError, TypeError, ValueError) as exc:
            errors.append(f"contract_results: {exc}")

        try:
            comparison_verdicts = _parse_comparison_verdicts(meta)
        except (PydanticValidationError, TypeError, ValueError) as exc:
            errors.append(f"comparison_verdicts: {exc}")

        if schema_name == "verification":
            try:
                suggested_contract_checks = _parse_suggested_contract_checks(meta)
            except ValueError as exc:
                errors.append(f"suggested_contract_checks: {exc}")

        if source_path is not None:
            plan_contract = _find_matching_plan_contract(Path(source_path).parent, meta)
            if isinstance(plan_contract_ref, str) and plan_contract is None:
                errors.append("plan_contract_ref: could not resolve matching plan contract")
            if plan_contract is not None:
                if not isinstance(plan_contract_ref, str):
                    errors.append("plan_contract_ref: required for contract-backed plan")
                if contract_results is None:
                    errors.append("contract_results: required for contract-backed plan")
                else:
                    if schema_name == "verification":
                        verification_errors = _verification_contract_errors(
                            plan_contract,
                            contract_results,
                            comparison_verdicts,
                            suggested_contract_checks,
                        )
                        errors.extend(verification_errors)
                        errors.extend(
                            _verification_status_errors(
                                meta.get("status"),
                                contract_results,
                                suggested_contract_checks,
                            )
                        )
                    else:
                        errors.extend(_summary_contract_errors(plan_contract, contract_results, comparison_verdicts))

    return FrontmatterValidation(
        valid=len(missing) == 0 and not errors,
        missing=missing,
        present=present,
        errors=errors,
        schema_name=schema_name,
    )


# ---------------------------------------------------------------------------
# Verification suite — result types
# ---------------------------------------------------------------------------


class FileCheckResult(BaseModel):
    checked: int = 0
    found: int = 0
    missing: list[str] = Field(default_factory=list)


class SummaryVerification(BaseModel):
    passed: bool
    summary_exists: bool = False
    files_created: FileCheckResult = Field(default_factory=FileCheckResult)
    commits_exist: bool = False
    self_check: str = "not_found"
    errors: list[str] = Field(default_factory=list)


class TaskInfo(BaseModel):
    name: str
    has_files: bool = False
    has_action: bool = False
    has_verify: bool = False
    has_done: bool = False


class PlanValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    task_count: int = 0
    tasks: list[TaskInfo] = Field(default_factory=list)
    frontmatter_fields: list[str] = Field(default_factory=list)


class PhaseCompleteness(BaseModel):
    complete: bool
    phase_number: str = ""
    plan_count: int = 0
    summary_count: int = 0
    incomplete_plans: list[str] = Field(default_factory=list)
    orphan_summaries: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReferenceVerification(BaseModel):
    valid: bool
    found: int = 0
    missing: list[str] = Field(default_factory=list)
    total: int = 0


class CommitVerification(BaseModel):
    all_valid: bool
    valid_hashes: list[str] = Field(default_factory=list)
    invalid_hashes: list[str] = Field(default_factory=list)
    total: int = 0


class ArtifactCheck(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    path: str
    exists: bool = False
    issues: list[str] = Field(default_factory=list)
    passed: bool = False


class ArtifactVerification(BaseModel):
    all_passed: bool
    passed_count: int = 0
    total: int = 0
    artifacts: list[ArtifactCheck] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers (file/git)
# ---------------------------------------------------------------------------


def _exec_git(cwd: Path, args: list[str]) -> tuple[int, str]:
    """Run a git command, return (exit_code, stdout)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 1, ""


# ---------------------------------------------------------------------------
# Verification suite — implementations
# ---------------------------------------------------------------------------

# Patterns to extract file paths mentioned in markdown
_FILE_MENTION_BACKTICK = re.compile(r"`([^`]+\.[a-zA-Z][a-zA-Z0-9]*)`")
_FILE_MENTION_VERB = re.compile(
    r"(?:Created|Modified|Added|Updated|Edited):\s*`?([^\s`]+\.[a-zA-Z][a-zA-Z0-9]*)`?",
    re.IGNORECASE,
)

# Commit hash patterns: `abc1234` or "commit abc1234"
_COMMIT_HASH_RE = re.compile(
    r"(?:`([0-9a-f]{7,12}|[0-9a-f]{40})`|\bcommit\s+([0-9a-f]{7,40})\b)",
    re.IGNORECASE,
)

# Self-check section heading
_SELF_CHECK_HEADING = re.compile(r"##\s*(?:Self[- ]?Check|Verification|Quality Check)", re.IGNORECASE)
_SELF_CHECK_PASS = re.compile(r"\b(?:(?:all\s+)?pass(?:ed)?|complete[d]?|succeeded)\b", re.IGNORECASE)
_SELF_CHECK_FAIL = re.compile(r"\b(?:fail(?:ed)?|incomplete|blocked)\b", re.IGNORECASE)


@instrument_gpd_function("frontmatter.verify_summary")
def verify_summary(
    cwd: Path,
    summary_path: Path,
    check_file_count: int = 2,
) -> SummaryVerification:
    """Verify a SUMMARY.md file: existence, mentioned files, commit hashes, self-check section."""
    full_path = summary_path if summary_path.is_absolute() else cwd / summary_path

    if not full_path.exists():
        return SummaryVerification(
            passed=False,
            summary_exists=False,
            errors=["SUMMARY.md not found"],
        )

    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return SummaryVerification(
            passed=False,
            summary_exists=True,
            errors=[f"Cannot read file (invalid UTF-8): {exc}"],
        )
    try:
        meta, _body = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return SummaryVerification(
            passed=False,
            summary_exists=True,
            errors=[f"Frontmatter YAML parse error: {exc}"],
        )

    errors: list[str] = []

    try:
        contract_results = _parse_contract_results(meta)
    except (PydanticValidationError, TypeError, ValueError) as exc:
        return SummaryVerification(
            passed=False,
            summary_exists=True,
            errors=[f"Invalid contract_results: {exc}"],
        )

    try:
        comparison_verdicts = _parse_comparison_verdicts(meta)
    except (PydanticValidationError, TypeError, ValueError) as exc:
        return SummaryVerification(
            passed=False,
            summary_exists=True,
            errors=[f"Invalid comparison_verdicts: {exc}"],
        )

    plan_contract_ref = meta.get("plan_contract_ref")
    plan_contract = _find_matching_plan_contract(full_path.parent, meta)
    if isinstance(plan_contract_ref, str) and plan_contract is None:
        errors.append("plan_contract_ref: could not resolve matching plan contract")
    if plan_contract is not None:
        if not isinstance(meta.get("plan_contract_ref"), str):
            errors.append("Contract-backed plan requires summary plan_contract_ref")
        if contract_results is None:
            errors.append("Contract-backed plan requires summary contract_results")
        else:
            errors.extend(_summary_contract_errors(plan_contract, contract_results, comparison_verdicts))

    # --- Spot-check files mentioned in summary ---
    mentioned: set[str] = set()
    raw_key_files = meta.get("key-files")
    if isinstance(raw_key_files, dict):
        for key in ("created", "modified"):
            value = raw_key_files.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and "/" in item:
                        mentioned.add(item)
    elif isinstance(raw_key_files, list):
        for item in raw_key_files:
            if isinstance(item, str) and "/" in item:
                mentioned.add(item)
    for pattern in (_FILE_MENTION_BACKTICK, _FILE_MENTION_VERB):
        for m in pattern.finditer(content):
            fp = m.group(1)
            if fp and not fp.startswith("http") and "/" in fp:
                mentioned.add(fp)

    files_to_check = list(mentioned)[:check_file_count]
    missing_files = [f for f in files_to_check if not (cwd / f).exists()]

    # --- Commit hashes ---
    hashes = [m.group(1) or m.group(2) for m in _COMMIT_HASH_RE.finditer(content)]
    commits_exist = False
    for h in hashes[:3]:
        exit_code, stdout = _exec_git(cwd, ["cat-file", "-t", h])
        if exit_code == 0 and stdout == "commit":
            commits_exist = True
            break

    # --- Self-check section ---
    self_check = "not_found"
    heading_match = _SELF_CHECK_HEADING.search(content)
    if heading_match:
        check_start = heading_match.start()
        next_heading = content.find("\n## ", check_start + 1)
        section = content[check_start:] if next_heading == -1 else content[check_start:next_heading]
        if _SELF_CHECK_FAIL.search(section):
            self_check = "failed"
        elif _SELF_CHECK_PASS.search(section):
            self_check = "passed"

    if missing_files:
        errors.append("Missing files: " + ", ".join(missing_files))
    if not commits_exist and hashes:
        errors.append("Referenced commit hashes not found in git history")
    if self_check == "failed":
        errors.append("Self-check section indicates failure")

    passed = len(errors) == 0 and len(missing_files) == 0 and self_check != "failed" and not (not commits_exist and hashes)
    return SummaryVerification(
        passed=passed,
        summary_exists=True,
        files_created=FileCheckResult(
            checked=len(files_to_check),
            found=len(files_to_check) - len(missing_files),
            missing=missing_files,
        ),
        commits_exist=commits_exist,
        self_check=self_check,
        errors=errors,
    )


# Task XML patterns
_TASK_ELEMENT_RE = re.compile(r"<task[^>]*>([\s\S]*?)</task>")
_TASK_NAME_RE = re.compile(r"<name>([\s\S]*?)</name>")
_CHECKPOINT_TASK_RE = re.compile(r'<task\s+[^>]*?type=["\']?checkpoint')


@instrument_gpd_function("frontmatter.verify_plan")
def verify_plan_structure(cwd: Path, file_path: Path) -> PlanValidation:
    """Validate plan file structure: required frontmatter, task elements, wave/deps consistency."""
    full_path = file_path if file_path.is_absolute() else cwd / file_path
    content = safe_read_file(full_path)
    if content is None:
        return PlanValidation(valid=False, errors=[f"File not found: {file_path}"])

    try:
        meta, _ = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return PlanValidation(valid=False, errors=[f"YAML parse error: {exc}"])

    errors: list[str] = []
    warnings: list[str] = []

    if "must_haves" in meta:
        errors.append(
            "Unsupported frontmatter field: must_haves. Encode execution and verification targets in the contract block."
        )

    # Required frontmatter fields use the canonical underscore schema.
    for fname in FRONTMATTER_SCHEMAS["plan"]["required"]:
        if _resolve_field(meta, fname) is None:
            errors.append(f"Missing required frontmatter field: {fname}")

    # Contract-backed validation
    contract: ResearchContract | None = None
    if isinstance(meta.get("contract"), dict):
        try:
            contract = ResearchContract.model_validate(meta["contract"])
        except PydanticValidationError as exc:
            errors.append(f"Invalid contract: {exc}")
        else:
            errors.extend(f"Invalid contract: {issue}" for issue in _validate_plan_contract(contract))
    elif "contract" in meta:
        errors.append("Invalid contract: expected an object")

    # Parse task elements
    tasks: list[TaskInfo] = []
    for task_match in _TASK_ELEMENT_RE.finditer(content):
        task_content = task_match.group(1)
        name_match = _TASK_NAME_RE.search(task_content)
        task_name = name_match.group(1).strip() if name_match else "unnamed"

        has_files = "<files>" in task_content
        has_action = "<action>" in task_content
        has_verify = "<verify>" in task_content
        has_done = "<done>" in task_content

        if not name_match:
            errors.append("Task missing <name> element")
        if not has_action:
            errors.append(f"Task '{task_name}' missing <action>")
        if not has_verify:
            warnings.append(f"Task '{task_name}' missing <verify>")
        if not has_done:
            warnings.append(f"Task '{task_name}' missing <done>")
        if not has_files:
            warnings.append(f"Task '{task_name}' missing <files>")

        tasks.append(
            TaskInfo(
                name=task_name,
                has_files=has_files,
                has_action=has_action,
                has_verify=has_verify,
                has_done=has_done,
            )
        )

    if not tasks:
        warnings.append("No <task> elements found")

    # Wave/depends_on consistency
    deps = meta.get("depends_on")
    wave = meta.get("wave")
    if wave is not None:
        try:
            wave_int = int(wave)
        except (TypeError, ValueError):
            wave_int = 0
        if wave_int > 1 and (not deps or (isinstance(deps, list) and len(deps) == 0)):
            warnings.append("Wave > 1 but depends_on is empty")

    # Interactive/checkpoint consistency
    has_checkpoints = bool(_CHECKPOINT_TASK_RE.search(content))
    interactive = meta.get("interactive")
    interactive_enabled = interactive in ("true", True)
    if has_checkpoints and not interactive_enabled:
        errors.append("Has checkpoint tasks but interactive is not true")
    if interactive_enabled and not has_checkpoints:
        errors.append("interactive is true but no checkpoint tasks were found")

    return PlanValidation(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        task_count=len(tasks),
        tasks=tasks,
        frontmatter_fields=list(meta.keys()),
    )


@instrument_gpd_function("frontmatter.verify_phase")
def verify_phase_completeness(cwd: Path, phase: str) -> PhaseCompleteness:
    """Verify that every plan in a phase has a matching summary.

    Uses lazy import of ``find_phase`` from ``gpd.core.phases``
    to break circular dependency.
    """
    from gpd.core.phases import find_phase

    phase_info = find_phase(cwd, phase)
    if phase_info is None:
        return PhaseCompleteness(
            complete=False,
            errors=[f"Phase not found: {phase}"],
        )

    phase_dir = cwd / phase_info.directory
    if not phase_dir.is_dir():
        return PhaseCompleteness(
            complete=False,
            errors=["Cannot read phase directory"],
        )

    files = [f.name for f in phase_dir.iterdir() if f.is_file()]
    plans = [f for f in files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
    summaries = [f for f in files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]

    # Extract plan IDs
    def plan_id(p: str) -> str:
        if p == STANDALONE_PLAN:
            return "_standalone"
        return p.removesuffix(PLAN_SUFFIX) if p.endswith(PLAN_SUFFIX) else p

    def summary_id(s: str) -> str:
        if s == STANDALONE_SUMMARY:
            return "_standalone"
        return s.removesuffix(SUMMARY_SUFFIX) if s.endswith(SUMMARY_SUFFIX) else s

    plan_ids = {plan_id(p) for p in plans}
    summary_ids = {summary_id(s) for s in summaries}

    incomplete = sorted(plan_ids - summary_ids)
    orphans = sorted(summary_ids - plan_ids)

    errors: list[str] = []
    warnings: list[str] = []
    if incomplete:
        errors.append(f"Plans without summaries: {', '.join(incomplete)}")
    if orphans:
        warnings.append(f"Summaries without plans: {', '.join(orphans)}")

    return PhaseCompleteness(
        complete=len(errors) == 0,
        phase_number=phase_info.phase_number,
        plan_count=len(plans),
        summary_count=len(summaries),
        incomplete_plans=incomplete,
        orphan_summaries=orphans,
        errors=errors,
        warnings=warnings,
    )


# Patterns for file references
_AT_REF_RE = re.compile(r"@([^\s\n,)]+/[^\s\n,)]+)")
_BACKTICK_FILE_RE = re.compile(r"`([^`]+/[^`]+\.[a-zA-Z][a-zA-Z0-9]{0,9})`")


@instrument_gpd_function("frontmatter.verify_references")
def verify_references(cwd: Path, file_path: Path) -> ReferenceVerification:
    """Check that ``@path`` and backtick-quoted file paths actually exist on disk."""
    full_path = file_path if file_path.is_absolute() else cwd / file_path
    content = safe_read_file(full_path)
    if content is None:
        return ReferenceVerification(valid=False, missing=[str(file_path)])

    found: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    # @-references
    for m in _AT_REF_RE.finditer(content):
        ref = m.group(1)
        if ref in seen:
            continue
        seen.add(ref)
        resolved = Path.home() / ref[2:] if ref.startswith("~/") else cwd / ref
        (found if resolved.exists() else missing).append(ref)

    # Backtick file paths
    for m in _BACKTICK_FILE_RE.finditer(content):
        ref = m.group(1)
        if ref in seen or ref.startswith("http") or "${" in ref or "{{" in ref:
            continue
        seen.add(ref)
        resolved = cwd / ref
        (found if resolved.exists() else missing).append(ref)

    return ReferenceVerification(
        valid=len(missing) == 0,
        found=len(found),
        missing=missing,
        total=len(found) + len(missing),
    )


@instrument_gpd_function("frontmatter.verify_commits")
def verify_commits(cwd: Path, hashes: list[str]) -> CommitVerification:
    """Verify that git commit hashes exist in the repository."""
    if not hashes:
        raise FrontmatterValidationError("At least one commit hash required")

    valid: list[str] = []
    invalid: list[str] = []
    for h in hashes:
        exit_code, stdout = _exec_git(cwd, ["cat-file", "-t", h])
        if exit_code == 0 and stdout.strip() == "commit":
            valid.append(h)
        else:
            invalid.append(h)

    return CommitVerification(
        all_valid=len(invalid) == 0,
        valid_hashes=valid,
        invalid_hashes=invalid,
        total=len(hashes),
    )


@instrument_gpd_function("frontmatter.verify_artifacts")
def verify_artifacts(cwd: Path, plan_file_path: Path) -> ArtifactVerification:
    """Verify artifact deliverables declared in the canonical plan contract."""
    full_path = plan_file_path if plan_file_path.is_absolute() else cwd / plan_file_path
    content = safe_read_file(full_path)
    if content is None:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[ArtifactCheck(path=str(plan_file_path), issues=["Plan file not found"])],
            total=1,
        )

    try:
        contract = parse_contract_block(content)
    except FrontmatterValidationError as exc:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[ArtifactCheck(path=str(plan_file_path), issues=[str(exc)])],
            total=1,
        )

    if contract is None:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[ArtifactCheck(path=str(plan_file_path), issues=["Plan contract not found"])],
            total=1,
        )

    deliverables = [deliverable for deliverable in contract.deliverables if deliverable.path]
    if not deliverables:
        return ArtifactVerification(
            all_passed=True,
            artifacts=[],
            total=0,
        )

    results: list[ArtifactCheck] = []
    for deliverable in deliverables:
        art_path = str(deliverable.path)
        art_full = cwd / art_path
        exists = art_full.exists()
        check = ArtifactCheck(path=art_path, exists=exists)

        if exists:
            file_content = safe_read_file(art_full) or ""
            for required_fragment in deliverable.must_contain:
                if required_fragment not in file_content:
                    check.issues.append(f"Missing pattern: {required_fragment}")

            check.passed = len(check.issues) == 0
        else:
            check.issues.append("File not found")

        results.append(check)

    passed_count = sum(1 for r in results if r.passed)
    return ArtifactVerification(
        all_passed=passed_count == len(results) and len(results) > 0,
        passed_count=passed_count,
        total=len(results),
        artifacts=results,
    )
