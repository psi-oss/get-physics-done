"""Prompt budget assertions for the `execute-phase` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_execute_phase_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_path = COMMANDS_DIR / "execute-phase.md"
    command_text = command_path.read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        command_path,
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/execute-phase.md" in command_text
    assert "<arguments>" in command_text
    assert "<inline_guidance>" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/ui/ui-brand.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/summary.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" not in command_text
    assert "Read the included workflow first and follow it end-to-end." in command_text


def test_execute_phase_workflow_refreshes_stage_context_in_order() -> None:
    workflow_text = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert 'PHASE_ARG=""' in workflow_text
    assert "EXECUTE_FLAGS=()" in workflow_text
    assert "GAPS_ONLY=false" in workflow_text
    assert '[ "$flag" = "--gaps-only" ] && GAPS_ONLY=true' in workflow_text
    assert '*) [ -z "$PHASE_ARG" ] && PHASE_ARG="$token" ;;' in workflow_text
    assert workflow_text.index("<step name=\"normalize_arguments\"") < workflow_text.index(
        "BOOTSTRAP_INIT=$(load_execute_phase_stage phase_bootstrap)"
    )
    assert "BOOTSTRAP_INIT=$(load_execute_phase_stage phase_bootstrap)" in workflow_text
    assert "WAVE_PLANNING_INIT=$(load_execute_phase_stage wave_planning)" in workflow_text
    assert "PRE_EXECUTION_INIT=$(load_execute_phase_stage pre_execution_specialists)" in workflow_text
    assert "WAVE_DISPATCH_INIT=$(load_execute_phase_stage wave_dispatch)" in workflow_text
    assert workflow_text.index("BOOTSTRAP_INIT=$(load_execute_phase_stage phase_bootstrap)") < workflow_text.index(
        "WAVE_PLANNING_INIT=$(load_execute_phase_stage wave_planning)"
    )
    assert workflow_text.index("WAVE_PLANNING_INIT=$(load_execute_phase_stage wave_planning)") < workflow_text.index(
        "PRE_EXECUTION_INIT=$(load_execute_phase_stage pre_execution_specialists)"
    )
    assert workflow_text.index("PRE_EXECUTION_INIT=$(load_execute_phase_stage pre_execution_specialists)") < workflow_text.index(
        "WAVE_DISPATCH_INIT=$(load_execute_phase_stage wave_dispatch)"
    )
    assert 'gpd --raw init execute-phase "${PHASE_ARG}" --include state,config' not in workflow_text
    assert "If `$GAPS_ONLY` is true, also skip non-gap_closure plans." in workflow_text
    assert "**After gap closure execution completes (`$GAPS_ONLY` is true):**" in workflow_text
    assert "execute-plan.md owns plan-local execution semantics" in workflow_text
    assert "# task(subagent_type=\"gpd-notation-coordinator\"" not in workflow_text
    assert "# task(subagent_type=\"gpd-experiment-designer\"" not in workflow_text


def test_execute_phase_single_sources_runtime_delegation_boilerplate() -> None:
    workflow_text = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert workflow_text.count("@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md") == 1
    assert "Canonical runtime delegation convention for every `task()` block in this workflow:" in workflow_text
    assert "Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism." not in workflow_text
    assert "owns empty-model omission, file-producing `readonly=false`, artifact-gated completion" in workflow_text
    assert workflow_text.count("Apply the canonical runtime delegation convention above.") == 6
