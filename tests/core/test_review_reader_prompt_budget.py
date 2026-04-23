"""Prompt budget assertions for the `gpd-review-reader` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_review_reader_prompt_stays_within_expected_budget() -> None:
    metrics = measure_prompt_surface(
        AGENTS_DIR / "gpd-review-reader.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 2_000
    assert metrics.expanded_char_count < 110_000


def test_gpd_review_reader_prompt_keeps_panel_contract_pointer_without_inlining_the_panel_schema() -> None:
    review_reader = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    expanded = expanded_prompt_text(
        AGENTS_DIR / "gpd-review-reader.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert "references/publication/peer-review-panel.md" in review_reader
    assert "references/shared/shared-protocols.md" in review_reader
    assert "references/orchestration/agent-infrastructure.md" in review_reader
    assert "Peer Review Panel Protocol" not in expanded
    assert "Stage 1 `CLAIMS{round_suffix}.json` must follow this compact `ClaimIndex` shape:" not in expanded
    assert "StageReviewReport`, nested `ReviewFinding`, and nested `ProofAuditRecord` entries use a closed schema" not in expanded
