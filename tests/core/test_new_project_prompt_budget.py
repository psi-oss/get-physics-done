"""Prompt budget regression tests for the `new-project` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import expanded_prompt_text, line_number_for_fragment, measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"

MINIMAL_QUESTION = "Describe your research project in one pass"
FULL_QUESTION = "What physics problem do you want to investigate?"
SETUP_QUESTION = "Which starting workflow preset should GPD use for `GPD/config.json`?"


def test_new_project_prompt_surface_is_heavier_than_start_but_uses_the_same_measurement_helper() -> None:
    new_project = measure_prompt_surface(
        COMMANDS_DIR / "new-project.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
        first_question_fragments=(MINIMAL_QUESTION, FULL_QUESTION, SETUP_QUESTION),
    )
    start = measure_prompt_surface(
        COMMANDS_DIR / "start.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "new-project.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert new_project.raw_include_count == 1
    assert start.raw_include_count > 0
    assert new_project.expanded_line_count > start.expanded_line_count
    assert new_project.expanded_char_count > start.expanded_char_count
    assert new_project.expanded_line_count < workflow.expanded_line_count + 200
    assert new_project.expanded_char_count < workflow.expanded_char_count + 12000
    assert new_project.first_question_line is not None
    assert new_project.first_question_marker == MINIMAL_QUESTION


def test_new_project_workflow_first_question_anchors_are_in_the_expected_order() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")

    minimal_line = line_number_for_fragment(workflow_text, MINIMAL_QUESTION)
    full_line = line_number_for_fragment(workflow_text, FULL_QUESTION)
    setup_line = line_number_for_fragment(workflow_text, SETUP_QUESTION)

    assert minimal_line is not None
    assert full_line is not None
    assert setup_line is not None
    assert minimal_line < full_line < setup_line


def test_new_project_command_no_longer_eagerly_inlines_late_stage_authorities() -> None:
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")
    expanded_command = expanded_prompt_text(
        COMMANDS_DIR / "new-project.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert "@{GPD_INSTALL_DIR}/references/research/questioning.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/project-contract-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/project.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/requirements.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/ui/ui-brand.md" not in command_text
    assert "<questioning_guide>" not in expanded_command
    assert "# PROJECT.md Template" not in expanded_command
    assert "# Requirements Template" not in expanded_command
    assert "<ui_patterns>" not in expanded_command
