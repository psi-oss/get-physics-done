"""Prompt budget assertions for the `plan-phase` startup surface."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.workflow_staging import validate_workflow_stage_manifest_payload
from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_plan_phase_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "plan-phase.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/plan-phase.md" in command_text
    assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/ui/ui-brand.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/planner-subagent-prompt.md" not in command_text
    assert "Follow the included workflow file exactly." in command_text


def test_plan_phase_workflow_defers_stage_authorities_until_the_manifest_stages_need_them() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "plan-phase-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="plan-phase",
    )

    assert manifest.stage_ids() == (
        "phase_bootstrap",
        "research_routing",
        "planner_authoring",
        "checker_revision",
    )

    bootstrap = manifest.stages[0]
    planner_authoring = manifest.stages[2]
    checker_revision = manifest.stages[3]

    assert bootstrap.loaded_authorities == ("workflows/plan-phase.md",)
    assert "templates/plan-contract-schema.md" in bootstrap.must_not_eager_load
    assert "templates/planner-subagent-prompt.md" in bootstrap.must_not_eager_load
    assert "references/ui/ui-brand.md" in bootstrap.must_not_eager_load

    assert planner_authoring.loaded_authorities == (
        "workflows/plan-phase.md",
        "templates/planner-subagent-prompt.md",
    )
    assert checker_revision.loaded_authorities == (
        "workflows/plan-phase.md",
        "templates/planner-subagent-prompt.md",
    )
    assert "reference_artifacts_content" in planner_authoring.required_init_fields
    assert "reference_artifacts_content" in checker_revision.required_init_fields
    assert "experiment_design_content" in planner_authoring.required_init_fields
    assert "experiment_design_content" in checker_revision.required_init_fields


def test_plan_phase_clean_non_autonomous_planning_reports_green_with_no_checkpoint() -> None:
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "Structured final status convention" in workflow_text
    assert "clean bounded non-autonomous planning" in workflow_text
    assert "has `checkpoint: none`" in workflow_text
    assert "report `status: green`" in workflow_text
    assert "Execution remaining as the next command is not by itself a yellow condition." in workflow_text
