"""Fast contract checks for runtime catalog schema inventory and wiring."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import gpd.adapters.runtime_catalog as runtime_catalog

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_CATALOG_PATH = _REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.json"
_RUNTIME_CATALOG_SCHEMA_PATH = _REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog_schema.json"


def _load_schema() -> dict[str, object]:
    return json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_catalog() -> list[dict[str, object]]:
    return json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))


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
