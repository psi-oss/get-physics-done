"""Tests for the quantum benchmark MCP server.

Tests the MCP tool functions directly. When qiskit is not installed,
verifies graceful error handling.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gpd.core.quantum_benchmarks import (
    CircuitStats,
    ComparisonResult,
    CostWeights,
    decide_better,
)


class TestDecisionEngine:
    """Test the decide_better logic without qiskit."""

    def _make_result(
        self,
        ref_twoq: int = 6,
        new_twoq: int = 3,
        ref_depth: int = 10,
        new_depth: int = 8,
        ref_time: float = 0.1,
        new_time: float = 0.05,
        unitary_f: float | None = 1.0,
        avg_f: float | None = 0.9995,
    ) -> ComparisonResult:
        return ComparisonResult(
            ref_stats=CircuitStats(
                total_gates=20,
                two_qubit_gates=ref_twoq,
                single_qubit_gates=14,
                depth=ref_depth,
                counts={"cx": ref_twoq, "h": 14},
            ),
            new_stats=CircuitStats(
                total_gates=15,
                two_qubit_gates=new_twoq,
                single_qubit_gates=12,
                depth=new_depth,
                counts={"cz": new_twoq, "h": 12},
            ),
            unitary_fidelity=unitary_f,
            avg_state_fidelity=avg_f,
            sim_time_ref=ref_time,
            sim_time_new=new_time,
        )

    def test_new_wins_lower_cost_high_fidelity(self):
        result = self._make_result()
        decision = decide_better(result)
        assert decision.better is True
        assert decision.meets_fidelity is True
        assert decision.cost_new < decision.cost_ref
        assert decision.fidelity_source == "avg_state"

    def test_new_loses_low_fidelity(self):
        result = self._make_result(avg_f=0.95)
        decision = decide_better(result, fidelity_threshold=0.999)
        assert decision.better is False
        assert decision.meets_fidelity is False

    def test_new_loses_higher_cost(self):
        result = self._make_result(new_twoq=10, new_depth=15, new_time=0.5)
        decision = decide_better(result)
        assert decision.better is False
        assert decision.meets_fidelity is True
        assert decision.cost_new > decision.cost_ref

    def test_no_fallback_to_unitary_fidelity(self):
        result = self._make_result(avg_f=None, unitary_f=0.9999)
        decision = decide_better(result)
        assert decision.better is False
        assert decision.fidelity is None
        assert decision.fidelity_source == "none"

    def test_no_fidelity_fails_closed(self):
        result = self._make_result(avg_f=None, unitary_f=None)
        decision = decide_better(result)
        assert decision.better is False
        assert decision.meets_fidelity is False
        assert decision.fidelity is None

    def test_custom_weights(self):
        result = self._make_result(new_twoq=6, new_depth=5, new_time=0.01)
        weights = CostWeights(twoq=0.0, depth=10.0, time=0.0)
        decision = decide_better(result, weights=weights)
        assert decision.better is True
        assert decision.cost_ref == 100.0
        assert decision.cost_new == 50.0

    def test_decision_to_dict(self):
        result = self._make_result()
        decision = decide_better(result)
        d = decision.to_dict()
        assert "better" in d
        assert "weights" in d
        assert d["weights"]["twoq"] == 2.0
        assert d["fidelity_source"] == "avg_state"
        assert "pareto" in d
        assert "two_qubit_gates" in d["pareto"]
        assert "depth" in d["pareto"]
        assert "sim_time" in d["pareto"]

    def test_pareto_improvement_pct(self):
        result = self._make_result(ref_twoq=6, new_twoq=3, ref_depth=10, new_depth=8)
        decision = decide_better(result)
        pareto = decision.pareto
        assert pareto["two_qubit_gates"]["improvement_pct"] == pytest.approx(-50.0)
        assert pareto["depth"]["improvement_pct"] == pytest.approx(-20.0)

    def test_rationale_winner(self):
        result = self._make_result()
        decision = decide_better(result)
        text = decision.rationale(fidelity_threshold=0.999)
        assert "WINNER" in text
        assert "avg_state" in text

    def test_rationale_rejected_fidelity(self):
        result = self._make_result(avg_f=0.95)
        decision = decide_better(result, fidelity_threshold=0.999)
        text = decision.rationale(fidelity_threshold=0.999)
        assert "REJECTED" in text
        assert "Fidelity below threshold" in text

    def test_rationale_no_fidelity(self):
        result = self._make_result(avg_f=None, unitary_f=None)
        decision = decide_better(result)
        text = decision.rationale()
        assert "No fidelity data available" in text


class TestMCPToolsWithoutQiskit:
    """Test MCP tools gracefully handle missing qiskit."""

    def test_compare_circuits_no_qiskit(self):
        with patch("gpd.mcp.servers.quantum_benchmark_server._check_qiskit", return_value="qiskit not installed"):
            from gpd.mcp.servers.quantum_benchmark_server import compare_circuits

            result = compare_circuits("", "")
            assert "error" in str(result).lower() or "iserror" in str(result).lower()
            assert "qiskit not installed" in str(result)

    def test_decide_better_no_qiskit(self):
        with patch("gpd.mcp.servers.quantum_benchmark_server._check_qiskit", return_value="qiskit not installed"):
            from gpd.mcp.servers.quantum_benchmark_server import decide_better as mcp_decide

            result = mcp_decide("", "")
            assert "error" in str(result).lower() or "iserror" in str(result).lower()
            assert "qiskit not installed" in str(result)

    def test_circuit_stats_no_qiskit(self):
        with patch("gpd.mcp.servers.quantum_benchmark_server._check_qiskit", return_value="qiskit not installed"):
            from gpd.mcp.servers.quantum_benchmark_server import circuit_stats

            result = circuit_stats("")
            assert "error" in str(result).lower() or "iserror" in str(result).lower()
            assert "qiskit not installed" in str(result)


class TestCircuitStats:
    """Test CircuitStats dataclass."""

    def test_to_dict(self):
        stats = CircuitStats(
            total_gates=10,
            two_qubit_gates=3,
            single_qubit_gates=7,
            depth=5,
            counts={"cx": 3, "h": 7},
        )
        d = stats.to_dict()
        assert d["total_gates"] == 10
        assert d["two_qubit_gates"] == 3
        assert d["depth"] == 5
        assert d["counts"] == {"cx": 3, "h": 7}

    def test_frozen(self):
        stats = CircuitStats(
            total_gates=10,
            two_qubit_gates=3,
            single_qubit_gates=7,
            depth=5,
        )
        with pytest.raises(AttributeError):
            stats.total_gates = 20  # type: ignore[misc]


class TestComparisonResult:
    """Test ComparisonResult serialization."""

    def test_to_dict(self):
        result = ComparisonResult(
            ref_stats=CircuitStats(10, 3, 7, 5, {"cx": 3}),
            new_stats=CircuitStats(8, 2, 6, 4, {"cz": 2}),
            unitary_fidelity=0.999,
            avg_state_fidelity=0.998,
            sim_time_ref=0.1,
            sim_time_new=0.05,
        )
        d = result.to_dict()
        assert d["unitary_fidelity"] == 0.999
        assert d["sim_time_ref_sec"] == 0.1
        assert "ref" in d
        assert "new" in d
