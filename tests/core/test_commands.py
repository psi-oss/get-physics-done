"""Tests for gpd.core.commands — ported JS command functions.

Tests the pure logic functions without filesystem mocking (uses tmp_path).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.commands import (
    cmd_apply_return_updates,
    cmd_current_timestamp,
    cmd_generate_slug,
    cmd_history_digest,
    cmd_regression_check,
    cmd_summary_extract,
    cmd_validate_return,
    cmd_verify_path_exists,
)
from gpd.core.errors import ValidationError
from gpd.core.state import default_state_dict, generate_state_markdown

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
        (tmp_path / "test.txt").write_text("hello", encoding="utf-8")
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
        f.write_text("content", encoding="utf-8")
        result = cmd_verify_path_exists(tmp_path, str(f))
        assert result.exists is True

    def test_empty_path_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="path required"):
            cmd_verify_path_exists(tmp_path, "")


# ─── cmd_summary_extract ──────────────────────────────────────────────────


class TestSummaryExtract:
    def _write_summary(self, tmp_path: Path, content: str) -> str:
        summary = tmp_path / "test-SUMMARY.md"
        summary.write_text(content, encoding="utf-8")
        return "test-SUMMARY.md"

    def test_basic_extract(self, tmp_path: Path):
        path = self._write_summary(
            tmp_path,
            (
                "---\n"
                'phase: "01"\n'
                'plan: "01"\n'
                "depth: standard\n"
                "provides: []\n"
                'completed: "2026-03-22"\n'
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
            tmp_path,
            (
                "---\n"
                'phase: "01"\n'
                'plan: "01"\n'
                "depth: standard\n"
                "provides: []\n"
                'completed: "2026-03-22"\n'
                "one-liner: filtered test\n"
                "affects:\n  - phase-2\n"
                "---\n\n# Summary\n"
            ),
        )
        result = cmd_summary_extract(tmp_path, path, fields=["one_liner"])
        assert isinstance(result, dict)
        assert result["one_liner"] == "filtered test"
        assert "affects" not in result

    def test_body_one_liner_fallback(self, tmp_path: Path):
        path = self._write_summary(
            tmp_path,
            (
                "---\n"
                "phase: 01\n"
                "plan: 01\n"
                "depth: standard\n"
                "provides: []\n"
                "completed: 2026-03-22\n"
                "---\n\n# Phase 1 Summary\n\n**Derived the Lagrangian**\n"
            ),
        )
        result = cmd_summary_extract(tmp_path, path)
        assert result.one_liner == "Derived the Lagrangian"

    def test_key_results_section(self, tmp_path: Path):
        path = self._write_summary(
            tmp_path,
            (
                "---\n"
                "phase: 01\n"
                "plan: 01\n"
                "depth: standard\n"
                "provides: []\n"
                "completed: 2026-03-22\n"
                "---\n\n## Key Results\n\nSome results here.\n\n## Next Steps\n\nDo more.\n"
            ),
        )
        result = cmd_summary_extract(tmp_path, path)
        assert result.key_results == "Some results here."

    def test_empty_path_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="summary-path required"):
            cmd_summary_extract(tmp_path, "")

    def test_not_found_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="File not found"):
            cmd_summary_extract(tmp_path, "nonexistent.md")

    @pytest.mark.parametrize(
        ("frontmatter_fragment", "match"),
        [
            ("key-files: src/main.py\n", r"Invalid key-files in test-SUMMARY\.md"),
            ("key-files:\n  created: src/main.py\n", r"Invalid key-files\.created in test-SUMMARY\.md"),
            ("key-files:\n  createdd:\n    - src/main.py\n", r"Invalid key-files in test-SUMMARY\.md: unexpected key\(s\) createdd"),
            ("methods: finite-difference\n", r"Invalid methods in test-SUMMARY\.md"),
            ("methods:\n  added: finite-difference\n", r"Invalid methods\.added in test-SUMMARY\.md"),
            ("patterns-established: test-first\n", r"Invalid patterns-established in test-SUMMARY\.md"),
            ("affects:\n  - \"\"\n", r"Invalid affects in test-SUMMARY\.md: entry 0 must be a non-empty string"),
            ("key-decisions:\n  - {summary: Use numpy, rationale: Fast, extra: nope}\n", r"Invalid key-decisions in test-SUMMARY\.md"),
        ],
    )
    def test_rejects_malformed_summary_evidence_shapes(
        self,
        tmp_path: Path,
        frontmatter_fragment: str,
        match: str,
    ):
        path = self._write_summary(
            tmp_path,
            (
                "---\n"
                'phase: "01"\n'
                'plan: "01"\n'
                "depth: standard\n"
                "provides: []\n"
                'completed: "2026-03-22"\n'
                f"{frontmatter_fragment}"
                "---\n\n# Summary\n"
            ),
        )

        with pytest.raises(ValidationError, match=match):
            cmd_summary_extract(tmp_path, path)


# ─── cmd_history_digest ───────────────────────────────────────────────────


class TestHistoryDigest:
    def _setup_phases(self, tmp_path: Path) -> None:
        phases_dir = tmp_path / "GPD" / "phases"
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
            "---\n\n# Setup Summary\n", encoding="utf-8"
        )
        (phases_dir / "02-core" / "02-SUMMARY.md").write_text(
            "---\n"
            "name: Core\n"
            "phase: 2\n"
            "provides:\n  - solver\n"
            "patterns-established:\n  - convention-lock\n"
            "---\n\n# Core Summary\n", encoding="utf-8"
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
        (tmp_path / "GPD").mkdir()
        result = cmd_history_digest(tmp_path)
        assert result.phases == {}

    def test_history_digest_rejects_malformed_summary_field_members(self, tmp_path: Path):
        phases_dir = tmp_path / "GPD" / "phases" / "01-setup"
        phases_dir.mkdir(parents=True)
        (phases_dir / "01-SUMMARY.md").write_text(
            "---\n"
            "name: Setup\n"
            "phase: 1\n"
            "provides:\n"
            "  - base-framework\n"
            "patterns-established:\n"
            "  - pattern-a\n"
            "key-decisions:\n"
            "  - Use numpy: fast\n"
            "methods:\n"
            "  added:\n"
            "    - spectral-method\n"
            "dependency-graph:\n"
            "  affects:\n"
            "    - 12\n"
            "---\n\n# Setup Summary\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="Invalid affects in GPD/phases/01-setup/01-SUMMARY\\.md"):
            cmd_history_digest(tmp_path)

    def test_history_digest_rejects_malformed_summary_frontmatter(self, tmp_path: Path):
        phases_dir = tmp_path / "GPD" / "phases" / "01-setup"
        phases_dir.mkdir(parents=True)
        (phases_dir / "01-SUMMARY.md").write_text(
            "---\n"
            "phase: 1\n"
            "provides: [unterminated\n"
            "---\n\n# Setup Summary\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="Malformed frontmatter in GPD/phases/01-setup/01-SUMMARY\\.md"):
            cmd_history_digest(tmp_path)


# ─── cmd_regression_check ─────────────────────────────────────────────────


class TestRegressionCheck:
    def _setup_complete_phases(self, tmp_path: Path) -> None:
        phases = tmp_path / "GPD" / "phases"
        for name in ("01-setup", "02-core"):
            d = phases / name
            d.mkdir(parents=True)
            (d / f"{name}-01-PLAN.md").write_text("---\nwave: 1\n---\n\n# Plan\n", encoding="utf-8")
            (d / f"{name}-01-SUMMARY.md").write_text(
                f"---\nphase: {name[:2]}\nconventions:\n  - metric = mostly-minus\n---\n\n# Summary\n", encoding="utf-8"
            )

    def test_passing_check(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        result = cmd_regression_check(tmp_path)
        assert result.passed is True
        assert result.phases_checked == 2

    def test_convention_conflict(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        # Add a conflicting convention in phase 2
        phase2_dir = tmp_path / "GPD" / "phases" / "02-core"
        (phase2_dir / "02-core-01-SUMMARY.md").write_text(
            "---\nconventions:\n  - metric = mostly-plus\n---\n\n# Summary\n", encoding="utf-8"
        )
        result = cmd_regression_check(tmp_path)
        assert result.passed is False
        assert len(result.issues) >= 1
        assert result.issues[0].type == "convention_conflict"
        assert result.issues[0].symbol == "metric"

    def test_verification_gap(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        phase1_dir = tmp_path / "GPD" / "phases" / "01-setup"
        (phase1_dir / "01-setup-VERIFICATION.md").write_text(
            "---\nstatus: gaps_found\nscore: 2/5 checks verified\n---\n\n# Verification\n", encoding="utf-8"
        )
        result = cmd_regression_check(tmp_path)
        assert result.passed is False
        issues = [i for i in result.issues if i.type == "unresolved_verification_issues"]
        assert len(issues) == 1
        assert issues[0].gap_count == 3

    def test_phase_scope_limits_checks_to_requested_phase(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        phase2_dir = tmp_path / "GPD" / "phases" / "02-core"
        (phase2_dir / "02-core-01-SUMMARY.md").write_text(
            "---\nconventions:\n  - metric = mostly-plus\n---\n\n# Summary\n", encoding="utf-8"
        )
        result = cmd_regression_check(tmp_path, phase="1")
        assert result.passed is True
        assert result.phases_checked == 1

    def test_invalid_verification_status_is_flagged(self, tmp_path: Path):
        self._setup_complete_phases(tmp_path)
        phase1_dir = tmp_path / "GPD" / "phases" / "01-setup"
        (phase1_dir / "01-setup-VERIFICATION.md").write_text(
            "---\nstatus: validating\nscore: 2/5 checks verified\n---\n\n# Verification\n", encoding="utf-8"
        )
        result = cmd_regression_check(tmp_path)
        assert result.passed is False
        issues = [i for i in result.issues if i.type == "invalid_verification_status"]
        assert len(issues) == 1
        assert issues[0].status == "validating"
        assert "must be one of" in (issues[0].error or "")

    def test_quick_mode_limits_phases(self, tmp_path: Path):
        phases = tmp_path / "GPD" / "phases"
        for i in range(1, 6):
            name = f"{str(i).zfill(2)}-phase{i}"
            d = phases / name
            d.mkdir(parents=True)
            (d / f"{name}-01-PLAN.md").write_text("---\nwave: 1\n---\n", encoding="utf-8")
            (d / f"{name}-01-SUMMARY.md").write_text(f"---\nphase: {i}\n---\n", encoding="utf-8")
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
        f.write_text(f"# Result\n\n```yaml\n{yaml_block}```\n", encoding="utf-8")
        return f

    def test_valid_return(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: completed\n"
                "  files_written: [src/main.py]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:verify-work 01]\n"
                "  duration_seconds: 120\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        assert result.warning_count == 0

    def test_missing_required_field(self, tmp_path: Path):
        f = self._write_return(tmp_path, ("gpd_return:\n  status: completed\n"))
        result = cmd_validate_return(f)
        assert result.passed is False
        assert "Missing required field: files_written" in result.errors
        assert "Missing required field: issues" in result.errors
        assert "Missing required field: next_actions" in result.errors

    def test_invalid_status(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: unknown\n"
                "  files_written: [src/main.py]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:verify-work 01]\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is False
        assert "Invalid status" in result.errors[0]

    def test_non_numeric_task_count(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: completed\n"
                "  files_written: [src/main.py]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:verify-work 01]\n"
                "  tasks_completed: abc\n"
                "  tasks_total: 5\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is False
        assert "not a number" in result.errors[0]

    def test_completed_but_incomplete_warning(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: completed\n"
                "  files_written: [src/main.py]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:verify-work 01]\n"
                "  tasks_completed: 3\n"
                "  tasks_total: 5\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        assert len(result.warnings) >= 1
        task_warnings = [w for w in result.warnings if "tasks_completed" in w]
        assert len(task_warnings) == 1

    def test_recommended_fields_warning(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: completed\n"
                "  files_written: [src/main.py]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:verify-work 01]\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        recommended_warnings = [w for w in result.warnings if "Recommended field" in w]
        assert len(recommended_warnings) == 1

    def test_no_return_block(self, tmp_path: Path):
        f = tmp_path / "no_return.md"
        f.write_text("# Just a regular file\n\nNo gpd_return here.\n", encoding="utf-8")
        result = cmd_validate_return(f)
        assert result.passed is False
        assert "No gpd_return YAML block found" in result.errors

    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError, match="File not found"):
            cmd_validate_return(tmp_path / "nonexistent.md")


class TestApplyReturnUpdates:
    def _write_state_project(self, tmp_path: Path) -> tuple[Path, Path]:
        planning = tmp_path / "GPD"
        planning.mkdir()
        state = default_state_dict()
        (planning / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
        return planning, planning / "STATE.md"

    def _write_return(self, tmp_path: Path, yaml_body: str) -> Path:
        f = tmp_path / "output.md"
        f.write_text(f"# Result\n\n```yaml\n{yaml_body}```\n", encoding="utf-8")
        return f

    def test_applies_explicit_state_changes_and_preserves_contract_updates(self, tmp_path: Path):
        _, state_path = self._write_state_project(tmp_path)
        before = state_path.read_text(encoding="utf-8")
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: checkpoint\n"
                "  files_written: [GPD/STATE.md]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:resume-work]\n"
                "  decisions:\n"
                "    - summary: Prefer canonical child-return application\n"
                '      phase: "10"\n'
                "  blockers:\n"
                "    - waiting on approval\n"
                "  contract_updates:\n"
                "    project_contract: retained\n"
            ),
        )

        result = cmd_apply_return_updates(tmp_path, f)

        assert result.passed is True
        assert result.status == "checkpoint"
        assert result.applied_decisions == 1
        assert result.applied_blockers == 1
        assert result.applied_state_operations == []
        assert result.applied_continuation_operations == []
        assert result.contract_updates == {"project_contract": "retained"}
        assert state_path.read_text(encoding="utf-8") != before
        updated_state = state_path.read_text(encoding="utf-8")
        assert "Prefer canonical child-return application" in updated_state
        assert "waiting on approval" in updated_state

    def test_rejects_unsupported_state_update_keys_before_mutation(self, tmp_path: Path):
        _, state_path = self._write_state_project(tmp_path)
        before = state_path.read_text(encoding="utf-8")
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: checkpoint\n"
                "  files_written: [GPD/STATE.md]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:resume-work]\n"
                "  state_updates:\n"
                "    unexpected_operation: true\n"
            ),
        )

        result = cmd_apply_return_updates(tmp_path, f)

        assert result.passed is False
        assert result.status == "failed"
        assert any("state_updates" in error and "unexpected_operation" in error for error in result.errors)
        assert state_path.read_text(encoding="utf-8") == before

    def test_quoted_values_stripped(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                '  status: "completed"\n'
                '  files_written: ["src/main.py"]\n'
                "  issues: []\n"
                '  next_actions: ["/gpd:verify-work 01"]\n'
                "  duration_seconds: 60\n"
            ),
        )
        result = cmd_validate_return(f)
        assert result.passed is True
        assert result.fields["status"] == "completed"
        assert result.fields["files_written"] == ["src/main.py"]
        assert result.fields["next_actions"] == ["/gpd:verify-work 01"]

    def test_block_list_values_are_parsed(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: checkpoint\n"
                "  files_written:\n"
                "    - src/main.py\n"
                "    - tests/test_main.py\n"
                "  issues:\n"
                "    - waiting on benchmark rerun\n"
                "  next_actions:\n"
                "    - /gpd:verify-work 01\n"
            ),
        )

        result = cmd_validate_return(f)

        assert result.passed is True
        assert result.fields["files_written"] == ["src/main.py", "tests/test_main.py"]
        assert result.fields["issues"] == ["waiting on benchmark rerun"]
        assert result.fields["next_actions"] == ["/gpd:verify-work 01"]

    def test_nested_continuation_payload_is_preserved(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: checkpoint\n"
                "  files_written: [src/main.py]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:resume-work]\n"
                "  state_updates:\n"
                "    advance_plan: true\n"
                "    update_progress: true\n"
                "  continuation_update:\n"
                "    handoff:\n"
                "      recorded_at: 2026-04-08T12:00:00Z\n"
                "      recorded_by: execute-plan\n"
                "      stopped_at: Completed phase 01\n"
                "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
                "    bounded_segment:\n"
                "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
                "      phase: 01\n"
                "      plan: 01\n"
                "      segment_id: seg-01\n"
                "      segment_status: paused\n"
                "      checkpoint_reason: segment_boundary\n"
            ),
        )

        result = cmd_validate_return(f)

        assert result.passed is True
        assert result.fields["state_updates"]["advance_plan"] is True
        assert result.fields["state_updates"]["update_progress"] is True
        assert result.fields["continuation_update"]["handoff"]["recorded_by"] == "execute-plan"
        assert result.fields["continuation_update"]["bounded_segment"]["segment_id"] == "seg-01"

    def test_rejects_transport_only_execution_segment_inside_continuation_update(self, tmp_path: Path):
        f = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: checkpoint\n"
                "  files_written: [src/main.py]\n"
                "  issues: []\n"
                "  next_actions: [/gpd:resume-work]\n"
                "  continuation_update:\n"
                "    execution_segment:\n"
                "      current_cursor: 3\n"
            ),
        )

        result = cmd_validate_return(f)

        assert result.passed is False
        assert any("continuation_update" in error and "execution_segment" in error for error in result.errors)

    def test_rejects_scalar_and_nested_map_shape_errors(self, tmp_path: Path):
        scalar_file = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: completed\n"
                "  files_written: src/main.py\n"
                "  issues: []\n"
                "  next_actions: [/gpd:verify-work 01]\n"
            ),
        )
        scalar_result = cmd_validate_return(scalar_file)
        assert scalar_result.passed is False
        assert any("files_written" in error and "list" in error for error in scalar_result.errors)

        nested_map_file = self._write_return(
            tmp_path,
            (
                "gpd_return:\n"
                "  status: blocked\n"
                "  files_written: []\n"
                "  issues: []\n"
                "  next_actions: []\n"
                "  blockers:\n"
                "    - waiting on approval\n"
                "  continuation_update: checkpoint\n"
            ),
        )
        nested_result = cmd_validate_return(nested_map_file)
        assert nested_result.passed is False
        assert any("continuation_update" in error for error in nested_result.errors)
