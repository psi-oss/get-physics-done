"""Persistent bibliography database with live linking.

Provides a JSON-backed bibliography database that tracks read/cited/relevant
status per reference and supports cross-referencing lookups for literature
review and writing workflows.

The database file lives at ``GPD/references/bibliography-db.json`` inside a
project and is the single persistent store that the bibliographer agent,
literature reviewer, and paper writer all read from and write to.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Iterator, Literal

from pydantic import BaseModel, Field

from gpd.mcp.paper.bibliography import CitationSource

logger = logging.getLogger(__name__)

# Default location relative to project root
DEFAULT_DB_PATH = Path("GPD/references/bibliography-db.json")


class ReadStatus(str, Enum):
    """Whether the reference has been read."""

    unread = "unread"
    skimmed = "skimmed"
    read = "read"
    studied = "studied"


class RelevanceLevel(str, Enum):
    """How relevant the reference is to the current project phase."""

    critical = "critical"  # Must surface in every downstream flow
    supporting = "supporting"  # Useful but not blocking
    background = "background"  # Context only
    tangential = "tangential"  # Noted but probably not needed


class VerificationStatus(str, Enum):
    """Verification state of the reference."""

    verified = "verified"
    pending = "pending"
    suspect = "suspect"
    not_found = "not_found"


class BibEntry(BaseModel):
    """A single entry in the bibliography database."""

    # Identity
    bib_key: str
    title: str
    authors: list[str] = []
    year: str = ""
    source_type: Literal["paper", "tool", "data", "website"] = "paper"

    # Identifiers
    arxiv_id: str | None = None
    doi: str | None = None
    url: str | None = None
    inspire_key: str | None = None

    # Publication details
    journal: str = ""
    volume: str = ""
    pages: str = ""

    # Status tracking
    read_status: ReadStatus = ReadStatus.unread
    cited: bool = False
    relevance: RelevanceLevel = RelevanceLevel.background
    verification: VerificationStatus = VerificationStatus.pending

    # Linking metadata
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    cited_by: list[str] = Field(default_factory=list)  # bib_keys that cite this entry
    cites: list[str] = Field(default_factory=list)  # bib_keys this entry cites
    related_to: list[str] = Field(default_factory=list)  # manually linked related entries
    project_phases: list[str] = Field(default_factory=list)  # phases where this is relevant
    added_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def matches_query(self, query: str) -> bool:
        """Check if this entry matches a free-text search query."""
        q = query.lower()
        searchable = " ".join([
            self.bib_key,
            self.title,
            " ".join(self.authors),
            self.year,
            self.journal,
            self.arxiv_id or "",
            self.doi or "",
            self.inspire_key or "",
            " ".join(self.tags),
            self.notes,
        ]).lower()
        return q in searchable

    def to_citation_source(self) -> CitationSource:
        """Convert back to a CitationSource for BibTeX generation."""
        return CitationSource(
            source_type=self.source_type,
            title=self.title,
            authors=list(self.authors),
            year=self.year,
            arxiv_id=self.arxiv_id,
            doi=self.doi,
            url=self.url,
            journal=self.journal,
            volume=self.volume,
            pages=self.pages,
        )


class BibliographyDBStats(BaseModel):
    """Summary statistics for the bibliography database."""

    total_entries: int = 0
    read_count: int = 0
    cited_count: int = 0
    verified_count: int = 0
    by_relevance: dict[str, int] = Field(default_factory=dict)
    by_read_status: dict[str, int] = Field(default_factory=dict)
    by_source_type: dict[str, int] = Field(default_factory=dict)


class BibliographyDB(BaseModel):
    """Persistent bibliography database with live linking.

    The database is a flat JSON file mapping bib_key -> BibEntry.
    It supports querying, filtering, and cross-referencing.
    """

    version: int = 1
    entries: dict[str, BibEntry] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    # ---- Persistence ----

    def save(self, path: Path) -> None:
        """Write the database to disk as JSON."""
        self.updated_at = datetime.now(UTC).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Bibliography DB saved to %s (%d entries)", path, len(self.entries))

    @classmethod
    def load(cls, path: Path) -> BibliographyDB:
        """Load the database from disk, or return an empty one."""
        if not path.exists():
            logger.info("No bibliography DB at %s, creating empty database", path)
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Failed to load bibliography DB from %s: %s", path, exc)
            return cls()

    # ---- Entry management ----

    def add_entry(self, entry: BibEntry, *, overwrite: bool = False) -> bool:
        """Add an entry. Returns True if added, False if key exists and overwrite=False."""
        if entry.bib_key in self.entries and not overwrite:
            return False
        entry.updated_at = datetime.now(UTC).isoformat()
        self.entries[entry.bib_key] = entry
        return True

    def add_from_citation_source(
        self,
        source: CitationSource,
        bib_key: str,
        *,
        relevance: RelevanceLevel = RelevanceLevel.background,
        tags: list[str] | None = None,
        notes: str = "",
        overwrite: bool = False,
    ) -> BibEntry:
        """Create a BibEntry from a CitationSource and add it to the database."""
        entry = BibEntry(
            bib_key=bib_key,
            title=source.title,
            authors=list(source.authors),
            year=source.year,
            source_type=source.source_type,
            arxiv_id=source.arxiv_id,
            doi=source.doi,
            url=source.url,
            journal=source.journal,
            volume=source.volume,
            pages=source.pages,
            relevance=relevance,
            tags=tags or [],
            notes=notes,
        )
        self.add_entry(entry, overwrite=overwrite)
        return entry

    def remove_entry(self, bib_key: str) -> bool:
        """Remove an entry by key. Returns True if removed."""
        if bib_key not in self.entries:
            return False
        # Clean up cross-references
        entry = self.entries[bib_key]
        for cited_key in entry.cites:
            if cited_key in self.entries:
                cited_entry = self.entries[cited_key]
                if bib_key in cited_entry.cited_by:
                    cited_entry.cited_by.remove(bib_key)
        for citing_key in entry.cited_by:
            if citing_key in self.entries:
                citing_entry = self.entries[citing_key]
                if bib_key in citing_entry.cites:
                    citing_entry.cites.remove(bib_key)
        for related_key in entry.related_to:
            if related_key in self.entries:
                related_entry = self.entries[related_key]
                if bib_key in related_entry.related_to:
                    related_entry.related_to.remove(bib_key)
        del self.entries[bib_key]
        return True

    def get_entry(self, bib_key: str) -> BibEntry | None:
        """Get an entry by its bib_key."""
        return self.entries.get(bib_key)

    # ---- Status updates ----

    def mark_read(self, bib_key: str, status: ReadStatus = ReadStatus.read) -> bool:
        """Update the read status of an entry."""
        entry = self.entries.get(bib_key)
        if entry is None:
            return False
        entry.read_status = status
        entry.updated_at = datetime.now(UTC).isoformat()
        return True

    def mark_cited(self, bib_key: str, cited: bool = True) -> bool:
        """Mark an entry as cited or uncited."""
        entry = self.entries.get(bib_key)
        if entry is None:
            return False
        entry.cited = cited
        entry.updated_at = datetime.now(UTC).isoformat()
        return True

    def set_relevance(self, bib_key: str, relevance: RelevanceLevel) -> bool:
        """Update the relevance level of an entry."""
        entry = self.entries.get(bib_key)
        if entry is None:
            return False
        entry.relevance = relevance
        entry.updated_at = datetime.now(UTC).isoformat()
        return True

    def set_verification(self, bib_key: str, status: VerificationStatus) -> bool:
        """Update the verification status of an entry."""
        entry = self.entries.get(bib_key)
        if entry is None:
            return False
        entry.verification = status
        entry.updated_at = datetime.now(UTC).isoformat()
        return True

    # ---- Live linking ----

    def add_citation_link(self, citing_key: str, cited_key: str) -> bool:
        """Record that citing_key cites cited_key.

        Returns True if the link was added, False if either key is missing.
        """
        citing = self.entries.get(citing_key)
        cited = self.entries.get(cited_key)
        if citing is None or cited is None:
            return False
        if cited_key not in citing.cites:
            citing.cites.append(cited_key)
        if citing_key not in cited.cited_by:
            cited.cited_by.append(citing_key)
        return True

    def add_related_link(self, key_a: str, key_b: str) -> bool:
        """Record that two entries are related (bidirectional).

        Returns True if the link was added, False if either key is missing.
        """
        entry_a = self.entries.get(key_a)
        entry_b = self.entries.get(key_b)
        if entry_a is None or entry_b is None:
            return False
        if key_b not in entry_a.related_to:
            entry_a.related_to.append(key_b)
        if key_a not in entry_b.related_to:
            entry_b.related_to.append(key_a)
        return True

    def get_citation_network(self, bib_key: str) -> dict[str, list[str]]:
        """Get the citation network around a specific entry.

        Returns a dict with ``cites``, ``cited_by``, and ``related_to`` keys,
        each containing a list of bib_keys.
        """
        entry = self.entries.get(bib_key)
        if entry is None:
            return {"cites": [], "cited_by": [], "related_to": []}
        return {
            "cites": list(entry.cites),
            "cited_by": list(entry.cited_by),
            "related_to": list(entry.related_to),
        }

    # ---- Query functions ----

    def search(self, query: str) -> list[BibEntry]:
        """Free-text search across all entries."""
        return [e for e in self.entries.values() if e.matches_query(query)]

    def filter_by_status(
        self,
        *,
        read_status: ReadStatus | None = None,
        cited: bool | None = None,
        relevance: RelevanceLevel | None = None,
        verification: VerificationStatus | None = None,
    ) -> list[BibEntry]:
        """Filter entries by one or more status fields."""
        results: list[BibEntry] = []
        for entry in self.entries.values():
            if read_status is not None and entry.read_status != read_status:
                continue
            if cited is not None and entry.cited != cited:
                continue
            if relevance is not None and entry.relevance != relevance:
                continue
            if verification is not None and entry.verification != verification:
                continue
            results.append(entry)
        return results

    def filter_by_tag(self, tag: str) -> list[BibEntry]:
        """Return all entries with the given tag."""
        tag_lower = tag.lower()
        return [e for e in self.entries.values() if tag_lower in [t.lower() for t in e.tags]]

    def filter_by_phase(self, phase: str) -> list[BibEntry]:
        """Return all entries relevant to a specific project phase."""
        return [e for e in self.entries.values() if phase in e.project_phases]

    def get_unread_relevant(self) -> list[BibEntry]:
        """Get entries that are critical or supporting but haven't been read."""
        return [
            e for e in self.entries.values()
            if e.read_status == ReadStatus.unread
            and e.relevance in (RelevanceLevel.critical, RelevanceLevel.supporting)
        ]

    def get_cited_entries(self) -> list[BibEntry]:
        """Get all entries that are marked as cited."""
        return [e for e in self.entries.values() if e.cited]

    def get_unverified_entries(self) -> list[BibEntry]:
        """Get all entries pending verification."""
        return [
            e for e in self.entries.values()
            if e.verification in (VerificationStatus.pending, VerificationStatus.suspect)
        ]

    def lookup_by_arxiv(self, arxiv_id: str) -> BibEntry | None:
        """Find an entry by arXiv ID."""
        for entry in self.entries.values():
            if entry.arxiv_id and entry.arxiv_id == arxiv_id:
                return entry
        return None

    def lookup_by_doi(self, doi: str) -> BibEntry | None:
        """Find an entry by DOI."""
        for entry in self.entries.values():
            if entry.doi and entry.doi == doi:
                return entry
        return None

    def iter_entries(self) -> Iterator[BibEntry]:
        """Iterate over all entries in insertion order."""
        yield from self.entries.values()

    # ---- Statistics ----

    def stats(self) -> BibliographyDBStats:
        """Compute summary statistics for the database."""
        by_relevance: dict[str, int] = {}
        by_read_status: dict[str, int] = {}
        by_source_type: dict[str, int] = {}
        read_count = 0
        cited_count = 0
        verified_count = 0

        for entry in self.entries.values():
            by_relevance[entry.relevance.value] = by_relevance.get(entry.relevance.value, 0) + 1
            by_read_status[entry.read_status.value] = by_read_status.get(entry.read_status.value, 0) + 1
            by_source_type[entry.source_type] = by_source_type.get(entry.source_type, 0) + 1
            if entry.read_status in (ReadStatus.read, ReadStatus.studied):
                read_count += 1
            if entry.cited:
                cited_count += 1
            if entry.verification == VerificationStatus.verified:
                verified_count += 1

        return BibliographyDBStats(
            total_entries=len(self.entries),
            read_count=read_count,
            cited_count=cited_count,
            verified_count=verified_count,
            by_relevance=by_relevance,
            by_read_status=by_read_status,
            by_source_type=by_source_type,
        )

    # ---- Bulk operations for workflow integration ----

    def export_citation_sources(
        self,
        *,
        cited_only: bool = False,
        relevance_min: RelevanceLevel | None = None,
    ) -> list[CitationSource]:
        """Export entries as CitationSource objects for BibTeX generation.

        Args:
            cited_only: If True, only export entries marked as cited.
            relevance_min: If set, only export entries at this relevance
                level or higher (critical > supporting > background > tangential).
        """
        relevance_order = [
            RelevanceLevel.critical,
            RelevanceLevel.supporting,
            RelevanceLevel.background,
            RelevanceLevel.tangential,
        ]
        min_idx = relevance_order.index(relevance_min) if relevance_min else len(relevance_order) - 1

        sources: list[CitationSource] = []
        for entry in self.entries.values():
            if cited_only and not entry.cited:
                continue
            entry_idx = relevance_order.index(entry.relevance)
            if entry_idx > min_idx:
                continue
            sources.append(entry.to_citation_source())
        return sources


def load_bibliography_db(project_root: Path) -> BibliographyDB:
    """Load (or create) the bibliography database for a project."""
    return BibliographyDB.load(project_root / DEFAULT_DB_PATH)


def save_bibliography_db(db: BibliographyDB, project_root: Path) -> None:
    """Save the bibliography database for a project."""
    db.save(project_root / DEFAULT_DB_PATH)
