"""Prompt budget assertions for the `gpd-literature-reviewer` agent surface."""

from __future__ import annotations

from pathlib import Path

from gpd import registry
from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_literature_reviewer_prompt_stays_within_expected_budget_and_keeps_the_contract_shell_tight() -> None:
    path = AGENTS_DIR / "gpd-literature-reviewer.md"
    source = path.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    expanded = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 2_100
    assert metrics.expanded_char_count < 100_000

    assert "Authority: use the frontmatter-derived Agent Requirements block" not in source
    assert registry.get_agent("gpd-literature-reviewer").system_prompt.count("## Agent Requirements") == 1
    assert "This is a one-shot checkpoint handoff." in source
    assert "gpd_return.status: checkpoint" in source
    assert "GPD/literature/{slug}-REVIEW.md" in source
    assert "GPD/literature/{slug}-CITATION-SOURCES.json" in source
    assert "`{GPD_INSTALL_DIR}/references/shared/shared-protocols.md`" in source
    assert "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" not in source
    assert "anchor_id" in source
    assert "locator" in source
    assert "fresh continuation run" in source
    assert "do not wait in-run for user approval" in source

    for heading in (
        "Paper Assessment Rubric",
        "Field Assessment Framework",
        "Multi-Session Continuation",
        "Context Budget Depth",
        "Realistic Paper Counts",
        "Incremental Review",
        "Paywall Handling",
        "Preprint Revision Retraction",
    ):
        assert f"## {heading}" not in expanded
