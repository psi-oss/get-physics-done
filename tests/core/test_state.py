"""Tests for gpd.core.state — parse/generate round-trip, validation, defaults."""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path

import pytest

from gpd.core import state as state_module
from gpd.core.constants import STATE_JSON_BACKUP_FILENAME, ProjectLayout
from gpd.core.continuation import ContinuationBoundedSegment
from gpd.core.state import (
    _find_list_parent_loc,
    _load_recent_projects_index,
    _load_state_snapshot_for_mutation,
    _normalize_state_schema,
    _recent_projects_index_path,
    default_state_dict,
    ensure_state_schema,
    generate_state_markdown,
    load_state_json,
    parse_state_to_json,
    peek_state_json,
    save_state_json,
    save_state_markdown,
    state_get,
    state_load,
    state_record_session,
    state_set_continuation_bounded_segment,
    state_set_project_contract,
    state_snapshot,
    state_update_progress,
    state_validate,
    sync_state_json,
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


def _write_raw_state_json(tmp_path: Path, payload: dict[str, object]) -> ProjectLayout:
    layout = ProjectLayout(tmp_path)
    layout.state_json.parent.mkdir(parents=True, exist_ok=True)
    layout.state_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return layout


def _draft_invalid_project_contract() -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["references"] = ["missing-ref"]
    return contract


def _project_contract_with_question(question: str) -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["scope"]["question"] = question
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


def test_parse_state_to_json_import_legacy_session_requires_resume_relevant_fields() -> None:
    markdown = (
        "# STATE\n\n"
        "## Project\n\n"
        "**Core Research Question:** What is the benchmark?\n"
        "**Current Focus:** Recovery\n"
        "**PROJECT.md Updated:** No\n\n"
        "## Position\n\n"
        "**Current Phase:** 03\n"
        "**Current Phase Name:** Analysis\n"
        "**Total Phases:** 4\n"
        "**Current Plan:** 02\n"
        "**Total Plans in Phase:** 3\n"
        "**Status:** Executing\n"
        "**Progress:** 40%\n\n"
        "## Session Continuity\n\n"
        "**Last session:** 2026-04-01T12:00:00+00:00\n"
        "**Hostname:** legacy-host\n"
        "**Platform:** legacy-platform\n"
        "**Stopped at:** —\n"
        "**Resume file:** —\n"
        "**Last result ID:** —\n\n"
        "## Decisions\n\nNone.\n\n"
        "## Blockers\n\nNone.\n\n"
        "## Performance Metrics\n\nNone.\n\n"
        "## Active Calculations\n\nNone.\n\n"
        "## Intermediate Results\n\nNone.\n\n"
        "## Open Questions\n\nNone.\n\n"
        "## Active Approximations\n\nNone.\n\n"
        "## Convention Lock\n\nNone.\n\n"
        "## Propagated Uncertainties\n\nNone.\n\n"
        "## Pending Todos\n\nNone.\n"
    )

    parsed = parse_state_to_json(markdown, import_legacy_session=True)

    assert parsed["continuation"]["handoff"]["resume_file"] is None
    assert parsed["continuation"]["handoff"]["stopped_at"] is None
    assert parsed["continuation"]["machine"]["hostname"] is None
    assert parsed["continuation"]["machine"]["platform"] is None


def test_parse_state_to_json_import_legacy_session_keeps_real_handoff_and_machine_context() -> None:
    markdown = (
        "# STATE\n\n"
        "## Project\n\n"
        "**Core Research Question:** What is the benchmark?\n"
        "**Current Focus:** Recovery\n"
        "**PROJECT.md Updated:** No\n\n"
        "## Position\n\n"
        "**Current Phase:** 03\n"
        "**Current Phase Name:** Analysis\n"
        "**Total Phases:** 4\n"
        "**Current Plan:** 02\n"
        "**Total Plans in Phase:** 3\n"
        "**Status:** Paused\n"
        "**Progress:** 40%\n\n"
        "## Session Continuity\n\n"
        "**Last session:** 2026-04-01T12:00:00+00:00\n"
        "**Hostname:** legacy-host\n"
        "**Platform:** legacy-platform\n"
        "**Stopped at:** Phase 03 Plan 02\n"
        "**Resume file:** GPD/phases/03-analysis/.continue-here.md\n"
        "**Last result ID:** result-7\n\n"
        "## Decisions\n\nNone.\n\n"
        "## Blockers\n\nNone.\n\n"
        "## Performance Metrics\n\nNone.\n\n"
        "## Active Calculations\n\nNone.\n\n"
        "## Intermediate Results\n\nNone.\n\n"
        "## Open Questions\n\nNone.\n\n"
        "## Active Approximations\n\nNone.\n\n"
        "## Convention Lock\n\nNone.\n\n"
        "## Propagated Uncertainties\n\nNone.\n\n"
        "## Pending Todos\n\nNone.\n"
    )

    parsed = parse_state_to_json(markdown, import_legacy_session=True)

    assert parsed["continuation"]["handoff"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert parsed["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 02"
    assert parsed["continuation"]["handoff"]["last_result_id"] == "result-7"
    assert parsed["continuation"]["machine"]["hostname"] == "legacy-host"
    assert parsed["continuation"]["machine"]["platform"] == "legacy-platform"


# ─── ensure_state_schema ─────────────────────────────────────────────────────


def test_ensure_state_schema_none():
    result = ensure_state_schema(None)
    assert "position" in result
    assert "decisions" in result


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


def test_ensure_state_schema_drops_project_contract_for_malformed_list_item():
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = ["bad"]

    result = ensure_state_schema({"project_contract": contract})

    assert result["project_contract"] is None


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


def test_integrity_issue_from_contract_error_accepts_pydantic_extra_forbidden_suffix() -> None:
    issue = state_module._integrity_issue_from_contract_error(
        "legacy_notes: Extra inputs are not permitted [type=extra_forbidden]"
    )

    assert issue == 'schema normalization: dropped unknown "project_contract.legacy_notes"'


def test_normalize_state_schema_drops_project_contract_that_fails_draft_scoping_validation():
    normalized, issues = _normalize_state_schema({"project_contract": _draft_invalid_project_contract()})

    assert normalized["project_contract"] is None
    assert any(
        'schema normalization: dropped "project_contract" because contract failed draft scoping validation'
        in issue
        for issue in issues
    )
    assert any("project_contract: claim claim-benchmark references unknown reference missing-ref" in issue for issue in issues)


def test_peek_state_json_respects_project_root_for_project_contract_grounding(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    outside_prior_output = tmp_path.parent / "outside-prior-output.md"
    outside_prior_output.write_text("outside\n", encoding="utf-8")
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [str(outside_prior_output)],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": ["TBD"],
        "crucial_inputs": ["TBD"],
    }

    assert state_module.validate_project_contract(contract, project_root=None).valid is True
    rooted_validation = state_module.validate_project_contract(contract, project_root=tmp_path)
    assert rooted_validation.valid is False
    assert "context_intake must not be empty" in rooted_validation.errors

    state = default_state_dict()
    state["project_contract"] = contract
    _write_raw_state_json(tmp_path, state)

    loaded, issues, source = state_module.peek_state_json(tmp_path)

    assert loaded is not None
    assert source == "state.json"
    assert any("schema normalization: dropped \"project_contract\"" in issue for issue in issues)
    assert loaded["project_contract"] is None


def test_restore_visible_project_contract_keeps_rootless_local_prior_output_grounding_visible() -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = []
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": ["./RESULTS.md"],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }

    restored, findings = state_module._restore_visible_project_contract(
        default_state_dict(),
        contract,
    )

    assert restored["project_contract"] is not None
    assert restored["project_contract"]["context_intake"]["must_include_prior_outputs"] == ["./RESULTS.md"]
    assert findings == [
        "context_intake.must_include_prior_outputs entry requires a resolved project_root to verify artifact grounding: ./RESULTS.md"
    ]


def test_restore_visible_project_contract_keeps_rootless_local_anchor_grounding_visible() -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = []
    contract["claims"][0]["references"] = []
    contract["acceptance_tests"][0]["evidence_required"] = ["deliv-figure"]
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": ["./RESULTS.md"],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }

    restored, findings = state_module._restore_visible_project_contract(
        default_state_dict(),
        contract,
    )

    assert restored["project_contract"] is not None
    assert restored["project_contract"]["context_intake"]["user_asserted_anchors"] == ["./RESULTS.md"]
    assert findings == [
        "context_intake.user_asserted_anchors entry requires a resolved project_root to verify artifact grounding: ./RESULTS.md"
    ]


def test_restore_visible_project_contract_accepts_existing_local_prior_output_grounding_with_project_root(
    tmp_path: Path,
) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = []
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": ["./RESULTS.md"],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    (tmp_path / "RESULTS.md").write_text("result\n", encoding="utf-8")

    restored, findings = state_module._restore_visible_project_contract(
        default_state_dict(),
        contract,
        project_root=tmp_path,
    )

    assert restored["project_contract"] is not None
    assert restored["project_contract"]["context_intake"]["must_include_prior_outputs"] == ["./RESULTS.md"]
    assert findings == []


def test_restore_visible_project_contract_rejects_nested_collection_truncation() -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["parameters"] = [
        {"symbol": "alpha", "domain_or_type": ["real"], "aliases": ["alpha"]},
    ]

    restored, findings = state_module._restore_visible_project_contract(
        default_state_dict(),
        contract,
    )

    assert restored["project_contract"] is None
    assert findings == []


def test_restore_visible_project_contract_normalizes_blank_nested_proof_lists() -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["parameters"] = [{"symbol": "alpha", "aliases": ""}]
    contract["claims"][0]["hypotheses"] = [{"id": "hyp-alpha", "text": "alpha >= 0", "symbols": ""}]

    restored, findings = state_module._restore_visible_project_contract(
        default_state_dict(),
        contract,
    )

    assert restored["project_contract"] is not None
    claim = restored["project_contract"]["claims"][0]
    assert claim["parameters"][0]["aliases"] == []
    assert claim["hypotheses"][0]["symbols"] == []
    assert not any("must be a list, not str" in finding for finding in findings)


def test_state_load_keeps_visible_blocked_contract_in_state_for_rootless_local_anchor(tmp_path: Path) -> None:
    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = []
    contract["claims"][0]["references"] = []
    contract["acceptance_tests"][0]["evidence_required"] = ["deliv-figure"]
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": ["./RESULTS.md"],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    state["project_contract"] = contract
    _write_raw_state_json(tmp_path, state)

    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"] is not None
    assert loaded.state["project_contract"]["context_intake"]["user_asserted_anchors"] == ["./RESULTS.md"]
    assert loaded.project_contract_load_info["status"] == "blocked_integrity"
    assert loaded.project_contract_gate["visible"] is True
    assert loaded.project_contract_gate["authoritative"] is False


def test_load_state_json_preserves_sibling_fields_when_nested_position_field_is_invalid(tmp_path: Path) -> None:
    state = default_state_dict()
    state["position"]["current_phase"] = "3"
    state["position"]["current_phase_name"] = 42
    state["position"]["status"] = "Executing"
    state["blockers"] = ["still valid"]
    _write_raw_state_json(tmp_path, state)

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["position"]["current_phase"] == "3"
    assert loaded["position"]["current_phase_name"] is None
    assert loaded["position"]["status"] == "Executing"
    assert loaded["blockers"] == ["still valid"]


def test_normalize_state_schema_irrecoverable_reset_drops_unknown_top_level_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    validation_error = state_module.PydanticValidationError.from_exception_data(
        "ResearchState",
        [
            {
                "type": "string_type",
                "loc": ("position", "current_phase_name"),
                "msg": "Input should be a valid string",
                "input": 42,
            }
        ],
    )

    def _always_fail(*args, **kwargs):
        raise validation_error

    monkeypatch.setattr(state_module.ResearchState, "model_validate", _always_fail)

    normalized, issues = _normalize_state_schema({"custom_field": "kept"})

    assert "custom_field" not in normalized
    assert any("schema normalization: irrecoverable validation failure; reset to defaults" in issue for issue in issues)


def test_normalize_state_schema_empty_dict_emits_reset_sentinel() -> None:
    """An empty dict {} must emit the irrecoverable-reset sentinel so backup recovery triggers."""
    normalized, issues = _normalize_state_schema({})

    assert normalized["position"]["progress_percent"] == 0  # got defaults
    assert any(
        "schema normalization: irrecoverable validation failure; reset to defaults" in issue
        for issue in issues
    )


def test_normalize_state_schema_none_returns_defaults_without_issues() -> None:
    """None input (fresh project) must return clean defaults with no integrity issues."""
    normalized, issues = _normalize_state_schema(None)

    assert normalized["position"]["progress_percent"] == 0
    assert issues == []


def test_state_validate_recovers_backup_when_primary_is_empty_dict(tmp_path: Path) -> None:
    """When state.json contains {}, backup recovery must restore the valid backup."""
    baseline = default_state_dict()
    # NOTE: current_phase is intentionally left as None (the default).
    # Setting it to a phase like "07" would trigger state_validate's
    # filesystem cross-check (state.py lines 4753-4776), which verifies
    # that a matching phase directory exists under phases_dir.  In a
    # bare tmp_path that directory does not exist, so the check would
    # add an issue and make valid=False.  This test targets backup
    # recovery, not filesystem consistency, so we avoid that path.
    baseline["open_questions"] = ["Important question"]
    save_state_json(tmp_path, baseline)
    save_state_markdown(tmp_path, generate_state_markdown(baseline))
    layout = ProjectLayout(tmp_path)

    # Corrupt primary to {}, keep backup valid
    layout.state_json.write_text("{}\n", encoding="utf-8")
    layout.state_json_backup.write_text(
        json.dumps(baseline, indent=2) + "\n", encoding="utf-8"
    )

    validation = state_validate(tmp_path)

    assert validation.valid is True
    assert validation.integrity_status == "warning"
    assert any(
        "state.json root was recovered from state.json.bak" in warning
        for warning in validation.warnings
    )


def test_mutation_snapshot_graceful_fallback_when_primary_and_backup_are_empty_dict(
    tmp_path: Path,
) -> None:
    """When both state.json and state.json.bak are {}, load must not crash and must return defaults."""
    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"
    save_state_json(tmp_path, recovered_state)
    save_state_markdown(tmp_path, generate_state_markdown(recovered_state))
    layout = ProjectLayout(tmp_path)

    # Corrupt both primary and backup to {}
    layout.state_json.write_text("{}\n", encoding="utf-8")
    layout.state_json_backup.write_text("{}\n", encoding="utf-8")

    loaded = _load_state_snapshot_for_mutation(tmp_path)

    # Must not crash; both {} normalize to defaults with sentinel, but
    # backup recovery does not fire (backup also has sentinel), so the
    # primary's normalized defaults are returned as-is.
    assert isinstance(loaded, dict)
    assert "position" in loaded


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
    assert any(
        "context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact"
        in warning
        for warning in result.warnings
    )
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
    assert result.schema_reference == "templates/project-contract-schema.md"
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
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is True
    assert result.warnings


def test_state_set_project_contract_persists_schema_valid_draft_with_approval_blockers(tmp_path: Path):
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
    assert result.reason is None
    assert any(
        warning.startswith("approval blocker: references must include at least one must_surface=true anchor")
        for warning in result.warnings
    )
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is not None
    assert saved["project_contract"]["references"][0]["must_surface"] is False


def test_save_state_markdown_preserves_canonical_continuation_recorded_at_when_session_date_is_missing(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    cwd = state_project_factory(tmp_path)
    state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    state["continuation"]["handoff"]["recorded_at"] = "2026-03-30T09:15:00+00:00"
    state["continuation"]["machine"]["recorded_at"] = "2026-03-30T09:15:00+00:00"
    state["session"]["last_date"] = "2026-03-30T09:15:00+00:00"
    save_state_json(cwd, state)

    markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
    edited_markdown = markdown.replace("**Last active:** 2026-03-30T09:15:00+00:00", "**Last active:** ", 1)

    save_state_markdown(cwd, edited_markdown)

    stored = load_state_json(cwd)
    assert stored is not None
    assert stored["continuation"]["handoff"]["recorded_at"] == "2026-03-30T09:15:00+00:00"
    assert stored["continuation"]["machine"]["recorded_at"] == "2026-03-30T09:15:00+00:00"


def test_state_set_project_contract_rejects_required_singleton_shape_drift(tmp_path: Path):
    for field_name in ("context_intake", "uncertainty_markers"):
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


def test_state_set_project_contract_rejects_malformed_optional_approach_policy(tmp_path: Path):
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["approach_policy"] = "not-a-dict"
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is False
    assert result.reason is not None
    assert "Invalid project contract schema:" in result.reason
    assert "approach_policy must be an object, not str" in result.reason
    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is None


def test_state_set_project_contract_rejects_non_object_input_without_crashing(tmp_path: Path):
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, [])

    assert result.updated is False
    assert result.reason == "Invalid project contract schema: project contract must be a JSON object"
    assert result.schema_reference == "templates/project-contract-schema.md"
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


def test_save_state_json_drops_preserved_visible_project_contract_when_candidate_salvage_has_blocking_findings(
    tmp_path: Path,
) -> None:
    visible_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    preserved_raw_contract = json.loads(json.dumps(visible_contract))
    preserved_raw_contract["claims"][0]["notes"] = "visible drift"

    layout = ProjectLayout(tmp_path)
    layout.state_json.parent.mkdir(parents=True, exist_ok=True)

    raw_state = default_state_dict()
    raw_state["position"]["status"] = "Executing"
    raw_state["project_contract"] = preserved_raw_contract
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    candidate_contract = json.loads(json.dumps(visible_contract))
    bad_claim = json.loads(json.dumps(visible_contract["claims"][0]))
    bad_claim.pop("statement", None)
    candidate_contract["claims"].append(bad_claim)

    next_state = default_state_dict()
    next_state["position"]["status"] = "Paused"
    next_state["project_contract"] = candidate_contract

    save_state_json(tmp_path, next_state)

    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["project_contract"] is None


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


def test_save_state_markdown_normalizes_visible_project_contract_when_primary_contract_has_singleton_list_drift(
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

    assert result["project_contract"] is not None
    assert result["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["project_contract"] is not None
    assert persisted["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    backup = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))
    assert backup["project_contract"] is not None
    assert backup["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert persisted["position"]["status"] == "Paused"


def test_save_state_markdown_normalizes_visible_project_contract_when_primary_contract_contains_recoverable_schema_drift(
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

    assert result["project_contract"] is not None
    assert result["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert backup["position"]["status"] == "Paused"
    assert backup["project_contract"] is not None
    assert backup["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]


def test_save_state_markdown_normalizes_visible_primary_project_contract_with_extra_keys(
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
    assert result["project_contract"] is not None
    assert "notes" not in result["project_contract"]["claims"][0]
    assert saved["project_contract"] is not None
    assert "notes" not in saved["project_contract"]["claims"][0]


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


def test_save_state_markdown_preserves_visible_blocked_primary_project_contract_even_with_empty_backup(
    tmp_path: Path,
) -> None:
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

    assert result["project_contract"]["claims"][0]["references"] == ["missing-ref"]
    assert persisted["project_contract"]["claims"][0]["references"] == ["missing-ref"]
    assert persisted["position"]["status"] == "Paused"
    assert backup["project_contract"]["claims"][0]["references"] == ["missing-ref"]


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


def test_state_load_backup_recovery_does_not_promote_salvaged_backup_contract_to_authoritative_raw_state(
    tmp_path: Path,
) -> None:
    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir(parents=True, exist_ok=True)

    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "9"
    backup_state["position"]["status"] = "Planning"
    backup_state["project_contract"] = json.loads(
        (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8")
    )
    backup_state["project_contract"]["context_intake"]["must_read_refs"] = "ref-benchmark"

    layout.state_json.write_text("{not-json", encoding="utf-8")
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    first_load = state_load(tmp_path)

    assert first_load.state["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert first_load.project_contract_load_info["status"] == "loaded_with_schema_normalization"
    assert first_load.project_contract_gate["authoritative"] is False
    assert first_load.project_contract_gate["repair_required"] is True
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["context_intake"][
        "must_read_refs"
    ] == ["ref-benchmark"]

    second_load = state_load(tmp_path)

    assert second_load.state["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert second_load.project_contract_load_info["status"] == "loaded"
    assert second_load.project_contract_gate["authoritative"] is True
    assert second_load.project_contract_gate["repair_required"] is False


def test_state_load_keeps_blocked_raw_project_contract_non_authoritative_after_runtime_canonicalization(
    tmp_path: Path,
) -> None:
    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = ["benchmark-paper"]
    state["project_contract"] = contract
    _write_raw_state_json(tmp_path, state)

    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"]["context_intake"]["must_read_refs"] == ["benchmark-paper"]
    assert loaded.project_contract_load_info["status"] == "blocked_integrity"
    assert loaded.project_contract_gate["visible"] is True
    assert loaded.project_contract_gate["authoritative"] is False
    assert loaded.project_contract_gate["repair_required"] is True


def test_state_load_blocks_nested_collection_truncation_in_raw_project_contract(tmp_path: Path) -> None:
    state = default_state_dict()
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["parameters"] = [
        {"symbol": "alpha", "domain_or_type": ["real"], "aliases": ["alpha"]},
    ]
    state["project_contract"] = contract
    _write_raw_state_json(tmp_path, state)

    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"] is None
    assert loaded.project_contract_load_info["status"] == "blocked_schema"
    assert loaded.project_contract_gate["visible"] is False
    assert loaded.project_contract_gate["repair_required"] is True
    assert "claims.0.parameters.0.domain_or_type: Input should be a valid string" in loaded.project_contract_load_info["errors"]


def test_state_load_backup_restore_surfaces_project_contract_salvage_diagnostics(
    tmp_path: Path,
) -> None:
    primary_state = default_state_dict()
    primary_state["position"]["status"] = "Executing"

    backup_state = json.loads(json.dumps(primary_state))
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark", 7]
    backup_state["project_contract"] = contract

    _write_backup_only_state(tmp_path, primary_state, backup_state=backup_state)

    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert any("context_intake.must_read_refs.1" in issue for issue in loaded.integrity_issues)


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
    assert loaded["session"]["resume_file"] is None
    assert loaded["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 2"
    assert loaded["continuation"]["bounded_segment"]["segment_id"] == "segment-03-02"
    assert loaded["continuation"]["bounded_segment"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["continuation"]["bounded_segment"]["segment_id"] == "segment-03-02"
    assert persisted["session"]["resume_file"] is None


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


def test_state_load_reports_state_exists_false_when_only_unrecoverable_state_file_is_present(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{\n", encoding="utf-8")

    loaded = state_load(tmp_path)

    assert loaded.state_exists is False
    assert loaded.state == {}


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


def test_state_snapshot_does_not_recover_intent_marker_and_keeps_state_unchanged(tmp_path: Path) -> None:
    stale_state = default_state_dict()
    stale_state["position"]["current_phase"] = "01"

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"

    layout = _write_intent_recovery_state(tmp_path, stale_state=stale_state, recovered_state=recovered_state)
    before_state = layout.state_json.read_text(encoding="utf-8")

    snapshot = state_snapshot(tmp_path)

    assert snapshot.current_phase == "01"
    assert layout.state_json.read_text(encoding="utf-8") == before_state
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["position"]["current_phase"] == "01"
    assert layout.state_intent.exists()


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


def test_peek_state_json_state_md_fallback_does_not_import_legacy_session_continuation(tmp_path: Path) -> None:
    state = default_state_dict()
    state["session"]["resume_file"] = "GPD/phases/03-analysis/.continue-here.md"
    state["session"]["stopped_at"] = "2026-03-10T12:00:00+00:00"
    state["session"]["hostname"] = "legacy-host"
    state["session"]["platform"] = "legacy-platform"
    layout = ProjectLayout(tmp_path)
    layout.gpd.mkdir(parents=True, exist_ok=True)
    layout.state_md.write_text(generate_state_markdown(state), encoding="utf-8")

    resume_path = tmp_path / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    loaded, issues, state_source = peek_state_json(tmp_path, recover_intent=False)

    assert loaded is not None
    assert state_source == "STATE.md"
    assert "state.json root was recovered from STATE.md after primary state.json was unavailable or unreadable" in issues
    assert loaded["continuation"]["handoff"]["resume_file"] is None
    assert loaded["continuation"]["machine"]["hostname"] is None


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


def test_sync_state_json_preserves_backup_project_contract_without_resurrecting_other_backup_only_json_fields(
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
    md_state["position"]["current_phase"] = "07"
    md_state["position"]["status"] = "Executing"

    result = sync_state_json(tmp_path, generate_state_markdown(md_state))
    stored = json.loads(layout.state_json.read_text(encoding="utf-8"))

    assert result["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == "backup-only contract"
    assert result["session"]["resume_file"] is None
    assert stored["project_contract"] is not None
    assert stored["project_contract"]["scope"]["question"] == "backup-only contract"
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


def test_state_load_ignores_backup_only_session_without_replacing_newer_primary_fields(
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
    assert loaded.state["session"]["resume_file"] is None
    assert loaded.state["continuation"]["handoff"]["resume_file"] is None
    assert loaded.state_source == "state.json"


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


def test_state_validate_does_not_revive_legacy_session_resume_file_as_continuation_mismatch(tmp_path: Path) -> None:
    save_state_json(tmp_path, default_state_dict())

    state_md = default_state_dict()
    state_md["session"]["resume_file"] = "GPD/phases/03-analysis/.continue-here.md"
    state_md["session"]["stopped_at"] = "2026-03-10T12:00:00+00:00"
    state_md["session"]["hostname"] = "legacy-host"
    state_md["session"]["platform"] = "legacy-platform"
    layout = ProjectLayout(tmp_path)
    layout.state_md.write_text(generate_state_markdown(state_md), encoding="utf-8")

    resume_path = tmp_path / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    result = state_validate(tmp_path)

    assert "continuation mismatch between state.json and STATE.md" not in result.issues


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


def test_save_state_markdown_does_not_backfill_missing_canonical_machine_from_session_surface(tmp_path: Path) -> None:
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
    assert result["session"]["hostname"] is None
    assert result["session"]["platform"] is None
    assert result["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 2"
    assert result["continuation"]["handoff"]["resume_file"] == "resume.md"
    assert result["continuation"]["machine"]["hostname"] is None
    assert result["continuation"]["machine"]["platform"] is None


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


@pytest.mark.parametrize(
    ("case_name", "expected_reason_fragment"),
    [
        ("outside_resume_file", "portable repo-local reference"),
        ("invalid_boolean", "waiting_for_review"),
        ("unknown_key", 'dropped unknown "continuation.bounded_segment.legacy_note"'),
        ("empty", "bounded_segment must include at least one non-empty field"),
    ],
)
def test_state_set_continuation_bounded_segment_rejects_salvageable_drift(
    tmp_path: Path,
    state_project_factory,
    case_name: str,
    expected_reason_fragment: str,
) -> None:
    cwd = state_project_factory(tmp_path)
    resume_path = cwd / "GPD" / "phases" / "03-analysis" / "resume.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    payloads: dict[str, dict[str, object]] = {
        "outside_resume_file": {
            "resume_file": "../outside.md",
            "phase": "03",
            "plan": "02",
            "segment_status": "paused",
        },
        "invalid_boolean": {
            "resume_file": str(resume_path),
            "phase": "03",
            "plan": "02",
            "segment_status": "paused",
            "waiting_for_review": "yes",
        },
        "unknown_key": {
            "resume_file": str(resume_path),
            "phase": "03",
            "plan": "02",
            "segment_status": "paused",
            "legacy_note": "stale",
        },
        "empty": {},
    }
    payload = payloads[case_name]

    before = load_state_json(cwd)
    assert before is not None

    result = state_set_continuation_bounded_segment(cwd, payload)

    assert result.updated is False
    assert expected_reason_fragment in (result.reason or "")

    after = load_state_json(cwd)
    assert after == before


def test_state_set_continuation_bounded_segment_persists_strict_valid_payload(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    resume_path = cwd / "GPD" / "phases" / "03-analysis" / "resume.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    result = state_set_continuation_bounded_segment(
        cwd,
        {
            "resume_file": str(resume_path),
            "phase": "03",
            "plan": "02",
            "segment_id": "segment-03-02",
            "segment_status": "paused",
            "waiting_for_review": True,
            "updated_at": "2026-03-29T12:30:00+00:00",
        },
    )

    assert result.updated is True
    stored = load_state_json(cwd)
    assert stored is not None
    bounded_segment = stored["continuation"]["bounded_segment"]
    assert set(bounded_segment) == set(ContinuationBoundedSegment.model_fields)
    assert bounded_segment["resume_file"] == "GPD/phases/03-analysis/resume.md"
    assert bounded_segment["waiting_for_review"] is True


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
    (planning / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

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
    (planning / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

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
    (planning / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

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
    (planning / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

    md = generate_state_markdown(state)
    (planning / "STATE.md").write_text(md, encoding="utf-8")
    (planning / "state.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )

    result = state_advance_plan(tmp_path)
    assert result.advanced is False
    assert result.reason == "last_plan"
    assert result.status == "ready_for_verification"


# ---------------------------------------------------------------------------
# FULL-002 Bug B: list-element-level normalization
# ---------------------------------------------------------------------------


def test_normalize_preserves_valid_list_entries_when_one_is_malformed():
    """Bug B (FULL-002): one malformed approximation must not destroy valid siblings."""
    valid_entry = {"name": "Large-N", "validity_range": "N >> 1", "status": "valid",
                   "controlling_param": "N", "current_value": ""}
    malformed_entry = {"label": "bad", "description": "wrong schema"}  # missing required 'name'

    normalized, issues = _normalize_state_schema({
        "approximations": [valid_entry, malformed_entry],
    })

    # The valid entry must survive
    assert len(normalized["approximations"]) == 1
    assert normalized["approximations"][0]["name"] == "Large-N"
    # An integrity issue must be logged for the malformed entry
    assert any("dropped malformed list entry" in issue for issue in issues)


def test_normalize_preserves_empty_list_when_all_entries_malformed():
    """Bug B (FULL-002): all-malformed entries should leave an empty list, not delete the section.

    Regression test for stale-index collision: after removing bad_0 at index 0,
    bad_1 shifts to index 0.  Without clearing removed_validation_paths per pass,
    the shifted element's loc collides with the already-recorded loc, causing it
    to be skipped and the entire section to be removed instead.
    """
    bad_1 = {"label": "X", "description": "no name field"}
    bad_2 = {"scope": "global"}  # also missing required 'name'

    normalized, issues = _normalize_state_schema({
        "approximations": [bad_1, bad_2],
    })

    # Section must still exist as an empty list
    assert "approximations" in normalized
    assert normalized["approximations"] == []
    assert any("dropped malformed list entry" in issue for issue in issues)


def test_normalize_removes_multiple_malformed_list_entries():
    """Bug B (FULL-002): multiple malformed entries removed; valid ones survive."""
    valid_1 = {"name": "Weak coupling", "validity_range": "g << 1", "status": "valid",
               "controlling_param": "g", "current_value": "0.1"}
    valid_2 = {"name": "Planar limit", "validity_range": "N -> inf", "status": "valid",
               "controlling_param": "N", "current_value": ""}
    bad_1 = {"label": "oops"}
    bad_2 = {"scope": "UV"}

    normalized, issues = _normalize_state_schema({
        "approximations": [valid_1, bad_1, valid_2, bad_2],
    })

    assert len(normalized["approximations"]) == 2
    names = {a["name"] for a in normalized["approximations"]}
    assert names == {"Weak coupling", "Planar limit"}


def test_normalize_preserves_valid_uncertainties_when_one_is_malformed():
    """Bug B (FULL-002): same fix applies to propagated_uncertainties list."""
    valid = {"quantity": "mass", "value": "1.0 GeV", "uncertainty": "0.01 GeV",
             "phase": "1", "method": "propagation"}
    malformed = {"label": "bad"}  # missing required 'quantity'

    normalized, issues = _normalize_state_schema({
        "propagated_uncertainties": [valid, malformed],
    })

    assert len(normalized["propagated_uncertainties"]) == 1
    assert normalized["propagated_uncertainties"][0]["quantity"] == "mass"
    assert any("dropped malformed list entry" in issue for issue in issues)


def test_normalize_still_removes_top_level_section_for_non_list_errors():
    """Regression guard: non-list validation errors still go through top-level removal."""
    # 'position' is a dict (Position model), not a list. If it has a deeply invalid
    # field that can't be nested-removed, it should still be handled by the existing
    # top-level removal path.
    normalized, issues = _normalize_state_schema({
        "position": {"current_phase": [1, 2, 3]},  # current_phase expects str, not list
    })

    # Position should be reset to defaults (either dropped and re-defaulted, or
    # the string coercion path handles it). The key point: no crash, and the
    # output is valid.
    assert "position" in normalized


def test_find_list_parent_loc_returns_list_index_ancestor():
    payload = {"approximations": [{"name": "ok"}, {"label": "bad"}]}
    result = _find_list_parent_loc(payload, ("approximations", 1, "name"))
    assert result == ("approximations", 1)


def test_find_list_parent_loc_returns_none_for_non_list_path():
    payload = {"position": {"current_phase": "1"}}
    result = _find_list_parent_loc(payload, ("position", "current_phase"))
    assert result is None


def test_find_list_parent_loc_returns_none_for_missing_key():
    payload = {"approximations": [{"name": "ok"}]}
    result = _find_list_parent_loc(payload, ("missing_key", 0, "name"))
    assert result is None
