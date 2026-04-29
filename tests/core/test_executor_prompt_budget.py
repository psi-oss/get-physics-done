"""Prompt-budget assertions for `gpd-executor` bootstrap loading."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
SPECS_DIR = REPO_ROOT / "src/gpd/specs"


def _read_executor_prompt() -> str:
    return (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    _, start_marker, tail = text.partition(start)
    assert start_marker, f"Missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"Missing marker: {end}"
    return body


def test_executor_bootstrap_does_not_eagerly_load_completion_only_templates() -> None:
    executor = _read_executor_prompt()
    role = _between(executor, "<role>", "</role>")

    assert "@{GPD_INSTALL_DIR}/templates/summary.md" not in role
    assert "@{GPD_INSTALL_DIR}/templates/calculation-log.md" not in role
    assert "@{GPD_INSTALL_DIR}/references/protocols/order-of-limits.md" not in role
    assert "Pattern A:" not in role
    assert "Pattern B:" not in role
    assert "Pattern C:" not in role
    assert "Pattern D:" not in role
    assert "first-result" not in role
    assert "pre-fanout" not in role
    assert "bounded execution segment envelope" not in role


def test_executor_prompt_does_not_self_bootstrap_execute_phase() -> None:
    executor = _read_executor_prompt()

    assert "execute-plan command" not in executor
    assert "init execute-phase" not in executor
    assert 'gpd --raw init execute-phase "${PHASE}"' not in executor
    assert "Do not bootstrap phase state from inside the executor." in executor


def test_expanded_executor_prompt_stays_under_budget_and_excludes_late_publication_artifacts() -> None:
    expanded = expand_at_includes(_read_executor_prompt(), SPECS_DIR, "/runtime/")

    bootstrap, _, _ = expanded.partition("<summary_creation>")

    assert len(expanded) < 220_000
    assert "Order-of-Limits Awareness" not in bootstrap
    assert "main.tex" not in expanded


def test_executor_context_pressure_thresholds_match_canonical_forced_checkpoint_wording() -> None:
    executor = _read_executor_prompt()
    canonical = (SPECS_DIR / "references/orchestration/context-pressure-thresholds.md").read_text(encoding="utf-8")

    assert "| gpd-executor | < 40% | 40-55% | 55-70% | > 70% |" in canonical
    assert "GREEN <40%, YELLOW 40-55%, ORANGE 55-70%, RED >70%" in executor
    assert "forced-checkpoint rule at 50%" in executor
    assert "preservation checkpoint inside YELLOW, not an ORANGE reclassification" in executor
    assert "If running total exceeds 50%, you are in ORANGE" not in executor
    assert ">50% context consumed" not in executor
