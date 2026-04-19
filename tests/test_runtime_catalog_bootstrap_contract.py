from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

import gpd.adapters.runtime_catalog as runtime_catalog

CATALOG_PATH = Path(__file__).resolve().parent.parent / "src" / "gpd" / "adapters" / "runtime_catalog.json"


def _load_descriptors_from_payload(
    payload: list[dict[str, object]],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)
    runtime_catalog._load_catalog.cache_clear()
    try:
        return runtime_catalog.iter_runtime_descriptors()
    finally:
        runtime_catalog._load_catalog.cache_clear()


def test_runtime_catalog_schema_loader_exposes_canonical_optional_keys() -> None:
    runtime_catalog._load_catalog.cache_clear()
    schema = runtime_catalog._load_runtime_catalog_schema_shape()

    assert "public_command_surface_prefix" in runtime_catalog._RUNTIME_ENTRY_OPTIONAL_KEYS
    assert "public_command_surface_prefix" in schema["entry_optional_keys"]
    assert "unsupported" in runtime_catalog._RUNTIME_CAPABILITY_ENUMS["permissions_surface"]
    assert "unsupported" in schema["capability_enums"]["permissions_surface"]
    assert schema["capability_defaults"] == asdict(runtime_catalog.RuntimeCapabilityPolicy())


def test_runtime_catalog_schema_matches_canonical_catalog_payload() -> None:
    schema = runtime_catalog._load_runtime_catalog_schema_shape()
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


def test_runtime_catalog_accepts_explicit_public_command_surface_prefix_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["public_command_surface_prefix"] = payload[0]["command_prefix"]

    descriptors = _load_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors[0].public_command_surface_prefix == descriptors[0].command_prefix


def test_runtime_catalog_accepts_descriptor_owned_public_command_surface_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["public_command_surface_prefix"] = "/public:"

    descriptors = _load_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors[0].public_command_surface_prefix == "/public:"
    assert descriptors[0].public_command_surface_prefix != descriptors[0].command_prefix
