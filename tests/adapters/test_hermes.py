"""Tests for the Hermes Agent runtime adapter.

Covers the two integration gaps the initial adapter had:

1. **Global config resolution.** `global_config_dir`, `resolve_global_config_dir`
   and `skills_dir` must all agree on the same Hermes config directory
   (``HERMES_HOME`` -> ``%LOCALAPPDATA%\\Hermes`` on Windows). Previously the
   installer (via ``resolve_target_dir``/catalog) and the skill reader
   (``skills_dir``) diverged, splitting installed GPD content from the Hermes
   skills directory.

2. **Install-time projection.** Command and agent skills must be passed through
   ``translate_shared_markdown`` so tool references (``file_read`` ->
   ``read_file``) and ``{GPD_*}`` path placeholders are rewritten for this
   runtime before writing. Previously skills were copied raw, leaving
   ``file_read``/``file_write`` (which Hermes does not expose) in the body and
   unresolved placeholders.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gpd.adapters.hermes import HermesAdapter, _hermes_global_config_dir
from gpd.adapters.install_utils import (
    split_markdown_frontmatter,
)
from gpd.adapters.runtime_catalog import (
    resolve_global_config_dir,
    get_runtime_descriptor,
)

REPO_GPD_ROOT = Path(__file__).resolve().parents[2] / "src" / "gpd"


@pytest.fixture()
def adapter() -> HermesAdapter:
    return HermesAdapter()


# ---------------------------------------------------------------------------
# 1. Config directory resolution stays consistent
# ---------------------------------------------------------------------------


def test_resolve_global_config_dir_matches_global_config_dir(
    adapter: HermesAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The installer and the skill reader must resolve the same directory."""
    monkeypatch.delenv("HERMES_HOME", raising=False)
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", r"C:\fake\localappdata")
        expected = Path(r"C:\fake\localappdata") / "Hermes"
    else:
        monkeypatch.setenv("HOME", "/fake/home")
        expected = Path("/fake/home") / ".hermes"

    assert adapter.global_config_dir == expected
    assert adapter.resolve_global_config_dir() == expected
    assert adapter.skills_dir == expected / "skills"


def test_hermes_home_env_override_is_authoritative(adapter: HermesAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    """``HERMES_HOME`` overrides the platform default everywhere."""
    monkeypatch.setenv("HERMES_HOME", "/custom/hermes")
    expected = Path("/custom/hermes").expanduser().resolve()
    assert adapter.global_config_dir == expected
    assert adapter.resolve_global_config_dir() == expected
    assert adapter.skills_dir == expected / "skills"


def test_hermes_skills_dir_env_override(adapter: HermesAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    """``HERMES_SKILLS_DIR`` overrides the derived skills directory."""
    monkeypatch.setenv("HERMES_SKILLS_DIR", "/custom/skills")
    assert adapter.skills_dir == Path("/custom/skills").expanduser().resolve()


# ---------------------------------------------------------------------------
# 2. Install-time projection rewrites tool names and placeholders
# ---------------------------------------------------------------------------


def test_translate_shared_markdown_maps_legacy_tool_names(adapter: HermesAdapter) -> None:
    """Legacy tool names must map to Hermes-native names before writing."""
    content = "- Use `file_read` to read.\n- Use `file_write` to write.\n- `TODO_WRITE`?"
    translated = adapter.translate_shared_markdown(content, "C:/fake/", install_scope="--global")
    assert "file_read" not in translated
    assert "read_file" in translated
    assert "file_write" not in translated
    assert "write_file" in translated


def test_translate_shared_markdown_resolves_path_placeholders(adapter: HermesAdapter) -> None:
    """``{GPD_CONFIG_DIR}`` and friends collapse into concrete paths."""
    content = "config: {GPD_CONFIG_DIR}\nagents: {GPD_AGENTS_DIR}\n"
    translated = adapter.translate_shared_markdown(content, "C:/fake/hermes/", install_scope="--global")
    assert "{GPD_CONFIG_DIR}" not in translated
    assert "{GPD_AGENTS_DIR}" not in translated
    assert "C:/fake/hermes/" in translated


def _compile_one_skill(adapter: HermesAdapter, command_stem: str, tmp_path: Path) -> Path:
    """Install a single command skill into a temp skills dir and return its path."""
    from gpd.adapters.hermes import _copy_commands_as_skills

    src = REPO_GPD_ROOT / "commands"
    skills_dir = tmp_path / "skills"
    generated = _copy_commands_as_skills(
        src,
        skills_dir,
        "gpd",
        str(tmp_path).replace("\\", "/") + "/",
        runtime="hermes",
        install_scope="--global",
        src_root=REPO_GPD_ROOT / "specs",
        explicit_target=False,
        adapter=adapter,
    )
    assert "gpd-plan-phase" in generated
    return skills_dir / "gpd-plan-phase" / "SKILL.md"


def test_installed_command_skill_translates_tool_names(adapter: HermesAdapter, tmp_path: Path) -> None:
    """A command installed as a skill must not contain legacy tool names."""
    skill_path = _compile_one_skill(adapter, "plan-phase", tmp_path)
    text = skill_path.read_text(encoding="utf-8")

    # The marker should be present (ownership).
    assert "<!-- Managed by Get Physics Done (GPD). -->" in text

    # Frontmatter must be intact and parseable as YAML.
    _, frontmatter, _, _ = split_markdown_frontmatter(text)
    assert "name:" in frontmatter

    # No unresolved path placeholders.
    assert "{GPD_" not in text

    # No legacy tool names that Hermes does not expose.
    assert "file_read" not in text
    assert "file_write" not in text


def test_installed_agent_skill_has_no_unresolved_placeholders(adapter: HermesAdapter, tmp_path: Path) -> None:
    """Agent skills install with their body protected and placeholders resolved."""
    from gpd.adapters.hermes import _copy_agents_as_skills

    agents_src = REPO_GPD_ROOT / "agents"
    skills_dir = tmp_path / "skills"
    generated = _copy_agents_as_skills(
        agents_src,
        skills_dir,
        "gpd",
        str(tmp_path).replace("\\", "/") + "/",
        runtime="hermes",
        install_scope="--global",
        src_root=REPO_GPD_ROOT / "specs",
    )
    assert generated
    planner = skills_dir / "gpd-agent-gpd-planner" / "SKILL.md"
    assert planner.exists()
    text = planner.read_text(encoding="utf-8")
    assert "{GPD_" not in text
    assert text.strip()


def test_adapter_is_registered_in_catalog(adapter: HermesAdapter) -> None:
    """Hermes is a first-class catalog runtime."""
    descriptor = get_runtime_descriptor("hermes")
    assert descriptor is not None
    assert descriptor.runtime_name == "hermes"


def test_hermes_config_resolution_beats_catalog_on_windows(
    adapter: HermesAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows the adapter's LOCALAPPDATA-based resolution must win over the
    catalog's home-relative default (which would target ``~/Hermes``)."""
    if os.name != "nt":
        monkeypatch.skip("Windows-only behavior")
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\real\localappdata")

    # The catalog defaults to the home subpath (~/Hermes); the adapter must
    # correct it to %LOCALAPPDATA%\Hermes on Windows so installer and reader
    # agree.
    assert adapter.global_config_dir == Path(r"C:\real\localappdata") / "Hermes"
    assert adapter.resolve_global_config_dir() == Path(r"C:\real\localappdata") / "Hermes"
    assert adapter.skills_dir == Path(r"C:\real\localappdata") / "Hermes" / "skills"