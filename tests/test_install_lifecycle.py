"""Install lifecycle tests for the supported runtime adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import MANIFEST_NAME, build_runtime_cli_bridge_command
from gpd.adapters.runtime_catalog import iter_runtime_descriptors


def _install_and_finalize(adapter, gpd_root: Path, target: Path, **install_kwargs: object) -> dict[str, object]:
    result = adapter.install(gpd_root, target, **install_kwargs)
    adapter.finalize_install(result)
    return result


def _assert_manifest_present(target: Path) -> dict[str, object]:
    manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["version"]
    assert manifest["files"]
    return manifest


@pytest.fixture()
def gpd_root() -> Path:
    """Return the GPD package data root."""
    root = Path(__file__).resolve().parent.parent / "src" / "gpd"
    assert (root / "commands").is_dir()
    assert (root / "agents").is_dir()
    assert (root / "specs").is_dir()
    assert (root / "hooks").is_dir()
    return root


_INSTALL_LIFECYCLE_DESCRIPTORS = iter_runtime_descriptors()
_MARKDOWN_COMMAND_RUNTIME = next(
    descriptor for descriptor in _INSTALL_LIFECYCLE_DESCRIPTORS if descriptor.native_include_support
)
_EXTERNAL_SKILLS_RUNTIME = next(
    descriptor for descriptor in _INSTALL_LIFECYCLE_DESCRIPTORS if "skills/" in descriptor.manifest_file_prefixes
)


def _managed_external_command_dir_names(adapter, target: Path, manifest: dict[str, object]) -> tuple[str, ...]:
    del adapter, target
    for value in manifest.values():
        if isinstance(value, list) and value and all(isinstance(item, str) and item.startswith("gpd-") for item in value):
            return tuple(sorted(value))
    raise AssertionError("adapter manifest did not expose managed external command directories")


def test_markdown_command_runtime_lifecycle_round_trip(tmp_path: Path, gpd_root: Path) -> None:
    adapter = get_adapter(_MARKDOWN_COMMAND_RUNTIME.runtime_name)
    target = tmp_path / _MARKDOWN_COMMAND_RUNTIME.config_dir_name
    target.mkdir()

    _install_and_finalize(adapter, gpd_root, target, is_global=True)

    commands_dir = target / "commands" / "gpd"
    assert commands_dir.is_dir()
    assert (commands_dir / "start.md").exists()
    assert (commands_dir / "tour.md").exists()

    slides_md = commands_dir / "slides.md"
    slides_content = slides_md.read_text(encoding="utf-8")
    assert "context_mode: projectless" in slides_content
    assert "/get-physics-done/workflows/slides.md" in slides_content

    suggest_next = (commands_dir / "suggest-next.md").read_text(encoding="utf-8")
    assert "Run `gpd --raw suggest`" in suggest_next

    manifest = _assert_manifest_present(target)
    assert manifest["runtime"] == adapter.runtime_name
    assert (target / "hooks" / "statusline.py").exists()
    assert (target / "get-physics-done" / "VERSION").exists()

    uninstall_result = adapter.uninstall(target)
    assert uninstall_result["removed"]
    assert not (target / "commands" / "gpd").exists()
    assert not (target / "get-physics-done").exists()
    assert not (target / MANIFEST_NAME).exists()


def test_external_skills_runtime_lifecycle_round_trip(tmp_path: Path, gpd_root: Path) -> None:
    adapter = get_adapter(_EXTERNAL_SKILLS_RUNTIME.runtime_name)
    target = tmp_path / _EXTERNAL_SKILLS_RUNTIME.config_dir_name
    target.mkdir()
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)

    _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

    gpd_skills = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
    assert gpd_skills
    assert (skills_dir / "gpd-help" / "SKILL.md").exists()
    assert (skills_dir / "gpd-start" / "SKILL.md").exists()
    assert (skills_dir / "gpd-tour" / "SKILL.md").exists()
    assert (skills_dir / "gpd-slides" / "SKILL.md").exists()

    help_skill = (skills_dir / "gpd-help" / "SKILL.md").read_text(encoding="utf-8")
    assert "context_mode:" in help_skill
    assert not (skills_dir / "gpd-planner").exists()

    assert (target / "agents" / "gpd-planner.toml").exists()
    config_toml = (target / "config.toml").read_text(encoding="utf-8")
    assert "notify" in config_toml
    assert "multi_agent = true" in config_toml
    manifest = _assert_manifest_present(target)
    managed_external_command_dir_names = _managed_external_command_dir_names(adapter, target, manifest)
    assert managed_external_command_dir_names
    assert all(name.startswith("gpd-") for name in managed_external_command_dir_names)

    suggest_next = (skills_dir / "gpd-suggest-next" / "SKILL.md").read_text(encoding="utf-8")
    bridge_command = build_runtime_cli_bridge_command(
        adapter.runtime_name,
        target_dir=target,
        config_dir_name=adapter.config_dir_name,
        is_global=True,
        explicit_target=False,
    )
    assert bridge_command in suggest_next

    preserved_skill = skills_dir / "gpd-user-keep"
    preserved_skill.mkdir()
    (preserved_skill / "SKILL.md").write_text("keep", encoding="utf-8")

    uninstall_result = adapter.uninstall(target, skills_dir=skills_dir)
    assert uninstall_result["skills"] > 0
    assert (preserved_skill / "SKILL.md").exists()
    assert not any((skills_dir / name).exists() for name in managed_external_command_dir_names)
    assert not (target / "get-physics-done").exists()
    assert not (target / MANIFEST_NAME).exists()
