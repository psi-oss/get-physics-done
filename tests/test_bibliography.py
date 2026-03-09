"""Tests for bibliography pipeline."""

from __future__ import annotations

import urllib.error
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

from gpd.mcp.paper.bibliography import (
    CitationSource,
    build_bibliography,
    citation_keys_for_sources,
    create_bibliography,
    enrich_from_arxiv,
    enrich_with_ads,
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


# ---- ADS graceful degradation tests ----


class TestADSGracefulDegradation:
    def test_ads_no_token_returns_empty(self, monkeypatch):
        monkeypatch.delenv("ADS_API_TOKEN", raising=False)
        # Reset the warning flag
        import gpd.mcp.paper.bibliography as bib_mod

        bib_mod._ads_token_warned = False
        result = enrich_with_ads(["2015ApJS..219...21Z"])
        assert result == {}

    def test_ads_network_error_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ADS_API_TOKEN", "fake-token")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network error")):
            result = enrich_with_ads(["2015ApJS..219...21Z"])
            assert result == {}


# ---- arXiv enrichment tests ----


class TestArxivEnrichment:
    def test_enrich_from_arxiv_no_searcher(self, monkeypatch):
        """When ArxivSearcher import fails, source is returned unchanged."""
        source = CitationSource(
            source_type="paper",
            title="",
            arxiv_id="2301.12345",
        )
        with patch.dict("sys.modules", {"artifact_editor_engine.lvp.literature.arxiv_search": None}):
            result = enrich_from_arxiv(source)
            assert result.title == ""

    def test_enrich_from_arxiv_fills_missing(self, monkeypatch):
        """When ArxivSearcher returns data, missing fields are filled."""

        @dataclass
        class MockPaper:
            arxiv_id: str = "2301.12345"
            title: str = "Mock Title"
            authors: list[str] = field(default_factory=lambda: ["A. Mock"])
            abstract: str = ""
            categories: list[str] = field(default_factory=list)
            published: str = "2023-01-15"
            updated: str = ""
            pdf_url: str = ""
            html_url: str = ""

        mock_searcher = MagicMock()
        mock_searcher._search_arxiv.return_value = [MockPaper()]

        with patch(
            "gpd.mcp.paper.bibliography.enrich_from_arxiv",
            wraps=enrich_from_arxiv,
        ):
            # Patch the import inside enrich_from_arxiv
            mock_module = MagicMock()
            mock_module.ArxivSearcher.return_value = mock_searcher

            with patch.dict(
                "sys.modules",
                {"artifact_editor_engine.lvp.literature.arxiv_search": mock_module},
            ):
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

    def test_build_bibliography_enrich_graceful(self, monkeypatch):
        monkeypatch.delenv("ADS_API_TOKEN", raising=False)
        import gpd.mcp.paper.bibliography as bib_mod

        bib_mod._ads_token_warned = False

        sources = [
            CitationSource(source_type="paper", title="Test", authors=["A"], year="2020"),
            CitationSource(source_type="paper", title="ArXiv Paper", arxiv_id="2301.99999"),
        ]
        # Even with enrich=True, should not crash without ADS token or ArxivSearcher
        bib = build_bibliography(sources, enrich=True)
        assert len(bib.entries) == 2
