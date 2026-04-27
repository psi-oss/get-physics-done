"""Tests for shared hook payload root resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from gpd.hooks.payload_roots import (
    _coerce_root_pair,
    _resolve_with_shared_service,
    normalize_workspace_text,
    payload_uses_alias_only_workspace_mapping,
    project_root_from_payload,
    resolve_payload_roots,
    workspace_dir_from_payload,
)


def _policy(
    *,
    workspace_keys: tuple[str, ...] = ("cwd",),
    project_dir_keys: tuple[str, ...] = ("project_dir",),
    target_path_keys: tuple[str, ...] = ("target_path",),
    target_root_keys: tuple[str, ...] = ("target_root",),
    root_resolution_service=None,
):
    return SimpleNamespace(
        workspace_keys=workspace_keys,
        project_dir_keys=project_dir_keys,
        target_path_keys=target_path_keys,
        target_root_keys=target_root_keys,
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


def test_payload_uses_alias_only_workspace_mapping_detects_alias_only_mapping(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()

    assert payload_uses_alias_only_workspace_mapping(
        {
            "workspace": {"current_dir": str(workspace)},
            "project_root": str(project),
        },
        hook_payload=_policy(workspace_keys=("workspace", "current_dir"), project_dir_keys=("project_root",)),
    )


def test_payload_uses_alias_only_workspace_mapping_detects_top_level_alias_only_mapping(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()

    assert payload_uses_alias_only_workspace_mapping(
        {
            "current_dir": str(workspace),
            "project_root": str(project),
        },
        hook_payload=_policy(workspace_keys=("cwd", "current_dir"), project_dir_keys=("project_dir", "project_root")),
    )


def test_payload_uses_alias_only_workspace_mapping_is_insensitive_to_workspace_key_order(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()

    assert payload_uses_alias_only_workspace_mapping(
        {
            "workspace": {"current_dir": str(workspace)},
            "project_root": str(project),
        },
        hook_payload=_policy(workspace_keys=("current_dir", "cwd"), project_dir_keys=("project_root",)),
    )


def test_coerce_root_pair_accepts_tuple_and_list_payloads(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"

    tuple_roots = _coerce_root_pair((str(workspace), str(project)), fallback_workspace_dir=str(tmp_path / "fallback"))
    list_roots = _coerce_root_pair([str(workspace), str(project)], fallback_workspace_dir=str(tmp_path / "fallback"))

    assert tuple_roots is not None
    assert list_roots is not None
    assert tuple_roots.workspace_dir == str(workspace.resolve(strict=False))
    assert tuple_roots.project_root == str(project.resolve(strict=False))
    assert tuple_roots.project_dir_present is False
    assert tuple_roots.project_dir_trusted is False
    assert tuple_roots.target_path is None
    assert tuple_roots.target_root is None
    assert list_roots.workspace_dir == tuple_roots.workspace_dir
    assert list_roots.project_root == tuple_roots.project_root


def test_coerce_root_pair_accepts_optional_target_metadata(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    target_path = workspace / "artifact.md"
    target_root = project / "paper"

    roots = _coerce_root_pair(
        (str(workspace), str(project), str(target_path), str(target_root)),
        fallback_workspace_dir=str(tmp_path / "fallback"),
    )

    assert roots is not None
    assert roots.target_path == str(target_path.resolve(strict=False))
    assert roots.target_root == str(target_root.resolve(strict=False))


def test_coerce_root_pair_preserves_trust_flags_from_mapping_payload(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"

    roots = _coerce_root_pair(
        {
            "workspace_dir": str(workspace),
            "project_root": str(project),
            "project_dir_present": True,
            "project_dir_trusted": False,
            "target_path": str(workspace / "artifact.md"),
            "target_root": str(project / "paper"),
        },
        fallback_workspace_dir=str(tmp_path / "fallback"),
    )

    assert roots is not None
    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is False
    assert roots.target_path == str((workspace / "artifact.md").resolve(strict=False))
    assert roots.target_root == str((project / "paper").resolve(strict=False))


def test_payload_roots_return_only_canonical_field_names(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"

    roots = _coerce_root_pair(
        {
            "workspace_dir": str(workspace),
            "project_root": str(project),
            "project_dir_present": True,
            "project_dir_trusted": True,
        },
        fallback_workspace_dir=str(tmp_path / "fallback"),
    )

    assert roots is not None
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is True
    assert roots.target_path is None
    assert roots.target_root is None
    for legacy_name in (
        "raw_workspace_dir",
        "resolved_project_root",
        "explicit_project_dir",
        "trusted_project_dir",
        "project_dir_is_authoritative",
        "project_dir_authoritative",
    ):
        assert not hasattr(roots, legacy_name)


def test_resolve_with_shared_service_uses_current_signature(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()

    service = Mock(return_value=(str(workspace), str(project)))

    roots = _resolve_with_shared_service(
        {"workspace": str(workspace)},
        workspace_dir=str(workspace),
        project_dir=str(project),
        target_path=str(workspace / "artifact.md"),
        target_root=str(project / "paper"),
        hook_payload=_policy(root_resolution_service=service),
        cwd=str(tmp_path),
    )

    assert roots is not None
    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    service.assert_called_once_with(
        payload={"workspace": str(workspace)},
        workspace_dir=str(workspace),
        project_dir=str(project),
        target_path=str(workspace / "artifact.md"),
        target_root=str(project / "paper"),
        cwd=str(tmp_path),
    )


def test_resolve_with_shared_service_supports_narrow_callback_signatures(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()
    seen_kwargs = {}

    def _service(*, workspace_dir, project_dir, cwd=None):
        seen_kwargs.update({"workspace_dir": workspace_dir, "project_dir": project_dir, "cwd": cwd})
        return (workspace_dir, project_dir)

    roots = _resolve_with_shared_service(
        {"workspace": str(workspace)},
        workspace_dir=str(workspace),
        project_dir=str(project),
        target_path=str(workspace / "artifact.md"),
        target_root=str(project / "paper"),
        hook_payload=_policy(root_resolution_service=_service),
        cwd=str(tmp_path),
    )

    assert roots is not None
    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert seen_kwargs == {
        "workspace_dir": str(workspace),
        "project_dir": str(project),
        "cwd": str(tmp_path),
    }


def test_resolve_with_shared_service_raises_non_signature_errors(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()

    def _service(**kwargs):
        if "payload" in kwargs or "data" in kwargs:
            raise ValueError("bad service state")
        raise TypeError("unsupported signature")

    with pytest.raises(RuntimeError, match="shared root resolution service failed"):
        _resolve_with_shared_service(
            {"workspace": str(workspace)},
            workspace_dir=str(workspace),
            project_dir=str(project),
            hook_payload=_policy(root_resolution_service=_service),
            cwd=str(tmp_path),
        )


def test_resolve_with_shared_service_does_not_mask_internal_type_error(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = tmp_path / "project"
    workspace.mkdir()
    project.mkdir()

    def _service(**_kwargs):
        raise TypeError("internal service bug")

    with pytest.raises(RuntimeError, match="shared root resolution service failed") as exc_info:
        _resolve_with_shared_service(
            {"workspace": str(workspace)},
            workspace_dir=str(workspace),
            project_dir=str(project),
            hook_payload=_policy(root_resolution_service=_service),
            cwd=str(tmp_path),
        )

    assert isinstance(exc_info.value.__cause__, TypeError)
    assert "internal service bug" in str(exc_info.value.__cause__)


def test_project_root_from_payload_prefers_explicit_project_dir_input(tmp_path) -> None:
    workspace = tmp_path / "project" / "src" / "notes"
    project = tmp_path / "project"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()

    result = project_root_from_payload(
        {"workspace": {"current_dir": str(workspace), "project_root": str(project)}},
        str(workspace),
        policy_getter=lambda _cwd: _policy(workspace_keys=("current_dir",), project_dir_keys=("project_root",)),
    )

    assert result == str(project.resolve(strict=False))


def test_project_root_from_payload_falls_back_to_workspace_when_resolution_fails(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with patch("gpd.hooks.payload_roots.resolve_project_roots", return_value=None):
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
    (project / "GPD").mkdir()
    policy_getter = Mock(return_value=_policy(project_dir_keys=("project_root",)))

    result = project_root_from_payload(
        {"project_root": str(project)},
        str(workspace),
        policy_getter=policy_getter,
    )

    policy_getter.assert_called_once_with(str(workspace))
    assert result == str(workspace.resolve(strict=False))


def test_resolve_payload_roots_returns_canonical_workspace_and_project_root(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    target_path = workspace / "paper" / "draft.tex"
    target_root = project / "paper"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()

    roots = resolve_payload_roots(
        {
            "workspace": {
                "cwd": str(workspace),
                "project_dir": str(project),
                "target_path": str(target_path),
                "target_root": str(target_root),
            }
        },
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.workspace_dir != roots.project_root
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is True
    assert roots.target_path == str(target_path.resolve(strict=False))
    assert roots.target_root == str(target_root.resolve(strict=False))


def test_resolve_payload_roots_marks_untrusted_project_dir_when_workspace_walkup_wins(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()
    (project / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(tmp_path / "stale-project-dir")}},
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is False


def test_resolve_payload_roots_trusts_explicit_project_dir_when_it_is_the_selected_verified_root_basis(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(project)}},
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is True


def test_resolve_payload_roots_does_not_trust_unverified_explicit_project_dir_even_when_selected(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(project)}},
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(workspace.resolve(strict=False))
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is False


def test_resolve_payload_roots_rejects_unrelated_verified_project_dir_hint(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()
    (project / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")

    unrelated = tmp_path / "other-project"
    unrelated.mkdir()
    (unrelated / "GPD").mkdir()
    (unrelated / "GPD" / "PROJECT.md").write_text("# Other\n", encoding="utf-8")

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(unrelated)}},
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(project.resolve(strict=False))
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is False


def test_resolve_payload_roots_does_not_capture_empty_ancestor_gpd_without_project_dir(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace)}},
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(workspace.resolve(strict=False))
    assert roots.project_dir_present is False
    assert roots.project_dir_trusted is False


def test_resolve_payload_roots_ignores_unrelated_verified_project_dir_when_workspace_is_not_a_project(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    unrelated = tmp_path / "other-project"
    unrelated.mkdir()
    (unrelated / "GPD").mkdir()

    roots = resolve_payload_roots(
        {"workspace": {"cwd": str(workspace), "project_dir": str(unrelated)}},
        policy_getter=lambda _cwd: _policy(workspace_keys=("cwd",), project_dir_keys=("project_dir",)),
    )

    assert roots.workspace_dir == str(workspace.resolve(strict=False))
    assert roots.project_root == str(workspace.resolve(strict=False))
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is False


def test_project_root_from_payload_prefers_policy_root_resolution_service(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    project.mkdir(parents=True)
    (project / "GPD").mkdir()
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


def test_resolve_payload_roots_accepts_canonical_fields_from_shared_service(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()
    service = Mock(
        return_value=SimpleNamespace(
            workspace_dir=str(workspace),
            project_root=str(project),
            target_path=str(workspace / "paper" / "draft.tex"),
            target_root=str(project / "paper"),
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
    assert roots.project_dir_present is True
    assert roots.project_dir_trusted is True
    assert roots.target_path == str((workspace / "paper" / "draft.tex").resolve(strict=False))
    assert roots.target_root == str((project / "paper").resolve(strict=False))


def test_resolve_payload_roots_keeps_raw_workspace_when_service_only_returns_project_root(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()
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


def test_resolve_payload_roots_preserves_payload_target_metadata_when_shared_service_omits_it(tmp_path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    target_path = workspace / "paper" / "draft.tex"
    target_root = project / "paper"
    workspace.mkdir(parents=True)
    (project / "GPD").mkdir()
    service = Mock(return_value={"workspace_dir": str(workspace), "project_root": str(project)})

    roots = resolve_payload_roots(
        {
            "workspace": {
                "cwd": str(workspace),
                "project_dir": str(project),
                "target_path": str(target_path),
                "target_root": str(target_root),
            }
        },
        policy_getter=lambda _cwd: _policy(
            workspace_keys=("cwd",),
            project_dir_keys=("project_dir",),
            root_resolution_service=service,
        ),
    )

    assert roots.target_path == str(target_path.resolve(strict=False))
    assert roots.target_root == str(target_root.resolve(strict=False))
