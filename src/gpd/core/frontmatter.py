"""Frontmatter parsing, schema validation, and verification helpers.

Core operations:
  extract_frontmatter / reconstruct_frontmatter / splice_frontmatter — YAML CRUD
  validate_frontmatter — schema enforcement for plan/summary/verification files
  verify_* — verification suite (summary, plan structure, phase, references, commits, artifacts)
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import (
    PROOF_ACCEPTANCE_TEST_KINDS,
    PROOF_AUDIT_REVIEWER,
    ComparisonVerdict,
    ContractResults,
    ProjectContractParseResult,
    ResearchContract,
    SuggestedContractCheck,
    claim_requires_proof_audit,
    collect_plan_contract_integrity_errors,
    collect_proof_audit_alignment_errors,
    contract_has_explicit_context_intake,
    parse_comparison_verdicts_data_strict,
    parse_contract_results_data_artifact,
    parse_project_contract_data_strict,
)
from gpd.core import knowledge_docs as _knowledge_docs
from gpd.core.constants import (
    PLAN_SUFFIX,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    SUMMARY_SUFFIX,
)
from gpd.core.contract_validation import _format_schema_error
from gpd.core.errors import GPDError
from gpd.core.observability import instrument_gpd_function
from gpd.core.root_resolution import resolve_project_root
from gpd.core.strict_yaml import load_strict_yaml
from gpd.core.tool_preflight import PlanToolPreflightError, parse_plan_tool_requirements
from gpd.core.utils import (
    matching_phase_artifact_count,
    normalize_ascii_slug,
    phase_artifact_display_name,
    phase_artifact_id,
    safe_read_file,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Exceptions
    "FrontmatterParseError",
    "FrontmatterValidationError",
    # Core parsing
    "extract_frontmatter",
    "reconstruct_frontmatter",
    "splice_frontmatter",
    "deep_merge_frontmatter",
    "parse_contract_block",
    "compute_knowledge_reviewed_content_sha256",
    # Schema validation
    "FRONTMATTER_SCHEMAS",
    "FrontmatterValidation",
    "validate_frontmatter",
    "validate_knowledge_frontmatter",
    # Verification result types
    "FileCheckResult",
    "SummaryVerification",
    "TaskInfo",
    "PlanValidation",
    "PhaseCompleteness",
    "ReferenceVerification",
    "CommitVerification",
    "ArtifactCheck",
    "ArtifactVerification",
    # Verification implementations
    "verify_summary",
    "verify_plan_structure",
    "verify_phase_completeness",
    "verify_references",
    "verify_commits",
    "verify_artifacts",
]

PLAN_FRONTMATTER_TYPES = ("execute", "tdd")
SUMMARY_DEPTH_VALUES = ("minimal", "standard", "full", "complex")
VERIFICATION_REPORT_STATUSES = ("passed", "gaps_found", "expert_needed", "human_needed")
KNOWLEDGE_GATE_VALUES = ("off", "warn", "block")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FrontmatterParseError(GPDError, ValueError):
    """YAML frontmatter block is syntactically invalid."""


class FrontmatterValidationError(GPDError, ValueError):
    """Frontmatter fails schema validation."""


# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)")
_EMPTY_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n---[ \t]*(?:\r?\n|$)")
_LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE = re.compile(r"^(?:[ \t]*\r?\n)+(?=---[ \t]*\r?\n)")

# Matches the full frontmatter block (including empty) for replacement operations.
# Uses a lookahead so the trailing newline is preserved for the caller to reattach.
_FRONTMATTER_BLOCK_RE = re.compile(r"^---[ \t]*\r?\n(?:[\s\S]*?\r?\n)?---[ \t]*(?=\r?\n|$)")


def _split_frontmatter_rewrite_content(content: str) -> tuple[str, str]:
    """Return any preserved leading prefix plus rewriteable content."""
    bom = "\ufeff" if content.startswith("\ufeff") else ""
    clean = content[len(bom) :]
    prefix_match = _LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE.match(clean)
    if prefix_match is None:
        return bom, clean
    return bom + clean[: prefix_match.end()], clean[prefix_match.end() :]


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown content.

    Returns ``(meta, body)`` where *meta* is the parsed YAML dict and *body*
    is everything after the closing ``---`` delimiter.

    If no frontmatter block is found, returns ``({}, content)``.

    Raises:
        FrontmatterParseError: If the YAML inside the ``---`` block is malformed.
    """
    clean = content.lstrip("\ufeff")  # strip BOM
    frontmatter_candidate = _LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE.sub("", clean, count=1)

    match = _FRONTMATTER_RE.match(frontmatter_candidate)
    if match:
        yaml_str = match.group(1)
        body = frontmatter_candidate[match.end() :]
        try:
            meta = load_strict_yaml(yaml_str)
            if meta is None:
                meta = {}
        except yaml.YAMLError as exc:
            raise FrontmatterParseError(str(exc)) from exc
        if not isinstance(meta, dict):
            raise FrontmatterParseError(f"Expected mapping, got {type(meta).__name__}")
        return meta, body

    # Empty frontmatter (---\n---)
    match = _EMPTY_FRONTMATTER_RE.match(frontmatter_candidate)
    if match:
        return {}, frontmatter_candidate[match.end() :]

    # No frontmatter at all
    return {}, clean


def _dump_yaml(meta: dict) -> str:
    """Dump *meta* to a YAML string (without ``---`` delimiters)."""
    return yaml.dump(
        meta,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=999999,
    ).rstrip()


def reconstruct_frontmatter(meta: dict, body: str) -> str:
    """Rebuild full markdown from *meta* dict and *body* text.

    Always uses ``\\n`` line endings regardless of input.
    """
    yaml_str = _dump_yaml(meta)
    return f"---\n{yaml_str}\n---\n\n{body}"


def splice_frontmatter(content: str, updates: dict) -> str:
    """Replace frontmatter fields in *content* with values from *updates*.

    Preserves the body and detects CRLF vs LF line endings from the original
    content.  If *content* has no frontmatter block, one is prepended.
    """
    meta, _body = extract_frontmatter(content)
    meta.update(updates)

    eol = "\r\n" if "\r\n" in content else "\n"
    yaml_str = _dump_yaml(meta)

    prefix, rewriteable = _split_frontmatter_rewrite_content(content)
    fm_match = _FRONTMATTER_BLOCK_RE.match(rewriteable)
    if fm_match:
        return prefix + f"---{eol}{yaml_str}{eol}---" + rewriteable[fm_match.end() :]
    return prefix + f"---{eol}{yaml_str}{eol}---{eol}{eol}" + rewriteable


def deep_merge_frontmatter(content: str, merge_data: dict) -> str:
    """Merge *merge_data* into existing frontmatter (one level deep).

    For each key in *merge_data*: if both the existing value and the new
    value are plain dicts (not lists or other types), their top-level
    entries are merged via ``dict.update`` — nested sub-dicts within those
    values are **not** merged recursively; they are replaced wholesale.
    For all other types the new value overwrites the existing one.
    """
    meta, _ = extract_frontmatter(content)
    for key, val in merge_data.items():
        existing = meta.get(key)
        if isinstance(val, dict) and isinstance(existing, dict):
            existing.update(val)
        else:
            meta[key] = val

    eol = "\r\n" if "\r\n" in content else "\n"
    yaml_str = _dump_yaml(meta)

    prefix, rewriteable = _split_frontmatter_rewrite_content(content)
    fm_match = _FRONTMATTER_BLOCK_RE.match(rewriteable)
    if fm_match:
        return prefix + f"---{eol}{yaml_str}{eol}---" + rewriteable[fm_match.end() :]
    return prefix + f"---{eol}{yaml_str}{eol}---{eol}{eol}" + rewriteable


@dataclass(slots=True)
class _PlanContractResolution:
    contract: ResearchContract | None = None
    errors: list[str] = field(default_factory=list)


def _format_pydantic_validation_errors(exc: PydanticValidationError) -> list[str]:
    """Return concise field-level validation errors."""

    messages: list[str] = []
    seen: set[str] = set()
    for error in exc.errors():
        formatted = _format_schema_error(error)
        if formatted in seen:
            continue
        seen.add(formatted)
        messages.append(formatted)
    return messages or [str(exc)]


def _prefixed_validation_errors(field_name: str, exc: Exception) -> list[str]:
    """Return user-facing validation errors prefixed by the frontmatter field name."""

    if isinstance(exc, PydanticValidationError):
        return [f"{field_name}: {message}" for message in _format_pydantic_validation_errors(exc)]
    return [f"{field_name}: {exc}"]


def _source_path_project_root(source_path: Path | None) -> Path | None:
    """Return the project root inferred from a file source path, when available."""

    if source_path is None:
        return None
    return resolve_project_root(source_path.parent, require_layout=False)


def _normalize_frontmatter_contract_mapping(contract_data: object) -> object:
    """Normalize frontmatter-authored blank nested proof-list scalars to empty lists."""

    if not isinstance(contract_data, dict):
        return contract_data

    normalized = deepcopy(contract_data)
    claims = normalized.get("claims")
    if not isinstance(claims, list):
        return normalized

    for claim in claims:
        if not isinstance(claim, dict):
            continue
        parameters = claim.get("parameters")
        if isinstance(parameters, list):
            for parameter in parameters:
                if (
                    isinstance(parameter, dict)
                    and isinstance(parameter.get("aliases"), str)
                    and not parameter["aliases"].strip()
                ):
                    parameter["aliases"] = []
        hypotheses = claim.get("hypotheses")
        if isinstance(hypotheses, list):
            for hypothesis in hypotheses:
                if (
                    isinstance(hypothesis, dict)
                    and isinstance(hypothesis.get("symbols"), str)
                    and not hypothesis["symbols"].strip()
                ):
                    hypothesis["symbols"] = []
    return normalized


def _validate_contract_mapping(
    contract_data: object,
    *,
    enforce_plan_semantics: bool,
    project_root: Path | None = None,
) -> _PlanContractResolution:
    """Return validated contract data plus explicit strict/semantic errors."""

    if not isinstance(contract_data, dict):
        return _PlanContractResolution(errors=["expected an object"])

    normalized_contract_data = _normalize_frontmatter_contract_mapping(contract_data)
    strict_result: ProjectContractParseResult = parse_project_contract_data_strict(normalized_contract_data)
    if strict_result.errors:
        return _PlanContractResolution(errors=list(dict.fromkeys(strict_result.errors)))

    contract = strict_result.contract
    if contract is None:
        return _PlanContractResolution(errors=["contract could not be normalized"])

    if not enforce_plan_semantics:
        return _PlanContractResolution(contract=contract)

    semantic_errors: list[str] = []
    if "context_intake" not in contract_data:
        semantic_errors.append("missing context_intake")
    elif not contract_has_explicit_context_intake(contract, project_root=project_root):
        semantic_errors.append("context_intake must not be empty")
    for error in _collect_plan_contract_explicit_field_errors(contract_data):
        if error not in semantic_errors:
            semantic_errors.append(error)
    for error in collect_plan_contract_integrity_errors(contract, project_root=project_root):
        if error not in semantic_errors:
            semantic_errors.append(error)
    if semantic_errors:
        return _PlanContractResolution(errors=semantic_errors)
    return _PlanContractResolution(contract=contract)


def parse_contract_block(content: str, *, source_path: Path | None = None) -> ResearchContract | None:
    """Extract and validate the optional ``contract`` block from frontmatter."""

    meta, _ = extract_frontmatter(content)
    if "contract" not in meta:
        return None
    resolution = _validate_contract_mapping(
        meta.get("contract"),
        enforce_plan_semantics=True,
        project_root=_source_path_project_root(source_path),
    )
    if resolution.errors:
        raise FrontmatterValidationError(
            "Invalid contract frontmatter: " + "; ".join(resolution.errors)
        )
    return resolution.contract


# ---------------------------------------------------------------------------
# Schema definitions and validation
# ---------------------------------------------------------------------------

FRONTMATTER_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "plan": {
        "required": [
            "phase",
            "plan",
            "type",
            "wave",
            "depends_on",
            "files_modified",
            "interactive",
            "conventions",
            "contract",
        ],
    },
    "summary": {
        "required": ["phase", "plan", "depth", "provides", "completed"],
    },
    "verification": {
        "required": ["phase", "verified", "status", "score"],
    },
    "knowledge": {
        "required": [
            "knowledge_schema_version",
            "knowledge_id",
            "title",
            "topic",
            "status",
            "created_at",
            "updated_at",
            "sources",
            "coverage_summary",
        ],
    },
}


def validate_knowledge_frontmatter(
    content: str,
    source_path: Path | None = None,
) -> FrontmatterValidation:
    """Validate knowledge frontmatter against the strict knowledge-doc schema."""

    meta, body = extract_frontmatter(content)
    required = FRONTMATTER_SCHEMAS["knowledge"]["required"]
    missing = [f for f in required if _resolve_field(meta, f) is None]
    present = [f for f in required if _resolve_field(meta, f) is not None]

    errors: list[str] = []

    unknown_fields = sorted(set(meta) - _KNOWLEDGE_TOP_LEVEL_FIELDS)
    for field_name in unknown_fields:
        errors.append(f"knowledge.{field_name}: unsupported field")

    if meta.get("knowledge_schema_version") != 1:
        errors.append("knowledge.knowledge_schema_version: must be the literal integer 1")

    _validate_knowledge_string_field(meta, "knowledge_id", errors)
    knowledge_id = meta.get("knowledge_id")
    if isinstance(knowledge_id, str):
        slug = knowledge_id.strip()
        if not slug.startswith("K-") or not slug[2:] or normalize_ascii_slug(slug[2:]) != slug[2:]:
            errors.append("knowledge.knowledge_id: must use canonical K-{ascii-hyphen-slug} format")

    _validate_knowledge_string_field(meta, "title", errors)
    _validate_knowledge_string_field(meta, "topic", errors)

    status = meta.get("status")
    if not isinstance(status, str) or not status.strip():
        errors.append("knowledge.status: expected a non-empty string")
        status_value = ""
    else:
        status_value = status.strip()
        if status_value not in _KNOWLEDGE_STATUS_VALUES:
            errors.append("knowledge.status: must be one of draft, in_review, stable, superseded")

    created_at = _validate_knowledge_datetime_field(meta, "created_at", errors)
    updated_at = _validate_knowledge_datetime_field(meta, "updated_at", errors)
    if created_at is not None and updated_at is not None and updated_at < created_at:
        errors.append("knowledge.updated_at must be on or after knowledge.created_at")

    sources = meta.get("sources")
    if not isinstance(sources, list):
        errors.append("knowledge.sources: expected a list")
        sources = []
    elif not sources:
        errors.append("knowledge.sources: must contain at least one source record")
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"knowledge.sources[{index}]: expected an object")
            continue
        allowed_source_fields = {
            "source_id",
            "kind",
            "locator",
            "title",
            "why_it_matters",
            "source_artifacts",
            "reference_id",
            "arxiv_id",
            "doi",
            "url",
        }
        for field_name in sorted(set(source) - allowed_source_fields):
            errors.append(f"knowledge.sources[{index}].{field_name}: unsupported field")
        _validate_knowledge_string_field(source, "source_id", errors)
        _validate_knowledge_string_field(source, "locator", errors)
        _validate_knowledge_string_field(source, "title", errors)
        _validate_knowledge_string_field(source, "why_it_matters", errors)
        source_kind = source.get("kind")
        if source_kind is not None:
            if not isinstance(source_kind, str) or not source_kind.strip():
                errors.append(f"knowledge.sources[{index}].kind: expected a non-empty string")
            elif source_kind.strip() not in ("paper", "dataset", "prior_artifact", "spec", "website", "other"):
                errors.append(
                    f"knowledge.sources[{index}].kind: must be one of paper, dataset, prior_artifact, spec, website, other"
                )
        source_artifacts = source.get("source_artifacts", [])
        if source_artifacts is not None:
            if not isinstance(source_artifacts, list):
                errors.append(f"knowledge.sources[{index}].source_artifacts: expected a list")
            else:
                for artifact_index, artifact in enumerate(source_artifacts):
                    if not isinstance(artifact, str) or not artifact.strip():
                        errors.append(
                            f"knowledge.sources[{index}].source_artifacts[{artifact_index}]: expected a non-empty string"
                        )
                    elif Path(artifact).is_absolute():
                        errors.append(
                            f"knowledge.sources[{index}].source_artifacts[{artifact_index}]: must be project-relative"
                        )
        for optional_field in ("reference_id", "arxiv_id", "doi", "url"):
            optional_value = source.get(optional_field)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                errors.append(f"knowledge.sources[{index}].{optional_field}: expected a string")

    coverage_summary = meta.get("coverage_summary")
    if not isinstance(coverage_summary, dict):
        errors.append("knowledge.coverage_summary: expected an object")
    else:
        allowed_summary_fields = {"covered_topics", "excluded_topics", "open_gaps"}
        for field_name in sorted(set(coverage_summary) - allowed_summary_fields):
            errors.append(f"knowledge.coverage_summary.{field_name}: unsupported field")
        for field_name in ("covered_topics", "excluded_topics", "open_gaps"):
            _validate_knowledge_string_list_field(
                coverage_summary.get(field_name),
                field_name=f"coverage_summary.{field_name}",
                errors=errors,
            )

    review = meta.get("review")
    current_content_sha256 = compute_knowledge_reviewed_content_sha256(content)
    if status_value == "draft":
        if review is not None:
            errors.append("knowledge.review is forbidden when status is draft")
    elif status_value == "in_review":
        if review is not None:
            _validate_knowledge_review_block(
                review,
                status=status_value,
                current_content_sha256=current_content_sha256,
                errors=errors,
            )
    elif status_value == "stable":
        if review is None:
            errors.append("knowledge.review is required when status is stable")
        else:
            _validate_knowledge_review_block(
                review,
                status=status_value,
                current_content_sha256=current_content_sha256,
                errors=errors,
            )
    elif status_value == "superseded":
        if review is not None:
            _validate_knowledge_review_block(
                review,
                status=status_value,
                current_content_sha256=current_content_sha256,
                errors=errors,
            )

        superseded_by = meta.get("superseded_by")
        if not isinstance(superseded_by, str) or not superseded_by.strip():
            errors.append("knowledge.superseded_by: expected a non-empty string")
        else:
            slug = superseded_by.strip()
            if not slug.startswith("K-") or not slug[2:] or normalize_ascii_slug(slug[2:]) != slug[2:]:
                errors.append("knowledge.superseded_by: must use canonical K-{ascii-hyphen-slug} format")
            if slug == knowledge_id:
                errors.append("knowledge.superseded_by must reference a different knowledge_id")
    else:
        if meta.get("superseded_by") is not None:
            errors.append(f"knowledge.superseded_by is forbidden when status is {status_value or 'invalid'}")

    if status_value in {"draft", "in_review", "stable"} and meta.get("superseded_by") is not None:
        errors.append(f"knowledge.superseded_by is forbidden when status is {status_value}")

    if source_path is not None and source_path.stem != str(knowledge_id or ""):
        errors.append(
            f"knowledge_id must match the filename stem ({source_path.stem!r} != {knowledge_id!r})"
        )

    return FrontmatterValidation(
        valid=len(missing) == 0 and not errors,
        missing=missing,
        present=present,
        errors=errors,
        schema_name="knowledge",
    )


UNSUPPORTED_FRONTMATTER_FIELDS: dict[str, dict[str, str]] = {
    "plan": {
        "must_haves": "must_haves is not part of the contract-first plan schema; encode verification targets in contract claims, deliverables, links, references, and acceptance_tests",
        "verification_inputs": "verification_inputs is not part of the contract-first plan schema; capture execution inputs in the contract block instead",
        "contract_evidence": "contract_evidence is not part of the contract-first plan schema; plans must declare claims, deliverables, and acceptance tests instead",
        "contract_results": "contract_results is summary/verification output, not plan input; keep plans contract-first",
        "comparison_verdicts": "comparison_verdicts belong to completed summaries, not plans",
        "suggested_contract_checks": "suggested_contract_checks is verification-only; plans must define acceptance_tests in the contract instead",
    },
    "summary": {
        "must_haves": "must_haves is not part of the contract-first summary schema; use contract_results and comparison_verdicts instead",
        "verification_inputs": "verification_inputs is not part of the contract-first summary schema; use contract_results and comparison_verdicts instead",
        "contract_evidence": "contract_evidence is not part of the contract-first summary schema; use contract_results instead",
        "suggested_contract_checks": "suggested_contract_checks is verification-only; summaries use contract_results and comparison_verdicts instead",
    },
    "verification": {
        "must_haves": "must_haves is not part of the contract-first verification schema; use contract_results and comparison_verdicts instead",
        "verification_inputs": "verification_inputs is not part of the contract-first verification schema; use contract_results and comparison_verdicts instead",
        "contract_evidence": "contract_evidence is not part of the contract-first verification schema; use contract_results instead",
        "independently_confirmed": "independently_confirmed is not part of the contract-first verification schema; keep aggregate confirmation counts in body prose instead",
    },
}

_DECISIVE_EXTERNAL_COMPARISON_KINDS = frozenset({"benchmark", "prior_work", "experiment", "baseline"})
_DECISIVE_REFERENCE_COMPARISON_KINDS = frozenset({"benchmark", "prior_work", "experiment", "cross_method", "baseline"})
_DECISIVE_ACCEPTANCE_TEST_COMPARISON_KINDS: dict[str, frozenset[str]] = {
    "benchmark": frozenset({"benchmark"}),
    "cross_method": frozenset({"cross_method"}),
}
# Plan contracts can omit collection fields that already have safe closed-vocabulary
# defaults in the schema models; downstream validation should stabilize them rather
# than reject otherwise valid model output for restating "other".
_PLAN_CONTRACT_EXPLICIT_COLLECTION_FIELDS: tuple[tuple[str, str], ...] = ()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_KNOWLEDGE_STATUS_VALUES = ("draft", "in_review", "stable", "superseded")
_KNOWLEDGE_TOP_LEVEL_FIELDS = {
    "knowledge_schema_version",
    "knowledge_id",
    "title",
    "topic",
    "status",
    "created_at",
    "updated_at",
    "sources",
    "coverage_summary",
    "review",
    "superseded_by",
}
_KNOWLEDGE_REVIEW_CANONICAL_FIELDS = {
    "reviewed_at",
    "review_round",
    "reviewer_kind",
    "reviewer_id",
    "decision",
    "summary",
    "approval_artifact_path",
    "approval_artifact_sha256",
    "reviewed_content_sha256",
    "stale",
}
_KNOWLEDGE_REVIEW_LEGACY_FIELDS = {
    "reviewed_at",
    "reviewer",
    "decision",
    "summary",
    "evidence_path",
    "evidence_sha256",
    "audit_artifact_path",
    "commit_sha",
    "trace_id",
}
_KNOWLEDGE_REVIEW_DECISION_VALUES = ("approved", "needs_changes", "rejected")
def _parse_iso8601_datetime(value: object) -> datetime | None:
    """Parse an ISO 8601 timestamp or return ``None`` when invalid."""

    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_lower_hex_sha256(value: object) -> bool:
    """Return True when *value* is a lowercase SHA-256 digest string."""

    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(
        character in "0123456789abcdef" for character in value
    )


def _validate_knowledge_string_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append an error when a required field is not a non-empty string."""

    value = meta.get(field_name)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"knowledge.{field_name}: expected a non-empty string")


def _validate_knowledge_string_list_field(
    value: object,
    *,
    field_name: str,
    errors: list[str],
) -> None:
    """Append an error when a field is not a list of non-empty strings."""

    if not isinstance(value, list):
        errors.append(f"knowledge.{field_name}: expected a list")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"knowledge.{field_name}: entry {index} must be a non-empty string")


def _validate_knowledge_datetime_field(meta: dict[str, object], field_name: str, errors: list[str]) -> datetime | None:
    """Append an error when a required field is not an ISO 8601 timestamp."""

    value = meta.get(field_name)
    parsed = _parse_iso8601_datetime(value)
    if parsed is None:
        errors.append(f"knowledge.{field_name}: expected an ISO 8601 timestamp")
    return parsed


def _validate_knowledge_sha256_field(meta: dict[str, object], field_name: str, errors: list[str]) -> str | None:
    """Append an error when a required field is not a lowercase SHA-256 digest."""

    value = meta.get(field_name)
    if not _is_lower_hex_sha256(value):
        errors.append(f"knowledge.review.{field_name}: expected a lowercase 64-hex sha256 digest")
        return None
    return str(value)


def _validate_knowledge_project_relative_path(
    meta: dict[str, object],
    field_name: str,
    errors: list[str],
) -> str | None:
    """Append an error when a required field is not a project-relative path."""

    value = meta.get(field_name)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"knowledge.review.{field_name}: expected a non-empty string")
        return None
    stripped = value.strip()
    if Path(stripped).is_absolute():
        errors.append(f"knowledge.review.{field_name}: must be a project-relative path")
        return None
    return stripped


def _knowledge_review_uses_canonical_contract(review: dict[str, object]) -> bool:
    """Return whether the review block is using the Step 4 contract shape."""

    return bool(set(review) & (_KNOWLEDGE_REVIEW_CANONICAL_FIELDS - _KNOWLEDGE_REVIEW_LEGACY_FIELDS))


def _validate_knowledge_review_block(
    review: object,
    *,
    status: str,
    current_content_sha256: str,
    errors: list[str],
) -> None:
    """Validate the knowledge review block against the requested lifecycle state."""

    if not isinstance(review, dict):
        errors.append("knowledge.review: expected an object")
        return

    review_field_names = set(review)
    allowed_fields = _KNOWLEDGE_REVIEW_CANONICAL_FIELDS | _KNOWLEDGE_REVIEW_LEGACY_FIELDS
    unknown_fields = sorted(review_field_names - allowed_fields)
    for field_name in unknown_fields:
        errors.append(f"knowledge.review.{field_name}: unsupported field")

    reviewed_at = _validate_knowledge_datetime_field(review, "reviewed_at", errors)
    decision = review.get("decision")
    if not isinstance(decision, str) or not decision.strip():
        errors.append("knowledge.review.decision: expected a non-empty string")
        decision_value = None
    else:
        decision_value = decision.strip()
        if decision_value not in _KNOWLEDGE_REVIEW_DECISION_VALUES:
            errors.append("knowledge.review.decision: must be one of approved, needs_changes, rejected")

    summary = review.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("knowledge.review.summary: expected a non-empty string")

    canonical_contract = _knowledge_review_uses_canonical_contract(review)

    if canonical_contract:
        if not isinstance(review.get("reviewer_kind"), str) or not review.get("reviewer_kind", "").strip():
            errors.append("knowledge.review.reviewer_kind: expected a non-empty string")
        if not isinstance(review.get("reviewer_id"), str) or not review.get("reviewer_id", "").strip():
            errors.append("knowledge.review.reviewer_id: expected a non-empty string")
        if reviewed_at is None:
            errors.append("knowledge.review.reviewed_at: expected an ISO 8601 timestamp")
        review_round = review.get("review_round")
        if type(review_round) is not int or review_round < 1:
            errors.append("knowledge.review.review_round: expected an integer >= 1")
        _validate_knowledge_project_relative_path(review, "approval_artifact_path", errors)
        _validate_knowledge_sha256_field(review, "approval_artifact_sha256", errors)
        if _validate_knowledge_sha256_field(review, "reviewed_content_sha256", errors) is None and review.get(
            "reviewed_content_sha256"
        ) is not None:
            errors.append("knowledge.review.approval_artifact_sha256: expected a lowercase 64-hex sha256 digest")
        stale = review.get("stale")
        if type(stale) is not bool:
            errors.append("knowledge.review.stale: expected a boolean")
    else:
        if not isinstance(review.get("reviewer"), str) or not review.get("reviewer", "").strip():
            errors.append("knowledge.review.reviewer: expected a non-empty string")
        if reviewed_at is None:
            errors.append("knowledge.review.reviewed_at: expected an ISO 8601 timestamp")
        evidence_path = review.get("evidence_path")
        audit_artifact_path = review.get("audit_artifact_path")
        commit_sha = review.get("commit_sha")
        trace_id = review.get("trace_id")
        if not any(
            isinstance(value, str) and value.strip()
            for value in (evidence_path, audit_artifact_path, commit_sha, trace_id)
        ):
            errors.append(
                "knowledge.review: requires at least one concrete evidence pointer: "
                "evidence_path, audit_artifact_path, commit_sha, or trace_id"
            )
        evidence_sha256 = review.get("evidence_sha256")
        if evidence_sha256 is not None and not _is_lower_hex_sha256(evidence_sha256):
            errors.append("knowledge.review.evidence_sha256: expected a lowercase 64-hex sha256 digest")
        if audit_artifact_path is not None and (
            not isinstance(audit_artifact_path, str) or not audit_artifact_path.strip() or Path(audit_artifact_path).is_absolute()
        ):
            errors.append("knowledge.review.audit_artifact_path: must be a project-relative path")
        # Legacy review records do not carry the Step 4 freshness contract.
        if review.get("stale") is not None and type(review.get("stale")) is not bool:
            errors.append("knowledge.review.stale: expected a boolean")

    if decision_value == "approved":
        if status == "draft":
            errors.append("knowledge.review.decision: approved review is forbidden when status is draft")
        elif status == "in_review":
            if canonical_contract:
                if review.get("stale") is not True:
                    errors.append("knowledge.review.stale: approved in_review docs must be marked stale: true")
            elif review.get("stale") is False:
                errors.append("knowledge.review.stale: approved in_review docs must be marked stale: true")
        elif status == "stable":
            if canonical_contract:
                if review.get("stale") is not False:
                    errors.append("knowledge.review.stale: approved stable docs must be marked stale: false")
                if not isinstance(review.get("approval_artifact_path"), str) or not review.get("approval_artifact_path", "").strip():
                    errors.append("knowledge.review.approval_artifact_path: expected a project-relative path")
                if not _is_lower_hex_sha256(review.get("approval_artifact_sha256")):
                    errors.append("knowledge.review.approval_artifact_sha256: expected a lowercase 64-hex sha256 digest")
                if not _is_lower_hex_sha256(review.get("reviewed_content_sha256")):
                    errors.append("knowledge.review.reviewed_content_sha256: expected a lowercase 64-hex sha256 digest")
                if review.get("reviewed_content_sha256") is not None and review.get("reviewed_content_sha256") != current_content_sha256:
                    errors.append(
                        "knowledge.review.reviewed_content_sha256 does not match the current trusted content hash"
                    )
            else:
                # Legacy stable records remain accepted for backward compatibility, but they do not
                # participate in the Step 4 freshness contract.
                if not any(
                    isinstance(value, str) and value.strip()
                    for value in (
                        review.get("evidence_path"),
                        review.get("audit_artifact_path"),
                        review.get("commit_sha"),
                        review.get("trace_id"),
                    )
                ):
                    errors.append(
                        "knowledge.review: requires at least one concrete evidence pointer: "
                        "evidence_path, audit_artifact_path, commit_sha, or trace_id"
                    )
    if status == "stable" and not canonical_contract:
        if review is None:
            errors.append("knowledge.review is required when status is stable")
        elif decision_value != "approved":
            errors.append("knowledge.review.decision must be approved when status is stable")
    if status == "in_review" and review is not None and canonical_contract and decision_value == "approved" and review.get("stale") is not True:
        errors.append("knowledge.review.stale: approved in_review docs must be marked stale: true")


def _knowledge_reviewed_content_projection(meta: dict[str, object], body: str) -> dict[str, object]:
    """Return the canonical content projection used for knowledge freshness hashing."""

    return {
        "knowledge_schema_version": meta.get("knowledge_schema_version"),
        "knowledge_id": meta.get("knowledge_id"),
        "title": meta.get("title"),
        "topic": meta.get("topic"),
        "sources": meta.get("sources"),
        "coverage_summary": meta.get("coverage_summary"),
        "body": body.replace("\r\n", "\n"),
    }


def _normalize_knowledge_review_inputs(
    knowledge_doc_or_content: object,
    *,
    body_text: str = "",
    meta: dict[str, object] | None = None,
    body: str | None = None,
) -> tuple[dict[str, object], str]:
    """Return ``(meta, body_text)`` for any supported knowledge-review input form."""

    effective_body = body_text or (body if body is not None else "")
    if meta is not None:
        if not isinstance(meta, dict):
            raise TypeError("meta must be a mapping")
        return meta, effective_body
    if isinstance(knowledge_doc_or_content, str):
        extracted_meta, extracted_body = extract_frontmatter(knowledge_doc_or_content)
        return extracted_meta, effective_body or extracted_body
    if isinstance(knowledge_doc_or_content, dict):
        return knowledge_doc_or_content, effective_body
    if hasattr(knowledge_doc_or_content, "model_dump"):
        return knowledge_doc_or_content.model_dump(mode="python"), effective_body
    raise TypeError("expected a knowledge document, content string, or metadata mapping")


def compute_knowledge_reviewed_content_sha256(
    knowledge_doc_or_content: object,
    *,
    body_text: str = "",
    meta: dict[str, object] | None = None,
    body: str | None = None,
) -> str:
    """Compute the canonical hash of the trust-bearing knowledge-doc projection."""

    normalized_meta, normalized_body = _normalize_knowledge_review_inputs(
        knowledge_doc_or_content,
        body_text=body_text,
        meta=meta,
        body=body,
    )
    projection = _knowledge_reviewed_content_projection(normalized_meta, normalized_body)
    encoded = json.dumps(projection, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return _sha256_text(encoded)


def _compat_knowledge_reviewed_content_projection(
    knowledge_doc_or_content: object,
    *,
    body_text: str = "",
    meta: dict[str, object] | None = None,
    body: str | None = None,
) -> dict[str, object]:
    """Compatibility wrapper for the knowledge-doc projection helper."""

    normalized_meta, normalized_body = _normalize_knowledge_review_inputs(
        knowledge_doc_or_content,
        body_text=body_text,
        meta=meta,
        body=body,
    )
    return _knowledge_reviewed_content_projection(normalized_meta, normalized_body)


_knowledge_docs.compute_knowledge_reviewed_content_sha256 = compute_knowledge_reviewed_content_sha256
_knowledge_docs.knowledge_reviewed_content_projection = _compat_knowledge_reviewed_content_projection


def _resolve_contract_artifact_path(
    *,
    project_root: Path | None,
    artifact_dir: Path | None,
    path_text: str,
) -> tuple[Path | None, str | None]:
    artifact_path = Path(path_text)
    if artifact_path.is_absolute():
        return None, "must be a project-relative path"

    anchor_dir = artifact_dir or project_root
    if anchor_dir is None:
        return artifact_path, None

    resolved_root = (project_root or anchor_dir).resolve(strict=False)
    candidate = (anchor_dir / artifact_path).resolve(strict=False)
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None, "must resolve inside the project root"
    return candidate, None


class FrontmatterValidation(BaseModel):
    """Result of frontmatter schema validation."""

    valid: bool
    missing: list[str] = Field(default_factory=list)
    present: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    schema_name: str = ""


def _resolve_field(meta: dict, name: str) -> str | None:
    """Return *name* when present in *meta*, otherwise ``None``."""
    return name if name in meta else None


def _validate_required_string_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append an error when a required field is not a non-empty string."""
    if field_name not in meta:
        return
    value = meta.get(field_name)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field_name}: expected a non-empty string")


def _validate_required_scalar_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append an error when a required field is not a non-null scalar."""
    if field_name not in meta:
        return
    value = meta.get(field_name)
    if value is None or isinstance(value, (list, dict, bool)):
        errors.append(f"{field_name}: expected a non-null scalar")


def _validate_required_int_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append an error when a required field is not a strict integer."""
    if field_name not in meta:
        return
    if type(meta.get(field_name)) is not int:
        errors.append(f"{field_name}: expected an integer")


def _validate_required_bool_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append an error when a required field is not a strict boolean."""
    if field_name not in meta:
        return
    if type(meta.get(field_name)) is not bool:
        errors.append(f"{field_name}: expected a boolean")


def _validate_required_object_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append an error when a required field is not an object."""
    if field_name not in meta:
        return
    if not isinstance(meta.get(field_name), dict):
        errors.append(f"{field_name}: expected an object")


def _validate_string_enum_field(
    meta: dict[str, object],
    field_name: str,
    errors: list[str],
    *,
    allowed_values: tuple[str, ...],
) -> None:
    """Append an error when a required string field uses an undocumented literal."""

    if field_name not in meta:
        return
    value = meta.get(field_name)
    if not isinstance(value, str) or not value.strip():
        return
    if value.strip() not in allowed_values:
        errors.append(f"{field_name}: must be one of {', '.join(allowed_values)}")


def _validate_timestamp_scalar_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append an error when a scalar field is not an ISO 8601 timestamp."""

    if field_name not in meta:
        return
    value = meta.get(field_name)
    if value is None or isinstance(value, (list, dict, bool)):
        return
    if isinstance(value, datetime):
        return
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or "T" not in stripped.upper():
            errors.append(f"{field_name}: expected an ISO 8601 timestamp")
            return
        try:
            datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{field_name}: expected an ISO 8601 timestamp")
        return
    errors.append(f"{field_name}: expected an ISO 8601 timestamp")


def _collect_plan_contract_explicit_field_errors(contract_data: dict[str, object]) -> list[str]:
    """Return missing semantic fields that lack safe schema defaults.

    Defaultable ``kind`` / ``role`` / ``relation`` fields are intentionally
    excluded here so omitted values normalize through the contract model
    instead of failing plan validation for restating the safe ``other`` default.
    """

    errors: list[str] = []
    for collection_name, field_name in _PLAN_CONTRACT_EXPLICIT_COLLECTION_FIELDS:
        raw_collection = contract_data.get(collection_name)
        if not isinstance(raw_collection, list):
            continue
        for index, item in enumerate(raw_collection):
            if not isinstance(item, dict):
                continue
            if field_name not in item:
                errors.append(f"{collection_name}.{index}.{field_name} must be explicit in plan contracts")
    return errors


def _parse_contract_results(meta: dict) -> ContractResults | None:
    """Parse a summary contract-results block when present."""
    if "contract_results" not in meta:
        return None
    raw = meta.get("contract_results")
    return parse_contract_results_data_artifact(raw)


def _parse_comparison_verdicts(meta: dict) -> list[ComparisonVerdict]:
    """Parse the optional summary comparison-verdict ledger."""
    return parse_comparison_verdicts_data_strict(meta.get("comparison_verdicts"))


def _parse_suggested_contract_checks(meta: dict) -> list[SuggestedContractCheck]:
    """Parse the optional structured verification suggestions."""
    raw = meta.get("suggested_contract_checks")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("expected a list")
    suggestions: list[SuggestedContractCheck] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError("entries must be objects")
        try:
            suggestions.append(SuggestedContractCheck.model_validate(item))
        except PydanticValidationError as exc:
            details = "; ".join(
                (
                    f"[{index}] must provide suggested_subject_kind and suggested_subject_id together"
                    if "suggested_subject_kind and suggested_subject_id must appear together" in message
                    else f"[{index}] {message}"
                )
                for message in _format_pydantic_validation_errors(exc)
            )
            raise ValueError(details) from exc
    return suggestions


def _unsupported_frontmatter_errors(schema_name: str, meta: dict[str, object]) -> list[str]:
    """Return explicit errors for unsupported frontmatter fields."""
    return [
        f"{unsupported_field}: {message}"
        for unsupported_field, message in UNSUPPORTED_FRONTMATTER_FIELDS.get(schema_name, {}).items()
        if unsupported_field in meta
    ]


def _validate_non_empty_string_list_field(meta: dict[str, object], field_name: str, errors: list[str]) -> None:
    """Append validation errors when a field is not a list of non-empty strings."""
    if field_name not in meta:
        return
    value = meta.get(field_name)
    if not isinstance(value, list):
        errors.append(f"{field_name}: expected a list")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field_name}: entry {index} must be a non-empty string")


def _validate_knowledge_deps_field(meta: dict[str, object], errors: list[str]) -> None:
    """Append validation errors for the optional top-level ``knowledge_deps`` field."""

    field_name = "knowledge_deps"
    if field_name not in meta:
        return
    value = meta.get(field_name)
    if not isinstance(value, list):
        errors.append(f"{field_name}: expected a list")
        return

    seen: set[str] = set()
    duplicates: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{field_name}: entry {index} must be a non-empty string")
            continue
        knowledge_id = item.strip()
        if not knowledge_id:
            errors.append(f"{field_name}: entry {index} must be a non-empty string")
            continue
        if (
            not knowledge_id.startswith("K-")
            or not knowledge_id[2:]
            or normalize_ascii_slug(knowledge_id[2:]) != knowledge_id[2:]
        ):
            errors.append(
                f"{field_name}: entry {index} must use canonical K-{{ascii-hyphen-slug}} format"
            )
            continue
        if knowledge_id in seen and knowledge_id not in duplicates:
            duplicates.append(knowledge_id)
        seen.add(knowledge_id)

    if duplicates:
        joined = ", ".join(duplicates)
        errors.append(f"{field_name}: duplicate ids are not allowed: {joined}")


def _validate_knowledge_gate_field(meta: dict[str, object], errors: list[str]) -> None:
    """Append validation errors for the optional top-level ``knowledge_gate`` field."""

    field_name = "knowledge_gate"
    if field_name not in meta:
        return
    value = meta.get(field_name)
    if not isinstance(value, str):
        errors.append(f"{field_name}: expected a string")
        return
    gate_value = value.strip()
    if not gate_value:
        errors.append(f"{field_name}: expected a non-empty string")
        return
    if gate_value not in KNOWLEDGE_GATE_VALUES:
        errors.append(f"{field_name}: must be one of off, warn, block")


def _plan_contract_ref_fragment_error(plan_contract_ref: str) -> str | None:
    """Return a user-facing fragment error for ``plan_contract_ref`` when invalid."""

    ref_value = plan_contract_ref.strip()
    if not ref_value:
        return "plan_contract_ref: expected a non-empty string"

    path_text, separator, fragment = ref_value.partition("#")
    if not path_text.strip():
        return "plan_contract_ref: must include a PLAN path before #/contract"
    if separator != "#" or fragment != "/contract":
        return "plan_contract_ref: must end with '#/contract'"
    return None


_PLAN_CONTRACT_REF_EXTERNAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def _plan_contract_ref_path_error(plan_contract_ref: str) -> str | None:
    """Return a safety error when a PLAN reference escapes the project-local plan space."""

    path_text = plan_contract_ref.strip().partition("#")[0].strip()
    if not path_text:
        return "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"
    if _PLAN_CONTRACT_REF_EXTERNAL_RE.match(path_text):
        return "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"
    if re.match(r"^[A-Za-z]:[\\/]", path_text) or re.match(r"^[A-Za-z]:$", path_text):
        return "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"

    relative_plan_path = Path(path_text[2:] if path_text.startswith("./") else path_text)
    if relative_plan_path.is_absolute():
        return "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"
    if any(part == ".." for part in relative_plan_path.parts):
        return "plan_contract_ref: must not traverse parent directories"
    if not relative_plan_path.parts or relative_plan_path.parts[0] != "GPD":
        return "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"
    return None


def _proof_specific_acceptance_test_ids(
    *,
    claim_acceptance_tests: list[str],
    acceptance_test_kind_by_id: dict[str, str],
) -> list[str]:
    return [
        test_id
        for test_id in claim_acceptance_tests
        if acceptance_test_kind_by_id.get(test_id) in PROOF_ACCEPTANCE_TEST_KINDS
    ]


def _claim_pass_proof_audit_errors(
    contract: ResearchContract,
    *,
    claim_id: str,
    claim_result,
    contract_results: ContractResults,
    acceptance_test_kind_by_id: dict[str, str],
    deliverable_path_by_id: dict[str, str | None],
) -> list[str]:
    claim_by_id = {claim.id: claim for claim in contract.claims}
    observable_kind_by_id = {observable.id: observable.kind for observable in contract.observables}
    claim = claim_by_id.get(claim_id)
    if claim is None or not claim_requires_proof_audit(claim, observable_kind_by_id):
        return []
    if claim_result.status != "passed":
        return []

    audit = claim_result.proof_audit
    if audit is None:
        return [f"claim {claim_id} status=passed requires proof_audit for proof-bearing claim"]

    errors: list[str] = []

    proof_test_ids = _proof_specific_acceptance_test_ids(
        claim_acceptance_tests=claim.acceptance_tests,
        acceptance_test_kind_by_id=acceptance_test_kind_by_id,
    )
    if not proof_test_ids:
        errors.append(f"claim {claim_id} status=passed requires at least one proof-specific acceptance_test")
    else:
        nonpassing_proof_test_ids = sorted(
            test_id
            for test_id in proof_test_ids
            if contract_results.acceptance_tests.get(test_id) is None
            or contract_results.acceptance_tests[test_id].status != "passed"
        )
        if nonpassing_proof_test_ids:
            errors.append(
                "claim "
                f"{claim_id} status=passed requires all declared proof-specific acceptance_tests to pass: "
                + ", ".join(nonpassing_proof_test_ids)
            )
        elif not any(
            contract_results.acceptance_tests.get(test_id) is not None
            and contract_results.acceptance_tests[test_id].status == "passed"
            for test_id in proof_test_ids
        ):
            errors.append(
                f"claim {claim_id} status=passed requires a passed proof-specific acceptance_test: {', '.join(sorted(proof_test_ids))}"
            )

    if audit.completeness != "complete":
        errors.append(f"claim {claim_id} status=passed requires proof_audit.completeness=complete")
    if audit.reviewer != PROOF_AUDIT_REVIEWER:
        errors.append(f"claim {claim_id} status=passed requires proof_audit.reviewer={PROOF_AUDIT_REVIEWER}")
    if not audit.reviewed_at:
        errors.append(f"claim {claim_id} status=passed requires proof_audit.reviewed_at")
    if audit.stale:
        errors.append(f"claim {claim_id} status=passed is incompatible with proof_audit.stale=true")
    if claim.quantifiers and audit.quantifier_status != "matched":
        errors.append(f"claim {claim_id} status=passed requires proof_audit.quantifier_status=matched")
    if audit.scope_status != "matched":
        errors.append(f"claim {claim_id} status=passed requires proof_audit.scope_status=matched")
    if audit.counterexample_status != "none_found":
        errors.append(f"claim {claim_id} status=passed requires proof_audit.counterexample_status=none_found")
    if not audit.proof_artifact_sha256:
        errors.append(f"claim {claim_id} status=passed requires proof_audit.proof_artifact_sha256")
    if not audit.audit_artifact_path:
        errors.append(f"claim {claim_id} status=passed requires proof_audit.audit_artifact_path")
    if not audit.audit_artifact_sha256:
        errors.append(f"claim {claim_id} status=passed requires proof_audit.audit_artifact_sha256")

    expected_statement_sha256 = _sha256_text(claim.statement)
    if audit.claim_statement_sha256 != expected_statement_sha256:
        errors.append(
            f"claim {claim_id} status=passed requires proof_audit.claim_statement_sha256 to match the current claim statement"
        )

    allowed_proof_paths = {
        path
        for deliverable_id in claim.proof_deliverables
        if (path := deliverable_path_by_id.get(deliverable_id))
    }
    if allowed_proof_paths and audit.proof_artifact_path not in allowed_proof_paths:
        errors.append(
            f"claim {claim_id} status=passed requires proof_audit.proof_artifact_path to match a declared proof_deliverables path"
        )

    return errors


def _matches_decisive_acceptance_test_verdict(
    verdict: ComparisonVerdict,
    *,
    subject_ids: set[str],
    allowed_comparison_kinds: frozenset[str],
) -> bool:
    """Return whether *verdict* closes a decisive acceptance-test comparison."""

    return (
        verdict.subject_role == "decisive"
        and verdict.comparison_kind in allowed_comparison_kinds
        and verdict.subject_id in subject_ids
    )


def _matches_decisive_reference_verdict(
    verdict: ComparisonVerdict,
    *,
    reference_id: str,
    known_reference_ids: set[str],
) -> bool:
    """Return whether *verdict* closes a decisive reference-backed comparison."""

    return (
        verdict.subject_role == "decisive"
        and verdict.comparison_kind in _DECISIVE_REFERENCE_COMPARISON_KINDS
        and reference_id in verdict.anchored_reference_ids(known_reference_ids)
    )


def _proof_audit_errors(
    contract: ResearchContract,
    contract_results: ContractResults,
    *,
    project_root: Path | None = None,
    artifact_dir: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    observable_kind_by_id = {observable.id: observable.kind for observable in contract.observables}
    acceptance_test_kind_by_id = {test.id: test.kind for test in contract.acceptance_tests}
    deliverable_path_by_id = {
        deliverable.id: deliverable.path
        for deliverable in contract.deliverables
    }

    for claim in contract.claims:
        if not claim_requires_proof_audit(claim, observable_kind_by_id):
            continue

        result = contract_results.claims.get(claim.id)
        if result is None:
            continue

        proof_audit = result.proof_audit
        if proof_audit is None:
            if result.status == "passed":
                errors.append(f"claim {claim.id} passed without proof_audit")
            continue

        errors.extend(
            collect_proof_audit_alignment_errors(
                claim,
                proof_audit,
                deliverable_path_by_id=deliverable_path_by_id,
            )
        )

        if proof_audit.proof_artifact_path:
            resolved_artifact, artifact_error = _resolve_contract_artifact_path(
                project_root=project_root,
                artifact_dir=artifact_dir,
                path_text=proof_audit.proof_artifact_path,
            )
            if artifact_error is not None:
                errors.append(f"claim {claim.id} proof_audit proof_artifact_path {artifact_error}")
            elif proof_audit.proof_artifact_sha256:
                try:
                    assert resolved_artifact is not None
                    actual_sha = hashlib.sha256(resolved_artifact.read_bytes()).hexdigest()
                except OSError:
                    actual_sha = None
                if actual_sha is None:
                    errors.append(
                        f"claim {claim.id} proof_audit proof_artifact_path does not resolve to a readable file"
                    )
                elif actual_sha != proof_audit.proof_artifact_sha256:
                    errors.append(f"claim {claim.id} proof_audit proof_artifact_sha256 is stale")

        if proof_audit.audit_artifact_path and proof_audit.audit_artifact_sha256:
            resolved_audit_artifact, artifact_error = _resolve_contract_artifact_path(
                project_root=project_root,
                artifact_dir=artifact_dir,
                path_text=proof_audit.audit_artifact_path,
            )
            if artifact_error is not None:
                errors.append(f"claim {claim.id} proof_audit audit_artifact_path {artifact_error}")
            else:
                try:
                    assert resolved_audit_artifact is not None
                    actual_audit_sha = hashlib.sha256(resolved_audit_artifact.read_bytes()).hexdigest()
                except OSError:
                    actual_audit_sha = None
                if actual_audit_sha is None:
                    errors.append(
                        f"claim {claim.id} proof_audit audit_artifact_path does not resolve to a readable file"
                    )
                elif actual_audit_sha != proof_audit.audit_artifact_sha256:
                    errors.append(f"claim {claim.id} proof_audit audit_artifact_sha256 is stale")

        if result.status != "passed":
            continue

        errors.extend(
            _claim_pass_proof_audit_errors(
                contract,
                claim_id=claim.id,
                claim_result=result,
                contract_results=contract_results,
                acceptance_test_kind_by_id=acceptance_test_kind_by_id,
                deliverable_path_by_id=deliverable_path_by_id,
            )
        )

    return errors


def _summary_contract_errors(
    contract: ResearchContract,
    contract_results: ContractResults,
    comparison_verdicts: list[ComparisonVerdict],
    *,
    project_root: Path | None = None,
    artifact_dir: Path | None = None,
) -> list[str]:
    """Return summary-to-contract alignment issues for a contract-backed plan."""

    errors = _proof_audit_errors(
        contract,
        contract_results,
        project_root=project_root,
        artifact_dir=artifact_dir,
    )

    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    forbidden_proxy_ids = {proxy.id for proxy in contract.forbidden_proxies}
    known_contract_ids = claim_ids | deliverable_ids | acceptance_test_ids | reference_ids | forbidden_proxy_ids
    known_subject_ids = claim_ids | deliverable_ids | acceptance_test_ids | reference_ids
    subject_kind_by_id = {
        **dict.fromkeys(claim_ids, "claim"),
        **dict.fromkeys(deliverable_ids, "deliverable"),
        **dict.fromkeys(acceptance_test_ids, "acceptance_test"),
        **dict.fromkeys(reference_ids, "reference"),
    }

    def _unknown(actual: set[str], expected: set[str], label: str) -> None:
        for item_id in sorted(actual - expected):
            errors.append(f"Unknown {label} contract_results entry: {item_id}")

    def _missing(actual: set[str], expected: set[str], label: str) -> None:
        for item_id in sorted(expected - actual):
            errors.append(f"Missing {label} contract_results entry: {item_id}")

    def _check_linked_ids(label: str, entry_id: str, linked_ids: list[str]) -> None:
        for linked_id in linked_ids:
            if linked_id not in known_contract_ids:
                errors.append(f"{label} {entry_id} linked_ids references unknown contract id {linked_id}")

    def _check_evidence_bindings(
        label: str,
        entry_id: str,
        evidence_items: list[object],
    ) -> None:
        for evidence in evidence_items:
            if evidence.claim_id is not None and evidence.claim_id not in claim_ids:
                errors.append(f"{label} {entry_id} evidence references unknown claim_id {evidence.claim_id}")
            if evidence.deliverable_id is not None and evidence.deliverable_id not in deliverable_ids:
                errors.append(
                    f"{label} {entry_id} evidence references unknown deliverable_id {evidence.deliverable_id}"
                )
            if evidence.acceptance_test_id is not None and evidence.acceptance_test_id not in acceptance_test_ids:
                errors.append(
                    f"{label} {entry_id} evidence references unknown acceptance_test_id {evidence.acceptance_test_id}"
                )
            if evidence.reference_id is not None and evidence.reference_id not in reference_ids:
                errors.append(f"{label} {entry_id} evidence references unknown reference_id {evidence.reference_id}")
            if evidence.forbidden_proxy_id is not None and evidence.forbidden_proxy_id not in forbidden_proxy_ids:
                errors.append(
                    f"{label} {entry_id} evidence references unknown forbidden_proxy_id {evidence.forbidden_proxy_id}"
                )

    _unknown(set(contract_results.claims), claim_ids, "claim")
    _unknown(set(contract_results.deliverables), deliverable_ids, "deliverable")
    _unknown(set(contract_results.acceptance_tests), acceptance_test_ids, "acceptance_test")
    _unknown(set(contract_results.references), reference_ids, "reference")
    _unknown(set(contract_results.forbidden_proxies), forbidden_proxy_ids, "forbidden_proxy")
    _missing(set(contract_results.claims), claim_ids, "claim")
    _missing(set(contract_results.deliverables), deliverable_ids, "deliverable")
    _missing(set(contract_results.acceptance_tests), acceptance_test_ids, "acceptance_test")
    _missing(set(contract_results.references), reference_ids, "reference")
    _missing(set(contract_results.forbidden_proxies), forbidden_proxy_ids, "forbidden_proxy")

    for claim_id, entry in contract_results.claims.items():
        if claim_id not in claim_ids:
            continue
        _check_linked_ids("claim", claim_id, entry.linked_ids)
        _check_evidence_bindings("claim", claim_id, entry.evidence)
    for deliverable_id, entry in contract_results.deliverables.items():
        if deliverable_id not in deliverable_ids:
            continue
        _check_linked_ids("deliverable", deliverable_id, entry.linked_ids)
        _check_evidence_bindings("deliverable", deliverable_id, entry.evidence)
    for test_id, entry in contract_results.acceptance_tests.items():
        if test_id not in acceptance_test_ids:
            continue
        _check_linked_ids("acceptance_test", test_id, entry.linked_ids)
        _check_evidence_bindings("acceptance_test", test_id, entry.evidence)
    for reference_id, usage in contract_results.references.items():
        if reference_id not in reference_ids:
            continue
        _check_evidence_bindings("reference", reference_id, usage.evidence)
    for proxy_id, result in contract_results.forbidden_proxies.items():
        if proxy_id not in forbidden_proxy_ids:
            continue
        _check_evidence_bindings("forbidden_proxy", proxy_id, result.evidence)

    for reference in contract.references:
        usage = contract_results.references.get(reference.id)
        if reference.must_surface and usage is None:
            errors.append(f"Missing must_surface reference coverage in summary: {reference.id}")
            continue
        if usage is None:
            continue
        completed = set(usage.completed_actions)
        missing = set(reference.required_actions) - completed
        if reference.must_surface and missing:
            errors.append(
                f"Reference {reference.id} missing required_actions in summary: {', '.join(sorted(missing))}"
            )

    for verdict in comparison_verdicts:
        if verdict.subject_id not in known_subject_ids:
            errors.append(f"comparison_verdict references unknown subject_id {verdict.subject_id}")
        expected_subject_kind = subject_kind_by_id.get(verdict.subject_id)
        if expected_subject_kind is not None and verdict.subject_kind != expected_subject_kind:
            errors.append(
                "comparison_verdict for "
                f"{verdict.subject_id} has subject_kind {verdict.subject_kind} but contract id is a {expected_subject_kind}"
            )
        if verdict.reference_id is not None and verdict.reference_id not in reference_ids:
            errors.append(f"comparison_verdict references unknown reference_id {verdict.reference_id}")
        if (
            verdict.subject_role == "decisive"
            and verdict.comparison_kind in _DECISIVE_EXTERNAL_COMPARISON_KINDS
            and not verdict.anchored_reference_ids(reference_ids)
        ):
            errors.append(
                "comparison_verdict for "
                f"{verdict.subject_id} must include reference_id or use subject_kind: reference "
                f"for decisive {verdict.comparison_kind} comparisons"
            )
        if verdict.subject_role != "decisive":
            continue
        if verdict.subject_id in contract_results.claims:
            claim_status = contract_results.claims[verdict.subject_id].status
            if claim_status == "passed" and verdict.verdict in {"fail", "tension", "inconclusive"}:
                errors.append(
                    f"comparison_verdict for claim {verdict.subject_id} contradicts passed contract_results status"
                )
            if claim_status in {"failed", "blocked"} and verdict.verdict == "pass":
                errors.append(
                    f"comparison_verdict for claim {verdict.subject_id} contradicts failed contract_results status"
                )
        if verdict.subject_id in contract_results.deliverables:
            deliverable_status = contract_results.deliverables[verdict.subject_id].status
            if deliverable_status == "passed" and verdict.verdict in {"fail", "tension", "inconclusive"}:
                errors.append(
                    "comparison_verdict for deliverable "
                    f"{verdict.subject_id} contradicts passed contract_results status"
                )
            if deliverable_status in {"failed", "blocked"} and verdict.verdict == "pass":
                errors.append(
                    "comparison_verdict for deliverable "
                    f"{verdict.subject_id} contradicts failed contract_results status"
                )
        if verdict.subject_id in contract_results.acceptance_tests:
            test_status = contract_results.acceptance_tests[verdict.subject_id].status
            if test_status == "passed" and verdict.verdict in {"fail", "tension", "inconclusive"}:
                errors.append(
                    "comparison_verdict for acceptance_test "
                    f"{verdict.subject_id} contradicts passed contract_results status"
                )
            if test_status in {"failed", "blocked"} and verdict.verdict == "pass":
                errors.append(
                    "comparison_verdict for acceptance_test "
                    f"{verdict.subject_id} contradicts failed contract_results status"
                )

    for test in contract.acceptance_tests:
        allowed_comparison_kinds = _DECISIVE_ACCEPTANCE_TEST_COMPARISON_KINDS.get(test.kind)
        if allowed_comparison_kinds is None:
            continue
        result = contract_results.acceptance_tests.get(test.id)
        subject_ids = {test.id, test.subject}
        if result is not None:
            subject_ids.update(result.linked_ids)
        if not any(
            _matches_decisive_acceptance_test_verdict(
                verdict,
                subject_ids=subject_ids,
                allowed_comparison_kinds=allowed_comparison_kinds,
            )
            for verdict in comparison_verdicts
        ):
            errors.append(f"Missing decisive comparison_verdict for acceptance test {test.id}")
    for reference in contract.references:
        if reference.role != "benchmark" and "compare" not in reference.required_actions:
            continue
        if not any(
            _matches_decisive_reference_verdict(
                verdict,
                reference_id=reference.id,
                known_reference_ids=reference_ids,
            )
            for verdict in comparison_verdicts
        ):
            errors.append(f"Missing decisive comparison_verdict for reference {reference.id}")

    return errors


def _verification_contract_errors(
    contract: ResearchContract,
    contract_results: ContractResults,
    comparison_verdicts: list[ComparisonVerdict],
    suggested_contract_checks: list[SuggestedContractCheck],
    *,
    project_root: Path | None = None,
    artifact_dir: Path | None = None,
) -> list[str]:
    """Return verification-specific alignment issues for contract-backed plans."""

    errors = _summary_contract_errors(
        contract,
        contract_results,
        comparison_verdicts,
        project_root=project_root,
        artifact_dir=artifact_dir,
    )

    decisive_incomplete = False
    for test in contract.acceptance_tests:
        if test.kind not in {"benchmark", "cross_method"}:
            continue
        result = contract_results.acceptance_tests.get(test.id)
        if result is None or result.status in {"partial", "not_attempted"}:
            decisive_incomplete = True
            break
    if not decisive_incomplete:
        for reference in contract.references:
            if reference.role != "benchmark" and "compare" not in reference.required_actions:
                continue
            usage = contract_results.references.get(reference.id)
            if usage is None or usage.status != "completed" or "compare" not in usage.completed_actions:
                decisive_incomplete = True
                break

    missing_decisive_coverage = decisive_incomplete or any(
        "Missing decisive comparison_verdict" in error for error in errors
    )
    if missing_decisive_coverage and not suggested_contract_checks:
        errors.append(
            "suggested_contract_checks: required when decisive benchmark/cross-method checks remain missing, partial, or incomplete"
        )

    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    subject_kind_by_id = {
        **dict.fromkeys(claim_ids, "claim"),
        **dict.fromkeys(deliverable_ids, "deliverable"),
        **dict.fromkeys(acceptance_test_ids, "acceptance_test"),
        **dict.fromkeys(reference_ids, "reference"),
    }
    valid_ids_by_kind = {
        "claim": claim_ids,
        "deliverable": deliverable_ids,
        "acceptance_test": acceptance_test_ids,
        "reference": reference_ids,
    }

    for index, check in enumerate(suggested_contract_checks):
        has_kind = check.suggested_subject_kind is not None
        has_id = check.suggested_subject_id is not None
        if has_kind != has_id:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] must provide suggested_subject_kind and suggested_subject_id together"
            )
            continue
        if not has_kind or check.suggested_subject_kind is None or check.suggested_subject_id is None:
            continue
        expected_kind = subject_kind_by_id.get(check.suggested_subject_id)
        if expected_kind is None:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] references unknown {check.suggested_subject_kind} id {check.suggested_subject_id}"
            )
            continue
        if expected_kind != check.suggested_subject_kind:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] references {check.suggested_subject_id} as {check.suggested_subject_kind},"
                f" but the contract declares it as {expected_kind}"
            )
            continue
        if check.suggested_subject_id not in valid_ids_by_kind[check.suggested_subject_kind]:
            errors.append(
                "suggested_contract_checks"
                f"[{index}] references unknown {check.suggested_subject_kind} id {check.suggested_subject_id}"
            )

    return errors


def _verification_status_errors(
    verification_status: object,
    contract_results: ContractResults,
    suggested_contract_checks: list[SuggestedContractCheck],
) -> list[str]:
    """Return contradictions between the declared verification status and the machine ledger."""

    if str(verification_status or "").strip() != "passed":
        return []

    errors: list[str] = []
    if suggested_contract_checks:
        errors.append("status: passed is inconsistent with non-empty suggested_contract_checks")

    non_passed_subjects = [
        f"claim {entry_id}"
        for entry_id, entry in contract_results.claims.items()
        if entry.status != "passed"
    ]
    non_passed_subjects.extend(
        f"deliverable {entry_id}"
        for entry_id, entry in contract_results.deliverables.items()
        if entry.status != "passed"
    )
    non_passed_subjects.extend(
        f"acceptance_test {entry_id}"
        for entry_id, entry in contract_results.acceptance_tests.items()
        if entry.status != "passed"
    )
    if non_passed_subjects:
        errors.append(
            "status: passed is inconsistent with non-passed contract_results targets: "
            + ", ".join(sorted(non_passed_subjects))
        )

    non_completed_references = [
        f"reference {entry_id}"
        for entry_id, entry in contract_results.references.items()
        if entry.status != "completed"
    ]
    if non_completed_references:
        errors.append(
            "status: passed is inconsistent with non-completed contract_results references: "
            + ", ".join(sorted(non_completed_references))
        )

    unresolved_proxies = [
        proxy_id
        for proxy_id, result in contract_results.forbidden_proxies.items()
        if result.status not in {"rejected", "not_applicable"}
    ]
    if unresolved_proxies:
        errors.append(
            "status: passed is inconsistent with unresolved forbidden_proxies: "
            + ", ".join(sorted(unresolved_proxies))
        )

    return errors


def _frontmatter_identity_matches(candidate_meta: dict[str, object], artifact_meta: dict[str, object]) -> bool:
    """Return whether a candidate PLAN frontmatter matches artifact phase/plan identity."""

    for key in ("phase", "plan"):
        expected = artifact_meta.get(key)
        if expected is None:
            continue
        actual = candidate_meta.get(key)
        if actual is None or str(actual).strip() != str(expected).strip():
            return False
    return True


def _resolve_plan_contract_candidate(
    candidate: Path,
    artifact_meta: dict[str, object],
    *,
    project_root: Path | None = None,
) -> tuple[bool, _PlanContractResolution]:
    """Inspect one PLAN candidate and return whether its identity matches."""

    content = safe_read_file(candidate)
    if content is None:
        return True, _PlanContractResolution(errors=[f"could not read referenced PLAN {candidate.as_posix()}"])

    try:
        meta, _body = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return True, _PlanContractResolution(
            errors=[f"referenced PLAN frontmatter YAML parse error: {exc}"]
        )

    if not _frontmatter_identity_matches(meta, artifact_meta):
        return False, _PlanContractResolution()

    if "contract" not in meta:
        return True, _PlanContractResolution(errors=["referenced PLAN is missing contract frontmatter"])

    resolution = _validate_contract_mapping(
        meta.get("contract"),
        enforce_plan_semantics=True,
        project_root=project_root,
    )
    if resolution.errors:
        return True, _PlanContractResolution(
            errors=[f"referenced PLAN contract: {error}" for error in resolution.errors]
        )
    return True, resolution


def _find_matching_plan_contract(
    summary_dir: Path,
    summary_meta: dict,
    *,
    project_root: Path | None = None,
) -> _PlanContractResolution:
    """Return the sibling plan contract for a summary when one can be resolved."""

    if project_root is None:
        project_root = resolve_project_root(summary_dir)

    plan_contract_ref = summary_meta.get("plan_contract_ref")
    if isinstance(plan_contract_ref, str):
        if _plan_contract_ref_fragment_error(plan_contract_ref) is not None:
            return _PlanContractResolution()
        path_error = _plan_contract_ref_path_error(plan_contract_ref)
        if path_error is not None:
            return _PlanContractResolution()
        plan_ref_path = plan_contract_ref.split("#", 1)[0].strip()
        relative_plan_path = Path(plan_ref_path[2:] if plan_ref_path.startswith("./") else plan_ref_path)
        if project_root is None:
            return _PlanContractResolution()
        candidate, path_error = _resolve_contract_artifact_path(
            project_root=project_root,
            artifact_dir=project_root,
            path_text=relative_plan_path.as_posix(),
        )
        if path_error is not None:
            return _PlanContractResolution(errors=[f"plan_contract_ref: {path_error}"])
        assert candidate is not None
        if not candidate.exists():
            return _PlanContractResolution()
        matched, resolution = _resolve_plan_contract_candidate(
            candidate,
            summary_meta,
            project_root=project_root,
        )
        if matched:
            return resolution
        return _PlanContractResolution()

    matching_candidates: list[_PlanContractResolution] = []
    for candidate in sorted(summary_dir.iterdir()):
        if not candidate.is_file() or not (candidate.name.endswith(PLAN_SUFFIX) or candidate.name == STANDALONE_PLAN):
            continue
        content = safe_read_file(candidate)
        if content is None:
            continue
        try:
            meta, _body = extract_frontmatter(content)
        except FrontmatterParseError:
            continue
        if not _frontmatter_identity_matches(meta, summary_meta):
            continue
        if "contract" not in meta:
            continue
        resolution = _validate_contract_mapping(
            meta.get("contract"),
            enforce_plan_semantics=True,
            project_root=project_root,
        )
        if resolution.errors:
            matching_candidates.append(
                _PlanContractResolution(
                    errors=[f"referenced PLAN contract: {error}" for error in resolution.errors]
                )
            )
            continue
        matching_candidates.append(resolution)

    valid_candidates = [resolution for resolution in matching_candidates if resolution.contract is not None]
    if len(valid_candidates) == 1:
        return valid_candidates[0]
    if len(valid_candidates) > 1:
        return _PlanContractResolution(
            errors=["multiple matching sibling PLAN contracts found; add plan_contract_ref"]
        )
    if matching_candidates:
        return matching_candidates[0]
    return _PlanContractResolution()


@instrument_gpd_function("frontmatter.validate")
def validate_frontmatter(content: str, schema_name: str, source_path: Path | None = None) -> FrontmatterValidation:
    """Validate frontmatter against a named schema.

    Raises:
        FrontmatterParseError: On malformed YAML.
        FrontmatterValidationError: If *schema_name* is unknown.
    """
    project_root = _source_path_project_root(source_path)
    schema = FRONTMATTER_SCHEMAS.get(schema_name)
    if schema is None:
        available = ", ".join(FRONTMATTER_SCHEMAS)
        raise FrontmatterValidationError(f"Unknown schema: {schema_name}. Available: {available}")

    if schema_name == "knowledge":
        return validate_knowledge_frontmatter(content, source_path=source_path)

    meta, _ = extract_frontmatter(content)  # may raise FrontmatterParseError
    required = schema["required"]

    missing = [f for f in required if _resolve_field(meta, f) is None]
    present = [f for f in required if _resolve_field(meta, f) is not None]
    errors: list[str] = []

    errors.extend(_unsupported_frontmatter_errors(schema_name, meta))

    if schema_name == "plan":
        for field_name in ("phase", "plan"):
            _validate_required_scalar_field(meta, field_name, errors)
        _validate_required_string_field(meta, "type", errors)
        _validate_string_enum_field(meta, "type", errors, allowed_values=PLAN_FRONTMATTER_TYPES)
        _validate_required_int_field(meta, "wave", errors)
        for field_name in ("depends_on", "files_modified"):
            _validate_non_empty_string_list_field(meta, field_name, errors)
        _validate_required_bool_field(meta, "interactive", errors)
        _validate_required_object_field(meta, "conventions", errors)
    elif schema_name == "summary":
        for field_name in ("phase", "plan", "completed"):
            _validate_required_scalar_field(meta, field_name, errors)
        _validate_required_string_field(meta, "depth", errors)
        _validate_string_enum_field(meta, "depth", errors, allowed_values=SUMMARY_DEPTH_VALUES)
        _validate_non_empty_string_list_field(meta, "provides", errors)
    elif schema_name == "verification":
        _validate_required_scalar_field(meta, "phase", errors)
        _validate_required_scalar_field(meta, "verified", errors)
        _validate_timestamp_scalar_field(meta, "verified", errors)
        _validate_required_string_field(meta, "status", errors)
        _validate_required_string_field(meta, "score", errors)

    if schema_name == "verification" and "status" in meta:
        raw_status = meta.get("status")
        if not isinstance(raw_status, str):
            errors.append("status: expected a string")
        elif raw_status.strip() not in VERIFICATION_REPORT_STATUSES:
            errors.append(
                "status: must be one of passed, gaps_found, expert_needed, human_needed"
            )

    if isinstance(meta.get("contract"), dict):
        resolution = _validate_contract_mapping(
            meta["contract"],
            enforce_plan_semantics=(schema_name == "plan"),
            project_root=project_root,
        )
        errors.extend(f"contract: {issue}" for issue in resolution.errors)
    elif "contract" in meta:
        errors.append("contract: expected an object")

    if schema_name == "plan":
        _validate_knowledge_deps_field(meta, errors)
        _validate_knowledge_gate_field(meta, errors)

    if schema_name == "plan" and "tool_requirements" in meta:
        try:
            parse_plan_tool_requirements(meta.get("tool_requirements"))
        except PlanToolPreflightError as exc:
            errors.append(f"tool_requirements: {exc}")

    if schema_name in {"summary", "verification"}:
        plan_contract_ref = meta.get("plan_contract_ref")
        plan_contract_ref_fragment_error: str | None = None
        plan_contract_ref_path_error: str | None = None
        if plan_contract_ref is not None and not isinstance(plan_contract_ref, str):
            errors.append("plan_contract_ref: expected a string")
        elif isinstance(plan_contract_ref, str):
            plan_contract_ref_fragment_error = _plan_contract_ref_fragment_error(plan_contract_ref)
            if plan_contract_ref_fragment_error is not None:
                errors.append(plan_contract_ref_fragment_error)
            else:
                plan_contract_ref_path_error = _plan_contract_ref_path_error(plan_contract_ref)
                if plan_contract_ref_path_error is not None:
                    errors.append(plan_contract_ref_path_error)
        if (meta.get("contract_results") is not None or meta.get("comparison_verdicts") is not None) and not isinstance(
            plan_contract_ref, str
        ):
            errors.append("plan_contract_ref: required when contract_results or comparison_verdicts are present")

        contract_results = None
        comparison_verdicts: list[ComparisonVerdict] = []
        suggested_contract_checks: list[SuggestedContractCheck] = []
        try:
            contract_results = _parse_contract_results(meta)
        except (PydanticValidationError, TypeError, ValueError) as exc:
            errors.extend(_prefixed_validation_errors("contract_results", exc))
        try:
            comparison_verdicts = _parse_comparison_verdicts(meta)
        except (PydanticValidationError, TypeError, ValueError) as exc:
            errors.extend(_prefixed_validation_errors("comparison_verdicts", exc))

        if schema_name == "verification":
            try:
                suggested_contract_checks = _parse_suggested_contract_checks(meta)
            except ValueError as exc:
                errors.extend(_prefixed_validation_errors("suggested_contract_checks", exc))

        if source_path is not None:
            artifact_dir = source_path.parent
            plan_contract_resolution = _find_matching_plan_contract(
                artifact_dir,
                meta,
                project_root=project_root,
            )
            plan_contract = plan_contract_resolution.contract
            errors.extend(f"plan_contract_ref: {issue}" for issue in plan_contract_resolution.errors)
            if (
                isinstance(plan_contract_ref, str)
                and plan_contract_ref_fragment_error is None
                and plan_contract_ref_path_error is None
                and plan_contract is None
                and not plan_contract_resolution.errors
            ):
                errors.append("plan_contract_ref: could not resolve matching plan contract")
            if plan_contract is not None:
                if not isinstance(plan_contract_ref, str):
                    errors.append("plan_contract_ref: required for contract-backed plan")
                if contract_results is None:
                    errors.append("contract_results: required for contract-backed plan")
                else:
                    if schema_name == "verification":
                        verification_errors = _verification_contract_errors(
                            plan_contract,
                            contract_results,
                            comparison_verdicts,
                            suggested_contract_checks,
                            project_root=project_root,
                            artifact_dir=artifact_dir,
                        )
                        errors.extend(verification_errors)
                        errors.extend(
                            _verification_status_errors(
                                meta.get("status"),
                                contract_results,
                                suggested_contract_checks,
                            )
                        )
                    else:
                        errors.extend(
                            _summary_contract_errors(
                                plan_contract,
                                contract_results,
                                comparison_verdicts,
                                project_root=project_root,
                                artifact_dir=artifact_dir,
                            )
                        )

    return FrontmatterValidation(
        valid=len(missing) == 0 and not errors,
        missing=missing,
        present=present,
        errors=errors,
        schema_name=schema_name,
    )


# ---------------------------------------------------------------------------
# Verification suite — result types
# ---------------------------------------------------------------------------


class FileCheckResult(BaseModel):
    checked: int = 0
    found: int = 0
    missing: list[str] = Field(default_factory=list)


class SummaryVerification(BaseModel):
    passed: bool
    summary_exists: bool = False
    files_created: FileCheckResult = Field(default_factory=FileCheckResult)
    commits_exist: bool = False
    self_check: str = "not_found"
    errors: list[str] = Field(default_factory=list)


class TaskInfo(BaseModel):
    name: str
    has_files: bool = False
    has_action: bool = False
    has_verify: bool = False
    has_done: bool = False


class PlanValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    task_count: int = 0
    tasks: list[TaskInfo] = Field(default_factory=list)
    frontmatter_fields: list[str] = Field(default_factory=list)


class PhaseCompleteness(BaseModel):
    complete: bool
    phase_number: str = ""
    plan_count: int = 0
    summary_count: int = 0
    incomplete_plans: list[str] = Field(default_factory=list)
    orphan_summaries: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReferenceVerification(BaseModel):
    valid: bool
    found: int = 0
    missing: list[str] = Field(default_factory=list)
    total: int = 0


class CommitVerification(BaseModel):
    all_valid: bool
    valid_hashes: list[str] = Field(default_factory=list)
    invalid_hashes: list[str] = Field(default_factory=list)
    total: int = 0


class ArtifactCheck(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    path: str
    exists: bool = False
    issues: list[str] = Field(default_factory=list)
    passed: bool = False


class ArtifactVerification(BaseModel):
    all_passed: bool
    passed_count: int = 0
    total: int = 0
    artifacts: list[ArtifactCheck] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers (file/git)
# ---------------------------------------------------------------------------


def _exec_git(cwd: Path, args: list[str]) -> tuple[int, str]:
    """Run a git command, return (exit_code, stdout)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 1, ""


# ---------------------------------------------------------------------------
# Verification suite — implementations
# ---------------------------------------------------------------------------

# Patterns to extract file paths mentioned in markdown
_FILE_MENTION_BACKTICK = re.compile(r"`([^`]+\.[a-zA-Z][a-zA-Z0-9]*)`")
_FILE_MENTION_VERB = re.compile(
    r"(?:Created|Modified|Added|Updated|Edited):\s*`?([^\s`]+\.[a-zA-Z][a-zA-Z0-9]*)`?",
    re.IGNORECASE,
)
_FILE_REFERENCE_SUFFIX = re.compile(r"\.[a-zA-Z][a-zA-Z0-9]*$")

# Commit hash patterns: `abc1234` or "commit abc1234"
_COMMIT_HASH_RE = re.compile(
    r"(?:`([0-9a-f]{7,12}|[0-9a-f]{40})`|\bcommit\s+([0-9a-f]{7,40})\b)",
    re.IGNORECASE,
)

# Self-check section heading
_SELF_CHECK_HEADING = re.compile(r"##\s*(?:Self[- ]?Check|Verification|Quality Check)", re.IGNORECASE)
_SELF_CHECK_PASS = re.compile(r"\b(?:(?:all\s+)?pass(?:ed)?|complete[d]?|succeeded)\b", re.IGNORECASE)
_SELF_CHECK_FAIL = re.compile(r"\b(?:fail(?:ed)?|incomplete|blocked)\b", re.IGNORECASE)


def _looks_like_local_file_reference(value: str, *, allow_bare_filename: bool) -> bool:
    """Return whether *value* looks like a local file path worth spot-checking."""
    candidate = value.strip()
    if not candidate or candidate.startswith(("http://", "https://")):
        return False
    if "/" in candidate:
        return True
    if not allow_bare_filename:
        return False
    return _FILE_REFERENCE_SUFFIX.search(Path(candidate).name) is not None


def _append_ordered_file_reference(
    mentioned: list[str],
    seen: set[str],
    value: object,
    *,
    allow_bare_filename: bool,
) -> None:
    """Record one file reference while preserving declaration order."""
    if not isinstance(value, str):
        return
    candidate = value.strip()
    if not _looks_like_local_file_reference(candidate, allow_bare_filename=allow_bare_filename) or candidate in seen:
        return
    seen.add(candidate)
    mentioned.append(candidate)


@instrument_gpd_function("frontmatter.verify_summary")
def verify_summary(
    cwd: Path,
    summary_path: Path,
    check_file_count: int = 2,
) -> SummaryVerification:
    """Verify a SUMMARY.md file: existence, mentioned files, commit hashes, self-check section."""
    full_path = summary_path if summary_path.is_absolute() else cwd / summary_path

    if not full_path.exists():
        return SummaryVerification(
            passed=False,
            summary_exists=False,
            errors=["SUMMARY.md not found"],
        )

    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return SummaryVerification(
            passed=False,
            summary_exists=True,
            errors=[f"Cannot read file (invalid UTF-8): {exc}"],
        )
    try:
        meta, _body = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return SummaryVerification(
            passed=False,
            summary_exists=True,
            errors=[f"Frontmatter YAML parse error: {exc}"],
        )

    schema_validation = validate_frontmatter(content, "summary", source_path=full_path)
    errors: list[str] = list(schema_validation.errors)
    errors.extend(f"{field} is required" for field in schema_validation.missing)

    # --- Spot-check files mentioned in summary ---
    mentioned: list[str] = []
    seen_mentions: set[str] = set()
    raw_key_files = meta.get("key-files")
    if isinstance(raw_key_files, dict):
        for key in ("created", "modified"):
            value = raw_key_files.get(key)
            if isinstance(value, list):
                for item in value:
                    _append_ordered_file_reference(mentioned, seen_mentions, item, allow_bare_filename=True)
    elif isinstance(raw_key_files, list):
        for item in raw_key_files:
            _append_ordered_file_reference(mentioned, seen_mentions, item, allow_bare_filename=True)
    for m in _FILE_MENTION_BACKTICK.finditer(content):
        _append_ordered_file_reference(mentioned, seen_mentions, m.group(1), allow_bare_filename=False)
    for m in _FILE_MENTION_VERB.finditer(content):
        _append_ordered_file_reference(mentioned, seen_mentions, m.group(1), allow_bare_filename=True)

    files_to_check = mentioned[:check_file_count]
    missing_files = [f for f in files_to_check if not (cwd / f).exists()]

    # --- Commit hashes ---
    hashes = [m.group(1) or m.group(2) for m in _COMMIT_HASH_RE.finditer(content)]
    commits_exist = False
    for h in hashes[:3]:
        exit_code, stdout = _exec_git(cwd, ["cat-file", "-t", h])
        if exit_code == 0 and stdout == "commit":
            commits_exist = True
            break

    # --- Self-check section ---
    self_check = "not_found"
    heading_match = _SELF_CHECK_HEADING.search(content)
    if heading_match:
        check_start = heading_match.start()
        next_heading = content.find("\n## ", check_start + 1)
        section = content[check_start:] if next_heading == -1 else content[check_start:next_heading]
        if _SELF_CHECK_FAIL.search(section):
            self_check = "failed"
        elif _SELF_CHECK_PASS.search(section):
            self_check = "passed"

    if missing_files:
        errors.append("Missing files: " + ", ".join(missing_files))
    if not commits_exist and hashes:
        errors.append("Referenced commit hashes not found in git history")
    if self_check == "failed":
        errors.append("Self-check section indicates failure")

    passed = len(errors) == 0 and len(missing_files) == 0 and self_check != "failed" and not (not commits_exist and hashes)
    return SummaryVerification(
        passed=passed,
        summary_exists=True,
        files_created=FileCheckResult(
            checked=len(files_to_check),
            found=len(files_to_check) - len(missing_files),
            missing=missing_files,
        ),
        commits_exist=commits_exist,
        self_check=self_check,
        errors=errors,
    )


# Task XML patterns
_TASK_ELEMENT_RE = re.compile(r"<task[^>]*>([\s\S]*?)</task>")
_TASK_NAME_RE = re.compile(r"<name>([\s\S]*?)</name>")
_CHECKPOINT_TASK_RE = re.compile(r'<task\s+[^>]*?type=["\']?checkpoint')


@instrument_gpd_function("frontmatter.verify_plan")
def verify_plan_structure(cwd: Path, file_path: Path) -> PlanValidation:
    """Validate plan file structure: required frontmatter, task elements, wave/deps consistency."""
    full_path = file_path if file_path.is_absolute() else cwd / file_path
    content = safe_read_file(full_path)
    if content is None:
        return PlanValidation(valid=False, errors=[f"File not found: {file_path}"])

    try:
        meta, _ = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return PlanValidation(valid=False, errors=[f"YAML parse error: {exc}"])

    errors: list[str] = []
    warnings: list[str] = []
    schema_validation = validate_frontmatter(content, "plan", source_path=full_path)
    errors.extend(list(schema_validation.errors))
    errors.extend(f"Missing required frontmatter field: {field_name}" for field_name in schema_validation.missing)

    # Parse task elements
    tasks: list[TaskInfo] = []
    for task_match in _TASK_ELEMENT_RE.finditer(content):
        task_content = task_match.group(1)
        name_match = _TASK_NAME_RE.search(task_content)
        task_name = name_match.group(1).strip() if name_match else "unnamed"

        has_files = "<files>" in task_content
        has_action = "<action>" in task_content
        has_verify = "<verify>" in task_content
        has_done = "<done>" in task_content

        if not name_match:
            errors.append("Task missing <name> element")
        if not has_action:
            errors.append(f"Task '{task_name}' missing <action>")
        if not has_verify:
            warnings.append(f"Task '{task_name}' missing <verify>")
        if not has_done:
            warnings.append(f"Task '{task_name}' missing <done>")
        if not has_files:
            warnings.append(f"Task '{task_name}' missing <files>")

        tasks.append(
            TaskInfo(
                name=task_name,
                has_files=has_files,
                has_action=has_action,
                has_verify=has_verify,
                has_done=has_done,
            )
        )

    if not tasks:
        warnings.append("No <task> elements found")

    # Wave/depends_on consistency
    deps = meta.get("depends_on")
    wave = meta.get("wave")
    if wave is not None:
        try:
            wave_int = int(wave)
        except (TypeError, ValueError):
            wave_int = 0
        if wave_int > 1 and (not deps or (isinstance(deps, list) and len(deps) == 0)):
            warnings.append("Wave > 1 but depends_on is empty")

    # Interactive/checkpoint consistency
    has_checkpoints = bool(_CHECKPOINT_TASK_RE.search(content))
    interactive = meta.get("interactive")
    interactive_enabled = interactive in ("true", True)
    if has_checkpoints and not interactive_enabled:
        errors.append("Has checkpoint tasks but interactive is not true")
    if interactive_enabled and not has_checkpoints:
        errors.append("interactive is true but no checkpoint tasks were found")

    return PlanValidation(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        task_count=len(tasks),
        tasks=tasks,
        frontmatter_fields=list(meta.keys()),
    )


@instrument_gpd_function("frontmatter.verify_phase")
def verify_phase_completeness(cwd: Path, phase: str) -> PhaseCompleteness:
    """Verify that every plan in a phase has a matching summary.

    Uses lazy import of ``find_phase`` from ``gpd.core.phases``
    to break circular dependency.
    """
    from gpd.core.phases import find_phase

    phase_info = find_phase(cwd, phase)
    if phase_info is None:
        return PhaseCompleteness(
            complete=False,
            errors=[f"Phase not found: {phase}"],
        )

    phase_dir = cwd / phase_info.directory
    if not phase_dir.is_dir():
        return PhaseCompleteness(
            complete=False,
            errors=["Cannot read phase directory"],
        )

    files = [f.name for f in phase_dir.iterdir() if f.is_file()]
    plans = [f for f in files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
    summaries = [f for f in files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]

    plan_ids = {phase_artifact_id(p, PLAN_SUFFIX, STANDALONE_PLAN) for p in plans}
    summary_ids = {phase_artifact_id(s, SUMMARY_SUFFIX, STANDALONE_SUMMARY) for s in summaries}

    incomplete = sorted(phase_artifact_display_name(plan_id, STANDALONE_PLAN) for plan_id in (plan_ids - summary_ids))
    orphans = sorted(
        phase_artifact_display_name(summary_id, STANDALONE_SUMMARY) for summary_id in (summary_ids - plan_ids)
    )

    errors: list[str] = []
    warnings: list[str] = []
    if incomplete:
        errors.append(f"Plans without summaries: {', '.join(incomplete)}")
    if orphans:
        warnings.append(f"Summaries without plans: {', '.join(orphans)}")

    return PhaseCompleteness(
        complete=len(errors) == 0,
        phase_number=phase_info.phase_number,
        plan_count=len(plans),
        summary_count=matching_phase_artifact_count(plans, summaries),
        incomplete_plans=incomplete,
        orphan_summaries=orphans,
        errors=errors,
        warnings=warnings,
    )


# Patterns for file references
_AT_REF_RE = re.compile(r"@([^\s\n,)]+/[^\s\n,)]+)")
_BACKTICK_FILE_RE = re.compile(r"`([^`]+/[^`]+\.[a-zA-Z][a-zA-Z0-9]{0,9})`")


@instrument_gpd_function("frontmatter.verify_references")
def verify_references(cwd: Path, file_path: Path) -> ReferenceVerification:
    """Check that ``@path`` and backtick-quoted file paths actually exist on disk."""
    full_path = file_path if file_path.is_absolute() else cwd / file_path
    content = safe_read_file(full_path)
    if content is None:
        return ReferenceVerification(valid=False, missing=[str(file_path)])

    found: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    # @-references
    for m in _AT_REF_RE.finditer(content):
        ref = m.group(1)
        if ref in seen:
            continue
        seen.add(ref)
        resolved = Path.home() / ref[2:] if ref.startswith("~/") else cwd / ref
        (found if resolved.exists() else missing).append(ref)

    # Backtick file paths
    for m in _BACKTICK_FILE_RE.finditer(content):
        ref = m.group(1)
        if ref in seen or ref.startswith("http") or "${" in ref or "{{" in ref:
            continue
        seen.add(ref)
        resolved = cwd / ref
        (found if resolved.exists() else missing).append(ref)

    return ReferenceVerification(
        valid=len(missing) == 0,
        found=len(found),
        missing=missing,
        total=len(found) + len(missing),
    )


@instrument_gpd_function("frontmatter.verify_commits")
def verify_commits(cwd: Path, hashes: list[str]) -> CommitVerification:
    """Verify that git commit hashes exist in the repository."""
    if not hashes:
        raise FrontmatterValidationError("At least one commit hash required")

    valid: list[str] = []
    invalid: list[str] = []
    for h in hashes:
        exit_code, stdout = _exec_git(cwd, ["cat-file", "-t", h])
        if exit_code == 0 and stdout.strip() == "commit":
            valid.append(h)
        else:
            invalid.append(h)

    return CommitVerification(
        all_valid=len(invalid) == 0,
        valid_hashes=valid,
        invalid_hashes=invalid,
        total=len(hashes),
    )


@instrument_gpd_function("frontmatter.verify_artifacts")
def verify_artifacts(cwd: Path, plan_file_path: Path) -> ArtifactVerification:
    """Verify artifact deliverables declared in the canonical plan contract."""
    full_path = plan_file_path if plan_file_path.is_absolute() else cwd / plan_file_path
    content = safe_read_file(full_path)
    if content is None:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[ArtifactCheck(path=str(plan_file_path), issues=["Plan file not found"])],
            total=1,
        )

    try:
        contract = parse_contract_block(content, source_path=full_path)
    except FrontmatterValidationError as exc:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[ArtifactCheck(path=str(plan_file_path), issues=[str(exc)])],
            total=1,
        )

    if contract is None:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[ArtifactCheck(path=str(plan_file_path), issues=["Plan contract not found"])],
            total=1,
        )

    deliverables = [deliverable for deliverable in contract.deliverables if deliverable.path]
    if contract.deliverables and not deliverables:
        return ArtifactVerification(
            all_passed=False,
            passed_count=0,
            total=len(contract.deliverables),
            artifacts=[
                ArtifactCheck(
                    path=str(plan_file_path),
                    issues=["Plan contract declares deliverables, but none have a verifiable path"],
                )
            ],
        )
    if not deliverables:
        return ArtifactVerification(
            all_passed=True,
            artifacts=[],
            total=0,
        )

    results: list[ArtifactCheck] = []
    artifact_root = full_path.parent
    for deliverable in deliverables:
        art_path = str(deliverable.path)
        art_full = Path(art_path)
        if not art_full.is_absolute():
            art_full = artifact_root / art_full
        exists = art_full.exists()
        check = ArtifactCheck(path=art_path, exists=exists)

        if exists:
            file_content = safe_read_file(art_full) or ""
            for required_fragment in deliverable.must_contain:
                if required_fragment not in file_content:
                    check.issues.append(f"Missing pattern: {required_fragment}")

            check.passed = len(check.issues) == 0
        else:
            check.issues.append("File not found")

        results.append(check)

    passed_count = sum(1 for r in results if r.passed)
    return ArtifactVerification(
        all_passed=passed_count == len(results) and len(results) > 0,
        passed_count=passed_count,
        total=len(results),
        artifacts=results,
    )
