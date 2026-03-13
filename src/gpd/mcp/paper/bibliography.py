"""Bibliography generation pipeline: pybtex + arXiv enrichment.

Creates BibTeX entries from research provenance data, enriches them
via arXiv APIs, and writes .bib files using pybtex.

The module also exposes machine-readable audit helpers so higher-level
review and publication workflows can reason about citation quality
without reparsing BibTeX.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pybtex.database import BibliographyData, Entry
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CitationSource(BaseModel):
    """A citation source from the research provenance chain."""

    source_type: Literal["paper", "tool", "data", "website"]
    title: str
    authors: list[str] = []
    year: str = ""
    arxiv_id: str | None = None
    doi: str | None = None
    url: str | None = None
    journal: str = ""
    volume: str = ""
    pages: str = ""


CitationResolutionStatus = Literal["provided", "enriched", "incomplete", "failed"]
CitationVerificationStatus = Literal["verified", "partial", "unverified"]


class CitationAuditRecord(BaseModel):
    """Machine-readable audit record for a citation source."""

    key: str
    source_type: Literal["paper", "tool", "data", "website"]
    title: str
    resolution_status: CitationResolutionStatus
    verification_status: CitationVerificationStatus
    verification_sources: list[str] = []
    canonical_identifiers: list[str] = []
    missing_core_fields: list[str] = []
    enriched_fields: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []


class BibliographyAudit(BaseModel):
    """Summary audit artifact for a bibliography emission batch."""

    generated_at: str
    total_sources: int
    resolved_sources: int
    partial_sources: int
    unverified_sources: int
    failed_sources: int
    entries: list[CitationAuditRecord]


# ---- BibTeX entry creation ----


def _create_bib_key(source: CitationSource, existing_keys: set[str]) -> str:
    """Generate a BibTeX key from first author last name + year.

    Deduplicates by appending a/b/c suffix.
    """
    if source.authors:
        # Extract last name from first author (handle "First Last" and "Last, First")
        first_author = source.authors[0]
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            parts = first_author.strip().split()
            last_name = parts[-1] if parts else "unknown"
    else:
        last_name = "unknown"

    # Normalize: lowercase, remove non-alphanumeric
    last_name = re.sub(r"[^a-zA-Z]", "", last_name).lower()
    if not last_name:
        last_name = "unknown"

    base_key = f"{last_name}{source.year}"

    if base_key not in existing_keys:
        return base_key

    # Deduplicate with a/b/c suffix, then numeric suffixes for 27+
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        candidate = f"{base_key}{suffix}"
        if candidate not in existing_keys:
            return candidate

    n = 27
    while True:
        candidate = f"{base_key}_{n}"
        if candidate not in existing_keys:
            return candidate
        n += 1


_SOURCE_TYPE_TO_BIBTEX = {
    "paper": "article",
    "tool": "misc",
    "data": "misc",
    "website": "misc",
}


def _source_to_entry(source: CitationSource, existing_keys: set[str]) -> tuple[str, Entry]:
    """Convert a CitationSource to a pybtex Entry."""
    key = _create_bib_key(source, existing_keys)
    entry_type = _SOURCE_TYPE_TO_BIBTEX[source.source_type]

    fields: list[tuple[str, str]] = []
    if source.authors:
        fields.append(("author", " and ".join(source.authors)))
    fields.append(("title", source.title))
    if source.journal:
        fields.append(("journal", source.journal))
    if source.year:
        fields.append(("year", source.year))
    if source.volume:
        fields.append(("volume", source.volume))
    if source.pages:
        fields.append(("pages", source.pages))
    if source.doi:
        fields.append(("doi", source.doi))
    if source.url:
        fields.append(("url", source.url))
    if source.arxiv_id:
        fields.append(("note", f"arXiv:{source.arxiv_id}"))

    return key, Entry(entry_type, fields)


def _core_missing_fields(source: CitationSource) -> list[str]:
    """Return the minimal fields needed for a trustworthy paper-style citation."""
    missing: list[str] = []
    if not source.title.strip():
        missing.append("title")
    if not source.authors:
        missing.append("authors")
    if not source.year.strip():
        missing.append("year")
    return missing


def _canonical_identifiers(source: CitationSource) -> list[str]:
    """Return normalized identifiers usable by audit/reporting layers."""
    identifiers: list[str] = []
    if source.doi:
        identifiers.append(f"doi:{source.doi}")
    if source.arxiv_id:
        identifiers.append(f"arxiv:{source.arxiv_id}")
    if source.url:
        identifiers.append(f"url:{source.url}")
    return identifiers


def audit_citation_source(
    source: CitationSource,
    existing_keys: set[str] | None = None,
    *,
    enrich: bool = True,
) -> tuple[CitationSource, CitationAuditRecord]:
    """Audit one source and optionally enrich it before bibliography emission."""
    existing = existing_keys or set()
    original_missing = _core_missing_fields(source)
    resolved = source
    resolution_status: CitationResolutionStatus = "provided"
    verification_status: CitationVerificationStatus = "unverified"
    verification_sources: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    enriched_fields: list[str] = []

    if original_missing:
        resolution_status = "incomplete"

    should_enrich = bool(enrich and source.arxiv_id and original_missing)
    if should_enrich:
        try:
            resolved = enrich_from_arxiv(source)
        except Exception as exc:
            resolution_status = "failed"
            errors.append(str(exc))
        else:
            verification_sources.append("arXiv")
            enriched_fields = [
                field
                for field in ("title", "authors", "year")
                if (
                    (field == "authors" and not getattr(source, field) and getattr(resolved, field))
                    or (field != "authors" and not str(getattr(source, field)).strip() and str(getattr(resolved, field)).strip())
                )
            ]
            resolution_status = "enriched" if not _core_missing_fields(resolved) else "incomplete"
            verification_status = "verified" if resolution_status == "enriched" else "partial"

    missing_after = _core_missing_fields(resolved)
    identifiers = _canonical_identifiers(resolved)

    if resolution_status == "provided":
        if missing_after:
            resolution_status = "incomplete"
        elif identifiers:
            verification_status = "partial"
            warnings.append("Canonical identifiers were provided by the caller but not externally verified")

    if resolution_status == "incomplete" and not errors:
        warnings.append(f"Missing core citation fields: {', '.join(missing_after)}")
    if not identifiers:
        warnings.append("No canonical identifier available")

    key = _create_bib_key(resolved, existing)
    record = CitationAuditRecord(
        key=key,
        source_type=resolved.source_type,
        title=resolved.title,
        resolution_status=resolution_status,
        verification_status=verification_status,
        verification_sources=verification_sources,
        canonical_identifiers=identifiers,
        missing_core_fields=missing_after,
        enriched_fields=enriched_fields,
        warnings=warnings,
        errors=errors,
    )
    return resolved, record


def _resolve_sources_for_bibliography(
    sources: list[CitationSource],
    *,
    enrich: bool,
    existing_keys: set[str] | None = None,
) -> tuple[list[CitationSource], list[CitationAuditRecord]]:
    """Resolve citation sources and reserve keys exactly as bibliography emission will."""
    audited_sources: list[CitationSource] = []
    audit_entries: list[CitationAuditRecord] = []
    reserved_keys = set(existing_keys or ())

    for source in sources:
        resolved, audit_record = audit_citation_source(source, reserved_keys, enrich=enrich)
        audited_sources.append(resolved)
        audit_entries.append(audit_record)
        reserved_keys.add(audit_record.key)

    return audited_sources, audit_entries


def bibliography_entries_from_sources(
    sources: list[CitationSource],
    existing_keys: set[str] | None = None,
) -> list[tuple[str, Entry]]:
    """Build ordered `(key, entry)` pairs for citation sources.

    This is the single key-generation path for bibliography emission so
    other parts of the pipeline can reuse the exact emitted citation keys.
    """
    entries: list[tuple[str, Entry]] = []
    reserved_keys = set(existing_keys or ())

    for source in sources:
        key, entry = _source_to_entry(source, reserved_keys)
        reserved_keys.add(key)
        entries.append((key, entry))

    return entries


def citation_keys_for_sources(
    sources: list[CitationSource],
    *,
    enrich: bool = False,
    existing_keys: set[str] | None = None,
) -> list[str]:
    """Return bibliography keys in the exact order they will be emitted."""
    resolved_sources = sources
    if enrich:
        resolved_sources, _audit_entries = _resolve_sources_for_bibliography(
            sources,
            enrich=True,
            existing_keys=existing_keys,
        )
    return [key for key, _entry in bibliography_entries_from_sources(resolved_sources, existing_keys=existing_keys)]


def create_bibliography(
    sources: list[CitationSource],
    existing_keys: set[str] | None = None,
) -> BibliographyData:
    """Convert all citation sources to a BibliographyData object."""
    bib = BibliographyData()
    for key, entry in bibliography_entries_from_sources(sources, existing_keys=existing_keys):
        bib.entries[key] = entry

    return bib


def write_bib_file(bib_data: BibliographyData, output_path: Path) -> None:
    """Write a .bib file using pybtex."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bib_data.to_file(str(output_path), "bibtex")


def write_bibliography_audit(audit: BibliographyAudit, output_path: Path) -> None:
    """Write a machine-readable bibliography audit artifact as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(audit.model_dump_json(indent=2), encoding="utf-8")


# ---- arXiv metadata to BibTeX ----


def enrich_from_arxiv(source: CitationSource) -> CitationSource:
    """Enrich a citation source with arXiv metadata if available.

    If source has arxiv_id but missing title/authors/year, look up via
    the ``arxiv`` Python package and fill in missing fields.  Returns
    updated source.  Raises on failure.
    """
    if not source.arxiv_id:
        return source

    if source.title and source.authors and source.year:
        return source  # Already complete

    import arxiv

    search = arxiv.Search(id_list=[source.arxiv_id], max_results=1)
    client = arxiv.Client(delay_seconds=0.0, num_retries=1)
    results = list(client.results(search))
    if not results:
        raise LookupError(f"arXiv returned no results for {source.arxiv_id}")

    paper = results[0]
    return source.model_copy(
        update={
            "title": source.title or paper.title,
            "authors": source.authors or [a.name for a in paper.authors],
            "year": source.year or (str(paper.published.year) if paper.published else ""),
        }
    )


# ---- Orchestrator ----


def build_bibliography_with_audit(
    sources: list[CitationSource],
    enrich: bool = True,
    existing_keys: set[str] | None = None,
) -> tuple[BibliographyData, BibliographyAudit]:
    """Build both the BibTeX payload and a machine-readable audit artifact."""
    audited_sources, audit_entries = _resolve_sources_for_bibliography(
        sources,
        enrich=enrich,
        existing_keys=existing_keys,
    )
    emitted_entries = bibliography_entries_from_sources(audited_sources, existing_keys=existing_keys)
    normalized_audit_entries: list[CitationAuditRecord] = []
    bib = BibliographyData()
    for audit_entry, (key, entry) in zip(audit_entries, emitted_entries, strict=False):
        bib.entries[key] = entry
        if audit_entry.key == key:
            normalized_audit_entries.append(audit_entry)
        else:
            normalized_audit_entries.append(audit_entry.model_copy(update={"key": key}))

    audit = BibliographyAudit(
        generated_at=datetime.now(UTC).isoformat(),
        total_sources=len(normalized_audit_entries),
        resolved_sources=sum(
            1 for entry in normalized_audit_entries if entry.resolution_status in {"provided", "enriched"}
        ),
        partial_sources=sum(1 for entry in normalized_audit_entries if entry.verification_status == "partial"),
        unverified_sources=sum(1 for entry in normalized_audit_entries if entry.verification_status == "unverified"),
        failed_sources=sum(1 for entry in normalized_audit_entries if entry.resolution_status == "failed"),
        entries=normalized_audit_entries,
    )
    return bib, audit


def build_bibliography(sources: list[CitationSource], enrich: bool = True) -> BibliographyData:
    """Build a BibliographyData from citation sources with optional enrichment.

    This is the main public API for the bibliography module.

    Args:
        sources: List of citation sources from the provenance chain.
        enrich: If True, attempt arXiv enrichment for incomplete sources.
    """
    bib, _audit = build_bibliography_with_audit(sources, enrich=enrich)
    return bib
