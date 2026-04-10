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


def test_route_skill_distinguishes_project_planning_from_creation_intent() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    with patch(
        "gpd.mcp.servers.skills_server._load_skill_index",
        return_value=[
            _skill("gpd-help", category="help", registry_name="help"),
            _skill("gpd-new-project", category="project", registry_name="new-project"),
        ],
    ):
        help_result = route_skill("overview of project planning")
        create_result = route_skill("create a new project workspace")

    assert help_result["suggestion"] == "gpd-help"
    assert help_result["confidence"] <= 0.1
    assert create_result["suggestion"] == "gpd-new-project"
    assert create_result["confidence"] > 0.1


def test_route_skill_breaks_equal_score_ties_deterministically() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    skills = [
        _skill("gpd-first", category="project", registry_name="merge phases"),
        _skill("gpd-second", category="project", registry_name="merge phases"),
        _skill("gpd-help", category="help", registry_name="help"),
    ]

    with patch("gpd.mcp.servers.skills_server._load_skill_index", return_value=skills):
        suggestions = [route_skill("merge phases together")["suggestion"] for _ in range(5)]

    assert suggestions == ["gpd-first"] * 5


def test_route_skill_ignores_generic_derived_keywords_that_would_create_false_positives() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    with patch(
        "gpd.mcp.servers.skills_server._load_skill_index",
        return_value=[
            _skill("gpd-help", category="help", registry_name="help"),
            _skill("gpd-verify-work", category="review", registry_name="verify-work"),
        ],
    ):
        result = route_skill("work on the paper outline")

    assert result["suggestion"] == "gpd-help"
    assert result["confidence"] <= 0.1


def test_route_skill_publishes_non_blank_contract_in_tool_schema() -> None:
    schema = _route_skill_tool_schema()
    task_description = schema["properties"]["task_description"]

    assert task_description["type"] == "string"
    assert task_description["minLength"] == 1
    assert task_description["pattern"] == r"\S"
    assert schema["required"] == ["task_description"]


def test_route_skill_uses_live_registry_names_for_missing_manual_keyword_routes() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    with patch(
        "gpd.mcp.servers.skills_server._load_skill_index",
        return_value=[
            _skill("gpd-help", category="help", registry_name="help"),
            _skill("gpd-check-todos", category="project", registry_name="check-todos"),
            _skill("gpd-new-milestone", category="project", registry_name="new-milestone"),
            _skill("gpd-compare-branches", category="project", registry_name="compare-branches"),
            _skill("gpd-record-insight", category="project", registry_name="record-insight"),
            _skill("gpd-merge-phases", category="project", registry_name="merge-phases"),
            _skill("gpd-set-profile", category="project", registry_name="set-profile"),
            _skill("gpd-reapply-patches", category="project", registry_name="reapply-patches"),
            _skill("gpd-verify-work", category="review", registry_name="verify-work"),
        ],
    ):
        assert route_skill("check pending todos")["suggestion"] == "gpd-check-todos"
        assert route_skill("start a new milestone")["suggestion"] == "gpd-new-milestone"
        assert route_skill("compare two branches side by side")["suggestion"] == "gpd-compare-branches"
        assert route_skill("record an insight from this session")["suggestion"] == "gpd-record-insight"
        assert route_skill("merge two phases together")["suggestion"] == "gpd-merge-phases"
        assert route_skill("set the research profile")["suggestion"] == "gpd-set-profile"
        assert route_skill("reapply local patches after update")["suggestion"] == "gpd-reapply-patches"


def test_route_skill_uses_phrase_level_routes_for_onboarding_and_setup_commands() -> None:
    from gpd.mcp.servers.skills_server import route_skill

    with patch(
        "gpd.mcp.servers.skills_server._load_skill_index",
        return_value=[
            _skill("gpd-help", category="help", registry_name="help"),
            _skill("gpd-execute-phase", category="execution", registry_name="execute-phase"),
            _skill("gpd-map-research", category="research", registry_name="map-research"),
            _skill("gpd-set-tier-models", category="settings", registry_name="set-tier-models"),
            _skill("gpd-start", category="help", registry_name="start"),
            _skill("gpd-tour", category="help", registry_name="tour"),
        ],
    ):
        assert route_skill("map an existing folder before planning")["suggestion"] == "gpd-map-research"
        assert route_skill("refresh the research map")["suggestion"] == "gpd-map-research"
        assert route_skill("pin exact tier models for this runtime")["suggestion"] == "gpd-set-tier-models"
        assert route_skill("guided first run for a new folder")["suggestion"] == "gpd-start"
        assert route_skill("want a guided overview of the main commands")["suggestion"] == "gpd-tour"
        assert route_skill("guided first run for a new folder")["suggestion"] != "gpd-execute-phase"


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
