"""Tests for gpd.core.commands — ported JS command functions.

Tests the pure logic functions without filesystem mocking (uses tmp_path).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gpd.core.commands import (
    cmd_current_timestamp,
    cmd_generate_slug,
    cmd_history_digest,
    cmd_regression_check,
    cmd_scaffold,
    cmd_summary_extract,
    cmd_todo_complete,
    cmd_validate_return,
    cmd_verify_path_exists,
)
from gpd.core.errors import ValidationError

# ─── cmd_current_timestamp ─────────────────────────────────────────────────


class TestCurrentTimestamp:
    def test_full_format_returns_iso(self):
        result = cmd_current_timestamp("full")
        assert "T" in result.timestamp
        assert "+" in result.timestamp or "Z" in result.timestamp

    def test_date_format_returns_ymd(self):
        result = cmd_current_timestamp("date")
        assert len(result.timestamp) == 10
        assert result.timestamp.count("-") == 2

    def test_filename_format_replaces_colons(self):
        result = cmd_current_timestamp("filename")
        assert ":" not in result.timestamp
        assert "T" in result.timestamp

    def test_default_is_full(self):
        result = cmd_current_timestamp()
        assert "T" in result.timestamp


# ─── cmd_generate_slug ─────────────────────────────────────────────────────


class TestGenerateSlug:
    def test_basic_slug(self):
        result = cmd_generate_slug("Hello World!")
        assert result.slug == "hello-world"

    def test_multiple_spaces(self):
        result = cmd_generate_slug("  Multiple   Spaces  ")
        assert result.slug == "multiple-spaces"

    def test_special_chars(self):
        result = cmd_generate_slug("Levi-Civita Sign (+,-)")
        assert result.slug == "levi-civita-sign"

    def test_empty_raises(self):
        with pytest.raises(ValidationError, match="text required"):
            cmd_generate_slug("")


# ─── cmd_verify_path_exists ────────────────────────────────────────────────


class TestVerifyPathExists:
    def test_file_exists(self, tmp_path: Path):
        (tmp_path / "test.txt").write_text("hello")
        result = cmd_verify_path_exists(tmp_path, "test.txt")
        assert result.exists is True
        assert result.type == "file"

    def test_directory_exists(self, tmp_path: Path):
        (tmp_path / "subdir").mkdir()
        result = cmd_verify_path_exists(tmp_path, "subdir")
        assert result.exists is True
        assert result.type == "directory"

    def test_not_found(self, tmp_path: Path):
        result = cmd_verify_path_exists(tmp_path, "nonexistent")
        assert result.exists is False
        assert result.type is None

    def test_absolute_path(self, tmp_path: Path):
        f = tmp_path / "abs.txt"
        f.write_text("content")
        result = cmd_verify_path_exists(tmp_path, str(f))
        assert result.exists is True

    def test_empty_path_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="path required"):
            cmd_verify_path_exists(tmp_path, "")


# ─── cmd_todo_complete ─────────────────────────────────────────────────────


class TestTodoComplete:
    def _setup_todo(self, tmp_path: Path, filename: str = "fix-bug.md") -> Path:
        pending = tmp_path / ".planning" / "todos" / "pending"
        pending.mkdir(parents=True)
        todo = pending / filename
        todo.write_text("---\ntitle: Fix bug\narea: core\n---\n\nFix the bug.\n")
        return todo

    def test_moves_to_done(self, tmp_path: Path):
        self._setup_todo(tmp_path)
        result = cmd_todo_complete(tmp_path, "fix-bug.md")
        assert result.completed is True
        assert result.file == "fix-bug.md"
        assert result.date == date.today().isoformat()

        # Source should be gone
        assert not (tmp_path / ".planning" / "todos" / "pending" / "fix-bug.md").exists()
        # Dest should exist
        done_path = tmp_path / ".planning" / "todos" / "done" / "fix-bug.md"
        assert done_path.exists()
        assert "completed:" in done_path.read_text()

    def test_not_found_raises(self, tmp_path: Path):
        (tmp_path / ".planning" / "todos" / "pending").mkdir(parents=True)
        with pytest.raises(ValidationError, match="Todo not found"):
            cmd_todo_complete(tmp_path, "nonexistent.md")

    def test_empty_filename_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="filename required"):
            cmd_todo_complete(tmp_path, "")


# ─── cmd_scaffold ──────────────────────────────────────────────────────────


class TestScaffold:
    def _setup_phase(self, tmp_path: Path, phase_dir: str = "03-core-work") -> Path:
        d = tmp_path / ".planning" / "phases" / phase_dir
        d.mkdir(parents=True)
        return d

    def test_scaffold_phase_dir(self, tmp_path: Path):
        result = cmd_scaffold(tmp_path, "phase-dir", phase="5", name="Integration Tests")
        assert result.created is True
        assert "05-integration-tests" in (result.directory or "")
        assert (tmp_path / ".planning" / "phases" / "05-integration-tests").is_dir()

    def test_scaffold_context(self, tmp_path: Path):
        self._setup_phase(tmp_path)
        result = cmd_scaffold(tmp_path, "context", phase="3", name="Core Work")
        assert result.created is True
        assert "CONTEXT.md" in (result.path or "")

    def test_scaffold_validation(self, tmp_path: Path):
        self._setup_phase(tmp_path)
        result = cmd_scaffold(tmp_path, "validation", phase="3")
        assert result.created is True
        assert "VALIDATION.md" in (result.path or "")

    def test_scaffold_verification(self, tmp_path: Path):
        self._setup_phase(tmp_path)
        result = cmd_scaffold(tmp_path, "verification", phase="3")
        assert result.created is True
        assert "VERIFICATION.md" in (result.path or "")

    def test_already_exists(self, tmp_path: Path):
        phase_dir = self._setup_phase(tmp_path)
        (phase_dir / "03-CONTEXT.md").write_text("existing")
        result = cmd_scaffold(tmp_path, "context", phase="3")
        assert result.created is False
        assert result.reason == "already_exists"

    def test_unknown_type_raises(self, tmp_path: Path):
        self._setup_phase(tmp_path)
        with pytest.raises(ValidationError, match="Unknown scaffold type"):
            cmd_scaffold(tmp_path, "unknown", phase="3")

    def test_phase_dir_missing_name_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="phase and name required"):
            cmd_scaffold(tmp_path, "phase-dir", phase="1")

    def test_missing_phase_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="--phase is required"):
            cmd_scaffold(tmp_path, "context")

    def test_nonexistent_phase_raises(self, tmp_path: Path):
        (tmp_path / ".planning" / "phases").mkdir(parents=True)
        with pytest.raises(ValidationError, match="Phase 99 directory not found"):
            cmd_scaffold(tmp_path, "context", phase="99")


# ─── cmd_summary_extract ──────────────────────────────────────────────────


class TestSummaryExtract:
    def _write_summary(self, tmp_path: Path, content: str) -> str:
        summary = tmp_path / "test-SUMMARY.md"
        summary.write_text(content)
        return "test-SUMMARY.md"

    def test_basic_extract(self, tmp_path: Path):
        path = self._write_summary(
            tmp_path,
            (
                "---\n"
                "one-liner: Phase completed successfully\n"
                "key-files:\n  - src/main.py\n"
                "methods:\n  added:\n    - finite-difference\n"
                "patterns-established:\n  - test-first\n"
                "key-decisions:\n  - Use numpy: for performance\n"
                "affects:\n  - phase-3\n"
                "---\n\n# Summary\n\n**Phase done**\n"
            ),
        )
        result = cmd_summary_extract(tmp_path, path)
        assert result.one_liner == "Phase completed successfully"
        assert "src/main.py" in result.key_files
        assert "finite-difference" in result.methods_added
        assert "test-first" in result.patterns
        assert len(result.decisions) == 1
        assert result.decisions[0].summary == "Use numpy"
        assert result.decisions[0].rationale == "for performance"
        assert "phase-3" in result.affects

    def test_field_filter(self, tmp_path: Path):
        path = self._write_summary(
            tmp_path, ("---\none-liner: filtered test\naffects:\n  - phase-2\n---\n\n# Summary\n")
        )
        result = cmd_summary_extract(tmp_path, path, fields=["one_liner"])
        assert isinstance(result, dict)
        assert result["one_liner"] == "filtered test"
        assert "affects" not in result

    def test_body_one_liner_fallback(self, tmp_path: Path):
        path = self._write_summary(
            tmp_path, ("---\nphase: 01\n---\n\n# Phase 1 Summary\n\n**Derived the Lagrangian**\n")
        )
        result = cmd_summary_extract(tmp_path, path)
        assert result.one_liner == "Derived the Lagrangian"

    def test_key_results_section(self, tmp_path: Path):
        path = self._write_summary(
            tmp_path, ("---\nphase: 01\n---\n\n## Key Results\n\nSome results here.\n\n## Next Steps\n\nDo more.\n")
        )
        result = cmd_summary_extract(tmp_path, path)
        assert result.key_results == "Some results here."

    def test_empty_path_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="summary-path required"):
            cmd_summary_extract(tmp_path, "")

    def test_not_found_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="File not found"):
            cmd_summary_extract(tmp_path, "nonexistent.md")


# ─── cmd_history_digest ───────────────────────────────────────────────────


class TestHistoryDigest:
    def _setup_phases(self, tmp_path: Path) -> None:
        phases_dir = tmp_path / ".planning" / "phases"
        for name in ("01-setup", "02-core"):
            d = phases_dir / name
            d.mkdir(parents=True)

        (phases_dir / "01-setup" / "01-SUMMARY.md").write_text(
            "---\n"
            "name: Setup\n"
            "phase: 1\n"
            "dependency-graph:\n  provides:\n    - base-framework\n  affects:\n    - phase-2\n"
            "patterns-established:\n  - test-driven\n"
            "key-decisions:\n  - Use Python 3.11\n"
            "methods:\n  added:\n    - spectral-method\n"
            "---\n\n# Setup Summary\n"
        )
        (phases_dir / "02-core" / "02-SUMMARY.md").write_text(
            "---\n"
            "name: Core\n"
            "phase: 2\n"
            "provides:\n  - solver\n"
            "patterns-established:\n  - convention-lock\n"
            "---\n\n# Core Summary\n"
        )

    def test_full_digest(self, tmp_path: Path):
        self._setup_phases(tmp_path)
        result = cmd_history_digest(tmp_path)
        assert "1" in result.phases
        assert "2" in result.phases
        assert "base-framework" in result.phases["1"].provides
        assert "phase-2" in result.phases["1"].affects
        assert "test-driven" in result.phases["1"].patterns
        assert "solver" in result.phases["2"].provides
        assert len(result.decisions) == 1
        assert "spectral-method" in result.methods

    def test_empty_project(self, tmp_path: Path):
        result = cmd_history_digest(tmp_path)
        assert result.phases == {}
        assert result.decisions == []
        assert result.methods == []

    def test_no_phases_dir(self, tmp_path: Path):
        (tmp_path / ".planning").mkdir()
        result = cmd_history_digest(tmp_path)
        assert result.phases == {}


# ─── cmd_regression_check ─────────────────────────────────────────────────


class TestRegressionCheck:
    def _setup_complete_phases(self, tmp_path: Path) -> None:
        phases = tmp_path / ".planning" / "phases"
        for name in ("01-setup", "02-core"):
            d = phases / name
            d.mkdir(parents=True)
            (d / f"{name}-01-PLAN.md").write_text("---\nwave: 1\n---\n\n# Plan\n")
            (d / f"{name}-01-SUMMARY.md").write_text(
                f"---\nphase: {name[:2]}\nconventions:\n  - metric = mostly-minus\n---\n\n# Summary\n"
            )

    def test_passing_check(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        result = cmd_regression_check(tmp_path)
        assert result.passed is True
        assert result.phases_checked == 2

    def test_convention_conflict(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        # Add a conflicting convention in phase 2
        phase2_dir = tmp_path / ".planning" / "phases" / "02-core"
        (phase2_dir / "02-core-01-SUMMARY.md").write_text(
            "---\nconventions:\n  - metric = mostly-plus\n---\n\n# Summary\n"
        )
        result = cmd_regression_check(tmp_path)
        assert result.passed is False
        assert len(result.issues) >= 1
        assert result.issues[0].type == "convention_conflict"
        assert result.issues[0].symbol == "metric"

    def test_verification_gap(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        phase1_dir = tmp_path / ".planning" / "phases" / "01-setup"
        (phase1_dir / "01-setup-VERIFICATION.md").write_text(
            "---\nstatus: gaps_found\nscore: 2/5 checks verified\n---\n\n# Verification\n"
        )
        result = cmd_regression_check(tmp_path)
        assert result.passed is False
        issues = [i for i in result.issues if i.type == "unresolved_verification_issues"]
        assert len(issues) == 1
        assert issues[0].gap_count == 3

    def test_quick_mode_limits_phases(self, tmp_path: Path):
        phases = tmp_path / ".planning" / "phases"
        for i in range(1, 6):
            name = f"{str(i).zfill(2)}-phase{i}"
            d = phases / name
            d.mkdir(parents=True)
            (d / f"{name}-01-PLAN.md").write_text("---\nwave: 1\n---\n")
            (d / f"{name}-01-SUMMARY.md").write_text(f"---\nphase: {i}\n---\n")
        result = cmd_regression_check(tmp_path, quick=True)
        assert result.phases_checked == 2

    def test_no_phases(self, tmp_path: Path):
        result = cmd_regression_check(tmp_path)
        assert result.passed is True
        assert result.phases_checked == 0


# ─── cmd_validate_return ──────────────────────────────────────────────────


class TestValidateReturn:
    def _write_return(self, tmp_path: Path, yaml_block: str) -> Path:
        f = tmp_path / "output.md"
        f.write_text(f"# Result\n\n```yaml\n{yaml_block}```\n")
        return f

    def test_valid_return(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: completed\n"
                "  phase: 01\n"
                "  plan: 01\n"
                "  tasks_completed: 5\n"
                "  tasks_total: 5\n"
                "  files_written: 3\n"
                "  duration_seconds: 120\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        assert result.warning_count == 0

    def test_missing_required_field(self, tmp_path: Path):
        f = self._write_return(tmp_path, ("gpd_return:\n  status: completed\n  phase: 01\n"))
        result = cmd_validate_return(f)
        assert result.passed is False
        assert len(result.errors) >= 2  # missing plan, tasks_completed, tasks_total

    def test_invalid_status(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            ("gpd_return:\n  status: unknown\n  phase: 01\n  plan: 01\n  tasks_completed: 3\n  tasks_total: 5\n"),
        )
        result = cmd_validate_return(f)
        assert result.passed is False
        assert "Invalid status" in result.errors[0]

    def test_non_numeric_task_count(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            ("gpd_return:\n  status: completed\n  phase: 01\n  plan: 01\n  tasks_completed: abc\n  tasks_total: 5\n"),
        )
        result = cmd_validate_return(f)
        assert result.passed is False
        assert "not a number" in result.errors[0]

    def test_completed_but_incomplete_warning(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            ("gpd_return:\n  status: completed\n  phase: 01\n  plan: 01\n  tasks_completed: 3\n  tasks_total: 5\n"),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        assert len(result.warnings) >= 1
        task_warnings = [w for w in result.warnings if "tasks_completed" in w]
        assert len(task_warnings) == 1

    def test_recommended_fields_warning(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            ("gpd_return:\n  status: completed\n  phase: 01\n  plan: 01\n  tasks_completed: 5\n  tasks_total: 5\n"),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        recommended_warnings = [w for w in result.warnings if "Recommended field" in w]
        assert len(recommended_warnings) == 2

    def test_no_return_block(self, tmp_path: Path):
        f = tmp_path / "no_return.md"
        f.write_text("# Just a regular file\n\nNo gpd_return here.\n")
        result = cmd_validate_return(f)
        assert result.passed is False
        assert "No gpd_return YAML block found" in result.errors

    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="File not found"):
            cmd_validate_return(tmp_path / "nonexistent.md")

    def test_quoted_values_stripped(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                '  status: "completed"\n'
                "  phase: '01'\n"
                '  plan: "01"\n'
                "  tasks_completed: 5\n"
                "  tasks_total: 5\n"
                "  files_written: 3\n"
                "  duration_seconds: 60\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        assert result.fields["status"] == "completed"
        assert result.fields["phase"] == "01"
