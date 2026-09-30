"""OpenAlex-backed translators that mimic the upstream arxiv_mcp_server shape.

The bridge calls these in front of the upstream MCP so that ``search_papers``
and ``get_abstract`` traffic is served from `api.openalex.org` whenever
possible, leaving ``export.arxiv.org`` only for the long-tail fallback. The
downstream model receives the exact same record shape it would from the
upstream MCP, with one prefix-tag swap (`[EXTERNAL CONTENT]`) so the
prompt-injection guard remains visible.

Public surface:

* :func:`openalex_search` — search by free-text query, returns papers
  list in upstream's Atom-derived shape.
* :func:`openalex_abstract` — fetch a single arxiv-id abstract record.
* :func:`openalex_results_to_papers` — pure-function helper used by both
  the live translator and shape-parity unit tests.
* :func:`gcs_fetch_pdf` — re-export of the GCS PDF fetcher so the
  translator boundary is the only import callers need.
"""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import quote

import httpx

from gpd.mcp.servers import _arxiv_gcs
from gpd.version import __version__ as GPD_VERSION

logger = logging.getLogger("gpd.arxiv_bridge.translators")

_OPENALEX_BASE = "https://api.openalex.org"

# arXiv's canonical OpenAlex *source* id (i.e. the venue, not an institution).
# Verified live against api.openalex.org/sources?search=arxiv on 2026-05-20:
# S4306400194 = "arXiv (Cornell University)", count = 28,975 results when used
# as `primary_location.source.id:S4306400194` on a sample query. The earlier
# `I4210109252` / `I4210168979` institution-style IDs returned 0 results for
# every query, which silently turned `openalex_search` into a no-op. Always
# filter via this source id, not an institution lineage.
OPENALEX_ARXIV_SOURCE_ID = "S4306400194"

# Prefix tag the downstream model sees on any abstract / search-result body.
# Kept short and stable so a fine-tuned prompt-injection guard can pattern-match.
EXTERNAL_CONTENT_PREFIX = "[EXTERNAL CONTENT] "

_USER_AGENT = (
    f"gpd-arxiv-bridge/{GPD_VERSION} "
    "(+https://github.com/psi-oss/get-physics-done; mailto:ops@psi.inc)"
)
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

# OpenAlex meters requests. Without a key, every client on the caller's IP
# address shares a small free daily budget (observed 2026-09-29: $0.10 a day,
# $0.001 per search, $0.0001 per filter lookup), and a spent budget returns
# HTTP 429 until midnight UTC. A free personal key has its own budget:
# https://help.openalex.org/api/authentication/
OPENALEX_API_KEY_ENV = "OPENALEX_API_KEY"


def _request_headers() -> dict[str, str]:
    headers = dict(_HEADERS)
    key = os.environ.get(OPENALEX_API_KEY_ENV, "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

# Recognise arxiv IDs anywhere inside an OpenAlex Work record (pdf_url,
# landing page, doi). New-format e.g. "2401.12345v3"; old-format e.g.
# "hep-th/9901001".
_ARXIV_ID_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf|html)/(?P<id>(?:[a-z\-]+(?:\.[a-z][a-z0-9\-]*)?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?)",
    re.IGNORECASE,
)
_DOI_ARXIV_RE = re.compile(
    r"10\.48550/arxiv\.(?P<id>(?:[a-z\-]+(?:\.[a-z][a-z0-9\-]*)?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?)",
    re.IGNORECASE,
)


def gcs_fetch_pdf(paper_id: str) -> bytes | None:
    """Fetch a paper PDF from the public Cornell-Google GCS mirror."""
    return _arxiv_gcs.fetch_pdf_from_gcs(paper_id)


def _strip_version(paper_id: str) -> str:
    """Drop a trailing ``vN`` for ID comparison; keep the canonical stem."""
    return re.sub(r"v\d+$", "", paper_id)


def _extract_arxiv_id(work: dict[str, object]) -> str | None:
    """Find the arxiv identifier inside an OpenAlex Work record.

    Checked in order: ``primary_location.pdf_url``, ``primary_location.landing_page_url``,
    ``ids.doi``, and any URL inside ``locations[*]``. Returns the canonical
    stem (no ``vN``) so the bridge can hand it back to the downstream model
    in the format the upstream MCP would have used.
    """

    def _scan(url: str | None) -> str | None:
        if not isinstance(url, str):
            return None
        m = _ARXIV_ID_RE.search(url) or _DOI_ARXIV_RE.search(url)
        if m:
            return _strip_version(m.group("id"))
        return None

    primary = work.get("primary_location") or {}
    for key in ("pdf_url", "landing_page_url", "source_url"):
        found = _scan(primary.get(key))
        if found:
            return found

    ids = work.get("ids") or {}
    for key in ("doi", "openalex"):
        found = _scan(ids.get(key))
        if found:
            return found

    for loc in work.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        for key in ("pdf_url", "landing_page_url"):
            found = _scan(loc.get(key))
            if found:
                return found

    return None


def _reassemble_abstract(inverted: dict[str, list[int]] | None) -> str:
    """Reconstruct plain abstract text from OpenAlex's inverted index.

    OpenAlex returns ``abstract_inverted_index`` as ``{word: [positions...]}``
    instead of plain text. Reassemble by sorting (position, word) pairs and
    joining. Returns an empty string when the index is missing/empty —
    callers decide whether that constitutes an error.
    """
    if not isinstance(inverted, dict) or not inverted:
        return ""
    positioned: list[tuple[int, str]] = []
    for word, positions in inverted.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                positioned.append((pos, word))
    positioned.sort(key=lambda pair: pair[0])
    return " ".join(word for _, word in positioned)


def _authors(work: dict[str, object]) -> list[str]:
    out: list[str] = []
    for entry in work.get("authorships") or []:
        if not isinstance(entry, dict):
            continue
        author = entry.get("author") or {}
        name = author.get("display_name")
        if isinstance(name, str) and name:
            out.append(name)
    return out


def _categories(work: dict[str, object]) -> list[str]:
    """Best-effort category list — OpenAlex 'concepts' or arxiv subfields.

    Upstream MCP returns arxiv categories like ``hep-th``. OpenAlex doesn't
    carry that taxonomy directly, so we fall back to concept display names.
    The downstream contract only requires a ``list[str]``, not a specific
    taxonomy, so consumers must not rely on arxiv-cat semantics here.
    """
    out: list[str] = []
    for concept in work.get("concepts") or []:
        if isinstance(concept, dict):
            name = concept.get("display_name")
            if isinstance(name, str) and name:
                out.append(name)
    return out


def _landing_url(work: dict[str, object], arxiv_id: str) -> str:
    # Always return the canonical arXiv URL. OpenAlex ``primary_location`` can
    # point at a publisher or OpenAlex page even when the work has an arXiv id,
    # and the upstream arxiv_mcp_server contract requires the arxiv.org URL so
    # downstream consumers route through the bridge's normal download path.
    del work  # signature parity with prior call sites; OpenAlex fields ignored.
    return f"https://arxiv.org/abs/{arxiv_id}"


def _pdf_url(work: dict[str, object], arxiv_id: str) -> str:
    del work  # same rationale as ``_landing_url``: canonical arxiv.org only.
    return f"https://arxiv.org/pdf/{arxiv_id}"


def _to_paper_record(work: dict[str, object]) -> dict[str, object] | None:
    """Translate one OpenAlex Work into upstream's search-result shape.

    Returns ``None`` when the work has no recoverable arxiv ID — the bridge
    drops these because the downstream contract requires arxiv IDs (the
    model uses them to call ``download_paper``).
    """
    arxiv_id = _extract_arxiv_id(work)
    if not arxiv_id:
        return None
    abstract = _reassemble_abstract(work.get("abstract_inverted_index"))
    return {
        "id": arxiv_id,
        "title": work.get("title") or "",
        "authors": _authors(work),
        "abstract": EXTERNAL_CONTENT_PREFIX + abstract,
        "categories": _categories(work),
        "published": work.get("publication_date") or "",
        "url": _landing_url(work, arxiv_id),
        "resource_uri": f"arxiv://{arxiv_id}",
    }


def openalex_results_to_papers(response: dict[str, object]) -> list[dict[str, object]]:
    """Convert an OpenAlex ``/works`` response into a list of upstream-shaped
    paper records, silently dropping works without an extractable arxiv ID."""
    out: list[dict[str, object]] = []
    for work in response.get("results") or []:
        if not isinstance(work, dict):
            continue
        record = _to_paper_record(work)
        if record is not None:
            out.append(record)
    return out


def _http_get(
    path: str, params: dict[str, object] | None = None
) -> tuple[int, dict[str, object] | None, str]:
    """Single OpenAlex GET. Returns ``(status_code, parsed_json, raw_text)``.

    Never raises on HTTP/parse errors — the translator caller chooses the
    error envelope. Returns ``(0, None, str(exc))`` on transport failure so
    callers can distinguish HTTP failures (status >= 400) from network
    failures (status == 0).
    """
    url = f"{_OPENALEX_BASE}{path}"
    try:
        resp = httpx.get(url, params=params, headers=_request_headers(), timeout=_TIMEOUT)
    except httpx.RequestError as exc:
        logger.info("OpenAlex request error on %s: %s", path, exc)
        return 0, None, str(exc)
    try:
        body = resp.json()
        if not isinstance(body, dict):
            body = None
    except ValueError:
        body = None
    return resp.status_code, body, resp.text


def openalex_search(args: dict[str, object]) -> dict[str, object]:
    """Search OpenAlex and return upstream-shaped ``{papers, total_results}``.

    Recognised ``args``: ``query`` (str, required) and ``max_results`` (int,
    1-200, default 10). Other keys are ignored — callers must translate
    arxiv-style filters before passing them through.
    """
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"papers": [], "total_results": 0}

    raw_max = args.get("max_results", 10)
    try:
        per_page = max(1, min(200, int(raw_max)))
    except (TypeError, ValueError):
        per_page = 10

    params: dict[str, object] = {
        "search": query.strip(),
        "per-page": per_page,
        # Restrict to works whose primary venue is arXiv (Cornell). Using the
        # canonical source id verified live against the OpenAlex sources
        # endpoint — see `OPENALEX_ARXIV_SOURCE_ID` above for the rationale
        # and the production-incident history that motivated this constant.
        "filter": f"primary_location.source.id:{OPENALEX_ARXIV_SOURCE_ID}",
    }

    status, body, _ = _http_get("/works", params)
    # Only retry without the filter when OpenAlex rejects the filter itself
    # (400 Bad Request / 422 Unprocessable). For 429, 5xx, timeouts, or parse
    # failures, the filter is not the problem — retrying doubles upstream load
    # without improving the outcome, which violates the rate-limit-resilient
    # contract this translator is built around.
    if status in {400, 422}:
        params.pop("filter", None)
        status, body, _ = _http_get("/works", params)

    if status != 200 or body is None:
        return {"papers": [], "total_results": 0}

    papers = openalex_results_to_papers(body)
    return {"papers": papers, "total_results": len(papers)}


def openalex_abstract(args: dict[str, object]) -> dict[str, object]:
    """Fetch a single paper's metadata + abstract by arxiv ID."""
    paper_id_raw = args.get("paper_id")
    if not isinstance(paper_id_raw, str) or not paper_id_raw.strip():
        return _abstract_error("", "paper_id must be a non-empty string")
    paper_id = _strip_version(paper_id_raw.strip())

    # OpenAlex resolves arxiv preprints via the canonical DOI prefix.
    # URL-encode the DOI segment so old-style arXiv IDs containing slashes
    # (e.g. "hep-th/9901001") don't break the request path.
    doi = f"10.48550/arxiv.{paper_id}"
    status, body, _ = _http_get(f"/works/doi:{quote(doi, safe='')}")
    if status != 200 or body is None:
        return _abstract_error(paper_id, f"OpenAlex lookup failed (HTTP {status}) for {paper_id}")

    abstract = _reassemble_abstract(body.get("abstract_inverted_index"))
    if not abstract:
        return _abstract_error(paper_id, f"No abstract available on OpenAlex for {paper_id}")

    return {
        "status": "success",
        "paper_id": paper_id,
        "title": body.get("title") or "",
        "authors": _authors(body),
        "abstract": EXTERNAL_CONTENT_PREFIX + abstract,
        "categories": _categories(body),
        "published": body.get("publication_date") or "",
        "pdf_url": _pdf_url(body, paper_id),
    }


def _abstract_error(paper_id: str, message: str) -> dict[str, object]:
    return {
        "status": "error",
        "paper_id": paper_id,
        "title": "",
        "authors": [],
        "abstract": "",
        "categories": [],
        "published": "",
        "pdf_url": "",
        "message": message,
    }


__all__ = [
    "EXTERNAL_CONTENT_PREFIX",
    "gcs_fetch_pdf",
    "openalex_abstract",
    "openalex_results_to_papers",
    "openalex_search",
]
