from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.core.arxiv_source_download import (
    ARXIV_SOURCE_MAX_BYTES,
    ArxivSourceDownload,
    build_source_download_url,
    download_arxiv_source_archive,
    normalize_arxiv_id,
    resolve_source_storage_dir,
)


class _FakeResponse:
    def __init__(self, payload: bytes, *, headers: dict[str, str]) -> None:
        self._buffer = io.BytesIO(payload)
        self.headers = headers

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_normalize_arxiv_id_accepts_known_forms() -> None:
    assert normalize_arxiv_id("2401.12345") == "2401.12345"
    assert normalize_arxiv_id("arXiv:2401.12345v2") == "2401.12345v2"
    assert normalize_arxiv_id("https://arxiv.org/abs/hep-th/9901001") == "hep-th/9901001"


def test_normalize_arxiv_id_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="Invalid arXiv ID format"):
        normalize_arxiv_id("not-a-paper")


def test_build_source_download_url_normalizes_first() -> None:
    assert build_source_download_url(" arXiv:2401.12345 ") == "https://arxiv.org/e-print/2401.12345"


def test_resolve_source_storage_dir_uses_sources_subdirectory(tmp_path: Path) -> None:
    resolved = resolve_source_storage_dir(tmp_path / "papers")
    assert resolved == (tmp_path / "papers" / "sources").resolve()
    assert resolved.is_dir()


def test_download_arxiv_source_archive_streams_to_disk(tmp_path: Path) -> None:
    payload = b"PK\x03\x04zip-archive-contents"
    response = _FakeResponse(
        payload,
        headers={
            "Content-Type": "application/zip",
            "Content-Length": str(len(payload)),
            "Content-Disposition": 'attachment; filename="2401.12345-source.zip"',
        },
    )

    with patch("gpd.core.arxiv_source_download.urlopen", return_value=response):
        result = download_arxiv_source_archive("2401.12345", storage_path=tmp_path)

    assert isinstance(result, ArxivSourceDownload)
    assert result.arxiv_id == "2401.12345"
    assert result.filename.endswith(".zip")
    assert result.path.read_bytes() == payload
    assert result.size_bytes == len(payload)
    assert result.cached is False


def test_download_arxiv_source_archive_uses_existing_file_when_present(tmp_path: Path) -> None:
    payload = b"\x1f\x8bpretend-gzip"
    response = _FakeResponse(
        payload,
        headers={
            "Content-Type": "application/gzip",
            "Content-Length": str(len(payload)),
        },
    )

    with patch("gpd.core.arxiv_source_download.urlopen", return_value=response):
        first = download_arxiv_source_archive("2401.12345", storage_path=tmp_path)

    second_response = _FakeResponse(
        payload,
        headers={
            "Content-Type": "application/gzip",
            "Content-Length": str(len(payload)),
        },
    )
    with patch("gpd.core.arxiv_source_download.urlopen", return_value=second_response):
        second = download_arxiv_source_archive("2401.12345", storage_path=tmp_path, overwrite=False)

    assert first.path == second.path
    assert second.cached is True


def test_download_arxiv_source_archive_rejects_large_content_length(tmp_path: Path) -> None:
    response = _FakeResponse(
        b"",
        headers={"Content-Length": str(ARXIV_SOURCE_MAX_BYTES + 1)},
    )

    with patch("gpd.core.arxiv_source_download.urlopen", return_value=response):
        with pytest.raises(ConnectionError, match="exceeds size limit"):
            download_arxiv_source_archive("2401.12345", storage_path=tmp_path)


def test_download_arxiv_source_archive_rejects_streams_that_grow_too_large(tmp_path: Path) -> None:
    payload = b"a" * (ARXIV_SOURCE_MAX_BYTES + 1)
    response = _FakeResponse(payload, headers={})

    with patch("gpd.core.arxiv_source_download.urlopen", return_value=response):
        with pytest.raises(ConnectionError, match="exceeds size limit"):
            download_arxiv_source_archive("2401.12345", storage_path=tmp_path)
