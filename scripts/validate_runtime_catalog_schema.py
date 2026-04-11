"""Validate runtime catalog JSON against its schema-shape contract."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CATALOG_PATH = REPO_ROOT / "src/gpd/adapters/runtime_catalog.json"
RUNTIME_CATALOG_SCHEMA_PATH = REPO_ROOT / "src/gpd/adapters/runtime_catalog_schema.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_runtime_catalog_schema() -> None:
    schema = json.loads(RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    catalog_payload = json.loads(RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))
    required_entry_keys = frozenset(schema["entry_required_keys"])
    allowed_entry_keys = required_entry_keys | frozenset(schema["entry_optional_keys"])
    global_config_keys = {strategy: frozenset(keys) for strategy, keys in schema["global_config_keys"].items()}
    capability_keys = frozenset(schema["capability_keys"])
    capability_enums = {field: frozenset(values) for field, values in schema["capability_enums"].items()}
    hook_payload_keys = frozenset(schema["hook_payload_keys"])
    managed_install_surfaces = frozenset(schema["managed_install_surfaces"])
    example_scopes = frozenset(schema["install_help_example_scopes"])

    _require(isinstance(catalog_payload, list), "runtime catalog must be a list")
    for index, entry in enumerate(catalog_payload):
        _require(isinstance(entry, dict), f"entry {index} must be an object")
        entry_name = str(entry.get("runtime_name", f"entry {index}"))
        entry_keys = frozenset(entry)
        _require(required_entry_keys <= entry_keys, f"{entry_name} is missing required keys")
        _require(entry_keys <= allowed_entry_keys, f"{entry_name} has unknown keys: {sorted(entry_keys - allowed_entry_keys)}")

        global_config = entry["global_config"]
        _require(isinstance(global_config, dict), f"{entry_name}.global_config must be an object")
        strategy = global_config.get("strategy")
        _require(isinstance(strategy, str), f"{entry_name}.global_config.strategy must be a string")
        allowed_keys = global_config_keys.get(strategy)
        _require(allowed_keys is not None, f"{entry_name}.global_config.strategy is unknown: {strategy!r}")
        _require(frozenset(global_config) == allowed_keys, f"{entry_name}.global_config keys do not match {strategy}")
        for key, value in global_config.items():
            _require(isinstance(value, str), f"{entry_name}.global_config.{key} must be a string")
            _require(value.strip() == value, f"{entry_name}.global_config.{key} has surrounding whitespace")

        capabilities = entry["capabilities"]
        _require(isinstance(capabilities, dict), f"{entry_name}.capabilities must be an object")
        _require(frozenset(capabilities) == capability_keys, f"{entry_name}.capabilities keys do not match schema")
        for field, allowed_values in capability_enums.items():
            value = capabilities.get(field)
            _require(isinstance(value, str), f"{entry_name}.capabilities.{field} must be a string")
            _require(value in allowed_values, f"{entry_name}.capabilities.{field} has invalid value {value!r}")

        hook_payload = entry["hook_payload"]
        _require(isinstance(hook_payload, dict), f"{entry_name}.hook_payload must be an object")
        _require(frozenset(hook_payload) == hook_payload_keys, f"{entry_name}.hook_payload keys do not match schema")
        for key, payload_values in hook_payload.items():
            _require(isinstance(payload_values, list), f"{entry_name}.hook_payload.{key} must be a list")
            _require(
                all(isinstance(item, str) and item.strip() == item for item in payload_values),
                f"{entry_name}.hook_payload.{key} values must be trimmed strings",
            )
            _require(len(payload_values) == len(set(payload_values)), f"{entry_name}.hook_payload.{key} has duplicates")

        _require(
            entry["managed_install_surface"] in managed_install_surfaces,
            f"{entry_name}.managed_install_surface has invalid value",
        )

        scope = entry.get("installer_help_example_scope")
        if scope is not None:
            _require(scope in example_scopes, f"{entry_name}.installer_help_example_scope has invalid value")

        prefixes = entry.get("manifest_file_prefixes")
        if prefixes is not None:
            _require(isinstance(prefixes, list), f"{entry_name}.manifest_file_prefixes must be a list")
            _require(
                all(isinstance(prefix, str) and prefix.strip() == prefix for prefix in prefixes),
                f"{entry_name}.manifest_file_prefixes values must be trimmed strings",
            )


def main() -> None:
    validate_runtime_catalog_schema()
    print("Runtime catalog schema guard passed.")


if __name__ == "__main__":
    main()
