"""Shared runtime metadata owned by the adapter layer."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
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
class HookPayloadPolicy:
    notify_event_types: tuple[str, ...] = ()
    workspace_keys: tuple[str, ...] = ()
    project_dir_keys: tuple[str, ...] = ()
    model_keys: tuple[str, ...] = ()
    provider_keys: tuple[str, ...] = ()
    usage_keys: tuple[str, ...] = ()
    input_tokens_keys: tuple[str, ...] = ()
    output_tokens_keys: tuple[str, ...] = ()
    total_tokens_keys: tuple[str, ...] = ()
    cached_input_tokens_keys: tuple[str, ...] = ()
    cache_write_input_tokens_keys: tuple[str, ...] = ()
    cost_usd_keys: tuple[str, ...] = ()
    context_window_size_keys: tuple[str, ...] = ()
    context_remaining_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityPolicy:
    permissions_surface: str = "unsupported"
    permission_surface_kind: str = "none"
    supports_runtime_permission_sync: bool = False
    supports_prompt_free_mode: bool = False
    prompt_free_requires_relaunch: bool = False
    statusline_surface: str = "none"
    statusline_config_surface: str = "none"
    notify_surface: str = "none"
    notify_config_surface: str = "none"
    telemetry_source: str = "none"
    telemetry_completeness: str = "none"
    supports_usage_tokens: bool = False
    supports_cost_usd: bool = False
    supports_context_meter: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    runtime_name: str
    display_name: str
    priority: int
    config_dir_name: str
    install_flag: str
    launch_command: str
    command_prefix: str
    activation_env_vars: tuple[str, ...]
    selection_flags: tuple[str, ...]
    selection_aliases: tuple[str, ...]
    global_config: GlobalConfigPolicy
    hook_payload: HookPayloadPolicy
    capabilities: RuntimeCapabilityPolicy = RuntimeCapabilityPolicy()
    manifest_file_prefixes: tuple[str, ...] = ()
    native_include_support: bool = False
    agent_prompt_uses_dollar_templates: bool = False


def _catalog_path() -> Path:
    return Path(__file__).with_name("runtime_catalog.json")


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[RuntimeDescriptor, ...]:
    raw_entries = json.loads(_catalog_path().read_text(encoding="utf-8"))
    descriptors: list[RuntimeDescriptor] = []
    for entry in raw_entries:
        capability_entry = entry.get("capabilities", {})
        hook_payload_entry = entry.get("hook_payload", {})
        descriptors.append(
            RuntimeDescriptor(
                runtime_name=str(entry["runtime_name"]),
                display_name=str(entry["display_name"]),
                priority=int(entry.get("priority", 100)),
                config_dir_name=str(entry["config_dir_name"]),
                install_flag=str(entry["install_flag"]),
                launch_command=str(entry["launch_command"]),
                command_prefix=str(entry["command_prefix"]),
                native_include_support=bool(entry.get("native_include_support", False)),
                activation_env_vars=tuple(str(value) for value in entry.get("activation_env_vars", [])),
                selection_flags=tuple(str(value) for value in entry.get("selection_flags", [])),
                selection_aliases=tuple(str(value) for value in entry.get("selection_aliases", [])),
                manifest_file_prefixes=_tuple_of_str(entry.get("manifest_file_prefixes")),
                global_config=GlobalConfigPolicy(
                    strategy=str(entry["global_config"]["strategy"]),
                    env_var=_optional_str(entry["global_config"].get("env_var")),
                    env_dir_var=_optional_str(entry["global_config"].get("env_dir_var")),
                    env_file_var=_optional_str(entry["global_config"].get("env_file_var")),
                    xdg_subdir=_optional_str(entry["global_config"].get("xdg_subdir")),
                    home_subpath=str(entry["global_config"].get("home_subpath", "")),
                ),
                capabilities=RuntimeCapabilityPolicy(
                    permissions_surface=str(capability_entry.get("permissions_surface", "unsupported")),
                    permission_surface_kind=str(capability_entry.get("permission_surface_kind", "none")),
                    supports_runtime_permission_sync=bool(
                        capability_entry.get("supports_runtime_permission_sync", False)
                    ),
                    supports_prompt_free_mode=bool(capability_entry.get("supports_prompt_free_mode", False)),
                    prompt_free_requires_relaunch=bool(
                        capability_entry.get("prompt_free_requires_relaunch", False)
                    ),
                    statusline_surface=str(capability_entry.get("statusline_surface", "none")),
                    statusline_config_surface=str(capability_entry.get("statusline_config_surface", "none")),
                    notify_surface=str(capability_entry.get("notify_surface", "none")),
                    notify_config_surface=str(capability_entry.get("notify_config_surface", "none")),
                    telemetry_source=str(capability_entry.get("telemetry_source", "none")),
                    telemetry_completeness=str(capability_entry.get("telemetry_completeness", "none")),
                    supports_usage_tokens=bool(capability_entry.get("supports_usage_tokens", False)),
                    supports_cost_usd=bool(capability_entry.get("supports_cost_usd", False)),
                    supports_context_meter=bool(capability_entry.get("supports_context_meter", False)),
                ),
                hook_payload=HookPayloadPolicy(
                    notify_event_types=_tuple_of_str_from_entry(hook_payload_entry, "notify_event_types"),
                    workspace_keys=_tuple_of_str_from_entry(
                        hook_payload_entry,
                        "workspace_keys",
                        ("current_dir", "cwd", "path", "workspace_dir"),
                    ),
                    project_dir_keys=_tuple_of_str_from_entry(
                        hook_payload_entry,
                        "project_dir_keys",
                        ("project_dir",),
                    ),
                    model_keys=_tuple_of_str_from_entry(
                        hook_payload_entry,
                        "model_keys",
                        ("display_name", "name", "id"),
                    ),
                    provider_keys=_tuple_of_str_from_entry(hook_payload_entry, "provider_keys"),
                    usage_keys=_tuple_of_str_from_entry(hook_payload_entry, "usage_keys"),
                    input_tokens_keys=_tuple_of_str_from_entry(hook_payload_entry, "input_tokens_keys"),
                    output_tokens_keys=_tuple_of_str_from_entry(hook_payload_entry, "output_tokens_keys"),
                    total_tokens_keys=_tuple_of_str_from_entry(hook_payload_entry, "total_tokens_keys"),
                    cached_input_tokens_keys=_tuple_of_str_from_entry(
                        hook_payload_entry,
                        "cached_input_tokens_keys",
                    ),
                    cache_write_input_tokens_keys=_tuple_of_str_from_entry(
                        hook_payload_entry,
                        "cache_write_input_tokens_keys",
                    ),
                    cost_usd_keys=_tuple_of_str_from_entry(hook_payload_entry, "cost_usd_keys"),
                    context_window_size_keys=_tuple_of_str_from_entry(
                        hook_payload_entry,
                        "context_window_size_keys",
                        ("context_window_size",),
                    ),
                    context_remaining_keys=_tuple_of_str_from_entry(
                        hook_payload_entry,
                        "context_remaining_keys",
                        ("remaining_percentage", "remainingPercent", "remaining"),
                    ),
                ),
                agent_prompt_uses_dollar_templates=bool(entry.get("agent_prompt_uses_dollar_templates", False)),
            )
        )
    descriptors.sort(key=lambda descriptor: (descriptor.priority, descriptor.runtime_name))
    return tuple(descriptors)


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _tuple_of_str(value: object, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        result = tuple(item for item in value if isinstance(item, str) and item)
        if result:
            return result
    return default


def _tuple_of_str_from_entry(
    entry: dict[str, object],
    key: str,
    default: tuple[str, ...] = (),
) -> tuple[str, ...]:
    if key not in entry:
        return default
    value = entry.get(key)
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str) and item)
    return default


def _merge_unique(groups: Iterable[tuple[str, ...]]) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for value in group:
            if value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return tuple(merged)


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


def get_hook_payload_policy(runtime: str | None = None) -> HookPayloadPolicy:
    if runtime:
        try:
            return get_runtime_descriptor(runtime).hook_payload
        except KeyError:
            pass

    descriptors = iter_runtime_descriptors()
    return HookPayloadPolicy(
        notify_event_types=_merge_unique(descriptor.hook_payload.notify_event_types for descriptor in descriptors),
        workspace_keys=_merge_unique(descriptor.hook_payload.workspace_keys for descriptor in descriptors),
        project_dir_keys=_merge_unique(descriptor.hook_payload.project_dir_keys for descriptor in descriptors),
        model_keys=_merge_unique(descriptor.hook_payload.model_keys for descriptor in descriptors),
        provider_keys=_merge_unique(descriptor.hook_payload.provider_keys for descriptor in descriptors),
        usage_keys=_merge_unique(descriptor.hook_payload.usage_keys for descriptor in descriptors),
        input_tokens_keys=_merge_unique(descriptor.hook_payload.input_tokens_keys for descriptor in descriptors),
        output_tokens_keys=_merge_unique(descriptor.hook_payload.output_tokens_keys for descriptor in descriptors),
        total_tokens_keys=_merge_unique(descriptor.hook_payload.total_tokens_keys for descriptor in descriptors),
        cached_input_tokens_keys=_merge_unique(
            descriptor.hook_payload.cached_input_tokens_keys for descriptor in descriptors
        ),
        cache_write_input_tokens_keys=_merge_unique(
            descriptor.hook_payload.cache_write_input_tokens_keys for descriptor in descriptors
        ),
        cost_usd_keys=_merge_unique(descriptor.hook_payload.cost_usd_keys for descriptor in descriptors),
        context_window_size_keys=_merge_unique(
            descriptor.hook_payload.context_window_size_keys for descriptor in descriptors
        ),
        context_remaining_keys=_merge_unique(descriptor.hook_payload.context_remaining_keys for descriptor in descriptors),
    )


def get_runtime_capabilities(runtime: str) -> RuntimeCapabilityPolicy:
    """Return the static runtime capability contract declared for one runtime."""
    return get_runtime_descriptor(runtime).capabilities


def resolve_global_config_dir(
    descriptor: RuntimeDescriptor,
    *,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    env = os.environ if environ is None else environ
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
    "HookPayloadPolicy",
    "RuntimeCapabilityPolicy",
    "RuntimeDescriptor",
    "get_hook_payload_policy",
    "get_runtime_capabilities",
    "get_runtime_descriptor",
    "iter_runtime_descriptors",
    "list_runtime_names",
    "resolve_global_config_dir",
]
