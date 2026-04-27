"""Focused assertions for non-routing MCP catalog and checklist contracts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import anyio
import pytest


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
    from gpd import registry as content_registry
    from gpd.mcp.servers.skills_server import get_skill, list_skills

    assert get_skill("") == {"error": "name must be a non-empty string", "schema_version": 1}
    assert list_skills(category="") == {"error": "category must be a non-empty string when provided", "schema_version": 1}

    result = list_skills(category="nonexistent")

    assert result == {
        "error": f"category must be one of: {', '.join(content_registry.skill_categories())}",
        "schema_version": 1,
    }


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


def test_add_pattern_title_schema_matches_slug_validation() -> None:
    from jsonschema import Draft202012Validator

    schema = _tool_schema("gpd.mcp.servers.patterns_server", "add_pattern")
    title = schema["properties"]["title"]
    validator = Draft202012Validator(schema)
    valid_payload = {
        "domain": "qft",
        "title": "Test sign error",
        "category": "sign-error",
        "severity": "high",
    }

    assert title["type"] == "string"
    assert title["minLength"] == 1
    assert title["pattern"] == r"[A-Za-z0-9]"
    assert not list(validator.iter_errors(valid_payload))
    assert list(validator.iter_errors({**valid_payload, "title": "   "}))
    assert list(validator.iter_errors({**valid_payload, "title": "!!!"}))


def test_run_check_schema_publishes_live_identifier_enum() -> None:
    from gpd.mcp.servers import verification_server

    schema = _tool_schema("gpd.mcp.servers.verification_server", "run_check")
    check_id = schema["properties"]["check_id"]

    assert check_id["enum"] == list(verification_server._RUN_CHECK_IDENTIFIER_VALUES)
    assert {"5.1", "contract.limit_recovery"} <= set(check_id["enum"])


def test_get_bundle_checklist_schema_publishes_unique_non_blank_bundle_ids() -> None:
    schema = _tool_schema("gpd.mcp.servers.verification_server", "get_bundle_checklist")
    bundle_ids = schema["properties"]["bundle_ids"]

    assert bundle_ids["type"] == "array"
    assert bundle_ids["uniqueItems"] is True
    assert bundle_ids["items"]["type"] == "string"
    assert bundle_ids["items"]["minLength"] == 1
    assert bundle_ids["items"]["pattern"] == r"\S"


def test_protocol_catalog_schema_refreshes_from_live_manifest_values(monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.mcp.servers import protocols_server

    monkeypatch.setattr(
        protocols_server,
        "_load_protocol_domain_manifest",
        lambda: {"alpha-protocol": "alpha", "beta-protocol": "beta"},
    )

    protocol_schema = _tool_schema("gpd.mcp.servers.protocols_server", "list_protocols")

    assert _collect_enum_values(protocol_schema["properties"]["domain"]) == {"alpha", "beta"}


def test_skill_catalog_schema_refreshes_from_live_registry_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd import registry as content_registry
    from gpd.mcp.servers import skills_server
    from gpd.registry import SkillDef

    monkeypatch.setattr(content_registry, "skill_categories", lambda: ("alpha", "beta"))
    monkeypatch.setattr(
        skills_server,
        "_load_skill_index",
        lambda: [
            SkillDef(
                name="gpd-alpha",
                description="Alpha.",
                content="Alpha content.",
                category="alpha",
                path="/tmp/gpd-alpha.md",
                source_kind="command",
                registry_name="alpha",
            ),
            SkillDef(
                name="gpd-beta",
                description="Beta.",
                content="Beta content.",
                category="beta",
                path="/tmp/gpd-beta.md",
                source_kind="command",
                registry_name="beta",
            ),
        ],
    )

    skill_schema = _tool_schema("gpd.mcp.servers.skills_server", "list_skills")
    result = skills_server.list_skills()

    assert _collect_enum_values(skill_schema["properties"]["category"]) == {"alpha", "beta"}
    assert result["categories"] == ["alpha", "beta"]
