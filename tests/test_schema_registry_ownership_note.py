from __future__ import annotations

from pathlib import Path

from scripts.schema_registry_sources import CANONICAL_SOURCES, render_table

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_schema_registry_ownership_note_names_canonical_sources() -> None:
    note_path = REPO_ROOT / "docs" / "schema-registry-ownership.md"
    note = note_path.read_text(encoding="utf-8")

    assert render_table() in note

    for source in CANONICAL_SOURCES:
        assert f"`{source.path}`" in note
        if source.pattern:
            matches = tuple(REPO_ROOT.glob(source.path))
            assert matches, f"No files match {source.path}"
            continue
        assert (REPO_ROOT / source.path).exists()
