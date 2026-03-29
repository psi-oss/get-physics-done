from __future__ import annotations

from pathlib import Path

from gpd.registry import get_command, list_commands

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

    for fragment in (
        "Provide a beginner-friendly, read-only tour of the core GPD command surface.",
        "This is a read-only tour of the main GPD commands. It will not change your files.",
        "the normal terminal, where you install GPD and run setup / status commands",
        "the runtime, where you use the GPD command prefix provided for that runtime",
        "Use a compact table with four columns:",
        "Use this when",
        "Do not use this when",
        "Example",
        "/gpd:start",
        "/gpd:new-project --minimal",
        "/gpd:new-project",
        "/gpd:map-research",
        "gpd resume",
        "/gpd:resume-work",
        "/gpd:suggest-next",
        "/gpd:progress",
        "/gpd:explain",
        "/gpd:quick",
        "/gpd:settings",
        "/gpd:help",
        "Normal terminal vs runtime",
        "Use \\`gpd resume\\` first if you need to reopen the project before using \\`/gpd:resume-work\\`.",
        "settings` is the guided runtime command for changing autonomy,",
        "Use `start` when you are still deciding, not `new-project`",
        "Use `resume-work` only when the project already has GPD state",
        "Use `settings` when you want to change autonomy, permissions, or runtime",
        "Use `help` when you want the command reference, not a setup wizard",
        "A few terms in plain English",
        "`GPD project` - a folder where GPD already saved its own project files and state",
        "`research map` - GPD's summary of an existing research folder before full project setup",
        "`phase` - one chunk of the project plan that GPD will organize later",
        "If you are still unsure, run /gpd:start.",
        "If you want to change permissions, autonomy, or runtime preferences, run \\`/gpd:settings\\`.",
        "If you need to reopen the project itself from your normal terminal, use \\`gpd resume\\` first and then \\`/gpd:resume-work\\` in the runtime.",
        "Do not ask the user to pick a branch and do not continue into another workflow",
    ):
        assert fragment in workflow
