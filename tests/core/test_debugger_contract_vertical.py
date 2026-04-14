"""Focused debugger vertical contract regressions."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_PATH = REPO_ROOT / "src/gpd/commands/debug.md"
WORKFLOW_PATH = REPO_ROOT / "src/gpd/specs/workflows/debug.md"
AGENT_PATH = REPO_ROOT / "src/gpd/agents/gpd-debugger.md"
AGENT_DELEGATION_REFERENCE = REPO_ROOT / "src/gpd/specs/references/orchestration/agent-delegation.md"
RUNTIME_DELEGATION_NOTE = REPO_ROOT / "src/gpd/specs/references/orchestration/runtime-delegation-note.md"


def test_debugger_vertical_spawn_contract_is_one_shot_and_file_producing() -> None:
    command = COMMAND_PATH.read_text(encoding="utf-8")
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    runtime_note = RUNTIME_DELEGATION_NOTE.read_text(encoding="utf-8")
    delegation = AGENT_DELEGATION_REFERENCE.read_text(encoding="utf-8")
    expanded_workflow = expand_at_includes(workflow, REPO_ROOT / "src/gpd", "/runtime/")

    assert "One-shot handoff" in delegation
    assert "Artifact gate" in delegation
    assert "Always set `readonly=false` for file-producing agents." in delegation
    assert "Spawn a fresh subagent for the task below." in runtime_note
    assert "one-shot handoff" in runtime_note
    assert "Always pass `readonly=false` for file-producing agents." in runtime_note

    assert workflow.count('subagent_type="gpd-debugger"') == 1
    assert workflow.count("readonly=false") == 1
    assert "Spawn a fresh subagent for the task below." in expanded_workflow
    assert "one-shot handoff" in expanded_workflow
    assert "Always pass `readonly=false` for file-producing agents." in expanded_workflow

    assert "Create: GPD/debug/{slug}.md" in command
    assert "@{GPD_INSTALL_DIR}/workflows/debug.md" in command
    assert "spawn gpd-debugger agent" in command


def test_debugger_vertical_artifact_paths_keep_active_and_resolved_session_state_separate() -> None:
    command = COMMAND_PATH.read_text(encoding="utf-8")
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    agent = AGENT_PATH.read_text(encoding="utf-8")

    assert "Create: GPD/debug/{slug}.md" in command
    assert "Debug file path: GPD/debug/{slug}.md" in command
    assert "expected debug session artifact" in command
    assert "artifact gate" in command
    assert "GPD/debug/{slug}.md" in workflow
    assert "session_status: diagnosed" in workflow
    assert "files_written: [GPD/debug/{slug}.md, ...]" in agent
    assert "session_file: GPD/debug/{slug}.md" in agent
    assert "**Troubleshooting Session:** GPD/debug/resolved/{slug}.md" in agent
    assert "A checkpoint is a one-shot handoff for the current run." in agent
    assert "You are not resumed in the same run." in agent


def test_debugger_vertical_seam_routes_on_typed_status_instead_of_headings() -> None:
    command = COMMAND_PATH.read_text(encoding="utf-8")
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    agent = AGENT_PATH.read_text(encoding="utf-8")

    assert "gpd_return.status: completed" in command
    assert "gpd_return.status: checkpoint" in command
    assert "gpd_return.status: blocked" in command
    assert "Do not branch on heading text here." in command
    assert "gpd_return.status: completed" in workflow
    assert "gpd_return.status: checkpoint" in workflow
    assert "gpd_return.status: blocked" in workflow
    assert "Do not route on heading markers in the returned text" in workflow
    assert "session_status: diagnosed" in workflow
    assert "typed `gpd_return` envelope and the session file instead" in workflow
    assert "A checkpoint is a one-shot handoff for the current run." in agent
    assert "The orchestrator presents the checkpoint to the user" in agent
