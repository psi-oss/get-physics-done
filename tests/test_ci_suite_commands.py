from __future__ import annotations

from pathlib import Path

import yaml

from tests.ci_sharding import (
    CI_CATEGORY_SHARD_COUNTS,
    CI_HOT_TEST_FILE_SPLITS,
    CI_HOT_TEST_FILE_WEIGHT_MULTIPLIERS,
    CI_MAX_SHARD_COUNT_TARGET,
    CI_SMOKE_JOB_TIMEOUT_MINUTES,
    CI_SMOKE_TEST_TARGETS,
    CI_TOTAL_SHARD_COUNT_TARGET,
    build_ci_work_units,
    ci_shard_specs,
    expand_ci_targets_to_nodeids,
    select_ci_shard_targets,
    write_ci_shard_targets_file,
)

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
    assert len(matrix_include) == CI_TOTAL_SHARD_COUNT_TARGET
    assert len(matrix_include) <= CI_MAX_SHARD_COUNT_TARGET

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
    assert 'uv run pytest -q --durations=20 --durations-min=0 "${PYTEST_TARGETS[@]}"' in pytest_shard_command
    assert pytest_steps[-1]["name"] == "Run pytest shard"
    assert pytest_steps[-1]["run"] == pytest_shard_command
    assert pytest_steps[2]["uses"] == "actions/setup-node@v6"
    assert pytest_steps[2]["with"]["node-version"] == "20"
    assert 'addopts = ""' in pyproject
    assert 'pytest-xdist>=3.8.0' in pyproject


def test_ci_workflow_runs_fast_release_package_smoke_lane_before_full_shards() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    smoke_job = jobs["smoke"]
    assert isinstance(smoke_job, dict)

    smoke_steps = _job_steps(workflow, "smoke")
    smoke_run_steps = {
        str(step.get("name", "")): str(step.get("run", ""))
        for step in smoke_steps
        if "run" in step
    }

    assert smoke_job["timeout-minutes"] == CI_SMOKE_JOB_TIMEOUT_MINUTES
    assert smoke_job.get("needs") is None
    assert smoke_steps[2]["uses"] == "actions/setup-node@v6"
    assert smoke_steps[2]["with"]["node-version"] == "20"
    assert smoke_run_steps["Run release/package smoke tests"] == "uv run pytest -q " + " ".join(CI_SMOKE_TEST_TARGETS)


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


def test_publish_release_runs_release_workflow_inside_uv_environment() -> None:
    workflow_text = (REPO_ROOT / ".github" / "workflows" / "publish-release.yml").read_text(encoding="utf-8")
    invocations = [
        line.strip()
        for line in workflow_text.splitlines()
        if "scripts/release_workflow.py" in line and not line.lstrip().startswith("#")
    ]

    assert invocations
    assert all("uv run python scripts/release_workflow.py" in invocation for invocation in invocations)


def test_tests_readme_documents_default_full_suite_and_category_named_runtime_informed_ci_shards() -> None:
    tests_readme = (REPO_ROOT / "tests" / "README.md").read_text(encoding="utf-8")

    assert "Default `uv run pytest` runs the full checked-in suite" in tests_readme
    assert "`uv run pytest -q` does the same with quieter output" in tests_readme
    assert "Install `pytest-xdist` to opt into parallel runs" in tests_readme
    assert "raises xdist auto-worker selection toward the current CI shard fanout" in tests_readme
    assert "use `uv run pytest -n auto --dist=worksteal`" in tests_readme
    assert "focused local contract-visibility smoke pass" in tests_readme
    assert "separate CI release/package smoke lane stays under 3 minutes" in tests_readme
    assert "uv run pytest -q tests/test_release_consistency.py tests/test_ci_suite_commands.py tests/test_repo_hygiene.py tests/test_schema_registry_ownership_note.py tests/adapters/test_runtime_catalog.py" in tests_readme
    assert "CI shards add `--durations=20 --durations-min=0`" in tests_readme
    assert "GitHub Actions workflow runs that same full suite as category-named runtime-informed shards" in tests_readme
    assert "`root 1/9` through `root 9/9`, `adapters 1/2` through `adapters 2/2`, `hooks 1/2` through `hooks 2/2`, `mcp`, and `core 1/5` through `core 5/5`" in tests_readme
    assert "boosts root modules that have been slow on GitHub Actions" in tests_readme
    assert "splits known hotspot modules such as `tests/test_runtime_cli.py`, `tests/test_registry.py`, `tests/test_update_workflow.py`, and `tests/hooks/test_runtime_detect.py`" in tests_readme
    assert "greedily rebalances those work units inside each category" in tests_readme
