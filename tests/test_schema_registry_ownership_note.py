from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_schema_registry_ownership_note_names_canonical_sources() -> None:
    note_path = REPO_ROOT / "docs" / "schema-registry-ownership.md"
    note = note_path.read_text(encoding="utf-8")

    canonical_paths = [
        "src/gpd/adapters/runtime_catalog.json",
        "src/gpd/adapters/runtime_catalog_schema.json",
        "src/gpd/adapters/runtime_catalog.py",
        "src/gpd/mcp/builtin_servers.py",
        "src/gpd/core/public_surface_contract.json",
        "src/gpd/core/public_surface_contract_schema.json",
        "src/gpd/core/public_surface_contract.py",
        "src/gpd/core/model_visible_sections.py",
        "src/gpd/specs/templates/",
        "infra/gpd-*.json",
    ]

    for canonical_path in canonical_paths:
        assert canonical_path in note
        if "*" in canonical_path:
            matches = tuple(REPO_ROOT.glob(canonical_path))
            assert matches, f"No files match {canonical_path}"
            continue
        assert (REPO_ROOT / canonical_path).exists()
