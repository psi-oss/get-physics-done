"""Tests for shared hook payload root resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from gpd.hooks.payload_roots import (
    normalize_workspace_text,
    project_root_from_payload,
    resolve_payload_roots,
    workspace_dir_from_payload,
)


def _policy(
    *,
    workspace_keys: tuple[str, ...] = ("cwd",),
    project_dir_keys: tuple[str, ...] = ("project_dir",),
    root_resolution_service=None,
):
    return SimpleNamespace(
        workspace_keys=workspace_keys,
        project_dir_keys=project_dir_keys,
        root_resolution_service=root_resolution_service,
    )


def test_normalize_workspace_text_resolves_explicit_path(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = workspace / ".." / "workspace"

    result = normalize_workspace_text(str(path))

    assert result == str(workspace.resolve(strict=False))


def test_normalize_workspace_text_falls_back_to_process_cwd_when_empty(tmp_path) -> None:
    with patch("gpd.hooks.payload_roots.Path.cwd", return_value=tmp_path):
        result = normalize_workspace_text("")

    assert result == str(tmp_path.resolve(strict=False))


def test_workspace_dir_from_payload_prefers_top_level_workspace_string(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    other = tmp_path / "other"
    workspace.mkdir()
    other.mkdir()

    result = workspace_dir_from_payload(
        {"workspace": str(workspace), "payload_workspace": str(other)},
        policy_getter=lambda _cwd: _policy(workspace_keys=("payload_workspace",)),
    )

    assert result == str(workspace.resolve(strict=False))


def test_workspace_dir_from_payload_uses_mapping_and_top_level_policy_aliases(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    mapping_payload = {"workspace": {"current_dir": str(workspace)}}

    mapping_result = workspace_dir_from_payload(
        mapping_payload,
        policy_getter=lambda _cwd: _policy(workspace_keys=("current_dir",)),
    )

    top_level_result = workspace_dir_from_payload(
        {"payload_workspace": str(workspace)},
        policy_getter=lambda _cwd: _policy(workspace_keys=("payload_workspace",)),
    )

    expected = str(workspace.resolve(strict=False))
    assert mapping_result == expected
    assert top_level_result == expected


def test_workspace_dir_from_payload_uses_cwd_as_policy_context(tmp_path) -> None:
    process_cwd = tmp_path / "process-cwd"
    workspace = tmp_path / "workspace"
    process_cwd.mkdir()
    workspace.mkdir()
    policy_getter = Mock(return_value=_policy(workspace_keys=("payload_workspace",)))

    result = workspace_dir_from_payload(
        {"payload_workspace": str(workspace)},
        policy_getter=policy_getter,
        cwd=str(process_cwd),
    )

    policy_getter.assert_called_once_with(str(process_cwd))
    assert result == str(workspace.resolve(strict=False))


def test_workspace_dir_from_payload_falls_back_to_cwd_then_os_getcwd(tmp_path) -> None:
    cwd = tmp_path / "cwd"
    os_cwd = tmp_path / "os-cwd"
    cwd.mkdir()
    os_cwd.mkdir()

    from_cwd = workspace_dir_from_payload({}, policy_getter=lambda _cwd: _policy(), cwd=str(cwd))
    with patch("gpd.hooks.payload_roots.os.getcwd", return_value=str(os_cwd)):
        from_os_getcwd = workspace_dir_from_payload({}, policy_getter=lambda _cwd: _policy())

    assert from_cwd == str(cwd.resolve(strict=False))
    assert from_os_getcwd == str(os_cwd.resolve(strict=False))


def test_project_root_from_payload_prefers_explicit_project_dir_alias(tmp_path) -> None:
    workspace = tmp_path / "project" / "src" / "notes"
    project = tmp_path / "project"
    workspace.mkdir(parents=True)

    result = project_root_from_payload(
        {"workspace": {"current_dir": str(workspace), "project_root": str(project)}},
        str(workspace),
        policy_getter=lambda _cwd: _policy(workspace_keys=("current_dir",), project_dir_keys=("project_root",)),
    )

    assert result == str(project.resolve(strict=False))


def test_project_root_from_payload_falls_back_to_workspace_when_resolution_fails(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with patch("gpd.hooks.payload_roots.resolve_project_root", return_value=None):
        result = project_root_from_payload(
            {"project_dir": str(tmp_path / "missing")},
            str(workspace),
            policy_getter=lambda _cwd: _policy(project_dir_keys=("project_dir",)),
        )

    assert result == str(workspace.resolve(strict=False))


def test_project_root_from_payload_uses_workspace_dir_as_policy_context_when_cwd_missing(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()
    policy_getter = Mock(return_value=_policy(project_dir_keys=("project_root",)))

    result = project_root_from_payload(
        {"project_root": str(project)},
        str(workspace),
        policy_getter=policy_getter,
    )

    policy_getter.assert_called_once_with(str(workspace))
    assert result == str(project.resolve(strict=False))


def test_resolve_payload_roots_preserves_raw_workspace_and_resolved_project_root(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(project)}},
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.workspace_dir != roots.project_root


def test_project_root_from_payload_prefers_policy_root_resolution_service(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    project.mkdir(parents=True)
    workspace.mkdir(parents=True, exist_ok=True)
    service = Mock(
        return_value={
            "workspace_dir": str(workspace),
            "project_root": str(project),
        }
    )

    result = project_root_from_payload(
        {"workspace": {"cwd": str(workspace), "project_dir": str(project)}},
        str(workspace),
        policy_getter=lambda _cwd: _policy(
            workspace_keys=("cwd",),
            project_dir_keys=("project_dir",),
            root_resolution_service=service,
        ),
    )

    service.assert_called_once()
    assert result == str(project.resolve(strict=False))


def test_resolve_payload_roots_accepts_compatibility_aliases_from_shared_service(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    service = Mock(
        return_value=SimpleNamespace(
            raw_workspace_dir=str(workspace),
            resolved_project_root=str(project),
        )
    )

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(project)}},
        policy_getter=lambda _cwd: _policy(
            workspace_keys=("cwd",),
            project_dir_keys=("project_dir",),
            root_resolution_service=service,
        ),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.raw_workspace_dir == roots.workspace_dir
    assert roots.resolved_project_root == roots.project_root


def test_resolve_payload_roots_keeps_raw_workspace_when_service_only_returns_project_root(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    service = Mock(return_value=str(project))

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(project)}},
        policy_getter=lambda _cwd: _policy(
            workspace_keys=("cwd",),
            project_dir_keys=("project_dir",),
            root_resolution_service=service,
        ),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.workspace_dir != roots.project_root
