"""Tests for command and agent markdown files — validates frontmatter and structure.

Ensures every .md content file in commands/ and agents/ has valid YAML
frontmatter with the required fields, and that the registry can parse them all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Package layout roots
_PKG_ROOT = Path(__file__).resolve().parent.parent / "src" / "gpd"
COMMANDS_DIR = _PKG_ROOT / "commands"
AGENTS_DIR = _PKG_ROOT / "agents"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_START = "---"


def _extract_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter from markdown text."""
    if not text.startswith(_FRONTMATTER_START):
        return None
    lines = text.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None
    yaml_text = "\n".join(lines[1:end_idx])
    return yaml.safe_load(yaml_text)


def _collect_md_files(directory: Path) -> list[Path]:
    """Collect all .md files from a directory, excluding __init__.py etc."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.md") if p.name != "__init__.py")


# ---------------------------------------------------------------------------
# Command markdown files
# ---------------------------------------------------------------------------


_command_files = _collect_md_files(COMMANDS_DIR)


@pytest.mark.parametrize(
    "cmd_path",
    _command_files,
    ids=[p.stem for p in _command_files],
)
class TestCommandMarkdown:
    def test_has_frontmatter(self, cmd_path: Path):
        text = cmd_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None, f"{cmd_path.name} has no YAML frontmatter"

    def test_has_name(self, cmd_path: Path):
        text = cmd_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        assert "name" in meta, f"{cmd_path.name} missing 'name' in frontmatter"
        assert isinstance(meta["name"], str)

    def test_has_description(self, cmd_path: Path):
        text = cmd_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        assert "description" in meta, f"{cmd_path.name} missing 'description'"
        assert len(str(meta["description"])) > 0

    def test_name_starts_with_gpd(self, cmd_path: Path):
        """All command names should start with 'gpd:' prefix."""
        text = cmd_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        name = meta.get("name", "")
        assert name.startswith("gpd:"), f"{cmd_path.name}: name '{name}' should start with 'gpd:'"

    def test_allowed_tools_is_list(self, cmd_path: Path):
        text = cmd_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        if "allowed-tools" in meta:
            assert isinstance(meta["allowed-tools"], list), (
                f"{cmd_path.name}: allowed-tools should be a list"
            )

    def test_requires_is_dict_if_present(self, cmd_path: Path):
        text = cmd_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        if "requires" in meta:
            assert isinstance(meta["requires"], dict), (
                f"{cmd_path.name}: requires should be a dict"
            )

    def test_body_is_not_empty(self, cmd_path: Path):
        """Commands should have body content after frontmatter."""
        text = cmd_path.read_text(encoding="utf-8")
        lines = text.split("\n")
        # Find end of frontmatter
        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break
        assert end_idx is not None
        body = "\n".join(lines[end_idx + 1:]).strip()
        assert len(body) > 0, f"{cmd_path.name} has empty body after frontmatter"


# ---------------------------------------------------------------------------
# Agent markdown files
# ---------------------------------------------------------------------------


_agent_files = _collect_md_files(AGENTS_DIR)


@pytest.mark.parametrize(
    "agent_path",
    _agent_files,
    ids=[p.stem for p in _agent_files],
)
class TestAgentMarkdown:
    def test_has_frontmatter(self, agent_path: Path):
        text = agent_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None, f"{agent_path.name} has no YAML frontmatter"

    def test_has_name(self, agent_path: Path):
        text = agent_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        assert "name" in meta, f"{agent_path.name} missing 'name'"
        assert isinstance(meta["name"], str)

    def test_has_description(self, agent_path: Path):
        text = agent_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        assert "description" in meta, f"{agent_path.name} missing 'description'"
        assert len(str(meta["description"])) > 0

    def test_name_starts_with_gpd(self, agent_path: Path):
        text = agent_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        name = meta.get("name", "")
        assert name.startswith("gpd-"), f"{agent_path.name}: name '{name}' should start with 'gpd-'"

    def test_has_tools(self, agent_path: Path):
        text = agent_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        assert "tools" in meta, f"{agent_path.name} missing 'tools'"
        tools_raw = meta["tools"]
        # Tools can be string (comma-separated) or list
        if isinstance(tools_raw, str):
            tools = [t.strip() for t in tools_raw.split(",")]
        else:
            tools = list(tools_raw)
        assert len(tools) > 0, f"{agent_path.name} has empty tools list"

    def test_has_color(self, agent_path: Path):
        text = agent_path.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        assert meta is not None
        assert "color" in meta, f"{agent_path.name} missing 'color'"

    def test_body_is_not_empty(self, agent_path: Path):
        text = agent_path.read_text(encoding="utf-8")
        lines = text.split("\n")
        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break
        assert end_idx is not None
        body = "\n".join(lines[end_idx + 1:]).strip()
        assert len(body) > 0, f"{agent_path.name} has empty body"


# ---------------------------------------------------------------------------
# Registry integration — can the registry parse all files?
# ---------------------------------------------------------------------------


class TestRegistryParsesAllContent:
    def test_all_commands_parse(self):
        from gpd.registry import get_command, list_commands

        names = list_commands()
        assert len(names) > 0
        for name in names:
            cmd = get_command(name)
            assert cmd.name, f"Command at {cmd.path} has no name"
            assert cmd.description, f"Command {cmd.name} has no description"

    def test_all_agents_parse(self):
        from gpd.registry import get_agent, list_agents

        names = list_agents()
        assert len(names) > 0
        for name in names:
            agent = get_agent(name)
            assert agent.name, f"Agent at {agent.path} has no name"
            assert agent.description, f"Agent {agent.name} has no description"

    def test_command_count_matches_files(self):
        """Registry should find at least as many commands as .md files in commands/."""
        from gpd.registry import list_commands

        file_count = len(_command_files)
        names = list_commands()
        assert len(names) >= file_count

    def test_agent_count_matches_files(self):
        """Registry should find at least as many agents as .md files in agents/."""
        from gpd.registry import list_agents

        file_count = len(_agent_files)
        names = list_agents()
        assert len(names) >= file_count

    def test_no_duplicate_command_names(self):
        from gpd.registry import list_commands

        names = list_commands()
        assert len(names) == len(set(names)), f"Duplicate command names: {[n for n in names if names.count(n) > 1]}"

    def test_no_duplicate_agent_names(self):
        from gpd.registry import list_agents

        names = list_agents()
        assert len(names) == len(set(names)), f"Duplicate agent names: {[n for n in names if names.count(n) > 1]}"

    def test_command_agent_references_valid(self):
        """If a command references an agent, that agent should exist."""
        from gpd.registry import get_command, list_agents, list_commands

        agent_names = set(list_agents())
        for cmd_name in list_commands():
            cmd = get_command(cmd_name)
            text = Path(cmd.path).read_text(encoding="utf-8")
            meta = _extract_frontmatter(text)
            if meta and "agent" in meta:
                agent_name = meta["agent"]
                assert agent_name in agent_names, (
                    f"Command {cmd.name} references agent '{agent_name}' which doesn't exist. "
                    f"Available: {sorted(agent_names)}"
                )
