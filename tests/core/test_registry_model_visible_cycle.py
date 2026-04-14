from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"


def _assert_import_order(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC_DIR)},
    )
    assert completed.returncode == 0, completed.stderr


def test_import_model_visible_text_before_registry() -> None:
    _assert_import_order("import gpd.core.model_visible_text; import gpd.registry")


def test_import_registry_before_model_visible_text() -> None:
    _assert_import_order("import gpd.registry; import gpd.core.model_visible_text")
