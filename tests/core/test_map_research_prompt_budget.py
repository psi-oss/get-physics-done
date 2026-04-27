"""Prompt budget assertions for the `map-research` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import count_unfenced_heading, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_map_research_command_prompt_budget_stays_close_to_the_workflow_surface() -> None:
    command_text = (COMMANDS_DIR / "map-research.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "map-research.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "map-research.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/map-research.md" in command_text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md" not in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 250
    assert metrics.expanded_char_count < workflow.expanded_char_count + 15000


def test_research_mapper_uses_one_canonical_mapping_complete_template() -> None:
    source = (AGENTS_DIR / "gpd-research-mapper.md").read_text(encoding="utf-8")

    assert source.count("## Mapping Complete") == 1
    assert count_unfenced_heading(source, "## Mapping Complete") == 0
    assert "Canonical format. Include optional blocks only when relevant:" in source
    assert "[Optional: quality warnings for documents below the minimum gate.]" in source
    assert "[Optional: staleness of other research-map docs.]" in source
    assert "report staleness in the canonical confirmation" in source
    assert "flag it in the canonical confirmation" in source
