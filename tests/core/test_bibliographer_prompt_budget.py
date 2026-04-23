"""Prompt budget assertions for the `gpd-bibliographer` agent surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import expanded_prompt_text, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_gpd_bibliographer_prompt_stays_within_expected_budget_and_keeps_contract_paths_lightweight() -> None:
    path = AGENTS_DIR / "gpd-bibliographer.md"
    source = path.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)
    expanded = expanded_prompt_text(path, src_root=SOURCE_ROOT, path_prefix=PATH_PREFIX)

    assert metrics.raw_include_count == 0
    assert metrics.expanded_line_count < 1_400
    assert metrics.expanded_char_count < 60_000

    for ref in (
        "references/shared/shared-protocols.md",
        "references/physics-subfields.md",
        "references/orchestration/agent-infrastructure.md",
        "templates/notation-glossary.md",
        "references/publication/bibtex-standards.md",
        "references/publication/publication-pipeline-modes.md",
        "references/publication/bibliography-advanced-search.md",
    ):
        lightweight = f"{{GPD_INSTALL_DIR}}/{ref}"
        eager = f"@{{GPD_INSTALL_DIR}}/{ref}"
        assert lightweight in source
        assert eager not in source

    assert "# Bibliography Advanced Search Protocols" not in expanded
    assert "# Notation Glossary Template" not in expanded
