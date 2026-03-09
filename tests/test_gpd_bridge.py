"""Tests for GPD runtime install discovery and version bridge helpers."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from gpd.mcp.gpd_bridge.discovery import find_gpd_install, find_gpd_references_dir
from gpd.mcp.gpd_bridge.version import check_gpd_version
from gpd.version import __version__


def test_find_gpd_install_recognizes_version_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    install_root = home / ".claude"
    core_dir = install_root / "get-physics-done"
    core_dir.mkdir(parents=True)
    (core_dir / "VERSION").write_text("0.1.0\n", encoding="utf-8")

    with (
        patch("gpd.mcp.gpd_bridge.discovery.Path.home", return_value=home),
        patch("gpd.mcp.gpd_bridge.discovery.Path.cwd", return_value=cwd),
        patch.dict(os.environ, {}, clear=True),
    ):
        assert find_gpd_install() == install_root


def test_find_gpd_references_dir_uses_version_based_install(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    install_root = home / ".gemini"
    refs_dir = install_root / "get-physics-done" / "references"
    refs_dir.mkdir(parents=True)
    (install_root / "get-physics-done" / "VERSION").write_text("0.1.0\n", encoding="utf-8")

    with (
        patch("gpd.mcp.gpd_bridge.discovery.Path.home", return_value=home),
        patch("gpd.mcp.gpd_bridge.discovery.Path.cwd", return_value=cwd),
        patch.dict(os.environ, {}, clear=True),
    ):
        assert find_gpd_references_dir() == refs_dir


def test_check_gpd_version_reads_version_file(tmp_path: Path) -> None:
    install_root = tmp_path / ".codex"
    core_dir = install_root / "get-physics-done"
    core_dir.mkdir(parents=True)
    (core_dir / "VERSION").write_text(f"{__version__}\n", encoding="utf-8")

    assert check_gpd_version(install_root) == (True, __version__)
