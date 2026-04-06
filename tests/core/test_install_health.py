"""Tests for gpd/core/install_health.py — install health diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.install_health import (
    InstallHealthReport,
    check_install_health,
    format_health_report,
)


class TestInstallHealthReport:
    """Test the report dataclass."""

    def test_to_dict(self) -> None:
        report = InstallHealthReport(
            config_dir="/tmp/test",
            runtime="claude-code",
            is_healthy=True,
        )
        d = report.to_dict()
        assert d["config_dir"] == "/tmp/test"
        assert d["runtime"] == "claude-code"
        assert d["is_healthy"] is True

    def test_defaults(self) -> None:
        report = InstallHealthReport(config_dir="/tmp/test")
        assert report.is_healthy is False
        assert report.missing_artifacts == []
        assert report.present_artifacts == []
        assert report.can_auto_repair is False


class TestCheckInstallHealth:
    """Test the health check function."""

    def test_missing_manifest(self, tmp_path: Path) -> None:
        report = check_install_health(tmp_path)
        assert not report.is_healthy
        assert any("manifest" in a.lower() for a in report.missing_artifacts)

    def test_healthy_install(self, tmp_path: Path) -> None:
        """A properly seeded install should report healthy."""
        from tests.runtime_install_helpers import seed_complete_runtime_install

        config_dir = tmp_path / ".claude"
        seed_complete_runtime_install(config_dir, runtime="claude-code", install_scope="local")
        report = check_install_health(config_dir)
        assert report.is_healthy, f"Expected healthy, missing: {report.missing_artifacts}"
        assert report.runtime == "claude-code"
        assert report.install_scope == "local"
        assert report.can_auto_repair  # manifest is intact

    def test_damaged_install_detects_missing(self, tmp_path: Path) -> None:
        """Deleting commands should be detected."""
        import shutil

        from tests.runtime_install_helpers import seed_complete_runtime_install

        config_dir = tmp_path / ".claude"
        seed_complete_runtime_install(config_dir, runtime="claude-code", install_scope="local")

        # Delete the commands directory.
        commands_dir = config_dir / "commands" / "gpd"
        if commands_dir.exists():
            shutil.rmtree(commands_dir)

        report = check_install_health(config_dir)
        assert not report.is_healthy
        assert any("commands" in a for a in report.missing_artifacts)
        assert report.can_auto_repair  # manifest still there


class TestFormatHealthReport:
    """Test the human-readable report formatter."""

    def test_healthy_report(self) -> None:
        report = InstallHealthReport(
            config_dir="/tmp/test",
            runtime="claude-code",
            is_healthy=True,
            manifest_status="ok",
        )
        text = format_health_report(report)
        assert "HEALTHY" in text
        assert "claude-code" in text

    def test_damaged_report_includes_repair(self) -> None:
        report = InstallHealthReport(
            config_dir="/tmp/test",
            runtime="claude-code",
            is_healthy=False,
            manifest_status="ok",
            missing_artifacts=["commands/gpd"],
            repair_command="npx -y get-physics-done --claude-code",
        )
        text = format_health_report(report)
        assert "DAMAGED" in text
        assert "commands/gpd" in text
        assert "npx" in text

    def test_missing_manifest_report(self) -> None:
        report = InstallHealthReport(
            config_dir="/tmp/test",
            is_healthy=False,
            manifest_status="missing",
            missing_artifacts=["gpd-file-manifest.json"],
        )
        text = format_health_report(report)
        assert "DAMAGED" in text
        assert "npx" in text
