"""Regression tests for bug fixes found in the third 12-agent codebase audit.

Each test targets a specific bug fix and verifies the corrected behavior.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bug 1 & 15: Progress percent capping at 100%
# (phases.py: progress_render and roadmap_analyze cap progress when
# summaries > plans)
# ---------------------------------------------------------------------------


class TestProgressPercentCapping:
    """progress_render and roadmap_analyze should cap progress at 100%."""

    def _setup_phases(self, tmp_path: Path, plan_counts: dict[str, int], summary_counts: dict[str, int]) -> None:
        """Create .gpd/phases/ directories with given plan and summary file counts."""
        gpd = tmp_path / ".gpd"
        phases_dir = gpd / "phases"
        # Create ROADMAP.md so get_milestone_info works
        gpd.mkdir(parents=True)
        (gpd / "ROADMAP.md").write_text("## v1.0: Test\n\n", encoding="utf-8")

        for phase_name in plan_counts:
            phase_dir = phases_dir / phase_name
            phase_dir.mkdir(parents=True)
            for i in range(plan_counts[phase_name]):
                (phase_dir / f"task-{i}-PLAN.md").write_text(f"plan {i}", encoding="utf-8")
            for i in range(summary_counts.get(phase_name, 0)):
                (phase_dir / f"task-{i}-SUMMARY.md").write_text(f"summary {i}", encoding="utf-8")

    def test_progress_render_caps_at_100(self, tmp_path: Path) -> None:
        """When summaries > plans, percent should be 100, not > 100."""
        from gpd.core.phases import progress_render

        # 2 plans, 4 summaries -> would be 200% without capping
        self._setup_phases(tmp_path, {"01-phase": 2}, {"01-phase": 4})
        result = progress_render(tmp_path, fmt="json")
        assert result.percent <= 100

    def test_progress_render_bar_caps_at_100(self, tmp_path: Path) -> None:
        """Bar format should also cap percent."""
        from gpd.core.phases import progress_render

        self._setup_phases(tmp_path, {"01-phase": 2}, {"01-phase": 5})
        result = progress_render(tmp_path, fmt="bar")
        assert result.percent <= 100

    def test_progress_render_table_caps_at_100(self, tmp_path: Path) -> None:
        """Table format should also cap percent."""
        from gpd.core.phases import progress_render

        self._setup_phases(tmp_path, {"01-phase": 1}, {"01-phase": 3})
        result = progress_render(tmp_path, fmt="table")
        # Table format has percent in the rendered string
        match = re.search(r"\((\d+)%\)", result.rendered)
        assert match is not None
        assert int(match.group(1)) <= 100

    def test_roadmap_analyze_caps_at_100(self, tmp_path: Path) -> None:
        """roadmap_analyze progress_percent should cap at 100."""
        from gpd.core.phases import roadmap_analyze

        gpd = tmp_path / ".gpd"
        phases_dir = gpd / "phases"

        # Create phase directory first (so it exists before ROADMAP.md is read)
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "task-1-PLAN.md").write_text("plan", encoding="utf-8")
        (phase_dir / "task-1-SUMMARY.md").write_text("summary 1", encoding="utf-8")
        (phase_dir / "task-2-SUMMARY.md").write_text("summary 2", encoding="utf-8")
        (phase_dir / "task-3-SUMMARY.md").write_text("summary 3", encoding="utf-8")

        # Create ROADMAP.md with phase headings
        roadmap = "## v1.0: Test\n\n### Phase 1: Setup\n\n**Goal:** Set up things\n"
        (gpd / "ROADMAP.md").write_text(roadmap, encoding="utf-8")

        result = roadmap_analyze(tmp_path)
        assert result.progress_percent <= 100


# ---------------------------------------------------------------------------
# Bug 2: Convention warning false positive for metric_signature
# ---------------------------------------------------------------------------


class TestConventionWarningFalsePositive:
    """Setting metric_signature to '(+,-,-,-)' should NOT produce a warning."""

    def test_no_warning_for_standard_metric_signature(self, tmp_path: Path) -> None:
        """Setting '(+,-,-,-)' normalizes to 'mostly-minus' which is standard."""
        from gpd.core.conventions import normalize_key, normalize_value
        from gpd.mcp.servers.conventions_server import CONVENTION_OPTIONS

        canonical = normalize_key("metric_signature")
        options = CONVENTION_OPTIONS.get(canonical, [])
        normalized_options = [normalize_value(canonical, o) for o in options]

        # The result value after convention_set is "mostly-minus" (normalized)
        result_value = normalize_value(canonical, "(+,-,-,-)")
        assert result_value == "mostly-minus"
        # The fix ensures "mostly-minus" is found in normalized_options
        assert result_value in normalized_options

    def test_convention_set_mcp_no_false_warning(self, tmp_path: Path) -> None:
        """Full MCP convention_set should not produce 'Non-standard value' warning."""
        from gpd.mcp.servers.conventions_server import convention_set

        # Create a minimal state.json
        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir(parents=True)
        state_json = gpd_dir / "state.json"
        state_json.write_text("{}", encoding="utf-8")

        result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")
        assert result["status"] == "set"
        assert "warning" not in result

    def test_convention_set_mostly_plus_no_warning(self, tmp_path: Path) -> None:
        """Setting '(-,+,+,+)' normalizes to 'mostly-plus' which is also standard."""
        from gpd.mcp.servers.conventions_server import convention_set

        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir(parents=True)
        state_json = gpd_dir / "state.json"
        state_json.write_text("{}", encoding="utf-8")

        result = convention_set(str(tmp_path), "metric_signature", "(-,+,+,+)")
        assert result["status"] == "set"
        assert "warning" not in result


# ---------------------------------------------------------------------------
# Bug 3: Traceability response consistency (errors_mcp.py)
# ---------------------------------------------------------------------------


class TestTraceabilityResponseConsistency:
    """get_traceability should return 'verification_checks' in both cases."""

    def test_no_data_case_has_verification_checks_key(self) -> None:
        """When no traceability data exists, response must still include verification_checks."""
        from gpd.mcp.servers.errors_mcp import ErrorStore, get_traceability

        # Use a mock store that returns an error but has no traceability data
        with patch("gpd.mcp.servers.errors_mcp._get_store") as mock_store_fn:
            store = MagicMock(spec=ErrorStore)
            # Return a valid error class but no traceability data
            store.get.return_value = {"id": 999, "name": "TestError"}
            store.get_traceability.return_value = None
            mock_store_fn.return_value = store

            result = get_traceability(999)
            assert "verification_checks" in result
            assert result["verification_checks"] == {}
            assert result["coverage_count"] == 0

    def test_success_case_has_verification_checks_key(self) -> None:
        """When traceability data exists, response must include verification_checks."""
        from gpd.mcp.servers.errors_mcp import ErrorStore, get_traceability

        with patch("gpd.mcp.servers.errors_mcp._get_store") as mock_store_fn:
            store = MagicMock(spec=ErrorStore)
            store.get.return_value = {"id": 1, "name": "TestError"}
            store.get_traceability.return_value = {"Dimensional Analysis": "direct"}
            mock_store_fn.return_value = store

            result = get_traceability(1)
            assert "verification_checks" in result
            assert result["verification_checks"] == {"Dimensional Analysis": "direct"}


# ---------------------------------------------------------------------------
# Bug 4: PatternError handling in add_pattern MCP tool
# ---------------------------------------------------------------------------


class TestPatternErrorHandling:
    """add_pattern MCP tool should return error dict, not raise."""

    def test_pattern_error_returns_dict(self) -> None:
        """PatternError during pattern_add should be caught and return {'error': ...}."""
        from gpd.core.errors import PatternError
        from gpd.mcp.servers.patterns_server import add_pattern

        with patch("gpd.mcp.servers.patterns_server.pattern_add") as mock_add:
            mock_add.side_effect = PatternError("Invalid domain")
            result = add_pattern(domain="invalid", title="Test")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid domain" in result["error"]

    def test_pattern_error_does_not_raise(self) -> None:
        """Calling add_pattern with bad inputs should not raise PatternError."""
        from gpd.core.errors import PatternError
        from gpd.mcp.servers.patterns_server import add_pattern

        with patch("gpd.mcp.servers.patterns_server.pattern_add") as mock_add:
            mock_add.side_effect = PatternError("duplicate title")
            # This should NOT raise
            result = add_pattern(domain="qft", title="test", category="sign-error")
        assert "error" in result


# ---------------------------------------------------------------------------
# Bug 5: PRL/APJ empty affiliation should not render \affiliation{}
# ---------------------------------------------------------------------------


class TestEmptyAffiliation:
    """Templates should not render \\affiliation{} for empty affiliation."""

    def test_prl_empty_affiliation(self) -> None:
        """PRL template should skip affiliation when empty."""
        from gpd.mcp.paper.models import Author, PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Test Paper",
            authors=[Author(name="John Doe", email="john@example.com", affiliation="")],
            abstract="Test abstract.",
            sections=[Section(title="Introduction", content="Hello.")],
            journal="prl",
        )
        tex = render_paper(config)
        assert "\\author{John Doe}" in tex
        # Should NOT have empty affiliation
        assert "\\affiliation{}" not in tex

    def test_apj_empty_affiliation(self) -> None:
        """APJ template should skip affiliation when empty."""
        from gpd.mcp.paper.models import Author, PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Test Paper",
            authors=[Author(name="Jane Doe", affiliation="")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Content.")],
            journal="apj",
        )
        tex = render_paper(config)
        assert "\\affiliation{}" not in tex


# ---------------------------------------------------------------------------
# Bug 6: MNRAS/Nature zero authors should not crash with \\
# ---------------------------------------------------------------------------


class TestZeroAuthors:
    """Templates should handle empty authors list without crashing."""

    def test_mnras_empty_authors(self) -> None:
        """MNRAS template should render without crashing on empty authors."""
        from gpd.mcp.paper.models import PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Test Paper",
            authors=[],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Content.")],
            journal="mnras",
        )
        tex = render_paper(config)
        # Should not contain a lone \\ that would crash LaTeX
        # (the template uses \BLOCK{if authors}\\ to guard against this)
        assert "\\author" in tex
        # When authors is empty, the block between \author[]{...} should not
        # have a dangling \\
        author_block_match = re.search(r"\\author\[]\{(.*?)\}", tex, re.DOTALL)
        assert author_block_match is not None, "Expected \\author block in MNRAS template"
        inner = author_block_match.group(1).strip()
        # The inner content should be empty or minimal, not contain \\
        assert inner == "" or "\\\\" not in inner

    def test_nature_empty_authors(self) -> None:
        """Nature template should render without crashing on empty authors."""
        from gpd.mcp.paper.models import PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Test Paper",
            authors=[],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Content.")],
            journal="nature",
        )
        tex = render_paper(config)
        author_match = re.search(r"\\author\{(.*?)\}", tex, re.DOTALL)
        assert author_match is not None, "Expected \\author block in Nature template"
        inner = author_match.group(1).strip()
        assert inner == "" or "\\\\[6pt]" not in inner


# ---------------------------------------------------------------------------
# Bug 7: State newline sanitization
# ---------------------------------------------------------------------------


class TestStateNewlineSanitization:
    """state_add_decision and state_add_blocker should strip newlines."""

    def _make_state_md(self, tmp_path: Path) -> Path:
        """Create a minimal STATE.md with Decisions and Blockers sections."""
        gpd = tmp_path / ".gpd"
        gpd.mkdir(parents=True)
        state_md = gpd / "STATE.md"
        content = (
            "# State\n\n"
            "## Current Position\n\n"
            "**Status:** Active\n\n"
            "### Decisions\nNone yet.\n\n"
            "### Blockers\nNone.\n"
        )
        state_md.write_text(content, encoding="utf-8")
        # Also create state.json (needed for the lock)
        (gpd / "state.json").write_text("{}", encoding="utf-8")
        return state_md

    def test_decision_newlines_stripped(self, tmp_path: Path) -> None:
        """Newlines in decision summary/rationale should be replaced with spaces."""
        from gpd.core.state import state_add_decision

        state_md = self._make_state_md(tmp_path)
        result = state_add_decision(
            tmp_path,
            summary="Line one\nLine two\nLine three",
            phase="1",
            rationale="Because\nof\nthis",
        )
        assert result.added
        content = state_md.read_text(encoding="utf-8")
        # Verify no raw newlines in the decision entry
        for line in content.split("\n"):
            if "[Phase 1]:" in line:
                # The decision entry should be on a single line
                assert "\n" not in line.strip()
                assert "Line one Line two Line three" in line
                break

    def test_blocker_newlines_stripped(self, tmp_path: Path) -> None:
        """Newlines in blocker text should be replaced with spaces."""
        from gpd.core.state import state_add_blocker

        state_md = self._make_state_md(tmp_path)
        result = state_add_blocker(tmp_path, "Problem\nwith\nspacing")
        assert result.added
        content = state_md.read_text(encoding="utf-8")
        # Find the blocker entry and verify it's on one line
        for line in content.split("\n"):
            if "Problem" in line and line.strip().startswith("-"):
                assert "Problem with spacing" in line
                break


# ---------------------------------------------------------------------------
# Bug 8: suggest.py _scan_phases OSError handler
# ---------------------------------------------------------------------------


class TestScanPhasesOSError:
    """_scan_phases should return empty list when phases dir has restricted permissions."""

    def test_restricted_permissions_returns_empty(self, tmp_path: Path) -> None:
        """When phases dir can't be iterated, return empty list."""
        from gpd.core.suggest import _scan_phases

        gpd = tmp_path / ".gpd"
        phases_dir = gpd / "phases"
        phases_dir.mkdir(parents=True)

        # Simulate an OSError by mocking Path.iterdir
        with patch.object(Path, "iterdir", side_effect=OSError("Permission denied")):
            result = _scan_phases(tmp_path)
        assert result == []

    def test_nonexistent_phases_dir_returns_empty(self, tmp_path: Path) -> None:
        """When phases dir doesn't exist, return empty list."""
        from gpd.core.suggest import _scan_phases

        result = _scan_phases(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# Bug 9: install_utils.py write_settings error message mentions directory
# ---------------------------------------------------------------------------


class TestWriteSettingsErrorMessage:
    """write_settings error should mention the directory, not the file path."""

    def test_write_error_mentions_directory(self, tmp_path: Path) -> None:
        """On write failure, the error message should reference the parent directory."""
        from gpd.adapters.install_utils import write_settings

        settings_path = tmp_path / "settings.json"

        with patch("pathlib.Path.write_text", side_effect=PermissionError("denied")):
            with pytest.raises(PermissionError, match=str(tmp_path)):
                write_settings(settings_path, {"key": "value"})

    def test_mkdir_error_mentions_directory(self, tmp_path: Path) -> None:
        """On mkdir failure, error should reference the parent directory."""
        from gpd.adapters.install_utils import write_settings

        settings_path = tmp_path / "deep" / "nested" / "settings.json"

        with patch("pathlib.Path.mkdir", side_effect=PermissionError("denied")):
            with pytest.raises(PermissionError, match="settings directory"):
                write_settings(settings_path, {"key": "value"})


# ---------------------------------------------------------------------------
# Bug 10: install_utils.py re.sub lambda for backslash-like sequences
# ---------------------------------------------------------------------------


class TestConvertToolReferencesBackslash:
    """convert_tool_references_in_body should handle tool names with backslash-like sequences."""

    def test_backslash_sequence_not_corrupted(self) -> None:
        """Tool names containing backslash-like sequences should not corrupt content."""
        from gpd.adapters.install_utils import convert_tool_references_in_body

        # Tool map with a simple replacement
        tool_map = {"TodoWrite": "todo_write"}
        content = "Use TodoWrite to record tasks."
        result = convert_tool_references_in_body(content, tool_map)
        assert "todo_write" in result
        # Verify no corruption from re.sub backslash handling
        assert "\\1" not in result
        assert "\\0" not in result

    def test_target_with_backslash_like_chars(self) -> None:
        """Lambda-based replacement ensures backslash chars in target don't cause issues."""
        from gpd.adapters.install_utils import convert_tool_references_in_body

        # Even if target has characters that look like backrefs, lambda handles it
        tool_map = {"OldTool": "new\\1tool"}
        content = "Use OldTool to do things."
        result = convert_tool_references_in_body(content, tool_map)
        # The lambda approach ensures literal replacement
        assert "new\\1tool" in result


# ---------------------------------------------------------------------------
# Bug 11: context.py init_verify_work should include verifier_model
# ---------------------------------------------------------------------------


class TestVerifierModelInContext:
    """init_verify_work return dict should include 'verifier_model' key."""

    def test_verify_work_has_verifier_model(self, tmp_path: Path) -> None:
        """The context dict must contain verifier_model."""
        from gpd.core.context import init_verify_work

        # Set up minimal project structure
        gpd = tmp_path / ".gpd"
        gpd.mkdir(parents=True)
        (gpd / "PROJECT.md").write_text("# Test Project\n", encoding="utf-8")
        (gpd / "ROADMAP.md").write_text("## v1.0: Test\n\n### Phase 1: Setup\n", encoding="utf-8")

        # Create phase directory
        phase_dir = gpd / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "task-1-PLAN.md").write_text("plan", encoding="utf-8")

        result = init_verify_work(tmp_path, "1")
        assert "verifier_model" in result
        assert isinstance(result["verifier_model"], str)


# ---------------------------------------------------------------------------
# Bug 12: check_update.py code injection prevention
# ---------------------------------------------------------------------------


class TestCheckUpdateCodeInjection:
    """Background update check should pass cache_file as sys.argv, not in -c code."""

    def test_cache_file_passed_as_argv(self) -> None:
        """The subprocess command should use sys.argv[1], not embed the path in -c code."""
        from gpd.hooks.check_update import main

        # get_update_cache_files is imported locally inside main() from runtime_detect
        cache_path_val = Path("/tmp/test-cache.json")

        with patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_path_val]):
            with patch("gpd.hooks.check_update.subprocess.Popen") as mock_popen:
                mock_popen.return_value = MagicMock()

                # The cache file should not exist so the throttle check is skipped
                with patch.object(Path, "exists", return_value=False):
                    main()

                assert mock_popen.called, "Popen should have been called"
                args = mock_popen.call_args[0][0]
                # The command list should have the cache file as a separate argument
                # (i.e., sys.argv[1]), NOT embedded in the -c code string
                assert len(args) >= 4
                c_code = args[2]  # The -c code string
                cache_arg = args[3]  # The cache file as sys.argv[1]
                # The -c code should reference sys.argv[1], not contain the actual path
                assert "sys.argv[1]" in c_code
                assert cache_arg == str(cache_path_val)


# ---------------------------------------------------------------------------
# Bug 13: commands.py SummaryExtractResult.conventions type annotation
# ---------------------------------------------------------------------------


class TestSummaryExtractConventionsType:
    """SummaryExtractResult.conventions should accept dict, list, str, or None."""

    def test_conventions_accepts_dict(self) -> None:
        from gpd.core.commands import SummaryExtractResult

        result = SummaryExtractResult(path="test.md", conventions={"metric": "mostly-minus"})
        assert result.conventions == {"metric": "mostly-minus"}

    def test_conventions_accepts_list(self) -> None:
        from gpd.core.commands import SummaryExtractResult

        result = SummaryExtractResult(path="test.md", conventions=["metric=mostly-minus"])
        assert result.conventions == ["metric=mostly-minus"]

    def test_conventions_accepts_string(self) -> None:
        from gpd.core.commands import SummaryExtractResult

        result = SummaryExtractResult(path="test.md", conventions="mostly-minus")
        assert result.conventions == "mostly-minus"

    def test_conventions_accepts_none(self) -> None:
        from gpd.core.commands import SummaryExtractResult

        result = SummaryExtractResult(path="test.md", conventions=None)
        assert result.conventions is None

    def test_conventions_rejects_arbitrary_object(self) -> None:
        """Arbitrary objects should not be accepted (pydantic validation)."""
        from pydantic import ValidationError as PydanticValidationError

        from gpd.core.commands import SummaryExtractResult

        # An arbitrary non-serializable object should fail validation
        with pytest.raises(PydanticValidationError):
            SummaryExtractResult(path="test.md", conventions=object())


# ---------------------------------------------------------------------------
# Bug 14: commands.py cmd_regression_check uses STANDALONE_VERIFICATION
# ---------------------------------------------------------------------------


class TestRegressionCheckVerificationConstant:
    """cmd_regression_check should use STANDALONE_VERIFICATION constant."""

    def test_uses_standalone_verification_constant(self, tmp_path: Path) -> None:
        """The regression check should look for VERIFICATION.md files correctly."""
        from gpd.core.commands import cmd_regression_check
        from gpd.core.constants import STANDALONE_VERIFICATION

        gpd = tmp_path / ".gpd"
        phases_dir = gpd / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)

        # Create completed phase (plan + summary)
        (phase_dir / "task-1-PLAN.md").write_text("plan", encoding="utf-8")
        (phase_dir / "task-1-SUMMARY.md").write_text(
            "---\nphase: 1\n---\n# Summary\n",
            encoding="utf-8",
        )

        # Create a VERIFICATION.md with gaps_found status
        verification_content = (
            "---\nstatus: gaps_found\nscore: 3/5\n---\n"
            "# Verification\nSome gaps here.\n"
        )
        (phase_dir / STANDALONE_VERIFICATION).write_text(verification_content, encoding="utf-8")

        result = cmd_regression_check(tmp_path)
        # Should detect the verification issue using STANDALONE_VERIFICATION
        assert result.phases_checked == 1
        verification_issues = [i for i in result.issues if i.type == "unresolved_verification_issues"]
        assert len(verification_issues) == 1
        assert verification_issues[0].file == STANDALONE_VERIFICATION

    def test_verification_suffix_also_detected(self, tmp_path: Path) -> None:
        """Files with VERIFICATION_SUFFIX should also be detected."""
        from gpd.core.commands import cmd_regression_check
        from gpd.core.constants import VERIFICATION_SUFFIX

        gpd = tmp_path / ".gpd"
        phases_dir = gpd / "phases"
        phase_dir = phases_dir / "01-setup"
        phase_dir.mkdir(parents=True)

        (phase_dir / "task-1-PLAN.md").write_text("plan", encoding="utf-8")
        (phase_dir / "task-1-SUMMARY.md").write_text(
            "---\nphase: 1\n---\n# Summary\n",
            encoding="utf-8",
        )
        (phase_dir / f"task-1{VERIFICATION_SUFFIX}").write_text(
            "---\nstatus: gaps_found\nscore: 2/4\n---\n",
            encoding="utf-8",
        )

        result = cmd_regression_check(tmp_path)
        assert result.phases_checked == 1
        assert any(i.type == "unresolved_verification_issues" for i in result.issues)
