"""Private machine-local Research Persona foundation.

This module owns only the strict data model and storage primitives for the
research-persona substrate. Runtime wiring, CLI commands, and generated prompt
integration belong in later phases.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from gpd.core.constants import ENV_DATA_DIR, HOME_DATA_DIR_NAME
from gpd.core.utils import atomic_write, file_lock, safe_read_file

__all__ = [
    "RESEARCH_PERSONA_CAPSULE_ROLE_VALUES",
    "RESEARCH_PERSONA_CATEGORY_VALUES",
    "RESEARCH_PERSONA_CONFIDENCE_VALUES",
    "RESEARCH_PERSONA_PATCH_OPERATION_VALUES",
    "RESEARCH_PERSONA_PRIVACY_VALUES",
    "RESEARCH_PERSONA_PROJECTION_PURPOSE_VALUES",
    "RESEARCH_PERSONA_SOURCE_KIND_VALUES",
    "RESEARCH_PERSONA_STORE_DIR_NAME",
    "ResearchPersona",
    "ResearchPersonaAxis",
    "ResearchPersonaCapsule",
    "ResearchPersonaError",
    "ResearchPersonaEvidence",
    "ResearchPersonaFact",
    "ResearchPersonaHistoryEvent",
    "ResearchPersonaPatch",
    "ResearchPersonaPatchOperation",
    "ResearchPersonaTombstone",
    "ResearchPersonaValidationResult",
    "append_research_persona_history",
    "append_research_persona_tombstone",
    "apply_research_persona_patch",
    "build_research_persona_capsule",
    "load_research_persona",
    "parse_research_persona_data_strict",
    "project_research_persona",
    "research_persona_path",
    "research_persona_root",
    "save_research_persona",
    "validate_research_persona",
]


logger = logging.getLogger(__name__)

RESEARCH_PERSONA_SCHEMA_VERSION = 1
RESEARCH_PERSONA_STORE_DIR_NAME = "research-persona"
RESEARCH_PERSONA_PROFILE_FILENAME = "profile.json"
RESEARCH_PERSONA_HISTORY_DIR_NAME = "history"
RESEARCH_PERSONA_TOMBSTONES_DIR_NAME = "tombstones"
RESEARCH_PERSONA_LEDGER_FILENAME = "events.jsonl"

RESEARCH_PERSONA_CONFIDENCE_VALUES: tuple[str, ...] = (
    "confirmed",
    "inferred",
    "stale",
    "disputed",
)
RESEARCH_PERSONA_CATEGORY_VALUES: tuple[str, ...] = (
    "standing_preference",
    "negative_preference",
    "tool",
    "research_area",
    "paper",
    "collaborator",
    "reference",
    "expertise",
    "workstyle",
    "scientific_taste",
    "contact",
    "identity",
    "private_paper",
    "taste",
)
RESEARCH_PERSONA_PRIVACY_VALUES: tuple[str, ...] = (
    "session_only",
    "private_local",
    "project_private",
    "safe_to_share",
    "never_prompt",
)
RESEARCH_PERSONA_SOURCE_KIND_VALUES: tuple[str, ...] = (
    "user_statement",
    "interview",
    "project_scan",
    "paper_import",
    "bibtex_import",
    "repo_scan",
    "manual_patch",
    "system_default",
)
RESEARCH_PERSONA_CAPSULE_ROLE_VALUES: tuple[str, ...] = (
    "planner",
    "executor",
    "verifier",
    "paper_writer",
    "literature",
    "recovery",
    "explainer",
    "doppelganger",
    "taste",
)
RESEARCH_PERSONA_PATCH_OPERATION_VALUES: tuple[str, ...] = (
    "add",
    "update",
    "remove",
    "add_fact",
    "upsert_fact",
    "replace_fact",
    "remove_fact",
    "delete_fact",
    "tombstone_fact",
    "add_axis",
    "upsert_axis",
    "replace_axis",
    "remove_axis",
    "delete_axis",
    "append_list",
    "remove_list_item",
    "set_list",
)
RESEARCH_PERSONA_PROJECTION_PURPOSE_VALUES: tuple[str, ...] = (
    "session",
    "local",
    "project_private",
    "prompt",
    "public",
)
RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS: tuple[str, ...] = (
    "standing_preferences",
    "negative_preferences",
    "tools",
    "research_areas",
    "papers",
    "collaborators",
    "references",
    "expertise",
    "workstyle",
    "scientific_taste",
)

_PROMPT_SAFE_STRING_LIST_FIELDS: tuple[str, ...] = (
    "standing_preferences",
    "negative_preferences",
    "tools",
    "research_areas",
    "expertise",
    "workstyle",
    "scientific_taste",
)
_PROJECT_PRIVATE_STRING_LIST_FIELDS: tuple[str, ...] = RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS
_SENSITIVE_PROMPT_CATEGORIES = {
    "contact",
    "contacts",
    "identity",
    "collaborator",
    "collaborators",
    "private_paper",
    "private_papers",
}

ResearchPersonaConfidence = Literal[*RESEARCH_PERSONA_CONFIDENCE_VALUES]
ResearchPersonaCategory = Literal[*RESEARCH_PERSONA_CATEGORY_VALUES]
ResearchPersonaPrivacy = Literal[*RESEARCH_PERSONA_PRIVACY_VALUES]
ResearchPersonaSourceKind = Literal[*RESEARCH_PERSONA_SOURCE_KIND_VALUES]
ResearchPersonaCapsuleRole = Literal[*RESEARCH_PERSONA_CAPSULE_ROLE_VALUES]
ResearchPersonaPatchOperationKind = Literal[*RESEARCH_PERSONA_PATCH_OPERATION_VALUES]
ResearchPersonaProjectionPurpose = Literal[*RESEARCH_PERSONA_PROJECTION_PURPOSE_VALUES]
ResearchPersonaStringListField = Literal[*RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS]


class ResearchPersonaError(ValueError):
    """Raised when research-persona data is structurally invalid."""


class _MutablePersonaModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")


class _FrozenPersonaModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _schema_version(value: object) -> int:
    if type(value) is not int or value != RESEARCH_PERSONA_SCHEMA_VERSION:
        raise ValueError("schema_version must be the integer 1")
    return value


def _required_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    return text


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("must be a string or null")
    text = value.strip()
    return text or None


def _strict_bool(value: object) -> bool:
    if type(value) is bool:
        return value
    raise ValueError("must be a boolean")


def _literal_choice(value: object, choices: tuple[str, ...]) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    for choice in choices:
        if text.casefold() == choice.casefold():
            return choice
    return text


def _strict_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("must be a list of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("must contain only strings")
        text = item.strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _literal_choice_list(value: object, choices: tuple[str, ...]) -> list[str]:
    normalized = _strict_string_list(value)
    canonicalized: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        choice = _literal_choice(item, choices)
        if not isinstance(choice, str) or choice not in choices:
            raise ValueError("must contain only supported literal values")
        if choice in seen:
            continue
        seen.add(choice)
        canonicalized.append(choice)
    return canonicalized


def _strict_model_list(value: object) -> object:
    if not isinstance(value, list):
        raise ValueError("must be a list")
    return value


def _strict_dict_list(value: object) -> object:
    if not isinstance(value, list):
        raise ValueError("must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("must contain only objects")
    return value


def _format_pydantic_errors(exc: PydanticValidationError) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "value"
        message = str(error.get("msg", "validation failed")).strip() or "validation failed"
        input_value = error.get("input")
        if message == "Field required":
            formatted = f"{location} is required"
        elif "valid dictionary" in message.lower():
            formatted = f"{location} must be an object, not {type(input_value).__name__}"
        elif message.startswith("Value error, "):
            formatted = f"{location} {message.removeprefix('Value error, ')}"
        else:
            formatted = f"{location}: {message}"
        if formatted in seen:
            continue
        seen.add(formatted)
        messages.append(formatted)
    return messages or [str(exc)]


def _normalize_projection_purpose(purpose: str) -> ResearchPersonaProjectionPurpose:
    aliases = {
        "project": "project_private",
        "private_project": "project_private",
        "capsule": "prompt",
        "prompt_capsule": "prompt",
        "share": "public",
        "safe_to_share": "public",
    }
    normalized = aliases.get(purpose.strip().casefold(), purpose.strip().casefold())
    if normalized not in RESEARCH_PERSONA_PROJECTION_PURPOSE_VALUES:
        choices = ", ".join(RESEARCH_PERSONA_PROJECTION_PURPOSE_VALUES)
        raise ResearchPersonaError(f"purpose must be one of: {choices}")
    return normalized  # type: ignore[return-value]


def _privacy_allowed_for_purpose(privacy: str, purpose: str) -> bool:
    if privacy == "never_prompt":
        return False
    if purpose == "session":
        return privacy in {"session_only", "private_local", "project_private", "safe_to_share"}
    if purpose == "local":
        return privacy in {"private_local", "project_private", "safe_to_share"}
    if purpose == "project_private":
        return privacy in {"project_private", "safe_to_share"}
    return privacy == "safe_to_share"


def _project_fact(fact: ResearchPersonaFact, *, purpose: str) -> dict[str, object] | None:
    if not _privacy_allowed_for_purpose(fact.privacy, purpose):
        return None
    if purpose in {"prompt", "public"} and fact.privacy != "safe_to_share":
        return None
    if purpose in {"prompt", "public"} and fact.category.casefold() in _SENSITIVE_PROMPT_CATEGORIES:
        if fact.privacy != "safe_to_share":
            return None

    projected: dict[str, object] = {
        "id": fact.id,
        "category": fact.category,
        "value": fact.value,
        "confidence": fact.confidence,
        "privacy": fact.privacy,
    }
    if fact.evidence_refs:
        projected["evidence_refs"] = list(fact.evidence_refs)
    if fact.last_confirmed_at is not None:
        projected["last_confirmed_at"] = fact.last_confirmed_at
    if fact.expires_at is not None:
        projected["expires_at"] = fact.expires_at
    return projected


def _project_axis(axis: ResearchPersonaAxis, *, purpose: str) -> dict[str, object] | None:
    if not _privacy_allowed_for_purpose(axis.privacy, purpose):
        return None
    projected: dict[str, object] = {
        "id": axis.id,
        "confidence": axis.confidence,
        "privacy": axis.privacy,
    }
    if axis.name is not None:
        projected["name"] = axis.name
    if axis.value is not None:
        projected["value"] = axis.value
    if axis.fact_ids:
        projected["fact_ids"] = list(axis.fact_ids)
    if axis.evidence_refs:
        projected["evidence_refs"] = list(axis.evidence_refs)
    return projected


def _projection_list_fields(purpose: str) -> tuple[str, ...]:
    if purpose in {"prompt", "public"}:
        return _PROMPT_SAFE_STRING_LIST_FIELDS
    if purpose == "project_private":
        return _PROJECT_PRIVATE_STRING_LIST_FIELDS
    return RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS


def _data_root(data_root: Path | None = None) -> Path:
    if data_root is not None:
        return data_root.expanduser()
    env_dir = os.environ.get(ENV_DATA_DIR, "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / HOME_DATA_DIR_NAME


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "posix":
        return
    try:
        path.chmod(0o700)
    except OSError:
        logger.warning("research persona directory at %s: could not enforce 0o700 permissions", path)


def _ensure_private_file(path: Path) -> None:
    if os.name != "posix":
        return
    try:
        path.chmod(0o600)
    except OSError:
        logger.warning("research persona file at %s: could not enforce 0o600 permissions", path)


def _ensure_store_dirs(root: Path) -> None:
    _ensure_private_dir(root)
    _ensure_private_dir(root / RESEARCH_PERSONA_HISTORY_DIR_NAME)
    _ensure_private_dir(root / RESEARCH_PERSONA_TOMBSTONES_DIR_NAME)


def _jsonl_append(path: Path, payload_json: str) -> Path:
    _ensure_private_dir(path.parent)
    with file_lock(path):
        existing = safe_read_file(path) or ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        atomic_write(path, existing + payload_json + "\n")
    _ensure_private_file(path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    if lock_path.exists():
        _ensure_private_file(lock_path)
    return path


class ResearchPersonaEvidence(_MutablePersonaModel):
    """One structured provenance item attached to a persona fact or patch."""

    id: str | None = None
    source_kind: ResearchPersonaSourceKind = "manual_patch"
    summary: str | None = None
    locator: str | None = None
    recorded_at: str | None = None

    @field_validator("id", "summary", "locator", "recorded_at", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _optional_string(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_SOURCE_KIND_VALUES)


class ResearchPersonaFact(_MutablePersonaModel):
    """One governed research-persona fact."""

    id: str
    category: ResearchPersonaCategory
    value: str
    confidence: ResearchPersonaConfidence = "inferred"
    privacy: ResearchPersonaPrivacy = "private_local"
    sources: list[ResearchPersonaSourceKind] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    last_confirmed_at: str | None = None
    expires_at: str | None = None

    @field_validator("id", "value", mode="before")
    @classmethod
    def _normalize_required_text(cls, value: object) -> str:
        return _required_string(value)

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_CATEGORY_VALUES)

    @field_validator("last_confirmed_at", "expires_at", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _optional_string(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_CONFIDENCE_VALUES)

    @field_validator("privacy", mode="before")
    @classmethod
    def _normalize_privacy(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_PRIVACY_VALUES)

    @field_validator("sources", mode="before")
    @classmethod
    def _normalize_sources(cls, value: object) -> list[str]:
        return _literal_choice_list(value, RESEARCH_PERSONA_SOURCE_KIND_VALUES)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _normalize_evidence_refs(cls, value: object) -> list[str]:
        return _strict_string_list(value)


class ResearchPersonaAxis(_MutablePersonaModel):
    """A named preference or behavior axis backed by fact identifiers."""

    id: str
    name: str | None = None
    value: float | None = None
    confidence: ResearchPersonaConfidence = "inferred"
    privacy: ResearchPersonaPrivacy = "private_local"
    fact_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def _normalize_id(cls, value: object) -> str:
        return _required_string(value)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _optional_string(value)

    @field_validator("value", mode="before")
    @classmethod
    def _normalize_value(cls, value: object) -> float | None:
        if value is None:
            return None
        if type(value) is bool or not isinstance(value, (int, float)):
            raise ValueError("must be a number between -1 and 1")
        normalized = float(value)
        if normalized < -1.0 or normalized > 1.0:
            raise ValueError("must be between -1 and 1")
        return normalized

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_CONFIDENCE_VALUES)

    @field_validator("privacy", mode="before")
    @classmethod
    def _normalize_privacy(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_PRIVACY_VALUES)

    @field_validator("fact_ids", "evidence_refs", mode="before")
    @classmethod
    def _normalize_string_lists(cls, value: object) -> list[str]:
        return _strict_string_list(value)


class ResearchPersona(_MutablePersonaModel):
    """Canonical private research-persona snapshot."""

    schema_version: int = RESEARCH_PERSONA_SCHEMA_VERSION
    facts: list[ResearchPersonaFact] = Field(default_factory=list)
    axes: list[ResearchPersonaAxis] = Field(default_factory=list)
    standing_preferences: list[str] = Field(default_factory=list)
    negative_preferences: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    research_areas: list[str] = Field(default_factory=list)
    papers: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    expertise: list[str] = Field(default_factory=list)
    workstyle: list[str] = Field(default_factory=list)
    scientific_taste: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        return _schema_version(value)

    @field_validator("facts", "axes", mode="before")
    @classmethod
    def _normalize_model_lists(cls, value: object) -> object:
        return _strict_model_list(value)

    @field_validator(*RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS, mode="before")
    @classmethod
    def _normalize_top_level_string_lists(cls, value: object) -> list[str]:
        return _strict_string_list(value)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> ResearchPersona:
        fact_ids: set[str] = set()
        duplicate_fact_ids: list[str] = []
        for fact in self.facts:
            if fact.id in fact_ids:
                duplicate_fact_ids.append(fact.id)
            fact_ids.add(fact.id)
        if duplicate_fact_ids:
            raise ValueError("duplicate fact ids not allowed: " + ", ".join(sorted(set(duplicate_fact_ids))))

        axis_ids: set[str] = set()
        duplicate_axis_ids: list[str] = []
        for axis in self.axes:
            if axis.id in axis_ids:
                duplicate_axis_ids.append(axis.id)
            axis_ids.add(axis.id)
        if duplicate_axis_ids:
            raise ValueError("duplicate axis ids not allowed: " + ", ".join(sorted(set(duplicate_axis_ids))))
        return self


class ResearchPersonaTombstone(_MutablePersonaModel):
    """Append-only deletion marker for a persona fact."""

    schema_version: int = RESEARCH_PERSONA_SCHEMA_VERSION
    fact_id: str
    reason: str | None = None
    source_kind: ResearchPersonaSourceKind = "manual_patch"
    created_at: str | None = None
    tombstoned_at: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        return _schema_version(value)

    @field_validator("fact_id", mode="before")
    @classmethod
    def _normalize_fact_id(cls, value: object) -> str:
        return _required_string(value)

    @field_validator("reason", "created_at", "tombstoned_at", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _optional_string(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_SOURCE_KIND_VALUES)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _normalize_evidence_refs(cls, value: object) -> list[str]:
        return _strict_string_list(value)


class ResearchPersonaPatchOperation(_MutablePersonaModel):
    """One small, typed mutation against a persona snapshot."""

    op: ResearchPersonaPatchOperationKind = Field(validation_alias=AliasChoices("op", "operation"))
    path: str | None = None
    fact: ResearchPersonaFact | None = None
    fact_id: str | None = None
    axis: ResearchPersonaAxis | None = None
    axis_id: str | None = None
    list_name: ResearchPersonaStringListField | None = None
    value: object | None = None
    values: list[str] = Field(default_factory=list)
    tombstone: ResearchPersonaTombstone | None = None
    reason: str | None = None

    @field_validator("op", mode="before")
    @classmethod
    def _normalize_op(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_PATCH_OPERATION_VALUES)

    @field_validator("path", "fact_id", "axis_id", "reason", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _optional_string(value)

    @field_validator("list_name", mode="before")
    @classmethod
    def _normalize_list_name(cls, value: object) -> object:
        if value is None:
            return None
        return _literal_choice(value, RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS)

    @field_validator("values", mode="before")
    @classmethod
    def _normalize_values(cls, value: object) -> list[str]:
        return _strict_string_list(value)

    @model_validator(mode="after")
    def _validate_operation_shape(self) -> ResearchPersonaPatchOperation:
        if self.tombstone is not None and self.fact_id is None:
            self.fact_id = self.tombstone.fact_id

        if self.op in {"add", "update", "remove"} and self.path is None:
            raise ValueError(f"{self.op} requires path")
        if self.op in {"add", "update"} and self.value is None:
            raise ValueError(f"{self.op} requires value")
        if self.op in {"add_fact", "upsert_fact", "replace_fact"} and self.fact is None:
            raise ValueError(f"{self.op} requires fact")
        if self.op in {"remove_fact", "delete_fact", "tombstone_fact"} and self.fact_id is None:
            raise ValueError(f"{self.op} requires fact_id")
        if self.op in {"add_axis", "upsert_axis", "replace_axis"} and self.axis is None:
            raise ValueError(f"{self.op} requires axis")
        if self.op in {"remove_axis", "delete_axis"} and self.axis_id is None:
            raise ValueError(f"{self.op} requires axis_id")
        if self.op in {"append_list", "remove_list_item", "set_list"} and self.list_name is None:
            raise ValueError(f"{self.op} requires list_name")
        if self.op in {"append_list", "remove_list_item"} and not self.values and self.value is None:
            raise ValueError(f"{self.op} requires value or values")
        return self


class ResearchPersonaPatch(_MutablePersonaModel):
    """A strict collection of persona patch operations."""

    schema_version: int = RESEARCH_PERSONA_SCHEMA_VERSION
    operations: list[ResearchPersonaPatchOperation] = Field(default_factory=list)
    tombstones: list[ResearchPersonaTombstone] = Field(default_factory=list)
    source_kind: ResearchPersonaSourceKind = "manual_patch"
    reason: str | None = None
    evidence: list[ResearchPersonaEvidence] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        return _schema_version(value)

    @field_validator("operations", "tombstones", "evidence", mode="before")
    @classmethod
    def _normalize_model_lists(cls, value: object) -> object:
        return _strict_model_list(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_SOURCE_KIND_VALUES)

    @field_validator("reason", mode="before")
    @classmethod
    def _normalize_reason(cls, value: object) -> str | None:
        return _optional_string(value)


class ResearchPersonaHistoryEvent(_MutablePersonaModel):
    """Append-only audit event for persona changes."""

    schema_version: int = RESEARCH_PERSONA_SCHEMA_VERSION
    event_id: str | None = None
    event_type: str
    summary: str | None = None
    source_kind: ResearchPersonaSourceKind = "manual_patch"
    created_at: str | None = None
    recorded_at: str | None = None
    actor: str | None = None
    patch: ResearchPersonaPatch | None = None
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        return _schema_version(value)

    @field_validator("event_type", mode="before")
    @classmethod
    def _normalize_event_type(cls, value: object) -> str:
        return _required_string(value)

    @field_validator("event_id", "summary", "created_at", "recorded_at", "actor", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _optional_string(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_SOURCE_KIND_VALUES)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _normalize_evidence_refs(cls, value: object) -> list[str]:
        return _strict_string_list(value)


class ResearchPersonaCapsule(_FrozenPersonaModel):
    """Prompt-safe role projection of the research persona."""

    schema_version: int = RESEARCH_PERSONA_SCHEMA_VERSION
    role: ResearchPersonaCapsuleRole
    purpose: Literal["prompt"] = "prompt"
    summary: str
    influence_summary: dict[str, object] = Field(default_factory=dict)
    facts: list[dict[str, object]] = Field(default_factory=list)
    axes: list[dict[str, object]] = Field(default_factory=list)
    standing_preferences: list[str] = Field(default_factory=list)
    negative_preferences: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    research_areas: list[str] = Field(default_factory=list)
    expertise: list[str] = Field(default_factory=list)
    workstyle: list[str] = Field(default_factory=list)
    scientific_taste: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        return _schema_version(value)

    @field_validator("role", mode="before")
    @classmethod
    def _normalize_role(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_CAPSULE_ROLE_VALUES)

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, value: object) -> str:
        return _required_string(value)

    @field_validator("facts", "axes", mode="before")
    @classmethod
    def _normalize_dict_lists(cls, value: object) -> object:
        return _strict_dict_list(value)

    @field_validator(*_PROMPT_SAFE_STRING_LIST_FIELDS, mode="before")
    @classmethod
    def _normalize_string_lists(cls, value: object) -> list[str]:
        return _strict_string_list(value)


class ResearchPersonaValidationResult(_FrozenPersonaModel):
    """Structured validation result for arbitrary persona input."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("valid", mode="before")
    @classmethod
    def _normalize_valid(cls, value: object) -> bool:
        return _strict_bool(value)

    @field_validator("errors", "warnings", mode="before")
    @classmethod
    def _normalize_messages(cls, value: object) -> list[str]:
        return _strict_string_list(value)


def research_persona_root(data_root: Path | None = None) -> Path:
    """Return the private machine-local research-persona store root."""

    return _data_root(data_root) / RESEARCH_PERSONA_STORE_DIR_NAME


def research_persona_path(data_root: Path | None = None) -> Path:
    """Return the private research-persona snapshot path."""

    return research_persona_root(data_root) / RESEARCH_PERSONA_PROFILE_FILENAME


def parse_research_persona_data_strict(data: object) -> ResearchPersona:
    """Parse strict research-persona data without scalar/list coercion."""

    if isinstance(data, ResearchPersona):
        return data
    if not isinstance(data, dict):
        raise ResearchPersonaError("research persona profile must be a JSON object")
    try:
        return ResearchPersona.model_validate(data)
    except PydanticValidationError as exc:
        raise ResearchPersonaError("; ".join(_format_pydantic_errors(exc))) from exc


def validate_research_persona(data: object) -> ResearchPersonaValidationResult:
    """Validate arbitrary persona data and return structured errors."""

    try:
        parse_research_persona_data_strict(data)
    except ResearchPersonaError as exc:
        return ResearchPersonaValidationResult(valid=False, errors=[str(exc)])
    return ResearchPersonaValidationResult(valid=True)


def load_research_persona(data_root: Path | None = None, *, strict: bool = False) -> ResearchPersona:
    """Read the private persona snapshot, returning an empty persona if missing.

    Malformed existing data raises in strict mode and otherwise falls back to an
    empty in-memory persona without creating or rewriting files.
    """

    path = research_persona_path(data_root)
    raw = safe_read_file(path)
    if raw is None:
        return ResearchPersona()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        if strict:
            raise ResearchPersonaError(f"research persona profile at {path} is not valid JSON") from exc
        logger.warning("research persona profile at %s is not valid JSON; using empty persona", path)
        return ResearchPersona()
    try:
        return parse_research_persona_data_strict(data)
    except ResearchPersonaError:
        if strict:
            raise
        logger.warning("research persona profile at %s failed validation; using empty persona", path)
        return ResearchPersona()


def save_research_persona(persona: ResearchPersona, data_root: Path | None = None) -> Path:
    """Persist a strict persona snapshot with private permissions."""

    if not isinstance(persona, ResearchPersona):
        raise ResearchPersonaError("save_research_persona requires a ResearchPersona instance")
    root = research_persona_root(data_root)
    _ensure_store_dirs(root)
    path = research_persona_path(data_root)
    with file_lock(path):
        atomic_write(path, persona.model_dump_json(indent=2) + "\n")
    _ensure_private_file(path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    if lock_path.exists():
        _ensure_private_file(lock_path)
    return path


def _index_by_id(rows: list[dict[str, object]], row_id: str) -> int | None:
    for index, row in enumerate(rows):
        if row.get("id") == row_id:
            return index
    return None


def _operation_values(operation: ResearchPersonaPatchOperation) -> list[str]:
    values = list(operation.values)
    if operation.value is not None:
        if not isinstance(operation.value, str):
            raise ResearchPersonaError(f"{operation.op} requires string value entries")
        values.append(operation.value)
    return _strict_string_list(values)


def _json_pointer_parts(path: str) -> list[str]:
    if not path.startswith("/"):
        raise ResearchPersonaError("patch path must start with /")
    parts = []
    for raw_part in path.strip("/").split("/"):
        if not raw_part:
            continue
        parts.append(raw_part.replace("~1", "/").replace("~0", "~"))
    if not parts:
        raise ResearchPersonaError("patch path must not be empty")
    return parts


def _remove_fact_from_payload(payload: dict[str, object], fact_id: str) -> None:
    facts = payload["facts"]
    if isinstance(facts, list):
        payload["facts"] = [fact for fact in facts if not isinstance(fact, dict) or fact.get("id") != fact_id]

    axes = payload["axes"]
    if isinstance(axes, list):
        for axis in axes:
            if not isinstance(axis, dict):
                continue
            fact_ids = axis.get("fact_ids")
            if isinstance(fact_ids, list):
                axis["fact_ids"] = [item for item in fact_ids if item != fact_id]


def _apply_pointer_add(payload: dict[str, object], operation: ResearchPersonaPatchOperation) -> None:
    if operation.path is None:
        raise ResearchPersonaError("add requires path")
    parts = _json_pointer_parts(operation.path)
    if parts == ["facts"]:
        fact = ResearchPersonaFact.model_validate(operation.value)
        facts = payload["facts"]
        if not isinstance(facts, list):
            raise ResearchPersonaError("facts must be a list")
        index = _index_by_id(facts, fact.id)
        if index is not None:
            raise ResearchPersonaError(f"add would duplicate fact id: {fact.id}")
        facts.append(fact.model_dump(mode="python"))
        return
    if parts == ["axes"]:
        axis = ResearchPersonaAxis.model_validate(operation.value)
        axes = payload["axes"]
        if not isinstance(axes, list):
            raise ResearchPersonaError("axes must be a list")
        index = _index_by_id(axes, axis.id)
        if index is not None:
            raise ResearchPersonaError(f"add would duplicate axis id: {axis.id}")
        axes.append(axis.model_dump(mode="python"))
        return
    if len(parts) == 1 and parts[0] in RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS:
        if not isinstance(operation.value, str):
            raise ResearchPersonaError(f"add to {operation.path} requires a string value")
        current = payload.get(parts[0])
        if not isinstance(current, list):
            raise ResearchPersonaError(f"{parts[0]} must be a list")
        values = _strict_string_list([operation.value])
        for item in values:
            if item not in current:
                current.append(item)
        return
    raise ResearchPersonaError(f"unsupported add path: {operation.path}")


def _apply_pointer_update(payload: dict[str, object], operation: ResearchPersonaPatchOperation) -> None:
    if operation.path is None:
        raise ResearchPersonaError("update requires path")
    parts = _json_pointer_parts(operation.path)
    if len(parts) == 2 and parts[0] == "facts":
        facts = payload["facts"]
        if not isinstance(facts, list):
            raise ResearchPersonaError("facts must be a list")
        index = _index_by_id(facts, parts[1])
        if index is None:
            raise ResearchPersonaError(f"update cannot find fact id: {parts[1]}")
        if not isinstance(operation.value, dict):
            raise ResearchPersonaError("fact update requires an object value")
        current = facts[index]
        if not isinstance(current, dict):
            raise ResearchPersonaError("facts must contain objects")
        updated = dict(current)
        updated.update(operation.value)
        updated["id"] = parts[1]
        facts[index] = ResearchPersonaFact.model_validate(updated).model_dump(mode="python")
        return
    if len(parts) == 2 and parts[0] == "axes":
        axes = payload["axes"]
        if not isinstance(axes, list):
            raise ResearchPersonaError("axes must be a list")
        index = _index_by_id(axes, parts[1])
        if index is None:
            raise ResearchPersonaError(f"update cannot find axis id: {parts[1]}")
        if not isinstance(operation.value, dict):
            raise ResearchPersonaError("axis update requires an object value")
        current = axes[index]
        if not isinstance(current, dict):
            raise ResearchPersonaError("axes must contain objects")
        updated = dict(current)
        updated.update(operation.value)
        updated["id"] = parts[1]
        axes[index] = ResearchPersonaAxis.model_validate(updated).model_dump(mode="python")
        return
    if len(parts) == 1 and parts[0] in RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS:
        payload[parts[0]] = _strict_string_list(operation.value)
        return
    raise ResearchPersonaError(f"unsupported update path: {operation.path}")


def _apply_pointer_remove(payload: dict[str, object], operation: ResearchPersonaPatchOperation) -> None:
    if operation.path is None:
        raise ResearchPersonaError("remove requires path")
    parts = _json_pointer_parts(operation.path)
    if len(parts) == 2 and parts[0] == "facts":
        _remove_fact_from_payload(payload, parts[1])
        return
    if len(parts) == 2 and parts[0] == "axes":
        axes = payload["axes"]
        if not isinstance(axes, list):
            raise ResearchPersonaError("axes must be a list")
        payload["axes"] = [axis for axis in axes if not isinstance(axis, dict) or axis.get("id") != parts[1]]
        return
    if len(parts) == 1 and parts[0] in RESEARCH_PERSONA_TOP_LEVEL_STRING_LIST_FIELDS:
        payload[parts[0]] = []
        return
    raise ResearchPersonaError(f"unsupported remove path: {operation.path}")


def apply_research_persona_patch(persona: ResearchPersona, patch: ResearchPersonaPatch) -> ResearchPersona:
    """Apply a strict in-memory patch and return a new persona snapshot."""

    if not isinstance(persona, ResearchPersona):
        raise ResearchPersonaError("apply_research_persona_patch requires a ResearchPersona instance")
    if not isinstance(patch, ResearchPersonaPatch):
        raise ResearchPersonaError("apply_research_persona_patch requires a ResearchPersonaPatch instance")

    payload = persona.model_dump(mode="python")
    tombstoned_fact_ids = {tombstone.fact_id for tombstone in patch.tombstones}
    for fact_id in tombstoned_fact_ids:
        _remove_fact_from_payload(payload, fact_id)

    for operation in patch.operations:
        facts = payload["facts"]
        axes = payload["axes"]
        if not isinstance(facts, list) or not isinstance(axes, list):
            raise ResearchPersonaError("persona payload is malformed")

        if operation.op == "add":
            _apply_pointer_add(payload, operation)
            continue

        if operation.op == "update":
            _apply_pointer_update(payload, operation)
            continue

        if operation.op == "remove":
            _apply_pointer_remove(payload, operation)
            continue

        if operation.op in {"add_fact", "upsert_fact", "replace_fact"}:
            if operation.fact is None:
                raise ResearchPersonaError(f"{operation.op} requires fact")
            fact_payload = operation.fact.model_dump(mode="python")
            fact_id = operation.fact.id
            if fact_id in tombstoned_fact_ids:
                continue
            index = _index_by_id(facts, fact_id)
            if operation.op == "add_fact" and index is not None:
                raise ResearchPersonaError(f"add_fact would duplicate fact id: {fact_id}")
            if operation.op == "replace_fact" and index is None:
                raise ResearchPersonaError(f"replace_fact cannot find fact id: {fact_id}")
            if index is None:
                facts.append(fact_payload)
            else:
                facts[index] = fact_payload
            continue

        if operation.op in {"remove_fact", "delete_fact", "tombstone_fact"}:
            if operation.fact_id is None:
                raise ResearchPersonaError(f"{operation.op} requires fact_id")
            tombstoned_fact_ids.add(operation.fact_id)
            _remove_fact_from_payload(payload, operation.fact_id)
            continue

        if operation.op in {"add_axis", "upsert_axis", "replace_axis"}:
            if operation.axis is None:
                raise ResearchPersonaError(f"{operation.op} requires axis")
            axis_payload = operation.axis.model_dump(mode="python")
            axis_id = operation.axis.id
            index = _index_by_id(axes, axis_id)
            if operation.op == "add_axis" and index is not None:
                raise ResearchPersonaError(f"add_axis would duplicate axis id: {axis_id}")
            if operation.op == "replace_axis" and index is None:
                raise ResearchPersonaError(f"replace_axis cannot find axis id: {axis_id}")
            if index is None:
                axes.append(axis_payload)
            else:
                axes[index] = axis_payload
            continue

        if operation.op in {"remove_axis", "delete_axis"}:
            if operation.axis_id is None:
                raise ResearchPersonaError(f"{operation.op} requires axis_id")
            payload["axes"] = [
                axis for axis in axes if not isinstance(axis, dict) or axis.get("id") != operation.axis_id
            ]
            continue

        if operation.op in {"append_list", "remove_list_item", "set_list"}:
            if operation.list_name is None:
                raise ResearchPersonaError(f"{operation.op} requires list_name")
            field_name = operation.list_name
            current = payload.get(field_name)
            if not isinstance(current, list):
                raise ResearchPersonaError(f"{field_name} must be a list")
            values = _operation_values(operation)
            if operation.op == "set_list":
                payload[field_name] = values
            elif operation.op == "append_list":
                merged = list(current)
                for item in values:
                    if item not in merged:
                        merged.append(item)
                payload[field_name] = merged
            else:
                removals = set(values)
                payload[field_name] = [item for item in current if item not in removals]
            continue

        raise ResearchPersonaError(f"unsupported research persona patch operation: {operation.op}")

    for fact_id in tombstoned_fact_ids:
        _remove_fact_from_payload(payload, fact_id)

    return parse_research_persona_data_strict(payload)


def append_research_persona_history(event: ResearchPersonaHistoryEvent, data_root: Path | None = None) -> Path:
    """Append one private history event under the store lock."""

    if not isinstance(event, ResearchPersonaHistoryEvent):
        raise ResearchPersonaError("append_research_persona_history requires a ResearchPersonaHistoryEvent instance")
    root = research_persona_root(data_root)
    _ensure_store_dirs(root)
    path = root / RESEARCH_PERSONA_HISTORY_DIR_NAME / RESEARCH_PERSONA_LEDGER_FILENAME
    return _jsonl_append(path, event.model_dump_json())


def append_research_persona_tombstone(tombstone: ResearchPersonaTombstone, data_root: Path | None = None) -> Path:
    """Append one private tombstone event under the store lock."""

    if not isinstance(tombstone, ResearchPersonaTombstone):
        raise ResearchPersonaError("append_research_persona_tombstone requires a ResearchPersonaTombstone instance")
    root = research_persona_root(data_root)
    _ensure_store_dirs(root)
    path = root / RESEARCH_PERSONA_TOMBSTONES_DIR_NAME / RESEARCH_PERSONA_LEDGER_FILENAME
    return _jsonl_append(path, tombstone.model_dump_json())


def project_research_persona(persona: ResearchPersona, *, purpose: str) -> dict[str, object]:
    """Return an allowlisted privacy projection for the requested purpose."""

    if not isinstance(persona, ResearchPersona):
        raise ResearchPersonaError("project_research_persona requires a ResearchPersona instance")
    normalized_purpose = _normalize_projection_purpose(purpose)

    projection: dict[str, object] = {
        "schema_version": persona.schema_version,
        "purpose": normalized_purpose,
        "facts": [
            projected
            for fact in persona.facts
            if (projected := _project_fact(fact, purpose=normalized_purpose)) is not None
        ],
        "axes": [
            projected
            for axis in persona.axes
            if (projected := _project_axis(axis, purpose=normalized_purpose)) is not None
        ],
    }
    for field_name in _projection_list_fields(normalized_purpose):
        projection[field_name] = list(getattr(persona, field_name))
    return projection


def build_research_persona_capsule(persona: ResearchPersona, *, role: str) -> ResearchPersonaCapsule:
    """Build a prompt-safe role capsule from safe-to-share persona fields only."""

    if not isinstance(persona, ResearchPersona):
        raise ResearchPersonaError("build_research_persona_capsule requires a ResearchPersona instance")
    normalized_role = _literal_choice(role, RESEARCH_PERSONA_CAPSULE_ROLE_VALUES)
    if normalized_role not in RESEARCH_PERSONA_CAPSULE_ROLE_VALUES:
        choices = ", ".join(RESEARCH_PERSONA_CAPSULE_ROLE_VALUES)
        raise ResearchPersonaError(f"role must be one of: {choices}")
    projection = project_research_persona(persona, purpose="prompt")
    facts = projection["facts"]
    axes = projection["axes"]
    fact_count = len(facts) if isinstance(facts, list) else 0
    axis_count = len(axes) if isinstance(axes, list) else 0
    preference_count = sum(
        len(projection.get(field_name, []))
        for field_name in _PROMPT_SAFE_STRING_LIST_FIELDS
        if isinstance(projection.get(field_name), list)
    )
    if fact_count or axis_count or preference_count:
        summary = (
            f"{normalized_role} capsule with {fact_count} prompt-safe facts, "
            f"{axis_count} axes, and {preference_count} preference entries."
        )
    else:
        summary = f"{normalized_role} capsule with no prompt-safe research persona facts."

    return ResearchPersonaCapsule(
        role=normalized_role,  # type: ignore[arg-type]
        summary=summary,
        influence_summary={
            "role": normalized_role,
            "facts": facts if isinstance(facts, list) else [],
            "axes": axes if isinstance(axes, list) else [],
            "standing_preferences": projection["standing_preferences"],
            "negative_preferences": projection["negative_preferences"],
            "tools": projection["tools"],
            "research_areas": projection["research_areas"],
            "expertise": projection["expertise"],
            "workstyle": projection["workstyle"],
            "scientific_taste": projection["scientific_taste"],
        },
        facts=facts if isinstance(facts, list) else [],
        axes=axes if isinstance(axes, list) else [],
        standing_preferences=projection["standing_preferences"],
        negative_preferences=projection["negative_preferences"],
        tools=projection["tools"],
        research_areas=projection["research_areas"],
        expertise=projection["expertise"],
        workstyle=projection["workstyle"],
        scientific_taste=projection["scientific_taste"],
    )
