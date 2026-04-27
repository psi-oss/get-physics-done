from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import tests.ci_sharding as ci_sharding
import tests.conftest as tests_conftest
from tests.ci_sharding import (
    CI_CATEGORY_SHARD_COUNTS,
    CI_HOT_TEST_FILE_SPLITS,
    all_test_relpaths,
    assert_ci_workflow_pytest_shard_policy,
    assert_tests_readme_documents_ci_shard_policy,
    build_ci_work_units,
    category_for_test_relpath,
    collected_test_inventory,
    expand_ci_targets_to_nodeids,
    plan_category_ci_shards,
    synthetic_test_inventory,
)


def _read(relpath: str) -> str:
    return (Path(__file__).resolve().parent / relpath).read_text(encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _workflow_data() -> dict[str, object]:
    return yaml.safe_load((_repo_root() / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


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


def test_root_conftest_honors_logical_xdist_mode_for_default_full_suite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ci_shards = sum(CI_CATEGORY_SHARD_COUNTS.values())
    config = SimpleNamespace(
        args=["tests"],
        option=SimpleNamespace(numprocesses="logical", maxprocesses=None),
    )

    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    monkeypatch.setattr(tests_conftest.os, "cpu_count", lambda: 16)

    assert tests_conftest.pytest_xdist_auto_num_workers(config) == ci_shards


def test_root_conftest_respects_xdist_auto_worker_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(
        args=["tests"],
        option=SimpleNamespace(numprocesses="auto", maxprocesses=None),
    )

    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "6")
    monkeypatch.setattr(tests_conftest.os, "cpu_count", lambda: 16)

    assert tests_conftest.pytest_xdist_auto_num_workers(config) is None


def test_default_collection_matches_all_checked_in_test_files() -> None:
    repo_root = _repo_root()
    all_relpaths = all_test_relpaths(tests_root=repo_root / "tests")
    inventory = collected_test_inventory(repo_root=repo_root)
    collected_counts = {rel_path: len(nodeids) for rel_path, nodeids in inventory.items()}
    live_categories = {category_for_test_relpath(relpath) for relpath in all_relpaths}
    unsharded_categories = live_categories - set(CI_CATEGORY_SHARD_COUNTS)

    assert tuple(sorted(collected_counts)) == all_relpaths
    assert all(count > 0 for count in collected_counts.values())
    assert not unsharded_categories, f"checked-in test categories missing CI shards: {sorted(unsharded_categories)}"
    _assert_ci_shards_cover_inventory_without_overlap_or_empty_shards(inventory)


def _assert_ci_shards_cover_inventory_without_overlap_or_empty_shards(
    inventory: dict[str, tuple[str, ...]],
) -> None:
    work_units = build_ci_work_units(inventory)
    all_nodeids = tuple(nodeid for nodeids in inventory.values() for nodeid in nodeids)
    flattened: list[str] = []

    for category, shard_total in CI_CATEGORY_SHARD_COUNTS.items():
        planned_shards = plan_category_ci_shards(category=category, inventory=inventory, work_units=work_units)
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
        assert all(shard_targets for shard_targets in planned_shards), f"{category} CI shard has no targets"
        assert sorted(category_flattened) == sorted(category_nodeids)
        assert len(category_flattened) == len(set(category_flattened))
        flattened.extend(category_flattened)

    assert sorted(flattened) == sorted(all_nodeids)
    assert len(flattened) == len(set(flattened))


def test_ci_collection_ignores_caller_pytest_addopts_and_disables_cache_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["env"] = kwargs["env"]
        captured["cwd"] = kwargs["cwd"]
        return SimpleNamespace(stdout="tests/test_sample.py::test_ok\n")

    monkeypatch.setenv("PYTEST_ADDOPTS", "-k no_tests --cache-clear")
    monkeypatch.setattr(ci_sharding.subprocess, "run", _fake_run)
    ci_sharding._collected_test_inventory_items.cache_clear()
    try:
        inventory = collected_test_inventory(repo_root=tmp_path)
    finally:
        ci_sharding._collected_test_inventory_items.cache_clear()

    assert inventory == {"test_sample.py": ("tests/test_sample.py::test_ok",)}
    env = captured["env"]
    assert isinstance(env, dict)
    assert "PYTEST_ADDOPTS" not in env
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert captured["args"] == [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "tests/",
        "--collect-only",
        "-q",
        "-n",
        "0",
    ]
    assert captured["cwd"] == tmp_path.resolve()


def test_ci_shard_target_resolution_collects_only_requested_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["cwd"] = kwargs["cwd"]
        return SimpleNamespace(
            stdout="\n".join(f"tests/core/test_sample.py::test_{index}" for index in range(5)) + "\n"
        )

    monkeypatch.setattr(ci_sharding.subprocess, "run", _fake_run)
    ci_sharding._collected_test_inventory_items.cache_clear()
    try:
        targets = ci_sharding.select_ci_shard_targets(
            category="core",
            shard_index=1,
            shard_total=CI_CATEGORY_SHARD_COUNTS["core"],
            repo_root=tmp_path,
        )
    finally:
        ci_sharding._collected_test_inventory_items.cache_clear()

    assert captured["args"] == [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "tests/core/",
        "--collect-only",
        "-q",
        "-n",
        "0",
    ]
    assert captured["cwd"] == tmp_path.resolve()
    assert targets == ("tests/core/test_sample.py",)


def test_ci_and_test_readme_document_default_full_suite_and_category_named_runtime_informed_shards() -> None:
    repo_root = _repo_root()
    workflow = _workflow_data()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    tests_readme = (repo_root / "tests" / "README.md").read_text(encoding="utf-8")
    assert_ci_workflow_pytest_shard_policy(workflow, pyproject_text=pyproject)
    assert_tests_readme_documents_ci_shard_policy(tests_readme)


def test_hotspot_files_are_split_into_multiple_work_units() -> None:
    inventory = synthetic_test_inventory()
    work_units = build_ci_work_units(inventory)

    for rel_path, split_count in CI_HOT_TEST_FILE_SPLITS.items():
        matching = [unit for unit in work_units if unit.label.startswith(rel_path)]
        assert len(matching) == split_count
        assert sum(len(unit.targets) for unit in matching) == len(inventory[rel_path])
    assert any(unit.label == "test_smoke.py" for unit in work_units)
    assert any(unit.label == "mcp/test_wolfram.py" for unit in work_units)


def test_synthetic_category_shard_layout_covers_every_nodeid_without_overlap() -> None:
    inventory = synthetic_test_inventory()
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


def test_synthetic_split_categories_keep_runtime_informed_weight_spread_tight() -> None:
    inventory = synthetic_test_inventory()
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

        assert max(shard_weights) - min(shard_weights) <= average_weight * 0.2
