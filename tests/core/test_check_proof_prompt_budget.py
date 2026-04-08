"""Prompt budget regressions for the `gpd-check-proof` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_check_proof_prompt_stays_within_expected_budget_and_drops_panel_inlining() -> None:
    path = AGENTS_DIR / "gpd-check-proof.md"
    source = path.read_text(encoding="utf-8")
    expanded = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 2_400
    assert metrics.expanded_char_count < 125_000
    assert "{GPD_INSTALL_DIR}/templates/proof-redteam-schema.md" in source
    assert "{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md" in source
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" not in source
    assert "Peer Review Panel Protocol" not in expanded
