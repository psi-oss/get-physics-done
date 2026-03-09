"""Regression tests for gpd.utils.paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from gpd.utils.paths import find_project_root


def test_find_project_root_detects_repo_from_nested_subdirectory(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    nested = repo_root / "src" / "gpd" / "core"
    nested.mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='gpd'\n", encoding="utf-8")
    (repo_root / "infra").mkdir()

    with patch("gpd.utils.paths.Path.cwd", return_value=nested):
        assert find_project_root() == repo_root
