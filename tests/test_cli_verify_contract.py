"""CLI parity tests for the contract-aware ``gpd verify`` subcommands.

Each command must emit exactly the envelope its MCP counterpart returns for the
same inputs, so the MCP tool functions are used directly as the oracle.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "stage0"


def _project_contract() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _benchmark_request() -> dict[str, object]:
    return {
        "check_key": "contract.benchmark_reproduction",
        "contract": _project_contract(),
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }


def _failing_benchmark_request() -> dict[str, object]:
    """Same benchmark check, but the observed metric misses the tolerance."""
    request = _benchmark_request()
    request["observed"] = {"metric_value": 0.05, "threshold_value": 0.02}
    return request


def _invoke(args: list[str], **kwargs: object) -> object:
    return runner.invoke(app, ["--raw", *args], catch_exceptions=False, **kwargs)


def test_contract_check_happy_path_matches_mcp_tool_payload(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    request = _benchmark_request()
    payload_path = tmp_path / "request.json"
    payload_path.write_text(json.dumps(request), encoding="utf-8")

    expected = run_contract_check(copy.deepcopy(request))
    result = _invoke(["verify", "contract-check", "--payload", str(payload_path)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert expected["status"] == "pass"
    assert expected["check_id"] == "5.16"


def test_contract_check_failed_status_exits_one_so_ci_callers_can_gate_on_exit_code(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    request = _failing_benchmark_request()
    payload_path = tmp_path / "request.json"
    payload_path.write_text(json.dumps(request), encoding="utf-8")

    expected = run_contract_check(copy.deepcopy(request))
    result = _invoke(["verify", "contract-check", "--payload", str(payload_path)])

    assert expected["status"] == "fail"
    assert "error" not in expected, "exit 1 must come from the failed status, not from a rejected payload"
    assert json.loads(result.output) == expected
    assert result.exit_code == 1, "a failed physics check must not report success to CI"


def test_contract_check_reads_request_from_stdin(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    request = _benchmark_request()
    expected = run_contract_check(copy.deepcopy(request))

    result = _invoke(["verify", "contract-check", "--payload", "-"], input=json.dumps(request))

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected


def test_contract_check_validation_error_matches_mcp_tool_and_exits_one(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    payload_path = tmp_path / "request.json"
    payload_path.write_text(json.dumps({}), encoding="utf-8")

    expected = run_contract_check({})
    result = _invoke(["verify", "contract-check", "--payload", str(payload_path)])

    assert result.exit_code == 1
    assert json.loads(result.output) == expected
    assert expected == {"error": "Missing check_key", "schema_version": 1}


def test_contract_check_unknown_check_key_exits_one(tmp_path: Path) -> None:
    payload_path = tmp_path / "request.json"
    payload_path.write_text(json.dumps({"check_key": "contract.not_a_check"}), encoding="utf-8")

    result = _invoke(["verify", "contract-check", "--payload", str(payload_path)])

    assert result.exit_code == 1
    assert json.loads(result.output)["error"] == "Unknown contract check: contract.not_a_check"


def test_contract_check_schema_flag_prints_request_schema_without_payload() -> None:
    from gpd.core.contract_checks import RunContractCheckRequest

    result = _invoke(["verify", "contract-check", "--schema"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == RunContractCheckRequest.model_json_schema()


def test_contract_check_without_payload_or_schema_is_a_usage_error() -> None:
    result = _invoke(["verify", "contract-check"])

    assert result.exit_code == 1
    assert "--payload" in result.output


def _run_without_cli_runner(argv: list[str]) -> int:
    """Run the CLI against the live ``sys.stdin`` so an isatty stub is observable."""
    import typer.main

    command = typer.main.get_command(app)
    with pytest.raises(SystemExit) as exit_info:
        command.main(argv, prog_name="gpd", standalone_mode=True)
    return int(exit_info.value.code or 0)


def test_contract_check_stdin_marker_fails_fast_when_stdin_is_a_tty(monkeypatch, capsys) -> None:
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    exit_code = _run_without_cli_runner(["verify", "contract-check", "--payload", "-"])

    assert exit_code != 0
    stderr = capsys.readouterr().err
    assert "Usage" in stderr
    assert "piped on stdin" in stderr


def test_suggest_checks_stdin_marker_fails_fast_when_stdin_is_a_tty(monkeypatch, capsys) -> None:
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    exit_code = _run_without_cli_runner(["verify", "suggest-checks", "--contract", "-"])

    assert exit_code != 0
    stderr = capsys.readouterr().err
    assert "Usage" in stderr
    assert "piped on stdin" in stderr


def test_suggest_checks_matches_mcp_tool_payload(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _project_contract()
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    expected = suggest_contract_checks(copy.deepcopy(contract))
    result = _invoke(["verify", "suggest-checks", "--contract", str(contract_path)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert expected["suggested_count"] > 0


def test_suggest_checks_honours_repeated_active_checks(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _project_contract()
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    expected = suggest_contract_checks(copy.deepcopy(contract), ["5.16", "contract.limit_recovery"])
    result = _invoke(
        [
            "verify",
            "suggest-checks",
            "--contract",
            str(contract_path),
            "--active-checks",
            "5.16",
            "--active-checks",
            "contract.limit_recovery",
        ]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert any(suggestion["already_active"] for suggestion in expected["suggested_checks"])


def test_bundle_checklist_matches_mcp_tool_payload() -> None:
    from gpd.mcp.servers.verification_server import get_bundle_checklist

    expected = get_bundle_checklist(["stat-mech-simulation"])
    result = _invoke(["verify", "bundle-checklist", "stat-mech-simulation"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert expected["found"] is True
    assert expected["bundle_count"] == 1


def test_bundle_checklist_blank_bundle_id_exits_one() -> None:
    from gpd.mcp.servers.verification_server import get_bundle_checklist

    expected = get_bundle_checklist(["stat-mech-simulation", "   "])
    result = _invoke(["verify", "bundle-checklist", "stat-mech-simulation", "   "])

    assert result.exit_code == 1
    assert json.loads(result.output) == expected
    assert expected["error"] == "bundle_ids[1] must be a non-empty string"


def test_checklist_matches_mcp_tool_payload() -> None:
    from gpd.mcp.servers.verification_server import get_checklist

    expected = get_checklist("qft")
    result = _invoke(["verify", "checklist", "qft"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert expected["found"] is True
    assert expected["domain_check_count"] == len(expected["domain_checks"])


def test_checklist_unknown_domain_reports_available_domains_and_exits_one() -> None:
    from gpd.mcp.servers.verification_server import get_checklist

    expected = get_checklist("not-a-domain")
    result = _invoke(["verify", "checklist", "not-a-domain"])

    assert result.exit_code == 1
    assert json.loads(result.output) == expected
    assert expected["found"] is False
    assert "qft" in expected["available_domains"]


def test_coverage_matches_mcp_tool_payload_for_csv_and_repeated_options() -> None:
    from gpd.mcp.servers.verification_server import get_verification_coverage

    expected = get_verification_coverage([15, 22], ["5.1", "5.2"])

    csv_result = _invoke(["verify", "coverage", "--error-classes", "15,22", "--active-checks", "5.1,5.2"])
    repeated_result = _invoke(
        [
            "verify",
            "coverage",
            "--error-classes",
            "15",
            "--error-classes",
            "22",
            "--active-checks",
            "5.1",
            "--active-checks",
            "5.2",
        ]
    )

    assert csv_result.exit_code == 0, csv_result.output
    assert json.loads(csv_result.output) == expected
    assert json.loads(repeated_result.output) == expected
    assert expected["total_classes"] == 2


def test_coverage_rejects_non_numeric_error_class_ids() -> None:
    result = _invoke(["verify", "coverage", "--error-classes", "15,oops", "--active-checks", "5.1"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert "oops" in payload["error"]


def test_coverage_rejects_error_class_values_that_int_would_reject() -> None:
    for value in ("-5", "-", "²"):
        result = _invoke(["verify", "coverage", "--error-classes", value, "--active-checks", "5.1"])

        assert result.exit_code == 1, f"{value!r} slipped past the error-class id guard"
        assert value in json.loads(result.output)["error"]


def test_coverage_empty_error_class_csv_is_a_usage_error_not_full_coverage() -> None:
    result = _invoke(["verify", "coverage", "--error-classes", ",", "--active-checks", "5.1"])

    assert result.exit_code != 0
    assert "Full coverage" not in result.output
    assert "--error-classes" in result.output


def test_coverage_dedupes_repeated_error_class_ids_order_preserving() -> None:
    from gpd.mcp.servers.verification_server import get_verification_coverage

    expected = get_verification_coverage([22, 15], ["5.1"])
    result = _invoke(["verify", "coverage", "--error-classes", "22,15,22", "--active-checks", "5.1"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert expected["total_classes"] == 2


def test_suggest_checks_splits_comma_separated_active_checks_like_coverage(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _project_contract()
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    expected = suggest_contract_checks(copy.deepcopy(contract), ["5.16", "contract.limit_recovery"])
    result = _invoke(
        [
            "verify",
            "suggest-checks",
            "--contract",
            str(contract_path),
            "--active-checks",
            "5.16,contract.limit_recovery",
        ]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert any(suggestion["already_active"] for suggestion in expected["suggested_checks"])


def test_bundle_checklist_unknown_bundle_id_exits_one() -> None:
    from gpd.mcp.servers.verification_server import get_bundle_checklist

    expected = get_bundle_checklist(["not-a-bundle"])
    result = _invoke(["verify", "bundle-checklist", "not-a-bundle"])

    assert result.exit_code == 1
    assert json.loads(result.output) == expected
    assert expected["missing_bundle_ids"] == ["not-a-bundle"]
