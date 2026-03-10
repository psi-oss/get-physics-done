"""Regression tests for the checked-in Claude snapshot.

The repository keeps a materialized local-install snapshot under ``.claude/``.
These tests ensure the managed snapshot stays in sync with what the Claude
adapter currently installs for a local workspace target.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters.claude_code import ClaudeCodeAdapter

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_GPD_ROOT = REPO_ROOT / "src" / "gpd"
CLAUDE_SNAPSHOT = REPO_ROOT / ".claude"
pytestmark = pytest.mark.skipif(not CLAUDE_SNAPSHOT.exists(), reason="local .claude snapshot not materialized")


def _collect_tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(p for p in root.rglob("*") if p.is_file())
    }


def _collect_agent_bytes(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(root.glob("gpd-*.md"))}


@pytest.fixture()
def generated_local_snapshot(tmp_path: Path) -> Path:
    target = tmp_path / ".claude"
    target.mkdir()
    ClaudeCodeAdapter().install(SOURCE_GPD_ROOT, target, is_global=False)
    return target


def test_checked_in_claude_snapshot_matches_local_install(generated_local_snapshot: Path) -> None:
    assert _collect_tree_bytes(generated_local_snapshot / "commands" / "gpd") == _collect_tree_bytes(
        CLAUDE_SNAPSHOT / "commands" / "gpd"
    )
    assert _collect_agent_bytes(generated_local_snapshot / "agents") == _collect_agent_bytes(CLAUDE_SNAPSHOT / "agents")
    assert _collect_tree_bytes(generated_local_snapshot / "get-physics-done") == _collect_tree_bytes(
        CLAUDE_SNAPSHOT / "get-physics-done"
    )


def test_checked_in_claude_manifest_matches_local_install(generated_local_snapshot: Path) -> None:
    expected = json.loads((generated_local_snapshot / "gpd-file-manifest.json").read_text(encoding="utf-8"))
    actual = json.loads((CLAUDE_SNAPSHOT / "gpd-file-manifest.json").read_text(encoding="utf-8"))

    expected.pop("timestamp", None)
    actual.pop("timestamp", None)

    assert actual == expected
