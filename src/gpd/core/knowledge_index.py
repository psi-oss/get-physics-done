"""Compatibility wrapper for runtime knowledge-doc discovery and lookup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gpd.core.knowledge_runtime import (
    KnowledgeDocDiscovery as KnowledgeDocInventory,
    KnowledgeDocRuntimeRecord as KnowledgeDocRecord,
    discover_knowledge_docs as load_knowledge_doc_inventory,
    find_knowledge_doc_candidates,
)

__all__ = [
    "KnowledgeDocInventory",
    "KnowledgeDocRecord",
    "KnowledgeDocResolution",
    "iter_knowledge_supersession_chain",
    "find_knowledge_doc_candidates",
    "load_knowledge_doc_inventory",
    "resolve_knowledge_doc",
    "search_knowledge_docs",
]


@dataclass(frozen=True, slots=True)
class KnowledgeDocResolution:
    """Deterministic knowledge-doc resolution result."""

    resolved: bool
    query: str
    record: KnowledgeDocRecord | None = None
    candidates: tuple[KnowledgeDocRecord, ...] = ()
    reason: str | None = None


def _normalize_statuses(statuses: tuple[str, ...] | None) -> set[str]:
    return {status.strip() for status in statuses or () if status and status.strip()}


def _record_sort_key(record: KnowledgeDocRecord) -> tuple[str, str]:
    return (record.path.casefold(), record.knowledge_id.casefold())


def _record_matches_filters(
    record: KnowledgeDocRecord,
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
    record: KnowledgeDocRecord,
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
) -> tuple[KnowledgeDocRecord, ...]:
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
) -> tuple[KnowledgeDocRecord, ...]:
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
    matches: tuple[KnowledgeDocRecord, ...],
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


def iter_knowledge_supersession_chain(project_root, token: str) -> tuple[KnowledgeDocRecord, ...]:
    """Follow `superseded_by` links from one knowledge doc until the chain ends."""

    inventory = load_knowledge_doc_inventory(project_root)
    by_id = inventory.by_id()
    resolution = resolve_knowledge_doc(project_root, token)
    if resolution.record is None:
        return ()

    chain: list[KnowledgeDocRecord] = []
    seen: set[str] = set()
    current = resolution.record
    while current is not None and current.knowledge_id not in seen:
        chain.append(current)
        seen.add(current.knowledge_id)
        successor_id = current.superseded_by
        current = by_id.get(successor_id) if successor_id else None
    return tuple(chain)
