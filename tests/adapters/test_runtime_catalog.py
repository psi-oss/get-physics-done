"""Regression tests for runtime catalog config resolution and ordering."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import gpd.adapters.runtime_catalog as runtime_catalog
from gpd.adapters.runtime_catalog import (
    get_hook_payload_policy,
    get_runtime_capabilities,
    get_runtime_descriptor,
    iter_runtime_descriptors,
    list_runtime_names,
    resolve_global_config_dir,
)

_RUNTIME_CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "gpd" / "adapters" / "runtime_catalog.json"


def _iter_runtime_descriptors_from_payload(
    payload: list[dict[str, object]],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)
    runtime_catalog._load_catalog.cache_clear()
    try:
        return runtime_catalog.iter_runtime_descriptors()
    finally:
        runtime_catalog._load_catalog.cache_clear()


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

    assert len({descriptor.runtime_name for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.priority for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.config_dir_name for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.install_flag for descriptor in descriptors}) == len(descriptors)

    selection_flags = [flag for descriptor in descriptors for flag in descriptor.selection_flags]
    selection_aliases = [alias for descriptor in descriptors for alias in descriptor.selection_aliases]
    activation_env_vars = [env_var for descriptor in descriptors for env_var in descriptor.activation_env_vars]

    assert len(set(selection_flags)) == len(selection_flags)
    assert len(set(selection_aliases)) == len(selection_aliases)
    assert len(set(activation_env_vars)) == len(activation_env_vars)


def test_runtime_catalog_rejects_unknown_top_level_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["legacy_note"] = "unexpected"

    with pytest.raises(ValueError, match=r"runtime catalog entry 0 contains unknown key\(s\): legacy_note"):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_blank_selection_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["selection_aliases"] = [payload[0]["selection_aliases"][0], " "]

    with pytest.raises(
        ValueError,
        match=r"runtime catalog entry 0\.selection_aliases\[1\] must be a non-empty string",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_non_boolean_native_include_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["native_include_support"] = "true"

    with pytest.raises(ValueError, match=r"runtime catalog entry 0\.native_include_support must be a boolean"):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_hook_payload_policy_uses_runtime_specific_overrides_and_merged_fallback() -> None:
    codex_policy = get_hook_payload_policy("codex")
    merged_policy = get_hook_payload_policy()

    assert codex_policy.notify_event_types == ("agent-turn-complete",)
    assert "agent-turn-complete" in merged_policy.notify_event_types
    assert "cwd" in merged_policy.workspace_keys
    assert codex_policy.supports_runtime_session_payload_attribution is False
    assert codex_policy.supports_agent_payload_attribution is False
    assert merged_policy.supports_runtime_session_payload_attribution is False
    assert merged_policy.supports_agent_payload_attribution is False
    assert isinstance(codex_policy.runtime_session_id_keys, tuple)
    assert isinstance(codex_policy.agent_id_keys, tuple)
    assert isinstance(codex_policy.agent_name_keys, tuple)
    assert isinstance(codex_policy.agent_scope_keys, tuple)
    assert isinstance(merged_policy.runtime_session_id_keys, tuple)
    assert isinstance(merged_policy.agent_id_keys, tuple)
    assert isinstance(merged_policy.agent_name_keys, tuple)
    assert isinstance(merged_policy.agent_scope_keys, tuple)


def test_hook_payload_policy_merges_declared_runtime_session_and_agent_attribution_keys(monkeypatch) -> None:
    descriptors = iter_runtime_descriptors()
    synthetic = (
        replace(
            descriptors[0],
            hook_payload=replace(
                descriptors[0].hook_payload,
                runtime_session_id_keys=("session_id",),
                agent_id_keys=("agent_id",),
                agent_name_keys=("agent_name",),
                agent_scope_keys=("agent_scope",),
            ),
        ),
        *descriptors[1:],
    )
    monkeypatch.setattr(runtime_catalog, "iter_runtime_descriptors", lambda: synthetic)

    runtime_policy = get_hook_payload_policy(synthetic[0].runtime_name)
    merged_policy = get_hook_payload_policy()

    assert runtime_policy.runtime_session_id_keys == ("session_id",)
    assert runtime_policy.agent_id_keys == ("agent_id",)
    assert runtime_policy.agent_name_keys == ("agent_name",)
    assert runtime_policy.agent_scope_keys == ("agent_scope",)
    assert runtime_policy.supports_runtime_session_payload_attribution is True
    assert runtime_policy.supports_agent_payload_attribution is True
    assert merged_policy.runtime_session_id_keys[0] == "session_id"
    assert merged_policy.agent_id_keys[0] == "agent_id"
    assert merged_policy.agent_name_keys[0] == "agent_name"
    assert merged_policy.agent_scope_keys[0] == "agent_scope"
    assert merged_policy.supports_runtime_session_payload_attribution is True
    assert merged_policy.supports_agent_payload_attribution is True


def test_runtime_capabilities_are_explicit_per_runtime() -> None:
    claude = get_runtime_capabilities("claude-code")
    gemini = get_runtime_capabilities("gemini")
    codex = get_runtime_capabilities("codex")
    opencode = get_runtime_capabilities("opencode")

    assert claude.permissions_surface == "config-file"
    assert claude.permission_surface_kind == "settings.json:permissions.defaultMode"
    assert claude.supports_runtime_permission_sync is True
    assert claude.supports_prompt_free_mode is True
    assert claude.prompt_free_requires_relaunch is True
    assert claude.statusline_surface == "explicit"
    assert claude.statusline_config_surface == "settings.json:statusLine"
    assert claude.notify_surface == "none"
    assert claude.notify_config_surface == "none"
    assert claude.supports_context_meter is True
    assert claude.supports_usage_tokens is False
    assert claude.supports_cost_usd is False
    assert claude.telemetry_completeness == "none"
    assert get_hook_payload_policy("claude-code").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("claude-code").supports_agent_payload_attribution is False

    assert gemini.permissions_surface == "launch-wrapper"
    assert gemini.permission_surface_kind == "managed-launcher-wrapper"
    assert gemini.supports_runtime_permission_sync is True
    assert gemini.supports_prompt_free_mode is True
    assert gemini.prompt_free_requires_relaunch is True
    assert gemini.statusline_surface == "explicit"
    assert gemini.statusline_config_surface == "settings.json:statusLine"
    assert gemini.notify_surface == "none"
    assert gemini.notify_config_surface == "none"
    assert gemini.supports_context_meter is True
    assert gemini.supports_usage_tokens is False
    assert gemini.supports_cost_usd is False
    assert gemini.telemetry_completeness == "none"
    assert get_hook_payload_policy("gemini").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("gemini").supports_agent_payload_attribution is False

    assert codex.permissions_surface == "config-file"
    assert codex.permission_surface_kind == "config.toml:approval_policy+sandbox_mode"
    assert codex.supports_runtime_permission_sync is True
    assert codex.supports_prompt_free_mode is True
    assert codex.prompt_free_requires_relaunch is True
    assert codex.statusline_surface == "none"
    assert codex.statusline_config_surface == "none"
    assert codex.notify_surface == "explicit"
    assert codex.notify_config_surface == "config.toml:notify"
    assert codex.telemetry_source == "notify-hook"
    assert codex.telemetry_completeness == "best-effort"
    assert codex.supports_context_meter is False
    assert codex.supports_usage_tokens is True
    assert codex.supports_cost_usd is True
    assert get_hook_payload_policy("codex").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("codex").supports_agent_payload_attribution is False

    assert opencode.permissions_surface == "config-file"
    assert opencode.permission_surface_kind == "opencode.json:permission"
    assert opencode.supports_runtime_permission_sync is True
    assert opencode.supports_prompt_free_mode is True
    assert opencode.prompt_free_requires_relaunch is True
    assert opencode.statusline_surface == "none"
    assert opencode.statusline_config_surface == "none"
    assert opencode.notify_surface == "none"
    assert opencode.notify_config_surface == "none"
    assert opencode.telemetry_completeness == "none"
    assert opencode.supports_context_meter is False
    assert opencode.supports_usage_tokens is False
    assert opencode.supports_cost_usd is False
    assert get_hook_payload_policy("opencode").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("opencode").supports_agent_payload_attribution is False


def test_runtime_capabilities_and_hook_payload_contract_stay_coherent() -> None:
    allowed_permissions_surfaces = {"config-file", "launch-wrapper", "unsupported"}
    allowed_permission_surface_kinds = {
        "settings.json:permissions.defaultMode",
        "managed-launcher-wrapper",
        "config.toml:approval_policy+sandbox_mode",
        "opencode.json:permission",
        "none",
    }
    allowed_hook_surfaces = {"explicit", "none"}
    allowed_statusline_config_surfaces = {"settings.json:statusLine", "none"}
    allowed_notify_config_surfaces = {"config.toml:notify", "none"}
    allowed_telemetry_sources = {"notify-hook", "none"}
    allowed_telemetry_completeness = {"best-effort", "none"}

    for runtime_name in list_runtime_names():
        capabilities = get_runtime_capabilities(runtime_name)
        hook_payload = get_hook_payload_policy(runtime_name)

        assert capabilities.permissions_surface in allowed_permissions_surfaces
        assert capabilities.permission_surface_kind in allowed_permission_surface_kinds
        assert isinstance(capabilities.supports_runtime_permission_sync, bool)
        assert isinstance(capabilities.supports_prompt_free_mode, bool)
        assert isinstance(capabilities.prompt_free_requires_relaunch, bool)
        assert capabilities.statusline_surface in allowed_hook_surfaces
        assert capabilities.statusline_config_surface in allowed_statusline_config_surfaces
        assert capabilities.notify_surface in allowed_hook_surfaces
        assert capabilities.notify_config_surface in allowed_notify_config_surfaces
        assert capabilities.telemetry_source in allowed_telemetry_sources
        assert capabilities.telemetry_completeness in allowed_telemetry_completeness
        assert isinstance(capabilities.supports_usage_tokens, bool)
        assert isinstance(capabilities.supports_cost_usd, bool)
        assert isinstance(capabilities.supports_context_meter, bool)
        assert hook_payload.supports_runtime_session_payload_attribution == bool(hook_payload.runtime_session_id_keys)
        assert hook_payload.supports_agent_payload_attribution == bool(
            hook_payload.agent_id_keys or hook_payload.agent_name_keys or hook_payload.agent_scope_keys
        )

        if capabilities.statusline_surface == "explicit":
            assert capabilities.statusline_config_surface != "none"
            assert hook_payload.model_keys
            assert hook_payload.context_window_size_keys
            assert hook_payload.context_remaining_keys
            assert capabilities.supports_context_meter is True
        else:
            assert capabilities.statusline_config_surface == "none"
            assert not hook_payload.context_window_size_keys
            assert not hook_payload.context_remaining_keys
            assert capabilities.supports_context_meter is False

        if capabilities.notify_surface == "explicit":
            assert capabilities.notify_config_surface != "none"
            assert hook_payload.notify_event_types
        else:
            assert capabilities.notify_config_surface == "none"
            assert not hook_payload.notify_event_types

        if capabilities.telemetry_completeness == "best-effort":
            assert capabilities.telemetry_source == "notify-hook"
            assert capabilities.notify_surface == "explicit"
            assert capabilities.supports_usage_tokens is True
            assert capabilities.supports_cost_usd is True
            assert hook_payload.usage_keys
            assert hook_payload.input_tokens_keys
            assert hook_payload.output_tokens_keys
            assert hook_payload.cost_usd_keys
        else:
            assert capabilities.telemetry_source == "none"
            assert capabilities.supports_usage_tokens is False
            assert capabilities.supports_cost_usd is False
            assert not hook_payload.usage_keys
            assert not hook_payload.input_tokens_keys
            assert not hook_payload.output_tokens_keys
            assert not hook_payload.cost_usd_keys

        if hook_payload.supports_runtime_session_payload_attribution or hook_payload.supports_agent_payload_attribution:
            assert capabilities.notify_surface == "explicit"
            assert capabilities.telemetry_source == "notify-hook"


def test_hook_payload_policy_exposes_usage_alias_fields_for_cost_telemetry() -> None:
    codex_policy = get_hook_payload_policy("codex")
    merged_policy = get_hook_payload_policy()
    merged_aliases = {
        *merged_policy.usage_keys,
        *merged_policy.input_tokens_keys,
        *merged_policy.output_tokens_keys,
        *merged_policy.cached_input_tokens_keys,
        *merged_policy.cache_write_input_tokens_keys,
        *merged_policy.cost_usd_keys,
    }

    assert codex_policy.usage_keys == ("usage", "token_usage", "tokens")
    assert codex_policy.input_tokens_keys == ("input_tokens", "prompt_tokens", "inputTokens", "promptTokens")
    assert codex_policy.output_tokens_keys == (
        "output_tokens",
        "completion_tokens",
        "outputTokens",
        "completionTokens",
    )
    assert codex_policy.cached_input_tokens_keys == (
        "cached_input_tokens",
        "cache_read_input_tokens",
        "cachedInputTokens",
        "cacheReadInputTokens",
    )
    assert codex_policy.cache_write_input_tokens_keys == (
        "cache_write_input_tokens",
        "cache_creation_input_tokens",
        "cacheWriteInputTokens",
        "cacheCreationInputTokens",
    )
    assert codex_policy.cost_usd_keys == ("cost_usd", "costUsd", "usd_cost", "usdCost")

    for alias in (
        "usage",
        "token_usage",
        "tokens",
        "promptTokens",
        "completionTokens",
        "cacheReadInputTokens",
        "cacheCreationInputTokens",
        "usdCost",
    ):
        assert alias in merged_aliases
