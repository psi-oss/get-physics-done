"""Helpers for normalizing and surfacing review contracts inside model-visible prompts."""

from __future__ import annotations

from collections.abc import Mapping

import yaml

VALID_REVIEW_MODES = ("publication", "review")
VALID_REVIEW_PREFLIGHT_CHECKS = (
    "project_state",
    "roadmap",
    "conventions",
    "research_artifacts",
    "manuscript",
    "artifact_manifest",
    "bibliography_audit",
    "bibliography_audit_clean",
    "compiled_manuscript",
    "publication_blockers",
    "review_ledger",
    "review_ledger_valid",
    "referee_decision",
    "referee_decision_valid",
    "publication_review_outcome",
    "reproducibility_manifest",
    "reproducibility_ready",
    "manuscript_proof_review",
    "referee_report_source",
    "phase_artifacts",
)
VALID_REVIEW_REQUIRED_STATES = ("phase_executed",)
VALID_REVIEW_CONDITIONAL_WHENS = (
    "theorem-bearing claims are present",
    "theorem-bearing manuscripts are present",
)

REVIEW_CONTRACT_FIELD_ORDER = (
    "schema_version",
    "review_mode",
    "required_outputs",
    "required_evidence",
    "blocking_conditions",
    "preflight_checks",
    "stage_ids",
    "stage_artifacts",
    "conditional_requirements",
    "final_decision_output",
    "requires_fresh_context_per_stage",
    "max_review_rounds",
    "required_state",
)
REVIEW_CONTRACT_CONDITIONAL_FIELD_ORDER = (
    "when",
    "required_outputs",
    "required_evidence",
    "blocking_conditions",
    "stage_artifacts",
)
REVIEW_CONTRACT_FRONTMATTER_KEY = "review-contract"
REVIEW_CONTRACT_PROMPT_WRAPPER_KEY = "review_contract"
REVIEW_CONTRACT_WRAPPER_KEYS = (REVIEW_CONTRACT_PROMPT_WRAPPER_KEY, REVIEW_CONTRACT_FRONTMATTER_KEY)
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
        loaded = yaml.safe_load(block)
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
    if isinstance(value, str):
        return [_normalize_review_contract_required_str(value, field_name=field_name)]
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a string or list of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        entry = _normalize_review_contract_required_str(item, field_name=field_name)
        if entry in seen:
            continue
        seen.add(entry)
        normalized.append(entry)
    return normalized


def _normalize_review_contract_choice(value: object, *, field_name: str, valid_values: tuple[str, ...]) -> str:
    normalized = _normalize_review_contract_required_str(value, field_name=field_name)
    if normalized not in valid_values:
        valid = ", ".join(valid_values)
        raise ValueError(f"{field_name} must be one of: {valid}; got {normalized!r}")
    return normalized


def _normalize_review_contract_choice_list(
    value: object,
    *,
    field_name: str,
    valid_values: tuple[str, ...],
) -> list[str]:
    normalized = _normalize_review_contract_string_list(value, field_name=field_name)
    invalid_values = [item for item in normalized if item not in valid_values]
    if invalid_values:
        valid = ", ".join(valid_values)
        formatted = ", ".join(repr(item) for item in invalid_values)
        raise ValueError(f"{field_name} must contain only: {valid}; got {formatted}")
    return normalized


def _normalize_review_contract_bool(value: object, *, field_name: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean")


def _normalize_review_contract_non_negative_int(value: object, *, field_name: str, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value


def _normalize_review_contract_conditional_when(value: object, *, field_name: str) -> str:
    return _normalize_review_contract_choice(
        value,
        field_name=field_name,
        valid_values=VALID_REVIEW_CONDITIONAL_WHENS,
    )


def _normalize_review_contract_conditional_requirements(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("conditional_requirements must be a list of mappings")

    normalized: list[dict[str, object]] = []
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
            "stage_artifacts": _normalize_review_contract_string_list(
                item.get("stage_artifacts"),
                field_name=f"{field_name}.stage_artifacts",
            ),
        }
        if not any(
            normalized_item[key]
            for key in ("required_outputs", "required_evidence", "blocking_conditions", "stage_artifacts")
        ):
            raise ValueError(
                f"{field_name} must declare at least one of: "
                "required_outputs, required_evidence, blocking_conditions, stage_artifacts"
            )
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
            valid_values=VALID_REVIEW_MODES,
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
    if required_state and required_state not in VALID_REVIEW_REQUIRED_STATES:
        valid = ", ".join(VALID_REVIEW_REQUIRED_STATES)
        raise ValueError(f"required_state must be one of: {valid}; got {required_state!r}")

    return {
        "schema_version": schema_version,
        "review_mode": _normalize_review_contract_choice(
            loaded.get("review_mode"),
            field_name="review_mode",
            valid_values=VALID_REVIEW_MODES,
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
        "preflight_checks": _normalize_review_contract_choice_list(
            loaded.get("preflight_checks"),
            field_name="preflight_checks",
            valid_values=VALID_REVIEW_PREFLIGHT_CHECKS,
        ),
        "stage_ids": _normalize_review_contract_string_list(
            loaded.get("stage_ids"),
            field_name="stage_ids",
        ),
        "stage_artifacts": _normalize_review_contract_string_list(
            loaded.get("stage_artifacts"),
            field_name="stage_artifacts",
        ),
        "conditional_requirements": _normalize_review_contract_conditional_requirements(
            loaded.get("conditional_requirements")
        ),
        "final_decision_output": _normalize_review_contract_optional_str(
            loaded.get("final_decision_output"),
            field_name="final_decision_output",
        ),
        "requires_fresh_context_per_stage": _normalize_review_contract_bool(
            loaded.get("requires_fresh_context_per_stage"),
            field_name="requires_fresh_context_per_stage",
        ),
        "max_review_rounds": _normalize_review_contract_non_negative_int(
            loaded.get("max_review_rounds"),
            field_name="max_review_rounds",
        ),
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


def render_review_contract_prompt(review_contract: object) -> str:
    """Render a canonical model-visible review-contract section."""

    payload = normalize_review_contract_payload(review_contract)
    if not payload:
        return ""
    rendered = yaml.safe_dump(
        {REVIEW_CONTRACT_PROMPT_WRAPPER_KEY: payload},
        sort_keys=False,
        allow_unicode=False,
    ).rstrip()
    return (
        "## Review Contract\n\n"
        "This command is enforced against the following hard review contract. "
        "Satisfy it directly in the generated artifacts.\n\n"
        f"```yaml\n{rendered}\n```"
    )
