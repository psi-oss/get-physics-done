"""Tests for persistent bibliography database with live linking."""

from __future__ import annotations

import json

import pytest

from gpd.mcp.paper.bibliography import CitationSource
from gpd.mcp.paper.bibliography_db import (
    BibEntry,
    BibliographyDB,
    ReadStatus,
    RelevanceLevel,
    VerificationStatus,
    load_bibliography_db,
    save_bibliography_db,
)


# ---- Fixtures ----


@pytest.fixture
def empty_db() -> BibliographyDB:
    return BibliographyDB()


@pytest.fixture
def sample_entry() -> BibEntry:
    return BibEntry(
        bib_key="einstein1905",
        title="On the Electrodynamics of Moving Bodies",
        authors=["A. Einstein"],
        year="1905",
        source_type="paper",
        doi="10.1002/andp.19053221004",
        tags=["relativity", "special-relativity"],
        relevance=RelevanceLevel.critical,
    )


@pytest.fixture
def populated_db(sample_entry: BibEntry) -> BibliographyDB:
    db = BibliographyDB()
    db.add_entry(sample_entry)
    db.add_entry(BibEntry(
        bib_key="dirac1928",
        title="The Quantum Theory of the Electron",
        authors=["P. A. M. Dirac"],
        year="1928",
        source_type="paper",
        journal="Proc. R. Soc. Lond. A",
        tags=["quantum-mechanics", "dirac-equation"],
        relevance=RelevanceLevel.supporting,
    ))
    db.add_entry(BibEntry(
        bib_key="weinberg1995",
        title="The Quantum Theory of Fields",
        authors=["S. Weinberg"],
        year="1995",
        source_type="paper",
        tags=["qft", "textbook"],
        relevance=RelevanceLevel.background,
        read_status=ReadStatus.studied,
    ))
    return db


# ---- Persistence tests ----


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path, populated_db: BibliographyDB):
        db_path = tmp_path / "GPD" / "references" / "bibliography-db.json"
        populated_db.save(db_path)

        assert db_path.exists()

        loaded = BibliographyDB.load(db_path)
        assert len(loaded.entries) == 3
        assert "einstein1905" in loaded.entries
        assert loaded.entries["einstein1905"].title == "On the Electrodynamics of Moving Bodies"

    def test_load_nonexistent_returns_empty(self, tmp_path):
        db = BibliographyDB.load(tmp_path / "nonexistent.json")
        assert len(db.entries) == 0

    def test_load_invalid_json_returns_empty(self, tmp_path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("not json at all")
        db = BibliographyDB.load(bad_path)
        assert len(db.entries) == 0

    def test_save_creates_parent_dirs(self, tmp_path):
        db = BibliographyDB()
        db.add_entry(BibEntry(bib_key="test2024", title="Test"))
        nested_path = tmp_path / "deep" / "nested" / "dir" / "db.json"
        db.save(nested_path)
        assert nested_path.exists()

    def test_project_load_save_helpers(self, tmp_path):
        db = load_bibliography_db(tmp_path)
        assert len(db.entries) == 0
        db.add_entry(BibEntry(bib_key="test2024", title="Test Paper"))
        save_bibliography_db(db, tmp_path)
        reloaded = load_bibliography_db(tmp_path)
        assert len(reloaded.entries) == 1


# ---- Entry management tests ----


class TestEntryManagement:
    def test_add_entry(self, empty_db: BibliographyDB, sample_entry: BibEntry):
        assert empty_db.add_entry(sample_entry) is True
        assert len(empty_db.entries) == 1

    def test_add_duplicate_returns_false(self, empty_db: BibliographyDB, sample_entry: BibEntry):
        empty_db.add_entry(sample_entry)
        assert empty_db.add_entry(sample_entry) is False
        assert len(empty_db.entries) == 1

    def test_add_duplicate_with_overwrite(self, empty_db: BibliographyDB, sample_entry: BibEntry):
        empty_db.add_entry(sample_entry)
        updated = sample_entry.model_copy(update={"title": "Updated Title"})
        assert empty_db.add_entry(updated, overwrite=True) is True
        assert empty_db.entries["einstein1905"].title == "Updated Title"

    def test_get_entry(self, populated_db: BibliographyDB):
        entry = populated_db.get_entry("einstein1905")
        assert entry is not None
        assert entry.title == "On the Electrodynamics of Moving Bodies"

    def test_get_nonexistent_entry(self, populated_db: BibliographyDB):
        assert populated_db.get_entry("nonexistent") is None

    def test_remove_entry(self, populated_db: BibliographyDB):
        assert populated_db.remove_entry("einstein1905") is True
        assert "einstein1905" not in populated_db.entries
        assert len(populated_db.entries) == 2

    def test_remove_nonexistent_entry(self, populated_db: BibliographyDB):
        assert populated_db.remove_entry("nonexistent") is False

    def test_remove_entry_cleans_cross_references(self, empty_db: BibliographyDB):
        empty_db.add_entry(BibEntry(bib_key="a", title="Paper A"))
        empty_db.add_entry(BibEntry(bib_key="b", title="Paper B"))
        empty_db.add_citation_link("a", "b")
        empty_db.add_related_link("a", "b")

        assert "a" in empty_db.entries["b"].cited_by
        assert "a" in empty_db.entries["b"].related_to

        empty_db.remove_entry("a")

        assert "a" not in empty_db.entries["b"].cited_by
        assert "a" not in empty_db.entries["b"].related_to

    def test_add_from_citation_source(self, empty_db: BibliographyDB):
        source = CitationSource(
            source_type="paper",
            title="Test Paper",
            authors=["J. Smith"],
            year="2024",
            doi="10.1234/test",
            arxiv_id="2401.12345",
        )
        entry = empty_db.add_from_citation_source(
            source, "smith2024",
            relevance=RelevanceLevel.critical,
            tags=["test"],
            notes="A test note",
        )
        assert entry.bib_key == "smith2024"
        assert entry.title == "Test Paper"
        assert entry.relevance == RelevanceLevel.critical
        assert entry.tags == ["test"]
        assert "smith2024" in empty_db.entries


# ---- Status tracking tests ----


class TestStatusTracking:
    def test_mark_read(self, populated_db: BibliographyDB):
        assert populated_db.mark_read("einstein1905", ReadStatus.read) is True
        assert populated_db.entries["einstein1905"].read_status == ReadStatus.read

    def test_mark_read_nonexistent(self, populated_db: BibliographyDB):
        assert populated_db.mark_read("nonexistent") is False

    def test_mark_cited(self, populated_db: BibliographyDB):
        assert populated_db.mark_cited("einstein1905") is True
        assert populated_db.entries["einstein1905"].cited is True

    def test_mark_cited_nonexistent(self, populated_db: BibliographyDB):
        assert populated_db.mark_cited("nonexistent") is False

    def test_set_relevance(self, populated_db: BibliographyDB):
        assert populated_db.set_relevance("dirac1928", RelevanceLevel.critical) is True
        assert populated_db.entries["dirac1928"].relevance == RelevanceLevel.critical

    def test_set_verification(self, populated_db: BibliographyDB):
        assert populated_db.set_verification("einstein1905", VerificationStatus.verified) is True
        assert populated_db.entries["einstein1905"].verification == VerificationStatus.verified


# ---- Live linking tests ----


class TestLiveLinking:
    def test_add_citation_link(self, populated_db: BibliographyDB):
        assert populated_db.add_citation_link("dirac1928", "einstein1905") is True
        assert "einstein1905" in populated_db.entries["dirac1928"].cites
        assert "dirac1928" in populated_db.entries["einstein1905"].cited_by

    def test_add_citation_link_idempotent(self, populated_db: BibliographyDB):
        populated_db.add_citation_link("dirac1928", "einstein1905")
        populated_db.add_citation_link("dirac1928", "einstein1905")
        assert populated_db.entries["dirac1928"].cites.count("einstein1905") == 1
        assert populated_db.entries["einstein1905"].cited_by.count("dirac1928") == 1

    def test_add_citation_link_missing_key(self, populated_db: BibliographyDB):
        assert populated_db.add_citation_link("dirac1928", "nonexistent") is False

    def test_add_related_link(self, populated_db: BibliographyDB):
        assert populated_db.add_related_link("einstein1905", "dirac1928") is True
        assert "dirac1928" in populated_db.entries["einstein1905"].related_to
        assert "einstein1905" in populated_db.entries["dirac1928"].related_to

    def test_add_related_link_idempotent(self, populated_db: BibliographyDB):
        populated_db.add_related_link("einstein1905", "dirac1928")
        populated_db.add_related_link("einstein1905", "dirac1928")
        assert populated_db.entries["einstein1905"].related_to.count("dirac1928") == 1

    def test_get_citation_network(self, populated_db: BibliographyDB):
        populated_db.add_citation_link("dirac1928", "einstein1905")
        populated_db.add_related_link("einstein1905", "weinberg1995")

        network = populated_db.get_citation_network("einstein1905")
        assert "dirac1928" in network["cited_by"]
        assert "weinberg1995" in network["related_to"]

    def test_get_citation_network_nonexistent(self, populated_db: BibliographyDB):
        network = populated_db.get_citation_network("nonexistent")
        assert network == {"cites": [], "cited_by": [], "related_to": []}


# ---- Query tests ----


class TestQueries:
    def test_search_by_title(self, populated_db: BibliographyDB):
        results = populated_db.search("electrodynamics")
        assert len(results) == 1
        assert results[0].bib_key == "einstein1905"

    def test_search_by_author(self, populated_db: BibliographyDB):
        results = populated_db.search("dirac")
        assert len(results) == 1
        assert results[0].bib_key == "dirac1928"

    def test_search_by_tag(self, populated_db: BibliographyDB):
        results = populated_db.search("qft")
        assert len(results) == 1
        assert results[0].bib_key == "weinberg1995"

    def test_search_case_insensitive(self, populated_db: BibliographyDB):
        results = populated_db.search("EINSTEIN")
        assert len(results) == 1

    def test_filter_by_read_status(self, populated_db: BibliographyDB):
        results = populated_db.filter_by_status(read_status=ReadStatus.studied)
        assert len(results) == 1
        assert results[0].bib_key == "weinberg1995"

    def test_filter_by_cited(self, populated_db: BibliographyDB):
        populated_db.mark_cited("einstein1905")
        results = populated_db.filter_by_status(cited=True)
        assert len(results) == 1

    def test_filter_by_relevance(self, populated_db: BibliographyDB):
        results = populated_db.filter_by_status(relevance=RelevanceLevel.critical)
        assert len(results) == 1
        assert results[0].bib_key == "einstein1905"

    def test_filter_by_verification(self, populated_db: BibliographyDB):
        populated_db.set_verification("einstein1905", VerificationStatus.verified)
        results = populated_db.filter_by_status(verification=VerificationStatus.verified)
        assert len(results) == 1

    def test_filter_combined(self, populated_db: BibliographyDB):
        populated_db.mark_read("einstein1905", ReadStatus.read)
        results = populated_db.filter_by_status(
            read_status=ReadStatus.read,
            relevance=RelevanceLevel.critical,
        )
        assert len(results) == 1
        assert results[0].bib_key == "einstein1905"

    def test_filter_by_tag(self, populated_db: BibliographyDB):
        results = populated_db.filter_by_tag("relativity")
        assert len(results) == 1
        assert results[0].bib_key == "einstein1905"

    def test_filter_by_tag_case_insensitive(self, populated_db: BibliographyDB):
        results = populated_db.filter_by_tag("RELATIVITY")
        assert len(results) == 1

    def test_filter_by_phase(self, populated_db: BibliographyDB):
        populated_db.entries["einstein1905"].project_phases.append("phase-1")
        results = populated_db.filter_by_phase("phase-1")
        assert len(results) == 1

    def test_get_unread_relevant(self, populated_db: BibliographyDB):
        results = populated_db.get_unread_relevant()
        # einstein1905 is critical + unread, dirac1928 is supporting + unread
        assert len(results) == 2

    def test_get_cited_entries(self, populated_db: BibliographyDB):
        populated_db.mark_cited("einstein1905")
        results = populated_db.get_cited_entries()
        assert len(results) == 1

    def test_get_unverified_entries(self, populated_db: BibliographyDB):
        # All entries start as pending
        results = populated_db.get_unverified_entries()
        assert len(results) == 3

    def test_lookup_by_arxiv(self, populated_db: BibliographyDB):
        populated_db.entries["einstein1905"].arxiv_id = "physics/0503066"
        result = populated_db.lookup_by_arxiv("physics/0503066")
        assert result is not None
        assert result.bib_key == "einstein1905"

    def test_lookup_by_arxiv_not_found(self, populated_db: BibliographyDB):
        assert populated_db.lookup_by_arxiv("9999.99999") is None

    def test_lookup_by_doi(self, populated_db: BibliographyDB):
        result = populated_db.lookup_by_doi("10.1002/andp.19053221004")
        assert result is not None
        assert result.bib_key == "einstein1905"

    def test_lookup_by_doi_not_found(self, populated_db: BibliographyDB):
        assert populated_db.lookup_by_doi("10.9999/nonexistent") is None


# ---- Statistics tests ----


class TestStatistics:
    def test_stats_empty_db(self, empty_db: BibliographyDB):
        s = empty_db.stats()
        assert s.total_entries == 0
        assert s.read_count == 0
        assert s.cited_count == 0

    def test_stats_populated_db(self, populated_db: BibliographyDB):
        populated_db.mark_cited("einstein1905")
        populated_db.set_verification("einstein1905", VerificationStatus.verified)
        s = populated_db.stats()
        assert s.total_entries == 3
        assert s.read_count == 1  # weinberg1995 is studied
        assert s.cited_count == 1
        assert s.verified_count == 1
        assert s.by_relevance["critical"] == 1
        assert s.by_relevance["supporting"] == 1
        assert s.by_relevance["background"] == 1


# ---- Export tests ----


class TestExport:
    def test_export_all_citation_sources(self, populated_db: BibliographyDB):
        sources = populated_db.export_citation_sources()
        assert len(sources) == 3
        assert all(isinstance(s, CitationSource) for s in sources)

    def test_export_cited_only(self, populated_db: BibliographyDB):
        populated_db.mark_cited("einstein1905")
        sources = populated_db.export_citation_sources(cited_only=True)
        assert len(sources) == 1
        assert sources[0].title == "On the Electrodynamics of Moving Bodies"

    def test_export_relevance_filter(self, populated_db: BibliographyDB):
        sources = populated_db.export_citation_sources(relevance_min=RelevanceLevel.supporting)
        assert len(sources) == 2  # critical + supporting, not background


# ---- BibEntry model tests ----


class TestBibEntry:
    def test_matches_query_title(self):
        entry = BibEntry(bib_key="test", title="Quantum Field Theory")
        assert entry.matches_query("quantum")
        assert not entry.matches_query("relativity")

    def test_to_citation_source_roundtrip(self, sample_entry: BibEntry):
        source = sample_entry.to_citation_source()
        assert source.title == sample_entry.title
        assert source.authors == sample_entry.authors
        assert source.doi == sample_entry.doi

    def test_iter_entries(self, populated_db: BibliographyDB):
        keys = [e.bib_key for e in populated_db.iter_entries()]
        assert len(keys) == 3
        assert "einstein1905" in keys
