from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_registry_imports_cleanly_in_fresh_interpreter() -> None:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    repo_src = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = repo_src if not existing_pythonpath else os.pathsep.join((repo_src, existing_pythonpath))

    result = subprocess.run(
        [sys.executable, "-c", "import gpd.registry; print('ok')"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "ok"
