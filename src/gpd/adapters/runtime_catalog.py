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
    runtime_session_id_keys: tuple[str, ...] = ()
    model_keys: tuple[str, ...] = ()
    provider_keys: tuple[str, ...] = ()
    usage_keys: tuple[str, ...] = ()
    input_tokens_keys: tuple[str, ...] = ()
    output_tokens_keys: tuple[str, ...] = ()
    total_tokens_keys: tuple[str, ...] = ()
    cached_input_tokens_keys: tuple[str, ...] = ()
    cache_write_input_tokens_keys: tuple[str, ...] = ()
    cost_usd_keys: tuple[str, ...] = ()
    agent_id_keys: tuple[str, ...] = ()
    agent_name_keys: tuple[str, ...] = ()
    agent_scope_keys: tuple[str, ...] = ()
    context_window_size_keys: tuple[str, ...] = ()
    context_remaining_keys: tuple[str, ...] = ()

    @property
    def supports_runtime_session_payload_attribution(self) -> bool:
        """Whether the runtime payload can expose a runtime-owned session id."""
        return bool(self.runtime_session_id_keys)

    @property
    def supports_agent_payload_attribution(self) -> bool:
        """Whether the runtime payload can expose agent/subagent attribution."""
        return bool(self.agent_id_keys or self.agent_name_keys or self.agent_scope_keys)


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityPolicy:
    permissions_surface: str = "unsupported"
    permission_surface_kind: str = "none"
    prompt_free_mode_value: str | None = None
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


_RUNTIME_ENTRY_REQUIRED_KEYS = frozenset(
    {
        "runtime_name",
        "display_name",
        "priority",
        "config_dir_name",
        "install_flag",
        "launch_command",
        "command_prefix",
        "activation_env_vars",
        "selection_flags",
        "selection_aliases",
        "global_config",
        "capabilities",
        "hook_payload",
    }
)
_RUNTIME_ENTRY_OPTIONAL_KEYS = frozenset(
    {
        "manifest_file_prefixes",
        "native_include_support",
        "agent_prompt_uses_dollar_templates",
    }
)
_RUNTIME_ENTRY_ALLOWED_KEYS = _RUNTIME_ENTRY_REQUIRED_KEYS | _RUNTIME_ENTRY_OPTIONAL_KEYS
_RUNTIME_GLOBAL_CONFIG_STRATEGIES = frozenset({"env_or_home", "xdg_app"})
_RUNTIME_CAPABILITY_ENUMS = {
    "permissions_surface": frozenset({"config-file", "launch-wrapper", "unsupported"}),
    "permission_surface_kind": frozenset(
        {
            "settings.json:permissions.defaultMode",
            "managed-launcher-wrapper",
            "config.toml:approval_policy+sandbox_mode",
            "opencode.json:permission",
            "none",
        }
    ),
    "statusline_surface": frozenset({"explicit", "none"}),
    "statusline_config_surface": frozenset({"settings.json:statusLine", "none"}),
    "notify_surface": frozenset({"explicit", "none"}),
    "notify_config_surface": frozenset({"config.toml:notify", "none"}),
    "telemetry_source": frozenset({"notify-hook", "none"}),
    "telemetry_completeness": frozenset({"best-effort", "none"}),
}
_RUNTIME_GLOBAL_CONFIG_KEYS = {
    "env_or_home": frozenset({"strategy", "env_var", "home_subpath"}),
    "xdg_app": frozenset({"strategy", "env_dir_var", "env_file_var", "xdg_subdir", "home_subpath"}),
}
_RUNTIME_CAPABILITY_KEYS = frozenset(
    {
        "permissions_surface",
        "permission_surface_kind",
        "prompt_free_mode_value",
        "supports_runtime_permission_sync",
        "supports_prompt_free_mode",
        "prompt_free_requires_relaunch",
        "statusline_surface",
        "statusline_config_surface",
        "notify_surface",
        "notify_config_surface",
        "telemetry_source",
        "telemetry_completeness",
        "supports_usage_tokens",
        "supports_cost_usd",
        "supports_context_meter",
    }
)
_RUNTIME_HOOK_PAYLOAD_KEYS = frozenset(
    {
        "notify_event_types",
        "workspace_keys",
        "project_dir_keys",
        "runtime_session_id_keys",
        "model_keys",
        "provider_keys",
        "usage_keys",
        "input_tokens_keys",
        "output_tokens_keys",
        "total_tokens_keys",
        "cached_input_tokens_keys",
        "cache_write_input_tokens_keys",
        "cost_usd_keys",
        "agent_id_keys",
        "agent_name_keys",
        "agent_scope_keys",
        "context_window_size_keys",
        "context_remaining_keys",
    }
)


def _require_mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _require_allowed_keys(
    payload: dict[str, object],
    *,
    label: str,
    allowed_keys: frozenset[str],
) -> None:
    unknown_keys = sorted(key for key in payload if key not in allowed_keys)
    if unknown_keys:
        raise ValueError(f"{label} contains unknown key(s): {', '.join(unknown_keys)}")


def _require_keys(
    payload: dict[str, object],
    *,
    label: str,
    required_keys: frozenset[str],
) -> None:
    missing_keys = sorted(key for key in required_keys if key not in payload)
    if missing_keys:
        raise ValueError(f"{label} is missing required key(s): {', '.join(missing_keys)}")


def _require_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")
    return value


def _require_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return value


def _require_string_tuple(
    value: object,
    *,
    label: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings")
    if not value and not allow_empty:
        raise ValueError(f"{label} must contain at least one string")

    items: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        normalized = _require_string(item, label=item_label)
        if normalized in seen:
            raise ValueError(f"{label} must not contain duplicate values")
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


def _parse_global_config(entry: dict[str, object], *, label: str) -> GlobalConfigPolicy:
    payload = _require_mapping(entry, label=label)
    strategy = _require_string(payload.get("strategy"), label=f"{label}.strategy")
    if strategy not in _RUNTIME_GLOBAL_CONFIG_STRATEGIES:
        raise ValueError(f"{label}.strategy must be one of: {', '.join(sorted(_RUNTIME_GLOBAL_CONFIG_STRATEGIES))}")

    required_keys = _RUNTIME_GLOBAL_CONFIG_KEYS[strategy]
    _require_allowed_keys(payload, label=label, allowed_keys=required_keys)
    _require_keys(payload, label=label, required_keys=required_keys)

    if strategy == "env_or_home":
        return GlobalConfigPolicy(
            strategy=strategy,
            env_var=_require_string(payload.get("env_var"), label=f"{label}.env_var"),
            home_subpath=_require_string(payload.get("home_subpath"), label=f"{label}.home_subpath"),
        )

    return GlobalConfigPolicy(
        strategy=strategy,
        env_dir_var=_require_string(payload.get("env_dir_var"), label=f"{label}.env_dir_var"),
        env_file_var=_require_string(payload.get("env_file_var"), label=f"{label}.env_file_var"),
        xdg_subdir=_require_string(payload.get("xdg_subdir"), label=f"{label}.xdg_subdir"),
        home_subpath=_require_string(payload.get("home_subpath"), label=f"{label}.home_subpath"),
    )


def _parse_capabilities(entry: object, *, label: str) -> RuntimeCapabilityPolicy:
    payload = _require_mapping(entry, label=label)
    _require_allowed_keys(payload, label=label, allowed_keys=_RUNTIME_CAPABILITY_KEYS)
    _require_keys(payload, label=label, required_keys=_RUNTIME_CAPABILITY_KEYS)

    for field_name, enum_values in _RUNTIME_CAPABILITY_ENUMS.items():
        value = _require_string(payload.get(field_name), label=f"{label}.{field_name}")
        if value not in enum_values:
            allowed = ", ".join(sorted(enum_values))
            raise ValueError(f"{label}.{field_name} must be one of: {allowed}")

    prompt_free_mode_value = _require_string(payload.get("prompt_free_mode_value"), label=f"{label}.prompt_free_mode_value")
    return RuntimeCapabilityPolicy(
        permissions_surface=_require_string(payload.get("permissions_surface"), label=f"{label}.permissions_surface"),
        permission_surface_kind=_require_string(
            payload.get("permission_surface_kind"), label=f"{label}.permission_surface_kind"
        ),
        prompt_free_mode_value=prompt_free_mode_value,
        supports_runtime_permission_sync=_require_bool(
            payload.get("supports_runtime_permission_sync"),
            label=f"{label}.supports_runtime_permission_sync",
        ),
        supports_prompt_free_mode=_require_bool(
            payload.get("supports_prompt_free_mode"),
            label=f"{label}.supports_prompt_free_mode",
        ),
        prompt_free_requires_relaunch=_require_bool(
            payload.get("prompt_free_requires_relaunch"),
            label=f"{label}.prompt_free_requires_relaunch",
        ),
        statusline_surface=_require_string(payload.get("statusline_surface"), label=f"{label}.statusline_surface"),
        statusline_config_surface=_require_string(
            payload.get("statusline_config_surface"), label=f"{label}.statusline_config_surface"
        ),
        notify_surface=_require_string(payload.get("notify_surface"), label=f"{label}.notify_surface"),
        notify_config_surface=_require_string(
            payload.get("notify_config_surface"), label=f"{label}.notify_config_surface"
        ),
        telemetry_source=_require_string(payload.get("telemetry_source"), label=f"{label}.telemetry_source"),
        telemetry_completeness=_require_string(
            payload.get("telemetry_completeness"), label=f"{label}.telemetry_completeness"
        ),
        supports_usage_tokens=_require_bool(payload.get("supports_usage_tokens"), label=f"{label}.supports_usage_tokens"),
        supports_cost_usd=_require_bool(payload.get("supports_cost_usd"), label=f"{label}.supports_cost_usd"),
        supports_context_meter=_require_bool(
            payload.get("supports_context_meter"), label=f"{label}.supports_context_meter"
        ),
    )


def _parse_hook_payload(entry: object, *, label: str) -> HookPayloadPolicy:
    payload = _require_mapping(entry, label=label)
    _require_allowed_keys(payload, label=label, allowed_keys=_RUNTIME_HOOK_PAYLOAD_KEYS)
    _require_keys(payload, label=label, required_keys=_RUNTIME_HOOK_PAYLOAD_KEYS)

    return HookPayloadPolicy(
        notify_event_types=_require_string_tuple(payload.get("notify_event_types"), label=f"{label}.notify_event_types", allow_empty=True),
        workspace_keys=_require_string_tuple(payload.get("workspace_keys"), label=f"{label}.workspace_keys", allow_empty=True),
        project_dir_keys=_require_string_tuple(payload.get("project_dir_keys"), label=f"{label}.project_dir_keys", allow_empty=True),
        runtime_session_id_keys=_require_string_tuple(
            payload.get("runtime_session_id_keys"), label=f"{label}.runtime_session_id_keys", allow_empty=True
        ),
        model_keys=_require_string_tuple(payload.get("model_keys"), label=f"{label}.model_keys", allow_empty=True),
        provider_keys=_require_string_tuple(payload.get("provider_keys"), label=f"{label}.provider_keys", allow_empty=True),
        usage_keys=_require_string_tuple(payload.get("usage_keys"), label=f"{label}.usage_keys", allow_empty=True),
        input_tokens_keys=_require_string_tuple(payload.get("input_tokens_keys"), label=f"{label}.input_tokens_keys", allow_empty=True),
        output_tokens_keys=_require_string_tuple(payload.get("output_tokens_keys"), label=f"{label}.output_tokens_keys", allow_empty=True),
        total_tokens_keys=_require_string_tuple(payload.get("total_tokens_keys"), label=f"{label}.total_tokens_keys", allow_empty=True),
        cached_input_tokens_keys=_require_string_tuple(
            payload.get("cached_input_tokens_keys"), label=f"{label}.cached_input_tokens_keys", allow_empty=True
        ),
        cache_write_input_tokens_keys=_require_string_tuple(
            payload.get("cache_write_input_tokens_keys"), label=f"{label}.cache_write_input_tokens_keys", allow_empty=True
        ),
        cost_usd_keys=_require_string_tuple(payload.get("cost_usd_keys"), label=f"{label}.cost_usd_keys", allow_empty=True),
        agent_id_keys=_require_string_tuple(payload.get("agent_id_keys"), label=f"{label}.agent_id_keys", allow_empty=True),
        agent_name_keys=_require_string_tuple(payload.get("agent_name_keys"), label=f"{label}.agent_name_keys", allow_empty=True),
        agent_scope_keys=_require_string_tuple(payload.get("agent_scope_keys"), label=f"{label}.agent_scope_keys", allow_empty=True),
        context_window_size_keys=_require_string_tuple(
            payload.get("context_window_size_keys"), label=f"{label}.context_window_size_keys", allow_empty=True
        ),
        context_remaining_keys=_require_string_tuple(
            payload.get("context_remaining_keys"), label=f"{label}.context_remaining_keys", allow_empty=True
        ),
    )


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[RuntimeDescriptor, ...]:
    raw_entries = json.loads(_catalog_path().read_text(encoding="utf-8"))
    if not isinstance(raw_entries, list):
        raise ValueError("runtime catalog must be a JSON array")
    descriptors: list[RuntimeDescriptor] = []
    for index, entry in enumerate(raw_entries):
        label = f"runtime catalog entry {index}"
        payload = _require_mapping(entry, label=label)
        _require_allowed_keys(payload, label=label, allowed_keys=_RUNTIME_ENTRY_ALLOWED_KEYS)
        _require_keys(payload, label=label, required_keys=_RUNTIME_ENTRY_REQUIRED_KEYS)
        descriptors.append(
            RuntimeDescriptor(
                runtime_name=_require_string(payload["runtime_name"], label=f"{label}.runtime_name"),
                display_name=_require_string(payload["display_name"], label=f"{label}.display_name"),
                priority=_require_int(payload["priority"], label=f"{label}.priority"),
                config_dir_name=_require_string(payload["config_dir_name"], label=f"{label}.config_dir_name"),
                install_flag=_require_string(payload["install_flag"], label=f"{label}.install_flag"),
                launch_command=_require_string(payload["launch_command"], label=f"{label}.launch_command"),
                command_prefix=_require_string(payload["command_prefix"], label=f"{label}.command_prefix"),
                activation_env_vars=_require_string_tuple(
                    payload["activation_env_vars"],
                    label=f"{label}.activation_env_vars",
                    allow_empty=False,
                ),
                selection_flags=_require_string_tuple(
                    payload["selection_flags"],
                    label=f"{label}.selection_flags",
                    allow_empty=False,
                ),
                selection_aliases=_require_string_tuple(
                    payload["selection_aliases"],
                    label=f"{label}.selection_aliases",
                    allow_empty=False,
                ),
                global_config=_parse_global_config(payload["global_config"], label=f"{label}.global_config"),
                capabilities=_parse_capabilities(payload["capabilities"], label=f"{label}.capabilities"),
                hook_payload=_parse_hook_payload(payload["hook_payload"], label=f"{label}.hook_payload"),
                manifest_file_prefixes=_require_string_tuple(
                    payload["manifest_file_prefixes"]
                    if "manifest_file_prefixes" in payload
                    else [],
                    label=f"{label}.manifest_file_prefixes",
                    allow_empty=True,
                ),
                native_include_support=_require_bool(
                    payload.get("native_include_support", False),
                    label=f"{label}.native_include_support",
                ),
                agent_prompt_uses_dollar_templates=_require_bool(
                    payload.get("agent_prompt_uses_dollar_templates", False),
                    label=f"{label}.agent_prompt_uses_dollar_templates",
                ),
            )
        )
    descriptors.sort(key=lambda descriptor: (descriptor.priority, descriptor.runtime_name))
    return tuple(descriptors)


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
        runtime_session_id_keys=_merge_unique(
            descriptor.hook_payload.runtime_session_id_keys for descriptor in descriptors
        ),
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
        agent_id_keys=_merge_unique(descriptor.hook_payload.agent_id_keys for descriptor in descriptors),
        agent_name_keys=_merge_unique(descriptor.hook_payload.agent_name_keys for descriptor in descriptors),
        agent_scope_keys=_merge_unique(descriptor.hook_payload.agent_scope_keys for descriptor in descriptors),
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
