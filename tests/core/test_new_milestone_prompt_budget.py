"""Prompt budget regression tests for the `new-milestone` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_new_milestone_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "new-milestone.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "new-milestone.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/references/research/questioning.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/ui/ui-brand.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/project.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/requirements.md" not in command_text
    assert "The workflow handles the full milestone initialization flow:" not in command_text
    assert "Read {GPD_INSTALL_DIR}/references/research/questioning.md only when you need guided milestone questioning." in command_text
    assert "Read {GPD_INSTALL_DIR}/templates/project.md only when updating `GPD/PROJECT.md`." in command_text
    assert "Read {GPD_INSTALL_DIR}/templates/requirements.md only when writing `GPD/REQUIREMENTS.md`." in command_text
    assert "Read {GPD_INSTALL_DIR}/references/ui/ui-brand.md only when rendering branded completion or status blocks." in command_text


def test_new_milestone_command_budget_tracks_the_workflow_without_wrapper_bloat() -> None:
    command = measure_prompt_surface(
        COMMANDS_DIR / "new-milestone.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "new-milestone.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert command.expanded_line_count < workflow.expanded_line_count + 120
    assert command.expanded_char_count < workflow.expanded_char_count + 4000
