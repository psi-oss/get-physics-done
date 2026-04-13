from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tests.ci_sharding import (
    CI_CATEGORY_SHARD_COUNTS,
    CI_HOT_TEST_FILE_SPLITS,
    build_ci_work_units,
    category_for_test_relpath,
    ci_shard_specs,
    ci_shard_target_filename,
    collected_test_inventory,
    plan_all_ci_shard_targets,
    write_ci_shard_plan,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOT_FILE_GROUP_TEST_LIMIT = 95


def test_multi_shard_hot_file_splits_respect_guardrails() -> None:
    inventory = collected_test_inventory(repo_root=REPO_ROOT)

    for rel_path, split_parts in CI_HOT_TEST_FILE_SPLITS.items():
        category = category_for_test_relpath(rel_path)
        if CI_CATEGORY_SHARD_COUNTS[category] <= 1:
            continue
        nodeids = inventory.get(rel_path)
        if not nodeids:
            continue
        max_group_size = -(-len(nodeids) // split_parts)
        assert max_group_size <= HOT_FILE_GROUP_TEST_LIMIT, (
            f"{rel_path} splits into {split_parts} groups but would need {max_group_size} tests per group to cover "
            f"{len(nodeids)} nodeids, exceeding the {HOT_FILE_GROUP_TEST_LIMIT} guard"
        )


def test_single_shard_categories_do_not_split_hot_files() -> None:
    work_units = build_ci_work_units(
        {
            "mcp/test_servers.py": tuple(f"tests/mcp/test_servers.py::test_{index}" for index in range(12)),
        }
    )

    assert len(work_units) == 1
    assert work_units[0].label == "mcp/test_servers.py"
    assert work_units[0].targets == ("tests/mcp/test_servers.py",)


def test_write_ci_shard_plan_collects_inventory_once_and_writes_all_target_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    collect_lines = [
        *(f"tests/test_runtime_cli.py::test_{index}" for index in range(9)),
        *(f"tests/adapters/test_install_roundtrip.py::test_{index}" for index in range(3)),
        *(f"tests/hooks/test_notify.py::test_{index}" for index in range(3)),
        *(f"tests/mcp/test_servers.py::test_{index}" for index in range(4)),
        *(f"tests/core/test_cli.py::test_{index}" for index in range(5)),
        *(f"tests/core/test_context.py::test_{index}" for index in range(4)),
    ]
    call_count: list[int] = []

    def fake_run(args, **kwargs):
        call_count.append(1)
        return SimpleNamespace(stdout="\n".join(collect_lines) + "\n", returncode=0)

    monkeypatch.setattr("tests.ci_sharding.subprocess.run", fake_run)

    target_dir = tmp_path / "pytest-shards"
    written_files = write_ci_shard_plan(target_dir=target_dir, repo_root=tmp_path)
    planned_targets = plan_all_ci_shard_targets(repo_root=tmp_path)

    assert len(call_count) == 1
    assert tuple(written_files) == tuple(spec.slug for spec in ci_shard_specs())

    for spec in ci_shard_specs():
        target_file = target_dir / ci_shard_target_filename(
            category=spec.category,
            shard_index=spec.shard_index,
            shard_total=spec.shard_total,
        )
        assert written_files[spec.slug] == target_file
        assert target_file.read_text(encoding="utf-8") == "\n".join(planned_targets[spec.slug]) + "\n"
