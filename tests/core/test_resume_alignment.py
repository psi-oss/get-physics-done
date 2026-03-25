"""Regression tests for resume/state documentation alignment."""

from __future__ import annotations

import json
import re
from pathlib import Path

from gpd.core import context as context_module
from gpd.core.context import init_resume
from gpd.core.state import default_state_dict, generate_state_markdown

ROOT = Path(__file__).resolve().parents[2]


def _setup_project(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()


def _write_state(tmp_path: Path, state: dict) -> None:
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_resume_docs_use_canonical_paths_and_no_legacy_resume_command() -> None:
    resume_doc = (ROOT / "src/gpd/specs/workflows/resume-work.md").read_text(encoding="utf-8")
    portability_doc = (ROOT / "src/gpd/specs/references/orchestration/state-portability.md").read_text(encoding="utf-8")
    schema_doc = (ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")
    state_doc = (ROOT / "src/gpd/specs/templates/state.md").read_text(encoding="utf-8")
    new_project_doc = (ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")
    transition_doc = (ROOT / "src/gpd/specs/workflows/transition.md").read_text(encoding="utf-8")
    execute_plan_doc = (ROOT / "src/gpd/specs/workflows/execute-plan.md").read_text(encoding="utf-8")

    for doc in (resume_doc, portability_doc):
        assert ".gpd/" not in doc
        assert re.search(r"/gpd:resume(?!-work)\b", doc) is None
        assert "auto_checkpoint" not in doc

    assert "/gpd:resume-work" in portability_doc
    assert "execution_resume_file" in resume_doc
    assert "execution_resume_file" in portability_doc
    assert "machine_change_detected" in resume_doc
    assert "session_resume_file" in resume_doc
    assert "stopped-at handoff" in resume_doc
    assert "previous hostname/platform" in resume_doc
    assert "machine-change notice" in resume_doc
    assert "stopped-at handoff" in portability_doc
    assert "resume pointer or interrupted segment" in portability_doc
    assert "hostname/platform differ" in portability_doc
    assert "machine-change advisory" in portability_doc
    assert "current-execution.json" in portability_doc
    assert "bounded-segment resume state" in portability_doc
    assert "portable bounded-segment resume hint" in portability_doc
    assert "Non-project or missing resume pointers are treated as advisory telemetry" in portability_doc
    assert 'do not make `resume_mode="bounded_segment"`' in portability_doc
    assert "project-relative paths" in portability_doc
    assert "normalizes project-local absolute `resume_file` paths back to relative form" in portability_doc
    assert "usable state from `GPD/state.json`, `GPD/state.json.bak`, or `GPD/STATE.md`" in resume_doc
    assert "lone unreadable file path does not count as portable recoverable state" in portability_doc
    assert "current readable `state.json` carries a malformed `project_contract`" in resume_doc
    assert "silently promoting `state.json.bak` as the current authoritative contract" in portability_doc
    assert "does not choose a newer backup by timestamp alone" in portability_doc
    assert "state.json  >  state.json.bak  >  STATE.md" in portability_doc
    assert "state.json > state.json.bak > STATE.md" in schema_doc
    assert "state saves fail closed if the backup cannot be refreshed" in schema_doc
    assert "/gpd:sync-state" in portability_doc
    assert "gpd state sync" not in portability_doc
    assert "hostname" in schema_doc
    assert "platform" in schema_doc
    assert '"resume_file": "' in schema_doc
    assert (
        "## Session Continuity\n\n"
        "**Last session:** —\n"
        "**Stopped at:** —\n"
        "**Resume file:** —\n"
        "**Hostname:** —\n"
        "**Platform:** —\n"
    ) in state_doc
    assert (
        "## Session Continuity\n\n"
        "**Last session:** [current ISO timestamp]\n"
        "**Stopped at:** Project initialized (minimal)\n"
        "**Resume file:** —\n"
        "**Hostname:** [current hostname]\n"
        "**Platform:** [current platform]\n"
    ) in new_project_doc
    assert "GPD/state.json.session" in new_project_doc
    assert (
        "**Last session:** [current ISO timestamp]\n"
        "**Stopped at:** Phase [X] complete, ready to plan Phase [X+1]\n"
        "**Resume file:** —\n"
        "**Hostname:** [current hostname]\n"
        "**Platform:** [current platform]\n"
    ) in transition_doc
    assert "Update the same values under `GPD/state.json.session`" in transition_doc
    assert "save_state_markdown" in transition_doc
    assert "gpd --raw state snapshot" not in transition_doc
    assert "**Core research question:** [Current core research question from PROJECT.md]" in transition_doc
    assert 'grep \'^\\*\\*Current Phase:\\*\\*\'' in transition_doc
    assert "GPD/state.json GPD/PROJECT.md" in transition_doc
    assert 'resume_file: "—"' in execute_plan_doc
    assert '--resume-file "—"' in execute_plan_doc
    assert 'resume_file: "None"' not in execute_plan_doc
    assert '--resume-file "None"' not in execute_plan_doc
    assert "Enables instant resumption and machine portability:" in state_doc
    assert "Last session timestamp" in state_doc
    assert "Stopped-at handoff point" in state_doc
    assert "Resume file pointer" in state_doc
    assert "Hostname of the previous machine" in state_doc
    assert "Platform of the previous machine" in state_doc
    assert "resume_file" in state_doc
    assert "Hostname" in state_doc
    assert "Platform" in state_doc
    assert "normalizes project-local absolute paths back to that form" in schema_doc


def test_generate_state_markdown_surfaces_machine_readable_contract_line() -> None:
    markdown = generate_state_markdown(default_state_dict())

    assert "**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`" in markdown


def test_init_resume_surfaces_machine_change_and_session_resume_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    _setup_project(tmp_path)
    state = default_state_dict()
    state["session"]["hostname"] = "old-host"
    state["session"]["platform"] = "Linux 5.15 x86_64"
    state["session"]["resume_file"] = "GPD/phases/03-analysis/.continue-here.md"
    _write_state(tmp_path, state)
    resume_path = tmp_path / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        context_module,
        "_current_machine_identity",
        lambda: {"hostname": "new-host", "platform": "Linux 6.1 x86_64"},
    )

    ctx = init_resume(tmp_path)

    assert ctx["execution_resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
    assert ctx["execution_resume_file_source"] == "session_resume_file"
    assert ctx["execution_paused_at"] is None
    assert ctx["resume_mode"] is None
    assert ctx["segment_candidates"] == [
        {
            "source": "session_resume_file",
            "status": "handoff",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "resumable": False,
        }
    ]
    assert ctx["active_execution_segment"] is None
    assert ctx["has_interrupted_agent"] is False
    assert ctx["session_hostname"] == "old-host"
    assert ctx["session_platform"] == "Linux 5.15 x86_64"
    assert ctx["current_hostname"] == "new-host"
    assert ctx["current_platform"] == "Linux 6.1 x86_64"
    assert ctx["machine_change_detected"] is True
    assert "old-host" in ctx["machine_change_notice"]
    assert "new-host" in ctx["machine_change_notice"]
