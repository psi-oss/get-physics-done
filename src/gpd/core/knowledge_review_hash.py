"""Canonical reviewed-content hashing for knowledge documents."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Protocol, cast

import yaml

from gpd.core.strict_yaml import load_strict_yaml

__all__ = [
    "compute_knowledge_reviewed_content_sha256",
    "knowledge_reviewed_content_projection",
]


class _ModelDumpable(Protocol):
    def model_dump(self, *, mode: str) -> dict[str, object]: ...


_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)")
_EMPTY_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n---[ \t]*(?:\r?\n|$)")
_LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE = re.compile(r"^(?:[ \t]*\r?\n)+(?=---[ \t]*\r?\n)")


def _extract_hash_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """Extract frontmatter without importing ``frontmatter.py`` and creating a cycle."""

    clean = content.lstrip("\ufeff")
    candidate = _LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE.sub("", clean, count=1)

    match = _FRONTMATTER_RE.match(candidate)
    if match is not None:
        try:
            parsed = load_strict_yaml(match.group(1))
        except yaml.YAMLError as exc:
            raise ValueError(str(exc)) from exc
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected mapping, got {type(parsed).__name__}")
        return parsed, candidate[match.end() :]

    match = _EMPTY_FRONTMATTER_RE.match(candidate)
    if match is not None:
        return {}, candidate[match.end() :]

    return {}, clean


def _normalize_knowledge_review_inputs(
    knowledge_doc_or_content: object = None,
    *,
    body_text: str = "",
    meta: dict[str, object] | None = None,
    body: str | None = None,
) -> tuple[dict[str, object], str]:
    """Return ``(meta, body_text)`` for every supported reviewed-content input."""

    effective_body = body_text or (body if body is not None else "")
    if meta is not None:
        if not isinstance(meta, dict):
            raise TypeError("meta must be a mapping")
        return meta, effective_body
    if isinstance(knowledge_doc_or_content, str):
        extracted_meta, extracted_body = _extract_hash_frontmatter(knowledge_doc_or_content)
        return extracted_meta, effective_body or extracted_body
    if isinstance(knowledge_doc_or_content, dict):
        return knowledge_doc_or_content, effective_body
    if hasattr(knowledge_doc_or_content, "model_dump"):
        model = cast(_ModelDumpable, knowledge_doc_or_content)
        return model.model_dump(mode="python"), effective_body
    raise TypeError("expected a knowledge document, content string, or metadata mapping")


def knowledge_reviewed_content_projection(
    knowledge_doc_or_content: object = None,
    *,
    body_text: str = "",
    meta: dict[str, object] | None = None,
    body: str | None = None,
) -> dict[str, object]:
    """Return the canonical trust-bearing knowledge-doc projection."""

    normalized_meta, normalized_body = _normalize_knowledge_review_inputs(
        knowledge_doc_or_content,
        body_text=body_text,
        meta=meta,
        body=body,
    )
    return {
        "knowledge_schema_version": normalized_meta.get("knowledge_schema_version"),
        "knowledge_id": normalized_meta.get("knowledge_id"),
        "title": normalized_meta.get("title"),
        "topic": normalized_meta.get("topic"),
        "sources": _canonical_sources(normalized_meta.get("sources")),
        "coverage_summary": _canonical_coverage_summary(normalized_meta.get("coverage_summary")),
        "body": normalized_body.replace("\r\n", "\n").replace("\r", "\n"),
    }


def _canonical_sources(value: object) -> object:
    """Return source records without typed-model-only empty optional defaults."""

    if not isinstance(value, list):
        return value
    projected: list[object] = []
    ordered_keys = (
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
    )
    for item in value:
        if not isinstance(item, dict):
            projected.append(item)
            continue
        source = {}
        for key in ordered_keys:
            if key not in item:
                continue
            field_value = item[key]
            if field_value is None or field_value == []:
                continue
            source[key] = field_value
        projected.append(source)
    return projected


def _canonical_coverage_summary(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        key: value.get(key)
        for key in ("covered_topics", "excluded_topics", "open_gaps")
        if key in value
    }


def compute_knowledge_reviewed_content_sha256(
    knowledge_doc_or_content: object = None,
    *,
    body_text: str = "",
    meta: dict[str, object] | None = None,
    body: str | None = None,
) -> str:
    """Compute the canonical hash of the trust-bearing knowledge-doc projection."""

    projection = knowledge_reviewed_content_projection(
        knowledge_doc_or_content,
        body_text=body_text,
        meta=meta,
        body=body,
    )
    encoded = json.dumps(projection, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
