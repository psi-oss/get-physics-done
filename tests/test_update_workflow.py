from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters import get_adapter

GPD_ROOT = Path(__file__).resolve().parent.parent / "src" / "gpd"


def test_update_workflow_uses_current_runtime_agnostic_contract() -> None:
    content = (GPD_ROOT / "specs" / "workflows" / "update.md").read_text(encoding="utf-8")

    assert "get-physics-done" in content
    assert "{GPD_RUNTIME_FLAG}" in content
    assert "{GPD_INSTALL_SCOPE_FLAG}" in content
    assert "--target-dir" in content
    assert "registry.npmjs.org/get-physics-done/latest" in content
    assert "pip index versions gpd" not in content
    assert "gpd install --all" not in content
    assert "gpd:update-check.json" not in content
    assert "commands/gpd/" not in content


def test_reapply_patches_workflow_uses_runtime_config_placeholders() -> None:
    content = (GPD_ROOT / "specs" / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")

    assert "{GPD_CONFIG_DIR}" in content
    assert "{GPD_GLOBAL_CONFIG_DIR}" in content
    assert "~/.claude/gpd-local-patches" not in content
    assert "./.claude/gpd-local-patches" not in content


@pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
def test_explicit_target_local_install_keeps_local_update_scope(tmp_path: Path, runtime: str) -> None:
    adapter = get_adapter(runtime)
    target = tmp_path / "explicit target" / f"{runtime} config"
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False, "explicit_target": True}
    if runtime == "codex":
        skills_dir = tmp_path / "explicit target" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    adapter.install(GPD_ROOT, target, **install_kwargs)

    content = (target / "get-physics-done" / "workflows" / "update.md").read_text(encoding="utf-8")

    assert 'INSTALL_SCOPE="--local"' in content
    assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in content
    assert "{GPD_INSTALL_SCOPE_FLAG}" not in content
    assert "TARGET_DIR_ARG=$(python3 - \"$GPD_CONFIG_DIR\"" in content


@pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
def test_explicit_target_local_install_reapply_patches_uses_runtime_paths(tmp_path: Path, runtime: str) -> None:
    adapter = get_adapter(runtime)
    target = tmp_path / "explicit target" / f"{runtime} config"
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False, "explicit_target": True}
    if runtime == "codex":
        skills_dir = tmp_path / "explicit target" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    adapter.install(GPD_ROOT, target, **install_kwargs)

    content = (target / "get-physics-done" / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")

    assert f'PATCHES_DIR="{target.as_posix()}/gpd-local-patches"' in content
    assert "{GPD_CONFIG_DIR}" not in content
    assert "{GPD_GLOBAL_CONFIG_DIR}" not in content
    assert "~/.claude/gpd-local-patches" not in content
    assert "./.claude/gpd-local-patches" not in content
