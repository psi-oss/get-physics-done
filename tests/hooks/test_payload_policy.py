from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gpd.adapters.runtime_catalog import get_hook_payload_policy
from gpd.hooks.install_context import HookLookupContext, SelfOwnedInstallContext
from gpd.hooks.payload_policy import resolve_hook_payload_policy, resolve_hook_surface_runtime


def test_resolve_hook_surface_runtime_prefers_self_owned_install_for_supported_surface(tmp_path: Path) -> None:
    hook_file = tmp_path / ".claude" / "hooks" / "statusline.py"
    self_install = SelfOwnedInstallContext(
        config_dir=tmp_path / ".claude",
        runtime="claude-code",
        install_scope="local",
    )

    with (
        patch("gpd.hooks.payload_policy.hook_layout.detect_self_owned_install", return_value=self_install),
        patch(
            "gpd.hooks.payload_policy.hook_layout.resolve_hook_lookup_context",
            return_value=HookLookupContext(
                lookup_cwd=tmp_path / "workspace",
                resolved_home=tmp_path / "home",
                active_runtime="gemini",
                preferred_runtime="gemini",
            ),
        ),
    ):
        runtime = resolve_hook_surface_runtime(hook_file=hook_file, cwd=tmp_path / "workspace", surface="statusline")

    assert runtime == "claude-code"


def test_resolve_hook_surface_runtime_ignores_self_owned_install_when_surface_is_unsupported(tmp_path: Path) -> None:
    hook_file = tmp_path / ".codex" / "hooks" / "statusline.py"
    self_install = SelfOwnedInstallContext(
        config_dir=tmp_path / ".codex",
        runtime="codex",
        install_scope="local",
    )

    with (
        patch("gpd.hooks.payload_policy.hook_layout.detect_self_owned_install", return_value=self_install),
        patch(
            "gpd.hooks.payload_policy.hook_layout.resolve_hook_lookup_context",
            return_value=HookLookupContext(
                lookup_cwd=tmp_path / "workspace",
                resolved_home=tmp_path / "home",
                active_runtime="gemini",
                preferred_runtime="gemini",
            ),
        ),
    ):
        runtime = resolve_hook_surface_runtime(hook_file=hook_file, cwd=tmp_path / "workspace", surface="statusline")

    assert runtime == "gemini"


def test_resolve_hook_surface_runtime_falls_back_when_self_owned_runtime_is_unknown(tmp_path: Path) -> None:
    hook_file = tmp_path / ".claude" / "hooks" / "notify.py"
    self_install = SelfOwnedInstallContext(
        config_dir=tmp_path / ".claude",
        runtime="unknown-runtime",
        install_scope="local",
    )

    with (
        patch("gpd.hooks.payload_policy.hook_layout.detect_self_owned_install", return_value=self_install),
        patch(
            "gpd.hooks.payload_policy.hook_layout.resolve_hook_lookup_context",
            return_value=HookLookupContext(
                lookup_cwd=tmp_path / "workspace",
                resolved_home=tmp_path / "home",
                active_runtime=None,
                preferred_runtime=None,
            ),
        ),
        patch("gpd.hooks.payload_policy.get_runtime_capabilities", side_effect=KeyError("unknown runtime")),
    ):
        runtime = resolve_hook_surface_runtime(hook_file=hook_file, cwd=tmp_path / "workspace", surface="notify")
        policy = resolve_hook_payload_policy(hook_file=hook_file, cwd=tmp_path / "workspace", surface="notify")

    assert runtime is None
    assert policy == get_hook_payload_policy()


def test_resolve_hook_surface_runtime_propagates_unexpected_runtime_catalog_errors(
    tmp_path: Path,
) -> None:
    hook_file = tmp_path / ".claude" / "hooks" / "notify.py"
    self_install = SelfOwnedInstallContext(
        config_dir=tmp_path / ".claude",
        runtime="broken-runtime",
        install_scope="local",
    )

    with (
        patch("gpd.hooks.payload_policy.hook_layout.detect_self_owned_install", return_value=self_install),
        patch(
            "gpd.hooks.payload_policy.hook_layout.resolve_hook_lookup_context",
            return_value=HookLookupContext(
                lookup_cwd=tmp_path / "workspace",
                resolved_home=tmp_path / "home",
                active_runtime="gemini",
                preferred_runtime="gemini",
            ),
        ),
        patch("gpd.hooks.payload_policy.get_runtime_capabilities", side_effect=RuntimeError("catalog boom")),
    ):
        with pytest.raises(RuntimeError, match="catalog boom"):
            resolve_hook_surface_runtime(hook_file=hook_file, cwd=tmp_path / "workspace", surface="notify")


def test_resolve_hook_payload_policy_uses_surface_runtime_resolution(tmp_path: Path) -> None:
    hook_file = tmp_path / ".codex" / "hooks" / "notify.py"

    with patch("gpd.hooks.payload_policy.resolve_hook_surface_runtime", return_value="codex") as mock_runtime:
        policy = resolve_hook_payload_policy(hook_file=hook_file, cwd=tmp_path / "workspace", surface="notify")

    mock_runtime.assert_called_once_with(hook_file=hook_file, cwd=tmp_path / "workspace", surface="notify")
    assert policy == get_hook_payload_policy("codex")


def test_resolve_hook_payload_policy_is_surface_aware_for_same_self_owned_install(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    hook_dir = tmp_path / ".codex" / "hooks"
    notify_hook = hook_dir / "notify.py"
    statusline_hook = hook_dir / "statusline.py"
    self_install = SelfOwnedInstallContext(
        config_dir=tmp_path / ".codex",
        runtime="codex",
        install_scope="local",
    )

    with (
        patch("gpd.hooks.payload_policy.hook_layout.detect_self_owned_install", return_value=self_install),
        patch(
            "gpd.hooks.payload_policy.hook_layout.resolve_hook_lookup_context",
            return_value=HookLookupContext(
                lookup_cwd=workspace,
                resolved_home=tmp_path / "home",
                active_runtime="claude-code",
                preferred_runtime="claude-code",
            ),
        ),
    ):
        notify_policy = resolve_hook_payload_policy(hook_file=notify_hook, cwd=workspace, surface="notify")
        statusline_policy = resolve_hook_payload_policy(
            hook_file=statusline_hook,
            cwd=workspace,
            surface="statusline",
        )

    assert notify_policy == get_hook_payload_policy("codex")
    assert statusline_policy == get_hook_payload_policy("claude-code")


def test_resolve_hook_surface_runtime_prefers_nested_local_install_when_runtime_hint_is_missing(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()

    from tests.hooks.helpers import mark_complete_install as _mark_complete_install

    _mark_complete_install(nested / ".claude", runtime="claude-code")

    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
    ):
        runtime = resolve_hook_surface_runtime(
            hook_file=nested / ".claude" / "hooks" / "notify.py",
            cwd=nested,
            surface="notify",
        )

    assert runtime == "claude-code"


def test_resolve_hook_surface_runtime_falls_back_to_installed_preferred_runtime_when_active_runtime_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    workspace.mkdir()
    home.mkdir()
    hook_file = workspace / ".codex" / "hooks" / "notify.py"

    with (
        patch("gpd.hooks.payload_policy.hook_layout.detect_self_owned_install", return_value=None),
        patch(
            "gpd.hooks.payload_policy.hook_layout.resolve_hook_lookup_context",
            return_value=HookLookupContext(
                lookup_cwd=workspace,
                resolved_home=home,
                active_runtime=None,
                preferred_runtime="claude-code",
            ),
        ),
        patch(
            "gpd.hooks.payload_policy.detect_runtime_install_target",
            return_value=SimpleNamespace(config_dir=home / ".claude", install_scope="global"),
        ),
    ):
        runtime = resolve_hook_surface_runtime(hook_file=hook_file, cwd=workspace, surface="notify")

    assert runtime == "claude-code"


def test_merged_hook_payload_policy_stays_surface_specific() -> None:
    codex_policy = get_hook_payload_policy("codex")
    claude_policy = get_hook_payload_policy("claude-code")

    assert codex_policy.notify_event_types == ("agent-turn-complete",)
    assert codex_policy.runtime_session_id_keys == ()
    assert codex_policy.agent_id_keys == ()
    assert codex_policy.agent_name_keys == ()
    assert codex_policy.agent_scope_keys == ()
    assert codex_policy.model_keys == ("display_name", "name", "id")
    assert codex_policy.provider_keys == ("provider", "vendor")
    assert codex_policy.usage_keys == ("usage", "token_usage", "tokens")
    assert codex_policy.input_tokens_keys == ("input_tokens", "prompt_tokens", "inputTokens", "promptTokens")
    assert codex_policy.output_tokens_keys == (
        "output_tokens",
        "completion_tokens",
        "outputTokens",
        "completionTokens",
    )
    assert codex_policy.total_tokens_keys == ("total_tokens", "totalTokens")
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

    assert claude_policy.notify_event_types == ()
    assert claude_policy.runtime_session_id_keys == ()
    assert claude_policy.agent_id_keys == ()
    assert claude_policy.agent_name_keys == ()
    assert claude_policy.agent_scope_keys == ()
    assert claude_policy.context_window_size_keys == ("context_window_size",)
    assert claude_policy.context_remaining_keys == ("remaining_percentage", "remainingPercent", "remaining")
