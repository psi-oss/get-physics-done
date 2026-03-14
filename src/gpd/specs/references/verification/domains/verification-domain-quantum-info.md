---
load_when:
  - "quantum information verification"
  - "quantum computing"
  - "quantum channel"
  - "CPTP"
  - "entanglement"
  - "quantum error correction"
  - "qubit"
  - "density matrix"
  - "quantum capacity"
tier: 2
context_cost: large
---

# Verification Domain — Quantum Information & Quantum Computing

CPTP verification, entanglement measures, information-theoretic bounds, channel capacity, quantum error correction, and circuit correctness checks for quantum information and quantum computing projects.

**Load when:** Working on quantum channels, entanglement theory, quantum error correction, quantum algorithms, quantum cryptography, or quantum communication protocols.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-amo.md` — AMO physics (for physical qubit implementations)
- `references/verification/domains/verification-domain-condmat.md` — condensed matter (for topological qubits, many-body entanglement)

---

<cptp_verification>

## CPTP and Channel Verification

Quantum channels must be completely positive and trace-preserving (CPTP). Violations indicate a non-physical map.

**Kraus representation verification:**

```
For a quantum channel E(rho) = sum_k K_k rho K_k^dagger:

Trace preservation: sum_k K_k^dagger K_k = I  (EXACT equality)
Complete positivity: guaranteed by Kraus form if TP holds.

Verification:
1. COMPUTE: sum_k K_k^dagger K_k. Must equal identity matrix to machine precision.
   Deviation > 10^{-10}: likely a bug in Kraus operator construction.
2. For trace non-increasing (quantum instrument): sum_k K_k^dagger K_k <= I (all eigenvalues <= 1).
3. Number of Kraus operators <= d^2 where d = dim(H). If more: redundant operators (not wrong, but inefficient).
```

**Choi matrix verification:**

```
Choi matrix: J(E) = sum_{i,j} |i><j| tensor E(|i><j|)
           = (id tensor E)(|Omega><Omega|)  where |Omega> = sum_i |ii> (unnormalized maximally entangled)

Complete positivity <=> J(E) >= 0 (positive semidefinite)
Trace preservation <=> Tr_B[J(E)] = I_A

Verification:
1. COMPUTE: eigenvalues of J(E). ALL must be >= 0 (to machine precision).
   Any eigenvalue < -10^{-10}: channel is NOT completely positive.
2. COMPUTE: Tr_B[J(E)]. Must equal I/d for trace-preserving channel.
   If Tr_B[J(E)] = I: channel is TP (no normalization by d in Choi convention used here).
   WARNING: Different conventions exist. Some define J(E) with |Omega> = sum_i |ii>/sqrt(d).
   Always verify which convention your code uses.
3. RANK: rank(J(E)) = minimum number of Kraus operators needed.
```

**Stinespring dilation verification:**

```
Stinespring: E(rho) = Tr_E[V rho V^dagger] where V: H_A -> H_B tensor H_E is an isometry.

Verification:
1. COMPUTE: V^dagger V = I_A (isometry condition). Must be exact.
2. COMPUTE: Tr_E[V |psi><psi| V^dagger] for several pure states |psi> and verify
   it matches E(|psi><psi|) from Kraus representation.
3. Minimal dilation: dim(H_E) = rank(J(E)).
```

</cptp_verification>

<density_matrix_verification>

## Density Matrix and State Verification

Every quantum state must be a valid density matrix. Invalid states produce meaningless results.

**Density matrix validity:**

```
rho is a valid density matrix iff:
  1. rho = rho^dagger         (Hermitian)
  2. rho >= 0                 (positive semidefinite: all eigenvalues >= 0)
  3. Tr(rho) = 1              (normalization)

Verification:
1. COMPUTE: ||rho - rho^dagger||_F. Must be < 10^{-12}. If > 10^{-6}: state construction error.
2. COMPUTE: min eigenvalue of rho. Must be >= -10^{-12}. Significantly negative: non-physical state.
3. COMPUTE: Tr(rho). Must equal 1 to machine precision.
4. COMPUTE: Tr(rho^2). Must satisfy Tr(rho^2) <= 1. Equality iff pure state.
   If Tr(rho^2) > 1 + 10^{-10}: rho is not a valid density matrix.
```

**Pure state verification:**

```
|psi> is a valid pure state iff <psi|psi> = 1.
rho = |psi><psi| is pure iff Tr(rho^2) = 1 and rank(rho) = 1.

For bipartite pure states |psi_AB>:
  Schmidt decomposition: |psi> = sum_i lambda_i |a_i>|b_i> with sum lambda_i^2 = 1, lambda_i >= 0.
  Entanglement entropy: S(A) = -sum lambda_i^2 log(lambda_i^2) = S(B).

Verification:
1. COMPUTE: S(A) and S(B) independently from reduced density matrices. Must be EQUAL for pure |psi_AB>.
   If S(A) != S(B): the state is mixed (or there is a bug).
2. Schmidt coefficients must be non-negative and square-sum to 1.
```

</density_matrix_verification>

<entanglement_verification>

## Entanglement Verification

**PPT criterion (Peres-Horodecki):**

```
Partial transpose: rho^{T_B}_{ij,kl} = rho_{il,kj} (transpose on second subsystem).

If rho^{T_B} has any negative eigenvalue, rho is ENTANGLED.
For 2x2 and 2x3 systems: PPT is necessary AND sufficient for separability.
For larger systems: PPT is necessary but NOT sufficient (bound entangled states exist).

Verification:
1. COMPUTE: eigenvalues of rho^{T_B}. Sort them.
2. If min eigenvalue < -10^{-10}: state is ENTANGLED.
3. For 2x2 or 2x3: min eigenvalue >= 0 implies SEPARABLE.
4. For larger systems: min eigenvalue >= 0 means PPT (may still be bound entangled).
```

**Entanglement monotone properties:**

```
Any valid entanglement measure E must satisfy:
1. E(rho) >= 0 for all rho
2. E(rho) = 0 for all separable states
3. E does not increase under LOCC: E(Lambda_LOCC(rho)) <= E(rho)
4. E is convex (optional for some measures): E(sum p_i rho_i) <= sum p_i E(rho_i)

Specific measures and their ranges:
  Negativity: N(rho) = (||rho^{T_B}||_1 - 1) / 2. Range [0, (d-1)/2]. Zero for PPT states.
  Log-negativity: E_N = log_2(||rho^{T_B}||_1). Range [0, log_2(d)].
  Concurrence (2 qubits): C = max(0, lambda_1 - lambda_2 - lambda_3 - lambda_4). Range [0, 1].
  Entanglement of formation: E_F = h((1 + sqrt(1 - C^2))/2) where h is binary entropy. Range [0, 1].
  Entanglement entropy (pure states): S = -Tr(rho_A log_2 rho_A). Range [0, log_2(min(d_A, d_B))].

Verification:
1. COMPUTE: E(product state). Must be EXACTLY 0 (to machine precision).
2. COMPUTE: E(maximally entangled state). Must equal known maximum for that measure and dimension.
3. COMPUTE: E before and after a local unitary (U_A tensor U_B). Must be EQUAL (LU invariance).
4. COMPUTE: E before and after an LOCC map. Must NOT increase.
```

**Concurrence for two qubits (Wootters formula):**

```
C(rho) = max(0, lambda_1 - lambda_2 - lambda_3 - lambda_4)

where lambda_i are eigenvalues (in decreasing order) of sqrt(sqrt(rho) * rho_tilde * sqrt(rho)),
and rho_tilde = (sigma_y tensor sigma_y) rho* (sigma_y tensor sigma_y).

Verification:
1. All lambda_i must be real and non-negative.
2. C must be in [0, 1].
3. For Bell states: C = 1. For product states: C = 0. For Werner state rho_W = p|Phi+><Phi+| + (1-p)I/4:
   C = max(0, (3p-1)/2).
4. Entanglement of formation: E_F = h((1 + sqrt(1-C^2))/2). Verify consistency.
```

</entanglement_verification>

<entropy_verification>

## Entropy and Information Measures

**Von Neumann entropy:**

```
S(rho) = -Tr(rho log rho) = -sum_i lambda_i log(lambda_i)

Properties (ALL must be satisfied):
1. S(rho) >= 0. Zero iff rho is pure.
2. S(rho) <= log(d) where d = dim(H). Maximum for maximally mixed state I/d.
3. Unitary invariance: S(U rho U^dagger) = S(rho).
4. Concavity: S(sum p_i rho_i) >= sum p_i S(rho_i).

Convention: log base 2 -> bits; natural log -> nats. ALWAYS state which.

Verification:
1. COMPUTE: S for maximally mixed state I/d. Must equal log(d) exactly.
2. COMPUTE: S for pure state. Must be 0 exactly.
3. If S < 0 or S > log(d): error in eigenvalue computation or log convention.
```

**Strong subadditivity:**

```
For tripartite system ABC:
  S(ABC) + S(B) <= S(AB) + S(BC)

Equivalently: I(A:C|B) = S(AB) + S(BC) - S(ABC) - S(B) >= 0 (conditional mutual information)

Verification: ALWAYS check SSA after computing entropies of subsystems.
Violation of SSA means at least one entropy value is wrong.
```

**Quantum mutual information:**

```
I(A:B) = S(A) + S(B) - S(AB)

Properties:
1. I(A:B) >= 0 (follows from SSA with C trivial).
2. I(A:B) <= 2 * min(S(A), S(B)).
3. I(A:B) = 0 iff rho_AB = rho_A tensor rho_B (product state).
4. For maximally entangled state of two d-dimensional systems: I(A:B) = 2*log(d).

Verification: If I(A:B) < 0: entropy computation is wrong.
If I(A:B) > 2*min(S(A), S(B)): entropy computation is wrong.
```

**Holevo bound:**

```
Accessible information <= chi = S(rho) - sum_x p_x S(rho_x)

where rho = sum_x p_x rho_x is the average state.

Verification:
1. chi >= 0 (concavity of entropy).
2. chi <= log(d) (bounded by log of alphabet/Hilbert space dimension).
3. chi <= H(X) where H(X) = -sum p_x log(p_x) is the classical entropy of the prior.
4. If chi < 0: entropy calculation error.
```

</entropy_verification>

<channel_capacity_verification>

## Channel Capacity Verification

**Quantum channel capacity:**

```
Quantum capacity: Q(E) = lim_{n->inf} (1/n) max_{rho} I_c(rho, E^{tensor n})

where I_c(rho, E) = S(E(rho)) - S_e(rho, E) is the coherent information,
and S_e(rho, E) = S((id tensor E)(|psi><psi|)) is the entropy exchange.

Single-letter lower bound: Q >= max_rho I_c(rho, E)

WARNING: Q can be SUPERADDITIVE. The single-letter formula is NOT the capacity in general.
It IS the capacity for degradable channels (amplitude damping, erasure).

Verification:
1. Q >= 0 always. If negative coherent information for all rho: Q may still be > 0 (need multi-letter).
2. For erasure channel E_p: Q = max(0, 1 - 2p). At p = 1/2: Q = 0 (no-cloning bound).
3. For depolarizing channel D_p (d=2): Q = 0 for p >= p_threshold ~ 0.253.
4. For amplitude damping A_gamma: Q = max_p [H_2(p(1-gamma)) - H_2(p*gamma)] (degradable, single-letter exact).
5. Q <= log(d) (bounded by log of input dimension).
6. Q(E) <= Q(F) if E = F composed with another channel (data processing).
```

**Classical capacity:**

```
Classical capacity: C(E) = lim_{n->inf} (1/n) max chi(E^{tensor n})

Holevo-Schumacher-Westmoreland theorem.
For entanglement-breaking channels: C = chi (single-letter, no superadditivity).

Verification:
1. C >= chi(E) (single-letter is always a lower bound).
2. C <= log(d_out) (bounded by output dimension).
3. C >= Q (classical capacity >= quantum capacity).
4. For noiseless channel: C = log(d).
```

</channel_capacity_verification>

<error_correction_verification>

## Quantum Error Correction Verification

**Knill-Laflamme conditions:**

```
For a quantum error-correcting code with codespace projector P and error operators {E_a}:

P E_a^dagger E_b P = alpha_{ab} P

where alpha_{ab} is a Hermitian matrix (the error matrix).

Verification:
1. COMPUTE: P E_a^dagger E_b P for all pairs (a,b) in the error set.
2. Result must be proportional to P (same scalar times projector for all code states).
3. If proportionality fails: the code does NOT correct this error set.
```

**Stabilizer code verification:**

```
For an [[n,k,d]] stabilizer code with stabilizer group S:

1. S is an Abelian subgroup of the n-qubit Pauli group.
2. |S| = 2^{n-k} (encodes k logical qubits in n physical qubits).
3. -I is NOT in S (code space is non-trivial).
4. Distance d = min weight of elements in N(S)\S (normalizer minus stabilizer).

Verification:
1. COMMUTATIVITY: All stabilizer generators commute pairwise. Check [S_i, S_j] = 0 for all pairs.
   If any anticommute: not a valid stabilizer group.
2. INDEPENDENCE: Generators are algebraically independent. Rank of binary symplectic matrix = n-k.
3. DISTANCE: Find minimum weight Pauli operator that commutes with all stabilizers but is not in S.
   This gives d. Verify d matches the claimed code distance.
4. For CSS codes: X and Z distances can be computed independently.
```

**Threshold theorem checks:**

```
For fault-tolerant quantum computation:
  Logical error rate: p_L ~ (p/p_th)^{ceil(d/2)}

where p is physical error rate and p_th is the threshold.

Verification:
1. p_L must decrease exponentially with distance d when p < p_th.
2. p_L must increase with d when p > p_th.
3. At p = p_th: p_L is approximately constant with d.
4. For surface code: p_th ~ 1% (depolarizing) or ~11% (Z-biased with XZZX).
```

</error_correction_verification>

<circuit_verification>

## Quantum Circuit Verification

**Unitary verification:**

```
For a quantum circuit implementing unitary U:

Verification:
1. COMPUTE: U^dagger U = I (unitarity). Deviation > 10^{-10}: circuit has non-unitary elements.
2. COMPUTE: det(U). Must have |det(U)| = 1.
3. For controlled gates: verify action on computational basis states.
   CX|00> = |00>, CX|01> = |01>, CX|10> = |11>, CX|11> = |10>.
4. Gate decomposition: verify the compiled circuit equals the target unitary.
   Fidelity: F = |Tr(U_target^dagger U_compiled)|^2 / d^2. Must be > 1 - epsilon.
```

**Circuit identity checks:**

```
Common identities that must hold:
1. HXH = Z, HZH = X, HYH = -Y (Hadamard conjugation)
2. CNOT * CNOT = I (self-inverse)
3. (H tensor H) * CNOT * (H tensor H) = CNOT with control/target swapped
4. T^dagger T = I, S^dagger S = I (gate inverses)
5. SWAP = CNOT_{12} * CNOT_{21} * CNOT_{12} (three CNOTs make a SWAP)

Verification: For each identity used in simplification, multiply out the matrices
and verify equality to machine precision.
```

**Measurement verification:**

```
For a projective measurement {P_k} on state rho:

1. Completeness: sum_k P_k = I
2. Orthogonality: P_j P_k = delta_{jk} P_k
3. Probabilities: p_k = Tr(P_k rho) >= 0 and sum_k p_k = 1
4. Post-measurement state: rho_k = P_k rho P_k / p_k (valid density matrix)

For POVM {M_k}:
1. Completeness: sum_k M_k = I
2. Positivity: M_k >= 0 for all k
3. Probabilities: p_k = Tr(M_k rho) >= 0 and sum_k p_k = 1
```

</circuit_verification>

<distance_measures>

## Distance Measures and Fidelity

**Trace distance:**

```
D(rho, sigma) = (1/2) ||rho - sigma||_1 = (1/2) sum_i |lambda_i|

where lambda_i are eigenvalues of (rho - sigma).

Properties:
1. 0 <= D <= 1. D = 0 iff rho = sigma. D = 1 for orthogonal pure states.
2. Contractivity: D(E(rho), E(sigma)) <= D(rho, sigma) for any CPTP map E.
3. Triangle inequality: D(rho, tau) <= D(rho, sigma) + D(sigma, tau).
4. Operational: D = max_{0<=M<=I} Tr[M(rho - sigma)] (optimal discrimination probability).

Verification: If D > 1 or D < 0: computation error.
```

**Fidelity (Uhlmann-Jozsa):**

```
F(rho, sigma) = (Tr sqrt(sqrt(rho) sigma sqrt(rho)))^2

WARNING: Two conventions exist:
  Jozsa: F = (Tr sqrt(...))^2  (ranges [0,1], this is the standard)
  Uhlmann: sqrt(F) = Tr sqrt(...)  (ranges [0,1], the square root of Jozsa)
ALWAYS state which convention is used.

Properties:
1. 0 <= F <= 1. F = 1 iff rho = sigma. F = 0 for orthogonal states.
2. For pure states: F(|psi>, |phi>) = |<psi|phi>|^2.
3. For pure and mixed: F(|psi>, rho) = <psi|rho|psi>.
4. Multiplicativity: F(rho_1 tensor rho_2, sigma_1 tensor sigma_2) = F(rho_1, sigma_1) * F(rho_2, sigma_2).
5. Unitary invariance: F(U rho U^dagger, U sigma U^dagger) = F(rho, sigma).

Fuchs-van de Graaf inequalities (relates F and D):
  1 - sqrt(F) <= D <= sqrt(1 - F)

Verification:
1. COMPUTE F and D independently. Check Fuchs-van de Graaf bounds.
2. F(rho, rho) must equal 1 exactly.
3. For product states: verify multiplicativity.
```

**Diamond norm:**

```
||E - F||_diamond = max_{rho} ||(id tensor E)(rho) - (id tensor F)(rho)||_1

where the maximization is over all bipartite states rho on H tensor H.

Verification:
1. ||E - F||_diamond >= ||E(rho) - F(rho)||_1 for any rho (lower bound from any state).
2. ||E - F||_diamond <= d * ||J(E) - J(F)||_1 (upper bound from Choi matrices).
3. For unitary channels: ||U - V||_diamond = 2 * sqrt(1 - |Tr(U^dagger V)|^2 / d^2) (for d=2).
4. Can be computed as an SDP (semidefinite program).
```

</distance_measures>

## Worked Examples

### CPTP violation detected via Choi matrix

**Scenario:** Constructing a "quantum channel" by guessing Kraus operators K_1 = [[1, 0], [0, sqrt(1-p)]] and K_2 = [[0, sqrt(p)], [0, 0]].

```python
import numpy as np

p = 0.3
K1 = np.array([[1, 0], [0, np.sqrt(1-p)]])
K2 = np.array([[0, np.sqrt(p)], [0, 0]])

# Check trace preservation
TP = K1.conj().T @ K1 + K2.conj().T @ K2
print("K1^dag K1 + K2^dag K2 =")
print(TP)
# Result: [[1, 0], [0, 1-p+p]] = [[1, 0], [0, 1]]. TP satisfied. Good.

# But what if we had K2 = [[0, sqrt(p)], [sqrt(p), 0]] (wrong guess)?
K2_wrong = np.array([[0, np.sqrt(p)], [np.sqrt(p), 0]])
TP_wrong = K1.conj().T @ K1 + K2_wrong.conj().T @ K2_wrong
print("\nWrong K2:")
print(TP_wrong)
# Result: [[1+p, 0], [0, 1]]. NOT equal to I. TP VIOLATED.
# This is NOT a valid quantum channel.
```

### Entanglement measure inconsistency revealing a bug

**Scenario:** Computing negativity for a two-qubit Werner state rho_W = p|Phi+><Phi+| + (1-p)I/4.

```python
import numpy as np

p = 0.6
# Werner state
Phi_plus = np.array([1, 0, 0, 1]) / np.sqrt(2)
rho_W = p * np.outer(Phi_plus, Phi_plus) + (1-p) * np.eye(4) / 4

# Partial transpose (transpose on second qubit)
# For 2x2 system: rho^{T_B}_{ij,kl} = rho_{il,kj}
rho_pt = rho_W.reshape(2,2,2,2).transpose(0,3,2,1).reshape(4,4)

eigenvalues = np.linalg.eigvalsh(rho_pt)
print(f"Partial transpose eigenvalues: {sorted(eigenvalues)}")
# For p=0.6: min eigenvalue = (1-3p)/4 = (1-1.8)/4 = -0.2

negativity = (np.sum(np.abs(eigenvalues)) - 1) / 2
print(f"Negativity: {negativity:.4f}")
# Negativity > 0 confirms entanglement. For p=0.6: N = 0.2

# Cross-check: Werner state is entangled iff p > 1/3 (PPT criterion for 2x2)
# p = 0.6 > 1/3: consistent.
# Concurrence: C = max(0, (3p-1)/2) = max(0, 0.4) = 0.4
# Both measures agree: state is entangled.
```
