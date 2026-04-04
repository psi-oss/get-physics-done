from __future__ import annotations

import json

import pytest

from gpd.mcp.managed_integrations import (
    MANAGED_INTEGRATIONS,
    WOLFRAM_BRIDGE_COMMAND,
    WOLFRAM_INTEGRATION_ID,
    WOLFRAM_MANAGED_SERVER_KEY,
    WOLFRAM_MCP_API_KEY_ENV_VAR,
    WOLFRAM_MCP_DEFAULT_ENDPOINT,
    WOLFRAM_MCP_ENDPOINT_ENV_VAR,
    get_managed_integration,
    list_managed_integrations,
)


def test_managed_integrations_registry_exposes_wolfram_descriptor() -> None:
    registry = list_managed_integrations()

    assert set(registry) == {WOLFRAM_INTEGRATION_ID}
    assert registry[WOLFRAM_INTEGRATION_ID] is MANAGED_INTEGRATIONS[WOLFRAM_INTEGRATION_ID]


def test_wolfram_descriptor_exposes_shared_contract() -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    assert descriptor.integration_id == WOLFRAM_INTEGRATION_ID
    assert descriptor.managed_server_key == WOLFRAM_MANAGED_SERVER_KEY
    assert descriptor.bridge_command == WOLFRAM_BRIDGE_COMMAND
    assert descriptor.api_key_env_var == WOLFRAM_MCP_API_KEY_ENV_VAR
    assert descriptor.endpoint_env_var == WOLFRAM_MCP_ENDPOINT_ENV_VAR
    assert descriptor.default_endpoint == WOLFRAM_MCP_DEFAULT_ENDPOINT
    assert descriptor.api_key_env_vars == (WOLFRAM_MCP_API_KEY_ENV_VAR,)


def test_wolfram_descriptor_uses_env_vars_for_configuration(monkeypatch) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    assert descriptor.is_configured({}) is False
    assert descriptor.is_configured({WOLFRAM_MCP_API_KEY_ENV_VAR: "secret"}) is True
    assert descriptor.is_configured({"WOLFRAM_MCP_SERVICE_API_KEY": "legacy-secret"}) is False
    assert descriptor.resolved_endpoint({}) == WOLFRAM_MCP_DEFAULT_ENDPOINT
    assert descriptor.resolved_endpoint({WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid"}) == (
        "https://example.invalid"
    )
    assert descriptor.projected_environment({}) == {}
    assert descriptor.projected_environment({WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid"}) == {
        WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid"
    }
    assert descriptor.projected_server_entry({WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid"}) == {
        "command": WOLFRAM_BRIDGE_COMMAND,
        "args": [],
        "env": {WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid"},
    }


def test_wolfram_descriptor_respects_project_local_disable_and_endpoint_override(tmp_path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"wolfram":{"enabled":false,"endpoint":"https://project.invalid/api/mcp"}}',
        encoding="utf-8",
    )

    env = {WOLFRAM_MCP_API_KEY_ENV_VAR: "secret"}

    assert descriptor.project_record(tmp_path) == {"enabled": False, "endpoint": "https://project.invalid/api/mcp"}
    assert descriptor.project_enabled(tmp_path) is False
    assert descriptor.is_configured(env, cwd=tmp_path) is False
    assert descriptor.resolved_endpoint(env, cwd=tmp_path) == "https://project.invalid/api/mcp"
    assert descriptor.config_summary(env, cwd=tmp_path)["enabled"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"wolfram": {"enabled": False, "api_key_env_var": "legacy"}},  # unknown nested key
        {"wolfram": {"enabled": False}, "legacy_notes": "ignored before strict mode"},  # unknown top-level key
    ],
)
def test_wolfram_descriptor_strict_parsing_rejects_unknown_keys(tmp_path, payload: dict[str, object]) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="unsupported keys"):
        descriptor.project_record(tmp_path, strict=True)


def test_wolfram_descriptor_strict_parsing_rejects_legacy_api_key_env_field(tmp_path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps({"wolfram": {"enabled": True, "api_key_env": "WOLFRAM_MCP_SERVICE_API_KEY"}}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"integrations\.wolfram contains unsupported keys: api_key_env"):
        descriptor.project_record(tmp_path, strict=True)


def test_wolfram_descriptor_resolves_project_local_config_from_nested_workspace(tmp_path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    project_root = tmp_path / "project"
    nested_workspace = project_root / "notes" / "scratch"
    nested_workspace.mkdir(parents=True)
    config_path = project_root / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")

    assert descriptor.project_config_path(nested_workspace) == config_path
    assert descriptor.project_enabled(nested_workspace) is False


def test_wolfram_descriptor_rejects_empty_endpoint_env_override() -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_ENDPOINT is set but empty"):
        descriptor.resolved_endpoint({WOLFRAM_MCP_ENDPOINT_ENV_VAR: "   "}, strict=True)


def test_get_managed_integration_rejects_malformed_ids() -> None:
    assert get_managed_integration(None) is None
    assert get_managed_integration(0) is None
    assert get_managed_integration("") is None
    assert get_managed_integration("   ") is None
    assert get_managed_integration(" WOLFRAM ") is not None
