from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_debug_surfaces_do_not_reference_removed_resolve_model_wrapper() -> None:
    for relative in (
        "src/gpd/commands/debug.md",
        "src/gpd/specs/workflows/debug.md",
    ):
        assert "gpd resolve-model" not in _read(relative)
