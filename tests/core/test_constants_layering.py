"""Ensure the Layer 1 constants module only imports stdlib."""

from __future__ import annotations

import ast
from pathlib import Path


def test_constants_layer1_imports_only_stdlib() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    constants_src = repo_root / "src" / "gpd" / "core" / "constants.py"
    tree = ast.parse(constants_src.read_text(encoding="utf-8"))

    offending_modules: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            offending_modules.extend(alias.name for alias in node.names if alias.name.startswith("gpd"))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            module = node.module
            if module == "gpd" or module.startswith("gpd."):
                offending_modules.append(module)

    assert not offending_modules, f"Layer 1 constants must stay stdlib-only (found imports {offending_modules})"
