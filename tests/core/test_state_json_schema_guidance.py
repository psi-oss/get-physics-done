"""Guardrails for model-visible project-contract grounding guidance."""

from __future__ import annotations

from pathlib import Path


def test_state_json_schema_surfaces_hidden_grounding_requirements() -> None:
    schema = (
        Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates" / "state-json-schema.md"
    ).read_text(encoding="utf-8")

    assert "at least three words" in schema
    assert "already exists inside the current project root" in schema
    assert "already exists inside the current project root" in schema
