from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from tests.ci_sharding import (
    CI_CATEGORY_SHARD_COUNTS,
    CI_FAST_PRIORITY_TEST_TARGETS,
    CI_FAST_PRIORITY_TIMEOUT_MINUTES,
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
    CI_SHARD_TARGET_RESOLVER_STEP_NAME,
    CI_TOTAL_SHARD_COUNT_TARGET,
    build_ci_work_units,
    ci_smoke_pytest_command,
    ci_shard_specs,
    collected_test_counts_by_file,
    collected_test_inventory,
    expand_ci_targets_to_nodeids,
    select_ci_shard_targets,
    write_ci_shard_targets_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

SMOKE_TARGET_TOTAL_LIMIT = 160
EXPECTED_SMOKE_TARGETS = tuple(CI_SMOKE_TEST_TARGETS)
HOT_FILE_MAX_TESTS_PER_GROUP = 95


def _direct_test_count(rel_path: str) -> int:
    if "::" in rel_path:
        rel_path, nodeid = rel_path.split("::", 1)
        test_name = nodeid.split("[")[0].split("::")[-1]
        return int(f"def {test_name}(" in (REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8").count("\ndef test_")


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


def _run_steps_by_name(steps: list[dict[str, object]]) -> dict[str, str]:
    return {str(step.get("name", "")): str(step.get("run", "")) for step in steps if "run" in step}


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
    resolve_targets_command = pytest_run_steps[CI_SHARD_TARGET_RESOLVER_STEP_NAME]
    pytest_shard_command = pytest_run_steps[CI_PYTEST_SHARD_STEP_NAME]
    assert "from tests.ci_sharding import write_ci_shard_targets_file" in resolve_targets_command
    assert all(
        env_name in resolve_targets_command
        for env_name in ("PYTEST_CATEGORY", "PYTEST_SHARD_INDEX", "PYTEST_SHARD_TARGET_FILE", "PYTEST_SHARD_TOTAL")
    )
    assert 'mapfile -t PYTEST_TARGETS < "$PYTEST_SHARD_TARGET_FILE"' in pytest_shard_command
    assert _run_command_contains_tokens(pytest_shard_command, CI_PYTEST_SHARD_COMMAND_TOKENS)
    assert '"${PYTEST_TARGETS[@]}"' in pytest_shard_command
    assert pytest_steps.index(_step_by_name(pytest_steps, CI_SHARD_TARGET_RESOLVER_STEP_NAME)) < pytest_steps.index(
        _step_by_name(pytest_steps, CI_PYTEST_SHARD_STEP_NAME)
    )
    assert _step_by_name(pytest_steps, CI_PYTEST_SHARD_STEP_NAME)["run"] == pytest_shard_command
    node_step = _step_by_name(pytest_steps, "Set up Node.js")
    assert node_step["uses"] == "actions/setup-node@v6"
    assert node_step["with"]["node-version"] == "20"
    assert 'addopts = ""' in pyproject
    assert 'pytest-xdist>=3.8.0' in pyproject


def test_pytest_job_validates_runtime_catalog_schema_step() -> None:
    workflow = _workflow_data()
    steps = _job_steps(workflow, "pytest")

    guard_steps = [step for step in steps if step.get("name") == CI_RUNTIME_CATALOG_SCHEMA_STEP_NAME]
    assert guard_steps, "Pytest job must include a runtime catalog validation step"
    guard_step = guard_steps[0]
    guard_run = str(guard_step.get("run", ""))
    assert guard_run == CI_RUNTIME_CATALOG_SCHEMA_COMMAND


def test_ci_workflow_runs_fast_release_package_smoke_lane_before_full_shards() -> None:
    workflow = _workflow_data()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    smoke_job = jobs["smoke"]
    assert isinstance(smoke_job, dict)

    smoke_steps = _job_steps(workflow, "smoke")
    smoke_run_steps = _run_steps_by_name(smoke_steps)

    assert smoke_job["timeout-minutes"] == CI_SMOKE_JOB_TIMEOUT_MINUTES
    assert smoke_job.get("needs") is None
    node_step = _step_by_name(smoke_steps, "Set up Node.js")
    assert node_step["uses"] == "actions/setup-node@v6"
    assert node_step["with"]["node-version"] == "20"
    smoke_command = smoke_run_steps[CI_SMOKE_PYTEST_STEP_NAME]
    assert smoke_command == ci_smoke_pytest_command()


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


def test_fast_smoke_job_timeout_matches_fast_priority_timeout_constant() -> None:
    workflow = _workflow_data()
    smoke_job = workflow["jobs"]["smoke"]
    assert isinstance(smoke_job, dict)
    assert smoke_job["timeout-minutes"] == CI_FAST_PRIORITY_TIMEOUT_MINUTES


def test_fast_priority_smoke_targets_follow_ci_fast_priority_list() -> None:
    smoke_command = _run_steps_by_name(_job_steps(_workflow_data(), "smoke"))[CI_SMOKE_PYTEST_STEP_NAME]
    smoke_targets = _pytest_command_targets(smoke_command)

    assert smoke_targets == tuple(CI_FAST_PRIORITY_TEST_TARGETS)


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
    smoke_command = "uv run pytest -q " + " ".join(CI_SMOKE_TEST_TARGETS)

    assert "Default `uv run pytest` runs the full checked-in suite" in tests_readme
    assert "`uv run pytest -q` does the same with quieter output" in tests_readme
    assert "Install `pytest-xdist` to opt into parallel runs" in tests_readme
    assert "raises xdist auto-worker selection toward the current CI shard fanout" in tests_readme
    assert "use `uv run pytest -n auto --dist=worksteal`" in tests_readme
    assert "focused local contract-visibility smoke pass" in tests_readme
    assert "separate CI release/package smoke lane stays under 3 minutes" in tests_readme
    assert smoke_command in tests_readme
    assert "CI shards add `--durations=20 --durations-min=0`" in tests_readme
    assert "GitHub Actions workflow runs that same full suite as category-named runtime-informed shards" in tests_readme
    assert "`root 1/9` through `root 9/9`, `adapters 1/2` through `adapters 2/2`, `hooks 1/2` through `hooks 2/2`, `mcp`, and `core 1/5` through `core 5/5`" in tests_readme
    assert "boosts root modules that have been slow on GitHub Actions" in tests_readme
    assert "splits known hotspot modules such as `tests/test_runtime_cli.py`, `tests/test_registry.py`, `tests/test_update_workflow.py`, and `tests/hooks/test_runtime_detect.py`" in tests_readme
    assert "greedily rebalances those work units inside each category" in tests_readme


def test_ci_release_package_smoke_targets_stay_within_budget() -> None:
    """Approximate smoke-target size so the release/package lane finishes under 3 minutes."""
    assert tuple(CI_SMOKE_TEST_TARGETS) == EXPECTED_SMOKE_TARGETS
    total_tests = sum(_direct_test_count(target) for target in CI_SMOKE_TEST_TARGETS)
    assert total_tests <= SMOKE_TARGET_TOTAL_LIMIT


def test_ci_hot_file_splits_keep_groups_under_guardrail() -> None:
    """Ensure each hot split can be contained within the 3-minute per-group target."""
    for rel_path, split_parts in CI_HOT_TEST_FILE_SPLITS.items():
        if rel_path.startswith("adapters/test_"):
            continue

        max_capacity = split_parts * HOT_FILE_MAX_TESTS_PER_GROUP
        expected_count = _direct_test_count(f"tests/{rel_path}")
        assert max_capacity >= expected_count
