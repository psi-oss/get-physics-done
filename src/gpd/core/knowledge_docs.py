"""Strict models and parsing helpers for knowledge-document frontmatter."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from gpd.core.utils import normalize_ascii_slug

__all__ = [
    "KnowledgeCoverageSummary",
    "KnowledgeDocData",
    "KnowledgeReviewRecord",
    "KnowledgeSourceRecord",
    "compute_knowledge_reviewed_content_sha256",
    "knowledge_reviewed_content_projection",
    "parse_knowledge_doc_data_strict",
]

_KNOWLEDGE_STATUS_VALUES = ("draft", "in_review", "stable", "superseded")
_KNOWLEDGE_SOURCE_KIND_VALUES = ("paper", "dataset", "prior_artifact", "spec", "website", "other")
_KNOWLEDGE_REVIEW_DECISION_VALUES = ("approved", "needs_changes", "rejected")
_KNOWLEDGE_REVIEWER_KIND_VALUES = ("human", "agent", "workflow")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _normalize_required_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a non-empty string")
    stripped = value.strip()
    if not stripped:
        raise ValueError("expected a non-empty string")
    return stripped


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expected a string")
    stripped = value.strip()
    return stripped or None


def _normalize_choice(value: object, allowed_values: tuple[str, ...]) -> str:
    normalized = _normalize_required_text(value)
    if normalized not in allowed_values:
        raise ValueError(f"must be one of {', '.join(allowed_values)}")
    return normalized


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("expected a list of non-empty strings")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("expected a list of non-empty strings")
        stripped = item.strip()
        if not stripped:
            raise ValueError("expected a list of non-empty strings")
        normalized.append(stripped)
    return normalized


def _normalize_knowledge_id(value: object) -> str:
    normalized = _normalize_required_text(value)
    if not normalized.startswith("K-"):
        raise ValueError("must use canonical K-{ascii-hyphen-slug} format")
    slug = normalized[2:]
    if not slug or normalize_ascii_slug(slug) != slug:
        raise ValueError("must use canonical K-{ascii-hyphen-slug} format")
    return normalized


def _normalize_project_relative_path(value: object, field_name: str) -> str:
    normalized = _normalize_required_text(value)
    path = Path(normalized)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError(f"{field_name} must be a project-relative path")
    return normalized


def _normalize_sha256_digest(value: object, field_name: str) -> str:
    normalized = _normalize_required_text(value)
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase 64-hex sha256 digest")
    return normalized


class KnowledgeSourceRecord(BaseModel):
    """Typed provenance record for one source referenced by a knowledge doc."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    kind: Literal["paper", "dataset", "prior_artifact", "spec", "website", "other"] = "other"
    locator: str
    title: str
    why_it_matters: str
    source_artifacts: list[str] = Field(default_factory=list)
    reference_id: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    url: str | None = None

    @field_validator("source_id", "locator", "title", "why_it_matters", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_text(value)

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: object) -> object:
        return _normalize_choice(value, _KNOWLEDGE_SOURCE_KIND_VALUES)

    @field_validator("source_artifacts", mode="before")
    @classmethod
    def _normalize_source_artifacts(cls, value: object) -> object:
        return _normalize_string_list(value) if value is not None else []

    @field_validator("reference_id", "arxiv_id", "doi", "url", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def _validate_source_artifacts(self) -> KnowledgeSourceRecord:
        for artifact in self.source_artifacts:
            _normalize_project_relative_path(artifact, "source_artifacts entry")
        return self


class KnowledgeReviewRecord(BaseModel):
    """Typed review evidence required for stable knowledge docs."""

    model_config = ConfigDict(extra="forbid")

    reviewed_at: datetime
    review_round: int
    reviewer_kind: Literal["human", "agent", "workflow"]
    reviewer_id: str
    decision: Literal["approved", "needs_changes", "rejected"]
    summary: str
    approval_artifact_path: str
    approval_artifact_sha256: str
    reviewed_content_sha256: str
    stale: bool

    @field_validator("review_round", mode="before")
    @classmethod
    def _normalize_review_round(cls, value: object) -> object:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("expected a positive integer")
        if value < 1:
            raise ValueError("expected a positive integer")
        return value

    @field_validator("reviewer_kind", mode="before")
    @classmethod
    def _normalize_reviewer_kind(cls, value: object) -> object:
        return _normalize_choice(value, _KNOWLEDGE_REVIEWER_KIND_VALUES)

    @field_validator("reviewer_id", "summary", mode="before")
    @classmethod
    def _normalize_required_text_fields(cls, value: object) -> object:
        return _normalize_required_text(value)

    @field_validator("decision", mode="before")
    @classmethod
    def _normalize_decision(cls, value: object) -> object:
        return _normalize_choice(value, _KNOWLEDGE_REVIEW_DECISION_VALUES)

    @field_validator("approval_artifact_path", mode="before")
    @classmethod
    def _normalize_approval_artifact_path(cls, value: object) -> object:
        return _normalize_project_relative_path(value, "approval_artifact_path")

    @field_validator("approval_artifact_sha256", "reviewed_content_sha256", mode="before")
    @classmethod
    def _normalize_sha256_fields(cls, value: object, info: ValidationInfo) -> object:
        return _normalize_sha256_digest(value, str(info.field_name))

    @field_validator("stale", mode="before")
    @classmethod
    def _normalize_stale(cls, value: object) -> object:
        if not isinstance(value, bool):
            raise ValueError("expected a boolean")
        return value


class KnowledgeCoverageSummary(BaseModel):
    """Machine-readable statement of scope coverage for a knowledge doc."""

    model_config = ConfigDict(extra="forbid")

    covered_topics: list[str]
    excluded_topics: list[str]
    open_gaps: list[str]

    @field_validator("covered_topics", "excluded_topics", "open_gaps", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> object:
        return _normalize_string_list(value)


class KnowledgeDocData(BaseModel):
    """Strict frontmatter model for knowledge-document metadata."""

    model_config = ConfigDict(extra="forbid")

    knowledge_schema_version: Literal[1]
    knowledge_id: str
    title: str
    topic: str
    status: Literal["draft", "in_review", "stable", "superseded"]
    created_at: datetime
    updated_at: datetime
    sources: list[KnowledgeSourceRecord]
    coverage_summary: KnowledgeCoverageSummary
    review: KnowledgeReviewRecord | None = None
    superseded_by: str | None = None

    @field_validator("knowledge_id", mode="before")
    @classmethod
    def _normalize_knowledge_id(cls, value: object) -> object:
        return _normalize_knowledge_id(value)

    @field_validator("title", "topic", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_text(value)

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        return _normalize_choice(value, _KNOWLEDGE_STATUS_VALUES)

    @field_validator("superseded_by", mode="before")
    @classmethod
    def _normalize_superseded_by(cls, value: object) -> object:
        return _normalize_knowledge_id(value) if value is not None else None

    @model_validator(mode="after")
    def _validate_lifecycle(self) -> KnowledgeDocData:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be on or after created_at")
        if not self.sources:
            raise ValueError("sources must contain at least one source record")

        if self.status == "draft":
            if self.review is not None:
                raise ValueError("review is forbidden when status is draft")
            if self.superseded_by is not None:
                raise ValueError("superseded_by is forbidden when status is draft")
        elif self.status == "in_review":
            if self.superseded_by is not None:
                raise ValueError("superseded_by is forbidden when status is in_review")
            if self.review is not None and self.review.decision == "approved" and not self.review.stale:
                raise ValueError("review.stale must be true when status is in_review and review.decision is approved")
        elif self.status == "stable":
            if self.review is None:
                raise ValueError("review is required when status is stable")
            if self.review.decision != "approved":
                raise ValueError("review.decision must be approved when status is stable")
            if self.review.stale:
                raise ValueError("review.stale must be false when status is stable")
            if self.review.review_round < 1:
                raise ValueError("review.review_round must be a positive integer when status is stable")
            if self.superseded_by is not None:
                raise ValueError("superseded_by is forbidden when status is stable")
        else:
            if self.superseded_by is None:
                raise ValueError("superseded_by is required when status is superseded")
            if self.superseded_by == self.knowledge_id:
                raise ValueError("superseded_by must reference a different knowledge_id")

        return self


def knowledge_reviewed_content_projection(
    knowledge_doc: KnowledgeDocData,
    *,
    body_text: str = "",
) -> dict[str, object]:
    """Return the canonical trusted-content projection used for review freshness."""

    normalized_body = body_text.replace("\r\n", "\n").replace("\r", "\n")
    return {
        "knowledge_schema_version": knowledge_doc.knowledge_schema_version,
        "knowledge_id": knowledge_doc.knowledge_id,
        "title": knowledge_doc.title,
        "topic": knowledge_doc.topic,
        "sources": [source.model_dump(mode="python") for source in knowledge_doc.sources],
        "coverage_summary": knowledge_doc.coverage_summary.model_dump(mode="python"),
        "body_text": normalized_body,
    }


def compute_knowledge_reviewed_content_sha256(
    knowledge_doc: KnowledgeDocData,
    *,
    body_text: str = "",
) -> str:
    """Compute the canonical hash for the reviewed knowledge-document content."""

    projection = knowledge_reviewed_content_projection(knowledge_doc, body_text=body_text)
    payload = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_knowledge_doc_data_strict(
    knowledge_data: object,
    *,
    source_path: Path | None = None,
) -> KnowledgeDocData:
    """Parse strict knowledge-doc frontmatter data and enforce filename parity."""

    if not isinstance(knowledge_data, dict):
        raise ValueError("knowledge frontmatter must be an object")

    parsed = KnowledgeDocData.model_validate(knowledge_data)
    if source_path is not None and source_path.stem != parsed.knowledge_id:
        raise ValueError(
            f"knowledge_id must match the filename stem ({source_path.stem!r} != {parsed.knowledge_id!r})"
        )
    return parsed
