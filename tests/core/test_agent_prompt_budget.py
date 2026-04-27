"""Broad expanded prompt budget coverage for registered agents."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import pytest

from gpd import registry
from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"

PROMPT_BUDGET_MARGIN = 0.03
MIN_LINE_MARGIN = 20
MIN_CHAR_MARGIN = 1_000

AGENT_BASELINES = {
    "gpd-bibliographer": (141, 6_953),
    "gpd-check-proof": (79, 5_020),
    "gpd-consistency-checker": (65, 4_113),
    "gpd-debugger": (247, 9_614),
    "gpd-executor": (3_128, 214_439),
    "gpd-experiment-designer": (2_125, 117_917),
    "gpd-explainer": (1_620, 86_979),
    "gpd-literature-reviewer": (1_500, 75_351),
    "gpd-notation-coordinator": (1_850, 101_891),
    "gpd-paper-writer": (1_280, 62_652),
    "gpd-phase-researcher": (1_952, 97_229),
    "gpd-plan-checker": (1_897, 84_081),
    "gpd-planner": (5_773, 281_554),
    "gpd-project-researcher": (2_116, 107_648),
    "gpd-referee": (1_144, 54_226),
    "gpd-research-mapper": (2_805, 126_745),
    "gpd-research-synthesizer": (2_240, 114_845),
    "gpd-review-literature": (54, 2_707),
    "gpd-review-math": (55, 3_459),
    "gpd-review-physics": (54, 2_720),
    "gpd-review-reader": (53, 3_274),
    "gpd-review-significance": (55, 2_906),
    "gpd-roadmapper": (2_592, 119_760),
    "gpd-verifier": (1_451, 79_380),
}

PEER_REVIEW_SPECIALIST_AGENTS = (
    "gpd-review-literature",
    "gpd-review-math",
    "gpd-review-physics",
    "gpd-review-significance",
)


def test_agent_prompt_budget_table_covers_registered_agents() -> None:
    assert set(AGENT_BASELINES) == set(registry.list_agents())


def _budget_from_baseline(value: int, *, minimum_margin: int) -> int:
    return value + max(minimum_margin, ceil(value * PROMPT_BUDGET_MARGIN))


@pytest.mark.parametrize("agent_name", sorted(AGENT_BASELINES))
def test_expanded_agent_prompt_stays_under_budget(agent_name: str) -> None:
    baseline_lines, baseline_chars = AGENT_BASELINES[agent_name]
    metrics = measure_prompt_surface(
        AGENTS_DIR / f"{agent_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.expanded_line_count <= _budget_from_baseline(
        baseline_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert metrics.expanded_char_count <= _budget_from_baseline(
        baseline_chars,
        minimum_margin=MIN_CHAR_MARGIN,
    )


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
