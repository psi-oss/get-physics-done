"""Shared test helpers for runtime hook suites."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterable
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import build_runtime_install_repair_command
from gpd.adapters.runtime_catalog import get_shared_install_metadata, iter_runtime_descriptors
from tests.runtime_install_helpers import seed_complete_runtime_install

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_SHARED_INSTALL = get_shared_install_metadata()


def runtime_env_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for env_var in descriptor.activation_env_vars:
            prefixes.add(env_var)
            prefixes.add(env_var.rsplit("_", 1)[0] if "_" in env_var else env_var)
    return tuple(sorted(prefixes, key=len, reverse=True))


def runtime_env_vars_to_clear(*, extra_env_vars: Iterable[str] = ()) -> set[str]:
    env_vars = {"GPD_ACTIVE_RUNTIME", "XDG_CONFIG_HOME", *extra_env_vars}
    for descriptor in _RUNTIME_DESCRIPTORS:
        global_config = descriptor.global_config
        for env_var in (global_config.env_var, global_config.env_dir_var, global_config.env_file_var):
            if env_var:
                env_vars.add(env_var)
    return env_vars


def clear_runtime_env(monkeypatch, *, extra_env_vars: Iterable[str] = ()) -> None:
    env_prefixes = runtime_env_prefixes()
    env_vars_to_clear = runtime_env_vars_to_clear(extra_env_vars=extra_env_vars)
    for key in list(os.environ):
        if key.startswith(env_prefixes) or key in env_vars_to_clear:
            monkeypatch.delenv(key, raising=False)


def clean_runtime_env(*, extra_env_vars: Iterable[str] = ()) -> dict[str, str]:
    env_prefixes = runtime_env_prefixes()
    env_vars_to_clear = runtime_env_vars_to_clear(extra_env_vars=extra_env_vars)
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(env_prefixes) and key not in env_vars_to_clear
    }


def _infer_runtime_from_config_dir(config_dir: Path) -> str | None:
    for descriptor in _RUNTIME_DESCRIPTORS:
        candidate = descriptor.runtime_name
        adapter = get_adapter(candidate)
        if config_dir.name in {adapter.config_dir_name, adapter.local_config_dir_name}:
            return candidate
    return None


def _overlay_tree(source: Path, destination: Path) -> None:
    for entry in source.rglob("*"):
        relative = entry.relative_to(source)
        target = destination / relative
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target)


def mark_complete_install(config_dir: Path, *, runtime: str | None = None, install_scope: str = "local") -> None:
    """Create a minimal complete-install marker tree for one runtime config dir."""
    config_dir.mkdir(parents=True, exist_ok=True)
    resolved_runtime = runtime or _infer_runtime_from_config_dir(config_dir)
    if resolved_runtime is not None:
        adapter = get_adapter(resolved_runtime)
        preexisting_install_tree = config_dir / "get-physics-done"
        manifest_path = config_dir / _SHARED_INSTALL.manifest_name
        stash_dir: Path | None = None
        if preexisting_install_tree.exists() and not manifest_path.exists():
            stash_dir = config_dir.parent / f".{config_dir.name}-preinstall-stash"
            if stash_dir.exists():
                shutil.rmtree(stash_dir)
            shutil.move(str(preexisting_install_tree), stash_dir)
        try:
            seed_complete_runtime_install(
                config_dir,
                runtime=resolved_runtime,
                install_scope=install_scope,
                home=config_dir.parent if install_scope == "global" else None,
                explicit_target=config_dir.name != adapter.config_dir_name,
            )
            if stash_dir is not None:
                _overlay_tree(stash_dir, config_dir / "get-physics-done")
                shutil.rmtree(stash_dir)
        except Exception:
            if stash_dir is not None and not preexisting_install_tree.exists():
                shutil.move(str(stash_dir), preexisting_install_tree)
            raise
        return

    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / _SHARED_INSTALL.manifest_name).write_text(
        json.dumps({"install_scope": install_scope}),
        encoding="utf-8",
    )


def repair_command(runtime: str, *, install_scope: str, target_dir: Path, explicit_target: bool) -> str:
    """Build the expected runtime-specific repair command for hook tests."""
    return build_runtime_install_repair_command(
        runtime,
        install_scope=install_scope,
        target_dir=target_dir,
        explicit_target=explicit_target,
    )
