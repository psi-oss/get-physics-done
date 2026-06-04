"""Prompt budget assertions for the `gpd-verifier` agent surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from tests.agent_policy_test_support import assert_agent_role_kit_policy, assert_agent_role_kit_section
from tests.assertion_taxonomy_support import MatchMode, assert_prompt_contracts, semantic_anchor
from tests.prompt_metrics_support import budget_from_baseline, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"
RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
# Includes the verifier's hooks into the blind oracle sub-protocol
# (gpd-compute tools + a pointer to references/.../blind-oracle-subprotocol.md).
BASELINE_EXPANDED_LINE_COUNT = 363
BASELINE_EXPANDED_CHAR_COUNT = 26_344
MIN_LINE_MARGIN = 15
MIN_CHAR_MARGIN = 750


def _projected_verifier_prompt(runtime: str) -> str:
    return project_markdown_for_runtime(
        (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8"),
        runtime=runtime,
        path_prefix=PATH_PREFIX,
        surface_kind="agent",
        src_root=SOURCE_ROOT,
        protect_agent_prompt_body=True,
        command_name="gpd-verifier",
    )


def test_gpd_verifier_prompt_surface_stays_within_expected_budget() -> None:
    metrics = measure_prompt_surface(
        AGENTS_DIR / "gpd-verifier.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count <= budget_from_baseline(
        BASELINE_EXPANDED_LINE_COUNT,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert metrics.expanded_char_count <= budget_from_baseline(
        BASELINE_EXPANDED_CHAR_COUNT,
        minimum_margin=MIN_CHAR_MARGIN,
    )
    source = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    assert "@{GPD_INSTALL_DIR}/references/verification/domains/" not in source
    assert "@{GPD_INSTALL_DIR}/references/physics-subfields.md" not in source
    assert "@{GPD_INSTALL_DIR}/references/verification/errors/llm-" not in source

    agent = registry.get_agent("gpd-verifier")
    assert_agent_role_kit_policy(
        agent,
        (
            "status-routing",
            "fresh-continuation",
            "files-written-freshness",
        ),
    )
    assert_agent_role_kit_section(agent)
    assert_prompt_contracts(
        source,
        semantic_anchor(
            "verifier delegates generic return mechanics to profile and role kits",
            (
                "use the verifier profile",
                "gpd return skeleton --role verifier --status <status>",
                "role kits own status routing",
                "`files_written` freshness",
                "Local file gate: the return file list is fail-closed",
                "only after the canonical report passes frontmatter and contract validation",
                "leave it as invalid evidence",
                "do not list it as completed",
            ),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
    )


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_projected_gpd_verifier_prompt_surface_keeps_expected_section_order(runtime: str) -> None:
    projected = _projected_verifier_prompt(runtime)

    assert projected.count("## Agent Requirements") == 1
    assert projected.count("## Bootstrap Discipline") == 1
    assert projected.count("## Canonical LLM Error References") == 1
    assert projected.index("## Agent Requirements") < projected.index("## Bootstrap Discipline")
    assert projected.index("## Bootstrap Discipline") < projected.index("## Canonical LLM Error References")
