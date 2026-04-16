"""Proxy-grade contract test for nested-root/read-only probe parity."""

from __future__ import annotations

import shutil
from pathlib import Path

import gpd.cli as cli_module
from gpd.core.health import _peek_normalized_state_for_health
from gpd.core.root_resolution import resolve_project_root, resolve_project_roots
from gpd.hooks.statusline import _statusline_project_root
from gpd.mcp.servers.state_server import load_state_json as mcp_load_state_json

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(tmp_path: Path) -> Path:
    source = HANDOFF_BUNDLE_ROOT / "empty-phase" / "positive" / "workspace"
    target = tmp_path / "empty-phase-positive"
    shutil.copytree(source, target)
    return target


def _make_nested_stub(workspace: Path) -> Path:
    nested = workspace / "src" / "notes"
    nested.mkdir(parents=True)
    (nested / "GPD").mkdir()
    return nested


def test_bug_nested_root_readonly_probe_parity_contract(tmp_path: Path) -> None:
    workspace = _copy_fixture_workspace(tmp_path)
    nested = _make_nested_stub(workspace)

    workspace_root = workspace.resolve(strict=False)
    nested_gpd = nested / "GPD"

    resolution = resolve_project_roots(nested)
    assert resolution is not None
    assert resolution.project_root == workspace_root
    assert resolution.basis.value == "workspace"
    assert resolution.confidence.value == "high"
    assert resolution.has_project_layout is True
    assert resolution.walk_up_steps > 0
    assert resolve_project_root(nested, require_layout=True) == workspace_root

    cli_root = cli_module._project_scoped_cwd(nested)
    statusline_root = _statusline_project_root(nested.as_posix())
    health_nested = _peek_normalized_state_for_health(nested)
    health_workspace = _peek_normalized_state_for_health(workspace)
    mcp_nested = mcp_load_state_json(nested)
    mcp_workspace = mcp_load_state_json(workspace)

    assert cli_root == workspace_root
    assert statusline_root == workspace_root
    assert health_nested == health_workspace
    assert mcp_nested == mcp_workspace

    assert nested_gpd.is_dir()
    assert list(nested_gpd.iterdir()) == []
