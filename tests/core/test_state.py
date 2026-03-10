"""Tests for gpd.core.state — parse/generate round-trip, validation, defaults."""

from __future__ import annotations

import json

from gpd.core.constants import ProjectLayout
from gpd.core.state import (
    VALID_STATUSES,
    ResearchState,
    default_state_dict,
    ensure_state_schema,
    generate_state_markdown,
    is_valid_status,
    load_state_json,
    parse_state_md,
    parse_state_to_json,
    save_state_json,
    save_state_markdown,
    state_load,
    state_extract_field,
    state_has_field,
    state_replace_field,
    state_validate,
    validate_state_transition,
)


def _state_with_result(result: dict) -> dict:
    state = default_state_dict()
    state["intermediate_results"] = [result]
    return state

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

See: .gpd/PROJECT.md (updated 2026-03-01)

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


def test_parse_state_md_decision_table_ignored():
    content = MINIMAL_STATE_MD.replace(
        "- [Phase 1]: Use metric signature (-,+,+,+) — matches Weinberg convention",
        "| Phase | Summary | Rationale |\n| ----- | ------- | --------- |\n| 1 | Use metric signature (-,+,+,+) | matches Weinberg convention |",
    )
    parsed = parse_state_md(content)
    assert parsed["decisions"] == []


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


def test_generate_state_markdown_shows_verification_evidence_count():
    state = _state_with_result(
        {
            "id": "R-01",
            "description": "Mass shell relation",
            "equation": "p^2 = m^2",
            "depends_on": [],
            "verified": True,
            "verification_records": [
                {"verifier": "gpd-verifier", "method": "limit-check", "confidence": "high"}
            ],
        }
    )
    md = generate_state_markdown(state)
    assert "evidence: 1" in md


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


def test_ensure_state_schema_does_not_migrate_removed_keys():
    removed_keys = {
        "project": {"core_question": "Why?", "current_focus": "Testing"},
        "metrics": [{"label": "Phase 1 P1", "duration": "12m"}],
        "session": {"last_session": "2026-03-10"},
        "position": {"progress": "[#####.....] 50%"},
    }
    result = ensure_state_schema(removed_keys)
    assert result["project_reference"]["core_research_question"] is None
    assert result["project_reference"]["current_focus"] is None
    assert result["performance_metrics"]["rows"] == []
    assert result["session"]["last_date"] is None
    assert result["position"]["progress_percent"] == 0
    assert result["project"] == removed_keys["project"]
    assert result["metrics"] == removed_keys["metrics"]


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


# ─── integrity mode / provenance ─────────────────────────────────────────────


def test_state_validate_missing_files_sets_review_integrity_metadata(tmp_path):
    result = state_validate(tmp_path, integrity_mode="review")
    assert result.valid is False
    assert result.integrity_mode == "review"
    assert result.integrity_status == "blocked"
    assert "state.json not found" in result.issues
    assert "STATE.md not found" in result.issues


def test_load_state_json_review_blocks_on_schema_normalization(tmp_path):
    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir(parents=True, exist_ok=True)
    layout.state_json.write_text(json.dumps({"position": {"status": 42}}), encoding="utf-8")

    assert load_state_json(tmp_path, integrity_mode="review") is None

    standard = load_state_json(tmp_path, integrity_mode="standard")
    assert standard is not None
    assert standard["position"]["status"] is None


def test_state_validate_standard_warns_for_verified_result_without_records(tmp_path):
    state = _state_with_result(
        {
            "id": "R-02",
            "description": "Unbacked result",
            "depends_on": [],
            "verified": True,
            "verification_records": [],
        }
    )
    save_state_json(tmp_path, state)

    result = state_validate(tmp_path)
    assert result.valid is True
    assert result.integrity_mode == "standard"
    assert result.integrity_status == "warning"
    assert any("verified=true but no verification_records present" in warning for warning in result.warnings)


def test_state_validate_review_blocks_verified_result_without_records(tmp_path):
    state = _state_with_result(
        {
            "id": "R-03",
            "description": "Review-blocking result",
            "depends_on": [],
            "verified": True,
            "verification_records": [],
        }
    )
    save_state_json(tmp_path, state)

    result = state_validate(tmp_path, integrity_mode="review")
    assert result.valid is False
    assert result.integrity_mode == "review"
    assert result.integrity_status == "blocked"
    assert any("verified=true but no verification_records present" in issue for issue in result.issues)


def test_state_validate_review_blocks_missing_evidence_file(tmp_path):
    state = _state_with_result(
        {
            "id": "R-04",
            "description": "Result with missing artifact",
            "depends_on": [],
            "verified": True,
            "verification_records": [
                {
                    "verifier": "gpd-verifier",
                    "method": "artifact-check",
                    "confidence": "high",
                    "evidence_path": "artifacts/reports/R-04.json",
                }
            ],
        }
    )
    save_state_json(tmp_path, state)

    result = state_validate(tmp_path, integrity_mode="review")
    assert result.valid is False
    assert result.integrity_status == "blocked"
    assert any('evidence_path "artifacts/reports/R-04.json" does not exist' in issue for issue in result.issues)


def test_state_load_review_surfaces_integrity_blockers(tmp_path):
    state = _state_with_result(
        {
            "id": "R-05",
            "description": "Result pending evidence ledger",
            "depends_on": [],
            "verified": True,
            "verification_records": [],
        }
    )
    save_state_json(tmp_path, state)

    loaded = state_load(tmp_path, integrity_mode="review")
    assert loaded.state["intermediate_results"][0]["id"] == "R-05"
    assert loaded.integrity_mode == "review"
    assert loaded.integrity_status == "blocked"
    assert any("verified=true but no verification_records present" in issue for issue in loaded.integrity_issues)


def test_save_state_markdown_preserves_verification_records_for_tagged_results(tmp_path):
    state = _state_with_result(
        {
            "id": "R-06",
            "description": "Tagged result",
            "equation": "F = ma",
            "depends_on": [],
            "verified": True,
            "verification_records": [
                {
                    "verifier": "gpd-verifier",
                    "method": "dimensional-analysis",
                    "confidence": "high",
                    "trace_id": "trace-06",
                    "commit_sha": "abc1234",
                }
            ],
        }
    )
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    md_content = layout.state_md.read_text(encoding="utf-8")
    assert "evidence: 1" in md_content

    save_state_markdown(tmp_path, md_content)
    reloaded = load_state_json(tmp_path)

    assert reloaded is not None
    result = reloaded["intermediate_results"][0]
    assert result["id"] == "R-06"
    assert result["verification_records"][0]["trace_id"] == "trace-06"
    assert result["verification_records"][0]["commit_sha"] == "abc1234"


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
    assert is_valid_status("Phase complete") is False
    assert is_valid_status("InvalidFoo") is False


def test_validate_state_transition_valid():
    assert validate_state_transition("Executing", "Phase complete — ready for verification") is None


def test_validate_state_transition_invalid():
    result = validate_state_transition("Not started", "Complete")
    assert result is not None
    assert "Invalid transition" in result


def test_validate_state_transition_removed_phase_complete_alias_invalid():
    result = validate_state_transition("Executing", "Phase complete")
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
    assert result["project_reference"]["core_research_question"] == "How does X work?"
    assert result["position"]["current_phase"] == "3"
    assert result["position"]["status"] == "Executing"
    assert result["session"]["last_date"] is not None
    assert "last_session" not in result["session"]
    assert result["performance_metrics"]["rows"][0]["label"] == "Phase 1 P1"
    assert "project" not in result
    assert "metrics" not in result
    assert len(result["decisions"]) == 1
    assert len(result["blockers"]) == 1


# ─── model types ─────────────────────────────────────────────────────────────


def test_research_state_model():
    state = ResearchState()
    dumped = state.model_dump()
    assert "position" in dumped
    assert "decisions" in dumped
    assert isinstance(dumped["decisions"], list)


def test_is_valid_status_rejects_prefix():
    """Prefixes of valid statuses must not be accepted."""
    assert is_valid_status("Exec") is False
    assert is_valid_status("Plan") is False


def test_extract_field_does_not_cross_newline():
    """state_extract_field must not capture text from the next line."""
    assert state_extract_field("**Status:**\n**Phase:** 3", "Status") is None


def test_decision_emdash_in_rationale_preserved():
    """An em-dash inside the rationale must not truncate the text."""
    s = default_state_dict()
    s["decisions"] = [
        {
            "phase": "2",
            "summary": "Pick gauge",
            "rationale": "Lorenz gauge — simplifies Fourier — standard choice",
        }
    ]
    md = generate_state_markdown(s)
    parsed = parse_state_md(md)
    assert len(parsed["decisions"]) == 1
    rat = parsed["decisions"][0]["rationale"]
    assert rat is not None
    assert "standard choice" in rat


def test_valid_statuses_is_list():
    assert isinstance(VALID_STATUSES, list)
    assert "Executing" in VALID_STATUSES
    assert "Complete" in VALID_STATUSES
