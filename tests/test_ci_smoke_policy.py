from __future__ import annotations

import ast
from pathlib import Path

import yaml

from tests.ci_sharding import CI_SHARD_TARGET_RESOLVER_STEP_NAME, CI_SMOKE_PYTEST_STEP_NAME

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_SHARDING_PATH = REPO_ROOT / "tests" / "ci_sharding.py"
FORBIDDEN_SMOKE_SELECTION_TOKENS = (
    "subprocess",
    "all_test_relpaths",
    "collected_test_inventory",
    "collected_test_counts_by_file",
    "build_ci_work_units",
    "expand_ci_targets_to_nodeids",
    "plan_category_ci_shards",
    "select_ci_shard_targets",
    "write_ci_shard_targets_file",
    "--collect-only",
)


def _ci_sharding_source() -> str:
    return CI_SHARDING_PATH.read_text(encoding="utf-8")


def _ci_sharding_tree() -> ast.Module:
    return ast.parse(_ci_sharding_source())


def _module_assignment_value(name: str) -> ast.AST:
    for node in _ci_sharding_tree().body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return node.value
    raise AssertionError(f"missing module assignment: {name}")


def _function_source(name: str) -> str:
    source = _ci_sharding_source()
    for node in _ci_sharding_tree().body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            return segment
    raise AssertionError(f"missing function definition: {name}")


def _workflow_data() -> dict[str, object]:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "test.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def _job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def _run_steps_by_name(steps: list[dict[str, object]]) -> dict[str, str]:
    return {str(step.get("name", "")): str(step.get("run", "")) for step in steps if "run" in step}


def test_ci_smoke_targets_are_declared_as_literal_static_paths() -> None:
    assigned = _module_assignment_value("CI_SMOKE_TEST_TARGETS")

    assert isinstance(assigned, ast.Tuple)
    assert assigned.elts
    assert all(isinstance(element, ast.Constant) and isinstance(element.value, str) for element in assigned.elts)


def test_ci_smoke_command_builder_stays_direct_and_static() -> None:
    command_source = _function_source("ci_smoke_pytest_command")

    assert "CI_SMOKE_TEST_TARGETS" in command_source
    assert '" ".join((' in command_source
    assert all(token not in command_source for token in FORBIDDEN_SMOKE_SELECTION_TOKENS)


def test_ci_smoke_workflow_skips_shard_resolution_and_collect_only_helpers() -> None:
    workflow = _workflow_data()
    smoke_steps = _job_steps(workflow, "smoke")
    smoke_step_names = [str(step.get("name", "")) for step in smoke_steps]
    smoke_command = _run_steps_by_name(smoke_steps)[CI_SMOKE_PYTEST_STEP_NAME]

    assert CI_SHARD_TARGET_RESOLVER_STEP_NAME not in smoke_step_names
    assert all(token not in smoke_command for token in FORBIDDEN_SMOKE_SELECTION_TOKENS)
