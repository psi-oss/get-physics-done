from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_comparison_workflows_call_comparison_contract_validator() -> None:
    compare_experiment = _read(WORKFLOWS_DIR / "compare-experiment.md")
    compare_results = _read(WORKFLOWS_DIR / "compare-results.md")

    expected = 'gpd validate comparison-contract "${COMPARISON_OUTPUT_PATH}"'
    assert expected in compare_experiment
    assert expected in compare_results
    assert "treat the comparison artifact as incomplete" in compare_experiment
    assert "treat the comparison artifact as incomplete" in compare_results


def test_verifier_artifact_levels_are_four_level_consistent() -> None:
    verifier = _read(AGENTS_DIR / "gpd-verifier.md")

    assert "## Step 4: Verify Artifacts (Four Levels)" in verifier
    assert "### Level 1: Existence" in verifier
    assert "### Level 2: Substantive Content" in verifier
    assert "### Level 3: Content Validation" in verifier
    assert "### Level 4: Integration" in verifier
    assert "all artifacts pass levels 1-4" in verifier


def test_verify_phase_keeps_independent_confirmed_tally_out_of_machine_fields() -> None:
    verify_phase = _read(WORKFLOWS_DIR / "verify-phase.md")

    assert "Keep any independent-confirmed tally in the report body or markdown return narrative only" in verify_phase
    assert "do not add it to verification frontmatter or `gpd_return`" in verify_phase
    assert "independently confirmed count (K/M)" not in verify_phase
