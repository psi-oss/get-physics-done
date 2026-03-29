"""Tests for shared hook update-resolution helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.hooks.update_resolution import (
    latest_update_cache,
    ordered_update_cache_candidates,
    primary_update_cache_file,
    resolve_update_cache_inputs,
    update_command_for_candidate,
)
from tests.hooks.helpers import mark_complete_install as _mark_complete_install
from tests.hooks.helpers import repair_command as _repair_command


def _noop_debug(_message: str) -> None:
    return


def test_latest_update_cache_prefers_candidate_order_over_newer_unrelated_cache(tmp_path: Path) -> None:
    preferred_cache = tmp_path / "preferred.json"
    preferred_cache.write_text(
        json.dumps({"update_available": True, "checked": 20}),
        encoding="utf-8",
    )
    unrelated_cache = tmp_path / "unrelated.json"
    unrelated_cache.write_text(
        json.dumps({"update_available": True, "checked": 30}),
        encoding="utf-8",
    )

    from types import SimpleNamespace

    preferred_candidate = SimpleNamespace(path=preferred_cache, runtime="codex", scope="local")
    unrelated_candidate = SimpleNamespace(path=unrelated_cache, runtime="claude-code", scope="global")

    with (
        patch("gpd.hooks.runtime_detect.get_update_cache_candidates", return_value=[preferred_candidate, unrelated_candidate]),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
        patch(
            "gpd.hooks.runtime_detect.detect_install_scope",
            side_effect=lambda runtime, **_kwargs: "local" if runtime == "codex" else None,
        ),
    ):
        cache, candidate = latest_update_cache(hook_file=__file__, cwd=str(tmp_path), debug=_noop_debug)

    assert cache == {"update_available": True, "checked": 20}
    assert candidate is preferred_candidate


def test_latest_update_cache_prefers_runtime_tagged_candidate_over_runtimeless_fallback(tmp_path: Path) -> None:
    fallback_cache = tmp_path / "fallback.json"
    fallback_cache.write_text(json.dumps({"update_available": True, "checked": 10}), encoding="utf-8")
    runtime_cache = tmp_path / "runtime.json"
    runtime_cache.write_text(json.dumps({"update_available": True, "checked": 20}), encoding="utf-8")

    from types import SimpleNamespace

    fallback_candidate = SimpleNamespace(path=fallback_cache, runtime=None, scope=None)
    runtime_candidate = SimpleNamespace(path=runtime_cache, runtime="codex", scope="local")

    with (
        patch("gpd.hooks.runtime_detect.get_update_cache_candidates", return_value=[fallback_candidate, runtime_candidate]),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
        patch(
            "gpd.hooks.runtime_detect.detect_install_scope",
            side_effect=lambda runtime, **_kwargs: "local" if runtime == "codex" else None,
        ),
    ):
        cache, candidate = latest_update_cache(hook_file=__file__, cwd=str(tmp_path), debug=_noop_debug)

    assert cache == {"update_available": True, "checked": 20}
    assert candidate is runtime_candidate


def test_ordered_update_cache_candidates_prefers_preferred_runtime_then_fallback_when_no_runtime_is_active(
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    preferred_candidate = SimpleNamespace(path=tmp_path / "codex.json", runtime="codex", scope="local")
    fallback_candidate = SimpleNamespace(path=tmp_path / "fallback.json", runtime=None, scope=None)
    unrelated_candidate = SimpleNamespace(path=tmp_path / "claude.json", runtime="claude-code", scope="global")

    with (
        patch(
            "gpd.hooks.runtime_detect.get_update_cache_candidates",
            return_value=[unrelated_candidate, fallback_candidate, preferred_candidate],
        ),
        patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
    ):
        candidates = ordered_update_cache_candidates(
            cwd=str(tmp_path),
            active_installed_runtime="unknown",
            preferred_runtime="codex",
        )

    assert candidates == [preferred_candidate, fallback_candidate]


def test_resolve_update_cache_inputs_uses_the_runtime_for_gpd_use_as_preference(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    with (
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex"),
    ):
        workspace_path, resolved_home, active_runtime, preferred_runtime = resolve_update_cache_inputs(
            cwd=workspace,
            home=home,
        )

    assert workspace_path == workspace
    assert resolved_home == home
    assert active_runtime == "unknown"
    assert preferred_runtime == "codex"


def test_resolve_update_cache_inputs_uses_explicit_preference_without_runtime_lookup(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    with (
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", side_effect=AssertionError("unexpected lookup")),
    ):
        workspace_path, resolved_home, active_runtime, preferred_runtime = resolve_update_cache_inputs(
            cwd=workspace,
            home=home,
            preferred_runtime="codex",
        )

    assert workspace_path == workspace
    assert resolved_home == home
    assert active_runtime == "unknown"
    assert preferred_runtime == "codex"


def test_resolve_update_cache_inputs_uses_non_project_cwd_for_runtime_preference_lookup(tmp_path: Path) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    home = tmp_path / "home"

    with (
        patch("gpd.hooks.install_context.resolve_project_root", return_value=None),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex") as mock_preferred,
    ):
        workspace_path, resolved_home, active_runtime, preferred_runtime = resolve_update_cache_inputs(
            cwd=workspace,
            home=home,
        )

    assert workspace_path == workspace
    assert resolved_home == home
    assert active_runtime == "unknown"
    assert preferred_runtime == "codex"
    assert mock_preferred.call_args.kwargs["cwd"] == workspace


def test_primary_update_cache_file_falls_back_to_home_gpd_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"

    cache_file = primary_update_cache_file([], home=home)

    assert cache_file == home / "GPD" / "cache" / "gpd-update-check.json"


def test_latest_update_cache_uses_shared_cache_constants_for_self_owned_install(tmp_path: Path) -> None:
    from gpd.hooks.install_context import SelfOwnedInstallContext

    self_config_dir = tmp_path / "runtime"
    self_config_dir.mkdir(parents=True)
    self_install = SelfOwnedInstallContext(config_dir=self_config_dir, runtime="codex", install_scope="local")
    cache_file = self_install.cache_file
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(json.dumps({"update_available": True, "checked": 10}), encoding="utf-8")
    (self_config_dir / "gpd-file-manifest.json").write_text(
        json.dumps(
            {
                "install_scope": "local",
                "runtime": "codex",
                "explicit_target": True,
                "install_target_dir": str(self_config_dir),
            }
        ),
        encoding="utf-8",
    )

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.get_update_cache_candidates", return_value=[]),
    ):
        cache, candidate = latest_update_cache(hook_file=__file__, cwd=str(tmp_path), debug=_noop_debug)

    assert cache == {"update_available": True, "checked": 10}
    assert candidate is not None
    assert candidate.path == cache_file


def test_latest_update_cache_uses_runtime_unknown_constant_not_literal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_unknown = "runtime-unknown"

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=None),
        patch("gpd.hooks.install_context.resolve_project_root", return_value=workspace),
        patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value=runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected lookup")),
        patch("gpd.hooks.runtime_detect.get_update_cache_candidates", return_value=[]),
    ):
        assert latest_update_cache(hook_file=__file__, cwd=str(workspace), debug=_noop_debug) == (None, None)


def test_update_command_for_candidate_prefers_self_owned_install_command(tmp_path: Path) -> None:
    from gpd.hooks.install_context import SelfOwnedInstallContext

    explicit_target = tmp_path / "custom-runtime-dir"
    explicit_target.mkdir(parents=True)
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
    self_install = SelfOwnedInstallContext(config_dir=explicit_target, runtime="codex", install_scope="local")
    candidate = type("Candidate", (), {"path": self_install.cache_file, "runtime": "codex", "scope": "local"})()

    with patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install):
        command = update_command_for_candidate(candidate, hook_file=__file__, cwd=str(tmp_path))

    expected = _repair_command("codex", install_scope="local", target_dir=explicit_target, explicit_target=True)
    assert command == expected


def test_update_command_for_candidate_uses_cache_runtime_when_install_exists(tmp_path: Path) -> None:
    workspace = tmp_path
    local_runtime_dir = workspace / ".codex"
    local_runtime_dir.mkdir(parents=True)
    _mark_complete_install(local_runtime_dir, runtime="codex")
    candidate = type("Candidate", (), {"path": local_runtime_dir / "cache" / "gpd-update-check.json", "runtime": "codex", "scope": "local"})()

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=None),
        patch("gpd.hooks.runtime_detect._runtime_dir_has_gpd_install", return_value=True),
    ):
        command = update_command_for_candidate(candidate, hook_file=__file__, cwd=str(workspace))

    expected = _repair_command("codex", install_scope="local", target_dir=local_runtime_dir, explicit_target=False)
    assert command == expected
