"""Prompt-contract guardrails for numerical-convergence standalone/current-workspace behavior."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_PATH = REPO_ROOT / "src/gpd/commands/numerical-convergence.md"
WORKFLOW_PATH = REPO_ROOT / "src/gpd/specs/workflows/numerical-convergence.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_numerical_convergence_command_surfaces_typed_current_workspace_output_policy() -> None:
    command = _read(COMMAND_PATH)
    parsed = registry.get_command("numerical-convergence")

    assert "command-policy:" in command
    assert "Keep standalone/current-workspace durable outputs under `GPD/analysis/` rooted at the invoking workspace." in command
    assert "If empty outside a project: command-context validation rejects the request" in command
    assert parsed.command_policy == registry.CommandPolicy(
        schema_version=1,
        supporting_context_policy=registry.CommandSupportingContextPolicy(
            project_context_mode="project-aware",
            project_reentry_mode="disallowed",
            optional_file_patterns=[
                "GPD/STATE.md",
                "GPD/ROADMAP.md",
                "GPD/research-map/VALIDATION.md",
                "GPD/analysis/*.md",
            ],
        ),
        output_policy=registry.CommandOutputPolicy(
            output_mode="managed",
            managed_root_kind="gpd_managed_durable",
            default_output_subtree="GPD/analysis",
            stage_artifact_policy="gpd_owned_outputs_only",
        ),
    )


def test_numerical_convergence_workflow_uses_workspace_locked_context_and_honest_target_resolution() -> None:
    workflow = _read(WORKFLOW_PATH)

    assert 'INIT=$(gpd --raw init progress --include state,config --no-project-reentry)' in workflow
    assert "must not silently reenter a different recent project" in workflow
    assert "Use the command wrapper's centralized command-context preflight plus `$ARGUMENTS` to classify the target honestly" in workflow
    assert "do not invent `phase_dir` or `phase_slug` from ambient workspace state" in workflow
    assert 'OUTPUT_PATH="${phase_dir}/NUMERICAL-VALIDATION.md"' in workflow
    assert 'OUTPUT_PATH="GPD/analysis/numerical-{slug}.md"' in workflow


def test_numerical_convergence_workflow_keeps_standalone_outputs_uncommitted_and_out_of_phase_dirs() -> None:
    workflow = _read(WORKFLOW_PATH)

    assert "Never write standalone/current-workspace numerical validation reports under `GPD/phases/**`." in workflow
    assert "Do not run an unconditional standalone docs commit for this workflow." in workflow
    assert "If the run is not phase-scoped, do not run `gpd pre-commit-check` or `gpd commit`." in workflow
    assert '  "docs: numerical convergence validation — ${phase_slug}" \\' in workflow
    assert "${phase_slug:-standalone}" not in workflow

