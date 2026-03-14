"""GPD content registry — canonical source for commands and agents.

Primary GPD commands and agents live in markdown files with YAML frontmatter.
This module parses them once, caches the results, and exposes typed dataclass
definitions so shared consumers can project runtime-specific install or
discovery surfaces without re-parsing the canonical content.
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

# ─── Frontmatter parsing helpers ────────────────────────────────────────────

_LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE = re.compile(r"^(?:[ \t]*\r?\n)+(?=---\r?\n)")
_FRONTMATTER_DELIMITER_RE = re.compile(r"^---[ \t]*(?:\r?\n)?$")


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
    commit_authority: str = "orchestrator"
    surface: str = "internal"
    role_family: str = "analysis"
    artifact_write_authority: str = "scoped_write"
    shared_state_authority: str = "return_only"


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
    context_mode: str = "project-required"
    review_contract: ReviewCommandContract | None = None


@dataclass(frozen=True, slots=True)
class ReviewCommandContract:
    """Typed orchestration contract for review-grade commands."""

    review_mode: str
    required_outputs: list[str]
    required_evidence: list[str]
    blocking_conditions: list[str]
    preflight_checks: list[str]
    stage_ids: list[str] = field(default_factory=list)
    stage_artifacts: list[str] = field(default_factory=list)
    final_decision_output: str = ""
    requires_fresh_context_per_stage: bool = False
    max_review_rounds: int = 0
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
    frontmatter_candidate = _LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE.sub("", text, count=1)
    frontmatter_parts = _split_frontmatter_block(frontmatter_candidate)
    if frontmatter_parts is None:
        return {}, text
    yaml_str, body = frontmatter_parts
    try:
        meta = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML frontmatter: {exc}") from exc
    if meta is None:
        return {}, body
    if not isinstance(meta, dict):
        raise ValueError(f"Frontmatter must parse to a mapping, got {type(meta).__name__}")
    return meta, body


def _split_frontmatter_block(text: str) -> tuple[str, str] | None:
    """Return ``(frontmatter, body)`` when *text* begins with markdown frontmatter."""
    lines = text.splitlines(keepends=True)
    if not lines or not _is_frontmatter_delimiter(lines[0]):
        return None

    frontmatter_lines: list[str] = []
    for index, line in enumerate(lines[1:], start=1):
        if _is_frontmatter_delimiter(line):
            return "".join(frontmatter_lines), "".join(lines[index + 1 :])
        frontmatter_lines.append(line)
    return None


def _is_frontmatter_delimiter(line: str) -> bool:
    """Return whether *line* is a frontmatter delimiter line."""
    return _FRONTMATTER_DELIMITER_RE.fullmatch(line) is not None


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


def _parse_bool_field(raw: object, *, field_name: str, command_name: str, default: bool = False) -> bool:
    """Normalize booleans from YAML, including common quoted string spellings."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw)
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if not normalized:
            return default
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    raise ValueError(f"{field_name} for {command_name} must be a boolean")


def _parse_non_negative_int_field(raw: object, *, field_name: str, command_name: str, default: int = 0) -> int:
    """Normalize integer-like review-contract fields with explicit validation."""
    if raw is None:
        return default
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return default
        raw = stripped
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} for {command_name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{field_name} for {command_name} must be >= 0")
    return value


VALID_CONTEXT_MODES: tuple[str, ...] = ("global", "projectless", "project-aware", "project-required")
VALID_AGENT_COMMIT_AUTHORITIES: tuple[str, ...] = ("direct", "orchestrator")
VALID_AGENT_SURFACES: tuple[str, ...] = ("public", "internal")
VALID_AGENT_ROLE_FAMILIES: tuple[str, ...] = ("worker", "analysis", "verification", "review", "coordination")
VALID_AGENT_ARTIFACT_WRITE_AUTHORITIES: tuple[str, ...] = ("scoped_write", "read_only")
VALID_AGENT_SHARED_STATE_AUTHORITIES: tuple[str, ...] = ("return_only", "direct")


def _parse_context_mode(raw: object, *, command_name: str) -> str:
    """Normalize command context_mode frontmatter to a validated string."""
    if raw is None:
        return "project-required"

    mode = str(raw).strip().lower()
    if not mode:
        return "project-required"
    if mode not in VALID_CONTEXT_MODES:
        valid = ", ".join(VALID_CONTEXT_MODES)
        raise ValueError(f"Invalid context_mode {mode!r} for {command_name}; expected one of: {valid}")
    return mode


def _parse_commit_authority(raw: object, *, agent_name: str) -> str:
    """Normalize agent commit ownership to a validated string."""
    if raw is None:
        return "orchestrator"

    authority = str(raw).strip().lower()
    if not authority:
        return "orchestrator"
    if authority not in VALID_AGENT_COMMIT_AUTHORITIES:
        valid = ", ".join(VALID_AGENT_COMMIT_AUTHORITIES)
        raise ValueError(f"Invalid commit_authority {authority!r} for {agent_name}; expected one of: {valid}")
    return authority


def _parse_agent_metadata_enum(
    raw: object,
    *,
    field_name: str,
    agent_name: str,
    valid_values: tuple[str, ...],
    default: str,
) -> str:
    """Normalize additive agent metadata fields with explicit validation."""
    if raw is None:
        return default

    value = str(raw).strip().lower()
    if not value:
        return default
    if value not in valid_values:
        valid = ", ".join(valid_values)
        raise ValueError(f"Invalid {field_name} {value!r} for {agent_name}; expected one of: {valid}")
    return value


_DEFAULT_REVIEW_CONTRACTS: dict[str, dict[str, object]] = {
    "gpd:write-paper": {
        "review_mode": "publication",
        "required_outputs": ["paper/main.tex", ".gpd/REFEREE-REPORT.md", ".gpd/REFEREE-REPORT.tex"],
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
    "gpd:respond-to-referees": {
        "review_mode": "publication",
        "required_outputs": [".gpd/paper/REFEREE_RESPONSE.md", ".gpd/AUTHOR-RESPONSE.md"],
        "required_evidence": [
            "existing manuscript",
            "structured referee issues",
            "peer-review review ledger when available",
            "peer-review decision artifacts when available",
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
        "required_outputs": [
            ".gpd/review/CLAIMS.json",
            ".gpd/review/STAGE-reader.json",
            ".gpd/review/STAGE-literature.json",
            ".gpd/review/STAGE-math.json",
            ".gpd/review/STAGE-physics.json",
            ".gpd/review/STAGE-interestingness.json",
            ".gpd/review/REVIEW-LEDGER.json",
            ".gpd/review/REFEREE-DECISION.json",
            ".gpd/REFEREE-REPORT.md",
            ".gpd/REFEREE-REPORT.tex",
            ".gpd/CONSISTENCY-REPORT.md",
        ],
        "required_evidence": [
            "existing manuscript",
            "phase summaries or milestone digest",
            "verification reports",
            "bibliography audit",
            "artifact manifest",
            "reproducibility manifest",
            "stage review artifacts",
        ],
        "blocking_conditions": [
            "missing project state",
            "missing roadmap",
            "missing conventions",
            "missing manuscript",
            "no research artifacts",
            "degraded review integrity",
            "unsupported physical significance claims",
            "collapsed novelty or venue fit",
        ],
        "preflight_checks": ["project_state", "roadmap", "conventions", "research_artifacts", "manuscript"],
        "stage_ids": ["reader", "literature", "math", "physics", "interestingness", "meta"],
        "stage_artifacts": [
            ".gpd/review/CLAIMS.json",
            ".gpd/review/STAGE-reader.json",
            ".gpd/review/STAGE-literature.json",
            ".gpd/review/STAGE-math.json",
            ".gpd/review/STAGE-physics.json",
            ".gpd/review/STAGE-interestingness.json",
            ".gpd/review/REVIEW-LEDGER.json",
            ".gpd/review/REFEREE-DECISION.json",
        ],
        "final_decision_output": ".gpd/review/REFEREE-DECISION.json",
        "requires_fresh_context_per_stage": True,
        "max_review_rounds": 3,
    },
    "gpd:verify-work": {
        "review_mode": "review",
        "required_outputs": [".gpd/phases/XX-name/{phase}-VERIFICATION.md"],
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
        stage_ids=_parse_str_list(merged.get("stage_ids")),
        stage_artifacts=_parse_str_list(merged.get("stage_artifacts")),
        final_decision_output=str(merged.get("final_decision_output", "")).strip(),
        requires_fresh_context_per_stage=_parse_bool_field(
            merged.get("requires_fresh_context_per_stage"),
            field_name="requires_fresh_context_per_stage",
            command_name=command_name,
        ),
        max_review_rounds=_parse_non_negative_int_field(
            merged.get("max_review_rounds"),
            field_name="max_review_rounds",
            command_name=command_name,
        ),
        required_state=required_state,
        schema_version=schema_version,
    )


def _parse_agent_file(path: Path, source: str) -> AgentDef:
    """Parse a single agent .md file into an AgentDef."""
    text = path.read_text(encoding="utf-8")
    try:
        meta, body = _parse_frontmatter(text)
    except ValueError as exc:
        raise ValueError(f"Invalid frontmatter in {path}: {exc}") from exc
    agent_name = str(meta.get("name", path.stem))
    return AgentDef(
        name=agent_name,
        description=str(meta.get("description", "")),
        system_prompt=body.strip(),
        tools=_parse_tools(meta.get("tools", "")),
        commit_authority=_parse_commit_authority(meta.get("commit_authority"), agent_name=agent_name),
        surface=_parse_agent_metadata_enum(
            meta.get("surface"),
            field_name="surface",
            agent_name=agent_name,
            valid_values=VALID_AGENT_SURFACES,
            default="internal",
        ),
        role_family=_parse_agent_metadata_enum(
            meta.get("role_family"),
            field_name="role_family",
            agent_name=agent_name,
            valid_values=VALID_AGENT_ROLE_FAMILIES,
            default="analysis",
        ),
        artifact_write_authority=_parse_agent_metadata_enum(
            meta.get("artifact_write_authority"),
            field_name="artifact_write_authority",
            agent_name=agent_name,
            valid_values=VALID_AGENT_ARTIFACT_WRITE_AUTHORITIES,
            default="scoped_write",
        ),
        shared_state_authority=_parse_agent_metadata_enum(
            meta.get("shared_state_authority"),
            field_name="shared_state_authority",
            agent_name=agent_name,
            valid_values=VALID_AGENT_SHARED_STATE_AUTHORITIES,
            default="return_only",
        ),
        color=str(meta.get("color", "")),
        path=str(path),
        source=source,
    )


def _parse_command_file(path: Path, source: str) -> CommandDef:
    """Parse a single command .md file into a CommandDef."""
    text = path.read_text(encoding="utf-8")
    try:
        meta, body = _parse_frontmatter(text)
    except ValueError as exc:
        raise ValueError(f"Invalid frontmatter in {path}: {exc}") from exc

    requires = meta.get("requires", {})
    if not isinstance(requires, dict):
        requires = {}

    allowed_tools_raw = meta.get("allowed-tools", [])
    if not isinstance(allowed_tools_raw, list):
        allowed_tools_raw = []

    try:
        review_contract = _parse_review_contract(meta.get("review-contract"), str(meta.get("name", path.stem)), requires)
    except ValueError as exc:
        raise ValueError(f"Invalid review-contract in {path}: {exc}") from exc

    return CommandDef(
        name=meta.get("name", path.stem),
        description=str(meta.get("description", "")),
        argument_hint=str(meta.get("argument-hint", "")),
        context_mode=_parse_context_mode(meta.get("context_mode"), command_name=str(meta.get("name", path.stem))),
        requires=requires,
        allowed_tools=[str(t) for t in allowed_tools_raw],
        review_contract=review_contract,
        content=body.strip(),
        path=str(path),
        source=source,
    )


def _validate_command_name(path: Path, command: CommandDef) -> None:
    """Reject command metadata that drifts from its registry filename."""
    expected_name = f"gpd:{path.stem}"
    if command.name != expected_name:
        raise ValueError(
            f"Command frontmatter name {command.name!r} does not match file stem {path.stem!r}; "
            f"expected {expected_name!r}"
        )


def load_agents_from_dir(agents_dir: Path) -> dict[str, AgentDef]:
    """Parse agent definitions from an arbitrary agents directory."""
    result: dict[str, AgentDef] = {}
    if not agents_dir.is_dir():
        return result

    for path in sorted(agents_dir.glob("*.md")):
        agent = _parse_agent_file(path, source="agents")
        if agent.name in result:
            first_path = result[agent.name].path
            raise ValueError(f"Duplicate agent name {agent.name!r} discovered in {path} and {first_path}")
        result[agent.name] = agent

    return result


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
    return load_agents_from_dir(AGENTS_DIR)


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
    "gpd-review": "paper",
    "gpd-paper": "paper",
    "gpd-literature": "research",
    "gpd-research": "research",
    "gpd-discover": "research",
    "gpd-explain": "help",
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
    "gpd-suggest": "help",
    # Full-name entries for skills not captured by prefix matching.
    "gpd-bibliographer": "research",
    "gpd-check-todos": "management",
    "gpd-consistency-checker": "verification",
    "gpd-discuss-phase": "planning",
    "gpd-executor": "execution",
    "gpd-experiment-designer": "planning",
    "gpd-explainer": "help",
    "gpd-list-phase-assumptions": "planning",
    "gpd-notation-coordinator": "verification",
    "gpd-phase-researcher": "research",
    "gpd-project-researcher": "research",
    "gpd-referee": "paper",
    "gpd-revise-phase": "management",
    "gpd-roadmapper": "planning",
    "gpd-slides": "output",
    "gpd-research-mapper": "exploration",
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
    """Build the canonical registry/MCP skill index from primary commands and agents."""
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
    normalized = name.strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]

    candidates = [normalized]
    if normalized.startswith("gpd:"):
        candidates.append(normalized.replace("gpd:", "", 1))

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
    """Get a canonical skill definition by canonical name or registry key."""
    skills = _cache.skills()
    normalized = name.strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]

    candidates: list[str] = []
    for candidate in (
        normalized,
        normalized.replace("gpd:", "gpd-", 1) if normalized.startswith("gpd:") else None,
        normalized.replace("gpd-", "gpd:", 1) if normalized.startswith("gpd-") else None,
        f"gpd-{normalized}" if normalized and not normalized.startswith(("gpd-", "gpd:")) else None,
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

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
    "VALID_AGENT_ARTIFACT_WRITE_AUTHORITIES",
    "VALID_AGENT_COMMIT_AUTHORITIES",
    "VALID_AGENT_ROLE_FAMILIES",
    "VALID_AGENT_SHARED_STATE_AUTHORITIES",
    "VALID_AGENT_SURFACES",
    "VALID_CONTEXT_MODES",
    "get_agent",
    "get_command",
    "get_skill",
    "invalidate_cache",
    "load_agents_from_dir",
    "list_agents",
    "list_commands",
    "list_review_commands",
    "list_skills",
]
