---
template_version: 1
---

# Quantum Information and Computation Project Template

Default project structure for quantum information and computation: quantum circuits, entanglement measures, quantum error correction, quantum channels, quantum cryptography, quantum algorithms, quantum thermodynamics, resource theories, open quantum systems, Lindblad dynamics, and tensor network methods.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Setup** - Identify the quantum information protocol/problem, fix qubit/qudit dimensions, establish notation
- [ ] **Phase 2: System Definition** - Specify Hilbert space, Hamiltonian or channel, noise model, initial states
- [ ] **Phase 3: Protocol/Algorithm Design** - Design quantum circuit, error correction code, or protocol
- [ ] **Phase 4: Analysis** - Prove correctness, compute fidelities/capacities/entanglement measures, derive bounds
- [ ] **Phase 5: Noise and Decoherence** - Analyze robustness under realistic noise models, threshold theorems
- [ ] **Phase 6: Numerical Simulation** - Simulate with realistic parameters, compare to bounds
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Establish conventions, identify the protocol or problem, and catalogue prior results and known bounds
**Success Criteria:**

1. [Protocol/problem clearly defined with input/output specification and target figure of merit]
2. [Prior results and known bounds catalogued (capacity formulas, threshold values, complexity results)]
3. [Conventions fixed: qubit/qudit dimension d, Pauli basis, state normalization, logarithm base, fidelity convention]
4. [Hilbert space dimensions and tensor product structure identified]

Plans:

- [ ] 01-01: [Survey literature for existing results on this problem/protocol]
- [ ] 01-02: [Fix notation and conventions; document in NOTATION_GLOSSARY.md]

### Phase 2: System Definition

**Goal:** Precisely specify the Hilbert space, Hamiltonian or channel, noise model, and initial states
**Success Criteria:**

1. [Hilbert space H and its tensor product structure defined (H_A tensor H_B tensor ...)]
2. [Hamiltonian or quantum channel defined in at least two representations (Kraus operators + Choi matrix, or Stinespring dilation)]
3. [CPTP property verified: Choi matrix positive semidefinite and partial trace condition Tr_B[J(E)] = I/d satisfied]
4. [Noise model specified with explicit error parameters (depolarizing rate p, T1/T2 times, dephasing rate)]
5. [Initial states defined as density matrices; purity and rank verified]

Plans:

- [ ] 02-01: [Define Hilbert space structure, Hamiltonian, and initial states]
- [ ] 02-02: [Define quantum channels and verify CPTP property via Choi matrix]
- [ ] 02-03: [Specify noise model and identify symmetry properties (covariance, degradability)]

### Phase 3: Protocol/Algorithm Design

**Goal:** Design the quantum circuit, error correction code, or information-processing protocol
**Success Criteria:**

1. [Protocol steps defined: state preparation, unitary gates, measurements, classical communication (LOCC structure explicit)]
2. [Resource requirements quantified: qubits, ebits, cbits, T-gates, circuit depth, ancilla count]
3. [Correctness proven for ideal (noiseless) case]
4. [Information-theoretic optimality assessed against known bounds (Holevo, Hastings, quantum Singleton)]

Plans:

- [ ] 03-01: [Design protocol or algorithm with explicit circuit description]
- [ ] 03-02: [Prove correctness in the ideal case]
- [ ] 03-03: [Assess resource requirements and compare with known bounds]

### Phase 4: Analysis

**Goal:** Prove correctness and derive analytic expressions for key figures of merit
**Success Criteria:**

1. [Fidelity, capacity, or entanglement measure computed analytically or bounded]
2. [Optimality bounds derived: converse bounds or no-go results where applicable]
3. [Entanglement monotone properties verified: non-increasing under LOCC]
4. [Strong subadditivity and data processing inequality satisfied in all entropy expressions]
5. [Scaling with system size, number of copies, or blocklength characterized]

Plans:

- [ ] 04-01: [Derive analytic expressions for target figures of merit]
- [ ] 04-02: [Prove optimality or derive converse bounds]
- [ ] 04-03: [Verify all information-theoretic inequalities are satisfied]

### Phase 5: Noise and Decoherence

**Goal:** Analyze protocol robustness under realistic noise models and derive threshold conditions
**Success Criteria:**

1. [Error propagation through circuit analyzed; dominant error sources identified]
2. [Performance metrics computed as function of noise parameters (fidelity vs p, capacity vs noise strength)]
3. [Fault tolerance threshold computed if applicable (surface code: p_th ~ 1%, concatenated: p_th ~ 10^{-4})]
4. [Lindblad master equation or process tensor used for continuous-time decoherence where appropriate]
5. [Non-Markovian effects assessed: when is Markovian approximation valid?]

Plans:

- [ ] 05-01: [Analyze error propagation and compute noisy performance metrics]
- [ ] 05-02: [Determine fault tolerance thresholds or break-even points]
- [ ] 05-03: [Assess validity of Markovian noise assumption]

### Phase 6: Numerical Simulation

**Goal:** Simulate the protocol with realistic parameters and validate analytic results
**Success Criteria:**

1. [Quantum circuit implemented and tested on simulator (Qiskit/Cirq/PennyLane)]
2. [Numerical results agree with analytic predictions within expected precision]
3. [Scaling behavior confirmed numerically (system size, noise strength, number of rounds)]
4. [Tensor network simulation used for large systems where full state vector is infeasible]
5. [Results benchmarked against at least one independent implementation or known analytic formula]

Plans:

- [ ] 06-01: [Implement quantum circuit and run noise simulations]
- [ ] 06-02: [Compute information-theoretic quantities numerically and compare with analytic bounds]
- [ ] 06-03: [Characterize scaling behavior and cross-check with independent method]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with all sections and figures]
2. [All results presented with explicit convention choices, noise model specification, and resource counts]
3. [Comparison with prior work and known bounds clearly stated]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 2 branches:** Explore multiple channel representations (Kraus vs Stinespring vs Choi) and noise models (depolarizing vs amplitude damping vs correlated). Compare structural insights from each.
- **Phase 3 splits:** Design parallel protocol variants (e.g., different code families, one-way vs two-way communication, different circuit architectures). Evaluate trade-offs at phase boundary.
- **Extra phase:** Add "Phase 3.5: Representation Comparison" — evaluate which channel representation or entanglement measure gives tightest bounds and cleanest analysis. Inform Phase 4 approach.
- **Literature depth:** 15+ papers, including connections to resource theories, convex optimization approaches, and alternative quantum frameworks (SDP relaxations, operator algebra methods).

### Exploit Mode
- **Phases 1-2 compressed:** Skip deep literature survey if the channel, protocol, or code family is well-known (depolarizing channel, surface code, teleportation). Go directly from system definition to protocol implementation.
- **Phase 3 focused:** Use the standard protocol or code construction. No exploration of alternatives.
- **Skip Phase 7:** If results feed into a larger project, skip paper writing. Output is SUMMARY.md with verified results.
- **Skip researcher:** If the analysis follows a known pattern (same protocol for a new channel, or standard capacity calculation for a known channel family).

### Adaptive Mode
- Start in explore for Phases 1-3 (representation selection, noise model identification, protocol design).
- Switch to exploit for Phases 4-6 once the channel representation, noise model, and protocol variant are chosen and validated.

---

## Standard Verification Checks for Quantum Information

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-quantum-info.md` for quantum-information-specific verification (CPTP, entanglement measures, channel capacity, error correction, circuit correctness).

### CPTP and Channel Verification
- **Trace preservation:** Sum_k K_k^dagger K_k = I for Kraus operators {K_k}
- **Complete positivity:** Choi matrix J(E) = (id tensor E)(|Omega><Omega|) is positive semidefinite, where |Omega> = sum_i |ii>/sqrt(d)
- **Partial trace condition:** Tr_B[J(E)] = I/d (trace-preserving) or Tr_B[J(E)] <= I/d (trace non-increasing)
- **Stinespring consistency:** E(rho) = Tr_E[V rho V^dagger] for some isometry V: H_A -> H_B tensor H_E

### State and Entanglement Verification
- **Density matrix validity:** rho = rho^dagger, rho >= 0, Tr(rho) = 1
- **Entanglement monotones:** Non-increasing under LOCC: E(Lambda_LOCC(rho)) <= E(rho)
- **PPT criterion:** If rho^{T_B} has negative eigenvalues, state is entangled (necessary and sufficient for 2x2 and 2x3)
- **Strong subadditivity:** S(ABC) + S(B) <= S(AB) + S(BC)
- **Concurrence bounds:** 0 <= C(rho) <= 1 for two-qubit states

### Information-Theoretic Bounds
- **Holevo bound:** chi = S(rho) - sum_x p_x S(rho_x) bounds accessible information
- **No-cloning:** No CPTP map E such that E(|psi>|0>) = |psi>|psi> for all |psi>
- **Quantum data processing inequality:** I(A;B) >= I(A;C) for Markov chain A -> B -> C
- **Fannes-Audenaert inequality:** |S(rho) - S(sigma)| <= T log(d-1) + H(T) where T = (1/2)||rho - sigma||_1

---

## Typical Approximation Hierarchy

| Level                 | Approximation                | Control Parameter        | Typical Use Case                            |
| --------------------- | ---------------------------- | ------------------------ | ------------------------------------------- |
| Exact unitary         | Noiseless evolution          | ---                      | Ideal algorithm analysis, proof of concept  |
| Pauli noise           | Stochastic Pauli errors      | Error rate p             | Stabilizer simulation, threshold estimation |
| Markovian noise       | Lindblad master equation     | Decay rates gamma        | Open quantum systems, T1/T2 modeling        |
| Coherent errors       | Unitary over-rotation        | Angle error delta        | Gate calibration errors                     |
| Non-Markovian         | Process tensor / transfer matrix | Memory time tau_c     | Correlated noise, non-Markovian environments|
| Fault-tolerant        | Logical error rate           | p < p_th (threshold)     | Below-threshold error correction            |
| Asymptotic (n -> inf) | Shannon/quantum capacity     | Blocklength n            | Capacity-achieving codes, rate optimization |

**When to go beyond ideal analysis:**

- Physical error rate above 10^{-4}: noise analysis essential, fault tolerance required
- Few-qubit regime (n < 20): finite-size effects dominate; asymptotic capacity bounds may not be tight
- Non-Markovian environment: Lindblad master equation insufficient; use process tensor or transfer matrix methods
- Correlated noise: independent noise model breaks down; use spatially/temporally correlated error models

---

## Common Pitfalls for Quantum Information

1. **Non-CPTP maps:** Constructing a map that is positive but not completely positive. Any physically realizable channel must be CP. Test: verify the Choi matrix is positive semidefinite, not just that individual Kraus operators look reasonable
2. **Wrong partial trace:** Tracing over the wrong subsystem in a bipartite or multipartite state. Partial trace over B in H_A tensor H_B gives rho_A = Tr_B(rho_AB). Confusing this with partial transpose produces nonsensical results
3. **Confusing fidelity definitions:** Entanglement fidelity F_e(E) = <Phi+|(id tensor E)(|Phi+><Phi+|)|Phi+> is not the same as average gate fidelity F_avg = integral <psi|E(|psi><psi|)|psi> d(psi). They are related by F_avg = (d*F_e + 1)/(d + 1) but not interchangeable
4. **Ignoring LOCC constraints:** Many entanglement manipulation tasks are restricted to local operations and classical communication. Proving something is possible with a global unitary does not prove it is possible under LOCC. Always specify the allowed operation class
5. **Wrong Stinespring dilation:** The isometry V: H_A -> H_B tensor H_E must satisfy E(rho) = Tr_E(V rho V^dagger). Getting the environment dimension wrong or tracing over the wrong factor gives an incorrect channel
6. **Entropy of mixed vs pure states:** The von Neumann entropy S(rho) = -Tr(rho log rho) is zero for pure states and maximal (log d) for maximally mixed states. Computing S as if a mixed state were pure (or vice versa) produces wrong entanglement entropy values
7. **Claiming quantum advantage without classical lower bound:** Demonstrating a quantum protocol achieves rate R or complexity C does not establish quantum advantage unless the best classical protocol is proven to achieve strictly worse performance. Must cite or prove a classical converse bound
8. **Channel capacity superadditivity:** Quantum channel capacity can be superadditive: C(E tensor E) > 2*C(E) in general (Hastings). Single-letter formulas (coherent information) give only a lower bound on quantum capacity; regularization is generally required
9. **Forgetting classical communication costs:** Many protocols (teleportation, superdense coding, entanglement distillation) require classical communication. Omitting the classical channel or miscounting cbits changes the protocol class and invalidates resource counting

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Quantum information projects should populate:

- **State Normalization:** Tr(rho) = 1 for density matrices; <psi|psi> = 1 for pure states
- **Pauli Basis:** sigma_x = |0><1| + |1><0|, sigma_y = -i|0><1| + i|1><0|, sigma_z = |0><0| - |1><1| (eigenstates of sigma_z are computational basis)
- **Qubit Ordering:** Big-endian |q_0 q_1 ... q_{n-1}> (textbook convention) vs little-endian (Qiskit convention). Specify which is used
- **Tensor Product Convention:** A tensor B acts on H_A tensor H_B; partial trace over B gives reduced state on A
- **Channel Representation:** Primary representation (Kraus, Stinespring, or Choi) and how to convert between them
- **Entanglement Measure:** Which measure is used (negativity, concurrence, entanglement entropy, squashed entanglement) and why
- **Logarithm Base:** log base 2 (bits/qubits) vs natural log (nats). Entropies differ by factor ln(2)
- **Fidelity Convention:** F(rho, sigma) = (Tr sqrt(sqrt(rho) sigma sqrt(rho)))^2 (Jozsa) vs F = Tr sqrt(sqrt(rho) sigma sqrt(rho)) (Uhlmann). Square vs no square

---

## Computational Environment

**Quantum circuit simulation:**

- `qiskit` — Full-stack quantum computing: circuit construction, transpilation, noise simulation, Aer backend
- `cirq` — Google's framework: emphasis on NISQ circuits, custom noise models, device-aware compilation
- `pennylane` — Differentiable quantum computing, variational algorithms, quantum machine learning

**Quantum information and open systems:**

- `qutip` — Open quantum systems: Lindblad master equations, process tomography, entanglement measures, Bloch sphere visualization
- `numpy` + `scipy` — Matrix operations, eigenvalue decomposition, sparse matrices for large Hilbert spaces
- `cvxpy` — Convex optimization and semidefinite programming for capacity bounds, entanglement witnesses, state discrimination

**Tensor network methods:**

- `quimb` — Tensor network library: MPS, DMRG, TEBD, tensor contraction for large quantum systems
- `itensor` — High-performance tensor network computations: MPS/MPO, DMRG, time evolution (Julia; Python bindings available)

**Stabilizer and error correction:**

- `stim` — High-performance stabilizer circuit simulation, error correction decoding, detector error models
- `pymatching` — Minimum-weight perfect matching decoder for surface codes
- `ldpc` — Belief propagation decoders for quantum LDPC codes

**Visualization:**

- `matplotlib` — Bloch sphere plots, capacity curves, threshold diagrams
- `qiskit.visualization` — Circuit drawing, state visualization, histogram plots

**Setup:**

```bash
pip install qiskit qiskit-aer qutip numpy scipy cvxpy stim pymatching quimb
# For Cirq: pip install cirq
# For PennyLane: pip install pennylane
# For ITensor (Julia): using Pkg; Pkg.add("ITensors")
```

---

## Bibliography Seeds

Every quantum information project should cite or consult these references as starting points:

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Nielsen & Chuang, *Quantum Computation and Quantum Information* | Standard conventions, circuit model, quantum channels, error correction foundations | Convention reference; foundational definitions |
| Wilde, *From Classical to Quantum Shannon Theory* | Rigorous quantum information theory: capacities, entropy inequalities, resource theory | Channel capacity calculations, information measures |
| Preskill, *Lecture Notes on Quantum Computation* (Ph219) | Pedagogical treatment of error correction, fault tolerance, topological codes | Threshold theorems, fault-tolerant constructions |
| Watrous, *The Theory of Quantum Information* | Mathematical foundations: norms, fidelities, channels, semidefinite programming | Formal proofs, optimization-based bounds |
| Hayden & Winter, *Counterexamples to the Maximal p-Norm Multiplicativity Conjecture* + related work | Randomized constructions, capacity superadditivity, decoupling theorems | Capacity bounds, random coding arguments, one-shot information theory |
| Bengtsson & Zyczkowski, *Geometry of Quantum States* | Geometric approach: Bloch ball, entanglement geometry, quantum state spaces | Entanglement characterization, state space structure |

**For specific topics:** Search arXiv quant-ph for recent reviews. Key review series: Reviews of Modern Physics (quantum information section), Nature Reviews Physics quantum technology articles.

---

## Worked Example: Quantum Teleportation Fidelity Under Depolarizing Noise

A complete 3-phase mini-project illustrating the template:

**Phase 1 — Setup:** Conventions fixed (Nielsen & Chuang: big-endian qubit ordering, log base 2, Jozsa fidelity). Problem: compute average teleportation fidelity when the shared Bell pair undergoes depolarizing noise E(rho) = (1-p)*rho + p*I/4 on both qubits. Known result: perfect teleportation fidelity F=1 for p=0 with maximally entangled state. Prior bounds: Horodecki teleportation fidelity formula F = (2*f + 1)/3 where f is singlet fraction.

**Phase 2 — System Definition and Analysis:** Hilbert space H = H_A tensor H_B, each C^2. Shared state: |Phi+> = (|00> + |11>)/sqrt(2). After depolarizing noise on both qubits: rho_AB = E_A tensor E_B (|Phi+><Phi+|). Choi matrix of depolarizing channel verified PSD. Resulting state: Werner state rho_W = (1-p)^2 |Phi+><Phi+| + [1-(1-p)^2] I/4. Singlet fraction f = <Phi+|rho_W|Phi+> = (3(1-p)^2 + 1)/4. Teleportation fidelity: F = (2f+1)/3 = ((1-p)^2 + 1)/2.

**Phase 3 — Validation:**
- CPTP check: depolarizing channel Kraus operators {sqrt(1-3p/4)*I, sqrt(p/4)*sigma_x, sqrt(p/4)*sigma_y, sqrt(p/4)*sigma_z}. Sum K_k^dagger K_k = (1-3p/4)*I + 3*(p/4)*I = I. Verified trace-preserving; Choi matrix eigenvalues all non-negative for 0 <= p <= 1. Verified CP.
- Limiting cases: At p=0: F=1 (perfect teleportation). At p=1: F=1/2 (random guess for qubit, correct). Monotonically decreasing in p.
- Entanglement threshold: State is entangled iff f > 1/2, i.e., (3(1-p)^2+1)/4 > 1/2, giving p < 1 - 1/sqrt(3) approx 0.423. Teleportation beats classical (F > 2/3) iff f > 1/2. Verified consistency with PPT criterion on the Werner state.
- Classical lower bound: Best classical strategy (measure and reprepare) achieves F_classical = 2/3 for qubits. Our protocol exceeds this for p < 1 - 1/sqrt(3), confirming quantum advantage in this noise regime.
