"""Assertions for runtime platform detection in gpd.core.context."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
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

        with patch("gpd.core.context.Path.home", return_value=tmp_path / "home"):
            module = importlib.reload(context_module)
            ctx = module.init_new_project(tmp_path)
            assert ctx["platform"] == expected

    importlib.reload(context_module)


def test_init_context_uses_runtime_detector_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = _RUNTIME_NAMES[0]

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)

        with (
            patch("gpd.core.context.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=runtime),
            patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected direct install lookup")),
        ):
            module = importlib.reload(context_module)
            ctx = module.init_new_project(tmp_path)
            assert ctx["platform"] == runtime

    importlib.reload(context_module)


def test_detect_platform_returns_runtime_detector_result_without_install_probe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _RUNTIME_NAMES[0]

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        with (
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=runtime),
            patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected direct install lookup")),
        ):
            assert context_module._detect_platform(tmp_path) == runtime


def test_detect_platform_prefers_runtime_detector_over_unrelated_activation_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    detector_runtime, env_runtime = _runtime_pair()
    env_descriptor = get_runtime_descriptor(env_runtime)

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        runtime_env.setenv(env_descriptor.activation_env_vars[0], "active")
        with (
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=detector_runtime),
            patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected direct install lookup")),
        ):
            assert context_module._detect_platform(tmp_path) == detector_runtime


def test_detect_platform_propagates_runtime_unknown_without_install_probe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_unknown = "runtime-unknown"

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        with (
            patch("gpd.core.context.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=runtime_unknown),
            patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected direct install lookup")),
        ):
            assert context_module._detect_platform(tmp_path) == runtime_unknown


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

    with monkeypatch.context() as runtime_env:
        _clear_runtime_env(runtime_env)
        with (
            patch("gpd.hooks.runtime_detect.RUNTIME_UNKNOWN", runtime_unknown),
            patch("gpd.core.context.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value=runtime_unknown),
            patch("gpd.hooks.runtime_detect.detect_runtime_install_target", side_effect=AssertionError("unexpected direct install lookup")),
        ):
            assert context_module._detect_platform(tmp_path) == runtime_unknown


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
