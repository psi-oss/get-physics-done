"""Tests for PydanticAI paper generator agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gpd.mcp.paper.generator import (
    FigureCaption,
    ReproducibilityInfo,
    SectionContent,
    SectionPlan,
    ToolUsageRecord,
    build_reproducibility_appendix,
    generate_paper,
)
from gpd.mcp.paper.models import Author, FigureRef, Section

# ---- Reproducibility appendix tests (no mocking needed) ----


class TestReproducibilityAppendix:
    def test_reproducibility_appendix_basic(self):
        info = ReproducibilityInfo(
            tools_used=[ToolUsageRecord(name="OpenFOAM", version="11", description="CFD solver")],
            session_id="test-123",
            compute_platform="Modal",
            total_compute_time="2.5 hours",
        )
        appendix = build_reproducibility_appendix(info)
        assert isinstance(appendix, Section)
        assert "OpenFOAM" in appendix.content
        assert "test-123" in appendix.content
        assert "Modal" in appendix.content
        assert "2.5 hours" in appendix.content

    def test_reproducibility_appendix_multiple_tools(self):
        info = ReproducibilityInfo(
            tools_used=[
                ToolUsageRecord(name="OpenFOAM"),
                ToolUsageRecord(name="LAMMPS"),
                ToolUsageRecord(name="VASP"),
            ],
        )
        appendix = build_reproducibility_appendix(info)
        assert "OpenFOAM" in appendix.content
        assert "LAMMPS" in appendix.content
        assert "VASP" in appendix.content

    def test_reproducibility_appendix_with_session_id(self):
        info = ReproducibilityInfo(
            tools_used=[],
            session_id="abc-def-123",
        )
        appendix = build_reproducibility_appendix(info)
        assert r"\texttt{abc-def-123}" in appendix.content

    def test_reproducibility_appendix_empty_tools(self):
        info = ReproducibilityInfo(tools_used=[])
        appendix = build_reproducibility_appendix(info)
        assert isinstance(appendix, Section)
        assert appendix.title == "Reproducibility"


# ---- Agent output model tests ----


class TestOutputModels:
    def test_section_plan_model(self):
        plan = SectionPlan(
            sections=[
                {"title": "Introduction", "key_points": ["point1"]},
                {"title": "Methods", "key_points": ["point2"]},
            ]
        )
        assert len(plan.sections) == 2

    def test_section_content_model(self):
        content = SectionContent(content=r"The Hamiltonian is $H = \sum_i p_i^2/2m$.")
        assert "Hamiltonian" in content.content

    def test_figure_caption_model(self):
        caption = FigureCaption(caption="Velocity field at $t=10$~s.")
        assert "Velocity" in caption.caption


# ---- generate_paper integration tests (mocked LLM) ----


def _make_mock_run(output):
    """Create an AsyncMock that returns a result with .output attribute."""
    mock_result = MagicMock()
    mock_result.output = output
    mock_run = AsyncMock(return_value=mock_result)
    return mock_run


def _make_mock_agent(run_mock):
    """Create a mock agent object with a .run method."""
    agent = MagicMock()
    agent.run = run_mock
    return agent


class TestGeneratePaper:
    @pytest.mark.asyncio
    async def test_generate_paper_mocked(self, monkeypatch):
        import gpd.mcp.paper.generator as gen_mod

        # Mock section planner
        plan = SectionPlan(
            sections=[
                {"title": "Introduction", "key_points": ["Background"]},
                {"title": "Results", "key_points": ["Findings"]},
                {"title": "Conclusion", "key_points": ["Summary"]},
            ]
        )
        monkeypatch.setattr(gen_mod, "_get_section_planner", lambda: _make_mock_agent(_make_mock_run(plan)))
        monkeypatch.setattr(
            gen_mod,
            "_get_section_writer",
            lambda: _make_mock_agent(_make_mock_run(SectionContent(content="Some LaTeX content."))),
        )
        monkeypatch.setattr(
            gen_mod,
            "_get_caption_writer",
            lambda: _make_mock_agent(_make_mock_run(FigureCaption(caption="A nice figure caption."))),
        )

        config = await generate_paper(
            research_summary="We studied turbulence.",
            title="Turbulence Study",
            authors=[Author(name="Test Author")],
            abstract="We studied turbulence.",
            figures=[FigureRef(path=Path("fig.png"), caption="hint", label="fig1")],
            citations=[],
            journal="prl",
        )
        assert config.title == "Turbulence Study"
        assert len(config.sections) == 3
        assert len(config.figures) == 1
        assert config.figures[0].caption == "A nice figure caption."
        assert config.journal == "prl"

    @pytest.mark.asyncio
    async def test_generate_paper_with_appendix(self, monkeypatch):
        import gpd.mcp.paper.generator as gen_mod

        plan = SectionPlan(sections=[{"title": "Intro", "key_points": ["x"]}])
        monkeypatch.setattr(gen_mod, "_get_section_planner", lambda: _make_mock_agent(_make_mock_run(plan)))
        monkeypatch.setattr(
            gen_mod,
            "_get_section_writer",
            lambda: _make_mock_agent(_make_mock_run(SectionContent(content="Content."))),
        )

        repro = ReproducibilityInfo(
            tools_used=[ToolUsageRecord(name="OpenFOAM", version="11")],
            session_id="s-123",
        )
        config = await generate_paper(
            research_summary="Test.",
            title="Test",
            authors=[Author(name="A")],
            abstract="Abstract.",
            figures=[],
            citations=[],
            reproducibility=repro,
        )
        assert len(config.appendix_sections) == 1
        assert "OpenFOAM" in config.appendix_sections[0].content

    @pytest.mark.asyncio
    async def test_generate_paper_cleans_fences(self, monkeypatch):
        import gpd.mcp.paper.generator as gen_mod

        # Reset cached latex utils so local fallback (with fence stripping) is used
        gen_mod._sanitize_latex = None
        gen_mod._clean_latex_fences = None

        plan = SectionPlan(sections=[{"title": "Intro", "key_points": ["x"]}])
        monkeypatch.setattr(gen_mod, "_get_section_planner", lambda: _make_mock_agent(_make_mock_run(plan)))

        # Return content wrapped in ```latex fences
        fenced_content = "```latex\nSome content here.\n```"
        monkeypatch.setattr(
            gen_mod,
            "_get_section_writer",
            lambda: _make_mock_agent(_make_mock_run(SectionContent(content=fenced_content))),
        )

        config = await generate_paper(
            research_summary="Test.",
            title="Test",
            authors=[Author(name="A")],
            abstract="Abstract.",
            figures=[],
            citations=[],
        )
        # The fences should be stripped
        assert "```" not in config.sections[0].content
        assert "Some content here." in config.sections[0].content
