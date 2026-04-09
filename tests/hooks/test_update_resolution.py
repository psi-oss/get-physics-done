"""Tests for shared hook update-resolution helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import get_shared_install_metadata
from gpd.hooks import runtime_detect as runtime_detect_module
from gpd.hooks.update_resolution import (
    latest_update_cache,
    ordered_update_cache_candidates,
    primary_update_cache_file,
    resolve_update_cache_inputs,
    update_command_for_candidate,
)
from tests.hooks.helpers import mark_complete_install as _mark_complete_install
from tests.hooks.helpers import repair_command as _repair_command
from tests.runtime_install_helpers import seed_complete_runtime_install

_SHARED_INSTALL = get_shared_install_metadata()


def _noop_debug(_message: str) -> None:
    return


def test_latest_update_cache_prefers_considered_candidate_order(tmp_path: Path) -> None:
    cases = (
        (
            [
                SimpleNamespace(path=tmp_path / "preferred.json", runtime="codex", scope="local"),
                SimpleNamespace(path=tmp_path / "unrelated.json", runtime="claude-code", scope="global"),
            ],
            {"preferred.json": {"update_available": True, "checked": 20}, "unrelated.json": {"update_available": True, "checked": 30}},
            {"update_available": True, "checked": 20},
            0,
        ),
        (
            [
                SimpleNamespace(path=tmp_path / "fallback.json", runtime=None, scope=None),
                SimpleNamespace(path=tmp_path / "runtime.json", runtime="codex", scope="local"),
            ],
            {"fallback.json": {"update_available": True, "checked": 10}, "runtime.json": {"update_available": True, "checked": 20}},
            {"update_available": True, "checked": 20},
            1,
        ),
    )

    for candidates, payloads, expected_cache, expected_index in cases:
        for candidate in candidates:
            candidate.path.write_text(json.dumps(payloads[candidate.path.name]), encoding="utf-8")

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_candidates", return_value=list(candidates)),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
            patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
            patch(
                "gpd.hooks.runtime_detect.detect_install_scope",
                side_effect=lambda runtime, **_kwargs: "local" if runtime == "codex" else None,
            ),
        ):
            cache, candidate = latest_update_cache(hook_file=__file__, cwd=str(tmp_path), debug=_noop_debug)

        assert cache == expected_cache
        assert candidate is candidates[expected_index]


def test_ordered_update_cache_candidates_prefers_preferred_runtime_then_fallback_when_no_runtime_is_active(
    tmp_path: Path,
) -> None:
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


def test_ordered_update_cache_candidates_treats_explicit_unknown_runtime_as_no_active_runtime(
    tmp_path: Path,
) -> None:
    preferred_candidate = SimpleNamespace(path=tmp_path / "codex.json", runtime="codex", scope="local")
    fallback_candidate = SimpleNamespace(path=tmp_path / "fallback.json", runtime=None, scope=None)
    unrelated_candidate = SimpleNamespace(path=tmp_path / "claude.json", runtime="claude-code", scope="global")

    with (
        patch(
            "gpd.hooks.runtime_detect.get_update_cache_candidates",
            return_value=[unrelated_candidate, fallback_candidate, preferred_candidate],
        ),
        patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
        patch(
            "gpd.hooks.update_resolution.resolve_update_cache_inputs",
            return_value=(tmp_path, tmp_path / "home", "claude-code", "codex"),
        ),
    ):
        candidates = ordered_update_cache_candidates(
            cwd=str(tmp_path),
            active_installed_runtime="unknown",
            preferred_runtime="codex",
        )

    assert candidates == [preferred_candidate, fallback_candidate]


def test_ordered_update_cache_candidates_falls_back_to_other_runtime_when_preferred_cache_is_absent(
    tmp_path: Path,
) -> None:
    fallback_candidate = SimpleNamespace(path=tmp_path / "fallback.json", runtime=None, scope=None)
    unrelated_candidate = SimpleNamespace(path=tmp_path / "claude.json", runtime="claude-code", scope="global")

    with (
        patch(
            "gpd.hooks.runtime_detect.get_update_cache_candidates",
            return_value=[unrelated_candidate, fallback_candidate],
        ),
        patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
    ):
        candidates = ordered_update_cache_candidates(
            cwd=str(tmp_path),
            active_installed_runtime="unknown",
            preferred_runtime="codex",
        )

    assert candidates == [unrelated_candidate, fallback_candidate]


def test_resolve_update_cache_inputs_uses_explicit_or_inferred_preference(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    cases = (
        (None, "codex"),
        ("codex", "codex"),
    )

    with (
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex"),
    ):
        for explicit_preference, expected_preference in cases:
            workspace_path, resolved_home, active_runtime, preferred_runtime = resolve_update_cache_inputs(
                cwd=workspace,
                home=home,
                preferred_runtime=explicit_preference,
            )

            assert workspace_path == workspace
            assert resolved_home == home
            assert active_runtime is None
            assert preferred_runtime == expected_preference


def test_primary_update_cache_file_falls_back_to_home_data_root_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"

    cache_file = primary_update_cache_file([], home=home)

    assert cache_file == home / ".gpd" / "cache" / "gpd-update-check.json"


def test_home_update_cache_path_comes_from_one_helper_for_lookup_and_write_paths(tmp_path: Path) -> None:
    helper_path = tmp_path / ".gpd" / "cache" / "gpd-update-check.json"

    with patch.object(runtime_detect_module, "home_update_cache_file", return_value=helper_path) as mock_helper:
        candidates = runtime_detect_module.get_update_cache_candidates(home=tmp_path, cwd=tmp_path)
        primary = primary_update_cache_file([], home=tmp_path)

    assert candidates[-1].path == helper_path
    assert primary == helper_path
    assert mock_helper.call_count == 2


def test_latest_update_cache_uses_shared_cache_constants_for_self_owned_install_and_workspace_precedence(
    tmp_path: Path,
) -> None:
    from gpd.hooks.install_context import SelfOwnedInstallContext

    self_config_dir = tmp_path / "runtime"
    self_config_dir.mkdir(parents=True)
    self_install = SelfOwnedInstallContext(config_dir=self_config_dir, runtime="codex", install_scope="local")
    self_cache = self_install.cache_file
    self_cache.parent.mkdir(parents=True)
    self_cache.write_text(json.dumps({"update_available": True, "checked": 10}), encoding="utf-8")
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

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_cache = workspace / ".claude" / "cache" / "gpd-update-check.json"
    workspace_cache.parent.mkdir(parents=True)
    workspace_cache.write_text(json.dumps({"update_available": True, "checked": 10}), encoding="utf-8")
    workspace_candidate = SimpleNamespace(path=workspace_cache, runtime="claude-code", scope="local")
    workspace_install = SimpleNamespace(config_dir=workspace / ".claude", install_scope="local")

    cases = (
        (
            {
                "self_install": self_install,
                "workspace_candidates": [],
                "active_runtime": "unknown",
                "runtime_install_target": None,
                "hook_cwd": tmp_path,
            },
            self_cache,
        ),
        (
            {
                "self_install": self_install,
                "workspace_candidates": [workspace_candidate],
                "active_runtime": "claude-code",
                "runtime_install_target": workspace_install,
                "hook_cwd": workspace,
            },
            workspace_cache,
        ),
    )

    for patch_values, expected_cache_path in cases:
        with (
            patch("gpd.hooks.install_context.detect_self_owned_install", return_value=patch_values["self_install"]),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value=patch_values["active_runtime"]),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value=patch_values["active_runtime"]),
            patch(
                "gpd.hooks.runtime_detect.detect_runtime_install_target",
                return_value=patch_values["runtime_install_target"],
            ),
            patch(
                "gpd.hooks.update_resolution.ordered_update_cache_candidates",
                return_value=patch_values["workspace_candidates"],
            ),
        ):
            cache, candidate = latest_update_cache(hook_file=__file__, cwd=str(patch_values["hook_cwd"]), debug=_noop_debug)

        assert cache == {"update_available": True, "checked": 10}
        assert candidate is not None
        assert candidate.path == expected_cache_path


def test_latest_update_cache_falls_back_when_self_owned_cache_is_missing(tmp_path: Path) -> None:
    self_cache_dir = tmp_path / "self-owned"
    self_cache_dir.mkdir(parents=True)
    self_install = SimpleNamespace(
        cache_file=self_cache_dir / "cache" / "gpd-update-check.json",
        config_dir=self_cache_dir,
        runtime="codex",
        install_scope="local",
    )
    fallback_candidate = SimpleNamespace(path=tmp_path / "fallback.json", runtime="codex", scope="local")
    fallback_candidate.path.write_text(json.dumps({"update_available": True, "checked": 42}), encoding="utf-8")

    with (
        patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install),
        patch("gpd.hooks.install_context.should_prefer_self_owned_install", return_value=True),
        patch(
            "gpd.hooks.update_resolution.resolve_update_cache_inputs",
            return_value=(tmp_path, tmp_path / "home", "codex", "codex"),
        ),
        patch("gpd.hooks.update_resolution.ordered_update_cache_candidates", return_value=[fallback_candidate]),
    ):
        cache, candidate = latest_update_cache(hook_file=__file__, cwd=str(tmp_path), debug=_noop_debug)

    assert cache == {"update_available": True, "checked": 42}
    assert candidate is fallback_candidate


def test_update_command_for_candidate_prefers_expected_resolution_modes(tmp_path: Path) -> None:
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

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_runtime_dir = workspace / ".codex"
    local_runtime_dir.mkdir(parents=True)
    _mark_complete_install(local_runtime_dir, runtime="codex")

    adapter = get_adapter("codex")
    resolved_home = tmp_path / "custom-home"
    resolved_home.mkdir()
    global_runtime_dir = adapter.resolve_global_config_dir(home=resolved_home)
    seed_complete_runtime_install(
        global_runtime_dir,
        runtime="codex",
        install_scope="global",
        home=resolved_home,
        explicit_target=False,
    )

    relocated_target = tmp_path / "relocated-self-owned" / adapter.config_dir_name
    seed_complete_runtime_install(
        relocated_target,
        runtime="codex",
        install_scope="local",
        explicit_target=True,
    )
    manifest_path = relocated_target / _SHARED_INSTALL.manifest_name
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    stale_self_install = SelfOwnedInstallContext(
        config_dir=relocated_target,
        runtime="codex",
        install_scope="local",
    )

    cases = (
        (
            type("Candidate", (), {"path": self_install.cache_file, "runtime": "codex", "scope": "local"})(),
            self_install,
            _repair_command("codex", install_scope="local", target_dir=explicit_target, explicit_target=True),
            tmp_path,
            (),
        ),
        (
            type("Candidate", (), {"path": local_runtime_dir / "cache" / "gpd-update-check.json", "runtime": "codex", "scope": "local"})(),
            None,
            _repair_command("codex", install_scope="local", target_dir=local_runtime_dir, explicit_target=False),
            workspace,
            (("gpd.hooks.runtime_detect._runtime_dir_has_gpd_install", True),),
        ),
        (
            SimpleNamespace(
                path=global_runtime_dir / "cache" / "gpd-update-check.json",
                runtime="codex",
                scope="global",
            ),
            None,
            _repair_command("codex", install_scope="global", target_dir=global_runtime_dir, explicit_target=False),
            workspace,
            (
                ("gpd.hooks.install_context.resolve_hook_lookup_context", SimpleNamespace(lookup_cwd=workspace, resolved_home=resolved_home, active_runtime=None, preferred_runtime=None)),
                ("gpd.hooks.runtime_detect.Path.home", resolved_home),
            ),
        ),
        (
            type("Candidate", (), {"path": stale_self_install.cache_file, "runtime": "codex", "scope": "local"})(),
            stale_self_install,
            None,
            tmp_path,
            (),
        ),
    )

    for candidate, self_install_value, expected, cwd, extra_patches in cases:
        context_patches = []
        if extra_patches:
            for name, value in extra_patches:
                context_patches.append((name, value))

        with patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install_value):
            if candidate.scope == "global":
                with (
                    patch(
                        "gpd.hooks.install_context.resolve_hook_lookup_context",
                        return_value=SimpleNamespace(lookup_cwd=workspace, resolved_home=resolved_home, active_runtime=None, preferred_runtime=None),
                    ),
                    patch("gpd.hooks.runtime_detect.Path.home", return_value=resolved_home),
                ):
                    command = update_command_for_candidate(candidate, hook_file=__file__, cwd=str(cwd))
            elif expected is None and candidate.path == stale_self_install.cache_file:
                command = update_command_for_candidate(candidate, hook_file=__file__, cwd=str(cwd))
            elif candidate.path.parent.name == "cache" and candidate.path.parent.parent.name == ".codex" and candidate.path.parent.parent.parent == workspace:
                with patch("gpd.hooks.runtime_detect._runtime_dir_has_gpd_install", return_value=True):
                    command = update_command_for_candidate(candidate, hook_file=__file__, cwd=str(cwd))
            else:
                command = update_command_for_candidate(candidate, hook_file=__file__, cwd=str(cwd))

        assert command == expected
