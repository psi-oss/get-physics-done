"""Quantum circuit benchmark verification for GPD agents.

Provides fidelity metrics (process fidelity, average state fidelity),
circuit cost analysis, and a Pareto-frontier decision engine for evaluating
whether a newly derived quantum circuit improves on a reference.

Requires: qiskit (optional dependency group 'quantum').
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


def _qiskit_available() -> bool:
    try:
        from qiskit import QuantumCircuit  # noqa: F401
        from qiskit.quantum_info import Operator, Statevector  # noqa: F401

        return True
    except ImportError:
        return False


@dataclass(frozen=True)
class CircuitStats:
    total_gates: int
    two_qubit_gates: int
    single_qubit_gates: int
    depth: int
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_gates": self.total_gates,
            "two_qubit_gates": self.two_qubit_gates,
            "single_qubit_gates": self.single_qubit_gates,
            "depth": self.depth,
            "counts": dict(self.counts),
        }




def circuit_stats(qc: object) -> CircuitStats:
    """Extract gate counts and depth from a Qiskit QuantumCircuit."""
    if not _qiskit_available():
        raise RuntimeError("qiskit is required for circuit_stats")
    counts = qc.count_ops()  # type: ignore[union-attr]
    total = int(sum(counts.values()))
    
    twoq = 0
    if hasattr(qc, "data"):
        for instr in qc.data:
            qargs = getattr(instr, "qubits", None)
            if qargs is None and isinstance(instr, tuple) and len(instr) > 1:
                qargs = instr[1]
            if qargs is not None and len(qargs) == 2:
                twoq += 1

    return CircuitStats(
        total_gates=total,
        two_qubit_gates=twoq,
        single_qubit_gates=total - twoq,
        depth=int(qc.depth()),  # type: ignore[union-attr]
        counts={k: int(v) for k, v in counts.items()},
    )


def unitary_fidelity(qc1: object, qc2: object, *, max_qubits: int = 5) -> float | None:
    """Process fidelity via unitary overlap: F = |Tr(U1^dag U2)|^2 / d^2.

    Returns None if circuits are too large or qiskit is unavailable.
    """
    if not _qiskit_available():
        return None
    import numpy as np
    from qiskit.quantum_info import Operator

    n = qc1.num_qubits  # type: ignore[union-attr]
    if n != qc2.num_qubits or n > max_qubits:  # type: ignore[union-attr]
        return None
    u1 = Operator(qc1).data
    u2 = Operator(qc2).data
    overlap = np.trace(np.conjugate(u1.T) @ u2)
    return float(np.abs(overlap)**2 / (2**(2*n)))


def average_state_fidelity(
    qc1: object, qc2: object, *, trials: int = 64, seed: int | None = 123, max_qubits: int = 5
) -> float | None:
    """Average state fidelity over Haar-random input states.

    Returns None if qiskit is unavailable, circuits are too large, or qubit counts mismatch.
    """
    if not _qiskit_available():
        return None
    import numpy as np
    from qiskit.quantum_info import Statevector

    if qc1.num_qubits != qc2.num_qubits:  # type: ignore[union-attr]
        return None
    n = qc1.num_qubits  # type: ignore[union-attr]
    if n > max_qubits:
        return None
    rng = np.random.default_rng(seed)
    d = 2**n
    acc = 0.0
    for _ in range(trials):
        v = rng.normal(size=d) + 1j * rng.normal(size=d)
        v = v / np.linalg.norm(v)
        sv = Statevector(v)
        psi1 = Statevector(sv).evolve(qc1).data
        psi2 = Statevector(sv).evolve(qc2).data
        acc += float(np.abs(np.vdot(psi1, psi2)) ** 2)
    return acc / trials


def time_simulation(qc: object, *, reps: int = 3) -> float:
    """Average simulation time in seconds using statevector evolution."""
    if not _qiskit_available():
        return math.nan
    from qiskit.quantum_info import Statevector

    start = time.perf_counter()
    for _ in range(reps):
        Statevector.from_instruction(qc)
    end = time.perf_counter()
    return (end - start) / reps


@dataclass
class ComparisonResult:
    ref_stats: CircuitStats
    new_stats: CircuitStats
    unitary_fidelity: float | None
    avg_state_fidelity: float | None
    sim_time_ref: float
    sim_time_new: float

    def to_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref_stats.to_dict(),
            "new": self.new_stats.to_dict(),
            "unitary_fidelity": self.unitary_fidelity,
            "avg_state_fidelity": self.avg_state_fidelity,
            "sim_time_ref_sec": self.sim_time_ref,
            "sim_time_new_sec": self.sim_time_new,
        }


def compare_circuits(qc_ref: object, qc_new: object, *, sim_reps: int = 3) -> ComparisonResult:
    """Compare two Qiskit QuantumCircuits on stats, fidelity, and timing."""
    return ComparisonResult(
        ref_stats=circuit_stats(qc_ref),
        new_stats=circuit_stats(qc_new),
        unitary_fidelity=unitary_fidelity(qc_ref, qc_new),
        avg_state_fidelity=average_state_fidelity(qc_ref, qc_new),
        sim_time_ref=time_simulation(qc_ref, reps=sim_reps),
        sim_time_new=time_simulation(qc_new, reps=sim_reps),
    )


@dataclass(frozen=True)
class CostWeights:
    twoq: float = 2.0
    depth: float = 1.0
    time: float = 0.0


def _pct_change(ref_val: float, new_val: float) -> float | None:
    """Calculate percentage change (negative = improvement / reduction)."""
    if ref_val == 0:
        return 0.0 if new_val == 0 else None
    return ((new_val - ref_val) / ref_val) * 100.0


@dataclass
class Decision:
    better: bool
    meets_fidelity: bool
    cost_ref: float
    cost_new: float
    fidelity: float | None
    fidelity_source: str  # "avg_state" or "none"
    weights: CostWeights
    pareto: dict[str, dict[str, float | None]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "better": self.better,
            "meets_fidelity": self.meets_fidelity,
            "cost_ref": self.cost_ref,
            "cost_new": self.cost_new,
            "fidelity": self.fidelity,
            "fidelity_source": self.fidelity_source,
            "weights": {"twoq": self.weights.twoq, "depth": self.weights.depth, "time": self.weights.time},
            "pareto": self.pareto,
        }

    def rationale(self, fidelity_threshold: float = 0.999) -> str:
        """Generate a human-readable decision explanation."""
        lines = []
        if self.fidelity is not None:
            if self.meets_fidelity:
                lines.append(f"✅ Fidelity {self.fidelity:.4f} >= {fidelity_threshold:.4f} (meets threshold, source: {self.fidelity_source})")
            else:
                lines.append(f"❌ Fidelity {self.fidelity:.4f} < {fidelity_threshold:.4f} (fails threshold, source: {self.fidelity_source})")
        else:
            lines.append("⚠️  No fidelity data available (avg_state_fidelity was None)")

        cost_savings = self.cost_ref - self.cost_new
        cost_pct = (cost_savings / self.cost_ref * 100) if self.cost_ref > 0 else 0.0
        lines.append(f"\nCost (weights: 2Q={self.weights.twoq}, depth={self.weights.depth}, time={self.weights.time}):")
        lines.append(f"  Reference: {self.cost_ref:.2f}")
        lines.append(f"  New:       {self.cost_new:.2f}")
        lines.append(f"  Savings:   {cost_savings:+.2f} ({cost_pct:+.1f}%)")

        if self.pareto:
            lines.append("\nPareto Frontier:")
            for metric, data in self.pareto.items():
                imp = data.get("improvement_pct")
                if imp is None:
                    lines.append(f"  ⚠️  {metric}: {data['ref']:.1f} → {data['new']:.1f} (N/A)")
                else:
                    symbol = "📈" if imp < 0 else ("📉" if imp > 0 else "➡️ ")
                    lines.append(f"  {symbol} {metric}: {data['ref']:.1f} → {data['new']:.1f} ({imp:+.1f}%)")

        if self.better:
            lines.append(f"\n🏆 WINNER: New circuit (fidelity OK, {abs(cost_pct):.1f}% cost reduction)")
        elif not self.meets_fidelity:
            lines.append("\n❌ REJECTED: Fidelity below threshold")
        else:
            lines.append(f"\n❌ REJECTED: New circuit is more expensive ({cost_pct:+.1f}%)")

        return "\n".join(lines)


def decide_better(
    result: ComparisonResult,
    *,
    fidelity_threshold: float = 0.999,
    weights: CostWeights | None = None,
) -> Decision:
    """Decide whether 'new' circuit beats 'ref' on a weighted cost metric.

    New wins if: avg_state_fidelity >= threshold AND cost_new < cost_ref.
    Cost = w_twoq * two_qubit_gates + w_depth * depth + w_time * sim_time.

    Note: w_time defaults to 0.0 — simulation time is informational only
    unless explicitly re-weighted. The decision does NOT fall back to
    unitary_fidelity because it is on a different scale (process fidelity
    vs average state fidelity).
    """
    if weights is None:
        weights = CostWeights()

    f = result.avg_state_fidelity
    fidelity_source = "avg_state" if f is not None else "none"

    cost_ref = (
        weights.twoq * result.ref_stats.two_qubit_gates
        + weights.depth * result.ref_stats.depth
        + weights.time * result.sim_time_ref
    )
    cost_new = (
        weights.twoq * result.new_stats.two_qubit_gates
        + weights.depth * result.new_stats.depth
        + weights.time * result.sim_time_new
    )

    meets_fidelity = (f is not None) and (f >= fidelity_threshold)
    better = meets_fidelity and (cost_new < cost_ref)

    pareto = {
        "two_qubit_gates": {
            "ref": float(result.ref_stats.two_qubit_gates),
            "new": float(result.new_stats.two_qubit_gates),
            "improvement_pct": _pct_change(
                result.ref_stats.two_qubit_gates, result.new_stats.two_qubit_gates
            ),
        },
        "depth": {
            "ref": float(result.ref_stats.depth),
            "new": float(result.new_stats.depth),
            "improvement_pct": _pct_change(
                result.ref_stats.depth, result.new_stats.depth
            ),
        },
        "sim_time": {
            "ref": float(result.sim_time_ref),
            "new": float(result.sim_time_new),
            "improvement_pct": _pct_change(
                result.sim_time_ref, result.sim_time_new
            ),
        },
    }

    return Decision(
        better=better,
        meets_fidelity=meets_fidelity,
        cost_ref=cost_ref,
        cost_new=cost_new,
        fidelity=f,
        fidelity_source=fidelity_source,
        weights=weights,
        pareto=pareto,
    )
