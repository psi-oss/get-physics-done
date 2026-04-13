from __future__ import annotations

from pathlib import Path

from gpd.core.include_expansion import expand_at_includes
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
    assert_tour_command_surface_contract(workflow)
    table_entries = workflow[
        workflow.index("Include these entries using the command syntax") : workflow.index("Keep this table runtime-facing only.")
    ]
    assert "- `gpd resume`" not in table_entries
    assert "Keep this table runtime-facing only." in workflow

    for fragment in (
        "A common first pass is help -> start -> tour, then the path that fits the folder.",
        "Use a compact table with four columns:",
        "Use this when",
        "Do not use this when",
        "Example",
        "active runtime's native command prefix",
        "plan-phase",
        "execute-phase",
        "verify-work",
        "peer-review",
        "respond-to-referees",
        "arxiv-submission",
        "branch-hypothesis",
        "set-profile",
        "set-tier-models",
        "Use `start` when you are still deciding, not `new-project`",
        "Use `resume-work` only when the project already has GPD state",
        "Use `set-tier-models` when you want to pin concrete runtime model ids only",
        "Use `help` when you want the command reference, not a setup wizard",
        "A few terms in plain English",
        "`GPD project` - a folder where GPD already saved its own project files and state",
        "`research map` - GPD's summary of an existing research folder before full project setup",
        "`phase` - one chunk of the project plan that GPD will organize later",
        "If you are still unsure, run the runtime-specific start command.",
        "If you want to pin concrete tier-1, tier-2, and tier-3 model ids, run the runtime-specific \\`set-tier-models\\` command.",
        "If you want to change permissions, autonomy, or runtime preferences after your first successful start or later, run the runtime-specific \\`settings\\` command.",
    ):
        assert fragment in workflow

    hard_coded_runtime_examples = (
        "gpd:start",
        "gpd:new-project",
        "gpd:map-research",
        "gpd:resume-work",
        "gpd:settings",
    )
    for fragment in hard_coded_runtime_examples:
        assert fragment not in workflow
