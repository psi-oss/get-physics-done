from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_readme_badges_do_not_embed_data_urls() -> None:
    readme = _read("README.md")

    assert "data:image" not in readme, "README badges should not embed data URI payloads"


def test_tests_readme_references_canonical_schema_note() -> None:
    tests_readme = _read("tests/README.md")

    assert "docs/schema-registry-ownership.md" in tests_readme
    assert "tests/test_schema_registry_ownership_note.py" in tests_readme


def test_debug_surfaces_do_not_reference_removed_resolve_model_wrapper() -> None:
    for relative in (
        "src/gpd/commands/debug.md",
        "src/gpd/specs/workflows/debug.md",
    ):
        assert "gpd resolve-model" not in _read(relative)
