from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_PYTHON = (
    REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt"
    else REPO_ROOT / ".venv" / "bin" / "python"
)


def _repo_python_command() -> list[str]:
    if REPO_PYTHON.is_file():
        return [str(REPO_PYTHON)]
    if sys.executable:
        return [sys.executable]
    return ["uv", "run", "python"]


def _top_level_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports


def _imported_names_from_module(path: Path, module_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            names.extend(alias.name for alias in node.names)
    return names


def test_adapter_base_does_not_import_registry_at_module_import_time() -> None:
    imports = _top_level_imports(REPO_ROOT / "src" / "gpd" / "adapters" / "base.py")

    assert "gpd.registry" not in imports


def test_contract_validation_uses_public_contract_imports() -> None:
    imports = _imported_names_from_module(
        REPO_ROOT / "src" / "gpd" / "core" / "contract_validation.py",
        "gpd.contracts",
    )

    assert not [name for name in imports if name.startswith("_")]


def test_registry_import_remains_stable_after_adapter_package_import() -> None:
    result = subprocess.run(
        [
            *_repo_python_command(),
            "-c",
            "import gpd.adapters.base\nfrom gpd import registry\nprint('GPD_IMPORT_STABILITY_SENTINEL=' + str(hasattr(registry, 'render_command_visibility_sections_from_frontmatter')))",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "GPD_IMPORT_STABILITY_SENTINEL=True" in result.stdout.splitlines()


def test_knowledge_docs_review_hash_api_does_not_depend_on_frontmatter_import_order() -> None:
    result = subprocess.run(
        [
            *_repo_python_command(),
            "-c",
            "from gpd.core.knowledge_docs import compute_knowledge_reviewed_content_sha256, knowledge_reviewed_content_projection\n"
            "print('GPD_KNOWLEDGE_HASH_API_SENTINEL=' + str(callable(compute_knowledge_reviewed_content_sha256) and callable(knowledge_reviewed_content_projection)))",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "GPD_KNOWLEDGE_HASH_API_SENTINEL=True" in result.stdout.splitlines()
