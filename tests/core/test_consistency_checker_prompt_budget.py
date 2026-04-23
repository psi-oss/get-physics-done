"""Prompt budget assertions for the `gpd-consistency-checker` surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-consistency-checker.md"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_consistency_checker_prompt_stays_small_and_keeps_its_canonical_contract() -> None:
    source = AGENT_PATH.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        AGENT_PATH,
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 100
    assert metrics.expanded_char_count < 6_000
    assert "one-shot handoff" in source
    assert "status: completed | checkpoint | blocked | failed" in source
    assert "files_written: [GPD/phases/{scope}/CONSISTENCY-CHECK.md]" in source
    assert "GPD/CONSISTENCY-CHECK.md" in source
    assert "Do not claim ownership of code fixes, commits, convention-authoring, or pattern-library updates." in source
    assert "@{GPD_INSTALL_DIR}" not in source
    assert "Create it from the template" not in source
    assert "gpd pattern add" not in source
    assert "Step 0.5" not in source
    assert "CONVENTIONS.md does not exist" not in source
