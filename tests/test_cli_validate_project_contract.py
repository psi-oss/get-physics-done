"""CLI tests for project-contract validation."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "stage0"


def test_validate_project_contract_command_accepts_valid_fixture(tmp_path: Path) -> None:
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["decisive_target_count"] > 0
    assert payload["guidance_signal_count"] > 0


def test_validate_project_contract_command_blocks_missing_skeptical_fields(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["uncertainty_markers"]["weakest_anchors"] = []
    contract["uncertainty_markers"]["disconfirming_observations"] = []
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert any("weakest_anchors" in error for error in payload["errors"])
    assert any("disconfirming_observations" in error for error in payload["errors"])


def test_validate_project_contract_command_blocks_invalid_reference_links(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = ["ref-missing"]
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert any("must_read_refs references unknown reference ref-missing" in error for error in payload["errors"])
