from __future__ import annotations

import json
from pathlib import Path

import anyio


def test_verification_contract_policy_text_stays_aligned_across_public_surfaces() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors
    from gpd.mcp.servers.verification_server import _CONTRACT_PAYLOAD_INPUT_SCHEMA, mcp
    from gpd.mcp.verification_contract_policy import VERIFICATION_CONTRACT_POLICY_TEXT

    descriptors = build_public_descriptors()
    verification_descriptor = descriptors["gpd-verification"]
    tools = {tool.name: tool for tool in anyio.run(mcp.list_tools)}
    infra_descriptor = json.loads((Path(__file__).resolve().parents[2] / "infra" / "gpd-verification.json").read_text())

    assert _CONTRACT_PAYLOAD_INPUT_SCHEMA["description"] == VERIFICATION_CONTRACT_POLICY_TEXT
    assert verification_descriptor["description"] == VERIFICATION_CONTRACT_POLICY_TEXT
    assert infra_descriptor["description"] == VERIFICATION_CONTRACT_POLICY_TEXT
    assert tools["run_contract_check"].description is not None
    assert tools["suggest_contract_checks"].description is not None
    assert tools["run_contract_check"].description.count(VERIFICATION_CONTRACT_POLICY_TEXT) == 1
    assert tools["suggest_contract_checks"].description.count(VERIFICATION_CONTRACT_POLICY_TEXT) == 1

