"""Canonical typed ``gpd_return`` envelope parsing and validation.

This module is the shared source of truth for the machine-readable return
contract used by command/CLI validation.  It keeps the top-level required
fields explicit, validates nested YAML payloads recursively, and rejects
scalar/list mismatches before callers interpret the envelope.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

from gpd.core.continuation import ContinuationBoundedSegment, ContinuationHandoff

__all__ = [
    "GPD_RETURN_BLOCK_RE",
    "GpdReturnContinuationBoundedSegment",
    "GpdReturnContinuationHandoff",
    "GpdReturnContinuationUpdate",
    "GpdReturnEnvelope",
    "GpdReturnStatusContract",
    "GpdReturnValidationResult",
    "REQUIRED_RETURN_FIELDS",
    "RETURN_ENVELOPE_STATUS_CONTRACTS",
    "VALID_RETURN_STATUSES",
    "extract_gpd_return_block",
    "validate_gpd_return_markdown",
]

VALID_RETURN_STATUSES: frozenset[str] = frozenset({"completed", "checkpoint", "blocked", "failed"})
"""Allowed values for ``gpd_return.status``."""

REQUIRED_RETURN_FIELDS: tuple[str, ...] = ("status", "files_written", "issues", "next_actions")
"""Fields that must be present in every ``gpd_return`` envelope."""

GPD_RETURN_BLOCK_RE = re.compile(r"```ya?ml\s*\n(gpd_return:\s*\n[\s\S]*?)```")
"""Fence matcher for the canonical ``gpd_return`` YAML block."""


@dataclass(frozen=True)
class GpdReturnStatusContract:
    """Status-specific top-level contract shape."""

    required_fields: tuple[str, ...]
    structured_fields: tuple[str, ...]


class GpdReturnContinuationHandoff(ContinuationHandoff):
    """Durable handoff payload visible in ``gpd_return``."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class GpdReturnContinuationBoundedSegment(ContinuationBoundedSegment):
    """Durable bounded-segment payload visible in ``gpd_return``."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class GpdReturnContinuationUpdate(BaseModel):
    """Typed durable continuation update nested inside ``gpd_return``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    handoff: GpdReturnContinuationHandoff | None = None
    bounded_segment: GpdReturnContinuationBoundedSegment | None = None


RETURN_ENVELOPE_STATUS_CONTRACTS: dict[str, GpdReturnStatusContract] = {
    "completed": GpdReturnStatusContract(
        required_fields=REQUIRED_RETURN_FIELDS,
        structured_fields=(
            "state_updates",
            "contract_updates",
            "decisions",
            "approved_plans",
            "blocked_plans",
            "continuation_update",
            "conventions_used",
        ),
    ),
    "checkpoint": GpdReturnStatusContract(
        required_fields=REQUIRED_RETURN_FIELDS,
        structured_fields=(
            "state_updates",
            "contract_updates",
            "decisions",
            "approved_plans",
            "blocked_plans",
            "blockers",
            "continuation_update",
        ),
    ),
    "blocked": GpdReturnStatusContract(
        required_fields=REQUIRED_RETURN_FIELDS,
        structured_fields=("approved_plans", "blocked_plans", "blockers", "continuation_update"),
    ),
    "failed": GpdReturnStatusContract(
        required_fields=REQUIRED_RETURN_FIELDS,
        structured_fields=("approved_plans", "blocked_plans", "blockers", "continuation_update"),
    ),
}
"""Explicit status-dependent contract structure for supported envelopes."""


class GpdReturnEnvelope(BaseModel):
    """Typed machine-readable ``gpd_return`` payload."""

    model_config = ConfigDict(extra="allow", strict=True)

    status: StrictStr
    files_written: list[StrictStr]
    issues: list[StrictStr]
    next_actions: list[StrictStr]
    tasks_completed: int | None = None
    tasks_total: int | None = None
    duration_seconds: int | float | None = None
    phase: StrictStr | None = None
    plan: StrictStr | None = None
    design_file: StrictStr | None = None
    field_assessment: StrictStr | None = None
    state_updates: dict[str, object] | None = None
    contract_updates: dict[str, object] | None = None
    decisions: list[object] | None = None
    approved_plans: list[StrictStr] | None = None
    blocked_plans: list[StrictStr] | None = None
    blockers: list[object] | None = None
    continuation_update: GpdReturnContinuationUpdate | None = None
    conventions_used: dict[str, object] | None = None
    checkpoint_hashes: list[dict[str, object]] | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("status must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("status must be a non-empty string")
        if normalized.lower() in VALID_RETURN_STATUSES and normalized not in VALID_RETURN_STATUSES:
            raise ValueError(
                f"status must use canonical lowercase spelling: {', '.join(sorted(VALID_RETURN_STATUSES))}"
            )
        if normalized not in VALID_RETURN_STATUSES:
            raise ValueError(f"Invalid status '{value}'. Must be one of: {', '.join(sorted(VALID_RETURN_STATUSES))}")
        return normalized

    @field_validator("files_written", "issues", "next_actions", mode="before")
    @classmethod
    def _validate_string_list(cls, value: object, info) -> list[str]:
        return _validate_string_list(value, field_name=info.field_name)

    @field_validator("decisions", "blockers", mode="before")
    @classmethod
    def _validate_yaml_sequence(cls, value: object, info) -> list[object] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError(f"{info.field_name} must be a list")
        for index, item in enumerate(value):
            _validate_yaml_native(item, f"gpd_return.{info.field_name}[{index}]")
        return value

    @field_validator("approved_plans", "blocked_plans", mode="before")
    @classmethod
    def _validate_plan_id_list(cls, value: object, info) -> list[str] | None:
        return _validate_string_list(value, field_name=info.field_name)

    @field_validator("tasks_completed", "tasks_total", mode="before")
    @classmethod
    def _validate_task_count(cls, value: object, info) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{info.field_name} not a number: {value!r}")
        return value

    @field_validator("state_updates", "contract_updates", "conventions_used", mode="before")
    @classmethod
    def _validate_yaml_mapping(cls, value: object, info) -> dict[str, object] | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError(f"{info.field_name} must be a mapping")
        _validate_yaml_mapping(value, f"gpd_return.{info.field_name}")
        return dict(value)

    @field_validator("checkpoint_hashes", mode="before")
    @classmethod
    def _validate_checkpoint_hashes(cls, value: object) -> list[dict[str, object]] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("checkpoint_hashes must be a list")
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise ValueError(f"gpd_return.checkpoint_hashes[{index}] must be a mapping")
            _validate_yaml_mapping(item, f"gpd_return.checkpoint_hashes[{index}]")
        return [dict(item) for item in value]

    @model_validator(mode="after")
    def _validate_extra_fields(self) -> GpdReturnEnvelope:
        extras = self.model_extra or {}
        for field_name, value in extras.items():
            _validate_yaml_native(value, f"gpd_return.{field_name}")
        return self


class GpdReturnValidationResult(BaseModel):
    """Validation result for a ``gpd_return`` envelope embedded in markdown."""

    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fields: dict[str, object] = Field(default_factory=dict)
    warning_count: int = 0
    envelope: GpdReturnEnvelope | None = None


def extract_gpd_return_block(content: str) -> str | None:
    """Extract the canonical fenced YAML block containing ``gpd_return``."""
    match = GPD_RETURN_BLOCK_RE.search(content)
    return match.group(1) if match else None


def validate_gpd_return_markdown(content: str) -> GpdReturnValidationResult:
    """Parse and validate a markdown file containing a fenced ``gpd_return`` block."""
    yaml_block = extract_gpd_return_block(content)
    if yaml_block is None:
        return GpdReturnValidationResult(passed=False, errors=["No gpd_return YAML block found"])

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        return GpdReturnValidationResult(passed=False, errors=[f"gpd_return YAML parse error: {exc}"])

    if not isinstance(parsed, Mapping):
        return GpdReturnValidationResult(passed=False, errors=["gpd_return YAML parse error: expected a mapping"])

    top_level_keys = set(parsed.keys())
    if top_level_keys != {"gpd_return"}:
        unexpected = ", ".join(sorted(top_level_keys - {"gpd_return"}))
        missing = "gpd_return" not in parsed
        if missing and unexpected:
            message = f"gpd_return YAML parse error: missing top-level gpd_return key and unexpected top-level key(s): {unexpected}"
        elif missing:
            message = "gpd_return YAML parse error: missing top-level gpd_return key"
        else:
            message = f"gpd_return YAML parse error: unexpected top-level key(s): {unexpected}"
        return GpdReturnValidationResult(passed=False, errors=[message])

    raw_envelope = parsed.get("gpd_return")
    if not isinstance(raw_envelope, Mapping):
        return GpdReturnValidationResult(
            passed=False,
            errors=["gpd_return YAML parse error: gpd_return must be a mapping"],
        )

    try:
        envelope = GpdReturnEnvelope.model_validate(raw_envelope)
    except PydanticValidationError as exc:
        return GpdReturnValidationResult(
            passed=False,
            errors=_format_pydantic_validation_error(exc),
        )

    warnings = _collect_gpd_return_warnings(envelope)
    return GpdReturnValidationResult(
        passed=True,
        warnings=warnings,
        fields=envelope.model_dump(exclude_none=True),
        warning_count=len(warnings),
        envelope=envelope,
    )


def _format_pydantic_validation_error(exc: PydanticValidationError) -> list[str]:
    errors: list[str] = []
    for item in exc.errors():
        location = tuple(str(part) for part in item.get("loc", ()))
        field_name = location[-1] if location else "gpd_return"
        message = _normalize_validation_message(item.get("msg", "validation error"))
        error_type = item.get("type", "")

        if error_type == "missing" or message == "Field required":
            errors.append(f"Missing required field: {field_name}")
            continue

        if location:
            if len(location) == 1 and (message.startswith(f"{field_name} ") or message.startswith(f"{field_name}:")):
                errors.append(message)
                continue
            errors.append(f"{'.'.join(location)}: {message}")
        else:
            errors.append(message)
    return errors


def _normalize_validation_message(message: str) -> str:
    if message.startswith("Value error, "):
        return message[len("Value error, ") :]
    return message


def _collect_gpd_return_warnings(envelope: GpdReturnEnvelope) -> list[str]:
    warnings: list[str] = []

    if envelope.status == "completed" and envelope.tasks_completed is not None and envelope.tasks_total is not None:
        if envelope.tasks_completed < envelope.tasks_total:
            warnings.append(
                f"Status is 'completed' but tasks_completed ({envelope.tasks_completed}) < tasks_total ({envelope.tasks_total})"
            )

    if "duration_seconds" not in envelope.model_fields_set or envelope.duration_seconds is None:
        warnings.append("Recommended field missing: duration_seconds")

    return warnings


def _validate_string_list(value: object, *, field_name: str) -> list[str]:
    if value is None:
        raise ValueError(f"{field_name} must be a list")
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"gpd_return.{field_name}[{index}] must be a string")
        stripped = item.strip()
        if not stripped:
            raise ValueError(f"gpd_return.{field_name}[{index}] must be a non-empty string")
        normalized.append(stripped)
    return normalized


def _validate_yaml_native(value: object, path: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_yaml_native(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        _validate_yaml_mapping(value, path)
        return
    raise ValueError(f"{path} must be a YAML scalar, list, or mapping, not {type(value).__name__}")


def _validate_yaml_mapping(value: Mapping[str, object], path: str) -> None:
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{path} must use string keys")
        _validate_yaml_native(item, f"{path}.{key}")
