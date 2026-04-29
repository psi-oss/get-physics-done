from __future__ import annotations

import json
from pathlib import Path

import pytest

import gpd.mcp.managed_integrations as managed_integrations
from gpd.mcp.managed_integrations import (
    MANAGED_INTEGRATIONS,
    WOLFRAM_BRIDGE_COMMAND,
    WOLFRAM_BRIDGE_MODULE,
    WOLFRAM_INTEGRATION_ID,
    WOLFRAM_MANAGED_SERVER_KEY,
    WOLFRAM_MCP_API_KEY_ENV_VAR,
    WOLFRAM_MCP_DEFAULT_ENDPOINT,
    WOLFRAM_MCP_ENDPOINT_ENV_VAR,
    get_managed_integration,
    list_managed_integrations,
)


class _FakeManagedIntegration:
    def __init__(
        self, integration_id: str, managed_server_key: str, configured: bool, server_entry: dict[str, object]
    ) -> None:
        self.integration_id = integration_id
        self.managed_server_key = managed_server_key
        self._configured = configured
        self._server_entry = server_entry
        self.calls: list[tuple[str, object, object]] = []

    def is_configured(self, env=None, cwd=None) -> bool:  # type: ignore[no-untyped-def]
        self.calls.append(("is_configured", env, cwd))
        return self._configured

    def projected_server_entry(self, env=None, cwd=None, *, python_path=None) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self.calls.append(("projected_server_entry", env, cwd, python_path))
        return self._server_entry


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
    assert descriptor.bridge_module == WOLFRAM_BRIDGE_MODULE
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
    assert descriptor.projected_server_entry(
        {
            WOLFRAM_MCP_API_KEY_ENV_VAR: "secret",
            WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid",
        },
        python_path="/usr/bin/python3",
    ) == {
        "command": "/usr/bin/python3",
        "args": ["-m", WOLFRAM_BRIDGE_MODULE],
        "env": {WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid"},
    }
    assert WOLFRAM_MCP_API_KEY_ENV_VAR not in descriptor.projected_server_entry(
        {WOLFRAM_MCP_API_KEY_ENV_VAR: "secret"},
        python_path="/usr/bin/python3",
    ).get("env", {})


def test_wolfram_descriptor_reports_canonical_missing_key_recovery_status() -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    env = {"WOLFRAM_MCP_SERVICE_API_KEY": "legacy-secret"}
    summary = descriptor.config_summary(env)

    assert summary["api_key_present"] is False
    assert summary["missing_api_key_env_vars"] == [WOLFRAM_MCP_API_KEY_ENV_VAR]
    assert "ignored_legacy_api_key_env_vars" not in summary
    assert summary["api_key_recovery"] == f"Set {WOLFRAM_MCP_API_KEY_ENV_VAR}."
    assert summary["auth_state"] == "missing-api-key"


def test_wolfram_cli_status_projects_missing_key_recovery_without_server_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from gpd.cli import _wolfram_integration_status_payload

    (tmp_path / "GPD").mkdir()
    monkeypatch.delenv(WOLFRAM_MCP_API_KEY_ENV_VAR, raising=False)
    monkeypatch.setenv("WOLFRAM_MCP_SERVICE_API_KEY", "legacy-secret")

    payload = _wolfram_integration_status_payload(tmp_path)

    assert payload["state"] == "missing-api-key"
    assert payload["projection_status"] == "blocked_missing_api_key"
    assert payload["projected_server"] is None
    assert payload["missing_api_key_env_vars"] == [WOLFRAM_MCP_API_KEY_ENV_VAR]
    assert "ignored_legacy_api_key_env_vars" not in payload
    assert f"Set {WOLFRAM_MCP_API_KEY_ENV_VAR}." in payload["next_step"]


def test_managed_optional_mcp_helpers_project_from_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    alpha = _FakeManagedIntegration(
        "alpha",
        "gpd-alpha",
        True,
        {"command": "alpha-bridge", "args": []},
    )
    beta = _FakeManagedIntegration(
        "beta",
        "gpd-beta",
        False,
        {"command": "beta-bridge", "args": []},
    )
    monkeypatch.setattr(
        managed_integrations,
        "MANAGED_INTEGRATIONS",
        {
            alpha.integration_id: alpha,
            beta.integration_id: beta,
        },
    )

    env = {"ALPHA_TOKEN": "secret"}
    servers = managed_integrations.projected_managed_optional_mcp_servers(env, cwd=tmp_path)

    assert servers == {"gpd-alpha": {"command": "alpha-bridge", "args": []}}
    assert managed_integrations.managed_optional_mcp_server_keys() == frozenset({"gpd-alpha", "gpd-beta"})
    assert alpha.calls == [
        ("is_configured", env, tmp_path),
        ("projected_server_entry", env, tmp_path, None),
    ]
    assert beta.calls == [
        ("is_configured", env, tmp_path),
    ]


def test_projected_managed_optional_wolfram_server_uses_module_launch_without_secret() -> None:
    env = {
        WOLFRAM_MCP_API_KEY_ENV_VAR: "super-secret-token",
        WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid/api/mcp",
    }

    servers = managed_integrations.projected_managed_optional_mcp_servers(
        env,
        python_path="/runtime/python",
    )

    assert servers == {
        WOLFRAM_MANAGED_SERVER_KEY: {
            "command": "/runtime/python",
            "args": ["-m", WOLFRAM_BRIDGE_MODULE],
            "env": {WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid/api/mcp"},
        }
    }
    serialized = json.dumps(servers)
    assert "super-secret-token" not in serialized
    assert WOLFRAM_MCP_API_KEY_ENV_VAR not in serialized


def test_wolfram_descriptor_respects_project_local_disable_without_endpoint_override(tmp_path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"wolfram":{"enabled":false}}',
        encoding="utf-8",
    )

    env = {
        WOLFRAM_MCP_API_KEY_ENV_VAR: "secret",
        WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://env.invalid/api/mcp",
    }

    assert descriptor.project_record(tmp_path) == {"enabled": False}
    assert descriptor.project_enabled(tmp_path) is False
    assert descriptor.is_configured(env, cwd=tmp_path) is False
    assert descriptor.resolved_endpoint(env, cwd=tmp_path) == "https://env.invalid/api/mcp"
    assert descriptor.config_summary(env, cwd=tmp_path)["enabled"] is False


def test_wolfram_descriptor_rejects_project_local_endpoint_override(tmp_path: Path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"wolfram":{"enabled":true,"endpoint":"https://project.invalid/api/mcp"}}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"endpoint is not supported in project-owned integrations\.json"):
        descriptor.project_record(tmp_path)
    with pytest.raises(RuntimeError, match=r"endpoint is not supported in project-owned integrations\.json"):
        descriptor.resolved_endpoint({WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://env.invalid/api/mcp"}, cwd=tmp_path)


def test_projected_wolfram_server_rejects_project_owned_endpoint_redirect(tmp_path: Path) -> None:
    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"wolfram":{"enabled":true,"endpoint":"https://attacker.invalid/api/mcp"}}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"endpoint is not supported in project-owned integrations\.json"):
        managed_integrations.projected_managed_optional_mcp_servers(
            {WOLFRAM_MCP_API_KEY_ENV_VAR: "secret"},
            cwd=tmp_path,
        )


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
        descriptor.project_record(tmp_path)


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({"wolfram": {"enabled": "false"}}, r"integrations\.wolfram\.enabled must be a boolean"),
        ({"wolfram": {"enabled": None}}, r"integrations\.wolfram\.enabled must be a boolean"),
        ({"wolfram": []}, r"integrations\.wolfram must be a JSON object"),
        (
            {"wolfram": {"enabled": True}, "legacy_notes": "unexpected"},
            r"integrations config contains unsupported keys: legacy_notes; supported keys are wolfram",
        ),
    ],
)
def test_wolfram_descriptor_default_parsing_fails_closed_for_malformed_config(
    tmp_path: Path,
    payload: dict[str, object],
    expected_error: str,
) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match=expected_error):
        descriptor.project_record(tmp_path)


def test_wolfram_descriptor_missing_config_is_treated_as_absent(tmp_path: Path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    assert descriptor.project_record(tmp_path) is None
    assert descriptor.project_enabled(tmp_path) is True


def test_wolfram_descriptor_default_parsing_rejects_unreadable_config(tmp_path: Path, monkeypatch) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"wolfram":{"enabled":true}}', encoding="utf-8")

    original_read_text = managed_integrations.Path.read_text

    def _fake_read_text(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == config_path:
            raise OSError("Permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(managed_integrations.Path, "read_text", _fake_read_text)

    with pytest.raises(RuntimeError, match=r"Cannot read integrations config: Permission denied"):
        descriptor.project_record(tmp_path)


def test_wolfram_descriptor_default_parsing_rejects_malformed_json(tmp_path: Path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"Malformed integrations config: .*Fix or delete integrations\.json"):
        descriptor.project_record(tmp_path)


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
        descriptor.project_record(tmp_path)


def test_wolfram_descriptor_resolves_project_local_config_from_nested_workspace(tmp_path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    project_root = tmp_path / "project"
    nested_workspace = project_root / "notes" / "scratch"
    nested_workspace.mkdir(parents=True)
    config_path = project_root / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    (project_root / "GPD" / "state.json").write_text("{}\n", encoding="utf-8")
    (project_root / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    config_path.write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")

    assert descriptor.project_config_path(nested_workspace) == config_path
    assert descriptor.project_enabled(nested_workspace) is False


def test_wolfram_descriptor_ignores_unverified_ancestor_integrations_config(tmp_path) -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    workspace = tmp_path / "scratch" / "work"
    workspace.mkdir(parents=True)
    ambient_config = tmp_path / "GPD" / "integrations.json"
    ambient_config.parent.mkdir()
    ambient_config.write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")

    assert descriptor.project_config_path(workspace) == workspace / "GPD" / "integrations.json"
    assert descriptor.project_enabled(workspace) is True


def test_wolfram_descriptor_rejects_empty_endpoint_env_override() -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_ENDPOINT is set but empty"):
        descriptor.resolved_endpoint({WOLFRAM_MCP_ENDPOINT_ENV_VAR: "   "})


def test_wolfram_descriptor_rejects_non_https_endpoint_env_override() -> None:
    descriptor = get_managed_integration("wolfram")
    assert descriptor is not None

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_ENDPOINT must be an HTTPS URL"):
        descriptor.resolved_endpoint({WOLFRAM_MCP_ENDPOINT_ENV_VAR: "http://example.invalid/api/mcp"})


def test_get_managed_integration_rejects_malformed_ids() -> None:
    assert get_managed_integration(None) is None
    assert get_managed_integration(0) is None
    assert get_managed_integration("") is None
    assert get_managed_integration("   ") is None
    assert get_managed_integration(" WOLFRAM ") is not None
