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
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.hooks.notify import _check_and_notify_update, _emit_execution_notification, _hook_payload_policy, main

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
            (config_dir.parent / ".agents" / "skills" / "gpd-help").mkdir(parents=True, exist_ok=True)
    else:
        (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {"install_scope": install_scope}
    if runtime is not None:
        manifest["runtime"] = runtime
        if runtime == "codex":
            manifest["codex_skills_dir"] = str(config_dir.parent / ".agents" / "skills")
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
        patch("gpd.hooks.notify._self_config_dir", return_value=None),
        patch("gpd.hooks.notify.resolve_project_root", return_value=workspace),
        patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value=runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected lookup")),
        patch("gpd.hooks.runtime_detect.get_update_cache_candidates", return_value=[]),
    ):
        assert notify_module._latest_update_cache(str(workspace)) == (None, None)


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


def test_notify_explicit_target_hook_cache_recovers_missing_install_scope_from_installed_surface(tmp_path: Path) -> None:
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
    expected = _repair_command("codex", install_scope="local", target_dir=explicit_target, explicit_target=True)
    assert expected in output


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
    (explicit_target / "gpd-file-manifest.json").write_text(
        json.dumps(
            {
                "install_scope": "local",
                "runtime": "codex",
                "explicit_target": True,
                "install_target_dir": str(explicit_target),
            }
        ),
        encoding="utf-8",
    )
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


def test_main_logs_workspace_resolution_exception_instead_of_raising() -> None:
    payload = json.dumps({"type": "agent-turn-complete", "workspace": "/tmp/project"})
    stderr = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.notify._workspace_from_payload", side_effect=RuntimeError("boom")),
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
    state = json.loads((workspace / "GPD" / "observability" / "last-notify.json").read_text(encoding="utf-8"))
    assert state["fingerprint"] == "resume:seg-2"
