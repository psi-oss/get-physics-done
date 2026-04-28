"""Prompt budget assertions for the `gpd-plan-checker` surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"
PLAN_CHECKER = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-plan-checker.md"


def _read_plan_checker() -> str:
    return PLAN_CHECKER.read_text(encoding="utf-8")


def test_plan_checker_prompt_stays_thin_while_preserving_direct_schema_visibility() -> None:
    metrics = measure_prompt_surface(
        PLAN_CHECKER,
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 0
    assert metrics.expanded_char_count < 110_000
    assert metrics.expanded_line_count < 2_300


def test_plan_checker_collapses_duplicate_dimension_steps_but_keeps_all_dimensions() -> None:
    source = _read_plan_checker()

    for dimension in range(17):
        assert f"## Dimension {dimension}:" in source

    assert "## Step 4: Run Verification Dimensions" in source
    assert "Do not repeat their checklists here" in source
    assert "Dimensions 0-16 evaluated using the dimension sections and Step 4 matrix" in source

    for removed_step in (
        "## Step 4: Check Research Question Coverage",
        "## Step 5: Validate Task Structure",
        "## Step 6: Check Mathematical Prerequisites",
        "## Step 7: Verify Approximation Validity",
        "## Step 8: Assess Computational Feasibility",
        "## Step 9: Verify Validation Strategy",
        "## Step 10: Check Result Wiring",
        "## Step 11: Verify Dependency Graph",
        "## Step 12: Assess Scope",
        "## Step 13: Verify Contract Coverage And Artifact Derivation",
        "## Step 14: Check Literature Awareness",
        "## Step 15: Assess Path to Publication",
        "## Step 16: Identify Failure Modes",
        "## Step 16.5: Validate Computational Environment",
    ):
        assert removed_step not in source

    assert (
        source.count(
            "When a phase has multiple plans, some may pass while others have blockers. Rather than blocking the entire phase, use partial approval to let passing plans proceed."
        )
        == 1
    )
