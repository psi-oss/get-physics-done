from __future__ import annotations

import json
from pathlib import Path

from gpd.contracts import contract_from_data, contract_from_data_salvage
from gpd.core.contract_validation import parse_project_contract_data_salvage, validate_project_contract
from gpd.core.state import (
    ProjectLayout,
    default_state_dict,
    load_state_json,
    save_state_json,
    save_state_markdown,
    state_set_project_contract,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "stage0" / "project_contract.json"


def _load_contract_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fast_project_contract_proxy_rejects_missing_scope_section() -> None:
    contract = _load_contract_fixture()
    contract.pop("scope")

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is False
    assert "scope is required" in result.errors


def test_fast_project_contract_proxy_rejects_unknown_proof_deliverable_in_draft_mode() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["proof_deliverables"] = ["deliv-missing"]

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is False
    assert "claim claim-benchmark references unknown proof deliverable deliv-missing" in result.errors


def test_fast_project_contract_proxy_strict_rejects_singleton_list_drift_but_salvage_recovers() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    assert contract_from_data(contract) is None

    salvaged = contract_from_data_salvage(contract)

    assert salvaged is not None
    assert salvaged.context_intake.must_read_refs == ["ref-benchmark"]


def test_fast_project_contract_proxy_salvage_preserves_claim_when_optional_proof_field_is_malformed() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [
        {
            "symbol": "alpha",
            "domain_or_type": ["real"],
            "aliases": ["alpha"],
            "required_in_proof": True,
        }
    ]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.recoverable_errors == []
    assert result.blocking_errors == ["claims.0.parameters.0.domain_or_type: Input should be a valid string"]
    assert len(result.contract.claims) == 1
    assert result.contract.claims[0].parameters[0].symbol == "alpha"
    assert result.contract.claims[0].parameters[0].domain_or_type is None
    assert contract_from_data_salvage(contract) is None


def test_fast_project_contract_proxy_rejects_malformed_optional_approach_policy(tmp_path: Path) -> None:
    contract = _load_contract_fixture()
    contract["approach_policy"] = "not-a-dict"
    save_state_json(tmp_path, default_state_dict())

    result = state_set_project_contract(tmp_path, contract)

    assert result.updated is False
    assert result.reason is not None
    assert "approach_policy must be an object, not str" in result.reason


def test_fast_project_contract_proxy_normalizes_visible_contract_drift_on_markdown_save(tmp_path: Path) -> None:
    state = default_state_dict()
    state["position"]["status"] = "Executing"
    save_state_json(tmp_path, state)

    layout = ProjectLayout(tmp_path)
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    persisted["project_contract"] = _load_contract_fixture()
    persisted["project_contract"]["context_intake"]["must_read_refs"] = "ref-benchmark"
    layout.state_json.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

    md_content = layout.state_md.read_text(encoding="utf-8").replace("**Status:** Executing", "**Status:** Paused", 1)
    save_state_markdown(tmp_path, md_content)

    saved = load_state_json(tmp_path)
    assert saved is not None
    assert saved["project_contract"] is not None
    assert saved["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
