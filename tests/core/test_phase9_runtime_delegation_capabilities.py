"""Phase 9 assertions for runtime delegation capability surfacing."""

from __future__ import annotations

import dataclasses

from gpd.adapters.runtime_catalog import (
    RuntimeCapabilityPolicy,
    get_runtime_capabilities,
    iter_runtime_descriptors,
)
from gpd.core.health import annotate_permissions_payload

_RUNTIME_CAPABILITY_FIELDS = tuple(field.name for field in dataclasses.fields(RuntimeCapabilityPolicy))


def test_permissions_payload_surfaces_complete_runtime_capabilities_for_all_runtimes() -> None:
    for descriptor in iter_runtime_descriptors():
        payload = annotate_permissions_payload({"runtime": descriptor.runtime_name})
        capabilities = payload["capabilities"]
        expected = get_runtime_capabilities(descriptor.runtime_name)

        assert capabilities["contract_source"] == "runtime-catalog"
        assert set(_RUNTIME_CAPABILITY_FIELDS).issubset(capabilities)
        for field_name in _RUNTIME_CAPABILITY_FIELDS:
            assert capabilities[field_name] == getattr(expected, field_name)


def test_permissions_payload_keeps_generic_delegation_defaults_for_unknown_runtime() -> None:
    payload = annotate_permissions_payload({"runtime": "not-a-runtime"})
    capabilities = payload["capabilities"]

    assert capabilities["contract_source"] == "generic-fallback"
    assert set(_RUNTIME_CAPABILITY_FIELDS).issubset(capabilities)
    assert capabilities["child_artifact_persistence_reliability"] == "unknown"
    assert capabilities["supports_structured_child_results"] is False
    assert capabilities["continuation_surface"] == "unknown"
    assert capabilities["checkpoint_stop_semantics"] == "unknown"
    assert capabilities["supports_runtime_session_payload_attribution"] is False
    assert capabilities["supports_agent_payload_attribution"] is False
