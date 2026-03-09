"""Tests for gpd.core.constants — ProjectLayout and constant integrity."""

from __future__ import annotations

from pathlib import Path

from gpd.core.constants import (
    PHASES_DIR_NAME,
    PLANNING_DIR_NAME,
    PLAN_SUFFIX,
    PROJECT_FILENAME,
    REQUIRED_PLANNING_DIRS,
    REQUIRED_PLANNING_FILES,
    REQUIRED_RETURN_FIELDS,
    ROADMAP_FILENAME,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    STATE_JSON_FILENAME,
    STATE_MD_FILENAME,
    SUMMARY_SUFFIX,
    VALID_RETURN_STATUSES,
    VERIFICATION_SUFFIX,
    ProjectLayout,
)


class TestProjectLayout:
    def test_basic_paths(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.root == tmp_path
        assert layout.planning == tmp_path / PLANNING_DIR_NAME
        assert layout.state_json == tmp_path / PLANNING_DIR_NAME / STATE_JSON_FILENAME
        assert layout.state_md == tmp_path / PLANNING_DIR_NAME / STATE_MD_FILENAME
        assert layout.roadmap == tmp_path / PLANNING_DIR_NAME / ROADMAP_FILENAME
        assert layout.project_md == tmp_path / PLANNING_DIR_NAME / PROJECT_FILENAME

    def test_phases_dir(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.phases_dir == tmp_path / PLANNING_DIR_NAME / PHASES_DIR_NAME

    def test_phase_dir(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.phase_dir("01-setup") == layout.phases_dir / "01-setup"

    def test_plan_file(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        pf = layout.plan_file("01-setup", "01")
        assert pf.name == f"01{PLAN_SUFFIX}"

    def test_summary_file(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        sf = layout.summary_file("01-setup", "01")
        assert sf.name == f"01{SUMMARY_SUFFIX}"

    def test_verification_file(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        vf = layout.verification_file("01-setup", "01")
        assert vf.name == f"01{VERIFICATION_SUFFIX}"

    def test_trace_file_sanitizes_name(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        tf = layout.trace_file("01", "plan with spaces!")
        # Spaces and ! should be replaced
        assert " " not in tf.name
        assert "!" not in tf.name
        assert tf.suffix == ".jsonl"

    def test_is_plan_file(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.is_plan_file("01-PLAN.md") is True
        assert layout.is_plan_file("PLAN.md") is True
        assert layout.is_plan_file("01-SUMMARY.md") is False
        assert layout.is_plan_file("random.md") is False

    def test_is_summary_file(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.is_summary_file("01-SUMMARY.md") is True
        assert layout.is_summary_file("SUMMARY.md") is True
        assert layout.is_summary_file("01-PLAN.md") is False

    def test_is_verification_file(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.is_verification_file("01-VERIFICATION.md") is True
        assert layout.is_verification_file("01-PLAN.md") is False

    def test_strip_plan_suffix(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.strip_plan_suffix("01-PLAN.md") == "01"
        assert layout.strip_plan_suffix("PLAN.md") == ""
        assert layout.strip_plan_suffix("other.md") == "other.md"

    def test_strip_summary_suffix(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path)
        assert layout.strip_summary_suffix("01-SUMMARY.md") == "01"
        assert layout.strip_summary_suffix("SUMMARY.md") == ""
        assert layout.strip_summary_suffix("other.md") == "other.md"

    def test_custom_planning_dir(self, tmp_path: Path):
        layout = ProjectLayout(tmp_path, planning_dir=".custom")
        assert layout.planning == tmp_path / ".custom"
        assert layout.state_json == tmp_path / ".custom" / STATE_JSON_FILENAME


class TestConstantValues:
    """Sanity checks — constants should have expected values."""

    def test_planning_dir_name(self):
        assert PLANNING_DIR_NAME == ".planning"

    def test_required_planning_files_contains_state(self):
        assert STATE_MD_FILENAME in REQUIRED_PLANNING_FILES
        assert STATE_JSON_FILENAME in REQUIRED_PLANNING_FILES
        assert ROADMAP_FILENAME in REQUIRED_PLANNING_FILES

    def test_required_planning_dirs_contains_phases(self):
        assert PHASES_DIR_NAME in REQUIRED_PLANNING_DIRS

    def test_valid_return_statuses(self):
        assert "completed" in VALID_RETURN_STATUSES
        assert "failed" in VALID_RETURN_STATUSES
        assert "blocked" in VALID_RETURN_STATUSES
        assert "checkpoint" in VALID_RETURN_STATUSES

    def test_required_return_fields(self):
        assert "status" in REQUIRED_RETURN_FIELDS
        assert "phase" in REQUIRED_RETURN_FIELDS

    def test_suffixes_end_with_md(self):
        assert PLAN_SUFFIX.endswith(".md")
        assert SUMMARY_SUFFIX.endswith(".md")
        assert VERIFICATION_SUFFIX.endswith(".md")

    def test_standalone_filenames(self):
        assert STANDALONE_PLAN == "PLAN.md"
        assert STANDALONE_SUMMARY == "SUMMARY.md"
