"""Focused regressions for the sensitivity-analysis standalone/current-workspace contract."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_DOC = REPO_ROOT / "src/gpd/commands/sensitivity-analysis.md"
WORKFLOW_DOC = REPO_ROOT / "src/gpd/specs/workflows/sensitivity-analysis.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sensitivity_analysis_command_exposes_typed_workspace_locked_policy() -> None:
    command_text = _read(COMMAND_DOC)
    parsed = registry.get_command("sensitivity-analysis")

    assert "command-policy:" in command_text
    assert "In standalone/current-workspace mode, centralized preflight requires explicit `--target` and `--params`" in command_text
    assert "Keep any standalone/current-workspace durable artifacts under `GPD/analysis/` rooted at the invoking workspace." in command_text
    assert parsed.command_policy == registry.CommandPolicy(
        schema_version=1,
        supporting_context_policy=registry.CommandSupportingContextPolicy(
            project_context_mode="project-aware",
            project_reentry_mode="disallowed",
            optional_file_patterns=[
                "GPD/STATE.md",
                "GPD/ROADMAP.md",
                "GPD/analysis/PARAMETERS.md",
            ],
        ),
        output_policy=registry.CommandOutputPolicy(
            output_mode="managed",
            managed_root_kind="gpd_managed_durable",
            default_output_subtree="GPD/analysis",
            stage_artifact_policy="gpd_owned_outputs_only",
        ),
    )


def test_sensitivity_analysis_workflow_uses_workspace_locked_supporting_context() -> None:
    workflow_text = _read(WORKFLOW_DOC)

    assert 'INIT=$(gpd --raw init progress --include state,config --no-project-reentry)' in workflow_text
    assert 'gpd result search' in workflow_text
    assert 'gpd result show "{result_id}"' in workflow_text
    assert 'gpd result deps "{result_id}"' in workflow_text
    assert "Never recover phase-backed persistence from `${PHASE_ARG:-}`" in workflow_text
    assert 'INIT=$(gpd --raw init phase-op --include state,config "${PHASE_ARG:-}")' not in workflow_text


def test_sensitivity_analysis_workflow_keeps_standalone_outputs_uncommitted_and_state_clean() -> None:
    workflow_text = _read(WORKFLOW_DOC)

    assert 'REPORT_PATH="${phase_dir}/SENSITIVITY-REPORT.md"' in workflow_text
    assert 'REPORT_PATH="GPD/analysis/sensitivity-{slug}.md"' in workflow_text
    assert "Never write standalone/current-workspace sensitivity reports under `GPD/phases/**`." in workflow_text
    assert "If no phase-scoped project context exists, skip all `gpd uncertainty add` calls." in workflow_text
    assert "Do not run an unconditional standalone docs commit for this workflow." in workflow_text
    assert "If the run is not phase-scoped, do not run `gpd pre-commit-check` or `gpd commit`." in workflow_text
