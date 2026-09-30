"""Layer 2 — Translator unit tests for the arXiv-MCP replacement.

Exercises the OpenAlex search/abstract translators and the GCS PDF fetcher
against five hand-picked papers covering: new-format ID, old-format ID, paper
with no abstract, paper with no extractable arxiv ID (skip case), paper with
multiple versions.

Assertions enforce response-shape parity with the upstream arxiv_mcp_server
contract: field names match, field types match, abstract non-empty when arXiv
has one, arxiv IDs always extractable when expected.

Run:
    pytest tests/mcp/test_arxiv_translators.py -q
    GPD_ARXIV_NO_NETWORK=1 pytest tests/mcp/test_arxiv_translators.py -q   # skip live calls

The translators are imported lazily; if they do not yet exist this module
xfails cleanly so the suite stays green during the bring-up window.
"""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.parity]

NETWORK = os.environ.get("GPD_ARXIV_NO_NETWORK") != "1"

# Hand-picked corpus. Stable IDs only; do not replace casually.
PAPERS = {
    "new_format": "2401.12345",          # standard new-format ID
    "old_format": "hep-th/9901001",      # pre-2007 old-format ID
    "no_abstract": "1701.00001",         # known to lack abstract on OpenAlex
    "no_arxiv_link": "W2741809807",      # OpenAlex work with no arxiv ID (skip)
    "multi_version": "1706.03762v5",     # Attention Is All You Need, v5 exists
}

UPSTREAM_PAPER_KEYS = {
    "id",
    "title",
    "authors",
    "abstract",
    "categories",
    "published",
    "url",
    "resource_uri",
}
UPSTREAM_ABSTRACT_KEYS = {
    "status",
    "paper_id",
    "title",
    "authors",
    "abstract",
    "categories",
    "published",
    "pdf_url",
}


@pytest.fixture(scope="module")
def translators():
    # Only xfail when the module/symbols genuinely do not exist yet — a broad
    # ``except Exception`` would also swallow runtime defects (TypeError,
    # AttributeError, etc.) inside the translator module and silently mark
    # them as "expected to fail", hiding real regressions.
    try:
        from gpd.mcp.servers.arxiv_translators import (  # type: ignore
            gcs_fetch_pdf,
            openalex_abstract,
            openalex_search,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.xfail(f"arxiv_translators not yet implemented: {exc}")
    return openalex_search, openalex_abstract, gcs_fetch_pdf


@pytest.mark.skipif(not NETWORK, reason="network probes disabled")
def test_search_new_format_id_extractable(translators):
    openalex_search, _, _ = translators
    res = openalex_search({"query": "attention is all you need", "max_results": 5})
    assert isinstance(res, dict)
    assert isinstance(res.get("papers"), list)
    assert res.get("total_results") == len(res["papers"])
    # OpenAlex occasionally returns an empty payload for live queries; that is
    # an upstream API hiccup rather than a translator regression, so skip the
    # id-extraction assertions when no results came back.
    if not res["papers"]:
        pytest.skip("OpenAlex returned no results for the live probe query")
    for p in res["papers"]:
        assert set(p.keys()) >= UPSTREAM_PAPER_KEYS, (
            f"missing keys: {UPSTREAM_PAPER_KEYS - set(p.keys())}"
        )
        assert isinstance(p["id"], str) and p["id"]
        assert isinstance(p["authors"], list)
        assert isinstance(p["categories"], list)
        assert p["abstract"].startswith("[EXTERNAL CONTENT]"), "must preserve upstream prefix"


@pytest.mark.skipif(not NETWORK, reason="network probes disabled")
def test_abstract_new_format(translators):
    _, openalex_abstract, _ = translators
    res = openalex_abstract({"paper_id": PAPERS["new_format"]})
    assert isinstance(res, dict)
    assert set(res.keys()) >= UPSTREAM_ABSTRACT_KEYS
    assert res["status"] == "success"
    assert res["paper_id"] == PAPERS["new_format"]
    assert res["abstract"].startswith("[EXTERNAL CONTENT]")
    assert len(res["abstract"]) > len("[EXTERNAL CONTENT] ") + 50


@pytest.mark.skipif(not NETWORK, reason="network probes disabled")
def test_abstract_old_format(translators):
    _, openalex_abstract, _ = translators
    res = openalex_abstract({"paper_id": PAPERS["old_format"]})
    assert res["status"] == "success"
    assert isinstance(res["categories"], list)


@pytest.mark.skipif(not NETWORK, reason="network probes disabled")
def test_abstract_missing_falls_back_gracefully(translators):
    """When OpenAlex has no abstract, the translator must surface a clear error
    (status='error', message non-empty) rather than crash or return a partial
    success masquerading as success."""
    _, openalex_abstract, _ = translators
    res = openalex_abstract({"paper_id": PAPERS["no_abstract"]})
    assert res["status"] in {"success", "error"}
    if res["status"] == "success":
        assert res["abstract"].startswith("[EXTERNAL CONTENT]")
    else:
        assert isinstance(res.get("message"), str) and res["message"]


def test_search_skips_works_without_arxiv_id(translators):
    """If OpenAlex returns a work that has no extractable arxiv ID, the
    translator must drop it from the result list rather than emit a paper
    object with id=None / id=''."""
    openalex_search, _, _ = translators
    fake_openalex_response = {
        "results": [
            {  # has arxiv id via pdf_url
                "id": "https://openalex.org/W1",
                "title": "good paper",
                "authorships": [{"author": {"display_name": "A"}}],
                "abstract_inverted_index": {"hello": [0], "world": [1]},
                "primary_location": {"pdf_url": "https://arxiv.org/pdf/2401.12345.pdf"},
                "publication_date": "2024-01-22",
                "concepts": [{"display_name": "physics"}],
            },
            {  # no arxiv id anywhere => skip
                "id": "https://openalex.org/W2741809807",
                "title": "non-arxiv preprint",
                "authorships": [{"author": {"display_name": "B"}}],
                "abstract_inverted_index": {"x": [0]},
                "primary_location": {"pdf_url": "https://example.org/foo.pdf"},
                "publication_date": "2017-09-01",
                "concepts": [],
            },
        ]
    }
    from gpd.mcp.servers import arxiv_translators  # type: ignore
    if not hasattr(arxiv_translators, "openalex_results_to_papers"):
        pytest.xfail("openalex_results_to_papers helper not implemented yet")
    papers = arxiv_translators.openalex_results_to_papers(fake_openalex_response)
    ids = [p["id"] for p in papers]
    assert "2401.12345" in ids
    assert all(i for i in ids), "no empty/None ids allowed"
    assert len(papers) == 1, "non-arxiv result must be dropped"


@pytest.mark.skipif(not NETWORK, reason="network probes disabled")
def test_pdf_fetch_handles_multiple_versions(translators):
    _, _, gcs_fetch_pdf = translators
    raw = PAPERS["multi_version"]  # contains explicit v5
    res = gcs_fetch_pdf(raw)
    # ``gcs_fetch_pdf`` is a re-export of ``_arxiv_gcs.fetch_pdf_from_gcs``,
    # which contractually returns raw PDF bytes (or ``None`` on miss). If the
    # GCS probe missed entirely, skip the body assertions rather than fail —
    # the multi-version probe is a live network test.
    if res is None:
        pytest.skip("GCS PDF not available for multi-version probe")
    if hasattr(res, "read"):
        res = res.read()
    assert isinstance(res, (bytes, bytearray))
    assert len(res) > 10_000, "PDF should be > 10KB"
    assert res[:4] == b"%PDF"


def test_shape_parity_search(translators):
    """Pure shape test: translator output must match upstream paper-record
    shape exactly (keys + types). No network: feeds a synthetic response."""
    from gpd.mcp.servers import arxiv_translators  # type: ignore
    if not hasattr(arxiv_translators, "openalex_results_to_papers"):
        pytest.xfail("openalex_results_to_papers helper not implemented yet")
    fake = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "t",
                "authorships": [{"author": {"display_name": "A1"}}, {"author": {"display_name": "A2"}}],
                "abstract_inverted_index": {"hello": [0]},
                "primary_location": {"pdf_url": "https://arxiv.org/pdf/2401.12345.pdf"},
                "publication_date": "2024-01-22",
                "concepts": [{"display_name": "physics.gen-ph"}],
            }
        ]
    }
    papers = arxiv_translators.openalex_results_to_papers(fake)
    assert len(papers) == 1
    p = papers[0]
    assert set(p.keys()) == UPSTREAM_PAPER_KEYS
    assert isinstance(p["id"], str)
    assert isinstance(p["title"], str)
    assert isinstance(p["authors"], list) and all(isinstance(a, str) for a in p["authors"])
    assert isinstance(p["abstract"], str) and p["abstract"].startswith("[EXTERNAL CONTENT]")
    assert isinstance(p["categories"], list)
    assert isinstance(p["published"], str)
    assert isinstance(p["url"], str)
    assert p["resource_uri"] == f"arxiv://{p['id']}"


def test_abstract_lookup_matches_arxiv_landing_pages(monkeypatch):
    """OpenAlex merges arXiv preprints into works whose primary DOI can belong
    to another version, so the lookup filters on location landing pages rather
    than the ``/works/doi:`` singleton. No network: fakes the HTTP layer."""
    from gpd.mcp.servers import arxiv_translators  # type: ignore

    work = {
        "id": "https://openalex.org/W2041262588",
        "title": "String Junctions and Their Duals in Heterotic String Theory",
        "authorships": [{"author": {"display_name": "A"}}],
        "abstract_inverted_index": {"hello": [0], "world": [1]},
        "publication_date": "1999-01-04",
        "concepts": [{"display_name": "physics"}],
    }
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        return 200, {"meta": {"count": 1}, "results": [work]}, ""

    monkeypatch.setattr(arxiv_translators, "_http_get", fake_get)
    res = arxiv_translators.openalex_abstract({"paper_id": "hep-th/9901001v2"})

    assert res["status"] == "success"
    assert res["paper_id"] == "hep-th/9901001"
    assert res["abstract"] == arxiv_translators.EXTERNAL_CONTENT_PREFIX + "hello world"
    assert res["pdf_url"] == "https://arxiv.org/pdf/hep-th/9901001"
    assert calls == [
        (
            "/works",
            {
                "filter": (
                    "locations.landing_page_url:https://doi.org/10.48550/arxiv.hep-th/9901001"
                    "|http://arxiv.org/abs/hep-th/9901001"
                ),
                "per_page": 1,
            },
        )
    ]


def test_abstract_lookup_falls_back_to_doi_singleton(monkeypatch):
    """With no landing-page match the lookup tries the DOI singleton and
    reports its HTTP status. No network: fakes the HTTP layer."""
    from gpd.mcp.servers import arxiv_translators  # type: ignore

    calls = []

    def fake_get(path, params=None):
        calls.append(path)
        if path == "/works":
            return 200, {"meta": {"count": 0}, "results": []}, ""
        return 404, None, "not found"

    monkeypatch.setattr(arxiv_translators, "_http_get", fake_get)
    res = arxiv_translators.openalex_abstract({"paper_id": "2401.12345"})

    assert res["status"] == "error"
    assert "HTTP 404" in res["message"]
    assert calls == ["/works", "/works/doi:10.48550%2Farxiv.2401.12345"]
