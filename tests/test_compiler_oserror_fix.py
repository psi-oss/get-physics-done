"""Test that build_paper catches OSError from figure preparation.

Regression test for a bug where the exception handler around
``_prepare_figures_with_sources`` only caught ``(ValueError, RuntimeError)``
but not ``OSError``, causing unhandled crashes on permission errors or
missing-file OS-level failures during figure processing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.mcp.paper.compiler import build_paper
from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section


def _minimal_config(tmp_path: Path) -> PaperConfig:
    """Return a minimal PaperConfig with one figure configured."""
    fig_path = tmp_path / "fig1.png"
    fig_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    return PaperConfig(
        title="Test Paper",
        authors=[Author(name="A. Tester")],
        abstract="Abstract text.",
        sections=[Section(title="Introduction", content="Hello world.")],
        figures=[FigureRef(path=fig_path, caption="A figure", label="fig:test")],
        journal="prl",
    )


@pytest.mark.asyncio
async def test_build_paper_catches_oserror_from_figure_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_paper must not propagate OSError from _prepare_figures_with_sources.

    Before the fix the except clause only caught (ValueError, RuntimeError),
    so an OSError (e.g. permission denied) would bubble up as an unhandled
    exception instead of being recorded in the errors list.
    """
    config = _minimal_config(tmp_path)
    output_dir = tmp_path / "output"

    def raise_oserror(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(
        "gpd.mcp.paper.compiler._prepare_figures_with_sources",
        raise_oserror,
    )

    # Stub out the heavy parts of the pipeline that follow figure preparation
    # so the test does not need a real TeX toolchain.
    monkeypatch.setattr(
        "gpd.mcp.paper.compiler.check_journal_dependencies",
        lambda spec: (False, ["TeX not available (stubbed)"]),
    )

    # This must NOT raise OSError.
    result = await build_paper(config, output_dir)

    assert result.success is False
    # The caught OSError should appear in the errors list.
    fig_errors = [e for e in result.errors if "Permission denied" in e]
    assert fig_errors, (
        f"Expected an error mentioning 'Permission denied' in result.errors, "
        f"got: {result.errors}"
    )
