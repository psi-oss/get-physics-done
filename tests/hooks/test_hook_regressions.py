"""Behavior-focused hook regression coverage."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gpd.adapters.runtime_catalog import list_runtime_names


@pytest.mark.parametrize(
    "cache_content",
    [
        "null",
        "[1, 2, 3]",
        '"just a string"',
        "{not valid json",
    ],
)
def test_notify_update_skips_non_dict_or_invalid_cache_files(tmp_path: Path, cache_content: str) -> None:
    from gpd.hooks.notify import _check_and_notify_update
    from gpd.hooks.runtime_detect import UpdateCacheCandidate

    cache_file = tmp_path / "gpd-update-check.json"
    cache_file.write_text(cache_content, encoding="utf-8")

    with (
        patch(
            "gpd.hooks.runtime_detect.get_update_cache_candidates",
            return_value=[UpdateCacheCandidate(path=cache_file, runtime="codex", scope="local")],
        ),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
    ):
        _check_and_notify_update()


def test_check_update_passes_cache_file_via_sys_argv(tmp_path: Path) -> None:
    from gpd.hooks.check_update import main
    from gpd.hooks.runtime_detect import UpdateCacheCandidate

    cache_path = tmp_path / "test-cache.json"

    with patch(
        "gpd.hooks.runtime_detect.get_update_cache_candidates",
        return_value=[UpdateCacheCandidate(path=cache_path)],
    ), patch("gpd.hooks.check_update.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        main()

    args = mock_popen.call_args[0][0]

    assert "sys.argv[1]" in args[2]
    assert args[3] == str(cache_path)


def test_runtime_detect_does_not_keep_dead_private_lookup_helpers() -> None:
    import gpd.hooks.runtime_detect as runtime_detect

    assert not hasattr(runtime_detect, "_install_marker_quality")
    assert not hasattr(runtime_detect, "_runtime_dirs_in_priority_order")


def test_short_form_prerelease_is_older_than_final_release() -> None:
    from gpd.hooks.check_update import _is_older_than

    assert _is_older_than("1.0.0a1", "1.0.0") is True


def test_statusline_read_position_returns_empty_for_non_dict_state(tmp_path: Path) -> None:
    from gpd.hooks.statusline import _read_position

    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    state_file = gpd_dir / "state.json"

    state_file.write_text("[]", encoding="utf-8")
    assert _read_position(str(tmp_path)) == ""

    state_file.write_text('"hello"', encoding="utf-8")
    assert _read_position(str(tmp_path)) == ""


@pytest.mark.parametrize(
    ("module_name", "function_name"),
    [
        ("gpd.hooks.notify", "_latest_update_cache"),
        ("gpd.hooks.statusline", "_latest_update_cache"),
    ],
)
def test_update_cache_helpers_prefer_candidate_order_over_newer_unrelated_cache(
    tmp_path: Path,
    module_name: str,
    function_name: str,
) -> None:
    module = __import__(module_name, fromlist=[function_name])
    cache_reader = getattr(module, function_name)

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
        cache, candidate = cache_reader(str(tmp_path))

    assert cache == {"update_available": True, "checked": 20}
    assert candidate is preferred_candidate


@pytest.mark.parametrize(
    ("module_name", "function_name"),
    [
        ("gpd.hooks.notify", "_latest_update_cache"),
        ("gpd.hooks.statusline", "_latest_update_cache"),
    ],
)
def test_update_cache_helpers_prefer_runtime_tagged_candidate_over_runtimeless_fallback(
    tmp_path: Path,
    module_name: str,
    function_name: str,
) -> None:
    module = __import__(module_name, fromlist=[function_name])
    cache_reader = getattr(module, function_name)

    fallback_cache = tmp_path / "fallback.json"
    fallback_cache.write_text(json.dumps({"update_available": True, "checked": 10}), encoding="utf-8")
    runtime_cache = tmp_path / "runtime.json"
    runtime_cache.write_text(json.dumps({"update_available": True, "checked": 20}), encoding="utf-8")

    fallback_candidate = SimpleNamespace(path=fallback_cache, runtime=None, scope=None)
    runtime_candidate = SimpleNamespace(path=runtime_cache, runtime="codex", scope="local")

    with (
        patch(
            "gpd.hooks.runtime_detect.get_update_cache_candidates",
            return_value=[fallback_candidate, runtime_candidate],
        ),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("gpd.hooks.runtime_detect.should_consider_update_cache_candidate", return_value=True),
        patch(
            "gpd.hooks.runtime_detect.detect_install_scope",
            side_effect=lambda runtime, **_kwargs: "local" if runtime == "codex" else None,
        ),
    ):
        cache, candidate = cache_reader(str(tmp_path))

    assert cache == {"update_available": True, "checked": 20}
    assert candidate is runtime_candidate


def test_installed_update_command_uses_manifest_runtime_metadata_for_custom_targets(tmp_path: Path) -> None:
    from gpd.hooks.install_metadata import installed_update_command

    explicit_target = tmp_path / "custom-runtime-dir"
    explicit_target.mkdir()
    (explicit_target / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "runtime": "codex"}),
        encoding="utf-8",
    )

    command = installed_update_command(explicit_target)

    assert command is not None
    assert "--codex --local --target-dir" in command
    assert str(explicit_target) in command


@pytest.mark.parametrize("runtime_arg", ["Claude Code", "claude"])
def test_runtime_cli_accepts_display_name_and_alias_runtime_argument(
    tmp_path: Path,
    runtime_arg: str,
) -> None:
    import gpd.runtime_cli as runtime_cli
    from gpd.adapters import get_adapter

    runtime = "claude-code"
    adapter = get_adapter(runtime)
    gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
    target_dir = tmp_path / adapter.config_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)
    result = adapter.install(gpd_root, target_dir, is_global=True)
    adapter.finalize_install(result)
    manifest_path = target_dir / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with patch("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None):
        with pytest.raises(SystemExit) as excinfo:
            runtime_cli.main(
                [
                    "--runtime",
                    runtime_arg,
                    "--config-dir",
                    str(target_dir),
                    "--install-scope",
                    "global",
                    "--raw",
                    "version",
                ]
            )

    assert excinfo.value.code == 0


def test_installed_runtime_fails_closed_for_invalid_manifest_runtime(tmp_path: Path) -> None:
    from gpd.adapters import get_adapter
    from gpd.hooks.install_metadata import installed_runtime

    runtime = "codex"
    adapter = get_adapter(runtime)
    gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
    target_dir = tmp_path / adapter.config_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)
    result = adapter.install(gpd_root, target_dir, is_global=True)
    adapter.finalize_install(result)

    manifest_path = target_dir / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = "definitely-not-a-runtime"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_runtime(target_dir) is None


def test_config_dir_has_complete_install_rejects_generic_markers_when_manifest_runtime_is_invalid(
    tmp_path: Path,
) -> None:
    from gpd.hooks.install_metadata import config_dir_has_complete_install, installed_update_command

    config_dir = tmp_path / "custom-runtime-dir"
    config_dir.mkdir()
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": "definitely-not-a-runtime"}),
        encoding="utf-8",
    )
    (config_dir / "get-physics-done").mkdir()

    assert config_dir_has_complete_install(config_dir) is False
    assert installed_update_command(config_dir) is None


def test_installed_update_command_ignores_process_cwd_for_nested_default_local_install(tmp_path: Path) -> None:
    from gpd.hooks.install_metadata import installed_update_command

    default_local_target = tmp_path / "workspace" / ".codex"
    default_local_target.mkdir(parents=True)
    (default_local_target / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "runtime": "codex"}),
        encoding="utf-8",
    )

    command = installed_update_command(default_local_target)

    assert command == "npx -y get-physics-done --codex --local"


@pytest.mark.parametrize("runtime", list_runtime_names())
@pytest.mark.parametrize("scope", ["local", "global"])
def test_installed_update_command_preserves_explicit_target_named_like_runtime_default(
    tmp_path: Path,
    runtime: str,
    scope: str,
) -> None:
    from gpd.adapters import get_adapter
    from gpd.hooks.install_metadata import installed_update_command

    adapter = get_adapter(runtime)
    explicit_target = tmp_path / f"custom-{scope}" / adapter.config_dir_name
    explicit_target.mkdir(parents=True)
    (explicit_target / "gpd-file-manifest.json").write_text(
        json.dumps(
            {
                "install_scope": scope,
                "runtime": runtime,
                "explicit_target": True,
                "install_target_dir": str(explicit_target),
            }
        ),
        encoding="utf-8",
    )

    command = installed_update_command(explicit_target)

    assert command is not None
    assert "--target-dir" in command
    assert str(explicit_target) in command


def test_installed_update_command_treats_scope_less_explicit_local_named_target_as_local(tmp_path: Path) -> None:
    from gpd.hooks.install_metadata import installed_update_command

    explicit_target = tmp_path / "custom-runtime" / ".codex"
    explicit_target.mkdir(parents=True)
    (explicit_target / "gpd-file-manifest.json").write_text(
        json.dumps(
            {
                "runtime": "codex",
                "explicit_target": True,
                "install_target_dir": str(explicit_target),
            }
        ),
        encoding="utf-8",
    )

    command = installed_update_command(explicit_target)

    assert command is not None
    assert "--local" in command
    assert "--global" not in command
    assert "--target-dir" in command
    assert str(explicit_target) in command


def test_installed_update_command_recovers_legacy_explicit_target_named_like_default_from_update_workflow(
    tmp_path: Path,
) -> None:
    from gpd.hooks.install_metadata import installed_update_command

    explicit_target = tmp_path / "custom-parent" / ".codex"
    explicit_target.mkdir(parents=True)
    (explicit_target / "gpd-file-manifest.json").write_text(
        json.dumps(
            {
                "install_scope": "local",
                "runtime": "codex",
                "install_target_dir": str(explicit_target),
            }
        ),
        encoding="utf-8",
    )
    update_workflow = explicit_target / "get-physics-done" / "workflows" / "update.md"
    update_workflow.parent.mkdir(parents=True, exist_ok=True)
    update_workflow.write_text(
        '\n'.join(
            [
                'GPD_CONFIG_DIR="' + str(explicit_target) + '"',
                'GPD_GLOBAL_CONFIG_DIR="' + str(tmp_path / ".codex-global") + '"',
                'INSTALL_SCOPE="--local"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    command = installed_update_command(explicit_target)

    assert command is not None
    assert "--local" in command
    assert "--target-dir" in command
    assert str(explicit_target) in command


@pytest.mark.parametrize(
    "files",
    [
        {"skills/gpd-help/SKILL.md": "hash"},
        {"command/gpd-help.md": "hash"},
    ],
)
def test_installed_runtime_fails_closed_for_manifest_without_runtime_even_with_catalog_owned_prefixes(
    tmp_path: Path,
    files: dict[str, str],
) -> None:
    from gpd.hooks.install_metadata import installed_runtime

    explicit_target = tmp_path / "custom-runtime-dir"
    explicit_target.mkdir()
    (explicit_target / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "files": files}),
        encoding="utf-8",
    )

    assert installed_runtime(explicit_target) is None


def test_installed_runtime_fails_closed_when_manifest_is_corrupt(tmp_path: Path) -> None:
    from gpd.hooks.install_metadata import installed_runtime

    home = tmp_path / "home"
    opencode_dir = home / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    (opencode_dir / "gpd-file-manifest.json").write_text("not-json", encoding="utf-8")

    with (
        patch.dict(
            "os.environ",
            {
                "OPENCODE_CONFIG_DIR": str(tmp_path / "foreign-opencode"),
                "OPENCODE_CONFIG": str(tmp_path / "foreign-opencode" / "config.json"),
                "XDG_CONFIG_HOME": str(tmp_path / "foreign-xdg"),
            },
            clear=False,
        ),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
    ):
        assert installed_runtime(opencode_dir) is None
