from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core import context as context_module
from gpd.core import state as state_module
from gpd.core.context import init_resume
from gpd.core.errors import StateError
from gpd.core.observability import CurrentExecutionState
from gpd.core.recent_projects import record_recent_project
from gpd.core.resume_surface import RESUME_COMPATIBILITY_ALIAS_FIELDS
from gpd.core.state import (
    parse_state_to_json,
    state_carry_forward_continuation_last_result_id,
    state_record_session,
)


def _write_current_execution(tmp_path: Path, payload: dict[str, object]) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    resume_file = payload.get("resume_file")
    if isinstance(resume_file, str) and resume_file:
        resume_path = Path(resume_file)
        if not resume_path.is_absolute():
            resume_path = tmp_path / resume_path
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
    (observability / "current-execution.json").write_text(json.dumps(payload), encoding="utf-8")


def _assert_no_resume_compat_aliases(payload: dict[str, object]) -> None:
    for key in RESUME_COMPATIBILITY_ALIAS_FIELDS:
        assert key not in payload


@pytest.fixture(autouse=True)
def _isolate_recent_project_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "data"))


def _update_state_session(
    cwd: Path,
    *,
    last_date: str | None = None,
    hostname: str,
    platform: str,
    stopped_at: str | None = None,
    resume_file: str | None,
    last_result_id: str | None = None,
) -> None:
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session"].update(
        {
            "last_date": last_date,
            "hostname": hostname,
            "platform": platform,
            "stopped_at": stopped_at,
            "resume_file": resume_file,
            "last_result_id": last_result_id,
        }
    )
    state["continuation"]["handoff"].update(
        {
            "recorded_at": last_date,
            "stopped_at": stopped_at,
            "resume_file": resume_file,
            "last_result_id": last_result_id,
            "recorded_by": "test",
        }
    )
    state["continuation"]["machine"].update(
        {
            "recorded_at": last_date,
            "hostname": hostname,
            "platform": platform,
        }
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    if isinstance(resume_file, str) and resume_file:
        resume_path = Path(resume_file)
        if not resume_path.is_absolute():
            resume_path = cwd / resume_path
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")


def _resolved_resume_result(
    ctx: dict[str, object],
    candidate: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if isinstance(candidate, dict):
        candidate_result = candidate.get("last_result")
        if isinstance(candidate_result, dict):
            return candidate_result
    active_result = ctx.get("active_resume_result")
    if isinstance(active_result, dict):
        return active_result
    return None


def test_build_resume_read_state_requires_canonical_resume_projection() -> None:
    with pytest.raises(RuntimeError, match="resume_projection missing from execution context"):
        context_module._build_resume_read_state(
            {"current_execution": {"segment_id": "seg-1"}},
            interrupted_agent_id=None,
            result_lookup_by_id={},
        )


def test_state_record_session_persists_machine_identity(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    result = state_record_session(cwd, stopped_at="Phase 03 Plan 2", resume_file="next-step.md")

    markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
    stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    reparsed = parse_state_to_json(markdown)

    assert result.recorded is True
    assert set(result.updated) >= {"Last session", "Hostname", "Platform", "Stopped at", "Resume file"}
    assert stored["session"]["hostname"] == "builder-01"
    assert stored["session"]["platform"] == "Linux 6.1 x86_64"
    assert reparsed["session"]["hostname"] == "builder-01"
    assert reparsed["session"]["platform"] == "Linux 6.1 x86_64"
    assert (
        "## Session Continuity\n\n"
        "**Last session:** " in markdown
    )
    assert (
        "**Stopped at:** Phase 03 Plan 2\n"
        "**Resume file:** next-step.md\n"
        "**Last result ID:** —\n"
        "**Hostname:** builder-01\n"
        "**Platform:** Linux 6.1 x86_64\n"
    ) in markdown


def test_state_record_session_normalizes_project_local_absolute_resume_file(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    resume_path = cwd / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    result = state_record_session(cwd, stopped_at="Paused", resume_file=str(resume_path))

    stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")

    assert result.recorded is True
    assert stored["session"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert "**Resume file:** GPD/phases/03-analysis/.continue-here.md" in markdown


def test_state_record_session_rejects_nonportable_resume_file(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    outside_resume = tmp_path.parent / f"{tmp_path.name}-outside" / "resume.md"
    outside_resume.parent.mkdir(parents=True, exist_ok=True)
    outside_resume.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    state_path = cwd / "GPD" / "state.json"
    markdown_path = cwd / "GPD" / "STATE.md"
    before_state = state_path.read_text(encoding="utf-8")
    before_markdown = markdown_path.read_text(encoding="utf-8")

    with pytest.raises(StateError, match="resume_file must be a repo-relative path inside the project root"):
        state_record_session(cwd, stopped_at="Paused", resume_file=str(outside_resume))

    assert state_path.read_text(encoding="utf-8") == before_state
    assert markdown_path.read_text(encoding="utf-8") == before_markdown


def test_state_carry_forward_continuation_last_result_id_updates_canonical_continuation_without_session_boundary(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {
            "id": "result-canonical",
            "equation": "R = A + B",
            "description": "Canonical bridge result",
            "units": "arb",
            "validity": "validated",
            "phase": "03",
            "depends_on": ["seed-result"],
            "verified": True,
            "verification_records": [],
        }
    ]
    state["session"].update(
        {
            "last_result_id": "result-legacy",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "stopped_at": "Phase 03",
        }
    )
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "stopped_at": "Phase 03",
            "last_result_id": "result-legacy",
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "recorded_by": "state_record_session",
        },
        "bounded_segment": {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "phase": "03",
            "plan": "02",
            "segment_id": "canonical-seg",
            "segment_status": "paused",
            "last_result_id": "result-legacy",
            "updated_at": "2026-03-29T12:00:00+00:00",
            "source_session_id": "sess-1",
            "recorded_by": "derived_execution_head",
        },
        "machine": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = state_carry_forward_continuation_last_result_id(cwd, "result-canonical")

    stored = json.loads(state_path.read_text(encoding="utf-8"))
    assert result.updated is True
    assert stored["continuation"]["handoff"]["last_result_id"] == "result-canonical"
    assert stored["continuation"]["bounded_segment"]["last_result_id"] == "result-canonical"
    assert stored["continuation"]["handoff"]["recorded_at"] == "2026-03-29T12:00:00+00:00"
    assert stored["continuation"]["handoff"]["recorded_by"] == "state_record_session"
    assert stored["session"]["last_result_id"] == "result-canonical"


def test_state_record_session_rejects_unknown_last_result_id_without_persisting(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    state_path = cwd / "GPD" / "state.json"
    markdown_path = cwd / "GPD" / "STATE.md"
    before_state = state_path.read_text(encoding="utf-8")
    before_markdown = markdown_path.read_text(encoding="utf-8")

    with pytest.raises(StateError, match='last_result_id "result-missing" does not match any canonical result'):
        state_record_session(
            cwd,
            stopped_at="Paused",
            resume_file="next-step.md",
            last_result_id="result-missing",
        )

    assert state_path.read_text(encoding="utf-8") == before_state
    assert markdown_path.read_text(encoding="utf-8") == before_markdown


def test_state_record_session_uses_bounded_segment_last_result_id_when_explicit_anchor_is_omitted(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    monkeypatch.setattr(
        state_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {
            "id": "result-canonical",
            "equation": "R = A + B",
            "description": "Canonical bridge result",
            "units": "arb",
            "validity": "validated",
            "phase": "03",
            "depends_on": ["seed-result"],
            "verified": True,
            "verification_records": [],
        }
    ]
    state["session"].update(
        {
            "last_result_id": "result-legacy",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "stopped_at": "Phase 03",
        }
    )
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "stopped_at": "Phase 03",
            "last_result_id": "result-legacy",
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "recorded_by": "state_record_session",
        },
        "bounded_segment": {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "phase": "03",
            "plan": "02",
            "segment_id": "canonical-seg",
            "segment_status": "paused",
            "last_result_id": "result-canonical",
            "updated_at": "2026-03-29T12:00:00+00:00",
            "source_session_id": "sess-1",
            "recorded_by": "derived_execution_head",
        },
        "machine": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = state_record_session(cwd, resume_file="next-step.md")

    markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
    stored = json.loads(state_path.read_text(encoding="utf-8"))

    assert result.recorded is True
    assert "Last result ID" in set(result.updated)
    assert stored["session"]["last_result_id"] == "result-canonical"
    assert stored["continuation"]["handoff"]["last_result_id"] == "result-canonical"
    assert stored["continuation"]["bounded_segment"]["last_result_id"] == "result-canonical"
    assert "**Last result ID:** result-canonical" in markdown


def test_init_resume_surfaces_machine_change_and_session_resume_candidate(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    _update_state_session(
        cwd,
        hostname="old-host",
        platform="Linux 5.15 x86_64",
        resume_file="GPD/phases/03-analysis/.continue-here.md",
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "new-host", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["machine_change_detected"] is True
    assert "old-host" in ctx["machine_change_notice"]
    assert "Rerun the installer" in ctx["machine_change_notice"]
    assert ctx["session_hostname"] == "old-host"
    assert ctx["session_platform"] == "Linux 5.15 x86_64"
    assert ctx["project_reentry_mode"] == "current-workspace"
    assert ctx["project_reentry_selected_candidate"] is not None
    assert ctx["project_reentry_selected_candidate"]["source"] == "current_workspace"
    assert ctx["project_reentry_selected_candidate"]["project_root"] == cwd.resolve(strict=False).as_posix()
    assert ctx["current_hostname"] == "new-host"
    assert ctx["current_platform"] == "Linux 6.1 x86_64"
    assert ctx["resume_surface_schema_version"] == 1
    assert ctx["active_bounded_segment"] is None
    assert ctx["derived_execution_head"] is None
    assert ctx["continuity_handoff_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["recorded_continuity_handoff_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["missing_continuity_handoff_file"] is None
    assert ctx["has_continuity_handoff"] is True
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
    _assert_no_resume_compat_aliases(ctx)
    assert ctx["resume_candidates"] == [
        {
            "status": "handoff",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "resumable": False,
            "kind": "continuity_handoff",
            "origin": "continuation.handoff",
            "resume_pointer": "GPD/phases/03-analysis/.continue-here.md",
        }
    ]
    assert "compat_resume_surface" not in ctx


def test_init_resume_uses_canonical_continuation_when_legacy_session_conflicts(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    canonical_resume = cwd / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    canonical_resume.parent.mkdir(parents=True, exist_ok=True)
    canonical_resume.write_text("resume\n", encoding="utf-8")
    legacy_resume = cwd / "GPD" / "phases" / "03-analysis" / "legacy.md"
    legacy_resume.write_text("resume\n", encoding="utf-8")

    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session"].update(
        {
            "last_date": "2026-03-02T12:00:00+00:00",
            "hostname": "legacy-host",
            "platform": "LegacyOS",
            "stopped_at": "Legacy stop",
            "resume_file": "GPD/phases/03-analysis/legacy.md",
        }
    )
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "recorded_at": "2026-03-04T09:15:00+00:00",
            "stopped_at": "Canonical stop",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "last_result_id": "result-canonical",
        },
        "bounded_segment": None,
        "machine": {
            "recorded_at": "2026-03-04T09:15:00+00:00",
            "hostname": "canonical-host",
            "platform": "CanonicalOS",
        },
    }
    state["intermediate_results"] = [
        {
            "id": "result-canonical",
            "equation": "R = A + B",
            "description": "Canonical bridge result",
            "units": "arb",
            "validity": "validated",
            "phase": "03",
            "depends_on": ["seed-result"],
            "verified": True,
            "verification_records": [],
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "canonical-host", "platform": "CanonicalOS"},
    )

    ctx = init_resume(cwd)

    assert ctx["session_hostname"] == "canonical-host"
    assert ctx["session_platform"] == "CanonicalOS"
    assert ctx["continuity_handoff_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["recorded_continuity_handoff_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["missing_continuity_handoff_file"] is None
    assert ctx["has_continuity_handoff"] is True
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
    assert len(ctx["resume_candidates"]) == 1
    assert ctx["resume_candidates"][0]["status"] == "handoff"
    assert ctx["resume_candidates"][0]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["resume_candidates"][0]["resumable"] is False
    assert ctx["resume_candidates"][0]["kind"] == "continuity_handoff"
    assert ctx["resume_candidates"][0]["origin"] == "continuation.handoff"
    assert ctx["resume_candidates"][0]["resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["resume_candidates"][0]["last_result_id"] == "result-canonical"
    assert "compat_resume_surface" not in ctx
    canonical_candidate = ctx["resume_candidates"][0]
    hydrated_result = _resolved_resume_result(ctx, canonical_candidate)
    assert hydrated_result is not None
    assert hydrated_result["id"] == "result-canonical"
    assert hydrated_result["equation"] == "R = A + B"
    assert hydrated_result["description"] == "Canonical bridge result"
    assert hydrated_result["phase"] == "03"


def test_init_resume_auto_selects_unique_recoverable_recent_project(tmp_path: Path, state_project_factory, monkeypatch) -> None:
    project_parent = tmp_path / "project-root"
    project_parent.mkdir()
    project_root = state_project_factory(project_parent)
    resume_path = project_root / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    workspace = tmp_path / "outside"
    workspace.mkdir()
    record_recent_project(
        project_root,
        session_data={
            "last_date": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        },
        store_root=tmp_path / "data",
    )
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "data"))

    ctx = init_resume(workspace)

    assert ctx["workspace_root"] == workspace.resolve(strict=False).as_posix()
    assert ctx["project_root"] == project_root.resolve(strict=False).as_posix()
    assert ctx["project_root_source"] == "recent_project"
    assert ctx["project_root_auto_selected"] is True
    assert ctx["project_reentry_mode"] == "auto-recent-project"
    assert ctx["project_reentry_selected_candidate"] is not None
    assert ctx["project_reentry_selected_candidate"]["source"] == "recent_project"
    assert ctx["project_reentry_selected_candidate"]["project_root"] == project_root.resolve(strict=False).as_posix()
    assert ctx["project_reentry_selected_candidate"]["resume_target_kind"] == "handoff"
    assert ctx["workspace_state_exists"] is False
    assert ctx["workspace_roadmap_exists"] is False
    assert ctx["workspace_project_exists"] is False
    assert ctx["workspace_planning_exists"] is False
    assert ctx["state_exists"] is True
    assert ctx["roadmap_exists"] is True
    assert ctx["project_exists"] is True
    assert ctx["planning_exists"] is True


def test_init_resume_promotes_auto_selected_recent_bounded_segment_over_same_pointer_handoff(
    tmp_path: Path, state_project_factory
) -> None:
    project_parent = tmp_path / "project-root"
    project_parent.mkdir()
    project_root = state_project_factory(project_parent)
    resume_file = "GPD/phases/03-analysis/.continue-here.md"
    resume_path = project_root / resume_file
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    _update_state_session(
        project_root,
        hostname="builder-01",
        platform="Linux 6.1 x86_64",
        stopped_at="Phase 03",
        resume_file=resume_file,
        last_result_id="result-recent-03",
    )
    state_path = project_root / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {
            "id": "result-recent-03",
            "equation": "R = A + B",
            "description": "Recent bounded-segment anchor",
            "phase": "03",
            "depends_on": [],
            "verified": True,
            "verification_records": [],
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    data_root = tmp_path / "data"
    record_recent_project(
        project_root,
        session_data={
            "last_date": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03",
            "resume_file": resume_file,
            "last_result_id": "result-recent-03",
            "resume_target_kind": "bounded_segment",
            "resume_target_recorded_at": "2026-03-29T12:00:00+00:00",
            "source_kind": "continuation.bounded_segment",
            "source_segment_id": "seg-recent-03",
            "source_transition_id": "transition-recent-03",
            "recovery_phase": "03",
            "recovery_plan": "01",
        },
        store_root=data_root,
    )
    workspace = tmp_path / "outside"
    workspace.mkdir()

    ctx = init_resume(workspace, data_root=data_root)

    assert ctx["project_root"] == project_root.resolve(strict=False).as_posix()
    assert ctx["project_root_source"] == "recent_project"
    assert ctx["project_root_auto_selected"] is True
    assert ctx["project_reentry_mode"] == "auto-recent-project"
    assert ctx["project_reentry_selected_candidate"] is not None
    assert ctx["project_reentry_selected_candidate"]["source"] == "recent_project"
    assert ctx["project_reentry_selected_candidate"]["resume_target_kind"] == "bounded_segment"
    assert ctx["project_reentry_selected_candidate"]["source_kind"] == "continuation.bounded_segment"
    assert ctx["project_reentry_selected_candidate"]["source_segment_id"] == "seg-recent-03"
    assert ctx["project_reentry_selected_candidate"]["source_transition_id"] == "transition-recent-03"
    assert ctx["project_reentry_selected_candidate"]["recovery_phase"] == "03"
    assert ctx["project_reentry_selected_candidate"]["recovery_plan"] == "01"
    assert ctx["active_bounded_segment"]["resume_file"] == resume_file
    assert ctx["active_bounded_segment"]["segment_id"] == "seg-recent-03"
    assert ctx["active_bounded_segment"]["phase"] == "03"
    assert ctx["active_bounded_segment"]["plan"] == "01"
    assert ctx["active_bounded_segment"]["last_result_id"] == "result-recent-03"
    assert ctx["active_resume_kind"] == "bounded_segment"
    assert ctx["active_resume_origin"] == "continuation.bounded_segment"
    assert ctx["active_resume_pointer"] == resume_file
    assert ctx["execution_resumable"] is True
    assert ctx["resume_candidates"][0]["kind"] == "bounded_segment"
    assert ctx["resume_candidates"][0]["origin"] == "continuation.bounded_segment"
    assert ctx["resume_candidates"][0]["last_result_id"] == "result-recent-03"
    assert ctx["resume_candidates"][0]["last_result"]["id"] == "result-recent-03"
    assert ctx["active_resume_result"]["id"] == "result-recent-03"
    assert ctx["continuity_handoff_file"] == resume_file
    assert "compat_resume_surface" not in ctx


def test_init_resume_prefers_canonical_handoff_over_live_execution_and_keeps_execution_advisory(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    _update_state_session(
        cwd,
        hostname="builder-01",
        platform="Linux 6.1 x86_64",
        resume_file="GPD/phases/03-analysis/alternate-resume.md",
    )
    _write_current_execution(
        cwd,
        {
            "session_id": "sess-1",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "updated_at": "2026-03-10T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["machine_change_detected"] is False
    assert ctx["derived_execution_head"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["recorded_continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["missing_continuity_handoff_file"] is None
    assert ctx["has_continuity_handoff"] is True
    assert ctx["active_bounded_segment"] is None
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/alternate-resume.md"
    _assert_no_resume_compat_aliases(ctx)
    assert "compat_resume_surface" not in ctx
    assert ctx["resume_candidates"] == [
        {
            "kind": "continuity_handoff",
            "origin": "continuation.handoff",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "resume_pointer": "GPD/phases/03-analysis/alternate-resume.md",
            "resumable": False,
            "status": "handoff",
        }
    ]


def test_init_resume_keeps_canonical_handoff_primary_across_machine_change(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    _update_state_session(
        cwd,
        hostname="builder-01",
        platform="Linux 6.1 x86_64",
        resume_file="GPD/phases/03-analysis/alternate-resume.md",
    )
    _write_current_execution(
        cwd,
        {
            "session_id": "sess-1",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "updated_at": "2026-03-10T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-02", "platform": "Linux 6.2 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["machine_change_detected"] is True
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/alternate-resume.md"
    _assert_no_resume_compat_aliases(ctx)
    assert "compat_resume_surface" not in ctx
    assert ctx["resume_candidates"] == [
        {
            "kind": "continuity_handoff",
            "origin": "continuation.handoff",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "resume_pointer": "GPD/phases/03-analysis/alternate-resume.md",
            "resumable": False,
            "status": "handoff",
        }
    ]


def test_init_resume_reads_canonical_continuation_from_state_json(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session"] = {
        "last_date": None,
        "hostname": None,
        "platform": None,
        "stopped_at": None,
        "resume_file": None,
    }
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03 Plan 02 Task 04",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "last_result_id": "result-canonical",
        },
        "machine": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
    }
    state["intermediate_results"] = [
        {
            "id": "result-canonical",
            "equation": "R = A + B",
            "description": "Canonical bridge result",
            "units": "arb",
            "validity": "validated",
            "phase": "03",
            "depends_on": ["seed-result"],
            "verified": True,
            "verification_records": [],
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    handoff = cwd / "GPD" / "phases" / "03-analysis" / "alternate-resume.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["recorded_continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["missing_continuity_handoff_file"] is None
    assert ctx["has_continuity_handoff"] is True
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert len(ctx["resume_candidates"]) == 1
    assert ctx["resume_candidates"][0]["status"] == "handoff"
    assert ctx["resume_candidates"][0]["resume_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["resume_candidates"][0]["resumable"] is False
    assert ctx["resume_candidates"][0]["last_result_id"] == "result-canonical"
    assert ctx["resume_candidates"][0]["kind"] == "continuity_handoff"
    assert ctx["resume_candidates"][0]["origin"] == "continuation.handoff"
    assert ctx["resume_candidates"][0]["resume_pointer"] == "GPD/phases/03-analysis/alternate-resume.md"
    _assert_no_resume_compat_aliases(ctx)
    assert ctx["session_hostname"] == "builder-01"
    assert ctx["session_platform"] == "Linux 6.1 x86_64"
    assert "compat_resume_surface" not in ctx


def test_init_resume_does_not_fall_back_to_legacy_session_when_canonical_continuation_is_corrupt(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session"] = {
        "last_date": "2026-03-29T12:00:00+00:00",
        "hostname": "builder-01",
        "platform": "Linux 6.1 x86_64",
        "stopped_at": "Legacy session stop",
        "resume_file": "GPD/phases/03-analysis/legacy-session.md",
    }
    state["continuation"] = {
        "schema_version": 1,
        "bounded_segment": "not-an-object",
        "machine": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    legacy_resume = cwd / "GPD" / "phases" / "03-analysis" / "legacy-session.md"
    legacy_resume.parent.mkdir(parents=True, exist_ok=True)
    legacy_resume.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(cwd)

    assert ctx["active_resume_pointer"] is None
    assert ctx["continuity_handoff_file"] is None
    assert ctx["recorded_continuity_handoff_file"] is None
    assert ctx["resume_candidates"] == []
    assert "compat_resume_surface" not in ctx


def test_init_resume_ignores_legacy_session_only_identity_without_active_resume_target(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session"] = {
        "last_date": "2026-03-29T12:00:00+00:00",
        "hostname": "legacy-host",
        "platform": "LegacyOS",
        "stopped_at": "Legacy stop",
        "resume_file": None,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(cwd)

    assert ctx["active_resume_kind"] is None
    assert ctx["active_resume_origin"] is None
    assert ctx["active_resume_pointer"] is None
    assert ctx["machine_change_detected"] is False
    assert ctx["machine_change_notice"] is None
    assert ctx["session_hostname"] is None
    assert ctx["session_platform"] is None
    assert ctx["session_last_date"] is None
    assert ctx["session_stopped_at"] is None
    assert "compat_resume_surface" not in ctx


def test_init_resume_propagates_unexpected_continuation_projection_errors(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("canonical resolution exploded")

    monkeypatch.setattr(context_module, "resolve_continuation", _boom)

    with pytest.raises(RuntimeError, match="canonical resolution exploded"):
        init_resume(cwd)


def test_init_resume_prefers_canonical_bounded_segment_over_lineage_head_snapshot(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session"] = {
        "last_date": None,
        "hostname": "builder-01",
        "platform": "Linux 6.1 x86_64",
        "stopped_at": None,
        "resume_file": None,
    }
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03 Plan 02 Task 04",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
        },
        "bounded_segment": {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "phase": "03",
            "plan": "02",
            "segment_id": "canonical-seg",
            "segment_status": "paused",
            "transition_id": "transition-canonical",
            "last_result_id": "result-canonical",
        },
        "machine": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
    }
    state["intermediate_results"] = [
        {
            "id": "result-canonical",
            "equation": "R = A + B",
            "description": "Canonical bridge result",
            "units": "arb",
            "validity": "validated",
            "phase": "03",
            "depends_on": ["seed-result"],
            "verified": True,
            "verification_records": [],
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    canonical_resume = cwd / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    canonical_resume.parent.mkdir(parents=True, exist_ok=True)
    canonical_resume.write_text("resume\n", encoding="utf-8")
    lineage_resume = cwd / "GPD" / "phases" / "03-analysis" / "lineage-head.md"
    lineage_resume.parent.mkdir(parents=True, exist_ok=True)
    lineage_resume.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )
    monkeypatch.setattr(
        "gpd.core.observability.get_current_execution",
        lambda cwd=None: CurrentExecutionState(
            session_id="sess-head",
            phase="04",
            plan="03",
            segment_id="head-seg",
            segment_status="paused",
            resume_file="GPD/phases/03-analysis/lineage-head.md",
            transition_id="transition-head",
            last_result_id="result-head",
            updated_at="2026-03-29T12:18:00+00:00",
        ),
    )

    ctx = init_resume(tmp_path)

    assert ctx["active_resume_kind"] == "bounded_segment"
    assert ctx["active_resume_origin"] == "continuation.bounded_segment"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["continuity_handoff_file"] is None
    assert ctx["recorded_continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["missing_continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["has_continuity_handoff"] is True
    assert ctx["derived_execution_head"]["resume_file"] == "GPD/phases/03-analysis/lineage-head.md"
    assert ctx["derived_execution_head_resume_file"] == "GPD/phases/03-analysis/lineage-head.md"
    assert ctx["active_bounded_segment"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    _assert_no_resume_compat_aliases(ctx)
    assert ctx["resume_candidates"][0]["kind"] == "bounded_segment"
    assert ctx["resume_candidates"][0]["origin"] == "continuation.bounded_segment"
    bounded_candidate = ctx["resume_candidates"][0]
    hydrated_result = _resolved_resume_result(ctx, bounded_candidate)
    assert hydrated_result is not None
    assert hydrated_result["id"] == "result-canonical"
    assert hydrated_result["equation"] == "R = A + B"
    assert hydrated_result["description"] == "Canonical bridge result"
    assert hydrated_result["phase"] == "03"


def test_init_resume_deduplicates_matching_session_handoff_and_ranks_interrupted_agent_last(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    resume_file = "GPD/phases/03-analysis/.continue-here.md"
    _update_state_session(
        cwd,
        hostname="builder-01",
        platform="Linux 6.1 x86_64",
        resume_file=resume_file,
    )
    _write_current_execution(
        cwd,
        {
            "session_id": "sess-1",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": resume_file,
            "updated_at": "2026-03-10T12:00:00+00:00",
        },
    )
    (cwd / context_module.PLANNING_DIR_NAME / context_module.AGENT_ID_FILENAME).write_text(
        "agent-77\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    _assert_no_resume_compat_aliases(ctx)
    assert ctx["continuity_handoff_file"] == resume_file
    assert ctx["recorded_continuity_handoff_file"] == resume_file
    assert ctx["missing_continuity_handoff_file"] is None
    assert ctx["has_continuity_handoff"] is True
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert [candidate["kind"] for candidate in ctx["resume_candidates"]] == [
        "continuity_handoff",
        "interrupted_agent",
    ]
    assert ctx["resume_candidates"][0]["origin"] == "continuation.handoff"
    assert ctx["resume_candidates"][1]["origin"] == "interrupted_agent_marker"
    assert "compat_resume_surface" not in ctx


def test_init_resume_normalizes_project_local_absolute_current_execution_resume_file(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    absolute_resume_path = cwd / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    absolute_resume_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_resume_path.write_text("resume\n", encoding="utf-8")
    _write_current_execution(
        cwd,
        {
            "session_id": "sess-1",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": str(absolute_resume_path),
            "updated_at": "2026-03-10T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["derived_execution_head_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["active_resume_kind"] == "bounded_segment"
    assert ctx["active_resume_origin"] == "continuation.bounded_segment"
    assert ctx["resume_candidates"][0]["origin"] == "continuation.bounded_segment"
    assert "compat_resume_surface" not in ctx


def test_init_resume_does_not_build_legacy_resume_aliases_before_public_canonicalization(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    absolute_resume_path = cwd / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    absolute_resume_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_resume_path.write_text("resume\n", encoding="utf-8")
    _write_current_execution(
        cwd,
        {
            "session_id": "sess-1",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": str(absolute_resume_path),
            "updated_at": "2026-03-10T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    captured: dict[str, object] = {}

    def _capture_public_payload(payload: dict[str, object], *, compat_fields=RESUME_COMPATIBILITY_ALIAS_FIELDS):
        captured["payload"] = dict(payload)
        return dict(payload)

    monkeypatch.setattr(context_module, "canonicalize_resume_public_payload", _capture_public_payload)

    ctx = init_resume(tmp_path)

    raw_payload = captured["payload"]
    assert isinstance(raw_payload, dict)
    _assert_no_resume_compat_aliases(raw_payload)
    assert raw_payload["derived_execution_head_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert raw_payload["active_resume_pointer"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx == raw_payload


def test_init_resume_ignores_nonportable_current_execution_resume_file_and_uses_session_handoff(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    _update_state_session(
        cwd,
        hostname="builder-01",
        platform="Linux 6.1 x86_64",
        resume_file="GPD/phases/03-analysis/alternate-resume.md",
    )
    external_resume_path = tmp_path.parent / f"{tmp_path.name}-external" / ".continue-here.md"
    external_resume_path.parent.mkdir(parents=True, exist_ok=True)
    external_resume_path.write_text("resume\n", encoding="utf-8")
    _write_current_execution(
        cwd,
        {
            "session_id": "sess-1",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": str(external_resume_path),
            "updated_at": "2026-03-10T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["derived_execution_head_resume_file"] is None
    assert ctx["execution_resumable"] is False
    assert ctx["continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["recorded_continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["missing_continuity_handoff_file"] is None
    assert ctx["has_continuity_handoff"] is True
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["derived_execution_head"]["segment_id"] == "seg-4"
    assert ctx["active_bounded_segment"] is None
    _assert_no_resume_compat_aliases(ctx)
    assert ctx["resume_candidates"] == [
        {
            "status": "handoff",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "resumable": False,
            "kind": "continuity_handoff",
            "origin": "continuation.handoff",
            "resume_pointer": "GPD/phases/03-analysis/alternate-resume.md",
        }
    ]
    assert "compat_resume_surface" not in ctx


def test_init_resume_surfaces_missing_session_handoff_as_advisory_candidate(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    _update_state_session(
        cwd,
        hostname="builder-01",
        platform="Linux 6.1 x86_64",
        resume_file="GPD/phases/03-analysis/alternate-resume.md",
        last_result_id="result-missing",
    )
    missing_handoff = cwd / "GPD" / "phases" / "03-analysis" / "alternate-resume.md"
    missing_handoff.unlink()
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["continuity_handoff_file"] is None
    assert ctx["recorded_continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["missing_continuity_handoff_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["has_continuity_handoff"] is True
    assert ctx["active_resume_kind"] is None
    assert ctx["active_resume_origin"] is None
    assert ctx["active_resume_pointer"] is None
    _assert_no_resume_compat_aliases(ctx)
    assert ctx["resume_candidates"] == [
        {
            "status": "missing",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "resumable": False,
            "advisory": True,
            "last_result_id": "result-missing",
            "kind": "continuity_handoff",
            "origin": "continuation.handoff",
            "resume_pointer": "GPD/phases/03-analysis/alternate-resume.md",
        }
    ]
    _assert_no_resume_compat_aliases(ctx)
    assert "compat_resume_surface" not in ctx


def test_init_resume_leaves_missing_result_id_unhydrated(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session"] = {
        "last_date": None,
        "hostname": "builder-01",
        "platform": "Linux 6.1 x86_64",
        "stopped_at": None,
        "resume_file": None,
        "last_result_id": None,
    }
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 03 Plan 02 Task 04",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "last_result_id": "result-missing",
        },
        "machine": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
    }
    state["intermediate_results"] = [
        {
            "id": "result-other",
            "equation": "Q = X - Y",
            "description": "Unrelated result",
            "units": "arb",
            "validity": "validated",
            "phase": "03",
            "depends_on": [],
            "verified": False,
            "verification_records": [],
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    handoff = cwd / "GPD" / "phases" / "03-analysis" / "alternate-resume.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    candidate = ctx["resume_candidates"][0]
    assert ctx["active_resume_kind"] == "continuity_handoff"
    assert ctx["active_resume_origin"] == "continuation.handoff"
    assert ctx["active_resume_pointer"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert candidate["last_result_id"] == "result-missing"
    assert candidate.get("last_result") is None
    assert ctx.get("active_resume_result") is None
    assert _resolved_resume_result(ctx, candidate) is None
    assert "compat_resume_surface" not in ctx


def test_init_resume_treats_missing_live_resume_file_as_advisory_only(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    _write_current_execution(
        cwd,
        {
            "session_id": "sess-1",
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "updated_at": "2026-03-10T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["derived_execution_head_resume_file"] is None
    assert ctx["execution_resumable"] is False
    assert ctx["active_resume_pointer"] is None
    assert ctx["active_bounded_segment"] is None
    assert ctx["derived_execution_head"]["segment_id"] == "seg-4"
    assert ctx["active_resume_kind"] is None
    _assert_no_resume_compat_aliases(ctx)
    assert ctx["resume_candidates"] == []
    assert "compat_resume_surface" not in ctx


def test_init_resume_leaves_selected_candidate_absent_for_ambiguous_recent_projects(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first_parent = tmp_path / "recent-a"
    second_parent = tmp_path / "recent-b"
    first_parent.mkdir()
    second_parent.mkdir()
    first = state_project_factory(first_parent)
    second = state_project_factory(second_parent)
    data_root = tmp_path / "data"
    for project, stamp, phase in (
        (first, "2026-03-29T12:00:00+00:00", "01"),
        (second, "2026-03-29T12:05:00+00:00", "02"),
    ):
        resume_path = project / "GPD" / "phases" / f"{phase}-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")
        record_recent_project(
            project,
            session_data={
                "last_date": stamp,
                "stopped_at": f"Phase {phase}",
                "resume_file": f"GPD/phases/{phase}-analysis/.continue-here.md",
            },
            store_root=data_root,
        )
    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))

    ctx = init_resume(workspace)

    assert ctx["project_reentry_mode"] == "ambiguous-recent-projects"
    assert ctx["project_reentry_requires_selection"] is True
    assert ctx["project_reentry_selected_candidate"] is None


def test_init_resume_leaves_selected_candidate_absent_for_unselected_recent_projects(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_parent = tmp_path / "recent-weak"
    project_parent.mkdir()
    project = state_project_factory(project_parent)
    data_root = tmp_path / "data"
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-29T12:00:00+00:00",
            "stopped_at": "Phase 01",
            "resume_file": None,
        },
        store_root=data_root,
    )
    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))

    ctx = init_resume(workspace)

    assert ctx["project_reentry_mode"] == "recent-projects"
    assert ctx["project_reentry_selected_candidate"] is None


def test_init_resume_state_exists_false_when_only_unrecoverable_state_file_is_present(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{\n", encoding="utf-8")

    ctx = init_resume(tmp_path)

    assert ctx["workspace_state_exists"] is False
    assert ctx["state_exists"] is False


def test_init_resume_nested_workspace_probe_does_not_create_fake_gpd_dir(
    tmp_path: Path,
    state_project_factory,
) -> None:
    project_root = state_project_factory(tmp_path)
    nested = project_root / "workspace" / "nested"
    nested.mkdir(parents=True)

    ctx = init_resume(nested)

    assert ctx["project_root"] == project_root.resolve(strict=False).as_posix()
    assert ctx["project_root_source"] == "current_workspace"
    assert ctx["project_reentry_mode"] == "current-workspace"
    assert ctx["state_exists"] is True
    assert ctx["workspace_state_exists"] is False
    assert not (nested / "GPD").exists()
