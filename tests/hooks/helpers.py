"""Shared test helpers for runtime hook suites."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import build_runtime_install_repair_command
from gpd.adapters.runtime_catalog import iter_runtime_descriptors

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


def runtime_env_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for env_var in descriptor.activation_env_vars:
            prefixes.add(env_var)
            prefixes.add(env_var.rsplit("_", 1)[0] if "_" in env_var else env_var)
    return tuple(sorted(prefixes, key=len, reverse=True))


def runtime_env_vars_to_clear() -> set[str]:
    env_vars = {"GPD_ACTIVE_RUNTIME", "XDG_CONFIG_HOME"}
    for descriptor in _RUNTIME_DESCRIPTORS:
        global_config = descriptor.global_config
        for env_var in (global_config.env_var, global_config.env_dir_var, global_config.env_file_var):
            if env_var:
                env_vars.add(env_var)
    return env_vars


def clean_runtime_env() -> dict[str, str]:
    env_vars_to_clear = runtime_env_vars_to_clear()
    return {key: value for key, value in os.environ.items() if key not in env_vars_to_clear}


def _infer_runtime_from_config_dir(config_dir: Path) -> str | None:
    for descriptor in _RUNTIME_DESCRIPTORS:
        candidate = descriptor.runtime_name
        adapter = get_adapter(candidate)
        if config_dir.name in {adapter.config_dir_name, adapter.local_config_dir_name}:
            return candidate
    return None


def mark_complete_install(config_dir: Path, *, runtime: str | None = None, install_scope: str = "local") -> None:
    """Create a minimal complete-install marker tree for one runtime config dir."""
    config_dir.mkdir(parents=True, exist_ok=True)
    resolved_runtime = runtime or _infer_runtime_from_config_dir(config_dir)
    if resolved_runtime is not None:
        adapter = get_adapter(resolved_runtime)
        for relpath in adapter.install_completeness_relpaths():
            if relpath == "gpd-file-manifest.json":
                continue
            artifact = config_dir / relpath
            artifact.parent.mkdir(parents=True, exist_ok=True)
            if artifact.suffix:
                artifact.write_text("{}\n" if artifact.suffix == ".json" else "# test\n", encoding="utf-8")
            else:
                artifact.mkdir(parents=True, exist_ok=True)
        if resolved_runtime == "codex":
            skills_dir = config_dir.parent / ".agents" / "skills"
            help_skill_dir = skills_dir / "gpd-help"
            help_skill_dir.mkdir(parents=True, exist_ok=True)
            (help_skill_dir / "SKILL.md").write_text("# test\n", encoding="utf-8")
    else:
        (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {"install_scope": install_scope}
    if resolved_runtime is not None:
        adapter = get_adapter(resolved_runtime)
        explicit_target = config_dir.name != adapter.config_dir_name
        manifest["runtime"] = resolved_runtime
        manifest["explicit_target"] = explicit_target
        manifest["install_target_dir"] = str(config_dir)
        if resolved_runtime == "codex":
            manifest["codex_skills_dir"] = str(config_dir.parent / ".agents" / "skills")
            manifest["codex_generated_skill_dirs"] = ["gpd-help"]
    (config_dir / "gpd-file-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def repair_command(runtime: str, *, install_scope: str, target_dir: Path, explicit_target: bool) -> str:
    """Build the expected runtime-specific repair command for hook tests."""
    return build_runtime_install_repair_command(
        runtime,
        install_scope=install_scope,
        target_dir=target_dir,
        explicit_target=explicit_target,
    )
