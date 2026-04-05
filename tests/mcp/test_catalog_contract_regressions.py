"""Focused regressions for non-routing MCP catalog and checklist contracts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import anyio


def _tool_schema(module_name: str, tool_name: str) -> dict[str, object]:
    module = importlib.import_module(module_name)
    mcp = module.mcp

    async def _load() -> dict[str, object]:
        tools = await mcp.list_tools()
        tool = next(tool for tool in tools if tool.name == tool_name)
        return tool.inputSchema

    return anyio.run(_load)


def _has_non_blank_contract(node: object) -> bool:
    if isinstance(node, dict):
        enum_values = node.get("enum")
        if isinstance(enum_values, list) and enum_values and all(isinstance(value, str) and value.strip() for value in enum_values):
            return True
        if node.get("type") == "string" and node.get("minLength") == 1 and node.get("pattern") == r"\S":
            return True
        return any(_has_non_blank_contract(value) for value in node.values())
    if isinstance(node, list):
        return any(_has_non_blank_contract(value) for value in node)
    return False


def _collect_enum_values(node: object) -> set[str]:
    if isinstance(node, dict):
        values = set(node.get("enum", [])) if isinstance(node.get("enum"), list) else set()
        for value in node.values():
            values.update(_collect_enum_values(value))
        return values
    if isinstance(node, list):
        values: set[str] = set()
        for value in node:
            values.update(_collect_enum_values(value))
        return values
    return set()


def test_protocol_catalog_tools_reject_blank_inputs_up_front() -> None:
    from gpd.mcp.servers.protocols_server import get_protocol, get_protocol_checkpoints, list_protocols

    assert get_protocol("") == {"error": "name must be a non-empty string", "schema_version": 1}
    assert get_protocol_checkpoints("") == {"error": "name must be a non-empty string", "schema_version": 1}
    assert list_protocols(domain="") == {"error": "domain must be a non-empty string when provided", "schema_version": 1}


def test_skill_catalog_tools_reject_blank_and_unknown_filters_up_front() -> None:
    from gpd.mcp.servers.skills_server import get_skill, list_skills

    assert get_skill("") == {"error": "name must be a non-empty string", "schema_version": 1}
    assert list_skills(category="") == {"error": "category must be a non-empty string when provided", "schema_version": 1}

    result = list_skills(category="nonexistent")

    assert result["count"] == 0
    assert result["skills"] == []
    assert "categories" in result


def test_verification_catalog_tools_reject_blank_inputs_up_front() -> None:
    from gpd.mcp.servers.verification_server import get_checklist, run_check

    assert run_check("5.1", "qft", "")["error"] == "artifact_content must be a non-empty string"
    assert run_check("", "qft", "artifact")["error"] == "check_id must be a non-empty string"
    assert get_checklist("")["error"] == "domain must be a non-empty string"


def test_catalog_tool_schemas_publish_non_blank_contracts() -> None:
    specs = [
        ("gpd.mcp.servers.protocols_server", "get_protocol", "name"),
        ("gpd.mcp.servers.protocols_server", "list_protocols", "domain"),
        ("gpd.mcp.servers.protocols_server", "get_protocol_checkpoints", "name"),
        ("gpd.mcp.servers.skills_server", "list_skills", "category"),
        ("gpd.mcp.servers.skills_server", "get_skill", "name"),
        ("gpd.mcp.servers.verification_server", "run_check", "check_id"),
        ("gpd.mcp.servers.verification_server", "run_check", "domain"),
        ("gpd.mcp.servers.verification_server", "run_check", "artifact_content"),
        ("gpd.mcp.servers.verification_server", "get_checklist", "domain"),
    ]

    for module_name, tool_name, field_name in specs:
        schema = _tool_schema(module_name, tool_name)
        assert _has_non_blank_contract(schema["properties"][field_name]), f"{tool_name}.{field_name} lost non-blank contract visibility"


def test_catalog_filter_schemas_publish_authoritative_enum_values() -> None:
    from gpd import registry as content_registry

    protocol_schema = _tool_schema("gpd.mcp.servers.protocols_server", "list_protocols")
    skill_schema = _tool_schema("gpd.mcp.servers.skills_server", "list_skills")
    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "references" / "protocols" / "protocol-domains.json").read_text(encoding="utf-8")
    )
    expected_protocol_domains = set(manifest["protocol_domains"].values())
    expected_skill_categories = set(content_registry.skill_categories())

    assert _collect_enum_values(protocol_schema["properties"]["domain"]) == expected_protocol_domains
    assert _collect_enum_values(skill_schema["properties"]["category"]) == expected_skill_categories
