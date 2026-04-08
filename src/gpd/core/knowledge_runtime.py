"""Runtime discovery and lookup helpers for project knowledge documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gpd.core.frontmatter import compute_knowledge_reviewed_content_sha256, extract_frontmatter
from gpd.core.knowledge_docs import (
    KnowledgeDocData,
    parse_knowledge_doc_data_strict,
)
from gpd.core.knowledge_migration import classify_knowledge_doc_migration
from gpd.core.utils import normalize_ascii_slug

__all__ = [
    "KnowledgeDocDiscovery",
    "KnowledgeDocRuntimeRecord",
    "discover_knowledge_docs",
    "find_knowledge_doc_candidates",
]


@dataclass(frozen=True)
class KnowledgeDocRuntimeRecord:
    """Normalized runtime-facing view of one knowledge document."""

    path: str
    knowledge_id: str
    title: str
    topic: str
    status: str
    superseded_by: str | None
    review_fresh: bool | None
    runtime_active: bool
    review_round: int | None
    approval_artifact_path: str | None
    reviewer_kind: str | None
    reviewer_id: str | None
    decision: str | None
    reviewed_content_sha256: str | None
    stale: bool | None
    source_count: int
    covered_topics: tuple[str, ...] = ()
    excluded_topics: tuple[str, ...] = ()
    open_gaps: tuple[str, ...] = ()

    @property
    def is_fresh_approved(self) -> bool:
        return self.runtime_active

    def to_context_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "knowledge_id": self.knowledge_id,
            "title": self.title,
            "topic": self.topic,
            "status": self.status,
            "superseded_by": self.superseded_by,
            "review_fresh": self.review_fresh,
            "runtime_active": self.runtime_active,
            "review_round": self.review_round,
            "approval_artifact_path": self.approval_artifact_path,
            "reviewer_kind": self.reviewer_kind,
            "reviewer_id": self.reviewer_id,
            "decision": self.decision,
            "reviewed_content_sha256": self.reviewed_content_sha256,
            "stale": self.stale,
            "source_count": self.source_count,
            "covered_topics": list(self.covered_topics),
            "excluded_topics": list(self.excluded_topics),
            "open_gaps": list(self.open_gaps),
        }


@dataclass
class KnowledgeDocDiscovery:
    """Discovery payload for runtime knowledge-doc indexing."""

    records: list[KnowledgeDocRuntimeRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def status_counts(self) -> dict[str, int]:
        counts = {"draft": 0, "in_review": 0, "stable": 0, "superseded": 0}
        for record in self.records:
            counts[record.status] = counts.get(record.status, 0) + 1
        return counts

    def by_path(self) -> dict[str, KnowledgeDocRuntimeRecord]:
        return {record.path: record for record in self.records}

    def by_id(self) -> dict[str, KnowledgeDocRuntimeRecord]:
        return {record.knowledge_id: record for record in self.records}


def _relative_posix(root: Path, path: Path) -> str:
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _knowledge_doc_match_tokens(record: KnowledgeDocRuntimeRecord) -> set[str]:
    tokens = {
        record.path.casefold(),
        Path(record.path).name.casefold(),
        record.knowledge_id.casefold(),
        record.knowledge_id[2:].casefold(),
    }
    for text in (
        record.title,
        record.topic,
        *record.covered_topics,
        *record.excluded_topics,
        *record.open_gaps,
    ):
        slug = normalize_ascii_slug(text)
        if slug:
            tokens.add(slug.casefold())
    return tokens


def _record_from_parsed_doc(
    rel_path: str,
    parsed: KnowledgeDocData,
    content: str,
) -> KnowledgeDocRuntimeRecord:
    review_fresh: bool | None = None
    reviewer_kind: str | None = None
    reviewer_id: str | None = None
    decision: str | None = None
    reviewed_content_sha256: str | None = None
    stale: bool | None = None
    if parsed.review is not None:
        reviewer_kind = parsed.review.reviewer_kind
        reviewer_id = parsed.review.reviewer_id
        decision = parsed.review.decision
        reviewed_content_sha256 = parsed.review.reviewed_content_sha256
        stale = parsed.review.stale
        if parsed.review.decision == "approved":
            review_fresh = (
                parsed.review.stale is False
                and parsed.review.reviewed_content_sha256 == compute_knowledge_reviewed_content_sha256(content)
            )
        else:
            review_fresh = False
    runtime_active = parsed.status == "stable" and review_fresh is True
    return KnowledgeDocRuntimeRecord(
        path=rel_path,
        knowledge_id=parsed.knowledge_id,
        title=parsed.title,
        topic=parsed.topic,
        status=parsed.status,
        superseded_by=parsed.superseded_by,
        review_fresh=review_fresh,
        runtime_active=runtime_active,
        review_round=parsed.review.review_round if parsed.review is not None else None,
        approval_artifact_path=parsed.review.approval_artifact_path if parsed.review is not None else None,
        reviewer_kind=reviewer_kind,
        reviewer_id=reviewer_id,
        decision=decision,
        reviewed_content_sha256=reviewed_content_sha256,
        stale=stale,
        source_count=len(parsed.sources),
        covered_topics=tuple(parsed.coverage_summary.covered_topics),
        excluded_topics=tuple(parsed.coverage_summary.excluded_topics),
        open_gaps=tuple(parsed.coverage_summary.open_gaps),
    )


def discover_knowledge_docs(project_root: Path) -> KnowledgeDocDiscovery:
    """Discover and parse project knowledge documents for runtime use."""

    knowledge_dir = project_root / "GPD" / "knowledge"
    if not knowledge_dir.is_dir():
        return KnowledgeDocDiscovery()

    discovery = KnowledgeDocDiscovery()
    for path in sorted(knowledge_dir.glob("*.md")):
        rel_path = _relative_posix(project_root, path)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            discovery.warnings.append(f"could not read knowledge doc {rel_path}: {exc}")
            continue
        try:
            meta, body = extract_frontmatter(content)
            parsed = parse_knowledge_doc_data_strict(meta, source_path=path)
        except Exception as exc:  # pragma: no cover - fail-closed warning path
            migration_report = classify_knowledge_doc_migration(project_root, path, content=content)
            migration_hint = migration_report.summary()
            discovery.warnings.append(f"skipping knowledge doc {rel_path}: {exc}; {migration_hint}")
            continue
        del body
        discovery.records.append(_record_from_parsed_doc(rel_path, parsed, content))
    return discovery


def find_knowledge_doc_candidates(
    project_root: Path,
    token: str,
    *,
    statuses: tuple[str, ...] | None = None,
    active_only: bool = False,
) -> list[KnowledgeDocRuntimeRecord]:
    """Return exact knowledge-doc candidates for a path/id/topic-like token."""

    token_text = str(token or "").strip()
    if not token_text:
        return []

    filtered_statuses = {status.strip() for status in statuses or () if status and status.strip()}
    token_key = token_text.casefold()
    matches: list[KnowledgeDocRuntimeRecord] = []
    for record in discover_knowledge_docs(project_root).records:
        if filtered_statuses and record.status not in filtered_statuses:
            continue
        if active_only and not record.runtime_active:
            continue
        if token_key in _knowledge_doc_match_tokens(record):
            matches.append(record)
    return matches
