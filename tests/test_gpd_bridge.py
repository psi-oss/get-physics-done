"""Tests for GPD bridge discovery and version checking."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.mcp.gpd_bridge.discovery import (
    GPD_CORE_DIR,
    discover_agents,
    discover_commands,
    discover_workflows,
    find_gpd_install,
)
from gpd.mcp.gpd_bridge.version import (
    GPD_REQUIRED_VERSION,
    check_gpd_version,
    format_version_warning,
)


def test_find_gpd_install_discovers_mock(mock_gpd_install: Path, monkeypatch: object) -> None:
    """find_gpd_install returns the mock .claude directory when cwd points there."""
    # mock_gpd_install is tmp_path/.claude -- set cwd to tmp_path so project-local search finds it
    parent = mock_gpd_install.parent
    monkeypatch.chdir(parent)  # type: ignore[attr-defined]
    result = find_gpd_install()
    assert result is not None
    assert result == mock_gpd_install


def test_find_gpd_install_returns_none_when_missing(tmp_path: Path, monkeypatch: object) -> None:
    """find_gpd_install returns None when no GPD directory exists."""
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    # Override HOME so global fallback also misses
    monkeypatch.setenv("HOME", str(tmp_path / "nonexistent"))  # type: ignore[attr-defined]
    # Clear CLAUDE_CONFIG_DIR to avoid interference
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)  # type: ignore[attr-defined]
    result = find_gpd_install()
    assert result is None


def test_discover_commands_returns_md_files(mock_gpd_install: Path) -> None:
    """discover_commands returns .md files from the commands/gpd/ directory."""
    commands = discover_commands(mock_gpd_install)
    assert len(commands) == 2
    names = [p.name for p in commands]
    assert "example-cmd.md" in names
    assert "plan.md" in names


def test_discover_commands_empty_when_no_dir(tmp_path: Path) -> None:
    """discover_commands returns empty list when commands dir does not exist."""
    commands = discover_commands(tmp_path)
    assert commands == []


def test_discover_agents_returns_gpd_prefixed_only(mock_gpd_install: Path) -> None:
    """discover_agents returns only gpd-*.md files, not other agent files."""
    agents = discover_agents(mock_gpd_install)
    assert len(agents) == 2
    names = [p.name for p in agents]
    assert "gpd-researcher.md" in names
    assert "gpd-analyst.md" in names
    # custom-agent.md should NOT appear
    assert "custom-agent.md" not in names


def test_discover_agents_empty_when_no_dir(tmp_path: Path) -> None:
    """discover_agents returns empty list when agents dir does not exist."""
    agents = discover_agents(tmp_path)
    assert agents == []


def test_discover_workflows(mock_gpd_install: Path) -> None:
    """discover_workflows returns .md files from the workflows directory."""
    workflows = discover_workflows(mock_gpd_install)
    assert len(workflows) == 1
    assert workflows[0].name == "research.md"


def test_check_gpd_version_compatible(mock_gpd_install: Path) -> None:
    """check_gpd_version returns (True, version) when version matches GPD_REQUIRED_VERSION."""
    is_compatible, version = check_gpd_version(mock_gpd_install)
    assert is_compatible is True
    assert version == GPD_REQUIRED_VERSION


def test_check_gpd_version_incompatible(mock_gpd_install: Path) -> None:
    """check_gpd_version returns (False, version) when version mismatches."""
    # Overwrite package.json with a different version
    pkg_json_path = mock_gpd_install / GPD_CORE_DIR / "package.json"
    pkg_json_path.write_text(json.dumps({"name": "get-physics-done-cc", "version": "99.0.0"}))

    is_compatible, version = check_gpd_version(mock_gpd_install)
    assert is_compatible is False
    assert version == "99.0.0"


def test_format_version_warning_includes_versions() -> None:
    """format_version_warning includes both installed and required versions."""
    warning = format_version_warning("2.0.0", "1.0.0")
    assert "2.0.0" in warning
    assert "1.0.0" in warning
