from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
TEMPLATES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "paper"


def test_compare_branches_uses_in_memory_branch_summary_extraction() -> None:
    workflow_text = (WORKFLOWS_DIR / "compare-branches.md").read_text(encoding="utf-8")

    assert "Prefer parsing the `git show` output directly in memory." in workflow_text
    assert "do not write it to `GPD/tmp/` just to run a path-based extractor." in workflow_text
    assert "Keep branch-summary extraction in memory/stdout only" in workflow_text
    assert "do not use `GPD/tmp/`, `/tmp`, or another temp root for this step." in workflow_text


def test_parameter_sweep_uses_gpd_owned_sweep_roots_for_phase_and_current_workspace_modes() -> None:
    command_text = (COMMANDS_DIR / "parameter-sweep.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "parameter-sweep.md").read_text(encoding="utf-8")

    assert "default_output_subtree: GPD/sweeps" in command_text
    assert 'SWEEP_ROOT="GPD/sweeps/${SWEEP_PHASE_KEY}/${SWEEP_SLUG}"' in workflow_text
    assert 'SWEEP_ROOT="GPD/sweeps/${SWEEP_SLUG}"' in workflow_text
    assert 'SWEEP_RESULTS_DIR="${SWEEP_ROOT}/results"' in workflow_text
    assert "${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json" in workflow_text
    assert "${SWEEP_DOC_DIR}/sweep-{PADDED_INDEX}-SUMMARY.md" in workflow_text
    assert "Do not invent `GPD/phases/XX-sweep`." in workflow_text
    assert "Do not write durable sweep datasets to `artifacts/`." in workflow_text
    assert "artifacts/phases/${SWEEP_PHASE_KEY}/sweeps/${SWEEP_SLUG}" not in workflow_text


def test_compare_experiment_uses_workspace_roots_for_inputs_and_gpd_roots_for_outputs() -> None:
    command_text = (REPO_ROOT / "src" / "gpd" / "commands" / "compare-experiment.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")

    assert "find artifacts/ results/ data/ figures/ simulations/ paper/ -maxdepth 4" in command_text
    assert "Treat `GPD/**` as internal provenance only for source discovery." in command_text
    assert "keep the generated GPD-authored comparison package under the current workspace `GPD/comparisons/` subtree." in command_text
    assert "ls GPD/phases/*/results/" not in command_text
    assert 'COMPARISON_OUTPUT_PATH="GPD/comparisons/[slug]-COMPARISON.md"' in workflow_text
    assert 'COMPARISON_SUPPORT_DIR="GPD/comparisons/{slug}/"' in workflow_text
    assert "Write final comparison figures, tables, and helper scripts under `${COMPARISON_SUPPORT_DIR}`." in workflow_text
    assert "Do not run an unconditional standalone docs commit for this workflow." in workflow_text
    assert "artifacts/comparisons/{slug}/" not in workflow_text
    assert "Do not place final comparison figures, tables, or scripts under `GPD/`." not in workflow_text


def test_compare_results_creates_workspace_gpd_comparison_root() -> None:
    command_text = (REPO_ROOT / "src" / "gpd" / "commands" / "compare-results.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "compare-results.md").read_text(encoding="utf-8")

    assert "default_output_subtree: GPD/comparisons" in command_text
    assert "allow_interactive_without_subject: true" in command_text
    assert 'COMPARISON_OUTPUT_PATH="GPD/comparisons/[slug]-COMPARISON.md"' in workflow_text
    assert "mkdir -p GPD/comparisons" in workflow_text
    assert "same current-workspace `GPD/comparisons/` subtree" in workflow_text


def test_error_propagation_keeps_a_single_phase_report_contract() -> None:
    command_text = (COMMANDS_DIR / "error-propagation.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "error-propagation.md").read_text(encoding="utf-8")

    assert "workflow-owned implementation" in command_text
    assert "@{GPD_INSTALL_DIR}/workflows/error-propagation.md" in command_text
    assert "Phase target: `GPD/phases/XX-name/ERROR-BUDGET.md`" not in command_text
    assert "Project-wide: `GPD/analysis/error-budget-{target}.md`" not in command_text
    assert 'Save to: `${target_phase_dir}/ERROR-BUDGET.md`.' in workflow_text
    assert "Do not create a second per-target `GPD/analysis/error-budget-{target}.md` report for this workflow." in workflow_text


def test_execute_phase_figure_tracker_scans_durable_figure_roots() -> None:
    workflow_text = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert 'PHASE_ARTIFACT_DIR="artifacts/phases/${phase_number}-${phase_slug}"' in workflow_text
    assert 'find "${PHASE_ARTIFACT_DIR}" figures/ paper/figures/ -maxdepth 3' in workflow_text
    assert "Generated figures and plots should live in stable workspace roots" in workflow_text


def test_write_paper_uses_durable_figure_and_literature_roots() -> None:
    workflow_text = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert 'find artifacts/phases figures "${PAPER_DIR}/figures" -maxdepth 3' in workflow_text
    assert "ls GPD/literature/*-REVIEW.md 2>/dev/null" in workflow_text
    assert "GPD/phases/*/figures/" not in workflow_text
    assert "GPD/phases/*/LITERATURE-REVIEW.md" not in workflow_text


def test_publication_manuscript_preflight_keeps_intake_out_of_manuscript_discovery() -> None:
    template_text = (TEMPLATES_DIR / "publication-manuscript-root-preflight.md").read_text(encoding="utf-8")

    assert "GPD/publication/{subject_slug}/intake/" in template_text
    assert "GPD/publication/{subject_slug}/manuscript/" in template_text
    assert "do not let `intake/` participate in manuscript-root discovery" in template_text
