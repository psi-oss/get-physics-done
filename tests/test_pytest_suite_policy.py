from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import tests.conftest as tests_conftest
from gpd.adapters.runtime_catalog import RuntimeDescriptor, iter_runtime_descriptors
from tests.ci_sharding import (
    CI_CATEGORY_SHARD_COUNTS,
    CI_FAST_PRIORITY_TEST_TARGETS,
    CI_FAST_PRIORITY_TIMEOUT_MINUTES,
    CI_HOT_TEST_FILE_SPLITS,
    CI_HOTSPOT_SPLIT_COVERAGE_MIN_TOP_FILES,
    CI_PYTEST_JOB_TIMEOUT_MINUTES,
    CI_PYTEST_SHARD_STEP_NAME,
    CI_SHARD_TARGET_RESOLVER_STEP_NAME,
    CI_SMOKE_JOB_TIMEOUT_MINUTES,
    CI_SMOKE_TEST_TARGETS,
    all_test_relpaths,
    build_ci_work_units,
    category_for_test_relpath,
    ci_shard_specs,
    ci_shard_target_filename,
    collected_test_counts_by_file,
    collected_test_inventory,
    expand_ci_targets_to_nodeids,
    plan_category_ci_shards,
    select_ci_shard_targets,
)

CI_FAST_PRIORITY_TEST_COUNT_LIMIT = 150


def _read(relpath: str) -> str:
    return (Path(__file__).resolve().parent / relpath).read_text(encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _workflow_data() -> dict[str, object]:
    return yaml.safe_load((_repo_root() / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


def _workflow_job(workflow: dict[str, object], job_name: str) -> dict[str, object]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    return job


def _workflow_job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    steps = _workflow_job(workflow, job_name)["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def _pytest_matrix_include(workflow: dict[str, object]) -> list[dict[str, object]]:
    pytest_job = _workflow_job(workflow, "pytest")
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)
    matrix = strategy["matrix"]
    assert isinstance(matrix, dict)
    include = matrix["include"]
    assert isinstance(include, list)
    assert all(isinstance(entry, dict) for entry in include)
    return include


def _job_needs(job: dict[str, object]) -> tuple[str, ...]:
    needs = job.get("needs")
    if needs is None:
        return ()
    if isinstance(needs, str):
        return (needs,)
    assert isinstance(needs, list)
    return tuple(str(entry) for entry in needs)


def _steps_using_action(steps: list[dict[str, object]], action_prefix: str) -> list[dict[str, object]]:
    return [step for step in steps if str(step.get("uses", "")).startswith(action_prefix)]


def _step_by_name(steps: list[dict[str, object]], name: str) -> dict[str, object]:
    matches = [step for step in steps if step.get("name") == name]
    assert len(matches) == 1
    return matches[0]


def _render_pytest_shard_target_filename(entry: dict[str, object], target_path: str) -> str:
    prefix = "${{ runner.temp }}/pytest-shards/"
    assert target_path.startswith(prefix)
    filename_template = target_path[len(prefix) :]

    if filename_template == "${{ matrix.target_filename }}":
        return str(entry["target_filename"])
    if filename_template == "${{ matrix.target_file }}":
        return str(entry["target_file"])
    if filename_template == "${{ matrix.slug }}.txt":
        return f"{entry['slug']}.txt"
    if filename_template == "${{ matrix.category }}-${{ matrix.shard_index }}.txt":
        return f"{entry['category']}-{entry['shard_index']}.txt"
    if filename_template == "${{ matrix.category }}.txt":
        return f"{entry['category']}.txt"

    pytest.fail(f"Unsupported PYTEST_SHARD_TARGET_FILE template: {target_path}")


def _runtime_descriptors_or_skip() -> tuple[RuntimeDescriptor, ...]:
    try:
        descriptors = iter_runtime_descriptors()
    except (FileNotFoundError, PermissionError) as error:
        pytest.skip(f"runtime catalog unavailable: {error}")
    if not descriptors:
        pytest.skip("runtime catalog contains no runtime descriptors")
    return descriptors


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
    assert tests_conftest._is_default_full_suite_invocation(["-q"]) is True
    assert tests_conftest._is_default_full_suite_invocation(["--maxfail=1", "tests", "-q"]) is True
    assert tests_conftest._is_default_full_suite_invocation(["tests/test_runtime_cli.py"]) is False
    assert tests_conftest._full_suite_auto_worker_count(cpu_count=16, ci_shard_total=ci_shards) == ci_shards
    assert tests_conftest._full_suite_auto_worker_count(cpu_count=8, ci_shard_total=ci_shards) == 16

    config = SimpleNamespace(
        args=["tests"],
        option=SimpleNamespace(numprocesses="auto", maxprocesses=None),
    )
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    monkeypatch.delenv(tests_conftest._CHILD_PYTEST_XDIST_DISABLE_ENV, raising=False)
    monkeypatch.setattr(tests_conftest.os, "cpu_count", lambda: 16)
    assert tests_conftest.pytest_xdist_auto_num_workers(config) == ci_shards

    config.option.maxprocesses = 12
    assert tests_conftest.pytest_xdist_auto_num_workers(config) == 12

    config.args = ["tests/test_runtime_cli.py"]
    assert tests_conftest.pytest_xdist_auto_num_workers(config) is None

    config.args = ["--maxfail=1", "tests", "-q"]
    assert tests_conftest.pytest_xdist_auto_num_workers(config) == 12

    monkeypatch.setenv(tests_conftest._CHILD_PYTEST_XDIST_DISABLE_ENV, "1")
    config.args = ["tests"]
    config.option.maxprocesses = None
    assert tests_conftest.pytest_xdist_auto_num_workers(config) == 0


def test_default_collection_matches_all_checked_in_test_files() -> None:
    repo_root = _repo_root()
    all_relpaths = all_test_relpaths(tests_root=repo_root / "tests")
    collected_counts = collected_test_counts_by_file(repo_root=repo_root)

    assert tuple(sorted(collected_counts)) == all_relpaths
    assert all(count > 0 for count in collected_counts.values())


def test_ci_pytest_job_waits_for_smoke_and_one_shot_planning_while_keeping_local_xdist_defaults() -> None:
    repo_root = _repo_root()
    workflow = _workflow_data()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_job = _workflow_job(workflow, "pytest")
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)
    needs = _job_needs(pytest_job)

    assert {"smoke", "plan-shards"} <= set(needs)
    assert "pytest" not in needs
    assert strategy["fail-fast"] is False
    assert pytest_job["timeout-minutes"] == CI_PYTEST_JOB_TIMEOUT_MINUTES

    pytest_ini_options = pyproject["tool"]["pytest"]["ini_options"]
    assert pytest_ini_options["addopts"] == "-n auto --dist=worksteal"
    dependency_groups = pyproject["dependency-groups"]
    dev_deps = dependency_groups["dev"]
    assert "pytest-xdist>=3.8.0" in dev_deps


def test_ci_pytest_job_downloads_preplanned_shard_targets_instead_of_resolving_them_per_shard() -> None:
    workflow = _workflow_data()
    plan_job = _workflow_job(workflow, "plan-shards")
    plan_steps = _workflow_job_steps(workflow, "plan-shards")
    pytest_steps = _workflow_job_steps(workflow, "pytest")
    pytest_step_names = [str(step.get("name", "")) for step in pytest_steps]
    pytest_shard_command = str(_step_by_name(pytest_steps, CI_PYTEST_SHARD_STEP_NAME).get("run", ""))

    plan_strategy = plan_job.get("strategy")
    if isinstance(plan_strategy, dict):
        assert "matrix" not in plan_strategy
    assert _steps_using_action(plan_steps, "actions/upload-artifact@")
    assert _steps_using_action(pytest_steps, "actions/download-artifact@")
    assert CI_SHARD_TARGET_RESOLVER_STEP_NAME not in pytest_step_names
    assert "PYTEST_SHARD_TARGET_FILE" in pytest_shard_command
    assert "write_ci_shard_targets_file" not in pytest_shard_command
    assert "select_ci_shard_targets" not in pytest_shard_command
    assert "plan_category_ci_shards" not in pytest_shard_command
    assert "--collect-only" not in pytest_shard_command


def test_ci_pytest_job_consumes_canonical_shard_target_filenames_for_every_matrix_row() -> None:
    workflow = _workflow_data()
    matrix_include = _pytest_matrix_include(workflow)
    pytest_step = _step_by_name(_workflow_job_steps(workflow, "pytest"), CI_PYTEST_SHARD_STEP_NAME)
    env = pytest_step.get("env")
    assert isinstance(env, dict)
    target_path = str(env["PYTEST_SHARD_TARGET_FILE"])

    actual_filenames = {
        (
            str(entry["category"]),
            int(entry["shard_index"]),
            int(entry["shard_total"]),
        ): _render_pytest_shard_target_filename(entry, target_path)
        for entry in matrix_include
    }
    expected_filenames = {
        (
            spec.category,
            spec.shard_index,
            spec.shard_total,
        ): ci_shard_target_filename(
            category=spec.category,
            shard_index=spec.shard_index,
            shard_total=spec.shard_total,
        )
        for spec in ci_shard_specs()
    }

    assert actual_filenames == expected_filenames
    assert actual_filenames[("mcp", 1, 1)] == "mcp.txt"


def test_hotspot_split_targets_exist_and_request_multiple_parts() -> None:
    all_relpaths = set(all_test_relpaths(tests_root=_repo_root() / "tests"))
    split_categories = {category_for_test_relpath(rel_path) for rel_path in CI_HOT_TEST_FILE_SPLITS}

    assert set(CI_HOT_TEST_FILE_SPLITS) <= all_relpaths
    assert all(split_count > 1 for split_count in CI_HOT_TEST_FILE_SPLITS.values())
    assert all(CI_CATEGORY_SHARD_COUNTS[category] > 1 for category in split_categories)


def test_single_shard_categories_keep_whole_file_targets() -> None:
    for category, shard_total in CI_CATEGORY_SHARD_COUNTS.items():
        if shard_total != 1:
            continue
        rel_path = f"{category}/test_policy_guard.py" if category != "root" else "test_policy_guard.py"
        inventory = {
            rel_path: tuple(f"tests/{rel_path}::test_{index}" for index in range(6)),
        }

        assert select_ci_shard_targets(
            category=category,
            shard_index=1,
            shard_total=shard_total,
            inventory=inventory,
        ) == (f"tests/{rel_path}",)


def test_ci_categories_represent_actual_test_domains() -> None:
    repo_root = _repo_root()
    all_relpaths = all_test_relpaths(tests_root=repo_root / "tests")
    observed_categories = {category_for_test_relpath(path) for path in all_relpaths}

    assert set(CI_CATEGORY_SHARD_COUNTS) <= observed_categories


def test_runtime_adapter_hotspot_splits_target_catalog_adapters_without_collection() -> None:
    splits = dict(CI_HOT_TEST_FILE_SPLITS)
    descriptors = _runtime_descriptors_or_skip()
    adapter_test_paths = {
        f"adapters/test_{descriptor.adapter_module}.py"
        for descriptor in descriptors
    }

    assert adapter_test_paths <= set(splits)
    assert all(splits[path] == 2 for path in adapter_test_paths)


def test_fast_priority_targets_stay_inside_three_minute_policy() -> None:
    all_targets = {f"tests/{rel_path}" for rel_path in all_test_relpaths(tests_root=_repo_root() / "tests")}
    target_files = {target.split("::", 1)[0] for target in CI_FAST_PRIORITY_TEST_TARGETS}

    assert CI_FAST_PRIORITY_TIMEOUT_MINUTES == CI_SMOKE_JOB_TIMEOUT_MINUTES == 3
    assert CI_FAST_PRIORITY_TEST_TARGETS == CI_SMOKE_TEST_TARGETS
    assert target_files <= all_targets
    assert all(target in CI_FAST_PRIORITY_TEST_TARGETS for target in CI_SMOKE_TEST_TARGETS)


def test_fast_priority_suite_total_test_count_stays_bounded() -> None:
    inventory = collected_test_inventory(repo_root=_repo_root())
    total_test_count = 0
    for target in CI_FAST_PRIORITY_TEST_TARGETS:
        if "::" in target:
            total_test_count += 1
            continue
        rel_path = target[len("tests/") :] if target.startswith("tests/") else target
        nodeids = inventory.get(rel_path)
        assert nodeids is not None, f"Fast priority target {target} is missing from collection inventory"
        total_test_count += len(nodeids)

    assert total_test_count <= CI_FAST_PRIORITY_TEST_COUNT_LIMIT, (
        f"Fast priority suite includes {total_test_count} collected tests, exceeding the {CI_FAST_PRIORITY_TEST_COUNT_LIMIT}-test limit."
    )


def test_hotspot_split_policy_covers_largest_collected_files_in_split_categories() -> None:
    counts_by_file = collected_test_counts_by_file(repo_root=_repo_root())
    split_eligible_counts = (
        (path, count)
        for path, count in counts_by_file.items()
        if CI_CATEGORY_SHARD_COUNTS[category_for_test_relpath(path)] > 1
    )
    largest_files = {
        rel_path
        for rel_path, _count in sorted(split_eligible_counts, key=lambda item: (-item[1], item[0]))[
            :CI_HOTSPOT_SPLIT_COVERAGE_MIN_TOP_FILES
        ]
    }

    assert largest_files <= set(CI_HOT_TEST_FILE_SPLITS)


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


def test_category_shards_never_empty() -> None:
    inventory = collected_test_inventory(repo_root=_repo_root())
    work_units = build_ci_work_units(inventory)

    for category, shard_total in CI_CATEGORY_SHARD_COUNTS.items():
        planned_shards = plan_category_ci_shards(category=category, work_units=work_units)
        assert len(planned_shards) == shard_total
        for shard_targets in planned_shards:
            assert shard_targets, f"{category} shard returned an empty target list"


def test_pytest_job_timeout_parity() -> None:
    workflow = _workflow_data()
    pytest_job = workflow["jobs"]["pytest"]
    assert isinstance(pytest_job, dict)
    assert pytest_job["timeout-minutes"] == CI_PYTEST_JOB_TIMEOUT_MINUTES
