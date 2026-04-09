"""Prompt budget regressions for the `gpd-research-synthesizer` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_research_synthesizer_prompt_stays_within_expected_budget_and_keeps_one_shot_return_language() -> None:
    path = AGENTS_DIR / "gpd-research-synthesizer.md"
    source = path.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert metrics.raw_include_count == 1
    assert metrics.expanded_line_count < 2_500
    assert metrics.expanded_char_count < 125_000

    assert "If you checkpoint, write one draft `SUMMARY.md`, return `checkpoint`, and stop; do not continue to a final pass in the same run." in source
    assert "If a checkpoint is required, stop after the draft `SUMMARY.md` and return `checkpoint`." in source
    assert "keep the return path one-shot" in source
    assert "Append this YAML block after the markdown return." in source
    assert "Use only status names: `completed` | `checkpoint` | `blocked` | `failed`." in source
    assert "This agent writes only `GPD/literature/SUMMARY.md`;" in source
    assert "files_written` must list only files actually written in this run." in source
    assert "If you checkpoint, write a single draft `SUMMARY.md` first, then stop." in source
    assert "Target under 3000 words for `SUMMARY.md`." in source
