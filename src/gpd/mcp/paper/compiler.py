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
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pybtex.database import BibliographyData

from gpd.core.paper_quality import Severity, validate_tex_draft
from gpd.mcp.paper.artifact_manifest import build_artifact_manifest, write_artifact_manifest
from gpd.mcp.paper.bibliography import (
    CitationSource,
    build_bibliography_with_audit,
    write_bib_file,
    write_bibliography_audit,
)
from gpd.mcp.paper.figures import _prepare_figures_with_sources
from gpd.mcp.paper.journal_map import get_journal_spec
from gpd.mcp.paper.models import FigureRef, JournalSpec, PaperConfig, PaperOutput
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
    found = shutil.which(compiler)
    if found:
        return found
    if platform.system() == "Windows":
        return _find_in_windows_paths(compiler)
    return None


@dataclass(frozen=True)
class LatexToolchainStatus:
    """Result of a LaTeX toolchain availability check."""

    available: bool
    compiler_path: str | None = None
    distribution: str | None = None
    message: str = ""


def detect_latex_toolchain(compiler: str = "pdflatex") -> LatexToolchainStatus:
    """Detect whether a usable LaTeX toolchain is present.

    Returns a :class:`LatexToolchainStatus` summarising availability, the
    resolved compiler path, the likely distribution name, and a
    human-readable message.
    """
    path = find_latex_compiler(compiler)
    if path is None:
        return LatexToolchainStatus(
            available=False,
            message=get_latex_install_guidance(),
        )

    # Heuristic distribution name
    lower = path.lower().replace("\\", "/")
    if "miktex" in lower:
        dist = "MiKTeX"
    elif "texlive" in lower:
        dist = "TeX Live"
    elif "mactex" in lower or "/Library/TeX/" in path:
        dist = "MacTeX"
    else:
        dist = "TeX distribution"

    return LatexToolchainStatus(
        available=True,
        compiler_path=path,
        distribution=dist,
        message=f"{compiler} found ({dist}): {path}",
    )


def get_latex_install_guidance() -> str:
    """Return platform-specific guidance for installing a LaTeX distribution."""
    system = platform.system()
    if system == "Windows":
        return (
            "No LaTeX compiler found.\n"
            "Install one of the following LaTeX distributions:\n"
            "  - MiKTeX (recommended): https://miktex.org/download\n"
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
            "Install a LaTeX distribution:\n"
            "  - MacTeX (recommended): brew install --cask mactex\n"
            "  - BasicTeX (smaller):    brew install --cask basictex\n"
            "  - TeX Live:              https://tug.org/texlive/"
        )
    # Linux / other
    return (
        "No LaTeX compiler found.\n"
        "Install TeX Live via your package manager:\n"
        "  - Debian/Ubuntu: sudo apt install texlive-latex-base\n"
        "  - Fedora:        sudo dnf install texlive-scheme-basic\n"
        "  - Arch:          sudo pacman -S texlive-basic\n"
        "  - Or full suite:  https://tug.org/texlive/"
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


def check_tex_file(resource_name: str, install_hint: str | None = None) -> tuple[bool, str]:
    """Check if a TeX resource file is available via kpsewhich.

    Returns:
        (available, message) tuple. If kpsewhich is not installed,
        assumes the resource is present.
    """
    try:
        result = subprocess.run(
            ["kpsewhich", resource_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        hint = install_hint or _default_install_hint(Path(resource_name).stem)
        return False, f"{resource_name} not found. {hint}"
    except FileNotFoundError:
        return True, "kpsewhich not available, assuming TeX resource present"
    except subprocess.TimeoutExpired:
        return True, "kpsewhich timed out, assuming TeX resource present"


def check_class_file(document_class: str, install_hint: str | None = None) -> tuple[bool, str]:
    """Check if a LaTeX class file is available via kpsewhich."""
    hint = install_hint or _default_install_hint(_get_tlmgr_package(document_class))
    return check_tex_file(f"{document_class}.cls", install_hint=hint)


def check_journal_dependencies(spec: JournalSpec) -> tuple[bool, list[str]]:
    """Check whether a journal's class and support files are installed."""
    errors: list[str] = []
    install_hint = spec.install_hint or _default_install_hint(spec.texlive_package)

    available, message = check_class_file(spec.document_class, install_hint=install_hint)
    if not available:
        errors.append(message)

    for resource_name in spec.required_tex_files:
        available, message = check_tex_file(resource_name, install_hint=install_hint)
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


async def compile_paper(tex_path: Path, output_dir: Path, compiler: str = "pdflatex") -> CompilationResult:
    """Compile a .tex file to PDF using latexmk or manual multi-pass.

    Args:
        tex_path: Path to the .tex file.
        output_dir: Directory for output files.
        compiler: TeX compiler to use (pdflatex or xelatex).

    Uses :func:`find_latex_compiler` for cross-platform compiler detection,
    including Windows MiKTeX and TeX Live installations that may not be on
    the system PATH.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-check: is the compiler available at all?
    if find_latex_compiler(compiler) is None:
        guidance = get_latex_install_guidance()
        return CompilationResult(
            success=False,
            error=f"Compiler '{compiler}' not found. {guidance}",
        )

    if shutil.which("latexmk"):
        return await _compile_with_latexmk(tex_path, output_dir, compiler)
    return await _compile_manual_multipass(tex_path, output_dir, compiler)


async def _compile_with_latexmk(tex_path: Path, output_dir: Path, compiler: str) -> CompilationResult:
    """Compile using latexmk (handles bibtex + multiple passes automatically)."""
    if compiler == "xelatex":
        cmd = ["latexmk", "-xelatex", "-interaction=nonstopmode", f"-output-directory={output_dir}", str(tex_path)]
    else:
        cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", f"-output-directory={output_dir}", str(tex_path)]

    logger.info("Compiling with latexmk: %s", " ".join(cmd))

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

        pdf_path = output_dir / f"{tex_path.stem}.pdf"
        log_content = stdout.decode(errors="replace") + stderr.decode(errors="replace")

        if pdf_path.exists():
            if process.returncode == 0:
                return CompilationResult(success=True, pdf_path=pdf_path)
            return CompilationResult(
                success=False,
                pdf_path=pdf_path,
                error=f"latexmk exited with code {process.returncode}",
                log=log_content[-5000:],
            )

        if process.returncode != 0:
            error = f"latexmk exited with code {process.returncode}"
        else:
            error = "latexmk finished without producing a PDF"
        return CompilationResult(success=False, error=error, log=log_content[-5000:])
    except FileNotFoundError:
        return CompilationResult(success=False, error="latexmk not found")


async def _compile_manual_multipass(tex_path: Path, output_dir: Path, compiler: str) -> CompilationResult:
    """Manual multi-pass: pdflatex -> bibtex -> pdflatex -> pdflatex."""
    compiler_path = find_latex_compiler(compiler)
    if not compiler_path:
        return CompilationResult(success=False, error=f"Compiler '{compiler}' not found")

    async def run_cmd(cmd: list[str], cwd: str) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
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

    def pdf_build_signature() -> tuple[int, int] | None:
        if not pdf_path.exists():
            return None
        try:
            stat = pdf_path.stat()
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

    def fresh_pdf_was_generated(initial_signature: tuple[int, int] | None) -> bool:
        current_signature = pdf_build_signature()
        if current_signature is None:
            return False
        return initial_signature is None or current_signature != initial_signature

    try:
        # Pass 1: pdflatex
        returncode, log = await run_cmd(base_cmd, cwd)
        record_result("pdflatex pass 1", returncode, log)

        # bibtex
        aux_path = output_dir / f"{tex_path.stem}.aux"
        bibtex = shutil.which("bibtex")
        if not bibtex:
            logger.warning("bibtex not found -- bibliography will not be processed; citations will show as [?]")
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
            await asyncio.to_thread(tex_path.write_text, fix_result.fixed_content, encoding="utf-8")
            logger.info("Applied autofix: %s", fix_result.fixes_applied)
            autofix_initial_pdf_signature = pdf_build_signature()

            combined_log_parts = []
            compile_errors = []
            fatal_errors = []

            returncode, log = await run_cmd(base_cmd, cwd)
            record_result("pdflatex autofix pass 1", returncode, log)
            if bibtex and aux_path.exists():
                returncode, log = await run_cmd([bibtex, str(aux_path)], cwd)
                record_result("bibtex autofix", returncode, log, fatal=True)
            returncode, log = await run_cmd(base_cmd, cwd)
            record_result("pdflatex autofix pass 2", returncode, log)
            returncode, log = await run_cmd(base_cmd, cwd)
            record_result("pdflatex autofix pass 3", returncode, log)
            if fresh_pdf_was_generated(autofix_initial_pdf_signature) and (
                not compile_errors or (returncode == 0 and not fatal_errors)
            ):
                return CompilationResult(success=True, pdf_path=pdf_path)

        error = fatal_errors[0] if fatal_errors else compile_errors[0] if compile_errors else "Compilation failed"
        return CompilationResult(success=False, error=error, log="".join(combined_log_parts)[-5000:])

    except TimeoutError:
        return CompilationResult(success=False, error="Compilation timed out")


# ---- Full pipeline ----


async def build_paper(
    config: PaperConfig,
    output_dir: Path,
    bib_data: BibliographyData | None = None,
    citation_sources: list[CitationSource] | None = None,
    enrich_bibliography: bool = True,
) -> PaperOutput:
    """Orchestrate the full paper build pipeline.

    1. Prepare figures (normalize, size)
    2. Write .bib file
    3. Render .tex from template
    4. Check required TeX resources
    5. Compile to PDF
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir: Path | None = None
    manifest = None
    manifest_path = output_dir / "ARTIFACT-MANIFEST.json"
    bibliography_audit = None
    bibliography_audit_path: Path | None = None
    errors: list[str] = []
    figure_source_pairs: list[tuple[FigureRef, FigureRef]] = []
    figures_prepared_successfully = True
    bib_path: Path | None = None
    bib_entry_source: str | None = "bib_data" if bib_data is not None else None

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
        if bib_data is None:
            bib_data = built_bib
            bib_entry_source = "citation_sources"
        else:
            bib_data = _merge_bibliography_data(bib_data, built_bib)
            bib_entry_source = "bib_data+citation_sources"
        bibliography_audit_path = output_dir / "BIBLIOGRAPHY-AUDIT.json"
        await asyncio.to_thread(write_bibliography_audit, bibliography_audit, bibliography_audit_path)

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
    tex_content = render_paper(config)
    tex_path = output_dir / "main.tex"
    await asyncio.to_thread(tex_path.write_text, tex_content, encoding="utf-8")

    # 3.5. Pre-compilation draft validation
    draft_errors = validate_tex_draft(tex_content)
    blocker_errors = [e for e in draft_errors if e.severity == Severity.blocker]
    major_errors = [e for e in draft_errors if e.severity == Severity.major]
    for err in blocker_errors:
        line_info = f" (line {err.line})" if err.line else ""
        errors.append(f"BLOCKER: {err.message}{line_info}")
    for err in major_errors:
        line_info = f" (line {err.line})" if err.line else ""
        errors.append(f"WARNING: {err.message}{line_info}")
    if blocker_errors:
        logger.warning(
            "Pre-compilation validation found %d blocker(s) -- compilation may fail or produce incorrect output",
            len(blocker_errors),
        )

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
    await asyncio.to_thread(write_artifact_manifest, manifest, manifest_path)

    # 4. Check required TeX resources (blocking subprocess; run in thread to avoid stalling the loop)
    spec = get_journal_spec(config.journal)
    dependencies_available, dependency_errors = await asyncio.to_thread(check_journal_dependencies, spec)
    if not dependencies_available:
        errors.extend(dependency_errors)
        return PaperOutput(
            tex_content=tex_content,
            bib_content=bib_content,
            figures_dir=figures_dir,
            pdf_path=None,
            bibliography_audit_path=bibliography_audit_path,
            bibliography_audit=bibliography_audit,
            manifest_path=manifest_path,
            manifest=manifest,
            success=False,
            errors=errors,
        )

    # 5. Compile
    result = await compile_paper(tex_path, output_dir, compiler=spec.compiler)

    if not result.success and result.error:
        errors.append(result.error)

    manifest = build_artifact_manifest(
        config,
        output_dir,
        tex_path=tex_path,
        bib_path=bib_path,
        bib_entry_source=bib_entry_source,
        bibliography_audit_path=bibliography_audit_path,
        bibliography_audit=bibliography_audit,
        figure_source_pairs=figure_source_pairs,
        pdf_path=result.pdf_path,
    )
    await asyncio.to_thread(write_artifact_manifest, manifest, manifest_path)

    final_success = result.success and figures_prepared_successfully and not errors

    return PaperOutput(
        tex_content=tex_content,
        bib_content=bib_content,
        figures_dir=figures_dir,
        pdf_path=result.pdf_path,
        bibliography_audit_path=bibliography_audit_path,
        bibliography_audit=bibliography_audit,
        manifest_path=manifest_path,
        manifest=manifest,
        success=final_success,
        errors=errors,
    )
