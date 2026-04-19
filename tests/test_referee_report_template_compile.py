"""Compile smoke test for the shipped referee report LaTeX template."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from gpd.mcp.paper.compiler import find_latex_compiler

REPO_ROOT = Path(__file__).resolve().parents[1]
REFEREE_TEMPLATE = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "paper" / "referee-report.tex"


def _combined_compile_log(build_dir: Path, stem: str, console_output: str) -> str:
    log_path = build_dir / f"{stem}.log"
    if not log_path.exists():
        return console_output

    file_log = log_path.read_text(encoding="utf-8", errors="replace")
    if not console_output:
        return file_log
    return f"{file_log}\n{console_output}"


def _log_excerpt(log: str, *, max_chars: int = 4000) -> str:
    if len(log) <= max_chars:
        return log
    return log[-max_chars:]


def test_shipped_referee_report_template_compiles_when_tex_is_available(tmp_path: Path) -> None:
    compiler_path = find_latex_compiler("pdflatex")
    if compiler_path is None:
        pytest.skip("pdflatex not available; skipping referee template compile smoke test")

    assert REFEREE_TEMPLATE.exists(), f"Missing shipped template at {REFEREE_TEMPLATE}"

    tex_path = tmp_path / REFEREE_TEMPLATE.name
    shutil.copy2(REFEREE_TEMPLATE, tex_path)

    result = subprocess.run(
        [
            compiler_path,
            "-interaction=nonstopmode",
            f"-output-directory={tmp_path}",
            str(tex_path),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
        timeout=120,
    )

    compile_log = _combined_compile_log(tmp_path, tex_path.stem, result.stdout + result.stderr)
    pdf_path = tmp_path / f"{tex_path.stem}.pdf"
    log_excerpt = _log_excerpt(compile_log)

    assert result.returncode == 0, (
        f"pdflatex exited with code {result.returncode} while compiling {REFEREE_TEMPLATE.name}.\n{log_excerpt}"
    )
    assert pdf_path.exists(), f"Expected compiled PDF at {pdf_path}.\n{log_excerpt}"
    assert pdf_path.stat().st_size > 0, f"Compiled PDF at {pdf_path} is empty.\n{log_excerpt}"
    assert "Package array Error" not in compile_log, (
        "Known longtable/tabularx regression is still present in referee-report.tex.\n"
        f"{log_excerpt}"
    )
