"""Consistency checks for public repo metadata and inventory counts."""

from __future__ import annotations

import tomllib
from pathlib import Path

from gpd import registry as content_registry
from gpd.contracts import ConventionLock
from gpd.core.health import _ALL_CHECKS
from gpd.core.patterns import PatternDomain


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def _project_script_lines(repo_root: Path) -> list[str]:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    collecting = False
    script_lines: list[str] = []
    for line in pyproject:
        stripped = line.strip()
        if stripped == "[project.scripts]":
            collecting = True
            continue
        if collecting and stripped.startswith("["):
            break
        if collecting and stripped:
            script_lines.append(stripped)
    return script_lines


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
    installer = _read("bin/install.js")

    assert "Python 3.11+" in readme
    assert "minor >= 11" in installer
    assert "Python 3.11+ is required" in installer


def test_release_inventory_counts_match_repo_contents() -> None:
    repo_root = _repo_root()
    commands_count = len(list((repo_root / "src" / "gpd" / "commands").glob("*.md")))
    agents_count = len(list((repo_root / "src" / "gpd" / "agents").glob("*.md")))
    content_registry.invalidate_cache()
    skills_count = len(content_registry.list_skills())
    mcp_server_count = len([p for p in (repo_root / "src" / "gpd" / "mcp" / "servers").glob("*.py") if p.name != "__init__.py"])
    mcp_script_count = sum(1 for line in _project_script_lines(repo_root) if line.startswith('"gpd-mcp-'))

    assert commands_count >= 50
    assert skills_count == commands_count + agents_count
    assert mcp_server_count == mcp_script_count


def test_convention_field_counts_match_source_of_truth() -> None:
    convention_count = len(ConventionLock.model_fields) - 1  # exclude custom_conventions
    assert convention_count == 18

    assert f"Convention lock ({convention_count} physics fields + custom)" in _read("src/gpd/core/__init__.py")
    assert f"locks conventions for up to {convention_count} physics fields" in _read("README.md")


def test_pattern_domain_counts_match_source_of_truth() -> None:
    domain_count = len(PatternDomain)
    assert domain_count == 13

    assert f"Error pattern library (8 categories, {domain_count} domains)" in _read("src/gpd/core/__init__.py")
    assert f'pattern_app = typer.Typer(help="Error pattern library (8 categories, {domain_count} domains)")' in _read(
        "src/gpd/cli.py"
    )


def test_mcp_server_count_matches_public_entrypoints() -> None:
    repo_root = _repo_root()
    mcp_server_count = len([p for p in (repo_root / "src" / "gpd" / "mcp" / "servers").glob("*.py") if p.name != "__init__.py"])
    mcp_script_count = sum(1 for line in _project_script_lines(repo_root) if line.startswith('"gpd-mcp-'))
    assert mcp_server_count == 7
    assert mcp_server_count == mcp_script_count


def test_agent_count_matches_prompts_and_user_docs() -> None:
    agents_count = len(list((_repo_root() / "src" / "gpd" / "agents").glob("*.md")))
    assert agents_count == 17
    assert "specialist agents" in _read("README.md")


def test_health_check_count_matches_skill_documentation() -> None:
    health_check_count = len(_ALL_CHECKS)
    assert health_check_count == 11

    command = _read("src/gpd/commands/health.md")
    assert "All {total} health checks passed." in command
    assert "All checks reported with status" in command
