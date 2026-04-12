from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import _materialize_workflow_paths
from gpd.adapters.runtime_catalog import (
    get_shared_install_metadata,
    iter_runtime_descriptors,
    resolve_global_config_dir,
)
from gpd.hooks.install_metadata import installed_update_command

GPD_ROOT = Path(__file__).resolve().parent.parent / "src" / "gpd"
_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_SHARED_INSTALL = get_shared_install_metadata()
INSTALL_ROOT_DIR_NAME = _SHARED_INSTALL.install_root_dir_name
MANIFEST_NAME = _SHARED_INSTALL.manifest_name
BOOTSTRAP_COMMAND = _SHARED_INSTALL.bootstrap_command


def _install_and_finalize(adapter, gpd_root: Path, target: Path, **install_kwargs: object) -> dict[str, object]:
    result = adapter.install(gpd_root, target, **install_kwargs)
    adapter.finalize_install(result)
    return result


def _install_kwargs_for_descriptor(descriptor, tmp_path: Path) -> dict[str, object]:
    install_kwargs: dict[str, object] = {}
    if "skills/" in descriptor.manifest_file_prefixes:
        install_kwargs["skills_dir"] = tmp_path / "shared-skills"
    return install_kwargs


def test_update_workflow_uses_current_runtime_agnostic_contract() -> None:
    content = (GPD_ROOT / "specs" / "workflows" / "update.md").read_text(encoding="utf-8")

    assert "{GPD_INSTALL_ROOT_DIR_NAME}" in content
    assert "{GPD_INSTALL_SCOPE_FLAG}" in content
    assert "{GPD_UPDATE_COMMAND}" in content
    assert "{GPD_PATCH_META}" in content
    assert "{GPD_RELEASE_LATEST_URL}" in content
    assert "{GPD_RELEASES_API_URL}" in content
    assert "{GPD_RELEASES_PAGE_URL}" in content
    assert "{GPD_GLOBAL_CONFIG_DIR}" in content
    assert 'PYTHON_BIN="${GPD_PYTHON:-}"' in content
    assert "TARGET_DIR_ARG=$(" not in content
    assert "{GPD_RUNTIME_FLAG}" not in content
    assert _SHARED_INSTALL.latest_release_url not in content
    assert "pip index versions gpd" not in content
    assert "gpd install --all" not in content
    assert "gpd:update-check.json" not in content
    assert "commands/gpd/" not in content


def test_reapply_patches_workflow_uses_runtime_config_placeholders() -> None:
    content = (GPD_ROOT / "specs" / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")

    assert "{GPD_PATCHES_DIR}" in content
    assert "{GPD_GLOBAL_PATCHES_DIR}" in content
    assert "{GPD_PATCHES_DIR_NAME}" in content
    for descriptor in _RUNTIME_DESCRIPTORS:
        runtime_patch_path = f"~/{descriptor.config_dir_name}/{_SHARED_INSTALL.patches_dir_name}"
        workspace_patch_path = f"./{descriptor.config_dir_name}/{_SHARED_INSTALL.patches_dir_name}"
        assert runtime_patch_path not in content
        assert workspace_patch_path not in content


def test_materialize_workflow_paths_replaces_global_placeholder_with_target_on_global_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = next(
        descriptor
        for descriptor in _RUNTIME_DESCRIPTORS
        if descriptor.global_config.env_var and descriptor.global_config.home_subpath
    )
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    canonical_global_dir = resolve_global_config_dir(descriptor, home=home_dir, environ={})

    override_dir = tmp_path / "env-override" / descriptor.config_dir_name
    override_dir.mkdir(parents=True)
    assert canonical_global_dir != override_dir

    env_var = descriptor.global_config.env_var
    assert env_var is not None
    monkeypatch.setenv(env_var, str(override_dir))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

    target_dir = tmp_path / "target" / descriptor.config_dir_name
    target_dir.mkdir(parents=True)
    content = "{GPD_GLOBAL_CONFIG_DIR}"

    rendered = _materialize_workflow_paths(
        content,
        target_dir=target_dir,
        runtime=descriptor.runtime_name,
        install_scope="--global",
        explicit_target=True,
    )

    assert canonical_global_dir.as_posix() not in rendered
    assert rendered == target_dir.as_posix()


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_default_local_install_keeps_local_update_scope_and_manifest(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / adapter.config_dir_name
    target.mkdir(parents=True)

    _install_and_finalize(
        adapter, GPD_ROOT, target, is_global=False, **_install_kwargs_for_descriptor(descriptor, tmp_path)
    )

    update_content = (target / INSTALL_ROOT_DIR_NAME / "workflows" / "update.md").read_text(encoding="utf-8")
    reapply_content = (target / INSTALL_ROOT_DIR_NAME / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")
    manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))

    assert 'INSTALL_SCOPE="--local"' in update_content
    assert 'INSTALL_SCOPE="--global"' not in update_content
    assert f'UPDATE_COMMAND="{adapter.update_command} --local"' in update_content
    assert f'PATCH_META="{target.as_posix()}/{_SHARED_INSTALL.patches_dir_name}/backup-meta.json"' in update_content
    assert manifest["install_scope"] == "local"
    assert installed_update_command(target) == f"{adapter.update_command} --local"
    assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in update_content
    assert f'GPD_INSTALL_DIR="{(target / _SHARED_INSTALL.install_root_dir_name).as_posix()}"' in update_content
    assert f'PATCHES_DIR="{target.as_posix()}/{_SHARED_INSTALL.patches_dir_name}"' in reapply_content
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

    _install_and_finalize(
        adapter, GPD_ROOT, target, is_global=False, **_install_kwargs_for_descriptor(descriptor, tmp_path)
    )

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

    _install_and_finalize(
        adapter, GPD_ROOT, target, is_global=False, **_install_kwargs_for_descriptor(descriptor, tmp_path)
    )

    manifest_path = target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("install_scope", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(target) is None


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_local_install_without_explicit_target_returns_no_trusted_update_command(
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "workspace" / descriptor.config_dir_name
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "workspace" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    manifest_path = target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(target) is None


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_moved_explicit_target_local_install_without_explicit_target_returns_no_trusted_update_command(
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    original_target = tmp_path / "original-explicit-target" / descriptor.config_dir_name
    original_target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "original-explicit-target" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, original_target, **install_kwargs)

    relocated_target = tmp_path / "moved-explicit-target" / descriptor.config_dir_name
    shutil.copytree(original_target, relocated_target)
    manifest_path = relocated_target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(relocated_target) is None


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_local_install_without_explicit_target_and_missing_workflow_returns_no_trusted_update_command(
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "workspace" / descriptor.config_dir_name
    target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": False}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "workspace" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    manifest_path = target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (target / INSTALL_ROOT_DIR_NAME / "workflows" / "update.md").unlink()

    assert installed_update_command(target) is None


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

    manifest_path = target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("install_scope", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(target) is None


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

    manifest_path = target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("install_scope", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert installed_update_command(target) is None


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

    content = (target / INSTALL_ROOT_DIR_NAME / "workflows" / "update.md").read_text(encoding="utf-8")
    command = installed_update_command(target)

    assert 'INSTALL_SCOPE="--local"' in content
    assert isinstance(command, str)
    assert f'UPDATE_COMMAND="{command}"' in content
    assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in content
    assert "{GPD_INSTALL_SCOPE_FLAG}" not in content
    assert "TARGET_DIR_ARG=$(" not in content


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_explicit_target_global_install_keeps_global_update_scope(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    target = tmp_path / "explicit-global" / f"{descriptor.runtime_name}-config"
    target.mkdir(parents=True)
    monkeypatch.setattr("gpd.adapters.install_utils.Path.home", lambda: tmp_path / "ambient-home")

    install_kwargs: dict[str, object] = {"is_global": True, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "explicit-global" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, target, **install_kwargs)

    content = (target / INSTALL_ROOT_DIR_NAME / "workflows" / "update.md").read_text(encoding="utf-8")
    reapply_content = (target / INSTALL_ROOT_DIR_NAME / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")
    manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
    command = installed_update_command(target)

    assert 'INSTALL_SCOPE="--global"' in content
    assert isinstance(command, str)
    assert f'UPDATE_COMMAND="{command}"' in content
    assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in content
    assert f'GPD_GLOBAL_CONFIG_DIR="{target.as_posix()}"' in content
    assert f'GLOBAL_PATCHES_DIR="{target.as_posix()}/{_SHARED_INSTALL.patches_dir_name}"' in reapply_content
    assert "{GPD_INSTALL_SCOPE_FLAG}" not in content
    assert "TARGET_DIR_ARG=$(" not in content
    assert manifest["install_scope"] == "global"
    assert manifest["explicit_target"] is True
    assert "--target-dir" in command


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_global_install_without_explicit_target_returns_no_trusted_update_command(
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

    manifest_path = canonical_target / MANIFEST_NAME
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
        assert installed_update_command(canonical_target) is None


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_global_install_materializes_authoritative_paths_for_custom_home(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    home_dir = tmp_path / "custom-home"
    home_dir.mkdir()
    canonical_target = resolve_global_config_dir(descriptor, home=home_dir, environ={})
    canonical_target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "custom-home-global" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    with monkeypatch.context() as ctx:
        ctx.setattr("gpd.adapters.install_utils.Path.home", lambda: tmp_path / "ambient-home")
        _install_and_finalize(adapter, GPD_ROOT, canonical_target, **install_kwargs)

    update_content = (canonical_target / INSTALL_ROOT_DIR_NAME / "workflows" / "update.md").read_text(encoding="utf-8")
    reapply_content = (canonical_target / INSTALL_ROOT_DIR_NAME / "workflows" / "reapply-patches.md").read_text(
        encoding="utf-8"
    )
    patches_dir = f"{canonical_target.as_posix()}/{_SHARED_INSTALL.patches_dir_name}"

    assert f'GPD_CONFIG_DIR="{canonical_target.as_posix()}"' in update_content
    assert f'GPD_GLOBAL_CONFIG_DIR="{canonical_target.as_posix()}"' in update_content
    assert f'PATCHES_DIR="{patches_dir}"' in reapply_content
    assert f'GLOBAL_PATCHES_DIR="{patches_dir}"' in reapply_content


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_env_resolved_global_install_without_explicit_target_returns_trusted_update_command(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    override_target = tmp_path / "override-config" / descriptor.config_dir_name
    override_target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "legacy-global-env" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    with monkeypatch.context() as ctx:
        if descriptor.global_config.strategy == "env_or_home":
            assert descriptor.global_config.env_var is not None
            ctx.setenv(descriptor.global_config.env_var, str(override_target))
        elif descriptor.global_config.strategy == "xdg_app":
            if descriptor.global_config.env_dir_var is not None:
                ctx.setenv(descriptor.global_config.env_dir_var, str(override_target))
            elif descriptor.global_config.env_file_var is not None:
                ctx.setenv(descriptor.global_config.env_file_var, str(override_target / "config.json"))
            else:
                ctx.setenv("XDG_CONFIG_HOME", str(override_target.parent))
        else:
            pytest.fail(f"Unsupported global config strategy: {descriptor.global_config.strategy}")
        ctx.setattr("gpd.hooks.install_metadata.Path.home", lambda: home_dir)
        _install_and_finalize(adapter, GPD_ROOT, override_target, **install_kwargs)

    manifest_path = override_target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with monkeypatch.context() as ctx:
        if descriptor.global_config.strategy == "env_or_home":
            assert descriptor.global_config.env_var is not None
            ctx.setenv(descriptor.global_config.env_var, str(override_target))
        elif descriptor.global_config.strategy == "xdg_app":
            if descriptor.global_config.env_dir_var is not None:
                ctx.setenv(descriptor.global_config.env_dir_var, str(override_target))
            elif descriptor.global_config.env_file_var is not None:
                ctx.setenv(descriptor.global_config.env_file_var, str(override_target / "config.json"))
            else:
                ctx.setenv("XDG_CONFIG_HOME", str(override_target.parent))
        else:
            pytest.fail(f"Unsupported global config strategy: {descriptor.global_config.strategy}")
        ctx.setattr("gpd.hooks.install_metadata.Path.home", lambda: home_dir)
        assert installed_update_command(override_target) == f"{BOOTSTRAP_COMMAND} {descriptor.install_flag} --global"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_noncanonical_global_install_without_explicit_target_returns_no_trusted_update_command(
    tmp_path: Path,
    descriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    explicit_target = tmp_path / "custom-global" / descriptor.config_dir_name
    explicit_target.mkdir(parents=True)

    install_kwargs: dict[str, object] = {"is_global": True, "explicit_target": True}
    if "skills/" in descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / "legacy-global-explicit" / "skills"
        skills_dir.mkdir(parents=True)
        install_kwargs["skills_dir"] = skills_dir

    _install_and_finalize(adapter, GPD_ROOT, explicit_target, **install_kwargs)

    manifest_path = explicit_target / MANIFEST_NAME
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

    assert installed_update_command(explicit_target) is None


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_global_install_without_explicit_target_and_env_leak_returns_trusted_update_command(
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

    manifest_path = canonical_target / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with monkeypatch.context() as ctx:
        ctx.setattr("gpd.hooks.install_metadata.Path.home", lambda: home_dir)
        if descriptor.global_config.strategy == "xdg_app" and descriptor.global_config.env_dir_var is not None:
            ctx.setenv(descriptor.global_config.env_dir_var, str(canonical_target))
        assert installed_update_command(canonical_target, home=home_dir) == (
            f"{BOOTSTRAP_COMMAND} {descriptor.install_flag} --global"
        )


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

    content = (target / INSTALL_ROOT_DIR_NAME / "workflows" / "reapply-patches.md").read_text(encoding="utf-8")

    assert f'PATCHES_DIR="{target.as_posix()}/{_SHARED_INSTALL.patches_dir_name}"' in content
    assert 'GLOBAL_PATCHES_DIR="' in content
    assert "{GPD_PATCHES_DIR}" not in content
    assert "{GPD_GLOBAL_PATCHES_DIR}" not in content
    for descriptor in _RUNTIME_DESCRIPTORS:
        runtime_patch_path = f"~/{descriptor.config_dir_name}/{_SHARED_INSTALL.patches_dir_name}"
        workspace_patch_path = f"./{descriptor.config_dir_name}/{_SHARED_INSTALL.patches_dir_name}"
        assert runtime_patch_path not in content
        assert workspace_patch_path not in content
