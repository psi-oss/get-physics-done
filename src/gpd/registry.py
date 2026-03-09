"""GPD content registry — single source of truth for discovering commands, agents, and specs.

All GPD content (commands, agents, spec-agents, spec-skills) lives in markdown files
with YAML frontmatter. This module parses them once, caches the results, and exposes
typed dataclass definitions so every consumer (commands/__init__.py, agents/__init__.py,
adapters, CLI, MCP) gets the same data without re-parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ─── Package layout ──────────────────────────────────────────────────────────

_PKG_ROOT = Path(__file__).resolve().parent  # gpd/
AGENTS_DIR = _PKG_ROOT / "agents"
COMMANDS_DIR = _PKG_ROOT / "commands"
SPECS_DIR = _PKG_ROOT / "specs"
SPECS_AGENTS_DIR = SPECS_DIR / "agents"
SPECS_SKILLS_DIR = SPECS_DIR / "skills"

# ─── Frontmatter regex ───────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)")


# ─── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentDef:
    """Parsed agent definition from a .md file."""

    name: str
    description: str
    system_prompt: str
    tools: list[str]
    color: str
    path: str
    source: str  # "agents" or "specs/agents"


@dataclass(frozen=True, slots=True)
class CommandDef:
    """Parsed command/skill definition from a .md file."""

    name: str
    description: str
    argument_hint: str
    requires: dict[str, object]
    allowed_tools: list[str]
    content: str
    path: str
    source: str  # "commands" or "specs/skills"


# ─── Parsing helpers ─────────────────────────────────────────────────────────


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse YAML frontmatter from markdown text. Returns (meta, body)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    yaml_str = match.group(1)
    body = text[match.end() :]
    meta = yaml.safe_load(yaml_str) or {}
    if not isinstance(meta, dict):
        return {}, text
    return meta, body


def _parse_tools(raw: object) -> list[str]:
    """Normalize tools field from frontmatter to a list of strings."""
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, list):
        return [str(t) for t in raw]
    return []


def _parse_agent_file(path: Path, source: str) -> AgentDef:
    """Parse a single agent .md file into an AgentDef."""
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    return AgentDef(
        name=meta.get("name", path.stem),
        description=str(meta.get("description", "")),
        system_prompt=body.strip(),
        tools=_parse_tools(meta.get("tools", "")),
        color=str(meta.get("color", "")),
        path=str(path),
        source=source,
    )


def _parse_command_file(path: Path, source: str) -> CommandDef:
    """Parse a single command .md file into a CommandDef."""
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    requires = meta.get("requires", {})
    if not isinstance(requires, dict):
        requires = {}

    allowed_tools_raw = meta.get("allowed-tools", [])
    if not isinstance(allowed_tools_raw, list):
        allowed_tools_raw = []

    return CommandDef(
        name=meta.get("name", path.stem),
        description=str(meta.get("description", "")),
        argument_hint=str(meta.get("argument-hint", "")),
        requires=requires,
        allowed_tools=[str(t) for t in allowed_tools_raw],
        content=body.strip(),
        path=str(path),
        source=source,
    )


# ─── Cache ───────────────────────────────────────────────────────────────────


@dataclass
class _RegistryCache:
    """Lazy-loaded, process-lifetime cache of all GPD content."""

    _agents: dict[str, AgentDef] | None = field(default=None, repr=False)
    _commands: dict[str, CommandDef] | None = field(default=None, repr=False)

    def agents(self) -> dict[str, AgentDef]:
        if self._agents is None:
            self._agents = _discover_agents()
        return self._agents

    def commands(self) -> dict[str, CommandDef]:
        if self._commands is None:
            self._commands = _discover_commands()
        return self._commands

    def invalidate(self) -> None:
        """Clear cached data (useful in tests or after install)."""
        self._agents = None
        self._commands = None


_cache = _RegistryCache()


# ─── Discovery ───────────────────────────────────────────────────────────────


def _discover_agents() -> dict[str, AgentDef]:
    """Discover all agent definitions from agents/ and specs/agents/ directories.

    Primary agents (agents/) take precedence over specs/agents/ for the same name.
    """
    result: dict[str, AgentDef] = {}

    # 1. specs/agents/ (legacy location, loaded first so primary overrides)
    if SPECS_AGENTS_DIR.is_dir():
        for path in sorted(SPECS_AGENTS_DIR.glob("*.md")):
            agent = _parse_agent_file(path, source="specs/agents")
            result[agent.name] = agent

    # 2. agents/ (primary, overrides specs/agents)
    if AGENTS_DIR.is_dir():
        for path in sorted(AGENTS_DIR.glob("*.md")):
            agent = _parse_agent_file(path, source="agents")
            result[agent.name] = agent

    return result


def _discover_commands() -> dict[str, CommandDef]:
    """Discover all command definitions from commands/ and specs/skills/ directories.

    Primary commands (commands/) take precedence over specs/skills/ for the same name.
    """
    result: dict[str, CommandDef] = {}

    # 1. specs/skills/ (legacy location, loaded first so primary overrides)
    if SPECS_SKILLS_DIR.is_dir():
        for skill_dir in sorted(SPECS_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                cmd = _parse_command_file(skill_md, source="specs/skills")
                # Use directory name as canonical name if frontmatter name differs
                canonical_name = skill_dir.name
                result[canonical_name] = CommandDef(
                    name=canonical_name,
                    description=cmd.description,
                    argument_hint=cmd.argument_hint,
                    requires=cmd.requires,
                    allowed_tools=cmd.allowed_tools,
                    content=cmd.content,
                    path=cmd.path,
                    source=cmd.source,
                )

    # 2. commands/ (primary, overrides specs/skills)
    #    Key by path.stem (e.g. "debug") — the frontmatter name may differ
    #    (e.g. "gpd:debug") but callers use the filesystem stem.
    #    Also remove the corresponding gpd-{stem} spec/skill entry so that
    #    primary commands fully replace their specs/skills counterparts
    #    (specs/skills use "gpd-debug" dir names while commands use "debug.md").
    if COMMANDS_DIR.is_dir():
        for path in sorted(COMMANDS_DIR.glob("*.md")):
            cmd = _parse_command_file(path, source="commands")
            result[path.stem] = cmd
            # Remove the gpd-prefixed specs/skills duplicate if it exists
            gpd_prefixed = f"gpd-{path.stem}"
            result.pop(gpd_prefixed, None)

    return result


# ─── Public API ──────────────────────────────────────────────────────────────


def list_agents() -> list[str]:
    """Return sorted list of all agent names."""
    return sorted(_cache.agents())


def get_agent(name: str) -> AgentDef:
    """Get a parsed agent definition by name.

    Raises KeyError if not found.
    """
    agents = _cache.agents()
    if name not in agents:
        raise KeyError(f"Agent not found: {name}")
    return agents[name]


def list_commands() -> list[str]:
    """Return sorted list of all command names."""
    return sorted(_cache.commands())


def get_command(name: str) -> CommandDef:
    """Get a parsed command definition by name.

    Raises KeyError if not found.
    """
    commands = _cache.commands()
    if name not in commands:
        raise KeyError(f"Command not found: {name}")
    return commands[name]


def invalidate_cache() -> None:
    """Clear the registry cache. Call after install/uninstall or in tests."""
    _cache.invalidate()


__all__ = [
    "AGENTS_DIR",
    "AgentDef",
    "COMMANDS_DIR",
    "CommandDef",
    "SPECS_AGENTS_DIR",
    "SPECS_DIR",
    "SPECS_SKILLS_DIR",
    "get_agent",
    "get_command",
    "invalidate_cache",
    "list_agents",
    "list_commands",
]
