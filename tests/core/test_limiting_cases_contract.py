"""Prompt-contract guardrails for limiting-cases standalone/current-workspace behavior."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_PATH = REPO_ROOT / "src/gpd/commands/limiting-cases.md"
WORKFLOW_PATH = REPO_ROOT / "src/gpd/specs/workflows/limiting-cases.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_limiting_cases_command_surfaces_typed_current_workspace_output_policy() -> None:
    command = _read(COMMAND_PATH)
    parsed = registry.get_command("limiting-cases")

    assert "name: gpd:limiting-cases" in command
    assert "command-policy:" in command
    assert "Standalone current-workspace runs write `GPD/analysis/limits-{slug}.md`" in command
    assert "bare numeric tokens are not valid standalone targets" in command
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
                "GPD/research-map/*.md",
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


def test_limiting_cases_workflow_rejects_numeric_standalone_targets_and_reuses_resolved_paths() -> None:
    workflow = _read(WORKFLOW_PATH)

    assert 'CONTEXT=$(gpd --raw validate command-context limiting-cases "$ARGUMENTS")' in workflow
    assert 'INIT=$(gpd --raw init progress --include state,config --no-project-reentry)' in workflow
    assert "standalone `gpd:limiting-cases` requires an explicit file path" in workflow
    assert "Do not reinterpret a numeric token as a hidden phase selection." in workflow
    assert 'OUTPUT_PATH="GPD/analysis/limits-{slug}.md"' in workflow
    assert "Reuse the resolved `TARGET_KIND`, `TARGET_FILE`, `slug`, and `OUTPUT_PATH` variables consistently." in workflow
    assert 'for path in "${TARGET_FILES[@]}"; do' in workflow


def test_limiting_cases_workflow_keeps_standalone_outputs_uncommitted_and_out_of_phase_dirs() -> None:
    workflow = _read(WORKFLOW_PATH)

    assert "Never write standalone/current-workspace limiting-cases reports under `GPD/phases/**`." in workflow
    assert "Do not run an unconditional standalone docs commit for this workflow." in workflow
    assert "If the run is standalone/current-workspace file mode, skip the commit step entirely" in workflow
    assert '  "docs: limiting cases verification — ${phase_slug}" \\' in workflow
    assert "${phase_slug:-standalone}" not in workflow
