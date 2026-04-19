"""Tests for bibliography pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pybtex.database import BibliographyData, Entry, Person
from pydantic import ValidationError

from gpd.mcp.paper.bibliography import (
    BibliographyAudit,
    CitationSource,
    audit_bibliography,
    audit_citation_source,
    build_bibliography,
    build_bibliography_with_audit,
    citation_keys_for_sources,
    create_bibliography,
    enrich_from_arxiv,
    parse_citation_source_payload,
    parse_citation_source_sidecar_payload,
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

    def test_generated_bib_key_sanitizes_year_component(self):
        sources = [CitationSource(source_type="paper", title="Odd Year", authors=["J. Smith"], year="in press, 2026")]
        bib = create_bibliography(sources)

        assert list(bib.entries.keys()) == ["smithinpress2026"]

    def test_bib_key_dedup(self):
        sources = [
            CitationSource(source_type="paper", title="Paper 1", authors=["A. Einstein"], year="1905"),
            CitationSource(source_type="paper", title="Paper 2", authors=["A. Einstein"], year="1905"),
        ]
        bib = create_bibliography(sources)
        keys = list(bib.entries.keys())
        assert len(keys) == 2
        assert keys[0] != keys[1]

    def test_preferred_bibtex_key_is_used_when_available(self):
        sources = [
            CitationSource(
                source_type="paper",
                title="Relativity",
                authors=["A. Einstein"],
                year="1905",
                bibtex_key="einstein-relativity",
            )
        ]

        bib = create_bibliography(sources)

        assert list(bib.entries.keys()) == ["einstein-relativity"]

    def test_preferred_bibtex_key_dedups_predictably(self):
        sources = [
            CitationSource(
                source_type="paper",
                title="Paper 1",
                authors=["A. Einstein"],
                year="1905",
                bibtex_key="shared-key",
            ),
            CitationSource(
                source_type="paper",
                title="Paper 2",
                authors=["A. Bohr"],
                year="1913",
                bibtex_key="shared-key",
            ),
        ]

        bib = create_bibliography(sources)

        assert list(bib.entries.keys()) == ["shared-key", "shared-keya"]

    @pytest.mark.parametrize("bibtex_key", ["bad key", "bad,key", "{bad}", "1bad", "bad/key"])
    def test_preferred_bibtex_key_rejects_unsafe_values(self, bibtex_key: str):
        sources = [
            CitationSource(
                source_type="paper",
                title="Relativity",
                authors=["A. Einstein"],
                year="1905",
                bibtex_key=bibtex_key,
            )
        ]

        with pytest.raises(ValueError, match="preferred bibtex_key"):
            create_bibliography(sources)

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


class TestCitationSourceParsing:
    def test_parse_citation_source_payload_normalizes_reference_id(self) -> None:
        source = parse_citation_source_payload(
            {
                "reference_id": "  lit-ref-001  ",
                "source_type": "paper",
                "title": "Benchmark Paper",
            }
        )

        assert source.reference_id == "lit-ref-001"
        assert source.source_type == "paper"
        assert source.title == "Benchmark Paper"

    def test_parse_citation_source_payload_rejects_unknown_keys(self) -> None:
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            parse_citation_source_payload(
                {
                    "reference_id": "lit-ref-001",
                    "source_type": "paper",
                    "title": "Benchmark Paper",
                    "legacy_note": "stale",
                }
            )

    def test_parse_citation_source_payload_rejects_blank_reference_id(self) -> None:
        with pytest.raises(ValueError, match="reference_id must be a non-empty string"):
            parse_citation_source_payload(
                {
                    "reference_id": "   ",
                    "source_type": "paper",
                    "title": "Benchmark Paper",
                }
            )

    def test_parse_citation_source_payload_rejects_blank_title(self) -> None:
        with pytest.raises(ValueError, match=r"title must be a non-empty string"):
            parse_citation_source_payload(
                {
                    "reference_id": "lit-ref-001",
                    "source_type": "paper",
                    "title": "   ",
                }
            )

    def test_parse_citation_source_payload_rejects_blank_author_entries(self) -> None:
        with pytest.raises(ValueError, match=r"authors must not contain blank entries"):
            parse_citation_source_payload(
                {
                    "reference_id": "lit-ref-001",
                    "source_type": "paper",
                    "title": "Benchmark Paper",
                    "authors": ["A. Author", "   "],
                }
            )

    def test_parse_citation_source_sidecar_payload_parses_strict_array(self) -> None:
        sources = parse_citation_source_sidecar_payload(
            [
                {
                    "reference_id": "lit-ref-001",
                    "source_type": "paper",
                    "title": "Benchmark Paper",
                }
            ]
        )

        assert [source.reference_id for source in sources] == ["lit-ref-001"]

    def test_parse_citation_source_sidecar_payload_rejects_duplicate_reference_id(self) -> None:
        with pytest.raises(ValueError, match=r"reference_id duplicates 'lit-ref-001'"):
            parse_citation_source_sidecar_payload(
                [
                    {
                        "reference_id": "lit-ref-001",
                        "source_type": "paper",
                        "title": "Benchmark Paper",
                    },
                    {
                        "reference_id": "lit-ref-001",
                        "source_type": "paper",
                        "title": "Other Paper",
                    },
                ]
            )


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


class TestStrictBibliographyContracts:
    def test_citation_source_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match=r"legacy_note[\s\S]*Extra inputs are not permitted"):
            CitationSource(
                source_type="paper",
                title="Test Paper",
                authors=["A. Einstein"],
                year="1905",
                legacy_note="stale",
            )

    def test_bibliography_audit_rejects_nested_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match=r"entries\.0\.unexpected[\s\S]*Extra inputs are not permitted"):
            BibliographyAudit.model_validate(
                {
                    "generated_at": "2026-03-10T00:00:00+00:00",
                    "total_sources": 1,
                    "resolved_sources": 1,
                    "partial_sources": 0,
                    "unverified_sources": 0,
                    "failed_sources": 0,
                    "entries": [
                        {
                            "key": "einstein1905",
                            "source_type": "paper",
                            "reference_id": "ref-einstein",
                            "title": "Relativity",
                            "resolution_status": "provided",
                            "verification_status": "partial",
                            "verification_sources": [],
                            "canonical_identifiers": [],
                            "missing_core_fields": [],
                            "enriched_fields": [],
                            "warnings": [],
                            "errors": [],
                            "unexpected": "boom",
                        }
                    ],
                }
            )

    def test_bibliography_audit_rejects_top_level_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match=r"unexpected[\s\S]*Extra inputs are not permitted"):
            BibliographyAudit.model_validate(
                {
                    "generated_at": "2026-03-10T00:00:00+00:00",
                    "total_sources": 1,
                    "resolved_sources": 1,
                    "partial_sources": 0,
                    "unverified_sources": 0,
                    "failed_sources": 0,
                    "entries": [],
                    "unexpected": True,
                }
            )


class TestBibliographyAudit:
    def test_audit_citation_source_marks_provided_identifiers_as_partial(self):
        source = CitationSource(
            source_type="paper",
            reference_id="ref-123",
            title="A Paper",
            authors=["J. Smith"],
            year="2024",
            doi="10.1234/example",
        )

        resolved, record = audit_citation_source(source, enrich=False)

        assert resolved == source
        assert record.resolution_status == "provided"
        assert record.verification_status == "partial"
        assert record.reference_id == "ref-123"
        assert record.canonical_identifiers == ["doi:10.1234/example"]
        assert record.missing_core_fields == []

    def test_build_bibliography_with_audit_preserves_reference_id(self):
        sources = [
            CitationSource(
                source_type="paper",
                reference_id="anchor-ref",
                title="A Paper",
                authors=["J. Smith"],
                year="2024",
                doi="10.1234/example",
            )
        ]

        bib, audit = build_bibliography_with_audit(sources, enrich=False)

        assert len(bib.entries) == 1
        assert audit.total_sources == 1
        assert audit.entries[0].reference_id == "anchor-ref"
        assert audit.entries[0].key.startswith("smith2024")

    def test_build_bibliography_with_audit_uses_preferred_bibtex_key(self):
        sources = [
            CitationSource(
                source_type="paper",
                reference_id="anchor-ref",
                bibtex_key="anchor-key",
                title="A Paper",
                authors=["J. Smith"],
                year="2024",
                doi="10.1234/example",
            )
        ]

        bib, audit = build_bibliography_with_audit(sources, enrich=False)

        assert list(bib.entries.keys()) == ["anchor-key"]
        assert audit.entries[0].reference_id == "anchor-ref"
        assert audit.entries[0].key == "anchor-key"

    def test_build_bibliography_with_audit_dedups_preferred_bibtex_key(self):
        sources = [
            CitationSource(
                source_type="paper",
                reference_id="anchor-ref-1",
                bibtex_key="shared-key",
                title="A Paper",
                authors=["J. Smith"],
                year="2024",
                doi="10.1234/example",
            ),
            CitationSource(
                source_type="paper",
                reference_id="anchor-ref-2",
                bibtex_key="shared-key",
                title="B Paper",
                authors=["A. Bohr"],
                year="1913",
                doi="10.5678/example",
            ),
        ]

        bib, audit = build_bibliography_with_audit(sources, enrich=False)

        assert list(bib.entries.keys()) == ["shared-key", "shared-keya"]
        assert [entry.key for entry in audit.entries] == ["shared-key", "shared-keya"]
        assert [entry.reference_id for entry in audit.entries] == ["anchor-ref-1", "anchor-ref-2"]

    def test_build_bibliography_with_audit_rejects_duplicate_reference_id(self):
        sources = [
            CitationSource(
                source_type="paper",
                reference_id="anchor-ref",
                title="A Paper",
                authors=["J. Smith"],
                year="2024",
            ),
            CitationSource(
                source_type="paper",
                reference_id="anchor-ref",
                title="B Paper",
                authors=["A. Bohr"],
                year="1913",
            ),
        ]

        with pytest.raises(ValueError, match="duplicates entries 0 and 1"):
            build_bibliography_with_audit(sources, enrich=False)

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

    def test_audit_bibliography_covers_plain_bibtex_entries(self):
        bib = BibliographyData()
        entry = Entry("misc", fields=[("title", "Plain Reference"), ("year", "2024"), ("url", "https://example.com")])
        entry.persons["author"] = [Person("Doe, J.")]
        bib.entries["doe2024"] = entry

        audit = audit_bibliography(bib)

        assert audit.total_sources == 1
        assert audit.resolved_sources == 1
        assert audit.unverified_sources == 1
        record = audit.entries[0]
        assert record.key == "doe2024"
        assert record.reference_id is None
        assert record.title == "Plain Reference"
        assert record.source_type == "tool"
        assert record.resolution_status == "provided"
        assert record.verification_status == "unverified"
        assert record.canonical_identifiers == ["url:https://example.com"]
        assert record.missing_core_fields == []

    def test_audit_bibliography_combines_source_and_plain_entries(self):
        source = CitationSource(
            source_type="paper",
            reference_id="lit-ref-einstein-1905",
            title="Relativity",
            authors=["A. Einstein"],
            year="1905",
            doi="10.1002/andp.19053221004",
        )
        bib = create_bibliography([source])

        plain_entry = Entry("misc", fields=[("title", "Project Note"), ("year", "2024"), ("url", "https://example.com")])
        plain_entry.persons["author"] = [Person("Doe, J.")]
        bib.entries["doe2024"] = plain_entry

        audit = audit_bibliography(bib, citation_sources=[source], enrich=False)

        assert audit.total_sources == 2
        assert [entry.key for entry in audit.entries] == list(bib.entries.keys())
        source_record = audit.entries[0]
        assert source_record.reference_id == "lit-ref-einstein-1905"
        assert source_record.canonical_identifiers == ["doi:10.1002/andp.19053221004"]
        plain_record = audit.entries[1]
        assert plain_record.reference_id is None
        assert plain_record.title == "Project Note"
        assert plain_record.verification_status == "unverified"
        assert plain_record.canonical_identifiers == ["url:https://example.com"]

    def test_audit_bibliography_accepts_precomputed_source_audit_entries(self):
        source = CitationSource(
            source_type="paper",
            reference_id="lit-ref-einstein-1905",
            title="Relativity",
            authors=["A. Einstein"],
            year="1905",
            doi="10.1002/andp.19053221004",
        )
        source_bib, source_audit = build_bibliography_with_audit([source], enrich=False)
        plain_entry = Entry("misc", fields=[("title", "Project Note"), ("year", "2024"), ("url", "https://example.com")])
        plain_entry.persons["author"] = [Person("Doe, J.")]
        source_bib.entries["doe2024"] = plain_entry

        audit = audit_bibliography(source_bib, source_audit_entries=list(source_audit.entries))

        assert audit.total_sources == 2
        assert [entry.key for entry in audit.entries] == list(source_bib.entries.keys())
        source_record = audit.entries[0]
        assert source_record.reference_id == "lit-ref-einstein-1905"
        assert source_record.verification_status == source_audit.entries[0].verification_status
        plain_record = audit.entries[1]
        assert plain_record.reference_id is None
        assert plain_record.title == "Project Note"

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
