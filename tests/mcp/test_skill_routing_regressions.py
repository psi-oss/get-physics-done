"""Focused regressions for skill-routing quality."""

from __future__ import annotations

from unittest.mock import patch

import anyio

from gpd.registry import SkillDef


def _skill(name: str, *, category: str, registry_name: str) -> SkillDef:
    return SkillDef(
        name=name,
        description=name,
        content=name,
        category=category,
        path=f"/tmp/{name}.md",
        source_kind="command",
        registry_name=registry_name,
    )


def _route_skill_tool_schema() -> dict[str, object]:
    from gpd.mcp.servers.skills_server import mcp

    async def _load() -> dict[str, object]:
        tools = await mcp.list_tools()
        tool = next(tool for tool in tools if tool.name == "route_skill")
        return tool.inputSchema

    return anyio.run(_load)


def test_route_skill_rejects_blank_queries_up_front() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    result = route_skill("")

    assert result == {"error": "task_description must be a non-empty string", "schema_version": 1}


def test_route_skill_does_not_route_generic_project_planning_to_new_project() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    with patch(
        "gpd.mcp.servers.skills_server._load_skill_index",
        return_value=[
            _skill("gpd-help", category="help", registry_name="help"),
            _skill("gpd-new-project", category="project", registry_name="new-project"),
        ],
    ):
        result = route_skill("overview of project planning")

    assert result["suggestion"] == "gpd-help"
    assert result["confidence"] <= 0.1


def test_route_skill_still_matches_real_new_project_lifecycle_intent() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    with patch(
        "gpd.mcp.servers.skills_server._load_skill_index",
        return_value=[
            _skill("gpd-help", category="help", registry_name="help"),
            _skill("gpd-new-project", category="project", registry_name="new-project"),
        ],
    ):
        result = route_skill("create a new project workspace")

    assert result["suggestion"] == "gpd-new-project"
    assert result["confidence"] > 0.1


def test_route_skill_publishes_non_blank_contract_in_tool_schema() -> None:
    schema = _route_skill_tool_schema()
    task_description = schema["properties"]["task_description"]

    assert task_description["type"] == "string"
    assert task_description["minLength"] == 1
    assert task_description["pattern"] == r"\S"
    assert schema["required"] == ["task_description"]


def test_canonicalize_command_surface_rewrites_real_command_examples_only() -> None:
    from gpd.mcp.servers.skills_server import _canonicalize_command_surface

    content = (
        "Use `$gpd-*` or /gpd:* for a real command example.\n"
        "Keep /tmp/$gpd-*, https://example.test/$gpd-*, and foo$gpd-*bar untouched.\n"
    )

    result = _canonicalize_command_surface(content)

    assert "Use `gpd-*`" in result
    assert "/gpd:*" not in result
    assert "/tmp/$gpd-*" in result
    assert "https://example.test/$gpd-*" in result
    assert "foo$gpd-*bar" in result
