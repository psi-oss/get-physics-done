"""Runtime discovery and lookup helpers for project knowledge documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gpd.core.constants import ProjectLayout
from gpd.core.frontmatter import extract_frontmatter
from gpd.core.knowledge_docs import (
    KnowledgeDocData,
    compute_knowledge_reviewed_content_sha256,
    parse_knowledge_doc_data_strict,
)
from gpd.core.knowledge_migration import classify_knowledge_doc_migration
from gpd.core.small_utils import relative_posix_path
from gpd.core.utils import normalize_ascii_slug

__all__ = [
    "KnowledgeDocDiscovery",
    "KnowledgeDocResolution",
    "KnowledgeDocRuntimeRecord",
    "discover_knowledge_docs",
    "find_knowledge_doc_candidates",
    "iter_knowledge_supersession_chain",
    "load_knowledge_doc_inventory",
    "resolve_knowledge_doc",
    "search_knowledge_docs",
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


@dataclass(frozen=True, slots=True)
class KnowledgeDocResolution:
    """Deterministic knowledge-doc resolution result."""

    resolved: bool
    query: str
    record: KnowledgeDocRuntimeRecord | None = None
    candidates: tuple[KnowledgeDocRuntimeRecord, ...] = ()
    reason: str | None = None


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


def load_knowledge_doc_inventory(project_root: Path) -> KnowledgeDocDiscovery:
    return discover_knowledge_docs(project_root)


def discover_knowledge_docs(project_root: Path) -> KnowledgeDocDiscovery:
    """Discover and parse project knowledge documents for runtime use."""

    layout = ProjectLayout(project_root)
    knowledge_dir = layout.knowledge_dir
    if not knowledge_dir.is_dir():
        return KnowledgeDocDiscovery()

    discovery = KnowledgeDocDiscovery()
    for path in sorted(knowledge_dir.glob("*.md")):
        rel_path = relative_posix_path(project_root, path)
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


def _normalize_statuses(statuses: tuple[str, ...] | None) -> set[str]:
    return {status.strip() for status in statuses or () if status and status.strip()}


def _record_sort_key(record: KnowledgeDocRuntimeRecord) -> tuple[str, str]:
    return (record.path.casefold(), record.knowledge_id.casefold())


def _record_matches_filters(
    record: KnowledgeDocRuntimeRecord,
    *,
    statuses: set[str],
    active_only: bool,
) -> bool:
    if statuses and record.status not in statuses:
        return False
    if active_only and not record.runtime_active:
        return False
    return True


def _explicit_knowledge_target_aliases(project_root: object, token: str) -> set[str]:
    token_text = str(token or "").strip()
    if not token_text:
        return set()

    aliases = {token_text.casefold()}
    token_path = Path(token_text)
    if token_path.suffix.lower() == ".md":
        aliases.add(token_path.name.casefold())
    if token_text.casefold().startswith("k-"):
        aliases.add(token_text.casefold())

    root = Path(project_root)
    if token_path.is_absolute():
        try:
            aliases.add(token_path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix().casefold())
        except ValueError:
            pass
    else:
        aliases.add(token_path.as_posix().casefold())
    return aliases


def _record_exact_match(
    record: KnowledgeDocRuntimeRecord,
    *,
    aliases: set[str],
) -> bool:
    record_aliases = {
        record.path.casefold(),
        Path(record.path).name.casefold(),
        record.knowledge_id.casefold(),
    }
    return not aliases.isdisjoint(record_aliases)


def _search_exact_knowledge_docs(
    project_root: object,
    *,
    token: str,
    statuses: set[str],
    active_only: bool,
) -> tuple[KnowledgeDocRuntimeRecord, ...]:
    aliases = _explicit_knowledge_target_aliases(project_root, token)
    if not aliases:
        return ()
    inventory = load_knowledge_doc_inventory(project_root)
    matches = [
        record
        for record in inventory.records
        if _record_matches_filters(record, statuses=statuses, active_only=active_only)
        and _record_exact_match(record, aliases=aliases)
    ]
    return tuple(sorted(matches, key=_record_sort_key))


def search_knowledge_docs(
    project_root,
    *,
    token: str | None = None,
    statuses: tuple[str, ...] | None = None,
    active_only: bool = False,
) -> tuple[KnowledgeDocRuntimeRecord, ...]:
    """Return deterministic knowledge-doc matches for *token*."""

    if token is None:
        inventory = load_knowledge_doc_inventory(project_root)
        matches = tuple(
            record
            for record in inventory.records
            if _record_matches_filters(
                record,
                statuses=_normalize_statuses(statuses),
                active_only=active_only,
            )
        )
        return tuple(sorted(matches, key=_record_sort_key))

    token_text = str(token).strip()
    if not token_text:
        return ()

    normalized_statuses = _normalize_statuses(statuses)
    exact_matches = _search_exact_knowledge_docs(
        project_root,
        token=token_text,
        statuses=normalized_statuses,
        active_only=active_only,
    )
    if exact_matches:
        return exact_matches

    if token_text.casefold().startswith("k-") or token_text.endswith(".md") or "/" in token_text:
        return ()

    return tuple(
        sorted(
            find_knowledge_doc_candidates(
                project_root,
                token_text,
                statuses=statuses,
                active_only=active_only,
            ),
            key=_record_sort_key,
        )
    )


def _resolve_exact_or_unique_active(
    matches: tuple[KnowledgeDocRuntimeRecord, ...],
    *,
    query: str,
) -> KnowledgeDocResolution:
    if len(matches) == 1:
        match = matches[0]
        return KnowledgeDocResolution(
            resolved=True,
            query=query,
            record=match,
            candidates=matches,
        )

    reason = None
    if matches:
        reason = f"multiple knowledge docs match {query!r}: {', '.join(record.path for record in matches)}"
    else:
        reason = f"no knowledge doc matches {query!r}"
    return KnowledgeDocResolution(
        resolved=False,
        query=query,
        candidates=matches,
        reason=reason,
    )


def resolve_knowledge_doc(
    project_root,
    token: str,
    *,
    statuses: tuple[str, ...] | None = None,
    active_only: bool = False,
) -> KnowledgeDocResolution:
    """Resolve *token* to one exact knowledge doc or return an explicit ambiguity result."""

    token_text = str(token or "").strip()
    if not token_text:
        return KnowledgeDocResolution(resolved=False, query=token_text, reason="empty knowledge token")

    matches = search_knowledge_docs(
        project_root,
        token=token_text,
        statuses=statuses,
        active_only=active_only,
    )
    return _resolve_exact_or_unique_active(matches, query=token_text)


def iter_knowledge_supersession_chain(project_root, token: str) -> tuple[KnowledgeDocRuntimeRecord, ...]:
    """Follow `superseded_by` links from one knowledge doc until the chain ends."""

    inventory = load_knowledge_doc_inventory(project_root)
    by_id = inventory.by_id()
    resolution = resolve_knowledge_doc(project_root, token)
    if resolution.record is None:
        return ()

    chain: list[KnowledgeDocRuntimeRecord] = []
    seen: set[str] = set()
    current = resolution.record
    while current is not None and current.knowledge_id not in seen:
        chain.append(current)
        seen.add(current.knowledge_id)
        successor_id = current.superseded_by
        current = by_id.get(successor_id) if successor_id else None
    return tuple(chain)
