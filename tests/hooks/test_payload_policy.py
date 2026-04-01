from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


def test_hook_payload_policy_wrappers_delegate_with_surface_specific_arguments(tmp_path: Path) -> None:
    from gpd.hooks import notify, statusline

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    hook_dir = tmp_path / ".codex" / "hooks"
    notify_hook = hook_dir / "notify.py"
    statusline_hook = hook_dir / "statusline.py"
    hook_dir.mkdir(parents=True)
    notify_hook.write_text("# notify hook\n", encoding="utf-8")
    statusline_hook.write_text("# statusline hook\n", encoding="utf-8")

    notify_policy = object()
    statusline_policy = object()
    with (
        patch("gpd.hooks.notify.__file__", str(notify_hook)),
        patch("gpd.hooks.statusline.__file__", str(statusline_hook)),
        patch("gpd.hooks.notify.resolve_hook_payload_policy", return_value=notify_policy) as mock_notify_policy,
        patch(
            "gpd.hooks.statusline.resolve_hook_payload_policy",
            return_value=statusline_policy,
        ) as mock_statusline_policy,
    ):
        assert notify._hook_payload_policy(str(workspace)) is notify_policy
        assert statusline._hook_payload_policy(str(workspace)) is statusline_policy

    mock_notify_policy.assert_called_once_with(
        hook_file=str(notify_hook),
        cwd=str(workspace),
        surface="notify",
    )
    mock_statusline_policy.assert_called_once_with(
        hook_file=str(statusline_hook),
        cwd=str(workspace),
        surface="statusline",
    )


def test_resolve_hook_surface_runtime_prefers_nested_workspace_local_install_over_ancestor_project_root(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    _ = project / ".claude"
    (nested / ".codex" / "hooks").mkdir(parents=True)

    from tests.hooks.helpers import mark_complete_install as _mark_complete_install

    _mark_complete_install(nested / ".codex", runtime="codex")

    with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
        runtime = resolve_hook_surface_runtime(
            hook_file=nested / ".codex" / "hooks" / "notify.py",
            cwd=nested,
            surface="notify",
        )

    assert runtime == "codex"


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


def test_resolve_hook_surface_runtime_falls_back_to_ancestor_project_root_install_when_nested_cwd_has_none(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()

    from tests.hooks.helpers import mark_complete_install as _mark_complete_install

    _mark_complete_install(project / ".claude", runtime="claude-code")

    with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
        runtime = resolve_hook_surface_runtime(
            hook_file=tmp_path / "hooks" / "notify.py",
            cwd=nested,
            surface="notify",
        )

    assert runtime == "claude-code"


def test_resolve_hook_surface_runtime_does_not_let_nested_other_runtime_hijack_active_runtime_lookup(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()

    from tests.hooks.helpers import mark_complete_install as _mark_complete_install

    _mark_complete_install(project / ".claude", runtime="claude-code")
    _mark_complete_install(nested / ".codex", runtime="codex")

    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="claude-code"),
    ):
        runtime = resolve_hook_surface_runtime(
            hook_file=tmp_path / "hooks" / "notify.py",
            cwd=nested,
            surface="notify",
        )

    assert runtime == "claude-code"
