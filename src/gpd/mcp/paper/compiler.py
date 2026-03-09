"""Compiler wrapper: class file checks, multi-pass compilation, full pipeline.

Wraps psi_core.latex.LaTeXCompiler with class file pre-checks (kpsewhich),
latexmk support for multi-pass compilation, and the build_paper orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from gpd.mcp.paper.bibliography import BibliographyData, write_bib_file
from gpd.mcp.paper.figures import prepare_figures
from gpd.mcp.paper.journal_map import get_journal_spec
from gpd.mcp.paper.models import FigureRef, PaperConfig, PaperOutput
from gpd.mcp.paper.template_registry import render_paper

logger = logging.getLogger(__name__)


# ---- Class file availability check ----

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


def check_class_file(document_class: str) -> tuple[bool, str]:
    """Check if a LaTeX class file is available via kpsewhich.

    Returns:
        (available, message) tuple. If kpsewhich is not installed,
        assumes the class file is present.
    """
    try:
        result = subprocess.run(
            ["kpsewhich", f"{document_class}.cls"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        pkg = _get_tlmgr_package(document_class)
        return False, f"{document_class}.cls not found. Install via: tlmgr install {pkg}"
    except FileNotFoundError:
        return True, "kpsewhich not available, assuming class file present"
    except subprocess.TimeoutExpired:
        return True, "kpsewhich timed out, assuming class file present"


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
    """
    output_dir.mkdir(parents=True, exist_ok=True)

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
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

        pdf_path = output_dir / f"{tex_path.stem}.pdf"
        if pdf_path.exists():
            return CompilationResult(success=True, pdf_path=pdf_path)

        log_content = stdout.decode(errors="replace") + stderr.decode(errors="replace")
        return CompilationResult(success=False, error="latexmk failed", log=log_content[-5000:])

    except TimeoutError:
        return CompilationResult(success=False, error="Compilation timed out after 120 seconds")
    except FileNotFoundError:
        return CompilationResult(success=False, error="latexmk not found")


async def _compile_manual_multipass(tex_path: Path, output_dir: Path, compiler: str) -> CompilationResult:
    """Manual multi-pass: pdflatex -> bibtex -> pdflatex -> pdflatex."""
    compiler_path = shutil.which(compiler)
    if not compiler_path:
        return CompilationResult(success=False, error=f"Compiler '{compiler}' not found")

    async def run_cmd(cmd: list[str], cwd: str) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        return process.returncode or 0, stdout.decode(errors="replace") + stderr.decode(errors="replace")

    cwd = str(tex_path.parent)
    base_cmd = [compiler_path, "-interaction=nonstopmode", f"-output-directory={output_dir}", str(tex_path)]

    try:
        # Pass 1: pdflatex
        await run_cmd(base_cmd, cwd)

        # bibtex
        aux_path = output_dir / f"{tex_path.stem}.aux"
        bibtex = shutil.which("bibtex")
        if bibtex and aux_path.exists():
            await run_cmd([bibtex, str(aux_path)], cwd)

        # Pass 2 & 3: pdflatex
        await run_cmd(base_cmd, cwd)
        returncode, log = await run_cmd(base_cmd, cwd)

        pdf_path = output_dir / f"{tex_path.stem}.pdf"
        if pdf_path.exists():
            return CompilationResult(success=True, pdf_path=pdf_path)

        # Try autofix
        from gpd.utils.latex import try_autofix

        tex_content = tex_path.read_text(encoding="utf-8")
        fix_result = try_autofix(tex_content, log)
        if fix_result.was_modified and fix_result.fixed_content:
            tex_path.write_text(fix_result.fixed_content, encoding="utf-8")
            logger.info("Applied autofix: %s", fix_result.fixes_applied)
            await run_cmd(base_cmd, cwd)
            if pdf_path.exists():
                return CompilationResult(success=True, pdf_path=pdf_path)

        return CompilationResult(success=False, error="Compilation failed", log=log[-5000:])

    except TimeoutError:
        return CompilationResult(success=False, error="Compilation timed out")


# ---- Full pipeline ----


async def build_paper(
    config: PaperConfig,
    output_dir: Path,
    bib_data: BibliographyData | None = None,
    figures: list[FigureRef] | None = None,
) -> PaperOutput:
    """Orchestrate the full paper build pipeline.

    1. Prepare figures (normalize, size)
    2. Write .bib file
    3. Render .tex from template
    4. Check class file availability
    5. Compile to PDF
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    errors: list[str] = []

    # 1. Prepare figures
    if figures:
        figures_dir.mkdir(exist_ok=True)
        prepared = prepare_figures(figures, figures_dir, config.journal)
        config = config.model_copy(update={"figures": prepared})

    # 2. Write .bib file
    bib_content = ""
    if bib_data:
        bib_path = output_dir / f"{config.bib_file}.bib"
        write_bib_file(bib_data, bib_path)
        bib_content = bib_path.read_text(encoding="utf-8")

    # 3. Render .tex
    tex_content = render_paper(config)
    tex_path = output_dir / "paper.tex"
    tex_path.write_text(tex_content, encoding="utf-8")

    # 4. Check class file
    spec = get_journal_spec(config.journal)
    available, msg = check_class_file(spec.document_class)
    if not available:
        errors.append(msg)
        return PaperOutput(
            tex_content=tex_content,
            bib_content=bib_content,
            figures_dir=figures_dir if figures else None,
            pdf_path=None,
            success=False,
            errors=errors,
        )

    # 5. Compile
    result = await compile_paper(tex_path, output_dir, compiler=spec.compiler)

    if not result.success and result.error:
        errors.append(result.error)

    return PaperOutput(
        tex_content=tex_content,
        bib_content=bib_content,
        figures_dir=figures_dir if figures else None,
        pdf_path=result.pdf_path,
        success=result.success,
        errors=errors,
    )
