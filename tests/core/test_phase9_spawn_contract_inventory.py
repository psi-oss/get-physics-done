"""Phase 9 spawn-contract inventory for canonical workflow handoffs."""

from __future__ import annotations

from pathlib import Path

from gpd.registry import _parse_spawn_contracts

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
EXPECTED_WORKFLOW_COUNTS = {
    "execute-phase.md": 1,
    "map-research.md": 4,
    "new-milestone.md": 3,
    "new-project.md": 7,
    "parameter-sweep.md": 1,
    "research-phase.md": 2,
    "verify-work.md": 1,
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_spawn_contracts(text: str) -> list[dict[str, object]]:
    return list(_parse_spawn_contracts(text, owner_name="workflow"))


def _assert_contract_shape(contract: dict[str, object], *, workflow_name: str, index: int) -> None:
    write_scope = contract.get("write_scope")
    expected_artifacts = contract.get("expected_artifacts")
    shared_state_policy = contract.get("shared_state_policy")

    assert isinstance(write_scope, dict), f"{workflow_name} block {index} missing write_scope mapping"
    assert isinstance(expected_artifacts, list), f"{workflow_name} block {index} missing expected_artifacts list"
    assert isinstance(shared_state_policy, str), f"{workflow_name} block {index} missing shared_state_policy"
    assert write_scope.get("mode") in {"scoped_write", "direct"}
    assert isinstance(write_scope.get("allowed_paths"), list)
    assert write_scope["allowed_paths"], f"{workflow_name} block {index} has no allowed_paths"
    assert expected_artifacts, f"{workflow_name} block {index} has no expected_artifacts"
    assert all(isinstance(path, str) and path.strip() for path in write_scope["allowed_paths"])
    assert all(isinstance(path, str) and path.strip() for path in expected_artifacts)
    if shared_state_policy == "return_only":
        assert write_scope["mode"] == "scoped_write"
    elif shared_state_policy != "direct":  # pragma: no cover - defensive assertion path
        raise AssertionError(f"{workflow_name} block {index} has invalid shared_state_policy {shared_state_policy!r}")


def test_spawn_contract_inventory_is_exhaustive_and_canonical() -> None:
    actual_files = {
        path.name for path in WORKFLOWS_DIR.glob("*.md") if "<spawn_contract>" in _read(path)
    }

    assert actual_files == set(EXPECTED_WORKFLOW_COUNTS)


def test_spawn_contract_blocks_are_structural_and_count_stable() -> None:
    for workflow_name, expected_count in EXPECTED_WORKFLOW_COUNTS.items():
        path = WORKFLOWS_DIR / workflow_name
        contracts = _extract_spawn_contracts(_read(path))

        assert len(contracts) == expected_count, workflow_name
        for index, contract in enumerate(contracts, start=1):
            _assert_contract_shape(contract, workflow_name=workflow_name, index=index)
