"""Tests for bibliography pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gpd.mcp.paper.bibliography import (
    CitationSource,
    build_bibliography,
    citation_keys_for_sources,
    create_bibliography,
    enrich_from_arxiv,
    write_bib_file,
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
