from __future__ import annotations

import json
from pathlib import Path

import anyio


def test_verification_contract_policy_text_stays_aligned_across_public_surfaces() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors
    from gpd.mcp.servers.verification_server import (
        _CONTRACT_PAYLOAD_INPUT_SCHEMA,
        _CONTRACT_SCOPE_INPUT_SCHEMA,
        mcp,
    )
    from gpd.mcp.verification_contract_policy import (
        VERIFICATION_BINDING_FIELD_NAMES,
        VERIFICATION_BINDING_TARGETS,
        VERIFICATION_CONTRACT_POLICY_TEXT,
        verification_contract_surface_summary_text,
        verification_server_description,
    )

    descriptors = build_public_descriptors()
    verification_descriptor = descriptors["gpd-verification"]
    tools = {tool.name: tool for tool in anyio.run(mcp.list_tools)}
    infra_descriptor = json.loads((Path(__file__).resolve().parents[2] / "infra" / "gpd-verification.json").read_text())
    repo_root = Path(__file__).resolve().parents[2]
    plan_schema = (repo_root / "src/gpd/specs/templates/plan-contract-schema.md").read_text(encoding="utf-8")
    state_schema = (repo_root / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")

    assert _CONTRACT_PAYLOAD_INPUT_SCHEMA["description"] == VERIFICATION_CONTRACT_POLICY_TEXT
    assert VERIFICATION_BINDING_TARGETS == (
        "observable",
        "claim",
        "deliverable",
        "acceptance_test",
        "reference",
        "forbidden_proxy",
    )
    assert VERIFICATION_BINDING_FIELD_NAMES == (
        "binding.observable_ids",
        "binding.claim_ids",
        "binding.deliverable_ids",
        "binding.acceptance_test_ids",
        "binding.reference_ids",
        "binding.forbidden_proxy_ids",
    )
    assert verification_descriptor["description"] == verification_server_description()
    assert infra_descriptor["description"] == verification_server_description()
    assert tools["run_contract_check"].description is not None
    assert tools["suggest_contract_checks"].description is not None
    assert verification_contract_surface_summary_text() in verification_descriptor["description"]
    assert verification_descriptor["description"].count(VERIFICATION_CONTRACT_POLICY_TEXT) == 0
    assert tools["run_contract_check"].description.count(VERIFICATION_CONTRACT_POLICY_TEXT) == 0
    assert tools["suggest_contract_checks"].description.count(VERIFICATION_CONTRACT_POLICY_TEXT) == 0
    assert verification_contract_surface_summary_text() in tools["run_contract_check"].description
    assert verification_contract_surface_summary_text() in tools["suggest_contract_checks"].description
    assert "``request`` object" in tools["run_contract_check"].description
    assert "``request`` input schema" in tools["run_contract_check"].description
    assert "``request.contract`` is optional" in tools["run_contract_check"].description
    assert "project_dir" in tools["run_contract_check"].description
    assert "request_template" in tools["suggest_contract_checks"].description
    assert "active_checks" in tools["suggest_contract_checks"].description
    assert "``contract`` must be an object" in tools["suggest_contract_checks"].description
    assert "schema_required_request_fields" in tools["suggest_contract_checks"].description
    assert "Nested object schemas are closed at every level" in VERIFICATION_CONTRACT_POLICY_TEXT
    assert "unknown top-level or nested keys" in VERIFICATION_CONTRACT_POLICY_TEXT
    assert "its absence is a blocker" in VERIFICATION_CONTRACT_POLICY_TEXT
    assert "missing `must_surface=true` is a non-blocking warning" in VERIFICATION_CONTRACT_POLICY_TEXT
    for field_name in VERIFICATION_BINDING_FIELD_NAMES:
        assert f"`{field_name}`" in VERIFICATION_CONTRACT_POLICY_TEXT
    assert (
        "If `references[]` is non-empty and the contract does not already carry concrete grounding elsewhere, "
        "at least one reference must set `must_surface: true`."
    ) in plan_schema
    assert "a missing `must_surface: true` reference is a warning, not a blocker" in plan_schema
    assert (
        "If a project contract has any `references[]` and does not already carry concrete prior-output, "
        "user-anchor, or baseline grounding, at least one reference must set `must_surface: true`."
    ) in state_schema
    assert "a missing `must_surface: true` reference is still a warning" in state_schema
    assert (
        "Project-scoping contracts must also provide non-empty `scope.in_scope` naming at least one concrete "
        "objective or boundary"
    ) in _CONTRACT_SCOPE_INPUT_SCHEMA["description"]
    assert "`scope.in_scope` is required and must name at least one project boundary or objective." in plan_schema
    assert "`scope.in_scope` must name at least one project boundary or objective." in state_schema
