"""Ensure README runtime mentions stay aligned with the catalog."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.json"
DOC_PATHS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "docs" / "linux.md",
    REPO_ROOT / "docs" / "macos.md",
    REPO_ROOT / "docs" / "windows.md",
]


def _format_runtime_list(display_names: list[str]) -> str:
    if not display_names:
        return ""
    if len(display_names) == 1:
        return display_names[0]
    if len(display_names) == 2:
        return f"{display_names[0]} or {display_names[1]}"
    return f"{', '.join(display_names[:-1])}, or {display_names[-1]}"


def test_runtime_mentions_align_with_catalog() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    ordered = sorted(catalog, key=lambda entry: entry.get("priority", 0))
    display_names = [entry.get("display_name") or entry["runtime_name"] for entry in ordered]
    expected_runtime_list = _format_runtime_list(display_names)
    for path in DOC_PATHS:
        content = path.read_text(encoding="utf-8")
        if "Claude Code" in content and "OpenCode" in content:
            assert expected_runtime_list in content
