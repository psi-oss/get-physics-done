from __future__ import annotations

import copy

from gpd.mcp.servers.verification_server import run_contract_check

_N = 20


def _request(*, claim_offset: float = 0.0, drift_at: int | None = None, drift: float = 0.0, **overrides):
    claim = [1.0 + 0.1 * i for i in range(_N)]
    blind = [c + claim_offset for c in claim]
    if drift_at is not None:
        blind[drift_at] = claim[drift_at] + drift
    request: dict = {
        "check_key": "contract.numeric_oracle_agreement",
        "metadata": {
            "contracted_observable_id": "obs-1",
            "contracted_observable_kind": "scalar",
            "typed_restatement_observable_id": "obs-1",
            "typed_restatement_observable_kind": "scalar",
            "typed_restatement_statement": "value of F at the sampled points",
            "numeric_tolerance": 1e-6,
            "min_shared_points": 20,
            "claim_cell_hash": "a" * 64,
            "blind_cell_hash": "b" * 64,
        },
        "observed": {
            "sample_points": [{"x": str(i)} for i in range(_N)],
            "claim_values": claim,
            "blind_values": blind,
        },
    }
    for key, value in overrides.items():
        if key in ("metadata", "observed"):
            request[key] = {**request[key], **value}
        else:
            request[key] = value
    return request


def test_agreement_passes() -> None:
    result = run_contract_check(_request())
    assert result["status"] == "pass"
    assert result["evidence_directness"] == "direct"
    assert result["metrics"]["numeric_oracle_verdict"]["verdict"] == "GREEN"
    assert result["metrics"]["verdict_hash"].startswith("sha256:")


def test_disagreement_fails() -> None:
    result = run_contract_check(_request(drift_at=5, drift=0.5))
    assert result["status"] == "fail"
    assert result["metrics"]["numeric_oracle_verdict"]["verdict"] == "RED"
    assert result["metrics"]["numeric_oracle_verdict"]["worst_point_index"] == 5
    assert result["automated_issues"]


def test_missing_cell_hash_is_inconclusive() -> None:
    request = _request()
    del request["metadata"]["claim_cell_hash"]
    result = run_contract_check(request)
    assert result["status"] == "insufficient_evidence"
    assert result["metrics"]["numeric_oracle_verdict"]["verdict"] == "INCONCLUSIVE"
    assert result["metrics"]["numeric_oracle_verdict"]["both_cells_present"] is False
    assert any("cell_hash" in item for item in result["missing_inputs"])


def test_fidelity_mismatch_is_inconclusive_despite_agreement() -> None:
    result = run_contract_check(
        _request(metadata={"typed_restatement_observable_id": "obs-other"})
    )
    assert result["status"] == "insufficient_evidence"
    verdict = result["metrics"]["numeric_oracle_verdict"]
    assert verdict["verdict"] == "INCONCLUSIVE"
    assert verdict["fidelity_ok"] is False
    assert verdict["agreeing_points"] == _N


def test_too_few_points_is_inconclusive_via_missing_inputs() -> None:
    request = _request()
    request["observed"]["sample_points"] = request["observed"]["sample_points"][:5]
    request["observed"]["claim_values"] = request["observed"]["claim_values"][:5]
    request["observed"]["blind_values"] = request["observed"]["blind_values"][:5]
    request["metadata"]["min_shared_points"] = 20
    result = run_contract_check(request)
    assert result["status"] == "insufficient_evidence"
    # Five usable points provided, comparison reports INCONCLUSIVE on sufficiency.
    assert result["metrics"]["numeric_oracle_verdict"]["verdict"] == "INCONCLUSIVE"


def test_missing_observed_lists_report_missing_inputs() -> None:
    request = _request()
    del request["observed"]["claim_values"]
    result = run_contract_check(request)
    assert result["status"] == "insufficient_evidence"
    assert "observed.claim_values" in result["missing_inputs"]
    # No verdict is built when prerequisites are absent.
    assert "numeric_oracle_verdict" not in result["metrics"]


def test_unknown_metadata_key_is_rejected() -> None:
    request = _request(metadata={"bogus_key": "x"})
    result = run_contract_check(request)
    assert result.get("status") == "error" or result.get("error")


def test_non_positive_tolerance_is_an_input_error() -> None:
    request = _request(metadata={"numeric_tolerance": 0.0})
    result = run_contract_check(request)
    assert result.get("status") == "error" or result.get("error")


def test_deterministic_verdict_hash_across_calls() -> None:
    first = run_contract_check(_request())
    second = run_contract_check(copy.deepcopy(_request()))
    assert (
        first["metrics"]["verdict_hash"]
        == second["metrics"]["verdict_hash"]
    )
