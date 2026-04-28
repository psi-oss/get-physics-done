"""Phase 11 assertions for the durable child-return continuation boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.commands import cmd_apply_return_updates
from gpd.core.continuation import ContinuationResumeSource, resolve_continuation
from gpd.core.return_contract import validate_gpd_return_markdown
from gpd.core.state import default_state_dict, generate_state_markdown


def _write_project_state(tmp_path: Path) -> Path:
    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    state = default_state_dict()
    (gpd_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    return gpd_dir


def _wrap_return_block(yaml_body: str) -> str:
    return f"```yaml\ngpd_return:\n{yaml_body}```\n"


def test_validate_and_apply_the_same_durable_continuation_payload(tmp_path: Path) -> None:
    gpd_dir = _write_project_state(tmp_path)
    resume_path = gpd_dir / "phases" / "01-test-phase" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    return_file = tmp_path / "durable_return.md"
    return_file.write_text(
        _wrap_return_block(
            "  status: checkpoint\n"
            "  files_written: [GPD/state.json]\n"
            "  issues: []\n"
            "  next_actions: [gpd:resume-work]\n"
            "  continuation_update:\n"
            "    handoff:\n"
            "      stopped_at: Completed phase 01\n"
            "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
            "    bounded_segment:\n"
            "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
            "      phase: \"01\"\n"
            "      plan: \"01\"\n"
            "      segment_id: seg-01\n"
            "      segment_status: paused\n"
            "      checkpoint_reason: segment_boundary\n"
        ),
        encoding="utf-8",
    )

    validation = validate_gpd_return_markdown(return_file.read_text(encoding="utf-8"))
    assert validation.passed is True
    assert validation.fields["continuation_update"]["handoff"]["stopped_at"] == "Completed phase 01"
    assert validation.fields["continuation_update"]["bounded_segment"]["segment_id"] == "seg-01"

    result = cmd_apply_return_updates(tmp_path, return_file)

    assert result.passed is True
    assert result.applied_continuation_operations == ["record_session", "set_bounded_segment"]

    updated_state = json.loads((gpd_dir / "state.json").read_text(encoding="utf-8"))
    assert updated_state["continuation"]["handoff"]["recorded_by"] == "state_record_session"
    assert updated_state["continuation"]["bounded_segment"]["segment_id"] == "seg-01"
    assert updated_state["continuation"]["bounded_segment"]["updated_at"]
    assert updated_state["continuation"]["bounded_segment"]["recorded_by"] == "apply_child_return_updates"
    projection = resolve_continuation(tmp_path, state=updated_state)
    assert projection.active_resume_file == "GPD/phases/01-test-phase/.continue-here.md"
    assert projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
    assert projection.resumable is True


def test_checkpoint_child_return_rejects_missing_continuation_update_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    gpd_dir = _write_project_state(tmp_path)
    state_path = gpd_dir / "state.json"
    state_md_path = gpd_dir / "STATE.md"
    original_state_json = state_path.read_bytes()
    original_state_md = state_md_path.read_text(encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.recent_projects import load_recent_projects_index
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "decisions": [{"phase": "01", "summary": "must not persist"}],
        }
    )

    result = applicator.apply_child_return_updates(tmp_path, envelope)

    assert result.passed is False
    assert any(
        "checkpoint returns must include continuation_update.bounded_segment.resume_file" in error
        for error in result.errors
    )
    assert state_path.read_bytes() == original_state_json
    assert state_md_path.read_text(encoding="utf-8") == original_state_md
    assert load_recent_projects_index().rows == []


def test_checkpoint_child_return_rejects_handoff_only_continuation_update_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    gpd_dir = _write_project_state(tmp_path)
    resume_path = gpd_dir / "phases" / "01-test-phase" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    state_path = gpd_dir / "state.json"
    state_md_path = gpd_dir / "STATE.md"
    original_state_json = state_path.read_bytes()
    original_state_md = state_md_path.read_text(encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.recent_projects import load_recent_projects_index
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "decisions": [{"phase": "01", "summary": "must not persist"}],
            "continuation_update": {
                "handoff": {
                    "stopped_at": "Phase 01 Plan 01",
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                },
            },
        }
    )

    result = applicator.apply_child_return_updates(tmp_path, envelope)

    assert result.passed is False
    assert any(
        "checkpoint returns must include continuation_update.bounded_segment.resume_file" in error
        for error in result.errors
    )
    assert state_path.read_bytes() == original_state_json
    assert state_md_path.read_text(encoding="utf-8") == original_state_md
    assert load_recent_projects_index().rows == []


def test_checkpoint_child_return_rejects_missing_bounded_segment_resume_file_before_mutation(
    tmp_path: Path,
) -> None:
    gpd_dir = _write_project_state(tmp_path)
    resume_path = gpd_dir / "phases" / "01-test-phase" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "decisions": [{"phase": "01", "summary": "must not persist"}],
            "continuation_update": {
                "handoff": {
                    "stopped_at": "Phase 01 Plan 01",
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                },
                "bounded_segment": {
                    "phase": "01",
                    "plan": "01",
                    "segment_id": "seg-no-resume-file",
                    "segment_status": "paused",
                },
            },
        }
    )

    result = applicator.apply_child_return_updates(tmp_path, envelope)
    stored_state = json.loads((gpd_dir / "state.json").read_text(encoding="utf-8"))
    stored_state_md = (gpd_dir / "STATE.md").read_text(encoding="utf-8")

    assert result.passed is False
    assert any(
        "checkpoint returns must include continuation_update.bounded_segment.resume_file" in error
        for error in result.errors
    )
    assert stored_state["continuation"]["handoff"]["resume_file"] is None
    assert stored_state["continuation"]["bounded_segment"] is None
    assert "must not persist" not in stored_state_md


def test_checkpoint_child_return_rejects_nonresumable_bounded_segment_status_before_mutation(
    tmp_path: Path,
) -> None:
    gpd_dir = _write_project_state(tmp_path)
    resume_path = gpd_dir / "phases" / "01-test-phase" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "decisions": [{"phase": "01", "summary": "must not persist"}],
            "continuation_update": {
                "bounded_segment": {
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                    "phase": "01",
                    "plan": "01",
                    "segment_id": "seg-active",
                    "segment_status": "active",
                },
            },
        }
    )

    result = applicator.apply_child_return_updates(tmp_path, envelope)
    stored_state = json.loads((gpd_dir / "state.json").read_text(encoding="utf-8"))
    stored_state_md = (gpd_dir / "STATE.md").read_text(encoding="utf-8")

    assert result.passed is False
    assert any("checkpoint bounded_segment.segment_status must be one of" in error for error in result.errors)
    assert stored_state["continuation"]["bounded_segment"] is None
    assert "must not persist" not in stored_state_md


def test_failed_child_return_rolls_back_recent_project_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "gpd-data"))
    gpd_dir = _write_project_state(tmp_path)
    resume_path = gpd_dir / "phases" / "01-test-phase" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.errors import StateError
    from gpd.core.recent_projects import load_recent_projects_index
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "continuation_update": {
                "handoff": {
                    "stopped_at": "Phase 01 Plan 01",
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                },
                "bounded_segment": {
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                    "phase": "01",
                    "plan": "01",
                    "segment_id": "seg-rollback",
                    "segment_status": "paused",
                },
            },
        }
    )

    def _fail_set_bounded_segment(*_args: object, **_kwargs: object):
        raise StateError("simulated continuation failure")

    monkeypatch.setattr(applicator, "state_set_continuation_bounded_segment", _fail_set_bounded_segment)

    result = applicator.apply_child_return_updates(tmp_path, envelope)
    stored_state = json.loads((gpd_dir / "state.json").read_text(encoding="utf-8"))
    recent_projects = load_recent_projects_index()

    assert result.passed is False
    assert any("set_bounded_segment: simulated continuation failure" in error for error in result.errors)
    assert stored_state["continuation"]["handoff"]["resume_file"] is None
    assert stored_state["continuation"]["bounded_segment"] is None
    assert recent_projects.rows == []


def test_failed_child_return_rolls_back_last_plan_advance_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gpd_dir = _write_project_state(tmp_path)
    state_path = gpd_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["position"]["current_phase"] = "02"
    state["position"]["current_plan"] = "3"
    state["position"]["total_plans_in_phase"] = 3
    state["position"]["status"] = "Executing"
    state["position"]["last_activity"] = "2026-03-01"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    resume_path = gpd_dir / "phases" / "02-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.errors import StateError
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "completed",
            "files_written": ["GPD/STATE.md"],
            "issues": [],
            "next_actions": ["gpd:verify-work"],
            "state_updates": {"advance_plan": True},
            "continuation_update": {
                "bounded_segment": {
                    "resume_file": "GPD/phases/02-analysis/.continue-here.md",
                    "phase": "02",
                    "plan": "03",
                    "segment_id": "seg-last-plan-rollback",
                    "segment_status": "paused",
                },
            },
        }
    )

    def _fail_set_bounded_segment(*_args: object, **_kwargs: object):
        raise StateError("simulated continuation failure")

    monkeypatch.setattr(applicator, "state_set_continuation_bounded_segment", _fail_set_bounded_segment)

    result = applicator.apply_child_return_updates(tmp_path, envelope)
    stored_state_md = (gpd_dir / "STATE.md").read_text(encoding="utf-8")
    stored_state = json.loads(state_path.read_text(encoding="utf-8"))

    assert result.passed is False
    assert any("set_bounded_segment: simulated continuation failure" in error for error in result.errors)
    assert not any("rollback skipped because file(s) changed after child-return mutation" in error for error in result.errors)
    assert "**Status:** Executing" in stored_state_md
    assert "**Last Activity:** 2026-03-01" in stored_state_md
    assert stored_state["position"]["status"] == "Executing"
    assert stored_state["position"]["last_activity"] == "2026-03-01"


def test_child_return_rejects_bounded_segment_with_unknown_last_result_id(tmp_path: Path) -> None:
    _write_project_state(tmp_path)

    from gpd.core import child_return_application as applicator
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "continuation_update": {
                "bounded_segment": {
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                    "phase": "01",
                    "plan": "01",
                    "segment_id": "seg-missing-result",
                    "segment_status": "paused",
                    "last_result_id": "missing-result",
                },
            },
        }
    )

    result = applicator.apply_child_return_updates(tmp_path, envelope)
    stored_state = json.loads((tmp_path / "GPD" / "state.json").read_text(encoding="utf-8"))

    assert result.passed is False
    assert any("set_bounded_segment" in error and "missing-result" in error for error in result.errors)
    assert stored_state["continuation"]["bounded_segment"] is None


def test_child_return_rejects_numeric_handoff_resume_file_without_clearing_existing_pointer(
    tmp_path: Path,
) -> None:
    gpd_dir = _write_project_state(tmp_path)
    state_path = gpd_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["continuation"]["handoff"]["resume_file"] = "GPD/phases/old/.continue-here.md"
    state["continuation"]["handoff"]["stopped_at"] = "old stop"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    return_file = tmp_path / "numeric_handoff.md"
    return_file.write_text(
        _wrap_return_block(
            "  status: checkpoint\n"
            "  files_written: [GPD/state.json]\n"
            "  issues: []\n"
            "  next_actions: [gpd:resume-work]\n"
            "  continuation_update:\n"
            "    handoff:\n"
            "      stopped_at: new stop\n"
            "      resume_file: 123\n"
        ),
        encoding="utf-8",
    )

    validation = validate_gpd_return_markdown(return_file.read_text(encoding="utf-8"))
    result = cmd_apply_return_updates(tmp_path, return_file)
    stored_state = json.loads(state_path.read_text(encoding="utf-8"))

    assert validation.passed is False
    assert any("resume_file must be a string or null" in error for error in validation.errors)
    assert result.passed is False
    assert stored_state["continuation"]["handoff"]["resume_file"] == "GPD/phases/old/.continue-here.md"
    assert stored_state["continuation"]["handoff"]["stopped_at"] == "old stop"


def test_child_return_rejects_numeric_bounded_segment_fields(tmp_path: Path) -> None:
    _write_project_state(tmp_path)
    payload = _wrap_return_block(
        "  status: checkpoint\n"
        "  files_written: [GPD/state.json]\n"
        "  issues: []\n"
        "  next_actions: [gpd:resume-work]\n"
        "  continuation_update:\n"
        "    bounded_segment:\n"
        "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
        "      phase: 1\n"
        "      segment_status: paused\n"
    )

    validation = validate_gpd_return_markdown(payload)

    assert validation.passed is False
    assert any("phase must be a string or null" in error for error in validation.errors)


def test_child_return_rejects_null_bounded_segment_boolean_gate(tmp_path: Path) -> None:
    _write_project_state(tmp_path)
    payload = _wrap_return_block(
        "  status: checkpoint\n"
        "  files_written: [GPD/state.json]\n"
        "  issues: []\n"
        "  next_actions: [gpd:resume-work]\n"
        "  continuation_update:\n"
        "    bounded_segment:\n"
        "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
        "      phase: \"01\"\n"
        "      segment_status: paused\n"
        "      waiting_for_review: null\n"
    )

    validation = validate_gpd_return_markdown(payload)

    assert validation.passed is False
    assert any("waiting_for_review must be a boolean when provided" in error for error in validation.errors)


def test_failed_child_return_does_not_roll_back_external_state_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gpd_dir = _write_project_state(tmp_path)
    resume_path = gpd_dir / "phases" / "01-test-phase" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.errors import StateError
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "continuation_update": {
                "handoff": {
                    "stopped_at": "Phase 01 Plan 01",
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                },
                "bounded_segment": {
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                    "phase": "01",
                    "plan": "01",
                    "segment_id": "seg-external-change",
                    "segment_status": "paused",
                },
            },
        }
    )

    def _external_change_then_fail(*_args: object, **_kwargs: object):
        state_path = gpd_dir / "state.json"
        current = json.loads(state_path.read_text(encoding="utf-8"))
        current["position"]["current_phase"] = "external-99"
        state_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        raise StateError("simulated continuation failure")

    monkeypatch.setattr(applicator, "state_set_continuation_bounded_segment", _external_change_then_fail)

    result = applicator.apply_child_return_updates(tmp_path, envelope)
    stored_state = json.loads((gpd_dir / "state.json").read_text(encoding="utf-8"))

    assert result.passed is False
    assert any("rollback skipped because file(s) changed after child-return mutation" in error for error in result.errors)
    assert stored_state["position"]["current_phase"] == "external-99"


def test_failed_child_return_rolls_back_non_stateerror_mutations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gpd_dir = _write_project_state(tmp_path)
    resume_path = gpd_dir / "phases" / "01-test-phase" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")

    from gpd.core import child_return_application as applicator
    from gpd.core.return_contract import GpdReturnEnvelope

    envelope = GpdReturnEnvelope.model_validate(
        {
            "status": "checkpoint",
            "files_written": ["GPD/state.json"],
            "issues": [],
            "next_actions": ["gpd:resume-work"],
            "decisions": [
                {
                    "phase": "01",
                    "summary": "Persist only if the full child-return apply succeeds",
                }
            ],
            "continuation_update": {
                "bounded_segment": {
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                    "phase": "01",
                    "plan": "01",
                    "segment_id": "seg-non-stateerror",
                    "segment_status": "paused",
                },
            },
        }
    )

    def _fail_set_bounded_segment(*_args: object, **_kwargs: object):
        raise OSError("simulated filesystem failure")

    monkeypatch.setattr(applicator, "state_set_continuation_bounded_segment", _fail_set_bounded_segment)

    result = applicator.apply_child_return_updates(tmp_path, envelope)
    stored_state_md = (gpd_dir / "STATE.md").read_text(encoding="utf-8")
    stored_state = json.loads((gpd_dir / "state.json").read_text(encoding="utf-8"))

    assert result.passed is False
    assert any("set_bounded_segment: simulated filesystem failure" in error for error in result.errors)
    assert "Persist only if the full child-return apply succeeds" not in stored_state_md
    assert stored_state["continuation"]["bounded_segment"] is None
