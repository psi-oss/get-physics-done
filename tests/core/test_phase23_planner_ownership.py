"""Planner ownership regressions for the Phase 23 thinning slice."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNER_PATH = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-planner.md"


def _read_planner_prompt() -> str:
    return PLANNER_PATH.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    _, start_marker, tail = text.partition(start)
    assert start_marker, f"Missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"Missing marker: {end}"
    return body


def test_planner_keeps_schema_bootstrap_visible_before_plan_examples() -> None:
    planner = _read_planner_prompt()
    role = _between(planner, "<role>", "</role>")

    phase_prompt_idx = role.index("@{GPD_INSTALL_DIR}/templates/phase-prompt.md")
    contract_schema_idx = role.index(
        "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md"
    )
    plan_emission_idx = role.index("before any `PLAN.md` emission.")

    assert phase_prompt_idx < plan_emission_idx
    assert contract_schema_idx < plan_emission_idx
    assert "Return structured results to the orchestrator." in role
