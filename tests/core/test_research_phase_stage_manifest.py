"""Stage-manifest regressions for the `research-phase` startup surface."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.workflow_staging import validate_workflow_stage_manifest_payload
from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_research_phase_stage_manifest_defers_runtime_delegation_until_the_handoff_stage() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "research-phase-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="research-phase",
    )

    assert manifest.stage_ids() == (
        "phase_bootstrap",
        "research_handoff",
    )

    bootstrap = manifest.stage("phase_bootstrap")
    handoff = manifest.stage("research_handoff")

    assert bootstrap.loaded_authorities == (
        "workflows/research-phase.md",
        "references/orchestration/model-profile-resolution.md",
    )
    assert "references/orchestration/runtime-delegation-note.md" in bootstrap.must_not_eager_load
    assert "reference_artifacts_content" not in bootstrap.required_init_fields

    assert handoff.loaded_authorities == (
        "workflows/research-phase.md",
        "references/orchestration/model-profile-resolution.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert "reference_artifacts_content" in handoff.required_init_fields
    assert handoff.writes_allowed == ("GPD/phases/XX-name/XX-RESEARCH.md",)


def test_research_phase_prompt_budget_keeps_the_vertical_reasonably_tight() -> None:
    agent_metrics = measure_prompt_surface(
        AGENTS_DIR / "gpd-phase-researcher.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    command_metrics = measure_prompt_surface(
        COMMANDS_DIR / "research-phase.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow_metrics = measure_prompt_surface(
        WORKFLOWS_DIR / "research-phase.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert agent_metrics.raw_include_count == 0
    assert agent_metrics.expanded_line_count == 2028
    assert agent_metrics.expanded_char_count == 101143
    assert agent_metrics.expanded_char_count < 130000
    assert command_metrics.raw_include_count == 2
    assert command_metrics.expanded_line_count == 421
    assert command_metrics.expanded_char_count == 17557
    assert command_metrics.expanded_char_count < 20000
    assert workflow_metrics.expanded_line_count == 318
    assert workflow_metrics.expanded_char_count == 13567
    assert workflow_metrics.expanded_char_count < 15000


def test_research_phase_command_prompt_budget_keeps_delegation_authorities_out_of_the_wrapper() -> None:
    command_text = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "research-phase.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "research-phase.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 2
    assert "@{GPD_INSTALL_DIR}/workflows/research-phase.md" in command_text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/model-profile-resolution.md" in command_text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md" not in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 300
    assert metrics.expanded_char_count < workflow.expanded_char_count + 18000
