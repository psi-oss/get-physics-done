from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes
from gpd.registry import get_command, list_commands
from tests.doc_surface_contracts import assert_tour_command_surface_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_tour_command_is_registered_and_projectless() -> None:
    assert "tour" in list_commands()
    command = get_command("gpd:tour")
    assert command.name == "gpd:tour"
    assert command.context_mode == "projectless"
    assert command.allowed_tools == ["file_read"]


def test_tour_command_references_workflow() -> None:
    raw_command_prompt = (COMMANDS_DIR / "tour.md").read_text(encoding="utf-8")
    command_prompt = expand_at_includes(raw_command_prompt, SOURCE_ROOT, PATH_PREFIX)

    assert "@{GPD_INSTALL_DIR}/workflows/tour.md" in raw_command_prompt
    assert "@{GPD_INSTALL_DIR}/references/onboarding/beginner-command-taxonomy.md" in raw_command_prompt
    assert "gpd:set-tier-models" in command_prompt
    assert "gpd:settings" in command_prompt


def test_tour_workflow_introduces_a_safe_beginner_walkthrough() -> None:
    workflow = (WORKFLOWS_DIR / "tour.md").read_text(encoding="utf-8")
    expanded_workflow = expand_at_includes(workflow, SOURCE_ROOT, PATH_PREFIX)
    assert_tour_command_surface_contract(workflow)
    table_entries = workflow[
        workflow.index("Include these entries:") : workflow.index("Keep this table runtime-facing only.")
    ]
    assert "- `gpd resume`" not in table_entries
    assert "Keep this table runtime-facing only." in workflow

    assert (
        "A common first pass is `help -> start -> tour -> new-project / map-research -> resume-work`, "
        "but the folder state still decides the actual path."
        in expanded_workflow
    )

    for fragment in (
        "Use a compact table with four columns:",
        "Use this when",
        "Do not use this when",
        "Example",
        "gpd:plan-phase",
        "gpd:execute-phase",
        "gpd:verify-work",
        "gpd:peer-review",
        "gpd:respond-to-referees",
        "gpd:arxiv-submission",
        "gpd:branch-hypothesis",
        "gpd:set-profile",
        "gpd:set-tier-models",
        "Use `start` when you are still deciding, not `new-project`",
        "Use `resume-work` only when the project already has GPD state",
        "Use `help` when you want the command reference, not a setup wizard",
        "A few terms in plain English",
        "`GPD project` - a folder where GPD already saved its own project files and state",
        "`research map` - GPD's summary of an existing research folder before full project setup",
        "`phase` - one chunk of the project plan that GPD will organize later",
        "If you are still unsure, run gpd:start.",
        "`settings` is the guided runtime command for changing autonomy",
        "`set-tier-models` is the direct runtime command for pinning concrete",
        "settings/model commands from the startup table",
    ):
        assert fragment in workflow

    assert workflow.count("gpd:set-tier-models") == 1
    assert workflow.count("gpd:settings") == 1
    assert workflow.count("set-tier-models") <= 3
    assert workflow.count("settings") <= 5
    assert workflow.count("tier-1") == 1
