from __future__ import annotations

from gpd.mcp.managed_integrations import (
    MANAGED_INTEGRATIONS,
    WOLFRAM_BRIDGE_COMMAND,
    WOLFRAM_INTEGRATION_ID,
    WOLFRAM_MANAGED_SERVER_KEY,
    WOLFRAM_MCP_API_KEY_ENV_VAR,
    WOLFRAM_MCP_DEFAULT_ENDPOINT,
    WOLFRAM_MCP_ENDPOINT_ENV_VAR,
    WOLFRAM_MCP_SERVICE_API_KEY_ENV_VAR,
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
    assert descriptor.api_key_env_vars == (
        WOLFRAM_MCP_API_KEY_ENV_VAR,
        WOLFRAM_MCP_SERVICE_API_KEY_ENV_VAR,
    )


def test_wolfram_descriptor_uses_env_vars_for_configuration(monkeypatch) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    assert descriptor.is_configured({}) is False
    assert descriptor.is_configured({WOLFRAM_MCP_API_KEY_ENV_VAR: "secret"}) is True
    assert descriptor.is_configured({WOLFRAM_MCP_SERVICE_API_KEY_ENV_VAR: "legacy-secret"}) is True
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


def test_get_managed_integration_rejects_malformed_ids() -> None:
    assert get_managed_integration(None) is None
    assert get_managed_integration(0) is None
    assert get_managed_integration("") is None
    assert get_managed_integration("   ") is None
    assert get_managed_integration(" WOLFRAM ") is not None
