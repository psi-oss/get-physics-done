from __future__ import annotations

from pathlib import Path

from gpd.registry import get_command, list_commands
from tests.doc_surface_contracts import assert_tour_command_surface_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_tour_command_is_registered_and_projectless() -> None:
    assert "tour" in list_commands()
    command = get_command("gpd:tour")
    assert command.name == "gpd:tour"
    assert command.context_mode == "projectless"


def test_tour_command_references_workflow() -> None:
    command_prompt = (COMMANDS_DIR / "tour.md").read_text(encoding="utf-8")
    assert "@{GPD_INSTALL_DIR}/workflows/tour.md" in command_prompt


def test_tour_workflow_introduces_a_safe_beginner_walkthrough() -> None:
    workflow = (WORKFLOWS_DIR / "tour.md").read_text(encoding="utf-8")
    assert_tour_command_surface_contract(workflow)

    for fragment in (
        "A common first pass is help -> start -> tour, then the path that fits the folder.",
        "Use a compact table with four columns:",
        "Use this when",
        "Do not use this when",
        "Example",
        "/gpd:plan-phase",
        "/gpd:execute-phase",
        "/gpd:verify-work",
        "/gpd:peer-review",
        "/gpd:respond-to-referees",
        "/gpd:arxiv-submission",
        "/gpd:branch-hypothesis",
        "/gpd:set-profile",
        "Use `start` when you are still deciding, not `new-project`",
        "Use `resume-work` only when the project already has GPD state",
        "Use `help` when you want the command reference, not a setup wizard",
        "A few terms in plain English",
        "`GPD project` - a folder where GPD already saved its own project files and state",
        "`research map` - GPD's summary of an existing research folder before full project setup",
        "`phase` - one chunk of the project plan that GPD will organize later",
        "If you are still unsure, run /gpd:start.",
        "If you want to change permissions, autonomy, or runtime preferences after your first successful start or later, run \\`/gpd:settings\\`.",
    ):
        assert fragment in workflow
