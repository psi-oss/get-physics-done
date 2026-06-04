from __future__ import annotations

import os
from pathlib import Path

import pytest

from gpd.core.profile import profile_path
from gpd.core.research_persona import (
    ResearchPersona,
    ResearchPersonaError,
    load_research_persona,
    research_persona_path,
    research_persona_root,
    save_research_persona,
)

_PERSONA_LIST_FIELDS = (
    "facts",
    "axes",
    "standing_preferences",
    "negative_preferences",
    "tools",
    "research_areas",
    "papers",
    "collaborators",
    "references",
    "expertise",
    "workstyle",
    "scientific_taste",
)


def _assert_empty_persona(persona: ResearchPersona) -> None:
    assert persona.schema_version == 1
    for field_name in _PERSONA_LIST_FIELDS:
        assert getattr(persona, field_name) == []


def _snapshot_tree(root: Path) -> dict[Path, str]:
    if not root.exists():
        return {}
    snapshot: dict[Path, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_dir():
            snapshot[relative] = "<DIR>"
        else:
            snapshot[relative] = path.read_text(encoding="utf-8")
    return snapshot


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


class TestResearchPersonaStoragePaths:
    def test_prefers_explicit_data_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        explicit_root = tmp_path / "explicit-data"
        monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "ignored-env-data"))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "ignored-home")

        assert research_persona_root(explicit_root) == explicit_root / "research-persona"
        assert research_persona_path(explicit_root) == explicit_root / "research-persona" / "profile.json"

    def test_uses_gpd_data_dir_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        env_root = tmp_path / "env-data"
        monkeypatch.setenv("GPD_DATA_DIR", str(env_root))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "ignored-home")

        assert research_persona_root() == env_root / "research-persona"
        assert research_persona_path() == env_root / "research-persona" / "profile.json"

    def test_defaults_to_home_gpd_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_home = tmp_path / "home"
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        assert research_persona_root() == fake_home / ".gpd" / "research-persona"
        assert research_persona_path() == fake_home / ".gpd" / "research-persona" / "profile.json"

    def test_profile_json_is_namespaced_separately_from_author_profile(self, tmp_path: Path) -> None:
        assert profile_path(tmp_path) == tmp_path / "profile.json"
        assert research_persona_path(tmp_path) == tmp_path / "research-persona" / "profile.json"
        assert research_persona_path(tmp_path) != profile_path(tmp_path)


class TestResearchPersonaStorageLoadSave:
    def test_missing_profile_loads_default_without_creating_files(self, tmp_path: Path) -> None:
        loaded = load_research_persona(tmp_path)

        _assert_empty_persona(loaded)
        assert not research_persona_path(tmp_path).exists()
        assert not research_persona_root(tmp_path).exists()

    def test_malformed_profile_strict_load_raises(self, tmp_path: Path) -> None:
        path = research_persona_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("{ not valid json", encoding="utf-8")

        with pytest.raises(ResearchPersonaError):
            load_research_persona(tmp_path, strict=True)

    def test_save_creates_private_store_dirs(self, tmp_path: Path) -> None:
        data_root = tmp_path / "private-data"
        persona = ResearchPersona(standing_preferences=["Prefer explicit assumptions"])

        path = save_research_persona(persona, data_root)

        assert path == data_root / "research-persona" / "profile.json"
        assert data_root.is_dir()
        assert research_persona_root(data_root).is_dir()
        assert path.is_file()

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        persona = ResearchPersona(
            standing_preferences=["Prefer derivations before simulations"],
            negative_preferences=["Do not treat numerics as proof"],
            tools=["pytest"],
            research_areas=["quantum field theory"],
            expertise=["renormalization"],
            workstyle=["identify the first broken level"],
            scientific_taste=["symmetry checks"],
        )

        saved_path = save_research_persona(persona, tmp_path)
        loaded = load_research_persona(tmp_path, strict=True)

        assert saved_path == research_persona_path(tmp_path)
        assert loaded == persona

    def test_save_uses_home_data_store_not_project_gpd_when_no_data_root_is_given(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_root = tmp_path / "project"
        project_gpd = project_root / "GPD"
        project_gpd.mkdir(parents=True)
        (project_gpd / "STATE.md").write_text("# State\n", encoding="utf-8")
        (project_gpd / "state.json").write_text("{}\n", encoding="utf-8")
        before = _snapshot_tree(project_gpd)

        fake_home = tmp_path / "home"
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        monkeypatch.chdir(project_root)

        path = save_research_persona(ResearchPersona(standing_preferences=["Keep private persona machine-local"]))

        assert path == fake_home / ".gpd" / "research-persona" / "profile.json"
        assert _snapshot_tree(project_gpd) == before
        assert not (project_gpd / "research-persona").exists()
        assert not (project_gpd / "profile.json").exists()
        assert not (project_gpd / "config.json").exists()

    @pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits are not portable")
    def test_save_enforces_private_posix_permissions(self, tmp_path: Path) -> None:
        path = save_research_persona(
            ResearchPersona(standing_preferences=["Keep local identity data private"]),
            tmp_path,
        )

        assert _mode(path) == 0o600
        assert _mode(research_persona_root(tmp_path)) == 0o700
