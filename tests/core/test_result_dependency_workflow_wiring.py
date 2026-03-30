"""Focused regressions for dependency-aware canonical result reuse guidance."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPARE_EXPERIMENT = REPO_ROOT / "src/gpd/specs/workflows/compare-experiment.md"
ERROR_PROPAGATION = REPO_ROOT / "src/gpd/specs/workflows/error-propagation.md"
EXPLAIN_WORKFLOW = REPO_ROOT / "src/gpd/specs/workflows/explain.md"
EXPLAIN_COMMAND = REPO_ROOT / "src/gpd/commands/explain.md"
SENSITIVITY_ANALYSIS = REPO_ROOT / "src/gpd/specs/workflows/sensitivity-analysis.md"
AGENT_INFRASTRUCTURE = REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md"


def test_compare_experiment_workflow_uses_dependency_aware_result_search() -> None:
    text = COMPARE_EXPERIMENT.read_text(encoding="utf-8")

    assert 'gpd result search --depends-on "{upstream_result_id}"' in text
    assert 'gpd result deps "{result_id}"' in text


def test_error_propagation_workflow_prefers_result_deps_before_manual_tree_rebuild() -> None:
    text = ERROR_PROPAGATION.read_text(encoding="utf-8")

    assert 'prefer `gpd result deps "{result_id}"` to recover the recorded dependency tree' in text
    assert 'run `gpd result deps "{result_id}"` first' in text


def test_explain_surfaces_result_deps_for_upstream_context() -> None:
    workflow_text = EXPLAIN_WORKFLOW.read_text(encoding="utf-8")
    command_text = EXPLAIN_COMMAND.read_text(encoding="utf-8")

    assert 'gpd result show "{result_id}"' in workflow_text
    assert 'gpd result deps "{result_id}"' in workflow_text
    assert 'gpd result show "{result_id}"' in command_text
    assert 'gpd result deps "{result_id}"' in command_text


def test_sensitivity_analysis_prompts_for_result_deps_after_canonical_lookup() -> None:
    text = SENSITIVITY_ANALYSIS.read_text(encoding="utf-8")

    assert 'gpd result search' in text
    assert 'gpd result deps "{result_id}"' in text


def test_agent_infrastructure_separates_phase_and_result_dependency_commands() -> None:
    text = AGENT_INFRASTRUCTURE.read_text(encoding="utf-8")

    assert 'gpd query deps <identifier>' in text
    assert 'Trace a specific phase/frontmatter dependency across phases' in text
    assert 'gpd result deps <identifier>' in text
    assert 'Trace dependencies for a canonical result identifier' in text
