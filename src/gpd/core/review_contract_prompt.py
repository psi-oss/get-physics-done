"""Helpers for normalizing and surfacing review contracts inside model-visible prompts."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

import yaml

from gpd.core.model_visible_sections import render_model_visible_yaml_section
from gpd.core.model_visible_text import (
    REVIEW_CONTRACT_CONDITIONAL_WHENS,
    REVIEW_CONTRACT_FRONTMATTER_KEY,
    REVIEW_CONTRACT_MODES,
    REVIEW_CONTRACT_PREFLIGHT_CHECKS,
    REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
    REVIEW_CONTRACT_REQUIRED_STATES,
    REVIEW_CONTRACT_WRAPPER_KEYS,
    review_contract_visibility_note,
)
from gpd.core.strict_yaml import load_strict_yaml

REVIEW_CONTRACT_FIELD_ORDER = (
    "schema_version",
    "review_mode",
    "required_outputs",
    "required_evidence",
    "blocking_conditions",
    "preflight_checks",
    "stage_artifacts",
    "conditional_requirements",
    "required_state",
)
REVIEW_CONTRACT_CONDITIONAL_FIELD_ORDER = (
    "when",
    "required_outputs",
    "required_evidence",
    "blocking_conditions",
    "preflight_checks",
    "blocking_preflight_checks",
    "stage_artifacts",
)
REVIEW_CONTRACT_KEYS = frozenset(REVIEW_CONTRACT_FIELD_ORDER)
REVIEW_CONTRACT_CONDITIONAL_KEYS = frozenset(REVIEW_CONTRACT_CONDITIONAL_FIELD_ORDER)


def _load_review_contract_payload(
    review_contract: object,
    *,
    allowed_wrapper_key: str,
) -> tuple[dict[str, object], bool]:
    """Return a strict review-contract mapping and whether it was wrapped."""

    if review_contract is None:
        return {}, False
    if isinstance(review_contract, str):
        block = review_contract.strip()
        if not block:
            return {}, False
        try:
            loaded = load_strict_yaml(block)
        except yaml.YAMLError as exc:
            raise ValueError(f"review contract must parse as valid YAML: {exc}") from exc
    elif isinstance(review_contract, Mapping):
        loaded = dict(review_contract)
    else:
        raise ValueError("review contract must be provided as YAML text or a mapping")

    if loaded is None:
        return {}, False
    if not isinstance(loaded, dict):
        raise ValueError(f"review contract must parse to a mapping, got {type(loaded).__name__}")

    wrapped_key_matches = [key for key in REVIEW_CONTRACT_WRAPPER_KEYS if key in loaded]
    if len(wrapped_key_matches) > 1:
        raise ValueError("review contract must use only one wrapper key")

    wrapped_key = wrapped_key_matches[0] if wrapped_key_matches else None
    if wrapped_key is not None and wrapped_key != allowed_wrapper_key:
        raise ValueError(f"review contract must use the wrapper key '{allowed_wrapper_key}'")

    wrapped_candidate = loaded.get(wrapped_key) if wrapped_key is not None else None
    if wrapped_key is not None and wrapped_candidate is None:
        return {}, True
    if wrapped_key is not None and not isinstance(wrapped_candidate, Mapping):
        raise ValueError("review contract must parse to a mapping")
    wrapped = dict(wrapped_candidate) if isinstance(wrapped_candidate, Mapping) else None

    if wrapped is not None:
        unknown_top_level_keys = sorted(str(key) for key in loaded if key not in REVIEW_CONTRACT_WRAPPER_KEYS)
        if unknown_top_level_keys:
            formatted = ", ".join(unknown_top_level_keys)
            raise ValueError(f"Unknown review-contract field(s): {formatted}")
        unknown_inner_keys = sorted(str(key) for key in wrapped if str(key) not in REVIEW_CONTRACT_KEYS)
        if unknown_inner_keys:
            formatted = ", ".join(unknown_inner_keys)
            raise ValueError(f"Unknown review-contract field(s): {formatted}")
        return wrapped, True

    unknown_keys = sorted(str(key) for key in loaded if str(key) not in REVIEW_CONTRACT_KEYS)
    if unknown_keys:
        formatted = ", ".join(unknown_keys)
        raise ValueError(f"Unknown review-contract field(s): {formatted}")

    return loaded, False


def _render_review_contract_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Return the compact model-visible payload, omitting empty optional collections."""

    rendered: dict[str, object] = {}
    for field_name in REVIEW_CONTRACT_FIELD_ORDER:
        value = payload.get(field_name)
        if field_name == "required_state":
            if value:
                rendered[field_name] = value
            continue
        if field_name == "conditional_requirements":
            if not value:
                continue
            conditional_requirements: list[dict[str, object]] = []
            for requirement in value:
                if not isinstance(requirement, Mapping):
                    continue
                rendered_requirement: dict[str, object] = {}
                for conditional_field in REVIEW_CONTRACT_CONDITIONAL_FIELD_ORDER:
                    conditional_value = requirement.get(conditional_field)
                    if conditional_value:
                        rendered_requirement[conditional_field] = conditional_value
                if rendered_requirement:
                    conditional_requirements.append(rendered_requirement)
            if conditional_requirements:
                rendered[field_name] = conditional_requirements
            continue
        if isinstance(value, list):
            if value:
                rendered[field_name] = value
            continue
        if value is not None:
            rendered[field_name] = value
    return rendered


def _normalize_review_contract_required_str(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def _normalize_review_contract_optional_str(value: object, *, field_name: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


def _normalize_review_contract_string_list(value: object, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        entry = _normalize_review_contract_required_str(item, field_name=field_name)
        if entry in seen:
            raise ValueError(f"{field_name} must not contain duplicates")
        seen.add(entry)
        normalized.append(entry)
    return normalized


def _normalize_review_contract_choice(value: object, *, field_name: str, valid_values: tuple[str, ...]) -> str:
    normalized = _normalize_review_contract_required_str(value, field_name=field_name)
    for valid_value in valid_values:
        if normalized.casefold() == valid_value.casefold():
            return valid_value
    valid = ", ".join(valid_values)
    raise ValueError(f"{field_name} must be one of: {valid}; got {normalized!r}")


def _normalize_review_contract_choice_list(
    value: object,
    *,
    field_name: str,
    valid_values: tuple[str, ...],
) -> list[str]:
    normalized = _normalize_review_contract_string_list(value, field_name=field_name)
    canonicalized: list[str] = []
    invalid_values: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        matched = next((valid_value for valid_value in valid_values if item.casefold() == valid_value.casefold()), None)
        if matched is None:
            invalid_values.append(item)
            continue
        if matched in seen:
            raise ValueError(f"{field_name} must not contain duplicates")
        seen.add(matched)
        canonicalized.append(matched)
    if invalid_values:
        valid = ", ".join(valid_values)
        formatted = ", ".join(repr(item) for item in invalid_values)
        raise ValueError(f"{field_name} must contain only: {valid}; got {formatted}")
    return canonicalized


def _normalize_review_contract_conditional_when(value: object, *, field_name: str) -> str:
    return _normalize_review_contract_choice(
        value,
        field_name=field_name,
        valid_values=REVIEW_CONTRACT_CONDITIONAL_WHENS,
    )


def _normalize_review_contract_conditional_requirements(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("conditional_requirements must be a list of mappings")

    normalized: list[dict[str, object]] = []
    seen_whens: dict[str, int] = {}
    for index, item in enumerate(value):
        field_name = f"conditional_requirements[{index}]"
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} must be a mapping")
        unknown_keys = sorted(str(key) for key in item if str(key) not in REVIEW_CONTRACT_CONDITIONAL_KEYS)
        if unknown_keys:
            formatted = ", ".join(unknown_keys)
            raise ValueError(f"Unknown review-contract field(s): {field_name}.{formatted}")
        normalized_item = {
            "when": _normalize_review_contract_conditional_when(item.get("when"), field_name=f"{field_name}.when"),
            "required_outputs": _normalize_review_contract_string_list(
                item.get("required_outputs"),
                field_name=f"{field_name}.required_outputs",
            ),
            "required_evidence": _normalize_review_contract_string_list(
                item.get("required_evidence"),
                field_name=f"{field_name}.required_evidence",
            ),
            "blocking_conditions": _normalize_review_contract_string_list(
                item.get("blocking_conditions"),
                field_name=f"{field_name}.blocking_conditions",
            ),
            "preflight_checks": _normalize_review_contract_choice_list(
                item.get("preflight_checks"),
                field_name=f"{field_name}.preflight_checks",
                valid_values=REVIEW_CONTRACT_PREFLIGHT_CHECKS,
            ),
            "blocking_preflight_checks": _normalize_review_contract_choice_list(
                item.get("blocking_preflight_checks"),
                field_name=f"{field_name}.blocking_preflight_checks",
                valid_values=REVIEW_CONTRACT_PREFLIGHT_CHECKS,
            ),
            "stage_artifacts": _normalize_review_contract_string_list(
                item.get("stage_artifacts"),
                field_name=f"{field_name}.stage_artifacts",
            ),
        }
        if not any(
            normalized_item[key]
            for key in (
                "required_outputs",
                "required_evidence",
                "blocking_conditions",
                "preflight_checks",
                "blocking_preflight_checks",
                "stage_artifacts",
            )
        ):
            raise ValueError(
                f"{field_name} must declare at least one of: "
                "required_outputs, required_evidence, blocking_conditions, "
                "preflight_checks, blocking_preflight_checks, stage_artifacts"
            )
        when = normalized_item["when"]
        if when in seen_whens:
            first_index = seen_whens[when]
            raise ValueError(
                f"{field_name}.when duplicates conditional_requirements[{first_index}].when: {when}"
            )
        seen_whens[when] = index
        normalized.append(normalized_item)
    return normalized


def _normalize_review_contract_payload(
    review_contract: object,
    *,
    allowed_wrapper_key: str,
) -> dict[str, object]:
    loaded, wrapped = _load_review_contract_payload(
        review_contract,
        allowed_wrapper_key=allowed_wrapper_key,
    )
    if not loaded:
        if wrapped:
            raise ValueError("review contract must set schema_version, review_mode")
        return {}

    if "schema_version" in loaded:
        schema_version = loaded.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise ValueError("schema_version must be the integer 1")
        if schema_version != 1:
            raise ValueError("schema_version must be 1")

    if "review_mode" in loaded:
        _normalize_review_contract_choice(
            loaded.get("review_mode"),
            field_name="review_mode",
            valid_values=REVIEW_CONTRACT_MODES,
        )

    if "schema_version" not in loaded or "review_mode" not in loaded:
        missing = [field for field in ("schema_version", "review_mode") if field not in loaded]
        formatted = ", ".join(missing)
        raise ValueError(f"review contract must set {formatted}")

    schema_version = loaded.get("schema_version")

    required_state_raw = loaded.get("required_state")
    required_state = _normalize_review_contract_optional_str(
        required_state_raw,
        field_name="required_state",
    )
    if required_state:
        required_state = _normalize_review_contract_choice(
            required_state,
            field_name="required_state",
            valid_values=REVIEW_CONTRACT_REQUIRED_STATES,
        )

    preflight_checks = _normalize_review_contract_choice_list(
        loaded.get("preflight_checks"),
        field_name="preflight_checks",
        valid_values=REVIEW_CONTRACT_PREFLIGHT_CHECKS,
    )
    conditional_requirements = _normalize_review_contract_conditional_requirements(
        loaded.get("conditional_requirements")
    )
    return {
        "schema_version": schema_version,
        "review_mode": _normalize_review_contract_choice(
            loaded.get("review_mode"),
            field_name="review_mode",
            valid_values=REVIEW_CONTRACT_MODES,
        ),
        "required_outputs": _normalize_review_contract_string_list(
            loaded.get("required_outputs"),
            field_name="required_outputs",
        ),
        "required_evidence": _normalize_review_contract_string_list(
            loaded.get("required_evidence"),
            field_name="required_evidence",
        ),
        "blocking_conditions": _normalize_review_contract_string_list(
            loaded.get("blocking_conditions"),
            field_name="blocking_conditions",
        ),
        "preflight_checks": preflight_checks,
        "stage_artifacts": _normalize_review_contract_string_list(
            loaded.get("stage_artifacts"),
            field_name="stage_artifacts",
        ),
        "conditional_requirements": conditional_requirements,
        "required_state": required_state,
    }


def normalize_review_contract_payload(review_contract: object) -> dict[str, object]:
    """Return a canonical typed payload for rendering a review contract section."""

    return _normalize_review_contract_payload(
        review_contract,
        allowed_wrapper_key=REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
    )


def normalize_review_contract_frontmatter_payload(review_contract: object) -> dict[str, object]:
    """Return a canonical typed payload for command frontmatter review contracts."""

    return _normalize_review_contract_payload(
        review_contract,
        allowed_wrapper_key=REVIEW_CONTRACT_FRONTMATTER_KEY,
    )


def review_contract_payload(review_contract: object) -> dict[str, object] | None:
    """Return the canonical serialized payload for a review-contract dataclass or mapping."""

    if review_contract is None:
        return None
    if isinstance(review_contract, Mapping):
        payload = dict(review_contract)
    elif dataclasses.is_dataclass(review_contract):
        payload = dataclasses.asdict(review_contract)
    else:
        raise ValueError("review contract must be a mapping or dataclass instance")

    if not payload:
        return None
    required_state = payload.get("required_state")
    if isinstance(required_state, str):
        required_state = required_state.strip()
        if required_state:
            payload["required_state"] = required_state
        else:
            payload.pop("required_state", None)
    elif not required_state:
        payload.pop("required_state", None)
    return payload or None


def render_review_contract_prompt(review_contract: object) -> str:
    """Render a canonical model-visible review-contract section."""

    if dataclasses.is_dataclass(review_contract):
        review_contract = review_contract_payload(review_contract)
    payload = normalize_review_contract_payload(review_contract)
    if not payload:
        return ""
    rendered_payload = _render_review_contract_payload(payload)
    return render_model_visible_yaml_section(
        heading="Review Contract",
        note=review_contract_visibility_note(),
        payload={REVIEW_CONTRACT_PROMPT_WRAPPER_KEY: rendered_payload},
    )
