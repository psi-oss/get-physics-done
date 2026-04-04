"""Tests for gpd.core.state — parse/generate round-trip, validation, defaults."""

from __future__ import annotations

import json
import logging
import os
import warnings
from contextlib import contextmanager
from pathlib import Path

import pytest

from gpd.contracts import ResearchContract
from gpd.core import state as state_module
from gpd.core.constants import STATE_JSON_BACKUP_FILENAME, STATE_JSON_FILENAME, ProjectLayout
from gpd.core.state import (
    VALID_STATUSES,
    ResearchState,
    _load_recent_projects_index,
    _load_state_snapshot_for_mutation,
    _normalize_state_schema,
    _recent_projects_index_path,
    default_state_dict,
    ensure_state_schema,
    generate_state_markdown,
    is_valid_status,
    load_state_json,
    parse_state_md,
    parse_state_to_json,
    peek_state_json,
    save_state_json,
    save_state_markdown,
    state_extract_field,
    state_get,
    state_has_field,
    state_load,
    state_record_session,
    state_replace_field,
    state_set_project_contract,
    state_snapshot,
    state_update_progress,
    state_validate,
    sync_state_json,
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


def _write_backup_only_state(
    tmp_path: Path,
    primary_state: dict[str, object],
    *,
    backup_state: dict[str, object] | None = None,
) -> ProjectLayout:
    save_state_json(tmp_path, primary_state)
    save_state_markdown(tmp_path, generate_state_markdown(primary_state))
    layout = ProjectLayout(tmp_path)
    state_for_backup = backup_state or primary_state
    layout.state_json_backup.write_text(json.dumps(state_for_backup, indent=2) + "\n", encoding="utf-8")
    layout.state_json.unlink()
    return layout


def _write_intent_recovery_state(
    tmp_path: Path,
    *,
    stale_state: dict[str, object],
    recovered_state: dict[str, object],
) -> ProjectLayout:
    """Create a stale state pair plus an intent marker pointing at recovered temp files."""
    save_state_json(tmp_path, stale_state)
    layout = ProjectLayout(tmp_path)
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text(generate_state_markdown(recovered_state), encoding="utf-8")
    layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")
    return layout


def _project_contract_with_question(question: str) -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["scope"]["question"] = question
    return contract


def _draft_invalid_project_contract() -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["references"] = ["missing-ref"]
    return contract

# ─── default_state_dict ──────────────────────────────────────────────────────


def test_default_state_dict_has_required_keys():
    s = default_state_dict()
    assert "position" in s
    assert "decisions" in s
    assert "blockers" in s
    assert "session" in s
    assert "continuation" in s
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
    assert s["continuation"]["handoff"]["resume_file"] is None
    assert s["project_contract"] is None


# ─── parse_state_md ──────────────────────────────────────────────────────────


MINIMAL_STATE_MD = """\
# Research State

## Project Reference

See: GPD/PROJECT.md (updated 2026-03-01)

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


def test_ensure_state_schema_salvages_project_contract_with_top_level_extra_key():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["legacy_notes"] = "forwarded from a prior schema revision"

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert "legacy_notes" not in result["project_contract"]


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


def test_ensure_state_schema_drops_project_contract_for_malformed_list_item():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = ["bad"]

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is None


def test_ensure_state_schema_malformed_project_contract_singleton_field_preserves_valid_siblings():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": "ref-benchmark",
        "known_good_baselines": ["baseline-A"],
        "crucial_inputs": ["normalize with published convention"],
    }

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert result["project_contract"]["context_intake"]["known_good_baselines"] == ["baseline-A"]
    assert result["project_contract"]["context_intake"]["crucial_inputs"] == [
        "normalize with published convention"
    ]


def test_normalize_state_schema_surfaces_singleton_project_contract_list_drift_without_scrubbing_value():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    normalized, issues = _normalize_state_schema({"project_contract": contract})

    assert normalized["project_contract"] is not None
    assert normalized["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert any(
        'schema normalization: normalized "project_contract.context_intake.must_read_refs" because expected list, got str'
        in issue
        for issue in issues
    )


def test_ensure_state_schema_salvages_scope_list_drift_without_dropping_contract():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["scope"]["unresolved_questions"] = "not-a-list"

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
    assert result["project_contract"]["scope"]["unresolved_questions"] == ["not-a-list"]


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
            "aliases": ["not-a-list"],
            "role": "benchmark",
            "why_it_matters": "Published comparison target",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare", "cite"],
        }
    ]


def test_ensure_state_schema_ignores_nested_metadata_must_surface_without_dropping_contract():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"][0]["metadata"] = {"must_surface": "yes"}

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["references"][0]["id"] == "ref-benchmark"
    assert result["project_contract"]["references"][0]["must_surface"] is True


def test_normalize_state_schema_reports_coercive_project_contract_scalars():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["schema_version"] = True
    contract["references"][0]["must_surface"] = "yes"

    normalized, issues = _normalize_state_schema({"project_contract": contract})

    assert normalized["project_contract"] is None
    assert any("project_contract.schema_version must be the integer 1" in issue for issue in issues)
    assert any("project_contract.references.0.must_surface must be a boolean" in issue for issue in issues)
    assert any(
        'schema normalization: dropped "project_contract" because authoritative scalar fields required normalization'
        in issue
        for issue in issues
    )


def test_normalize_state_schema_salvages_partial_continuation_and_reports_unknown_keys() -> None:
    state = default_state_dict()
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "resume_file": "GPD/phases/03-analysis/canonical-handoff.md",
            "stopped_at": "Canonical stop",
            "recorded_by": "state_record_session",
        },
        "bounded_segment": {
            "resume_file": "GPD/phases/03-analysis/canonical-handoff.md",
            "segment_status": "paused",
            "segment_id": "seg-1",
            "unexpected_flag": "ignored",
        },
        "machine": {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
        "legacy_surface": {"resume_file": "legacy.md"},
    }

    normalized, issues = _normalize_state_schema(state)

    assert normalized["continuation"]["handoff"]["resume_file"] == "GPD/phases/03-analysis/canonical-handoff.md"
    assert normalized["continuation"]["handoff"]["stopped_at"] == "Canonical stop"
    assert normalized["continuation"]["machine"]["hostname"] == "builder-01"
    assert normalized["continuation"]["machine"]["platform"] == "Linux 6.1 x86_64"
    assert normalized["continuation"]["bounded_segment"] is not None
    assert normalized["continuation"]["bounded_segment"]["segment_status"] == "paused"
    assert normalized["continuation"]["bounded_segment"]["segment_id"] == "seg-1"
    assert any('schema normalization: dropped unknown "continuation.bounded_segment.unexpected_flag"' in issue for issue in issues)
    assert any('schema normalization: dropped unknown "continuation.legacy_surface"' in issue for issue in issues)


def test_normalize_state_schema_drops_project_contract_that_fails_draft_scoping_validation():
    normalized, issues = _normalize_state_schema({"project_contract": _draft_invalid_project_contract()})

    assert normalized["project_contract"] is None
    assert any(
        'schema normalization: dropped "project_contract" because contract failed draft scoping validation'
        in issue
        for issue in issues
    )
    assert any("project_contract: claim claim-benchmark references unknown reference missing-ref" in issue for issue in issues)


def test_ensure_state_schema_strips_claim_extra_keys_without_dropping_claim():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is not None
    assert result["project_contract"]["claims"] == [
        {
            "id": "claim-benchmark",
            "statement": "Recover the benchmark value within tolerance",
            "claim_kind": "other",
            "observables": ["obs-benchmark"],
            "deliverables": ["deliv-figure"],
            "acceptance_tests": ["test-benchmark"],
            "references": ["ref-benchmark"],
            "parameters": [],
            "hypotheses": [],
            "quantifiers": [],
            "conclusion_clauses": [],
            "proof_deliverables": [],
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
    assert result.warnings == []
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
    assert saved["project_contract"]["uncertainty_markers"]["weakest_anchors"] == ["Reference tolerance interpretation"]
    assert "Which diagnostic artifact should be primary?" in saved["open_questions"]


def test_state_set_project_contract_repairs_raw_blocked_payload_even_when_visible_state_matches(
    tmp_path: Path,
) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    blocked_contract = json.loads(json.dumps(contract))
    blocked_contract["claims"][0]["notes"] = "legacy drift"
    raw_state["project_contract"] = blocked_contract
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    loaded_before = load_state_json(tmp_path)
    assert loaded_before is not None
    visible_contract = loaded_before["project_contract"]
    assert isinstance(visible_contract, dict)
    assert visible_contract != blocked_contract

    result = state_set_project_contract(tmp_path, visible_contract)

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert result.updated is True
    assert persisted["project_contract"] == visible_contract
    assert "notes" not in persisted["project_contract"]["claims"][0]


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


def test_state_set_project_contract_rejects_singleton_list_drift(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is False
    assert result.reason == "Invalid project contract schema: context_intake.must_read_refs must be a list, not str"
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_state_set_project_contract_rejects_research_contract_instance_singleton_list_drift(
    tmp_path: Path,
):
    contract = ResearchContract.model_validate(
        json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    )
    object.__setattr__(
        contract.context_intake,
        "must_include_prior_outputs",
        "GPD/phases/00-baseline/00-01-SUMMARY.md",
    )
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is False
    assert (
        result.reason
        == "Invalid project contract schema: context_intake.must_include_prior_outputs must be a list, not str"
    )
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_state_set_project_contract_suppresses_serializer_warning_for_invalid_research_contract_instance(
    tmp_path: Path,
):
    contract = ResearchContract.model_validate(
        json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    )
    object.__setattr__(contract, "schema_version", "bad")
    save_state_json(tmp_path, default_state_dict())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = state_set_project_contract(tmp_path, contract)

    assert result.updated is False
    assert caught == []
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_state_set_project_contract_rejects_recoverable_schema_normalization(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is False
    assert result.reason == "Invalid project contract schema: claims.0.notes: Extra inputs are not permitted"
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_state_set_project_contract_surfaces_approved_mode_warnings_on_success(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"][0]["must_surface"] = False
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is True
    assert any("references must include at least one must_surface=true anchor" in warning for warning in result.warnings)


def test_state_set_project_contract_accepts_schema_valid_draft_with_approval_blockers(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": ["Need a concrete must-surface anchor before approval."],
        "crucial_inputs": [],
    }
    contract["references"][0]["role"] = "background"
    contract["references"][0]["must_surface"] = False
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is True
    assert any("references must include at least one must_surface=true anchor" in warning for warning in result.warnings)
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is not None
    assert saved["project_contract"]["references"][0]["role"] == "background"


def test_state_set_project_contract_rejects_whole_singleton_defaulting(tmp_path: Path):
    for field_name in ("context_intake", "approach_policy", "uncertainty_markers"):
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract[field_name] = "not-a-dict"
        save_state_json(tmp_path, default_state_dict())

        result = state_set_project_contract(tmp_path, contract)

        assert result.updated is False
        assert result.reason is not None
        assert "Invalid project contract schema:" in result.reason
        assert f"{field_name} must be an object, not str" in result.reason
        saved = load_state_json(tmp_path)
        assert saved is not None
        assert saved["project_contract"] is None


def test_state_set_project_contract_rejects_non_object_input_without_crashing(tmp_path: Path):
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, [])

    assert result.updated is False
    assert result.reason == "Invalid project contract schema: project contract must be a JSON object"
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_save_state_json_preserves_project_contract_when_singleton_list_drift_is_salvageable(
    tmp_path: Path,
):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    state["open_questions"] = ["Keep this question"]
    state["project_contract"] = contract

    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["project_contract"] is not None
    assert persisted["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert persisted["open_questions"] == ["Keep this question"]


def test_save_state_json_preserves_last_valid_backup_project_contract_when_new_write_salvages_primary_contract(
    tmp_path: Path,
):
    valid_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    initial_state = default_state_dict()
    initial_state["position"]["status"] = "Executing"
    initial_state["project_contract"] = valid_contract
    save_state_json(tmp_path, initial_state)

    invalid_contract = json.loads(json.dumps(valid_contract))
    invalid_contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    next_state = default_state_dict()
    next_state["position"]["status"] = "Paused"
    next_state["project_contract"] = invalid_contract
    save_state_json(tmp_path, next_state)

    layout = ProjectLayout(tmp_path)
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup = json.loads((layout.gpd / STATE_JSON_BACKUP_FILENAME).read_text(encoding="utf-8"))

    assert persisted["project_contract"] is not None
    assert persisted["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert backup["position"]["status"] == "Paused"
    assert backup["project_contract"] is not None
    assert backup["project_contract"]["references"][0]["id"] == "ref-benchmark"


def test_save_state_json_preserves_recoverable_warning_only_project_contract_drift(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"

    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    state["project_contract"] = contract

    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["project_contract"] is not None
    assert "notes" not in persisted["project_contract"]["claims"][0]


def test_save_state_json_reports_duplicate_and_blank_project_contract_list_members(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark", "ref-benchmark", " "]
    contract["references"][0]["required_actions"] = ["read", "read", " "]

    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    state["project_contract"] = contract

    with caplog.at_level(logging.WARNING, logger="gpd.core.state"):
        save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["project_contract"] is not None
    assert persisted["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert persisted["project_contract"]["references"][0]["required_actions"] == ["read"]
    assert any("must_read_refs.1 is a duplicate" in record.message for record in caplog.records)
    assert any("must_read_refs.2 must not be blank" in record.message for record in caplog.records)
    assert any("required_actions.1 is a duplicate" in record.message for record in caplog.records)
    assert any("required_actions.2 must not be blank" in record.message for record in caplog.records)


def test_save_state_json_drops_project_contract_that_fails_draft_scoping_validation(tmp_path: Path) -> None:
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    state["project_contract"] = _draft_invalid_project_contract()

    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["project_contract"] is None


def test_load_state_json_preserves_draft_invalid_project_contract_visibility(tmp_path: Path) -> None:
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    raw_state["project_contract"] = _draft_invalid_project_contract()
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["project_contract"] is not None
    assert loaded["project_contract"]["claims"][0]["references"] == ["missing-ref"]
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["claims"][0][
        "references"
    ] == ["missing-ref"]


def test_save_state_markdown_drops_malformed_project_contract_when_primary_contract_has_singleton_list_drift(
    tmp_path: Path,
):
    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    persisted["project_contract"] = contract
    layout.state_json.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

    md_content = layout.state_md.read_text(encoding="utf-8").replace("**Status:** Executing", "**Status:** Paused", 1)
    result = save_state_markdown(tmp_path, md_content)

    assert result["project_contract"] is None
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["project_contract"] is None
    backup = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))
    assert backup["project_contract"] is None
    assert persisted["position"]["status"] == "Paused"


def test_save_state_markdown_drops_malformed_project_contract_when_primary_contract_contains_recoverable_schema_drift(
    tmp_path: Path,
):
    valid_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    state["project_contract"] = valid_contract
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    corrupted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    corrupted["project_contract"]["context_intake"]["must_read_refs"] = "ref-benchmark"
    layout.state_json.write_text(json.dumps(corrupted, indent=2) + "\n", encoding="utf-8")

    md_content = layout.state_md.read_text(encoding="utf-8").replace("**Status:** Executing", "**Status:** Paused", 1)
    result = save_state_markdown(tmp_path, md_content)

    backup = json.loads((layout.gpd / STATE_JSON_BACKUP_FILENAME).read_text(encoding="utf-8"))

    assert result["project_contract"] is None
    assert backup["position"]["status"] == "Paused"
    assert backup["project_contract"] is None


def test_save_state_markdown_drops_malformed_primary_project_contract_with_extra_keys(
    tmp_path: Path,
) -> None:
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "warning-only drift"
    persisted["project_contract"] = contract
    layout.state_json.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

    md_content = layout.state_md.read_text(encoding="utf-8").replace("**Status:** Executing", "**Status:** Paused", 1)
    result = save_state_markdown(tmp_path, md_content)

    saved = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert result["project_contract"] is None
    assert saved["project_contract"] is None


def test_save_state_markdown_preserves_backup_project_contract_when_primary_json_is_unreadable(
    tmp_path: Path,
) -> None:
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    backup_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_state["project_contract"]["scope"]["question"] = "Recovered during markdown save"
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    layout.state_json.write_text("{not-json", encoding="utf-8")

    md_content = layout.state_md.read_text(encoding="utf-8").replace("**Status:** Executing", "**Status:** Paused", 1)
    result = save_state_markdown(tmp_path, md_content)

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))

    assert result["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == "Recovered during markdown save"
    assert persisted["project_contract"] is not None
    assert persisted["project_contract"]["scope"]["question"] == "Recovered during markdown save"
    assert persisted["position"]["status"] == "Paused"
    assert backup["project_contract"] is not None
    assert backup["project_contract"]["scope"]["question"] == "Recovered during markdown save"


def test_save_state_markdown_does_not_promote_backup_project_contract_when_primary_contract_is_blocked(
    tmp_path: Path,
):
    baseline = default_state_dict()
    baseline["position"]["status"] = "Executing"
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    broken_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = "not-an-object"
    broken_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(broken_state, indent=2) + "\n", encoding="utf-8")

    backup_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    md_content = layout.state_md.read_text(encoding="utf-8").replace("**Status:** Executing", "**Status:** Paused", 1)
    result = save_state_markdown(tmp_path, md_content)

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))

    assert result["project_contract"] is None
    assert persisted["project_contract"] is None
    assert persisted["position"]["status"] == "Paused"
    assert backup["project_contract"] is None
    assert backup["position"]["status"] == "Paused"


def test_save_state_markdown_does_not_preserve_draft_invalid_primary_project_contract(tmp_path: Path) -> None:
    baseline = default_state_dict()
    baseline["position"]["status"] = "Executing"
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    broken_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    broken_state["project_contract"] = _draft_invalid_project_contract()
    layout.state_json.write_text(json.dumps(broken_state, indent=2) + "\n", encoding="utf-8")

    md_content = layout.state_md.read_text(encoding="utf-8").replace("**Status:** Executing", "**Status:** Paused", 1)
    result = save_state_markdown(tmp_path, md_content)

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))

    assert result["project_contract"] is None
    assert persisted["project_contract"] is None
    assert persisted["position"]["status"] == "Paused"
    assert backup["project_contract"] is None


def test_load_state_json_backup_restore_preserves_project_contract_when_backup_requires_salvage(
    tmp_path: Path,
):
    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "9"
    backup_state["position"]["status"] = "Planning"
    backup_state["open_questions"] = ["Recovered from backup"]
    backup_state["project_contract"] = contract

    layout.state_json.write_text("{not-json", encoding="utf-8")
    (layout.gpd / STATE_JSON_BACKUP_FILENAME).write_text(
        json.dumps(backup_state, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["project_contract"] is not None
    assert loaded["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert loaded["position"]["current_phase"] == "9"
    assert loaded["open_questions"] == ["Recovered from backup"]

    restored = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert restored["project_contract"] is not None


def test_load_state_json_recovers_backup_only_state_when_primary_json_is_missing(tmp_path: Path) -> None:
    primary_state = default_state_dict()
    primary_state["position"]["status"] = "Executing"
    backup_state = json.loads(json.dumps(primary_state))
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_state["project_contract"]["scope"]["question"] = "Recovered from backup state"
    layout = _write_backup_only_state(tmp_path, primary_state, backup_state=backup_state)

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["project_contract"]["scope"]["question"] == "Recovered from backup state"
    assert loaded["position"]["status"] == "Executing"
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["scope"]["question"] == (
        "Recovered from backup state"
    )


def test_load_state_json_recovers_backup_continuation_when_primary_json_is_corrupted(tmp_path: Path) -> None:
    primary_state = default_state_dict()
    primary_state["session"]["last_date"] = "2026-03-29T12:00:00+00:00"
    primary_state["session"]["stopped_at"] = "Phase 03 Plan 2"
    primary_state["session"]["resume_file"] = "resume.md"
    primary_state["continuation"]["handoff"]["recorded_at"] = "2026-03-29T12:00:00+00:00"
    primary_state["continuation"]["handoff"]["stopped_at"] = "Phase 03 Plan 2"
    backup_state = json.loads(json.dumps(primary_state))
    backup_state["continuation"]["bounded_segment"] = {
        "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        "phase": "03",
        "plan": "02",
        "segment_id": "segment-03-02",
        "segment_status": "blocked",
        "waiting_for_review": True,
    }
    layout = _write_backup_only_state(tmp_path, primary_state, backup_state=backup_state)
    layout.state_json.write_text("{not-json", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["session"]["resume_file"] == "resume.md"
    assert loaded["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 2"
    assert loaded["continuation"]["bounded_segment"]["segment_id"] == "segment-03-02"
    assert loaded["continuation"]["bounded_segment"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["continuation"]["bounded_segment"]["segment_id"] == (
        "segment-03-02"
    )


def test_load_state_json_recovers_backup_continuation_when_primary_continuation_section_is_invalid(tmp_path: Path) -> None:
    primary_state = default_state_dict()
    primary_state["session"]["last_date"] = "2026-03-29T12:00:00+00:00"
    primary_state["session"]["stopped_at"] = "Legacy stop"
    primary_state["session"]["resume_file"] = "legacy.md"
    primary_state["continuation"] = []

    backup_state = default_state_dict()
    backup_state["continuation"]["handoff"].update(
        {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03 Plan 2",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        }
    )
    backup_state["continuation"]["machine"].update(
        {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        }
    )
    backup_state["continuation"]["bounded_segment"] = {
        "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        "phase": "03",
        "plan": "02",
        "segment_id": "segment-03-02",
        "segment_status": "paused",
    }
    layout = _write_backup_only_state(tmp_path, primary_state, backup_state=backup_state)
    layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 2"
    assert loaded["continuation"]["bounded_segment"]["segment_id"] == "segment-03-02"
    assert loaded["session"] == {
        "last_date": "2026-03-29T12:00:00+00:00",
        "stopped_at": "Phase 03 Plan 2",
        "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        "hostname": "builder-01",
        "platform": "Linux 6.1 x86_64",
        "last_result_id": None,
    }
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["continuation"]["bounded_segment"]["segment_id"] == "segment-03-02"
    assert persisted["session"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"


def test_load_state_json_repairs_primary_json_from_state_markdown_when_primary_is_unreadable(tmp_path: Path) -> None:
    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"
    save_state_json(tmp_path, recovered_state)
    save_state_markdown(tmp_path, generate_state_markdown(recovered_state))

    layout = ProjectLayout(tmp_path)
    layout.state_json.write_text("{not-json", encoding="utf-8")
    layout.state_json_backup.unlink(missing_ok=True)

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["position"]["current_phase"] == "05"
    assert loaded["position"]["status"] == "Executing"
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["position"]["current_phase"] == "05"


def test_load_state_json_primary_file_preserves_project_contract_when_singleton_list_drift_is_salvageable(
    tmp_path: Path,
):
    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    corrupted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    corrupted["project_contract"] = contract
    layout.state_json.write_text(json.dumps(corrupted, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["project_contract"] is not None
    assert loaded["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert loaded["position"]["current_phase"] == "2"


def test_load_state_json_preserves_recoverable_warning_only_project_contract_drift(tmp_path: Path):
    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"

    corrupted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    corrupted["project_contract"] = contract
    layout.state_json.write_text(json.dumps(corrupted, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["project_contract"] is not None
    assert "notes" not in loaded["project_contract"]["claims"][0]


def test_state_load_matches_context_progress_for_recoverably_normalized_project_contract(
    tmp_path: Path,
):
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

    state = default_state_dict()
    state["position"]["current_phase"] = "2"
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    persisted["project_contract"] = contract
    layout.state_json.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

    from gpd.core.context import init_progress

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["project_contract"] == ctx["project_contract"]
    assert loaded.project_contract_gate == ctx["project_contract_gate"]
    assert loaded.project_contract_load_info["status"] == "loaded_with_schema_normalization"
    assert loaded.project_contract_gate["authoritative"] is False
    assert loaded.project_contract_gate["repair_required"] is True
    assert ctx["project_contract_load_info"]["status"] == "loaded_with_schema_normalization"
    assert loaded.project_contract_load_info["source_path"] == ctx["project_contract_load_info"]["source_path"]
    assert {
        *loaded.project_contract_load_info["warnings"],
        *ctx["project_contract_load_info"]["warnings"],
    } == {"claims.0.notes: Extra inputs are not permitted"}
    assert loaded.project_contract_validation == ctx["project_contract_validation"]
    assert "notes" not in loaded.state["project_contract"]["claims"][0]


def test_state_load_recovers_backup_only_state_when_primary_json_is_missing(tmp_path: Path) -> None:
    primary_state = default_state_dict()
    primary_state["position"]["status"] = "Executing"
    backup_state = json.loads(json.dumps(primary_state))
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_state["project_contract"]["scope"]["question"] = "Recovered from backup state"
    layout = _write_backup_only_state(tmp_path, primary_state, backup_state=backup_state)

    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"]["scope"]["question"] == "Recovered from backup state"
    assert loaded.state["position"]["status"] == "Executing"
    assert loaded.state_exists is True
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["scope"]["question"] == (
        "Recovered from backup state"
    )


def test_state_load_and_runtime_context_keep_primary_project_contract_when_position_requires_normalization(
    tmp_path: Path,
) -> None:
    from gpd.core.context import init_progress

    primary_state = default_state_dict()
    primary_state["position"] = "stale-root"
    primary_state["project_contract"] = _project_contract_with_question("stale primary contract")

    backup_state = default_state_dict()
    backup_state["position"]["status"] = "Planning"
    backup_state["project_contract"] = _project_contract_with_question("recovered backup contract")

    save_state_json(tmp_path, backup_state)
    layout = ProjectLayout(tmp_path)
    layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["position"]["status"] == "Planning"
    assert loaded.state["project_contract"]["scope"]["question"] == "stale primary contract"
    assert ctx["project_contract"]["scope"]["question"] == "stale primary contract"
    assert loaded.project_contract_load_info["source_path"].endswith(STATE_JSON_FILENAME)
    assert ctx["project_contract_load_info"]["source_path"].endswith(STATE_JSON_FILENAME)


def test_state_load_reports_state_exists_false_when_only_unrecoverable_state_file_is_present(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{\n", encoding="utf-8")

    loaded = state_load(tmp_path)

    assert loaded.state_exists is False
    assert loaded.state == {}


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


def test_ensure_state_schema_mirrors_session_into_canonical_continuation():
    result = ensure_state_schema({
        "session": {
            "last_date": "2026-03-02T12:00:00+00:00",
            "stopped_at": "Phase 3 P2",
            "resume_file": "resume.md",
            "hostname": "builder-01",
            "platform": "Linux x86_64",
        }
    })

    assert result["continuation"]["handoff"] == {
        "recorded_at": "2026-03-02T12:00:00+00:00",
        "stopped_at": "Phase 3 P2",
        "resume_file": "resume.md",
        "recorded_by": None,
        "last_result_id": None,
    }
    assert result["continuation"]["machine"] == {
        "recorded_at": "2026-03-02T12:00:00+00:00",
        "hostname": "builder-01",
        "platform": "Linux x86_64",
    }


def test_ensure_state_schema_backfills_session_from_canonical_continuation():
    result = ensure_state_schema({
        "continuation": {
            "schema_version": 1,
            "handoff": {
                "recorded_at": "2026-03-02T12:00:00+00:00",
                "stopped_at": "Phase 4 P1",
                "resume_file": "continue.md",
            },
            "machine": {
                "recorded_at": "2026-03-02T12:00:00+00:00",
                "hostname": "builder-02",
                "platform": "macOS arm64",
            },
        }
    })

    assert result["session"] == {
        "last_date": "2026-03-02T12:00:00+00:00",
        "stopped_at": "Phase 4 P1",
        "resume_file": "continue.md",
        "hostname": "builder-02",
        "platform": "macOS arm64",
        "last_result_id": None,
    }


def test_ensure_state_schema_backfills_missing_canonical_machine_fields_from_session():
    result = ensure_state_schema(
        {
            "session": {
                "last_date": "2026-03-02T12:00:00+00:00",
                "stopped_at": "Legacy stop",
                "resume_file": "legacy.md",
                "hostname": "builder-03",
                "platform": "Linux arm64",
            },
            "continuation": {
                "schema_version": 1,
                "handoff": {
                    "recorded_at": "2026-03-04T09:15:00+00:00",
                    "stopped_at": "Canonical stop",
                    "resume_file": "canonical.md",
                },
                "machine": {},
            },
        }
    )

    assert result["continuation"]["handoff"] == {
        "recorded_at": "2026-03-04T09:15:00+00:00",
        "stopped_at": "Canonical stop",
        "resume_file": "canonical.md",
        "recorded_by": None,
        "last_result_id": None,
    }
    assert result["continuation"]["machine"] == {
        "recorded_at": "2026-03-02T12:00:00+00:00",
        "hostname": "builder-03",
        "platform": "Linux arm64",
    }
    assert result["session"] == {
        "last_date": "2026-03-04T09:15:00+00:00",
        "stopped_at": "Canonical stop",
        "resume_file": "canonical.md",
        "hostname": "builder-03",
        "platform": "Linux arm64",
        "last_result_id": None,
    }


def test_ensure_state_schema_does_not_let_session_override_canonical_continuation():
    result = ensure_state_schema(
        {
            "session": {
                "last_date": "2026-03-02T12:00:00+00:00",
                "stopped_at": "Legacy stop",
                "resume_file": "legacy.md",
                "hostname": "legacy-host",
                "platform": "LegacyOS",
            },
            "continuation": {
                "schema_version": 1,
                "handoff": {
                    "recorded_at": "2026-03-04T09:15:00+00:00",
                    "stopped_at": "Canonical stop",
                    "resume_file": "canonical.md",
                },
                "machine": {
                    "recorded_at": "2026-03-04T09:15:00+00:00",
                    "hostname": "canonical-host",
                    "platform": "CanonicalOS",
                },
            },
        }
    )

    assert result["continuation"]["handoff"]["resume_file"] == "canonical.md"
    assert result["continuation"]["machine"]["hostname"] == "canonical-host"
    assert result["session"] == {
        "last_date": "2026-03-04T09:15:00+00:00",
        "stopped_at": "Canonical stop",
        "resume_file": "canonical.md",
        "hostname": "canonical-host",
        "platform": "CanonicalOS",
        "last_result_id": None,
    }


def test_ensure_state_schema_prefers_canonical_continuation_over_conflicting_session():
    result = ensure_state_schema(
        {
            "session": {
                "last_date": "2026-03-01T09:00:00+00:00",
                "stopped_at": "Legacy stop",
                "resume_file": "legacy.md",
                "hostname": "legacy-host",
                "platform": "Legacy OS",
            },
            "continuation": {
                "schema_version": 1,
                "handoff": {
                    "recorded_at": "2026-03-02T12:00:00+00:00",
                    "stopped_at": "Phase 4 P1",
                    "resume_file": "continue.md",
                },
                "machine": {
                    "recorded_at": "2026-03-02T12:00:00+00:00",
                    "hostname": "builder-02",
                    "platform": "macOS arm64",
                },
            },
        }
    )

    assert result["continuation"]["handoff"]["resume_file"] == "continue.md"
    assert result["continuation"]["machine"]["hostname"] == "builder-02"
    assert result["session"] == {
        "last_date": "2026-03-02T12:00:00+00:00",
        "stopped_at": "Phase 4 P1",
        "resume_file": "continue.md",
        "hostname": "builder-02",
        "platform": "macOS arm64",
        "last_result_id": None,
    }


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


def test_load_state_json_coerces_integer_current_plan_without_dropping_position(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())
    layout = ProjectLayout(tmp_path)
    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))
    stored["position"] = {
        "current_phase": "03",
        "current_plan": 2,
        "status": "Executing",
        "total_plans_in_phase": 4,
    }
    layout.state_json.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["position"]["current_phase"] == "03"
    assert loaded["position"]["current_plan"] == "2"
    assert loaded["position"]["status"] == "Executing"


def test_load_state_json_coerces_integer_current_phase_without_dropping_position(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())
    layout = ProjectLayout(tmp_path)
    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))
    stored["position"] = {
        "current_phase": 3,
        "current_plan": 2,
        "status": "Executing",
        "total_phases": 10,
        "total_plans_in_phase": 4,
    }
    layout.state_json.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["position"]["current_phase"] == "3"
    assert loaded["position"]["current_plan"] == "2"
    assert loaded["position"]["status"] == "Executing"
    assert loaded["position"]["total_phases"] == 10
    assert loaded["position"]["total_plans_in_phase"] == 4


def test_state_get_rebuilds_missing_state_markdown_from_state_json(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())
    layout = ProjectLayout(tmp_path)
    layout.state_md.unlink()

    result = state_get(tmp_path)

    assert result.content is not None
    assert "# Research State" in result.content
    assert layout.state_md.exists()


def test_peek_state_json_keeps_normalized_primary_when_unrelated_section_is_schema_corrupt(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())
    layout = ProjectLayout(tmp_path)
    primary_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    primary_state["blockers"] = "not-a-list"
    layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "09"
    backup_state["position"]["status"] = "Executing"
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    loaded, issues, state_source = peek_state_json(tmp_path)

    assert loaded is not None
    assert loaded["position"]["current_phase"] is None
    assert loaded["position"]["status"] is None
    assert loaded["blockers"] == []
    assert state_source == "state.json"
    assert any('schema normalization: dropped "blockers" because expected list, got str' in issue for issue in issues)


def test_state_validate_keeps_normalized_primary_when_unrelated_section_is_schema_corrupt(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())
    layout = ProjectLayout(tmp_path)
    primary_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    primary_state["blockers"] = "not-a-list"
    layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["position"]["status"] = "Executing"
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    result = state_validate(tmp_path)

    assert result.valid is True
    assert result.integrity_status == "warning"
    assert result.state_source == "state.json"
    assert any('schema normalization: dropped "blockers" because expected list, got str' in warning for warning in result.warnings)
    assert not any("state.json root was recovered from state.json.bak" in warning for warning in result.warnings)


def test_state_snapshot_recovers_intent_marker_and_reports_current_state(tmp_path: Path) -> None:
    stale_state = default_state_dict()
    stale_state["position"]["current_phase"] = "01"

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"

    layout = _write_intent_recovery_state(tmp_path, stale_state=stale_state, recovered_state=recovered_state)
    before_state = layout.state_json.read_text(encoding="utf-8")

    snapshot = state_snapshot(tmp_path)

    assert snapshot.current_phase == "05"
    assert layout.state_json.read_text(encoding="utf-8") != before_state
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["position"]["current_phase"] == "05"
    assert not layout.state_intent.exists()


def test_load_state_json_discards_stale_intent_when_current_state_files_are_newer(tmp_path: Path) -> None:
    stale_state = default_state_dict()
    stale_state["position"]["current_phase"] = "01"

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"

    layout = _write_intent_recovery_state(tmp_path, stale_state=stale_state, recovered_state=recovered_state)
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    os.utime(json_tmp, ns=(1_000_000_000, 1_000_000_000))
    os.utime(md_tmp, ns=(1_000_000_000, 1_000_000_000))

    repaired_state = default_state_dict()
    repaired_state["position"]["current_phase"] = "09"
    repaired_state["position"]["status"] = "Paused"
    layout.state_json.write_text(json.dumps(repaired_state, indent=2) + "\n", encoding="utf-8")
    layout.state_md.write_text(generate_state_markdown(repaired_state), encoding="utf-8")
    os.utime(layout.state_json, ns=(2_000_000_000, 2_000_000_000))
    os.utime(layout.state_md, ns=(2_000_000_000, 2_000_000_000))

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["position"]["current_phase"] == "09"
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["position"]["current_phase"] == "09"
    assert not layout.state_intent.exists()
    assert not json_tmp.exists()
    assert not md_tmp.exists()


def test_peek_state_json_fallback_does_not_consume_intent_marker(tmp_path: Path) -> None:
    stale_state = default_state_dict()
    stale_state["position"]["current_phase"] = "01"

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"

    layout = _write_intent_recovery_state(tmp_path, stale_state=stale_state, recovered_state=recovered_state)
    layout.state_json.unlink()
    layout.state_json_backup.unlink()
    before_intent = layout.state_intent.read_text(encoding="utf-8")

    loaded, issues, state_source = peek_state_json(tmp_path, recover_intent=False)

    assert loaded is not None
    assert loaded["position"]["current_phase"] == "01"
    assert issues == ["state.json root was recovered from STATE.md after primary state.json was unavailable or unreadable"]
    assert state_source == "STATE.md"
    assert layout.state_intent.exists()
    assert layout.state_intent.read_text(encoding="utf-8") == before_intent


def test_mutation_snapshot_recovers_from_state_markdown_when_json_and_backup_are_unreadable(tmp_path: Path) -> None:
    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"
    save_state_json(tmp_path, recovered_state)
    save_state_markdown(tmp_path, generate_state_markdown(recovered_state))

    layout = ProjectLayout(tmp_path)
    layout.state_json.write_text("{bad json\n", encoding="utf-8")
    layout.state_json_backup.write_text("{also bad json\n", encoding="utf-8")

    loaded = _load_state_snapshot_for_mutation(tmp_path)

    assert loaded["position"]["current_phase"] == "05"
    assert loaded["position"]["status"] == "Executing"


def test_save_state_markdown_preserves_backup_project_contract_without_resurrecting_other_backup_only_json_fields(
    tmp_path: Path,
) -> None:
    baseline = default_state_dict()
    save_state_json(tmp_path, baseline)
    layout = ProjectLayout(tmp_path)

    backup_state = default_state_dict()
    backup_state["project_contract"] = _project_contract_with_question("backup-only contract")
    backup_state["session"]["resume_file"] = "backup-resume.md"
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    layout.state_json.write_text("{bad json\n", encoding="utf-8")

    md_state = default_state_dict()
    md_state["position"]["current_phase"] = "06"
    md_state["position"]["status"] = "Paused"

    result = save_state_markdown(tmp_path, generate_state_markdown(md_state))
    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))

    assert result["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == "backup-only contract"
    assert result["session"]["resume_file"] is None
    assert stored["project_contract"] is not None
    assert stored["project_contract"]["scope"]["question"] == "backup-only contract"
    assert stored["session"]["resume_file"] is None


def test_save_state_markdown_preserves_backup_continuation_without_reviving_backup_only_session_resume_file(
    tmp_path: Path,
) -> None:
    baseline = default_state_dict()
    save_state_json(tmp_path, baseline)
    layout = ProjectLayout(tmp_path)

    backup_state = default_state_dict()
    backup_state["session"]["resume_file"] = "stale-session-only.md"
    backup_state["continuation"]["handoff"].update(
        {
            "resume_file": "GPD/phases/06-analysis/.continue-here.md",
            "stopped_at": "Phase 06 Plan 2",
            "recorded_at": "2026-04-03T12:00:00+00:00",
        }
    )
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    layout.state_json.write_text("{bad json\n", encoding="utf-8")

    md_state = default_state_dict()
    md_state["position"]["current_phase"] = "06"
    md_state["position"]["status"] = "Paused"

    result = save_state_markdown(tmp_path, generate_state_markdown(md_state))
    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))

    assert result["continuation"]["handoff"]["resume_file"] == "GPD/phases/06-analysis/.continue-here.md"
    assert result["session"]["resume_file"] == "GPD/phases/06-analysis/.continue-here.md"
    assert result["session"]["stopped_at"] == "Phase 06 Plan 2"
    assert stored["continuation"]["handoff"]["resume_file"] == "GPD/phases/06-analysis/.continue-here.md"
    assert stored["session"]["resume_file"] == "GPD/phases/06-analysis/.continue-here.md"


def test_save_state_markdown_preserves_backup_project_contract_when_primary_root_is_not_an_object(
    tmp_path: Path,
) -> None:
    baseline = default_state_dict()
    save_state_json(tmp_path, baseline)
    layout = ProjectLayout(tmp_path)

    backup_state = default_state_dict()
    backup_state["project_contract"] = _project_contract_with_question("backup-only contract")
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    layout.state_json.write_text("[]\n", encoding="utf-8")

    md_state = default_state_dict()
    md_state["position"]["current_phase"] = "06"
    md_state["position"]["status"] = "Paused"

    result = save_state_markdown(tmp_path, generate_state_markdown(md_state))
    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))

    assert result["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == "backup-only contract"
    assert stored["project_contract"] is not None
    assert stored["project_contract"]["scope"]["question"] == "backup-only contract"


def test_save_state_markdown_recovers_pending_intent_before_merging_existing_state(tmp_path: Path) -> None:
    stale_state = default_state_dict()
    stale_state["position"]["current_phase"] = "01"
    stale_state["project_contract"] = _project_contract_with_question("stale contract")

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"
    recovered_state["project_contract"] = _project_contract_with_question("recovered contract")

    layout = _write_intent_recovery_state(tmp_path, stale_state=stale_state, recovered_state=recovered_state)

    md_state = default_state_dict()
    md_state["position"]["current_phase"] = "06"
    md_state["position"]["status"] = "Paused"

    result = save_state_markdown(tmp_path, generate_state_markdown(md_state))

    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))

    assert result["position"]["current_phase"] == "06"
    assert stored["position"]["current_phase"] == "06"
    assert stored["project_contract"]["scope"]["question"] == "recovered contract"
    assert not layout.state_intent.exists()


def test_state_load_persists_state_md_recovery_to_backup_and_recent_projects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))

    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir(parents=True, exist_ok=True)
    state = default_state_dict()
    state["continuation"]["handoff"].update(
        {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03 Plan 2",
            "resume_file": "NEXT.md",
            "recorded_by": "state_record_session",
        }
    )
    state["continuation"]["machine"].update(
        {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-03",
            "platform": "Linux 6.3 x86_64",
        }
    )
    layout.state_md.write_text(generate_state_markdown(state), encoding="utf-8")

    loaded = state_load(tmp_path)
    backup = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))
    index = _load_recent_projects_index()

    assert loaded.state["continuation"]["handoff"]["resume_file"] == "NEXT.md"
    assert layout.state_json.exists()
    assert layout.state_json_backup.exists()
    assert backup["continuation"]["handoff"]["resume_file"] == "NEXT.md"
    assert index.rows[0].project_root == tmp_path.resolve(strict=False).as_posix()
    assert index.rows[0].resume_file == "NEXT.md"
    assert index.rows[0].resume_target_recorded_at == "2026-03-29T12:00:00+00:00"


def test_sync_state_json_does_not_resurrect_backup_only_json_fields_when_primary_is_unreadable(tmp_path: Path) -> None:
    baseline = default_state_dict()
    save_state_json(tmp_path, baseline)
    layout = ProjectLayout(tmp_path)

    backup_state = default_state_dict()
    backup_state["project_contract"] = _project_contract_with_question("backup-only contract")
    backup_state["session"]["resume_file"] = "backup-resume.md"
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    layout.state_json.write_text("{bad json\n", encoding="utf-8")

    md_state = default_state_dict()
    md_state["position"]["current_phase"] = "07"
    md_state["position"]["status"] = "Executing"

    result = sync_state_json(tmp_path, generate_state_markdown(md_state))
    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))

    assert result["project_contract"] is None
    assert result["session"]["resume_file"] is None
    assert stored["project_contract"] is None
    assert stored["session"]["resume_file"] is None


def test_state_set_project_contract_does_not_fall_back_to_persisting_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_state_json(tmp_path, default_state_dict())
    contract = _project_contract_with_question("safe contract write")

    def _unexpected_loader(_cwd: Path) -> dict[str, object]:
        raise AssertionError("legacy persisting loader should not be used")

    monkeypatch.setattr("gpd.core.state.load_state_json", _unexpected_loader)

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is True
    stored = json.loads((tmp_path / "GPD" / "state.json").read_text(encoding="utf-8"))
    assert stored["project_contract"]["scope"]["question"] == "safe contract write"


def test_state_set_project_contract_recovers_intent_under_state_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_state_json(tmp_path, default_state_dict())
    contract = _project_contract_with_question("locked contract write")
    observed_lock_states: list[bool] = []
    original_recover_intent = state_module._recover_intent_locked

    def _record_recover_intent(cwd: Path) -> None:
        lock_path = (cwd / "GPD" / "state.json").with_suffix(".json.lock")
        observed_lock_states.append(lock_path.exists())
        original_recover_intent(cwd)

    monkeypatch.setattr(state_module, "_recover_intent_locked", _record_recover_intent)

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is True
    assert observed_lock_states
    assert all(observed_lock_states)


def test_sync_state_json_recovers_pending_intent_before_merging_markdown(tmp_path: Path) -> None:
    stale_state = default_state_dict()
    stale_state["position"]["current_phase"] = "01"
    stale_state["project_contract"] = _project_contract_with_question("stale contract")

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"
    recovered_state["project_contract"] = _project_contract_with_question("recovered contract")

    layout = _write_intent_recovery_state(tmp_path, stale_state=stale_state, recovered_state=recovered_state)

    md_state = default_state_dict()
    md_state["position"]["current_phase"] = "07"
    md_state["position"]["status"] = "Executing"

    result = sync_state_json(tmp_path, generate_state_markdown(md_state))

    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))

    assert result["position"]["current_phase"] == "07"
    assert stored["position"]["current_phase"] == "07"
    assert stored["project_contract"]["scope"]["question"] == "recovered contract"
    assert not layout.state_intent.exists()


def test_load_state_json_review_blocks_on_schema_normalization(tmp_path):
    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir(parents=True, exist_ok=True)
    layout.state_json.write_text(json.dumps({"position": {"status": 42}}), encoding="utf-8")

    assert load_state_json(tmp_path, integrity_mode="review") is None


def test_state_validate_review_surfaces_parse_errors_instead_of_not_found(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())
    layout = ProjectLayout(tmp_path)
    layout.state_json_backup.unlink()
    layout.state_json.write_text("{bad json\n", encoding="utf-8")

    result = state_validate(tmp_path, integrity_mode="review")

    assert any("state.json parse error:" in issue for issue in result.issues)
    assert not any("state.json not found" in issue for issue in result.issues)


def test_state_validate_review_surfaces_structural_errors_instead_of_not_found(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())
    layout = ProjectLayout(tmp_path)
    layout.state_json_backup.unlink()
    layout.state_json.write_text("[]\n", encoding="utf-8")

    result = state_validate(tmp_path, integrity_mode="review")

    assert any("state.json structural error: state root must be an object, got list" in issue for issue in result.issues)
    assert not any("state.json not found" in issue for issue in result.issues)

    standard = load_state_json(tmp_path, integrity_mode="standard")
    assert standard is not None
    assert standard["position"]["status"] is None


def test_state_load_standard_surfaces_schema_normalization_for_malformed_verification_records(tmp_path):
    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir(parents=True, exist_ok=True)
    layout.state_json.write_text(
        json.dumps(
            {
                "intermediate_results": [
                    {
                        "id": "R-02b",
                        "description": "Broken stored evidence",
                        "depends_on": [],
                        "verified": True,
                        "verification_records": ["oops"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = state_load(tmp_path, integrity_mode="standard")

    assert loaded.state["intermediate_results"][0]["verification_records"] == []
    assert any(
        'schema normalization: dropped "intermediate_results[0].verification_records[0]" because expected object, got str'
        in issue
        for issue in loaded.integrity_issues
    )
    assert any("verified=true but no verification_records present" in issue for issue in loaded.integrity_issues)


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


def test_state_validate_standard_warns_when_project_contract_lacks_must_surface_anchor_but_has_other_grounding(
    tmp_path,
):
    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"][0]["must_surface"] = False
    state["project_contract"] = contract
    save_state_json(tmp_path, state)

    result = state_validate(tmp_path)

    assert result.valid is True
    assert result.integrity_mode == "standard"
    assert result.integrity_status == "warning"
    assert any(
        "project_contract: references must include at least one must_surface=true anchor" in warning
        for warning in result.warnings
    )


def test_state_validate_standard_warns_for_project_contract_approval_blockers(tmp_path):
    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": ["Need a concrete must-surface anchor before approval."],
        "crucial_inputs": [],
    }
    contract["references"][0]["must_surface"] = False
    state["project_contract"] = contract
    save_state_json(tmp_path, state)

    result = state_validate(tmp_path)

    assert result.valid is True
    assert result.integrity_mode == "standard"
    assert result.integrity_status == "warning"
    assert any(
        "project_contract: references must include at least one must_surface=true anchor" in warning
        for warning in result.warnings
    )
    assert any(
        "project_contract: approved project contract requires at least one concrete anchor/reference/prior-output/baseline"
        in warning
        for warning in result.warnings
    )


def test_state_validate_review_blocks_project_contract_without_non_reference_grounding(tmp_path):
    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": ["Need a concrete must-surface anchor before approval."],
        "crucial_inputs": [],
    }
    contract["references"][0]["must_surface"] = False
    state["project_contract"] = contract
    save_state_json(tmp_path, state)

    result = state_validate(tmp_path, integrity_mode="review")

    assert result.valid is False
    assert result.integrity_mode == "review"
    assert result.integrity_status == "blocked"
    assert any(
        "project_contract: references must include at least one must_surface=true anchor" in issue
        for issue in result.issues
    )
    assert any(
        "project_contract: approved project contract requires at least one concrete anchor/reference/prior-output/baseline"
        in issue
        for issue in result.issues
    )


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


def test_state_validate_matches_load_for_recoverable_project_contract_warning_drift(tmp_path):
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    persisted["project_contract"] = contract
    layout.state_json.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)
    validation = state_validate(tmp_path)

    assert loaded is not None
    assert loaded["project_contract"] is not None
    assert "notes" not in loaded["project_contract"]["claims"][0]
    assert validation.valid is True
    assert any("claims.0.notes" in warning for warning in validation.warnings)


def test_state_load_surfaces_standard_mode_warnings(tmp_path: Path) -> None:
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "harmless"

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    persisted["project_contract"] = contract
    layout.state_json.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)

    assert loaded.integrity_status == "warning"
    assert any("claims.0.notes" in issue for issue in loaded.integrity_issues)


def test_state_validate_warns_when_primary_project_contract_is_blocked(tmp_path: Path) -> None:
    baseline = default_state_dict()
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    broken_state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = "not-an-object"
    broken_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(broken_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    validation = state_validate(tmp_path)

    assert validation.valid is True
    assert validation.integrity_status == "warning"
    assert validation.state_source == "state.json"
    assert any(
        'dropped "project_contract" because contract schema required normalization' in warning
        for warning in validation.warnings
    )
    assert not any("state.json root was recovered from state.json.bak" in warning for warning in validation.warnings)


def test_state_load_recovers_backup_project_contract_when_primary_contract_is_blocked(tmp_path: Path) -> None:
    baseline = default_state_dict()
    baseline["position"]["status"] = "Executing"
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    broken_state = default_state_dict()
    broken_state["position"]["status"] = "Executing"
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"][0]["must_surface"] = "yes"
    broken_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(broken_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["position"]["status"] = "Executing"
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"] is None
    assert loaded.state_source == "state.json"
    assert any(
        "project_contract.references.0.must_surface must be a boolean"
        in issue
        for issue in loaded.integrity_issues
    )
    assert any(
        'dropped "project_contract" because authoritative scalar fields required normalization' in issue
        for issue in loaded.integrity_issues
    )
    assert not any("state.json root was recovered from state.json.bak" in issue for issue in loaded.integrity_issues)


def test_save_state_json_clears_project_contract_without_resurrecting_previous_value(tmp_path: Path) -> None:
    baseline = default_state_dict()
    baseline["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    save_state_json(tmp_path, baseline)

    cleared = default_state_dict()
    cleared["position"]["status"] = "Executing"
    save_state_json(tmp_path, cleared)

    loaded = state_load(tmp_path)
    stored = json.loads((ProjectLayout(tmp_path).state_json).read_text(encoding="utf-8"))

    assert loaded.state["project_contract"] is None
    assert stored["project_contract"] is None
    assert loaded.state_source == "state.json"


def test_state_update_progress_omits_checkpoint_files_from_result_api(tmp_path: Path) -> None:
    cwd = _bootstrap_project_with_state(tmp_path)

    result = state_update_progress(cwd)

    assert not hasattr(result, "checkpoint_files")
    assert "checkpoint_files" not in result.model_dump()


def test_state_update_progress_does_not_match_numbered_plan_with_bare_summary(tmp_path: Path) -> None:
    cwd = _bootstrap_project_with_state(tmp_path)
    phase_dir = cwd / "GPD" / "phases" / "01-alpha"
    phase_dir.mkdir()
    (phase_dir / "01-01-PLAN.md").write_text("# Plan\n", encoding="utf-8")
    (phase_dir / "SUMMARY.md").write_text("# Summary\n", encoding="utf-8")

    result = state_update_progress(cwd)

    assert result.updated is True
    assert result.total == 1
    assert result.completed == 0
    assert result.percent == 0


def test_state_update_progress_counts_standalone_plan_summary_pair(tmp_path: Path) -> None:
    cwd = _bootstrap_project_with_state(tmp_path)
    phase_dir = cwd / "GPD" / "phases" / "01-alpha"
    phase_dir.mkdir()
    (phase_dir / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
    (phase_dir / "SUMMARY.md").write_text("# Summary\n", encoding="utf-8")

    result = state_update_progress(cwd)

    assert result.updated is True
    assert result.total == 1
    assert result.completed == 1
    assert result.percent == 100


def test_state_validate_recovers_backup_when_primary_root_is_not_an_object(tmp_path: Path) -> None:
    baseline = default_state_dict()
    baseline["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    layout.state_json.write_text("[]\n", encoding="utf-8")
    layout.state_json_backup.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    validation = state_validate(tmp_path)

    assert validation.valid is True
    assert validation.integrity_status == "warning"
    assert any("state.json root was recovered from state.json.bak" in warning for warning in validation.warnings)


def test_state_validate_recovers_backup_only_state_when_primary_json_is_missing(tmp_path: Path) -> None:
    primary_state = default_state_dict()
    primary_state["position"]["status"] = "Executing"
    backup_state = json.loads(json.dumps(primary_state))
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_state["project_contract"]["scope"]["question"] = "Recovered from backup state"
    _write_backup_only_state(tmp_path, primary_state, backup_state=backup_state)

    validation = state_validate(tmp_path)

    assert validation.valid is True
    assert validation.integrity_status == "warning"
    assert not any("state.json not found" in issue for issue in validation.issues)
    assert any(
        "state.json root was recovered from state.json.bak after primary state.json was missing" in warning
        for warning in validation.warnings
    )


def test_state_validate_recovers_backup_root_without_project_contract(tmp_path: Path) -> None:
    baseline = default_state_dict()
    baseline["position"]["status"] = "Executing"
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    backup_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup_state["project_contract"] = None
    layout.state_json.write_text("[]\n", encoding="utf-8")
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    validation = state_validate(tmp_path)

    assert validation.valid is True
    assert validation.integrity_status == "warning"
    assert any("state.json root was recovered from state.json.bak" in warning for warning in validation.warnings)
    assert not any("project_contract was recovered from state.json.bak" in warning for warning in validation.warnings)


def test_state_load_recovers_backup_session_without_replacing_newer_primary_fields(
    tmp_path: Path,
) -> None:
    primary_state = default_state_dict()
    primary_state["position"]["current_phase"] = "05"
    primary_state["position"]["status"] = "Executing"
    primary_state["project_contract"] = _project_contract_with_question("newer primary contract")
    save_state_json(tmp_path, primary_state)
    save_state_markdown(tmp_path, generate_state_markdown(primary_state))
    layout = ProjectLayout(tmp_path)

    broken_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    broken_state["session"] = "bad"
    layout.state_json.write_text(json.dumps(broken_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "02"
    backup_state["position"]["status"] = "Planning"
    backup_state["session"]["resume_file"] = "backup-resume.md"
    backup_state["project_contract"] = _project_contract_with_question("backup contract")
    backup_state["project_contract"]["references"][0]["must_surface"] = "yes"
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)

    assert loaded.state["position"]["current_phase"] == "05"
    assert loaded.state["position"]["status"] == "Executing"
    assert loaded.state["project_contract"]["scope"]["question"] == "newer primary contract"
    assert loaded.state["session"]["resume_file"] == "backup-resume.md"
    assert loaded.state_source == "state.json"
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["session"]["resume_file"] == "backup-resume.md"


def test_state_load_keeps_primary_position_authoritative_when_only_position_requires_normalization(
    tmp_path: Path,
) -> None:
    primary_state = default_state_dict()
    primary_state["position"]["current_phase"] = "05"
    primary_state["position"]["status"] = "Executing"
    primary_state["project_contract"] = _project_contract_with_question("newer primary contract")
    save_state_json(tmp_path, primary_state)
    save_state_markdown(tmp_path, generate_state_markdown(primary_state))
    layout = ProjectLayout(tmp_path)

    broken_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    broken_state["position"] = []
    layout.state_json.write_text(json.dumps(broken_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "02"
    backup_state["position"]["status"] = "Planning"
    backup_state["project_contract"] = _project_contract_with_question("backup contract")
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)

    assert loaded.state["position"]["current_phase"] == "02"
    assert loaded.state["position"]["status"] == "Planning"
    assert loaded.state["project_contract"]["scope"]["question"] == "newer primary contract"
    assert loaded.state_source == "state.json"
    assert (
        "state.json position was recovered from state.json.bak after primary position required normalization"
        in loaded.integrity_issues
    )
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["position"]["current_phase"] == "02"
    assert persisted["position"]["status"] == "Planning"
    assert persisted["project_contract"]["scope"]["question"] == "newer primary contract"


def test_state_validate_keeps_warning_after_markdown_exists_for_a_non_object_state_root(tmp_path: Path) -> None:
    baseline = default_state_dict()
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    backup_state = default_state_dict()
    backup_state["position"]["status"] = "Executing"
    backup_state["blockers"] = "not-a-list"
    layout.state_json.write_text("[]\n", encoding="utf-8")
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    layout.state_md.write_text(generate_state_markdown(backup_state), encoding="utf-8")

    validation = state_validate(tmp_path)

    assert validation.valid is True
    assert validation.integrity_status == "warning"
    assert any("state.json root was recovered from state.json.bak" in warning for warning in validation.warnings)
    assert validation.issues == []


def test_state_validate_review_blocks_when_primary_project_contract_requires_blocking_normalization(
    tmp_path: Path,
) -> None:
    baseline = default_state_dict()
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    broken_state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = "not-an-object"
    broken_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(broken_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    validation = state_validate(tmp_path, integrity_mode="review")

    assert validation.valid is False
    assert validation.integrity_status == "blocked"
    assert validation.state_source == "state.json"
    assert any(
        'dropped "project_contract" because contract schema required normalization'
        in issue
        for issue in validation.issues
    )
    assert not any("state.json root was recovered from state.json.bak" in issue for issue in validation.issues)


def test_state_validate_review_blocks_when_state_root_is_recovered_from_backup_without_project_contract(
    tmp_path: Path,
) -> None:
    baseline = default_state_dict()
    baseline["position"]["status"] = "Executing"
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    backup_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    backup_state["project_contract"] = None
    layout.state_json.write_text("[]\n", encoding="utf-8")
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    validation = state_validate(tmp_path, integrity_mode="review")

    assert validation.valid is False
    assert validation.integrity_status == "blocked"
    assert any("state.json root was recovered from state.json.bak" in issue for issue in validation.issues)
    assert not any("project_contract was recovered from state.json.bak" in issue for issue in validation.issues)


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
    assert result["continuation"]["handoff"]["recorded_at"] == result["session"]["last_date"]
    assert result["continuation"]["handoff"]["stopped_at"] == result["session"]["stopped_at"]
    assert result["continuation"]["handoff"]["resume_file"] is None
    assert result["continuation"]["machine"]["recorded_at"] == result["session"]["last_date"]
    assert result["performance_metrics"]["rows"][0]["label"] == "Phase 1 P1"
    assert len(result["decisions"]) == 1
    assert len(result["blockers"]) == 1


def test_parse_state_to_json_preserves_session_last_result_id() -> None:
    content = MINIMAL_STATE_MD.replace(
        "**Resume file:** —\n",
        "**Resume file:** GPD/phases/03-analysis/.continue-here.md\n**Last result ID:** result-03\n",
    )

    result = parse_state_to_json(content)

    assert result["session"]["last_result_id"] == "result-03"
    assert result["continuation"]["handoff"]["last_result_id"] == "result-03"


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


def test_state_record_session_recovers_when_state_markdown_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    state = default_state_dict()
    state["position"]["current_phase"] = "4"
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    layout.state_md.unlink()

    result = state_record_session(tmp_path, stopped_at="Phase 4 P2", resume_file="NEXT.md")

    assert result.recorded is True
    assert layout.state_md.exists()
    repaired = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert repaired["session"]["stopped_at"] == "Phase 4 P2"
    assert repaired["continuation"]["handoff"]["resume_file"] == "NEXT.md"


def test_state_record_session_updates_recent_project_index(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    cwd = state_project_factory(tmp_path)
    result = state_record_session(cwd, stopped_at="Phase 4 P2", resume_file="NEXT.md")

    index = _load_recent_projects_index()
    row = index.rows[0]

    assert result.recorded is True
    assert _recent_projects_index_path().exists()
    assert len(index.rows) == 1
    assert row.project_root == cwd.resolve(strict=False).as_posix()
    assert row.last_session_at is not None
    assert row.last_seen_at is not None
    assert row.stopped_at == "Phase 4 P2"
    assert row.resume_file == "NEXT.md"
    assert row.resume_target_kind == "handoff"
    assert row.resume_target_recorded_at == row.last_session_at
    assert row.hostname == "builder-01"
    assert row.platform == "Linux 6.1 x86_64"
    assert row.source_kind == "continuation.handoff"
    assert row.source_session_id is None
    assert row.source_segment_id is None
    assert row.source_transition_id is None
    assert row.available is True


def test_state_record_session_without_resume_file_updates_recent_project_freshness(
    tmp_path: Path,
    state_project_factory,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    cwd = state_project_factory(tmp_path)
    result = state_record_session(cwd, stopped_at="Phase 4 P2")

    index = _load_recent_projects_index()
    row = index.rows[0]

    assert result.recorded is True
    assert row.project_root == cwd.resolve(strict=False).as_posix()
    assert row.last_session_at is not None
    assert row.last_seen_at == row.last_session_at
    assert row.resume_file is None
    assert row.resume_target_kind is None
    assert row.resume_target_recorded_at is None
    assert row.stopped_at == "Phase 4 P2"


def test_save_state_markdown_backfills_missing_canonical_machine_from_session_surface(tmp_path: Path) -> None:
    baseline = default_state_dict()
    baseline["position"]["status"] = "Executing"
    baseline["continuation"]["handoff"].update(
        {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03 Plan 2",
            "resume_file": "resume.md",
            "recorded_by": "state_record_session",
        }
    )
    save_state_json(tmp_path, baseline)

    md_content = (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8")
    md_content = md_content.replace("**Hostname:** —", "**Hostname:** builder-02")
    md_content = md_content.replace("**Platform:** —", "**Platform:** Linux x86_64")

    result = save_state_markdown(tmp_path, md_content)

    assert result["session"]["stopped_at"] == "Phase 03 Plan 2"
    assert result["session"]["resume_file"] == "resume.md"
    assert result["session"]["hostname"] == "builder-02"
    assert result["session"]["platform"] == "Linux x86_64"
    assert result["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 2"
    assert result["continuation"]["handoff"]["resume_file"] == "resume.md"
    assert result["continuation"]["machine"]["hostname"] == "builder-02"
    assert result["continuation"]["machine"]["platform"] == "Linux x86_64"


def test_save_state_json_projects_recent_project_resume_file_from_canonical_continuation(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))

    cwd = state_project_factory(tmp_path)
    resume_path = cwd / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    state["session"].update(
        {
            "last_date": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 4 P2",
            "resume_file": "session.md",
        }
    )
    state["continuation"]["handoff"].update(
        {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 4 P2",
            "resume_file": "session.md",
        }
    )
    state["continuation"]["bounded_segment"] = {
        "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        "phase": "03",
        "plan": "02",
        "segment_id": "segment-03-02",
        "segment_status": "paused",
        "transition_id": "transition-03-02",
        "last_result_id": "result-03-02",
        "source_session_id": "session-03",
        "updated_at": "2026-03-29T12:30:00+00:00",
    }

    save_state_json(cwd, state)

    index = _load_recent_projects_index()
    assert len(index.rows) == 1
    row = index.rows[0]
    assert row.project_root == cwd.resolve(strict=False).as_posix()
    assert row.resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert row.resume_target_kind == "bounded_segment"
    assert row.resume_target_recorded_at == "2026-03-29T12:30:00+00:00"
    assert row.resume_file_available is True
    assert row.resumable is True
    assert row.stopped_at == "Phase 03 Plan 02"
    assert row.source_kind == "continuation.bounded_segment"
    assert row.source_session_id == "session-03"
    assert row.source_segment_id == "segment-03-02"
    assert row.source_transition_id == "transition-03-02"
    assert row.source_recorded_at == "2026-03-29T12:30:00+00:00"
    assert row.recovery_phase == "03"
    assert row.recovery_plan == "02"


def test_save_state_json_preserves_canonical_continuation_when_session_conflicts(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    state["session"].update(
        {
            "last_date": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Legacy session stop",
            "resume_file": "legacy-session.md",
        }
    )
    state["continuation"]["handoff"].update(
        {
            "recorded_at": "2026-03-30T09:15:00+00:00",
            "stopped_at": "Canonical handoff stop",
            "resume_file": "canonical-handoff.md",
            "recorded_by": "test",
        }
    )

    save_state_json(cwd, state)

    stored = load_state_json(cwd)
    assert stored is not None
    assert stored["continuation"]["handoff"]["resume_file"] == "canonical-handoff.md"
    assert stored["continuation"]["handoff"]["stopped_at"] == "Canonical handoff stop"
    assert stored["session"]["resume_file"] == "canonical-handoff.md"
    assert stored["session"]["stopped_at"] == "Canonical handoff stop"


def test_save_state_json_normalizes_canonical_continuation_resume_paths_for_persistence(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    project_resume = cwd / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    project_resume.parent.mkdir(parents=True, exist_ok=True)
    project_resume.write_text("resume\n", encoding="utf-8")
    external_resume = tmp_path.parent / f"{tmp_path.name}-external" / "outside.md"
    external_resume.parent.mkdir(parents=True, exist_ok=True)
    external_resume.write_text("outside\n", encoding="utf-8")

    state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    state["continuation"]["handoff"].update(
        {
            "recorded_at": "2026-03-30T09:15:00+00:00",
            "stopped_at": "Canonical handoff stop",
            "resume_file": str(project_resume),
            "recorded_by": "test",
        }
    )
    state["continuation"]["bounded_segment"] = {
        "resume_file": str(external_resume),
        "phase": "03",
        "plan": "02",
        "segment_id": "segment-03-02",
        "segment_status": "paused",
        "transition_id": "transition-03-02",
        "last_result_id": "result-03-02",
        "source_session_id": "session-03",
        "updated_at": "2026-03-29T12:30:00+00:00",
    }

    save_state_json(cwd, state)

    stored = load_state_json(cwd)
    assert stored is not None
    assert stored["continuation"]["handoff"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert stored["continuation"]["bounded_segment"]["resume_file"] is None
    assert stored["session"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"


def test_save_state_markdown_does_not_override_canonical_continuation_session_mirror(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    cwd = state_project_factory(tmp_path)
    state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    state["continuation"]["handoff"].update(
        {
            "recorded_at": "2026-03-30T09:15:00+00:00",
            "stopped_at": "Canonical handoff stop",
            "resume_file": "canonical-handoff.md",
            "recorded_by": "test",
        }
    )
    save_state_json(cwd, state)

    markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
    edited_markdown = (
        markdown.replace("**Stopped at:** Canonical handoff stop", "**Stopped at:** Edited in markdown", 1)
        .replace("**Resume file:** canonical-handoff.md", "**Resume file:** edited-in-markdown.md", 1)
    )

    save_state_markdown(cwd, edited_markdown)

    stored = load_state_json(cwd)
    assert stored is not None
    assert stored["continuation"]["handoff"]["resume_file"] == "canonical-handoff.md"
    assert stored["continuation"]["handoff"]["stopped_at"] == "Canonical handoff stop"
    assert stored["session"]["resume_file"] == "canonical-handoff.md"
    assert stored["session"]["stopped_at"] == "Canonical handoff stop"

    cleared_state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    cleared_state["session"]["resume_file"] = None
    cleared_state["continuation"]["handoff"]["resume_file"] = None
    cleared_state["continuation"]["bounded_segment"] = None
    save_state_json(cwd, cleared_state)

    cleared_index = _load_recent_projects_index(tmp_path / "gpd-data")
    assert len(cleared_index.rows) == 1
    assert cleared_index.rows[0].project_root == cwd.resolve(strict=False).as_posix()
    assert cleared_index.rows[0].resume_file is None
    assert cleared_index.rows[0].resume_target_kind is None
    assert cleared_index.rows[0].resume_target_recorded_at is None
    assert cleared_index.rows[0].resume_file_available is None
    assert cleared_index.rows[0].resumable is False


def test_state_record_session_preserves_existing_recent_project_rows(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-02", "platform": "Linux 6.2 x86_64"},
    )

    cwd = state_project_factory(tmp_path)
    current_root = cwd.resolve(strict=False).as_posix()
    stale_root = (tmp_path / "missing-project").as_posix()

    index_path = _recent_projects_index_path()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "project_root": current_root,
                        "last_session_at": "2026-03-01T00:00:00+00:00",
                        "last_seen_at": "2026-03-01T00:00:00+00:00",
                        "stopped_at": "Phase 1 P1",
                        "resume_file": "old.md",
                        "hostname": "builder-01",
                        "platform": "Linux 6.1 x86_64",
                        "available": True,
                    },
                    {
                        "project_root": stale_root,
                        "last_session_at": "2026-02-01T00:00:00+00:00",
                        "last_seen_at": "2026-02-01T00:00:00+00:00",
                        "stopped_at": "Phase 0 P1",
                        "resume_file": "stale.md",
                        "hostname": "builder-old",
                        "platform": "Linux 5.15 x86_64",
                        "available": False,
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    state_record_session(cwd, stopped_at="Phase 4 P2", resume_file="NEXT.md")

    index = _load_recent_projects_index()
    row_roots = [row.project_root for row in index.rows]

    assert row_roots == [current_root, stale_root]
    assert len(index.rows) == 2
    assert index.rows[0].stopped_at == "Phase 4 P2"
    assert index.rows[0].resume_file == "NEXT.md"
    assert index.rows[0].resume_target_kind == "handoff"
    assert index.rows[0].hostname == "builder-02"
    assert index.rows[0].platform == "Linux 6.2 x86_64"
    assert index.rows[1].available is False
    assert index.rows[1].stopped_at == "Phase 0 P1"


def test_state_record_session_refreshes_recent_projects_after_index_lock_acquisition(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-02", "platform": "Linux 6.2 x86_64"},
    )

    cwd = state_project_factory(tmp_path)
    current_root = cwd.resolve(strict=False).as_posix()
    injected_root = (tmp_path / "missing-project").resolve(strict=False)
    injected_root.mkdir()
    index_path = _recent_projects_index_path()
    original_file_lock = state_module.file_lock

    @contextmanager
    def _inject_existing_row(path: Path, timeout: float = 5.0):
        if path == index_path:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "project_root": injected_root.as_posix(),
                                "last_session_at": "2026-03-01T00:00:00+00:00",
                                "last_seen_at": "2026-03-01T00:00:00+00:00",
                                "stopped_at": "Phase 1 P1",
                                "resume_file": "old.md",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            yield
            return
        with original_file_lock(path, timeout=timeout):
            yield

    monkeypatch.setattr(state_module, "file_lock", _inject_existing_row)

    state_record_session(cwd, stopped_at="Phase 4 P2", resume_file="NEXT.md")

    index = _load_recent_projects_index()

    assert [row.project_root for row in index.rows] == [current_root, injected_root.as_posix()]
    assert index.rows[0].resume_file == "NEXT.md"
    assert index.rows[1].resume_file == "old.md"


# ─── model types ─────────────────────────────────────────────────────────────


def test_research_state_model():
    state = ResearchState()
    dumped = state.model_dump()
    assert "position" in dumped
    assert "decisions" in dumped
    assert "continuation" in dumped
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
    """Create a minimal GPD/ project with STATE.md + state.json."""
    from gpd.core.state import default_state_dict, generate_state_markdown

    planning = tmp_path / "GPD"
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

    planning = tmp_path / "GPD"
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


def test_state_compact_uses_recovered_state_snapshot_when_primary_json_is_unreadable(tmp_path: Path) -> None:
    from gpd.core.constants import STATE_ARCHIVE_FILENAME
    from gpd.core.state import state_compact

    state = default_state_dict()
    state["position"]["current_phase"] = "05"
    save_state_json(tmp_path, state)
    save_state_markdown(
        tmp_path,
        "\n".join(
            [
                "# Project State",
                "",
                "### Decisions",
                "- [Phase 03] Archive me",
                "- [Phase 05] Keep me",
            ]
            + [f"filler {idx}" for idx in range(170)]
        ),
    )
    planning = tmp_path / "GPD"
    layout = ProjectLayout(tmp_path)
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "05"
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    layout.state_json.write_text("{bad json\n", encoding="utf-8")

    result = state_compact(tmp_path)

    assert result.compacted is True
    archive = (planning / STATE_ARCHIVE_FILENAME).read_text(encoding="utf-8")
    assert "Archive me" in archive
    assert "Keep me" in (planning / "STATE.md").read_text(encoding="utf-8")


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

    planning = tmp_path / "GPD"
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

    planning = tmp_path / "GPD"
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
