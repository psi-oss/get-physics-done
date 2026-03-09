"""Tests for discovery models, categorization, config loading, and env var resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

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
    load_sources_config,
    resolve_env_vars,
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


# -- load_sources_config tests --


class TestLoadSourcesConfig:
    def test_returns_default_when_file_missing(self, tmp_path: Path) -> None:
        config = load_sources_config(tmp_path / "nonexistent.yaml")
        assert config.version == "1.0.0"
        assert "gpd-modal" in config.sources

    def test_parses_valid_yaml(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "test-sources.yaml"
        yaml_path.write_text(
            yaml.dump(
                {
                    "version": "1.0.0",
                    "sources": {
                        "test-source": {
                            "type": "modal",
                            "app_name": "my-app",
                        },
                    },
                }
            )
        )
        config = load_sources_config(yaml_path)
        assert "test-source" in config.sources
        assert config.sources["test-source"].app_name == "my-app"

    def test_resolves_env_vars_in_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_APP", "resolved-app")
        yaml_path = tmp_path / "test-sources.yaml"
        yaml_path.write_text(
            yaml.dump(
                {
                    "version": "1.0.0",
                    "sources": {
                        "test-source": {
                            "type": "modal",
                            "app_name": "${MY_APP}",
                        },
                    },
                }
            )
        )
        config = load_sources_config(yaml_path)
        assert config.sources["test-source"].app_name == "resolved-app"

    def test_falls_back_on_invalid_yaml(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text(":::invalid yaml{{{}}")
        config = load_sources_config(yaml_path)
        assert config.version == "1.0.0"
        assert "gpd-modal" in config.sources

    def test_rejects_unsupported_version(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "v2.yaml"
        yaml_path.write_text(yaml.dump({"version": "2.0.0", "sources": {}}))
        config = load_sources_config(yaml_path)
        # Falls back to default because version 2.x is unsupported
        assert "gpd-modal" in config.sources


# -- get_default_config tests --


class TestGetDefaultConfig:
    def test_has_three_sources(self) -> None:
        config = get_default_config()
        assert len(config.sources) == 3
        assert "gpd-modal" in config.sources
        assert "external" in config.sources
        assert "local" in config.sources

    def test_gpd_modal_source(self) -> None:
        config = get_default_config()
        modal_src = config.sources["gpd-modal"]
        assert modal_src.type == "modal"
        assert modal_src.app_name == "gpd-mcp-servers"
        assert modal_src.reconcile is True

    def test_local_source_has_configs(self) -> None:
        config = get_default_config()
        local_src = config.sources["local"]
        assert local_src.type == "local"
        assert "sympy" in local_src.configs
        assert "lean4" in local_src.configs
        assert len(local_src.configs) == 6
