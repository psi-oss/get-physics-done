"""Executable correctness validators for research artifacts."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.contracts import parse_comparison_verdicts_data_strict
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

__all__ = [
    "CorrectnessValidationResult",
    "validate_comparison_contract",
    "validate_verification_oracle_evidence",
]


class CorrectnessValidationResult(BaseModel):
    """Machine-readable result for body-level correctness artifact checks."""

    valid: bool
    artifact_type: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    verdict_count: int = 0
    checked_path: str | None = None


@dataclass(frozen=True)
class _Fence:
    lang: str
    body: str
    start: int
    end: int


_FENCE_RE = re.compile(r"```(?P<lang>[^\n`]*)\r?\n(?P<body>[\s\S]*?)\r?\n```")
_CODE_LANGS = {
    "python",
    "py",
    "sympy",
    "numpy",
    "sage",
    "julia",
    "r",
    "mathematica",
    "wolfram",
    "bash",
    "sh",
}
_OUTPUT_LANGS = {"output", "text", "stdout", "stderr", "console", "terminal"}
_OUTPUT_LABEL_RE = re.compile(
    r"(?:^|\n)\s*(?:\*\*)?\s*(?:actual\s+|execution\s+)?output\s*:?\s*(?:\*\*)?",
    re.IGNORECASE,
)
_PLACEHOLDER_OUTPUT_RE = re.compile(
    r"\b(?:would produce|expected output|not run|not executed|no output|omitted|placeholder|todo)\b",
    re.IGNORECASE,
)
_VERDICT_RE = re.compile(r"\b(?:PASS|FAIL|INCONCLUSIVE)\b", re.IGNORECASE)


def _first_lang_token(raw_lang: str) -> str:
    return raw_lang.strip().split(maxsplit=1)[0].lower()


def _iter_fences(content: str) -> list[_Fence]:
    fences: list[_Fence] = []
    for match in _FENCE_RE.finditer(content):
        fences.append(
            _Fence(
                lang=_first_lang_token(match.group("lang")),
                body=match.group("body"),
                start=match.start(),
                end=match.end(),
            )
        )
    return fences


def _has_substantive_block_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped in {"...", "[]", "{}", "[output]", "<output>", "PASS/FAIL"}:
        return False
    return any(char.isalnum() for char in stripped)


def _output_block_is_actual(output_body: str, intervening_text: str) -> bool:
    if _PLACEHOLDER_OUTPUT_RE.search(output_body) or _PLACEHOLDER_OUTPUT_RE.search(intervening_text):
        return False
    return _has_substantive_block_text(output_body)


def validate_verification_oracle_evidence(
    content: str,
    *,
    source_path: Path | None = None,
) -> CorrectnessValidationResult:
    """Require at least one executed code block, output block, and verdict."""

    fences = _iter_fences(content)
    evidence_count = 0
    for index, code_fence in enumerate(fences):
        if code_fence.lang not in _CODE_LANGS or not _has_substantive_block_text(code_fence.body):
            continue

        for output_fence in fences[index + 1 : index + 3]:
            if output_fence.start - code_fence.end > 1600:
                break
            if output_fence.lang in _CODE_LANGS:
                break
            intervening_text = content[code_fence.end : output_fence.start]
            has_output_marker = output_fence.lang in _OUTPUT_LANGS or _OUTPUT_LABEL_RE.search(intervening_text)
            if not has_output_marker:
                continue
            if not _output_block_is_actual(output_fence.body, intervening_text):
                continue
            verdict_window = content[code_fence.start : min(len(content), output_fence.end + 800)]
            if not _VERDICT_RE.search(verdict_window):
                continue
            evidence_count += 1
            break

    errors: list[str] = []
    if evidence_count == 0:
        errors.append(
            "computational_oracle: verification report must include at least one executed code block, "
            "actual output block, and PASS/FAIL/INCONCLUSIVE verdict"
        )

    return CorrectnessValidationResult(
        valid=not errors,
        artifact_type="verification-oracle",
        errors=errors,
        evidence_count=evidence_count,
        checked_path=str(source_path) if source_path is not None else None,
    )


_COMPARISON_KIND_VALUES = {"benchmark", "prior_work", "experiment", "cross_method", "baseline", "other"}
_OVERALL_AGREEMENT_VALUES = {"good", "marginal", "poor", "inconclusive"}


def _append_non_empty_string_error(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    value = meta.get(field_name)
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field_name}: expected a non-empty string")


def _append_string_list_errors(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    value = meta.get(field_name)
    if value is None:
        return
    if not isinstance(value, list):
        errors.append(f"{field_name}: expected a list")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field_name}[{index}]: expected a non-empty string")


def _append_numeric_field_error(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    value = meta.get(field_name)
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(float(value)):
        errors.append(f"{field_name}: expected a finite number")


def _append_comparison_sources_errors(meta: dict[str, object], errors: list[str]) -> None:
    value = meta.get("comparison_sources")
    if value is None:
        return
    if not isinstance(value, list) or not value:
        errors.append("comparison_sources: expected a non-empty list")
        return
    allowed = {"label", "kind", "path"}
    for index, source in enumerate(value):
        if not isinstance(source, dict):
            errors.append(f"comparison_sources[{index}]: expected an object")
            continue
        extra = sorted(set(source) - allowed)
        if extra:
            errors.append(f"comparison_sources[{index}]: unsupported field(s): {', '.join(extra)}")
        for field_name in ("label", "kind", "path"):
            field_value = source.get(field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                errors.append(f"comparison_sources[{index}].{field_name}: expected a non-empty string")


def validate_comparison_contract(
    content: str,
    *,
    source_path: Path | None = None,
) -> CorrectnessValidationResult:
    """Validate standalone ``GPD/comparisons/*-COMPARISON.md`` frontmatter."""

    errors: list[str] = []
    if source_path is not None and not source_path.name.endswith("-COMPARISON.md"):
        errors.append("path: comparison artifacts must be named *-COMPARISON.md")

    try:
        meta, _body = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return CorrectnessValidationResult(
            valid=False,
            artifact_type="comparison-contract",
            errors=[f"frontmatter: {exc}"],
            checked_path=str(source_path) if source_path is not None else None,
        )

    if not meta:
        errors.append("frontmatter: comparison artifact requires YAML frontmatter")

    verdict_count = 0
    if "comparison_verdicts" not in meta:
        errors.append("comparison_verdicts: required")
    else:
        try:
            verdicts = parse_comparison_verdicts_data_strict(meta.get("comparison_verdicts"))
        except (TypeError, ValueError) as exc:
            errors.append(f"comparison_verdicts: {exc}")
        else:
            verdict_count = len(verdicts)
            if verdict_count == 0:
                errors.append("comparison_verdicts: must include at least one verdict")

    comparison_kind = meta.get("comparison_kind")
    if comparison_kind is not None:
        if not isinstance(comparison_kind, str) or comparison_kind.strip() not in _COMPARISON_KIND_VALUES:
            errors.append("comparison_kind: must be one of benchmark, prior_work, experiment, cross_method, baseline, other")

    overall_agreement = meta.get("overall_agreement")
    if overall_agreement is not None:
        if not isinstance(overall_agreement, str) or overall_agreement.strip() not in _OVERALL_AGREEMENT_VALUES:
            errors.append("overall_agreement: must be one of good, marginal, poor, inconclusive")

    _append_non_empty_string_error(meta, "theory_source", errors)
    _append_non_empty_string_error(meta, "data_source", errors)
    _append_string_list_errors(meta, "protocol_bundle_ids", errors)
    _append_string_list_errors(meta, "bundle_expectations", errors)
    _append_comparison_sources_errors(meta, errors)
    for numeric_field in ("chi2_ndof", "p_value", "max_tension_sigma"):
        _append_numeric_field_error(meta, numeric_field, errors)

    experiment_marker_fields = {"theory_source", "data_source", "overall_agreement"}
    if experiment_marker_fields.intersection(meta):
        for required_field in ("theory_source", "data_source", "overall_agreement"):
            if required_field not in meta:
                errors.append(f"{required_field}: required for experiment comparisons")
        for required_field in ("chi2_ndof", "p_value", "max_tension_sigma"):
            if required_field not in meta:
                errors.append(f"{required_field}: required for experiment comparisons")

    return CorrectnessValidationResult(
        valid=not errors,
        artifact_type="comparison-contract",
        errors=errors,
        verdict_count=verdict_count,
        checked_path=str(source_path) if source_path is not None else None,
    )
