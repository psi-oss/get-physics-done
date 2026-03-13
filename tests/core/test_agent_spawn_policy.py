"""Regression tests for current spawned-agent writeability semantics."""

from __future__ import annotations

import pytest

from gpd import registry


@pytest.fixture(autouse=True)
def _clean_registry_cache():
    registry.invalidate_cache()
    yield
    registry.invalidate_cache()


def test_every_registered_agent_exposes_a_non_empty_tool_surface() -> None:
    for name in registry.list_agents():
        assert registry.get_agent(name).tools, name


def test_direct_commit_agents_can_write_files() -> None:
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        if agent.commit_authority != "direct":
            continue
        assert "file_write" in agent.tools, name


def test_orchestrator_owned_agents_still_include_writers() -> None:
    orchestrator_writers = {
        name
        for name in registry.list_agents()
        if registry.get_agent(name).commit_authority == "orchestrator"
        and "file_write" in registry.get_agent(name).tools
    }

    assert orchestrator_writers


def test_orchestrator_owned_agents_include_edit_capable_writers() -> None:
    orchestrator_editors = {
        name
        for name in registry.list_agents()
        if registry.get_agent(name).commit_authority == "orchestrator"
        and "file_edit" in registry.get_agent(name).tools
    }

    assert orchestrator_editors
