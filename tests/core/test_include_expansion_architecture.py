from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _imports(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_registry_uses_neutral_include_expansion_not_adapter_install_utils() -> None:
    imports = _imports(REPO_ROOT / "src/gpd/registry.py")

    assert "gpd.core.include_expansion" in imports
    assert "gpd.adapters.install_utils" not in imports


def test_neutral_include_expansion_stays_runtime_adapter_free() -> None:
    imports = _imports(REPO_ROOT / "src/gpd/core/include_expansion.py")

    assert all(not module.startswith("gpd.adapters") for module in imports)
    assert all(not module.startswith("gpd.registry") for module in imports)
