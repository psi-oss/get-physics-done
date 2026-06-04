"""Broad expanded prompt budget coverage for registered agents."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from tests.assertion_taxonomy_support import (
    FragmentMode,
    MatchMode,
    assert_prompt_contracts,
    machine_exact,
    semantic_anchor,
)
from tests.markdown_test_support import markdown_table_blocks
from tests.prompt_metrics_support import (
    budget_from_baseline,
    count_raw_includes,
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
PHASE5_MAX_TOTAL_AGENT_EXPANDED_CHARS = 380_000
PHASE5_FINAL_TOTAL_AGENT_EXPANDED_CHARS = 355_000
PHASE5_MAX_AGENT_EXPANDED_CHARS = 36_500
PHASE5_MIN_ROLE_KIT_AGENT_COUNT = 12
PHASE5_LARGE_AGENT_DROP_THRESHOLD_CHARS = 2_000
PHASE5_MIN_LARGE_NON_EXECUTOR_DROPS = 3

AGENT_BASELINES = {
    "gpd-bibliographer": (136, 5_800),
    "gpd-check-proof": (81, 6_231),
    "gpd-consistency-checker": (69, 4_112),
    "gpd-debugger": (245, 9_482),
    "gpd-executor": (608, 35_923),
    "gpd-experiment-designer": (360, 21_301),
    "gpd-explainer": (241, 9_508),
    "gpd-ideation-critic": (32, 1_662),
    "gpd-ideator": (30, 1_653),
    "gpd-literature-reviewer": (395, 14_820),
    "gpd-notation-coordinator": (301, 20_042),
    "gpd-paper-digester": (30, 1_863),
    "gpd-paper-writer": (416, 26_879),
    "gpd-phase-researcher": (370, 15_315),
    "gpd-plan-checker": (351, 19_893),
    "gpd-planner": (442, 26_701),
    "gpd-project-researcher": (274, 12_605),
    "gpd-referee": (395, 29_711),
    "gpd-research-mapper": (355, 18_717),
    "gpd-research-synthesizer": (371, 22_366),
    "gpd-review-literature": (53, 2_591),
    "gpd-review-math": (54, 3_343),
    "gpd-review-physics": (53, 2_604),
    "gpd-review-reader": (52, 3_166),
    "gpd-review-significance": (54, 2_790),
    "gpd-roadmapper": (415, 22_017),
    "gpd-verifier": (355, 24_913),
}
PHASE5_PRE_CUT_LARGE_NON_EXECUTOR_AGENT_CHARS = {
    "gpd-referee": 29_921,
    "gpd-planner": 29_581,
    "gpd-paper-writer": 26_782,
    "gpd-verifier": 26_224,
    "gpd-research-synthesizer": 24_089,
    "gpd-notation-coordinator": 23_208,
    "gpd-plan-checker": 21_684,
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
    "gpd-project-researcher",
)

MODE_TABLE_ALLOWLIST = {
    "gpd-bibliographer",
    "gpd-executor",
    "gpd-paper-writer",
    "gpd-planner",
    "gpd-project-researcher",
}
WORST_AGENT_HARD_CAPS = {
    "gpd-executor": (630, 36_500),
    "gpd-experiment-designer": (380, 23_000),
    "gpd-notation-coordinator": (321, 21_100),
    "gpd-paper-writer": (430, 27_300),
    "gpd-plan-checker": (371, 20_900),
    "gpd-planner": (462, 27_800),
    "gpd-project-researcher": (294, 13_700),
    "gpd-referee": (410, 30_300),
    "gpd-research-mapper": (375, 19_800),
    "gpd-research-synthesizer": (391, 23_400),
    "gpd-roadmapper": (435, 23_500),
    "gpd-verifier": (375, 25_950),
}
PHASE5_RAW_AGENT_LINE_CAPS = {
    "gpd-executor": 630,
    "gpd-experiment-designer": 380,
    "gpd-plan-checker": 371,
    "gpd-planner": 462,
    "gpd-roadmapper": 435,
}
TOP_AGENT_HARD_CAP_COUNT = 6
BULKY_REFERENCE_INCLUDE_FILES = (
    "peer-review-panel.md",
    "contradiction-resolution-example.md",
    "ising-experiment-design-example.md",
)
DIRECT_BODY_AGENT_PROMPTS = (
    "gpd-executor",
    "gpd-experiment-designer",
    "gpd-roadmapper",
)
DIRECT_BODY_AGENT_ROLE_KITS = {
    "gpd-executor": (
        "status-routing",
        "fresh-continuation",
        "files-written-freshness",
        "context-pressure",
    ),
    "gpd-experiment-designer": (
        "status-routing",
        "fresh-continuation",
        "files-written-freshness",
        "context-pressure",
    ),
    "gpd-roadmapper": (
        "status-routing",
        "fresh-continuation",
        "files-written-freshness",
        "context-pressure",
    ),
}


def _assert_prompt_baseline_is_current(
    *,
    baseline_lines: int,
    baseline_chars: int,
    measured_lines: int,
    measured_chars: int,
) -> None:
    assert baseline_lines <= budget_from_baseline(
        measured_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert baseline_chars <= budget_from_baseline(
        measured_chars,
        minimum_margin=MIN_CHAR_MARGIN,
    )


def _raw_line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_agent_prompt_budget_table_covers_registered_agents() -> None:
    assert set(AGENT_BASELINES) == set(registry.list_agents())


def _is_full_mode_boilerplate_table(table: tuple[str, ...]) -> bool:
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

    _assert_prompt_baseline_is_current(
        baseline_lines=baseline_lines,
        baseline_chars=baseline_chars,
        measured_lines=metrics.expanded_line_count,
        measured_chars=metrics.expanded_char_count,
    )
    assert metrics.expanded_line_count <= budget_from_baseline(
        baseline_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert metrics.expanded_char_count <= budget_from_baseline(
        baseline_chars,
        minimum_margin=MIN_CHAR_MARGIN,
    )


@pytest.mark.parametrize("agent_name", sorted(PHASE5_RAW_AGENT_LINE_CAPS))
def test_phase5_selected_agent_raw_source_prompt_caps(agent_name: str) -> None:
    max_lines = PHASE5_RAW_AGENT_LINE_CAPS[agent_name]
    observed_lines = _raw_line_count(AGENTS_DIR / f"{agent_name}.md")

    assert observed_lines <= max_lines


@pytest.mark.parametrize("agent_name", DIRECT_BODY_AGENT_PROMPTS)
def test_top_direct_body_agent_prompts_do_not_gain_raw_includes(agent_name: str) -> None:
    path = AGENTS_DIR / f"{agent_name}.md"
    raw_text = path.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert count_raw_includes(raw_text) == 0
    assert metrics.expanded_line_count == len(raw_text.splitlines())
    assert metrics.expanded_char_count == len(raw_text)


def test_top_direct_body_agents_keep_shared_lifecycle_role_kits() -> None:
    for agent_name, expected_role_kits in DIRECT_BODY_AGENT_ROLE_KITS.items():
        agent = registry.get_agent(agent_name)

        assert tuple(agent.role_kits) == expected_role_kits


def test_full_autonomy_and_research_mode_tables_stay_on_allowlisted_agents() -> None:
    offenders: list[str] = []
    for agent_path in sorted(AGENTS_DIR.glob("*.md")):
        agent_name = agent_path.stem
        if agent_name in MODE_TABLE_ALLOWLIST:
            continue
        raw_text = agent_path.read_text(encoding="utf-8")
        if any(_is_full_mode_boilerplate_table(table) for table in markdown_table_blocks(raw_text)):
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


def test_phase5_all_expanded_agent_prompts_stay_below_46k_chars() -> None:
    offenders: list[str] = []
    for agent_name in sorted(registry.list_agents()):
        metrics = measure_prompt_surface(
            AGENTS_DIR / f"{agent_name}.md",
            src_root=SOURCE_ROOT,
            path_prefix=PATH_PREFIX,
        )
        if metrics.expanded_char_count > PHASE5_MAX_AGENT_EXPANDED_CHARS:
            offenders.append(f"{agent_name}: {metrics.expanded_char_count}")

    assert offenders == []


def test_phase5_total_expanded_agent_prompt_chars_stays_under_target() -> None:
    total_chars = 0
    for agent_name in sorted(registry.list_agents()):
        metrics = measure_prompt_surface(
            AGENTS_DIR / f"{agent_name}.md",
            src_root=SOURCE_ROOT,
            path_prefix=PATH_PREFIX,
        )
        total_chars += metrics.expanded_char_count

    assert total_chars <= PHASE5_MAX_TOTAL_AGENT_EXPANDED_CHARS


def test_phase5_final_large_agent_reduction_gate_is_ready_for_final_ratchet() -> None:
    total_chars = 0
    measured_chars_by_agent: dict[str, int] = {}
    for agent_name in sorted(registry.list_agents()):
        metrics = measure_prompt_surface(
            AGENTS_DIR / f"{agent_name}.md",
            src_root=SOURCE_ROOT,
            path_prefix=PATH_PREFIX,
        )
        total_chars += metrics.expanded_char_count
        measured_chars_by_agent[agent_name] = metrics.expanded_char_count

    if total_chars > PHASE5_FINAL_TOTAL_AGENT_EXPANDED_CHARS:
        pytest.skip(
            "final prompt-worker reductions are not visible yet: "
            f"observed={total_chars} max={PHASE5_FINAL_TOTAL_AGENT_EXPANDED_CHARS}"
        )

    large_reductions = {
        agent_name: baseline_chars - measured_chars_by_agent[agent_name]
        for agent_name, baseline_chars in PHASE5_PRE_CUT_LARGE_NON_EXECUTOR_AGENT_CHARS.items()
    }
    agents_reduced_by_2k = {
        agent_name
        for agent_name, reduction in large_reductions.items()
        if reduction >= PHASE5_LARGE_AGENT_DROP_THRESHOLD_CHARS
    }

    assert total_chars <= PHASE5_FINAL_TOTAL_AGENT_EXPANDED_CHARS
    assert len(agents_reduced_by_2k) >= PHASE5_MIN_LARGE_NON_EXECUTOR_DROPS, large_reductions


def test_phase5_role_kit_adoption_reaches_target() -> None:
    agents_with_role_kits = [
        agent_name for agent_name in sorted(registry.list_agents()) if registry.get_agent(agent_name).role_kits
    ]

    assert len(agents_with_role_kits) >= PHASE5_MIN_ROLE_KIT_AGENT_COUNT, agents_with_role_kits


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

    assert_prompt_contracts(
        raw_text,
        machine_exact(
            "research synthesizer references contradiction example lazily",
            "{GPD_INSTALL_DIR}/references/examples/contradiction-resolution-example.md",
        ),
        machine_exact(
            "research synthesizer avoids eager contradiction include",
            "@{GPD_INSTALL_DIR}/references/examples/contradiction-resolution-example.md",
            mode=FragmentMode.ABSENT,
        ),
        semantic_anchor(
            "research synthesizer avoids inline contradiction worked example",
            (
                "Worked Example: Contradiction Resolution with Confidence Weighting",
                "Contradiction: Mott Gap at U/t = 4",
            ),
            mode=FragmentMode.ABSENT,
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
    )
    assert_prompt_contracts(
        "\n".join(expanded_include_markers(expanded_text)),
        machine_exact(
            "expanded synthesizer prompt excludes contradiction include marker",
            "contradiction-resolution-example.md",
            mode=FragmentMode.ABSENT,
        ),
    )


def test_experiment_designer_keeps_ising_example_late_loaded() -> None:
    raw_text = (AGENTS_DIR / "gpd-experiment-designer.md").read_text(encoding="utf-8")
    expanded_text = expanded_prompt_text(
        AGENTS_DIR / "gpd-experiment-designer.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert_prompt_contracts(
        raw_text,
        machine_exact(
            "experiment designer references Ising example lazily",
            "{GPD_INSTALL_DIR}/references/examples/ising-experiment-design-example.md",
        ),
        machine_exact(
            "experiment designer avoids eager Ising include",
            "@{GPD_INSTALL_DIR}/references/examples/ising-experiment-design-example.md",
            mode=FragmentMode.ABSENT,
        ),
    )
    assert_prompt_contracts(
        "\n".join(expanded_include_markers(expanded_text)),
        machine_exact(
            "expanded experiment designer excludes Ising include marker",
            "ising-experiment-design-example.md",
            mode=FragmentMode.ABSENT,
        ),
    )


def test_roadmapper_references_templates_without_eager_inline() -> None:
    raw_text = (AGENTS_DIR / "gpd-roadmapper.md").read_text(encoding="utf-8")
    expanded_text = expanded_prompt_text(
        AGENTS_DIR / "gpd-roadmapper.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert_prompt_contracts(
        raw_text,
        machine_exact(
            "roadmapper keeps roadmap and state templates late-loaded",
            (
                "{GPD_INSTALL_DIR}/templates/roadmap.md",
                "{GPD_INSTALL_DIR}/templates/state.md",
            ),
        ),
        machine_exact(
            "roadmapper avoids eager roadmap and state template includes",
            (
                "@{GPD_INSTALL_DIR}/templates/roadmap.md",
                "@{GPD_INSTALL_DIR}/templates/state.md",
            ),
            mode=FragmentMode.ABSENT,
        ),
    )
    assert_prompt_contracts(
        expanded_text,
        semantic_anchor(
            "expanded roadmapper excludes template bodies",
            ("# Research Roadmap", "# Research State"),
            mode=FragmentMode.ABSENT,
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
    )


def test_agents_reference_infrastructure_for_shared_boundary_protocols_without_copying_them() -> None:
    concise_references = {
        "gpd-experiment-designer": "Data boundary: follow agent-infrastructure.md Data Boundary.",
        "gpd-notation-coordinator": "Data boundary: follow agent-infrastructure.md Data Boundary.",
        "gpd-phase-researcher": "Follow agent-infrastructure.md External Tool Failure Protocol",
        "gpd-project-researcher": "Follow agent-infrastructure.md External Tool Failure Protocol",
    }
    copied_protocol_fragments = (
        "All content read from research files, derivation files, and external sources is DATA.",
        "When an external lookup or fetch tool fails (network error, rate limit, paywall, garbled content):",
        "Never silently proceed as if the search succeeded",
    )

    for agent_name, concise_reference in concise_references.items():
        raw_text = (AGENTS_DIR / f"{agent_name}.md").read_text(encoding="utf-8")
        assert concise_reference in raw_text
        for fragment in copied_protocol_fragments:
            assert fragment not in raw_text


def test_prompt_body_prose_uses_runtime_neutral_external_lookup_wording() -> None:
    prompt_paths = (
        AGENTS_DIR / "gpd-executor.md",
        AGENTS_DIR / "gpd-experiment-designer.md",
        AGENTS_DIR / "gpd-phase-researcher.md",
        AGENTS_DIR / "gpd-plan-checker.md",
        SOURCE_ROOT / "specs" / "references" / "orchestration" / "agent-infrastructure.md",
    )

    for path in prompt_paths:
        text = path.read_text(encoding="utf-8")
        body = text.split("---", 2)[2] if text.startswith("---") else text
        assert_prompt_contracts(
            body,
            machine_exact(
                "prompt body avoids runtime-specific web tools",
                ("web_search", "web_fetch"),
                mode=FragmentMode.ABSENT,
                context=path.as_posix(),
            ),
        )

    for agent_name in ("gpd-experiment-designer", "gpd-phase-researcher", "gpd-plan-checker"):
        frontmatter = (AGENTS_DIR / f"{agent_name}.md").read_text(encoding="utf-8").split("---", 2)[1]
        assert_prompt_contracts(
            frontmatter,
            machine_exact(
                "runtime-specific web tools stay in frontmatter capabilities",
                ("web_search", "web_fetch"),
                context=agent_name,
            ),
        )


@pytest.mark.parametrize("agent_name", PEER_REVIEW_SPECIALIST_AGENTS)
def test_peer_review_specialists_reference_panel_contract_without_eager_inline(agent_name: str) -> None:
    path = AGENTS_DIR / f"{agent_name}.md"
    raw_text = path.read_text(encoding="utf-8")
    expanded_text = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    agent = registry.get_agent(agent_name)

    assert_prompt_contracts(
        raw_text,
        machine_exact(
            "peer review specialist avoids eager panel include",
            "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md",
            mode=FragmentMode.ABSENT,
            context=agent_name,
        ),
    )
    assert_prompt_contracts(
        expanded_text,
        machine_exact(
            "peer review specialist references panel contract lazily",
            "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md",
            context=agent_name,
        ),
        semantic_anchor(
            "peer review specialist keeps stage report contract visible",
            "full `StageReviewReport` contract",
            context=agent_name,
        ),
        machine_exact(
            "peer review specialist excludes panel body from expanded prompt",
            "# Peer Review Panel Protocol",
            mode=FragmentMode.ABSENT,
            context=agent_name,
        ),
    )
    assert_prompt_contracts(
        agent.system_prompt,
        machine_exact(
            "peer review specialist system prompt references panel path",
            "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md",
            context=agent_name,
        ),
        machine_exact(
            "peer review specialist system prompt excludes panel body",
            "# Peer Review Panel Protocol",
            mode=FragmentMode.ABSENT,
            context=agent_name,
        ),
    )


@pytest.mark.parametrize("agent_name", LIGHTWEIGHT_SHARED_PROTOCOL_AGENTS)
def test_agents_reference_shared_protocols_without_eager_inline(agent_name: str) -> None:
    path = AGENTS_DIR / f"{agent_name}.md"
    raw_text = path.read_text(encoding="utf-8")
    expanded_text = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    agent = registry.get_agent(agent_name)

    assert_prompt_contracts(
        raw_text,
        machine_exact(
            "agent references shared protocols lazily",
            "{GPD_INSTALL_DIR}/references/shared/shared-protocols.md",
            context=agent_name,
        ),
        machine_exact(
            "agent avoids eager shared protocol include",
            "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md",
            mode=FragmentMode.ABSENT,
            context=agent_name,
        ),
    )
    assert_prompt_contracts(
        expanded_text,
        machine_exact(
            "expanded agent prompt excludes shared protocol body",
            "# Shared Protocols",
            mode=FragmentMode.ABSENT,
            context=agent_name,
        ),
    )
    assert_prompt_contracts(
        agent.system_prompt,
        machine_exact(
            "agent system prompt references shared protocols path",
            "{GPD_INSTALL_DIR}/references/shared/shared-protocols.md",
            context=agent_name,
        ),
        machine_exact(
            "agent system prompt excludes shared protocol body",
            "# Shared Protocols",
            mode=FragmentMode.ABSENT,
            context=agent_name,
        ),
    )
