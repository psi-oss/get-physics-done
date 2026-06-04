from __future__ import annotations

import pytest
from pydantic import ValidationError

from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaAxis,
    ResearchPersonaError,
    ResearchPersonaFact,
    parse_research_persona_data_strict,
)

TOP_LEVEL_LIST_FIELDS = (
    "facts",
    "axes",
    "standing_preferences",
    "negative_preferences",
    "tools",
    "research_areas",
    "papers",
    "collaborators",
    "references",
    "expertise",
    "workstyle",
    "scientific_taste",
)


def _fact_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "fact-workstyle",
        "category": "workstyle",
        "value": "Prefers concise plans with explicit verification.",
        "confidence": "confirmed",
        "privacy": "safe_to_share",
    }
    payload.update(overrides)
    return payload


def _error_locations(exc: ValidationError) -> set[tuple[str | int, ...]]:
    return {tuple(error["loc"]) for error in exc.errors()}


def test_default_persona_is_schema_version_one_with_empty_collections() -> None:
    persona = ResearchPersona()

    assert persona.schema_version == 1
    for field_name in TOP_LEVEL_LIST_FIELDS:
        assert getattr(persona, field_name) == []


@pytest.mark.parametrize("schema_version", [True, False, 1.0, "1", 0, 2])
def test_schema_version_must_be_exact_integer_one(schema_version: object) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ResearchPersona(schema_version=schema_version)

    assert ("schema_version",) in _error_locations(exc_info.value)


def test_unknown_fields_are_forbidden_at_top_level_and_nested_models() -> None:
    with pytest.raises(ValidationError) as top_level:
        ResearchPersona.model_validate({"schema_version": 1, "legacy_profile": "leak"})
    assert ("legacy_profile",) in _error_locations(top_level.value)

    with pytest.raises(ValidationError) as fact_error:
        ResearchPersonaFact.model_validate(_fact_payload(legacy_note="leak"))
    assert ("legacy_note",) in _error_locations(fact_error.value)

    with pytest.raises(ValidationError) as axis_error:
        ResearchPersonaAxis.model_validate({"id": "risk_tolerance", "value": 0.25, "legacy_note": "leak"})
    assert ("legacy_note",) in _error_locations(axis_error.value)


def test_strings_and_lists_are_normalized_without_leaking_duplicates_or_blanks() -> None:
    fact = ResearchPersonaFact(
        id="  fact-workstyle  ",
        category=" WorkStyle ",
        value="  Prefers concise plans.  ",
        confidence=" CONFIRMED ",
        privacy=" Safe_To_Share ",
        sources=[" user_statement ", "", "user_statement", " manual_patch "],
        evidence_refs=[" note-1 ", "note-1", " note-2 "],
    )

    assert fact.id == "fact-workstyle"
    assert fact.category == "workstyle"
    assert fact.value == "Prefers concise plans."
    assert fact.confidence == "confirmed"
    assert fact.privacy == "safe_to_share"
    assert fact.sources == ["user_statement", "manual_patch"]
    assert fact.evidence_refs == ["note-1", "note-2"]

    persona = ResearchPersona(
        standing_preferences=[" concise ", "", "concise", " rigorous "],
        tools=[" uv ", "uv", " pytest "],
        research_areas=[" quantum gravity ", "quantum gravity", " scattering "],
    )

    assert persona.standing_preferences == ["concise", "rigorous"]
    assert persona.tools == ["uv", "pytest"]
    assert persona.research_areas == ["quantum gravity", "scattering"]


def test_strict_parse_rejects_scalar_strings_for_list_fields() -> None:
    with pytest.raises((ResearchPersonaError, ValidationError, ValueError)):
        parse_research_persona_data_strict({"schema_version": 1, "standing_preferences": "concise"})


def test_bool_values_are_not_coerced_as_integers_or_numbers() -> None:
    with pytest.raises(ValidationError) as schema_error:
        ResearchPersona.model_validate({"schema_version": True})
    assert ("schema_version",) in _error_locations(schema_error.value)

    with pytest.raises(ValidationError) as axis_error:
        ResearchPersonaAxis(id="risk_tolerance", value=True)
    assert ("value",) in _error_locations(axis_error.value)


def test_fact_defaults_and_vocabularies_are_validated() -> None:
    fact = ResearchPersonaFact.model_validate(_fact_payload())

    assert fact.sources == []
    assert fact.evidence_refs == []
    assert fact.confidence == "confirmed"
    assert fact.privacy == "safe_to_share"

    for field_name, bad_value in (
        ("category", "unsupported_category"),
        ("confidence", "certain"),
        ("privacy", "public"),
    ):
        with pytest.raises(ValidationError) as exc_info:
            ResearchPersonaFact.model_validate(_fact_payload(**{field_name: bad_value}))
        assert (field_name,) in _error_locations(exc_info.value)


@pytest.mark.parametrize("field_name", ["id", "value"])
def test_fact_required_strings_reject_blanks(field_name: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ResearchPersonaFact.model_validate(_fact_payload(**{field_name: "   "}))

    assert (field_name,) in _error_locations(exc_info.value)


def test_axis_accepts_in_range_values_and_rejects_values_outside_unit_bounds() -> None:
    axis = ResearchPersonaAxis(id="risk_tolerance", value=0.25)

    assert axis.id == "risk_tolerance"
    assert axis.value == 0.25

    for value in (-1.01, 1.01):
        with pytest.raises(ValidationError) as exc_info:
            ResearchPersonaAxis(id="risk_tolerance", value=value)
        assert ("value",) in _error_locations(exc_info.value)
