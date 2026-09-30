"""Unit tests for ar5iv HTML fetcher."""

from __future__ import annotations

import pytest

from gpd.mcp.servers import _arxiv_ar5iv


def test_html_to_text_strips_script_style_nav() -> None:
    html = """
    <html>
      <head><script>alert('x')</script><style>body {}</style></head>
      <body>
        <nav>menu</nav>
        <header>top</header>
        <main>actual content</main>
        <footer>bottom</footer>
        <aside>side</aside>
      </body>
    </html>
    """
    text = _arxiv_ar5iv._html_to_text(html)
    # The extractor strips SKIP_TAGS — none of these should appear:
    for unwanted in ("alert", "menu", "top", "bottom", "side", "body {}"):
        assert unwanted not in text
    assert "actual content" in text


def test_html_to_text_returns_stripped_chunks() -> None:
    html = "<p>  hello   </p><p>world</p>"
    text = _arxiv_ar5iv._html_to_text(html)
    assert "hello" in text
    assert "world" in text


def _make_fake_client(responses: list[object]) -> object:
    class FakeClient:
        def __init__(self) -> None:
            self._idx = 0

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *exc) -> None:
            pass

        def get(self, url: str, follow_redirects: bool = True) -> object:
            resp = responses[self._idx]
            self._idx += 1
            return resp

        def stream(self, _method: str, _url: str, follow_redirects: bool = True) -> object:
            resp = responses[self._idx]
            self._idx += 1
            return resp

    return FakeClient()


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", text: str = "", headers: dict | None = None) -> None:
        self.status_code = status_code
        self.content = content
        self.text = text
        self.headers = headers or {}

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def iter_bytes(self):
        if self.content:
            yield self.content


def test_fetch_hits_ar5iv_first(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_fake_client(
        [_FakeResponse(200, content=b"<html><body>hello</body></html>", text="<html><body>hello</body></html>")]
    )

    def fake_client_ctor(*args, **kwargs) -> object:
        return fake

    monkeypatch.setattr(_arxiv_ar5iv.httpx, "Client", fake_client_ctor)
    result = _arxiv_ar5iv.fetch_html_content("2401.00001")
    assert result is not None
    assert "hello" in result


def test_fetch_falls_through_on_307(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_fake_client(
        [
            _FakeResponse(307),  # ar5iv miss
            _FakeResponse(200, content=b"<html>fallback</html>", text="<html>fallback</html>"),
        ]
    )
    monkeypatch.setattr(_arxiv_ar5iv.httpx, "Client", lambda *a, **k: fake)
    result = _arxiv_ar5iv.fetch_html_content("2604.00001")
    assert result is not None
    assert "fallback" in result


def test_fetch_returns_none_on_total_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_fake_client([_FakeResponse(404), _FakeResponse(404)])
    monkeypatch.setattr(_arxiv_ar5iv.httpx, "Client", lambda *a, **k: fake)
    assert _arxiv_ar5iv.fetch_html_content("9999.99999") is None


def test_fetch_treats_empty_extracted_text_as_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _make_fake_client(
        [
            _FakeResponse(200, content=b"<html><script>x</script></html>", text="<html><script>x</script></html>"),
            _FakeResponse(200, content=b"<html><body>real</body></html>", text="<html><body>real</body></html>"),
        ]
    )
    monkeypatch.setattr(_arxiv_ar5iv.httpx, "Client", lambda *a, **k: fake)
    result = _arxiv_ar5iv.fetch_html_content("2401.00001")
    assert result is not None
    assert "real" in result


def test_fetch_treats_conversion_failure_page_as_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    """ar5iv answers 200 with a failed-conversion page for some papers (for
    example hep-th/9711200); that page is not the paper."""
    stub = (
        b"<html><body><p>No content available</p>"
        b"<p>Conversion to HTML had a Fatal error and exited abruptly.</p></body></html>"
    )
    fake = _make_fake_client([_FakeResponse(200, content=stub, text=stub.decode()), _FakeResponse(404)])
    monkeypatch.setattr(_arxiv_ar5iv.httpx, "Client", lambda *a, **k: fake)
    assert _arxiv_ar5iv.fetch_html_content("hep-th/9711200") is None
