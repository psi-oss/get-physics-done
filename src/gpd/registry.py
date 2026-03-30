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

from gpd.command_labels import canonical_command_label, canonical_skill_label, command_slug_from_label
from gpd.core.review_contract_prompt import render_review_contract_prompt

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
    project_reentry_capable: bool = False
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


def _format_frontmatter_field_subject(field_name: str, owner_name: str | None = None) -> str:
    """Return a field label suitable for targeted validation errors."""
    if owner_name:
        return f"{field_name} for {owner_name}"
    return field_name


def _parse_frontmatter_string_field(
    raw: object,
    *,
    field_name: str,
    owner_name: str,
    default: str = "",
    required: bool = False,
) -> str:
    """Validate frontmatter scalar fields that must stay strings."""
    if raw is None:
        if default:
            return default
        if required:
            subject = _format_frontmatter_field_subject(field_name, owner_name)
            raise ValueError(f"{subject} must be a non-empty string")
        return default
    if not isinstance(raw, str):
        subject = _format_frontmatter_field_subject(field_name, owner_name)
        raise ValueError(f"{subject} must be a string")
    value = raw.strip()
    if required and not value:
        subject = _format_frontmatter_field_subject(field_name, owner_name)
        raise ValueError(f"{subject} must be a non-empty string")
    return value


def _parse_tools(raw: object, *, field_name: str = "tools", owner_name: str | None = None) -> list[str]:
    """Normalize tools-like frontmatter fields with explicit validation."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if not isinstance(raw, list):
        subject = _format_frontmatter_field_subject(field_name, owner_name)
        raise ValueError(f"{subject} must be a string or list of strings")

    values: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            subject = _format_frontmatter_field_subject(field_name, owner_name)
            raise ValueError(f"{subject} must contain only strings")
        value = item.strip()
        if value:
            values.append(value)
    return values


def _parse_requires(raw: object, *, command_name: str) -> dict[str, object]:
    """Normalize command requires frontmatter without accepting malformed mappings."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"requires for {command_name} must be a mapping")
    return raw


def _parse_allowed_tools(raw: object, *, command_name: str) -> list[str]:
    """Normalize command allowed-tools frontmatter without coercing invalid entries."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"allowed-tools for {command_name} must be a list of strings")

    values: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"allowed-tools for {command_name} must contain only strings")
        value = item.strip()
        if value:
            values.append(value)
    return values


def _parse_str_list(raw: object, *, field_name: str, command_name: str) -> list[str]:
    """Normalize review-contract string list fields with explicit validation."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [_parse_required_str_field(raw, field_name=field_name, command_name=command_name)]
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} for {command_name} must be a string or list of strings")

    values: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} for {command_name} must contain only strings")
        values.append(_parse_required_str_field(item, field_name=field_name, command_name=command_name))
    return values


def _parse_required_str_field(raw: object, *, field_name: str, command_name: str) -> str:
    """Normalize required review-contract string fields with explicit validation."""
    if not isinstance(raw, str):
        raise ValueError(f"{field_name} for {command_name} must be a string")
    value = raw.strip()
    if not value:
        raise ValueError(f"{field_name} for {command_name} must be a non-empty string")
    return value


def _parse_optional_str_field(raw: object, *, field_name: str, command_name: str) -> str:
    """Normalize optional review-contract string fields without coercing other types."""
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValueError(f"{field_name} for {command_name} must be a string")
    return raw.strip()


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


def _parse_project_reentry_capable(raw: object, *, command_name: str, context_mode: str) -> bool:
    """Normalize project re-entry metadata and reject invalid command-mode pairings."""
    value = _parse_bool_field(
        raw,
        field_name="project_reentry_capable",
        command_name=command_name,
        default=False,
    )
    if value and context_mode != "project-required":
        raise ValueError(
            f"project_reentry_capable for {command_name} requires context_mode 'project-required'"
        )
    return value


def _parse_non_negative_int_field(raw: object, *, field_name: str, command_name: str, default: int = 0) -> int:
    """Normalize integer-like review-contract fields with explicit validation."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        raise ValueError(f"{field_name} for {command_name} must be an integer")
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
VALID_REVIEW_MODES: tuple[str, ...] = ("publication", "review")
VALID_REVIEW_PREFLIGHT_CHECKS: tuple[str, ...] = (
    "project_state",
    "roadmap",
    "conventions",
    "research_artifacts",
    "manuscript",
    "compiled_manuscript",
    "referee_report_source",
    "phase_artifacts",
)
VALID_REVIEW_REQUIRED_STATES: tuple[str, ...] = ("phase_executed",)


def _parse_context_mode(raw: object, *, command_name: str) -> str:
    """Normalize command context_mode frontmatter to a validated string."""
    if raw is None:
        return "project-required"

    if not isinstance(raw, str):
        raise ValueError(f"context_mode for {command_name} must be a string")
    mode = raw.strip().lower()
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

    if not isinstance(raw, str):
        raise ValueError(f"commit_authority for {agent_name} must be a string")
    authority = raw.strip().lower()
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

    if not isinstance(raw, str):
        raise ValueError(f"{field_name} for {agent_name} must be a string")
    value = raw.strip().lower()
    if not value:
        return default
    if value not in valid_values:
        valid = ", ".join(valid_values)
        raise ValueError(f"Invalid {field_name} {value!r} for {agent_name}; expected one of: {valid}")
    return value


def _parse_review_contract_enum_field(
    raw: object,
    *,
    field_name: str,
    command_name: str,
    valid_values: tuple[str, ...],
) -> str:
    """Normalize review-contract enum fields without coercing unsupported values."""
    value = _parse_required_str_field(raw, field_name=field_name, command_name=command_name)
    if value not in valid_values:
        valid = ", ".join(valid_values)
        raise ValueError(f"{field_name} for {command_name} must be one of: {valid}; got {value!r}")
    return value


def _parse_review_contract_enum_list(
    raw: object,
    *,
    field_name: str,
    command_name: str,
    valid_values: tuple[str, ...],
) -> list[str]:
    """Normalize review-contract enum lists without accepting unknown runtime checks."""
    values = [
        _parse_required_str_field(value, field_name=field_name, command_name=command_name)
        for value in _parse_str_list(raw, field_name=field_name, command_name=command_name)
    ]
    invalid_values = [value for value in values if value not in valid_values]
    if invalid_values:
        valid = ", ".join(valid_values)
        formatted = ", ".join(repr(value) for value in invalid_values)
        raise ValueError(f"{field_name} for {command_name} must contain only: {valid}; got {formatted}")
    return values


def _parse_review_contract_required_state(raw: object, *, command_name: str) -> str:
    """Normalize optional required_state values to the states the CLI evaluates."""
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValueError(f"required_state for {command_name} must be a string")

    value = raw.strip()
    if not value:
        return ""
    if value not in VALID_REVIEW_REQUIRED_STATES:
        valid = ", ".join(VALID_REVIEW_REQUIRED_STATES)
        raise ValueError(f"required_state for {command_name} must be one of: {valid}; got {value!r}")
    return value


_DEFAULT_REVIEW_CONTRACTS: dict[str, dict[str, object]] = {}

_VALID_REVIEW_CONTRACT_KEYS: frozenset[str] = frozenset(
    {
        "review_mode",
        "required_outputs",
        "required_evidence",
        "blocking_conditions",
        "preflight_checks",
        "stage_ids",
        "stage_artifacts",
        "final_decision_output",
        "requires_fresh_context_per_stage",
        "max_review_rounds",
        "required_state",
        "schema_version",
    }
)


def _parse_review_contract_schema_version(raw: object, *, command_name: str) -> int:
    """Validate explicit review-contract schema_version without coercing unsupported values."""
    if raw is None:
        raise ValueError(f"review-contract for {command_name} must set schema_version")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"schema_version for {command_name} must be the integer 1")
    if raw != 1:
        raise ValueError(f"schema_version for {command_name} must be 1")
    return raw


def _review_contract_payload(review_contract: ReviewCommandContract) -> dict[str, object]:
    """Return a stable mapping for model-visible review-contract rendering."""

    return {
        "schema_version": review_contract.schema_version,
        "review_mode": review_contract.review_mode,
        "required_outputs": list(review_contract.required_outputs),
        "required_evidence": list(review_contract.required_evidence),
        "blocking_conditions": list(review_contract.blocking_conditions),
        "preflight_checks": list(review_contract.preflight_checks),
        "stage_ids": list(review_contract.stage_ids),
        "stage_artifacts": list(review_contract.stage_artifacts),
        "final_decision_output": review_contract.final_decision_output,
        "requires_fresh_context_per_stage": review_contract.requires_fresh_context_per_stage,
        "max_review_rounds": review_contract.max_review_rounds,
        "required_state": review_contract.required_state,
    }


def render_review_contract_section(review_contract: ReviewCommandContract | None) -> str:
    """Render a model-visible review-contract block for command prompt bodies."""

    if review_contract is None:
        return ""
    return render_review_contract_prompt(
        yaml.safe_dump(
            {"review_contract": _review_contract_payload(review_contract)},
            sort_keys=False,
            allow_unicode=False,
        )
    )


def _command_model_content(body: str, review_contract: ReviewCommandContract | None) -> str:
    """Return the model-visible command body, including enforced review contracts."""

    review_section = render_review_contract_section(review_contract)
    if not review_section:
        return body
    if not body:
        return review_section
    return f"{review_section}\n\n{body}"


def _parse_review_contract(raw: object, command_name: str) -> ReviewCommandContract | None:
    """Parse review-contract frontmatter into a typed contract with no hidden defaults."""
    merged = dict(_DEFAULT_REVIEW_CONTRACTS.get(command_name, {}))
    if raw is not None and not isinstance(raw, dict):
        raise ValueError(f"review-contract for {command_name} must be a mapping")
    if isinstance(raw, dict):
        unknown_keys = sorted(str(key) for key in raw if str(key) not in _VALID_REVIEW_CONTRACT_KEYS)
        if unknown_keys:
            formatted = ", ".join(unknown_keys)
            raise ValueError(f"Unknown review-contract field(s) for {command_name}: {formatted}")
        merged.update(raw)

    if not merged:
        return None

    raw_review_mode = merged.get("review_mode")
    if raw_review_mode is None:
        if raw is None:
            return None
        raise ValueError(f"review-contract for {command_name} must set review_mode")
    review_mode = _parse_review_contract_enum_field(
        raw_review_mode,
        field_name="review_mode",
        command_name=command_name,
        valid_values=VALID_REVIEW_MODES,
    )
    schema_version = _parse_review_contract_schema_version(merged.get("schema_version"), command_name=command_name)
    required_state = _parse_review_contract_required_state(merged.get("required_state"), command_name=command_name)

    return ReviewCommandContract(
        review_mode=review_mode,
        required_outputs=_parse_str_list(
            merged.get("required_outputs"),
            field_name="required_outputs",
            command_name=command_name,
        ),
        required_evidence=_parse_str_list(
            merged.get("required_evidence"),
            field_name="required_evidence",
            command_name=command_name,
        ),
        blocking_conditions=_parse_str_list(
            merged.get("blocking_conditions"),
            field_name="blocking_conditions",
            command_name=command_name,
        ),
        preflight_checks=_parse_review_contract_enum_list(
            merged.get("preflight_checks"),
            field_name="preflight_checks",
            command_name=command_name,
            valid_values=VALID_REVIEW_PREFLIGHT_CHECKS,
        ),
        stage_ids=_parse_str_list(
            merged.get("stage_ids"),
            field_name="stage_ids",
            command_name=command_name,
        ),
        stage_artifacts=_parse_str_list(
            merged.get("stage_artifacts"),
            field_name="stage_artifacts",
            command_name=command_name,
        ),
        final_decision_output=_parse_optional_str_field(
            merged.get("final_decision_output"),
            field_name="final_decision_output",
            command_name=command_name,
        ),
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
    agent_name = _parse_frontmatter_string_field(
        meta.get("name"),
        field_name="name",
        owner_name=path.stem,
        default=path.stem,
        required=True,
    )
    return AgentDef(
        name=agent_name,
        description=_parse_frontmatter_string_field(
            meta.get("description"),
            field_name="description",
            owner_name=agent_name,
        ),
        system_prompt=body.strip(),
        tools=_parse_tools(meta.get("tools"), owner_name=agent_name),
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
        color=_parse_frontmatter_string_field(
            meta.get("color"),
            field_name="color",
            owner_name=agent_name,
        ),
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

    command_name = _parse_frontmatter_string_field(
        meta.get("name"),
        field_name="name",
        owner_name=path.stem,
        default=path.stem,
        required=True,
    )
    requires = _parse_requires(meta.get("requires"), command_name=command_name)
    allowed_tools = _parse_allowed_tools(meta.get("allowed-tools"), command_name=command_name)

    try:
        review_contract = _parse_review_contract(meta.get("review-contract"), command_name)
    except ValueError as exc:
        raise ValueError(f"Invalid review-contract in {path}: {exc}") from exc

    body = body.strip()
    context_mode = _parse_context_mode(meta.get("context_mode"), command_name=command_name)
    project_reentry_capable = _parse_project_reentry_capable(
        meta.get("project_reentry_capable"),
        command_name=command_name,
        context_mode=context_mode,
    )

    return CommandDef(
        name=command_name,
        description=_parse_frontmatter_string_field(
            meta.get("description"),
            field_name="description",
            owner_name=command_name,
        ),
        argument_hint=_parse_frontmatter_string_field(
            meta.get("argument-hint"),
            field_name="argument-hint",
            owner_name=command_name,
        ),
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        requires=requires,
        allowed_tools=allowed_tools,
        review_contract=review_contract,
        content=_command_model_content(body, review_contract),
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
    slug = command_slug_from_label(name)
    candidates = []
    for candidate in (
        canonical_command_label(name),
        slug,
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

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
    slug = command_slug_from_label(name)

    candidates: list[str] = []
    for candidate in (
        name.strip(),
        canonical_skill_label(name),
        canonical_command_label(name),
        slug,
        f"gpd-{slug}" if slug else None,
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
    "render_review_contract_section",
]
