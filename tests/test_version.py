from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import gpd.version as gpd_version

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_MODULE_PATH = REPO_ROOT / "src" / "gpd" / "version.py"


def _make_checkout(tmp_path: Path, version: str) -> Path:
    repo_root = tmp_path / "checkout"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "get-physics-done",
                "version": version,
                "gpdPythonVersion": version,
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "get-physics-done"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    src_root = repo_root / "src" / "gpd"
    for subdir in ("commands", "agents", "hooks", "specs"):
        (src_root / subdir).mkdir(parents=True, exist_ok=True)
    return repo_root


def test_source_checkout_falls_back_to_pyproject_version() -> None:
    expected = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    module_name = "test_gpd_version_fallback"
    spec = importlib.util.spec_from_file_location(module_name, VERSION_MODULE_PATH)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)

    with patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
        spec.loader.exec_module(module)

    assert module.__version__ == expected


def test_resolve_install_gpd_root_prefers_cwd_checkout(tmp_path: Path) -> None:
    repo_root = _make_checkout(tmp_path, "9.9.9")
    nested = repo_root / "research" / "project"
    nested.mkdir(parents=True)

    assert gpd_version.resolve_install_gpd_root(nested) == repo_root / "src" / "gpd"


def test_resolve_active_version_prefers_cwd_checkout_version(tmp_path: Path) -> None:
    repo_root = _make_checkout(tmp_path, "9.9.9")
    nested = repo_root / "research" / "project"
    nested.mkdir(parents=True)

    assert gpd_version.resolve_active_version(nested) == "9.9.9"
