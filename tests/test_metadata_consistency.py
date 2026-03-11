"""Consistency checks for public repo metadata and inventory counts."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

from gpd import registry as content_registry
from gpd.contracts import ConventionLock
from gpd.core.config import MODEL_PROFILES
from gpd.core.health import _ALL_CHECKS
from gpd.core.patterns import PatternDomain
from gpd.registry import VALID_CONTEXT_MODES


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def _decorated_mcp_tools(relative_path: str) -> list[str]:
    """Return top-level ``@mcp.tool()`` function names from a server module."""
    tree = ast.parse(_read(relative_path), filename=relative_path)
    tool_names: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "tool"
                and isinstance(func.value, ast.Name)
                and func.value.id == "mcp"
            ):
                tool_names.append(node.name)
                break
    return tool_names


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


def test_managed_mcp_server_keys_match_public_descriptors_and_infra_inventory() -> None:
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS, build_public_descriptors

    repo_root = _repo_root()
    descriptor_keys = set(build_public_descriptors())
    infra_keys = {path.stem for path in (repo_root / "infra").glob("gpd-*.json")}

    assert GPD_MCP_SERVER_KEYS == descriptor_keys
    assert GPD_MCP_SERVER_KEYS == infra_keys


def test_public_mcp_descriptor_capabilities_match_server_tools() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    descriptors = build_public_descriptors()
    for name, descriptor in descriptors.items():
        args = descriptor.get("args")
        assert isinstance(args, list)
        if args == ["-m", "arxiv_mcp_server"]:
            continue

        assert len(args) == 2
        assert args[0] == "-m"
        module_name = str(args[1])
        module_path = Path("src") / Path(*module_name.split(".")).with_suffix(".py")

        assert descriptor["capabilities"] == _decorated_mcp_tools(module_path.as_posix()), name


def test_public_mcp_descriptor_entry_point_alternatives_match_pyproject_scripts() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    repo_root = _repo_root()
    script_targets: dict[str, str] = {}
    for line in _project_script_lines(repo_root):
        name, target = line.split("=", 1)
        script_targets[name.strip().strip('"')] = target.strip().strip('"')

    descriptors = build_public_descriptors()
    for name, descriptor in descriptors.items():
        args = descriptor.get("args")
        assert isinstance(args, list)
        if args == ["-m", "arxiv_mcp_server"]:
            assert "alternatives" not in descriptor
            continue

        alternatives = descriptor.get("alternatives")
        assert isinstance(alternatives, dict), name
        entry_point = alternatives.get("entry_point")
        assert isinstance(entry_point, dict), name
        script_name = entry_point.get("command")
        assert isinstance(script_name, str), name
        assert entry_point.get("args") == []
        assert entry_point.get("notes") == "Requires gpd package installed"
        assert len(args) == 2
        assert args[0] == "-m"
        assert script_targets[script_name] == f"{args[1]}:main"


def test_arxiv_descriptor_tracks_required_dependency_surface() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    project = tomllib.loads(_read("pyproject.toml"))["project"]
    dependencies: list[str] = project["dependencies"]
    assert any(item.startswith("arxiv-mcp-server") for item in dependencies)

    descriptor = build_public_descriptors()["gpd-arxiv"]
    assert descriptor["prerequisites"] == ["Install GPD first: npx -y get-physics-done@latest"]


def test_agent_count_matches_prompts_and_user_docs() -> None:
    agents_count = len(list((_repo_root() / "src" / "gpd" / "agents").glob("*.md")))
    assert agents_count == len(MODEL_PROFILES)
    assert "specialist agents" in _read("README.md")
    assert f"across all {agents_count} agents" in _read("src/gpd/specs/workflows/set-profile.md")


def test_health_check_count_matches_skill_documentation() -> None:
    health_check_count = len(_ALL_CHECKS)
    assert health_check_count == 12

    command = _read("src/gpd/commands/health.md")
    assert "All {total} health checks passed." in command
    assert "All checks reported with status" in command


def test_every_command_declares_valid_context_mode() -> None:
    commands_dir = _repo_root() / "src" / "gpd" / "commands"
    pattern = re.compile(r"^context_mode:\s*(.+?)\s*$", re.MULTILINE)

    missing: list[str] = []
    invalid: list[str] = []

    for path in sorted(commands_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        match = pattern.search(content)
        if match is None:
            missing.append(path.name)
            continue
        mode = match.group(1).strip()
        if mode not in VALID_CONTEXT_MODES:
            invalid.append(f"{path.name}: {mode}")

    assert missing == []
    assert invalid == []
