"""Ensure only the adapter catalog normalizes runtime names."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def test_runtime_normalization_imports_use_adapter_catalog_only() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    allowed_runtime_detect = (repo_root / "src" / "gpd" / "hooks" / "runtime_detect.py").resolve()
    search_roots = [
        repo_root / "src",
        repo_root / "scripts",
        repo_root / "bin",
    ]
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in {".venv", ".git", "__pycache__"} for part in path.parts):
                continue
            if path.resolve() == allowed_runtime_detect:
                continue
            content = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "gpd.hooks.runtime_detect"
                    and any(alias.name == "normalize_runtime_name" for alias in node.names)
                ):
                    pytest.fail(
                        f"{path.relative_to(repo_root)} must not import normalize_runtime_name"
                        " from gpd.hooks.runtime_detect"
                    )
