"""Fast cross-surface checks for packaged command/skill inventory."""

from __future__ import annotations

import json
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGE_JSON = REPO_ROOT / "package.json"
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _wheel_artifact_patterns() -> tuple[str, ...]:
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return tuple(pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["artifacts"])


def test_registry_command_and_agent_inventory_is_packaged() -> None:
    artifact_patterns = _wheel_artifact_patterns()

    for command_name in registry.list_commands():
        command = registry.get_command(command_name)
        command_path = Path(command.path)
        assert command_path.is_file(), f"missing command prompt for {command_name}: {command.path}"
        relative_path = command_path.relative_to(REPO_ROOT).as_posix()
        assert any(fnmatchcase(relative_path, pattern) for pattern in artifact_patterns), (
            f"registry command {command_name} is not covered by wheel artifacts: {relative_path}"
        )

    for agent_name in registry.list_agents():
        agent = registry.get_agent(agent_name)
        agent_path = Path(agent.path)
        assert agent_path.is_file(), f"missing agent prompt for {agent_name}: {agent.path}"
        relative_path = agent_path.relative_to(REPO_ROOT).as_posix()
        assert any(fnmatchcase(relative_path, pattern) for pattern in artifact_patterns), (
            f"registry agent {agent_name} is not covered by wheel artifacts: {relative_path}"
        )


def test_prompt_inventory_matches_registry_and_npm_bootstrap_boundary() -> None:
    command_files = sorted(path for path in COMMANDS_DIR.glob("*.md"))
    agent_files = sorted(path for path in AGENTS_DIR.glob("*.md"))

    assert {Path(registry.get_command(name).path) for name in registry.list_commands()} == set(command_files)
    assert {Path(registry.get_agent(name).path) for name in registry.list_agents()} == set(agent_files)

    package_files = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["files"]
    assert all(not entry.startswith(("src/gpd/commands/", "src/gpd/agents/")) for entry in package_files)


def test_skill_names_are_gpd_prefixed_and_unique_across_commands_and_agents() -> None:
    command_skill_names = [registry.get_skill(command_name).name for command_name in registry.list_commands()]
    agent_skill_names = registry.list_agents()
    skill_names = registry.list_skills()

    assert skill_names == sorted(set(skill_names))
    assert all(name.startswith("gpd-") for name in skill_names)
    assert len(command_skill_names) == len(set(command_skill_names))
    assert len(agent_skill_names) == len(set(agent_skill_names))
    assert set(command_skill_names).isdisjoint(agent_skill_names)
    assert set(skill_names) == set(command_skill_names) | set(agent_skill_names)


def test_command_agent_refs_exist_and_allowed_tools_metadata_is_mirrored() -> None:
    from gpd.mcp.servers import skills_server

    known_agents = set(registry.list_agents())
    commands_with_tools = 0

    for command_name in registry.list_commands():
        command = registry.get_command(command_name)
        if command.agent is not None:
            assert command.agent in known_agents, f"{command_name} references missing agent {command.agent}"
        if command.allowed_tools:
            commands_with_tools += 1

        payload = skills_server.get_skill(command_name)
        assert "error" not in payload
        assert payload["allowed_tools_surface"] == "command.allowed-tools"
        assert payload["allowed_tools"] == list(dict.fromkeys(command.allowed_tools))
        assert payload["structured_metadata_authority"]["allowed_tools"] == "mirrored"

    assert commands_with_tools > 0
