from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import tests.conftest as tests_conftest
from tests.ci_sharding import (
    CI_CATEGORY_SHARD_COUNTS,
    CI_HOT_TEST_FILE_SPLITS,
    all_test_relpaths,
    build_ci_work_units,
    category_for_test_relpath,
    ci_shard_specs,
    collected_test_counts_by_file,
    collected_test_inventory,
    expand_ci_targets_to_nodeids,
    plan_category_ci_shards,
)


def _read(relpath: str) -> str:
    return (Path(__file__).resolve().parent / relpath).read_text(encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _workflow_data() -> dict[str, object]:
    return yaml.safe_load((_repo_root() / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


def _workflow_job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def test_root_conftest_keeps_default_collection_as_full_suite() -> None:
    root_conftest = _read("conftest.py")
    core_conftest = _read("core/conftest.py")

    assert "_isolate_machine_local_gpd_data" in root_conftest
    assert "pytest_xdist_auto_num_workers" in root_conftest
    assert "test suite mode: full (default)" in root_conftest
    assert "FAST_SUITE_EXCLUDES" not in root_conftest
    assert "--full-suite" not in root_conftest
    assert "GPD_TEST_FULL" not in root_conftest
    assert "pytest_ignore_collect" not in root_conftest
    assert "collect_ignore" not in core_conftest


def test_root_conftest_scales_local_full_suite_auto_workers_toward_ci_fanout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ci_shards = sum(CI_CATEGORY_SHARD_COUNTS.values())

    assert tests_conftest._is_default_full_suite_invocation([]) is True
    assert tests_conftest._is_default_full_suite_invocation(["tests"]) is True
    assert tests_conftest._is_default_full_suite_invocation(["tests/"]) is True
    assert tests_conftest._is_default_full_suite_invocation(["tests/test_runtime_cli.py"]) is False
    assert tests_conftest._full_suite_auto_worker_count(cpu_count=16, ci_shard_total=ci_shards) == ci_shards
    assert tests_conftest._full_suite_auto_worker_count(cpu_count=8, ci_shard_total=ci_shards) == 16

    config = SimpleNamespace(
        args=["tests"],
        option=SimpleNamespace(numprocesses="auto", maxprocesses=None),
    )
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    monkeypatch.setattr(tests_conftest.os, "cpu_count", lambda: 16)
    assert tests_conftest.pytest_xdist_auto_num_workers(config) == ci_shards

    config.option.maxprocesses = 12
    assert tests_conftest.pytest_xdist_auto_num_workers(config) == 12

    config.args = ["tests/test_runtime_cli.py"]
    assert tests_conftest.pytest_xdist_auto_num_workers(config) is None


def test_default_collection_matches_all_checked_in_test_files() -> None:
    repo_root = _repo_root()
    all_relpaths = all_test_relpaths(tests_root=repo_root / "tests")
    collected_counts = collected_test_counts_by_file(repo_root=repo_root)

    assert tuple(sorted(collected_counts)) == all_relpaths
    assert all(count > 0 for count in collected_counts.values())


def test_ci_and_test_readme_document_default_full_suite_and_category_named_runtime_informed_shards() -> None:
    repo_root = _repo_root()
    workflow = _workflow_data()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    tests_readme = (repo_root / "tests" / "README.md").read_text(encoding="utf-8")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    pytest_steps = _workflow_job_steps(workflow, "pytest")
    pytest_step_names = [str(step.get("name", "")) for step in pytest_steps]
    pytest_run_steps = {
        str(step.get("name", "")): str(step.get("run", ""))
        for step in pytest_steps
        if "run" in step
    }
    pytest_job = jobs["pytest"]
    assert isinstance(pytest_job, dict)
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)
    matrix = strategy["matrix"]
    assert isinstance(matrix, dict)
    include = matrix["include"]
    assert isinstance(include, list)

    assert jobs["pytest"].get("needs") is None
    # trigger-staging-rebuild moved to staging-rebuild.yml (workflow_run trigger)
    assert "trigger-staging-rebuild" not in jobs

    assert strategy["fail-fast"] is False
    assert len(include) == sum(CI_CATEGORY_SHARD_COUNTS.values())
    assert tuple(
        (
            str(entry["display_name"]),
            str(entry["category"]),
            int(entry["shard_index"]),
            int(entry["shard_total"]),
        )
        for entry in include
    ) == tuple(
        (spec.display_name, spec.category, spec.shard_index, spec.shard_total)
        for spec in ci_shard_specs()
    )

    assert "Set up Node.js" in pytest_step_names
    assert pytest_step_names.index("Set up Node.js") < pytest_step_names.index("Install dependencies")
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert 'pytest-xdist>=3.8.0' in pyproject
    resolve_targets_command = pytest_run_steps["Resolve pytest shard targets"]
    pytest_shard_command = pytest_run_steps["Run pytest shard"]
    assert "from tests.ci_sharding import write_ci_shard_targets_file" in resolve_targets_command
    assert "PYTEST_CATEGORY" in resolve_targets_command
    assert 'mapfile -t PYTEST_TARGETS < "$PYTEST_SHARD_TARGET_FILE"' in pytest_shard_command
    assert 'uv run pytest -q "${PYTEST_TARGETS[@]}"' in pytest_shard_command
    assert "Default `uv run pytest` runs the full checked-in suite" in tests_readme
    assert "`uv run pytest -q` does the same with quieter output" in tests_readme
    assert "raises xdist auto-worker selection toward the current CI shard fanout" in tests_readme
    assert "override that default explicitly with `uv run pytest -n 0`" in tests_readme
    assert "GitHub Actions workflow runs that same full suite as category-named runtime-informed shards" in tests_readme
    assert "`root 1/9` through `root 9/9`, `adapters 1/2` through `adapters 2/2`, `hooks 1/2` through `hooks 2/2`, `mcp`, and `core 1/5` through `core 5/5`" in tests_readme
    assert "boosts root modules that have been slow on GitHub Actions" in tests_readme
    assert "splits known hotspot modules such as `tests/test_runtime_cli.py`, `tests/test_registry.py`, `tests/test_update_workflow.py`, and `tests/hooks/test_runtime_detect.py`" in tests_readme
    assert "greedily rebalances those work units inside each category" in tests_readme


def test_hotspot_files_are_split_into_multiple_work_units() -> None:
    inventory = collected_test_inventory(repo_root=_repo_root())
    work_units = build_ci_work_units(inventory)

    for rel_path, split_count in CI_HOT_TEST_FILE_SPLITS.items():
        matching = [unit for unit in work_units if unit.label.startswith(rel_path)]
        assert len(matching) == split_count
        assert sum(len(unit.targets) for unit in matching) == len(inventory[rel_path])


def test_category_shard_layout_covers_every_collected_nodeid_without_overlap() -> None:
    inventory = collected_test_inventory(repo_root=_repo_root())
    work_units = build_ci_work_units(inventory)
    all_nodeids = tuple(nodeid for nodeids in inventory.values() for nodeid in nodeids)
    flattened: list[str] = []

    for category, shard_total in CI_CATEGORY_SHARD_COUNTS.items():
        planned_shards = plan_category_ci_shards(category=category, work_units=work_units)
        expanded_targets = [
            expand_ci_targets_to_nodeids(shard_targets, inventory=inventory)
            for shard_targets in planned_shards
        ]
        category_nodeids = tuple(
            nodeid
            for rel_path, nodeids in inventory.items()
            if category_for_test_relpath(rel_path) == category
            for nodeid in nodeids
        )
        category_flattened = [nodeid for shard_nodeids in expanded_targets for nodeid in shard_nodeids]

        assert len(planned_shards) == shard_total
        assert sorted(category_flattened) == sorted(category_nodeids)
        assert len(category_flattened) == len(set(category_flattened))
        flattened.extend(category_flattened)

    assert sorted(flattened) == sorted(all_nodeids)
    assert len(flattened) == len(set(flattened))


def test_split_categories_keep_runtime_informed_weight_spread_tight() -> None:
    inventory = collected_test_inventory(repo_root=_repo_root())
    work_units = build_ci_work_units(inventory)
    per_target_weight = {
        target: unit.weight / len(unit.targets)
        for unit in work_units
        for target in unit.targets
    }

    for category, shard_total in CI_CATEGORY_SHARD_COUNTS.items():
        if shard_total == 1:
            continue
        planned_shards = plan_category_ci_shards(category=category, work_units=work_units)
        shard_weights = [
            sum(per_target_weight[target] for target in shard_targets)
            for shard_targets in planned_shards
        ]
        average_weight = sum(shard_weights) / len(shard_weights)

        assert max(shard_weights) - min(shard_weights) <= average_weight * 0.1
