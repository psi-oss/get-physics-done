"""Tests for discovery models, categorization, config loading, and env var resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gpd.mcp.discovery.models import (
    PHYSICS_CATEGORIES,
    MCPSourcesConfig,
    MCPStatus,
    SourceConfig,
    ToolCatalogSnapshot,
    ToolEntry,
    categorize_tool,
)
from gpd.mcp.discovery.sources import (
    get_default_config,
    load_external_services_file,
    load_sources_config,
    resolve_env_vars,
    resolve_project_root,
    resolve_source_path,
)

# -- MCPStatus tests --


class TestMCPStatus:
    def test_enum_values(self) -> None:
        assert MCPStatus.available == "available"
        assert MCPStatus.stale == "stale"
        assert MCPStatus.unavailable == "unavailable"
        assert MCPStatus.unknown == "unknown"

    def test_all_values_present(self) -> None:
        values = {s.value for s in MCPStatus}
        assert values == {"available", "stale", "unavailable", "unknown"}


# -- ToolEntry tests --


class TestToolEntry:
    def test_creation_with_defaults(self) -> None:
        entry = ToolEntry(name="openfoam", description="CFD solver", source="modal")
        assert entry.name == "openfoam"
        assert entry.description == "CFD solver"
        assert entry.source == "modal"
        assert entry.status == MCPStatus.unknown
        assert entry.categories == []
        assert entry.domains == []
        assert entry.tools == []
        assert entry.overview == ""

    def test_creation_with_all_fields(self) -> None:
        entry = ToolEntry(
            name="openfoam",
            description="CFD solver",
            source="modal",
            status=MCPStatus.available,
            categories=["cfd"],
            domains=["Computational fluid dynamics"],
            tools=[{"name": "create_simulation", "desc": "Create a sim"}],
            overview="OpenFOAM CFD toolkit",
        )
        assert entry.status == MCPStatus.available
        assert entry.categories == ["cfd"]
        assert len(entry.tools) == 1


# -- PhysicsCategory tests --


class TestPhysicsCategory:
    def test_category_has_required_fields(self) -> None:
        cat = PHYSICS_CATEGORIES[0]
        assert cat.name == "cfd"
        assert cat.display_name == "Computational Fluid Dynamics"
        assert len(cat.domain_keywords) > 0
        assert len(cat.preferred_mcps) > 0

    def test_all_12_categories_present(self) -> None:
        names = {c.name for c in PHYSICS_CATEGORIES}
        expected = {
            "cfd",
            "nbody",
            "fem",
            "quantum",
            "md",
            "climate",
            "multiphysics",
            "bio",
            "geophysics",
            "em_plasma",
            "databases",
            "utility",
        }
        assert names == expected


# -- categorize_tool tests --


class TestCategorizeTool:
    def test_domain_match_cfd(self) -> None:
        result = categorize_tool("some_tool", ["Computational fluid dynamics simulation"])
        assert "cfd" in result

    def test_preferred_mcp_match(self) -> None:
        result = categorize_tool("openfoam", [])
        assert "cfd" in result

    def test_uncategorized_for_unknown(self) -> None:
        result = categorize_tool("mystery_tool", ["Unknown domain xyz"])
        assert result == ["uncategorized"]

    def test_multiple_categories(self) -> None:
        result = categorize_tool("febio", ["Biomechanics and finite element"])
        assert "fem" in result
        assert "bio" in result

    def test_case_insensitive_matching(self) -> None:
        result = categorize_tool("test", ["COMPUTATIONAL FLUID DYNAMICS"])
        assert "cfd" in result


# -- MCPSourcesConfig tests --


class TestMCPSourcesConfig:
    def test_creation_with_defaults(self) -> None:
        config = MCPSourcesConfig()
        assert config.version == "1.0.0"
        assert config.sources == {}
        assert config.categories is None

    def test_creation_with_sources(self) -> None:
        config = MCPSourcesConfig(
            sources={"test": SourceConfig(type="modal")},
        )
        assert "test" in config.sources
        assert config.sources["test"].type == "modal"


# -- ToolCatalogSnapshot tests --


class TestToolCatalogSnapshot:
    def test_summary_format(self) -> None:
        snapshot = ToolCatalogSnapshot(
            total_tools=134,
            available_tools=87,
            stale_tools=12,
            categories_discovered=["cfd", "nbody", "fem", "quantum", "md"],
            tools={},
        )
        summary = snapshot.summary()
        assert "134 tools" in summary
        assert "87 available" in summary
        assert "12 stale" in summary
        assert "35 unknown" in summary
        assert "5 categories" in summary

    def test_summary_empty(self) -> None:
        snapshot = ToolCatalogSnapshot()
        summary = snapshot.summary()
        assert "0 tools" in summary
        assert "0 categories" in summary


# -- resolve_env_vars tests --


class TestResolveEnvVars:
    def test_replaces_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR", "hello")
        assert resolve_env_vars("${TEST_VAR}") == "hello"

    def test_handles_default_syntax(self) -> None:
        # Ensure the var is NOT set
        os.environ.pop("MISSING_VAR_XYZ", None)
        assert resolve_env_vars("${MISSING_VAR_XYZ:-fallback}") == "fallback"

    def test_leaves_unresolvable_as_is(self) -> None:
        os.environ.pop("UNSET_VAR_ABC", None)
        result = resolve_env_vars("${UNSET_VAR_ABC}")
        assert result == "${UNSET_VAR_ABC}"

    def test_replaces_multiple(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("A", "x")
        monkeypatch.setenv("B", "y")
        assert resolve_env_vars("${A}-${B}") == "x-y"

    def test_default_used_when_var_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SET_VAR", "actual")
        assert resolve_env_vars("${SET_VAR:-default}") == "actual"


class TestResolveProjectRoot:
    def test_prefers_explicit_project_root(self, tmp_path: Path) -> None:
        assert resolve_project_root(tmp_path) == tmp_path


class TestResolveSourcePath:
    def test_resolves_relative_path_against_project_root(self, tmp_path: Path) -> None:
        resolved = resolve_source_path("infra/mcp/registry/external_services.yaml", project_root=tmp_path)
        assert resolved == (tmp_path / "infra" / "mcp" / "registry" / "external_services.yaml").resolve()

    def test_returns_none_for_unresolved_env_var(self) -> None:
        os.environ.pop("MISSING_SOURCE_ROOT", None)
        assert resolve_source_path("${MISSING_SOURCE_ROOT}/external.yaml") is None


class TestLoadExternalServicesFile:
    def test_returns_empty_mapping_for_missing_file(self, tmp_path: Path) -> None:
        result = load_external_services_file(str(tmp_path / "missing.yaml"))
        assert result == {}


# -- load_sources_config tests --


class TestLoadSourcesConfig:
    def test_returns_default_config(self) -> None:
        config = load_sources_config()
        assert config.version == "1.0.0"
        assert config == get_default_config()
        assert set(config.sources) == {"external", "local"}


# -- get_default_config tests --


class TestGetDefaultConfig:
    def test_has_public_sources_only(self) -> None:
        config = get_default_config()
        assert len(config.sources) == 2
        assert "external" in config.sources
        assert "local" in config.sources

    def test_external_source_uses_public_registry(self) -> None:
        config = get_default_config()
        external_src = config.sources["external"]
        assert external_src.type == "external"
        assert external_src.services_file == "${GPD_ROOT:-.}/infra/mcp/registry/external_services.yaml"

    def test_local_source_has_configs(self) -> None:
        config = get_default_config()
        local_src = config.sources["local"]
        assert local_src.type == "local"
        assert "sympy" in local_src.configs
        assert "lean4" in local_src.configs
        assert len(local_src.configs) == 6
