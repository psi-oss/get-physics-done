"""Phase 9 spawn-contract inventory for canonical workflow handoffs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gpd.registry import _parse_spawn_contracts

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
EXPECTED_WORKFLOW_COUNTS = {
    "derive-equation.md": 1,
    "execute-phase.md": 2,
    "literature-review.md": 2,
    "map-research.md": 4,
    "new-milestone.md": 3,
    "new-project.md": 7,
    "parameter-sweep.md": 1,
    "peer-review.md": 7,
    "plan-phase.md": 1,
    "research-phase.md": 1,
    "verify-work.md": 1,
    "verify-phase.md": 1,
}
EXPECTED_RAW_WORKFLOW_COUNTS = {
    **EXPECTED_WORKFLOW_COUNTS,
    "plan-phase.md": 2,
    "research-phase.md": 2,
}
SPAWN_CONTRACT_BLOCK_RE = re.compile(
    r"^[ \t]*<spawn_contract>[ \t]*$\n(?P<body>.*?)^[ \t]*</spawn_contract>[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
UNQUOTED_PLACEHOLDER_PATH_LIST_ITEM_RE = re.compile(r"^[ \t]*-[ \t]+\{[^}\n]+\}/", re.MULTILINE)


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
    actual_files = {path.name for path in WORKFLOWS_DIR.glob("*.md") if "<spawn_contract>" in _read(path)}

    assert actual_files == set(EXPECTED_WORKFLOW_COUNTS)


def test_spawn_contract_blocks_are_structural_and_count_stable() -> None:
    for workflow_name, expected_count in EXPECTED_WORKFLOW_COUNTS.items():
        path = WORKFLOWS_DIR / workflow_name
        contracts = _extract_spawn_contracts(_read(path))

        assert len(contracts) == expected_count, workflow_name
        for index, contract in enumerate(contracts, start=1):
            _assert_contract_shape(contract, workflow_name=workflow_name, index=index)


def test_spawn_contract_parser_accepts_strict_yaml_colons_and_flow_lists() -> None:
    contracts = _extract_spawn_contracts(
        """
<spawn_contract>
activation: "subject contains: explicit manuscript"
write_scope:
  mode: scoped_write
  allowed_paths: ["GPD/review/path:with-colon.md", "GPD/review/list-item.md"]
expected_artifacts:
  - "GPD/review/result:final.md"
shared_state_policy: return_only
</spawn_contract>
"""
    )

    assert contracts == [
        {
            "activation": "subject contains: explicit manuscript",
            "write_scope": {
                "mode": "scoped_write",
                "allowed_paths": ["GPD/review/path:with-colon.md", "GPD/review/list-item.md"],
            },
            "expected_artifacts": ["GPD/review/result:final.md"],
            "shared_state_policy": "return_only",
        }
    ]


def test_spawn_contract_parser_rejects_unquoted_placeholder_path_items() -> None:
    with pytest.raises(ValueError, match="unquoted placeholder path list item"):
        _extract_spawn_contracts(
            """
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - {phase_dir}/{phase_number}-RESEARCH.md
expected_artifacts:
  - {phase_dir}/{phase_number}-RESEARCH.md
shared_state_policy: return_only
</spawn_contract>
"""
        )


@pytest.mark.parametrize("field_path", ["write_scope.allowed_paths", "expected_artifacts"])
def test_spawn_contract_parser_rejects_blank_list_fields(field_path: str) -> None:
    allowed_paths = """
  allowed_paths:
"""
    expected_artifacts = "expected_artifacts: [GPD/review/result.md]"
    if field_path == "expected_artifacts":
        allowed_paths = "  allowed_paths: [GPD/review/result.md]\n"
        expected_artifacts = "expected_artifacts:"

    with pytest.raises(ValueError, match=rf"{re.escape(field_path)} must be a list"):
        _extract_spawn_contracts(
            f"""
<spawn_contract>
write_scope:
  mode: scoped_write
{allowed_paths}{expected_artifacts}
shared_state_policy: return_only
</spawn_contract>
"""
        )


def test_spawn_contract_source_blocks_quote_placeholder_path_items() -> None:
    offenders: list[str] = []
    for path in WORKFLOWS_DIR.glob("*.md"):
        for block_index, match in enumerate(SPAWN_CONTRACT_BLOCK_RE.finditer(_read(path)), start=1):
            if UNQUOTED_PLACEHOLDER_PATH_LIST_ITEM_RE.search(match.group("body")):
                offenders.append(f"{path.name} block {block_index}")

    assert offenders == []


def test_spawn_contract_source_blocks_preserve_distinct_handoff_sites() -> None:
    for workflow_name, expected_count in EXPECTED_RAW_WORKFLOW_COUNTS.items():
        text = _read(WORKFLOWS_DIR / workflow_name)
        assert text.count("<spawn_contract>") == expected_count, workflow_name
