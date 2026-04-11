"""Fast inventory and wiring checks for command and skill registries."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMANDS_DIR = _REPO_ROOT / "src" / "gpd" / "commands"
_AGENTS_DIR = _REPO_ROOT / "src" / "gpd" / "agents"


def test_registry_command_inventory_matches_command_files() -> None:
    file_inventory = {path.stem for path in _COMMANDS_DIR.glob("*.md")}

    registry.invalidate_cache()
    registry_inventory = set(registry.list_commands())

    assert registry_inventory == file_inventory


def test_registry_skill_inventory_matches_command_and_agent_files() -> None:
    command_inventory = {path.stem for path in _COMMANDS_DIR.glob("*.md")}
    agent_inventory = {path.stem for path in _AGENTS_DIR.glob("*.md")}
    expected_skill_inventory = {f"gpd-{command_name}" for command_name in command_inventory} | agent_inventory

    registry.invalidate_cache()
    registry_skill_inventory = set(registry.list_skills())

    assert registry_skill_inventory == expected_skill_inventory


def test_registry_skill_wiring_tracks_command_and_agent_origins() -> None:
    command_inventory = {path.stem for path in _COMMANDS_DIR.glob("*.md")}
    agent_inventory = {path.stem for path in _AGENTS_DIR.glob("*.md")}

    registry.invalidate_cache()

    for command_name in sorted(command_inventory):
        skill_name = f"gpd-{command_name}"
        skill = registry.get_skill(skill_name)

        assert skill.source_kind == "command"
        assert skill.registry_name == command_name
        assert registry.get_command(command_name).name == f"gpd:{command_name}"

    for agent_name in sorted(agent_inventory):
        skill = registry.get_skill(agent_name)

        assert skill.source_kind == "agent"
        assert skill.registry_name == agent_name
        assert registry.get_agent(agent_name).name == agent_name
