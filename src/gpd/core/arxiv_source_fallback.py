"""Fallback retrieval of arXiv paper content from source tarballs.

When PDF fetching fails (corrupted PDFs, access errors, rate limiting),
this module provides an alternative path: download the arXiv e-print
source tarball, extract TeX files, and convert them to readable text.

Usage::

    from gpd.core.arxiv_source_fallback import fetch_arxiv_paper_text

    text = fetch_arxiv_paper_text("2301.12345")
"""

from __future__ import annotations

import gzip
import io
import logging
import re
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

__all__ = [
    "ArxivSourceResult",
    "fetch_arxiv_source",
    "extract_tex_from_tarball",
    "tex_to_text",
    "fetch_arxiv_paper_text",
]

# arXiv e-print source URL pattern.  The /e-print/ endpoint serves the
# original submission source (usually a gzipped tarball of TeX files).
ARXIV_EPRINT_URL_TEMPLATE = "https://arxiv.org/e-print/{arxiv_id}"

# arXiv asks automated tools to identify themselves.
_USER_AGENT = "get-physics-done/1.0 (https://github.com/psi-oss/get-physics-done)"

# Timeout for HTTP requests in seconds.
_REQUEST_TIMEOUT = 30

# Maximum tarball size we are willing to download (50 MB).
_MAX_TARBALL_BYTES = 50 * 1024 * 1024

# Regex for validating arXiv IDs (new-style YYMM.NNNNN and old-style archive/NNNNNNN).
_ARXIV_ID_RE = re.compile(
    r"^(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)$"
)

# TeX commands that produce structural text (section headings, etc.).
_SECTION_COMMANDS = re.compile(
    r"\\(?:section|subsection|subsubsection|paragraph|subparagraph)\*?\{([^}]*)\}"
)

# Common TeX environments to strip (figures, tables with positioning markup).
_STRIP_ENVIRONMENTS = re.compile(
    r"\\begin\{(?:figure|table)\*?\}.*?\\end\{(?:figure|table)\*?\}",
    re.DOTALL,
)


@dataclass
class ArxivSourceResult:
    """Result of fetching and processing arXiv source files."""

    arxiv_id: str
    tex_files: dict[str, str] = field(default_factory=dict)
    main_tex_file: str | None = None
    extracted_text: str = ""
    success: bool = False
    error: str | None = None


def _validate_arxiv_id(arxiv_id: str) -> str:
    """Validate and normalize an arXiv identifier.

    Strips leading ``arXiv:`` prefix if present, and validates against
    known arXiv ID formats.

    Raises:
        ValueError: If the ID does not match a known arXiv format.
    """
    cleaned = arxiv_id.strip()
    # Strip common prefixes.
    for prefix in ("arXiv:", "arxiv:", "http://arxiv.org/abs/", "https://arxiv.org/abs/"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    cleaned = cleaned.strip("/")

    if not _ARXIV_ID_RE.match(cleaned):
        raise ValueError(
            f"Invalid arXiv ID format: {arxiv_id!r}. "
            "Expected YYMM.NNNNN or archive/NNNNNNN."
        )
    return cleaned


def _build_eprint_url(arxiv_id: str) -> str:
    """Build the arXiv e-print download URL for a given ID."""
    return ARXIV_EPRINT_URL_TEMPLATE.format(arxiv_id=arxiv_id)


def fetch_arxiv_source(arxiv_id: str) -> bytes:
    """Download the arXiv e-print source for a given paper.

    Args:
        arxiv_id: arXiv paper identifier (e.g. ``"2301.12345"``).

    Returns:
        Raw bytes of the source archive (typically a gzipped tarball).

    Raises:
        ValueError: If the arXiv ID is invalid.
        ConnectionError: If the download fails.
    """
    validated_id = _validate_arxiv_id(arxiv_id)
    url = _build_eprint_url(validated_id)

    logger.info("Fetching arXiv source for %s from %s", validated_id, url)

    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_TARBALL_BYTES:
                raise ConnectionError(
                    f"arXiv source for {validated_id} exceeds size limit "
                    f"({content_length} bytes > {_MAX_TARBALL_BYTES} bytes)"
                )
            data = response.read(_MAX_TARBALL_BYTES + 1)
            if len(data) > _MAX_TARBALL_BYTES:
                raise ConnectionError(
                    f"arXiv source for {validated_id} exceeds size limit"
                )
            return data
    except HTTPError as exc:
        raise ConnectionError(
            f"Failed to fetch arXiv source for {validated_id}: "
            f"HTTP {exc.code} {exc.reason}"
        ) from exc
    except URLError as exc:
        raise ConnectionError(
            f"Failed to fetch arXiv source for {validated_id}: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise ConnectionError(
            f"Timeout fetching arXiv source for {validated_id}"
        ) from exc


def extract_tex_from_tarball(data: bytes) -> dict[str, str]:
    r"""Extract TeX source files from an arXiv source archive.

    Handles both gzipped tarballs (most common) and single gzipped TeX
    files (sometimes used for single-file submissions).

    Args:
        data: Raw bytes from :func:`fetch_arxiv_source`.

    Returns:
        Mapping of filename to TeX content for all ``.tex`` files found.
    """
    tex_files: dict[str, str] = {}

    # Try as gzipped tarball first (most common case).
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name = member.name
                if name.endswith(".tex") or name.endswith(".bbl"):
                    extracted = tar.extractfile(member)
                    if extracted is not None:
                        try:
                            content = extracted.read().decode("utf-8", errors="replace")
                            tex_files[name] = content
                        except Exception:
                            logger.warning("Could not decode %s", name)
            if tex_files:
                return tex_files
    except (tarfile.TarError, gzip.BadGzipFile, EOFError):
        pass

    # Try as plain tarball (uncompressed).
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name = member.name
                if name.endswith(".tex") or name.endswith(".bbl"):
                    extracted = tar.extractfile(member)
                    if extracted is not None:
                        try:
                            content = extracted.read().decode("utf-8", errors="replace")
                            tex_files[name] = content
                        except Exception:
                            logger.warning("Could not decode %s", name)
            if tex_files:
                return tex_files
    except (tarfile.TarError, EOFError):
        pass

    # Try as single gzipped TeX file.
    try:
        decompressed = gzip.decompress(data)
        text = decompressed.decode("utf-8", errors="replace")
        if "\\begin{document}" in text or "\\documentclass" in text:
            tex_files["main.tex"] = text
            return tex_files
    except (gzip.BadGzipFile, EOFError):
        pass

    # Try as plain TeX (some very old submissions).
    try:
        text = data.decode("utf-8", errors="replace")
        if "\\begin{document}" in text or "\\documentclass" in text:
            tex_files["main.tex"] = text
            return tex_files
    except UnicodeDecodeError:
        pass

    return tex_files


def _identify_main_tex(tex_files: dict[str, str]) -> str | None:
    """Identify the main TeX file from a collection of source files.

    Heuristics, in priority order:
    1. File containing ``\\documentclass``
    2. File named ``main.tex`` or ``paper.tex``
    3. The largest ``.tex`` file
    """
    # Priority 1: contains \documentclass
    for name, content in tex_files.items():
        if name.endswith(".tex") and "\\documentclass" in content:
            return name

    # Priority 2: conventional names
    for candidate in ("main.tex", "paper.tex", "ms.tex", "article.tex"):
        if candidate in tex_files:
            return candidate

    # Priority 3: largest .tex file
    tex_only = {k: v for k, v in tex_files.items() if k.endswith(".tex")}
    if tex_only:
        return max(tex_only, key=lambda k: len(tex_only[k]))

    return None


def tex_to_text(tex_content: str) -> str:
    """Convert TeX source to readable plain text.

    This is a best-effort conversion that strips LaTeX markup while
    preserving the document's textual content and structure. It is not a
    full TeX parser -- it handles the most common constructs found in
    arXiv physics papers.

    Args:
        tex_content: Raw LaTeX source.

    Returns:
        Plain text approximation of the document content.
    """
    text = tex_content

    # Remove comments (lines starting with %).
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)

    # Extract document body if \begin{document}...\end{document} is present.
    body_match = re.search(
        r"\\begin\{document\}(.*?)\\end\{document\}",
        text,
        re.DOTALL,
    )
    if body_match:
        text = body_match.group(1)

    # Convert section headings to readable text.
    text = _SECTION_COMMANDS.sub(r"\n\n=== \1 ===\n\n", text)

    # Strip figure and table environments (keep captions though).
    text = _STRIP_ENVIRONMENTS.sub("", text)

    # Handle common environments.
    text = re.sub(r"\\begin\{(?:abstract)\}", "\n=== Abstract ===\n", text)
    text = re.sub(r"\\end\{(?:abstract)\}", "\n", text)
    text = re.sub(r"\\begin\{(?:equation|align|eqnarray|gather|multline)\*?\}", "\n[equation]\n", text)
    text = re.sub(r"\\end\{(?:equation|align|eqnarray|gather|multline)\*?\}", "\n[/equation]\n", text)
    text = re.sub(r"\\begin\{(?:itemize|enumerate|description)\}", "\n", text)
    text = re.sub(r"\\end\{(?:itemize|enumerate|description)\}", "\n", text)
    text = re.sub(r"\\item\s*(?:\[([^\]]*)\])?\s*", r"\n  - \1 ", text)

    # Remove common commands that don't contribute text.
    text = re.sub(r"\\(?:label|ref|eqref|cite|citep|citet|bibliography|bibliographystyle)\{[^}]*\}", "", text)
    text = re.sub(r"\\(?:includegraphics|input|include)(?:\[[^\]]*\])?\{[^}]*\}", "", text)
    text = re.sub(r"\\(?:vspace|hspace|vskip|hskip|phantom|vphantom|hphantom)\*?\{[^}]*\}", "", text)
    text = re.sub(r"\\(?:newcommand|renewcommand|newenvironment|renewenvironment)\*?\{[^}]*\}(?:\[[^\]]*\])?\{[^}]*\}", "", text)

    # Convert formatting commands to their content.
    text = re.sub(r"\\(?:textbf|textit|textrm|texttt|textsf|emph|underline)\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:bf|it|rm|tt|sf|em)\b\s*", "", text)

    # Convert footnotes and marginpar to inline text.
    text = re.sub(r"\\footnote\{([^}]*)\}", r" [\1]", text)
    text = re.sub(r"\\marginpar\{([^}]*)\}", r" [\1]", text)

    # Strip remaining backslash commands (simple ones without arguments).
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\{([^}]*)\})?", r"\1", text)

    # Clean up braces.
    text = text.replace("{", "").replace("}", "")

    # Clean up whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


def fetch_arxiv_paper_text(
    arxiv_id: str,
    *,
    include_all_files: bool = False,
) -> ArxivSourceResult:
    """Fetch an arXiv paper's content via its source files.

    This is the main entry point for the fallback mechanism. It
    downloads the e-print source, extracts TeX files, identifies the
    main document, and converts it to readable text.

    Args:
        arxiv_id: arXiv paper identifier.
        include_all_files: If True, include content from all TeX files,
            not just the main document.

    Returns:
        An :class:`ArxivSourceResult` with the extracted text and metadata.
    """
    result = ArxivSourceResult(arxiv_id=arxiv_id)

    try:
        validated_id = _validate_arxiv_id(arxiv_id)
        result.arxiv_id = validated_id
    except ValueError as exc:
        result.error = str(exc)
        logger.error("Invalid arXiv ID: %s", exc)
        return result

    try:
        source_data = fetch_arxiv_source(validated_id)
    except ConnectionError as exc:
        result.error = str(exc)
        logger.warning("arXiv source fetch failed for %s: %s", validated_id, exc)
        return result

    tex_files = extract_tex_from_tarball(source_data)
    if not tex_files:
        result.error = f"No TeX files found in arXiv source for {validated_id}"
        logger.warning(result.error)
        return result

    result.tex_files = tex_files
    result.main_tex_file = _identify_main_tex(tex_files)

    if include_all_files:
        # Convert each TeX file independently, then combine text.
        # This avoids problems with \begin{document}...\end{document}
        # in the main file truncating content from subsidiary files.
        ordered_names = sorted(tex_files.keys())
        if result.main_tex_file:
            ordered_names.remove(result.main_tex_file)
            ordered_names.insert(0, result.main_tex_file)
        parts = [tex_to_text(tex_files[name]) for name in ordered_names]
        result.extracted_text = "\n\n".join(p for p in parts if p.strip())
    elif result.main_tex_file:
        result.extracted_text = tex_to_text(tex_files[result.main_tex_file])
    else:
        # Fall back to the largest file.
        largest = max(tex_files, key=lambda k: len(tex_files[k]))
        result.extracted_text = tex_to_text(tex_files[largest])

    result.success = bool(result.extracted_text.strip())
    if not result.success:
        result.error = f"TeX-to-text conversion produced empty output for {validated_id}"
        logger.warning(result.error)

    logger.info(
        "arXiv source fallback for %s: %d TeX files, main=%s, %d chars extracted",
        validated_id,
        len(tex_files),
        result.main_tex_file,
        len(result.extracted_text),
    )
    return result
