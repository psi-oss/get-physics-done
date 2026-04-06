"""Schema-driven parity checks for model-visible contract prompt surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args, get_origin

from gpd.adapters.install_utils import expand_at_includes
from gpd.contracts import (
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
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_DIR = REPO_ROOT / "src/gpd/specs"
TEMPLATES_DIR = SPECS_DIR / "templates"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"

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


def test_plan_contract_schema_surfaces_canonical_research_contract_fields() -> None:
    plan_schema = _read(TEMPLATES_DIR / "plan-contract-schema.md")

    _assert_tokens_visible(plan_schema, _field_tokens(*PLAN_MODELS), label="plan-contract-schema.md")
    assert "scalar|curve|map|classification|proof_obligation|other" in plan_schema
    assert "do not count as grounding" in plan_schema
    assert "proof-specific acceptance test" in plan_schema
    assert "proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses" in plan_schema


def test_expanded_phase_prompt_surfaces_the_same_research_contract_fields_before_generation() -> None:
    phase_prompt = _expanded(TEMPLATES_DIR / "phase-prompt.md")

    _assert_tokens_visible(phase_prompt, _field_tokens(*PLAN_MODELS), label="expanded phase-prompt.md")
    assert "scalar|curve|map|classification|proof_obligation|other" in phase_prompt
    assert "do not count as grounding" in phase_prompt
    assert "proof-specific acceptance test" in phase_prompt
    assert "proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses" in phase_prompt


def test_contract_results_schema_and_verification_template_surface_canonical_result_ledger_fields() -> None:
    contract_results_schema = _read(TEMPLATES_DIR / "contract-results-schema.md")
    verification_report = _read(TEMPLATES_DIR / "verification-report.md")

    tokens = _field_tokens(*RESULT_MODELS)
    _assert_tokens_visible(contract_results_schema, tokens, label="contract-results-schema.md")
    _assert_phrases_visible(contract_results_schema, _choice_phrases(*RESULT_MODELS), label="contract-results-schema.md")
    assert "contract-results-schema.md" in verification_report
    for token in ("contract_results", "comparison_verdicts", "suggested_contract_checks", "subject_role"):
        assert token in verification_report
    assert "proof-audit rules in the canonical schema" in verification_report


def test_expanded_verifier_and_executor_prompts_keep_canonical_result_ledger_fields_visible() -> None:
    verifier_prompt = _expanded(AGENTS_DIR / "gpd-verifier.md")
    executor_prompt = _expanded(AGENTS_DIR / "gpd-executor.md")

    tokens = _field_tokens(*RESULT_MODELS)
    phrases = _choice_phrases(*RESULT_MODELS)

    _assert_tokens_visible(verifier_prompt, tokens, label="expanded gpd-verifier.md")
    _assert_tokens_visible(executor_prompt, tokens, label="expanded gpd-executor.md")
    _assert_phrases_visible(verifier_prompt, phrases, label="expanded gpd-verifier.md")
    _assert_phrases_visible(executor_prompt, phrases, label="expanded gpd-executor.md")
