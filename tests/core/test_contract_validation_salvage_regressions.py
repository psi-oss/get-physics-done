"""Focused regressions for project-contract salvage reliability."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from gpd.core.contract_validation import validate_project_contract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def test_draft_salvage_surfaces_lossy_list_and_case_drift_warnings() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = ""
    contract["references"][0]["role"] = "Benchmark"

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is True
    assert "context_intake.must_read_refs was normalized from blank string to empty list" in result.warnings
    assert "context_intake.must_read_refs must not be blank" in result.warnings
    assert "references.0.role must use exact canonical value: benchmark" in result.warnings


def test_approved_mode_rejects_the_same_schema_drift_strictly() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = ""
    contract["references"][0]["role"] = "Benchmark"

    result = validate_project_contract(copy.deepcopy(contract), mode="approved")

    assert result.valid is False
    assert "context_intake.must_read_refs was normalized from blank string to empty list" in result.errors
    assert "context_intake.must_read_refs must not be blank" in result.errors
    assert "references.0.role must use exact canonical value: benchmark" in result.errors
