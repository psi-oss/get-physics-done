"""Prompt-budget assertions for `gpd-planner` bootstrap loading."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNER_PATH = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-planner.md"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def _read_planner_prompt() -> str:
    return PLANNER_PATH.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    _, start_marker, tail = text.partition(start)
    assert start_marker, f"Missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"Missing marker: {end}"
    return body


def test_planner_bootstrap_does_not_eagerly_load_execution_or_completion_only_materials() -> None:
    planner = _read_planner_prompt()
    role = _between(planner, "<role>", "</role>")

    assert "@{GPD_INSTALL_DIR}/templates/phase-prompt.md" in role
    assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in role
    assert "@{GPD_INSTALL_DIR}/workflows/execute-plan.md" not in role
    assert "@{GPD_INSTALL_DIR}/templates/summary.md" not in role
    assert "@{GPD_INSTALL_DIR}/references/protocols/order-of-limits.md" not in role
    assert role.index("@{GPD_INSTALL_DIR}/templates/phase-prompt.md") < role.index(
        "before any `PLAN.md` emission."
    )
    assert role.index("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") < role.index(
        "before any `PLAN.md` emission."
    )


def test_expanded_planner_prompt_stays_under_budget() -> None:
    metrics = measure_prompt_surface(
        PLANNER_PATH,
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count <= 9
    assert metrics.expanded_char_count < 290_000
    assert metrics.expanded_line_count < 6_000


def test_planner_prompt_no_longer_carries_the_removed_high_level_boilerplate() -> None:
    planner = _read_planner_prompt()

    for removed_marker in (
        "Quality Degradation Curve",
        "Research Fast",
        "Specificity Examples",
    ):
        assert removed_marker not in planner
