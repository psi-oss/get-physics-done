"""Prompt budget regressions for the `gpd-referee` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_referee_prompt_stays_within_expected_budget() -> None:
    metrics = measure_prompt_surface(
        AGENTS_DIR / "gpd-referee.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 6_000
    assert metrics.expanded_char_count < 300_000


def test_gpd_referee_prompt_keeps_publication_path_mentions_without_eager_schema_expansion() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    expanded = expanded_prompt_text(
        AGENTS_DIR / "gpd-referee.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert "references/publication/peer-review-panel.md" in referee
    assert "references/publication/referee-review-playbook.md" in referee
    assert "templates/paper/review-ledger-schema.md" in referee
    assert "templates/paper/referee-decision-schema.md" in referee
    assert "templates/paper/referee-report.tex" in referee
    assert "Peer Review Panel Protocol" not in expanded
    assert "Referee Review Playbook" not in expanded
    assert "Review Ledger Schema" not in expanded
    assert "Referee Decision Schema" not in expanded
    assert "Referee Report Template" not in expanded
