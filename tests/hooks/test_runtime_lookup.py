"""Tests for shared runtime-lookup helper behavior."""

from __future__ import annotations

from pathlib import Path

from gpd.hooks.install_context import resolve_hook_lookup_context
from gpd.hooks.payload_roots import PayloadRoots
from gpd.hooks.runtime_lookup import (
    normalize_runtime_hint,
    resolve_runtime_lookup_active_runtime,
    resolve_runtime_lookup_context,
    resolve_runtime_lookup_context_from_payload_roots,
    resolve_runtime_lookup_dir,
)
from tests.hooks.helpers import mark_complete_install as _mark_complete_install


def test_resolve_runtime_lookup_dir_prefers_same_runtime_nested_install_for_explicit_project_dir(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    workspace = project_root / "src" / "analysis"
    workspace.mkdir(parents=True)

    _mark_complete_install(workspace / ".codex", runtime="codex")

    resolved = resolve_runtime_lookup_dir(
        workspace_dir=str(workspace),
        project_root=str(project_root),
        explicit_project_dir=True,
        active_runtime="codex",
    )

    assert resolved == str(workspace)


def test_resolve_runtime_lookup_dir_ignores_untrusted_project_dir_hint(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    workspace = project_root / "src" / "analysis"
    workspace.mkdir(parents=True)

    _mark_complete_install(project_root / ".claude", runtime="claude-code")
    _mark_complete_install(workspace / ".codex", runtime="codex")

    resolved = resolve_runtime_lookup_dir(
        workspace_dir=str(workspace),
        project_root=str(project_root),
        explicit_project_dir=True,
        project_dir_trusted=False,
        active_runtime="claude-code",
    )

    assert resolved == str(workspace)


def test_resolve_runtime_lookup_dir_uses_workspace_for_trusted_project_dir_when_active_runtime_is_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    workspace = project_root / "src" / "analysis"
    workspace.mkdir(parents=True)

    _mark_complete_install(workspace / ".codex", runtime="codex")

    resolved = resolve_runtime_lookup_dir(
        workspace_dir=str(workspace),
        project_root=str(project_root),
        explicit_project_dir=True,
        active_runtime=None,
    )

    assert resolved == str(workspace)


def test_resolve_runtime_lookup_dir_prefers_trusted_project_root_over_nested_foreign_install_when_runtime_is_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    workspace = project_root / "src" / "analysis"
    workspace.mkdir(parents=True)

    _mark_complete_install(project_root / ".claude", runtime="claude-code")
    _mark_complete_install(workspace / ".codex", runtime="codex")

    resolved = resolve_runtime_lookup_dir(
        workspace_dir=str(workspace),
        project_root=str(project_root),
        explicit_project_dir=True,
        active_runtime=None,
    )

    assert resolved == str(project_root)


def test_resolve_runtime_lookup_dir_falls_back_to_project_root_for_trusted_project_dir_without_workspace_install(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    workspace = project_root / "src" / "analysis"
    workspace.mkdir(parents=True)

    _mark_complete_install(project_root / ".codex", runtime="codex")

    resolved = resolve_runtime_lookup_dir(
        workspace_dir=str(workspace),
        project_root=str(project_root),
        explicit_project_dir=True,
        active_runtime=None,
    )

    assert resolved == str(project_root)


def test_resolve_runtime_lookup_dir_keeps_trusted_project_root_when_nested_other_runtime_exists(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    workspace = project_root / "src" / "analysis"
    workspace.mkdir(parents=True)

    _mark_complete_install(workspace / ".codex", runtime="codex")

    resolved = resolve_runtime_lookup_dir(
        workspace_dir=str(workspace),
        project_root=str(project_root),
        explicit_project_dir=True,
        project_dir_trusted=True,
        active_runtime="claude-code",
    )

    assert resolved == str(project_root)


def test_resolve_runtime_lookup_active_runtime_prefers_project_runtime_for_explicit_project_dir() -> None:
    calls: list[str | None] = []

    def _runtime_resolver(cwd: str | None) -> str | None:
        calls.append(cwd)
        if cwd == "/tmp/project":
            return "codex"
        if cwd == "/tmp/project/src/analysis":
            return "claude-code"
        return None

    resolved = resolve_runtime_lookup_active_runtime(
        workspace_dir="/tmp/project/src/analysis",
        project_root="/tmp/project",
        explicit_project_dir=True,
        runtime_resolver=_runtime_resolver,
    )

    assert resolved == "codex"
    assert calls == ["/tmp/project"]


def test_resolve_runtime_lookup_active_runtime_ignores_unknown_project_runtime_and_falls_back() -> None:
    calls: list[str | None] = []

    def _runtime_resolver(cwd: str | None) -> str | None:
        calls.append(cwd)
        if cwd == "/tmp/project":
            return "unknown"
        if cwd == "/tmp/project/src/analysis":
            return "codex"
        return None

    resolved = resolve_runtime_lookup_active_runtime(
        workspace_dir="/tmp/project/src/analysis",
        project_root="/tmp/project",
        explicit_project_dir=True,
        runtime_resolver=_runtime_resolver,
    )

    assert resolved == "codex"
    assert calls == ["/tmp/project", "/tmp/project/src/analysis"]


def test_resolve_runtime_lookup_active_runtime_uses_workspace_when_project_dir_is_not_explicit() -> None:
    calls: list[str | None] = []

    def _runtime_resolver(cwd: str | None) -> str | None:
        calls.append(cwd)
        if cwd == "/tmp/project":
            return "codex"
        if cwd == "/tmp/project/src/analysis":
            return "claude-code"
        return None

    resolved = resolve_runtime_lookup_active_runtime(
        workspace_dir="/tmp/project/src/analysis",
        project_root="/tmp/project",
        explicit_project_dir=False,
        runtime_resolver=_runtime_resolver,
    )

    assert resolved == "claude-code"
    assert calls == ["/tmp/project/src/analysis"]


def test_normalize_runtime_hint_handles_alias_unknown_and_blank_values() -> None:
    assert normalize_runtime_hint("claude") == "claude-code"
    assert normalize_runtime_hint("  claude  ") == "claude-code"
    assert normalize_runtime_hint("unknown") is None
    assert normalize_runtime_hint("   ") is None


def test_resolve_runtime_lookup_context_falls_back_to_workspace_runtime_when_project_runtime_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    workspace = project_root / "src" / "analysis"
    workspace.mkdir(parents=True)

    _mark_complete_install(workspace / ".codex", runtime="codex")

    calls: list[str | None] = []

    def _runtime_resolver(cwd: str | None) -> str | None:
        calls.append(cwd)
        if cwd == str(project_root):
            return None
        if cwd == str(workspace):
            return "codex"
        return None

    resolved = resolve_runtime_lookup_context(
        workspace_dir=str(workspace),
        project_root=str(project_root),
        explicit_project_dir=True,
        runtime_resolver=_runtime_resolver,
    )

    assert resolved.active_runtime == "codex"
    assert resolved.lookup_dir == str(workspace)
    assert calls == [str(project_root), str(workspace)]


def test_resolve_runtime_lookup_context_from_payload_roots_preserves_optional_target_metadata() -> None:
    normalized_project = str(Path("/tmp/project").resolve(strict=False))
    normalized_workspace = str(Path("/tmp/project/src/analysis").resolve(strict=False))
    normalized_target_path = str(Path("/tmp/project/paper/draft.tex").resolve(strict=False))
    normalized_target_root = str(Path("/tmp/project/paper").resolve(strict=False))
    roots = PayloadRoots(
        workspace_dir=normalized_workspace,
        project_root=normalized_project,
        project_dir_present=True,
        project_dir_trusted=True,
        target_path=normalized_target_path,
        target_root=normalized_target_root,
    )

    resolved = resolve_runtime_lookup_context_from_payload_roots(
        roots,
        runtime_resolver=lambda cwd: "codex" if cwd == normalized_project else None,
    )

    assert resolved.active_runtime == "codex"
    assert resolved.lookup_dir == normalized_project
    assert resolved.target_path == normalized_target_path
    assert resolved.target_root == normalized_target_root


def test_resolve_hook_lookup_context_uses_shared_runtime_hint_normalizer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    calls: list[str | None] = []

    def _normalize(runtime: str | None) -> str | None:
        calls.append(runtime)
        if runtime is None:
            return None
        runtime = runtime.strip()
        if runtime == "active":
            return "claude-code"
        if runtime == "preferred":
            return "codex"
        return None

    monkeypatch.setattr("gpd.hooks.install_context.normalize_runtime_hint", _normalize)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda **_: None)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_active_runtime", lambda **_: None)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", lambda **_: None)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_local_runtime_with_gpd_install", lambda **_: None)

    resolved = resolve_hook_lookup_context(
        cwd=None,
        home=home,
        active_installed_runtime=" active ",
        preferred_runtime=" preferred ",
    )

    assert " active " in calls
    assert " preferred " in calls
    assert resolved.active_runtime is None
    assert resolved.preferred_runtime == "codex"


def test_resolve_hook_lookup_context_normalizes_unknown_and_alias_runtime_hints(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    workspace.mkdir()
    home.mkdir()

    _mark_complete_install(workspace / ".claude", runtime="claude-code")

    resolved = resolve_hook_lookup_context(
        cwd=workspace,
        home=home,
        active_installed_runtime="unknown",
        preferred_runtime="claude",
    )

    assert resolved.lookup_cwd == workspace
    assert resolved.active_runtime == "claude-code"
    assert resolved.preferred_runtime == "claude-code"


def test_resolve_hook_lookup_context_revalidates_stale_active_installed_runtime_hint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    workspace.mkdir()
    home.mkdir()

    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda **_: "claude-code")
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", lambda **_: "claude-code")
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_local_runtime_with_gpd_install", lambda **_: None)

    resolved = resolve_hook_lookup_context(
        cwd=workspace,
        home=home,
        active_installed_runtime="codex",
        preferred_runtime="claude",
    )

    assert resolved.active_runtime == "claude-code"
    assert resolved.preferred_runtime == "claude-code"


def test_resolve_hook_lookup_context_ignores_invalid_preferred_runtime_hint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    workspace.mkdir()
    home.mkdir()

    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_active_runtime", lambda **_: None)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", lambda **_: None)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_local_runtime_with_gpd_install", lambda **_: None)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda **_: "codex")

    resolved = resolve_hook_lookup_context(
        cwd=workspace,
        home=home,
        preferred_runtime="not-a-runtime",
    )

    assert resolved.lookup_cwd == workspace
    assert resolved.active_runtime is None
    assert resolved.preferred_runtime == "codex"
