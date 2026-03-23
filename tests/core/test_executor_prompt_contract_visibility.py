"""Focused regressions for contract-schema visibility in executor summary creation."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes
from gpd.contracts import ComparisonVerdict, ContractResults

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
EXECUTION_REFERENCE_DIR = REPO_ROOT / "src/gpd/specs/references/execution"


def _read_executor_prompt() -> str:
    return (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")


def _read_executor_completion_reference() -> str:
    return (EXECUTION_REFERENCE_DIR / "executor-completion.md").read_text(encoding="utf-8")


def _read_executor_worked_example() -> str:
    return (EXECUTION_REFERENCE_DIR / "executor-worked-example.md").read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    _, start_marker, tail = text.partition(start)
    assert start_marker, f"Missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"Missing marker: {end}"
    return body


def _assert_contract_schema_tokens_visible(text: str) -> None:
    assert "plan_contract_ref" in text
    for token in ContractResults.model_fields:
        assert f"`{token}`" in text or f"{token}:" in text, f"Missing contract-results token: {token}"
    for token in ComparisonVerdict.model_fields:
        assert f"`{token}`" in text or f"{token}:" in text, f"Missing comparison-verdict token: {token}"


def test_executor_summary_creation_requires_loading_contract_schema_before_frontmatter() -> None:
    executor = _read_executor_prompt()
    summary_creation = _between(executor, "<summary_creation>", "</summary_creation>")

    assert "explicitly load and read the canonical ledger schema before drafting any YAML" in summary_creation
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" in summary_creation
    assert "Re-open it immediately before writing frontmatter" in summary_creation
    assert "Do not rely on memory, prior plans, or a paraphrase from `templates/summary.md`." in summary_creation
    assert "load the schema above before writing frontmatter" in summary_creation


def test_expanded_executor_prompt_keeps_contract_results_schema_visible_for_summary_creation() -> None:
    expanded = expand_at_includes(
        _read_executor_prompt(),
        REPO_ROOT / "src/gpd/specs",
        "/runtime/",
    )

    assert "# Contract Results Schema" in expanded
    assert "Must end with the exact `#/contract` fragment" in expanded
    assert "These ledgers are user-visible evidence." in expanded
    _assert_contract_schema_tokens_visible(expanded)


def test_executor_reference_examples_keep_uncertainty_markers_explicit_and_non_empty() -> None:
    for text in (_read_executor_completion_reference(), _read_executor_worked_example()):
        assert "uncertainty_markers:" in text
        assert "weakest_anchors: []" not in text
        assert "unvalidated_assumptions: []" not in text
        assert "competing_explanations: []" not in text
        assert "disconfirming_observations: []" not in text
        assert 'weakest_anchors: ["finite-term mass matching"]' in text
        assert 'unvalidated_assumptions: ["general-gauge-independence"]' in text
        assert 'competing_explanations: ["on-shell vs MS-bar finite-part conventions"]' in text
        assert 'disconfirming_observations: ["no independent gauge-parameter scan"]' in text
