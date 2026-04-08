"""Strict models and parsing helpers for knowledge-document frontmatter."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gpd.core.utils import normalize_ascii_slug

__all__ = [
    "KnowledgeCoverageSummary",
    "KnowledgeDocData",
    "KnowledgeReviewRecord",
    "KnowledgeSourceRecord",
    "parse_knowledge_doc_data_strict",
]

_KNOWLEDGE_STATUS_VALUES = ("draft", "stable", "superseded")
_KNOWLEDGE_SOURCE_KIND_VALUES = ("paper", "dataset", "prior_artifact", "spec", "website", "other")
_KNOWLEDGE_REVIEW_DECISION_VALUES = ("approved", "needs_changes", "rejected")


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
            if Path(artifact).is_absolute():
                raise ValueError("source_artifacts entries must be project-relative paths")
        return self


class KnowledgeReviewRecord(BaseModel):
    """Typed review evidence required for stable knowledge docs."""

    model_config = ConfigDict(extra="forbid")

    reviewed_at: datetime
    reviewer: str
    decision: Literal["approved", "needs_changes", "rejected"]
    summary: str
    evidence_path: str | None = None
    evidence_sha256: str | None = None
    audit_artifact_path: str | None = None
    commit_sha: str | None = None
    trace_id: str | None = None

    @field_validator("reviewer", "summary", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: object) -> object:
        return _normalize_required_text(value)

    @field_validator("decision", mode="before")
    @classmethod
    def _normalize_decision(cls, value: object) -> object:
        return _normalize_choice(value, _KNOWLEDGE_REVIEW_DECISION_VALUES)

    @field_validator("evidence_path", "evidence_sha256", "audit_artifact_path", "commit_sha", "trace_id", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def _validate_evidence(self) -> KnowledgeReviewRecord:
        if not any((self.evidence_path, self.audit_artifact_path, self.commit_sha, self.trace_id)):
            raise ValueError(
                "review requires at least one concrete evidence pointer: "
                "evidence_path, audit_artifact_path, commit_sha, or trace_id"
            )
        return self


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
    status: Literal["draft", "stable", "superseded"]
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
        elif self.status == "stable":
            if self.review is None:
                raise ValueError("review is required when status is stable")
            if self.review.decision != "approved":
                raise ValueError("review.decision must be approved when status is stable")
            if self.superseded_by is not None:
                raise ValueError("superseded_by is forbidden when status is stable")
        else:
            if self.superseded_by is None:
                raise ValueError("superseded_by is required when status is superseded")
            if self.superseded_by == self.knowledge_id:
                raise ValueError("superseded_by must reference a different knowledge_id")

        return self


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
