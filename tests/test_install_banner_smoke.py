"""Smoke check that the bootstrap banner shows the current brand year."""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _clean_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def _node_path() -> str | None:
    return shutil.which("node")


def test_install_banner_mentions_current_year() -> None:
    node = _node_path()
    if not node:
        pytest.skip("Node.js is required for this smoke check")

    result = subprocess.run(
        [node, str(REPO_ROOT / "bin" / "install.js"), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "Installer help should exit cleanly"
    output = _clean_ansi(result.stdout)
    current_year = str(datetime.now(UTC).year)
    assert f"© {current_year}" in output
