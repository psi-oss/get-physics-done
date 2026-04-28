"""Compiler wrapper: TeX dependency checks, multi-pass compilation, full pipeline.

Wraps the LaTeX compiler with TeX resource pre-checks (kpsewhich),
latexmk support for multi-pass compilation, and the build_paper orchestrator.
Supports cross-platform LaTeX detection including Windows (MiKTeX, TeX Live).
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pybtex.database import BibliographyData

from gpd.mcp.paper.artifact_manifest import build_artifact_manifest, write_artifact_manifest
from gpd.mcp.paper.bibliography import (
    BibliographyAudit,
    CitationSource,
    audit_bibliography,
    build_bibliography_with_audit,
    write_bib_file,
    write_bibliography_audit,
)
from gpd.mcp.paper.figures import _prepare_figures_with_sources
from gpd.mcp.paper.journal_map import get_journal_spec
from gpd.mcp.paper.models import (
    ArtifactManifest,
    ArtifactRecord,
    FigureRef,
    JournalSpec,
    PaperConfig,
    PaperOutput,
    PaperToolchainCapability,
    derive_output_filename,
)
from gpd.mcp.paper.template_registry import render_paper

logger = logging.getLogger(__name__)


# ---- Cross-platform LaTeX detection ----

# Common Windows install paths for MiKTeX and TeX Live.
_WINDOWS_LATEX_SEARCH_DIRS: list[str] = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "MiKTeX", "miktex", "bin", "x64"),
    os.path.join(os.environ.get("PROGRAMFILES", ""), "MiKTeX", "miktex", "bin", "x64"),
    os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "MiKTeX", "miktex", "bin", "x64"),
    # TeX Live uses year-based directories; glob the most likely locations.
    os.path.join(os.environ.get("PROGRAMFILES", ""), "texlive"),
    os.path.join("C:\\", "texlive"),
]


def _which(binary: str) -> str | None:
    """Module-local wrapper around :func:`shutil.which` for test isolation."""
    return shutil.which(binary)


def _find_in_windows_paths(binary: str) -> str | None:
    """Search common Windows LaTeX install directories for *binary*."""
    for base in _WINDOWS_LATEX_SEARCH_DIRS:
        if not base or not os.path.isdir(base):
            continue
        # TeX Live nests binaries under <year>/bin/windows (or win64)
        candidate = os.path.join(base, f"{binary}.exe")
        if os.path.isfile(candidate):
            return candidate
        # Walk one level for TeX Live year dirs
        try:
            for child in os.listdir(base):
                child_path = os.path.join(base, child)
                if os.path.isdir(child_path):
                    for sub in ("bin", os.path.join("bin", "windows"), os.path.join("bin", "win64")):
                        candidate = os.path.join(child_path, sub, f"{binary}.exe")
                        if os.path.isfile(candidate):
                            return candidate
        except OSError:
            continue
    return None


def find_latex_compiler(compiler: str = "pdflatex") -> str | None:
    """Locate a LaTeX compiler on the current system.

    First tries the standard PATH via ``shutil.which``.  On Windows, also
    searches common MiKTeX and TeX Live install directories that may not be
    on the PATH.

    Returns the full path to the compiler, or ``None`` if not found.
    """
    found = _which(compiler)
    if found:
        return found
    if platform.system() == "Windows":
        return _find_in_windows_paths(compiler)
    return None


def find_tectonic() -> str | None:
    """Locate the Tectonic TeX engine on the current system.

    First tries the standard PATH via :func:`shutil.which`.  On Windows, also
    checks ``%LOCALAPPDATA%\\Programs\\Tectonic\\tectonic.exe`` and
    ``~/.cargo/bin/tectonic.exe`` — the two most common non-PATH install
    locations for Tectonic on Windows.

    Returns the full path to the tectonic binary, or ``None`` if not found.
    """
    found = _which("tectonic")
    if found:
        return found
    if platform.system() == "Windows":
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tectonic", "tectonic.exe"),
            os.path.join(os.path.expanduser("~"), ".cargo", "bin", "tectonic.exe"),
        ]
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
    return None


LatexToolchainStatus = PaperToolchainCapability


def detect_latex_toolchain(compiler: str = "pdflatex", *, prefer_tectonic: bool = True) -> LatexToolchainStatus:
    """Detect whether a usable paper toolchain is present.

    Returns a :class:`LatexToolchainStatus` summarising compiler availability,
    the resolved compiler path, helper-tool availability, the likely
    distribution name, and a human-readable readiness summary.

    Args:
        compiler: The pdflatex-family compiler to probe (default ``"pdflatex"``).
        prefer_tectonic: When ``True`` (the default), probe for Tectonic first.
            If Tectonic is found, it is reported as the active engine and the
            toolchain is considered ``"ready"`` without requiring separate
            bibtex / latexmk binaries — Tectonic handles them internally.
    """
    tectonic_path = find_tectonic() if prefer_tectonic else None
    tectonic_available = tectonic_path is not None

    path = find_latex_compiler(compiler)
    bibtex_path = find_latex_compiler("bibtex")
    latexmk_path = find_latex_compiler("latexmk")
    kpsewhich_path = find_latex_compiler("kpsewhich")

    compiler_available = path is not None
    bibtex_available = bibtex_path is not None
    latexmk_available = latexmk_path is not None
    kpsewhich_available = kpsewhich_path is not None
    # PDF extraction now uses pypdf (BSD-3-Clause) — no pdftotext binary required.
    try:
        import pypdf  # noqa: F401

        pdf_lib_available = True
    except ImportError:
        pdf_lib_available = False
    warnings: list[str] = []

    if not pdf_lib_available:
        warnings.append(
            "pypdf not found; PDF peer-review intake will require a nearby `.txt` companion file, "
            "but TeX/Markdown/TXT/CSV/TSV and built-in DOCX/XLSX intake remain available. "
            "Install with: pip install 'get-physics-done[paper]'"
        )

    # When Tectonic is available and preferred, it replaces pdflatex + bibtex +
    # latexmk entirely — no separate install guidance needed for those.
    if tectonic_available and prefer_tectonic:
        summary = f"Tectonic found: {tectonic_path}; handles bibliography and multi-pass internally"
        summary += "; readiness=ready"
        return LatexToolchainStatus(
            compiler="tectonic",
            compiler_available=True,
            compiler_path=tectonic_path,
            distribution="Tectonic",
            bibtex_available=bibtex_available,
            latexmk_available=latexmk_available,
            kpsewhich_available=kpsewhich_available,
            tectonic_available=True,
            tectonic_path=tectonic_path,
            pdf_review_ready=pdf_lib_available,
            readiness_state="ready",
            message=summary,
            warnings=warnings,
        )

    if compiler_available:
        if not bibtex_available:
            warnings.append(
                "bibtex not found; bibliography-free builds may still work, but citation-bearing builds and "
                "submission prep can fail without bibtex."
            )
        if not latexmk_available:
            warnings.append("latexmk not found; multi-pass compilation will fall back to manual passes.")
        if not kpsewhich_available:
            warnings.append("kpsewhich not found; TeX resource checks will assume installed resources.")
    if not compiler_available:
        warnings.append("Install a LaTeX distribution to enable paper compilation.")

    # Heuristic distribution name
    dist: str | None
    if compiler_available:
        lower = path.lower().replace("\\", "/")
        if "miktex" in lower:
            dist = "MiKTeX"
        elif "texlive" in lower:
            dist = "TeX Live"
        elif "mactex" in lower or "/Library/TeX/" in path:
            dist = "MacTeX"
        else:
            dist = "TeX distribution"
    else:
        dist = None

    if not compiler_available:
        return LatexToolchainStatus(
            compiler=compiler,
            compiler_available=False,
            compiler_path=None,
            distribution=None,
            bibtex_available=bibtex_available,
            latexmk_available=latexmk_available,
            kpsewhich_available=kpsewhich_available,
            tectonic_available=False,
            tectonic_path=None,
            pdf_review_ready=pdf_lib_available,
            readiness_state="blocked",
            message=get_latex_install_guidance(),
            warnings=warnings,
        )

    if bibtex_available:
        readiness_state = "ready"
        summary = f"{compiler} found ({dist}): {path}; BibTeX available"
    else:
        readiness_state = "degraded"
        summary = f"{compiler} found ({dist}): {path}; BibTeX missing"

    if latexmk_available:
        summary += "; latexmk available"
    else:
        summary += "; latexmk unavailable"
    if kpsewhich_available:
        summary += "; kpsewhich available"
    else:
        summary += "; kpsewhich unavailable"
    summary += f"; readiness={readiness_state}"

    return LatexToolchainStatus(
        compiler=compiler,
        compiler_available=True,
        compiler_path=path,
        distribution=dist,
        bibtex_available=bibtex_available,
        latexmk_available=latexmk_available,
        kpsewhich_available=kpsewhich_available,
        tectonic_available=False,
        tectonic_path=None,
        pdf_review_ready=pdf_lib_available,
        readiness_state=readiness_state,
        message=summary,
        warnings=warnings,
    )


def get_latex_install_guidance() -> str:
    """Return platform-specific guidance for installing a LaTeX distribution."""
    system = platform.system()
    tectonic_guidance = (
        "  - Tectonic (recommended, lightweight ~80MB, single binary):\n"
        "      https://tectonic-typesetting.github.io/en-US/install.html\n"
        "    Handles pdflatex + bibtex + multi-pass in one self-contained binary.\n"
    )
    if system == "Windows":
        return (
            "No LaTeX compiler found.\n"
            "Install one of the following:\n" + tectonic_guidance + "  - MiKTeX: https://miktex.org/download\n"
            "    After install, open the MiKTeX Console and enable automatic\n"
            "    package installation so missing .sty/.cls files are fetched\n"
            "    on demand.\n"
            "  - TeX Live: https://tug.org/texlive/windows.html\n"
            "After installation, restart your terminal so the new PATH entries\n"
            "take effect."
        )
    if system == "Darwin":
        return (
            "No LaTeX compiler found.\n"
            "Install one of the following:\n"
            + tectonic_guidance
            + "  - MacTeX (full, ~4.5GB): brew install --cask mactex\n"
            "  - BasicTeX (smaller, ~100MB): brew install --cask basictex\n"
            "  - TeX Live:                   https://tug.org/texlive/"
        )
    # Linux / other
    return (
        "No LaTeX compiler found.\n"
        "Install one of the following:\n"
        + tectonic_guidance
        + "  - Debian/Ubuntu: sudo apt install texlive-latex-base\n"
        "  - Fedora:        sudo dnf install texlive-scheme-basic\n"
        "  - Arch:          sudo pacman -S texlive-basic\n"
        "  - Or full suite: https://tug.org/texlive/"
    )


# ---- TeX resource availability check ----

_DOCUMENT_CLASS_TO_TLMGR: dict[str, str] = {
    "revtex4-2": "revtex",
    "aastex631": "aastex",
    "aastex701": "aastex",
    "mnras": "mnras",
    "jfm": "jfm",
    "article": "latex-base",
}


def _get_tlmgr_package(document_class: str) -> str:
    """Map document class to TeX Live package name."""
    return _DOCUMENT_CLASS_TO_TLMGR.get(document_class, document_class)


def _default_install_hint(package_name: str) -> str:
    """Return the standard TeX Live install guidance string."""
    return f"Install via: tlmgr install {package_name}"


def _merge_bibliography_data(*bibliographies: BibliographyData) -> BibliographyData:
    """Merge multiple pybtex bibliographies while preserving preambles."""
    merged = BibliographyData()
    merged_preamble: list[str] = []

    for bibliography in bibliographies:
        for preamble_line in getattr(bibliography, "preamble_list", []):
            if preamble_line not in merged_preamble:
                merged_preamble.append(preamble_line)
        for key, entry in bibliography.entries.items():
            merged.entries[key] = entry

    merged.preamble_list[:] = merged_preamble
    return merged


def _reference_bibtex_keys_from_audit(audit: BibliographyAudit | None) -> dict[str, str]:
    """Return the final emitted BibTeX key for each referenced project anchor."""
    if audit is None:
        return {}

    reference_bibtex_keys: dict[str, str] = {}
    for entry in audit.entries:
        reference_id = entry.reference_id.strip() if isinstance(entry.reference_id, str) else ""
        if reference_id:
            if reference_id in reference_bibtex_keys:
                raise ValueError(f"duplicate bibliography reference_id {reference_id!r} in audit")
            reference_bibtex_keys[reference_id] = entry.key
    return reference_bibtex_keys


class CitationCoherenceResult:
    """Result of comparing .tex citations against .bib entries."""

    __slots__ = (
        "tex_cite_keys",
        "bib_entry_keys",
        "unreferenced_bib_keys",
        "unresolved_cite_keys",
        "warnings",
    )

    def __init__(
        self,
        tex_cite_keys: set[str],
        bib_entry_keys: set[str],
        unreferenced_bib_keys: set[str],
        unresolved_cite_keys: set[str],
        warnings: list[str],
    ) -> None:
        self.tex_cite_keys = tex_cite_keys
        self.bib_entry_keys = bib_entry_keys
        self.unreferenced_bib_keys = unreferenced_bib_keys
        self.unresolved_cite_keys = unresolved_cite_keys
        self.warnings = warnings


_NOCITE_STAR_RE = re.compile(r"\\nocite\{\s*\*\s*\}")
_BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")


def _path_is_under(path: Path, root: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    return resolved_path == resolved_root or resolved_path.is_relative_to(resolved_root)


def _reject_external_manifest_sidecar(path: Path, output_dir: Path, *, label: str) -> None:
    if not _path_is_under(path, output_dir):
        raise ValueError(
            f"{label} must stay inside output_dir when emitting ARTIFACT-MANIFEST.json; "
            "external sidecars would make the portable manifest reference paths outside the paper package"
        )


def _remove_failed_build_output(path: Path | None, output_dir: Path) -> None:
    if path is None or not _path_is_under(path, output_dir):
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _mark_artifact_manifest_failed(
    manifest: ArtifactManifest | None,
    *,
    stage: str,
    errors: list[str],
) -> ArtifactManifest | None:
    if manifest is None or not manifest.artifacts:
        return manifest

    anchor = manifest.artifacts[0]
    displayed_errors = errors[:5]
    error_summary = "; ".join(displayed_errors)
    if len(errors) > len(displayed_errors):
        error_summary = f"{error_summary}; ... {len(errors) - len(displayed_errors)} more"

    failure_record = ArtifactRecord(
        artifact_id=f"build-failure-{stage}",
        category="audit",
        path=anchor.path,
        sha256=anchor.sha256,
        produced_by=f"build_paper:{stage}",
        metadata={
            "build_success": False,
            "failure_stage": stage,
            "error_count": len(errors),
            "errors": error_summary,
        },
    )
    return manifest.model_copy(update={"artifacts": [*manifest.artifacts, failure_record]})


def check_citation_bib_coherence(
    tex_content: str,
    bib_content: str,
) -> CitationCoherenceResult:
    """Compare citation commands in rendered .tex against entries in .bib.

    Operates on in-memory strings only -- no disk I/O.  Designed to run
    inside ``build_paper()`` between the TeX render step and the artifact
    manifest step.

    Handles ``\\nocite{*}`` (standard LaTeX: all bib entries are considered
    referenced).  Splits multi-key citations (``\\cite{a,b,c}``).
    """
    from gpd.core.paper_quality import _CITE_CMD_PREFIX_WITH_NOCITE, _visible_tex_content

    all_cite_re = re.compile(
        _CITE_CMD_PREFIX_WITH_NOCITE
        + r"(?:\[[^\]]*\])*"  # optional [] arguments (natbib)
        + r"\{([^}]*)\}"  # capture the key list
    )
    visible_tex_content = _visible_tex_content(tex_content)

    # Detect \nocite{*} -- all bib entries are considered referenced
    nocite_star = bool(_NOCITE_STAR_RE.search(visible_tex_content))

    # Parse all \cite-family commands from .tex
    tex_cite_keys: set[str] = set()
    for match in all_cite_re.finditer(visible_tex_content):
        for key in match.group(1).split(","):
            stripped = key.strip()
            if stripped:
                tex_cite_keys.add(stripped)

    # Parse all @type{key, entries from .bib
    bib_entry_keys: set[str] = set()
    for match in _BIB_KEY_RE.finditer(bib_content):
        key = match.group(1).strip()
        if key:
            bib_entry_keys.add(key)

    # If \nocite{*} is present, all bib entries count as referenced
    if nocite_star:
        unreferenced: set[str] = set()
    else:
        unreferenced = bib_entry_keys - tex_cite_keys

    unresolved = tex_cite_keys - bib_entry_keys
    # Remove the special "*" key from unresolved (it's a \nocite{*} artifact)
    unresolved.discard("*")

    warnings: list[str] = []

    if bib_entry_keys and not tex_cite_keys and not nocite_star:
        warnings.append(
            f"Bibliography contains {len(bib_entry_keys)} entries but the "
            f"manuscript body has zero \\cite{{}} commands. The bibliography "
            f"will not appear in the compiled paper."
        )
    elif unreferenced:
        sorted_keys = sorted(unreferenced)
        preview = ", ".join(sorted_keys[:5])
        suffix = f" (+{len(sorted_keys) - 5} more)" if len(sorted_keys) > 5 else ""
        warnings.append(f"{len(unreferenced)} bibliography entries are never cited: {preview}{suffix}")

    if unresolved:
        sorted_keys = sorted(unresolved)
        preview = ", ".join(sorted_keys[:5])
        suffix = f" (+{len(sorted_keys) - 5} more)" if len(sorted_keys) > 5 else ""
        warnings.append(f"{len(unresolved)} \\cite{{}} keys have no matching bibliography entry: {preview}{suffix}")

    return CitationCoherenceResult(
        tex_cite_keys=tex_cite_keys,
        bib_entry_keys=bib_entry_keys,
        unreferenced_bib_keys=unreferenced,
        unresolved_cite_keys=unresolved,
        warnings=warnings,
    )


def check_tex_file(
    resource_name: str,
    install_hint: str | None = None,
    *,
    assume_present_when_unavailable: bool = True,
) -> tuple[bool, str]:
    """Check if a TeX resource file is available via kpsewhich.

    Returns:
        (available, message) tuple. If kpsewhich is not installed,
        assumes the resource is present.
    """
    kpsewhich = find_latex_compiler("kpsewhich")
    hint = install_hint or _default_install_hint(Path(resource_name).stem)
    if not kpsewhich:
        if assume_present_when_unavailable:
            return True, "kpsewhich not available, assuming TeX resource present"
        return False, f"kpsewhich not available; cannot verify {resource_name}. {hint}"

    try:
        result = subprocess.run(
            [kpsewhich, resource_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        return False, f"{resource_name} not found. {hint}"
    except FileNotFoundError:
        if assume_present_when_unavailable:
            return True, "kpsewhich not available, assuming TeX resource present"
        return False, f"kpsewhich not available; cannot verify {resource_name}. {hint}"
    except subprocess.TimeoutExpired:
        if assume_present_when_unavailable:
            return True, "kpsewhich timed out, assuming TeX resource present"
        return False, f"kpsewhich timed out while checking {resource_name}. {hint}"


def check_class_file(
    document_class: str,
    install_hint: str | None = None,
    *,
    assume_present_when_unavailable: bool = True,
) -> tuple[bool, str]:
    """Check if a LaTeX class file is available via kpsewhich."""
    hint = install_hint or _default_install_hint(_get_tlmgr_package(document_class))
    return check_tex_file(
        f"{document_class}.cls",
        install_hint=hint,
        assume_present_when_unavailable=assume_present_when_unavailable,
    )


def check_journal_dependencies(spec: JournalSpec) -> tuple[bool, list[str]]:
    """Check whether a journal's class and support files are installed."""
    errors: list[str] = []
    install_hint = spec.install_hint or _default_install_hint(spec.texlive_package)

    available, message = check_class_file(
        spec.document_class,
        install_hint=install_hint,
    )
    if not available:
        errors.append(message)

    for resource_name in spec.required_tex_files:
        available, message = check_tex_file(
            resource_name,
            install_hint=install_hint,
        )
        if not available:
            errors.append(message)

    return not errors, errors


# ---- Multi-pass compilation ----


@dataclass(frozen=True)
class CompilationResult:
    """Result of LaTeX compilation."""

    success: bool
    pdf_path: Path | None = None
    error: str | None = None
    log: str | None = None
    warning: str | None = None


class _CompilationLaunchFailure(Exception):
    """Internal signal that a subprocess could not be started."""

    def __init__(self, command_label: str, original: OSError) -> None:
        super().__init__(str(original))
        self.command_label = command_label
        self.original = original


def _command_label(command: str) -> str:
    label = Path(command).name
    return label or command


def _launch_failure_error(command_label: str, exc: OSError) -> str:
    return f"failed to launch {command_label}: {exc}"


async def compile_paper(
    tex_path: Path,
    output_dir: Path,
    compiler: str = "pdflatex",
    *,
    prefer_tectonic: bool = True,
) -> CompilationResult:
    """Compile a .tex file to PDF.

    Routes through Tectonic when available and *prefer_tectonic* is ``True``
    (the default).  Falls back to latexmk or manual multi-pass when only a
    pdflatex-family compiler is present.

    Args:
        tex_path: Path to the .tex file.
        output_dir: Directory for output files.
        compiler: pdflatex-family compiler to use when Tectonic is not
            available (``"pdflatex"`` or ``"xelatex"``).
        prefer_tectonic: When ``True``, route through Tectonic if it is found
            on the system PATH (or in well-known install locations on Windows).

    Uses :func:`find_latex_compiler` for cross-platform compiler detection,
    including Windows MiKTeX and TeX Live installations that may not be on
    the system PATH.
    """
    tex_path = Path(tex_path).resolve(strict=False)
    output_dir = Path(output_dir).resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prefer Tectonic when available — it handles bibtex + multi-pass itself.
    if prefer_tectonic:
        tectonic_path = find_tectonic()
        if tectonic_path:
            return await _compile_with_tectonic(tex_path, output_dir, tectonic_path=tectonic_path)

    # Pre-check: is the pdflatex-family compiler available at all?
    if find_latex_compiler(compiler) is None:
        guidance = get_latex_install_guidance()
        return CompilationResult(
            success=False,
            error=f"Compiler '{compiler}' not found. {guidance}",
        )

    latexmk_path = find_latex_compiler("latexmk")
    if latexmk_path:
        return await _compile_with_latexmk(tex_path, output_dir, compiler, latexmk_path=latexmk_path)
    return await _compile_manual_multipass(tex_path, output_dir, compiler)


async def _compile_with_tectonic(
    tex_path: Path,
    output_dir: Path,
    *,
    tectonic_path: str,
) -> CompilationResult:
    """Compile a .tex file using Tectonic.

    Tectonic resolves bibliography and performs all necessary passes in a
    single invocation — no separate bibtex / latexmk steps required.

    Command: ``tectonic --outdir <output_dir> --keep-logs <tex_path>``
    """
    cmd = [
        tectonic_path,
        "--outdir",
        str(output_dir),
        "--keep-logs",
        str(tex_path),
    ]
    logger.info("Compiling with Tectonic: %s", " ".join(cmd))

    pdf_path = output_dir / f"{tex_path.stem}.pdf"

    def _pdf_signature() -> tuple[int, int] | None:
        if not pdf_path.exists():
            return None
        try:
            stat = pdf_path.stat()
        except OSError:
            return None
        return stat.st_size, stat.st_mtime_ns

    initial_signature = _pdf_signature()

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(tex_path.parent),
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except TimeoutError:
            process.kill()
            await process.wait()
            return CompilationResult(success=False, error="Tectonic compilation timed out after 120 seconds")

        log_content = stdout.decode(errors="replace") + stderr.decode(errors="replace")

        current_signature = _pdf_signature()
        pdf_is_fresh = current_signature is not None and (
            initial_signature is None or current_signature != initial_signature
        )

        if pdf_is_fresh:
            if process.returncode == 0:
                return CompilationResult(success=True, pdf_path=pdf_path)
            return CompilationResult(
                success=True,
                pdf_path=pdf_path,
                warning=f"tectonic exited with code {process.returncode} — PDF was produced but check the log for issues",
                log=log_content[-5000:],
            )

        if process.returncode != 0:
            error = f"tectonic exited with code {process.returncode}"
        else:
            error = "tectonic finished without producing a PDF"
        return CompilationResult(success=False, error=error, log=log_content[-5000:])
    except FileNotFoundError:
        return CompilationResult(success=False, error="tectonic not found")
    except OSError as exc:
        return CompilationResult(success=False, error=_launch_failure_error("tectonic", exc))


async def _compile_with_latexmk(
    tex_path: Path,
    output_dir: Path,
    compiler: str,
    *,
    latexmk_path: str,
) -> CompilationResult:
    """Compile using latexmk (handles bibtex + multiple passes automatically)."""
    if compiler == "xelatex":
        cmd = [latexmk_path, "-xelatex", "-interaction=nonstopmode", f"-output-directory={output_dir}", str(tex_path)]
    else:
        cmd = [latexmk_path, "-pdf", "-interaction=nonstopmode", f"-output-directory={output_dir}", str(tex_path)]

    logger.info("Compiling with latexmk: %s", " ".join(cmd))

    pdf_path = output_dir / f"{tex_path.stem}.pdf"

    def _pdf_signature() -> tuple[int, int] | None:
        """Return (size, mtime_ns) if the PDF exists, else None."""
        if not pdf_path.exists():
            return None
        try:
            stat = pdf_path.stat()
        except OSError:
            return None
        return stat.st_size, stat.st_mtime_ns

    initial_signature = _pdf_signature()

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(tex_path.parent),
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except TimeoutError:
            process.kill()
            await process.wait()
            return CompilationResult(success=False, error="Compilation timed out after 120 seconds")

        log_content = stdout.decode(errors="replace") + stderr.decode(errors="replace")

        # Freshness check: PDF must exist and differ from the pre-run snapshot.
        current_signature = _pdf_signature()
        pdf_is_fresh = current_signature is not None and (
            initial_signature is None or current_signature != initial_signature
        )

        if pdf_is_fresh:
            # Fresh PDF produced. latexmk exit code 12 means "failure in
            # some part of making files" but pdflatex may still produce a
            # valid PDF (e.g., unresolved references in nonstop mode).
            # The freshness check confirms the PDF is real, not stale.
            if process.returncode == 0:
                return CompilationResult(success=True, pdf_path=pdf_path)
            return CompilationResult(
                success=True,
                pdf_path=pdf_path,
                warning=f"latexmk exited with code {process.returncode} — PDF was produced but check the log for issues",
                log=log_content[-5000:],
            )

        # No fresh PDF. A stale file may sit on disk from an earlier build.
        if pdf_path.exists():
            if process.returncode != 0:
                error = f"latexmk exited with code {process.returncode}"
            else:
                error = "latexmk finished without producing a fresh PDF"
            return CompilationResult(
                success=False,
                pdf_path=pdf_path,
                error=error,
                log=log_content[-5000:],
            )

        if process.returncode != 0:
            error = f"latexmk exited with code {process.returncode}"
        else:
            error = "latexmk finished without producing a PDF"
        return CompilationResult(success=False, error=error, log=log_content[-5000:])
    except FileNotFoundError:
        return CompilationResult(success=False, error="latexmk not found")
    except OSError as exc:
        return CompilationResult(success=False, error=_launch_failure_error("latexmk", exc))


async def _compile_manual_multipass(tex_path: Path, output_dir: Path, compiler: str) -> CompilationResult:
    """Manual multi-pass: pdflatex -> bibtex -> pdflatex -> pdflatex."""
    compiler_path = find_latex_compiler(compiler)
    if not compiler_path:
        return CompilationResult(success=False, error=f"Compiler '{compiler}' not found")

    async def run_cmd(cmd: list[str], cwd: str) -> tuple[int, str]:
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except OSError as exc:
            raise _CompilationLaunchFailure(_command_label(cmd[0]), exc) from exc
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise
        return process.returncode or 0, stdout.decode(errors="replace") + stderr.decode(errors="replace")

    cwd = str(tex_path.parent)
    base_cmd = [compiler_path, "-interaction=nonstopmode", f"-output-directory={output_dir}", str(tex_path)]
    combined_log_parts: list[str] = []
    compile_errors: list[str] = []
    fatal_errors: list[str] = []
    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    autofix_scratch_tex_path: Path | None = None
    autofix_scratch_pdf_path: Path | None = None

    def pdf_build_signature(path: Path = pdf_path) -> tuple[int, int] | None:
        if not path.exists():
            return None
        try:
            stat = path.stat()
        except OSError:
            return None
        return stat.st_size, stat.st_mtime_ns

    initial_pdf_signature = pdf_build_signature()

    def record_result(step: str, returncode: int, log: str, *, fatal: bool = False) -> None:
        combined_log_parts.append(log)
        if returncode != 0:
            error = f"{step} exited with code {returncode}"
            compile_errors.append(error)
            if fatal:
                fatal_errors.append(error)

    def fresh_pdf_was_generated(
        initial_signature: tuple[int, int] | None,
        path: Path = pdf_path,
    ) -> bool:
        current_signature = pdf_build_signature(path)
        if current_signature is None:
            return False
        return initial_signature is None or current_signature != initial_signature

    def write_autofix_scratch(content: str) -> Path:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".tex",
            prefix=f".{tex_path.stem}-gpd-autofix-",
            dir=tex_path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            return Path(handle.name)

    def cleanup_autofix_scratch(scratch_tex_path: Path, scratch_pdf_path: Path | None = None) -> None:
        scratch_output_dir = output_dir
        scratch_stem = scratch_tex_path.stem
        scratch_paths = [
            scratch_tex_path,
            scratch_output_dir / f"{scratch_stem}.aux",
            scratch_output_dir / f"{scratch_stem}.bbl",
            scratch_output_dir / f"{scratch_stem}.blg",
            scratch_output_dir / f"{scratch_stem}.fdb_latexmk",
            scratch_output_dir / f"{scratch_stem}.fls",
            scratch_output_dir / f"{scratch_stem}.log",
            scratch_output_dir / f"{scratch_stem}.out",
            scratch_output_dir / f"{scratch_stem}.synctex.gz",
        ]
        if scratch_pdf_path is not None:
            scratch_paths.append(scratch_pdf_path)
        for path in scratch_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.debug("Could not remove autofix scratch artifact %s", path, exc_info=True)

    def aux_requires_bibliography(aux_path: Path) -> bool:
        try:
            content = aux_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
        return "\\citation" in content or "\\bibdata" in content

    def record_missing_bibtex_requirement() -> None:
        if bibtex or not aux_path.exists() or not aux_requires_bibliography(aux_path):
            return
        warning = "bibtex not found -- bibliography will not be processed; citations will show as [?]"
        logger.warning(warning)
        if warning + "\n" not in combined_log_parts:
            combined_log_parts.append(warning + "\n")
        error = "bibtex not found but citations require bibliography processing"
        if error not in compile_errors:
            compile_errors.append(error)
        if error not in fatal_errors:
            fatal_errors.append(error)

    try:
        # Pass 1: pdflatex
        returncode, log = await run_cmd(base_cmd, cwd)
        record_result("pdflatex pass 1", returncode, log)

        # bibtex
        aux_path = output_dir / f"{tex_path.stem}.aux"
        bibtex = find_latex_compiler("bibtex")
        if not bibtex:
            record_missing_bibtex_requirement()
        if bibtex and aux_path.exists():
            returncode, log = await run_cmd([bibtex, str(aux_path)], cwd)
            record_result("bibtex", returncode, log, fatal=True)

        # Pass 2 & 3: pdflatex
        returncode, log = await run_cmd(base_cmd, cwd)
        record_result("pdflatex pass 2", returncode, log)
        returncode, log = await run_cmd(base_cmd, cwd)
        record_result("pdflatex pass 3", returncode, log)

        if fresh_pdf_was_generated(initial_pdf_signature) and not compile_errors:
            return CompilationResult(success=True, pdf_path=pdf_path)
        # Only the last pass matters: earlier passes often exit non-zero
        # due to unresolved references/citations (expected behaviour).
        if fresh_pdf_was_generated(initial_pdf_signature) and returncode == 0 and not fatal_errors:
            return CompilationResult(success=True, pdf_path=pdf_path)

        # Try autofix
        from gpd.utils.latex import try_autofix

        combined_log = "".join(combined_log_parts)
        tex_content = await asyncio.to_thread(tex_path.read_text, encoding="utf-8")
        fix_result = try_autofix(tex_content, combined_log)
        if fix_result.was_modified and fix_result.fixed_content:
            autofix_scratch_tex_path = await asyncio.to_thread(write_autofix_scratch, fix_result.fixed_content)
            scratch_tex_path = autofix_scratch_tex_path
            autofix_scratch_pdf_path = output_dir / f"{scratch_tex_path.stem}.pdf"
            scratch_pdf_path = autofix_scratch_pdf_path
            logger.info("Testing autofix on scratch TeX: %s", fix_result.fixes_applied)
            autofix_initial_pdf_signature = pdf_build_signature(scratch_pdf_path)
            autofix_base_cmd = [
                compiler_path,
                "-interaction=nonstopmode",
                f"-output-directory={output_dir}",
                str(scratch_tex_path),
            ]
            autofix_aux_path = output_dir / f"{scratch_tex_path.stem}.aux"

            combined_log_parts = []
            compile_errors = []
            fatal_errors = []

            returncode, log = await run_cmd(autofix_base_cmd, cwd)
            record_result("pdflatex autofix pass 1", returncode, log)
            if bibtex and autofix_aux_path.exists():
                returncode, log = await run_cmd([bibtex, str(autofix_aux_path)], cwd)
                record_result("bibtex autofix", returncode, log, fatal=True)
            if not bibtex:
                aux_path = autofix_aux_path
                record_missing_bibtex_requirement()
            returncode, log = await run_cmd(autofix_base_cmd, cwd)
            record_result("pdflatex autofix pass 2", returncode, log)
            returncode, log = await run_cmd(autofix_base_cmd, cwd)
            record_result("pdflatex autofix pass 3", returncode, log)
            if fresh_pdf_was_generated(autofix_initial_pdf_signature, scratch_pdf_path) and (
                not compile_errors or (returncode == 0 and not fatal_errors)
            ):
                await asyncio.to_thread(shutil.copy2, scratch_pdf_path, pdf_path)
                await asyncio.to_thread(tex_path.write_text, fix_result.fixed_content, encoding="utf-8")
                await asyncio.to_thread(cleanup_autofix_scratch, scratch_tex_path, scratch_pdf_path)
                logger.info("Applied autofix: %s", fix_result.fixes_applied)
                return CompilationResult(success=True, pdf_path=pdf_path)
            await asyncio.to_thread(cleanup_autofix_scratch, scratch_tex_path, scratch_pdf_path)

        error = fatal_errors[0] if fatal_errors else compile_errors[0] if compile_errors else "Compilation failed"
        return CompilationResult(success=False, error=error, log="".join(combined_log_parts)[-5000:])

    except TimeoutError:
        if autofix_scratch_tex_path is not None:
            await asyncio.to_thread(
                cleanup_autofix_scratch,
                autofix_scratch_tex_path,
                autofix_scratch_pdf_path,
            )
        return CompilationResult(success=False, error="Compilation timed out")
    except _CompilationLaunchFailure as exc:
        if autofix_scratch_tex_path is not None:
            await asyncio.to_thread(
                cleanup_autofix_scratch,
                autofix_scratch_tex_path,
                autofix_scratch_pdf_path,
            )
        if isinstance(exc.original, FileNotFoundError):
            error = f"{exc.command_label} not found"
        else:
            error = _launch_failure_error(exc.command_label, exc.original)
        log = "".join(combined_log_parts)[-5000:] or None
        return CompilationResult(success=False, error=error, log=log)


# ---- Full pipeline ----


async def build_paper(
    config: PaperConfig,
    output_dir: Path,
    bib_data: BibliographyData | None = None,
    citation_sources: list[CitationSource] | None = None,
    enrich_bibliography: bool = True,
    *,
    sidecar_root: Path | None = None,
    artifact_manifest_output_path: Path | None = None,
    bibliography_audit_output_path: Path | None = None,
    emit_artifact_manifest: bool = True,
    emit_bibliography_audit: bool = True,
) -> PaperOutput:
    """Orchestrate the full paper build pipeline.

    1. Prepare figures (normalize, size)
    2. Write .bib file
    3. Render .tex from template
    4. Check required TeX resources
    5. Compile to PDF

    Sidecar files (ARTIFACT-MANIFEST.json, BIBLIOGRAPHY-AUDIT.json) are written
    to ``sidecar_root`` when provided, otherwise to ``output_dir`` alongside
    the manuscript. ``emit_artifact_manifest`` and ``emit_bibliography_audit``
    can be set to ``False`` to suppress those files entirely (minimal mode).
    File-specific output paths override the shared sidecar root so callers can
    promote one sidecar without moving the other.
    """
    if emit_artifact_manifest:
        if sidecar_root is not None:
            _reject_external_manifest_sidecar(sidecar_root, output_dir, label="sidecar_root")
        if artifact_manifest_output_path is not None:
            _reject_external_manifest_sidecar(
                artifact_manifest_output_path,
                output_dir,
                label="artifact_manifest_output_path",
            )
        if emit_bibliography_audit and bibliography_audit_output_path is not None:
            _reject_external_manifest_sidecar(
                bibliography_audit_output_path,
                output_dir,
                label="bibliography_audit_output_path",
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    if sidecar_root is not None:
        sidecar_root.mkdir(parents=True, exist_ok=True)
    resolved_sidecar_root = sidecar_root if sidecar_root is not None else output_dir
    figures_dir: Path | None = None
    manifest = None
    manifest_path = None
    if emit_artifact_manifest:
        manifest_path = artifact_manifest_output_path or resolved_sidecar_root / "ARTIFACT-MANIFEST.json"
    bibliography_audit = None
    bibliography_audit_path: Path | None = None
    errors: list[str] = []
    figure_source_pairs: list[tuple[FigureRef, FigureRef]] = []
    figures_prepared_successfully = True
    bib_path: Path | None = None
    bib_entry_source: str | None = "bib_data" if bib_data is not None else None
    citation_audit_entries = None

    # 1. Prepare figures
    if config.figures:
        requested_figure_count = len(config.figures)
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(exist_ok=True)
        try:
            prepared, fig_errors, figure_source_pairs = _prepare_figures_with_sources(
                config.figures,
                figures_dir,
                config.journal,
            )
            try:
                figures_prefix = figures_dir.relative_to(output_dir)
            except ValueError:
                figures_prefix = figures_dir

            def _rebase_prepared_figure_path(figure: FigureRef) -> FigureRef:
                if figure.path.is_absolute():
                    return figure
                return figure.model_copy(update={"path": figures_prefix / figure.path})

            prepared = [_rebase_prepared_figure_path(figure) for figure in prepared]
            figure_source_pairs = [
                (original, _rebase_prepared_figure_path(prepared_figure))
                for original, prepared_figure in figure_source_pairs
            ]
            figures_prepared_successfully = not fig_errors and len(prepared) == requested_figure_count
            if len(prepared) != requested_figure_count and not fig_errors:
                errors.append(
                    "Figure preparation did not preserve all requested figures; treating build as unsuccessful."
                )
            errors.extend(fig_errors)
        except (ValueError, RuntimeError, OSError) as exc:
            figures_prepared_successfully = False
            errors.append(f"Figure preparation failed: {exc}")
            prepared = []
            figure_source_pairs = []
        config = config.model_copy(update={"figures": prepared})

    if citation_sources:
        reserved_bib_keys = set(bib_data.entries) if bib_data is not None else None
        built_bib, bibliography_audit = await asyncio.to_thread(
            build_bibliography_with_audit,
            citation_sources,
            enrich_bibliography,
            reserved_bib_keys,
        )
        citation_audit_entries = list(bibliography_audit.entries)
        if bib_data is None:
            bib_data = built_bib
            bib_entry_source = "citation_sources"
        else:
            bib_data = _merge_bibliography_data(bib_data, built_bib)
            bib_entry_source = "bib_data+citation_sources"

    if bib_data is not None:
        bibliography_audit = audit_bibliography(bib_data, source_audit_entries=citation_audit_entries)
        if emit_bibliography_audit:
            bibliography_audit_path = (
                bibliography_audit_output_path or resolved_sidecar_root / "BIBLIOGRAPHY-AUDIT.json"
            )
            await asyncio.to_thread(write_bibliography_audit, bibliography_audit, bibliography_audit_path)
    reference_bibtex_keys = _reference_bibtex_keys_from_audit(bibliography_audit)

    # 2. Write .bib file
    bib_content = ""
    if bib_data:
        bib_stem = config.bib_file.removesuffix(".bib")
        bib_path = output_dir / f"{bib_stem}.bib"
        await asyncio.to_thread(write_bib_file, bib_data, bib_path)
        bib_content = await asyncio.to_thread(bib_path.read_text, encoding="utf-8")

    # 3. Render .tex
    bib_stem = config.bib_file.removesuffix(".bib")
    if bib_stem != config.bib_file:
        config = config.model_copy(update={"bib_file": bib_stem})
    rendered_tex_content = render_paper(config)
    tex_content = rendered_tex_content
    output_stem = derive_output_filename(config)
    tex_path = output_dir / f"{output_stem}.tex"
    preserved_tex_differs_from_config = False
    if tex_path.exists():
        logger.warning("Skipping .tex write — %s already exists. Delete it to regenerate.", tex_path)
        # Read on-disk content so the coherence check audits the file that
        # will actually be compiled, not the freshly rendered string which
        # may differ after manual edits or scaffold-once reruns.
        tex_content = await asyncio.to_thread(tex_path.read_text, encoding="utf-8")
        preserved_tex_differs_from_config = tex_content != rendered_tex_content
        if preserved_tex_differs_from_config and emit_artifact_manifest:
            errors.append(
                f"Existing TeX file {tex_path} differs from the current PaperConfig render; "
                "ARTIFACT-MANIFEST.json was not refreshed because it would claim metadata for stale preserved TeX. "
                "Delete the TeX file to regenerate it, or run with sidecar emission disabled when intentionally "
                "compiling manual edits."
            )
            manifest_path = None
    else:
        await asyncio.to_thread(tex_path.write_text, tex_content, encoding="utf-8")

    # --- Citation-bibliography coherence check ---
    citation_warnings: list[str] = []
    if bib_content:
        coherence = check_citation_bib_coherence(tex_content, bib_content)
        for w in coherence.warnings:
            logger.warning("Citation coherence: %s", w)
        citation_warnings = coherence.warnings

    # 4. Check required TeX resources (blocking subprocess; run in thread to avoid stalling the loop)
    spec = get_journal_spec(config.journal)
    dependencies_available, dependency_errors = await asyncio.to_thread(check_journal_dependencies, spec)
    if not dependencies_available:
        errors.extend(dependency_errors)
        await asyncio.to_thread(_remove_failed_build_output, output_dir / f"{output_stem}.pdf", output_dir)
        if emit_artifact_manifest and not preserved_tex_differs_from_config:
            manifest = build_artifact_manifest(
                config,
                output_dir,
                tex_path=tex_path,
                bib_path=bib_path,
                bib_entry_source=bib_entry_source,
                bibliography_audit_path=bibliography_audit_path,
                bibliography_audit=bibliography_audit,
                figure_source_pairs=figure_source_pairs,
            )
            manifest = _mark_artifact_manifest_failed(manifest, stage="dependency", errors=errors)
            if manifest_path is not None:
                await asyncio.to_thread(write_artifact_manifest, manifest, manifest_path)
        return PaperOutput(
            tex_content=tex_content,
            bib_content=bib_content,
            tex_path=tex_path,
            figures_dir=figures_dir,
            pdf_path=None,
            bibliography_audit_path=bibliography_audit_path,
            bibliography_audit=bibliography_audit,
            reference_bibtex_keys=reference_bibtex_keys,
            manifest_path=manifest_path if manifest is not None else None,
            manifest=manifest,
            success=False,
            errors=errors,
            citation_warnings=citation_warnings,
        )

    # 5. Compile
    result = await compile_paper(tex_path, output_dir, compiler=spec.compiler)

    if not result.success and result.error:
        errors.append(result.error)

    final_success = result.success and figures_prepared_successfully and not errors
    published_pdf_path = result.pdf_path if final_success else None
    if not final_success:
        await asyncio.to_thread(_remove_failed_build_output, result.pdf_path, output_dir)
        await asyncio.to_thread(_remove_failed_build_output, output_dir / f"{output_stem}.pdf", output_dir)

    if emit_artifact_manifest and not preserved_tex_differs_from_config:
        manifest = build_artifact_manifest(
            config,
            output_dir,
            tex_path=tex_path,
            bib_path=bib_path,
            bib_entry_source=bib_entry_source,
            bibliography_audit_path=bibliography_audit_path,
            bibliography_audit=bibliography_audit,
            figure_source_pairs=figure_source_pairs,
            pdf_path=published_pdf_path,
        )
        if not final_success:
            manifest = _mark_artifact_manifest_failed(
                manifest,
                stage="compile" if not result.success else "build",
                errors=errors,
            )
        if manifest_path is not None:
            await asyncio.to_thread(write_artifact_manifest, manifest, manifest_path)

    return PaperOutput(
        tex_content=tex_content,
        bib_content=bib_content,
        tex_path=tex_path,
        figures_dir=figures_dir,
        pdf_path=published_pdf_path,
        bibliography_audit_path=bibliography_audit_path,
        bibliography_audit=bibliography_audit,
        reference_bibtex_keys=reference_bibtex_keys,
        manifest_path=manifest_path if manifest is not None else None,
        manifest=manifest,
        success=final_success,
        errors=errors,
        citation_warnings=citation_warnings,
    )
