"""Regression tests for minimal package/framework reuse guidance."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLING_REF = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "tooling" / "tool-integration.md"
RESEARCHER_SHARED = (
    REPO_ROOT / "src" / "gpd" / "specs" / "references" / "research" / "researcher-shared.md"
)
PHASE_RESEARCHER = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-phase-researcher.md"
PLANNER = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-planner.md"
EXECUTOR = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-executor.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_tooling_reference_surfaces_minimal_package_selection_policy() -> None:
    tooling = _read(TOOLING_REF)

    assert "## Package / Framework Selection" in tooling
    assert "Prefer established packages and frameworks when they fit the scientific requirements" in tooling
    assert "surface it via `tool_requirements` or `researcher_setup`" in tooling


def test_research_prompts_require_reuse_decision_or_bespoke_justification() -> None:
    researcher_shared = _read(RESEARCHER_SHARED)
    phase_researcher = _read(PHASE_RESEARCHER)

    assert "search for established packages/frameworks before recommending bespoke code" in researcher_shared
    assert "### Package / Framework Reuse Decision" in phase_researcher
    assert "If bespoke code is still recommended" in phase_researcher
    assert "Package/framework reuse decision documented, or bespoke-code justification recorded" in phase_researcher


def test_planner_and_executor_consume_research_package_guidance_without_new_schema() -> None:
    planner = _read(PLANNER)
    executor = _read(EXECUTOR)

    assert "plan around using or lightly adapting it instead of defaulting to bespoke infrastructure" in planner
    assert "surface it in `tool_requirements` or `researcher_setup`" in planner
    assert "Prefer established packages/frameworks identified in RESEARCH.md or the plan" in executor
