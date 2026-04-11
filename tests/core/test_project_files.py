"""Tests for gpd.core.project_files — auto-migration of root planning files."""

from __future__ import annotations

from pathlib import Path

from gpd.core.constants import PLANNING_DIR_NAME, PROJECT_FILENAME, ROADMAP_FILENAME
from gpd.core.project_files import migrate_root_planning_files


def test_migrate_does_not_copy_root_roadmap_to_gpd(tmp_path: Path) -> None:
    """Root ROADMAP.md is no longer auto-copied from read-only paths."""
    (tmp_path / ROADMAP_FILENAME).write_text("# Roadmap\n", encoding="utf-8")

    migrated = migrate_root_planning_files(tmp_path)

    assert migrated == []
    assert not (tmp_path / PLANNING_DIR_NAME / ROADMAP_FILENAME).exists()


def test_migrate_does_not_copy_root_project_to_gpd(tmp_path: Path) -> None:
    """Root PROJECT.md is no longer auto-copied from read-only paths."""
    (tmp_path / PROJECT_FILENAME).write_text("# Project\n", encoding="utf-8")

    migrated = migrate_root_planning_files(tmp_path)

    assert migrated == []
    assert not (tmp_path / PLANNING_DIR_NAME / PROJECT_FILENAME).exists()


def test_migrate_does_not_copy_both_files(tmp_path: Path) -> None:
    (tmp_path / ROADMAP_FILENAME).write_text("# R\n", encoding="utf-8")
    (tmp_path / PROJECT_FILENAME).write_text("# P\n", encoding="utf-8")

    migrated = migrate_root_planning_files(tmp_path)

    assert migrated == []
    assert not (tmp_path / PLANNING_DIR_NAME).exists()


def test_migrate_skips_when_gpd_already_has_file(tmp_path: Path) -> None:
    """No copy when GPD/ already has the file."""
    gpd_dir = tmp_path / PLANNING_DIR_NAME
    gpd_dir.mkdir()
    (gpd_dir / ROADMAP_FILENAME).write_text("# GPD Roadmap\n", encoding="utf-8")
    (tmp_path / ROADMAP_FILENAME).write_text("# Root Roadmap\n", encoding="utf-8")

    migrated = migrate_root_planning_files(tmp_path)

    assert migrated == []
    # GPD/ version unchanged
    assert (gpd_dir / ROADMAP_FILENAME).read_text(encoding="utf-8") == "# GPD Roadmap\n"


def test_migrate_noop_when_neither_exists(tmp_path: Path) -> None:
    """No error when files don't exist in either location."""
    migrated = migrate_root_planning_files(tmp_path)

    assert migrated == []


def test_migrate_does_not_create_gpd_dir_if_needed(tmp_path: Path) -> None:
    """No-op migration does not create GPD/ for read-only callers."""
    assert not (tmp_path / PLANNING_DIR_NAME).exists()
    (tmp_path / ROADMAP_FILENAME).write_text("# R\n", encoding="utf-8")

    migrated = migrate_root_planning_files(tmp_path)

    assert migrated == []
    assert not (tmp_path / PLANNING_DIR_NAME).exists()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    """Second call is a no-op."""
    (tmp_path / ROADMAP_FILENAME).write_text("# R\n", encoding="utf-8")

    first = migrate_root_planning_files(tmp_path)
    second = migrate_root_planning_files(tmp_path)

    assert first == []
    assert second == []


def test_migrate_does_not_touch_copy_path(tmp_path: Path, monkeypatch) -> None:
    """No-op migration does not attempt copy operations."""
    (tmp_path / ROADMAP_FILENAME).write_text("# R\n", encoding="utf-8")

    def _failing_copy(*args, **kwargs):
        raise AssertionError("copy should not be called")

    monkeypatch.setattr("shutil.copy2", _failing_copy)

    migrated = migrate_root_planning_files(tmp_path)

    assert migrated == []
    assert not (tmp_path / PLANNING_DIR_NAME / ROADMAP_FILENAME).exists()
