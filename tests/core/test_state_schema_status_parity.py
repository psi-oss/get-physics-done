"""Parity tests for documented state status vocabulary."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.core.state import VALID_STATUSES, ResearchState

REPO_ROOT = Path(__file__).resolve().parents[2]


def _state_schema_text() -> str:
    return (REPO_ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")


def _status_schema_values() -> list[str]:
    text = _state_schema_text()
    match = re.search(r"\*\*Valid `status` values:\*\*\n\n```\n(?P<values>.*?)\n```", text, re.DOTALL)
    assert match is not None
    return [value.strip() for value in match.group("values").replace("\n", " ").split(",") if value.strip()]


def _top_level_schema_fields() -> list[str]:
    text = _state_schema_text()
    match = re.search(r"## Top-Level Fields\n\n(?P<table>\| Field .*?)\n\n", text, re.DOTALL)
    assert match is not None
    fields: list[str] = []
    for line in match.group("table").splitlines()[2:]:
        parts = line.split("|")
        if len(parts) < 3:
            continue
        field = parts[1].strip().strip("`")
        if field and not field.startswith("_"):
            fields.append(field)
    return fields


def _roadmap_status_values() -> list[str]:
    text = (REPO_ROOT / "src/gpd/specs/templates/roadmap.md").read_text(encoding="utf-8")
    match = re.search(r"<status_values>\n(?P<body>.*?)\n\s*</status_values>", text, re.DOTALL)
    assert match is not None
    return re.findall(r"^- `([^`]+)` -", match.group("body"), re.MULTILINE)


def test_state_schema_status_values_match_core_state() -> None:
    assert _status_schema_values() == VALID_STATUSES

    text = _state_schema_text()
    match = re.search(r"VALID_STATUSES list \((?P<count>\d+) values\)", text)
    assert match is not None
    assert int(match.group("count")) == len(VALID_STATUSES)


def test_state_schema_top_level_fields_match_research_state_model() -> None:
    assert _top_level_schema_fields() == list(ResearchState.model_fields)


def test_state_schema_documents_structured_list_and_alignment_fields() -> None:
    text = _state_schema_text()
    for field in ("active_calculations", "open_questions", "pending_todos", "blockers"):
        assert f"| `{field}` | `(string \\| object)[]` |" in text
    assert "| `resolved_questions` | `ResolvedQuestionObject[]` |" in text
    assert "| `contract_alignment` | `ContractAlignmentGate` |" in text
    assert "### `ResolvedQuestionObject`" in text
    assert "### `ContractAlignmentGate`" in text


def test_state_schema_uses_public_state_persistence_wording() -> None:
    text = _state_schema_text()

    assert "public state persistence path" in text
    assert "Public state commands parse markdown-visible fields" in text
    assert "Public state commands that update canonical JSON regenerate the human-readable STATE.md view" in text
    for internal_helper in (
        "save_state_markdown",
        "save_state_json",
        "sync_state_json",
        "generate_state_markdown",
        "load_state_json",
        "file_lock",
    ):
        assert internal_helper not in text


def test_roadmap_status_values_match_core_state() -> None:
    assert _roadmap_status_values() == VALID_STATUSES
