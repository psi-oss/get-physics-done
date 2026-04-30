"""Tests for gpd/hooks/notify.py."""

from __future__ import annotations

import io
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest

import gpd.hooks.notify as notify_module
from gpd.adapters.runtime_catalog import get_hook_payload_policy, iter_runtime_descriptors
from gpd.core.constants import (
    HOME_DATA_DIR_NAME,
    OBSERVABILITY_DIR_NAME,
    OBSERVABILITY_LAST_NOTIFY_FILENAME,
    ProjectLayout,
)
from gpd.core.costs import usage_ledger_path
from gpd.hooks.notify import _check_and_notify_update, _emit_execution_notification, _hook_payload_policy, main
from tests.hooks.helpers import mark_complete_install as _mark_complete_install
from tests.hooks.helpers import repair_command as _repair_command

_TELEMETRY_RUNTIME = next(
    descriptor.runtime_name
    for descriptor in iter_runtime_descriptors()
    if descriptor.capabilities.telemetry_completeness != "none"
)
_TEST_PROVIDER = "provider-under-test"
_TEST_MODEL = "model-under-test"


def _write_current_execution(workspace: Path, payload: dict[str, object]) -> None:
    observability = workspace / "GPD" / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    (workspace / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (observability / "current-execution.json").write_text(json.dumps(payload), encoding="utf-8")


class _ExecutionSnapshot(SimpleNamespace):
    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return dict(self.__dict__)

    def __getattr__(self, name: str) -> object:
        return None


def test_notify_uses_latest_local_cache_and_scoped_codex_install_command(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home_cache = home / ".gpd" / "cache"
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


def test_notify_dedupes_repeated_update_notices(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    local_runtime_dir = workspace / ".codex"
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

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert output.count("Update available: v1.2.3") == 1


def test_notify_keeps_update_and_execution_fingerprints_isolated(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "GPD").mkdir(parents=True)

    stderr = io.StringIO()
    update_cache = {
        "update_available": True,
        "installed": "1.2.3",
        "latest": "1.3.0",
        "checked": 20,
    }

    with (
        patch("gpd.hooks.notify._latest_update_cache", return_value=(update_cache, object())),
        patch("gpd.hooks.notify._shared_update_command_for_candidate", return_value="runtime-update-command"),
        patch("gpd.hooks.notify._execution_notification_message", return_value=("[GPD] Execution review due\n", "resume:seg-2")),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))
        _emit_execution_notification(str(workspace))
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert output.count("Update available: v1.2.3") == 1
    assert output.count("Execution review due") == 1
    state = json.loads(ProjectLayout(workspace).last_observability_notification.read_text(encoding="utf-8"))
    assert state["update_fingerprint"] == "update:1.2.3:1.3.0:runtime-update-command"
    assert state["execution_fingerprint"] == "resume:seg-2"
    assert "fingerprint" not in state


def test_check_and_notify_update_reads_lookup_cache_but_claims_project_state(tmp_path: Path) -> None:
    lookup_dir = tmp_path / "project" / "src" / "notes"
    lookup_dir.mkdir(parents=True)
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    (project / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    update_cache = {
        "update_available": True,
        "installed": "1.2.3",
        "latest": "1.3.0",
        "checked": 20,
    }
    candidate = object()
    stderr = io.StringIO()

    with (
        patch("gpd.hooks.notify._latest_update_cache", return_value=(update_cache, candidate)) as mock_latest,
        patch("gpd.hooks.notify._shared_update_command_for_candidate", return_value="runtime-update-command") as mock_command,
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(lookup_dir), state_cwd=str(project))

    mock_latest.assert_called_once_with(str(lookup_dir))
    mock_command.assert_called_once_with(candidate, hook_file=notify_module.__file__, cwd=str(lookup_dir))
    assert "Update available: v1.2.3" in stderr.getvalue()
    state = json.loads(ProjectLayout(project).last_observability_notification.read_text(encoding="utf-8"))
    assert state["update_fingerprint"] == "update:1.2.3:1.3.0:runtime-update-command"


def test_emit_execution_notification_still_emits_when_dedupe_persistence_fails(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify._execution_notification_message", return_value=("[GPD] Execution review due\n", "resume:seg-2")),
        patch("gpd.hooks.notify._claim_last_notification", return_value=None),
        patch("sys.stderr", stderr),
    ):
        _emit_execution_notification(str(workspace))

    assert "Execution review due" in stderr.getvalue()


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
        patch("gpd.hooks.notify.Path.home", return_value=tmp_path / "home"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert "Update available: v3.0.0" in output
    expected = _repair_command("codex", install_scope="local", target_dir=explicit_target, explicit_target=True)
    assert expected in output


def test_notify_explicit_target_hook_cache_does_not_recover_missing_install_scope_from_stale_surface(tmp_path: Path) -> None:
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
        patch("gpd.hooks.notify.Path.home", return_value=tmp_path / "home"),
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
        patch("gpd.hooks.notify.Path.home", return_value=tmp_path / "home"),
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


def test_notify_skips_closed_contract_payload_without_event_type(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    payload = json.dumps({"workspace": {"cwd": str(workspace)}})

    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch(
            "gpd.hooks.notify._resolve_payload_roots",
            return_value=SimpleNamespace(
                workspace_dir=str(workspace),
                project_root=str(workspace),
                project_dir_present=False,
                project_dir_trusted=False,
            ),
        ),
        patch("gpd.hooks.notify._hook_payload_policy", return_value=SimpleNamespace(notify_event_types=("agent-turn-complete",))),
        patch("gpd.hooks.notify._record_usage_telemetry") as mock_telemetry,
        patch("gpd.hooks.notify._trigger_update_check") as mock_update,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_exec,
    ):
        main()

    mock_telemetry.assert_not_called()
    mock_update.assert_not_called()
    mock_notify.assert_not_called()
    mock_exec.assert_not_called()


def test_record_usage_telemetry_uses_workspace_dir_for_runtime_selection(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    payload = {"type": "agent-turn-complete"}
    observed_cwd: list[str | None] = []

    def _fake_payload_runtime(cwd: str | None = None) -> str | None:
        observed_cwd.append(cwd)
        return _TELEMETRY_RUNTIME

    with (
        patch("gpd.hooks.notify._payload_runtime", side_effect=_fake_payload_runtime),
        patch("gpd.hooks.notify._runtime_supports_usage_telemetry", return_value=True),
        patch("gpd.core.costs.record_usage_from_runtime_payload") as mock_record,
    ):
        notify_module._record_usage_telemetry(payload, workspace_dir=str(nested), project_root=str(project))

    assert observed_cwd == [str(nested)]
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["runtime"] == _TELEMETRY_RUNTIME


def test_record_usage_telemetry_prefers_resolved_active_runtime_when_supplied(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    payload = {"type": "agent-turn-complete"}

    with (
        patch("gpd.hooks.notify._payload_runtime") as mock_payload_runtime,
        patch("gpd.hooks.notify._runtime_supports_usage_telemetry", return_value=True),
        patch("gpd.core.costs.record_usage_from_runtime_payload") as mock_record,
    ):
        notify_module._record_usage_telemetry(
            payload,
            workspace_dir=str(nested),
            project_root=str(project),
            active_runtime=_TELEMETRY_RUNTIME,
        )

    mock_payload_runtime.assert_not_called()
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["runtime"] == _TELEMETRY_RUNTIME


def test_notify_home_update_cache_without_live_install_emits_no_update_command(tmp_path: Path) -> None:
    home_cache = tmp_path / "home" / ".gpd" / "cache"
    home_cache.mkdir(parents=True)
    (home_cache / "gpd-update-check.json").write_text(
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
        patch.dict("os.environ", {"GPD_DATA_DIR": ""}),
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert output == ""


def test_notify_ignores_stale_project_local_update_cache(tmp_path: Path) -> None:
    project_cache = tmp_path / "GPD" / "cache"
    project_cache.mkdir(parents=True)
    (project_cache / "gpd-update-check.json").write_text(
        json.dumps({"update_available": True, "installed": "2.0.0", "latest": "2.1.0", "checked": 30}),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    assert stderr.getvalue() == ""


def test_notification_state_path_uses_project_layout_observability_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "GPD").mkdir(parents=True)
    (workspace / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    nested = workspace / "src" / "notes"
    nested.mkdir(parents=True)

    from gpd.hooks.notify import _notification_state_path

    assert _notification_state_path(str(nested)) == ProjectLayout(workspace).last_observability_notification


def test_notification_state_path_ignores_empty_ancestor_gpd(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "GPD").mkdir(parents=True)
    nested = workspace / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    expected = home / HOME_DATA_DIR_NAME / OBSERVABILITY_DIR_NAME / OBSERVABILITY_LAST_NOTIFY_FILENAME

    from gpd.hooks.notify import _notification_state_path

    with patch("gpd.hooks.notify.Path.home", return_value=home):
        assert _notification_state_path(str(nested)) == expected


def test_notification_state_path_uses_home_data_root_outside_project_layout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    expected = home / HOME_DATA_DIR_NAME / OBSERVABILITY_DIR_NAME / OBSERVABILITY_LAST_NOTIFY_FILENAME

    from gpd.hooks.notify import _notification_state_path

    with patch("gpd.hooks.notify.Path.home", return_value=home):
        assert _notification_state_path(str(workspace)) == expected


def test_notification_state_path_prefers_self_owned_install_outside_project_layout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    self_owned_runtime_dir = tmp_path / ".codex"
    hook_path = self_owned_runtime_dir / "hooks" / "notify.py"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(self_owned_runtime_dir, runtime="codex")

    from gpd.hooks.notify import _notification_state_path

    with patch("gpd.hooks.notify.__file__", str(hook_path)):
        assert _notification_state_path(str(workspace)) == (
            self_owned_runtime_dir / OBSERVABILITY_DIR_NAME / OBSERVABILITY_LAST_NOTIFY_FILENAME
        )


def test_check_and_notify_update_uses_home_state_without_creating_workspace_gpd(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    state_path = home / HOME_DATA_DIR_NAME / OBSERVABILITY_DIR_NAME / OBSERVABILITY_LAST_NOTIFY_FILENAME

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.Path.home", return_value=home),
        patch(
            "gpd.hooks.notify._latest_update_cache",
            return_value=(
                {
                    "update_available": True,
                    "installed": "1.2.3",
                    "latest": "1.3.0",
                    "checked": 20,
                },
                object(),
            ),
        ),
        patch("gpd.hooks.notify._shared_update_command_for_candidate", return_value="runtime-update-command"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert "Update available: v1.2.3" in stderr.getvalue()
    assert not (workspace / "GPD").exists()
    assert state_path.exists()


def test_check_and_notify_update_prefers_self_owned_state_outside_project_layout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    self_owned_runtime_dir = tmp_path / ".codex"
    hook_path = self_owned_runtime_dir / "hooks" / "notify.py"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(self_owned_runtime_dir, runtime="codex")

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.__file__", str(hook_path)),
        patch("gpd.hooks.notify.Path.home", side_effect=AssertionError("home fallback should not be used")),
        patch(
            "gpd.hooks.notify._latest_update_cache",
            return_value=(
                {
                    "update_available": True,
                    "installed": "1.2.3",
                    "latest": "1.3.0",
                    "checked": 20,
                },
                object(),
            ),
        ),
        patch("gpd.hooks.notify._shared_update_command_for_candidate", return_value="runtime-update-command"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert "Update available: v1.2.3" in stderr.getvalue()
    state_path = self_owned_runtime_dir / OBSERVABILITY_DIR_NAME / OBSERVABILITY_LAST_NOTIFY_FILENAME
    assert state_path.exists()


@pytest.mark.parametrize(
    ("patch_target", "error_message"),
    [
        ("gpd.hooks.notify.file_lock", "lock denied"),
        ("gpd.hooks.notify.atomic_write", "write denied"),
    ],
)
def test_check_and_notify_update_stays_advisory_when_notification_state_persistence_fails(
    tmp_path: Path,
    patch_target: str,
    error_message: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.notify.Path.home", return_value=home),
        patch(
            "gpd.hooks.notify._latest_update_cache",
            return_value=(
                {
                    "update_available": True,
                    "installed": "1.2.3",
                    "latest": "1.3.0",
                    "checked": 20,
                },
                object(),
            ),
        ),
        patch("gpd.hooks.notify._shared_update_command_for_candidate", return_value="runtime-update-command"),
        patch(patch_target, side_effect=PermissionError(error_message)),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert "Update available: v1.2.3" in stderr.getvalue()


def test_emit_execution_notification_scopes_home_fallback_dedupe_per_workspace(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    stderr = io.StringIO()

    with (
        patch("gpd.hooks.notify.Path.home", return_value=home),
        patch(
            "gpd.hooks.notify._execution_notification_message",
            return_value=("[GPD] First-result review due for 03-01: rerun anchor: result-42\n", "first-result:seg-1"),
        ),
        patch("sys.stderr", stderr),
    ):
        _emit_execution_notification(str(workspace_a))
        _emit_execution_notification(str(workspace_b))

    output = stderr.getvalue()
    assert output.count("First-result review due for 03-01") == 2
    assert output.count("rerun anchor: result-42") == 2


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
    mock_notify.assert_called_once_with(str(workspace), state_cwd=str(workspace))


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


def test_main_uses_self_owned_hook_policy_with_alias_only_workspace_payload(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    self_owned_runtime_dir = tmp_path / ".codex"
    hook_path = self_owned_runtime_dir / "hooks" / "notify.py"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    _mark_complete_install(self_owned_runtime_dir, runtime="codex")
    _mark_complete_install(workspace / ".claude", runtime="claude-code", install_scope="global")

    payload = json.dumps({"type": "session-end", "workspace": {"current_dir": str(workspace)}})
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
    mock_notify.assert_called_once_with(expected, state_cwd=expected)


def test_main_passes_workspace_and_project_roots_to_usage_recorder_when_supported(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    (project / "GPD").mkdir()

    payload = {
        "type": "agent-turn-complete",
        "workspace": {"cwd": str(nested), "project_dir": str(project)},
        "model": {"id": _TEST_MODEL, "provider": _TEST_PROVIDER},
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
        patch("gpd.hooks.notify._hook_payload_policy", return_value=get_hook_payload_policy(_TELEMETRY_RUNTIME)),
        patch("gpd.hooks.notify._payload_runtime", return_value=_TELEMETRY_RUNTIME),
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
    mock_notify.assert_called_once_with(str(project), state_cwd=str(project))
    mock_execution.assert_called_once_with(str(project))
    assert captured["payload"] == payload
    assert captured["runtime"] == _TELEMETRY_RUNTIME
    assert captured["cwd"] == resolved_nested
    assert captured["workspace_root"] == resolved_nested
    assert captured["project_root"] == resolved_project
    assert captured["cwd"] == captured["workspace_root"]
    assert captured["workspace_root"] != captured["project_root"]


def test_main_does_not_promote_project_dir_when_policy_has_no_project_dir_keys(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    (project / "GPD").mkdir()
    payload = {
        "type": "agent-turn-complete",
        "workspace": {"cwd": str(nested)},
        "project_dir": str(project),
    }
    hook_payload = SimpleNamespace(
        notify_event_types=(),
        workspace_keys=(),
        project_dir_keys=(),
    )

    with (
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch(
            "gpd.hooks.notify._resolve_payload_roots",
            return_value=SimpleNamespace(
                workspace_dir=str(nested),
                project_root=str(nested),
                project_dir_present=False,
                project_dir_trusted=False,
            ),
        ),
        patch(
            "gpd.hooks.notify.resolve_runtime_lookup_context_from_payload_roots",
            return_value=SimpleNamespace(lookup_dir=str(nested), active_runtime=_TELEMETRY_RUNTIME),
        ) as mock_runtime_lookup,
        patch("gpd.hooks.notify._hook_payload_policy", return_value=hook_payload) as mock_policy,
        patch("gpd.hooks.notify._record_usage_telemetry") as mock_telemetry,
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_update,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_execution,
    ):
        main()

    mock_runtime_lookup.assert_called_once()
    assert mock_policy.call_args_list == [call(str(nested)), call(str(nested))]
    mock_telemetry.assert_called_once_with(
        payload,
        workspace_dir=str(nested),
        project_root=str(nested),
        active_runtime=_TELEMETRY_RUNTIME,
    )
    mock_trigger.assert_called_once_with(str(nested))
    mock_update.assert_called_once_with(str(nested), state_cwd=str(nested))
    mock_execution.assert_called_once_with(str(nested))


def test_main_uses_policy_declared_project_root_alias_for_side_effects(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    (project / "GPD").mkdir()
    payload = {
        "type": "agent-turn-complete",
        "workspace": {"cwd": str(nested)},
        "project_root": str(project),
    }
    hook_payload = SimpleNamespace(
        notify_event_types=(),
        workspace_keys=("cwd",),
        project_dir_keys=("project_root",),
    )

    with (
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch(
            "gpd.hooks.notify.resolve_runtime_lookup_context_from_payload_roots",
            return_value=SimpleNamespace(lookup_dir=str(nested), active_runtime=_TELEMETRY_RUNTIME),
        ) as mock_runtime_lookup,
        patch("gpd.hooks.notify._hook_payload_policy", return_value=hook_payload) as mock_policy,
        patch("gpd.hooks.notify._record_usage_telemetry") as mock_telemetry,
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_update,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_execution,
    ):
        main()

    resolved_project = str(project.resolve(strict=False))
    mock_runtime_lookup.assert_called_once()
    assert call(str(nested)) in mock_policy.call_args_list
    mock_telemetry.assert_called_once_with(
        payload,
        workspace_dir=str(nested.resolve(strict=False)),
        project_root=resolved_project,
        active_runtime=_TELEMETRY_RUNTIME,
    )
    mock_trigger.assert_called_once_with(str(nested))
    mock_update.assert_called_once_with(str(nested), state_cwd=resolved_project)
    mock_execution.assert_called_once_with(resolved_project)


def test_main_does_not_promote_project_dir_for_alias_only_workspace_payload(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    (project / "GPD").mkdir()
    payload = {
        "type": "agent-turn-complete",
        "workspace": {"current_dir": str(nested), "project_dir": str(project)},
    }
    hook_payload = SimpleNamespace(
        notify_event_types=(),
        workspace_keys=("cwd", "current_dir"),
        project_dir_keys=("project_dir",),
    )

    with (
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch(
            "gpd.hooks.notify._resolve_payload_roots",
            return_value=SimpleNamespace(
                workspace_dir=str(nested),
                project_root=str(project),
                project_dir_present=True,
                project_dir_trusted=True,
            ),
        ),
        patch(
            "gpd.hooks.notify.resolve_runtime_lookup_context_from_payload_roots",
            return_value=SimpleNamespace(lookup_dir=str(nested), active_runtime=_TELEMETRY_RUNTIME),
        ) as mock_runtime_lookup,
        patch("gpd.hooks.notify._hook_payload_policy", return_value=hook_payload) as mock_policy,
        patch("gpd.hooks.notify._record_usage_telemetry") as mock_telemetry,
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_update,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_execution,
    ):
        main()

    mock_runtime_lookup.assert_called_once()
    runtime_roots = mock_runtime_lookup.call_args.args[0]
    assert runtime_roots.project_root == str(project)
    assert runtime_roots.project_dir_trusted is False
    assert mock_policy.call_args_list == [call(str(nested)), call(str(nested))]
    mock_telemetry.assert_called_once_with(
        payload,
        workspace_dir=str(nested),
        project_root=str(nested),
        active_runtime=_TELEMETRY_RUNTIME,
    )
    mock_trigger.assert_called_once_with(str(nested))
    mock_update.assert_called_once_with(str(nested), state_cwd=str(nested))
    mock_execution.assert_called_once_with(str(nested))


def test_main_expands_tilde_workspace_and_project_dir(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "project"
    nested = project / "src"
    nested.mkdir(parents=True)
    (project / "GPD").mkdir()
    payload = {"type": "agent-turn-complete", "workspace": {"cwd": "~/project/src", "project_dir": "~/project"}}

    with (
        patch.dict("os.environ", {"HOME": str(home), "USERPROFILE": str(home)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with(str(project))
    mock_notify.assert_called_once_with(str(project), state_cwd=str(project))


def test_main_defaults_project_root_to_workspace_dir_when_project_dir_is_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "workspace": str(workspace)}))),
        patch(
            "gpd.hooks.notify._resolve_payload_roots",
            return_value=SimpleNamespace(
                workspace_dir=str(workspace.resolve(strict=False)),
                project_root=str(workspace.parent.resolve(strict=False)),
                project_dir_present=False,
                project_dir_trusted=False,
            ),
        ),
        patch("gpd.hooks.notify._hook_payload_policy", return_value=SimpleNamespace(project_dir_keys=("project_dir",), notify_event_types=())),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
        patch("gpd.hooks.notify._emit_execution_notification") as mock_exec,
        patch("gpd.hooks.notify._record_usage_telemetry") as mock_telemetry,
    ):
        main()

    mock_telemetry.assert_called_once()
    mock_trigger.assert_called_once_with(str(workspace.resolve(strict=False)))
    mock_notify.assert_called_once_with(
        str(workspace.resolve(strict=False)),
        state_cwd=str(workspace.resolve(strict=False)),
    )
    mock_exec.assert_called_once_with(str(workspace.resolve(strict=False)))


def test_main_records_usage_telemetry_from_alias_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data-root"
    payload = {
        "type": "agent-turn-complete",
        "workspace": str(workspace),
        "model": {"id": _TEST_MODEL, "provider": _TEST_PROVIDER},
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
        patch("gpd.hooks.notify._payload_runtime", return_value=_TELEMETRY_RUNTIME),
        patch("gpd.hooks.notify._runtime_supports_usage_telemetry", return_value=True),
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
    ):
        main()

    ledger_path = usage_ledger_path(data_root)
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(rows) == 1
    row = rows[0]
    assert row["runtime"] == _TELEMETRY_RUNTIME
    assert row["provider"] == _TEST_PROVIDER
    assert row["model"] == _TEST_MODEL
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
        "model": {"id": _TEST_MODEL, "provider": _TEST_PROVIDER},
        "tokens": {
            "promptTokens": 120,
            "completionTokens": 30,
            "usdCost": 0.42,
        },
    }

    with (
        patch.dict("os.environ", {"GPD_DATA_DIR": str(data_root)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value=_TELEMETRY_RUNTIME),
        patch("gpd.hooks.notify._runtime_supports_usage_telemetry", return_value=True),
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
        "model": {"id": _TEST_MODEL, "provider": _TEST_PROVIDER},
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


def test_runtime_supports_usage_telemetry_returns_false_for_unknown_runtime() -> None:
    with patch("gpd.adapters.runtime_catalog.get_runtime_capabilities", side_effect=KeyError("unknown runtime")):
        assert notify_module._runtime_supports_usage_telemetry("broken-runtime") is False


def test_runtime_supports_usage_telemetry_propagates_unexpected_runtime_catalog_errors() -> None:
    with patch(
        "gpd.adapters.runtime_catalog.get_runtime_capabilities",
        side_effect=RuntimeError("catalog boom"),
    ):
        with pytest.raises(RuntimeError, match="catalog boom"):
            notify_module._runtime_supports_usage_telemetry("broken-runtime")


def test_main_does_not_record_usage_when_usage_container_has_no_token_or_cost_signal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data-root"
    payload = {
        "type": "agent-turn-complete",
        "workspace": str(workspace),
        "model": {"id": _TEST_MODEL, "provider": _TEST_PROVIDER},
        "token_usage": {"requestCount": 1},
    }

    with (
        patch.dict("os.environ", {"GPD_DATA_DIR": str(data_root)}),
        patch("sys.stdin", io.StringIO(json.dumps(payload))),
        patch("gpd.hooks.notify._payload_runtime", return_value=_TELEMETRY_RUNTIME),
        patch("gpd.hooks.notify._runtime_supports_usage_telemetry", return_value=True),
        patch("gpd.hooks.notify._trigger_update_check"),
        patch("gpd.hooks.notify._check_and_notify_update"),
        patch("gpd.hooks.notify._emit_execution_notification"),
    ):
        main()

    assert not usage_ledger_path(data_root).exists()


def test_record_usage_telemetry_logs_advisory_when_runtime_capability_lookup_fails_unexpectedly(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    stderr = io.StringIO()

    with (
        patch("gpd.adapters.runtime_catalog.get_runtime_capabilities", side_effect=RuntimeError("catalog boom")),
        patch("gpd.core.costs.record_usage_from_runtime_payload") as mock_record,
        patch("gpd.hooks.notify._debug") as mock_debug,
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        notify_module._record_usage_telemetry(
            {"type": "agent-turn-complete"},
            workspace_dir=str(workspace),
            project_root=str(workspace),
            active_runtime="broken-runtime",
        )

    mock_record.assert_not_called()
    mock_debug.assert_called_once_with("usage telemetry skipped: catalog boom")


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
        patch("gpd.hooks.notify._payload_runtime", return_value=_TELEMETRY_RUNTIME),
        patch("gpd.hooks.notify._runtime_supports_usage_telemetry", return_value=True),
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
        patch("gpd.hooks.notify._resolve_payload_roots", side_effect=RuntimeError("boom")),
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        main()

    assert "notify handler failed: boom" in stderr.getvalue()


def test_emit_execution_notification_for_first_result_gate(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "GPD").mkdir()
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


def test_emit_execution_notification_falls_back_to_last_result_id_when_no_label_or_task(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "GPD").mkdir()
    snapshot = _ExecutionSnapshot(
        phase="03",
        plan="01",
        segment_id="seg-1",
        first_result_gate_pending=True,
        last_result_id="result-42",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.core.observability.get_current_execution", return_value=snapshot),
        patch("sys.stderr", stderr),
    ):
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert "First-result review due for 03-01" in output
    assert "rerun anchor: result-42" in output


@pytest.mark.parametrize(
    ("snapshot_kwargs", "expected_artifact"),
    [
        (
            {"last_result_label": "Benchmark reproduction", "last_result_id": "result-42"},
            "Benchmark reproduction",
        ),
        (
            {"current_task": "Investigating the current task", "last_result_id": "result-42"},
            "Investigating the current task",
        ),
    ],
)
def test_emit_execution_notification_prefers_label_or_current_task_over_last_result_id(
    tmp_path: Path,
    snapshot_kwargs: dict[str, object],
    expected_artifact: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "GPD").mkdir()
    snapshot = _ExecutionSnapshot(
        phase="03",
        plan="01",
        segment_id="seg-1",
        first_result_gate_pending=True,
        **snapshot_kwargs,
    )

    stderr = io.StringIO()
    with (
        patch("gpd.core.observability.get_current_execution", return_value=snapshot),
        patch("sys.stderr", stderr),
    ):
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert "First-result review due for 03-01" in output
    assert expected_artifact in output
    assert "rerun anchor: result-42" not in output


def test_emit_execution_notification_outside_project_layout_dedupes_per_workspace(tmp_path: Path) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    home = tmp_path / "home"
    snapshot = _ExecutionSnapshot(
        phase="03",
        plan="01",
        segment_id="seg-1",
        first_result_gate_pending=True,
        last_result_id="result-42",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.core.observability.get_current_execution", return_value=snapshot),
        patch("gpd.hooks.notify.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _emit_execution_notification(str(workspace_a))
        _emit_execution_notification(str(workspace_b))

    assert stderr.getvalue().count("First-result review due for 03-01") == 2


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


def test_emit_execution_notification_prefers_lineage_head_over_stale_current_execution_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "07",
            "plan": "02",
            "segment_id": "recorded-seg",
            "segment_status": "paused",
            "resume_file": "GPD/phases/07/.continue-here.md",
            "updated_at": "2026-03-27T12:01:00+00:00",
        },
    )

    head_snapshot = _ExecutionSnapshot(
        phase="07",
        plan="02",
        segment_id="head-seg",
        segment_status="blocked",
        blocked_reason="manual stop required",
        current_task="Lineage head task",
        updated_at="2026-03-27T12:03:00+00:00",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.core.observability.get_current_execution", return_value=head_snapshot),
        patch("sys.stderr", stderr),
    ):
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert "Blocked in 07-02" in output
    assert "manual stop required" in output
    assert "Resume candidate from live overlay" not in output


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
    assert "Resume candidate from live overlay" not in stderr.getvalue()


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
    assert output.count("Resume candidate from live overlay for 04-02") == 1


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
    assert "Resume candidate from live overlay" not in output


def test_emit_execution_notification_dedupes_concurrent_resume_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "GPD").mkdir()
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
            "[GPD] Resume candidate from live overlay for 04-02: GPD/phases/04/.continue-here.md\n",
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
        threads = [
            threading.Thread(target=_emit, name="notify-dedupe-1", daemon=True),
            threading.Thread(target=_emit, name="notify-dedupe-2", daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        live_threads = [thread.name for thread in threads if thread.is_alive()]
        assert not live_threads, f"Notification threads did not stop: {live_threads}; errors: {errors}"

    assert errors == []
    assert stderr.getvalue().count("Resume candidate from live overlay for 04-02") == 1
    state = json.loads(ProjectLayout(workspace).last_observability_notification.read_text(encoding="utf-8"))
    assert state["execution_fingerprint"] == "resume:seg-2"
    assert "fingerprint" not in state
