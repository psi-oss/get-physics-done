from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_MODULE_PATH = REPO_ROOT / "src" / "gpd" / "version.py"


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
