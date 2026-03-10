"""Audit round 4: CodexAdapter._skills_dir state leak regression test.

The CodexAdapter.install() method sets self._skills_dir before delegating to
super().install().  If the base class raises, _skills_dir must be restored to
its previous value so the adapter instance is not left in a corrupt state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.adapters.codex import CodexAdapter


class TestSkillsDirRestoredOnInstallFailure:
    """Verify _skills_dir is restored when super().install() raises."""

    def test_skills_dir_restored_after_exception(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        sentinel = Path("/original/skills/dir")
        adapter._skills_dir = sentinel

        target = tmp_path / ".codex"
        target.mkdir()
        gpd_root = tmp_path / "gpd_root"
        gpd_root.mkdir()

        with patch.object(
            CodexAdapter.__bases__[0],
            "install",
            side_effect=RuntimeError("simulated install failure"),
        ):
            with pytest.raises(RuntimeError, match="simulated install failure"):
                adapter.install(gpd_root, target, is_global=False, skills_dir=tmp_path / "new-skills")

        assert adapter._skills_dir == sentinel

    def test_skills_dir_restored_to_none_when_unset(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        # Do not set _skills_dir at all -- getattr should return None
        assert not hasattr(adapter, "_skills_dir")

        target = tmp_path / ".codex"
        target.mkdir()
        gpd_root = tmp_path / "gpd_root"
        gpd_root.mkdir()

        with patch.object(
            CodexAdapter.__bases__[0],
            "install",
            side_effect=RuntimeError("simulated install failure"),
        ):
            with pytest.raises(RuntimeError, match="simulated install failure"):
                adapter.install(gpd_root, target, is_global=False, skills_dir=tmp_path / "new-skills")

        assert adapter._skills_dir is None

    def test_skills_dir_restored_after_successful_install(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        sentinel = Path("/original/skills/dir")
        adapter._skills_dir = sentinel

        target = tmp_path / ".codex"
        target.mkdir()
        gpd_root = tmp_path / "gpd_root"
        gpd_root.mkdir()

        fake_result = {"runtime": "codex", "target": str(target), "commands": 0, "agents": 0}

        with patch.object(
            CodexAdapter.__bases__[0],
            "install",
            return_value=fake_result,
        ):
            result = adapter.install(gpd_root, target, is_global=False, skills_dir=tmp_path / "new-skills")

        assert result == fake_result
        assert adapter._skills_dir == sentinel
