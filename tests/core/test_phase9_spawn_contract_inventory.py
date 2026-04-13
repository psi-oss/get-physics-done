"""Phase 9 spawn-contract inventory for canonical workflow handoffs."""

from __future__ import annotations

from pathlib import Path

from gpd.registry import _parse_spawn_contracts

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
DELEGATION_REFERENCE_PATH = REPO_ROOT / "src/gpd/specs/references/orchestration/agent-delegation.md"
EXPECTED_WORKFLOW_COUNTS = {
    "execute-phase.md": 1,
    "literature-review.md": 2,
    "map-research.md": 4,
    "new-milestone.md": 3,
    "new-project.md": 7,
    "parameter-sweep.md": 1,
    "plan-phase.md": 2,
    "research-phase.md": 2,
    "verify-work.md": 1,
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_spawn_contracts(text: str, *, owner_name: str) -> list[dict[str, object]]:
    return list(_parse_spawn_contracts(text, owner_name=owner_name))


def _assert_contract_shape(contract: dict[str, object], *, owner_name: str, index: int) -> None:
    write_scope = contract.get("write_scope")
    expected_artifacts = contract.get("expected_artifacts")
    shared_state_policy = contract.get("shared_state_policy")

    assert isinstance(write_scope, dict), f"{owner_name} block {index} missing write_scope mapping"
    assert isinstance(expected_artifacts, list), f"{owner_name} block {index} missing expected_artifacts list"
    assert isinstance(shared_state_policy, str), f"{owner_name} block {index} missing shared_state_policy"
    assert write_scope.get("mode") in {"scoped_write", "direct"}
    assert isinstance(write_scope.get("allowed_paths"), list)
    assert write_scope["allowed_paths"], f"{owner_name} block {index} has no allowed_paths"
    assert expected_artifacts, f"{owner_name} block {index} has no expected_artifacts"
    assert all(isinstance(path, str) and path.strip() for path in write_scope["allowed_paths"])
    assert all(isinstance(path, str) and path.strip() for path in expected_artifacts)
    if shared_state_policy == "return_only":
        assert write_scope["mode"] == "scoped_write"
    elif shared_state_policy != "direct":  # pragma: no cover - defensive assertion path
        raise AssertionError(f"{owner_name} block {index} has invalid shared_state_policy {shared_state_policy!r}")


def test_spawn_contract_inventory_is_exhaustive_and_canonical() -> None:
    actual_files = {
        path.name for path in WORKFLOWS_DIR.glob("*.md") if "<spawn_contract>" in _read(path)
    }

    assert actual_files == set(EXPECTED_WORKFLOW_COUNTS)


def test_spawn_contract_blocks_are_structural_and_count_stable() -> None:
    for workflow_name, expected_count in EXPECTED_WORKFLOW_COUNTS.items():
        path = WORKFLOWS_DIR / workflow_name
        contracts = _extract_spawn_contracts(_read(path), owner_name=workflow_name)

        assert len(contracts) == expected_count, workflow_name
        for index, contract in enumerate(contracts, start=1):
            _assert_contract_shape(contract, owner_name=workflow_name, index=index)


def test_delegation_reference_spawn_contract_example_uses_canonical_nested_write_scope() -> None:
    assert DELEGATION_REFERENCE_PATH.is_file(), (
        "delegation reference must exist for the spawn-contract inventory ratifier: "
        f"{DELEGATION_REFERENCE_PATH.relative_to(REPO_ROOT)}"
    )
    text = _read(DELEGATION_REFERENCE_PATH)
    contracts = _extract_spawn_contracts(text, owner_name=DELEGATION_REFERENCE_PATH.name)

    assert len(contracts) == 1
    _assert_contract_shape(contracts[0], owner_name=DELEGATION_REFERENCE_PATH.name, index=1)
    assert contracts[0]["write_scope"]["mode"] == "scoped_write"
    assert contracts[0]["write_scope"]["allowed_paths"] == ["relative/path/owned/by/this/agent"]
    assert contracts[0]["expected_artifacts"] == ["relative/path/to/verify"]
    assert contracts[0]["shared_state_policy"] == "return_only"

    block = text.split("<spawn_contract>", 1)[1].split("</spawn_contract>", 1)[0]
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    assert lines[0] == "write_scope:"
