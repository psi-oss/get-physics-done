"""Tests for gpd.__main__ — ensures ``python -m gpd`` works."""

from __future__ import annotations

import subprocess
import sys


def test_python_m_gpd_help():
    """``python -m gpd --help`` should exit 0 and show usage."""
    result = subprocess.run(
        [sys.executable, "-m", "gpd", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Usage" in result.stdout or "usage" in result.stdout.lower()


def test_python_m_gpd_version():
    """``python -m gpd --version`` should print a version string."""
    result = subprocess.run(
        [sys.executable, "-m", "gpd", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    # Version output should contain a digit
    combined = result.stdout + result.stderr
    assert any(c.isdigit() for c in combined), f"No version digit in: {combined!r}"


def test_python_m_gpd_unknown_command():
    """``python -m gpd nonexistent`` should fail with non-zero exit."""
    result = subprocess.run(
        [sys.executable, "-m", "gpd", "nonexistent"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
