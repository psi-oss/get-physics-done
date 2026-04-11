"""Shared runtime metadata owned by the adapter layer."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, fields
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


_HOOK_PAYLOAD_FIELD_NAMES = tuple(field.name for field in fields(HookPayloadPolicy))


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


_RUNTIME_CAPABILITY_FIELD_NAMES = tuple(field.name for field in fields(RuntimeCapabilityPolicy))


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    runtime_name: str
    adapter_module: str
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
    managed_install_surface: str = "nested_commands"
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


def _load_json_strict_no_duplicate_keys(path: Path) -> object:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        payload: dict[str, object] = {}
        for key, value in pairs:
            if key in payload:
                raise ValueError(f"{path.name} contains duplicate JSON key: {key}")
            payload[key] = value
        return payload

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)


@lru_cache(maxsize=1)
def _load_runtime_catalog_schema_shape() -> dict[str, object]:
    schema_path = _runtime_catalog_schema_path()
    raw_schema = _load_json_strict_no_duplicate_keys(schema_path)
    if not isinstance(raw_schema, dict) or not raw_schema:
        raise ValueError("runtime catalog schema must be a non-empty JSON object")

    allowed_top_level_keys = {
        "schema_version",
        "entry_required_keys",
        "entry_optional_keys",
        "global_config_keys",
        "capability_keys",
        "capability_enums",
        "hook_payload_keys",
        "managed_install_surfaces",
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
            if not isinstance(item, str) or not item or item.strip() != item:
                raise ValueError(f"{item_label} must be a non-empty string")
            if item in seen:
                raise ValueError(f"{label} must not contain duplicate values")
            seen.add(item)
            items.append(item)
        return tuple(items)

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

    hook_payload_keys = frozenset(
        _require_string_tuple(raw_schema.get("hook_payload_keys"), label="runtime catalog schema.hook_payload_keys", allow_empty=False)
    )
    managed_install_surfaces = frozenset(
        _require_string_tuple(
            raw_schema.get("managed_install_surfaces"),
            label="runtime catalog schema.managed_install_surfaces",
            allow_empty=False,
        )
    )
    install_help_example_scopes = frozenset(
        _require_string_tuple(
            raw_schema.get("install_help_example_scopes"),
            label="runtime catalog schema.install_help_example_scopes",
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

    return {
        "schema_version": schema_version,
        "entry_required_keys": entry_required_keys,
        "entry_optional_keys": entry_optional_keys,
        "global_config_keys": global_config_keys,
        "capability_keys": capability_keys,
        "capability_enums": capability_enums,
        "hook_payload_keys": hook_payload_keys,
        "managed_install_surfaces": managed_install_surfaces,
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
_RUNTIME_CONFIG_SURFACE_LABEL_RE = re.compile(r"^[A-Za-z0-9._-]+:[A-Za-z0-9+._-]+$")
_RUNTIME_CAPABILITY_ENUMS = _RUNTIME_CATALOG_SHAPE["capability_enums"]
_RUNTIME_GLOBAL_CONFIG_KEYS = _RUNTIME_CATALOG_SHAPE["global_config_keys"]
_RUNTIME_CAPABILITY_KEYS = _RUNTIME_CATALOG_SHAPE["capability_keys"]
_RUNTIME_HOOK_PAYLOAD_KEYS = _RUNTIME_CATALOG_SHAPE["hook_payload_keys"]
_RUNTIME_MANAGED_INSTALL_SURFACES = _RUNTIME_CATALOG_SHAPE["managed_install_surfaces"]
_RUNTIME_LAUNCH_WRAPPER_PERMISSION_SURFACE_KINDS = _RUNTIME_CATALOG_SHAPE["launch_wrapper_permission_surface_kinds"]


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


def _require_string_member(value: object, *, label: str, allowed_values: Iterable[str]) -> str:
    item = _require_string(value, label=label)
    allowed = frozenset(allowed_values)
    if item not in allowed:
        raise ValueError(f"{label} must be {_format_quoted_disjunction(allowed)}")
    return item


def _default_adapter_module(runtime_name: str) -> str:
    return runtime_name.replace("-", "_")


def _parse_adapter_module(value: object, *, label: str, runtime_name: str) -> str:
    if value is None:
        return _default_adapter_module(runtime_name)
    module_name = _require_string(value, label=label)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module_name) is None:
        raise ValueError(f"{label} must be a Python module name segment")
    return module_name


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


def _parse_capabilities(
    entry: object,
    *,
    label: str,
    launch_wrapper_permission_surface_kinds: frozenset[str],
) -> RuntimeCapabilityPolicy:
    payload = _require_mapping(entry, label=label)
    _require_allowed_keys(payload, label=label, allowed_keys=_RUNTIME_CAPABILITY_KEYS)
    _require_keys(payload, label=label, required_keys=_RUNTIME_CAPABILITY_KEYS)

    for field_name, enum_values in _RUNTIME_CAPABILITY_ENUMS.items():
        value = _require_string(payload.get(field_name), label=f"{label}.{field_name}")
        if value not in enum_values:
            allowed = ", ".join(sorted(enum_values))
            raise ValueError(f"{label}.{field_name} must be one of: {allowed}")

    capability_kwargs: dict[str, object] = {}
    capability_kwargs["permissions_surface"] = _require_string(payload.get("permissions_surface"), label=f"{label}.permissions_surface")
    capability_kwargs["permission_surface_kind"] = _require_runtime_surface_label(
        payload.get("permission_surface_kind"),
        label=f"{label}.permission_surface_kind",
        special_values=launch_wrapper_permission_surface_kinds,
    )
    capability_kwargs["prompt_free_mode_value"] = _require_string(payload.get("prompt_free_mode_value"), label=f"{label}.prompt_free_mode_value")
    capability_kwargs["supports_runtime_permission_sync"] = _require_bool(
        payload.get("supports_runtime_permission_sync"),
        label=f"{label}.supports_runtime_permission_sync",
    )
    capability_kwargs["supports_prompt_free_mode"] = _require_bool(
        payload.get("supports_prompt_free_mode"),
        label=f"{label}.supports_prompt_free_mode",
    )
    capability_kwargs["prompt_free_requires_relaunch"] = _require_bool(
        payload.get("prompt_free_requires_relaunch"),
        label=f"{label}.prompt_free_requires_relaunch",
    )
    capability_kwargs["statusline_surface"] = _require_string(payload.get("statusline_surface"), label=f"{label}.statusline_surface")
    capability_kwargs["statusline_config_surface"] = _require_runtime_surface_label(
        payload.get("statusline_config_surface"),
        label=f"{label}.statusline_config_surface",
    )
    capability_kwargs["notify_surface"] = _require_string(payload.get("notify_surface"), label=f"{label}.notify_surface")
    capability_kwargs["notify_config_surface"] = _require_runtime_surface_label(
        payload.get("notify_config_surface"),
        label=f"{label}.notify_config_surface",
    )
    capability_kwargs["telemetry_source"] = _require_string(payload.get("telemetry_source"), label=f"{label}.telemetry_source")
    capability_kwargs["telemetry_completeness"] = _require_string(
        payload.get("telemetry_completeness"), label=f"{label}.telemetry_completeness"
    )
    capability_kwargs["supports_usage_tokens"] = _require_bool(payload.get("supports_usage_tokens"), label=f"{label}.supports_usage_tokens")
    capability_kwargs["supports_cost_usd"] = _require_bool(payload.get("supports_cost_usd"), label=f"{label}.supports_cost_usd")
    capability_kwargs["supports_context_meter"] = _require_bool(
        payload.get("supports_context_meter"), label=f"{label}.supports_context_meter"
    )
    capability_kwargs["child_artifact_persistence_reliability"] = _require_string(
        payload.get("child_artifact_persistence_reliability"),
        label=f"{label}.child_artifact_persistence_reliability",
    )
    capability_kwargs["supports_structured_child_results"] = _require_bool(
        payload.get("supports_structured_child_results"),
        label=f"{label}.supports_structured_child_results",
    )
    capability_kwargs["continuation_surface"] = _require_string(payload.get("continuation_surface"), label=f"{label}.continuation_surface")
    capability_kwargs["checkpoint_stop_semantics"] = _require_string(
        payload.get("checkpoint_stop_semantics"), label=f"{label}.checkpoint_stop_semantics"
    )
    capability_kwargs["supports_runtime_session_payload_attribution"] = _require_bool(
        payload.get("supports_runtime_session_payload_attribution"),
        label=f"{label}.supports_runtime_session_payload_attribution",
    )
    capability_kwargs["supports_agent_payload_attribution"] = _require_bool(
        payload.get("supports_agent_payload_attribution"),
        label=f"{label}.supports_agent_payload_attribution",
    )

    missing_fields = set(_RUNTIME_CAPABILITY_FIELD_NAMES) - set(capability_kwargs)
    if missing_fields:
        raise ValueError(f"{label} missing parsed capability field(s): {', '.join(sorted(missing_fields))}")

    policy = RuntimeCapabilityPolicy(**capability_kwargs)
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
            if flag == descriptor.install_flag:
                raise ValueError(
                    f"runtime catalog entry {descriptor.runtime_name!r} selection_flags must not repeat install_flag {flag!r}"
                )
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


def _expected_validated_command_surface(command_prefix: str) -> str:
    if command_prefix.startswith("/gpd"):
        return "public_runtime_slash_command"
    if command_prefix.startswith("$gpd"):
        return "public_runtime_dollar_command"
    return "public_runtime_command_surface"


def _parse_validated_command_surface(value: object, *, label: str, command_prefix: str) -> str:
    expected = _expected_validated_command_surface(command_prefix)
    if value is None:
        return expected
    surface = _require_string(value, label=label)
    if _RUNTIME_VALIDATED_COMMAND_SURFACE_RE.fullmatch(surface) is None:
        raise ValueError(f"{label} must match /^public_runtime_[a-z0-9_]+_command$/")
    if surface != expected:
        raise ValueError(f"{label} must be {expected!r} for command_prefix {command_prefix!r}")
    return surface


def _parse_public_command_surface_prefix(
    value: object,
    *,
    label: str,
    command_prefix: str,
) -> str:
    if value is None:
        return command_prefix
    prefix = _require_string(value, label=label)
    if prefix != command_prefix:
        raise ValueError(f"{label} must match command_prefix")
    return prefix


def _parse_hook_payload(entry: object, *, label: str) -> HookPayloadPolicy:
    payload = _require_mapping(entry, label=label)
    _require_allowed_keys(payload, label=label, allowed_keys=_RUNTIME_HOOK_PAYLOAD_KEYS)
    _require_keys(payload, label=label, required_keys=_RUNTIME_HOOK_PAYLOAD_KEYS)

    values = {}
    for field_name in _HOOK_PAYLOAD_FIELD_NAMES:
        values[field_name] = _require_string_tuple(
            payload[field_name], label=f"{label}.{field_name}", allow_empty=True
        )

    return HookPayloadPolicy(**values)


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[RuntimeDescriptor, ...]:
    _load_runtime_catalog_schema_shape()
    raw_entries = _load_json_strict_no_duplicate_keys(_catalog_path())
    if not isinstance(raw_entries, list):
        raise ValueError("runtime catalog must be a JSON array")
    descriptors: list[RuntimeDescriptor] = []
    for index, entry in enumerate(raw_entries):
        label = f"runtime catalog entry {index}"
        payload = _require_mapping(entry, label=label)
        _require_allowed_keys(payload, label=label, allowed_keys=_RUNTIME_ENTRY_ALLOWED_KEYS)
        _require_keys(payload, label=label, required_keys=_RUNTIME_ENTRY_REQUIRED_KEYS)
        runtime_name_value = _require_string(payload["runtime_name"], label=f"{label}.runtime_name")
        command_prefix_value = _require_string(payload["command_prefix"], label=f"{label}.command_prefix")
        install_flag_value = _require_string(payload["install_flag"], label=f"{label}.install_flag")
        selection_flags_value = _require_string_tuple(
            payload["selection_flags"],
            label=f"{label}.selection_flags",
            allow_empty=False,
        )
        selection_aliases_value = _require_string_tuple(
            payload["selection_aliases"],
            label=f"{label}.selection_aliases",
            allow_empty=False,
        )
        _validate_runtime_descriptor_selection_tokens(
            install_flag=install_flag_value,
            selection_flags=selection_flags_value,
            selection_aliases=selection_aliases_value,
            label=label,
        )
        descriptors.append(
            RuntimeDescriptor(
                runtime_name=runtime_name_value,
                adapter_module=_parse_adapter_module(
                    payload.get("adapter_module"),
                    label=f"{label}.adapter_module",
                    runtime_name=runtime_name_value,
                ),
                display_name=_require_string(payload["display_name"], label=f"{label}.display_name"),
                priority=_require_int(payload["priority"], label=f"{label}.priority"),
                config_dir_name=_require_string(payload["config_dir_name"], label=f"{label}.config_dir_name"),
                install_flag=install_flag_value,
                launch_command=_require_string(payload["launch_command"], label=f"{label}.launch_command"),
                command_prefix=command_prefix_value,
                activation_env_vars=_require_string_tuple(
                    payload["activation_env_vars"],
                    label=f"{label}.activation_env_vars",
                    allow_empty=False,
                ),
                selection_flags=selection_flags_value,
                selection_aliases=selection_aliases_value,
                global_config=_parse_global_config(payload["global_config"], label=f"{label}.global_config"),
                capabilities=_parse_capabilities(
                    payload["capabilities"],
                    label=f"{label}.capabilities",
                    launch_wrapper_permission_surface_kinds=_RUNTIME_LAUNCH_WRAPPER_PERMISSION_SURFACE_KINDS,
                ),
                hook_payload=_parse_hook_payload(payload["hook_payload"], label=f"{label}.hook_payload"),
                manifest_file_prefixes=_require_string_tuple(
                    payload["manifest_file_prefixes"]
                    if "manifest_file_prefixes" in payload
                    else [],
                    label=f"{label}.manifest_file_prefixes",
                    allow_empty=True,
                ),
                managed_install_surface=_require_string_member(
                    payload["managed_install_surface"],
                    label=f"{label}.managed_install_surface",
                    allowed_values=_RUNTIME_MANAGED_INSTALL_SURFACES,
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
                    command_prefix=command_prefix_value,
                ),
                public_command_surface_prefix=_parse_public_command_surface_prefix(
                    payload.get("public_command_surface_prefix"),
                    label=f"{label}.public_command_surface_prefix",
                    command_prefix=command_prefix_value,
                ),
            )
        )
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
    return ManagedInstallSurfacePolicy(
        gpd_content_globs=(f"{install_root}/**/*",),
        nested_command_globs=("commands/gpd/**/*",) if descriptor.managed_install_surface == "nested_commands" else (),
        flat_command_globs=("command/gpd-*.md",) if descriptor.managed_install_surface == "flat_commands" else (),
        managed_agent_globs=("agents/gpd-*.md", "agents/gpd-*.toml"),
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


def _alias_variants(value: str | None) -> set[str]:
    if not isinstance(value, str):
        return set()
    normalized = value.strip().casefold()
    if not normalized:
        return set()
    variants = {normalized}
    if normalized.startswith("--"):
        variants.add("--" + normalized.removeprefix("--").replace("_", "-"))
        variants.add("--" + normalized.removeprefix("--").replace("-", "_"))
    if "-" in normalized:
        variants.add(normalized.replace("-", "_"))
    if "_" in normalized:
        variants.add(normalized.replace("_", "-"))
    return variants


def _validate_runtime_descriptor_selection_tokens(
    *,
    install_flag: str,
    selection_flags: tuple[str, ...],
    selection_aliases: tuple[str, ...],
    label: str,
) -> None:
    seen: set[str] = set()

    def _check(value: str, field_label: str) -> None:
        variants = sorted(_alias_variants(value))
        duplicate = next((variant for variant in variants if variant in seen), None)
        if duplicate is not None:
            raise ValueError(
                f"{field_label} duplicates normalized runtime selection token {duplicate!r}"
            )
        seen.update(variants)

    _check(install_flag, f"{label}.install_flag")
    for index, flag in enumerate(selection_flags):
        _check(flag, f"{label}.selection_flags[{index}]")
    for index, alias in enumerate(selection_aliases):
        _check(alias, f"{label}.selection_aliases[{index}]")


def normalize_runtime_name(value: str | None) -> str | None:
    """Resolve a runtime id, display name, alias, or install flag to a canonical runtime name."""
    if not isinstance(value, str):
        return None

    normalized = value.strip().casefold()
    if not normalized:
        return None

    for descriptor in iter_runtime_descriptors():
        candidates = (
            descriptor.runtime_name,
            descriptor.display_name,
            descriptor.install_flag,
            descriptor.adapter_module,
            *descriptor.selection_flags,
            *descriptor.selection_aliases,
        )
        for alias in candidates:
            if normalized in _alias_variants(alias):
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


def _paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve(strict=False) == right.expanduser().resolve(strict=False)
    except OSError:
        return left.expanduser() == right.expanduser()


def _xdg_config_home(environ: dict[str, str] | None) -> str | None:
    if environ is not None:
        return environ.get("XDG_CONFIG_HOME")
    return os.environ.get("XDG_CONFIG_HOME")


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
        xdg_home = _xdg_config_home(environ)
        if xdg_home and policy.xdg_subdir:
            return Path(xdg_home).expanduser() / policy.xdg_subdir
        return (home or Path.home()) / policy.home_subpath

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
