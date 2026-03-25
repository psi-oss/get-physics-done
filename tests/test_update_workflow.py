from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import iter_runtime_descriptors, resolve_global_config_dir
from gpd.hooks.install_metadata import installed_update_command

GPD_ROOT = Path(__file__).resolve().parent.parent / "src" / "gpd"
_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


def _install_and_finalize(adapter, gpd_root: Path, target: Path, **install_kwargs: object) -> dict[str, object]:
    result = adapter.install(gpd_root, target, **install_kwargs)
    adapter.finalize_install(result)
    return result


def test_update_workflow_uses_current_runtime_agnostic_contract() -> None:
    content = (GPD_ROOT / "specs" / "workflows" / "update.md").read_text(encoding="utf-8")

    assert "get-physics-done" in content
    assert "{GPD_RUNTIME_FLAG}" in content
    assert "{GPD_INSTALL_SCOPE_FLAG}" in content
    assert "{GPD_GLOBAL_CONFIG_DIR}" in content
    assert "--target-dir" in content
    assert "--global" in content
    assert "registry.npmjs.org/get-physics-done/latest" in content
    assert 'PYTHON_BIN="${GPD_PYTHON:-}"' in content
    assert "pip index versions gpd" not in content
    assert "gpd install --all" not in content
    assert "gpd:update-check.json" not in content
    assert "commands/gpd/" not in content


def test_reapply_patches_workflow_uses_runtime_config_placeholders() -> None:
    content = (GPD_ROOT / "specs" / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")

    assert "{GPD_CONFIG_DIR}" in content
    assert "{GPD_GLOBAL_CONFIG_DIR}" in content
    for descriptor in _RUNTIME_DESCRIPTORS:
        runtime_patch_path = f"~/{descriptor.config_dir_name}/gpd-local-patches"
        workspace_patch_path = f"./{descriptor.config_dir_name}/gpd-local-patches"
        assert runtime_patch_path not in content
        assert workspace_patch_path not in content


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_default_local_install_keeps_local_update_scope_and_manifest(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / adapter.config_dir_name
    target.mkdir(parents=True)

    if "skills/" in descriptor.manifest_file_prefixes:
        monkeypatch.setenv("CODEX_SKILLS_DIR", str(tmp_path / "shared-skills"))

    _install_and_finalize(adapter, GPD_ROOT, target, is_global=False)

    content = (target / "get-physics-done" / "workflows" / "update.md").read_text(encoding="utf-8")
    manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))

    assert 'INSTALL_SCOPE="--local"' in content
    assert 'INSTALL_SCOPE="--global"' not in content
    assert manifest["install_scope"] == "local"
    assert installed_update_command(target) == f"{adapter.update_command} --local"
    if "skills/" in descriptor.manifest_file_prefixes:
        files = manifest.get("files", {})
        assert isinstance(files, dict)
        assert any(key.startswith("skills/") for key in files)


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_installed_update_command_is_derived_from_adapter_metadata(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / adapter.config_dir_name
    target.mkdir(parents=True)

    if "skills/" in descriptor.manifest_file_prefixes:
        monkeypatch.setenv("CODEX_SKILLS_DIR", str(tmp_path / "shared-skills"))

    _install_and_finalize(adapter, GPD_ROOT, target, is_global=False)

    assert installed_update_command(target) == f"{adapter.update_command} --local"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_legacy_local_install_without_install_scope_keeps_local_update_scope(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / adapter.config_dir_name
    target.mkdir(parents=True)

    if "skills/" in descriptor.manifest_file_prefixes:
        monkeypatch.setenv("CODEX_SKILLS_DIR", str(tmp_path / "shared-skills"))

    _install_and_finalize(adapter, GPD_ROOT, target, is_global=False)

    manifest_path = target / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("install_scope", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(target) == f"{adapter.update_command} --local"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_explicit_target_local_install_without_install_scope_keeps_local_update_scope(
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "explicit-target" / f"{descriptor.runtime_name}-config"
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "explicit-target" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    manifest_path = target / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("install_scope", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(target) == f"{adapter.update_command} --local --target-dir {target.as_posix()}"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_explicit_target_global_install_without_install_scope_keeps_global_update_scope(
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "explicit-global" / f"{descriptor.runtime_name}-config"
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": True, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "explicit-global" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    manifest_path = target / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("install_scope", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(target) == f"{adapter.update_command} --global --target-dir {target.as_posix()}"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_explicit_target_local_install_keeps_local_update_scope(tmp_path: Path, descriptor) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "explicit target" / f"{descriptor.runtime_name} config"
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "explicit target" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    content = (target / "get-physics-done" / "workflows" / "update.md").read_text(encoding="utf-8")

    assert 'INSTALL_SCOPE="--local"' in content
    assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in content
    assert "{GPD_INSTALL_SCOPE_FLAG}" not in content
    assert 'TARGET_DIR_ARG=$("$PYTHON_BIN" - "$INSTALL_SCOPE" "$GPD_CONFIG_DIR" "$GPD_GLOBAL_CONFIG_DIR"' in content


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_explicit_target_global_install_keeps_global_update_scope(tmp_path: Path, descriptor) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "explicit-global" / f"{descriptor.runtime_name}-config"
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": True, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "explicit-global" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    content = (target / "get-physics-done" / "workflows" / "update.md").read_text(encoding="utf-8")
    manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
    command = installed_update_command(target)

    assert 'INSTALL_SCOPE="--global"' in content
    assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in content
    assert "{GPD_INSTALL_SCOPE_FLAG}" not in content
    assert 'TARGET_DIR_ARG=$("$PYTHON_BIN" - "$INSTALL_SCOPE" "$GPD_CONFIG_DIR" "$GPD_GLOBAL_CONFIG_DIR"' in content
    assert manifest["install_scope"] == "global"
    assert manifest["explicit_target"] is True
    assert command == f"{adapter.update_command} --global --target-dir {target.as_posix()}"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_legacy_global_install_without_explicit_target_ignores_current_env_override(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    canonical_target = resolve_global_config_dir(descriptor, home=home_dir, environ={})
    canonical_target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "legacy-global" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    with monkeypatch.context() as ctx:
        ctx.setattr("gpd.hooks.install_metadata.Path.home", lambda: home_dir)
        _install_and_finalize(adapter, GPD_ROOT, canonical_target, **install_kwargs)

    manifest_path = canonical_target / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    if descriptor.global_config.strategy == "env_or_home":
        assert descriptor.global_config.env_var is not None
        monkeypatch.setenv(descriptor.global_config.env_var, str(tmp_path / "override-config"))
    elif descriptor.global_config.strategy == "xdg_app":
        if descriptor.global_config.env_dir_var is not None:
            monkeypatch.setenv(descriptor.global_config.env_dir_var, str(tmp_path / "override-config"))
        elif descriptor.global_config.env_file_var is not None:
            monkeypatch.setenv(descriptor.global_config.env_file_var, str(tmp_path / "override-config" / "config.json"))
        else:
            monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "override-config"))
    else:
        pytest.fail(f"Unsupported global config strategy: {descriptor.global_config.strategy}")

    with monkeypatch.context() as ctx:
        ctx.setattr("gpd.hooks.install_metadata.Path.home", lambda: home_dir)
        command = installed_update_command(canonical_target)

    assert command == f"{adapter.update_command} --global"
    assert "--target-dir" not in command


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_legacy_global_install_without_explicit_target_ignores_env_leak_captured_in_workflow(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    canonical_target = resolve_global_config_dir(descriptor, home=home_dir, environ={})
    canonical_target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "legacy-global" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    with monkeypatch.context() as ctx:
        if descriptor.global_config.strategy == "env_or_home":
            assert descriptor.global_config.env_var is not None
            ctx.setenv(descriptor.global_config.env_var, str(tmp_path / "foreign-config"))
        elif descriptor.global_config.strategy == "xdg_app":
            if descriptor.global_config.env_dir_var is not None:
                ctx.setenv(descriptor.global_config.env_dir_var, str(tmp_path / "foreign-config"))
            elif descriptor.global_config.env_file_var is not None:
                ctx.setenv(descriptor.global_config.env_file_var, str(tmp_path / "foreign-config" / "config.json"))
            else:
                ctx.setenv("XDG_CONFIG_HOME", str(tmp_path / "foreign-config"))
        else:
            pytest.fail(f"Unsupported global config strategy: {descriptor.global_config.strategy}")
        ctx.setattr("gpd.hooks.install_metadata.Path.home", lambda: home_dir)
        _install_and_finalize(adapter, GPD_ROOT, canonical_target, **install_kwargs)

    manifest_path = canonical_target / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with monkeypatch.context() as ctx:
        ctx.setattr("gpd.hooks.install_metadata.Path.home", lambda: home_dir)
        command = installed_update_command(canonical_target)

    assert command == f"{adapter.update_command} --global"
    assert "--target-dir" not in command


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_explicit_target_local_install_reapply_patches_uses_runtime_paths(tmp_path: Path, descriptor) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "explicit target" / f"{descriptor.runtime_name} config"
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "explicit target" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    content = (target / "get-physics-done" / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")

    assert f'PATCHES_DIR="{target.as_posix()}/gpd-local-patches"' in content
    assert "{GPD_CONFIG_DIR}" not in content
    assert "{GPD_GLOBAL_CONFIG_DIR}" not in content
    for descriptor in _RUNTIME_DESCRIPTORS:
        runtime_patch_path = f"~/{descriptor.config_dir_name}/gpd-local-patches"
        workspace_patch_path = f"./{descriptor.config_dir_name}/gpd-local-patches"
        assert runtime_patch_path not in content
        assert workspace_patch_path not in content
