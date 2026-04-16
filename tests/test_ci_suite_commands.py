from __future__ import annotations

from pathlib import Path

import yaml

from tests.ci_sharding import CI_CATEGORY_SHARD_COUNTS, ci_shard_specs

REPO_ROOT = Path(__file__).resolve().parent.parent


def _workflow_data() -> dict[str, object]:
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


def _job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def _pytest_matrix_include(workflow: dict[str, object]) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    pytest_job = jobs["pytest"]
    assert isinstance(pytest_job, dict)
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)
    matrix = strategy["matrix"]
    assert isinstance(matrix, dict)
    include = matrix["include"]
    assert isinstance(include, list)
    assert all(isinstance(entry, dict) for entry in include)
    return include


def test_ci_workflow_runs_category_named_runtime_informed_pytest_shards_with_default_parallelism_and_ci_worksteal() -> None:
    workflow = _workflow_data()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    pytest_steps = _job_steps(workflow, "pytest")
    pytest_step_names = [str(step.get("name", "")) for step in pytest_steps]
    pytest_run_steps = {
        str(step.get("name", "")): str(step.get("run", ""))
        for step in pytest_steps
        if "run" in step
    }
    matrix_include = _pytest_matrix_include(workflow)
    actual_shards = tuple(
        (
            str(entry["display_name"]),
            str(entry["category"]),
            int(entry["shard_index"]),
            int(entry["shard_total"]),
        )
        for entry in matrix_include
    )
    expected_shards = tuple(
        (spec.display_name, spec.category, spec.shard_index, spec.shard_total)
        for spec in ci_shard_specs()
    )

    assert jobs["pytest"].get("needs") is None
    pytest_job = jobs["pytest"]
    assert isinstance(pytest_job, dict)
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)
    assert strategy["fail-fast"] is False
    assert actual_shards == expected_shards
    assert len(matrix_include) == sum(CI_CATEGORY_SHARD_COUNTS.values())

    # trigger-staging-rebuild moved to staging-rebuild.yml (workflow_run trigger)
    # to avoid showing as a skipped check on PRs.
    assert "trigger-staging-rebuild" not in jobs

    assert "Set up Node.js" in pytest_step_names
    assert pytest_step_names.index("Set up Node.js") < pytest_step_names.index("Install dependencies")
    resolve_targets_command = pytest_run_steps["Resolve pytest shard targets"]
    pytest_shard_command = pytest_run_steps["Run pytest shard"]
    assert "from tests.ci_sharding import write_ci_shard_targets_file" in resolve_targets_command
    assert "PYTEST_CATEGORY" in resolve_targets_command
    assert "PYTEST_SHARD_TARGET_FILE" in resolve_targets_command
    assert "Resolved {len(targets)} pytest targets for {os.environ['PYTEST_CATEGORY']}" in resolve_targets_command
    assert "shard {os.environ['PYTEST_SHARD_INDEX']}/{os.environ['PYTEST_SHARD_TOTAL']}" in resolve_targets_command
    assert 'mapfile -t PYTEST_TARGETS < "$PYTEST_SHARD_TARGET_FILE"' in pytest_shard_command
    assert 'uv run pytest -q "${PYTEST_TARGETS[@]}"' in pytest_shard_command
    assert pytest_steps[-1]["name"] == "Run pytest shard"
    assert pytest_steps[-1]["run"] == pytest_shard_command
    assert pytest_steps[2]["uses"] == "actions/setup-node@v6"
    assert pytest_steps[2]["with"]["node-version"] == "20"
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert 'pytest-xdist>=3.8.0' in pyproject


def test_tests_readme_documents_default_full_suite_and_category_named_runtime_informed_ci_shards() -> None:
    tests_readme = (REPO_ROOT / "tests" / "README.md").read_text(encoding="utf-8")

    assert "Default `uv run pytest` runs the full checked-in suite" in tests_readme
    assert "`uv run pytest -q` does the same with quieter output" in tests_readme
    assert "Both inherit `-n auto --dist=worksteal` from `pyproject.toml`" in tests_readme
    assert "raises xdist auto-worker selection toward the current CI shard fanout" in tests_readme
    assert "override that default explicitly with `uv run pytest -n 0`" in tests_readme
    assert "GitHub Actions workflow runs that same full suite as category-named runtime-informed shards" in tests_readme
    assert "`root 1/9` through `root 9/9`, `adapters 1/2` through `adapters 2/2`, `hooks 1/2` through `hooks 2/2`, `mcp`, and `core 1/5` through `core 5/5`" in tests_readme
    assert "boosts root modules that have been slow on GitHub Actions" in tests_readme
    assert "splits known hotspot modules such as `tests/test_runtime_cli.py`, `tests/test_registry.py`, `tests/test_update_workflow.py`, and `tests/hooks/test_runtime_detect.py`" in tests_readme
    assert "greedily rebalances those work units inside each category" in tests_readme
