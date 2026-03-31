"""Guardrails for model-visible project-contract grounding guidance."""

from __future__ import annotations

from pathlib import Path


def test_state_json_schema_surfaces_hidden_grounding_requirements() -> None:
    schema = (
        Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates" / "state-json-schema.md"
    ).read_text(encoding="utf-8")

    assert "The `project_contract` schema is closed." in schema
    assert "Do not invent extra keys at the top level or inside nested objects." in schema
    assert "List-shaped fields must stay lists, even when they contain one item." in schema
    assert "Blank list entries are invalid." in schema
    assert "Duplicate list entries are also invalid after trimming whitespace" in schema
    assert "at least three words" in schema
    assert "gpd --raw validate project-contract - --mode approved" in schema
    assert "`context_intake`, `approach_policy`, and `uncertainty_markers` are JSON objects when present; do not collapse them to strings or lists." in schema
    assert "`schema_version` must be the integer `1`." in schema
    assert "`must_surface` is a boolean scalar. Use the JSON literals `true` and `false`;" in schema
    assert "`context_intake` must not be empty." in schema
    assert "already exists inside the current project root" in schema
    assert "already exists inside the current project root" in schema
