from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from tests.ci_sharding import (
    CI_CATEGORY_SHARD_COUNTS,
    CI_HOT_TEST_FILE_SPLITS,
    CI_HOT_TEST_FILE_WEIGHT_MULTIPLIERS,
    CI_MAX_SHARD_COUNT_TARGET,
    CI_PYTEST_SHARD_COMMAND_TOKENS,
    CI_PYTEST_SHARD_STEP_NAME,
    CI_RUNTIME_CATALOG_SCHEMA_COMMAND,
    CI_RUNTIME_CATALOG_SCHEMA_STEP_NAME,
    CI_SMOKE_JOB_TIMEOUT_MINUTES,
    CI_SMOKE_PYTEST_STEP_NAME,
    CI_SMOKE_TEST_TARGETS,
    CI_TOTAL_SHARD_COUNT_TARGET,
    build_ci_work_units,
    ci_shard_specs,
    ci_smoke_pytest_command,
    collected_test_counts_by_file,
    collected_test_inventory,
    expand_ci_targets_to_nodeids,
    select_ci_shard_targets,
    write_ci_shard_targets_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _workflow_data(filename: str = "test.yml") -> dict[str, object]:
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / filename).read_text(encoding="utf-8"))


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


def _job_needs(job: dict[str, object]) -> tuple[str, ...]:
    needs = job.get("needs")
    if needs is None:
        return ()
    if isinstance(needs, str):
        return (needs,)
    assert isinstance(needs, list)
    return tuple(str(name) for name in needs)


def _step_runs_uv(step: dict[str, object]) -> bool:
    run = step.get("run")
    if not isinstance(run, str):
        return False
    return any(
        line.lstrip().startswith("uv ")
        for line in run.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _pytest_command_targets(command: str) -> tuple[str, ...]:
    tokens = command.split()
    assert tuple(tokens[:4]) == ("uv", "run", "pytest", "-q")
    return tuple(tokens[4:])


def _run_command_contains_tokens(command: str, tokens: tuple[str, ...]) -> bool:
    return all(token in command.split() for token in tokens)


def _step_by_name(steps: list[dict[str, object]], name: str) -> dict[str, object]:
    matches = [step for step in steps if step.get("name") == name]
    assert len(matches) == 1
    return matches[0]


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
    pytest_run_steps = _run_steps_by_name(pytest_steps)
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

    pytest_job = jobs["pytest"]
    assert isinstance(pytest_job, dict)
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)
    assert "smoke" in _job_needs(pytest_job)
    assert strategy["fail-fast"] is False
    assert actual_shards == expected_shards
    assert len(matrix_include) == sum(CI_CATEGORY_SHARD_COUNTS.values())
    assert len(matrix_include) == CI_TOTAL_SHARD_COUNT_TARGET
    assert len(matrix_include) <= CI_MAX_SHARD_COUNT_TARGET

    # trigger-staging-rebuild moved to staging-rebuild.yml (workflow_run trigger)
    # to avoid showing as a skipped check on PRs.
    assert "trigger-staging-rebuild" not in jobs

    assert "Set up Node.js" in pytest_step_names
    assert pytest_step_names.index("Set up Node.js") < pytest_step_names.index("Install dependencies")
    pytest_shard_command = pytest_run_steps[CI_PYTEST_SHARD_STEP_NAME]
    assert 'mapfile -t PYTEST_TARGETS < "$PYTEST_SHARD_TARGET_FILE"' in pytest_shard_command
    assert _run_command_contains_tokens(pytest_shard_command, CI_PYTEST_SHARD_COMMAND_TOKENS)
    assert '"${PYTEST_TARGETS[@]}"' in pytest_shard_command
    assert _step_by_name(pytest_steps, CI_PYTEST_SHARD_STEP_NAME)["run"] == pytest_shard_command
    node_step = _step_by_name(pytest_steps, "Set up Node.js")
    assert node_step["uses"] == "actions/setup-node@v6"
    assert node_step["with"]["node-version"] == "20"
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert 'pytest-xdist>=3.8.0' in pyproject


def test_ci_workflow_runs_runtime_catalog_schema_validation_once() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    pytest_steps = _job_steps(workflow, "pytest")

    guard_steps = [
        (str(job_name), step)
        for job_name in jobs
        for step in _job_steps(workflow, str(job_name))
        if step.get("name") == CI_RUNTIME_CATALOG_SCHEMA_STEP_NAME
    ]

    assert len(guard_steps) == 1, "Workflow should validate the runtime catalog schema exactly once"
    guard_job_name, guard_step = guard_steps[0]
    assert guard_step not in pytest_steps
    guard_run = str(guard_step.get("run", ""))
    assert guard_run == CI_RUNTIME_CATALOG_SCHEMA_COMMAND
    assert guard_job_name != "pytest"


def test_ci_workflow_runs_fast_release_package_smoke_lane_with_expected_step_order() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    smoke_job = jobs["smoke"]
    assert isinstance(smoke_job, dict)

    smoke_steps = _job_steps(workflow, "smoke")
    smoke_run_steps = _run_steps_by_name(smoke_steps)

    assert smoke_job["timeout-minutes"] == CI_SMOKE_JOB_TIMEOUT_MINUTES
    node_step = _step_by_name(smoke_steps, "Set up Node.js")
    assert node_step["uses"] == "actions/setup-node@v6"
    assert node_step["with"]["node-version"] == "20"
    smoke_command = smoke_run_steps[CI_SMOKE_PYTEST_STEP_NAME]
    assert smoke_command == ci_smoke_pytest_command()
    smoke_step_names = [str(step.get("name", "")) for step in smoke_steps]
    dry_run_index = smoke_step_names.index("Smoke npm pack dry run")
    manifest_index = smoke_step_names.index("Verify npm pack manifest")
    pytest_index = smoke_step_names.index(CI_SMOKE_PYTEST_STEP_NAME)
    assert dry_run_index < manifest_index < pytest_index


def test_ci_release_package_smoke_lane_uses_only_explicit_fast_targets() -> None:
    workflow = _workflow_data()
    smoke_command = _run_steps_by_name(_job_steps(workflow, "smoke"))[CI_SMOKE_PYTEST_STEP_NAME]
    smoke_targets = _pytest_command_targets(smoke_command)

    assert smoke_targets == tuple(CI_SMOKE_TEST_TARGETS)
    assert smoke_targets
    assert all(target.startswith("tests/") for target in smoke_targets)
    assert all(target not in {"tests", "tests/"} for target in smoke_targets)
    assert all("*" not in target for target in smoke_targets)
    assert all(("::" in target) or Path(target).suffix == ".py" for target in smoke_targets)


def test_ci_shard_selection_uses_supplied_static_inventory_without_collect_only(monkeypatch) -> None:
    def fail_collect_only(*, repo_root: Path | None = None) -> dict[str, tuple[str, ...]]:
        raise AssertionError("collect-only should not run when inventory is supplied")

    monkeypatch.setattr("tests.ci_sharding.collected_test_inventory", fail_collect_only)

    inventory = {
        "test_runtime_cli.py": tuple(f"tests/test_runtime_cli.py::test_{index}" for index in range(12)),
        "test_release_consistency.py": ("tests/test_release_consistency.py::test_release",),
        "core/test_cli.py": tuple(f"tests/core/test_cli.py::test_{index}" for index in range(6)),
    }

    root_targets = select_ci_shard_targets(
        category="root",
        shard_index=1,
        shard_total=CI_CATEGORY_SHARD_COUNTS["root"],
        inventory=inventory,
    )
    second_root_targets = select_ci_shard_targets(
        category="root",
        shard_index=2,
        shard_total=CI_CATEGORY_SHARD_COUNTS["root"],
        inventory=inventory,
    )

    assert root_targets
    assert second_root_targets
    assert all(target.startswith("tests/test_") for target in root_targets)
    assert all(target.startswith("tests/test_") for target in second_root_targets)
    assert set(root_targets).isdisjoint(second_root_targets)

    planned_root_nodeids = []
    for shard_index in range(1, CI_CATEGORY_SHARD_COUNTS["root"] + 1):
        planned_root_nodeids.extend(
            expand_ci_targets_to_nodeids(
                select_ci_shard_targets(
                    category="root",
                    shard_index=shard_index,
                    shard_total=CI_CATEGORY_SHARD_COUNTS["root"],
                    inventory=inventory,
                ),
                inventory=inventory,
            )
        )

    expected_root_nodeids = tuple(
        nodeid
        for rel_path, nodeids in inventory.items()
        if rel_path.startswith("test_")
        for nodeid in nodeids
    )
    assert sorted(planned_root_nodeids) == sorted(expected_root_nodeids)
    assert len(planned_root_nodeids) == len(set(planned_root_nodeids))


def test_ci_sharding_constants_do_not_import_runtime_adapters() -> None:
    source = (REPO_ROOT / "tests" / "ci_sharding.py").read_text(encoding="utf-8")

    assert "from gpd.adapters import iter_adapters" not in source
    assert "iter_adapters()" not in source


def test_ci_hot_test_file_targets_exist_without_collect_only() -> None:
    configured_relpaths = set(CI_HOT_TEST_FILE_SPLITS) | set(CI_HOT_TEST_FILE_WEIGHT_MULTIPLIERS)

    missing = sorted(relpath for relpath in configured_relpaths if not (REPO_ROOT / "tests" / relpath).is_file())

    assert missing == []


def test_ci_sharding_rejects_unknown_categories() -> None:
    inventory = {"experimental/test_new.py": ("tests/experimental/test_new.py::test_new",)}

    try:
        select_ci_shard_targets(
            category="experimental",
            shard_index=1,
            shard_total=1,
            inventory=inventory,
        )
    except ValueError as error:
        assert "unknown CI pytest category" in str(error)
    else:
        raise AssertionError("unknown categories must fail closed")


def test_build_ci_work_units_ignores_empty_static_inventory_entries() -> None:
    work_units = build_ci_work_units(
        {
            "test_empty.py": (),
            "test_release_consistency.py": ("tests/test_release_consistency.py::test_release",),
        }
    )

    assert [unit.label for unit in work_units] == ["test_release_consistency.py"]


def test_write_ci_shard_targets_file_accepts_static_inventory(tmp_path: Path, monkeypatch) -> None:
    def fail_collect_only(*, repo_root: Path | None = None) -> dict[str, tuple[str, ...]]:
        raise AssertionError("collect-only should not run when inventory is supplied")

    monkeypatch.setattr("tests.ci_sharding.collected_test_inventory", fail_collect_only)
    target_file = tmp_path / "pytest-targets.txt"
    inventory = {
        "adapters/test_codex.py": (
            "tests/adapters/test_codex.py::test_a",
            "tests/adapters/test_codex.py::test_b",
        ),
    }

    targets = write_ci_shard_targets_file(
        target_file=target_file,
        category="adapters",
        shard_index=1,
        shard_total=CI_CATEGORY_SHARD_COUNTS["adapters"],
        inventory=inventory,
    )

    assert targets == ("tests/adapters/test_codex.py::test_a",)
    assert target_file.read_text(encoding="utf-8") == "tests/adapters/test_codex.py::test_a\n"


def test_collected_inventory_cache_prevents_duplicate_collection(monkeypatch, tmp_path: Path) -> None:
    call_count: list[int] = []

    def fake_run(*args, **kwargs):
        call_count.append(1)
        return SimpleNamespace(stdout="tests/test_cache_dummy.py::test_one\n", returncode=0)

    monkeypatch.setattr("tests.ci_sharding.subprocess.run", fake_run)

    inventory = collected_test_inventory(repo_root=tmp_path)
    counts = collected_test_counts_by_file(repo_root=tmp_path)

    assert len(call_count) == 1
    assert inventory == {"test_cache_dummy.py": ("tests/test_cache_dummy.py::test_one",)}
    assert counts == {"test_cache_dummy.py": 1}


def test_collected_inventory_collect_only_uses_managed_python(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_run(args, **kwargs):
        calls.append(tuple(args))
        return SimpleNamespace(stdout="tests/test_uv_dummy.py::test_one\n", returncode=0)

    monkeypatch.setattr("tests.ci_sharding.subprocess.run", fake_run)

    assert collected_test_inventory(repo_root=tmp_path) == {
        "test_uv_dummy.py": ("tests/test_uv_dummy.py::test_one",)
    }
    assert calls[0][-5:] == ("tests/", "--collect-only", "-q", "-n", "0")
    assert calls[0][:3] == ("uv", "run", "pytest") or calls[0][1:3] == ("-m", "pytest")


def test_publish_release_jobs_set_up_uv_before_uv_commands() -> None:
    workflow = _workflow_data("publish-release.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    for job_name in jobs:
        steps = _job_steps(workflow, str(job_name))
        uv_setup_indices = [
            index for index, step in enumerate(steps) if step.get("uses") == "astral-sh/setup-uv@v7"
        ]
        uv_command_indices = [index for index, step in enumerate(steps) if _step_runs_uv(step)]

        if not uv_command_indices:
            continue

        assert uv_setup_indices, f"Job {job_name} uses uv but never sets it up in that same job"
        for uv_index in uv_command_indices:
            assert any(setup_index < uv_index for setup_index in uv_setup_indices), (
                f"Job {job_name} uses uv before running astral-sh/setup-uv@v7"
            )
