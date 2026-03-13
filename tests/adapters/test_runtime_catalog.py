"""Regression tests for runtime catalog config resolution and ordering."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.runtime_catalog import (
    get_hook_payload_policy,
    get_runtime_descriptor,
    iter_runtime_descriptors,
    list_runtime_names,
    resolve_global_config_dir,
)


def test_resolve_global_config_dir_env_or_home_respects_explicit_empty_environ(monkeypatch) -> None:
    monkeypatch.setenv("CODEX_CONFIG_DIR", "/tmp/process-codex-config")

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("codex"),
        home=Path("/tmp/home"),
        environ={},
    )

    assert resolved == Path("/tmp/home/.codex")


def test_resolve_global_config_dir_xdg_app_respects_explicit_empty_environ(monkeypatch) -> None:
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", "/tmp/process-opencode-config")
    monkeypatch.setenv("OPENCODE_CONFIG", "/tmp/process-opencode/opencode.json")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/process-xdg")

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("opencode"),
        home=Path("/tmp/home"),
        environ={},
    )

    assert resolved == Path("/tmp/home/.config/opencode")


def test_runtime_catalog_explicit_priority_order() -> None:
    descriptors = iter_runtime_descriptors()
    assert [descriptor.runtime_name for descriptor in descriptors] == list_runtime_names()
    assert [descriptor.priority for descriptor in descriptors] == sorted(descriptor.priority for descriptor in descriptors)


def test_runtime_catalog_records_native_include_support() -> None:
    assert get_runtime_descriptor("claude-code").native_include_support is True
    assert get_runtime_descriptor("codex").native_include_support is False
    assert get_runtime_descriptor("gemini").native_include_support is False
    assert get_runtime_descriptor("opencode").native_include_support is False


def test_runtime_catalog_runtime_keys_are_unique() -> None:
    descriptors = iter_runtime_descriptors()

    assert len({descriptor.priority for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.config_dir_name for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.install_flag for descriptor in descriptors}) == len(descriptors)

    selection_flags = [flag for descriptor in descriptors for flag in descriptor.selection_flags]
    selection_aliases = [alias for descriptor in descriptors for alias in descriptor.selection_aliases]
    activation_env_vars = [env_var for descriptor in descriptors for env_var in descriptor.activation_env_vars]

    assert len(set(selection_flags)) == len(selection_flags)
    assert len(set(selection_aliases)) == len(selection_aliases)
    assert len(set(activation_env_vars)) == len(activation_env_vars)


def test_hook_payload_policy_uses_runtime_specific_overrides_and_merged_fallback() -> None:
    codex_policy = get_hook_payload_policy("codex")
    merged_policy = get_hook_payload_policy()

    assert codex_policy.notify_event_types == ("agent-turn-complete",)
    assert "agent-turn-complete" in merged_policy.notify_event_types
    assert "cwd" in merged_policy.workspace_keys
