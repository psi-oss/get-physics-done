"""Shared helpers for installed-hook metadata."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import build_runtime_install_repair_command
from gpd.adapters.runtime_catalog import iter_runtime_descriptors, resolve_global_config_dir
from gpd.hooks.runtime_detect import (
    RUNTIME_UNKNOWN,
    SCOPE_GLOBAL,
    SCOPE_LOCAL,
    _runtime_from_manifest_or_path,
    normalize_runtime_name,
)


def load_install_manifest(config_dir: Path) -> dict[str, object]:
    """Return the parsed install manifest for *config_dir* when available."""

    manifest_path = config_dir / "gpd-file-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_install_manifest_state(config_dir: Path) -> tuple[str, dict[str, object]]:
    """Return the manifest parse state and payload for *config_dir*.

    The state is one of ``missing``, ``corrupt``, ``invalid``, or ``ok``.
    ``ok`` means the manifest parsed as a mapping; the payload is the parsed
    dict in that case and ``{}`` otherwise.
    """

    manifest_path = config_dir / "gpd-file-manifest.json"
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "missing", {}
    except (OSError, json.JSONDecodeError):
        return "corrupt", {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return "corrupt", {}

    if not isinstance(payload, dict):
        return "invalid", {}
    return "ok", payload


def install_scope_from_manifest(config_dir: Path) -> str | None:
    """Return the persisted install scope for *config_dir*."""

    scope = load_install_manifest(config_dir).get("install_scope")
    return scope if scope in {"local", "global"} else None


def _install_scope_from_installed_update_workflow(config_dir: Path) -> str | None:
    """Return the persisted install scope from the installed update workflow."""

    update_workflow = config_dir / "get-physics-done" / "workflows" / "update.md"
    try:
        content = update_workflow.read_text(encoding="utf-8")
    except OSError:
        return None

    if 'INSTALL_SCOPE="--local"' in content:
        return SCOPE_LOCAL
    if 'INSTALL_SCOPE="--global"' in content:
        return SCOPE_GLOBAL
    return None


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


def _has_generic_complete_install(config_dir: Path) -> bool:
    """Return whether *config_dir* has runtime-agnostic GPD install markers."""
    manifest_path = config_dir / "gpd-file-manifest.json"
    gpd_dir = config_dir / "get-physics-done"
    return manifest_path.is_file() and gpd_dir.is_dir()


def _paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser() == right.expanduser()


def _infer_runtime_from_manifest(config_dir: Path) -> str | None:
    manifest = load_install_manifest(config_dir)
    runtime = manifest.get("runtime")
    if "runtime" in manifest:
        if not isinstance(runtime, str):
            runtime = None
        else:
            normalized_runtime = runtime.strip()
            if normalized_runtime:
                canonical_runtime = normalize_runtime_name(normalized_runtime)
                if canonical_runtime is not None:
                    return canonical_runtime

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


def installed_runtime(config_dir: Path) -> str | None:
    """Return the runtime associated with *config_dir* when it can be inferred."""

    manifest_runtime = _infer_runtime_from_manifest(config_dir)
    if manifest_runtime is not None:
        return manifest_runtime

    path_runtime = _runtime_from_manifest_or_path(config_dir, allow_local_path_fallback=False)
    if path_runtime == RUNTIME_UNKNOWN:
        return None
    return path_runtime


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
    canonical_global_dir = resolve_global_config_dir(adapter.runtime_descriptor, home=Path.home(), environ={})
    return not _paths_equal(install_target, canonical_global_dir)


def _detect_install_scope_fallback(
    config_dir: Path,
    *,
    runtime: str,
    install_target: Path,
) -> str | None:
    """Return a stable install-scope fallback when the manifest omits it."""

    persisted_scope = _install_scope_from_installed_update_workflow(config_dir)
    if persisted_scope is not None:
        return persisted_scope

    try:
        adapter = get_adapter(runtime)
    except KeyError:
        return None

    canonical_global_dir = resolve_global_config_dir(adapter.runtime_descriptor, home=Path.home(), environ={})
    if _paths_equal(install_target, canonical_global_dir) or _paths_equal(config_dir, canonical_global_dir):
        return SCOPE_GLOBAL

    if _paths_equal(install_target, config_dir) and config_dir.name == adapter.local_config_dir_name:
        return SCOPE_LOCAL

    return None


def config_dir_has_complete_install(config_dir: Path) -> bool:
    """Return whether *config_dir* has the stable markers of a GPD install."""
    manifest = load_install_manifest(config_dir)
    runtime = installed_runtime(config_dir)
    if runtime is not None:
        try:
            return get_adapter(runtime).has_complete_install(config_dir)
        except KeyError:
            return False
    if "runtime" in manifest:
        return False
    return _has_generic_complete_install(config_dir)


def installed_update_command(config_dir: Path) -> str | None:
    """Return the bootstrap update command for the install in *config_dir*."""

    runtime = installed_runtime(config_dir)
    if runtime is None:
        return None

    install_target = _manifest_target_dir(config_dir)
    scope = install_scope_from_manifest(config_dir) or _detect_install_scope_fallback(
        config_dir,
        runtime=runtime,
        install_target=install_target,
    )
    try:
        adapter = get_adapter(runtime)
    except KeyError:
        return build_runtime_install_repair_command(
            runtime,
            install_scope=scope,
            target_dir=install_target,
            explicit_target=bool(_manifest_explicit_target(config_dir)),
        )

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
