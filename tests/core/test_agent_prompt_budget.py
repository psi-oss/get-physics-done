"""Broad expanded prompt budget coverage for registered agents."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

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

PEER_REVIEW_SPECIALIST_AGENTS = (
    "gpd-review-literature",
    "gpd-review-math",
    "gpd-review-physics",
    "gpd-review-significance",
)


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


@pytest.mark.parametrize("agent_name", PEER_REVIEW_SPECIALIST_AGENTS)
def test_peer_review_specialists_reference_panel_contract_without_eager_inline(agent_name: str) -> None:
    path = AGENTS_DIR / f"{agent_name}.md"
    raw_text = path.read_text(encoding="utf-8")
    expanded_text = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    agent = registry.get_agent(agent_name)

    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" not in raw_text
    assert "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" in expanded_text
    assert "full `StageReviewReport` contract" in expanded_text
    assert "# Peer Review Panel Protocol" not in expanded_text
    assert "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" in agent.system_prompt
    assert "# Peer Review Panel Protocol" not in agent.system_prompt
