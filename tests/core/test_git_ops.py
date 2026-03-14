"""Tests for gpd.core.git_ops — commit and pre-commit check logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.git_ops import (
    CommitResult,
    PreCommitCheckResult,
    cmd_commit,
    cmd_pre_commit_check,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Pre-commit check — unit tests
# ---------------------------------------------------------------------------


class TestPreCommitCheck:
    """Tests for cmd_pre_commit_check."""

    def test_no_files_passes(self, tmp_path: Path) -> None:
        result = cmd_pre_commit_check(tmp_path, [])
        assert result.passed is True
        assert result.files_checked == 0

    @patch("gpd.core.git_ops._exec_git")
    def test_no_files_checks_staged_files_when_available(self, mock_git: MagicMock, tmp_path: Path) -> None:
        md = tmp_path / "state.md"
        md.write_text("# ok\n", encoding="utf-8")
        mock_git.return_value = (0, "state.md", "")

        result = cmd_pre_commit_check(tmp_path, [])

        assert result.passed is True
        assert result.files_checked == 1
        assert result.details[0].file == "state.md"

    def test_valid_markdown_passes(self, tmp_path: Path) -> None:
        md = tmp_path / "test.md"
        md.write_text("---\nstatus: active\n---\n\n# Hello\n", encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["test.md"])
        assert result.passed is True
        assert result.files_checked == 1
        assert result.details[0].frontmatter_valid is True
        assert result.details[0].has_nan is False

    def test_invalid_frontmatter_fails(self, tmp_path: Path) -> None:
        md = tmp_path / "bad.md"
        md.write_text("---\n: bad: yaml: [unclosed\n---\n\n# Oops\n", encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["bad.md"])
        assert result.passed is False
        assert result.details[0].frontmatter_valid is False
        assert any("parse error" in w.lower() or "yaml" in w.lower() for w in result.warnings)

    def test_nan_detection_fails(self, tmp_path: Path) -> None:
        md = tmp_path / "nan.md"
        md.write_text("---\nstatus: done\n---\n\nResult: NaN\n", encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["nan.md"])
        assert result.passed is False
        assert result.details[0].has_nan is True

    def test_inf_detection_fails(self, tmp_path: Path) -> None:
        md = tmp_path / "inf.md"
        md.write_text("---\nstatus: done\n---\n\nValue: -inf\n", encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["inf.md"])
        assert result.passed is False
        assert result.details[0].has_nan is True

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        result = cmd_pre_commit_check(tmp_path, ["nonexistent.md"])
        assert result.passed is False
        assert result.details[0].exists is False

    def test_no_frontmatter_still_passes(self, tmp_path: Path) -> None:
        md = tmp_path / "plain.md"
        md.write_text("# Just a heading\n\nSome text.\n", encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["plain.md"])
        assert result.passed is True
        assert result.details[0].frontmatter_valid is True

    def test_non_markdown_file_skips_frontmatter(self, tmp_path: Path) -> None:
        txt = tmp_path / "data.json"
        txt.write_text('{"key": "value"}', encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["data.json"])
        assert result.passed is True
        assert result.details[0].frontmatter_valid is None  # not checked

    def test_json_nonfinite_detection_fails(self, tmp_path: Path) -> None:
        txt = tmp_path / "data.json"
        txt.write_text('{"value": NaN}', encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["data.json"])
        assert result.passed is False
        assert result.details[0].has_nan is True

    def test_multiple_files_mixed(self, tmp_path: Path) -> None:
        good = tmp_path / "good.md"
        good.write_text("---\nok: true\n---\n\nFine.\n", encoding="utf-8")
        bad = tmp_path / "bad.md"
        bad.write_text("---\nstatus: done\n---\n\nResult: nan\n", encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["good.md", "bad.md"])
        assert result.passed is False
        assert result.files_checked == 2

    def test_nan_in_word_no_false_positive(self, tmp_path: Path) -> None:
        """NaN inside a word (e.g. Nantes) should not trigger."""
        md = tmp_path / "nantes.md"
        md.write_text("---\ncity: Nantes\n---\n\nVisit Nantes.\n", encoding="utf-8")
        result = cmd_pre_commit_check(tmp_path, ["nantes.md"])
        # The word "Nantes" should not trigger NaN detection
        assert result.details[0].has_nan is False

    def test_prose_and_limit_notation_do_not_trigger_false_positive(self, tmp_path: Path) -> None:
        md = tmp_path / "plan.md"
        md.write_text(
            "---\nstatus: active\n---\n\n"
            "- Minimal test run completes without segfaults, NaN, or Inf\n"
            "- Verify output contains no NaN values\n"
            "- Thermodynamic limit: L -> inf\n"
            "- Branch cut on (-infinity, 0]\n",
            encoding="utf-8",
        )
        result = cmd_pre_commit_check(tmp_path, ["plan.md"])
        assert result.passed is True
        assert result.details[0].has_nan is False

    def test_directory_inputs_are_checked_recursively(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "ok.md").write_text("---\nstatus: active\n---\n\nFine.\n", encoding="utf-8")

        result = cmd_pre_commit_check(tmp_path, ["docs"])

        assert result.passed is True
        assert result.files_checked == 1
        assert result.details[0].file == "docs/ok.md"

    def test_scratch_commit_target_fails_storage_validation(self, tmp_path: Path) -> None:
        target = tmp_path / ".gpd" / "tmp" / "final.csv"
        target.parent.mkdir(parents=True)
        target.write_text("x,y\n", encoding="utf-8")

        result = cmd_pre_commit_check(tmp_path, [".gpd/tmp/final.csv"])

        assert result.passed is False
        assert result.details[0].storage_valid is False
        assert result.details[0].storage_class == "scratch"
        assert any("scratch directories" in warning for warning in result.warnings)

    def test_project_local_tmp_commit_target_fails_storage_validation(self, tmp_path: Path) -> None:
        target = tmp_path / "tmp" / "final.csv"
        target.parent.mkdir(parents=True)
        target.write_text("x,y\n", encoding="utf-8")

        result = cmd_pre_commit_check(tmp_path, ["tmp/final.csv"])

        assert result.passed is False
        assert result.details[0].storage_valid is False
        assert result.details[0].storage_class == "project_local_other"
        assert any("scratch directories" in warning for warning in result.warnings)

    def test_internal_artifact_commit_target_fails_storage_validation(self, tmp_path: Path) -> None:
        target = tmp_path / ".gpd" / "paper" / "main.tex"
        target.parent.mkdir(parents=True)
        target.write_text("\\documentclass{article}\n", encoding="utf-8")

        result = cmd_pre_commit_check(tmp_path, [".gpd/paper/main.tex"])

        assert result.passed is False
        assert result.details[0].storage_valid is False
        assert result.details[0].storage_class == "internal_durable"
        assert any("internal metadata directories" in warning for warning in result.warnings)


# ---------------------------------------------------------------------------
# Commit — unit tests (mocked git)
# ---------------------------------------------------------------------------


class TestCommit:
    """Tests for cmd_commit with mocked git subprocess."""

    def test_empty_message_raises(self, tmp_path: Path) -> None:
        from gpd.core.errors import ValidationError

        with pytest.raises(ValidationError, match="required"):
            cmd_commit(tmp_path, "")

    def test_whitespace_message_raises(self, tmp_path: Path) -> None:
        from gpd.core.errors import ValidationError

        with pytest.raises(ValidationError, match="required"):
            cmd_commit(tmp_path, "   ")

    def test_successful_commit(self, tmp_path: Path) -> None:
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=True)),
            patch(
                "gpd.core.git_ops.cmd_pre_commit_check",
                return_value=PreCommitCheckResult(passed=True, files_checked=1),
            ) as mock_precheck,
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            # git add succeeds, diff --cached shows changes, commit succeeds, rev-parse returns SHA
            mock_git.side_effect = [
                (0, "", ""),       # git add
                (1, "", ""),       # git diff --cached --quiet (1 = has changes)
                (0, "", ""),       # git commit
                (0, "abc1234", ""),  # git rev-parse
            ]
            result = cmd_commit(tmp_path, "test: commit message", files=[".gpd/STATE.md"])

        assert result.committed is True
        assert result.sha == "abc1234"
        assert result.message == "test: commit message"
        mock_precheck.assert_called_once_with(tmp_path, [".gpd/STATE.md"])

    def test_nothing_to_commit(self, tmp_path: Path) -> None:
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=True)),
            patch(
                "gpd.core.git_ops.cmd_pre_commit_check",
                return_value=PreCommitCheckResult(passed=True, files_checked=1),
            ),
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            mock_git.side_effect = [
                (0, "", ""),  # git add
                (0, "", ""),  # git diff --cached --quiet (0 = no changes)
            ]
            result = cmd_commit(tmp_path, "test: no changes")
        assert result.committed is False
        assert "nothing to commit" in (result.error or "")
        assert result.reason == "nothing_to_commit"

    def test_git_add_failure(self, tmp_path: Path) -> None:
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=True)),
            patch(
                "gpd.core.git_ops.cmd_pre_commit_check",
                return_value=PreCommitCheckResult(passed=True, files_checked=1),
            ),
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            mock_git.side_effect = [
                (128, "", "fatal: not a git repository"),  # git add fails
            ]
            result = cmd_commit(tmp_path, "test: failing add")
        assert result.committed is False
        assert "git add failed" in (result.error or "")
        assert result.reason == "git_add_failed"

    def test_git_commit_failure(self, tmp_path: Path) -> None:
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=True)),
            patch(
                "gpd.core.git_ops.cmd_pre_commit_check",
                return_value=PreCommitCheckResult(passed=True, files_checked=1),
            ),
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            mock_git.side_effect = [
                (0, "", ""),     # git add
                (1, "", ""),     # diff --cached (has changes)
                (1, "", "error: something went wrong"),  # git commit fails
            ]
            result = cmd_commit(tmp_path, "test: failing commit")
        assert result.committed is False
        assert "git commit failed" in (result.error or "")
        assert result.reason == "git_commit_failed"

    def test_default_files_stages_planning(self, tmp_path: Path) -> None:
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=True)),
            patch(
                "gpd.core.git_ops.cmd_pre_commit_check",
                return_value=PreCommitCheckResult(passed=True, files_checked=1),
            ) as mock_precheck,
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            mock_git.side_effect = [
                (0, "", ""),       # git add
                (1, "", ""),       # diff --cached
                (0, "", ""),       # git commit
                (0, "def5678", ""),  # rev-parse
            ]
            cmd_commit(tmp_path, "test: default staging")
            # Verify the git add was called with .gpd/
            add_call = mock_git.call_args_list[0]
            assert ".gpd/" in add_call[0][1]
            mock_precheck.assert_called_once_with(tmp_path, [".gpd/"])

    def test_empty_files_defaults_to_planning_dir(self, tmp_path: Path) -> None:
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=True)),
            patch(
                "gpd.core.git_ops.cmd_pre_commit_check",
                return_value=PreCommitCheckResult(passed=True, files_checked=1),
            ) as mock_precheck,
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            mock_git.side_effect = [
                (0, "", ""),       # git add
                (1, "", ""),       # diff --cached
                (0, "", ""),       # git commit
                (0, "def5678", ""),  # rev-parse
            ]
            cmd_commit(tmp_path, "test: default staging", files=[])
            add_call = mock_git.call_args_list[0]
            assert ".gpd/" in add_call[0][1]
            mock_precheck.assert_called_once_with(tmp_path, [".gpd/"])

    def test_commit_blocks_when_pre_commit_check_fails(self, tmp_path: Path) -> None:
        pre_commit = PreCommitCheckResult(
            passed=False,
            files_checked=1,
            warnings=["File contains NaN or Inf values"],
        )
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=True)),
            patch("gpd.core.git_ops.cmd_pre_commit_check", return_value=pre_commit),
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            result = cmd_commit(tmp_path, "test: blocked", files=["bad.md"])

        assert result.committed is False
        assert result.reason == "pre_commit_check_failed"
        assert result.pre_commit == pre_commit
        mock_git.assert_not_called()

    def test_commit_skips_when_commit_docs_disabled(self, tmp_path: Path) -> None:
        with (
            patch("gpd.core.config.load_config", return_value=MagicMock(commit_docs=False)),
            patch("gpd.core.git_ops.cmd_pre_commit_check") as mock_precheck,
            patch("gpd.core.git_ops._exec_git") as mock_git,
        ):
            result = cmd_commit(tmp_path, "test: skipped", files=[".gpd/STATE.md"])

        assert result.committed is False
        assert result.skipped is True
        assert result.reason == "commit_docs_disabled"
        mock_precheck.assert_not_called()
        mock_git.assert_not_called()


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestCommitCLI:
    """Tests for the CLI wiring of commit and pre-commit-check."""

    @patch("gpd.core.git_ops.cmd_commit")
    def test_commit_cli(self, mock_commit: MagicMock) -> None:
        mock_commit.return_value = CommitResult(
            committed=True,
            message="test: message",
            files=[".gpd/STATE.md"],
            sha="abc1234",
        )
        result = runner.invoke(app, ["commit", "test: message", "--files", ".gpd/STATE.md"])
        assert result.exit_code == 0
        mock_commit.assert_called_once()

    @patch("gpd.core.git_ops.cmd_commit")
    def test_commit_cli_failure_exits_1(self, mock_commit: MagicMock) -> None:
        mock_commit.return_value = CommitResult(
            committed=False,
            message="test: message",
            error="nothing to commit",
        )
        result = runner.invoke(app, ["commit", "test: message"])
        assert result.exit_code == 1

    @patch("gpd.core.git_ops.cmd_commit")
    def test_commit_cli_skip_exits_0(self, mock_commit: MagicMock) -> None:
        mock_commit.return_value = CommitResult(
            committed=False,
            skipped=True,
            reason="commit_docs_disabled",
            message="test: message",
        )
        result = runner.invoke(app, ["commit", "test: message"])
        assert result.exit_code == 0

    @patch("gpd.core.git_ops.cmd_pre_commit_check")
    def test_pre_commit_check_cli_pass(self, mock_check: MagicMock) -> None:
        mock_check.return_value = PreCommitCheckResult(
            passed=True,
            files_checked=1,
        )
        result = runner.invoke(app, ["pre-commit-check", "--files", ".gpd/STATE.md"])
        assert result.exit_code == 0
        mock_check.assert_called_once()

    @patch("gpd.core.git_ops.cmd_commit")
    def test_commit_cli_accepts_multiple_paths_after_single_files_flag(self, mock_commit: MagicMock) -> None:
        mock_commit.return_value = CommitResult(
            committed=True,
            message="test: message",
            files=[".gpd/PROJECT.md", ".gpd/state.json"],
            sha="abc1234",
        )
        result = runner.invoke(
            app,
            ["commit", "test: message", "--files", ".gpd/PROJECT.md", ".gpd/state.json"],
        )
        assert result.exit_code == 0
        mock_commit.assert_called_once_with(
            ANY,
            "test: message",
            files=[".gpd/PROJECT.md", ".gpd/state.json"],
        )

    @patch("gpd.core.git_ops.cmd_pre_commit_check")
    def test_pre_commit_check_cli_accepts_multiple_paths_after_single_files_flag(self, mock_check: MagicMock) -> None:
        mock_check.return_value = PreCommitCheckResult(
            passed=True,
            files_checked=2,
        )
        result = runner.invoke(
            app,
            ["pre-commit-check", "--files", ".gpd/PROJECT.md", ".gpd/state.json"],
        )
        assert result.exit_code == 0
        mock_check.assert_called_once_with(
            ANY,
            [".gpd/PROJECT.md", ".gpd/state.json"],
        )

    @patch("gpd.core.git_ops.cmd_pre_commit_check")
    def test_pre_commit_check_cli_fail(self, mock_check: MagicMock) -> None:
        mock_check.return_value = PreCommitCheckResult(
            passed=False,
            files_checked=1,
            warnings=["Frontmatter error"],
        )
        result = runner.invoke(app, ["pre-commit-check", "--files", "bad.md"])
        assert result.exit_code == 1

    def test_commit_appears_in_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "commit" in result.output

    def test_pre_commit_check_appears_in_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "pre-commit-check" in result.output
