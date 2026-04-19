"""GPD content registry — canonical source for commands and agents.

Primary GPD commands and agents live in markdown files with YAML frontmatter.
This module parses them once, caches the results, and exposes typed dataclass
definitions so shared consumers can project runtime-specific install or
discovery surfaces without re-parsing the canonical content.
"""

from __future__ import annotations

import dataclasses
import re
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from gpd.adapters.install_utils import expand_at_includes
from gpd.command_labels import canonical_command_label, canonical_skill_label, command_slug_from_label
from gpd.core.model_visible_sections import render_model_visible_yaml_section
from gpd.core.model_visible_text import (
    AGENT_ARTIFACT_WRITE_AUTHORITIES,
    AGENT_COMMIT_AUTHORITIES,
    AGENT_ROLE_FAMILIES,
    AGENT_SHARED_STATE_AUTHORITIES,
    AGENT_SURFACES,
    COMMAND_POLICY_FRONTMATTER_KEY,
    COMMAND_POLICY_PROMPT_WRAPPER_KEY,
    REVIEW_CONTRACT_FRONTMATTER_KEY,
    REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
    VALID_CONTEXT_MODES,
    agent_visibility_note,
    command_visibility_note,
    skeptical_rigor_guardrails_section,
)
from gpd.core.review_contract_prompt import (
    normalize_review_contract_frontmatter_payload,
    render_review_contract_prompt,
)
from gpd.core.strict_yaml import load_strict_yaml
from gpd.core.workflow_staging import (
    WorkflowStageManifest,
    invalidate_workflow_stage_manifest_cache,
    known_init_fields_for_workflow,
    load_workflow_stage_manifest_from_path,
    resolve_workflow_stage_manifest_path,
)
from gpd.specs import SPECS_DIR

# ─── Package layout ──────────────────────────────────────────────────────────

_PKG_ROOT = Path(__file__).resolve().parent  # gpd/
AGENTS_DIR = _PKG_ROOT / "agents"
COMMANDS_DIR = _PKG_ROOT / "commands"
_MODEL_VISIBLE_INCLUDE_PATH_PREFIX = "{GPD_INSTALL_DIR}/__gpd_registry_include__/"
LOCAL_CLI_BRIDGE_WORKFLOW_EXEMPT_COMMANDS: frozenset[str] = frozenset({"health", "suggest-next"})
CommandNameFormat = Literal["slug", "label"]

# ─── Frontmatter parsing helpers ────────────────────────────────────────────

_LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE = re.compile(r"^(?:[ \t]*\r?\n)+(?=---\r?\n)")
_FRONTMATTER_DELIMITER_RE = re.compile(r"^---[ \t]*(?:\r?\n)?$")
_MODEL_VISIBLE_INCLUDE_START_RE = re.compile(r"^[ \t]*<!-- \[included:.*?\] -->[ \t]*$")
_MODEL_VISIBLE_INCLUDE_END_RE = re.compile(r"^[ \t]*<!-- \[end included\] -->[ \t]*$")
_MODEL_VISIBLE_FENCE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})")
_STANDALONE_HTML_COMMENT_RE = re.compile(r"^[ \t]*<!--(?P<body>.*?)-->[ \t]*$", re.DOTALL)
_SPAWN_CONTRACT_BLOCK_RE = re.compile(
    r"^[ \t]*<spawn_contract>[ \t]*$\n(?P<body>.*?)^[ \t]*</spawn_contract>[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
_COMMAND_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "argument-hint",
        # Runtime-projected prompt surfaces may still carry this presentation key.
        "color",
        "requires",
        "allowed-tools",
        REVIEW_CONTRACT_FRONTMATTER_KEY,
        COMMAND_POLICY_FRONTMATTER_KEY,
        "context_mode",
        "project_reentry_capable",
        # plan-phase carries this metadata in canonical frontmatter even though
        # registry consumers currently do not project it.
        "agent",
    }
)
_AGENT_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "tools",
        "allowed-tools",
        "commit_authority",
        "surface",
        "role_family",
        "artifact_write_authority",
        "shared_state_authority",
        "color",
    }
)
_COMMAND_POLICY_FIELD_ORDER = (
    "schema_version",
    "subject_policy",
    "supporting_context_policy",
    "output_policy",
)
_COMMAND_POLICY_SUBJECT_FIELD_ORDER = (
    "subject_kind",
    "resolution_mode",
    "explicit_input_kinds",
    "allow_external_subjects",
    "allow_interactive_without_subject",
    "supported_roots",
    "allowed_suffixes",
    "bootstrap_allowed",
)
_COMMAND_POLICY_SUPPORTING_CONTEXT_FIELD_ORDER = (
    "project_context_mode",
    "project_reentry_mode",
    "required_file_patterns",
    "optional_file_patterns",
)
_COMMAND_POLICY_OUTPUT_FIELD_ORDER = (
    "output_mode",
    "managed_root_kind",
    "default_output_subtree",
    "stage_artifact_policy",
)
_COMMAND_POLICY_KEYS = frozenset(_COMMAND_POLICY_FIELD_ORDER)
_COMMAND_POLICY_SUBJECT_KEYS = frozenset(_COMMAND_POLICY_SUBJECT_FIELD_ORDER)
_COMMAND_POLICY_SUPPORTING_CONTEXT_KEYS = frozenset(_COMMAND_POLICY_SUPPORTING_CONTEXT_FIELD_ORDER)
_COMMAND_POLICY_OUTPUT_KEYS = frozenset(_COMMAND_POLICY_OUTPUT_FIELD_ORDER)
_WRITE_PAPER_EXTERNAL_AUTHORING_INPUT_KIND = "authoring_intake_manifest"
_WRITE_PAPER_EXTERNAL_AUTHORING_SCOPE = "explicit_intake_manifest"
_WRITE_PAPER_EXTERNAL_AUTHORING_REQUIRED_OUTPUTS = (
    "${PAPER_DIR}/{topic_specific_stem}.tex",
    "${PAPER_DIR}/PAPER-CONFIG.json",
    "${PAPER_DIR}/ARTIFACT-MANIFEST.json",
    "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
    "${PAPER_DIR}/reproducibility-manifest.json",
)
_WRITE_PAPER_EXTERNAL_AUTHORING_REQUIRED_EVIDENCE = (
    "validated external authoring intake manifest with explicit claim-to-evidence bindings",
)
_WRITE_PAPER_EXTERNAL_AUTHORING_BLOCKING_CONDITIONS = (
    "invalid or incomplete external authoring intake manifest",
)
_WRITE_PAPER_EXTERNAL_AUTHORING_RELAXED_PREFLIGHT_CHECKS = (
    "project_state",
    "roadmap",
    "conventions",
    "research_artifacts",
    "verification_reports",
    "manuscript_proof_review",
)
_WRITE_PAPER_EXTERNAL_AUTHORING_OPTIONAL_PREFLIGHT_CHECKS = (
    "artifact_manifest",
    "bibliography_audit",
    "bibliography_audit_clean",
    "reproducibility_manifest",
    "reproducibility_ready",
)


def _validate_command_frontmatter_keys(meta: dict[object, object], *, command_name: str) -> None:
    """Reject unknown command frontmatter keys so all command surfaces stay aligned."""

    unknown_keys = sorted(str(key) for key in meta if str(key) not in _COMMAND_FRONTMATTER_KEYS)
    if unknown_keys:
        raise ValueError(f"unknown frontmatter keys for {command_name}: {', '.join(unknown_keys)}")


def _validate_agent_frontmatter_keys(meta: dict[object, object], *, agent_name: str) -> None:
    """Reject unknown agent frontmatter keys so all agent surfaces stay aligned."""

    unknown_keys = sorted(str(key) for key in meta if str(key) not in _AGENT_FRONTMATTER_KEYS)
    if unknown_keys:
        raise ValueError(f"unknown frontmatter keys for {agent_name}: {', '.join(unknown_keys)}")


def _inline_model_visible_includes(content: str) -> str:
    """Inline shared include directives while preserving canonical placeholder tokens."""

    expanded = expand_at_includes(content, _PKG_ROOT, _MODEL_VISIBLE_INCLUDE_PATH_PREFIX)
    cleaned_lines: list[str] = []
    in_included_block = False
    active_fence_char: str | None = None
    active_fence_length = 0

    for line in expanded.splitlines(keepends=True):
        stripped = line.strip()
        if _MODEL_VISIBLE_INCLUDE_START_RE.fullmatch(stripped):
            in_included_block = True
            continue
        if _MODEL_VISIBLE_INCLUDE_END_RE.fullmatch(stripped):
            in_included_block = False
            continue

        fence_match = _MODEL_VISIBLE_FENCE_RE.match(line)
        if active_fence_char is None:
            if fence_match is not None:
                fence = fence_match.group("fence")
                active_fence_char = fence[0]
                active_fence_length = len(fence)
                cleaned_lines.append(line)
                continue
        else:
            if (
                fence_match is not None
                and fence_match.group("fence")[0] == active_fence_char
                and len(fence_match.group("fence")) >= active_fence_length
            ):
                active_fence_char = None
                active_fence_length = 0
            cleaned_lines.append(line)
            continue

        comment_match = _STANDALONE_HTML_COMMENT_RE.fullmatch(stripped)
        if comment_match is not None and not in_included_block:
            body = comment_match.group("body").strip()
            # Keep executable contract markers visible even in direct prompt text.
            if body.startswith("ASSERT_CONVENTION:"):
                cleaned_lines.append(line)
            continue

        cleaned_lines.append(line)

    cleaned = "".join(cleaned_lines)
    return (
        cleaned.replace(
            f"{_MODEL_VISIBLE_INCLUDE_PATH_PREFIX}get-physics-done/",
            "{GPD_INSTALL_DIR}/",
        )
        .replace(
            f"{_MODEL_VISIBLE_INCLUDE_PATH_PREFIX}get-physics-done",
            "{GPD_INSTALL_DIR}",
        )
        .replace(
            f"{_MODEL_VISIBLE_INCLUDE_PATH_PREFIX}agents/",
            "{GPD_AGENTS_DIR}/",
        )
        .replace(
            f"{_MODEL_VISIBLE_INCLUDE_PATH_PREFIX}agents",
            "{GPD_AGENTS_DIR}",
        )
    )


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
    command_policy: CommandPolicy | None = None
    review_contract: ReviewCommandContract | None = None
    agent: str | None = None
    staged_loading: WorkflowStageManifest | None = None
    spawn_contracts: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class CommandSubjectPolicy:
    """Typed command subject-resolution policy."""

    subject_kind: str | None = None
    resolution_mode: str | None = None
    explicit_input_kinds: list[str] = field(default_factory=list)
    allow_external_subjects: bool | None = None
    allow_interactive_without_subject: bool | None = None
    supported_roots: list[str] = field(default_factory=list)
    allowed_suffixes: list[str] = field(default_factory=list)
    bootstrap_allowed: bool | None = None


@dataclass(frozen=True, slots=True)
class CommandSupportingContextPolicy:
    """Typed command supporting-context policy."""

    project_context_mode: str | None = None
    project_reentry_mode: str | None = None
    required_file_patterns: list[str] = field(default_factory=list)
    optional_file_patterns: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CommandOutputPolicy:
    """Typed command output policy."""

    output_mode: str | None = None
    managed_root_kind: str | None = None
    default_output_subtree: str | None = None
    stage_artifact_policy: str | None = None


@dataclass(frozen=True, slots=True)
class CommandPolicy:
    """Typed additive command policy compiled from frontmatter and legacy fields."""

    schema_version: int = 1
    subject_policy: CommandSubjectPolicy | None = None
    supporting_context_policy: CommandSupportingContextPolicy | None = None
    output_policy: CommandOutputPolicy | None = None


@dataclass(frozen=True, slots=True)
class ReviewContractConditionalRequirement:
    """Condition-scoped review-contract requirements."""

    when: str
    required_outputs: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    blocking_conditions: list[str] = field(default_factory=list)
    preflight_checks: list[str] = field(default_factory=list)
    blocking_preflight_checks: list[str] = field(default_factory=list)
    stage_artifacts: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReviewContractScopeVariant:
    """Scope-specific review-contract overrides and relaxed preflight metadata."""

    scope: str
    activation: str
    relaxed_preflight_checks: list[str] = field(default_factory=list)
    optional_preflight_checks: list[str] = field(default_factory=list)
    required_outputs_override: list[str] = field(default_factory=list)
    required_evidence_override: list[str] = field(default_factory=list)
    blocking_conditions_override: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReviewCommandContract:
    """Typed orchestration contract for review-grade commands."""

    review_mode: str
    required_outputs: list[str]
    required_evidence: list[str]
    blocking_conditions: list[str]
    preflight_checks: list[str]
    stage_artifacts: list[str] = field(default_factory=list)
    conditional_requirements: list[ReviewContractConditionalRequirement] = field(default_factory=list)
    scope_variants: list[ReviewContractScopeVariant] = field(default_factory=list)
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
    spawn_contracts: tuple[dict[str, object], ...] = ()


# ─── Parsing helpers ─────────────────────────────────────────────────────────


def _frontmatter_parts(text: str) -> tuple[str | None, str]:
    """Return raw frontmatter YAML and body from markdown text when present."""

    text = text.lstrip("﻿")
    frontmatter_candidate = _LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE.sub("", text, count=1)
    frontmatter_parts = _split_frontmatter_block(frontmatter_candidate)
    if frontmatter_parts is None:
        return None, text
    return frontmatter_parts


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse YAML frontmatter from markdown text. Returns (meta, body)."""
    yaml_str, body = _frontmatter_parts(text)
    if yaml_str is None:
        return {}, text
    meta = _load_frontmatter_mapping(yaml_str, error_prefix="Malformed YAML frontmatter")
    return meta, body


def _load_frontmatter_mapping(frontmatter: str, *, error_prefix: str) -> dict[str, object]:
    """Load YAML frontmatter into a mapping while rejecting duplicate keys."""

    try:
        meta = load_strict_yaml(frontmatter) if frontmatter.strip() else {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{error_prefix}: {exc}") from exc
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise ValueError(f"Frontmatter must parse to a mapping, got {type(meta).__name__}")
    return meta


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


def _raw_scalar_frontmatter_value(frontmatter: str | None, *, field_name: str) -> str | None:
    """Return the raw scalar text for one frontmatter field when present."""

    if not frontmatter:
        return None

    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(field_name)}:[ \t]*(?P<value>[^#\r\n]*)[ \t]*(?:#.*)?$")
    match = pattern.search(frontmatter)
    if match is None:
        return None
    return match.group("value").strip()


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
    values: list[str] = []
    seen: set[str] = set()
    subject = _format_frontmatter_field_subject(field_name, owner_name)

    def _append(value: str) -> None:
        if not value:
            raise ValueError(f"{subject} must not contain blank entries")
        if value not in seen:
            seen.add(value)
            values.append(value)

    if isinstance(raw, str):
        for item in raw.split(","):
            _append(item.strip())
        return values
    if not isinstance(raw, list):
        raise ValueError(f"{subject} must be a string or list of strings")

    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"{subject} must contain only strings")
        _append(item.strip())
    return values


def _merge_tool_lists(*tool_lists: list[str]) -> list[str]:
    """Merge multiple tool lists while preserving first-seen order."""
    merged: list[str] = []
    seen: set[str] = set()
    for tool_list in tool_lists:
        for tool in tool_list:
            if tool in seen:
                continue
            seen.add(tool)
            merged.append(tool)
    return merged


def _parse_requires(raw: object, *, command_name: str) -> dict[str, object]:
    """Normalize command requires frontmatter without accepting malformed mappings."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"requires for {command_name} must be a mapping")
    unsupported_keys = sorted(str(key) for key in raw if str(key) != "files")
    if unsupported_keys:
        formatted = ", ".join(unsupported_keys)
        raise ValueError(f"requires for {command_name} only supports files; got {formatted}")
    files = raw.get("files")
    if files is None:
        return {}
    normalized_files: list[str] = []
    seen: set[str] = set()
    if isinstance(files, str):
        candidates = [files]
    elif isinstance(files, list):
        candidates = files
    else:
        raise ValueError(f"files for {command_name} must be a string or list of strings")
    for item in candidates:
        if not isinstance(item, str):
            raise ValueError(f"files for {command_name} must contain only strings")
        normalized = item.strip()
        if not normalized:
            raise ValueError(f"files for {command_name} must not contain blank entries")
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_files.append(normalized)
    return {"files": normalized_files}


def _parse_allowed_tools(raw: object, *, command_name: str) -> list[str]:
    """Normalize command allowed-tools frontmatter without coercing invalid entries."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"allowed-tools for {command_name} must be a list of strings")

    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"allowed-tools for {command_name} must contain only strings")
        value = item.strip()
        if not value:
            raise ValueError(f"allowed-tools for {command_name} must not contain blank entries")
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _normalize_command_policy_string(
    value: object,
    *,
    field_name: str,
    command_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} for {command_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} for {command_name} must be a non-empty string")
    return normalized


def _normalize_command_policy_bool(
    value: object,
    *,
    field_name: str,
    command_name: str,
) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} for {command_name} must be a boolean")


def _normalize_command_policy_string_list(
    value: object,
    *,
    field_name: str,
    command_name: str,
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} for {command_name} must be a list of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} for {command_name} must contain only strings")
        entry = item.strip()
        if not entry:
            raise ValueError(f"{field_name} for {command_name} must not contain blank entries")
        if entry in seen:
            raise ValueError(f"{field_name} for {command_name} must not contain duplicates")
        seen.add(entry)
        normalized.append(entry)
    return normalized


def _normalize_command_policy_context_mode(
    value: object,
    *,
    field_name: str,
    command_name: str,
) -> str:
    normalized = _normalize_command_policy_string(
        value,
        field_name=field_name,
        command_name=command_name,
    ).lower()
    if normalized not in VALID_CONTEXT_MODES:
        valid = ", ".join(VALID_CONTEXT_MODES)
        raise ValueError(f"{field_name} for {command_name} must be one of: {valid}")
    return normalized


def _command_policy_frontmatter_value(
    meta: dict[str, object],
    *,
    command_name: str,
) -> tuple[object, bool]:
    """Return the canonical command-policy frontmatter payload and whether it was explicit."""

    if COMMAND_POLICY_PROMPT_WRAPPER_KEY in meta:
        raise ValueError(
            f"command-policy for {command_name} must use the canonical frontmatter key "
            f"'{COMMAND_POLICY_FRONTMATTER_KEY}'"
        )
    if COMMAND_POLICY_FRONTMATTER_KEY not in meta:
        return None, False
    return meta.get(COMMAND_POLICY_FRONTMATTER_KEY), True


def _command_policy_supporting_context_from_legacy(
    *,
    context_mode: str,
    project_reentry_capable: bool,
    requires: dict[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "project_context_mode": context_mode,
        "project_reentry_mode": "allowed" if project_reentry_capable else "disallowed",
    }
    required_files = requires.get("files")
    if isinstance(required_files, list) and required_files:
        payload["required_file_patterns"] = list(required_files)
    return payload


def _command_policy_requests_check(
    review_contract: ReviewCommandContract | None,
    check_name: str,
) -> bool:
    if review_contract is None:
        return False
    return check_name in list(getattr(review_contract, "preflight_checks", []) or [])


def _command_policy_is_publication_contract(review_contract: ReviewCommandContract | None) -> bool:
    return str(getattr(review_contract, "review_mode", "") or "").strip() == "publication"


def _command_policy_supported_roots_from_patterns(patterns: list[str]) -> list[str]:
    supported_roots: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        parts = Path(pattern).parts
        if not parts:
            continue
        root = parts[0].strip()
        if not root or root in seen:
            continue
        seen.add(root)
        supported_roots.append(root)
    return supported_roots


def _publication_contract_mentions_external_artifact(review_contract: ReviewCommandContract | None) -> bool:
    if review_contract is None:
        return False
    textual_cues = [
        *(str(item) for item in list(getattr(review_contract, "required_evidence", []) or [])),
        *(str(item) for item in list(getattr(review_contract, "blocking_conditions", []) or [])),
    ]
    return any("external-artifact review" in cue.casefold() for cue in textual_cues)


def _publication_compat_subject_policy(
    *,
    review_contract: ReviewCommandContract | None,
    legacy_supporting_context: dict[str, object],
) -> dict[str, object] | None:
    if not _command_policy_is_publication_contract(review_contract):
        return None
    if not _command_policy_requests_check(review_contract, "manuscript"):
        return None

    required_patterns = [
        str(pattern).strip()
        for pattern in list(legacy_supporting_context.get("required_file_patterns", []) or [])
        if str(pattern).strip()
    ]
    supported_roots = _command_policy_supported_roots_from_patterns(required_patterns)
    allow_external_subjects = _publication_contract_mentions_external_artifact(review_contract)
    bootstrap_allowed = (
        not required_patterns
        and not _command_policy_requests_check(review_contract, "compiled_manuscript")
        and not _command_policy_requests_check(review_contract, "referee_report_source")
    )

    explicit_input_kinds: list[str] = []
    if _command_policy_requests_check(review_contract, "referee_report_source"):
        explicit_input_kinds.extend(["referee_report_path", "paste_referee_report"])
    elif supported_roots:
        explicit_input_kinds.extend(["manuscript_root", "manuscript_path"])
    if allow_external_subjects:
        explicit_input_kinds.append("publication_artifact_path")

    allowed_suffixes = [".tex"]
    if not _command_policy_requests_check(review_contract, "compiled_manuscript"):
        allowed_suffixes.append(".md")
    if allow_external_subjects:
        for suffix in (".txt", ".pdf"):
            if suffix not in allowed_suffixes:
                allowed_suffixes.append(suffix)

    resolution_mode = "project_manuscript"
    if bootstrap_allowed:
        resolution_mode = "project_manuscript_or_bootstrap"
    elif _command_policy_requests_check(review_contract, "referee_report_source"):
        resolution_mode = "project_manuscript_with_report_source"
    elif explicit_input_kinds:
        resolution_mode = "explicit_or_project_manuscript"

    payload: dict[str, object] = {
        "subject_kind": "publication",
        "resolution_mode": resolution_mode,
        "allowed_suffixes": allowed_suffixes,
    }
    if explicit_input_kinds:
        payload["explicit_input_kinds"] = explicit_input_kinds
    if supported_roots:
        payload["supported_roots"] = supported_roots
    if allow_external_subjects:
        payload["allow_external_subjects"] = True
    if (
        allow_external_subjects
        and str(legacy_supporting_context.get("project_context_mode", "")).strip() == "project-aware"
    ):
        payload["allow_interactive_without_subject"] = True
    if bootstrap_allowed:
        payload["bootstrap_allowed"] = True
    return payload


def _merge_command_policy_defaults(
    explicit_mapping: dict[str, object] | None,
    default_mapping: dict[str, object] | None,
) -> dict[str, object] | None:
    if default_mapping is None:
        return dict(explicit_mapping) if explicit_mapping is not None else None
    if explicit_mapping is None:
        return dict(default_mapping)
    merged = dict(default_mapping)
    merged.update(explicit_mapping)
    return merged


def _merge_command_policy_submapping(
    explicit_mapping: dict[str, object] | None,
    legacy_mapping: dict[str, object] | None,
    *,
    field_name: str,
    command_name: str,
    allow_explicit_override: bool = False,
) -> dict[str, object] | None:
    if explicit_mapping is None:
        if legacy_mapping:
            return dict(legacy_mapping)
        return None
    if not legacy_mapping:
        return dict(explicit_mapping)

    merged = dict(legacy_mapping)
    for key, value in explicit_mapping.items():
        legacy_value = merged.get(key)
        if legacy_value is None or legacy_value == []:
            merged[key] = value
            continue
        if allow_explicit_override:
            merged[key] = value
            continue
        if value != legacy_value:
            raise ValueError(f"{field_name}.{key} for {command_name} must stay aligned with legacy command metadata")
    return merged


def _normalize_command_subject_policy(
    raw: object,
    *,
    command_name: str,
) -> dict[str, object] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError(f"command_policy.subject_policy for {command_name} must be a mapping")
    raw_mapping = dict(raw)
    unknown_keys = sorted(str(key) for key in raw_mapping if str(key) not in _COMMAND_POLICY_SUBJECT_KEYS)
    if unknown_keys:
        formatted = ", ".join(unknown_keys)
        raise ValueError(f"Unknown command-policy field(s): subject_policy.{formatted}")

    normalized: dict[str, object] = {}
    for field_name in ("subject_kind", "resolution_mode"):
        if field_name in raw_mapping:
            normalized[field_name] = _normalize_command_policy_string(
                raw_mapping.get(field_name),
                field_name=f"command_policy.subject_policy.{field_name}",
                command_name=command_name,
            )
    for field_name in ("allow_external_subjects", "allow_interactive_without_subject", "bootstrap_allowed"):
        if field_name in raw_mapping:
            normalized[field_name] = _normalize_command_policy_bool(
                raw_mapping.get(field_name),
                field_name=f"command_policy.subject_policy.{field_name}",
                command_name=command_name,
            )
    for field_name in ("explicit_input_kinds", "supported_roots", "allowed_suffixes"):
        if field_name in raw_mapping:
            normalized[field_name] = _normalize_command_policy_string_list(
                raw_mapping.get(field_name),
                field_name=f"command_policy.subject_policy.{field_name}",
                command_name=command_name,
            )
    allowed_suffixes = normalized.get("allowed_suffixes")
    if isinstance(allowed_suffixes, list):
        invalid_suffixes = [suffix for suffix in allowed_suffixes if not suffix.startswith(".")]
        if invalid_suffixes:
            formatted = ", ".join(repr(item) for item in invalid_suffixes)
            raise ValueError(
                f"command_policy.subject_policy.allowed_suffixes for {command_name} "
                f"must contain dotted suffixes like '.tex'; got {formatted}"
            )
    return normalized or None


def _normalize_command_supporting_context_policy(
    raw: object,
    *,
    command_name: str,
) -> dict[str, object] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError(f"command_policy.supporting_context_policy for {command_name} must be a mapping")
    raw_mapping = dict(raw)
    unknown_keys = sorted(str(key) for key in raw_mapping if str(key) not in _COMMAND_POLICY_SUPPORTING_CONTEXT_KEYS)
    if unknown_keys:
        formatted = ", ".join(unknown_keys)
        raise ValueError(f"Unknown command-policy field(s): supporting_context_policy.{formatted}")

    normalized: dict[str, object] = {}
    if "project_context_mode" in raw_mapping:
        normalized["project_context_mode"] = _normalize_command_policy_context_mode(
            raw_mapping.get("project_context_mode"),
            field_name="command_policy.supporting_context_policy.project_context_mode",
            command_name=command_name,
        )
    if "project_reentry_mode" in raw_mapping:
        normalized["project_reentry_mode"] = _normalize_command_policy_string(
            raw_mapping.get("project_reentry_mode"),
            field_name="command_policy.supporting_context_policy.project_reentry_mode",
            command_name=command_name,
        )
    for field_name in ("required_file_patterns", "optional_file_patterns"):
        if field_name in raw_mapping:
            normalized[field_name] = _normalize_command_policy_string_list(
                raw_mapping.get(field_name),
                field_name=f"command_policy.supporting_context_policy.{field_name}",
                command_name=command_name,
            )
    return normalized or None


def _normalize_command_output_policy(
    raw: object,
    *,
    command_name: str,
) -> dict[str, object] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError(f"command_policy.output_policy for {command_name} must be a mapping")
    raw_mapping = dict(raw)
    unknown_keys = sorted(str(key) for key in raw_mapping if str(key) not in _COMMAND_POLICY_OUTPUT_KEYS)
    if unknown_keys:
        formatted = ", ".join(unknown_keys)
        raise ValueError(f"Unknown command-policy field(s): output_policy.{formatted}")

    normalized: dict[str, object] = {}
    for field_name in _COMMAND_POLICY_OUTPUT_FIELD_ORDER:
        if field_name in raw_mapping:
            normalized[field_name] = _normalize_command_policy_string(
                raw_mapping.get(field_name),
                field_name=f"command_policy.output_policy.{field_name}",
                command_name=command_name,
            )
    return normalized or None


def _command_policy_payload(command_policy: object) -> dict[str, object] | None:
    def _strip_none_fields(value: object) -> object:
        if isinstance(value, dict):
            return {key: _strip_none_fields(item) for key, item in value.items() if item is not None}
        if isinstance(value, list):
            return [_strip_none_fields(item) for item in value]
        return value

    if command_policy is None:
        return None
    if isinstance(command_policy, Mapping):
        return dict(_strip_none_fields(dict(command_policy)))
    if dataclasses.is_dataclass(command_policy):
        payload = _strip_none_fields(dataclasses.asdict(command_policy))
        return payload if isinstance(payload, dict) else None
    raise ValueError("command policy must be a mapping or dataclass instance")


def _normalize_command_policy_payload(
    command_policy: object,
    *,
    command_name: str,
    context_mode: str,
    project_reentry_capable: bool,
    requires: dict[str, object],
    review_contract: ReviewCommandContract | None = None,
    explicit: bool = False,
) -> dict[str, object]:
    legacy_supporting_context = _command_policy_supporting_context_from_legacy(
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        requires=requires,
    )
    compat_subject_policy = _publication_compat_subject_policy(
        review_contract=review_contract,
        legacy_supporting_context=legacy_supporting_context,
    )
    legacy_payload: dict[str, object] = {
        "schema_version": 1,
        "subject_policy": compat_subject_policy,
        "supporting_context_policy": legacy_supporting_context,
    }

    payload = _command_policy_payload(command_policy)
    if payload is None:
        if explicit:
            raise ValueError("command policy must set schema_version")
        return legacy_payload
    if not isinstance(payload, dict):
        raise ValueError(f"command policy for {command_name} must be a mapping")

    unknown_keys = sorted(str(key) for key in payload if str(key) not in _COMMAND_POLICY_KEYS)
    if unknown_keys:
        formatted = ", ".join(unknown_keys)
        raise ValueError(f"Unknown command-policy field(s): {formatted}")

    if "schema_version" not in payload:
        raise ValueError("command policy must set schema_version")
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError("command policy schema_version must be the integer 1")
    if schema_version != 1:
        raise ValueError("command policy schema_version must be 1")

    subject_policy = _merge_command_policy_defaults(
        _normalize_command_subject_policy(payload.get("subject_policy"), command_name=command_name),
        compat_subject_policy,
    )
    supporting_context_policy = _normalize_command_supporting_context_policy(
        payload.get("supporting_context_policy"),
        command_name=command_name,
    )
    output_policy = _normalize_command_output_policy(payload.get("output_policy"), command_name=command_name)

    return {
        "schema_version": schema_version,
        "subject_policy": subject_policy,
        "supporting_context_policy": _merge_command_policy_submapping(
            supporting_context_policy,
            legacy_supporting_context,
            field_name="command_policy.supporting_context_policy",
            command_name=command_name,
            allow_explicit_override=_command_policy_is_publication_contract(review_contract),
        ),
        "output_policy": output_policy,
    }


def _render_command_policy_submapping(
    payload: dict[str, object] | None,
    *,
    field_order: tuple[str, ...],
) -> dict[str, object] | None:
    if not payload:
        return None
    rendered: dict[str, object] = {}
    for field_name in field_order:
        if field_name not in payload:
            continue
        value = payload[field_name]
        if isinstance(value, list):
            if value:
                rendered[field_name] = value
            continue
        if isinstance(value, bool):
            rendered[field_name] = value
            continue
        if value is not None:
            rendered[field_name] = value
    return rendered or None


def _render_command_policy_payload(
    command_policy: CommandPolicy | dict[str, object] | None,
) -> dict[str, object] | None:
    payload = _command_policy_payload(command_policy)
    if not payload:
        return None

    rendered: dict[str, object] = {"schema_version": int(payload["schema_version"])}
    subject_policy = payload.get("subject_policy")
    if isinstance(subject_policy, dict):
        rendered_subject = _render_command_policy_submapping(
            subject_policy,
            field_order=_COMMAND_POLICY_SUBJECT_FIELD_ORDER,
        )
        if rendered_subject:
            rendered["subject_policy"] = rendered_subject
    supporting_context_policy = payload.get("supporting_context_policy")
    if isinstance(supporting_context_policy, dict):
        rendered_supporting_context = _render_command_policy_submapping(
            supporting_context_policy,
            field_order=_COMMAND_POLICY_SUPPORTING_CONTEXT_FIELD_ORDER,
        )
        if rendered_supporting_context:
            rendered["supporting_context_policy"] = rendered_supporting_context
    output_policy = payload.get("output_policy")
    if isinstance(output_policy, dict):
        rendered_output = _render_command_policy_submapping(
            output_policy,
            field_order=_COMMAND_POLICY_OUTPUT_FIELD_ORDER,
        )
        if rendered_output:
            rendered["output_policy"] = rendered_output
    return rendered


def _parse_command_policy(
    raw: object,
    *,
    command_name: str,
    context_mode: str,
    project_reentry_capable: bool,
    requires: dict[str, object],
    review_contract: ReviewCommandContract | None = None,
    explicit: bool = False,
) -> CommandPolicy:
    if isinstance(raw, CommandPolicy):
        return raw
    try:
        payload = _normalize_command_policy_payload(
            raw,
            command_name=command_name,
            context_mode=context_mode,
            project_reentry_capable=project_reentry_capable,
            requires=requires,
            review_contract=review_contract,
            explicit=explicit,
        )
    except ValueError as exc:
        raise ValueError(f"command-policy for {command_name}: {exc}") from exc

    subject_policy_payload = payload.get("subject_policy")
    supporting_context_payload = payload.get("supporting_context_policy")
    output_policy_payload = payload.get("output_policy")
    return CommandPolicy(
        schema_version=int(payload["schema_version"]),
        subject_policy=(
            CommandSubjectPolicy(**subject_policy_payload) if isinstance(subject_policy_payload, dict) else None
        ),
        supporting_context_policy=(
            CommandSupportingContextPolicy(**supporting_context_payload)
            if isinstance(supporting_context_payload, dict)
            else None
        ),
        output_policy=(
            CommandOutputPolicy(**output_policy_payload) if isinstance(output_policy_payload, dict) else None
        ),
    )


def _parse_bool_field(raw: object, *, field_name: str, command_name: str, default: bool = False) -> bool:
    """Parse a strict YAML boolean and reject legacy compatibility aliases."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    raise ValueError(f"{field_name} for {command_name} must be a boolean")


def _validate_raw_boolean_frontmatter_field(
    frontmatter: str | None,
    *,
    field_name: str,
    command_name: str,
) -> None:
    """Reject legacy boolean spellings before YAML coercion can hide them."""

    raw_value = _raw_scalar_frontmatter_value(frontmatter, field_name=field_name)
    if raw_value is None:
        return
    if raw_value.casefold() in {"true", "false"}:
        return
    raise ValueError(f"{field_name} for {command_name} must be a boolean")


def _validate_raw_nonempty_string_frontmatter_field(
    frontmatter: str | None,
    *,
    field_name: str,
    owner_name: str,
) -> None:
    """Reject explicit blank or null scalar spellings before YAML hides them."""

    raw_value = _raw_scalar_frontmatter_value(frontmatter, field_name=field_name)
    if raw_value is None:
        return
    if raw_value.casefold() not in {"", "null", "~"}:
        return
    raise ValueError(f"{field_name} for {owner_name} must be a non-empty string")


def _validate_raw_command_frontmatter(frontmatter: str | None, *, command_name: str) -> None:
    """Reject legacy raw frontmatter spellings for strict command metadata."""

    _validate_raw_nonempty_string_frontmatter_field(
        frontmatter,
        field_name="context_mode",
        owner_name=command_name,
    )
    _validate_raw_nonempty_string_frontmatter_field(
        frontmatter,
        field_name="agent",
        owner_name=command_name,
    )
    _validate_raw_boolean_frontmatter_field(
        frontmatter,
        field_name="project_reentry_capable",
        command_name=command_name,
    )


def _validate_raw_agent_frontmatter(frontmatter: str | None, *, agent_name: str) -> None:
    """Reject explicit blank or null spellings for defaulted agent metadata."""

    _validate_raw_nonempty_string_frontmatter_field(
        frontmatter,
        field_name="commit_authority",
        owner_name=agent_name,
    )
    for field_name in (
        "surface",
        "role_family",
        "artifact_write_authority",
        "shared_state_authority",
    ):
        _validate_raw_nonempty_string_frontmatter_field(
            frontmatter,
            field_name=field_name,
            owner_name=agent_name,
        )


@lru_cache(maxsize=1)
def _canonical_agent_names(agents_dir: Path) -> frozenset[str]:
    """Return validated built-in agent names from the canonical package tree."""

    return frozenset(load_agents_from_dir(agents_dir))


@lru_cache(maxsize=1)
def _builtin_agent_names() -> frozenset[str]:
    """Return built-in agent names from the packaged canonical agent tree."""

    return frozenset(load_agents_from_dir(_PKG_ROOT / "agents"))


def canonical_agent_names() -> tuple[str, ...]:
    """Return the sorted built-in agent labels accepted by command frontmatter."""

    return tuple(sorted(_canonical_agent_names(AGENTS_DIR)))


def _parse_project_reentry_capable(raw: object, *, command_name: str, context_mode: str) -> bool:
    """Normalize project re-entry metadata and reject invalid command-mode pairings."""
    value = _parse_bool_field(
        raw,
        field_name="project_reentry_capable",
        command_name=command_name,
        default=False,
    )
    if value and context_mode != "project-required":
        raise ValueError(f"project_reentry_capable for {command_name} requires context_mode 'project-required'")
    return value


def _parse_command_agent(raw: object, *, command_name: str) -> str | None:
    """Normalize optional command agent metadata to a canonical skill name."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"agent for {command_name} must be a string")
    value = raw.strip().lower()
    if not value:
        raise ValueError(f"agent for {command_name} must be a non-empty string")
    normalized = canonical_skill_label(value)
    known_agents = frozenset(canonical_agent_names()) | _builtin_agent_names()
    if known_agents and normalized not in known_agents:
        raise ValueError(f"Unknown agent {normalized!r} for {command_name}")
    return normalized


def _review_contract_frontmatter_value(meta: dict[str, object], *, command_name: str) -> object:
    """Return the canonical review-contract frontmatter payload."""

    if REVIEW_CONTRACT_PROMPT_WRAPPER_KEY in meta:
        raise ValueError(
            f"review-contract for {command_name} must use the canonical frontmatter key '{REVIEW_CONTRACT_FRONTMATTER_KEY}'"
        )
    if REVIEW_CONTRACT_FRONTMATTER_KEY not in meta:
        return None
    return {REVIEW_CONTRACT_FRONTMATTER_KEY: meta.get(REVIEW_CONTRACT_FRONTMATTER_KEY)}


def _parse_context_mode(raw: object, *, command_name: str) -> str:
    """Normalize command context_mode frontmatter to a validated string."""
    if raw is None:
        return "project-required"

    if not isinstance(raw, str):
        raise ValueError(f"context_mode for {command_name} must be a string")
    mode = raw.strip().lower()
    if not mode:
        raise ValueError(f"context_mode for {command_name} must be a non-empty string")
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
        raise ValueError(f"commit_authority for {agent_name} must be a non-empty string")
    if authority not in AGENT_COMMIT_AUTHORITIES:
        valid = ", ".join(AGENT_COMMIT_AUTHORITIES)
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
        raise ValueError(f"{field_name} for {agent_name} must be a non-empty string")
    if value not in valid_values:
        valid = ", ".join(valid_values)
        raise ValueError(f"Invalid {field_name} {value!r} for {agent_name}; expected one of: {valid}")
    return value


def render_review_contract_section(review_contract: ReviewCommandContract | None) -> str:
    """Render a model-visible review-contract block for command prompt bodies."""

    if review_contract is None:
        return ""
    return render_review_contract_prompt(review_contract)


def _agent_requirements_payload(
    *,
    tools: list[str],
    commit_authority: str,
    surface: str,
    role_family: str,
    artifact_write_authority: str,
    shared_state_authority: str,
) -> dict[str, object]:
    return {
        "commit_authority": commit_authority,
        "surface": surface,
        "role_family": role_family,
        "artifact_write_authority": artifact_write_authority,
        "shared_state_authority": shared_state_authority,
        "tools": list(tools),
    }


def _normalize_agent_requirements_inputs(
    *,
    tools: list[str],
    commit_authority: str,
    surface: str,
    role_family: str,
    artifact_write_authority: str,
    shared_state_authority: str,
) -> dict[str, object]:
    """Validate and canonicalize public agent-requirements render inputs."""

    owner_name = "rendered agent requirements"
    return _agent_requirements_payload(
        tools=_parse_tools(list(tools), owner_name=owner_name),
        commit_authority=_parse_commit_authority(commit_authority, agent_name=owner_name),
        surface=_parse_agent_metadata_enum(
            surface,
            field_name="surface",
            agent_name=owner_name,
            valid_values=AGENT_SURFACES,
            default="internal",
        ),
        role_family=_parse_agent_metadata_enum(
            role_family,
            field_name="role_family",
            agent_name=owner_name,
            valid_values=AGENT_ROLE_FAMILIES,
            default="analysis",
        ),
        artifact_write_authority=_parse_agent_metadata_enum(
            artifact_write_authority,
            field_name="artifact_write_authority",
            agent_name=owner_name,
            valid_values=AGENT_ARTIFACT_WRITE_AUTHORITIES,
            default="scoped_write",
        ),
        shared_state_authority=_parse_agent_metadata_enum(
            shared_state_authority,
            field_name="shared_state_authority",
            agent_name=owner_name,
            valid_values=AGENT_SHARED_STATE_AUTHORITIES,
            default="return_only",
        ),
    )


def render_agent_requirements_section(
    *,
    tools: list[str],
    commit_authority: str,
    surface: str,
    role_family: str,
    artifact_write_authority: str,
    shared_state_authority: str,
) -> str:
    """Render a model-visible agent-contract block for agent prompt bodies."""

    normalized_payload = _normalize_agent_requirements_inputs(
        tools=tools,
        commit_authority=commit_authority,
        surface=surface,
        role_family=role_family,
        artifact_write_authority=artifact_write_authority,
        shared_state_authority=shared_state_authority,
    )
    return render_model_visible_yaml_section(
        heading="Agent Requirements",
        note=agent_visibility_note(),
        payload=normalized_payload,
    )


def render_agent_visibility_sections_from_frontmatter(frontmatter: str, *, agent_name: str) -> str:
    """Render canonical model-visible agent constraints from raw frontmatter."""

    _validate_raw_agent_frontmatter(frontmatter, agent_name=agent_name)
    meta = _load_frontmatter_mapping(frontmatter, error_prefix=f"Malformed frontmatter for {agent_name}")
    tools = _merge_tool_lists(
        _parse_tools(meta.get("tools"), owner_name=agent_name),
        _parse_tools(meta.get("allowed-tools"), field_name="allowed-tools", owner_name=agent_name),
    )
    return render_agent_requirements_section(
        tools=tools,
        commit_authority=_parse_commit_authority(meta.get("commit_authority"), agent_name=agent_name),
        surface=_parse_agent_metadata_enum(
            meta.get("surface"),
            field_name="surface",
            agent_name=agent_name,
            valid_values=AGENT_SURFACES,
            default="internal",
        ),
        role_family=_parse_agent_metadata_enum(
            meta.get("role_family"),
            field_name="role_family",
            agent_name=agent_name,
            valid_values=AGENT_ROLE_FAMILIES,
            default="analysis",
        ),
        artifact_write_authority=_parse_agent_metadata_enum(
            meta.get("artifact_write_authority"),
            field_name="artifact_write_authority",
            agent_name=agent_name,
            valid_values=AGENT_ARTIFACT_WRITE_AUTHORITIES,
            default="scoped_write",
        ),
        shared_state_authority=_parse_agent_metadata_enum(
            meta.get("shared_state_authority"),
            field_name="shared_state_authority",
            agent_name=agent_name,
            valid_values=AGENT_SHARED_STATE_AUTHORITIES,
            default="return_only",
        ),
    )


def _command_visibility_payload(
    *,
    context_mode: str,
    project_reentry_capable: bool,
    agent: str | None = None,
    allowed_tools: list[str],
    requires: dict[str, object],
    command_policy: CommandPolicy | dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "context_mode": context_mode,
        "project_reentry_capable": project_reentry_capable,
    }
    if agent is not None:
        payload["agent"] = agent
    if allowed_tools:
        payload["allowed_tools"] = list(allowed_tools)
    if requires:
        payload["requires"] = requires
    rendered_command_policy = _render_command_policy_payload(command_policy)
    if rendered_command_policy:
        payload[COMMAND_POLICY_PROMPT_WRAPPER_KEY] = rendered_command_policy
    return payload


def _normalize_command_visibility_inputs(
    *,
    context_mode: str,
    project_reentry_capable: bool,
    agent: str | None = None,
    allowed_tools: list[str],
    requires: dict[str, object],
    command_policy: CommandPolicy | Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate and canonicalize public command-requirements render inputs."""

    command_name = "rendered command requirements"
    normalized_context_mode = _parse_context_mode(context_mode, command_name=command_name)
    normalized_requires = _parse_requires(requires, command_name=command_name)
    normalized_project_reentry_capable = _parse_project_reentry_capable(
        project_reentry_capable,
        command_name=command_name,
        context_mode=normalized_context_mode,
    )
    return _command_visibility_payload(
        context_mode=normalized_context_mode,
        project_reentry_capable=normalized_project_reentry_capable,
        agent=_parse_command_agent(agent, command_name=command_name),
        allowed_tools=_parse_allowed_tools(allowed_tools, command_name=command_name),
        requires=normalized_requires,
        command_policy=_parse_command_policy(
            command_policy,
            command_name=command_name,
            context_mode=normalized_context_mode,
            project_reentry_capable=normalized_project_reentry_capable,
            requires=normalized_requires,
        ),
    )


def render_command_requires_section(
    *,
    context_mode: str,
    project_reentry_capable: bool,
    agent: str | None = None,
    allowed_tools: list[str],
    requires: dict[str, object],
    command_policy: CommandPolicy | Mapping[str, object] | None = None,
) -> str:
    """Render model-visible execution constraints from command frontmatter."""

    normalized_payload = _normalize_command_visibility_inputs(
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        agent=agent,
        allowed_tools=allowed_tools,
        requires=requires,
        command_policy=command_policy,
    )
    return render_model_visible_yaml_section(
        heading="Command Requirements",
        note=command_visibility_note(),
        payload=normalized_payload,
    )


def render_command_visibility_sections(
    *,
    context_mode: str,
    project_reentry_capable: bool,
    agent: str | None = None,
    allowed_tools: list[str],
    requires: dict[str, object],
    command_policy: CommandPolicy | Mapping[str, object] | None = None,
    review_contract: ReviewCommandContract | None,
) -> str:
    """Render model-visible command constraints in canonical prompt order."""

    sections: list[str] = []
    sections.append(
        render_command_requires_section(
            context_mode=context_mode,
            project_reentry_capable=project_reentry_capable,
            agent=agent,
            allowed_tools=allowed_tools,
            requires=requires,
            command_policy=command_policy,
        )
    )

    review_section = render_review_contract_section(review_contract)
    if review_section:
        sections.append(review_section)

    return "\n\n".join(sections)


def render_command_visibility_sections_from_frontmatter(frontmatter: str, *, command_name: str) -> str:
    """Render canonical model-visible command constraints from raw frontmatter."""

    _validate_raw_command_frontmatter(frontmatter, command_name=command_name)
    meta = _load_frontmatter_mapping(frontmatter, error_prefix=f"Malformed frontmatter for {command_name}")
    review_contract_value = _review_contract_frontmatter_value(meta, command_name=command_name)
    command_policy_value, command_policy_explicit = _command_policy_frontmatter_value(meta, command_name=command_name)
    _validate_command_frontmatter_keys(meta, command_name=command_name)

    requires = _parse_requires(meta.get("requires"), command_name=command_name)
    allowed_tools = _parse_allowed_tools(meta.get("allowed-tools"), command_name=command_name)
    agent = _parse_command_agent(meta.get("agent"), command_name=command_name)
    context_mode = _parse_context_mode(meta.get("context_mode"), command_name=command_name)
    project_reentry_capable = _parse_project_reentry_capable(
        meta.get("project_reentry_capable"),
        command_name=command_name,
        context_mode=context_mode,
    )
    review_contract = _parse_review_contract(
        review_contract_value,
        command_name=command_name,
    )
    command_policy = _parse_command_policy(
        command_policy_value,
        command_name=command_name,
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        requires=requires,
        review_contract=review_contract,
        explicit=command_policy_explicit,
    )
    return render_command_visibility_sections(
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        agent=agent,
        allowed_tools=allowed_tools,
        requires=requires,
        command_policy=command_policy,
        review_contract=review_contract,
    )


def _agent_model_content(
    body: str,
    *,
    tools: list[str],
    commit_authority: str,
    surface: str,
    role_family: str,
    artifact_write_authority: str,
    shared_state_authority: str,
) -> str:
    """Return the model-visible agent body, including enforced agent constraints."""

    body = _inline_model_visible_includes(body)
    sections: list[str] = [
        render_agent_requirements_section(
            tools=tools,
            commit_authority=commit_authority,
            surface=surface,
            role_family=role_family,
            artifact_write_authority=artifact_write_authority,
            shared_state_authority=shared_state_authority,
        ),
        skeptical_rigor_guardrails_section(),
    ]
    if body:
        sections.append(body)
    return "\n\n".join(sections)


def _command_model_content(
    body: str,
    review_contract: ReviewCommandContract | None,
    *,
    context_mode: str,
    project_reentry_capable: bool,
    agent: str | None = None,
    allowed_tools: list[str],
    requires: dict[str, object],
    command_policy: CommandPolicy | None = None,
) -> str:
    """Return the model-visible command body, including enforced command constraints."""

    body = _inline_model_visible_includes(body)
    sections: list[str] = []
    visibility_sections = render_command_visibility_sections(
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        agent=agent,
        allowed_tools=allowed_tools,
        requires=requires,
        command_policy=command_policy,
        review_contract=review_contract,
    )
    if visibility_sections:
        sections.append(visibility_sections)
    sections.append(skeptical_rigor_guardrails_section())
    if body:
        sections.append(body)
    return "\n\n".join(sections)


def _parse_review_contract(raw: object, command_name: str) -> ReviewCommandContract | None:
    """Parse review-contract frontmatter through the canonical shared normalizer."""
    try:
        payload = normalize_review_contract_frontmatter_payload(raw)
    except ValueError as exc:
        raise ValueError(f"review-contract for {command_name}: {exc}") from exc

    if not payload:
        return None

    scope_variants_payload = list(payload["scope_variants"])
    if str(payload["review_mode"]) == "publication" and not scope_variants_payload:
        required_evidence = [str(item) for item in payload["required_evidence"]]
        if any("external-artifact review" in item.casefold() for item in required_evidence):
            scope_variants_payload = [
                {
                    "scope": "explicit_artifact",
                    "activation": "explicit external artifact subject was supplied",
                    "relaxed_preflight_checks": [
                        "project_state",
                        "roadmap",
                        "conventions",
                        "research_artifacts",
                        "verification_reports",
                        "manuscript_proof_review",
                    ],
                    "optional_preflight_checks": [
                        "artifact_manifest",
                        "bibliography_audit",
                        "bibliography_audit_clean",
                        "reproducibility_manifest",
                        "reproducibility_ready",
                    ],
                }
            ]

    return ReviewCommandContract(
        review_mode=str(payload["review_mode"]),
        required_outputs=list(payload["required_outputs"]),
        required_evidence=list(payload["required_evidence"]),
        blocking_conditions=list(payload["blocking_conditions"]),
        preflight_checks=list(payload["preflight_checks"]),
        stage_artifacts=list(payload["stage_artifacts"]),
        conditional_requirements=[
            ReviewContractConditionalRequirement(
                when=str(requirement["when"]),
                required_outputs=list(requirement.get("required_outputs", [])),
                required_evidence=list(requirement.get("required_evidence", [])),
                blocking_conditions=list(requirement.get("blocking_conditions", [])),
                preflight_checks=list(requirement.get("preflight_checks", [])),
                blocking_preflight_checks=list(requirement.get("blocking_preflight_checks", [])),
                stage_artifacts=list(requirement.get("stage_artifacts", [])),
            )
            for requirement in payload["conditional_requirements"]
        ],
        scope_variants=[
            ReviewContractScopeVariant(
                scope=str(variant["scope"]),
                activation=str(variant["activation"]),
                relaxed_preflight_checks=list(variant.get("relaxed_preflight_checks", [])),
                optional_preflight_checks=list(variant.get("optional_preflight_checks", [])),
                required_outputs_override=list(variant.get("required_outputs_override", [])),
                required_evidence_override=list(variant.get("required_evidence_override", [])),
                blocking_conditions_override=list(variant.get("blocking_conditions_override", [])),
            )
            for variant in scope_variants_payload
        ],
        required_state=str(payload["required_state"]),
        schema_version=int(payload["schema_version"]),
    )


def _apply_write_paper_external_authoring_registry_overrides(
    path: Path,
    *,
    command_name: str,
    context_mode: str,
    command_policy: CommandPolicy | None,
    review_contract: ReviewCommandContract | None,
) -> tuple[str, CommandPolicy | None, ReviewCommandContract | None]:
    """Project the bounded write-paper external-authoring lane into the canonical runtime surface."""

    canonical_path = (COMMANDS_DIR / "write-paper.md").resolve(strict=False)
    if command_name != "gpd:write-paper" or path.resolve(strict=False) != canonical_path:
        return context_mode, command_policy, review_contract

    existing_subject_policy = command_policy.subject_policy if command_policy is not None else None
    existing_supporting_context = command_policy.supporting_context_policy if command_policy is not None else None
    existing_output_policy = command_policy.output_policy if command_policy is not None else None

    subject_policy = CommandSubjectPolicy(
        subject_kind=(
            existing_subject_policy.subject_kind
            if existing_subject_policy is not None and existing_subject_policy.subject_kind is not None
            else "publication"
        ),
        resolution_mode=(
            existing_subject_policy.resolution_mode
            if existing_subject_policy is not None and existing_subject_policy.resolution_mode is not None
            else "project_manuscript_or_bootstrap"
        ),
        explicit_input_kinds=[_WRITE_PAPER_EXTERNAL_AUTHORING_INPUT_KIND],
        allow_external_subjects=False,
        allow_interactive_without_subject=False,
        supported_roots=(
            list(existing_subject_policy.supported_roots)
            if existing_subject_policy is not None and existing_subject_policy.supported_roots
            else ["paper", "manuscript", "draft"]
        ),
        allowed_suffixes=(
            list(existing_subject_policy.allowed_suffixes)
            if existing_subject_policy is not None
            else []
        ),
        bootstrap_allowed=(
            existing_subject_policy.bootstrap_allowed
            if existing_subject_policy is not None and existing_subject_policy.bootstrap_allowed is not None
            else True
        ),
    )
    supporting_context_policy = CommandSupportingContextPolicy(
        project_context_mode="project-aware",
        project_reentry_mode=(
            existing_supporting_context.project_reentry_mode
            if existing_supporting_context is not None
            and existing_supporting_context.project_reentry_mode is not None
            else "disallowed"
        ),
        required_file_patterns=(
            list(existing_supporting_context.required_file_patterns)
            if existing_supporting_context is not None
            else []
        ),
        optional_file_patterns=(
            list(existing_supporting_context.optional_file_patterns)
            if existing_supporting_context is not None
            else []
        ),
    )
    command_policy = CommandPolicy(
        schema_version=command_policy.schema_version if command_policy is not None else 1,
        subject_policy=subject_policy,
        supporting_context_policy=supporting_context_policy,
        output_policy=existing_output_policy,
    )

    if review_contract is not None:
        existing_scope_variants = list(review_contract.scope_variants)
        if not any(
            str(variant.scope).strip() == _WRITE_PAPER_EXTERNAL_AUTHORING_SCOPE for variant in existing_scope_variants
        ):
            existing_scope_variants.append(
                ReviewContractScopeVariant(
                    scope=_WRITE_PAPER_EXTERNAL_AUTHORING_SCOPE,
                    activation="validated explicit external authoring intake manifest was supplied outside a project",
                    relaxed_preflight_checks=list(_WRITE_PAPER_EXTERNAL_AUTHORING_RELAXED_PREFLIGHT_CHECKS),
                    optional_preflight_checks=list(_WRITE_PAPER_EXTERNAL_AUTHORING_OPTIONAL_PREFLIGHT_CHECKS),
                    required_outputs_override=list(_WRITE_PAPER_EXTERNAL_AUTHORING_REQUIRED_OUTPUTS),
                    required_evidence_override=list(_WRITE_PAPER_EXTERNAL_AUTHORING_REQUIRED_EVIDENCE),
                    blocking_conditions_override=list(_WRITE_PAPER_EXTERNAL_AUTHORING_BLOCKING_CONDITIONS),
                )
            )
        review_contract = dataclasses.replace(review_contract, scope_variants=existing_scope_variants)

    return "project-aware", command_policy, review_contract


def _parse_spawn_contracts(content: str, *, owner_name: str) -> tuple[dict[str, object], ...]:
    """Parse canonical spawn-contract blocks from rendered markdown content."""

    contracts: list[dict[str, object]] = []
    for match in _SPAWN_CONTRACT_BLOCK_RE.finditer(content):
        block = textwrap.dedent(match.group("body")).strip()
        if not block:
            raise ValueError(f"spawn-contract for {owner_name}: empty block")
        parsed = _parse_spawn_contract_block(block, owner_name=owner_name)
        contracts.append(parsed)
    return tuple(contracts)


def _parse_spawn_contract_block(block: str, *, owner_name: str) -> dict[str, object]:
    """Parse one spawn-contract block without requiring strict YAML quoting."""

    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    contract: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "write_scope:":
            index += 1
            write_scope: dict[str, object] = {}
            while index < len(lines) and lines[index].startswith("  "):
                nested = lines[index].strip()
                if nested.startswith("mode:"):
                    write_scope["mode"] = nested.split(":", 1)[1].strip()
                    index += 1
                    continue
                if nested == "allowed_paths:":
                    index += 1
                    allowed_paths: list[str] = []
                    while index < len(lines) and lines[index].startswith("    - "):
                        allowed_paths.append(lines[index].split("- ", 1)[1].strip())
                        index += 1
                    write_scope["allowed_paths"] = allowed_paths
                    continue
                raise ValueError(f"spawn-contract for {owner_name}: unexpected write_scope field {nested!r}")
            contract["write_scope"] = write_scope
            continue
        if line == "expected_artifacts:":
            index += 1
            expected_artifacts: list[str] = []
            while index < len(lines) and lines[index].startswith("  - "):
                expected_artifacts.append(lines[index].split("- ", 1)[1].strip())
                index += 1
            contract["expected_artifacts"] = expected_artifacts
            continue
        if line.startswith("shared_state_policy:"):
            contract["shared_state_policy"] = line.split(":", 1)[1].strip()
            index += 1
            continue
        raise ValueError(f"spawn-contract for {owner_name}: unexpected line {line!r}")

    if "write_scope" not in contract:
        raise ValueError(f"spawn-contract for {owner_name}: missing write_scope")
    if "expected_artifacts" not in contract:
        raise ValueError(f"spawn-contract for {owner_name}: missing expected_artifacts")
    if "shared_state_policy" not in contract:
        raise ValueError(f"spawn-contract for {owner_name}: missing shared_state_policy")
    return contract


def _load_command_staged_loading(path: Path, *, allowed_tools: list[str]) -> WorkflowStageManifest | None:
    """Load staged-loading metadata for a command from its workflow sidecar."""

    manifest_path = resolve_workflow_stage_manifest_path(path.stem)
    if not manifest_path.is_file():
        return None
    canonical_manifest_path = (SPECS_DIR / "workflows" / f"{path.stem}-stage-manifest.json").resolve(strict=False)
    canonical_command_path = (_PKG_ROOT / "commands" / path.name).resolve(strict=False)
    if (
        path.resolve(strict=False) != canonical_command_path
        and manifest_path.resolve(strict=False) == canonical_manifest_path
    ):
        return None
    return load_workflow_stage_manifest_from_path(
        manifest_path,
        expected_workflow_id=path.stem,
        allowed_tools=allowed_tools,
        known_init_fields=known_init_fields_for_workflow(path.stem),
    )


def _parse_agent_file(path: Path, source: str) -> AgentDef:
    """Parse a single agent .md file into an AgentDef."""
    text = path.read_text(encoding="utf-8")
    raw_frontmatter, _unused_body = _frontmatter_parts(text)
    try:
        meta, body = _parse_frontmatter(text)
    except ValueError as exc:
        raise ValueError(f"Invalid frontmatter in {path}: {exc}") from exc
    _validate_raw_agent_frontmatter(raw_frontmatter, agent_name=path.stem)
    agent_name = _parse_frontmatter_string_field(
        meta.get("name"),
        field_name="name",
        owner_name=path.stem,
        required=True,
    )
    _validate_agent_frontmatter_keys(meta, agent_name=agent_name)
    tools = _merge_tool_lists(
        _parse_tools(meta.get("tools"), owner_name=agent_name),
        _parse_tools(meta.get("allowed-tools"), field_name="allowed-tools", owner_name=agent_name),
    )
    description = _parse_frontmatter_string_field(
        meta.get("description"),
        field_name="description",
        owner_name=agent_name,
    )
    commit_authority = _parse_commit_authority(meta.get("commit_authority"), agent_name=agent_name)
    surface = _parse_agent_metadata_enum(
        meta.get("surface"),
        field_name="surface",
        agent_name=agent_name,
        valid_values=AGENT_SURFACES,
        default="internal",
    )
    role_family = _parse_agent_metadata_enum(
        meta.get("role_family"),
        field_name="role_family",
        agent_name=agent_name,
        valid_values=AGENT_ROLE_FAMILIES,
        default="analysis",
    )
    artifact_write_authority = _parse_agent_metadata_enum(
        meta.get("artifact_write_authority"),
        field_name="artifact_write_authority",
        agent_name=agent_name,
        valid_values=AGENT_ARTIFACT_WRITE_AUTHORITIES,
        default="scoped_write",
    )
    shared_state_authority = _parse_agent_metadata_enum(
        meta.get("shared_state_authority"),
        field_name="shared_state_authority",
        agent_name=agent_name,
        valid_values=AGENT_SHARED_STATE_AUTHORITIES,
        default="return_only",
    )
    color = _parse_frontmatter_string_field(
        meta.get("color"),
        field_name="color",
        owner_name=agent_name,
    )
    system_prompt = _agent_model_content(
        body.strip(),
        tools=tools,
        commit_authority=commit_authority,
        surface=surface,
        role_family=role_family,
        artifact_write_authority=artifact_write_authority,
        shared_state_authority=shared_state_authority,
    )
    return AgentDef(
        name=agent_name,
        description=description,
        system_prompt=system_prompt,
        tools=tools,
        commit_authority=commit_authority,
        surface=surface,
        role_family=role_family,
        artifact_write_authority=artifact_write_authority,
        shared_state_authority=shared_state_authority,
        color=color,
        path=str(path),
        source=source,
    )


def _parse_command_file(path: Path, source: str) -> CommandDef:
    """Parse a single command .md file into a CommandDef."""
    text = path.read_text(encoding="utf-8")
    raw_frontmatter, _unused_body = _frontmatter_parts(text)
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
    _validate_raw_command_frontmatter(raw_frontmatter, command_name=command_name)
    try:
        command_policy_value, command_policy_explicit = _command_policy_frontmatter_value(
            meta,
            command_name=command_name,
        )
    except ValueError as exc:
        raise ValueError(f"Invalid command-policy in {path}: {exc}") from exc

    try:
        review_contract = _parse_review_contract(
            _review_contract_frontmatter_value(meta, command_name=command_name),
            command_name,
        )
    except ValueError as exc:
        raise ValueError(f"Invalid review-contract in {path}: {exc}") from exc
    _validate_command_frontmatter_keys(meta, command_name=command_name)
    requires = _parse_requires(meta.get("requires"), command_name=command_name)
    allowed_tools = _parse_allowed_tools(meta.get("allowed-tools"), command_name=command_name)
    agent = _parse_command_agent(meta.get("agent"), command_name=command_name)

    body = body.strip()
    context_mode = _parse_context_mode(meta.get("context_mode"), command_name=command_name)
    project_reentry_capable = _parse_project_reentry_capable(
        meta.get("project_reentry_capable"),
        command_name=command_name,
        context_mode=context_mode,
    )
    try:
        command_policy = _parse_command_policy(
            command_policy_value,
            command_name=command_name,
            context_mode=context_mode,
            project_reentry_capable=project_reentry_capable,
            requires=requires,
            review_contract=review_contract,
            explicit=command_policy_explicit,
        )
    except ValueError as exc:
        raise ValueError(f"Invalid command-policy in {path}: {exc}") from exc
    context_mode, command_policy, review_contract = _apply_write_paper_external_authoring_registry_overrides(
        path,
        command_name=command_name,
        context_mode=context_mode,
        command_policy=command_policy,
        review_contract=review_contract,
    )
    staged_loading = _load_command_staged_loading(path, allowed_tools=allowed_tools)
    content = _command_model_content(
        body,
        review_contract,
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        agent=agent,
        allowed_tools=allowed_tools,
        requires=requires,
        command_policy=command_policy,
    )
    spawn_contracts = _parse_spawn_contracts(content, owner_name=command_name)

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
        agent=agent,
        context_mode=context_mode,
        project_reentry_capable=project_reentry_capable,
        command_policy=command_policy,
        requires=requires,
        allowed_tools=allowed_tools,
        review_contract=review_contract,
        staged_loading=staged_loading,
        spawn_contracts=spawn_contracts,
        content=content,
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


def _validate_agent_name(path: Path, agent: AgentDef) -> None:
    """Reject agent metadata that drifts from its registry filename."""

    expected_name = path.stem
    if agent.name != expected_name:
        raise ValueError(
            f"Agent frontmatter name {agent.name!r} does not match file stem {path.stem!r}; expected {expected_name!r}"
        )


def load_agents_from_dir(agents_dir: Path) -> dict[str, AgentDef]:
    """Parse agent definitions from an arbitrary agents directory."""
    result: dict[str, AgentDef] = {}
    if not agents_dir.is_dir():
        return result

    for path in sorted(agents_dir.glob("*.md")):
        agent = _parse_agent_file(path, source="agents")
        _validate_agent_name(path, agent)
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
    "gpd-autonomous": "execution",
    "gpd-digest-knowledge": "research",
    "gpd-execute": "execution",
    "gpd-plan-checker": "verification",
    "gpd-plan": "planning",
    "gpd-verify": "verification",
    "gpd-debug": "debugging",
    "gpd-new": "project",
    "gpd-write": "paper",
    "gpd-peer-review": "paper",
    "gpd-review-knowledge": "research",
    "gpd-review": "paper",
    "gpd-paper": "paper",
    "gpd-literature": "research",
    "gpd-research": "research",
    "gpd-discover": "research",
    "gpd-explain": "help",
    "gpd-start": "help",
    "gpd-tour": "help",
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
    "gpd-tangent": "planning",
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
VALID_SKILL_CATEGORIES: tuple[str, ...] = tuple(sorted({*set(_SKILL_CATEGORY_MAP.values()), "other"}))


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


def skill_categories() -> tuple[str, ...]:
    """Return the canonical skill-category enum published to shared callers."""
    return VALID_SKILL_CATEGORIES


def _canonical_skill_name_for_command(command: CommandDef) -> str:
    """Project a command registry entry into the canonical gpd-* skill namespace."""
    return command.name.replace("gpd:", "gpd-", 1)


def _discover_skills(commands: dict[str, CommandDef], agents: dict[str, AgentDef]) -> dict[str, SkillDef]:
    """Build the canonical registry/MCP skill index from primary commands and agents."""
    result: dict[str, SkillDef] = {}

    for registry_name, command in sorted(commands.items()):
        if command.source != "commands":
            continue
        skill_name = _canonical_skill_name_for_command(command)
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
            spawn_contracts=command.spawn_contracts,
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


def _format_command_name(command: CommandDef | str, *, name_format: CommandNameFormat) -> str:
    """Render a command registry entry in the requested public name shape."""
    if name_format not in {"slug", "label"}:
        raise ValueError("name_format must be 'slug' or 'label'")

    if isinstance(command, CommandDef):
        slug = command_slug_from_label(command.name)
        label = command.name
    else:
        slug = command_slug_from_label(command) or command
        label = canonical_command_label(command)
    return slug if name_format == "slug" else label


def list_commands(*, name_format: CommandNameFormat = "slug") -> list[str]:
    """Return sorted command names.

    Defaults to registry slugs for historical compatibility. Pass
    ``name_format="label"`` to receive public ``gpd:<slug>`` command labels.
    """
    return sorted(_format_command_name(command, name_format=name_format) for command in _cache.commands().values())


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


def list_review_commands(*, name_format: CommandNameFormat = "label") -> list[str]:
    """Return sorted review-contract command names.

    Defaults to public ``gpd:<slug>`` labels for historical compatibility. Pass
    ``name_format="slug"`` to align with ``list_commands()``'s default registry
    key shape.
    """
    return sorted(
        _format_command_name(command, name_format=name_format)
        for command in _cache.commands().values()
        if command.review_contract is not None
    )


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
    _canonical_agent_names.cache_clear()
    _builtin_agent_names.cache_clear()
    invalidate_workflow_stage_manifest_cache()


__all__ = [
    "AGENTS_DIR",
    "AgentDef",
    "COMMANDS_DIR",
    "LOCAL_CLI_BRIDGE_WORKFLOW_EXEMPT_COMMANDS",
    "CommandDef",
    "CommandOutputPolicy",
    "CommandPolicy",
    "CommandSubjectPolicy",
    "CommandSupportingContextPolicy",
    "ReviewContractConditionalRequirement",
    "ReviewContractScopeVariant",
    "ReviewCommandContract",
    "SkillDef",
    "SPECS_DIR",
    "AGENT_ARTIFACT_WRITE_AUTHORITIES",
    "AGENT_COMMIT_AUTHORITIES",
    "AGENT_ROLE_FAMILIES",
    "AGENT_SHARED_STATE_AUTHORITIES",
    "AGENT_SURFACES",
    "VALID_CONTEXT_MODES",
    "canonical_agent_names",
    "get_agent",
    "get_command",
    "get_skill",
    "invalidate_cache",
    "load_agents_from_dir",
    "list_agents",
    "list_commands",
    "list_review_commands",
    "list_skills",
    "render_agent_visibility_sections_from_frontmatter",
    "render_agent_requirements_section",
    "render_command_visibility_sections",
    "render_command_visibility_sections_from_frontmatter",
    "render_review_contract_section",
]
