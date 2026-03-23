"""Tests for PDF output filename derivation and build_paper integration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from gpd.mcp.paper.models import Author, PaperConfig, Section, derive_output_filename


def _minimal_config(**overrides) -> PaperConfig:
    defaults = {
        "title": "Test Paper",
        "authors": [Author(name="Alice")],
        "abstract": "An abstract.",
        "sections": [Section(heading="Intro", content="Content.")],
    }
    defaults.update(overrides)
    return PaperConfig(**defaults)


class TestDeriveOutputFilename:
    def test_explicit_output_filename_used_verbatim(self) -> None:
        config = _minimal_config(output_filename="my-custom-name")
        assert derive_output_filename(config) == "my-custom-name"

    def test_title_based_slug(self) -> None:
        config = _minimal_config(title="Quantum Entanglement in Black Holes")
        assert derive_output_filename(config) == "quantum-entanglement-in-black-holes"

    def test_empty_title_falls_back_to_main(self) -> None:
        config = _minimal_config(title="")
        assert derive_output_filename(config) == "main"

    def test_whitespace_only_title_falls_back_to_main(self) -> None:
        config = _minimal_config(title="   ")
        assert derive_output_filename(config) == "main"

    def test_special_characters_stripped(self) -> None:
        config = _minimal_config(title="Hello! World? #2024")
        assert derive_output_filename(config) == "hello-world-2024"

    def test_consecutive_hyphens_collapsed(self) -> None:
        config = _minimal_config(title="A -- B --- C")
        assert derive_output_filename(config) == "a-b-c"

    def test_max_length_truncation(self) -> None:
        long_title = "a " * 100
        config = _minimal_config(title=long_title)
        result = derive_output_filename(config)
        assert len(result) <= 60

    def test_unicode_characters_stripped(self) -> None:
        config = _minimal_config(title="Schrodinger Equation")
        assert derive_output_filename(config) == "schrodinger-equation"

    def test_leading_trailing_hyphens_stripped(self) -> None:
        config = _minimal_config(title="---Hello World---")
        assert derive_output_filename(config) == "hello-world"

    def test_only_special_chars_falls_back_to_main(self) -> None:
        config = _minimal_config(title="!@#$%^&*()")
        assert derive_output_filename(config) == "main"

    def test_output_filename_takes_precedence_over_title(self) -> None:
        config = _minimal_config(title="Some Title", output_filename="override")
        assert derive_output_filename(config) == "override"

    def test_none_output_filename_uses_title(self) -> None:
        config = _minimal_config(title="Test Title", output_filename=None)
        assert derive_output_filename(config) == "test-title"

    def test_default_output_filename_is_none(self) -> None:
        config = _minimal_config()
        assert config.output_filename is None


def _journal_spec():
    from gpd.mcp.paper.models import JournalSpec

    return JournalSpec(
        key="prl",
        document_class="revtex4-2",
        class_options=[],
        bib_style="apsrev4-2",
        column_width_cm=8.6,
        double_width_cm=17.8,
        max_height_cm=24.0,
        dpi=300,
        preferred_formats=["pdf"],
        texlive_package="revtex",
    )


class TestBuildPaperNaming:
    def test_build_paper_uses_derived_filename_for_tex(self, tmp_path: Path) -> None:
        config = _minimal_config(title="My Great Paper")
        with (
            patch("gpd.mcp.paper.compiler.render_paper", return_value="\\documentclass{article}"),
            patch("gpd.mcp.paper.compiler.get_journal_spec", return_value=_journal_spec()),
            patch("gpd.mcp.paper.compiler.check_journal_dependencies", return_value=(False, ["missing"])),
            patch("gpd.mcp.paper.compiler.build_artifact_manifest", return_value=None),
            patch("gpd.mcp.paper.compiler.write_artifact_manifest"),
        ):
            from gpd.mcp.paper.compiler import build_paper

            asyncio.run(build_paper(config, tmp_path))
        assert (tmp_path / "my-great-paper.tex").exists()

    def test_build_paper_uses_explicit_output_filename(self, tmp_path: Path) -> None:
        config = _minimal_config(title="Ignored Title", output_filename="custom-output")
        with (
            patch("gpd.mcp.paper.compiler.render_paper", return_value="\\documentclass{article}"),
            patch("gpd.mcp.paper.compiler.get_journal_spec", return_value=_journal_spec()),
            patch("gpd.mcp.paper.compiler.check_journal_dependencies", return_value=(False, ["missing"])),
            patch("gpd.mcp.paper.compiler.build_artifact_manifest", return_value=None),
            patch("gpd.mcp.paper.compiler.write_artifact_manifest"),
        ):
            from gpd.mcp.paper.compiler import build_paper

            asyncio.run(build_paper(config, tmp_path))
        assert (tmp_path / "custom-output.tex").exists()

    def test_build_paper_empty_title_uses_main(self, tmp_path: Path) -> None:
        config = _minimal_config(title="")
        with (
            patch("gpd.mcp.paper.compiler.render_paper", return_value="\\documentclass{article}"),
            patch("gpd.mcp.paper.compiler.get_journal_spec", return_value=_journal_spec()),
            patch("gpd.mcp.paper.compiler.check_journal_dependencies", return_value=(False, ["missing"])),
            patch("gpd.mcp.paper.compiler.build_artifact_manifest", return_value=None),
            patch("gpd.mcp.paper.compiler.write_artifact_manifest"),
        ):
            from gpd.mcp.paper.compiler import build_paper

            asyncio.run(build_paper(config, tmp_path))
        assert (tmp_path / "main.tex").exists()
