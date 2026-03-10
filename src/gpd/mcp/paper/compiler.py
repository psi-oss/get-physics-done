"""Compiler wrapper: TeX dependency checks, multi-pass compilation, full pipeline.

Wraps the LaTeX compiler with TeX resource pre-checks (kpsewhich),
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
from gpd.mcp.paper.models import JournalSpec, PaperConfig, PaperOutput
from gpd.mcp.paper.template_registry import render_paper

logger = logging.getLogger(__name__)


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
        if process.returncode == 0 and pdf_path.exists():
            return CompilationResult(success=True, pdf_path=pdf_path)

        log_content = stdout.decode(errors="replace") + stderr.decode(errors="replace")
        if process.returncode != 0:
            error = f"latexmk exited with code {process.returncode}"
        else:
            error = "latexmk finished without producing a PDF"
        return CompilationResult(success=False, error=error, log=log_content[-5000:])

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
    combined_log_parts: list[str] = []
    compile_errors: list[str] = []

    def record_result(step: str, returncode: int, log: str) -> None:
        combined_log_parts.append(log)
        if returncode != 0:
            compile_errors.append(f"{step} exited with code {returncode}")

    try:
        # Pass 1: pdflatex
        returncode, log = await run_cmd(base_cmd, cwd)
        record_result("pdflatex pass 1", returncode, log)

        # bibtex
        aux_path = output_dir / f"{tex_path.stem}.aux"
        bibtex = shutil.which("bibtex")
        if bibtex and aux_path.exists():
            returncode, log = await run_cmd([bibtex, str(aux_path)], cwd)
            record_result("bibtex", returncode, log)

        # Pass 2 & 3: pdflatex
        returncode, log = await run_cmd(base_cmd, cwd)
        record_result("pdflatex pass 2", returncode, log)
        returncode, log = await run_cmd(base_cmd, cwd)
        record_result("pdflatex pass 3", returncode, log)

        pdf_path = output_dir / f"{tex_path.stem}.pdf"
        if not compile_errors and pdf_path.exists():
            return CompilationResult(success=True, pdf_path=pdf_path)

        # Try autofix
        from gpd.utils.latex import try_autofix

        combined_log = "".join(combined_log_parts)
        tex_content = await asyncio.to_thread(tex_path.read_text, encoding="utf-8")
        fix_result = try_autofix(tex_content, combined_log)
        if fix_result.was_modified and fix_result.fixed_content:
            await asyncio.to_thread(tex_path.write_text, fix_result.fixed_content, encoding="utf-8")
            logger.info("Applied autofix: %s", fix_result.fixes_applied)

            combined_log_parts = []
            compile_errors = []

            returncode, log = await run_cmd(base_cmd, cwd)
            record_result("pdflatex autofix pass 1", returncode, log)
            if bibtex and aux_path.exists():
                returncode, log = await run_cmd([bibtex, str(aux_path)], cwd)
                record_result("bibtex autofix", returncode, log)
            returncode, log = await run_cmd(base_cmd, cwd)
            record_result("pdflatex autofix pass 2", returncode, log)
            returncode, log = await run_cmd(base_cmd, cwd)
            record_result("pdflatex autofix pass 3", returncode, log)
            if not compile_errors and pdf_path.exists():
                return CompilationResult(success=True, pdf_path=pdf_path)

        error = compile_errors[0] if compile_errors else "Compilation failed"
        return CompilationResult(success=False, error=error, log=combined_log[-5000:])

    except TimeoutError:
        return CompilationResult(success=False, error="Compilation timed out")


# ---- Full pipeline ----


async def build_paper(
    config: PaperConfig,
    output_dir: Path,
    bib_data: BibliographyData | None = None,
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
    errors: list[str] = []

    # 1. Prepare figures
    if config.figures:
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(exist_ok=True)
        prepared = prepare_figures(config.figures, figures_dir, config.journal)
        config = config.model_copy(update={"figures": prepared})

    # 2. Write .bib file
    bib_content = ""
    if bib_data:
        bib_path = output_dir / f"{config.bib_file}.bib"
        await asyncio.to_thread(write_bib_file, bib_data, bib_path)
        bib_content = await asyncio.to_thread(bib_path.read_text, encoding="utf-8")

    # 3. Render .tex
    tex_content = render_paper(config)
    tex_path = output_dir / "paper.tex"
    await asyncio.to_thread(tex_path.write_text, tex_content, encoding="utf-8")

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
        figures_dir=figures_dir,
        pdf_path=result.pdf_path,
        success=result.success,
        errors=errors,
    )
