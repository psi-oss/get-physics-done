"""Shared helpers for installed-hook metadata."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.adapters import get_adapter, iter_adapters
from gpd.adapters.install_utils import build_runtime_install_repair_command
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.hooks.runtime_detect import SCOPE_LOCAL, _runtime_from_manifest_or_path


def load_install_manifest(config_dir: Path) -> dict[str, object]:
    """Return the parsed install manifest for *config_dir* when available."""

    manifest_path = config_dir / "gpd-file-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def install_scope_from_manifest(config_dir: Path) -> str | None:
    """Return the persisted install scope for *config_dir*."""

    scope = load_install_manifest(config_dir).get("install_scope")
    return scope if scope in {"local", "global"} else None


def _manifest_target_dir(config_dir: Path) -> Path:
    manifest_target = load_install_manifest(config_dir).get("install_target_dir")
    if isinstance(manifest_target, str) and manifest_target.strip():
        return Path(manifest_target)
    return config_dir


def _manifest_explicit_target(config_dir: Path) -> bool | None:
    explicit_target = load_install_manifest(config_dir).get("explicit_target")
    if isinstance(explicit_target, bool):
        return explicit_target
    return None


def _paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser() == right.expanduser()


def _infer_runtime_from_manifest(config_dir: Path) -> str | None:
    manifest = load_install_manifest(config_dir)
    runtime = manifest.get("runtime")
    if isinstance(runtime, str) and runtime.strip():
        return runtime.strip()

    files = manifest.get("files")
    if isinstance(files, dict):
        file_keys = [str(key) for key in files]
        for descriptor in iter_runtime_descriptors():
            if any(
                key.startswith(prefix)
                for key in file_keys
                for prefix in descriptor.manifest_file_prefixes
            ):
                return descriptor.runtime_name
    return None


def _infer_runtime_from_config_dir(config_dir: Path) -> str | None:
    for adapter in iter_adapters():
        if config_dir.name == adapter.local_config_dir_name:
            return adapter.runtime_name
    return None


def installed_runtime(config_dir: Path) -> str | None:
    """Return the runtime associated with *config_dir* when it can be inferred."""

    return _infer_runtime_from_manifest(config_dir) or _runtime_from_manifest_or_path(config_dir)


def _infer_explicit_target(
    config_dir: Path,
    *,
    adapter,
    install_scope: str | None,
    install_target: Path,
) -> bool:
    """Infer whether the install target was explicitly selected.

    This must stay independent of the current process cwd so installed hooks
    behave deterministically even when invoked from nested workspaces or other
    directories.
    """
    if install_scope == SCOPE_LOCAL:
        if not _paths_equal(install_target, config_dir):
            return True
        return config_dir.name != adapter.local_config_dir_name
    return not _paths_equal(install_target, adapter.global_config_dir)


def config_dir_has_complete_install(config_dir: Path) -> bool:
    """Return whether *config_dir* has the stable markers of a GPD install."""
    runtime = installed_runtime(config_dir)
    if runtime is not None:
        try:
            return get_adapter(runtime).has_detectable_install(config_dir)
        except KeyError:
            pass
    return (config_dir / "gpd-file-manifest.json").is_file() and (config_dir / "get-physics-done").is_dir()


def installed_update_command(config_dir: Path) -> str | None:
    """Return the bootstrap update command for the install in *config_dir*."""

    runtime = installed_runtime(config_dir)
    if runtime is None:
        return None

    scope = install_scope_from_manifest(config_dir)
    try:
        adapter = get_adapter(runtime)
    except KeyError:
        return build_runtime_install_repair_command(
            runtime,
            install_scope=scope,
            target_dir=_manifest_target_dir(config_dir),
            explicit_target=bool(_manifest_explicit_target(config_dir)),
        )

    install_target = _manifest_target_dir(config_dir)
    explicit_target = _manifest_explicit_target(config_dir)

    if explicit_target is None:
        explicit_target = _infer_explicit_target(
            config_dir,
            adapter=adapter,
            install_scope=scope,
            install_target=install_target,
        )

    return build_runtime_install_repair_command(
        runtime,
        install_scope=scope,
        target_dir=install_target,
        explicit_target=bool(explicit_target),
    )
