"""Tests for LVP-based equation verification commands."""

from __future__ import annotations

from gpd import registry


class TestLvpCommandDiscovery:
    """Verify LVP commands are discovered and correctly structured."""

    def test_verify_equations_discovered(self) -> None:
        commands = registry._discover_commands()
        assert "verify-equations" in commands

    def test_scan_equations_discovered(self) -> None:
        commands = registry._discover_commands()
        assert "scan-equations" in commands

    def test_check_citations_discovered(self) -> None:
        commands = registry._discover_commands()
        assert "check-citations" in commands

    def test_verify_equations_frontmatter(self) -> None:
        commands = registry._discover_commands()
        cmd = commands["verify-equations"]
        assert cmd.name == "gpd:verify-equations"
        assert "equation" in cmd.description.lower() or "verify" in cmd.description.lower()
        assert cmd.context_mode == "project-aware"

    def test_scan_equations_frontmatter(self) -> None:
        commands = registry._discover_commands()
        cmd = commands["scan-equations"]
        assert cmd.name == "gpd:scan-equations"
        assert cmd.context_mode == "project-aware"

    def test_check_citations_frontmatter(self) -> None:
        commands = registry._discover_commands()
        cmd = commands["check-citations"]
        assert cmd.name == "gpd:check-citations"

    def test_verify_equations_has_allowed_tools(self) -> None:
        commands = registry._discover_commands()
        cmd = commands["verify-equations"]
        assert "file_read" in cmd.allowed_tools
        assert "web_search" in cmd.allowed_tools

    def test_scan_equations_does_not_require_web(self) -> None:
        commands = registry._discover_commands()
        cmd = commands["scan-equations"]
        assert "web_search" not in cmd.allowed_tools
        assert "file_read" in cmd.allowed_tools


class TestLvpSkillCategories:
    """Verify LVP commands are categorized correctly."""

    def test_verify_equations_category(self) -> None:
        assert registry._infer_skill_category("gpd-verify-equations") == "verification"

    def test_scan_equations_category(self) -> None:
        assert registry._infer_skill_category("gpd-scan-equations") == "analysis"

    def test_check_citations_category(self) -> None:
        assert registry._infer_skill_category("gpd-check-citations") == "verification"


class TestLvpProjectAwareRegistration:
    """Verify LVP commands are registered for standalone mode."""

    def test_verify_equations_in_explicit_inputs(self) -> None:
        from gpd.cli import _PROJECT_AWARE_EXPLICIT_INPUTS

        assert "gpd:verify-equations" in _PROJECT_AWARE_EXPLICIT_INPUTS

    def test_scan_equations_in_explicit_inputs(self) -> None:
        from gpd.cli import _PROJECT_AWARE_EXPLICIT_INPUTS

        assert "gpd:scan-equations" in _PROJECT_AWARE_EXPLICIT_INPUTS

    def test_check_citations_in_explicit_inputs(self) -> None:
        from gpd.cli import _PROJECT_AWARE_EXPLICIT_INPUTS

        assert "gpd:check-citations" in _PROJECT_AWARE_EXPLICIT_INPUTS
