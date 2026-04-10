"""Tests for the shared project-root resolution service."""

from __future__ import annotations

from pathlib import Path

from gpd.core.root_resolution import (
    RootResolutionBasis,
    RootResolutionConfidence,
    normalize_workspace_hint,
    resolve_project_root,
    resolve_project_roots,
)


def _make_project_root(project: Path) -> None:
    gpd_dir = project / "GPD"
    gpd_dir.mkdir(parents=True)
    (gpd_dir / "state.json").write_text("{}", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text("# State\n", encoding="utf-8")
    (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (gpd_dir / "phases").mkdir()


def test_normalize_workspace_hint_resolves_explicit_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = workspace / ".." / "workspace"

    result = normalize_workspace_hint(str(path))

    assert result == workspace.resolve(strict=False)


def test_normalize_workspace_hint_returns_none_for_empty_text() -> None:
    assert normalize_workspace_hint("") is None
    assert normalize_workspace_hint("   ") is None


def test_resolve_project_roots_uses_verified_explicit_project_dir_walkup(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested_hint = project / "src" / "notes"
    other_workspace = tmp_path / "workspace"
    (project / "GPD").mkdir(parents=True)
    nested_hint.mkdir(parents=True)
    other_workspace.mkdir()

    resolution = resolve_project_roots(other_workspace, project_dir=nested_hint)

    assert resolution is not None
    assert resolution.workspace_root == other_workspace.resolve(strict=False)
    assert resolution.project_hint == nested_hint.resolve(strict=False)
    assert resolution.project_root == project.resolve(strict=False)
    assert resolution.basis == RootResolutionBasis.PROJECT_DIR
    assert resolution.confidence == RootResolutionConfidence.HIGH
    assert resolution.has_project_layout is True
    assert resolution.verified is True
    assert resolution.walk_up_steps == 2


def test_resolve_project_roots_prefers_verified_workspace_over_unverified_explicit_project_hint(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workspace = project / "src" / "notes"
    missing_project_dir = tmp_path / "not-a-project"
    _make_project_root(project)
    workspace.mkdir(parents=True)

    resolution = resolve_project_roots(workspace, project_dir=missing_project_dir)

    assert resolution is not None
    assert resolution.project_root == project.resolve(strict=False)
    assert resolution.basis == RootResolutionBasis.WORKSPACE
    assert resolution.confidence == RootResolutionConfidence.HIGH
    assert resolution.has_project_layout is True
    assert resolution.walk_up_steps == 2


def test_resolve_project_roots_falls_back_to_explicit_project_dir_when_nothing_is_verified(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project_hint = tmp_path / "maybe-project"
    workspace.mkdir()
    project_hint.mkdir()

    resolution = resolve_project_roots(workspace, project_dir=project_hint)

    assert resolution is not None
    assert resolution.project_root == project_hint.resolve(strict=False)
    assert resolution.basis == RootResolutionBasis.PROJECT_DIR
    assert resolution.confidence == RootResolutionConfidence.MEDIUM
    assert resolution.has_project_layout is False
    assert resolution.walk_up_steps == 0


def test_resolve_project_roots_falls_back_to_workspace_when_only_workspace_hint_exists(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    resolution = resolve_project_roots(workspace)

    assert resolution is not None
    assert resolution.project_root == workspace.resolve(strict=False)
    assert resolution.workspace_root == workspace.resolve(strict=False)
    assert resolution.project_hint is None
    assert resolution.basis == RootResolutionBasis.WORKSPACE
    assert resolution.confidence == RootResolutionConfidence.LOW
    assert resolution.has_project_layout is False
    assert resolution.walk_up_steps == 0


def test_resolve_project_roots_ignores_a_file_named_gpd(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workspace = project / "workspace"
    workspace.mkdir(parents=True)
    (project / "GPD").write_text("not a layout directory", encoding="utf-8")

    resolution = resolve_project_roots(workspace)

    assert resolution is not None
    assert resolution.project_root == workspace.resolve(strict=False)
    assert resolution.basis == RootResolutionBasis.WORKSPACE
    assert resolution.confidence == RootResolutionConfidence.LOW
    assert resolution.has_project_layout is False
    assert resolution.walk_up_steps == 0
    assert resolve_project_root(workspace, require_layout=True) is None


def test_resolve_project_roots_prefers_stronger_ancestor_over_nested_empty_gpd_stub(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    workspace = project / "workspace" / "notes"
    nested_stub = workspace / "GPD"
    _make_project_root(project)
    nested_stub.mkdir(parents=True)
    workspace.mkdir(parents=True, exist_ok=True)

    resolution = resolve_project_roots(workspace)

    assert resolution is not None
    assert resolution.project_root == project.resolve(strict=False)
    assert resolution.basis == RootResolutionBasis.WORKSPACE
    assert resolution.confidence == RootResolutionConfidence.HIGH
    assert resolution.has_project_layout is True
    assert resolution.walk_up_steps == 2


def test_resolve_project_roots_falls_back_to_nearest_bare_gpd_when_no_stronger_ancestor_exists(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "GPD").mkdir(parents=True)

    resolution = resolve_project_roots(workspace)

    assert resolution is not None
    assert resolution.project_root == workspace.resolve(strict=False)
    assert resolution.basis == RootResolutionBasis.WORKSPACE
    assert resolution.confidence == RootResolutionConfidence.HIGH
    assert resolution.has_project_layout is True
    assert resolution.walk_up_steps == 0


def test_resolve_project_root_require_layout_rejects_unverified_fallback(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert resolve_project_root(workspace, require_layout=True) is None
    assert resolve_project_root(workspace) == workspace.resolve(strict=False)


def test_resolve_project_root_returns_none_without_hints() -> None:
    assert resolve_project_roots() is None
    assert resolve_project_root() is None
