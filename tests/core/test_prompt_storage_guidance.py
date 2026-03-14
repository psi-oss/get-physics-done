from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_compare_branches_uses_in_memory_branch_summary_extraction() -> None:
    workflow_text = (WORKFLOWS_DIR / "compare-branches.md").read_text(encoding="utf-8")

    assert "Prefer parsing the `git show` output directly in memory." in workflow_text
    assert "do not write it to `.gpd/tmp/` just to run a path-based extractor." in workflow_text
    assert "Keep branch-summary extraction in memory/stdout only" in workflow_text
    assert "do not use `.gpd/tmp/`, `/tmp`, or another temp root for this step." in workflow_text


def test_parameter_sweep_keeps_internal_docs_in_gpd_and_durable_data_in_artifacts() -> None:
    workflow_text = (WORKFLOWS_DIR / "parameter-sweep.md").read_text(encoding="utf-8")

    assert 'SWEEP_ARTIFACT_DIR="artifacts/phases/${SWEEP_PHASE_KEY}/sweeps/${SWEEP_SLUG}"' in workflow_text
    assert "Keep plans and SUMMARY files in `${SWEEP_PHASE_DIR}`" in workflow_text
    assert "Do not put point-result JSON under `.gpd/phases/**`." in workflow_text
    assert "${SWEEP_ARTIFACT_DIR}/results/point-{PADDED_INDEX}.json" in workflow_text
    assert "${SWEEP_PHASE_DIR}/sweep-{PADDED_INDEX}-SUMMARY.md" in workflow_text
    assert "${SWEEP_DIR}/results/point-{PADDED_INDEX}.json" not in workflow_text


def test_compare_experiment_uses_durable_workspace_roots_for_inputs_and_outputs() -> None:
    command_text = (REPO_ROOT / "src" / "gpd" / "commands" / "compare-experiment.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")

    assert "find artifacts/ results/ data/ figures/ simulations/ paper/ -maxdepth 4" in command_text
    assert "Treat `.gpd/**` as internal provenance only." in command_text
    assert "ls .gpd/phases/*/results/" not in command_text
    assert "artifacts/comparisons/{slug}/" in workflow_text
    assert "Do not place final comparison figures, tables, or scripts under `.gpd/`." in workflow_text


def test_execute_phase_figure_tracker_scans_durable_figure_roots() -> None:
    workflow_text = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert 'PHASE_ARTIFACT_DIR="artifacts/phases/${phase_number}-${phase_slug}"' in workflow_text
    assert 'find "${PHASE_ARTIFACT_DIR}" figures/ paper/figures/ -maxdepth 3' in workflow_text
    assert "Generated figures and plots should live in stable workspace roots" in workflow_text


def test_write_paper_uses_durable_figure_and_literature_roots() -> None:
    workflow_text = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert "find artifacts/phases figures paper/figures -maxdepth 3" in workflow_text
    assert "ls .gpd/literature/*-REVIEW.md 2>/dev/null" in workflow_text
    assert ".gpd/phases/*/figures/" not in workflow_text
    assert ".gpd/phases/*/LITERATURE-REVIEW.md" not in workflow_text
