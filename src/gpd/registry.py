"""GPD content registry — single source of truth for discovering commands and agents.

Primary GPD commands and agents live in markdown files with YAML frontmatter.
This module parses them once, caches the results, and exposes typed dataclass
definitions so every consumer (adapters, CLI, MCP skills server) gets the
same data without re-parsing.
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
    source: str  # "agents"


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
    source: str  # "commands"
    review_contract: ReviewCommandContract | None = None


@dataclass(frozen=True, slots=True)
class ReviewCommandContract:
    """Typed orchestration contract for review-grade commands."""

    review_mode: str
    required_outputs: list[str]
    required_evidence: list[str]
    blocking_conditions: list[str]
    preflight_checks: list[str]
    required_state: str = ""
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class SkillDef:
    """Canonical skill exposure derived from primary commands and agents."""

    name: str
    description: str
    content: str
    category: str
    path: str
    source_kind: str  # "command" or "agent"
    registry_name: str


# ─── Parsing helpers ─────────────────────────────────────────────────────────


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse YAML frontmatter from markdown text. Returns (meta, body)."""
    text = text.lstrip('﻿')
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    yaml_str = match.group(1)
    body = text[match.end() :]
    try:
        meta = yaml.safe_load(yaml_str) or {}
    except yaml.YAMLError:
        return {}, text
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


def _parse_str_list(raw: object) -> list[str]:
    """Normalize a raw scalar/list field into a list of strings."""
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


_DEFAULT_REVIEW_CONTRACTS: dict[str, dict[str, object]] = {
    "gpd:write-paper": {
        "review_mode": "publication",
        "required_outputs": ["paper/main.tex", ".gpd/REFEREE-REPORT.md"],
        "required_evidence": [
            "phase summaries or milestone digest",
            "verification reports",
            "bibliography audit",
            "artifact manifest",
        ],
        "blocking_conditions": [
            "missing project state",
            "missing roadmap",
            "missing conventions",
            "no research artifacts",
            "degraded review integrity",
        ],
        "preflight_checks": ["project_state", "roadmap", "conventions", "research_artifacts"],
    },
    "gpd:respond-to-referees": {
        "review_mode": "publication",
        "required_outputs": ["REFEREE_RESPONSE.md", "AUTHOR-RESPONSE.md"],
        "required_evidence": [
            "existing manuscript",
            "structured referee issues",
            "revision verification evidence",
        ],
        "blocking_conditions": [
            "missing project state",
            "missing manuscript",
            "degraded review integrity",
        ],
        "preflight_checks": ["project_state", "manuscript", "conventions"],
    },
    "gpd:peer-review": {
        "review_mode": "publication",
        "required_outputs": [".gpd/REFEREE-REPORT.md", ".gpd/CONSISTENCY-REPORT.md"],
        "required_evidence": [
            "existing manuscript",
            "phase summaries or milestone digest",
            "verification reports",
            "bibliography audit",
            "artifact manifest",
            "reproducibility manifest",
        ],
        "blocking_conditions": [
            "missing project state",
            "missing roadmap",
            "missing conventions",
            "missing manuscript",
            "no research artifacts",
            "degraded review integrity",
        ],
        "preflight_checks": ["project_state", "roadmap", "conventions", "research_artifacts", "manuscript"],
    },
    "gpd:verify-work": {
        "review_mode": "review",
        "required_outputs": ["VERIFICATION.md"],
        "required_evidence": ["roadmap", "phase summaries", "artifact files"],
        "blocking_conditions": [
            "missing project state",
            "missing roadmap",
            "missing phase artifacts",
            "degraded review integrity",
        ],
        "preflight_checks": ["project_state", "roadmap", "phase_artifacts"],
        "required_state": "phase_executed",
    },
    "gpd:arxiv-submission": {
        "review_mode": "publication",
        "required_outputs": ["arxiv-submission.tar.gz"],
        "required_evidence": ["compiled manuscript", "bibliography audit", "artifact manifest"],
        "blocking_conditions": [
            "missing manuscript",
            "unresolved publication blockers",
            "degraded review integrity",
        ],
        "preflight_checks": ["project_state", "manuscript", "conventions"],
    },
}


def _parse_review_contract(raw: object, command_name: str, requires: dict[str, object]) -> ReviewCommandContract | None:
    """Parse review contract frontmatter or provide a typed default for review workflows."""
    merged = dict(_DEFAULT_REVIEW_CONTRACTS.get(command_name, {}))
    if isinstance(raw, dict):
        merged.update(raw)

    if not merged:
        return None

    required_state = str(merged.get("required_state", "")).strip()
    if not required_state:
        raw_requires_state = requires.get("state")
        required_state = str(raw_requires_state).strip() if raw_requires_state is not None else ""

    review_mode = str(merged.get("review_mode", "")).strip()
    if not review_mode:
        return None

    schema_version_raw = merged.get("schema_version", 1)
    try:
        schema_version = int(schema_version_raw)
    except (TypeError, ValueError):
        schema_version = 1

    return ReviewCommandContract(
        review_mode=review_mode,
        required_outputs=_parse_str_list(merged.get("required_outputs")),
        required_evidence=_parse_str_list(merged.get("required_evidence")),
        blocking_conditions=_parse_str_list(merged.get("blocking_conditions")),
        preflight_checks=_parse_str_list(merged.get("preflight_checks")),
        required_state=required_state,
        schema_version=schema_version,
    )


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
        review_contract=_parse_review_contract(meta.get("review-contract"), str(meta.get("name", path.stem)), requires),
        content=body.strip(),
        path=str(path),
        source=source,
    )


def _validate_command_name(path: Path, command: CommandDef) -> None:
    """Reject command metadata that drifts from its registry filename."""
    if not command.name.startswith("gpd:"):
        return
    expected_name = f"gpd:{path.stem}"
    if command.name != expected_name:
        raise ValueError(
            f"Command frontmatter name {command.name!r} does not match file stem {path.stem!r}; "
            f"expected {expected_name!r}"
        )


# ─── Cache ───────────────────────────────────────────────────────────────────


@dataclass
class _RegistryCache:
    """Lazy-loaded, process-lifetime cache of all GPD content."""

    _agents: dict[str, AgentDef] | None = field(default=None, repr=False)
    _commands: dict[str, CommandDef] | None = field(default=None, repr=False)
    _skills: dict[str, SkillDef] | None = field(default=None, repr=False)

    def agents(self) -> dict[str, AgentDef]:
        if self._agents is None:
            self._agents = _discover_agents()
        return self._agents

    def commands(self) -> dict[str, CommandDef]:
        if self._commands is None:
            self._commands = _discover_commands()
        return self._commands

    def skills(self) -> dict[str, SkillDef]:
        if self._skills is None:
            self._skills = _discover_skills(self.commands(), self.agents())
        return self._skills

    def invalidate(self) -> None:
        """Clear cached data (useful in tests or after install)."""
        self._agents = None
        self._commands = None
        self._skills = None


_cache = _RegistryCache()


# ─── Discovery ───────────────────────────────────────────────────────────────


def _discover_agents() -> dict[str, AgentDef]:
    """Discover all agent definitions from the primary agents/ directory."""
    result: dict[str, AgentDef] = {}
    if AGENTS_DIR.is_dir():
        for path in sorted(AGENTS_DIR.glob("*.md")):
            agent = _parse_agent_file(path, source="agents")
            result[agent.name] = agent

    return result


def _discover_commands() -> dict[str, CommandDef]:
    """Discover all command definitions from the primary commands/ directory."""
    result: dict[str, CommandDef] = {}
    if COMMANDS_DIR.is_dir():
        for path in sorted(COMMANDS_DIR.glob("*.md")):
            cmd = _parse_command_file(path, source="commands")
            _validate_command_name(path, cmd)
            result[path.stem] = cmd

    return result


_SKILL_CATEGORY_MAP: dict[str, str] = {
    "gpd-execute": "execution",
    "gpd-plan-checker": "verification",
    "gpd-plan": "planning",
    "gpd-verify": "verification",
    "gpd-debug": "debugging",
    "gpd-new": "project",
    "gpd-write": "paper",
    "gpd-peer-review": "paper",
    "gpd-paper": "paper",
    "gpd-literature": "research",
    "gpd-research": "research",
    "gpd-discover": "research",
    "gpd-map": "exploration",
    "gpd-show": "exploration",
    "gpd-progress": "status",
    "gpd-health": "diagnostics",
    "gpd-validate": "verification",
    "gpd-check": "verification",
    "gpd-audit": "verification",
    "gpd-add": "management",
    "gpd-insert": "management",
    "gpd-remove": "management",
    "gpd-merge": "management",
    "gpd-complete": "management",
    "gpd-compact": "management",
    "gpd-pause": "session",
    "gpd-resume": "session",
    "gpd-record": "management",
    "gpd-export": "output",
    "gpd-arxiv": "output",
    "gpd-graph": "visualization",
    "gpd-decisions": "status",
    "gpd-error-propagation": "analysis",
    "gpd-error": "diagnostics",
    "gpd-sensitivity": "analysis",
    "gpd-numerical": "analysis",
    "gpd-dimensional": "analysis",
    "gpd-limiting": "analysis",
    "gpd-parameter": "analysis",
    "gpd-compare": "analysis",
    "gpd-derive": "computation",
    "gpd-set": "configuration",
    "gpd-update": "management",
    "gpd-undo": "management",
    "gpd-sync": "management",
    "gpd-branch": "management",
    "gpd-respond": "paper",
    "gpd-reapply": "management",
    "gpd-regression": "verification",
    "gpd-quick": "execution",
    "gpd-help": "help",
    "gpd-peer-review": "paper",
    "gpd-suggest": "help",
    # Full-name entries for skills not captured by prefix matching.
    "gpd-bibliographer": "research",
    "gpd-check-todos": "management",
    "gpd-consistency-checker": "verification",
    "gpd-discuss-phase": "planning",
    "gpd-executor": "execution",
    "gpd-experiment-designer": "planning",
    "gpd-list-phase-assumptions": "planning",
    "gpd-notation-coordinator": "verification",
    "gpd-phase-researcher": "research",
    "gpd-project-researcher": "research",
    "gpd-referee": "paper",
    "gpd-revise-phase": "management",
    "gpd-roadmapper": "planning",
    "gpd-theory-mapper": "exploration",
    "gpd-verifier": "verification",
}


def _infer_skill_category(skill_name: str) -> str:
    """Infer a user-facing category for a skill name.

    Keys are checked longest-first so that full-name entries (e.g.
    ``gpd-check-todos``) take priority over shorter prefixes (e.g.
    ``gpd-check``).
    """
    for prefix in sorted(_SKILL_CATEGORY_MAP, key=len, reverse=True):
        if skill_name.startswith(prefix):
            return _SKILL_CATEGORY_MAP[prefix]
    return "other"


def _canonical_skill_name_for_command(registry_name: str, command: CommandDef) -> str:
    """Project a command registry entry into the canonical gpd-* skill namespace."""
    if command.name.startswith("gpd:"):
        return command.name.replace("gpd:", "gpd-", 1)
    if registry_name.startswith("gpd-"):
        return registry_name
    return f"gpd-{registry_name}"


def _discover_skills(commands: dict[str, CommandDef], agents: dict[str, AgentDef]) -> dict[str, SkillDef]:
    """Build the canonical skill surface from primary commands and agents.
    """
    result: dict[str, SkillDef] = {}

    for registry_name, command in sorted(commands.items()):
        if command.source != "commands":
            continue
        skill_name = _canonical_skill_name_for_command(registry_name, command)
        if skill_name in result:
            raise ValueError(f"Duplicate skill name {skill_name!r} from command registry")
        result[skill_name] = SkillDef(
            name=skill_name,
            description=command.description,
            content=command.content,
            category=_infer_skill_category(skill_name),
            path=command.path,
            source_kind="command",
            registry_name=registry_name,
        )

    for registry_name, agent in sorted(agents.items()):
        if agent.source != "agents":
            continue
        skill_name = agent.name
        if skill_name in result:
            raise ValueError(f"Duplicate skill name {skill_name!r} across commands and agents")
        result[skill_name] = SkillDef(
            name=skill_name,
            description=agent.description,
            content=agent.system_prompt,
            category=_infer_skill_category(skill_name),
            path=agent.path,
            source_kind="agent",
            registry_name=registry_name,
        )

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
    candidates = [name]
    if name.startswith("gpd:"):
        candidates.append(name.replace("gpd:", "", 1))

    for candidate in candidates:
        command = commands.get(candidate)
        if command is not None:
            return command

    raise KeyError(f"Command not found: {name}")


def list_review_commands() -> list[str]:
    """Return sorted list of command names that expose review contracts."""
    return sorted(cmd.name for cmd in _cache.commands().values() if cmd.review_contract is not None)


def list_skills() -> list[str]:
    """Return sorted list of all canonical skill names."""
    return sorted(_cache.skills())


def get_skill(name: str) -> SkillDef:
    """Get a canonical skill definition by canonical name."""
    skills = _cache.skills()
    candidates = [name]
    if name.startswith("gpd:"):
        candidates.append(name.replace("gpd:", "gpd-", 1))

    for candidate in candidates:
        skill = skills.get(candidate)
        if skill is not None:
            return skill

    raise KeyError(f"Skill not found: {name}")


def invalidate_cache() -> None:
    """Clear the registry cache. Call after install/uninstall or in tests."""
    _cache.invalidate()


__all__ = [
    "AGENTS_DIR",
    "AgentDef",
    "COMMANDS_DIR",
    "CommandDef",
    "ReviewCommandContract",
    "SkillDef",
    "SPECS_DIR",
    "get_agent",
    "get_command",
    "get_skill",
    "invalidate_cache",
    "list_agents",
    "list_commands",
    "list_review_commands",
    "list_skills",
]
