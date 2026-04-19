"""Broad expanded prompt budget coverage for registered agents."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"

AGENT_BUDGETS = {
    "gpd-bibliographer": (500, 25_000),
    "gpd-check-proof": (500, 25_000),
    "gpd-consistency-checker": (500, 25_000),
    "gpd-debugger": (500, 30_000),
    "gpd-executor": (3_500, 230_000),
    "gpd-experiment-designer": (2_400, 130_000),
    "gpd-explainer": (1_900, 100_000),
    "gpd-literature-reviewer": (1_800, 90_000),
    "gpd-notation-coordinator": (2_100, 115_000),
    "gpd-paper-writer": (1_500, 75_000),
    "gpd-phase-researcher": (2_200, 110_000),
    "gpd-plan-checker": (2_100, 95_000),
    "gpd-planner": (6_000, 290_000),
    "gpd-project-researcher": (2_300, 120_000),
    "gpd-referee": (1_300, 70_000),
    "gpd-research-mapper": (3_100, 140_000),
    "gpd-research-synthesizer": (2_500, 125_000),
    "gpd-review-literature": (2_100, 120_000),
    "gpd-review-math": (2_100, 115_000),
    "gpd-review-physics": (2_100, 115_000),
    "gpd-review-reader": (500, 25_000),
    "gpd-review-significance": (2_100, 120_000),
    "gpd-roadmapper": (2_900, 130_000),
    "gpd-verifier": (6_500, 430_000),
}


def test_agent_prompt_budget_table_covers_registered_agents() -> None:
    assert set(AGENT_BUDGETS) == set(registry.list_agents())


@pytest.mark.parametrize("agent_name", sorted(AGENT_BUDGETS))
def test_expanded_agent_prompt_stays_under_budget(agent_name: str) -> None:
    max_lines, max_chars = AGENT_BUDGETS[agent_name]
    metrics = measure_prompt_surface(
        AGENTS_DIR / f"{agent_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.expanded_line_count <= max_lines
    assert metrics.expanded_char_count <= max_chars
