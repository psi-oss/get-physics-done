"""Shared helpers for installed-hook metadata."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from gpd.adapters import get_adapter, iter_adapters
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.hooks.runtime_detect import SCOPE_LOCAL, update_command_for_runtime


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

    return _infer_runtime_from_manifest(config_dir) or _infer_runtime_from_config_dir(config_dir)


def installed_update_command(config_dir: Path) -> str | None:
    """Return the bootstrap update command for the install in *config_dir*."""

    runtime = installed_runtime(config_dir)
    if runtime is None:
        return None

    scope = install_scope_from_manifest(config_dir)
    command = update_command_for_runtime(runtime, scope=scope)
    if scope != SCOPE_LOCAL:
        return command

    try:
        adapter = get_adapter(runtime)
    except KeyError:
        return command

    if config_dir.name == adapter.local_config_dir_name:
        return command
    return f"{command} --target-dir {shlex.quote(str(config_dir))}"
