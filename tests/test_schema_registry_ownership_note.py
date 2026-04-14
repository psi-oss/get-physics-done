from __future__ import annotations

from pathlib import Path

from scripts.schema_registry_sources import CANONICAL_SOURCES, render_table

REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_schema_registry_table(note: str) -> str:
    lines = note.splitlines()
    start_index = next(i for i, line in enumerate(lines) if line.strip().startswith("| Source |"))
    end_index = start_index
    for index in range(start_index + 1, len(lines)):
        if not lines[index].strip().startswith("|"):
            break
        end_index = index
    return "\n".join(lines[start_index : end_index + 1])


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


def test_schema_registry_ownership_table_matches_renderer() -> None:
    note_path = REPO_ROOT / "docs" / "schema-registry-ownership.md"
    note = note_path.read_text(encoding="utf-8")

    assert _extract_schema_registry_table(note) == render_table()
