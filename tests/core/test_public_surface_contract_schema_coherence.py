"""Verify the public surface contract JSON aligns with the schema loader."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.public_surface_contract import (
    load_public_surface_contract,
    load_public_surface_contract_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "src/gpd/core/public_surface_contract.json"


def _load_contract_payload() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_matches_schema_top_level_keys() -> None:
    schema = load_public_surface_contract_schema()
    payload = _load_contract_payload()

    assert tuple(payload.keys()) == schema.top_level_keys
    assert payload.get("schema_version") == 1


def test_local_cli_bridge_ordered_commands_align_with_schema() -> None:
    schema = load_public_surface_contract_schema()
    payload = _load_contract_payload()
    bridge_payload = payload["local_cli_bridge"]

    assert tuple(bridge_payload["commands"]) == schema.local_cli_bridge_commands
    assert tuple(bridge_payload["named_commands"]) == schema.local_cli_named_command_keys


def test_loading_public_surface_contract_uses_current_files() -> None:
    contract = load_public_surface_contract()
    schema = load_public_surface_contract_schema()
    payload = _load_contract_payload()
    named_commands = payload["local_cli_bridge"]["named_commands"]
    expected_ordered_commands = tuple(named_commands[key] for key in schema.local_cli_named_command_keys)

    assert contract.local_cli_bridge.commands == schema.local_cli_bridge_commands
    assert contract.local_cli_bridge.named_commands.ordered() == expected_ordered_commands


def test_contract_sections_match_schema_keys() -> None:
    schema = load_public_surface_contract_schema()
    payload = _load_contract_payload()

    for section_name, expected_keys in schema.section_keys.items():
        section_payload = payload[section_name]
        assert isinstance(section_payload, dict)
        assert tuple(section_payload.keys()) == expected_keys, section_name

    named_commands_payload = payload["local_cli_bridge"]["named_commands"]
    assert tuple(named_commands_payload.keys()) == schema.local_cli_named_command_keys
