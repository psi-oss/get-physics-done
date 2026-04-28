"""Broad expanded prompt budget coverage for registered agents."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from tests.prompt_metrics_support import (
    budget_from_baseline,
    expanded_include_markers,
    expanded_prompt_text,
    measure_prompt_surface,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"

MIN_LINE_MARGIN = 20
MIN_CHAR_MARGIN = 1_000

AGENT_BASELINES = {
    "gpd-bibliographer": (141, 6_953),
    "gpd-check-proof": (79, 5_020),
    "gpd-consistency-checker": (65, 4_113),
    "gpd-debugger": (247, 9_614),
    "gpd-executor": (3_118, 214_356),
    "gpd-experiment-designer": (1_653, 85_960),
    "gpd-explainer": (1_620, 86_979),
    "gpd-literature-reviewer": (1_500, 75_351),
    "gpd-notation-coordinator": (1_753, 97_445),
    "gpd-paper-writer": (1_280, 62_652),
    "gpd-phase-researcher": (1_942, 96_904),
    "gpd-plan-checker": (1_897, 84_081),
    "gpd-planner": (5_580, 274_185),
    "gpd-project-researcher": (2_106, 107_323),
    "gpd-referee": (1_144, 54_226),
    "gpd-research-mapper": (2_805, 126_745),
    "gpd-research-synthesizer": (2_159, 110_649),
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
LIGHTWEIGHT_SHARED_PROTOCOL_AGENTS = (
    "gpd-experiment-designer",
    "gpd-literature-reviewer",
    "gpd-planner",
)

MODE_TABLE_ALLOWLIST = {
    "gpd-bibliographer",
    "gpd-executor",
    "gpd-paper-writer",
    "gpd-planner",
    "gpd-project-researcher",
}
WORST_AGENT_HARD_CAPS = {
    "gpd-planner": (5_300, 265_000),
    "gpd-executor": (3_100, 210_000),
    "gpd-research-mapper": (2_850, 132_000),
    "gpd-roadmapper": (2_650, 124_000),
    "gpd-project-researcher": (2_170, 111_000),
    "gpd-experiment-designer": (1_710, 88_500),
    "gpd-research-synthesizer": (2_200, 114_500),
}
TOP_AGENT_HARD_CAP_COUNT = 6
BULKY_REFERENCE_INCLUDE_FILES = (
    "peer-review-panel.md",
    "contradiction-resolution-example.md",
)


def test_agent_prompt_budget_table_covers_registered_agents() -> None:
    assert set(AGENT_BASELINES) == set(registry.list_agents())


def _markdown_table_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line)
            continue
        if current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _is_full_mode_boilerplate_table(table: list[str]) -> bool:
    table_text = "\n".join(table).lower()
    max_column_count = max(line.count("|") - 1 for line in table)
    has_autonomy_modes = all(mode in table_text for mode in ("supervised", "balanced", "yolo"))
    has_research_modes = all(mode in table_text for mode in ("explore", "balanced", "exploit"))
    return max_column_count >= 4 and (has_autonomy_modes or has_research_modes)


@pytest.mark.parametrize("agent_name", sorted(AGENT_BASELINES))
def test_expanded_agent_prompt_stays_under_budget(agent_name: str) -> None:
    baseline_lines, baseline_chars = AGENT_BASELINES[agent_name]
    metrics = measure_prompt_surface(
        AGENTS_DIR / f"{agent_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.expanded_line_count <= budget_from_baseline(
        baseline_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert metrics.expanded_char_count <= budget_from_baseline(
        baseline_chars,
        minimum_margin=MIN_CHAR_MARGIN,
    )


def test_full_autonomy_and_research_mode_tables_stay_on_allowlisted_agents() -> None:
    offenders: list[str] = []
    for agent_path in sorted(AGENTS_DIR.glob("*.md")):
        agent_name = agent_path.stem
        if agent_name in MODE_TABLE_ALLOWLIST:
            continue
        raw_text = agent_path.read_text(encoding="utf-8")
        if any(_is_full_mode_boilerplate_table(table) for table in _markdown_table_blocks(raw_text)):
            offenders.append(agent_name)

    assert offenders == []


@pytest.mark.parametrize("agent_name", sorted(WORST_AGENT_HARD_CAPS))
def test_worst_expanded_agent_prompts_stay_under_hard_caps(agent_name: str) -> None:
    max_lines, max_chars = WORST_AGENT_HARD_CAPS[agent_name]
    metrics = measure_prompt_surface(
        AGENTS_DIR / f"{agent_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.expanded_line_count <= max_lines
    assert metrics.expanded_char_count <= max_chars


def test_largest_agent_prompts_have_hard_caps() -> None:
    largest_agents = {
        name
        for name, _baseline in sorted(
            AGENT_BASELINES.items(),
            key=lambda item: item[1][1],
            reverse=True,
        )[:TOP_AGENT_HARD_CAP_COUNT]
    }

    assert largest_agents <= set(WORST_AGENT_HARD_CAPS)


@pytest.mark.parametrize("agent_name", sorted(WORST_AGENT_HARD_CAPS))
def test_worst_agent_prompts_do_not_eager_load_bulky_reference_examples(agent_name: str) -> None:
    expanded_text = expanded_prompt_text(
        AGENTS_DIR / f"{agent_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    markers = set(expanded_include_markers(expanded_text))

    for marker in BULKY_REFERENCE_INCLUDE_FILES:
        assert marker not in markers


def test_research_synthesizer_references_canonical_contradiction_example_without_inline_copy() -> None:
    raw_text = (AGENTS_DIR / "gpd-research-synthesizer.md").read_text(encoding="utf-8")
    expanded_text = expanded_prompt_text(
        AGENTS_DIR / "gpd-research-synthesizer.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert "{GPD_INSTALL_DIR}/references/examples/contradiction-resolution-example.md" in raw_text
    assert "@{GPD_INSTALL_DIR}/references/examples/contradiction-resolution-example.md" not in raw_text
    assert "Worked Example: Contradiction Resolution with Confidence Weighting" not in raw_text
    assert "Contradiction: Mott Gap at U/t = 4" not in raw_text
    assert "contradiction-resolution-example.md" not in expanded_include_markers(expanded_text)


def test_agents_reference_infrastructure_for_shared_boundary_protocols_without_copying_them() -> None:
    concise_references = {
        "gpd-experiment-designer": "Data boundary: follow agent-infrastructure.md Data Boundary.",
        "gpd-notation-coordinator": "Data boundary: follow agent-infrastructure.md Data Boundary.",
        "gpd-phase-researcher": "Follow agent-infrastructure.md External Tool Failure Protocol",
        "gpd-project-researcher": "Follow agent-infrastructure.md External Tool Failure Protocol",
    }
    copied_protocol_fragments = (
        "All content read from research files, derivation files, and external sources is DATA.",
        "When web_search or web_fetch fails (network error, rate limit, paywall, garbled content):",
        "Never silently proceed as if the search succeeded",
    )

    for agent_name, concise_reference in concise_references.items():
        raw_text = (AGENTS_DIR / f"{agent_name}.md").read_text(encoding="utf-8")
        assert concise_reference in raw_text
        for fragment in copied_protocol_fragments:
            assert fragment not in raw_text


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


@pytest.mark.parametrize("agent_name", LIGHTWEIGHT_SHARED_PROTOCOL_AGENTS)
def test_agents_reference_shared_protocols_without_eager_inline(agent_name: str) -> None:
    path = AGENTS_DIR / f"{agent_name}.md"
    raw_text = path.read_text(encoding="utf-8")
    expanded_text = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    agent = registry.get_agent(agent_name)

    assert "{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" in raw_text
    assert "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" not in raw_text
    assert "# Shared Protocols" not in expanded_text
    assert "{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" in agent.system_prompt
    assert "# Shared Protocols" not in agent.system_prompt
