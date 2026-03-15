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
    assert payload["warnings"] == []
    assert payload["question"] == "What benchmark must the project recover?"
    assert payload["decisive_target_count"] > 0
    assert payload["guidance_signal_count"] > 0
    assert payload["reference_count"] > 0


def test_validate_project_contract_command_accepts_valid_fixture_via_stdin() -> None:
    contract_text = (FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "validate", "project-contract", "-"],
        input=contract_text,
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["question"] == "What benchmark must the project recover?"
    assert payload["reference_count"] > 0


def test_validate_project_contract_command_warns_when_user_guidance_is_missing(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["guidance_signal_count"] == 0
    assert payload["reference_count"] > 0
    assert (
        "no user guidance signals recorded yet (must_read_refs, prior outputs, anchors, baselines, gaps, or crucial inputs)"
        in payload["warnings"]
    )


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


def test_validate_project_contract_command_blocks_must_surface_reference_without_applies_to(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"][0]["must_surface"] = True
    contract["references"][0]["applies_to"] = []
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert any("must_surface but missing applies_to" in error for error in payload["errors"])


def test_validate_project_contract_command_blocks_background_only_reference_in_approved_mode(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = [
        {
            "id": "ref-background",
            "kind": "paper",
            "locator": "Background review article",
            "role": "background",
            "why_it_matters": "General context only",
            "applies_to": [],
            "must_surface": False,
            "required_actions": [],
        }
    ]
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    for claim in contract.get("claims", []):
        claim["references"] = []
    for target in contract.get("acceptance_tests", []):
        target["evidence_required"] = [item for item in target.get("evidence_required", []) if item != "ref-benchmark"]
    contract["scope"]["unresolved_questions"] = []
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["mode"] == "approved"
    assert any("approved project contract requires at least one concrete anchor" in error for error in payload["errors"])


def test_validate_project_contract_command_blocks_background_must_read_ref_without_real_anchor(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = [
        {
            "id": "ref-background",
            "kind": "paper",
            "locator": "Background review article",
            "role": "background",
            "why_it_matters": "General context only",
            "applies_to": [],
            "must_surface": False,
            "required_actions": ["read"],
        }
    ]
    contract["context_intake"] = {
        "must_read_refs": ["ref-background"],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    for claim in contract.get("claims", []):
        claim["references"] = []
    for target in contract.get("acceptance_tests", []):
        target["evidence_required"] = [item for item in target.get("evidence_required", []) if item != "ref-benchmark"]
    contract["scope"]["unresolved_questions"] = []
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["mode"] == "approved"
    assert any("approved project contract requires at least one concrete anchor" in error for error in payload["errors"])


def test_validate_project_contract_command_reports_shape_errors_without_traceback(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["references"] = ["ref-benchmark"]
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "project-contract", str(contract_path)], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["mode"] == "approved"
    assert "references.0 must be an object, not str" in payload["errors"]


def test_validate_project_contract_command_preserves_requested_mode_for_non_object_input() -> None:
    result = runner.invoke(
        app,
        ["--raw", "validate", "project-contract", "-", "--mode", "approved"],
        input="[]",
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["mode"] == "approved"
    assert payload["errors"] == ["project contract must be a JSON object"]


def test_validate_project_contract_command_rejects_invalid_mode(tmp_path: Path) -> None:
    contract_path = tmp_path / "project-contract.json"
    contract_path.write_text((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "validate", "project-contract", str(contract_path), "--mode", "banana"],
    )

    assert result.exit_code == 1, result.output
    assert "Invalid --mode" in str(result.exception)
