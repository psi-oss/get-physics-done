"""Fast contract checks for runtime catalog schema inventory and wiring."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import fields
from pathlib import Path

import gpd.adapters.runtime_catalog as runtime_catalog
from scripts.validate_runtime_catalog_schema import validate_runtime_catalog_schema

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_CATALOG_PATH = _REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.json"
_RUNTIME_CATALOG_SCHEMA_PATH = _REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog_schema.json"


def _load_schema() -> dict[str, object]:
    return json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_catalog() -> list[dict[str, object]]:
    return json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))


_TRIMMED_STRING_PATTERN = r"^\S.*\S$|^\S$"
_CAPABILITY_BOOL_FIELDS = frozenset(
    (
        "supports_runtime_permission_sync",
        "supports_prompt_free_mode",
        "prompt_free_requires_relaunch",
        "supports_usage_tokens",
        "supports_cost_usd",
        "supports_context_meter",
        "supports_structured_child_results",
        "supports_runtime_session_payload_attribution",
        "supports_agent_payload_attribution",
    )
)


def _trimmed_string_schema() -> dict[str, object]:
    return {
        "type": "string",
        "minLength": 1,
        "pattern": _TRIMMED_STRING_PATTERN,
    }


def _string_list_schema(*, min_items: int) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "array",
        "items": _trimmed_string_schema(),
        "uniqueItems": True,
    }
    if min_items:
        schema["minItems"] = min_items
    return schema


def _enum_schema(values: Iterable[str]) -> dict[str, object]:
    return {"type": "string", "enum": sorted(values)}


def _build_global_config_schema(schema_payload: dict[str, object]) -> dict[str, object]:
    sections = schema_payload["global_config_keys"]
    required_sections = schema_payload["global_config_required_keys"]
    return {
        "type": "object",
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    key: {"const": strategy, "type": "string"} if key == "strategy" else _trimmed_string_schema()
                    for key in keys
                },
                "required": required_sections[strategy],
                "additionalProperties": False,
            }
            for strategy, keys in sections.items()
        ],
    }


def _build_capabilities_schema(schema_payload: dict[str, object]) -> dict[str, object]:
    capability_keys = schema_payload["capability_keys"]
    capability_required_keys = schema_payload["capability_required_keys"]
    capability_enums = schema_payload["capability_enums"]
    properties: dict[str, object] = {}
    for field_name in capability_keys:
        if field_name in capability_enums:
            properties[field_name] = {"type": "string", "enum": sorted(capability_enums[field_name])}
        elif field_name in _CAPABILITY_BOOL_FIELDS:
            properties[field_name] = {"type": "boolean"}
        else:
            properties[field_name] = _trimmed_string_schema()

    return {
        "type": "object",
        "properties": properties,
        "required": capability_required_keys,
        "additionalProperties": False,
    }


def _build_hook_payload_schema(schema_payload: dict[str, object]) -> dict[str, object]:
    keys = schema_payload["hook_payload_keys"]
    required_keys = schema_payload["hook_payload_required_keys"]
    return {
        "type": "object",
        "properties": {key: _string_list_schema(min_items=0) for key in keys},
        "required": required_keys,
        "additionalProperties": False,
    }


def _build_entry_schema(schema_payload: dict[str, object]) -> dict[str, object]:
    required_keys = schema_payload["entry_required_keys"]
    optional_keys = schema_payload["entry_optional_keys"]
    managed_install_surfaces = schema_payload["managed_install_surfaces"]
    install_help_example_scopes = schema_payload["install_help_example_scopes"]

    def factory(field_name: str) -> dict[str, object]:
        if field_name == "adapter_module":
            return {"type": "string", "pattern": r"^[A-Za-z_][A-Za-z0-9_]*$"}
        if field_name == "priority":
            return {"type": "integer"}
        if field_name in (
            "runtime_name",
            "display_name",
            "config_dir_name",
            "install_flag",
            "launch_command",
            "command_prefix",
            "public_command_surface_prefix",
        ):
            return _trimmed_string_schema()
        if field_name == "activation_env_vars" or field_name == "selection_flags" or field_name == "selection_aliases":
            return _string_list_schema(min_items=1)
        if field_name == "manifest_file_prefixes":
            return _string_list_schema(min_items=0)
        if field_name in ("native_include_support", "agent_prompt_uses_dollar_templates"):
            return {"type": "boolean"}
        if field_name == "managed_install_surface":
            return _enum_schema(managed_install_surfaces)
        if field_name == "global_config":
            return _build_global_config_schema(schema_payload)
        if field_name == "capabilities":
            return _build_capabilities_schema(schema_payload)
        if field_name == "hook_payload":
            return _build_hook_payload_schema(schema_payload)
        if field_name == "installer_help_example_scope":
            return _enum_schema(install_help_example_scopes)
        if field_name == "validated_command_surface":
            return {"type": "string", "minLength": 1, "pattern": r"^public_runtime_[a-z0-9_]+_command$"}
        raise AssertionError(f"unhandled entry field {field_name}")

    properties = {field: factory(field) for field in (*required_keys, *optional_keys)}

    return {
        "type": "object",
        "properties": properties,
        "required": required_keys,
        "additionalProperties": False,
    }


def _build_catalog_json_schema(schema_payload: dict[str, object]) -> dict[str, object]:
    return {
        "type": "array",
        "items": _build_entry_schema(schema_payload),
        "minItems": 1,
    }


def test_runtime_catalog_schema_inventory_matches_runtime_dataclasses() -> None:
    schema = _load_schema()

    descriptor_fields = {field.name for field in fields(runtime_catalog.RuntimeDescriptor)}
    global_config_fields = {field.name for field in fields(runtime_catalog.GlobalConfigPolicy)}
    capability_fields = {field.name for field in fields(runtime_catalog.RuntimeCapabilityPolicy)}
    hook_payload_fields = {field.name for field in fields(runtime_catalog.HookPayloadPolicy)}

    assert set(schema["entry_required_keys"]) | set(schema["entry_optional_keys"]) == descriptor_fields
    assert set(schema["global_config_keys"]["env_or_home"]) | set(schema["global_config_keys"]["xdg_app"]) == global_config_fields
    assert set(schema["capability_keys"]) == capability_fields
    assert set(schema["hook_payload_keys"]) == hook_payload_fields


def test_runtime_catalog_schema_top_level_keys_match_schema_payload() -> None:
    schema = _load_schema()

    assert set(schema["top_level_keys"]) == set(schema)


def test_runtime_catalog_schema_parser_inventory_matches_internal_runtime_shape() -> None:
    schema = _load_schema()

    assert set(schema["capability_keys"]) == set(runtime_catalog._RUNTIME_CAPABILITY_KEYS)
    assert set(schema["hook_payload_keys"]) == set(runtime_catalog._RUNTIME_HOOK_PAYLOAD_KEYS)
    assert set(schema["managed_install_surfaces"]) == set(runtime_catalog._RUNTIME_MANAGED_INSTALL_SURFACES)
    assert set(schema["install_help_example_scopes"]) == set(runtime_catalog._RUNTIME_INSTALL_HELP_EXAMPLE_SCOPES)
    assert set(schema["launch_wrapper_permission_surface_kinds"]) == set(
        runtime_catalog._RUNTIME_LAUNCH_WRAPPER_PERMISSION_SURFACE_KINDS
    )


def test_runtime_catalog_schema_required_keys_match_loaded_runtime_descriptors() -> None:
    schema = _load_schema()
    catalog = _load_catalog()
    required_keys = set(schema["entry_required_keys"])
    optional_keys = set(schema["entry_optional_keys"])
    required_descriptor_fields = {
        field.name
        for field in fields(runtime_catalog.RuntimeDescriptor)
        if field.name not in optional_keys
    }

    assert required_keys == required_descriptor_fields
    for entry in catalog:
        assert required_keys <= set(entry)


def test_runtime_catalog_entries_conform_to_schema_enums_and_nested_key_inventories() -> None:
    schema = _load_schema()
    catalog = _load_catalog()

    capability_enums = schema["capability_enums"]
    global_config_keys = schema["global_config_keys"]
    managed_install_surfaces = set(schema["managed_install_surfaces"])
    install_help_example_scopes = set(schema["install_help_example_scopes"])

    for entry in catalog:
        capability_payload = entry["capabilities"]
        global_config_payload = entry["global_config"]
        strategy = global_config_payload["strategy"]

        assert entry["managed_install_surface"] in managed_install_surfaces

        scope = entry.get("installer_help_example_scope")
        if scope is not None:
            assert scope in install_help_example_scopes

        assert set(global_config_payload) == set(global_config_keys[strategy])

        for enum_field, allowed_values in capability_enums.items():
            assert capability_payload[enum_field] in set(allowed_values)


def test_runtime_catalog_schema_required_optional_keys_partition_descriptor_fields() -> None:
    schema = _load_schema()

    required_keys = set(schema["entry_required_keys"])
    optional_keys = set(schema["entry_optional_keys"])
    descriptor_fields = {field.name for field in fields(runtime_catalog.RuntimeDescriptor)}

    assert required_keys.isdisjoint(optional_keys)
    assert required_keys | optional_keys == descriptor_fields


def test_runtime_catalog_schema_nested_required_keys_match_nested_inventories() -> None:
    schema = _load_schema()

    assert set(schema["global_config_required_keys"]) == set(schema["global_config_keys"])
    for strategy, keys in schema["global_config_keys"].items():
        assert set(schema["global_config_required_keys"][strategy]) == set(keys)

    assert set(schema["capability_required_keys"]) == set(schema["capability_keys"])
    assert set(schema["hook_payload_required_keys"]) == set(schema["hook_payload_keys"])


def test_runtime_catalog_descriptor_count_is_intentional() -> None:
    descriptors = runtime_catalog.iter_runtime_descriptors()
    catalog = _load_catalog()
    expected_runtime_names = tuple(entry["runtime_name"] for entry in catalog)

    assert len(descriptors) == len(catalog)
    assert tuple(descriptor.runtime_name for descriptor in descriptors) == expected_runtime_names


def test_runtime_catalog_schema_enum_inventory_matches_loader_shape() -> None:
    schema = _load_schema()
    loaded_shape = runtime_catalog._load_runtime_catalog_schema_shape()

    assert set(schema["capability_enums"]) == set(runtime_catalog._RUNTIME_CAPABILITY_ENUMS)
    for enum_name, allowed_values in schema["capability_enums"].items():
        assert set(allowed_values) == set(loaded_shape["capability_enums"][enum_name])
        assert set(allowed_values) == set(runtime_catalog._RUNTIME_CAPABILITY_ENUMS[enum_name])


def test_runtime_catalog_json_schema_validation_matches_loader_or_validator() -> None:
    schema_payload = _load_schema()
    catalog_payload = _load_catalog()

    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError:
        validate_runtime_catalog_schema()
        return

    json_schema = _build_catalog_json_schema(schema_payload)
    Draft202012Validator.check_schema(json_schema)
    Draft202012Validator(json_schema).validate(catalog_payload)
