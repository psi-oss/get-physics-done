from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes
from gpd.registry import get_command, list_commands
from tests.doc_surface_contracts import assert_start_workflow_router_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_start_command_is_registered_and_projectless() -> None:
    assert "start" in list_commands()
    command = get_command("gpd:start")
    assert command.name == "gpd:start"
    assert command.context_mode == "projectless"


def test_start_command_references_workflow() -> None:
    raw_command_prompt = (COMMANDS_DIR / "start.md").read_text(encoding="utf-8")
    command_prompt = expand_at_includes(raw_command_prompt, SOURCE_ROOT, PATH_PREFIX)

    assert "@{GPD_INSTALL_DIR}/workflows/start.md" in raw_command_prompt
    assert "@{GPD_INSTALL_DIR}/references/onboarding/beginner-command-taxonomy.md" in raw_command_prompt
    assert "gpd resume" in command_prompt
    assert "gpd resume --recent" in command_prompt
    assert "gpd:resume-work" in command_prompt
    assert "gpd:suggest-next" in command_prompt
    assert "advisory recent-project picker" in command_prompt
    assert "reloads canonical state in the reopened project" in command_prompt
    assert (
        command_prompt.index("`gpd resume` remains the local read-only current-workspace recovery snapshot")
        < command_prompt.index("`gpd resume --recent` remains the normal-terminal advisory recent-project picker")
        < command_prompt.index("`gpd:suggest-next` is the fastest post-resume next command")
    )


def test_start_workflow_routes_to_existing_entrypoints() -> None:
    workflow = (WORKFLOWS_DIR / "start.md").read_text(encoding="utf-8")

    assert_start_workflow_router_contract(workflow)
    assert "gpd --raw init new-project --stage scope_intake" in workflow
    assert "core project/root detection" in workflow
    assert "Do not use that file search to override the core classifier." in workflow
    assert "HAS_GPD_PROJECT=false" not in workflow
    assert "RESEARCH_FILE_COUNT" not in workflow

    for fragment_options in (
        (
            "GPD project` (a folder where GPD already saved its own project files, notes, and state)",
            "GPD project` (a folder where GPD already saved its own project files, notes, and state",
        ),
        (
            "research map` (GPD's summary of an existing research folder before full project setup)",
            "research map` (GPD's summary of an existing research folder before full project setup",
        ),
        ("In GPD terms, \\`map-research\\` means inspect an existing folder before planning.",),
        ("In GPD terms, \\`new-project\\` creates the project scaffolding GPD will use later.",),
        ("This folder already has saved GPD work (`GPD project`)",),
        ("This folder already has GPD's folder summary (`research map`)",),
        ("This folder already has research files, but GPD is not set up here yet",),
        ("This folder looks new or mostly empty",),
        ("I will show the safest next steps first and the broader options second.",),
        ("Keep the numbered list short.",),
        ("Resume this project (recommended)",),
        ("Review the project status first",),
        ("Map this folder first (recommended)",),
        ("Start a brand-new GPD project anyway",),
        ("Fast start (recommended)",),
        ("Full guided setup",),
        ("Turn this into a full GPD project",),
        ("Reopen a different GPD project",),
        (
            "This is the in-runtime continue command for an existing GPD project.",
            "This is the in-runtime recovery command for the selected project.",
            "This is the in-runtime return path for the selected project.",
        ),
        (
            "If the researcher chooses `Resume this project (recommended)` or `Continue where I left off`:",
            "If the researcher chooses `Resume this project` or `Continue where I left off`:",
            "If the researcher chooses `Resume this project (recommended)`, `Continue where I left off`, `Inspect recovery state (recommended)`, or `Inspect recovery state`:",
        ),
        (
            "If the researcher chooses `Map this folder first (recommended)` or `Refresh the research map`:",
            "If the researcher chooses `Map this folder first` or `Refresh the research map`:",
        ),
        (
            "Use \\`gpd resume --recent\\` in your normal terminal to find the project first.",
            "Use \\`gpd resume --recent\\` in your normal terminal first.",
            "Use \\`gpd resume --recent\\` in your normal terminal to pick the project first.",
        ),
        (
            "The recent-project picker is advisory; choose the workspace there, then \\`gpd:resume-work\\` reloads canonical state for that project.",
            "The recent-project picker is advisory",
        ),
        (
            "Then open that project folder in the runtime and run \\`gpd:resume-work\\`.",
            "Then open the project folder in the runtime and run \\`gpd:resume-work\\`.",
        ),
        (
            "In GPD terms, \\`resume-work\\` is the in-runtime continuation step once the recovery ladder has identified the right project.",
            "In GPD terms, \\`resume-work\\` is the in-runtime recovery step once the recovery ladder has identified the right project.",
            "In GPD terms, \\`resume-work\\` is the in-runtime command that continues a selected project.",
            "In GPD terms, \\`resume-work\\` is the in-runtime continuation step once the recovery ladder has identified the right project and reopened its workspace.",
        ),
        ("Do not silently create project files from `gpd:start` itself.",),
        (
            "Do not silently switch the user into a different project folder.",
            "Do not silently switch to a different project folder.",
            "Do not silently switch projects.",
        ),
        (
            "When in doubt between a fresh folder and an existing research folder, prefer `map-research` as the safer recommendation.",
            "When in doubt between a fresh folder and an existing research folder, prefer `map-research`.",
        ),
        ("keep the official GPD terms visible in plain-English form",),
    ):
        assert any(fragment in workflow for fragment in fragment_options)

    assert "- `Keep the numbered list short." not in workflow
    assert "this is an internal structuring rule, not a line to show the researcher" in workflow

    assert "Read `{GPD_INSTALL_DIR}/workflows/new-project.md` with the file-read tool." not in workflow
    assert "Read `{GPD_INSTALL_DIR}/workflows/help.md` with the file-read tool." not in workflow
    assert "Read `{GPD_INSTALL_DIR}/workflows/tour.md` with the file-read tool." not in workflow
