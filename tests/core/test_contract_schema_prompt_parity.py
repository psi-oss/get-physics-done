"""Schema-driven parity checks for model-visible contract prompt surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args, get_origin

from gpd.adapters.install_utils import expand_at_includes
from gpd.contracts import (
    CONTRACT_ACCEPTANCE_AUTOMATION_VALUES,
    CONTRACT_ACCEPTANCE_TEST_KIND_VALUES,
    CONTRACT_CLAIM_KIND_VALUES,
    CONTRACT_DELIVERABLE_KIND_VALUES,
    CONTRACT_LINK_RELATION_VALUES,
    CONTRACT_OBSERVABLE_KIND_VALUES,
    CONTRACT_REFERENCE_ACTION_VALUES,
    CONTRACT_REFERENCE_KIND_VALUES,
    CONTRACT_REFERENCE_ROLE_VALUES,
    PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES,
    PROOF_AUDIT_QUANTIFIER_STATUS_VALUES,
    PROOF_AUDIT_SCOPE_STATUS_VALUES,
    PROOF_HYPOTHESIS_CATEGORY_VALUES,
    ComparisonVerdict,
    ContractAcceptanceTest,
    ContractApproachPolicy,
    ContractClaim,
    ContractContextIntake,
    ContractDeliverable,
    ContractEvidenceEntry,
    ContractForbiddenProxy,
    ContractForbiddenProxyResult,
    ContractLink,
    ContractObservable,
    ContractProofAudit,
    ContractProofConclusionClause,
    ContractProofHypothesis,
    ContractProofParameter,
    ContractReference,
    ContractReferenceUsage,
    ContractResultEntry,
    ContractResults,
    ContractScope,
    ContractUncertaintyMarkers,
    ResearchContract,
    SuggestedContractCheck,
    VerificationEvidence,
)
from gpd.core import project_contract_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_DIR = REPO_ROOT / "src/gpd/specs"
TEMPLATES_DIR = SPECS_DIR / "templates"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"

PLAN_QUANTIFIER_VISIBILITY_PHRASES = (
    "Quantifiers are visible when explicit quantifier or domain obligations exist; unquantified proof-bearing claims "
    "do not need a non-empty quantifier list.",
)
PROJECT_QUANTIFIER_VISIBILITY_PHRASES = (
    "proof-bearing claims must keep `parameters`, `hypotheses`, `conclusion_clauses`, and `proof_deliverables` "
    "visible, and must keep `quantifiers` visible when an explicit quantifier or domain obligation exists",
    "`claims[].quantifiers[]` is optional for unquantified proof-bearing claims",
)
RESULT_QUANTIFIER_VISIBILITY_PHRASES = (
    "A claim is quantified for this rule when explicit `claims[].quantifiers[]` or domain obligations are declared",
    "unquantified proof-bearing claims do not need a non-empty quantifier list",
)

PLAN_MODELS = (
    ResearchContract,
    ContractScope,
    ContractContextIntake,
    ContractApproachPolicy,
    ContractObservable,
    ContractClaim,
    ContractDeliverable,
    ContractAcceptanceTest,
    ContractReference,
    ContractForbiddenProxy,
    ContractLink,
    ContractUncertaintyMarkers,
    ContractProofParameter,
    ContractProofHypothesis,
    ContractProofConclusionClause,
)

RESULT_MODELS = (
    ContractResults,
    ContractResultEntry,
    ContractReferenceUsage,
    ContractForbiddenProxyResult,
    ContractEvidenceEntry,
    ComparisonVerdict,
    SuggestedContractCheck,
    ContractUncertaintyMarkers,
    ContractProofAudit,
)

_LITERAL_TOKEN_EXCLUSIONS: dict[type[object], set[str]] = {
    ContractProofHypothesis: {"category"},
    ContractProofAudit: {"quantifier_status", "scope_status", "counterexample_status"},
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _expanded(path: Path) -> str:
    return expand_at_includes(_read(path), SPECS_DIR, "/runtime/")


def _literal_tokens(annotation: object) -> set[str]:
    origin = get_origin(annotation)
    if origin is Literal:
        return {arg for arg in get_args(annotation) if isinstance(arg, str)}

    tokens: set[str] = set()
    for arg in get_args(annotation):
        tokens.update(_literal_tokens(arg))
    return tokens


def _ordered_literal_tokens(annotation: object) -> tuple[str, ...]:
    origin = get_origin(annotation)
    if origin is Literal:
        return tuple(arg for arg in get_args(annotation) if isinstance(arg, str))

    tokens: list[str] = []
    for arg in get_args(annotation):
        tokens.extend(_ordered_literal_tokens(arg))
    return tuple(tokens)


def _field_tokens(*models: type[object]) -> set[str]:
    tokens: set[str] = set()
    for model in models:
        for field_name, field in model.model_fields.items():
            tokens.add(field_name)
            if model is ContractReferenceUsage and field_name in {"completed_actions", "missing_actions"}:
                continue
            if field_name in _LITERAL_TOKEN_EXCLUSIONS.get(model, set()):
                continue
            tokens.update(_literal_tokens(field.annotation))
    return tokens


def _choice_phrases(*models: type[object]) -> set[str]:
    phrases: set[str] = set()
    for model in models:
        for field_name, field in model.model_fields.items():
            if model is ContractReferenceUsage and field_name in {"completed_actions", "missing_actions"}:
                continue
            if model is ContractProofAudit:
                continue
            if field_name in _LITERAL_TOKEN_EXCLUSIONS.get(model, set()):
                continue
            values = _ordered_literal_tokens(field.annotation)
            if len(values) > 1:
                phrases.add("|".join(values))
    return phrases


def _assert_tokens_visible(text: str, tokens: set[str], *, label: str) -> None:
    missing = sorted(token for token in tokens if token not in text)
    assert not missing, f"{label} is missing canonical tokens: {', '.join(missing)}"


def _assert_phrases_visible(text: str, phrases: set[str], *, label: str) -> None:
    missing = sorted(phrase for phrase in phrases if phrase not in text)
    assert not missing, f"{label} is missing canonical choice phrases: {', '.join(missing)}"


def _choice_line(field_name: str, values: tuple[str, ...]) -> str:
    return f"{field_name}: {' | '.join(values)}"


def test_plan_contract_schema_surfaces_canonical_research_contract_fields() -> None:
    raw_plan_schema = _read(TEMPLATES_DIR / "plan-contract-schema.md")
    plan_schema = _expanded(TEMPLATES_DIR / "plan-contract-schema.md")

    assert "@{GPD_INSTALL_DIR}/templates/contract-proof-obligation-rules.md" in raw_plan_schema
    _assert_tokens_visible(plan_schema, _field_tokens(*PLAN_MODELS), label="plan-contract-schema.md")
    assert "scalar|curve|map|classification|proof_obligation|other" in plan_schema
    assert "do not count as grounding" in plan_schema
    assert "proof-specific acceptance test" in plan_schema
    assert "proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses" in plan_schema
    for phrase in PLAN_QUANTIFIER_VISIBILITY_PHRASES:
        assert phrase in plan_schema


def test_expanded_phase_prompt_surfaces_the_same_research_contract_fields_before_generation() -> None:
    phase_prompt = _expanded(TEMPLATES_DIR / "phase-prompt.md")

    _assert_tokens_visible(phase_prompt, _field_tokens(*PLAN_MODELS), label="expanded phase-prompt.md")
    assert "scalar|curve|map|classification|proof_obligation|other" in phase_prompt
    assert "do not count as grounding" in phase_prompt
    assert "proof-specific acceptance test" in phase_prompt
    assert "proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses" in phase_prompt
    for phrase in PLAN_QUANTIFIER_VISIBILITY_PHRASES:
        assert phrase in phase_prompt


def test_contract_results_schema_and_verification_template_surface_canonical_result_ledger_fields() -> None:
    contract_results_schema = _read(TEMPLATES_DIR / "contract-results-schema.md")
    verification_report = _read(TEMPLATES_DIR / "verification-report.md")

    tokens = _field_tokens(*RESULT_MODELS)
    _assert_tokens_visible(contract_results_schema, tokens, label="contract-results-schema.md")
    _assert_phrases_visible(contract_results_schema, _choice_phrases(*RESULT_MODELS), label="contract-results-schema.md")
    assert (
        "Inside `evidence[]`, list-typed proof coverage fields (`covered_hypothesis_ids`, "
        "`missing_hypothesis_ids`, `covered_parameter_symbols`, `missing_parameter_symbols`, "
        "`uncovered_conclusion_clause_ids`) must stay YAML lists even when they contain a single item. "
        "Keep quantifier coverage in `proof_audit.uncovered_quantifiers`, not in `evidence[]`."
        in contract_results_schema
    )
    assert "contract-results-schema.md" in verification_report
    for token in ("contract_results", "suggested_contract_checks"):
        assert token in verification_report
    assert "proof-audit rules in the canonical schema" in verification_report
    for phrase in RESULT_QUANTIFIER_VISIBILITY_PHRASES:
        assert phrase in contract_results_schema


def test_expanded_verifier_and_executor_prompts_keep_canonical_result_ledger_fields_visible() -> None:
    verifier_prompt = _expanded(AGENTS_DIR / "gpd-verifier.md")
    executor_prompt = _expanded(AGENTS_DIR / "gpd-executor.md")

    tokens = _field_tokens(*RESULT_MODELS)
    phrases = _choice_phrases(*RESULT_MODELS)

    _assert_tokens_visible(verifier_prompt, tokens, label="expanded gpd-verifier.md")
    _assert_tokens_visible(executor_prompt, tokens, label="expanded gpd-executor.md")
    _assert_phrases_visible(verifier_prompt, phrases, label="expanded gpd-verifier.md")
    _assert_phrases_visible(executor_prompt, phrases, label="expanded gpd-executor.md")


def test_project_contract_schema_examples_surface_validator_accepted_proof_objects() -> None:
    for schema_name in ("project-contract-schema.md", "state-json-schema.md"):
        schema_text = _expanded(TEMPLATES_DIR / schema_name)
        assert '"parameters": [' in schema_text
        assert '"hypotheses": [' in schema_text
        assert '"conclusion_clauses": [' in schema_text
        assert '"symbol": "k"' in schema_text
        assert '"id": "hyp-main"' in schema_text
        assert '"id": "concl-main"' in schema_text
        assert '"automation": "human"' in schema_text
        assert "Project Contract ID Linkage Rules" in schema_text
        assert "`context_intake.must_read_refs[]` must contain `references[].id` values only." in schema_text
        assert (
            "`links[].source` and `links[].target` may point only to observable, claim, deliverable, "
            "acceptance-test, reference, forbidden-proxy, or link IDs."
        ) in schema_text
        assert "`links[].verified_by[]` must contain `acceptance_tests[].id` values only." in schema_text
        for phrase in PROJECT_QUANTIFIER_VISIBILITY_PHRASES:
            assert phrase in schema_text


def test_state_json_schema_references_project_contract_schema_as_single_raw_source() -> None:
    raw_state_schema = _read(TEMPLATES_DIR / "state-json-schema.md")
    expanded_state_schema = _expanded(TEMPLATES_DIR / "state-json-schema.md")

    assert raw_state_schema.count("@{GPD_INSTALL_DIR}/templates/project-contract-schema.md") == 1
    assert raw_state_schema.count("@{GPD_INSTALL_DIR}/templates/contract-proof-obligation-rules.md") == 0
    assert "# Project Contract Schema" not in raw_state_schema
    assert '"claim-main"' not in raw_state_schema
    assert "This state schema intentionally includes that template instead of restating" in raw_state_schema

    assert "# Project Contract Schema" in expanded_state_schema
    assert '"claim-main"' in expanded_state_schema
    assert "Project Contract ID Linkage Rules" in expanded_state_schema
    assert expanded_state_schema.count("Use these rules for both PLAN frontmatter contracts") == 1


def test_project_and_state_contract_schemas_surface_full_closed_research_vocabularies() -> None:
    expected_lines = (
        _choice_line("observables[].kind", CONTRACT_OBSERVABLE_KIND_VALUES),
        _choice_line("deliverables[].kind", CONTRACT_DELIVERABLE_KIND_VALUES),
        _choice_line("acceptance_tests[].kind", CONTRACT_ACCEPTANCE_TEST_KIND_VALUES),
        _choice_line("acceptance_tests[].automation", CONTRACT_ACCEPTANCE_AUTOMATION_VALUES),
        _choice_line("references[].kind", CONTRACT_REFERENCE_KIND_VALUES),
        _choice_line("references[].role", CONTRACT_REFERENCE_ROLE_VALUES),
        _choice_line("links[].relation", CONTRACT_LINK_RELATION_VALUES),
    )

    for schema_name in ("project-contract-schema.md", "state-json-schema.md"):
        schema_text = _expanded(TEMPLATES_DIR / schema_name)
        for line in expected_lines:
            assert line in schema_text, f"{schema_name} is missing canonical enum line: {line}"


def test_project_contract_schema_case_recovery_uses_canonical_proof_hypothesis_categories() -> None:
    matching_choices = [
        choices
        for pattern, choices in project_contract_schema._LITERAL_CASE_DRIFT_FIELD_PATTERNS
        if pattern.pattern == r"^claims\.\d+\.hypotheses\.\d+\.category$"
    ]

    assert matching_choices == [PROOF_HYPOTHESIS_CATEGORY_VALUES]


def test_project_contract_model_literals_use_exported_enum_constants() -> None:
    assert _ordered_literal_tokens(ContractObservable.model_fields["kind"].annotation) == CONTRACT_OBSERVABLE_KIND_VALUES
    assert _ordered_literal_tokens(ContractClaim.model_fields["claim_kind"].annotation) == CONTRACT_CLAIM_KIND_VALUES
    assert _ordered_literal_tokens(ContractDeliverable.model_fields["kind"].annotation) == CONTRACT_DELIVERABLE_KIND_VALUES
    assert (
        _ordered_literal_tokens(ContractAcceptanceTest.model_fields["kind"].annotation)
        == CONTRACT_ACCEPTANCE_TEST_KIND_VALUES
    )
    assert (
        _ordered_literal_tokens(ContractAcceptanceTest.model_fields["automation"].annotation)
        == CONTRACT_ACCEPTANCE_AUTOMATION_VALUES
    )
    assert _ordered_literal_tokens(ContractReference.model_fields["kind"].annotation) == CONTRACT_REFERENCE_KIND_VALUES
    assert _ordered_literal_tokens(ContractReference.model_fields["role"].annotation) == CONTRACT_REFERENCE_ROLE_VALUES
    assert (
        _ordered_literal_tokens(ContractReference.model_fields["required_actions"].annotation)
        == CONTRACT_REFERENCE_ACTION_VALUES
    )
    assert _ordered_literal_tokens(ContractLink.model_fields["relation"].annotation) == CONTRACT_LINK_RELATION_VALUES


def test_contract_results_schema_and_expanded_prompts_surface_full_proof_audit_status_vocabularies() -> None:
    expected_lines = (
        _choice_line("proof_audit.completeness", _ordered_literal_tokens(ContractProofAudit.model_fields["completeness"].annotation)),
        _choice_line("proof_audit.quantifier_status", PROOF_AUDIT_QUANTIFIER_STATUS_VALUES),
        _choice_line("proof_audit.scope_status", PROOF_AUDIT_SCOPE_STATUS_VALUES),
        _choice_line("proof_audit.counterexample_status", PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES),
        _choice_line("evidence[].confidence", _ordered_literal_tokens(VerificationEvidence.model_fields["confidence"].annotation)),
    )

    contract_results_schema = _read(TEMPLATES_DIR / "contract-results-schema.md")
    verifier_prompt = _expanded(AGENTS_DIR / "gpd-verifier.md")
    executor_prompt = _expanded(AGENTS_DIR / "gpd-executor.md")

    for line in expected_lines:
        assert line in contract_results_schema
        assert line in verifier_prompt
        assert line in executor_prompt
