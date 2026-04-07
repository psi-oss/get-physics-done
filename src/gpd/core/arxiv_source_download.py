"""Helpers for downloading raw arXiv source archives."""

from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

ARXIV_SOURCE_URL_TEMPLATE = "https://arxiv.org/e-print/{arxiv_id}"
ARXIV_DEFAULT_STORAGE_PATH = Path.home() / ".arxiv-mcp-server" / "papers"
ARXIV_SOURCE_STORAGE_DIRNAME = "sources"
ARXIV_SOURCE_USER_AGENT = "get-physics-done/1.1.0 (https://github.com/psi-oss/get-physics-done)"
ARXIV_SOURCE_TIMEOUT_SECONDS = 60
ARXIV_SOURCE_CHUNK_BYTES = 64 * 1024
ARXIV_SOURCE_SNIFF_BYTES = 1024
ARXIV_SOURCE_MAX_BYTES = 250 * 1024 * 1024

_ARXIV_ID_RE = re.compile(
    r"^(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)$"
)
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_CONTENT_TYPE_TO_SUFFIX = {
    "application/gzip": ".gz",
    "application/x-gzip": ".gz",
    "application/tar": ".tar",
    "application/x-tar": ".tar",
    "application/x-gtar": ".tar",
    "application/x-eprint-tar": ".tar",
    "application/x-compressed-tar": ".tar.gz",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
}


@dataclass(frozen=True, slots=True)
class ArxivSourceDownload:
    """Metadata for one downloaded arXiv source archive."""

    arxiv_id: str
    download_url: str
    path: Path
    filename: str
    size_bytes: int
    content_type: str | None
    cached: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "arxiv_id": self.arxiv_id,
            "download_url": self.download_url,
            "path": str(self.path),
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "cached": self.cached,
        }


def normalize_arxiv_id(arxiv_id: str) -> str:
    """Validate and normalize an arXiv identifier."""

    cleaned = arxiv_id.strip()
    for prefix in ("arXiv:", "arxiv:", "http://arxiv.org/abs/", "https://arxiv.org/abs/"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    cleaned = cleaned.strip("/")
    if not _ARXIV_ID_RE.fullmatch(cleaned):
        raise ValueError(
            f"Invalid arXiv ID format: {arxiv_id!r}. Expected YYMM.NNNNN or archive/NNNNNNN."
        )
    return cleaned


def build_source_download_url(arxiv_id: str) -> str:
    """Build the arXiv e-print URL for *arxiv_id*."""

    return ARXIV_SOURCE_URL_TEMPLATE.format(arxiv_id=normalize_arxiv_id(arxiv_id))


def resolve_source_storage_dir(storage_path: str | Path | None = None) -> Path:
    """Return the directory where source archives should be stored."""

    base = Path(storage_path) if storage_path is not None else ARXIV_DEFAULT_STORAGE_PATH
    resolved = base.expanduser().resolve(strict=False) / ARXIV_SOURCE_STORAGE_DIRNAME
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _content_type(headers: object) -> str | None:
    if hasattr(headers, "get_content_type"):
        value = headers.get_content_type()
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    if hasattr(headers, "get"):
        raw = headers.get("Content-Type")
        if isinstance(raw, str) and raw.strip():
            return raw.split(";", 1)[0].strip().lower()
    return None


def _content_disposition_filename(headers: object) -> str | None:
    if hasattr(headers, "get_filename"):
        filename = headers.get_filename()
        if isinstance(filename, str) and filename.strip():
            return filename.strip()
    if not hasattr(headers, "get"):
        return None
    raw = headers.get("Content-Disposition")
    if not isinstance(raw, str) or not raw.strip():
        return None
    message = Message()
    message["content-disposition"] = raw
    for key in ("filename", "filename*"):
        value = message.get_param(key, header="content-disposition", unquote=True)
        if isinstance(value, tuple):
            _charset, _language, encoded = value
            value = encoded
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _archive_suffix_from_content(
    content_type: str | None,
    filename: str | None,
    sniff_bytes: bytes,
) -> str:
    if isinstance(filename, str):
        lowered = filename.lower()
        for suffix in (".tar.gz", ".tgz", ".zip", ".tar", ".gz"):
            if lowered.endswith(suffix):
                return ".tar.gz" if suffix == ".tgz" else suffix
    if content_type in _CONTENT_TYPE_TO_SUFFIX:
        return _CONTENT_TYPE_TO_SUFFIX[content_type]
    if sniff_bytes.startswith(b"\x1f\x8b"):
        return ".gz"
    if sniff_bytes.startswith(b"PK\x03\x04"):
        return ".zip"
    if len(sniff_bytes) >= 262 and sniff_bytes[257:262] == b"ustar":
        return ".tar"
    return ".src"


def _safe_filename_component(value: str) -> str:
    collapsed = _SAFE_FILENAME_RE.sub("_", value).strip("._")
    return collapsed or "arxiv-source"


def _content_length(headers: object) -> int | None:
    if not hasattr(headers, "get"):
        return None
    raw = headers.get("Content-Length")
    if raw is None:
        return None
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def download_arxiv_source_archive(
    arxiv_id: str,
    *,
    storage_path: str | Path | None = None,
    overwrite: bool = False,
    timeout_seconds: int = ARXIV_SOURCE_TIMEOUT_SECONDS,
    max_bytes: int = ARXIV_SOURCE_MAX_BYTES,
) -> ArxivSourceDownload:
    """Download the raw source archive for an arXiv paper."""

    normalized_id = normalize_arxiv_id(arxiv_id)
    download_url = build_source_download_url(normalized_id)
    storage_dir = resolve_source_storage_dir(storage_path)

    request = Request(download_url, headers={"User-Agent": ARXIV_SOURCE_USER_AGENT})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            headers = response.headers
            expected_size = _content_length(headers)
            if expected_size is not None and expected_size > max_bytes:
                raise ConnectionError(
                    f"arXiv source for {normalized_id} exceeds size limit "
                    f"({expected_size} bytes > {max_bytes} bytes)"
                )

            with tempfile.NamedTemporaryFile(
                prefix=f"{_safe_filename_component(normalized_id)}-",
                suffix=".part",
                dir=storage_dir,
                delete=False,
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                total_bytes = 0
                sniff_bytes = b""
                while True:
                    chunk = response.read(ARXIV_SOURCE_CHUNK_BYTES)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ConnectionError(
                            f"arXiv source for {normalized_id} exceeds size limit ({max_bytes} bytes)"
                        )
                    if len(sniff_bytes) < ARXIV_SOURCE_SNIFF_BYTES:
                        sniff_bytes += chunk[: ARXIV_SOURCE_SNIFF_BYTES - len(sniff_bytes)]
                    tmp_file.write(chunk)
    except HTTPError as exc:
        raise ConnectionError(
            f"Failed to fetch arXiv source for {normalized_id}: HTTP {exc.code} {exc.reason}"
        ) from exc
    except URLError as exc:
        raise ConnectionError(f"Failed to fetch arXiv source for {normalized_id}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ConnectionError(f"Timeout fetching arXiv source for {normalized_id}") from exc
    except Exception:
        if "tmp_path" in locals():
            tmp_path.unlink(missing_ok=True)
        raise

    filename_hint = _content_disposition_filename(headers)
    suffix = _archive_suffix_from_content(_content_type(headers), filename_hint, sniff_bytes)
    default_name = f"{_safe_filename_component(normalized_id)}-source{suffix}"
    filename = _safe_filename_component(Path(filename_hint).name) if filename_hint else default_name
    if filename == _safe_filename_component(filename) and Path(filename).suffix == "" and suffix != ".src":
        filename = f"{filename}{suffix}"
    if filename == _safe_filename_component(filename) and filename == _safe_filename_component(Path(filename).stem):
        if not any(filename.lower().endswith(known) for known in (".tar.gz", ".zip", ".tar", ".gz", ".src")):
            filename = default_name

    target_path = storage_dir / filename
    if target_path.exists() and not overwrite:
        cached_size = target_path.stat().st_size
        tmp_path.unlink(missing_ok=True)
        return ArxivSourceDownload(
            arxiv_id=normalized_id,
            download_url=download_url,
            path=target_path,
            filename=target_path.name,
            size_bytes=cached_size,
            content_type=_content_type(headers),
            cached=True,
        )

    tmp_path.replace(target_path)
    logger.info("Downloaded arXiv source for %s to %s", normalized_id, target_path)
    return ArxivSourceDownload(
        arxiv_id=normalized_id,
        download_url=download_url,
        path=target_path,
        filename=target_path.name,
        size_bytes=target_path.stat().st_size,
        content_type=_content_type(headers),
        cached=False,
    )


__all__ = [
    "ARXIV_DEFAULT_STORAGE_PATH",
    "ARXIV_SOURCE_MAX_BYTES",
    "ARXIV_SOURCE_STORAGE_DIRNAME",
    "ArxivSourceDownload",
    "build_source_download_url",
    "download_arxiv_source_archive",
    "normalize_arxiv_id",
    "resolve_source_storage_dir",
]
