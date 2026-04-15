"""Pandoc integration -- programmatic markdown-to-LaTeX conversion.

Thin wrapper around the `pandoc` binary: availability/version detection,
subprocess invocation with Lua filters and bibliographies, and a convenience
``markdown_to_latex_fragment`` API for paper-writer agents.

Pandoc is an optional dependency. When it is not installed, ``detect_pandoc()``
returns a status with ``available=False`` and callers must fall back to the
direct-LaTeX code path.

The module is deliberately domain-agnostic: no hardcoded paths, no project
layout assumptions. All configuration (filters, bibliography, template) is
passed in by the caller. The same code runs in GRD or -- via a simple module
rename -- in Get Physics Done (GPD).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimum pandoc version for reliable Lua filter support.
# 2.17 stabilised the `pandoc.Span`, walk_block/walk_inline AST helpers we rely on.
MIN_PANDOC_VERSION: tuple[int, int] = (2, 17)

DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_DETECT_TIMEOUT_SECONDS: float = 5.0

# External filter binaries whose presence affects capability.
# Kept domain-agnostic: this is a generic pandoc-adjacent tooling probe.
#
# pandoc-citeproc is intentionally NOT auto-enabled: it was deprecated in
# pandoc 2.11 (the `--citeproc` flag supersedes it), and on older hosts
# where the binary is still present it would double-process citations
# alongside `--natbib` and produce broken bibliographies. Callers that
# genuinely want the legacy filter can still request it via
# ``external_filters=["pandoc-citeproc"]``.
_KNOWN_EXTERNAL_FILTERS: tuple[str, ...] = ("pandoc-crossref",)


class PandocError(RuntimeError):
    """Base class for pandoc-related failures."""


class PandocNotAvailable(PandocError):
    """Raised when pandoc is required but not installed or too old."""


class PandocExecutionError(PandocError):
    """Raised when a pandoc subprocess exits non-zero."""

    def __init__(self, message: str, *, stderr: str = "", returncode: int | None = None) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


@dataclass(frozen=True)
class PandocStatus:
    """Result of probing the pandoc installation."""

    available: bool
    binary_path: str | None = None
    version: tuple[int, int, int] | None = None
    version_string: str | None = None
    meets_minimum: bool = False
    installed_filters: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None

    def require(self) -> None:
        """Raise :class:`PandocNotAvailable` unless pandoc is usable."""
        if not self.available:
            raise PandocNotAvailable(self.error or "pandoc is not installed or not on PATH")
        if not self.meets_minimum:
            min_major, min_minor = MIN_PANDOC_VERSION
            raise PandocNotAvailable(
                f"pandoc {self.version_string or 'unknown'} is too old; "
                f">={min_major}.{min_minor} is required for reliable Lua filter support"
            )


_VERSION_RE = re.compile(r"pandoc(?:\.exe)?\s+(\d+)\.(\d+)(?:\.(\d+))?")


def _parse_version(output: str) -> tuple[tuple[int, int, int] | None, str | None]:
    for line in output.splitlines():
        match = _VERSION_RE.search(line.strip())
        if match:
            major = int(match.group(1))
            minor = int(match.group(2))
            patch = int(match.group(3) or 0)
            return (major, minor, patch), line.strip()
    return None, None


def detect_pandoc(
    *,
    binary: str = "pandoc",
    timeout: float = DEFAULT_DETECT_TIMEOUT_SECONDS,
) -> PandocStatus:
    """Probe pandoc availability, version, and installed companion filters.

    Never raises -- returns a :class:`PandocStatus` describing what was found.
    Callers that need pandoc should call :meth:`PandocStatus.require` afterwards.
    """
    binary_path = shutil.which(binary)
    if binary_path is None:
        return PandocStatus(available=False, error=f"{binary!r} not found on PATH")

    try:
        result = subprocess.run(  # noqa: S603 (binary resolved via shutil.which)
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:  # race vs. shutil.which; handle defensively
        return PandocStatus(available=False, binary_path=binary_path, error=str(exc))
    except subprocess.TimeoutExpired:
        return PandocStatus(
            available=False,
            binary_path=binary_path,
            error=f"{binary} --version timed out after {timeout:.0f}s",
        )

    if result.returncode != 0:
        return PandocStatus(
            available=False,
            binary_path=binary_path,
            error=f"{binary} --version exited {result.returncode}: {result.stderr.strip()}",
        )

    version, version_line = _parse_version(result.stdout)
    if version is None:
        return PandocStatus(
            available=False,
            binary_path=binary_path,
            error="could not parse pandoc version from --version output",
        )

    meets_minimum = (version[0], version[1]) >= MIN_PANDOC_VERSION

    filters: list[str] = []
    for name in _KNOWN_EXTERNAL_FILTERS:
        if shutil.which(name) is not None:
            filters.append(name)

    return PandocStatus(
        available=True,
        binary_path=binary_path,
        version=version,
        version_string=version_line,
        meets_minimum=meets_minimum,
        installed_filters=tuple(filters),
    )


def _build_command(
    binary_path: str,
    *,
    from_format: str,
    to_format: str,
    lua_filters: list[Path] | None,
    bibliography: Path | None,
    template: Path | None,
    standalone: bool,
    citeproc: bool,
    natbib: bool,
    external_filters: list[str] | None,
    extra_args: list[str] | None,
) -> list[str]:
    cmd: list[str] = [binary_path, "-f", from_format, "-t", to_format]
    if standalone:
        cmd.append("--standalone")
    if template is not None:
        cmd.extend(["--template", str(template)])
    # External filters (pandoc-crossref) must come BEFORE Lua filters and
    # BEFORE --citeproc so their transformations happen first in the
    # filter chain -- pandoc-crossref has to resolve @fig:foo refs before
    # citeproc would otherwise try to treat them as citations.
    for name in external_filters or []:
        cmd.extend(["--filter", name])
    for lua in lua_filters or []:
        cmd.extend(["--lua-filter", str(lua)])
    if bibliography is not None:
        cmd.extend(["--bibliography", str(bibliography)])
    # --natbib and --citeproc are mutually exclusive to pandoc. citeproc
    # inlines formatted citation text; natbib emits \cite{...} for a later
    # bibtex pass. The paper pipeline relies on the template's
    # \bibliography{...}, so natbib is the right default.
    if citeproc:
        cmd.append("--citeproc")
    elif natbib:
        cmd.append("--natbib")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def run_pandoc(
    input_text: str,
    *,
    from_format: str = "markdown",
    to_format: str = "latex",
    lua_filters: list[Path] | None = None,
    bibliography: Path | None = None,
    template: Path | None = None,
    standalone: bool = False,
    citeproc: bool = False,
    natbib: bool = False,
    external_filters: list[str] | None = None,
    extra_args: list[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    binary: str = "pandoc",
    status: PandocStatus | None = None,
) -> str:
    """Run pandoc on an in-memory string and return stdout.

    Raises:
        PandocNotAvailable: pandoc is missing or below the minimum version.
        PandocExecutionError: pandoc exited non-zero.
    """
    if status is None:
        status = detect_pandoc(binary=binary)
    status.require()
    assert status.binary_path is not None  # narrowed by require()

    cmd = _build_command(
        status.binary_path,
        from_format=from_format,
        to_format=to_format,
        lua_filters=lua_filters,
        bibliography=bibliography,
        template=template,
        standalone=standalone,
        citeproc=citeproc,
        natbib=natbib,
        external_filters=external_filters,
        extra_args=extra_args,
    )

    try:
        completed = subprocess.run(  # noqa: S603
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PandocExecutionError(
            f"pandoc timed out after {timeout:.0f}s",
            stderr=exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
        ) from exc

    if completed.returncode != 0:
        raise PandocExecutionError(
            f"pandoc exited {completed.returncode}",
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    if completed.stderr:
        # Pandoc emits warnings on stderr even on success (e.g. missing refs).
        for line in completed.stderr.splitlines():
            logger.debug("pandoc: %s", line)

    return completed.stdout


def resolve_external_filters(
    requested: list[str] | None,
    status: PandocStatus,
) -> list[str]:
    """Return the subset of *requested* external filters that are actually installed.

    When *requested* is ``None`` (the "auto" case), every known filter
    in ``_KNOWN_EXTERNAL_FILTERS`` (currently just ``pandoc-crossref``) is
    enabled if it is in ``status.installed_filters``. This makes
    ``markdown_to_latex_fragment`` light up extra capabilities
    automatically when they happen to be present on the compile host,
    without forcing callers to probe.

    Passing an empty list explicitly disables all external filters. Pass
    an explicit list (e.g. ``["pandoc-citeproc"]``) to opt in to filters
    that are deliberately excluded from auto-detection.
    """
    if requested is None:
        return [name for name in _KNOWN_EXTERNAL_FILTERS if name in status.installed_filters]
    resolved: list[str] = []
    for name in requested:
        if name in status.installed_filters:
            resolved.append(name)
        else:
            logger.debug("pandoc filter %s requested but not installed; skipping", name)
    return resolved


def markdown_to_latex_fragment(
    markdown: str,
    *,
    lua_filters: list[Path] | None = None,
    bibliography: Path | None = None,
    citeproc: bool = False,
    natbib: bool = True,
    external_filters: list[str] | None = None,
    extra_args: list[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    binary: str = "pandoc",
    status: PandocStatus | None = None,
) -> str:
    """Convert a markdown string to a LaTeX fragment (no preamble/document wrapper).

    This is the primary API for paper-writer agents: they author in markdown,
    this function returns LaTeX that the template registry can substitute into
    a journal template. ``standalone`` is intentionally off so the output has
    no ``\\documentclass`` / ``\\begin{document}`` scaffolding.

    ``natbib`` defaults to True so pandoc emits natbib commands --
    ``\\citet{key}`` for textual ``@key`` references and ``\\citep{k1, k2}``
    for parenthetical ``[@k1; @k2]`` groups -- for the downstream bibtex
    pass to resolve against the template's ``\\bibliography{...}``.
    ``citeproc=True`` takes precedence (inlines formatted text and disables
    natbib), matching pandoc's own semantics (``--natbib`` and ``--citeproc``
    are mutually exclusive on the CLI).

    **Caveat:** with ``natbib=True``, any literal ``@token`` in prose is
    interpreted as a cite key. Authors who need literal ``@`` (email
    addresses, social handles) should escape as ``\\@`` or call with
    ``natbib=False``.

    *external_filters* defaults to ``None`` meaning "auto": every
    auto-detected filter (currently just ``pandoc-crossref``) that is
    installed on the host is added to the chain. Pass an explicit list to
    pin the selection, or an empty list to disable them entirely.
    ``pandoc-citeproc`` is intentionally excluded from auto-detection --
    see :data:`_KNOWN_EXTERNAL_FILTERS` for the rationale.
    """
    if status is None:
        status = detect_pandoc(binary=binary)
    resolved_externals = resolve_external_filters(external_filters, status)
    return run_pandoc(
        markdown,
        from_format="markdown",
        to_format="latex",
        lua_filters=lua_filters,
        bibliography=bibliography,
        template=None,
        standalone=False,
        citeproc=citeproc,
        natbib=natbib,
        external_filters=resolved_externals,
        extra_args=extra_args,
        timeout=timeout,
        binary=binary,
        status=status,
    )


__all__ = [
    "DEFAULT_DETECT_TIMEOUT_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "MIN_PANDOC_VERSION",
    "PandocError",
    "PandocExecutionError",
    "PandocNotAvailable",
    "PandocStatus",
    "detect_pandoc",
    "markdown_to_latex_fragment",
    "resolve_external_filters",
    "run_pandoc",
]
