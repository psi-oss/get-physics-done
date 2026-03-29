from __future__ import annotations

import json
from pathlib import Path

from gpd.core import context as context_module
from gpd.core import state as state_module
from gpd.core.context import init_resume
from gpd.core.state import parse_state_to_json, state_record_session


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


def _update_state_session(
    cwd: Path,
    *,
    last_date: str | None = None,
    hostname: str,
    platform: str,
    stopped_at: str | None = None,
    resume_file: str | None,
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
        }
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    if isinstance(resume_file, str) and resume_file:
        resume_path = Path(resume_file)
        if not resume_path.is_absolute():
            resume_path = cwd / resume_path
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("resume\n", encoding="utf-8")


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
    assert ctx["current_hostname"] == "new-host"
    assert ctx["current_platform"] == "Linux 6.1 x86_64"
    assert ctx["execution_resume_file_source"] == "session_resume_file"
    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["resume_mode"] is None
    assert ctx["segment_candidates"] == [
        {
            "source": "session_resume_file",
            "status": "handoff",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "resumable": False,
        }
    ]


def test_init_resume_keeps_current_execution_primary_and_includes_session_resume_file(
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
    assert ctx["execution_resume_file_source"] == "current_execution"
    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["resume_mode"] == "bounded_segment"
    assert ctx["segment_candidates"][0]["source"] == "current_execution"
    assert ctx["segment_candidates"][1]["source"] == "session_resume_file"
    assert ctx["segment_candidates"][1]["resume_file"] == "GPD/phases/03-analysis/alternate-resume.md"


def test_init_resume_keeps_current_execution_primary_across_machine_change(
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
    assert ctx["execution_resume_file_source"] == "current_execution"
    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["resume_mode"] == "bounded_segment"
    assert ctx["segment_candidates"][0]["source"] == "current_execution"
    assert ctx["segment_candidates"][1]["source"] == "session_resume_file"


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
        },
        "machine": {
            "recorded_at": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
    }
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

    assert ctx["execution_resume_file_source"] == "session_resume_file"
    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["resume_mode"] is None
    assert ctx["session_hostname"] == "builder-01"
    assert ctx["session_platform"] == "Linux 6.1 x86_64"
    assert ctx["segment_candidates"] == [
        {
            "source": "session_resume_file",
            "status": "handoff",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "resumable": False,
        }
    ]


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

    assert ctx["resume_mode"] == "bounded_segment"
    assert ctx["session_resume_file"] == resume_file
    assert [candidate["source"] for candidate in ctx["segment_candidates"]] == [
        "current_execution",
        "interrupted_agent",
    ]
    assert ctx["segment_candidates"][0]["resume_file"] == resume_file
    assert ctx["segment_candidates"][1]["agent_id"] == "agent-77"


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

    assert ctx["current_execution_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["segment_candidates"][0]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"


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

    assert ctx["current_execution_resume_file"] is None
    assert ctx["execution_resumable"] is False
    assert ctx["execution_resume_file_source"] == "session_resume_file"
    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["resume_mode"] is None
    assert ctx["active_execution_segment"]["segment_id"] == "seg-4"
    assert ctx["segment_candidates"] == [
        {
            "source": "session_resume_file",
            "status": "handoff",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "resumable": False,
        }
    ]


def test_init_resume_surfaces_missing_session_handoff_as_advisory_candidate(
    tmp_path: Path, state_project_factory, monkeypatch
) -> None:
    cwd = state_project_factory(tmp_path)
    _update_state_session(
        cwd,
        hostname="builder-01",
        platform="Linux 6.1 x86_64",
        resume_file="GPD/phases/03-analysis/alternate-resume.md",
    )
    missing_handoff = cwd / "GPD" / "phases" / "03-analysis" / "alternate-resume.md"
    missing_handoff.unlink()
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["session_resume_file"] is None
    assert ctx["recorded_session_resume_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["missing_session_resume_file"] == "GPD/phases/03-analysis/alternate-resume.md"
    assert ctx["execution_resume_file_source"] is None
    assert ctx["execution_resume_file"] is None
    assert ctx["resume_mode"] is None
    assert ctx["segment_candidates"] == [
        {
            "source": "session_resume_file",
            "status": "missing",
            "resume_file": "GPD/phases/03-analysis/alternate-resume.md",
            "resumable": False,
            "advisory": True,
        }
    ]


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

    assert ctx["active_execution_segment"]["segment_id"] == "seg-4"
    assert ctx["current_execution_resume_file"] is None
    assert ctx["execution_resumable"] is False
    assert ctx["execution_resume_file"] is None
    assert ctx["resume_mode"] is None
    assert ctx["segment_candidates"] == []


def test_init_resume_state_exists_false_when_only_unrecoverable_state_file_is_present(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{\n", encoding="utf-8")

    ctx = init_resume(tmp_path)

    assert ctx["state_exists"] is False
