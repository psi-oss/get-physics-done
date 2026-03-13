"""Tests for bibliography pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gpd.mcp.paper.bibliography import (
    BibliographyAudit,
    CitationSource,
    audit_citation_source,
    build_bibliography,
    build_bibliography_with_audit,
    citation_keys_for_sources,
    create_bibliography,
    enrich_from_arxiv,
    write_bib_file,
    write_bibliography_audit,
)

# ---- BibTeX creation tests ----


class TestBibtexCreation:
    def test_paper_source_to_article_entry(self):
        sources = [CitationSource(source_type="paper", title="Test Paper", authors=["A. Einstein"], year="1905")]
        bib = create_bibliography(sources)
        assert len(bib.entries) == 1
        entry = list(bib.entries.values())[0]
        assert entry.type == "article"

    def test_tool_source_to_misc_entry(self):
        sources = [CitationSource(source_type="tool", title="OpenFOAM", year="2024")]
        bib = create_bibliography(sources)
        entry = list(bib.entries.values())[0]
        assert entry.type == "misc"

    def test_bib_key_generation(self):
        sources = [CitationSource(source_type="paper", title="Relativity", authors=["A. Einstein"], year="1905")]
        bib = create_bibliography(sources)
        keys = list(bib.entries.keys())
        assert keys[0].startswith("einstein1905")

    def test_bib_key_dedup(self):
        sources = [
            CitationSource(source_type="paper", title="Paper 1", authors=["A. Einstein"], year="1905"),
            CitationSource(source_type="paper", title="Paper 2", authors=["A. Einstein"], year="1905"),
        ]
        bib = create_bibliography(sources)
        keys = list(bib.entries.keys())
        assert len(keys) == 2
        assert keys[0] != keys[1]

    def test_citation_keys_match_bibliography_emission(self):
        sources = [
            CitationSource(source_type="paper", title="Paper 1", authors=["Einstein, Albert"], year="1905"),
            CitationSource(source_type="paper", title="Paper 2", authors=["A. Einstein"], year="1905"),
        ]
        assert citation_keys_for_sources(sources) == list(create_bibliography(sources).entries.keys())

    def test_citation_keys_match_enriched_emission(self):
        from datetime import datetime

        mock_author = MagicMock()
        mock_author.name = "A. Mock"

        mock_result = MagicMock()
        mock_result.title = "Mock Title"
        mock_result.authors = [mock_author]
        mock_result.published = datetime(2023, 1, 15)

        mock_arxiv = MagicMock()
        mock_arxiv.Search.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.results.return_value = [mock_result]
        mock_arxiv.Client.return_value = mock_client

        sources = [CitationSource(source_type="paper", title="", arxiv_id="2301.12345")]
        with patch.dict("sys.modules", {"arxiv": mock_arxiv}):
            keys = citation_keys_for_sources(sources, enrich=True)
        with patch.dict("sys.modules", {"arxiv": mock_arxiv}):
            bibliography, audit = build_bibliography_with_audit(sources, enrich=True)

        assert keys == list(bibliography.entries.keys())
        assert keys == [entry.key for entry in audit.entries]
        assert keys == ["mock2023"]

    def test_create_bibliography_multiple(self):
        sources = [
            CitationSource(source_type="paper", title="P1", authors=["A"], year="2020"),
            CitationSource(source_type="tool", title="T1", year="2021"),
            CitationSource(source_type="data", title="D1", year="2022"),
        ]
        bib = create_bibliography(sources)
        assert len(bib.entries) == 3

    def test_write_bib_file(self, tmp_path):
        sources = [
            CitationSource(source_type="paper", title="Test Paper", authors=["J. Smith"], year="2020", journal="ApJ")
        ]
        bib = create_bibliography(sources)
        output = tmp_path / "refs.bib"
        write_bib_file(bib, output)
        content = output.read_text()
        assert "@article" in content.lower() or "@misc" in content.lower()
        assert "Test Paper" in content


# ---- arXiv enrichment tests ----


class TestArxivEnrichment:
    def test_enrich_from_arxiv_no_package_raises(self):
        """When arxiv package import fails, error propagates."""
        source = CitationSource(
            source_type="paper",
            title="",
            arxiv_id="2301.12345",
        )
        with patch.dict("sys.modules", {"arxiv": None}):
            with pytest.raises(ImportError):
                enrich_from_arxiv(source)

    def test_enrich_from_arxiv_no_results_raises(self):
        """When arxiv returns no results, LookupError is raised."""
        mock_arxiv = MagicMock()
        mock_arxiv.Search.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.results.return_value = []
        mock_arxiv.Client.return_value = mock_client

        with patch.dict("sys.modules", {"arxiv": mock_arxiv}):
            source = CitationSource(
                source_type="paper",
                title="",
                arxiv_id="2301.12345",
            )
            with pytest.raises(LookupError, match="no results"):
                enrich_from_arxiv(source)

    def test_enrich_from_arxiv_fills_missing(self):
        """When arxiv package returns data, missing fields are filled."""
        from datetime import datetime

        mock_author = MagicMock()
        mock_author.name = "A. Mock"

        mock_result = MagicMock()
        mock_result.title = "Mock Title"
        mock_result.authors = [mock_author]
        mock_result.published = datetime(2023, 1, 15)

        mock_arxiv = MagicMock()
        mock_arxiv.Search.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.results.return_value = [mock_result]
        mock_arxiv.Client.return_value = mock_client

        with patch.dict("sys.modules", {"arxiv": mock_arxiv}):
            source = CitationSource(
                source_type="paper",
                title="",
                arxiv_id="2301.12345",
            )
            result = enrich_from_arxiv(source)
            assert result.title == "Mock Title"
            assert result.authors == ["A. Mock"]
            assert result.year == "2023"


# ---- Integration tests ----


class TestBuildBibliography:
    def test_build_bibliography_no_enrich(self):
        sources = [
            CitationSource(source_type="paper", title="Test", authors=["A"], year="2020"),
            CitationSource(source_type="tool", title="Tool", year="2021"),
        ]
        bib = build_bibliography(sources, enrich=False)
        assert len(bib.entries) == 2


class TestBibliographyAudit:
    def test_audit_citation_source_marks_provided_identifiers_as_partial(self):
        source = CitationSource(
            source_type="paper",
            title="A Paper",
            authors=["J. Smith"],
            year="2024",
            doi="10.1234/example",
        )

        resolved, record = audit_citation_source(source, enrich=False)

        assert resolved == source
        assert record.resolution_status == "provided"
        assert record.verification_status == "partial"
        assert record.canonical_identifiers == ["doi:10.1234/example"]
        assert record.missing_core_fields == []

    def test_build_bibliography_with_audit_records_successful_enrichment(self):
        from datetime import datetime

        mock_author = MagicMock()
        mock_author.name = "A. Mock"

        mock_result = MagicMock()
        mock_result.title = "Mock Title"
        mock_result.authors = [mock_author]
        mock_result.published = datetime(2023, 1, 15)

        mock_arxiv = MagicMock()
        mock_arxiv.Search.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.results.return_value = [mock_result]
        mock_arxiv.Client.return_value = mock_client

        with patch.dict("sys.modules", {"arxiv": mock_arxiv}):
            sources = [CitationSource(source_type="paper", title="", arxiv_id="2301.12345")]
            bib, audit = build_bibliography_with_audit(sources, enrich=True)

        assert len(bib.entries) == 1
        assert audit.total_sources == 1
        assert audit.resolved_sources == 1
        entry = audit.entries[0]
        assert entry.resolution_status == "enriched"
        assert entry.verification_status == "verified"
        assert entry.verification_sources == ["arXiv"]
        assert entry.enriched_fields == ["title", "authors", "year"]

    def test_build_bibliography_with_audit_records_failed_enrichment(self):
        mock_arxiv = MagicMock()
        mock_arxiv.Search.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.results.return_value = []
        mock_arxiv.Client.return_value = mock_client

        with patch.dict("sys.modules", {"arxiv": mock_arxiv}):
            bib, audit = build_bibliography_with_audit(
                [CitationSource(source_type="paper", title="", arxiv_id="2301.12345")],
                enrich=True,
            )

        assert len(bib.entries) == 1
        assert audit.failed_sources == 1
        entry = audit.entries[0]
        assert entry.resolution_status == "failed"
        assert entry.verification_status == "unverified"
        assert entry.errors
        assert "no results" in entry.errors[0]

    def test_write_bibliography_audit(self, tmp_path):
        audit = BibliographyAudit(
            generated_at="2026-03-10T00:00:00+00:00",
            total_sources=1,
            resolved_sources=0,
            partial_sources=1,
            unverified_sources=0,
            failed_sources=0,
            entries=[],
        )
        output = tmp_path / "bibliography-audit.json"

        write_bibliography_audit(audit, output)

        content = output.read_text(encoding="utf-8")
        assert '"total_sources": 1' in content
        assert '"partial_sources": 1' in content
