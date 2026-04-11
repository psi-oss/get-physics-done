"""Prompt-hygiene guardrails for key command wrappers."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _commands_with_matching_workflows() -> list[str]:
    return sorted(
        command_path.stem
        for command_path in COMMANDS_DIR.glob("*.md")
        if (WORKFLOWS_DIR / command_path.name).exists()
    )


def test_commands_reference_their_workflow_file_once() -> None:
    for command in _commands_with_matching_workflows():
        prompt = (COMMANDS_DIR / f"{command}.md").read_text(encoding="utf-8")
        workflow_ref = f"@{{GPD_INSTALL_DIR}}/workflows/{command}.md"
        assert prompt.count(workflow_ref) in {1, 2}


def test_workflows_do_not_repeat_runtime_delegation_note() -> None:
    delegation_note = "runtime-delegation-note.md"
    offenders = {}
    for path in WORKFLOWS_DIR.glob("*.md"):
        count = path.read_text(encoding="utf-8").count(delegation_note)
        if count > 1:
            offenders[path.name] = count

    assert offenders == {}
