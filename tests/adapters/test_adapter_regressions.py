"""Behavior-focused adapter regression coverage."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.core.public_surface_contract import local_cli_bridge_commands
from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS


def test_write_settings_errors_reference_the_directory(tmp_path: Path) -> None:
    from gpd.adapters.install_utils import write_settings

    settings_path = tmp_path / "settings.json"

    with patch("pathlib.Path.write_text", side_effect=PermissionError("denied")):
        with pytest.raises(PermissionError, match=re.escape(str(tmp_path))):
            write_settings(settings_path, {"key": "value"})


def test_write_settings_mkdir_errors_reference_settings_directory(tmp_path: Path) -> None:
    from gpd.adapters.install_utils import write_settings

    settings_path = tmp_path / "deep" / "nested" / "settings.json"

    with patch("pathlib.Path.mkdir", side_effect=PermissionError("denied")):
        with pytest.raises(PermissionError, match="settings directory"):
            write_settings(settings_path, {"key": "value"})


def test_convert_tool_references_uses_literal_replacements() -> None:
    from gpd.adapters.install_utils import convert_tool_references_in_body

    assert "todo_write" in convert_tool_references_in_body(
        "Use TodoWrite to record tasks.",
        {"TodoWrite": "todo_write"},
    )
    assert "new\\1tool" in convert_tool_references_in_body(
        "Use OldTool to do things.",
        {"OldTool": "new\\1tool"},
    )


def test_codex_install_restores_skills_dir_after_failure(gpd_root: Path, tmp_path: Path) -> None:
    from gpd.adapters.codex import CodexAdapter

    adapter = CodexAdapter()
    sentinel = Path("/original/skills/dir")
    adapter._skills_dir = sentinel

    target = tmp_path / ".codex"
    target.mkdir()

    with patch.object(
        CodexAdapter.__bases__[0],
        "install",
        side_effect=RuntimeError("simulated install failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated install failure"):
            adapter.install(gpd_root, target, is_global=False, skills_dir=tmp_path / "new-skills")

    assert adapter._skills_dir == sentinel


def test_codex_install_restores_skills_dir_after_success(gpd_root: Path, tmp_path: Path) -> None:
    from gpd.adapters.codex import CodexAdapter

    adapter = CodexAdapter()
    sentinel = Path("/original/skills/dir")
    adapter._skills_dir = sentinel

    target = tmp_path / ".codex"
    target.mkdir()
    fake_result = {"runtime": "codex", "target": str(target), "commands": 0, "agents": 0}

    with patch.object(CodexAdapter.__bases__[0], "install", return_value=fake_result):
        result = adapter.install(gpd_root, target, is_global=False, skills_dir=tmp_path / "new-skills")

    assert result == fake_result
    assert adapter._skills_dir == sentinel


def test_configure_opencode_permissions_fails_closed_for_non_dict_json(tmp_path: Path) -> None:
    from gpd.adapters.opencode import configure_opencode_permissions

    config_dir = tmp_path / "opencode"
    config_dir.mkdir()
    (config_dir / "opencode.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    before = (config_dir / "opencode.json").read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="malformed"):
        configure_opencode_permissions(config_dir)

    assert (config_dir / "opencode.json").read_text(encoding="utf-8") == before


def test_write_mcp_servers_opencode_fails_closed_for_non_dict_mcp_key(tmp_path: Path) -> None:
    from gpd.adapters.opencode import _write_mcp_servers_opencode

    config_dir = tmp_path / "opencode"
    config_dir.mkdir()
    (config_dir / "opencode.json").write_text(json.dumps({"mcp": "not a dict"}), encoding="utf-8")
    before = (config_dir / "opencode.json").read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="malformed"):
        _write_mcp_servers_opencode(
            config_dir,
            {
                "gpd-errors": {
                    "command": "python",
                    "args": ["-m", "gpd.mcp.servers.errors_mcp"],
                }
            },
        )

    assert (config_dir / "opencode.json").read_text(encoding="utf-8") == before


def test_managed_mcp_env_values_win_over_stale_existing_env() -> None:
    from gpd.mcp.builtin_servers import merge_managed_mcp_entry

    merged = merge_managed_mcp_entry(
        {
            "command": "old-command",
            "env": {
                "GPD_WOLFRAM_MCP_ENDPOINT": "https://stale.invalid/mcp",
                "USER_EXTRA_ENV": "keep-me",
            },
        },
        {
            "command": "gpd-mcp-wolfram",
            "args": [],
            "env": {"GPD_WOLFRAM_MCP_ENDPOINT": "https://managed.invalid/mcp"},
        },
        merge_mapping_keys=frozenset({"env"}),
    )

    assert merged["command"] == "gpd-mcp-wolfram"
    assert merged["env"] == {
        "GPD_WOLFRAM_MCP_ENDPOINT": "https://managed.invalid/mcp",
        "USER_EXTRA_ENV": "keep-me",
    }


def test_explicit_user_owned_env_policy_can_preserve_existing_value() -> None:
    from gpd.mcp.builtin_servers import merge_managed_mcp_entry

    merged = merge_managed_mcp_entry(
        {"env": {"GPD_WOLFRAM_MCP_ENDPOINT": "https://user.invalid/mcp"}},
        {"env": {"GPD_WOLFRAM_MCP_ENDPOINT": "https://managed.invalid/mcp"}},
        merge_mapping_keys=frozenset({"env"}),
        user_owned_mapping_keys={"env": frozenset({"GPD_WOLFRAM_MCP_ENDPOINT"})},
    )

    assert merged["env"] == {"GPD_WOLFRAM_MCP_ENDPOINT": "https://user.invalid/mcp"}


@pytest.mark.parametrize(
    ("module_name", "helper_name"),
    [
        ("gpd.adapters.codex", "_build_managed_optional_mcp_servers"),
        ("gpd.adapters.claude_code", "_build_managed_optional_mcp_servers"),
        ("gpd.adapters.gemini", "_project_managed_mcp_servers"),
        ("gpd.adapters.opencode", "_project_managed_mcp_servers"),
    ],
)
def test_managed_wolfram_projection_helpers_hide_api_key_and_preserve_endpoint(
    module_name: str,
    helper_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(module_name)
    helper = getattr(module, helper_name)

    monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "super-secret-token")
    monkeypatch.setenv("GPD_WOLFRAM_MCP_ENDPOINT", "https://example.invalid/api/mcp")

    servers = helper()
    wolfram = servers["gpd-wolfram"]
    payload = json.dumps(wolfram)

    assert wolfram["command"] == "gpd-mcp-wolfram"
    assert wolfram["args"] == []
    assert "super-secret-token" not in payload
    assert "GPD_WOLFRAM_MCP_API_KEY" not in payload
    assert "https://example.invalid/api/mcp" in payload


@pytest.mark.parametrize(
    ("module_name", "helper_name", "expected_keys"),
    [
        (
            "gpd.adapters.codex",
            "_managed_optional_mcp_server_keys",
            frozenset({"gpd-wolfram"}),
        ),
        (
            "gpd.adapters.claude_code",
            "_managed_integrations.gpd_managed_mcp_server_keys",
            frozenset({*GPD_MCP_SERVER_KEYS, "gpd-wolfram"}),
        ),
        (
            "gpd.adapters.gemini",
            "_managed_integrations.gpd_managed_mcp_server_keys",
            frozenset({*GPD_MCP_SERVER_KEYS, "gpd-wolfram"}),
        ),
        (
            "gpd.adapters.opencode",
            "_managed_integrations.gpd_managed_mcp_server_keys",
            frozenset({*GPD_MCP_SERVER_KEYS, "gpd-wolfram"}),
        ),
    ],
)
def test_managed_mcp_key_helpers_include_registry_backed_optional_keys(
    module_name: str,
    helper_name: str,
    expected_keys: frozenset[str],
) -> None:
    module = importlib.import_module(module_name)
    helper = module
    for attr in helper_name.split("."):
        helper = getattr(helper, attr)

    keys = helper()

    assert keys == expected_keys


@pytest.mark.parametrize(
    ("module_name", "function_name"),
    [
        ("gpd.adapters.claude_code", "_rewrite_gpd_cli_invocations"),
        ("gpd.adapters.codex", "_rewrite_codex_gpd_cli_invocations"),
        ("gpd.adapters.gemini", "_rewrite_gpd_cli_invocations"),
        ("gpd.adapters.opencode", "_rewrite_gpd_cli_invocations"),
    ],
)
@pytest.mark.parametrize(
    ("shell_line", "expected_fragment"),
    [
        ("gpd; echo ok\n", "/runtime/gpd; echo ok"),
        ("echo $(gpd)\n", "echo $(/runtime/gpd)"),
        ("gpd>out.log\n", "/runtime/gpd>out.log"),
    ],
)
def test_runtime_shell_rewriters_handle_metacharacter_terminated_gpd_commands(
    module_name: str,
    function_name: str,
    shell_line: str,
    expected_fragment: str,
) -> None:
    module = importlib.import_module(module_name)
    rewrite = getattr(module, function_name)

    result = rewrite(f"```bash\n{shell_line}```\n", "/runtime/gpd")

    assert expected_fragment in result


@pytest.mark.parametrize(
    ("module_name", "function_name"),
    [
        ("gpd.adapters.claude_code", "_rewrite_gpd_cli_invocations"),
        ("gpd.adapters.codex", "_rewrite_codex_gpd_cli_invocations"),
        ("gpd.adapters.gemini", "_rewrite_gpd_cli_invocations"),
        ("gpd.adapters.opencode", "_rewrite_gpd_cli_invocations"),
    ],
)
def test_runtime_rewriters_preserve_public_local_cli_contract(module_name: str, function_name: str) -> None:
    module = importlib.import_module(module_name)
    rewrite = getattr(module, function_name)

    public_commands = local_cli_bridge_commands()
    content = (
        "Use `gpd --help` before anything else.\n"
        "Keep `gpd config ensure-section` bridged because it is an executable shell step.\n"
        "```bash\n"
        + "\n".join([*public_commands, "gpd config ensure-section"])
        + "\n```\n"
    )

    result = rewrite(content, "/runtime/gpd")

    assert "`gpd --help`" in result
    assert "`gpd config ensure-section`" in result
    for command in public_commands:
        assert command in result
        assert f"/runtime/gpd{command[3:]}" not in result
    assert "/runtime/gpd config ensure-section" in result
