"""Behavior-focused adapter regression coverage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def test_write_settings_errors_reference_the_directory(tmp_path: Path) -> None:
    from gpd.adapters.install_utils import write_settings

    settings_path = tmp_path / "settings.json"

    with patch("pathlib.Path.write_text", side_effect=PermissionError("denied")):
        with pytest.raises(PermissionError, match=str(tmp_path)):
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


def test_configure_opencode_permissions_recovers_from_non_dict_json(tmp_path: Path) -> None:
    from gpd.adapters.opencode import configure_opencode_permissions

    config_dir = tmp_path / "opencode"
    config_dir.mkdir()
    (config_dir / "opencode.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    modified = configure_opencode_permissions(config_dir)
    written = json.loads((config_dir / "opencode.json").read_text(encoding="utf-8"))

    assert modified is True
    assert isinstance(written, dict)
    assert isinstance(written["permission"], dict)


def test_write_mcp_servers_opencode_recovers_from_non_dict_mcp_key(tmp_path: Path) -> None:
    from gpd.adapters.opencode import _write_mcp_servers_opencode

    config_dir = tmp_path / "opencode"
    config_dir.mkdir()
    (config_dir / "opencode.json").write_text(json.dumps({"mcp": "not a dict"}), encoding="utf-8")

    count = _write_mcp_servers_opencode(
        config_dir,
        {
            "gpd-errors": {
                "command": "python",
                "args": ["-m", "gpd.mcp.servers.errors_mcp"],
            }
        },
    )
    written = json.loads((config_dir / "opencode.json").read_text(encoding="utf-8"))

    assert count == 1
    assert isinstance(written["mcp"], dict)
    assert "gpd-errors" in written["mcp"]
