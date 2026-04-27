"""Focused assertions for the dimensional-analysis standalone/workspace contract."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_DOC = REPO_ROOT / "src/gpd/commands/dimensional-analysis.md"
WORKFLOW_DOC = REPO_ROOT / "src/gpd/specs/workflows/dimensional-analysis.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dimensional_analysis_command_exposes_workspace_locked_policy() -> None:
    command_text = _read(COMMAND_DOC)
    parsed = registry.get_command("dimensional-analysis")

    assert "command-policy:" in command_text
    assert "If empty and project context exists: prompt for the target" in command_text
    assert "If empty outside a project: command-context validation rejects the request" in command_text
    assert "Keep any standalone/current-workspace GPD-authored audit artifact under `GPD/analysis/` rooted at the invoking workspace." in command_text
    assert parsed.command_policy == registry.CommandPolicy(
        schema_version=1,
        subject_policy=registry.CommandSubjectPolicy(
            explicit_input_kinds=["phase number or file path"],
        ),
        supporting_context_policy=registry.CommandSupportingContextPolicy(
            project_context_mode="project-aware",
            project_reentry_mode="disallowed",
            optional_file_patterns=[
                "GPD/STATE.md",
                "GPD/ROADMAP.md",
                "GPD/research-map/FORMALISM.md",
                "GPD/research-map/VALIDATION.md",
            ],
        ),
        output_policy=registry.CommandOutputPolicy(
            output_mode="managed",
            managed_root_kind="gpd_managed_durable",
            default_output_subtree="GPD/analysis",
        ),
    )


def test_dimensional_analysis_workflow_uses_workspace_locked_init_and_advisory_conventions() -> None:
    workflow_text = _read(WORKFLOW_DOC)

    assert 'INIT=$(gpd --raw init progress --include state,config --no-project-reentry)' in workflow_text
    assert "do not auto-reenter a different recent project here" in workflow_text
    assert "If `state_exists` is false in the current workspace: proceed in standalone mode." in workflow_text
    assert "If `derived_convention_lock` is missing or incomplete: treat it as advisory only" in workflow_text
    assert "do not synthesize a project convention check" in workflow_text


def test_dimensional_analysis_workflow_keeps_outputs_in_workspace_analysis_root() -> None:
    workflow_text = _read(WORKFLOW_DOC)

    assert 'OUTPUT_PATH="GPD/analysis/dimensional-{slug}.md"' in workflow_text
    assert "mkdir -p GPD/analysis" in workflow_text
    assert "The durable audit artifact stays under the same current-workspace `GPD/analysis/` subtree" in workflow_text
    assert "Do not run an unconditional standalone docs commit for this workflow." in workflow_text
    assert "skip the commit step entirely and report `${OUTPUT_PATH}` back to the user." in workflow_text
    assert "gpd commit \\" not in workflow_text
    assert "${phase_dir}/DIMENSIONAL-ANALYSIS.md" not in workflow_text
