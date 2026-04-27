"""Shared runtime metadata owned by the adapter layer."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath


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
    target_path_keys: tuple[str, ...] = ()
    target_root_keys: tuple[str, ...] = ()
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
class SharedInstallMetadata:
    bootstrap_package_name: str
    bootstrap_command: str
    latest_release_url: str
    releases_api_url: str
    releases_page_url: str
    install_root_dir_name: str
    manifest_name: str
    patches_dir_name: str


@dataclass(frozen=True, slots=True)
class ManagedInstallSurfacePolicy:
    gpd_content_globs: tuple[str, ...] = ()
    nested_command_globs: tuple[str, ...] = ()
    flat_command_globs: tuple[str, ...] = ()
    managed_agent_globs: tuple[str, ...] = ()


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
    child_artifact_persistence_reliability: str = "best-effort"
    supports_structured_child_results: bool = False
    continuation_surface: str = "none"
    checkpoint_stop_semantics: str = "stop"
    supports_runtime_session_payload_attribution: bool = False
    supports_agent_payload_attribution: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    runtime_name: str
    display_name: str
    priority: int
    config_dir_name: str
    install_flag: str
    launch_command: str
    adapter_module: str
    adapter_class: str
    command_prefix: str
    activation_env_vars: tuple[str, ...]
    selection_flags: tuple[str, ...]
    selection_aliases: tuple[str, ...]
    global_config: GlobalConfigPolicy
    hook_payload: HookPayloadPolicy
    capabilities: RuntimeCapabilityPolicy = RuntimeCapabilityPolicy()
    managed_install_surface: ManagedInstallSurfacePolicy = ManagedInstallSurfacePolicy()
    manifest_file_prefixes: tuple[str, ...] = ()
    native_include_support: bool = False
    agent_prompt_uses_dollar_templates: bool = False
    installer_help_example_scope: str | None = None
    validated_command_surface: str = "public_runtime_command_surface"
    public_command_surface_prefix: str = ""


_SHARED_INSTALL_METADATA = SharedInstallMetadata(
    bootstrap_package_name="get-physics-done",
    bootstrap_command="npx -y get-physics-done",
    latest_release_url="https://registry.npmjs.org/get-physics-done/latest",
    releases_api_url="https://api.github.com/repos/psi-oss/get-physics-done/releases",
    releases_page_url="https://github.com/psi-oss/get-physics-done/releases",
    install_root_dir_name="get-physics-done",
    manifest_name="gpd-file-manifest.json",
    patches_dir_name="gpd-local-patches",
)


def _runtime_catalog_schema_path() -> Path:
    return Path(__file__).with_name("runtime_catalog_schema.json")


_RUNTIME_CONFIG_SURFACE_LABEL_RE = re.compile(r"^[A-Za-z0-9._-]+:[A-Za-z0-9+._-]+$")
_RUNTIME_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_RUNTIME_FLAG_RE = re.compile(r"^--[a-z0-9][a-z0-9-]*$")
_RUNTIME_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PYTHON_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_PYTHON_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RUNTIME_CAPABILITY_BOOL_FIELDS = frozenset(
    {
        "supports_runtime_permission_sync",
        "supports_prompt_free_mode",
        "prompt_free_requires_relaunch",
        "supports_usage_tokens",
        "supports_cost_usd",
        "supports_context_meter",
        "supports_structured_child_results",
        "supports_runtime_session_payload_attribution",
        "supports_agent_payload_attribution",
    }
)
_RUNTIME_CAPABILITY_RUNTIME_SURFACE_LABEL_FIELDS = (
    "permission_surface_kind",
    "statusline_config_surface",
    "notify_config_surface",
)
_RUNTIME_CAPABILITY_OPTIONAL_STRING_FIELDS = frozenset({"prompt_free_mode_value"})
_USAGE_TOKEN_HOOK_PAYLOAD_FIELDS = ("usage_keys", "input_tokens_keys", "output_tokens_keys")


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


def _require_pattern(value: object, *, label: str, pattern: re.Pattern[str], description: str) -> str:
    normalized = _require_string(value, label=label)
    if pattern.fullmatch(normalized) is None:
        raise ValueError(f"{label} must be {description}")
    return normalized


def _require_env_var_name(value: object, *, label: str) -> str:
    return _require_pattern(value, label=label, pattern=_RUNTIME_ENV_VAR_RE, description="an environment variable name")


def _require_relative_catalog_path(value: object, *, label: str, allow_slash: bool) -> str:
    normalized = _require_string(value, label=label).replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        normalized.startswith("/")
        or normalized.startswith("~")
        or PureWindowsPath(normalized).drive
        or PureWindowsPath(normalized).is_absolute()
        or ".." in pure.parts
        or "." in pure.parts
        or (not allow_slash and len(pure.parts) != 1)
    ):
        path_kind = "relative path" if allow_slash else "relative path segment"
        raise ValueError(f"{label} must be a safe {path_kind} without traversal")
    return _require_string(value, label=label)


def _require_relative_catalog_path_tuple(
    value: object,
    *,
    label: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    items = _require_string_tuple(value, label=label, allow_empty=allow_empty)
    for index, item in enumerate(items):
        _require_relative_catalog_path(item, label=f"{label}[{index}]", allow_slash=True)
    return items


def _require_env_var_name_tuple(
    value: object,
    *,
    label: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    items = _require_string_tuple(value, label=label, allow_empty=allow_empty)
    for index, item in enumerate(items):
        _require_env_var_name(item, label=f"{label}[{index}]")
    return items


def _require_flag_tuple(
    value: object,
    *,
    label: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    items = _require_string_tuple(value, label=label, allow_empty=allow_empty)
    for index, item in enumerate(items):
        _require_pattern(item, label=f"{label}[{index}]", pattern=_RUNTIME_FLAG_RE, description="a --kebab-case flag")
    return items


def _format_quoted_disjunction(values: Iterable[str]) -> str:
    normalized = tuple(sorted({value for value in values if value}))
    if not normalized:
        return "a bundled launch-wrapper surface literal"
    if len(normalized) == 1:
        return f'"{normalized[0]}"'
    quoted = ", ".join(f'"{value}"' for value in normalized)
    return f"one of {quoted}"


def _require_runtime_surface_label(
    value: object,
    *,
    label: str,
    special_values: frozenset[str] = frozenset(),
) -> str:
    normalized = _require_string(value, label=label)
    if normalized == "none":
        return normalized
    if normalized in special_values:
        return normalized
    if _RUNTIME_CONFIG_SURFACE_LABEL_RE.fullmatch(normalized) is None:
        if special_values:
            raise ValueError(
                f'{label} must be "none", {_format_quoted_disjunction(special_values)}, or a config surface label like file:key'
            )
        raise ValueError(f'{label} must be "none" or a config surface label like file:key')
    return normalized


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


def _validated_capability_values(
    payload: dict[str, object],
    *,
    label: str,
    capability_keys: frozenset[str],
    capability_defaults: dict[str, object] | None,
    capability_enums: dict[str, frozenset[str]],
    launch_wrapper_permission_surface_kinds: frozenset[str],
) -> dict[str, object]:
    _require_allowed_keys(payload, label=label, allowed_keys=capability_keys)
    if capability_defaults is None:
        _require_keys(payload, label=label, required_keys=capability_keys)

    def _capability_value(field_name: str) -> object:
        if field_name in payload:
            return payload[field_name]
        if capability_defaults is not None:
            return capability_defaults[field_name]
        raise KeyError(field_name)

    values: dict[str, object] = {}
    for field_name, enum_values in capability_enums.items():
        value = _require_string(_capability_value(field_name), label=f"{label}.{field_name}")
        if value not in enum_values:
            allowed = ", ".join(sorted(enum_values))
            raise ValueError(f"{label}.{field_name} must be one of: {allowed}")
        values[field_name] = value

    for field_name in _RUNTIME_CAPABILITY_RUNTIME_SURFACE_LABEL_FIELDS:
        special_values = (
            launch_wrapper_permission_surface_kinds
            if field_name == "permission_surface_kind"
            else frozenset()
        )
        values[field_name] = _require_runtime_surface_label(
            _capability_value(field_name),
            label=f"{label}.{field_name}",
            special_values=special_values,
        )

    for field_name in sorted(_RUNTIME_CAPABILITY_BOOL_FIELDS):
        values[field_name] = _require_bool(_capability_value(field_name), label=f"{label}.{field_name}")

    for field_name in sorted(_RUNTIME_CAPABILITY_OPTIONAL_STRING_FIELDS):
        raw_value = _capability_value(field_name)
        values[field_name] = (
            None if raw_value is None else _require_string(raw_value, label=f"{label}.{field_name}")
        )

    validated_fields = set(values)
    for field_name in sorted(capability_keys - validated_fields):
        values[field_name] = _require_string(_capability_value(field_name), label=f"{label}.{field_name}")

    return values


def _validated_string_tuple_policy_values(
    payload: dict[str, object],
    *,
    label: str,
    policy_keys: frozenset[str],
    policy_defaults: dict[str, object] | None,
) -> dict[str, tuple[str, ...]]:
    _require_allowed_keys(payload, label=label, allowed_keys=policy_keys)
    if policy_defaults is None:
        _require_keys(payload, label=label, required_keys=policy_keys)

    values: dict[str, tuple[str, ...]] = {}
    for field_name in sorted(policy_keys):
        if field_name in payload:
            values[field_name] = _require_string_tuple(
                payload[field_name],
                label=f"{label}.{field_name}",
                allow_empty=True,
            )
            continue
        if policy_defaults is None:
            raise KeyError(field_name)
        default_value = policy_defaults[field_name]
        if not isinstance(default_value, tuple):
            raise ValueError(f"{label}.{field_name} default must be a tuple of strings")
        values[field_name] = default_value
    return values


def _validate_managed_install_surface_globs(values: dict[str, tuple[str, ...]], *, label: str) -> None:
    for field_name, patterns in values.items():
        for index, pattern in enumerate(patterns):
            normalized = pattern.replace("\\", "/")
            if (
                normalized.startswith("/")
                or normalized.startswith("~")
                or PureWindowsPath(pattern).drive
                or PureWindowsPath(pattern).is_absolute()
                or ".." in PurePosixPath(normalized).parts
            ):
                raise ValueError(
                    f"{label}.{field_name}.{index} must be a relative managed install glob without traversal"
                )


def _capability_policy_from_values(values: dict[str, object]) -> RuntimeCapabilityPolicy:
    return RuntimeCapabilityPolicy(
        permissions_surface=values["permissions_surface"],
        permission_surface_kind=values["permission_surface_kind"],
        prompt_free_mode_value=values["prompt_free_mode_value"],
        supports_runtime_permission_sync=values["supports_runtime_permission_sync"],
        supports_prompt_free_mode=values["supports_prompt_free_mode"],
        prompt_free_requires_relaunch=values["prompt_free_requires_relaunch"],
        statusline_surface=values["statusline_surface"],
        statusline_config_surface=values["statusline_config_surface"],
        notify_surface=values["notify_surface"],
        notify_config_surface=values["notify_config_surface"],
        telemetry_source=values["telemetry_source"],
        telemetry_completeness=values["telemetry_completeness"],
        supports_usage_tokens=values["supports_usage_tokens"],
        supports_cost_usd=values["supports_cost_usd"],
        supports_context_meter=values["supports_context_meter"],
        child_artifact_persistence_reliability=values["child_artifact_persistence_reliability"],
        supports_structured_child_results=values["supports_structured_child_results"],
        continuation_surface=values["continuation_surface"],
        checkpoint_stop_semantics=values["checkpoint_stop_semantics"],
        supports_runtime_session_payload_attribution=values["supports_runtime_session_payload_attribution"],
        supports_agent_payload_attribution=values["supports_agent_payload_attribution"],
    )


def _validate_capability_policy_coherence(
    policy: RuntimeCapabilityPolicy,
    *,
    label: str,
    launch_wrapper_permission_surface_kinds: frozenset[str],
) -> None:
    if policy.supports_prompt_free_mode and policy.prompt_free_mode_value is None:
        raise ValueError(
            f"{label}.prompt_free_mode_value must be a non-empty string when supports_prompt_free_mode=true"
        )
    if policy.permissions_surface == "config-file":
        if policy.permission_surface_kind == "none" or policy.permission_surface_kind in launch_wrapper_permission_surface_kinds:
            raise ValueError(f"{label}.permission_surface_kind must be a config surface label when permissions_surface=config-file")
        if not policy.supports_runtime_permission_sync:
            raise ValueError(f"{label}.supports_runtime_permission_sync must be true when permissions_surface=config-file")
    elif policy.permissions_surface == "launch-wrapper":
        if policy.permission_surface_kind not in launch_wrapper_permission_surface_kinds:
            raise ValueError(
                f"{label}.permission_surface_kind must be {_format_quoted_disjunction(launch_wrapper_permission_surface_kinds)} "
                "when permissions_surface=launch-wrapper"
            )
        if not policy.supports_runtime_permission_sync:
            raise ValueError(f"{label}.supports_runtime_permission_sync must be true when permissions_surface=launch-wrapper")
    else:
        if policy.permission_surface_kind != "none":
            raise ValueError(f'{label}.permission_surface_kind must be "none" when permissions_surface=unsupported')
        if policy.supports_runtime_permission_sync:
            raise ValueError(f"{label}.supports_runtime_permission_sync must be false when permissions_surface=unsupported")
        if policy.supports_prompt_free_mode:
            raise ValueError(f"{label}.supports_prompt_free_mode must be false when permissions_surface=unsupported")
        if policy.prompt_free_requires_relaunch:
            raise ValueError(f"{label}.prompt_free_requires_relaunch must be false when permissions_surface=unsupported")
    if not policy.supports_prompt_free_mode and policy.prompt_free_requires_relaunch:
        raise ValueError(f"{label}.prompt_free_requires_relaunch requires supports_prompt_free_mode=true")
    if policy.supports_structured_child_results and policy.continuation_surface != "explicit":
        raise ValueError(
            f"{label}.continuation_surface must be explicit when supports_structured_child_results=true"
        )
    if policy.statusline_surface == "explicit":
        if policy.statusline_config_surface == "none":
            raise ValueError(f'{label}.statusline_config_surface must not be "none" when statusline_surface=explicit')
    elif policy.statusline_config_surface != "none":
        raise ValueError(f'{label}.statusline_config_surface must be "none" when statusline_surface=none')
    if policy.notify_surface == "explicit":
        if policy.notify_config_surface == "none":
            raise ValueError(f'{label}.notify_config_surface must not be "none" when notify_surface=explicit')
    elif policy.notify_config_surface != "none":
        raise ValueError(f'{label}.notify_config_surface must be "none" when notify_surface=none')
    if policy.telemetry_completeness == "none":
        if policy.telemetry_source != "none":
            raise ValueError(f'{label}.telemetry_source must be "none" when telemetry_completeness=none')
        if policy.supports_usage_tokens:
            raise ValueError(f"{label}.supports_usage_tokens must be false when telemetry_completeness=none")
        if policy.supports_cost_usd:
            raise ValueError(f"{label}.supports_cost_usd must be false when telemetry_completeness=none")
    elif policy.telemetry_source == "none":
        raise ValueError(f'{label}.telemetry_source must not be "none" when telemetry_completeness is not none')


@lru_cache(maxsize=1)
def _load_runtime_catalog_schema_shape() -> dict[str, object]:
    schema_path = _runtime_catalog_schema_path()
    raw_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(raw_schema, dict) or not raw_schema:
        raise ValueError("runtime catalog schema must be a non-empty JSON object")

    allowed_top_level_keys = {
        "schema_version",
        "entry_required_keys",
        "entry_optional_keys",
        "global_config_keys",
        "capability_keys",
        "capability_defaults",
        "capability_enums",
        "hook_payload_keys",
        "hook_payload_defaults",
        "managed_install_surface_keys",
        "managed_install_surface_defaults",
        "install_help_example_scopes",
        "launch_wrapper_permission_surface_kinds",
    }
    unknown_top_level_keys = sorted(key for key in raw_schema if key not in allowed_top_level_keys)
    if unknown_top_level_keys:
        formatted = ", ".join(unknown_top_level_keys)
        raise ValueError(f"runtime catalog schema contains unknown key(s): {formatted}")

    schema_version = raw_schema.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError(f"Unsupported runtime catalog schema_version: {schema_version!r}")

    def _require_schema_mapping(value: object, *, label: str) -> dict[str, object]:
        if not isinstance(value, dict) or not value:
            raise ValueError(f"{label} must be a non-empty JSON object")
        return value

    entry_required_keys = frozenset(
        _require_string_tuple(raw_schema.get("entry_required_keys"), label="runtime catalog schema.entry_required_keys", allow_empty=False)
    )
    entry_optional_keys = frozenset(
        _require_string_tuple(raw_schema.get("entry_optional_keys"), label="runtime catalog schema.entry_optional_keys", allow_empty=True)
    )
    if entry_required_keys & entry_optional_keys:
        overlap = ", ".join(sorted(entry_required_keys & entry_optional_keys))
        raise ValueError(f"runtime catalog schema entry key overlap is not allowed: {overlap}")

    global_config_keys_raw = _require_schema_mapping(raw_schema.get("global_config_keys"), label="runtime catalog schema.global_config_keys")
    global_config_keys: dict[str, frozenset[str]] = {}
    for strategy, keys in global_config_keys_raw.items():
        if not isinstance(strategy, str) or not strategy or strategy.strip() != strategy:
            raise ValueError("runtime catalog schema.global_config_keys keys must be non-empty strings")
        global_config_keys[strategy] = frozenset(
            _require_string_tuple(
                keys,
                label=f"runtime catalog schema.global_config_keys.{strategy}",
                allow_empty=False,
            )
        )

    capability_keys = frozenset(
        _require_string_tuple(raw_schema.get("capability_keys"), label="runtime catalog schema.capability_keys", allow_empty=False)
    )
    capability_defaults_raw = _require_schema_mapping(
        raw_schema.get("capability_defaults"),
        label="runtime catalog schema.capability_defaults",
    )
    unknown_default_keys = sorted(key for key in capability_defaults_raw if key not in capability_keys)
    missing_default_keys = sorted(key for key in capability_keys if key not in capability_defaults_raw)
    if unknown_default_keys:
        raise ValueError(
            "runtime catalog schema.capability_defaults contains unknown key(s): "
            + ", ".join(unknown_default_keys)
        )
    if missing_default_keys:
        raise ValueError(
            "runtime catalog schema.capability_defaults is missing key(s): "
            + ", ".join(missing_default_keys)
        )

    capability_enums_raw = _require_schema_mapping(raw_schema.get("capability_enums"), label="runtime catalog schema.capability_enums")
    capability_enums: dict[str, frozenset[str]] = {}
    for field_name, values in capability_enums_raw.items():
        if not isinstance(field_name, str) or not field_name or field_name.strip() != field_name:
            raise ValueError("runtime catalog schema.capability_enums keys must be non-empty strings")
        capability_enums[field_name] = frozenset(
            _require_string_tuple(
                values,
                label=f"runtime catalog schema.capability_enums.{field_name}",
                allow_empty=False,
            )
        )

    launch_wrapper_permission_surface_kinds = frozenset(
        _require_string_tuple(
            raw_schema.get("launch_wrapper_permission_surface_kinds"),
            label="runtime catalog schema.launch_wrapper_permission_surface_kinds",
            allow_empty=False,
        )
    )
    default_capability_values = _validated_capability_values(
        dict(capability_defaults_raw),
        label="runtime catalog schema.capability_defaults",
        capability_keys=capability_keys,
        capability_defaults=None,
        capability_enums=capability_enums,
        launch_wrapper_permission_surface_kinds=launch_wrapper_permission_surface_kinds,
    )
    _validate_capability_policy_coherence(
        _capability_policy_from_values(default_capability_values),
        label="runtime catalog schema.capability_defaults",
        launch_wrapper_permission_surface_kinds=launch_wrapper_permission_surface_kinds,
    )

    hook_payload_keys = frozenset(
        _require_string_tuple(raw_schema.get("hook_payload_keys"), label="runtime catalog schema.hook_payload_keys", allow_empty=False)
    )
    hook_payload_defaults_raw = _require_schema_mapping(
        raw_schema.get("hook_payload_defaults"),
        label="runtime catalog schema.hook_payload_defaults",
    )
    unknown_hook_payload_default_keys = sorted(key for key in hook_payload_defaults_raw if key not in hook_payload_keys)
    missing_hook_payload_default_keys = sorted(key for key in hook_payload_keys if key not in hook_payload_defaults_raw)
    if unknown_hook_payload_default_keys:
        raise ValueError(
            "runtime catalog schema.hook_payload_defaults contains unknown key(s): "
            + ", ".join(unknown_hook_payload_default_keys)
        )
    if missing_hook_payload_default_keys:
        raise ValueError(
            "runtime catalog schema.hook_payload_defaults is missing key(s): "
            + ", ".join(missing_hook_payload_default_keys)
        )
    hook_payload_defaults = _validated_string_tuple_policy_values(
        dict(hook_payload_defaults_raw),
        label="runtime catalog schema.hook_payload_defaults",
        policy_keys=hook_payload_keys,
        policy_defaults=None,
    )
    managed_install_surface_keys = frozenset(
        _require_string_tuple(
            raw_schema.get("managed_install_surface_keys"),
            label="runtime catalog schema.managed_install_surface_keys",
            allow_empty=False,
        )
    )
    managed_install_surface_defaults_raw = _require_schema_mapping(
        raw_schema.get("managed_install_surface_defaults"),
        label="runtime catalog schema.managed_install_surface_defaults",
    )
    unknown_managed_surface_default_keys = sorted(
        key for key in managed_install_surface_defaults_raw if key not in managed_install_surface_keys
    )
    missing_managed_surface_default_keys = sorted(
        key for key in managed_install_surface_keys if key not in managed_install_surface_defaults_raw
    )
    if unknown_managed_surface_default_keys:
        raise ValueError(
            "runtime catalog schema.managed_install_surface_defaults contains unknown key(s): "
            + ", ".join(unknown_managed_surface_default_keys)
        )
    if missing_managed_surface_default_keys:
        raise ValueError(
            "runtime catalog schema.managed_install_surface_defaults is missing key(s): "
            + ", ".join(missing_managed_surface_default_keys)
        )
    managed_install_surface_defaults = _validated_string_tuple_policy_values(
        dict(managed_install_surface_defaults_raw),
        label="runtime catalog schema.managed_install_surface_defaults",
        policy_keys=managed_install_surface_keys,
        policy_defaults=None,
    )
    install_help_example_scopes = frozenset(
        _require_string_tuple(
            raw_schema.get("install_help_example_scopes"),
            label="runtime catalog schema.install_help_example_scopes",
            allow_empty=False,
        )
    )

    return {
        "schema_version": schema_version,
        "entry_required_keys": entry_required_keys,
        "entry_optional_keys": entry_optional_keys,
        "global_config_keys": global_config_keys,
        "capability_keys": capability_keys,
        "capability_defaults": default_capability_values,
        "capability_enums": capability_enums,
        "hook_payload_keys": hook_payload_keys,
        "hook_payload_defaults": hook_payload_defaults,
        "managed_install_surface_keys": managed_install_surface_keys,
        "managed_install_surface_defaults": managed_install_surface_defaults,
        "install_help_example_scopes": install_help_example_scopes,
        "launch_wrapper_permission_surface_kinds": launch_wrapper_permission_surface_kinds,
    }


def _catalog_path() -> Path:
    return Path(__file__).with_name("runtime_catalog.json")


_RUNTIME_CATALOG_SHAPE = _load_runtime_catalog_schema_shape()
_RUNTIME_ENTRY_REQUIRED_KEYS = _RUNTIME_CATALOG_SHAPE["entry_required_keys"]
_RUNTIME_ENTRY_OPTIONAL_KEYS = _RUNTIME_CATALOG_SHAPE["entry_optional_keys"]
_RUNTIME_ENTRY_ALLOWED_KEYS = _RUNTIME_ENTRY_REQUIRED_KEYS | _RUNTIME_ENTRY_OPTIONAL_KEYS
_RUNTIME_GLOBAL_CONFIG_STRATEGIES = frozenset(_RUNTIME_CATALOG_SHAPE["global_config_keys"].keys())
_RUNTIME_INSTALL_HELP_EXAMPLE_SCOPES = _RUNTIME_CATALOG_SHAPE["install_help_example_scopes"]
_RUNTIME_VALIDATED_COMMAND_SURFACE_RE = re.compile(r"^public_runtime_[a-z0-9_]+_command$")
_RUNTIME_COMMAND_PREFIX_RE = re.compile(r"^[/$][A-Za-z0-9][A-Za-z0-9._-]*(?::|-)$")
_RUNTIME_CAPABILITY_ENUMS = _RUNTIME_CATALOG_SHAPE["capability_enums"]
_RUNTIME_GLOBAL_CONFIG_KEYS = _RUNTIME_CATALOG_SHAPE["global_config_keys"]
_RUNTIME_CAPABILITY_KEYS = _RUNTIME_CATALOG_SHAPE["capability_keys"]
_RUNTIME_CAPABILITY_DEFAULTS = _RUNTIME_CATALOG_SHAPE["capability_defaults"]
_RUNTIME_HOOK_PAYLOAD_KEYS = _RUNTIME_CATALOG_SHAPE["hook_payload_keys"]
_RUNTIME_HOOK_PAYLOAD_DEFAULTS = _RUNTIME_CATALOG_SHAPE["hook_payload_defaults"]
_RUNTIME_MANAGED_INSTALL_SURFACE_KEYS = _RUNTIME_CATALOG_SHAPE["managed_install_surface_keys"]
_RUNTIME_MANAGED_INSTALL_SURFACE_DEFAULTS = _RUNTIME_CATALOG_SHAPE["managed_install_surface_defaults"]
_RUNTIME_LAUNCH_WRAPPER_PERMISSION_SURFACE_KINDS = _RUNTIME_CATALOG_SHAPE["launch_wrapper_permission_surface_kinds"]


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
            env_var=_require_env_var_name(payload.get("env_var"), label=f"{label}.env_var"),
            home_subpath=_require_relative_catalog_path(
                payload.get("home_subpath"),
                label=f"{label}.home_subpath",
                allow_slash=True,
            ),
        )

    return GlobalConfigPolicy(
        strategy=strategy,
        env_dir_var=_require_env_var_name(payload.get("env_dir_var"), label=f"{label}.env_dir_var"),
        env_file_var=_require_env_var_name(payload.get("env_file_var"), label=f"{label}.env_file_var"),
        xdg_subdir=_require_relative_catalog_path(
            payload.get("xdg_subdir"),
            label=f"{label}.xdg_subdir",
            allow_slash=True,
        ),
        home_subpath=_require_relative_catalog_path(
            payload.get("home_subpath"),
            label=f"{label}.home_subpath",
            allow_slash=True,
        ),
    )


def _parse_capabilities(
    entry: object,
    *,
    label: str,
    launch_wrapper_permission_surface_kinds: frozenset[str],
) -> RuntimeCapabilityPolicy:
    payload = _require_mapping(entry, label=label)
    policy = _capability_policy_from_values(
        _validated_capability_values(
            payload,
            label=label,
            capability_keys=_RUNTIME_CAPABILITY_KEYS,
            capability_defaults=_RUNTIME_CAPABILITY_DEFAULTS,
            capability_enums=_RUNTIME_CAPABILITY_ENUMS,
            launch_wrapper_permission_surface_kinds=launch_wrapper_permission_surface_kinds,
        )
    )
    _validate_capability_policy_coherence(
        policy,
        label=label,
        launch_wrapper_permission_surface_kinds=launch_wrapper_permission_surface_kinds,
    )
    return policy


def _validate_runtime_catalog_uniqueness(descriptors: list[RuntimeDescriptor]) -> None:
    runtime_names: dict[str, str] = {}
    install_flags: dict[str, str] = {}
    selection_flags: dict[str, str] = {}
    selection_tokens: dict[str, str] = {}

    for descriptor in descriptors:
        if descriptor.runtime_name in runtime_names:
            raise ValueError(f"runtime catalog contains duplicate runtime_name {descriptor.runtime_name!r}")
        runtime_names[descriptor.runtime_name] = descriptor.runtime_name

        existing_install_flag_runtime = install_flags.get(descriptor.install_flag)
        if existing_install_flag_runtime is not None:
            raise ValueError(
                f"runtime catalog contains duplicate install_flag {descriptor.install_flag!r} for "
                f"{existing_install_flag_runtime!r} and {descriptor.runtime_name!r}"
            )
        install_flags[descriptor.install_flag] = descriptor.runtime_name

        for flag in descriptor.selection_flags:
            existing_flag_runtime = selection_flags.get(flag)
            if existing_flag_runtime is not None:
                raise ValueError(
                    f"runtime catalog contains duplicate selection flag {flag!r} for "
                    f"{existing_flag_runtime!r} and {descriptor.runtime_name!r}"
                )
            selection_flags[flag] = descriptor.runtime_name

        selection_tokens_for_descriptor = {
            descriptor.runtime_name,
            descriptor.display_name,
            descriptor.launch_command,
            *descriptor.selection_aliases,
            *(flag.removeprefix("--") for flag in descriptor.selection_flags),
            descriptor.install_flag.removeprefix("--"),
        }
        for token in selection_tokens_for_descriptor:
            normalized_token = token.casefold()
            existing_token_runtime = selection_tokens.get(normalized_token)
            if existing_token_runtime is not None and existing_token_runtime != descriptor.runtime_name:
                raise ValueError(
                    f"runtime catalog contains duplicate runtime selection token {token!r} for "
                    f"{existing_token_runtime!r} and {descriptor.runtime_name!r}"
                )
            selection_tokens[normalized_token] = descriptor.runtime_name


def _validate_runtime_catalog_help_example_scopes(descriptors: list[RuntimeDescriptor]) -> None:
    scope_owners: dict[str, str] = {}
    for descriptor in descriptors:
        scope = descriptor.installer_help_example_scope
        if scope is None:
            continue
        existing_owner = scope_owners.get(scope)
        if existing_owner is not None and existing_owner != descriptor.runtime_name:
            raise ValueError(
                "runtime catalog contains duplicate installer_help_example_scope "
                f"{scope!r} for {existing_owner!r} and {descriptor.runtime_name!r}"
            )
        scope_owners[scope] = descriptor.runtime_name


def _parse_install_help_example_scope(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    scope = _require_string(value, label=label)
    if scope not in _RUNTIME_INSTALL_HELP_EXAMPLE_SCOPES:
        allowed = ", ".join(sorted(_RUNTIME_INSTALL_HELP_EXAMPLE_SCOPES))
        raise ValueError(f"{label} must be one of: {allowed}")
    return scope


def _parse_validated_command_surface(value: object, *, label: str) -> str:
    if value is None:
        return "public_runtime_command_surface"
    surface = _require_string(value, label=label)
    if _RUNTIME_VALIDATED_COMMAND_SURFACE_RE.fullmatch(surface) is None:
        raise ValueError(f"{label} must match /^public_runtime_[a-z0-9_]+_command$/")
    return surface


def _parse_public_command_surface_prefix(
    value: object,
    *,
    label: str,
    command_prefix: str,
) -> str:
    prefix = command_prefix if value is None else _require_string(value, label=label)
    if _RUNTIME_COMMAND_PREFIX_RE.fullmatch(prefix) is None:
        raise ValueError(f"{label} must be a slash or dollar command prefix ending in ':' or '-'")
    return prefix


def _parse_command_prefix(value: object, *, label: str) -> str:
    prefix = _require_string(value, label=label)
    if _RUNTIME_COMMAND_PREFIX_RE.fullmatch(prefix) is None:
        raise ValueError(f"{label} must be a slash or dollar command prefix ending in ':' or '-'")
    return prefix


def _parse_hook_payload(entry: object, *, label: str) -> HookPayloadPolicy:
    payload = _require_mapping(entry, label=label)
    return HookPayloadPolicy(
        **_validated_string_tuple_policy_values(
            payload,
            label=label,
            policy_keys=_RUNTIME_HOOK_PAYLOAD_KEYS,
            policy_defaults=_RUNTIME_HOOK_PAYLOAD_DEFAULTS,
        )
    )


def _parse_managed_install_surface(entry: object, *, label: str) -> ManagedInstallSurfacePolicy:
    payload = _require_mapping(entry, label=label)
    values = _validated_string_tuple_policy_values(
        payload,
        label=label,
        policy_keys=_RUNTIME_MANAGED_INSTALL_SURFACE_KEYS,
        policy_defaults=_RUNTIME_MANAGED_INSTALL_SURFACE_DEFAULTS,
    )
    _validate_managed_install_surface_globs(values, label=label)
    return ManagedInstallSurfacePolicy(
        **values
    )


def _validate_runtime_descriptor_capability_contract(
    descriptor: RuntimeDescriptor,
    *,
    label: str,
) -> None:
    def _require_hook_payload_fields(capability_field: str, field_names: tuple[str, ...]) -> None:
        missing = [field_name for field_name in field_names if not getattr(descriptor.hook_payload, field_name)]
        if missing:
            formatted = ", ".join(f"{label}.hook_payload.{field_name}" for field_name in missing)
            raise ValueError(f"{label}.capabilities.{capability_field} requires {formatted}")

    if descriptor.capabilities.statusline_surface == "explicit":
        _require_hook_payload_fields("statusline_surface", ("model_keys",))
    if descriptor.capabilities.notify_surface == "explicit":
        _require_hook_payload_fields("notify_surface", ("notify_event_types",))
    if descriptor.capabilities.telemetry_source == "notify-hook":
        if descriptor.capabilities.notify_surface != "explicit":
            raise ValueError(f"{label}.capabilities.telemetry_source requires {label}.capabilities.notify_surface=explicit")
        _require_hook_payload_fields("telemetry_source", ("notify_event_types",))
    if descriptor.capabilities.supports_usage_tokens:
        if descriptor.capabilities.telemetry_source == "none":
            raise ValueError(
                f'{label}.capabilities.supports_usage_tokens requires {label}.capabilities.telemetry_source!="none"'
            )
        _require_hook_payload_fields("supports_usage_tokens", _USAGE_TOKEN_HOOK_PAYLOAD_FIELDS)
    if descriptor.capabilities.supports_cost_usd:
        if descriptor.capabilities.telemetry_source == "none":
            raise ValueError(
                f'{label}.capabilities.supports_cost_usd requires {label}.capabilities.telemetry_source!="none"'
            )
        _require_hook_payload_fields("supports_cost_usd", ("cost_usd_keys",))
    if descriptor.capabilities.supports_context_meter:
        if descriptor.capabilities.statusline_surface != "explicit":
            raise ValueError(f"{label}.capabilities.supports_context_meter requires {label}.capabilities.statusline_surface=explicit")
        _require_hook_payload_fields(
            "supports_context_meter",
            ("context_window_size_keys", "context_remaining_keys"),
        )
    if (
        descriptor.capabilities.supports_runtime_session_payload_attribution
        != descriptor.hook_payload.supports_runtime_session_payload_attribution
    ):
        raise ValueError(
            f"{label}.capabilities.supports_runtime_session_payload_attribution must match "
            f"{label}.hook_payload.runtime_session_id_keys"
        )
    if (
        descriptor.capabilities.supports_agent_payload_attribution
        != descriptor.hook_payload.supports_agent_payload_attribution
    ):
        raise ValueError(
            f"{label}.capabilities.supports_agent_payload_attribution must match "
            f"{label}.hook_payload.agent_id_keys/agent_name_keys/agent_scope_keys"
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
        command_prefix = _parse_command_prefix(payload["command_prefix"], label=f"{label}.command_prefix")
        descriptor = RuntimeDescriptor(
            runtime_name=_require_pattern(
                payload["runtime_name"],
                label=f"{label}.runtime_name",
                pattern=_RUNTIME_ID_RE,
                description="a lowercase runtime id",
            ),
            display_name=_require_string(payload["display_name"], label=f"{label}.display_name"),
            priority=_require_int(payload["priority"], label=f"{label}.priority"),
            config_dir_name=_require_relative_catalog_path(
                payload["config_dir_name"],
                label=f"{label}.config_dir_name",
                allow_slash=False,
            ),
            install_flag=_require_pattern(
                payload["install_flag"],
                label=f"{label}.install_flag",
                pattern=_RUNTIME_FLAG_RE,
                description="a --kebab-case flag",
            ),
            launch_command=_require_string(payload["launch_command"], label=f"{label}.launch_command"),
            adapter_module=_require_pattern(
                payload["adapter_module"],
                label=f"{label}.adapter_module",
                pattern=_PYTHON_MODULE_RE,
                description="a Python module path",
            ),
            adapter_class=_require_pattern(
                payload["adapter_class"],
                label=f"{label}.adapter_class",
                pattern=_PYTHON_IDENTIFIER_RE,
                description="a Python class name",
            ),
            command_prefix=command_prefix,
            activation_env_vars=_require_env_var_name_tuple(
                payload["activation_env_vars"],
                label=f"{label}.activation_env_vars",
                allow_empty=False,
            ),
            selection_flags=_require_flag_tuple(
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
            capabilities=_parse_capabilities(
                payload["capabilities"],
                label=f"{label}.capabilities",
                launch_wrapper_permission_surface_kinds=_RUNTIME_LAUNCH_WRAPPER_PERMISSION_SURFACE_KINDS,
            ),
            hook_payload=_parse_hook_payload(payload["hook_payload"], label=f"{label}.hook_payload"),
            managed_install_surface=_parse_managed_install_surface(
                payload["managed_install_surface"] if "managed_install_surface" in payload else {},
                label=f"{label}.managed_install_surface",
            ),
            manifest_file_prefixes=_require_relative_catalog_path_tuple(
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
            installer_help_example_scope=_parse_install_help_example_scope(
                payload.get("installer_help_example_scope"),
                label=f"{label}.installer_help_example_scope",
            ),
            validated_command_surface=_parse_validated_command_surface(
                payload.get("validated_command_surface"),
                label=f"{label}.validated_command_surface",
            ),
            public_command_surface_prefix=_parse_public_command_surface_prefix(
                payload.get("public_command_surface_prefix"),
                label=f"{label}.public_command_surface_prefix",
                command_prefix=command_prefix,
            ),
        )
        _validate_runtime_descriptor_capability_contract(descriptor, label=label)
        descriptors.append(descriptor)
    descriptors.sort(key=lambda descriptor: (descriptor.priority, descriptor.runtime_name))
    _validate_runtime_catalog_uniqueness(descriptors)
    _validate_runtime_catalog_help_example_scopes(descriptors)
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


def get_shared_install_metadata() -> SharedInstallMetadata:
    """Return the canonical shared install/update metadata."""
    return _SHARED_INSTALL_METADATA


def _runtime_managed_install_surface_policy(descriptor: RuntimeDescriptor) -> ManagedInstallSurfacePolicy:
    install_root = get_shared_install_metadata().install_root_dir_name
    configured = descriptor.managed_install_surface
    return ManagedInstallSurfacePolicy(
        gpd_content_globs=_merge_unique(((f"{install_root}/**/*",), configured.gpd_content_globs)),
        nested_command_globs=configured.nested_command_globs,
        flat_command_globs=configured.flat_command_globs,
        managed_agent_globs=configured.managed_agent_globs,
    )


def get_managed_install_surface_policy(runtime: str | None = None) -> ManagedInstallSurfacePolicy:
    """Return managed install-surface detection globs for one runtime or the merged catalog."""
    descriptors = (get_runtime_descriptor(runtime),) if runtime is not None else iter_runtime_descriptors()
    policies = tuple(_runtime_managed_install_surface_policy(descriptor) for descriptor in descriptors)
    return ManagedInstallSurfacePolicy(
        gpd_content_globs=_merge_unique(policy.gpd_content_globs for policy in policies),
        nested_command_globs=_merge_unique(policy.nested_command_globs for policy in policies),
        flat_command_globs=_merge_unique(policy.flat_command_globs for policy in policies),
        managed_agent_globs=_merge_unique(policy.managed_agent_globs for policy in policies),
    )


def iter_runtime_descriptors() -> tuple[RuntimeDescriptor, ...]:
    return _load_catalog()


def get_runtime_help_example_runtime(scope: str) -> str | None:
    """Return the runtime tagged as the install-help example for *scope*."""

    if scope not in _RUNTIME_INSTALL_HELP_EXAMPLE_SCOPES:
        allowed = ", ".join(sorted(_RUNTIME_INSTALL_HELP_EXAMPLE_SCOPES))
        raise ValueError(f"scope must be one of: {allowed}")
    for descriptor in iter_runtime_descriptors():
        if descriptor.installer_help_example_scope == scope:
            return descriptor.runtime_name
    return None


def list_runtime_names() -> list[str]:
    return [descriptor.runtime_name for descriptor in iter_runtime_descriptors()]


def normalize_runtime_name(value: str | None) -> str | None:
    """Resolve a runtime id, display name, alias, launch command, or install flag to a canonical runtime name."""
    if not isinstance(value, str):
        return None

    normalized = value.strip().casefold()
    if not normalized:
        return None

    for descriptor in iter_runtime_descriptors():
        if normalized in {
            descriptor.runtime_name.casefold(),
            descriptor.display_name.casefold(),
            descriptor.launch_command.casefold(),
            descriptor.install_flag.casefold(),
            *(flag.casefold() for flag in descriptor.selection_flags),
            *(alias.casefold() for alias in descriptor.selection_aliases),
        }:
            return descriptor.runtime_name
    return None


def get_runtime_descriptor(runtime: str) -> RuntimeDescriptor:
    for descriptor in iter_runtime_descriptors():
        if descriptor.runtime_name == runtime:
            return descriptor
    supported = ", ".join(list_runtime_names())
    raise KeyError(f"Unknown runtime {runtime!r}. Supported: {supported}")


def get_hook_payload_policy(runtime: str | None = None) -> HookPayloadPolicy:
    if runtime is not None:
        return get_runtime_descriptor(runtime).hook_payload

    descriptors = tuple(iter_runtime_descriptors())
    return HookPayloadPolicy(
        **{
            field.name: _merge_unique(getattr(descriptor.hook_payload, field.name) for descriptor in descriptors)
            for field in fields(HookPayloadPolicy)
        }
    )


def get_runtime_capabilities(runtime: str) -> RuntimeCapabilityPolicy:
    """Return the static runtime capability contract declared for one runtime."""
    return get_runtime_descriptor(runtime).capabilities


def _paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve(strict=False) == right.expanduser().resolve(strict=False)
    except OSError:
        return left.expanduser() == right.expanduser()


def _normalize_global_config_dir(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _home_global_config_dir(home: Path | None, home_subpath: str) -> Path:
    return _normalize_global_config_dir((home or Path.home()) / home_subpath)


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
                return _normalize_global_config_dir(Path(override))
        return _home_global_config_dir(home, policy.home_subpath)

    if policy.strategy == "xdg_app":
        if policy.env_dir_var:
            override = env.get(policy.env_dir_var)
            if override:
                return _normalize_global_config_dir(Path(override))
        if policy.env_file_var:
            config_path = env.get(policy.env_file_var)
            if config_path:
                return _normalize_global_config_dir(Path(config_path).expanduser().parent)
        xdg_home = env.get("XDG_CONFIG_HOME")
        if xdg_home and policy.xdg_subdir:
            return _normalize_global_config_dir(Path(xdg_home) / policy.xdg_subdir)
        return _home_global_config_dir(home, policy.home_subpath)

    raise ValueError(f"Unsupported global config strategy: {policy.strategy}")


def resolve_global_config_dir_candidates(
    descriptor: RuntimeDescriptor,
    *,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[Path, ...]:
    """Return every authoritative global config dir for the current environment.

    Some flows need to recognize both the canonical home-based location and the
    currently effective env-overridden location as global runtime roots. That
    lets local/runtime ownership checks stay fail-closed when manifests drift,
    without treating one authoritative global root as a workspace-local install.
    """

    candidates: list[Path] = []
    for candidate in (
        resolve_global_config_dir(descriptor, home=home, environ=environ),
        resolve_global_config_dir(descriptor, home=home, environ={}),
    ):
        if any(_paths_equal(candidate, existing) for existing in candidates):
            continue
        candidates.append(candidate)
    return tuple(candidates)


__all__ = [
    "GlobalConfigPolicy",
    "HookPayloadPolicy",
    "ManagedInstallSurfacePolicy",
    "RuntimeCapabilityPolicy",
    "RuntimeDescriptor",
    "SharedInstallMetadata",
    "get_hook_payload_policy",
    "get_managed_install_surface_policy",
    "get_runtime_capabilities",
    "get_runtime_descriptor",
    "get_runtime_help_example_runtime",
    "get_shared_install_metadata",
    "iter_runtime_descriptors",
    "list_runtime_names",
    "normalize_runtime_name",
    "resolve_global_config_dir_candidates",
    "resolve_global_config_dir",
]
