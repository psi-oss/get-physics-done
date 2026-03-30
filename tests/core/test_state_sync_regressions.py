from __future__ import annotations

import json
from pathlib import Path

import pytest

import gpd.core.state as state_module
from gpd.core.state import (
    default_state_dict,
    generate_state_markdown,
    save_state_json,
    save_state_markdown,
    state_load,
    state_update_progress,
    state_validate,
    sync_state_json_core,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def test_sync_state_json_core_uses_markdown_bullet_sections_as_authority(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "03"
    existing["position"]["status"] = "Executing"
    existing["active_calculations"] = ["stale calculation"]
    existing["intermediate_results"] = ["stale result"]
    existing["open_questions"] = ["stale question"]
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")

    markdown_state = default_state_dict()
    markdown_state["position"]["current_phase"] = "03"
    markdown_state["position"]["status"] = "Executing"
    markdown_state["active_calculations"] = ["fresh calculation"]
    markdown_state["intermediate_results"] = ["fresh result"]
    markdown_state["open_questions"] = []
    md_content = generate_state_markdown(markdown_state)

    result = sync_state_json_core(cwd, md_content)
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert result["active_calculations"] == ["fresh calculation"]
    assert result["intermediate_results"] == ["fresh result"]
    assert result["open_questions"] == []
    assert stored["active_calculations"] == ["fresh calculation"]
    assert stored["intermediate_results"] == ["fresh result"]
    assert stored["open_questions"] == []


def test_state_validate_flags_mirrored_markdown_drift_beyond_position(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    state_json = default_state_dict()
    state_json["position"]["current_phase"] = "03"
    state_json["position"]["status"] = "Executing"
    state_json["decisions"] = [{"phase": "03", "summary": "Keep cutoff fixed", "rationale": "baseline"}]
    state_json["blockers"] = ["Waiting on benchmark data"]
    state_json["open_questions"] = ["Does the fitted exponent drift?"]
    (planning / "state.json").write_text(json.dumps(state_json, indent=2), encoding="utf-8")

    state_md = default_state_dict()
    state_md["position"]["current_phase"] = "03"
    state_md["position"]["status"] = "Executing"
    state_md["decisions"] = [{"phase": "03", "summary": "Relax cutoff scan", "rationale": "new evidence"}]
    state_md["blockers"] = ["Waiting on regenerated benchmark data"]
    state_md["open_questions"] = ["Does the fitted exponent stabilize under rebinning?"]
    (planning / "STATE.md").write_text(generate_state_markdown(state_md), encoding="utf-8")

    result = state_validate(cwd)

    assert result.valid is False
    assert "decisions mismatch between state.json and STATE.md" in result.issues
    assert "blockers mismatch between state.json and STATE.md" in result.issues
    assert "open_questions mismatch between state.json and STATE.md" in result.issues


def test_sync_state_json_core_preserves_user_edits_to_structured_result_bullets(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    state = default_state_dict()
    state["position"]["current_phase"] = "03"
    state["position"]["status"] = "Executing"
    state["intermediate_results"] = [
        {
            "id": "R-03-01-editme",
            "description": "Old benchmark summary",
            "equation": "E = mc^2",
            "units": "energy",
            "validity": "v << c",
            "phase": "03",
            "depends_on": ["R-02-01-prior"],
            "verified": True,
            "verification_records": [
                {
                    "verified_at": "2026-03-13T00:00:00+00:00",
                    "method": "manual",
                    "confidence": "medium",
                }
            ],
        }
    ]
    (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    md_content = generate_state_markdown(state).replace("Old benchmark summary", "Edited benchmark summary")

    result = sync_state_json_core(cwd, md_content)
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert result["intermediate_results"][0]["description"] == "Edited benchmark summary"
    assert stored["intermediate_results"][0]["description"] == "Edited benchmark summary"
    assert len(stored["intermediate_results"][0]["verification_records"]) == 1
    assert stored["intermediate_results"][0]["verification_records"][0]["method"] == "manual"


def test_save_state_markdown_preserves_existing_project_contract_in_primary_state_json(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))

    existing_state = default_state_dict()
    existing_state["project_contract"] = contract
    (planning / "state.json").write_text(json.dumps(existing_state, indent=2), encoding="utf-8")

    markdown_state = default_state_dict()
    markdown_state["position"]["current_phase"] = "03"
    markdown_state["position"]["status"] = "Executing"
    md_content = generate_state_markdown(markdown_state)
    (planning / "STATE.md").write_text(md_content, encoding="utf-8")

    result = save_state_markdown(cwd, md_content)
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert result["project_contract"] is not None
    assert stored["project_contract"] is not None
    assert result["project_contract"]["scope"]["question"] == contract["scope"]["question"]
    assert stored["project_contract"]["scope"]["question"] == contract["scope"]["question"]
    assert stored["project_contract"]["references"][0]["id"] == contract["references"][0]["id"]


def test_sync_state_json_core_bootstrap_preserves_progress_and_metrics(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    state = default_state_dict()
    state["position"]["current_phase"] = "03"
    state["position"]["status"] = "Executing"
    state["position"]["progress_percent"] = 42
    state["project_reference"]["project_md_updated"] = "2026-03-10"
    state["performance_metrics"]["rows"] = [
        {"label": "Phase 03 P01", "duration": "12m", "tasks": "3", "files": "2"}
    ]

    result = sync_state_json_core(cwd, generate_state_markdown(state))
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert result["position"]["progress_percent"] == 42
    assert stored["position"]["progress_percent"] == 42
    assert stored["project_reference"]["project_md_updated"] == "2026-03-10"
    assert stored["performance_metrics"]["rows"] == [
        {"label": "Phase 03 P01", "duration": "12m", "tasks": "3", "files": "2"}
    ]


def test_sync_state_json_core_preserves_markdown_round_trip_sections(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)

    state = default_state_dict()
    state["position"]["current_phase"] = "03"
    state["position"]["status"] = "Executing"
    state["approximations"] = [
        {
            "name": "Hydrodynamic expansion",
            "validity_range": "Kn << 1",
            "controlling_param": "Kn",
            "current_value": "0.05",
            "status": "valid",
        }
    ]
    state["convention_lock"] = {
        "metric_signature": "-+++",
        "custom_conventions": {"branch_cut": "principal"},
    }
    state["propagated_uncertainties"] = [
        {
            "quantity": "m",
            "value": "1.00",
            "uncertainty": "0.02",
            "phase": "03",
            "method": "fit",
        }
    ]
    state["pending_todos"] = ["Verify normalization", "Check sign convention"]

    result = sync_state_json_core(cwd, generate_state_markdown(state))

    assert result["approximations"] == [
        {
            "name": "Hydrodynamic expansion",
            "validity_range": "Kn << 1",
            "controlling_param": "Kn",
            "current_value": "0.05",
            "status": "valid",
        }
    ]
    assert result["convention_lock"]["metric_signature"] == "-+++"
    assert result["convention_lock"]["custom_conventions"] == {"branch_cut": "principal"}
    assert result["propagated_uncertainties"] == [
        {
            "quantity": "m",
            "value": "1.00",
            "uncertainty": "0.02",
            "phase": "03",
            "method": "fit",
        }
    ]
    assert result["pending_todos"] == ["Verify normalization", "Check sign convention"]


def test_sync_state_json_core_preserves_structured_json_sections_when_markdown_lacks_structured_blocks(
    tmp_path: Path,
) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "03"
    existing["position"]["status"] = "Executing"
    existing["approximations"] = [
        {
            "name": "Large-N expansion",
            "validity_range": "N >> 1",
            "controlling_param": "1/N",
            "current_value": "0.1",
            "status": "valid",
        }
    ]
    existing["convention_lock"] = {"metric_signature": "-+++", "custom_conventions": {"branch_cut": "principal"}}
    existing["propagated_uncertainties"] = [
        {
            "quantity": "m",
            "value": "1.00",
            "uncertainty": "0.02",
            "phase": "03",
            "method": "fit",
        }
    ]
    existing["pending_todos"] = ["Verify normalization"]
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")

    markdown_without_structured_blocks = """\
# Research State

## Project Reference

See: GPD/PROJECT.md (updated 2026-03-08)

**Core research question:** What is the mass gap?
**Current focus:** Lattice study

## Current Position

**Current Phase:** 03
**Status:** Executing
**Progress:** [####......] 40%

## Active Calculations

None yet.

## Intermediate Results

None yet.

## Open Questions

None yet.

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |

## Accumulated Context

### Decisions

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

**Last session:** —
**Stopped at:** —
**Resume file:** —
"""

    result = sync_state_json_core(cwd, markdown_without_structured_blocks)

    assert result["approximations"] == existing["approximations"]
    assert result["convention_lock"]["metric_signature"] == "-+++"
    assert result["convention_lock"]["custom_conventions"] == {"branch_cut": "principal"}
    assert result["propagated_uncertainties"] == existing["propagated_uncertainties"]
    assert result["pending_todos"] == existing["pending_todos"]


def test_sync_state_json_core_placeholder_fields_preserve_existing_session_continuity(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "03"
    existing["position"]["status"] = "Executing"
    existing["project_reference"]["core_research_question"] = "Old question"
    existing["project_reference"]["current_focus"] = "Old focus"
    existing["session"]["last_date"] = "2026-03-01T10:00:00+00:00"
    existing["session"]["stopped_at"] = "Old stop"
    existing["session"]["resume_file"] = "resume.md"
    existing["performance_metrics"]["rows"] = [
        {"label": "Phase 03 P01", "duration": "20m", "tasks": "4", "files": "2"}
    ]
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")

    markdown_state = default_state_dict()
    markdown_state["position"]["current_phase"] = "03"
    markdown_state["position"]["status"] = "Executing"

    result = sync_state_json_core(cwd, generate_state_markdown(markdown_state))

    assert result["project_reference"]["core_research_question"] is None
    assert result["project_reference"]["current_focus"] is None
    assert result["session"]["last_date"] == "2026-03-01T10:00:00+00:00"
    assert result["session"]["stopped_at"] == "Old stop"
    assert result["session"]["resume_file"] == "resume.md"
    assert result["performance_metrics"]["rows"] == []


def test_save_state_markdown_updates_markdown_and_json_together(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "01"
    existing["position"]["status"] = "Ready to plan"
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")
    (planning / "STATE.md").write_text(generate_state_markdown(existing), encoding="utf-8")

    updated = default_state_dict()
    updated["position"]["current_phase"] = "02"
    updated["position"]["status"] = "Executing"
    md_content = generate_state_markdown(updated)

    result = save_state_markdown(cwd, md_content)
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert (planning / "STATE.md").read_text(encoding="utf-8") == md_content
    assert result["position"]["current_phase"] == "02"
    assert stored["position"]["current_phase"] == "02"
    assert stored["position"]["status"] == "Executing"


def test_sync_state_json_core_raises_and_restores_prior_files_when_backup_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"

    existing = default_state_dict()
    existing["position"]["status"] = "Executing"
    (planning / "state.json").write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    (planning / "state.json.bak").write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    updated = default_state_dict()
    updated["position"]["status"] = "Paused"
    md_content = generate_state_markdown(updated)
    real_atomic_write = state_module.atomic_write

    def failing_atomic_write(path: Path, content: str) -> None:
        if Path(path).name == "state.json.bak":
            raise OSError("backup write failed")
        real_atomic_write(path, content)

    monkeypatch.setattr(state_module, "atomic_write", failing_atomic_write)

    with pytest.raises(OSError, match="backup write failed"):
        sync_state_json_core(cwd, md_content)

    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))
    backup = json.loads((planning / "state.json.bak").read_text(encoding="utf-8"))

    assert stored["position"]["status"] == "Executing"
    assert backup["position"]["status"] == "Executing"


def test_save_state_markdown_raises_and_restores_prior_pair_when_backup_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = _bootstrap_project(tmp_path)
    existing = default_state_dict()
    existing["position"]["status"] = "Executing"
    save_state_json(cwd, existing)

    planning = cwd / "GPD"
    original_md = (planning / "STATE.md").read_text(encoding="utf-8")
    updated_md = original_md.replace("**Status:** Executing", "**Status:** Paused", 1)
    real_atomic_write = state_module.atomic_write

    def failing_atomic_write(path: Path, content: str) -> None:
        if Path(path).name == "state.json.bak":
            raise OSError("backup write failed")
        real_atomic_write(path, content)

    monkeypatch.setattr(state_module, "atomic_write", failing_atomic_write)

    with pytest.raises(OSError, match="backup write failed"):
        save_state_markdown(cwd, updated_md)

    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))
    backup = json.loads((planning / "state.json.bak").read_text(encoding="utf-8"))

    assert stored["position"]["status"] == "Executing"
    assert backup["position"]["status"] == "Executing"
    assert (planning / "STATE.md").read_text(encoding="utf-8") == original_md


def test_state_update_progress_ignores_orphan_summaries_and_caps_percent(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["total_phases"] = 2
    state["position"]["status"] = "Executing"
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

    phase_one = planning / "phases" / "01-foundations"
    phase_one.mkdir(parents=True)
    (phase_one / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_one / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    phase_two = planning / "phases" / "02-orphan-summary"
    phase_two.mkdir(parents=True)
    (phase_two / "02-SUMMARY.md").write_text("# orphan summary\n", encoding="utf-8")

    result = state_update_progress(cwd)

    assert result.updated is True
    assert result.completed == 1
    assert result.total == 1
    assert result.percent == 100
    assert not hasattr(result, "checkpoint_files")
    assert "checkpoint_files" not in result.model_dump(mode="json")
    assert not (cwd / "GPD" / "phase-checkpoints" / "01-foundations.md").exists()
    assert not (cwd / "GPD" / "CHECKPOINTS.md").exists()


def test_state_update_progress_leaves_checkpoint_shelf_artifacts_unchanged(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["total_phases"] = 2
    state["position"]["status"] = "Executing"
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

    phase_one = planning / "phases" / "01-foundations"
    phase_one.mkdir(parents=True)
    (phase_one / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_one / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    phase_two = planning / "phases" / "02-analysis"
    phase_two.mkdir(parents=True)
    (phase_two / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_two / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    checkpoint_dir = cwd / "GPD" / "phase-checkpoints"
    checkpoint_dir.mkdir()
    stale_checkpoint = checkpoint_dir / "99-old-phase.md"
    stale_checkpoint.write_text("stale checkpoint\n", encoding="utf-8")
    checkpoints_index = cwd / "GPD" / "CHECKPOINTS.md"
    checkpoints_index.write_text("stale index\n", encoding="utf-8")

    result = state_update_progress(cwd)

    assert result.updated is True
    assert result.completed == 2
    assert result.total == 2
    assert result.percent == 100
    assert not hasattr(result, "checkpoint_files")
    assert "checkpoint_files" not in result.model_dump(mode="json")
    assert not (checkpoint_dir / "01-foundations.md").exists()
    assert not (checkpoint_dir / "02-analysis.md").exists()
    assert stale_checkpoint.read_text(encoding="utf-8") == "stale checkpoint\n"
    assert stale_checkpoint.exists()
    assert checkpoints_index.read_text(encoding="utf-8") == "stale index\n"


def test_state_update_progress_counts_legacy_standalone_summary_files(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["total_phases"] = 1
    state["position"]["status"] = "Executing"
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

    phase_one = planning / "phases" / "01-foundations"
    phase_one.mkdir(parents=True)
    (phase_one / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_one / "SUMMARY.md").write_text("# legacy summary\n", encoding="utf-8")

    result = state_update_progress(cwd)

    assert result.updated is True
    assert result.total == 1
    assert result.completed == 1
    assert result.percent == 100


def test_state_validate_allows_pristine_default_convention_lock(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"
    state = default_state_dict()
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    result = state_validate(cwd)

    assert result.valid is True
    assert not any("convention_lock" in issue for issue in result.issues)
    assert not any("convention_lock" in warning for warning in result.warnings)


def test_state_load_reports_json_backed_state_as_existing_without_state_md(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / "GPD"
    state = default_state_dict()
    (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    loaded = state_load(cwd)

    assert loaded.state_exists is True
    assert loaded.state == state
    assert loaded.state_raw == ""
