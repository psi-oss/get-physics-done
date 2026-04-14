"""Prompt budget regression tests for the `gpd-plan-checker` surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"
PLAN_CHECKER = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-plan-checker.md"
EXPECTED_RAW_INCLUDE_COUNT = 3
MAX_EXPANDED_CHAR_COUNT = 115_000
MAX_EXPANDED_LINE_COUNT = 2_500


def test_plan_checker_prompt_stays_thin_while_preserving_direct_schema_visibility() -> None:
    metrics = measure_prompt_surface(
        PLAN_CHECKER,
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == EXPECTED_RAW_INCLUDE_COUNT, metrics
    assert metrics.expanded_char_count < MAX_EXPANDED_CHAR_COUNT, metrics
    assert metrics.expanded_line_count < MAX_EXPANDED_LINE_COUNT, metrics
