"""Bibliography generation pipeline: pybtex + ADS/arXiv enrichment.

Creates BibTeX entries from research provenance data, enriches them
via NASA ADS and arXiv APIs, and writes .bib files using pybtex.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Literal

from pybtex.database import BibliographyData, Entry
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ADS_API_URL = "https://api.adsabs.harvard.edu/v1"

# Track whether we've already logged the ADS token suggestion
_ads_token_warned = False


class CitationSource(BaseModel):
    """A citation source from the research provenance chain."""

    source_type: Literal["paper", "tool", "data", "website"]
    title: str
    authors: list[str] = []
    year: str = ""
    arxiv_id: str | None = None
    doi: str | None = None
    bibcode: str | None = None
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

    # Deduplicate with a/b/c suffix
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        candidate = f"{base_key}{suffix}"
        if candidate not in existing_keys:
            return candidate

    return f"{base_key}_extra"


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


# ---- ADS API enrichment (graceful degradation) ----


def _get_ads_token() -> str | None:
    """Read ADS API token from environment variable."""
    return os.environ.get("ADS_API_TOKEN")


def enrich_with_ads(bibcodes: list[str]) -> dict[str, str]:
    """Export BibTeX for bibcodes from NASA ADS.

    Returns dict mapping bibcode -> BibTeX string.
    If no token or API fails, returns empty dict (graceful degradation).
    """
    global _ads_token_warned  # noqa: PLW0603

    token = _get_ads_token()
    if not token:
        if not _ads_token_warned:
            logger.info(
                "ADS_API_TOKEN not set. Set it for better bibliography quality. "
                "Get a token at https://ui.adsabs.harvard.edu/user/settings/token"
            )
            _ads_token_warned = True
        return {}

    try:
        payload = json.dumps({"bibcode": bibcodes}).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        req = urllib.request.Request(
            f"{ADS_API_URL}/export/bibtex",
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        export_text = result.get("export", "")
        # Parse into per-bibcode mapping
        mapping: dict[str, str] = {}
        for bibcode in bibcodes:
            if bibcode in export_text:
                mapping[bibcode] = export_text
        return mapping

    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        logger.debug("ADS API request failed; skipping enrichment", exc_info=True)
        return {}


def search_ads_by_title(title: str) -> list[dict]:
    """Search ADS by title to find bibcode and metadata.

    Returns list of result dicts. Gracefully returns [] on failure.
    """
    token = _get_ads_token()
    if not token:
        return []

    try:
        query = urllib.parse.quote(f'title:"{title}"')
        url = f"{ADS_API_URL}/search/query?q={query}&fl=bibcode,title,author,doi,year,pub&rows=3"
        headers = {"Authorization": f"Bearer {token}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return result.get("response", {}).get("docs", [])

    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        logger.debug("ADS search failed; returning empty", exc_info=True)
        return []


# ---- arXiv metadata to BibTeX ----


def enrich_from_arxiv(source: CitationSource) -> CitationSource:
    """Enrich a citation source with arXiv metadata if available.

    If source has arxiv_id but missing title/authors/year, look up via
    the ``arxiv`` Python package and fill in missing fields.  Returns
    updated source.  If the lookup fails, returns source unchanged.
    """
    if not source.arxiv_id:
        return source

    if source.title and source.authors and source.year:
        return source  # Already complete

    try:
        import arxiv

        search = arxiv.Search(id_list=[source.arxiv_id], max_results=1)
        client = arxiv.Client(delay_seconds=0.0, num_retries=1)
        results = list(client.results(search))
        if not results:
            return source

        paper = results[0]
        updated = source.model_copy(
            update={
                "title": source.title or paper.title,
                "authors": source.authors or [a.name for a in paper.authors],
                "year": source.year or (str(paper.published.year) if paper.published else ""),
            }
        )
        return updated

    except Exception:
        logger.debug("arxiv enrichment unavailable or failed; returning source unchanged")
        return source


# ---- Orchestrator ----


def build_bibliography(sources: list[CitationSource], enrich: bool = True) -> BibliographyData:
    """Build a BibliographyData from citation sources with optional enrichment.

    This is the main public API for the bibliography module.

    Args:
        sources: List of citation sources from the provenance chain.
        enrich: If True, attempt arXiv/ADS enrichment for incomplete sources.
    """
    enriched = list(sources)

    if enrich:
        # 1. arXiv enrichment for sources with arxiv_id
        enriched = [enrich_from_arxiv(s) if s.arxiv_id else s for s in enriched]

        # 2. ADS enrichment for sources with bibcode
        bibcodes = [s.bibcode for s in enriched if s.bibcode]
        if bibcodes:
            enrich_with_ads(bibcodes)
            # ADS enrichment currently returns raw BibTeX; for now we just
            # ensure the call doesn't crash. Full integration deferred.

    return create_bibliography(enriched)
