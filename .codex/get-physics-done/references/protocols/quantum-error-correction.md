---
load_when:
  - "quantum error correction"
  - "stabilizer code"
  - "surface code"
  - "toric code"
  - "logical qubit"
  - "fault tolerance"
  - "error threshold"
  - "syndrome"
  - "decoder"
tier: 2
context_cost: medium
---

# Quantum Error Correction Protocol

Quantum error correction (QEC) calculations require rigorous tracking of error models, code parameters, logical vs physical operations, and threshold estimates. The interplay between quantum information theory and many-body physics makes convention mismatches especially dangerous.

## Related Protocols

- See `group-theory.md` for stabilizer group structure and representations
- See `topological-methods.md` for topological codes and anyonic excitations
- See `numerical-computation.md` for Monte Carlo threshold estimation
- See `exact-diagonalization.md` for small-code exact simulation
- See `monte-carlo.md` for threshold estimation via statistical sampling

## Step 1: Declare Code Parameters and Error Model

Before any QEC calculation, explicitly state:

1. **Code family:** Stabilizer, subsystem, topological (surface, toric, color), concatenated, LDPC, or other. State the code parameters [[n, k, d]] (physical qubits, logical qubits, distance).
2. **Error model:** Depolarizing, dephasing, amplitude damping, erasure, biased noise, or circuit-level noise. State the error rate p and whether it is per-gate, per-cycle, or per-qubit.
3. **Stabilizer generators:** List all stabilizer generators S_i with their Pauli string representations. Verify: all generators commute, the group generated has order 2^{n-k}, and no stabilizer is proportional to the identity.
4. **Logical operators:** State the logical X and Z operators for each logical qubit. Verify: they commute with all stabilizers, anticommute with each other (for the same logical qubit), and have weight >= d.

## Step 2: Stabilizer Formalism Verification

1. **Commutativity:** Verify [S_i, S_j] = 0 for all pairs of stabilizer generators. For Pauli operators, this is equivalent to checking that the symplectic inner product of their binary representations is 0.
2. **Independence:** Verify the stabilizer generators are independent (no generator is a product of others). The number of independent generators should be n - k.
3. **Logical operator independence:** Verify logical operators are not in the stabilizer group. A logical operator that is also a stabilizer would mean the "logical" degree of freedom is fixed, reducing k.
4. **Code distance verification:** d = min weight of a logical operator (operator that commutes with all stabilizers but is not in the stabilizer group). For small codes, enumerate all such operators. For large codes, use bounds (Singleton, Hamming, quantum Singleton/Knill-Laflamme).

## Step 3: Syndrome Measurement and Decoding

1. **Syndrome extraction:** Each stabilizer measurement yields a bit (eigenvalue +1 or -1). The syndrome is the binary vector of all measurement outcomes. Verify the syndrome space has dimension n - k.
2. **Error correction condition:** The Knill-Laflamme conditions: for correctable errors E_a, E_b, we need P E_a^dagger E_b P = alpha_{ab} P, where P is the codespace projector. Verify this for the claimed set of correctable errors.
3. **Decoder specification:** State the decoding algorithm (minimum weight, MWPM, union-find, tensor network, neural network). Note that optimal decoding is #P-hard in general; practical decoders trade optimality for efficiency.
4. **Logical error rate:** After decoding, the logical error rate p_L should decrease with increasing code distance d. For a code with threshold p_th, p_L ~ (p/p_th)^{d/2} for p < p_th.

## Step 4: Threshold Estimation

1. **Monte Carlo simulation:** Generate random errors according to the noise model, decode, and count logical failures. The threshold is the crossing point of logical error rate curves for different code distances.
2. **Statistical rigor:** Report error bars from finite sampling. Use enough samples that the statistical uncertainty is smaller than the claimed precision of p_th. Typical: 10^4-10^6 samples per data point.
3. **Finite-size scaling:** Near threshold, use scaling collapse: p_L = f((p - p_th) * d^{1/nu}) where nu is the correlation length exponent. Verify the scaling collapse quality.
4. **Circuit-level vs phenomenological:** Distinguish between phenomenological noise (errors on data qubits only) and circuit-level noise (errors on all operations including syndrome measurement). Circuit-level thresholds are always lower.

## Step 5: Fault Tolerance Verification

1. **Fault-tolerant operations:** Verify that syndrome extraction circuits are fault-tolerant (a single fault does not cause two data errors in the same code block). This typically requires verified or flagged circuits.
2. **Transversal gates:** Verify which gates are transversal (bit-wise) for the code. By the Eastin-Knill theorem, no code has a universal transversal gate set.
3. **Magic state distillation:** If non-Clifford gates are needed (typically T gates), verify the magic state distillation protocol, its overhead scaling, and the required input state fidelity.
4. **Overhead counting:** Report the total qubit overhead (physical qubits per logical qubit) and the total time overhead (physical gates per logical gate) for the claimed fault-tolerant scheme.

## Step 6: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Stabilizer commutativity | Symplectic inner product check | Non-commuting generators |
| Code parameters | Count independent stabilizers | Wrong [[n,k,d]] |
| Distance verification | Minimum weight logical operator | Overestimated distance |
| Knill-Laflamme conditions | Matrix element calculation | Non-correctable errors claimed correctable |
| Threshold bounds | Known bounds for code family | Unrealistic threshold claims |
| Overhead scaling | Asymptotic analysis | Impractical resource requirements |

## Common LLM Errors in QEC

1. **Confusing classical and quantum error correction:** Quantum codes must handle phase errors, not just bit-flip errors. A classical [n,k,d] code does not directly give a quantum [[n,k,d]] code.
2. **Wrong code distance:** Claiming d = 3 when a weight-2 logical operator exists (true d = 2). Always verify by exhaustive search for small codes.
3. **Ignoring measurement errors:** Syndrome measurements can also have errors. A single round of syndrome measurement is not sufficient for fault tolerance — need d rounds (or more with error correction on syndromes).
4. **Threshold overestimation:** Using phenomenological noise model thresholds (~10%) when circuit-level thresholds (~1%) are appropriate.
5. **Forgetting Eastin-Knill:** Claiming a universal transversal gate set, which is impossible for any error-correcting code.

## Standard References

- Nielsen & Chuang: *Quantum Computation and Quantum Information* (standard textbook)
- Gottesman: *Stabilizer Codes and Quantum Error Correction* (arXiv:quant-ph/9705052)
- Dennis et al.: *Topological quantum memory* (arXiv:quant-ph/0110143, surface code analysis)
- Fowler et al.: *Surface codes: Towards practical large-scale quantum computation* (arXiv:1208.0928)
- Terhal: *Quantum error correction for quantum memories* (Rev. Mod. Phys. 87, 307, 2015)
