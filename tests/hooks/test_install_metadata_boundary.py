"""Targeted regressions for install-metadata runtime boundary hardening."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.hooks.install_metadata import (
    config_dir_has_complete_install,
    installed_update_command,
    load_install_manifest_state,
)


def _seed_anonymous_install_tree(config_dir: Path, *, hook_filename: str) -> Path:
    """Create an install tree that only carries anonymous legacy ownership hints."""
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps(
            {
                "install_scope": "local",
                "files": {
                    "skills/gpd-help/SKILL.md": "legacy-hint",
                },
            }
        ),
        encoding="utf-8",
    )

    hook_path = config_dir / "hooks" / hook_filename
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    return hook_path


@pytest.mark.parametrize(
    ("manifest_content", "expected_state", "expected_payload"),
    [
        (None, "missing", {}),
        (b"\xff", "corrupt", {}),
        ("[]", "invalid", {}),
        (json.dumps({"install_scope": "local", "runtime": "codex"}), "ok", {"install_scope": "local", "runtime": "codex"}),
    ],
)
def test_load_install_manifest_state_classifies_manifest_payloads(
    tmp_path: Path,
    manifest_content: bytes | str | None,
    expected_state: str,
    expected_payload: dict[str, object],
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / "gpd-file-manifest.json"
    if manifest_content is not None:
        if isinstance(manifest_content, bytes):
            manifest_path.write_bytes(manifest_content)
        else:
            manifest_path.write_text(manifest_content, encoding="utf-8")

    assert load_install_manifest_state(config_dir) == (expected_state, expected_payload)


def test_runtime_less_manifest_tree_is_rejected_by_install_metadata(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    _seed_anonymous_install_tree(config_dir, hook_filename="install_metadata.py")

    assert config_dir_has_complete_install(config_dir) is False
    assert installed_update_command(config_dir) is None


def test_non_utf8_manifest_tree_is_rejected_by_install_metadata(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_bytes(b"\xff")

    assert config_dir_has_complete_install(config_dir) is False
    assert installed_update_command(config_dir) is None


@pytest.mark.parametrize(
    ("module_name", "hook_filename"),
    [
        ("gpd.hooks.check_update", "check_update.py"),
        ("gpd.hooks.statusline", "statusline.py"),
        ("gpd.hooks.notify", "notify.py"),
    ],
)
def test_hook_self_detection_rejects_runtime_less_manifest_tree(
    tmp_path: Path,
    module_name: str,
    hook_filename: str,
) -> None:
    config_dir = tmp_path / ".codex"
    hook_path = _seed_anonymous_install_tree(config_dir, hook_filename=hook_filename)
    module = importlib.import_module(module_name)

    with patch.object(module, "__file__", str(hook_path)):
        assert module._self_config_dir() is None


@pytest.mark.parametrize(
    ("module_name", "hook_filename"),
    [
        ("gpd.hooks.check_update", "check_update.py"),
        ("gpd.hooks.statusline", "statusline.py"),
        ("gpd.hooks.notify", "notify.py"),
    ],
)
def test_hook_self_detection_rejects_non_utf8_manifest_tree(
    tmp_path: Path,
    module_name: str,
    hook_filename: str,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_bytes(b"\xff")
    hook_path = config_dir / "hooks" / hook_filename
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    module = importlib.import_module(module_name)

    with patch.object(module, "__file__", str(hook_path)):
        assert module._self_config_dir() is None
