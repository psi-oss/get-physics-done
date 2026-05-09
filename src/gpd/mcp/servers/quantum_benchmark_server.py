"""MCP server for GPD quantum circuit benchmarking.

Exposes circuit comparison and decision tools so solver agents can
verify newly derived quantum circuits against reference implementations.

Usage:
    python -m gpd.mcp.servers.quantum_benchmark_server
    # or via entry point:
    gpd-mcp-quantum-benchmark
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from gpd.mcp.servers import (
    configure_mcp_logging,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)

logger = configure_mcp_logging("gpd-quantum-benchmark")

mcp = FastMCP("gpd-quantum-benchmark")


def _check_qiskit() -> str | None:
    """Return error message if qiskit is not importable, else None."""
    try:
        from qiskit import QuantumCircuit  # noqa: F401

        return None
    except ImportError:
        return "qiskit is not installed. Install with: pip install get-physics-done[quantum]"


@mcp.tool()
def compare_circuits(
    ref_qasm: str,
    new_qasm: str,
    sim_reps: int = 3,
) -> dict[str, object]:
    """Compare two quantum circuits on gate counts, fidelity, and simulation time.

    Accepts OpenQASM 2.0 strings for the reference and new circuits.
    Returns stats for both circuits plus unitary and average state fidelity.

    Args:
        ref_qasm: OpenQASM 2.0 string for the reference circuit
        new_qasm: OpenQASM 2.0 string for the new/optimized circuit
        sim_reps: Number of simulation repetitions for timing (default 3)
    """
    err = _check_qiskit()
    if err:
        return stable_mcp_error(err)

    from qiskit import QuantumCircuit

    from gpd.core.quantum_benchmarks import compare_circuits as _compare

    try:
        qc_ref = QuantumCircuit.from_qasm_str(ref_qasm)
        qc_new = QuantumCircuit.from_qasm_str(new_qasm)
    except Exception as e:
        return stable_mcp_error(f"Failed to parse QASM: {e}")

    result = _compare(qc_ref, qc_new, sim_reps=sim_reps)
    return stable_mcp_response(result.to_dict())


@mcp.tool()
def decide_better(
    ref_qasm: str,
    new_qasm: str,
    fidelity_threshold: float = 0.999,
    weight_twoq: float = 2.0,
    weight_depth: float = 1.0,
    weight_time: float = 1.0,
    sim_reps: int = 3,
) -> dict[str, object]:
    """Decide whether a new quantum circuit improves on a reference.

    Runs full comparison then applies the Pareto-frontier decision engine.
    New wins if fidelity >= threshold AND weighted cost is lower.
    Cost = weight_twoq * two_qubit_gates + weight_depth * depth + weight_time * sim_time.

    Args:
        ref_qasm: OpenQASM 2.0 string for the reference circuit
        new_qasm: OpenQASM 2.0 string for the new/optimized circuit
        fidelity_threshold: Minimum fidelity to accept the new circuit (default 0.999)
        weight_twoq: Cost weight for two-qubit gates (default 2.0)
        weight_depth: Cost weight for circuit depth (default 1.0)
        weight_time: Cost weight for simulation time (default 1.0)
        sim_reps: Number of simulation repetitions for timing (default 3)
    """
    err = _check_qiskit()
    if err:
        return stable_mcp_error(err)

    from qiskit import QuantumCircuit

    from gpd.core.quantum_benchmarks import CostWeights
    from gpd.core.quantum_benchmarks import compare_circuits as _compare
    from gpd.core.quantum_benchmarks import decide_better as _decide

    try:
        qc_ref = QuantumCircuit.from_qasm_str(ref_qasm)
        qc_new = QuantumCircuit.from_qasm_str(new_qasm)
    except Exception as e:
        return stable_mcp_error(f"Failed to parse QASM: {e}")

    result = _compare(qc_ref, qc_new, sim_reps=sim_reps)
    weights = CostWeights(twoq=weight_twoq, depth=weight_depth, time=weight_time)
    decision = _decide(result, fidelity_threshold=fidelity_threshold, weights=weights)

    payload = decision.to_dict()
    payload["comparison"] = result.to_dict()
    return stable_mcp_response(payload)


@mcp.tool()
def circuit_stats(
    qasm: str,
) -> dict[str, object]:
    """Get gate counts, depth, and circuit statistics for a quantum circuit.

    Args:
        qasm: OpenQASM 2.0 string for the circuit to analyze
    """
    err = _check_qiskit()
    if err:
        return stable_mcp_error(err)

    from qiskit import QuantumCircuit

    from gpd.core.quantum_benchmarks import circuit_stats as _stats

    try:
        qc = QuantumCircuit.from_qasm_str(qasm)
    except Exception as e:
        return stable_mcp_error(f"Failed to parse QASM: {e}")

    stats = _stats(qc)
    return stable_mcp_response(stats.to_dict())


def main() -> None:
    tighten_registered_tool_contracts(mcp)
    mcp.run()


if __name__ == "__main__":
    main()
