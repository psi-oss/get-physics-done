"""Helpers for surfacing review contracts inside model-visible prompt bodies."""

from __future__ import annotations

from collections.abc import Mapping

import yaml

REVIEW_CONTRACT_FIELD_ORDER = (
    "schema_version",
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
)
REVIEW_CONTRACT_WRAPPER_KEYS = ("review_contract", "review-contract")
REVIEW_CONTRACT_KEYS = frozenset(REVIEW_CONTRACT_FIELD_ORDER)
REVIEW_CONTRACT_DEFAULTS = {
    "required_outputs": [],
    "required_evidence": [],
    "blocking_conditions": [],
    "preflight_checks": [],
    "stage_ids": [],
    "stage_artifacts": [],
    "final_decision_output": "",
    "requires_fresh_context_per_stage": False,
    "max_review_rounds": 0,
    "required_state": "",
}


def extract_frontmatter_block(frontmatter: str, field_name: str) -> str:
    """Return one top-level YAML frontmatter block, preserving raw formatting."""

    lines = frontmatter.split("\n")
    prefix = f"{field_name}:"
    collected: list[str] = []
    collecting = False

    for line in lines:
        stripped = line.strip()
        is_top_level = line == line.lstrip()
        if not collecting:
            if is_top_level and stripped.startswith(prefix):
                collected.append(line.rstrip())
                collecting = True
            continue
        if is_top_level and stripped:
            break
        collected.append(line.rstrip())

    while collected and not collected[-1]:
        collected.pop()
    return "\n".join(collected)


def _load_review_contract_payload(review_contract: object) -> tuple[dict[str, object], bool]:
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

    wrapped = None
    for key in REVIEW_CONTRACT_WRAPPER_KEYS:
        candidate = loaded.get(key)
        if isinstance(candidate, Mapping):
            wrapped = dict(candidate)
            break

    if wrapped is not None:
        unknown_top_level_keys = sorted(
            str(key) for key in loaded if key not in REVIEW_CONTRACT_WRAPPER_KEYS
        )
        if unknown_top_level_keys:
            formatted = ", ".join(unknown_top_level_keys)
            raise ValueError(f"Unknown review-contract field(s): {formatted}")
        return wrapped, True

    unknown_keys = sorted(str(key) for key in loaded if str(key) not in REVIEW_CONTRACT_KEYS)
    if unknown_keys:
        formatted = ", ".join(unknown_keys)
        raise ValueError(f"Unknown review-contract field(s): {formatted}")

    return loaded, False


def normalize_review_contract_payload(review_contract: object) -> dict[str, object]:
    """Return a canonical typed payload for rendering a review contract section."""

    loaded, wrapped = _load_review_contract_payload(review_contract)
    if not loaded:
        if wrapped:
            raise ValueError("review contract must set schema_version, review_mode")
        return {}

    if "schema_version" not in loaded or "review_mode" not in loaded:
        missing = [field for field in ("schema_version", "review_mode") if field not in loaded]
        formatted = ", ".join(missing)
        raise ValueError(f"review contract must set {formatted}")

    payload: dict[str, object] = {}
    for key in REVIEW_CONTRACT_FIELD_ORDER:
        if key in loaded:
            payload[key] = loaded[key]
        elif key in REVIEW_CONTRACT_DEFAULTS:
            default = REVIEW_CONTRACT_DEFAULTS[key]
            payload[key] = list(default) if isinstance(default, list) else default
    return payload


def render_review_contract_prompt(review_contract: object) -> str:
    """Render a canonical model-visible review-contract section."""

    payload = normalize_review_contract_payload(review_contract)
    if not payload:
        return ""
    rendered = yaml.safe_dump(
        {"review_contract": payload},
        sort_keys=False,
        allow_unicode=False,
    ).rstrip()
    return (
        "## Review Contract\n\n"
        "This command is enforced against the following hard review contract. "
        "Satisfy it directly in the generated artifacts.\n\n"
        f"```yaml\n{rendered}\n```"
    )
