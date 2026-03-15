"""Tests for gpd.core.state — parse/generate round-trip, validation, defaults."""

from __future__ import annotations

import json
from pathlib import Path

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
    state_extract_field,
    state_has_field,
    state_load,
    state_record_session,
    state_replace_field,
    state_set_project_contract,
    state_validate,
    validate_state_transition,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _state_with_result(result: dict) -> dict:
    state = default_state_dict()
    state["intermediate_results"] = [result]
    return state


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _event_name(event: dict[str, object]) -> str | None:
    for key in ("name", "span_name", "event", "event_name"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return None

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
    assert "project_contract" in s


def test_default_state_dict_position_defaults():
    s = default_state_dict()
    pos = s["position"]
    assert pos["current_phase"] is None
    assert pos["status"] is None
    assert pos["progress_percent"] == 0
    assert s["project_contract"] is None


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
**Resume file:** —
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
    assert proj["core_research_question"] == "How does X work?"
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
    assert sess["resume_file"] == "—"


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


def test_ensure_state_schema_valid_project_contract():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    result = ensure_state_schema({"project_contract": contract})
    assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
    assert result["project_contract"]["uncertainty_markers"]["disconfirming_observations"] == [
        "Benchmark agreement disappears once normalization is fixed"
    ]


def test_ensure_state_schema_invalid_project_contract_resets_to_none():
    result = ensure_state_schema(
        {
            "project_contract": {
                "scope": {
                    "in_scope": ["benchmark"],
                }
            }
        }
    )
    assert result["project_contract"] is None


def test_ensure_state_schema_malformed_project_contract_list_item_preserves_contract():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = ["bad"]

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
    assert result["project_contract"]["references"] == []


def test_ensure_state_schema_malformed_project_contract_singleton_field_preserves_valid_siblings():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": "not-a-list",
        "known_good_baselines": ["baseline-A"],
        "crucial_inputs": ["normalize with published convention"],
    }

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["context_intake"]["must_read_refs"] == []
    assert result["project_contract"]["context_intake"]["known_good_baselines"] == ["baseline-A"]
    assert result["project_contract"]["context_intake"]["crucial_inputs"] == [
        "normalize with published convention"
    ]


def test_ensure_state_schema_salvages_scope_list_drift_without_dropping_contract():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["scope"]["unresolved_questions"] = "not-a-list"

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
    assert result["project_contract"]["scope"]["unresolved_questions"] == []


def test_ensure_state_schema_salvages_reference_optional_field_without_dropping_reference():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"][0]["aliases"] = "not-a-list"

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["references"] == [
        {
            "id": "ref-benchmark",
            "kind": "paper",
            "locator": "Author et al., Journal, 2024",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Published comparison target",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare", "cite"],
        }
    ]


def test_ensure_state_schema_strips_claim_extra_keys_without_dropping_claim():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["claims"] == [
        {
            "id": "claim-benchmark",
            "statement": "Recover the benchmark value within tolerance",
            "observables": ["obs-benchmark"],
            "deliverables": ["deliv-figure"],
            "acceptance_tests": ["test-benchmark"],
            "references": ["ref-benchmark"],
        }
    ]


def test_ensure_state_schema_malformed_verification_record_preserves_intermediate_results():
    state = default_state_dict()
    state["intermediate_results"] = [
        {
            "id": "good-1",
            "description": "Good result",
            "verification_records": [
                {
                    "verified_at": "2026-03-14T00:00:00Z",
                    "verifier": "gpd-verifier",
                    "method": "manual",
                    "confidence": "high",
                }
            ],
        },
        {
            "id": "bad-1",
            "description": "Bad verification payload",
            "verification_records": ["oops"],
        },
        {
            "id": "good-2",
            "description": "Still present",
        },
    ]

    result = ensure_state_schema(state)

    ids = [item["id"] for item in result["intermediate_results"] if isinstance(item, dict)]
    assert ids == ["good-1", "bad-1", "good-2"]
    bad_result = next(item for item in result["intermediate_results"] if isinstance(item, dict) and item["id"] == "bad-1")
    assert bad_result["verification_records"] == []


def test_state_set_project_contract_persists_contract_and_unresolved_questions(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is True
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
    assert saved["project_contract"]["uncertainty_markers"]["weakest_anchors"] == ["Reference tolerance interpretation"]
    assert "Which diagnostic artifact should be primary?" in saved["open_questions"]


def test_state_set_project_contract_rejects_invalid_contract(tmp_path: Path):
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(
        tmp_path,
        {
            "scope": {
                "in_scope": ["missing question"],
            }
        },
    )

    assert result.updated is False
    assert result.reason is not None
    assert "Invalid project contract" in result.reason
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_state_set_project_contract_rejects_contract_missing_skeptical_fields(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["uncertainty_markers"]["weakest_anchors"] = []
    contract["uncertainty_markers"]["disconfirming_observations"] = []
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is False
    assert result.reason is not None
    assert "failed scoping validation" in result.reason
    assert "weakest_anchors" in result.reason
    assert "disconfirming_observations" in result.reason
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_state_set_project_contract_accepts_self_healable_contract(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is True
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"]["context_intake"]["must_read_refs"] == []


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


def test_state_validate_rejects_garbage_state_markdown(tmp_path):
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    layout.state_md.write_text("garbage", encoding="utf-8")

    result = state_validate(tmp_path)

    assert result.valid is False
    assert result.integrity_status == "degraded"
    assert any('STATE.md missing "# Research State" heading' in issue for issue in result.issues)


def test_state_validate_rejects_state_markdown_missing_canonical_section(tmp_path):
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    broken = layout.state_md.read_text(encoding="utf-8").replace("## Current Position", "## Position", 1)
    layout.state_md.write_text(broken, encoding="utf-8")

    result = state_validate(tmp_path)

    assert result.valid is False
    assert any('STATE.md missing "## Current Position" section' in issue for issue in result.issues)


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
    assert is_valid_status("InvalidFoo") is False


def test_validate_state_transition_valid():
    assert validate_state_transition("Executing", "Phase complete — ready for verification") is None


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
    assert result["project_reference"]["core_research_question"] == "How does X work?"
    assert result["position"]["current_phase"] == "3"
    assert result["position"]["status"] == "Executing"
    assert result["session"]["last_date"] is not None
    assert result["performance_metrics"]["rows"][0]["label"] == "Phase 1 P1"
    assert len(result["decisions"]) == 1
    assert len(result["blockers"]) == 1


def test_state_record_session_does_not_emit_local_observability_events(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir()
    layout.phases_dir.mkdir()

    state = default_state_dict()
    state["position"]["current_phase"] = "4"
    state["position"]["status"] = "Executing"
    state["session"]["last_date"] = "2026-03-01T10:00:00+00:00"
    state["session"]["stopped_at"] = "Phase 4 P1"
    state["session"]["resume_file"] = "resume.md"
    save_state_json(tmp_path, state)

    result = state_record_session(tmp_path, stopped_at="Phase 4 P2", resume_file="NEXT.md")
    assert result.recorded is True

    observability_dir = layout.gpd / "observability"
    assert not observability_dir.exists()


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


# ─── Issue 1: state_compact must call _recover_intent_locked ──────────────────


def _bootstrap_project_with_state(
    tmp_path: Path,
    state_dict: dict | None = None,
    *,
    current_phase: str = "03",
    status: str = "Executing",
    extra_lines: int = 0,
) -> Path:
    """Create a minimal .gpd/ project with STATE.md + state.json."""
    from gpd.core.state import default_state_dict, generate_state_markdown

    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n")
    (planning / "ROADMAP.md").write_text("# Roadmap\n")

    state = state_dict or default_state_dict()
    pos = state.setdefault("position", {})
    if pos.get("current_phase") is None:
        pos["current_phase"] = current_phase
    if pos.get("status") is None:
        pos["status"] = status
    if pos.get("current_plan") is None:
        pos["current_plan"] = "1"
    if pos.get("total_plans_in_phase") is None:
        pos["total_plans_in_phase"] = 3
    if pos.get("progress_percent") is None:
        pos["progress_percent"] = 33

    md = generate_state_markdown(state)
    if extra_lines > 0:
        md += "\n" + "\n".join(f"<!-- padding line {i} -->" for i in range(extra_lines))
    (planning / "STATE.md").write_text(md, encoding="utf-8")
    (planning / "state.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )
    return tmp_path


def test_state_compact_recovers_intent_before_reading(tmp_path):
    """state_compact must call _recover_intent_locked before reading state.json.

    Simulates an interrupted dual-write by leaving an intent marker whose
    temp files contain updated state.  After recovery, state_compact should
    see the updated (recovered) state.json, not the stale one.
    """
    from gpd.core.constants import STATE_WRITE_INTENT_FILENAME
    from gpd.core.state import (
        default_state_dict,
        generate_state_markdown,
        state_compact,
    )

    # Build a project whose STATE.md is large enough to trigger compaction
    state = default_state_dict()
    pos = state["position"]
    pos["current_phase"] = "05"
    pos["status"] = "Executing"
    pos["current_plan"] = "1"
    pos["total_plans_in_phase"] = 3
    pos["progress_percent"] = 50

    # Add many old decisions so there is content to compact
    state["decisions"] = [
        {"phase": str((i % 3) + 1), "summary": f"Old decision {i}"}
        for i in range(40)
    ]

    md = generate_state_markdown(state)
    md += "\n" + "\n".join(f"<!-- padding {i} -->" for i in range(100))

    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n")
    (planning / "ROADMAP.md").write_text("# Roadmap\n")

    # Write a STALE state.json with phase "01" (wrong)
    stale_state = default_state_dict()
    stale_state["position"]["current_phase"] = "01"
    stale_state["position"]["status"] = "Executing"
    (planning / "state.json").write_text(
        json.dumps(stale_state, indent=2) + "\n", encoding="utf-8"
    )
    (planning / "STATE.md").write_text(md, encoding="utf-8")

    # Create temp files that _recover_intent_locked will promote —
    # these carry the correct state with phase "05"
    json_tmp = planning / ".state-json-tmp"
    md_tmp = planning / ".state-md-tmp"
    json_tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text(md, encoding="utf-8")

    # Write the intent marker pointing at the temp files
    intent_path = planning / STATE_WRITE_INTENT_FILENAME
    intent_path.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")

    # Now call state_compact.  Before the fix, it would read the stale
    # state.json (phase "01") and skip intent recovery entirely.
    result = state_compact(tmp_path)

    # The intent marker must have been consumed (recovered)
    assert not intent_path.exists(), "intent marker should be removed after recovery"
    # The temp files should have been promoted (renamed away)
    assert not json_tmp.exists(), "json temp should be promoted by recovery"

    # state.json should now reflect phase "05" (recovered), not "01" (stale)
    recovered = json.loads((planning / "state.json").read_text(encoding="utf-8"))
    assert recovered["position"]["current_phase"] == "05"

    # state_compact itself should return a sensible result
    assert result.error is None


# ─── Issue 2: unreachable code removed from state_advance_plan ────────────────


def test_advance_plan_advances_normally(tmp_path):
    """state_advance_plan should advance Current Plan when below total."""
    from gpd.core.state import state_advance_plan

    cwd = _bootstrap_project_with_state(
        tmp_path,
        current_phase="03",
        status="Ready to execute",
    )
    result = state_advance_plan(cwd)
    assert result.advanced is True
    assert result.previous_plan == 1
    assert result.current_plan == 2


def test_advance_plan_returns_error_when_fields_missing(tmp_path):
    """state_advance_plan returns an error when Current Plan field is missing.

    After removing the unreachable code, the earlier None-check on
    safe_parse_int must still catch the missing-field case correctly.
    """
    from gpd.core.state import state_advance_plan

    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n")
    (planning / "ROADMAP.md").write_text("# Roadmap\n")

    # A STATE.md that has no **Current Plan:** field at all
    md = "# Research State\n\n**Status:** Executing\n**Total Plans in Phase:** 3\n"
    (planning / "STATE.md").write_text(md, encoding="utf-8")
    (planning / "state.json").write_text("{}", encoding="utf-8")

    result = state_advance_plan(tmp_path)
    assert result.advanced is False
    assert result.error is not None
    assert "Cannot parse" in result.error


def test_advance_plan_marks_phase_complete_on_last_plan(tmp_path):
    """When current_plan >= total_plans, it marks phase complete."""
    from gpd.core.state import (
        default_state_dict,
        generate_state_markdown,
        state_advance_plan,
    )

    state = default_state_dict()
    pos = state["position"]
    pos["current_phase"] = "02"
    pos["current_plan"] = "3"
    pos["total_plans_in_phase"] = 3
    pos["status"] = "Executing"
    pos["progress_percent"] = 90

    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n")
    (planning / "ROADMAP.md").write_text("# Roadmap\n")

    md = generate_state_markdown(state)
    (planning / "STATE.md").write_text(md, encoding="utf-8")
    (planning / "state.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )

    result = state_advance_plan(tmp_path)
    assert result.advanced is False
    assert result.reason == "last_plan"
    assert result.status == "ready_for_verification"
