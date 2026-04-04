from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _workflow_text(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("workflow_name", "surface_marker", "expected_token"),
    [
        ("plan-phase.md", "Parse JSON for:", "project_contract_gate"),
        ("execute-phase.md", "Parse JSON for:", "project_contract_gate"),
        ("execute-plan.md", "Extract from init JSON:", "project_contract_gate"),
        ("quick.md", "Parse JSON for:", "project_contract_gate"),
        ("literature-review.md", "Parse JSON for:", "project_contract_gate"),
        ("compare-experiment.md", "Parse JSON for:", "project_contract_gate"),
        ("compare-results.md", "Parse JSON for:", "project_contract_gate"),
        ("new-project.md", "Parse JSON for:", "project_contract_gate"),
        ("new-milestone.md", "Parse JSON for:", "project_contract_gate"),
        ("map-research.md", "Extract from init JSON:", "project_contract_gate"),
        ("progress.md", "Extract from init JSON:", "project_contract_gate"),
        ("audit-milestone.md", "Extract from init JSON:", "project_contract_gate"),
        ("resume-work.md", "- **Availability and contract authority:**", "project_contract_gate"),
        ("write-paper.md", "Parse JSON for:", "project_contract_gate"),
        ("respond-to-referees.md", "Parse JSON for:", "project_contract_gate"),
        ("peer-review.md", "Parse JSON for:", "project_contract_gate"),
    ],
)
def test_contract_gate_is_visible_before_authoritative_use(
    workflow_name: str,
    surface_marker: str,
    expected_token: str,
) -> None:
    workflow = _workflow_text(workflow_name)
    surface_line = next(line for line in workflow.splitlines() if surface_marker in line)

    assert expected_token in surface_line
    assert workflow.index(surface_line) < workflow.index("project_contract_gate.authoritative")
    assert "project_contract_gate.authoritative" in workflow


@pytest.mark.parametrize(
    ("command_name", "surface_marker"),
    [
        ("literature-review.md", "Extract `commit_docs`"),
        ("research-phase.md", "Extract from init JSON:"),
    ],
)
def test_command_contract_gate_is_visible_before_authoritative_use(command_name: str, surface_marker: str) -> None:
    commands_dir = REPO_ROOT / "src/gpd/commands"
    command = (commands_dir / command_name).read_text(encoding="utf-8")
    surface_line = next(line for line in command.splitlines() if surface_marker in line)

    assert "project_contract_gate" in surface_line
    assert command.index(surface_line) < command.index("project_contract_gate.authoritative")


def test_write_paper_surfaces_manuscript_reference_status_before_using_it() -> None:
    workflow = _workflow_text("write-paper.md")
    surface_line = next(line for line in workflow.splitlines() if line.startswith("Parse JSON for:"))

    assert "derived_manuscript_reference_status" in surface_line
    assert "derived_manuscript_reference_status_count" in surface_line
    assert workflow.index(surface_line) < workflow.index("derived_manuscript_reference_status")
    assert workflow.index(surface_line) < workflow.index("derived_manuscript_reference_status_count")
    assert "If `derived_manuscript_reference_status` is present" in workflow


def test_execute_phase_latex_compile_guidance_uses_resolved_manuscript_root() -> None:
    workflow = _workflow_text("execute-phase.md")

    assert "paper/ARTIFACT-MANIFEST.json" not in workflow
    assert "cd paper" not in workflow
    assert "MANUSCRIPT_ROOT" in workflow
    assert "ARTIFACT-MANIFEST.json" in workflow
    assert "latex_compile" in workflow


def test_peer_review_reliability_reference_matches_peer_review_workflow_invocation() -> None:
    workflow = _workflow_text("peer-review.md")
    reliability = (
        REPO_ROOT / "src/gpd/specs/references/publication/peer-review-reliability.md"
    ).read_text(encoding="utf-8")

    expected = 'gpd validate review-preflight peer-review "$ARGUMENTS" --strict'

    assert expected in workflow
    assert expected in reliability
    assert "gpd validate review-preflight peer-review --strict" not in reliability


def test_reapply_patches_keeps_manifest_regeneration_contract_honest() -> None:
    workflow = _workflow_text("reapply-patches.md")

    assert "do not invent a manual manifest-regeneration step" in workflow
    assert "The managed file manifest is rebuilt by the next `/gpd:update`" in workflow
    assert "regenerate the file manifest" not in workflow


def test_help_update_describes_bootstrap_update_surface_not_repo_pull() -> None:
    workflow = _workflow_text("help.md")

    assert "Runs the public bootstrap update command for the active runtime" in workflow
    assert "Preserves local modifications via patch backups" in workflow
    assert "Pulls latest GPD files from the repository" not in workflow


def test_new_milestone_roadmapper_prompt_surfaces_contract_gate_inputs() -> None:
    workflow = _workflow_text("new-milestone.md")
    contract_context = workflow[workflow.index("<contract_context>") : workflow.index("</contract_context>")]

    assert "Project contract gate: {project_contract_gate}" in contract_context
    assert "Project contract validation: {project_contract_validation}" in contract_context
    assert "Project contract load info: {project_contract_load_info}" in contract_context
    assert workflow.index("Project contract gate: {project_contract_gate}") < workflow.index("approved project contract")
    assert "`project_contract_gate.authoritative` is true" in workflow


def test_help_resume_surface_stays_user_facing() -> None:
    workflow = _workflow_text("help.md")

    assert "Compatibility-only intake fields stay internal" in workflow
    assert "compat_resume_surface" not in workflow
    assert "session.resume_file" not in workflow
    assert "shared resume-surface resolver owns canonical candidate kind/origin semantics" not in workflow


def test_arxiv_submission_does_not_instruct_unsupported_explicit_submission_root() -> None:
    workflow = _workflow_text("arxiv-submission.md")

    assert "submission/topic_stem.tex" not in workflow
    assert "explicit manuscript under `paper/`, `manuscript/`, or `draft/`" in workflow


def test_paper_quality_scoring_reference_tracks_per_journal_gate_and_generic_fallback() -> None:
    scoring = (
        REPO_ROOT / "src/gpd/specs/references/publication/paper-quality-scoring.md"
    ).read_text(encoding="utf-8")

    assert "minimum_submission_score" in scoring
    assert "score ≥ 80" not in scoring
    assert "`mnras` and `jfm` currently use the generic weighting profile" in scoring


def test_write_paper_and_scoring_docs_distinguish_builder_supported_vs_manual_only_journals() -> None:
    workflow = _workflow_text("write-paper.md")
    scoring = (
        REPO_ROOT / "src/gpd/specs/references/publication/paper-quality-scoring.md"
    ).read_text(encoding="utf-8")

    assert "These are the only valid `journal` values in `PAPER-CONFIG.json` and `${PAPER_DIR}/ARTIFACT-MANIFEST.json`." in workflow
    assert "artifact-driven `--from-project` path" in scoring
    assert "Manual JSON is also the only supported path today for scoring-only profiles" in scoring
    assert "`prd`, `prb`, `prc`, and `nature_physics`" in scoring


def test_settings_publication_manuscript_preset_surfaces_real_latex_readiness_gates() -> None:
    settings = _workflow_text("settings.md")

    assert "only affects local smoke checks" not in settings
    assert "can degrade or block `paper-build` / `arxiv-submission`" in settings
