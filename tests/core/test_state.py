"""Tests for gpd.core.state — parse/generate round-trip, validation, defaults."""

from __future__ import annotations

from gpd.core.state import (
    VALID_STATUSES,
    ResearchState,
    default_state_dict,
    ensure_state_schema,
    generate_state_markdown,
    is_valid_status,
    parse_state_md,
    parse_state_to_json,
    state_extract_field,
    state_has_field,
    state_replace_field,
    validate_state_transition,
)

# ─── default_state_dict ──────────────────────────────────────────────────────


def test_default_state_dict_has_required_keys():
    s = default_state_dict()
    assert "position" in s
    assert "decisions" in s
    assert "blockers" in s
    assert "session" in s
    assert "convention_lock" in s
    assert "approximations" in s
    assert "propagated_uncertainties" in s


def test_default_state_dict_position_defaults():
    s = default_state_dict()
    pos = s["position"]
    assert pos["current_phase"] is None
    assert pos["status"] is None
    assert pos["progress_percent"] == 0


# ─── parse_state_md ──────────────────────────────────────────────────────────


MINIMAL_STATE_MD = """\
# Research State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core research question:** How does X work?
**Current focus:** Testing the parser

## Current Position

**Current Phase:** 3
**Current Phase Name:** Derive Lagrangian
**Total Phases:** 10
**Current Plan:** 2
**Total Plans in Phase:** 4
**Status:** Executing
**Last Activity:** 2026-03-01
**Last Activity Description:** Completed derivation

**Progress:** [████████░░] 80%

## Active Calculations

- Computing trace over SU(3) generators

## Intermediate Results

None yet.

## Open Questions

- Is the ansatz consistent?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| Phase 1 P1 | 12m | 3 tasks | 5 files |

## Accumulated Context

### Decisions

- [Phase 1]: Use metric signature (-,+,+,+) — matches Weinberg convention

### Active Approximations

None yet.

**Convention Lock:**

No conventions locked yet.

### Propagated Uncertainties

None yet.

### Pending Todos

None yet.

### Blockers/Concerns

- Need to verify gauge invariance

## Session Continuity

**Last session:** 2026-03-01T10:00:00+00:00
**Stopped at:** Phase 3 P2
**Resume file:** None
"""


def test_parse_state_md_position():
    parsed = parse_state_md(MINIMAL_STATE_MD)
    pos = parsed["position"]
    assert pos["current_phase"] == "3"
    assert pos["current_phase_name"] == "Derive Lagrangian"
    assert pos["total_phases"] == 10
    assert pos["current_plan"] == "2"
    assert pos["total_plans_in_phase"] == 4
    assert pos["status"] == "Executing"
    assert pos["progress_percent"] == 80


def test_parse_state_md_project():
    parsed = parse_state_md(MINIMAL_STATE_MD)
    proj = parsed["project"]
    assert proj["core_question"] == "How does X work?"
    assert proj["current_focus"] == "Testing the parser"
    assert proj["project_md_updated"] == "2026-03-01"


def test_parse_state_md_decisions():
    parsed = parse_state_md(MINIMAL_STATE_MD)
    assert len(parsed["decisions"]) == 1
    d = parsed["decisions"][0]
    assert d["phase"] == "1"
    assert "metric signature" in d["summary"]
    assert d["rationale"] is not None


def test_parse_state_md_blockers():
    parsed = parse_state_md(MINIMAL_STATE_MD)
    assert len(parsed["blockers"]) == 1
    assert "gauge invariance" in parsed["blockers"][0]


def test_parse_state_md_session():
    parsed = parse_state_md(MINIMAL_STATE_MD)
    sess = parsed["session"]
    assert sess["last_date"] is not None
    assert "Phase 3 P2" in sess["stopped_at"]
    assert sess["resume_file"] == "None"


def test_parse_state_md_bullets():
    parsed = parse_state_md(MINIMAL_STATE_MD)
    assert len(parsed["active_calculations"]) == 1
    assert "SU(3)" in parsed["active_calculations"][0]
    assert len(parsed["open_questions"]) == 1
    assert "ansatz" in parsed["open_questions"][0]


def test_parse_state_md_metrics():
    parsed = parse_state_md(MINIMAL_STATE_MD)
    assert len(parsed["metrics"]) == 1
    assert parsed["metrics"][0]["label"] == "Phase 1 P1"
    assert parsed["metrics"][0]["duration"] == "12m"


# ─── round-trip: generate → parse ────────────────────────────────────────────


def test_round_trip_default():
    """generate_state_markdown(default) → parse_state_md should recover fields."""
    s = default_state_dict()
    md = generate_state_markdown(s)
    parsed = parse_state_md(md)
    assert parsed["position"]["status"] is None or parsed["position"]["status"] == "—"


def test_round_trip_with_data():
    s = default_state_dict()
    s["position"]["current_phase"] = "5"
    s["position"]["current_phase_name"] = "Renormalization"
    s["position"]["total_phases"] = 12
    s["position"]["status"] = "Executing"
    s["position"]["progress_percent"] = 42
    s["decisions"] = [{"phase": "3", "summary": "Use dim-reg", "rationale": "Standard approach"}]
    s["blockers"] = ["IR divergence in loop integral"]

    md = generate_state_markdown(s)
    parsed = parse_state_md(md)

    assert parsed["position"]["current_phase"] == "5"
    assert parsed["position"]["current_phase_name"] == "Renormalization"
    assert parsed["position"]["total_phases"] == 12
    assert parsed["position"]["status"] == "Executing"
    assert parsed["position"]["progress_percent"] == 42
    assert len(parsed["decisions"]) == 1
    assert "dim-reg" in parsed["decisions"][0]["summary"]
    assert len(parsed["blockers"]) == 1
    assert "IR divergence" in parsed["blockers"][0]


# ─── ensure_state_schema ─────────────────────────────────────────────────────


def test_ensure_state_schema_none():
    result = ensure_state_schema(None)
    assert "position" in result
    assert "decisions" in result


def test_ensure_state_schema_partial():
    partial = {"position": {"current_phase": "7", "status": "Planning"}}
    result = ensure_state_schema(partial)
    assert result["position"]["current_phase"] == "7"
    assert result["position"]["status"] == "Planning"
    assert "decisions" in result


def test_ensure_state_schema_legacy_project_key():
    legacy = {"project": {"core_question": "Why?", "current_focus": "Testing"}}
    result = ensure_state_schema(legacy)
    assert result["project_reference"]["core_research_question"] == "Why?"
    assert result["project_reference"]["current_focus"] == "Testing"


def test_ensure_state_schema_empty_dict():
    """An empty {} must produce a valid default state without crashing."""
    result = ensure_state_schema({})
    assert "position" in result
    assert "decisions" in result
    assert result["position"]["progress_percent"] == 0


def test_ensure_state_schema_extra_unknown_fields():
    """Unknown top-level keys are preserved via extra='allow'."""
    result = ensure_state_schema({"_version": 1, "_synced_at": "2025-01-01", "custom_field": "kept"})
    assert result["_version"] == 1
    assert result["_synced_at"] == "2025-01-01"
    assert result["custom_field"] == "kept"
    # Standard fields still present
    assert "position" in result
    assert "decisions" in result


def test_ensure_state_schema_wrong_type_nested_int_for_string():
    """An int where a string is expected in a nested model should not crash."""
    result = ensure_state_schema({"position": {"status": 42}})
    # position key gets dropped due to validation error; defaults applied
    assert isinstance(result, dict)
    assert "position" in result
    assert result["position"]["status"] is None  # default


def test_ensure_state_schema_wrong_type_string_for_int():
    """A non-numeric string where int is expected should not crash."""
    result = ensure_state_schema({"position": {"progress_percent": "fifty"}})
    assert isinstance(result, dict)
    assert result["position"]["progress_percent"] == 0  # default


def test_ensure_state_schema_numeric_string_for_int():
    """A numeric string like '50' should coerce to int via Pydantic."""
    result = ensure_state_schema({"position": {"progress_percent": "50"}})
    assert result["position"]["progress_percent"] == 50


def test_ensure_state_schema_ints_in_string_list():
    """Ints in a list[str|dict] field should not crash."""
    result = ensure_state_schema({"active_calculations": [1, 2, 3]})
    assert isinstance(result["active_calculations"], list)


def test_ensure_state_schema_bad_nested_decision():
    """Decisions with wrong sub-field types should not crash."""
    result = ensure_state_schema({"decisions": [{"phase": 1, "summary": 42}]})
    assert isinstance(result["decisions"], list)


def test_ensure_state_schema_convention_lock_wrong_type():
    """Convention lock with int values where strings expected should not crash."""
    result = ensure_state_schema({"convention_lock": {"metric_signature": 42}})
    assert isinstance(result["convention_lock"], dict)


def test_ensure_state_schema_preserves_good_fields_when_one_is_bad():
    """When one top-level key has type errors, other valid keys survive."""
    result = ensure_state_schema({
        "position": {"status": 42},  # bad: int for str
        "blockers": ["still valid"],
    })
    assert result["blockers"] == ["still valid"]


def test_ensure_state_schema_version_not_checked():
    """_version=999 is accepted (no version gating)."""
    result = ensure_state_schema({"_version": 999})
    assert result["_version"] == 999


def test_ensure_state_schema_non_dict_input():
    """A list or other non-dict input returns defaults."""
    result = ensure_state_schema([1, 2, 3])
    assert "position" in result
    assert "decisions" in result


def test_ensure_state_schema_string_for_session():
    """session as a non-dict value is corrected at the top-level type check."""
    result = ensure_state_schema({"session": "bad"})
    assert isinstance(result["session"], dict)


def test_ensure_state_schema_list_for_session():
    """session as a list is corrected at the top-level type check."""
    result = ensure_state_schema({"session": ["bad"]})
    assert isinstance(result["session"], dict)


# ─── field helpers ────────────────────────────────────────────────────────────


def test_state_extract_field():
    content = "**Status:** Executing\n**Phase:** 3"
    assert state_extract_field(content, "Status") == "Executing"
    assert state_extract_field(content, "Phase") == "3"
    assert state_extract_field(content, "Missing") is None


def test_state_replace_field():
    content = "**Status:** Executing\n**Phase:** 3"
    updated = state_replace_field(content, "Status", "Paused")
    assert "**Status:** Paused" in updated
    assert "Phase:** 3" in updated


def test_state_has_field():
    content = "**Status:** Executing"
    assert state_has_field(content, "Status") is True
    assert state_has_field(content, "Missing") is False


# ─── status validation ───────────────────────────────────────────────────────


def test_is_valid_status():
    assert is_valid_status("Executing") is True
    assert is_valid_status("Planning") is True
    assert is_valid_status("Complete") is True
    assert is_valid_status("InvalidFoo") is False


def test_validate_state_transition_valid():
    assert validate_state_transition("Executing", "Phase complete") is None


def test_validate_state_transition_invalid():
    result = validate_state_transition("Not started", "Complete")
    assert result is not None
    assert "Invalid transition" in result


def test_validate_state_transition_same_status():
    assert validate_state_transition("Executing", "Executing") is None


def test_validate_state_transition_paused_allows_any():
    assert validate_state_transition("Paused", "Executing") is None
    assert validate_state_transition("Paused", "Planning") is None


# ─── parse_state_to_json ─────────────────────────────────────────────────────


def test_parse_state_to_json_structure():
    result = parse_state_to_json(MINIMAL_STATE_MD)
    assert result["_version"] == 1
    assert "_synced_at" in result
    assert result["position"]["current_phase"] == "3"
    assert result["position"]["status"] == "Executing"
    assert len(result["decisions"]) == 1
    assert len(result["blockers"]) == 1


# ─── model types ─────────────────────────────────────────────────────────────


def test_research_state_model():
    state = ResearchState()
    dumped = state.model_dump()
    assert "position" in dumped
    assert "decisions" in dumped
    assert isinstance(dumped["decisions"], list)


def test_valid_statuses_is_list():
    assert isinstance(VALID_STATUSES, list)
    assert "Executing" in VALID_STATUSES
    assert "Complete" in VALID_STATUSES
