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


def _parse_qasm(qasm_str: str) -> object:
    """Parse an OpenQASM string, attempting QASM 3 then QASM 2.

    Falls back through: qiskit.qasm3.loads -> qiskit.qasm2.loads -> QuantumCircuit.from_qasm_str.
    """
    from qiskit import QuantumCircuit

    # Try QASM 3 first (only if the module is available).
    try:
        import qiskit.qasm3
        return qiskit.qasm3.loads(qasm_str)
    except ImportError:
        pass
    except (ValueError, qiskit.qasm3.QASM3ImporterError if hasattr(qiskit, 'qasm3') else Exception):
        logger.debug("QASM 3 parse failed, falling back to QASM 2")

    # Try QASM 2 (only if the module is available).
    try:
        import qiskit.qasm2
        return qiskit.qasm2.loads(qasm_str)
    except ImportError:
        pass
    except (ValueError, Exception) as e:
        logger.debug("QASM 2 parse failed (%s), falling back to legacy", e)

    return QuantumCircuit.from_qasm_str(qasm_str)


@mcp.tool()
def compare_circuits(
    ref_qasm: str,
    new_qasm: str,
    sim_reps: int = 3,
) -> dict[str, object]:
    """Compare two quantum circuits on gate counts, fidelity, and simulation time.

    Accepts OpenQASM 2.0 or 3.0 strings for the reference and new circuits.
    Returns stats for both circuits plus unitary and average state fidelity.

    Args:
        ref_qasm: OpenQASM string for the reference circuit
        new_qasm: OpenQASM string for the new/optimized circuit
        sim_reps: Number of simulation repetitions for timing (default 3)
    """
    err = _check_qiskit()
    if err:
        return stable_mcp_error(err)
    if sim_reps < 1:
        return stable_mcp_error("sim_reps must be >= 1")

    from gpd.core.quantum_benchmarks import compare_circuits as _compare

    try:
        qc_ref = _parse_qasm(ref_qasm)
        qc_new = _parse_qasm(new_qasm)
    except Exception as e:
        return stable_mcp_error(f"Failed to parse QASM: {e}")

    try:
        result = _compare(qc_ref, qc_new, sim_reps=sim_reps)
    except Exception as e:
        return stable_mcp_error(f"Benchmark comparison failed: {e}")
    return stable_mcp_response(result.to_dict())


@mcp.tool()
def decide_better(
    ref_qasm: str,
    new_qasm: str,
    fidelity_threshold: float = 0.999,
    weight_twoq: float = 2.0,
    weight_depth: float = 1.0,
    weight_time: float = 0.0,
    sim_reps: int = 3,
) -> dict[str, object]:
    """Decide whether a new quantum circuit improves on a reference.

    Runs full comparison then applies the Pareto-frontier decision engine.
    New wins if fidelity >= threshold AND weighted cost is lower.
    Cost = weight_twoq * two_qubit_gates + weight_depth * depth + weight_time * sim_time.

    Args:
        ref_qasm: OpenQASM string for the reference circuit
        new_qasm: OpenQASM string for the new/optimized circuit
        fidelity_threshold: Minimum fidelity to accept the new circuit (default 0.999)
        weight_twoq: Cost weight for two-qubit gates (default 2.0)
        weight_depth: Cost weight for circuit depth (default 1.0)
        weight_time: Cost weight for simulation time (default 0.0, informational only)
        sim_reps: Number of simulation repetitions for timing (default 3)
    """
    err = _check_qiskit()
    if err:
        return stable_mcp_error(err)
    if sim_reps < 1:
        return stable_mcp_error("sim_reps must be >= 1")

    from gpd.core.quantum_benchmarks import CostWeights
    from gpd.core.quantum_benchmarks import compare_circuits as _compare
    from gpd.core.quantum_benchmarks import decide_better as _decide

    try:
        qc_ref = _parse_qasm(ref_qasm)
        qc_new = _parse_qasm(new_qasm)
    except Exception as e:
        return stable_mcp_error(f"Failed to parse QASM: {e}")

    try:
        result = _compare(qc_ref, qc_new, sim_reps=sim_reps)
        weights = CostWeights(twoq=weight_twoq, depth=weight_depth, time=weight_time)
        decision = _decide(result, fidelity_threshold=fidelity_threshold, weights=weights)
    except Exception as e:
        return stable_mcp_error(f"Decision evaluation failed: {e}")

    payload = decision.to_dict()
    payload["comparison"] = result.to_dict()
    payload["rationale"] = decision.rationale(fidelity_threshold=fidelity_threshold)
    return stable_mcp_response(payload)


@mcp.tool()
def circuit_stats(
    qasm: str,
) -> dict[str, object]:
    """Get gate counts, depth, and circuit statistics for a quantum circuit.

    Args:
        qasm: OpenQASM string for the circuit to analyze
    """
    err = _check_qiskit()
    if err:
        return stable_mcp_error(err)

    from gpd.core.quantum_benchmarks import circuit_stats as _stats

    try:
        qc = _parse_qasm(qasm)
    except Exception as e:
        return stable_mcp_error(f"Failed to parse QASM: {e}")

    try:
        stats = _stats(qc)
    except Exception as e:
        return stable_mcp_error(f"Circuit stats failed: {e}")
    return stable_mcp_response(stats.to_dict())


def main() -> None:
    tighten_registered_tool_contracts(mcp)
    mcp.run()


if __name__ == "__main__":
    main()
