from __future__ import annotations

from pathlib import Path

import pytest

from tests.ci_sharding import CI_HOT_TEST_FILE_SPLITS, collected_test_inventory, has_stable_cached_inventory

REPO_ROOT = Path(__file__).resolve().parent.parent
HOT_FILE_GROUP_TEST_LIMIT = 95


def test_hot_file_splits_with_cached_inventory_respect_guardrails() -> None:
    if not has_stable_cached_inventory(repo_root=REPO_ROOT):
        pytest.skip(
            "cached pytest collect inventory is required to guard hot split sizes without rerunning --collect-only"
        )

    inventory = collected_test_inventory(repo_root=REPO_ROOT)

    for rel_path, split_parts in CI_HOT_TEST_FILE_SPLITS.items():
        nodeids = inventory.get(rel_path)
        if not nodeids:
            continue
        max_group_size = -(-len(nodeids) // split_parts)
        assert max_group_size <= HOT_FILE_GROUP_TEST_LIMIT, (
            f"{rel_path} splits into {split_parts} groups but would need {max_group_size} tests per group to cover "
            f"{len(nodeids)} nodeids, exceeding the {HOT_FILE_GROUP_TEST_LIMIT} guard"
        )
