"""Behavior-focused hook regression coverage."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


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

    cache_file = tmp_path / "gpd-update-check.json"
    cache_file.write_text(cache_content, encoding="utf-8")

    with patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]), patch(
        "gpd.hooks.runtime_detect.detect_active_runtime",
        return_value="unknown",
    ):
        _check_and_notify_update()


def test_check_update_passes_cache_file_via_sys_argv() -> None:
    from gpd.hooks.check_update import main
    from gpd.hooks.runtime_detect import UpdateCacheCandidate

    cache_path = Path("/tmp/test-cache.json")

    with patch(
        "gpd.hooks.runtime_detect.get_update_cache_candidates",
        return_value=[UpdateCacheCandidate(path=cache_path)],
    ), patch("gpd.hooks.check_update.subprocess.Popen") as mock_popen, patch.object(Path, "exists", return_value=False):
        mock_popen.return_value = MagicMock()
        main()

    args = mock_popen.call_args[0][0]

    assert "sys.argv[1]" in args[2]
    assert args[3] == str(cache_path)


def test_short_form_prerelease_is_older_than_final_release() -> None:
    from gpd.hooks.check_update import _is_older_than

    assert _is_older_than("1.0.0a1", "1.0.0") is True


def test_statusline_read_position_returns_empty_for_non_dict_state(tmp_path: Path) -> None:
    from gpd.hooks.statusline import _read_position

    gpd_dir = tmp_path / ".gpd"
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


@pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
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


@pytest.mark.parametrize(
    ("files", "expected_runtime"),
    [
        ({"skills/gpd-help/SKILL.md": "hash"}, "codex"),
        ({"command/gpd-help.md": "hash"}, "opencode"),
    ],
)
def test_installed_runtime_infers_runtime_from_catalog_owned_manifest_prefixes(
    tmp_path: Path,
    files: dict[str, str],
    expected_runtime: str,
) -> None:
    from gpd.hooks.install_metadata import installed_runtime

    explicit_target = tmp_path / "custom-runtime-dir"
    explicit_target.mkdir()
    (explicit_target / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "files": files}),
        encoding="utf-8",
    )

    assert installed_runtime(explicit_target) == expected_runtime
