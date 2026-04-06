from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent.parent / "src" / "gpd" / "adapters" / "runtime_catalog.json"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "gpd" / "adapters" / "runtime_catalog_schema.json"


def test_runtime_catalog_schema_matches_canonical_catalog_payload() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    required_entry_keys = set(schema["entry_required_keys"])
    allowed_entry_keys = required_entry_keys | set(schema["entry_optional_keys"])
    required_global_config_keys = {
        strategy: set(keys) for strategy, keys in schema["global_config_keys"].items()
    }
    required_capability_keys = set(schema["capability_keys"])
    required_hook_payload_keys = set(schema["hook_payload_keys"])

    assert catalog
    for entry in catalog:
        entry_keys = set(entry)
        assert required_entry_keys <= entry_keys
        assert entry_keys <= allowed_entry_keys
        assert set(entry["global_config"]) == required_global_config_keys[entry["global_config"]["strategy"]]
        assert set(entry["capabilities"]) == required_capability_keys
        assert set(entry["hook_payload"]) == required_hook_payload_keys
