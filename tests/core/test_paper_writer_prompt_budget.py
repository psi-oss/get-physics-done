"""Prompt budget regression tests for the `gpd-paper-writer` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_paper_writer_prompt_stays_within_expected_budget_and_keeps_contract_paths_lightweight() -> None:
    path = AGENTS_DIR / "gpd-paper-writer.md"
    source = path.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    expanded = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 3_400
    assert metrics.expanded_char_count < 160_000
    assert "{GPD_INSTALL_DIR}/templates/notation-glossary.md" in source
    assert "{GPD_INSTALL_DIR}/templates/latex-preamble.md" in source
    assert "{GPD_INSTALL_DIR}/templates/paper/author-response.md" in source
    assert "{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" in source
    assert "{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" in source
    assert "{GPD_INSTALL_DIR}/references/publication/paper-writer-cookbook.md" in source
    assert "{GPD_INSTALL_DIR}/references/publication/figure-generation-templates.md" in source
    assert "{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md" in source
    assert "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" not in source
    assert "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" not in source
    assert "@{GPD_INSTALL_DIR}/templates/notation-glossary.md" not in source
    assert "@{GPD_INSTALL_DIR}/templates/latex-preamble.md" not in source
    assert "@{GPD_INSTALL_DIR}/templates/paper/author-response.md" not in source
    assert "# Notation Glossary Template" not in expanded
    assert "# LaTeX Preamble Template" not in expanded
    assert "# Author Response Template" not in expanded
