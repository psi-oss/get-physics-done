"""Regression tests for runtime platform detection in gpd.core.context."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import gpd.core.context as context_module
from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters.install_utils import GPD_INSTALL_DIR_NAME
from gpd.adapters.runtime_catalog import get_runtime_descriptor
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME

_RUNTIME_NAMES = tuple(list_runtimes())
_SUPPORTED_RUNTIME_DESCRIPTORS = tuple(get_runtime_descriptor(runtime) for runtime in _RUNTIME_NAMES)
_RUNTIME_ENV_KEYS = {
    ENV_GPD_ACTIVE_RUNTIME,
    *(
        env_var
        for descriptor in _SUPPORTED_RUNTIME_DESCRIPTORS
        for env_var in (
            *descriptor.activation_env_vars,
            descriptor.global_config.env_var,
            descriptor.global_config.env_dir_var,
            descriptor.global_config.env_file_var,
            "XDG_CONFIG_HOME" if descriptor.global_config.strategy == "xdg_app" else None,
        )
        if env_var
    ),
}


def _mark_complete_runtime_install(config_dir: Path, *, runtime: str, install_scope: str = "local") -> None:
    """Create the concrete install markers the fallback detector should trust."""
    adapter = get_adapter(runtime)
    config_dir.mkdir(parents=True, exist_ok=True)
    for relpath in adapter.install_completeness_relpaths():
        if relpath == "gpd-file-manifest.json":
            continue
        artifact = config_dir / relpath
        artifact.parent.mkdir(parents=True, exist_ok=True)
        if artifact.suffix:
            artifact.write_text("{}\n" if artifact.suffix == ".json" else "# test\n", encoding="utf-8")
        else:
            artifact.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {"runtime": runtime, "install_scope": install_scope}
    if runtime == "codex":
        skills_dir = config_dir.parent / ".agents" / "skills"
        (skills_dir / "gpd-help").mkdir(parents=True, exist_ok=True)
        manifest["codex_skills_dir"] = str(skills_dir)
    (config_dir / "gpd-file-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _runtime_pair() -> tuple[str, str]:
    if len(_RUNTIME_NAMES) < 2:
        raise AssertionError("Expected at least two supported runtimes")
    return _RUNTIME_NAMES[0], _RUNTIME_NAMES[1]


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove runtime detection env vars so each test controls the signal."""
    for key in _RUNTIME_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    ("env_var", "expected"),
    [(descriptor.activation_env_vars[0], descriptor.runtime_name) for descriptor in _SUPPORTED_RUNTIME_DESCRIPTORS],
)
def test_init_context_uses_active_runtime_signal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env_var: str, expected: str
) -> None:
    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        runtime_env.setenv(env_var, "active")

        module = importlib.reload(context_module)
        ctx = module.init_new_project(tmp_path)
        assert ctx["platform"] == expected

    importlib.reload(context_module)


def test_init_context_uses_runtime_detect_directory_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = _RUNTIME_NAMES[0]
    adapter = get_adapter(runtime)

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        _mark_complete_runtime_install(tmp_path / adapter.local_config_dir_name, runtime=runtime)

        with (
            patch("gpd.core.context.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="unknown"),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="unknown"),
        ):
            module = importlib.reload(context_module)
            ctx = module.init_new_project(tmp_path)
            assert ctx["platform"] == runtime

    importlib.reload(context_module)


def test_detect_platform_fallback_ignores_incomplete_local_runtime_dirs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stray_runtime, installed_runtime = _runtime_pair()
    stray_adapter = get_adapter(stray_runtime)
    installed_adapter = get_adapter(installed_runtime)

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        (tmp_path / stray_adapter.local_config_dir_name).mkdir()
        _mark_complete_runtime_install(tmp_path / installed_adapter.local_config_dir_name, runtime=installed_runtime)

        with (
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="unknown"),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="unknown"),
        ):
            assert context_module._detect_platform(tmp_path) == installed_runtime


def test_detect_platform_fallback_ignores_incomplete_global_runtime_dirs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stray_runtime, installed_runtime = _runtime_pair()
    stray_adapter = get_adapter(stray_runtime)
    installed_adapter = get_adapter(installed_runtime)

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        stray_global = stray_adapter.resolve_global_config_dir(home=tmp_path)
        stray_global.mkdir(parents=True, exist_ok=True)
        installed_global = installed_adapter.resolve_global_config_dir(home=tmp_path)
        _mark_complete_runtime_install(installed_global, runtime=installed_runtime, install_scope="global")

        with (
            patch("gpd.core.context.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="unknown"),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="unknown"),
        ):
            assert context_module._detect_platform(tmp_path) == installed_runtime


def test_detect_platform_delegates_install_fallback_to_runtime_detector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stray_runtime, installed_runtime = _runtime_pair()
    calls: list[tuple[str, Path | None, Path | None]] = []

    def _fake_detect_runtime_install_target(
        runtime: str,
        *,
        cwd: Path | None = None,
        home: Path | None = None,
    ) -> object | None:
        calls.append((runtime, cwd, home))
        if runtime == installed_runtime:
            return SimpleNamespace(config_dir=tmp_path / "installed", install_scope="local")
        return None

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        with (
            patch("gpd.core.context.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="unknown"),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="unknown"),
            patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=_fake_detect_runtime_install_target),
        ):
            assert context_module._detect_platform(tmp_path) == installed_runtime

    assert calls == [
        (stray_runtime, tmp_path, tmp_path),
        (installed_runtime, tmp_path, tmp_path),
    ]


def test_init_context_prefers_explicit_gpd_runtime_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    preferred_runtime, secondary_runtime = _runtime_pair()
    preferred_adapter = get_adapter(preferred_runtime)
    secondary_adapter = get_adapter(secondary_runtime)

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        runtime_env.setenv(ENV_GPD_ACTIVE_RUNTIME, preferred_runtime)
        (tmp_path / secondary_adapter.local_config_dir_name / GPD_INSTALL_DIR_NAME).mkdir(parents=True)
        (tmp_path / preferred_adapter.local_config_dir_name / GPD_INSTALL_DIR_NAME).mkdir(parents=True)

        with patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path), \
             patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path):
            module = importlib.reload(context_module)
            ctx = module.init_progress(tmp_path)
            assert ctx["platform"] == preferred_runtime

    importlib.reload(context_module)


def test_resolve_model_delegates_runtime_specific_lookup_to_config_helper(tmp_path: Path) -> None:
    runtime = _RUNTIME_NAMES[0]
    calls: dict[str, object] = {}

    def _fake_resolve_model(project_dir: Path, agent_name: str, runtime: str | None = None) -> str | None:
        calls["project_dir"] = project_dir
        calls["agent_name"] = agent_name
        calls["runtime"] = runtime
        return "delegated-model"

    with patch.object(context_module, "_resolve_model_canonical", side_effect=_fake_resolve_model):
        result = context_module._resolve_model(
            tmp_path,
            "gpd-planner",
            {"model_profile": "review", "model_overrides": {runtime: {"tier-1": "do-not-read-directly"}}},
            runtime=runtime,
        )

    assert result == "delegated-model"
    assert calls == {"project_dir": tmp_path, "agent_name": "gpd-planner", "runtime": runtime}


def test_resolve_model_falls_back_to_platform_detection_when_runtime_detector_returns_unknown(tmp_path: Path) -> None:
    runtime = _RUNTIME_NAMES[0]
    calls: dict[str, object] = {}

    def _fake_resolve_model(project_dir: Path, agent_name: str, runtime: str | None = None) -> str | None:
        calls["project_dir"] = project_dir
        calls["agent_name"] = agent_name
        calls["runtime"] = runtime
        return "fallback-model"

    with (
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="unknown"),
        patch.object(context_module, "_detect_platform", return_value=runtime),
        patch.object(context_module, "_resolve_model_canonical", side_effect=_fake_resolve_model),
    ):
        result = context_module._resolve_model(tmp_path, "gpd-executor")

    assert result == "fallback-model"
    assert calls == {"project_dir": tmp_path, "agent_name": "gpd-executor", "runtime": runtime}


def test_resolve_model_uses_runtime_unknown_constant_not_literal(tmp_path: Path) -> None:
    runtime_unknown = "runtime-unknown"
    calls: dict[str, object] = {}

    def _fake_resolve_model(project_dir: Path, agent_name: str, runtime: str | None = None) -> str | None:
        calls["project_dir"] = project_dir
        calls["agent_name"] = agent_name
        calls["runtime"] = runtime
        return "default-model"

    with (
        patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
        patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=runtime_unknown),
        patch.object(context_module, "_detect_platform", return_value=runtime_unknown),
        patch.object(context_module, "_resolve_model_canonical", side_effect=_fake_resolve_model),
    ):
        result = context_module._resolve_model(tmp_path, "gpd-executor")

    assert result == "default-model"
    assert calls == {"project_dir": tmp_path, "agent_name": "gpd-executor", "runtime": None}


def test_detect_platform_uses_runtime_unknown_constant_not_literal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_unknown = "runtime-unknown"
    installed_runtime = _RUNTIME_NAMES[0]

    def _fake_detect_runtime_install_target(
        runtime: str,
        *,
        cwd: Path | None = None,
        home: Path | None = None,
    ) -> object | None:
        if runtime == installed_runtime:
            return SimpleNamespace(config_dir=tmp_path / "installed", install_scope="local")
        return None

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        with (
            patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
            patch("gpd.core.context.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value=runtime_unknown),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=runtime_unknown),
            patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=_fake_detect_runtime_install_target),
        ):
            assert context_module._detect_platform(tmp_path) == installed_runtime


def test_detect_platform_degrades_cleanly_when_runtime_detect_import_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_detect_module = sys.modules.get("gpd.hooks.runtime_detect")
    monkeypatch.setitem(sys.modules, "gpd.hooks.runtime_detect", None)
    try:
        assert context_module._detect_platform(tmp_path) == "unknown"
    finally:
        if runtime_detect_module is None:
            sys.modules.pop("gpd.hooks.runtime_detect", None)
        else:
            monkeypatch.setitem(sys.modules, "gpd.hooks.runtime_detect", runtime_detect_module)
