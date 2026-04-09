"""Prompt budget regression tests for the `resume-work` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_resume_work_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "resume-work.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "resume-work.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "resume-work.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/resume-work.md" in command_text
    assert "Resume research from the selected project's canonical state." in command_text
    assert "Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/resume-work.md`." in command_text
    assert "requires:" in command_text
    assert 'files: ["GPD/ROADMAP.md"]' in command_text
    assert "GPD/STATE.md" not in command_text
    assert "resume-vocabulary.md" not in command_text
    assert "STATE.md loading (or reconstruction if missing)" not in command_text
    assert "Context-aware option offering" not in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 80
    assert metrics.expanded_char_count < workflow.expanded_char_count + 5000
