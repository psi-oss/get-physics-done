"""Tests for gpd/hooks/notify.py."""

from __future__ import annotations

import io
import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import gpd.hooks.notify as notify_module
from gpd.adapters import get_adapter
from gpd.adapters.install_utils import build_runtime_install_repair_command
from gpd.adapters.runtime_catalog import get_hook_payload_policy, iter_runtime_descriptors
from gpd.core.constants import ProjectLayout
from gpd.core.costs import usage_ledger_path
from gpd.hooks.notify import _check_and_notify_update, _emit_execution_notification, _hook_payload_policy, main
from gpd.hooks.runtime_detect import update_command_for_runtime

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


def _runtime_env_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for env_var in descriptor.activation_env_vars:
            prefixes.add(env_var)
            prefixes.add(env_var.rsplit("_", 1)[0] if "_" in env_var else env_var)
    return tuple(sorted(prefixes, key=len, reverse=True))


def _repair_command(runtime: str, *, install_scope: str, target_dir: Path, explicit_target: bool) -> str:
    return build_runtime_install_repair_command(
        runtime,
        install_scope=install_scope,
        target_dir=target_dir,
        explicit_target=explicit_target,
    )


_RUNTIME_ENV_PREFIXES = _runtime_env_prefixes()


def _runtime_env_vars_to_clear() -> set[str]:
    env_vars = {"GPD_ACTIVE_RUNTIME", "XDG_CONFIG_HOME"}
    for descriptor in _RUNTIME_DESCRIPTORS:
        global_config = descriptor.global_config
        for env_var in (global_config.env_var, global_config.env_dir_var, global_config.env_file_var):
            if env_var:
                env_vars.add(env_var)
    return env_vars


_RUNTIME_ENV_VARS_TO_CLEAR = _runtime_env_vars_to_clear()


@pytest.fixture(autouse=True)
def _reset_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep notify-hook tests isolated from prior runtime env overrides."""
    for key in list(os.environ):
        if key.startswith(_RUNTIME_ENV_PREFIXES) or key in _RUNTIME_ENV_VARS_TO_CLEAR:
            monkeypatch.delenv(key, raising=False)


def _write_current_execution(workspace: Path, payload: dict[str, object]) -> None:
    observability = workspace / "GPD" / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    (observability / "current-execution.json").write_text(json.dumps(payload), encoding="utf-8")


def _mark_complete_install(config_dir: Path, *, runtime: str | None = None, install_scope: str = "local") -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    if runtime is not None:
        adapter = get_adapter(runtime)
        for relpath in adapter.install_completeness_relpaths():
            if relpath == "gpd-file-manifest.json":
                continue
            artifact = config_dir / relpath
            artifact.parent.mkdir(parents=True, exist_ok=True)
            if artifact.suffix:
                artifact.write_text("{}\n" if artifact.suffix == ".json" else "# test\n", encoding="utf-8")
            else:
                artifact.mkdir(parents=True, exist_ok=True)
        if runtime == "codex":
            help_skill_dir = config_dir.parent / ".agents" / "skills" / "gpd-help"
            help_skill_dir.mkdir(parents=True, exist_ok=True)
            (help_skill_dir / "SKILL.md").write_text("# test\n", encoding="utf-8")
    else:
        (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {"install_scope": install_scope}
    if runtime is not None:
        explicit_target = config_dir.name != adapter.config_dir_name
        manifest["runtime"] = runtime
        manifest["explicit_target"] = explicit_target
        manifest["install_target_dir"] = str(config_dir)
        if runtime == "codex":
            manifest["codex_skills_dir"] = str(config_dir.parent / ".agents" / "skills")
            manifest["codex_generated_skill_dirs"] = ["gpd-help"]
    (config_dir / "gpd-file-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_notify_uses_latest_local_cache_and_scoped_codex_install_command(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home_cache = home / "GPD" / "cache"
    home_cache.mkdir(parents=True)
    (home_cache / "gpd-update-check.json").write_text(
        json.dumps({"update_available": False, "checked": 10}),
        encoding="utf-8",
    )

    local_cache = tmp_path / ".codex" / "cache"
    local_cache.mkdir(parents=True)
    _mark_complete_install(tmp_path / ".codex", runtime="codex")
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "1.2.3",
                "latest": "1.3.0",
                "checked": 20,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert "Update available: v1.2.3" in output
    assert "v1.3.0" in output
    expected = _repair_command("codex", install_scope="local", target_dir=tmp_path / ".codex", explicit_target=False)
    assert f"Run: {expected}" in output


def test_notify_prefers_active_runtime_cache_over_newer_unrelated_runtime_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"

    local_runtime_dir = tmp_path / ".codex"
    local_cache = local_runtime_dir / "cache"
    local_cache.mkdir(parents=True)
    _mark_complete_install(local_runtime_dir, runtime="codex")
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "1.2.3",
                "latest": "1.3.0",
                "checked": 20,
            }
        ),
        encoding="utf-8",
    )

    unrelated_runtime_dir = home / ".claude"
    unrelated_cache = unrelated_runtime_dir / "cache"
    unrelated_cache.mkdir(parents=True)
    _mark_complete_install(unrelated_runtime_dir, runtime="claude-code", install_scope="global")
    (unrelated_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "9.0.0",
                "latest": "9.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert "Update available: v1.2.3" in output
    assert "v9.0.0" not in output
    expected = _repair_command("codex", install_scope="local", target_dir=local_runtime_dir, explicit_target=False)
    assert f"Run: {expected}" in output


def test_notify_prefers_installed_global_scope_cache_over_stale_local_scope_cache(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    local_cache = workspace / ".codex" / "cache"
    local_cache.mkdir(parents=True)
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "1.2.3",
                "latest": "1.3.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    global_runtime_dir = home / ".codex"
    global_cache = global_runtime_dir / "cache"
    global_cache.mkdir(parents=True)
    _mark_complete_install(global_runtime_dir, runtime="codex", install_scope="global")
    (global_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": False,
                "installed": "9.0.0",
                "latest": "9.1.0",
                "checked": 10,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert stderr.getvalue() == ""


def test_notify_uses_explicit_workspace_cwd_over_process_cwd(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    local_cache = workspace / ".codex" / "cache"
    local_cache.mkdir(parents=True)
    _mark_complete_install(workspace / ".codex", runtime="codex")
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "2.0.0",
                "latest": "2.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".claude" / "cache").mkdir(parents=True)

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert "Update available: v2.0.0" in output
    assert "Run: npx -y get-physics-done --codex --local" in output


def test_latest_update_cache_uses_runtime_unknown_constant_not_literal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_unknown = "runtime-unknown"

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=None),
        patch("gpd.hooks.notify.resolve_project_root", return_value=workspace),
        patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value=runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected lookup")),
        patch("gpd.hooks.runtime_detect.get_update_cache_candidates", return_value=[]),
    ):
        assert notify_module._latest_update_cache(str(workspace)) == (None, None)


def test_trigger_update_check_uses_sibling_check_update_script(tmp_path: Path) -> None:
    hook_path = tmp_path / "hooks" / "notify.py"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")

    with (
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("gpd.hooks.notify.subprocess.Popen") as mock_popen,
    ):
        notify_module._trigger_update_check(str(tmp_path))

    args = mock_popen.call_args[0][0]
    assert args[1] == str(hook_path.with_name("check_update.py"))


def test_notify_prefers_explicit_target_hook_cache_and_target_dir_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    explicit_target = tmp_path / "custom-runtime-dir"
    hook_path = explicit_target / "hooks" / "notify.py"
    cache_file = explicit_target / "cache" / "gpd-update-check.json"
    hook_path.parent.mkdir(parents=True)
    cache_file.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(explicit_target, runtime="codex")
    cache_file.write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "3.0.0",
                "latest": "3.1.0",
                "checked": 40,
            }
        ),
        encoding="utf-8",
    )
    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert "Update available: v3.0.0" in output
    expected = _repair_command("codex", install_scope="local", target_dir=explicit_target, explicit_target=True)
    assert expected in output


def test_notify_explicit_target_hook_cache_does_not_recover_missing_install_scope_from_legacy_surface(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    explicit_target = tmp_path / "custom-runtime-dir"
    hook_path = explicit_target / "hooks" / "notify.py"
    cache_file = explicit_target / "cache" / "gpd-update-check.json"
    hook_path.parent.mkdir(parents=True)
    cache_file.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(explicit_target, runtime="codex")
    update_workflow = explicit_target / "get-physics-done" / "workflows" / "update.md"
    update_workflow.parent.mkdir(parents=True, exist_ok=True)
    update_workflow.write_text('INSTALL_SCOPE="--local"\n', encoding="utf-8")
    manifest_path = explicit_target / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("install_scope", None)
    manifest["explicit_target"] = True
    manifest["install_target_dir"] = str(explicit_target)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cache_file.write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "3.0.0",
                "latest": "3.1.0",
                "checked": 40,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert output == ""


def test_notify_ignores_unrelated_self_config_cache_when_workspace_has_active_install(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    workspace_runtime_dir = workspace / ".codex"
    workspace_cache = workspace_runtime_dir / "cache"
    workspace_cache.mkdir(parents=True)
    _mark_complete_install(workspace_runtime_dir, runtime="codex")
    (workspace_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "1.2.3",
                "latest": "1.3.0",
                "checked": 20,
            }
        ),
        encoding="utf-8",
    )

    unrelated_runtime_dir = tmp_path / "custom-runtime-dir"
    hook_path = unrelated_runtime_dir / "hooks" / "notify.py"
    unrelated_cache = unrelated_runtime_dir / "cache"
    hook_path.parent.mkdir(parents=True)
    unrelated_cache.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(unrelated_runtime_dir, runtime="codex")
    (unrelated_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "9.0.0",
                "latest": "9.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert "Update available: v1.2.3" in output
    assert "v9.0.0" not in output
    expected = _repair_command("codex", install_scope="local", target_dir=workspace_runtime_dir, explicit_target=False)
    assert expected in output


def test_notify_keeps_target_dir_for_default_named_explicit_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    explicit_target = tmp_path / "custom-parent" / ".codex"
    hook_path = explicit_target / "hooks" / "notify.py"
    cache_file = explicit_target / "cache" / "gpd-update-check.json"
    hook_path.parent.mkdir(parents=True)
    cache_file.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(explicit_target, runtime="codex")
    manifest_path = explicit_target / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["explicit_target"] = True
    manifest["install_target_dir"] = str(explicit_target)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cache_file.write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "3.0.0",
                "latest": "3.1.0",
                "checked": 40,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    expected = _repair_command("codex", install_scope="local", target_dir=explicit_target, explicit_target=True)
    assert expected in output


def test_runtime_less_explicit_target_notify_hook_emits_no_update_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    explicit_target = tmp_path / "custom-runtime-dir"
    hook_path = explicit_target / "hooks" / "notify.py"
    cache_file = explicit_target / "cache" / "gpd-update-check.json"
    hook_path.parent.mkdir(parents=True)
    cache_file.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(explicit_target)
    cache_file.write_text(
        json.dumps({"update_available": True, "installed": "3.0.0", "latest": "3.1.0", "checked": 40}),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert stderr.getvalue() == ""


def test_notify_runtime_directory_without_install_emits_no_update_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    local_cache = workspace / ".codex" / "cache"
    local_cache.mkdir(parents=True)
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "2.0.0",
                "latest": "2.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert stderr.getvalue() == ""


def test_notify_unknown_runtime_falls_back_to_runtime_neutral_update_command(tmp_path: Path) -> None:
    gpd_cache = tmp_path / "GPD" / "cache"
    gpd_cache.mkdir(parents=True)
    (gpd_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "2.0.0",
                "latest": "2.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert f"Run: {update_command_for_runtime('unknown')}" in output
    assert "Run: gpd-update" not in output


def test_notify_ignores_stale_uninstalled_runtime_cache_when_other_runtime_is_installed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    stale_cache = workspace / ".codex" / "cache"
    stale_cache.mkdir(parents=True)
    (stale_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "2.0.0",
                "latest": "2.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    global_runtime_dir = home / ".claude"
    _mark_complete_install(global_runtime_dir, runtime="claude-code", install_scope="global")

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert stderr.getvalue() == ""


def test_notification_state_path_uses_project_layout_observability_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "GPD").mkdir(parents=True)
    nested = workspace / "src" / "notes"
    nested.mkdir(parents=True)

    from gpd.hooks.notify import _notification_state_path

    assert _notification_state_path(str(nested)) == ProjectLayout(workspace).last_observability_notification


def test_hook_payload_policy_prefers_installed_runtime_over_stale_local_runtime_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".codex").mkdir(parents=True)

    home = tmp_path / "home"
    global_runtime_dir = home / ".claude"
    _mark_complete_install(global_runtime_dir, runtime="claude-code", install_scope="global")

    with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
        policy = _hook_payload_policy(str(workspace))

    assert policy.notify_event_types == ()


def test_hook_payload_policy_prefers_self_owned_install_over_workspace_runtime(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    self_owned_runtime_dir = tmp_path / ".codex"
    hook_path = self_owned_runtime_dir / "hooks" / "notify.py"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(self_owned_runtime_dir, runtime="codex")
    _mark_complete_install(workspace / ".claude", runtime="claude-code", install_scope="global")

    with patch("gpd.hooks.notify.__file__", str(hook_path)):
        policy = _hook_payload_policy(str(workspace))

    assert policy.notify_event_types == get_hook_payload_policy("codex").notify_event_types
    assert policy.notify_event_types != get_hook_payload_policy("claude-code").notify_event_types


def test_main_resolves_workspace_before_filtering_event_types(tmp_path: Path) -> None:
    process_cwd = tmp_path / "process-cwd"
    process_cwd.mkdir()
    process_runtime_dir = process_cwd / ".codex"
    _mark_complete_install(process_runtime_dir, runtime="codex")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_runtime_dir = workspace / ".claude"
    _mark_complete_install(workspace_runtime_dir, runtime="claude-code")

    home = tmp_path / "home"
    home.mkdir()
    payload = json.dumps({"type": "session-end", "workspace": str(workspace)})
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=process_cwd),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with(str(workspace))
    mock_notify.assert_called_once_with(str(workspace))


def test_main_uses_self_owned_hook_policy_even_when_workspace_runtime_differs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    self_owned_runtime_dir = tmp_path / ".codex"
    hook_path = self_owned_runtime_dir / "hooks" / "notify.py"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(self_owned_runtime_dir, runtime="codex")
    _mark_complete_install(workspace / ".claude", runtime="claude-code", install_scope="global")

    payload = json.dumps({"type": "session-end", "workspace": str(workspace)})
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_update,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_execution,
    ):
        main()

    mock_trigger.assert_not_called()
    mock_update.assert_not_called()
    mock_execution.assert_not_called()


def test_main_accepts_workspace_mapping_with_cwd_field() -> None:
    expected = str(Path("/tmp/project").resolve(strict=False))
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "workspace": {"cwd": "/tmp/project"}}))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with(expected)
    mock_notify.assert_called_once_with(expected)


def test_workspace_resolution_helpers_keep_raw_workspace_path_distinct_from_project_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    payload = {"workspace": {"cwd": str(nested), "project_dir": str(project)}}

    raw_workspace = notify_module._workspace_dir_from_payload(payload)
    resolved_project = notify_module._resolved_project_root_from_payload(payload, cwd=raw_workspace)

    assert raw_workspace == nested.resolve(strict=False).as_posix()
    assert resolved_project == project.resolve(strict=False).as_posix()
    assert raw_workspace != resolved_project


def test_main_prefers_project_dir_root_over_nested_workspace_cwd(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)

    payload = {"type": "agent-turn-complete", "workspace": {"cwd": str(nested), "project_dir": str(project)}}
    with (
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_execution,
    ):
        main()

    mock_trigger.assert_called_once_with(str(project))
    mock_notify.assert_called_once_with(str(project))
    mock_execution.assert_called_once_with(str(project))


def test_main_prefers_top_level_project_dir_root_over_top_level_cwd(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)

    payload = {"type": "agent-turn-complete", "cwd": str(nested), "project_dir": str(project)}
    with (
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_execution,
    ):
        main()

    mock_trigger.assert_called_once_with(str(project))
    mock_notify.assert_called_once_with(str(project))
    mock_execution.assert_called_once_with(str(project))


def test_main_passes_workspace_and_project_roots_to_usage_recorder_when_supported(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)

    payload = {
        "type": "agent-turn-complete",
        "workspace": {"cwd": str(nested), "project_dir": str(project)},
        "model": {"id": "gpt-5", "provider": "openai"},
        "tokens": {"promptTokens": 120, "completionTokens": 30},
    }
    captured: dict[str, object] = {}

    def _record(
        payload_arg: dict[str, object],
        *,
        runtime: str | None,
        cwd: Path,
        workspace_root: Path,
        project_root: Path,
    ) -> None:
        captured["payload"] = payload_arg
        captured["runtime"] = runtime
        captured["cwd"] = cwd
        captured["workspace_root"] = workspace_root
        captured["project_root"] = project_root

    with (
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value="codex"),
        patch("gpd.hooks.notify._runtime_supports_usage_telemetry", return_value=True),
        patch("gpd.core.costs.record_usage_from_runtime_payload", side_effect=_record) as mock_record,
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_execution,
    ):
        main()

    resolved_nested = nested.resolve(strict=False)
    resolved_project = project.resolve(strict=False)

    mock_record.assert_called_once()
    mock_trigger.assert_called_once_with(str(project))
    mock_notify.assert_called_once_with(str(project))
    mock_execution.assert_called_once_with(str(project))
    assert captured["payload"] == payload
    assert captured["runtime"] == "codex"
    assert captured["cwd"] == resolved_nested
    assert captured["workspace_root"] == resolved_nested
    assert captured["project_root"] == resolved_project
    assert captured["cwd"] == captured["workspace_root"]
    assert captured["workspace_root"] != captured["project_root"]


def test_usage_recorder_kwargs_keep_legacy_cwd_contract_for_old_recorders(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src"
    nested.mkdir(parents=True)

    def _legacy_recorder(payload_arg: dict[str, object], *, runtime: str | None, cwd: Path) -> None:
        del payload_arg, runtime, cwd

    kwargs = notify_module._usage_recorder_kwargs(
        _legacy_recorder,
        runtime="codex",
        workspace_dir=str(nested),
        project_root=str(project),
    )

    assert kwargs == {
        "runtime": "codex",
        "cwd": nested.resolve(strict=False),
    }


def test_main_expands_tilde_workspace_and_project_dir(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "project"
    nested = project / "src"
    nested.mkdir(parents=True)
    payload = {"type": "agent-turn-complete", "workspace": {"cwd": "~/project/src", "project_dir": "~/project"}}

    with (
        patch.dict("os.environ", {"HOME": str(home)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with(str(project))
    mock_notify.assert_called_once_with(str(project))


def test_main_accepts_top_level_cwd_workspace_alias() -> None:
    expected = str(Path("/tmp/project").resolve(strict=False))
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "cwd": "/tmp/project"}))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with(expected)
    mock_notify.assert_called_once_with(expected)


def test_main_accepts_string_workspace_payload() -> None:
    expected = str(Path("/tmp/project").resolve(strict=False))
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "workspace": "/tmp/project"}))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with(expected)
    mock_notify.assert_called_once_with(expected)


def test_main_records_usage_telemetry_from_alias_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data-root"
    payload = {
        "type": "agent-turn-complete",
        "workspace": str(workspace),
        "model": {"id": "gpt-5", "provider": "openai"},
        "tokens": {
            "promptTokens": 120,
            "completionTokens": 30,
            "cacheReadInputTokens": 12,
            "cacheCreationInputTokens": 5,
            "usdCost": 0.42,
        },
    }

    with (
        patch.dict("os.environ", {"GPD_DATA_DIR": str(data_root)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value="codex"),
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
    ):
        main()

    ledger_path = usage_ledger_path(data_root)
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(rows) == 1
    row = rows[0]
    assert row["runtime"] == "codex"
    assert row["provider"] == "openai"
    assert row["model"] == "gpt-5"
    assert row["input_tokens"] == 120
    assert row["output_tokens"] == 30
    assert row["total_tokens"] == 150
    assert row["cached_input_tokens"] == 12
    assert row["cache_write_input_tokens"] == 5
    assert row["cost_usd"] == 0.42
    assert row["cost_status"] == "measured"
    assert row["agent_scope"] == "unknown"
    assert row["agent_attribution_source"] == "unknown"


def test_main_records_workspace_state_subagent_attribution(tmp_path: Path) -> None:
    project = tmp_path / "workspace"
    nested = project / "src"
    nested.mkdir(parents=True)
    data_root = tmp_path / "data-root"
    (project / "GPD").mkdir(parents=True, exist_ok=True)
    (project / "GPD" / "current-agent-id.txt").write_text("agent-77\n", encoding="utf-8")
    _write_current_execution(
        project,
        {
            "session_id": "sess-subagent",
            "segment_status": "active",
            "current_task": "Run executor task",
        },
    )
    payload = {
        "type": "agent-turn-complete",
        "workspace": {"cwd": str(nested), "project_dir": str(project)},
        "model": {"id": "gpt-5", "provider": "openai"},
        "tokens": {
            "promptTokens": 120,
            "completionTokens": 30,
            "usdCost": 0.42,
        },
    }

    with (
        patch.dict("os.environ", {"GPD_DATA_DIR": str(data_root)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value="codex"),
        patch("gpd.core.costs.get_current_session_id", return_value="sess-subagent"),
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
    ):
        main()

    ledger_path = usage_ledger_path(data_root)
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(rows) == 1
    row = rows[0]
    assert row["workspace_root"] == nested.resolve(strict=False).as_posix()
    assert row["project_root"] == project.resolve(strict=False).as_posix()
    assert row["workspace_root"] != row["project_root"]
    assert row["agent_scope"] == "subagent"
    assert row["agent_id"] == "agent-77"
    assert row["agent_attribution_source"] == "workspace-state"
    assert row["agent_id_source"] == "workspace.current-agent-id"


def test_main_does_not_record_usage_when_runtime_capability_is_unknown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data-root"
    payload = {
        "type": "agent-turn-complete",
        "workspace": str(workspace),
        "model": {"id": "gpt-5", "provider": "openai"},
        "tokens": {
            "promptTokens": 120,
            "completionTokens": 30,
            "usdCost": 0.42,
        },
    }

    with (
        patch.dict("os.environ", {"GPD_DATA_DIR": str(data_root)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value=None),
        patch("gpd.core.costs.record_usage_from_runtime_payload") as mock_record,
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
    ):
        main()

    mock_record.assert_not_called()
    assert not usage_ledger_path(data_root).exists()


def test_main_does_not_record_usage_when_runtime_capability_excludes_notify_telemetry(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data-root"
    payload = {
        "type": "agent-turn-complete",
        "workspace": str(workspace),
        "model": {"id": "gpt-5", "provider": "openai"},
        "tokens": {
            "promptTokens": 120,
            "completionTokens": 30,
            "usdCost": 0.42,
        },
    }

    with (
        patch.dict("os.environ", {"GPD_DATA_DIR": str(data_root)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value="claude-code"),
        patch("gpd.core.costs.record_usage_from_runtime_payload") as mock_record,
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
    ):
        main()

    mock_record.assert_not_called()
    assert not usage_ledger_path(data_root).exists()


def test_main_logs_usage_skip_when_runtime_capability_is_unknown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    payload = json.dumps({"type": "agent-turn-complete", "workspace": str(workspace)})
    stderr = io.StringIO()

    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.notify._payload_runtime", return_value=""),
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        main()

    assert "usage telemetry skipped: runtime capability unknown or unsupported" in stderr.getvalue()


def test_main_does_not_record_usage_when_usage_container_has_no_token_or_cost_signal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data-root"
    payload = {
        "type": "agent-turn-complete",
        "workspace": str(workspace),
        "model": {"id": "gpt-5", "provider": "openai"},
        "token_usage": {"requestCount": 1},
    }

    with (
        patch.dict("os.environ", {"GPD_DATA_DIR": str(data_root)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value="codex"),
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
    ):
        main()

    assert not usage_ledger_path(data_root).exists()


def test_main_logs_handler_exception_instead_of_swallowing(tmp_path: Path) -> None:
    """Exceptions in _trigger_update_check / _check_and_notify_update are logged via _debug."""
    payload = json.dumps({"type": "agent-turn-complete", "workspace": "/tmp/project"})
    stderr = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.notify._trigger_update_check", side_effect=RuntimeError("boom")),
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        # Should not raise — the exception is caught and logged
        main()

    output = stderr.getvalue()
    assert "notify handler failed: boom" in output


def test_main_treats_usage_telemetry_failures_as_advisory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    payload = json.dumps({"type": "agent-turn-complete", "workspace": str(workspace)})
    stderr = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.notify._payload_runtime", return_value="codex"),
        patch("gpd.core.costs.record_usage_from_runtime_payload", side_effect=RuntimeError("telemetry boom")),
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification") as mock_emit,
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        main()

    assert "usage telemetry skipped: telemetry boom" in stderr.getvalue()
    mock_emit.assert_called_once_with(str(workspace.resolve(strict=False)))


def test_main_logs_workspace_resolution_exception_instead_of_raising() -> None:
    payload = json.dumps({"type": "agent-turn-complete", "workspace": "/tmp/project"})
    stderr = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.notify._resolved_project_root_from_payload", side_effect=RuntimeError("boom")),
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        main()

    assert "notify handler failed: boom" in stderr.getvalue()


def test_emit_execution_notification_for_first_result_gate(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-1",
            "first_result_gate_pending": True,
            "last_result_label": "Benchmark reproduction",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    assert "First-result review due for 03-01" in stderr.getvalue()
    assert "Benchmark reproduction" in stderr.getvalue()


def test_emit_execution_notification_walks_up_from_nested_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    nested = workspace / "src" / "notes"
    nested.mkdir(parents=True)
    _write_current_execution(
        workspace,
        {
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-1",
            "first_result_gate_pending": True,
            "last_result_label": "Benchmark reproduction",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(nested))

    assert "First-result review due for 03-01" in stderr.getvalue()


def test_emit_execution_notification_for_pre_fanout_review(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "05",
            "plan": "03",
            "segment_id": "seg-9",
            "segment_status": "waiting_review",
            "waiting_for_review": True,
            "checkpoint_reason": "pre_fanout",
            "pre_fanout_review_pending": True,
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    assert "Pre-fanout review due for 05-03" in stderr.getvalue()


def test_emit_execution_notification_prefers_review_over_resume_for_bounded_gate_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "05",
            "plan": "03",
            "segment_id": "seg-9",
            "segment_status": "paused",
            "resume_file": "GPD/phases/05/.continue-here.md",
            "checkpoint_reason": "pre_fanout",
            "pre_fanout_review_pending": True,
            "downstream_locked": True,
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    assert "Pre-fanout review due for 05-03" in stderr.getvalue()
    assert "Resume ready" not in stderr.getvalue()


def test_emit_execution_notification_for_skeptical_review_uses_anchor_focus(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "05",
            "plan": "04",
            "segment_id": "seg-10",
            "segment_status": "waiting_review",
            "waiting_for_review": True,
            "checkpoint_reason": "pre_fanout",
            "pre_fanout_review_pending": True,
            "skeptical_requestioning_required": True,
            "weakest_unchecked_anchor": "Direct observable benchmark",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert "Skeptical pre-fanout review due for 05-04" in output
    assert "Direct observable benchmark" in output


def test_emit_execution_notification_keeps_pre_fanout_review_until_clear_even_if_unlocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "05",
            "plan": "05",
            "segment_id": "seg-11",
            "segment_status": "waiting_review",
            "checkpoint_reason": "pre_fanout",
            "pre_fanout_review_pending": True,
            "downstream_locked": False,
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    assert "Pre-fanout review due for 05-05" in stderr.getvalue()


def test_emit_execution_notification_does_not_claim_stuck(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "06",
            "plan": "01",
            "segment_id": "seg-12",
            "segment_status": "blocked",
            "blocked_reason": "anchor mismatch",
            "waiting_reason": "time_budget_exceeded",
            "waiting_for_review": True,
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue().lower()
    assert "stuck" not in output
    assert "blocked in 06-01" in output or "waiting in 06-01" in output
    assert "time budget exceeded" in output or "anchor mismatch" in output


def test_emit_execution_notification_dedupes_repeated_resume_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "04",
            "plan": "02",
            "segment_id": "seg-2",
            "segment_status": "paused",
            "resume_file": "GPD/phases/04/.continue-here.md",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert output.count("Resume ready for 04-02") == 1


def test_emit_execution_notification_for_paused_state_without_resume_file_is_conservative(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "04",
            "plan": "03",
            "segment_id": "seg-3",
            "segment_status": "paused",
            "last_result_label": "Recent artifact",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert "Paused in 04-03" in output
    assert "Resume ready" not in output


def test_emit_execution_notification_dedupes_concurrent_resume_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    barrier = threading.Barrier(2)

    class _SlowStderr:
        def __init__(self) -> None:
            self._chunks: list[str] = []
            self._lock = threading.Lock()

        def write(self, message: str) -> int:
            time.sleep(0.05)
            with self._lock:
                self._chunks.append(message)
            return len(message)

        def getvalue(self) -> str:
            with self._lock:
                return "".join(self._chunks)

    def _message(_cwd: str) -> tuple[str, str]:
        barrier.wait(timeout=1)
        return (
            "[GPD] Resume ready for 04-02: GPD/phases/04/.continue-here.md\n",
            "resume:seg-2",
        )

    stderr = _SlowStderr()
    errors: list[BaseException] = []

    def _emit() -> None:
        try:
            _emit_execution_notification(str(workspace))
        except BaseException as exc:  # pragma: no cover - surfaced via assertion below
            errors.append(exc)

    with (
        patch("gpd.hooks.notify._execution_notification_message", side_effect=_message),
        patch("sys.stderr", stderr),
    ):
        threads = [threading.Thread(target=_emit), threading.Thread(target=_emit)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert errors == []
    assert stderr.getvalue().count("Resume ready for 04-02") == 1
    state = json.loads(ProjectLayout(workspace).last_observability_notification.read_text(encoding="utf-8"))
    assert state["fingerprint"] == "resume:seg-2"
