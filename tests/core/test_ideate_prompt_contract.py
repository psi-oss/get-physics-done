"""Focused phase-1 contract guardrails for the ideate command/workflow surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.registry import get_command, list_commands

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
IDEATE_COMMAND_PATH = COMMANDS_DIR / "ideate.md"
IDEATE_WORKFLOW_PATH = WORKFLOWS_DIR / "ideate.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_any(content: str, *phrases: str) -> bool:
    return any(phrase in content for phrase in phrases)


def test_ideate_phase1_surfaces_land_together() -> None:
    assert IDEATE_COMMAND_PATH.exists() == IDEATE_WORKFLOW_PATH.exists()


def test_ideate_command_is_registered_and_projectless_when_present() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate phase-1 command/workflow has not landed yet")

    raw_command = _read(IDEATE_COMMAND_PATH)
    command = get_command("gpd:ideate")

    assert "ideate" in list_commands()
    assert "name: gpd:ideate" in raw_command
    assert "@{GPD_INSTALL_DIR}/workflows/ideate.md" in raw_command
    assert command.name == "gpd:ideate"
    assert command.context_mode == "projectless"
    assert set(command.allowed_tools).issuperset({"ask_user", "file_read", "shell"})


def test_ideate_workflow_preserves_phase1_launch_summary_contract_when_present() -> None:
    if not IDEATE_WORKFLOW_PATH.exists():
        pytest.skip("ideate phase-1 command/workflow has not landed yet")

    workflow = _read(IDEATE_WORKFLOW_PATH)

    for fragment in ("Start ideation", "Adjust launch", "Review raw context", "Stop here"):
        assert fragment in workflow

    for fragment in ("Idea", "Outcome", "Anchors", "Constraints"):
        assert fragment in workflow

    assert _contains_any(workflow, "Risks / Open Questions", "Risks/Open Questions", "Open Questions")
    assert _contains_any(workflow, "Execution Preferences", "Mode")
