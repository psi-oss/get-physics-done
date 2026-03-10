"""Bibliography generation pipeline: pybtex + arXiv enrichment.

Creates BibTeX entries from research provenance data, enriches them
via arXiv APIs, and writes .bib files using pybtex.
"""

from __future__ import annotations

import logging
import re
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


def bibliography_entries_from_sources(sources: list[CitationSource]) -> list[tuple[str, Entry]]:
    """Build ordered `(key, entry)` pairs for citation sources.

    This is the single key-generation path for bibliography emission so
    other parts of the pipeline can reuse the exact emitted citation keys.
    """
    entries: list[tuple[str, Entry]] = []
    existing_keys: set[str] = set()

    for source in sources:
        key, entry = _source_to_entry(source, existing_keys)
        existing_keys.add(key)
        entries.append((key, entry))

    return entries


def citation_keys_for_sources(sources: list[CitationSource]) -> list[str]:
    """Return bibliography keys in the exact order they will be emitted."""
    return [key for key, _entry in bibliography_entries_from_sources(sources)]


def create_bibliography(sources: list[CitationSource]) -> BibliographyData:
    """Convert all citation sources to a BibliographyData object."""
    bib = BibliographyData()
    for key, entry in bibliography_entries_from_sources(sources):
        bib.entries[key] = entry

    return bib


def write_bib_file(bib_data: BibliographyData, output_path: Path) -> None:
    """Write a .bib file using pybtex."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bib_data.to_file(str(output_path), "bibtex")


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


def build_bibliography(sources: list[CitationSource], enrich: bool = True) -> BibliographyData:
    """Build a BibliographyData from citation sources with optional enrichment.

    This is the main public API for the bibliography module.

    Args:
        sources: List of citation sources from the provenance chain.
        enrich: If True, attempt arXiv enrichment for incomplete sources.
    """
    enriched = list(sources)

    if enrich:
        enriched = [enrich_from_arxiv(s) if s.arxiv_id else s for s in enriched]

    return create_bibliography(enriched)
