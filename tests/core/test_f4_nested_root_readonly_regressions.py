"""Fixture-backed regressions for nested-root and read-only probe parity."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gpd.core.health import _peek_normalized_state_for_health
from gpd.core.root_resolution import resolve_project_root, resolve_project_roots
from gpd.mcp.servers.state_server import load_state_json as mcp_load_state_json

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(slug: str, variant: str, tmp_path: Path) -> Path:
    source = HANDOFF_BUNDLE_ROOT / slug / variant / "workspace"
    target = tmp_path / f"{slug}-{variant}"
    shutil.copytree(source, target)
    return target


def test_nested_empty_gpd_stub_does_not_capture_stronger_project_root(tmp_path: Path) -> None:
    workspace = _copy_fixture_workspace("empty-phase", "positive", tmp_path)
    nested = workspace / "src" / "notes"
    nested.mkdir(parents=True)
    (nested / "GPD").mkdir()

    resolution = resolve_project_roots(nested)

    assert resolution is not None
    assert resolution.project_root == workspace.resolve(strict=False)
    assert resolution.basis.value == "workspace"
    assert resolution.confidence.value == "high"
    assert resolution.has_project_layout is True
    assert resolution.walk_up_steps > 0
    assert resolve_project_root(nested, require_layout=True) == workspace.resolve(strict=False)


@pytest.mark.parametrize(
    "surface_name,surface",
    [
        ("health_peek", _peek_normalized_state_for_health),
        ("mcp_state_loader", mcp_load_state_json),
    ],
    ids=["health-peek", "mcp-state-loader"],
)
def test_read_only_nested_workspace_surfaces_agree_on_project_state_without_creating_a_nested_stub(
    surface_name: str,
    surface,
    tmp_path: Path,
) -> None:
    workspace = _copy_fixture_workspace("empty-phase", "positive", tmp_path)
    nested = workspace / "src" / "notes"
    nested.mkdir(parents=True)
    nested_gpd = nested / "GPD"
    assert not nested_gpd.exists()

    nested_result = surface(nested)
    root_result = surface(workspace)

    assert not nested_gpd.exists(), surface_name

    if surface_name == "health_peek":
        assert nested_result[0] == root_result[0]
        assert nested_result[1] == root_result[1]
    else:
        assert nested_result == root_result
