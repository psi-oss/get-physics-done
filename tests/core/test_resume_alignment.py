"""Regression tests for resume/state documentation alignment."""

from __future__ import annotations

import json
import re
from pathlib import Path

from gpd.core import context as context_module
from gpd.core.context import init_resume
from gpd.core.state import default_state_dict, generate_state_markdown
from tests.doc_surface_contracts import assert_resume_authority_contract, resume_authority_public_vocabulary_intro

ROOT = Path(__file__).resolve().parents[2]


def _setup_project(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()


def _write_state(tmp_path: Path, state: dict) -> None:
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_resume_docs_use_canonical_paths_and_no_legacy_resume_command() -> None:
    resume_doc = (ROOT / "src/gpd/specs/workflows/resume-work.md").read_text(encoding="utf-8")
    help_doc = (ROOT / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")
    portability_doc = (ROOT / "src/gpd/specs/references/orchestration/state-portability.md").read_text(encoding="utf-8")
    state_machine_doc = (ROOT / "src/gpd/specs/templates/state-machine.md").read_text(encoding="utf-8")
    continue_here_doc = (ROOT / "src/gpd/specs/templates/continue-here.md").read_text(encoding="utf-8")
    schema_doc = (ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")
    state_doc = (ROOT / "src/gpd/specs/templates/state.md").read_text(encoding="utf-8")
    new_project_doc = (ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")
    transition_doc = (ROOT / "src/gpd/specs/workflows/transition.md").read_text(encoding="utf-8")
    execute_plan_doc = (ROOT / "src/gpd/specs/workflows/execute-plan.md").read_text(encoding="utf-8")

    for doc in (resume_doc, help_doc, portability_doc):
        assert ".gpd/" not in doc
        assert re.search(r"/gpd:resume(?!-work)\b", doc) is None
        assert "auto_checkpoint" not in doc

    assert "/gpd:resume-work" in portability_doc
    assert_resume_authority_contract(
        resume_doc,
        allow_explicit_alias_examples=False,
        require_generic_compatibility_note=False,
    )
    assert_resume_authority_contract(
        help_doc,
        allow_explicit_alias_examples=False,
        require_generic_compatibility_note=True,
    )
    assert_resume_authority_contract(
        portability_doc,
        allow_explicit_alias_examples=True,
        require_generic_compatibility_note=True,
    )
    assert "Canonical continuation and recovery authority:" in resume_doc
    assert resume_authority_public_vocabulary_intro() in resume_doc
    assert resume_authority_public_vocabulary_intro() in help_doc
    assert resume_authority_public_vocabulary_intro() in portability_doc
    assert "Those fields are the public top-level resume vocabulary only." in resume_doc
    assert "Those fields are the public top-level resume vocabulary only." in help_doc
    assert "Those fields are the public top-level resume vocabulary only." in portability_doc
    assert "compat_resume_surface" not in resume_doc
    assert "gpd init resume" not in resume_doc
    assert "machine_change_detected" in resume_doc
    assert "legacy session mirror" not in resume_doc
    assert "session.resume_file" not in resume_doc
    assert "state.json.continuation.machine.hostname" in resume_doc
    assert "state.json.continuation.handoff" in resume_doc
    assert "compat_resume_surface" not in portability_doc
    assert "backend-only compatibility inputs" in portability_doc
    assert "session.resume_file" not in portability_doc
    assert "shared resume resolver" in help_doc
    assert "compat_resume_surface" not in help_doc
    assert "Recorded handoff artifact is missing" in resume_doc
    assert "stopped-at continuation point" in resume_doc
    assert "previous hostname/platform" in resume_doc
    assert "machine-change notice" in resume_doc
    assert "rerunning the installer so runtime-local config stays current" in resume_doc
    assert "stopped-at continuation point" in portability_doc
    assert "bounded resume pointer, recorded handoff, or interrupted segment" in portability_doc
    assert "hostname/platform differ" in portability_doc
    assert "machine-change advisory" in portability_doc
    assert "rerunning the installer" in portability_doc
    assert "current-execution.json" in portability_doc
    assert "state.json.continuation.handoff.resume_file" in portability_doc
    assert "bounded-segment resume state" in portability_doc
    assert "advisory continuity context only" in portability_doc
    assert "does not create a resumable bounded-segment candidate" in portability_doc
    assert "backend-only inputs" in portability_doc
    assert 'set `active_resume_kind="bounded_segment"`' in portability_doc
    assert "The canonical public resume surface centers on `active_resume_kind`, `active_resume_origin`, `active_resume_pointer`" in portability_doc
    assert "public top-level resume vocabulary" in portability_doc
    assert "shared resume resolver" in portability_doc
    assert "shared resume-surface resolver owns the canonical candidate kind/origin semantics" in portability_doc
    assert "Execution lineage" in portability_doc
    assert "Compatibility mirror showing the latest execution snapshot" in portability_doc
    assert "No single handoff file, lineage row, or execution snapshot is, by itself, the canonical continuation state." in portability_doc
    assert "Canonical state in `state.json.continuation` wins first" in portability_doc
    assert "Storage authority for machine-readable project state and canonical continuation hierarchy" in portability_doc
    assert "Editable human-readable mirror of state" in portability_doc
    assert "Temporary continuation handoff artifact written by `/gpd:pause-work`" in portability_doc
    assert "derived execution head and `GPD/observability/current-execution.json` are compatibility projections" in portability_doc
    assert "temporary handoff artifact" in resume_doc
    assert "supporting continuity surfaces only" in resume_doc
    assert "Do not treat any single `.continue-here.md` file or compatibility snapshot as the sole authority in isolation." in resume_doc
    assert "shared resume-surface resolver owns the canonical candidate kind/origin semantics" in resume_doc
    assert "The shared resume resolver keeps the derived execution head and the temporary handoff artifact subordinate to the storage authority chain." in resume_doc
    assert "shared resolver across those layers" in resume_doc
    assert "project-relative paths" in portability_doc
    assert "normalizes project-local absolute `resume_file` paths back to relative form" in portability_doc
    assert "usable state from `GPD/state.json`, `GPD/state.json.bak`, or `GPD/STATE.md`" in resume_doc
    assert "lone unreadable file path does not count as portable recoverable state" in portability_doc
    assert "current readable `state.json` carries a malformed `project_contract`" in resume_doc
    assert "silently promoting `state.json.bak` as the current authoritative contract" in portability_doc
    assert "does not choose a newer backup by timestamp alone" in portability_doc
    assert "state.json (including canonical continuation)  >  state.json.bak  >  STATE.md" in portability_doc
    assert "reconstructs the full project context from the recovery ladder in `GPD/state.json`, `GPD/state.json.bak`, or `GPD/STATE.md`" in portability_doc
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
    assert "GPD/state.json.continuation" in new_project_doc
    assert "continuation.handoff.recorded_at" in new_project_doc
    assert "continuation.machine.hostname" in new_project_doc
    assert "GPD/state.json.session" not in new_project_doc
    assert (
        "**Last session:** [current ISO timestamp]\n"
        "**Stopped at:** Phase [X] complete, ready to plan Phase [X+1]\n"
        "**Resume file:** —\n"
        "**Hostname:** [current hostname]\n"
        "**Platform:** [current platform]\n"
    ) in transition_doc
    assert "GPD/state.json.continuation" in transition_doc
    assert "continuation.handoff.stopped_at" in transition_doc
    assert "continuation.machine.platform" in transition_doc
    assert "GPD/state.json.session" not in transition_doc
    assert "session mirror" not in transition_doc
    assert "save_state_markdown" in transition_doc
    assert "gpd --raw state snapshot" not in transition_doc
    assert "**Core research question:** [Current core research question from PROJECT.md]" in transition_doc
    assert 'grep \'^\\*\\*Current Phase:\\*\\*\'' in transition_doc
    assert "GPD/state.json GPD/PROJECT.md" in transition_doc
    assert "continuation_update:" in execute_plan_doc
    assert "session_update:" not in execute_plan_doc
    assert "resume_file: null" in execute_plan_doc
    assert "bounded_segment: null" in execute_plan_doc
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
    assert "recommends rerunning the installer when runtime-local config may be stale" in schema_doc
    assert "Durable canonical continuation authority; compatibility mirrors derive from it" in schema_doc
    assert "Model-authored continuity updates should target `continuation.handoff` and `continuation.machine`" in schema_doc
    assert "canonical object first and only falls back to the derived execution head compatibility mirror when the canonical continuation is missing or incomplete" in schema_doc
    assert "That backend treats `continuation` as primary" in schema_doc
    assert schema_doc.index("| `continuation`") < schema_doc.index("| `session`")
    assert "Raw compatibility cues remain backend-only intake signals rather than primary resume fields" in schema_doc
    assert "state.json.continuation.bounded_segment" in schema_doc
    assert "An append-only execution lineage records what happened." in state_machine_doc
    assert (
        "A derived execution head projects the latest resumable execution state for compatibility surfaces." in state_machine_doc
        or "A derived execution head is a compatibility projection of the latest resumable execution state." in state_machine_doc
    )
    assert "`state.json.continuation.bounded_segment` remains the durable bounded-resume authority." in state_machine_doc
    assert "Temporary handoff artifact" in state_machine_doc
    assert "Derived execution head / `GPD/observability/current-execution.json`" in state_machine_doc
    assert "reads `state.json.continuation` first and only consults compatibility surfaces when canonical continuation is missing or incomplete" in state_machine_doc
    assert "canonical temporary phase handoff artifact" in continue_here_doc
    assert (
        "This file is **not** the authoritative store for project position, session continuity, or resume ranking." in continue_here_doc
        or "This file is **not** the authoritative store for project position, continuation state, or resume ranking." in continue_here_doc
    )
    assert "Deleting or missing this file does not erase project state by itself" in continue_here_doc
    assert (
        "must not be treated as the storage authority for project status, session continuity, or bounded resume ranking" in continue_here_doc
        or "must not be treated as the storage authority for project status, continuation state, or bounded resume ranking" in continue_here_doc
    )


def test_recovery_docs_keep_runtime_resume_work_distinct_from_local_resume_surfaces() -> None:
    portability_doc = (ROOT / "src/gpd/specs/references/orchestration/state-portability.md").read_text(encoding="utf-8")
    schema_doc = (ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")

    assert (
        "If you already know the repo, run `/gpd:resume-work` in the coding assistant when you are ready to "
        "continue work there, or `gpd resume` from your normal system terminal for a read-only local recovery "
        "summary."
    ) in portability_doc
    assert "gpd resume --recent" in portability_doc
    assert "`/gpd:pause-work`, `/gpd:resume-work`" in schema_doc
    assert "`gpd resume` is the public local read-only recovery surface" in schema_doc
    assert "`gpd init resume` remains the machine-readable backend" in schema_doc
    assert "gpd resume" in portability_doc


def test_generate_state_markdown_surfaces_machine_readable_contract_line() -> None:
    markdown = generate_state_markdown(default_state_dict())

    assert "**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`" in markdown


def test_init_resume_ignores_session_only_machine_change_metadata_without_canonical_continuation(
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
    monkeypatch.setattr(
        context_module,
        "_resolve_reentry_context",
        lambda requested_cwd, data_root=None: (
            requested_cwd,
            {
                "workspace_root": requested_cwd.as_posix(),
                "project_root": requested_cwd.as_posix(),
                "project_root_source": "current-workspace",
                "project_root_auto_selected": False,
                "project_reentry_mode": "current-workspace",
                "project_reentry_requires_selection": False,
                "project_reentry_candidates": [],
            },
        ),
    )

    ctx = init_resume(tmp_path)

    assert ctx["active_resume_pointer"] is None
    assert ctx["active_resume_origin"] is None
    assert ctx["execution_paused_at"] is None
    assert "resume_mode" not in ctx
    assert "segment_candidates" not in ctx
    assert "active_execution_segment" not in ctx
    assert "compat_resume_surface" not in ctx
    assert ctx["resume_candidates"] == []
    assert ctx["has_interrupted_agent"] is False
    assert ctx["session_hostname"] is None
    assert ctx["session_platform"] is None
    assert ctx["current_hostname"] == "new-host"
    assert ctx["current_platform"] == "Linux 6.1 x86_64"
    assert ctx["machine_change_detected"] is False
    assert ctx["machine_change_notice"] is None
