"""Typed policy and current-workspace honesty assertions for derive-equation."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_DOC = REPO_ROOT / "src/gpd/commands/derive-equation.md"
WORKFLOW_DOC = REPO_ROOT / "src/gpd/specs/workflows/derive-equation.md"


def test_derive_equation_exposes_typed_current_workspace_output_policy() -> None:
    command = registry.get_command("derive-equation")

    assert command.command_policy == registry.CommandPolicy(
        schema_version=1,
        subject_policy=registry.CommandSubjectPolicy(
            explicit_input_kinds=["equation or topic to derive"],
        ),
        supporting_context_policy=registry.CommandSupportingContextPolicy(
            project_context_mode="project-aware",
            project_reentry_mode="disallowed",
            optional_file_patterns=[
                "GPD/STATE.md",
                "GPD/analysis/*.md",
                "GPD/phases/*/DERIVATION-*.md",
            ],
        ),
        output_policy=registry.CommandOutputPolicy(
            output_mode="managed",
            managed_root_kind="gpd_managed_durable",
            default_output_subtree="GPD/analysis",
            stage_artifact_policy="gpd_owned_outputs_only",
        ),
    )


def test_derive_equation_docs_keep_current_workspace_outputs_honest() -> None:
    command_text = COMMAND_DOC.read_text(encoding="utf-8")
    workflow_text = WORKFLOW_DOC.read_text(encoding="utf-8")

    assert "Outside a project, an explicit derivation target is required and empty standalone launches stay blocked." in command_text
    assert "Keep standalone/current-workspace durable derivation artifacts under `GPD/analysis/` rooted at the invoking workspace." in command_text
    assert "Only runs with authoritative phase context may additionally write sibling phase artifacts and persist project registry state." in command_text
    assert "Do not synthesize a phase-local output path from an ancestor project root or an unverified phase guess." in workflow_text
    assert "Current-workspace fallback (standalone or no authoritative phase context)" in workflow_text
