"""Ensure the runtime catalog reference page is in sync with the renderer."""

from __future__ import annotations

from pathlib import Path

from scripts.render_runtime_catalog_table import render_table

REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_runtime_catalog_table(doc: str) -> str:
    lines = doc.splitlines()
    start_index = next(i for i, line in enumerate(lines) if line.strip().startswith("| Runtime |"))
    end_index = start_index
    for index in range(start_index + 1, len(lines)):
        if not lines[index].strip().startswith("|"):
            break
        end_index = index
    return "\n".join(lines[start_index : end_index + 1])


def test_runtime_catalog_reference_matches_renderer() -> None:
    doc = (REPO_ROOT / "docs" / "runtime-catalog-reference.md").read_text(encoding="utf-8")
    table = _extract_runtime_catalog_table(doc)
    assert table == render_table()
