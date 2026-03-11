"""Shared runtime metadata owned by the adapter layer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GlobalConfigPolicy:
    strategy: str
    env_var: str | None = None
    env_dir_var: str | None = None
    env_file_var: str | None = None
    xdg_subdir: str | None = None
    home_subpath: str = ""


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    runtime_name: str
    display_name: str
    config_dir_name: str
    install_flag: str
    command_prefix: str
    activation_env_vars: tuple[str, ...]
    selection_flags: tuple[str, ...]
    selection_aliases: tuple[str, ...]
    global_config: GlobalConfigPolicy
    agent_prompt_uses_dollar_templates: bool = False


def _catalog_path() -> Path:
    return Path(__file__).with_name("runtime_catalog.json")


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[RuntimeDescriptor, ...]:
    raw_entries = json.loads(_catalog_path().read_text(encoding="utf-8"))
    descriptors: list[RuntimeDescriptor] = []
    for entry in raw_entries:
        descriptors.append(
            RuntimeDescriptor(
                runtime_name=str(entry["runtime_name"]),
                display_name=str(entry["display_name"]),
                config_dir_name=str(entry["config_dir_name"]),
                install_flag=str(entry["install_flag"]),
                command_prefix=str(entry["command_prefix"]),
                activation_env_vars=tuple(str(value) for value in entry.get("activation_env_vars", [])),
                selection_flags=tuple(str(value) for value in entry.get("selection_flags", [])),
                selection_aliases=tuple(str(value) for value in entry.get("selection_aliases", [])),
                global_config=GlobalConfigPolicy(
                    strategy=str(entry["global_config"]["strategy"]),
                    env_var=_optional_str(entry["global_config"].get("env_var")),
                    env_dir_var=_optional_str(entry["global_config"].get("env_dir_var")),
                    env_file_var=_optional_str(entry["global_config"].get("env_file_var")),
                    xdg_subdir=_optional_str(entry["global_config"].get("xdg_subdir")),
                    home_subpath=str(entry["global_config"].get("home_subpath", "")),
                ),
                agent_prompt_uses_dollar_templates=bool(entry.get("agent_prompt_uses_dollar_templates", False)),
            )
        )
    return tuple(descriptors)


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def iter_runtime_descriptors() -> tuple[RuntimeDescriptor, ...]:
    return _load_catalog()


def list_runtime_names() -> list[str]:
    return [descriptor.runtime_name for descriptor in iter_runtime_descriptors()]


def get_runtime_descriptor(runtime: str) -> RuntimeDescriptor:
    for descriptor in iter_runtime_descriptors():
        if descriptor.runtime_name == runtime:
            return descriptor
    supported = ", ".join(list_runtime_names())
    raise KeyError(f"Unknown runtime {runtime!r}. Supported: {supported}")


def resolve_global_config_dir(
    descriptor: RuntimeDescriptor,
    *,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    env = environ or os.environ
    policy = descriptor.global_config
    if policy.strategy == "env_or_home":
        if policy.env_var:
            override = env.get(policy.env_var)
            if override:
                return Path(override).expanduser()
        return (home or Path.home()) / policy.home_subpath

    if policy.strategy == "xdg_app":
        if policy.env_dir_var:
            override = env.get(policy.env_dir_var)
            if override:
                return Path(override).expanduser()
        if policy.env_file_var:
            config_path = env.get(policy.env_file_var)
            if config_path:
                return Path(config_path).expanduser().parent
        xdg_home = env.get("XDG_CONFIG_HOME")
        if xdg_home and policy.xdg_subdir:
            return Path(xdg_home).expanduser() / policy.xdg_subdir
        return (home or Path.home()) / policy.home_subpath

    raise ValueError(f"Unsupported global config strategy: {policy.strategy}")


__all__ = [
    "GlobalConfigPolicy",
    "RuntimeDescriptor",
    "get_runtime_descriptor",
    "iter_runtime_descriptors",
    "list_runtime_names",
    "resolve_global_config_dir",
]
