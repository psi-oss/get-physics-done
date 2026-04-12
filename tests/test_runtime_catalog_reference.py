"""Ensure the runtime catalog reference page is in sync with the renderer."""

from __future__ import annotations

from pathlib import Path

from scripts.render_runtime_catalog_table import render_table

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_catalog_reference_matches_renderer() -> None:
    doc = (REPO_ROOT / "docs" / "runtime-catalog-reference.md").read_text(encoding="utf-8")
    assert render_table() in doc
