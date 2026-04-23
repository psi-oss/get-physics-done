"""Assertions for complete-milestone prompt wiring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_complete_milestone_command_uses_supported_version_placeholders_and_preloads_dependencies() -> None:
    command = _read("src/gpd/commands/complete-milestone.md")

    assert "{{version}}" not in command
    assert "{version}" in command
    assert "Mark research milestone {version} complete" in command
    assert "GPD/v{version}-MILESTONE-AUDIT.md" in command
    assert "GPD/milestones/v{version}-ROADMAP.md" in command
    assert "GPD/milestones/v{version}-REQUIREMENTS.md" in command
    assert "chore: archive v{version} research milestone" in command
    assert "@{GPD_INSTALL_DIR}/workflows/complete-milestone.md" in command
    assert "@{GPD_INSTALL_DIR}/templates/milestone.md" in command
    assert "@{GPD_INSTALL_DIR}/templates/milestone-archive.md" in command


def test_complete_milestone_workflow_required_reading_uses_portable_runtime_paths() -> None:
    workflow = _read("src/gpd/specs/workflows/complete-milestone.md")

    assert "1. `@{GPD_INSTALL_DIR}/templates/milestone.md`" in workflow
    assert "2. `@{GPD_INSTALL_DIR}/templates/milestone-archive.md`" in workflow
    assert "3. `GPD/ROADMAP.md`" in workflow
    assert "4. `GPD/REQUIREMENTS.md`" in workflow
    assert "5. `GPD/PROJECT.md`" in workflow
    assert "templates/milestone.md" not in workflow.replace("@{GPD_INSTALL_DIR}/templates/milestone.md", "")
    assert "templates/milestone-archive.md" not in workflow.replace("@{GPD_INSTALL_DIR}/templates/milestone-archive.md", "")


def test_complete_milestone_workflow_references_portable_archive_template() -> None:
    workflow = _read("src/gpd/specs/workflows/complete-milestone.md")

    assert "@{GPD_INSTALL_DIR}/templates/milestone-archive.md" in workflow
    assert "ROADMAP archive** uses `templates/milestone-archive.md`" not in workflow
