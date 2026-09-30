"""HTML retrieval for arxiv papers via ar5iv.labs.arxiv.org."""

from __future__ import annotations

import logging
from html.parser import HTMLParser

import httpx

from gpd.version import __version__ as GPD_VERSION

logger = logging.getLogger("gpd.arxiv_bridge.ar5iv")

_AR5IV_BASE = "https://ar5iv.labs.arxiv.org/html"
_ARXIV_HTML_BASE = "https://arxiv.org/html"

_USER_AGENT = (
    f"gpd-arxiv-bridge/{GPD_VERSION} "
    "(+https://github.com/psi-oss/get-physics-done; mailto:ops@psi.inc)"
)
_HEADERS = {"User-Agent": _USER_AGENT}
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# Cap body size so a runaway / pathological response cannot OOM the bridge
# process. 25 MB is well over the largest ar5iv HTML payload we have ever
# observed in production (typical paper renders to 0.3–2 MB).
_MAX_BODY_BYTES = 25 * 1024 * 1024


def _read_capped(resp: httpx.Response) -> bytes | None:
    """Stream the response body up to ``_MAX_BODY_BYTES`` then abort.

    Returns ``None`` when the response would exceed the cap so the caller
    can fall through to the next attempt instead of treating a truncated
    body as a valid HTML payload."""

    chunks: list[bytes] = []
    total = 0
    for chunk in resp.iter_bytes():
        total += len(chunk)
        if total > _MAX_BODY_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


class _ArticleTextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth: int = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._chunks.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._chunks)


def _html_to_text(html: str) -> str:
    parser = _ArticleTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ar5iv serves this page with HTTP 200 when LaTeXML failed on a paper (for
# example hep-th/9711200). It is not the paper, so callers fall through to PDF.
_CONVERSION_FAILED_MARKER = "Conversion to HTML had a Fatal error"


def is_conversion_failure(text: str) -> bool:
    """True when ``text`` is ar5iv's failed-conversion page, not a paper."""
    return _CONVERSION_FAILED_MARKER in text


def fetch_html_content(paper_id: str) -> str | None:
    # ar5iv first (follow_redirects=False so 307 = miss, not a hop into
    # arxiv.org). arxiv.org/html as fallback for papers ar5iv lacks.
    attempts = (
        (_AR5IV_BASE, False, "ar5iv"),
        (_ARXIV_HTML_BASE, True, "arxiv-html"),
    )
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS) as client:
            for base, follow, label in attempts:
                url = f"{base}/{paper_id}"
                try:
                    with client.stream("GET", url, follow_redirects=follow) as resp:
                        if resp.status_code != 200:
                            logger.info(
                                "html-%s miss for %s: status=%d",
                                label,
                                paper_id,
                                resp.status_code,
                            )
                            continue
                        body = _read_capped(resp)
                except httpx.RequestError as exc:
                    logger.info("html-%s request error for %s: %s", label, paper_id, exc)
                    continue

                if body is None:
                    logger.warning(
                        "html-%s body exceeded %d-byte cap for %s; treating as miss",
                        label,
                        _MAX_BODY_BYTES,
                        paper_id,
                    )
                    continue

                if not body:
                    continue

                text = _html_to_text(body.decode("utf-8", errors="replace"))
                if is_conversion_failure(text):
                    logger.info("html-%s conversion failed for %s; treating as miss", label, paper_id)
                    continue
                if text.strip():
                    return text
    except Exception:
        logger.exception("unexpected error in HTML fetch for %s", paper_id)
    return None
