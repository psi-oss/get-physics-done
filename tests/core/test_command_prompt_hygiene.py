"""Prompt-hygiene guardrails for key command wrappers."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"

COMMANDS_WITH_WORKFLOW = (
    "debug",
    "complete-milestone",
    "digest-knowledge",
    "new-project",
    "peer-review",
    "plan-phase",
    "verify-work",
    "arxiv-submission",
)


def test_commands_reference_their_workflow_file_once() -> None:
    for command in COMMANDS_WITH_WORKFLOW:
        prompt = (COMMANDS_DIR / f"{command}.md").read_text(encoding="utf-8")
        workflow_ref = f"@{{GPD_INSTALL_DIR}}/workflows/{command}.md"
        assert prompt.count(workflow_ref) == 1


def test_workflows_do_not_repeat_runtime_delegation_note() -> None:
    delegation_note = "runtime-delegation-note.md"
    offenders = {}
    for path in WORKFLOWS_DIR.glob("*.md"):
        count = path.read_text(encoding="utf-8").count(delegation_note)
        if count > 1:
            offenders[path.name] = count

    assert offenders == {}
