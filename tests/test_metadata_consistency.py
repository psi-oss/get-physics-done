"""Consistency checks for public repo metadata and inventory counts."""

from __future__ import annotations

import tomllib
from pathlib import Path

from gpd.contracts import ConventionLock
from gpd.core.health import _ALL_CHECKS
from gpd.core.patterns import PatternDomain


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def test_readme_ci_badge_points_to_existing_workflow() -> None:
    repo_root = _repo_root()
    workflow = repo_root / ".github" / "workflows" / "test.yml"
    readme = _read("README.md")

    assert workflow.is_file()
    assert "actions/workflows/test.yml" in readme


def test_python_floor_is_consistent_across_install_surfaces() -> None:
    project = tomllib.loads(_read("pyproject.toml"))["project"]
    assert project["requires-python"] == ">=3.11"

    readme = _read("README.md")
    user_guide = _read("docs/USER-GUIDE.md")
    installer = _read("bin/install.js")

    assert "Python 3.11+" in readme
    assert "Python 3.11+" in user_guide
    assert "minor >= 11" in installer
    assert "Python 3.11+ is required" in installer


def test_release_inventory_counts_match_repo_contents() -> None:
    repo_root = _repo_root()
    changelog = _read("CHANGELOG.md")

    commands_count = len(list((repo_root / "src" / "gpd" / "commands").glob("*.md")))
    agents_count = len(list((repo_root / "src" / "gpd" / "agents").glob("*.md")))
    skills_count = len(list((repo_root / "src" / "gpd" / "specs" / "skills").glob("*/SKILL.md")))
    mcp_server_count = len([p for p in (repo_root / "src" / "gpd" / "mcp" / "servers").glob("*.py") if p.name != "__init__.py"])

    assert f"- {commands_count} commands" in changelog
    assert f"- {agents_count} specialist agents" in changelog
    assert f"- {skills_count} skills" in changelog
    assert f"- {mcp_server_count} MCP tool servers" in changelog


def test_convention_field_counts_match_source_of_truth() -> None:
    convention_count = len(ConventionLock.model_fields) - 1  # exclude custom_conventions
    assert convention_count == 18

    assert f"Convention lock ({convention_count} physics fields + custom)" in _read("src/gpd/core/__init__.py")
    assert f"Convention lock ({convention_count} physics fields + custom)" in _read("ARCHITECTURE.md")
    assert f"locks conventions for up to {convention_count} physics fields" in _read("docs/USER-GUIDE.md")
    assert f"enforcing {convention_count} physics notation fields" in _read("CHANGELOG.md")


def test_pattern_domain_counts_match_source_of_truth() -> None:
    domain_count = len(PatternDomain)
    assert domain_count == 13

    assert f"Error pattern library (8 categories, {domain_count} domains)" in _read("src/gpd/core/__init__.py")
    assert f'pattern_app = typer.Typer(help="Error pattern library (8 categories, {domain_count} domains)")' in _read(
        "src/gpd/cli.py"
    )
    assert f"Error pattern library (8 categories, {domain_count} domains)" in _read("ARCHITECTURE.md")
    assert f"expect {domain_count} domains" in _read("MANUAL-TEST-PLAN.md")


def test_mcp_server_count_matches_security_and_architecture_docs() -> None:
    repo_root = _repo_root()
    mcp_server_count = len([p for p in (repo_root / "src" / "gpd" / "mcp" / "servers").glob("*.py") if p.name != "__init__.py"])
    assert mcp_server_count == 7

    assert f"({mcp_server_count} tool servers in `src/gpd/mcp/servers/`)" in _read("SECURITY.md")
    assert f"{mcp_server_count} MCP tool servers" in _read("ARCHITECTURE.md")


def test_agent_count_matches_architecture_profile_summary() -> None:
    agents_count = len(list((_repo_root() / "src" / "gpd" / "agents").glob("*.md")))
    assert agents_count == 17

    assert f"{agents_count} agents × 5 profiles" in _read("ARCHITECTURE.md")


def test_health_check_count_matches_skill_documentation() -> None:
    health_check_count = len(_ALL_CHECKS)
    assert health_check_count == 11

    skill = _read("src/gpd/specs/skills/gpd-health/SKILL.md")
    assert f"({health_check_count} checks)" in skill
    assert f"All {health_check_count} checks reported with status" in skill
