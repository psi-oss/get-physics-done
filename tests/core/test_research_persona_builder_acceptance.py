"""Acceptance smoke tests for the Phase 3 Research Persona builder."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_REPORT = REPO_ROOT / "tmp" / "phase-03-persona-builder-report.md"

PHASE3_SOURCE_FILES = (
    REPO_ROOT / "src" / "gpd" / "commands" / "build-persona.md",
    REPO_ROOT / "src" / "gpd" / "agents" / "gpd-persona-builder.md",
    REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona.md",
    REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona" / "persona-intake.md",
    REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona" / "persona-synthesis.md",
    REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona" / "approval-and-apply.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _missing_phase3_sources() -> list[str]:
    return [path.relative_to(REPO_ROOT).as_posix() for path in PHASE3_SOURCE_FILES if not path.exists()]


def _combined_phase3_source_text() -> str:
    missing = _missing_phase3_sources()
    if missing:
        pytest.skip("Phase 3 source files are not present yet; existence test reports the missing paths")
    return "\n\n".join(_read(path) for path in PHASE3_SOURCE_FILES)


def test_phase_3_report_documents_builder_contract() -> None:
    assert PHASE_REPORT.exists(), "Phase 3 report must exist before acceptance can run"

    report = _read(PHASE_REPORT)

    for required in (
        "gpd:build-persona",
        "gpd-persona-builder",
        "src/gpd/specs/workflows/build-persona.md",
        "gpd research-persona validate",
        "gpd research-persona apply-patch",
        "patch-only",
        "never_prompt",
        "private_local",
        "project_private",
        "safe_to_share",
        "Researcher Doppelganger",
        "Expertise-Aware Explanations",
        "Scientific Taste Model",
        "source ingestion",
    ):
        assert required in report


def test_phase_3_expected_source_files_exist() -> None:
    missing = _missing_phase3_sources()

    assert not missing, "Phase 3 persona-builder source files are missing:\n" + "\n".join(missing)


def test_phase_3_surfaces_route_mutation_through_cli_approval_flow() -> None:
    combined = _combined_phase3_source_text()

    for required in (
        "gpd research-persona validate",
        "gpd research-persona diff",
        "gpd research-persona apply-patch",
    ):
        assert required in combined

    forbidden_fragments = (
        "write_text",
        "atomic_write",
        "save_research_persona",
        "append_research_persona_history",
        "append_research_persona_tombstone",
    )
    lowered = combined.lower()
    for forbidden in forbidden_fragments:
        assert forbidden.lower() not in lowered


def test_phase_3_surfaces_include_privacy_and_ambitious_feature_hooks() -> None:
    combined = _combined_phase3_source_text()

    for required in (
        "never_prompt",
        "private_local",
        "project_private",
        "safe_to_share",
        "doppelganger",
        "explainer",
        "taste",
    ):
        assert required in combined

    assert "prompt" in combined.lower()
    assert "privacy" in combined.lower()
