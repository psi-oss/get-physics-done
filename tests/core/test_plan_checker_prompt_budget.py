"""Prompt budget regression tests for the `gpd-plan-checker` surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"
PLAN_CHECKER = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-plan-checker.md"


def test_plan_checker_prompt_stays_thin_while_preserving_direct_schema_visibility() -> None:
    metrics = measure_prompt_surface(
        PLAN_CHECKER,
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert metrics.expanded_char_count < 110_000
    assert metrics.expanded_line_count < 2_300
