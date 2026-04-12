"""Prompt budget sanity checks for the `gpd-phase-researcher` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_phase_researcher_prompt_stays_within_budget_and_keeps_instructions_visible() -> None:
    path = AGENTS_DIR / "gpd-phase-researcher.md"
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    expanded = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert metrics.expanded_line_count < 2_200
    assert metrics.expanded_char_count < 110_000
    assert "## Step 1: Gather context" in expanded
    assert "## Step 5: Draft `RESEARCH.md`" in expanded
    assert "gpd_return.status: checkpoint" in expanded
    assert "## RESEARCH COMPLETE" in expanded
