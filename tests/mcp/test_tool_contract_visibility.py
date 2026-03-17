from __future__ import annotations

import json
from pathlib import Path

import anyio


def _tool_description(mcp_server: object, tool_name: str) -> str:
    async def _load() -> str:
        tools = await mcp_server.list_tools()
        return next(tool.description for tool in tools if tool.name == tool_name)

    return anyio.run(_load)


def test_run_contract_check_tool_description_surfaces_request_requirements() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "run_contract_check")

    assert "``request.check_key`` or ``request.check_id`` is required" in description
    assert "``request.contract`` is optional" in description
    assert "``schema_version: 1``" in description
    assert "``request.binding``, ``request.metadata``, and ``request.observed`` are each" in description
    assert "``required_request_fields``" in description
    assert "``optional_request_fields``" in description
    assert "``request_template``" in description


def test_suggest_contract_checks_tool_description_surfaces_contract_requirements() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "suggest_contract_checks")

    assert "``contract`` must be an object with ``schema_version: 1``" in description
    assert "``active_checks`` is optional and must be ``list[str]``" in description
    assert "``already_active``" in description
    assert "``run_contract_check(request=...)``" in description


def test_assert_convention_validate_description_surfaces_required_headers() -> None:
    from gpd.mcp.servers.conventions_server import mcp

    description = _tool_description(mcp, "assert_convention_validate")

    assert "Every derivation artifact must include at least one ASSERT_CONVENTION line." in description
    assert "Missing assertions are treated as invalid, not advisory" in description


def test_public_descriptors_surface_contract_and_optional_dependency_visibility() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    descriptors = build_public_descriptors()

    verification = descriptors["gpd-verification"]
    assert "structured request objects or schema_version=1 contract payloads" in verification["description"]
    assert "request templates" in verification["description"]
    assert "shared semantic integrity rules" in verification["description"]
    assert "target resolution ambiguous" in verification["description"]
    assert "references[].carry_forward_to only for workflow scope labels" in verification["description"]
    assert "never contract IDs" in verification["description"]

    conventions = descriptors["gpd-conventions"]
    assert "ASSERT_CONVENTION validation" in conventions["description"]
    assert "Every derivation artifact must carry at least one ASSERT_CONVENTION header" in conventions["description"]

    arxiv = descriptors["gpd-arxiv"]
    assert arxiv["optional"] is True
    assert arxiv["availability"] == "conditional"
    assert "optional Python module 'arxiv_mcp_server'" in arxiv["availability_condition"]
    assert "Optional/conditional arXiv paper search and retrieval" in arxiv["description"]


def test_public_verification_infra_descriptor_surfaces_semantic_contract_rules() -> None:
    descriptor = json.loads(
        (Path(__file__).resolve().parents[2] / "infra" / "gpd-verification.json").read_text(encoding="utf-8")
    )

    description = descriptor["description"]
    assert "structured request objects or schema_version=1 contract payloads" in description
    assert "shared semantic integrity rules" in description
    assert "target resolution ambiguous" in description
    assert "references[].carry_forward_to only for workflow scope labels" in description
    assert "never contract IDs" in description
