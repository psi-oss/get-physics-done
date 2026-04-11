"""Tests for gpd/hooks/runtime_detect.py edge cases.

Covers: no runtime dirs, multiple runtime dirs, env var detection,
priority ordering, helper functions, and unknown runtime fallback.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import gpd.hooks.runtime_detect as runtime_detect_module
from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import get_shared_install_metadata, iter_runtime_descriptors
from gpd.adapters.runtime_catalog import normalize_runtime_name as catalog_normalize_runtime_name
from gpd.hooks.install_metadata import installed_runtime
from gpd.hooks.runtime_detect import (
    RUNTIME_UNKNOWN,
    SCOPE_GLOBAL,
    SCOPE_LOCAL,
    SOURCE_ENV,
    SOURCE_LOCAL,
    SOURCE_UNKNOWN,
    TodoCandidate,
    UpdateCacheCandidate,
    _has_gpd_install,
    _ordered_runtime_dirs_for_lookup,
    _runtime_from_manifest_or_path,
    all_runtime_dirs,
    detect_active_runtime,
    detect_active_runtime_with_gpd_install,
    detect_install_scope,
    detect_runtime_for_gpd_use,
    detect_runtime_install_target,
    get_cache_dirs,
    get_gpd_install_dirs,
    get_todo_candidates,
    get_todo_dirs,
    get_update_cache_candidates,
    get_update_cache_files,
    normalize_runtime_name,
    resolve_effective_runtime,
    should_consider_todo_candidate,
    should_consider_update_cache_candidate,
    supported_runtime_names,
    update_command_for_runtime,
)
from tests.hooks.helpers import clean_runtime_env as _clean_runtime_env
from tests.hooks.helpers import mark_complete_install as _mark_complete_install

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_RUNTIME_BY_NAME = {descriptor.runtime_name: descriptor for descriptor in _RUNTIME_DESCRIPTORS}
_SHARED_INSTALL = get_shared_install_metadata()
RUNTIME_CLAUDE = _RUNTIME_BY_NAME["claude-code"].runtime_name
RUNTIME_CODEX = _RUNTIME_BY_NAME["codex"].runtime_name
RUNTIME_GEMINI = _RUNTIME_BY_NAME["gemini"].runtime_name
RUNTIME_OPENCODE = _RUNTIME_BY_NAME["opencode"].runtime_name


def _mark_gpd_install(config_dir: Path, *, runtime: str | None = None, install_scope: str = SCOPE_LOCAL) -> None:
    """Mark a runtime directory as containing a GPD install."""
    _mark_complete_install(config_dir, runtime=runtime, install_scope=install_scope)


def _write_install_manifest(config_dir: Path, *, install_scope: str) -> None:
    """Write a minimal manifest describing the install scope."""
    config_dir.mkdir(parents=True, exist_ok=True)
    try:
        existing_manifest = json.loads((config_dir / "gpd-file-manifest.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        existing_manifest = {}
    manifest: dict[str, object] = existing_manifest if isinstance(existing_manifest, dict) else {}
    runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), str) else None
    if runtime is None:
        for descriptor in _RUNTIME_DESCRIPTORS:
            candidate = descriptor.runtime_name
            if config_dir.name == get_adapter(candidate).local_config_dir_name:
                runtime = candidate
                break
    explicit_target = manifest.get("explicit_target")
    if not isinstance(explicit_target, bool) and runtime is not None:
        explicit_target = config_dir.name != get_adapter(runtime).config_dir_name
    manifest["install_scope"] = install_scope
    if runtime is not None:
        manifest["runtime"] = runtime
    if explicit_target is not None:
        manifest["explicit_target"] = explicit_target
    manifest["install_target_dir"] = str(config_dir)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

# ─── detect_active_runtime ─────────────────────────────────────────────────


class TestDetectActiveRuntime:
    """Tests for detect_active_runtime with various env/dir states."""

    def test_no_env_no_dirs_returns_unknown(self, tmp_path: Path) -> None:
        """When no env vars set and no runtime dirs exist → 'unknown'."""
        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_UNKNOWN

    def test_claude_env_var_detected(self) -> None:
        """CLAUDE_CODE_SESSION env var → 'claude'."""
        env = _clean_runtime_env()
        env["CLAUDE_CODE_SESSION"] = "abc123"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_codex_env_var_detected(self) -> None:
        """CODEX_SESSION env var → 'codex'."""
        env = _clean_runtime_env()
        env["CODEX_SESSION"] = "xyz"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CODEX

    def test_explicit_gpd_runtime_override_detected(self) -> None:
        """GPD_ACTIVE_RUNTIME env var → canonical runtime."""
        env = _clean_runtime_env()
        env["GPD_ACTIVE_RUNTIME"] = "Codex"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CODEX

    def test_gemini_env_var_detected(self) -> None:
        """GEMINI_CLI env var → 'gemini'."""
        env = _clean_runtime_env()
        env["GEMINI_CLI"] = "1"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_GEMINI

    def test_opencode_env_var_detected(self) -> None:
        """OPENCODE_SESSION env var → 'opencode'."""
        env = _clean_runtime_env()
        env["OPENCODE_SESSION"] = "sess"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_OPENCODE

    def test_env_var_takes_priority_over_dirs(self, tmp_path: Path) -> None:
        """Env var signal wins even if multiple runtime dirs exist."""
        # Create codex dir but set claude env var
        (tmp_path / ".codex").mkdir()
        env = _clean_runtime_env()
        env["CLAUDE_CODE"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_multiple_dirs_picks_first_in_priority(self, tmp_path: Path) -> None:
        """Bare runtime dirs should not count as active without a verified install."""
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".gemini").mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_UNKNOWN

    def test_claude_dir_wins_over_codex(self, tmp_path: Path) -> None:
        """Bare config dirs alone should not produce a runtime selection."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".codex").mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
        ):
            assert detect_active_runtime() == RUNTIME_UNKNOWN

    def test_only_opencode_dir(self, tmp_path: Path) -> None:
        """Bare OpenCode config dirs should not count without a verified install."""
        oc_dir = tmp_path / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_UNKNOWN

    def test_multiple_env_vars_first_wins(self) -> None:
        """When multiple env vars set, first in signal list wins (claude > codex)."""
        env = _clean_runtime_env()
        env["CLAUDE_CODE_SESSION"] = "1"
        env["CODEX_SESSION"] = "1"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_explicit_cwd_overrides_process_cwd_for_runtime_detection(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".gemini").mkdir()

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / ".claude").mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert detect_active_runtime(cwd=workspace) == RUNTIME_UNKNOWN

    def test_local_runtime_dirs_outrank_global_runtime_dirs(self, tmp_path: Path) -> None:
        """Local runtime detection wins even when the global runtime has higher name priority."""
        home = tmp_path / "home"
        (tmp_path / ".gemini").mkdir()
        (home / ".claude").mkdir(parents=True)

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_active_runtime() == RUNTIME_UNKNOWN


class TestResolveEffectiveRuntime:
    def test_reports_env_source(self) -> None:
        env = _clean_runtime_env()
        env["CODEX_SESSION"] = "xyz"
        with patch.dict(os.environ, env, clear=True):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_CODEX
        assert result.source == SOURCE_ENV

    def test_installed_runtime_without_activation_signal_stays_unknown(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".gemini")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_UNKNOWN
        assert result.source == SOURCE_UNKNOWN
        assert result.has_gpd_install is False
        assert result.install_scope is None

    def test_reports_global_source_without_install(self, tmp_path: Path) -> None:
        (tmp_path / "home" / ".claude").mkdir(parents=True)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
        ):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_UNKNOWN
        assert result.source == SOURCE_UNKNOWN
        assert result.has_gpd_install is False

    def test_manifest_runtime_alias_fails_closed_for_installed_runtime(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        manifest_path = runtime_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["runtime"] = "Codex"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
        ):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_UNKNOWN
        assert result.source == SOURCE_UNKNOWN
        assert result.has_gpd_install is False

    def test_invalid_manifest_runtime_fails_closed(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        _write_install_manifest(runtime_dir, install_scope=SCOPE_LOCAL)
        manifest_path = runtime_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["runtime"] = "not-a-runtime"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
        ):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_UNKNOWN
        assert result.source == SOURCE_UNKNOWN
        assert result.has_gpd_install is False
        assert detect_runtime_install_target(RUNTIME_CODEX, cwd=workspace, home=home) is None

    def test_require_gpd_install_returns_unknown_when_runtime_has_no_install(self, tmp_path: Path) -> None:
        (tmp_path / ".codex").mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            result = resolve_effective_runtime(require_gpd_install=True)

        assert result.runtime == RUNTIME_UNKNOWN

    def test_require_gpd_install_does_not_fall_through_to_another_installed_runtime(
        self, tmp_path: Path
    ) -> None:
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        env["CLAUDE_CODE_SESSION"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            result = resolve_effective_runtime(require_gpd_install=True)

        assert result.runtime == RUNTIME_UNKNOWN

    def test_require_gpd_install_reports_local_source_for_explicit_target_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX, install_scope=SCOPE_LOCAL)

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            result = resolve_effective_runtime(cwd=workspace, home=home, require_gpd_install=True)

        assert result.runtime == RUNTIME_CODEX
        assert result.source == SOURCE_LOCAL
        assert result.has_gpd_install is True
        assert result.install_scope == SCOPE_LOCAL


class TestNormalizeRuntimeName:
    """Tests for the shared runtime-name normalizer."""

    def test_accepts_runtime_ids_display_names_and_aliases(self) -> None:
        assert normalize_runtime_name("claude-code") == RUNTIME_CLAUDE
        assert normalize_runtime_name("Claude Code") == RUNTIME_CLAUDE
        assert normalize_runtime_name("claude") == RUNTIME_CLAUDE
        assert normalize_runtime_name("open code") == RUNTIME_OPENCODE
        assert catalog_normalize_runtime_name("claude-code") == RUNTIME_CLAUDE
        assert catalog_normalize_runtime_name("Claude Code") == RUNTIME_CLAUDE
        assert catalog_normalize_runtime_name("claude") == RUNTIME_CLAUDE
        assert catalog_normalize_runtime_name("open code") == RUNTIME_OPENCODE

    def test_rejects_unknown_runtime_names(self) -> None:
        assert normalize_runtime_name("not-a-runtime") is None
        assert catalog_normalize_runtime_name("not-a-runtime") is None

    def test_detect_runtime_install_target_returns_none_for_unknown_runtime(self, tmp_path: Path) -> None:
        assert detect_runtime_install_target("not-a-runtime", cwd=tmp_path, home=tmp_path / "home") is None


def test_supported_runtime_names_reflect_live_runtime_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_detect_module, "list_runtime_names", lambda: ["alpha", "beta", "gamma"])
    monkeypatch.setattr(
        runtime_detect_module.adapters_module,
        "get_adapter",
        lambda runtime: (_ for _ in ()).throw(AssertionError(f"unexpected adapter load: {runtime}")),
    )

    assert supported_runtime_names() == ("alpha", "beta", "gamma")
    assert runtime_detect_module._prioritized_runtimes("beta") == ["beta", "alpha", "gamma"]


def test_detect_active_runtime_uses_catalog_descriptor_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    descriptors = {
        "alpha-runtime": SimpleNamespace(activation_env_vars=("GPD_TEST_ALPHA_ACTIVE",)),
        "beta-runtime": SimpleNamespace(activation_env_vars=("GPD_TEST_BETA_ACTIVE",)),
    }

    monkeypatch.setattr(runtime_detect_module, "list_runtime_names", lambda: list(descriptors))
    monkeypatch.setattr(runtime_detect_module, "get_runtime_descriptor", descriptors.__getitem__)
    monkeypatch.setattr(runtime_detect_module, "detect_install_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_detect_module, "_detect_runtime_install_target", lambda *args, **kwargs: None)
    monkeypatch.delenv("GPD_ACTIVE_RUNTIME", raising=False)
    monkeypatch.setenv("GPD_TEST_BETA_ACTIVE", "1")

    result = resolve_effective_runtime(cwd=tmp_path, home=tmp_path)

    assert result.runtime == "beta-runtime"
    assert result.source == SOURCE_ENV


def test_get_adapter_loads_only_one_runtime_module(monkeypatch: pytest.MonkeyPatch) -> None:
    import gpd.adapters as adapters_module

    loaded_modules: list[str] = []
    real_import_module = adapters_module.import_module

    def tracking_import_module(name: str, package: str | None = None) -> object:
        if name.startswith("gpd.adapters."):
            loaded_modules.append(name)
        return real_import_module(name, package)

    monkeypatch.setattr(adapters_module, "_REGISTRY", {})
    monkeypatch.setattr(adapters_module, "import_module", tracking_import_module)

    adapter = adapters_module.get_adapter(RUNTIME_CODEX)

    assert adapter.runtime_name == RUNTIME_CODEX
    assert loaded_modules == [f"gpd.adapters.{RUNTIME_CODEX.replace('-', '_')}"]


def test_runtime_detect_does_not_export_cached_runtime_inventory() -> None:
    assert hasattr(runtime_detect_module, "supported_runtime_names")
    assert not hasattr(runtime_detect_module, "ALL_RUNTIMES")


class TestDetectActiveRuntimeWithInstall:
    """Tests for the install-aware runtime detection helper used by hooks."""

    def test_plain_runtime_dirs_without_gpd_install_do_not_count(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".gemini").mkdir()
        (tmp_path / ".config" / "opencode").mkdir(parents=True)

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_UNKNOWN

    def test_installed_runtime_without_activation_signal_stays_unknown(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_UNKNOWN

    def test_active_runtime_with_install_is_detected(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        env["CODEX_SESSION"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_CODEX

    def test_active_runtime_without_install_returns_unknown_in_install_aware_resolution(
        self, tmp_path: Path
    ) -> None:
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        env["CLAUDE_CODE_SESSION"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_UNKNOWN

    def test_corrupted_opencode_global_manifest_fails_closed_for_installed_runtime(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        opencode_dir = home / ".config" / "opencode"
        (opencode_dir / "get-physics-done").mkdir(parents=True)
        (opencode_dir / "gpd-file-manifest.json").write_text("not-json", encoding="utf-8")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_UNKNOWN

    def test_corrupted_opencode_global_manifest_fails_closed_even_with_explicit_home_override(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        opencode_dir = home / ".config" / "opencode"
        (opencode_dir / "get-physics-done").mkdir(parents=True)
        (opencode_dir / "gpd-file-manifest.json").write_text("not-json", encoding="utf-8")

        env = _clean_runtime_env()
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime_with_gpd_install(cwd=workspace, home=home) == RUNTIME_UNKNOWN

    def test_manifest_without_runtime_key_fails_closed_for_installed_runtime(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        opencode_dir = home / ".config" / "opencode"
        _mark_gpd_install(opencode_dir, runtime=RUNTIME_OPENCODE, install_scope=SCOPE_GLOBAL)
        manifest_path = opencode_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("runtime")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_UNKNOWN

    def test_installed_runtime_ignores_corrupt_env_resolved_global_dir_without_trusted_manifest(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        custom_dir.mkdir()
        (custom_dir / "gpd-file-manifest.json").write_text("not-json", encoding="utf-8")

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert installed_runtime(custom_dir) is None

    def test_installed_runtime_ignores_manifestless_env_resolved_global_dir_without_trusted_manifest(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        custom_dir.mkdir()

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert installed_runtime(custom_dir) is None

    def test_installed_runtime_ignores_manifestless_explicit_target_named_like_local_runtime_dir(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        custom_dir = tmp_path / "custom" / ".codex"
        custom_dir.mkdir(parents=True)

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert installed_runtime(custom_dir) is None

    def test_installed_runtime_ignores_manifestless_workspace_local_dir_named_like_runtime_default(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        nested_workspace = workspace / "research" / "notes"
        nested_workspace.mkdir(parents=True)
        canonical_local_dir = workspace / ".codex"
        canonical_local_dir.mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=nested_workspace),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert installed_runtime(canonical_local_dir) is None

    def test_runtime_from_manifest_or_path_does_not_fall_back_to_manifestless_local_path(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        candidate = workspace / ".codex"
        candidate.mkdir()

        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert _runtime_from_manifest_or_path(candidate) is None

    def test_runtime_from_manifest_or_path_rejects_manifestless_env_global_dir(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX, install_scope=SCOPE_GLOBAL)
        (custom_dir / "gpd-file-manifest.json").unlink()

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _runtime_from_manifest_or_path(custom_dir) is None

    def test_installed_runtime_fails_closed_for_runtime_less_manifest_without_prefix_evidence(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        custom_dir.mkdir()
        (custom_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": SCOPE_GLOBAL}),
            encoding="utf-8",
        )

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert installed_runtime(custom_dir) is None

    def test_installed_runtime_fails_closed_for_corrupt_canonical_global_dir(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        canonical_dir = home / ".config" / "opencode"
        canonical_dir.mkdir(parents=True)
        (canonical_dir / "gpd-file-manifest.json").write_text("not-json", encoding="utf-8")

        env = _clean_runtime_env()
        env["OPENCODE_CONFIG_DIR"] = str(tmp_path / "foreign-opencode")
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert installed_runtime(canonical_dir) is None

    def test_installed_runtime_fails_closed_for_manifestless_canonical_global_dir(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        canonical_dir = home / ".config" / "opencode"
        canonical_dir.mkdir(parents=True)

        env = _clean_runtime_env()
        env["OPENCODE_CONFIG_DIR"] = str(tmp_path / "foreign-opencode")
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert installed_runtime(canonical_dir) is None

    def test_validate_target_runtime_rejects_manifestless_env_global_dir_with_gpd_markers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        adapter = get_adapter(RUNTIME_CODEX)
        target_dir = tmp_path / "custom-codex"
        version_path = target_dir / "get-physics-done" / "VERSION"
        version_path.parent.mkdir(parents=True)
        version_path.write_text("1.0.0\n", encoding="utf-8")

        monkeypatch.setattr(adapter, "_install_explicit_target", True, raising=False)
        monkeypatch.setenv("CODEX_CONFIG_DIR", str(target_dir))

        with pytest.raises(RuntimeError, match="contains GPD artifacts but no manifest"):
            adapter._validate_target_runtime(target_dir, action="install")

    def test_validate_target_runtime_rejects_manifestless_explicit_target_named_like_local_runtime_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        adapter = get_adapter(RUNTIME_CODEX)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target_dir = tmp_path / "custom" / ".codex"
        version_path = target_dir / "get-physics-done" / "VERSION"
        version_path.parent.mkdir(parents=True)
        version_path.write_text("1.0.0\n", encoding="utf-8")

        monkeypatch.setattr(adapter, "_install_explicit_target", True, raising=False)

        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            with pytest.raises(RuntimeError, match="contains GPD artifacts but no manifest"):
                adapter._validate_target_runtime(target_dir, action="install")

    def test_validate_target_runtime_rejects_runtime_less_manifest_with_gpd_markers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        adapter = get_adapter(RUNTIME_CODEX)
        target_dir = tmp_path / ".codex"
        _mark_gpd_install(target_dir, runtime=RUNTIME_CODEX)
        manifest_path = target_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("runtime", None)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(adapter, "_install_explicit_target", True, raising=False)

        with pytest.raises(RuntimeError, match="manifest cannot be trusted"):
            adapter._validate_target_runtime(target_dir, action="install")


class TestDetectRuntimeForGpdUse:
    """Tests for the install-aware runtime selection used by GPD-owned surfaces."""

    def test_prefers_installed_runtime_over_uninstalled_higher_priority_runtime(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        env["CLAUDE_CODE_SESSION"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_runtime_for_gpd_use() == RUNTIME_CODEX

    def test_falls_back_to_plain_active_runtime_when_no_install_is_found(self, tmp_path: Path) -> None:
        env = _clean_runtime_env()
        env["GEMINI_CLI"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_runtime_for_gpd_use() == RUNTIME_GEMINI

    def test_explicit_target_install_is_detected_for_gpd_surfaces(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            assert detect_runtime_for_gpd_use(cwd=workspace, home=home) == RUNTIME_CODEX

    def test_explicit_runtime_override_wins_when_multiple_installed_runtimes_exist(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".claude")
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        env["GPD_ACTIVE_RUNTIME"] = "codex"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_runtime_for_gpd_use() == RUNTIME_CODEX

    def test_import_time_patched_adapter_lookup_does_not_poison_runtime_resolution(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        global_dir = get_adapter(RUNTIME_CLAUDE).resolve_global_config_dir(home=home)
        _mark_gpd_install(global_dir, runtime=RUNTIME_CLAUDE, install_scope=SCOPE_GLOBAL)

        class _DummyAdapter:
            pass

        try:
            with patch("gpd.adapters.get_adapter", return_value=_DummyAdapter()):
                importlib.reload(runtime_detect_module)

            env = _clean_runtime_env()
            with patch.dict(os.environ, env, clear=True):
                assert runtime_detect_module.detect_runtime_for_gpd_use(cwd=workspace, home=home) == RUNTIME_CLAUDE
        finally:
            importlib.reload(runtime_detect_module)

# ─── all_runtime_dirs ──────────────────────────────────────────────────────


class TestAllRuntimeDirs:
    """Tests for all_runtime_dirs."""

    def test_returns_all_global_dirs(self) -> None:
        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            dirs = all_runtime_dirs()

            assert len(dirs) == len(_RUNTIME_DESCRIPTORS)
            home = Path.home()
            assert {
                get_adapter(descriptor.runtime_name).resolve_global_config_dir(home=home)
                for descriptor in _RUNTIME_DESCRIPTORS
            } == set(dirs)

    def test_uses_env_override_paths(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        env = {
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-custom"),
            "CODEX_CONFIG_DIR": str(tmp_path / "codex-custom"),
            "GEMINI_CONFIG_DIR": str(tmp_path / "gemini-custom"),
            "OPENCODE_CONFIG_DIR": str(tmp_path / "opencode-custom"),
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = all_runtime_dirs()

        assert tmp_path / "claude-custom" in dirs
        assert tmp_path / "codex-custom" in dirs
        assert tmp_path / "gemini-custom" in dirs
        assert tmp_path / "opencode-custom" in dirs


# ─── get_todo_dirs / get_cache_dirs ────────────────────────────────────────


class TestHelperDirs:
    """Tests for get_todo_dirs and get_cache_dirs."""

    def test_todo_dirs_include_local_and_global_runtime_paths(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_todo_dirs()

        assert all(d.name == "todos" for d in dirs)
        assert len(dirs) == 2 * len(_RUNTIME_DESCRIPTORS)
        assert tmp_path / ".codex" / "todos" in dirs
        assert tmp_path / ".opencode" / "todos" in dirs
        assert home / ".codex" / "todos" in dirs
        assert home / ".config" / "opencode" / "todos" in dirs

    def test_cache_dirs_include_local_and_global_runtime_paths(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_cache_dirs()

        assert all(d.name == "cache" for d in dirs)
        assert len(dirs) == 2 * len(_RUNTIME_DESCRIPTORS)
        assert tmp_path / ".claude" / "cache" in dirs
        assert tmp_path / ".opencode" / "cache" in dirs
        assert home / ".claude" / "cache" in dirs
        assert home / ".config" / "opencode" / "cache" in dirs

    def test_todo_dirs_use_explicit_workspace_cwd(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            dirs = get_todo_dirs(cwd=workspace, home=home)

        assert workspace / ".claude" / "todos" in dirs
        assert workspace / ".codex" / "todos" in dirs
        assert home / ".claude" / "todos" in dirs
        assert home / ".config" / "opencode" / "todos" in dirs

    def test_todo_dirs_can_prioritize_active_runtime(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        env = _clean_runtime_env()
        env["CODEX_SESSION"] = "active"

        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_todo_dirs(prefer_active=True)

        assert dirs[0] == tmp_path / ".codex" / "todos"
        assert dirs[1] == home / ".codex" / "todos"

    def test_todo_dirs_prefer_installed_runtime_when_higher_priority_runtime_is_uninstalled(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".claude").mkdir()
        _mark_gpd_install(tmp_path / ".codex")

        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_todo_dirs(prefer_active=True)

        assert dirs[0] == tmp_path / ".codex" / "todos"
        assert dirs[1] == home / ".codex" / "todos"

    def test_todo_candidates_prioritize_explicit_target_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            candidates = get_todo_candidates(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert candidates[0].path == custom_dir / "todos"
        assert candidates[0].runtime == RUNTIME_CODEX
        assert candidates[0].scope == SCOPE_LOCAL


def test_ordered_runtime_dirs_for_lookup_dedupes_resolved_equivalent_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    equivalent_cwd = str(home / ".." / "home")

    ordered_dirs = _ordered_runtime_dirs_for_lookup(
        RUNTIME_CODEX,
        cwd=equivalent_cwd,
        home=home,
    )

    assert len(ordered_dirs) == 1
    assert ordered_dirs[0][0].resolve(strict=False) == (home / ".codex").resolve(strict=False)


class TestDetectInstallScope:
    """Tests for local/global install-scope detection."""

    def test_prefers_local_scope_when_local_runtime_dir_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        _mark_gpd_install(tmp_path / ".codex")
        (home / ".codex").mkdir(parents=True)

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CODEX) == SCOPE_LOCAL

    def test_returns_global_scope_when_only_global_runtime_dir_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        _mark_gpd_install(home / ".gemini", install_scope=SCOPE_GLOBAL)

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_GEMINI) == SCOPE_GLOBAL

    def test_manifest_scope_overrides_env_global_dir_for_explicit_target(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX, install_scope=SCOPE_LOCAL)

        elsewhere = tmp_path / "workspace"
        elsewhere.mkdir()
        home = tmp_path / "home"

        with (
            patch.dict(os.environ, {"CODEX_CONFIG_DIR": str(custom_dir)}, clear=False),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CODEX) == SCOPE_LOCAL

    def test_ignores_workspace_runtime_dir_without_gpd_install_when_global_install_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".codex").mkdir()
        global_dir = home / ".codex"
        _mark_gpd_install(global_dir, install_scope=SCOPE_GLOBAL)

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CODEX) == SCOPE_GLOBAL

    def test_returns_none_when_runtime_dirs_have_no_gpd_install_markers(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".claude").mkdir()
        (home / ".claude").mkdir(parents=True)

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CLAUDE) is None


# ─── get_gpd_install_dirs ──────────────────────────────────────────────────


class TestGPDInstallDirs:
    """Tests for get_gpd_install_dirs."""

    def test_returns_both_local_and_global(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_gpd_install_dirs()

        assert len(dirs) == 2 * len(_RUNTIME_DESCRIPTORS)
        assert all("get-physics-done" in str(d) for d in dirs)
        assert tmp_path / ".opencode" / "get-physics-done" in dirs
        assert home / ".config" / "opencode" / "get-physics-done" in dirs

    def test_prefers_env_override_global_dirs(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        env = {
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-custom"),
            "CODEX_CONFIG_DIR": str(tmp_path / "codex-custom"),
            "GEMINI_CONFIG_DIR": str(tmp_path / "gemini-custom"),
            "OPENCODE_CONFIG_DIR": str(tmp_path / "opencode-custom"),
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_gpd_install_dirs()

        assert tmp_path / "claude-custom" / "get-physics-done" in dirs
        assert tmp_path / "codex-custom" / "get-physics-done" in dirs
        assert tmp_path / "gemini-custom" / "get-physics-done" in dirs
        assert tmp_path / "opencode-custom" / "get-physics-done" in dirs

    def test_prefer_active_uses_installed_runtime_when_higher_priority_runtime_is_uninstalled(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".claude").mkdir()
        _mark_gpd_install(tmp_path / ".codex")

        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_gpd_install_dirs(prefer_active=True)

        assert dirs[0] == tmp_path / ".codex" / "get-physics-done"
        assert dirs[1] == home / ".codex" / "get-physics-done"


class TestUpdateCacheFiles:
    """Tests for get_update_cache_files."""

    def test_preferred_runtime_uses_explicit_workspace_cwd(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()

        files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_CODEX)

        assert files[0] == workspace / ".codex" / "cache" / "gpd-update-check.json"
        assert files[1] == home / ".codex" / "cache" / "gpd-update-check.json"

    def test_unknown_preferred_runtime_uses_canonical_runtime_order_without_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()
        (workspace / ".codex" / "cache").mkdir(parents=True)
        (home / ".claude" / "cache").mkdir(parents=True)

        files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert files[0] == workspace / ".claude" / "cache" / "gpd-update-check.json"
        assert files[1] == home / ".claude" / "cache" / "gpd-update-check.json"

    def test_unknown_preferred_runtime_uses_installed_runtime_for_gpd_surfaces(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()
        (workspace / ".claude" / "cache").mkdir(parents=True)
        _mark_gpd_install(workspace / ".codex")

        files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert files[0] == workspace / ".codex" / "cache" / "gpd-update-check.json"
        assert files[1] == home / ".codex" / "cache" / "gpd-update-check.json"

    def test_explicit_target_install_is_prioritized_for_update_cache_lookup(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert files[0] == custom_dir / "cache" / "gpd-update-check.json"
        assert files[1] == workspace / ".codex" / "cache" / "gpd-update-check.json"


class TestUpdateCacheCandidates:
    """Tests for update-cache candidate filtering."""

    def test_candidate_from_wrong_scope_is_rejected_when_runtime_install_scope_is_known(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        global_runtime_dir = home / ".codex"
        _mark_gpd_install(global_runtime_dir, install_scope=SCOPE_GLOBAL)

        stale_local_candidate = UpdateCacheCandidate(
            workspace / ".codex" / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        live_global_candidate = UpdateCacheCandidate(
            global_runtime_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_GLOBAL,
        )

        with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
            assert should_consider_update_cache_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_update_cache_candidate(live_global_candidate, cwd=workspace, home=home) is True

    def test_candidate_with_malformed_manifest_runtime_is_rejected(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        manifest_path = runtime_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["runtime"] = "not-a-runtime"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        candidate = UpdateCacheCandidate(
            runtime_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_update_cache_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_manifest_missing_runtime_is_rejected(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        manifest_path = runtime_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("runtime")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        candidate = UpdateCacheCandidate(
            runtime_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_update_cache_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_non_utf8_manifest_is_rejected(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        (runtime_dir / "gpd-file-manifest.json").write_bytes(b"\xff")

        candidate = UpdateCacheCandidate(
            runtime_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_update_cache_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_missing_manifest_is_rejected_without_trusted_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        (runtime_dir / "cache").mkdir(parents=True)

        candidate = UpdateCacheCandidate(
            runtime_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_update_cache_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_manifest_but_incomplete_install_is_rejected_without_trusted_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        (runtime_dir / "cache").mkdir(parents=True)
        _write_install_manifest(runtime_dir, install_scope=SCOPE_LOCAL)

        candidate = UpdateCacheCandidate(
            runtime_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_update_cache_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_listing_keeps_installed_scope_ahead_of_stale_other_scope(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        (workspace / ".codex" / "cache").mkdir(parents=True)

        global_runtime_dir = home / ".codex"
        _mark_gpd_install(global_runtime_dir, install_scope=SCOPE_GLOBAL)

        candidates = get_update_cache_candidates(cwd=workspace, home=home, preferred_runtime=RUNTIME_CODEX)

        assert candidates[0].runtime == RUNTIME_CODEX
        assert candidates[0].scope == SCOPE_GLOBAL
        assert candidates[1].runtime == RUNTIME_CODEX
        assert candidates[1].scope == SCOPE_LOCAL

    def test_candidate_from_default_path_is_rejected_when_explicit_target_serves_runtime(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        stale_local_candidate = UpdateCacheCandidate(
            workspace / ".codex" / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        explicit_target_candidate = UpdateCacheCandidate(
            custom_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            assert should_consider_update_cache_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_update_cache_candidate(explicit_target_candidate, cwd=workspace, home=home) is True


class TestTodoCandidates:
    def test_candidate_from_wrong_scope_is_rejected_when_runtime_install_scope_is_known(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        global_runtime_dir = home / ".codex"
        _mark_gpd_install(global_runtime_dir, install_scope=SCOPE_GLOBAL)

        stale_local_candidate = TodoCandidate(
            workspace / ".codex" / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        live_global_candidate = TodoCandidate(
            global_runtime_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_GLOBAL,
        )

        with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
            assert should_consider_todo_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_todo_candidate(live_global_candidate, cwd=workspace, home=home) is True

    def test_candidate_with_malformed_manifest_runtime_is_rejected(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        manifest_path = runtime_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["runtime"] = "not-a-runtime"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        candidate = TodoCandidate(
            runtime_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_todo_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_manifest_missing_runtime_is_rejected(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        manifest_path = runtime_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("runtime")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        candidate = TodoCandidate(
            runtime_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_todo_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_non_utf8_manifest_is_rejected(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        _mark_gpd_install(runtime_dir)
        (runtime_dir / "gpd-file-manifest.json").write_bytes(b"\xff")

        candidate = TodoCandidate(
            runtime_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_todo_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_missing_manifest_is_rejected_without_trusted_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        (runtime_dir / "todos").mkdir(parents=True)

        candidate = TodoCandidate(
            runtime_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_todo_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_with_manifest_but_incomplete_install_is_rejected_without_trusted_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        runtime_dir = workspace / ".codex"
        (runtime_dir / "todos").mkdir(parents=True)
        _write_install_manifest(runtime_dir, install_scope=SCOPE_LOCAL)

        candidate = TodoCandidate(
            runtime_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            assert should_consider_todo_candidate(candidate, cwd=workspace, home=home) is False

    def test_candidate_from_default_path_is_rejected_when_explicit_target_serves_runtime(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir, runtime=RUNTIME_CODEX)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        stale_local_candidate = TodoCandidate(
            workspace / ".codex" / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        explicit_target_candidate = TodoCandidate(
            custom_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            assert should_consider_todo_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_todo_candidate(explicit_target_candidate, cwd=workspace, home=home) is True


class TestUpdateCommand:
    """Tests for update_command_for_runtime."""

    def test_known_runtime_commands_are_adapter_derived(self) -> None:
        for runtime in (descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS):
            assert update_command_for_runtime(runtime) == get_adapter(runtime).update_command

    def test_unknown_runtime_uses_runtime_neutral_update_command(self) -> None:
        assert update_command_for_runtime(RUNTIME_UNKNOWN) == _SHARED_INSTALL.bootstrap_command

    def test_claude_runtime_uses_claude_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_CLAUDE).endswith(" --claude")

    def test_codex_runtime_uses_codex_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_CODEX).endswith(" --codex")

    def test_gemini_runtime_uses_gemini_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_GEMINI).endswith(" --gemini")

    def test_opencode_runtime_uses_opencode_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_OPENCODE).endswith(" --opencode")

    def test_local_scope_adds_local_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_CLAUDE, scope=SCOPE_LOCAL).endswith(" --claude --local")

    def test_global_scope_adds_global_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_OPENCODE, scope=SCOPE_GLOBAL).endswith(" --opencode --global")


# ─── _has_gpd_install ──────────────────────────────────────────────────────


class TestHasGpdInstall:
    """Tests for _has_gpd_install directory detection."""

    def test_returns_true_when_complete_install_artifacts_exist(self, tmp_path: Path) -> None:
        """_has_gpd_install returns True only for the shared complete-install contract."""
        _mark_gpd_install(tmp_path / ".codex")
        tmp_path = tmp_path / ".codex"
        assert _has_gpd_install(tmp_path) is True

    def test_returns_false_for_partial_install_markers(self, tmp_path: Path) -> None:
        """Partial markers no longer count as an installed runtime surface."""
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "get-physics-done").mkdir()
        assert _has_gpd_install(tmp_path) is False

    def test_returns_false_when_manifest_lacks_runtime(self, tmp_path: Path) -> None:
        """A present manifest without a valid runtime must fail closed."""
        runtime_dir = tmp_path / ".codex"
        _mark_gpd_install(runtime_dir)
        manifest_path = runtime_dir / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("runtime")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        assert _has_gpd_install(runtime_dir) is False
