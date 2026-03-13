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


def test_registry_agent_metadata_values_are_valid() -> None:
    valid_surfaces = set(registry.VALID_AGENT_SURFACES)
    valid_role_families = set(registry.VALID_AGENT_ROLE_FAMILIES)
    valid_artifact_authorities = set(registry.VALID_AGENT_ARTIFACT_WRITE_AUTHORITIES)
    valid_shared_state_authorities = set(registry.VALID_AGENT_SHARED_STATE_AUTHORITIES)

    for name in registry.list_agents():
        agent = registry.get_agent(name)
        assert agent.surface in valid_surfaces, name
        assert agent.role_family in valid_role_families, name
        assert agent.artifact_write_authority in valid_artifact_authorities, name
        assert agent.shared_state_authority in valid_shared_state_authorities, name


def test_representative_agents_expose_expected_metadata_policy() -> None:
    expectations = {
        "gpd-executor": {
            "surface": "public",
            "role_family": "worker",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "return_only",
        },
        "gpd-planner": {
            "surface": "public",
            "role_family": "coordination",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "return_only",
        },
        "gpd-roadmapper": {
            "surface": "public",
            "role_family": "coordination",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "direct",
        },
        "gpd-notation-coordinator": {
            "surface": "public",
            "role_family": "coordination",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "direct",
        },
        "gpd-phase-researcher": {
            "surface": "internal",
            "role_family": "analysis",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "return_only",
        },
        "gpd-verifier": {
            "surface": "internal",
            "role_family": "verification",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "return_only",
        },
        "gpd-review-reader": {
            "surface": "internal",
            "role_family": "review",
            "artifact_write_authority": "scoped_write",
            "shared_state_authority": "return_only",
        },
    }

    for name, expected in expectations.items():
        agent = registry.get_agent(name)
        assert agent.surface == expected["surface"], name
        assert agent.role_family == expected["role_family"], name
        assert agent.artifact_write_authority == expected["artifact_write_authority"], name
        assert agent.shared_state_authority == expected["shared_state_authority"], name
