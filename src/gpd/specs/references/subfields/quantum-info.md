---
load_when:
  - "quantum information"
  - "quantum computing"
  - "entanglement"
  - "quantum error correction"
  - "qubit"
  - "quantum circuit"
  - "quantum channel"
tier: 2
context_cost: medium
---

# Quantum Information

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/tensor-networks.md`, `references/protocols/variational-methods.md`, `references/protocols/quantum-error-correction.md`.

**Quantum Circuits:**

- Universal gate sets: {H, T, CNOT} or {H, Toffoli} or {arbitrary single-qubit + CNOT}
- Circuit depth: number of time steps (layers); width: number of qubits
- Solovay-Kitaev theorem: any single-qubit gate approximated to epsilon accuracy with O(log^c(1/epsilon)) gates from a finite universal set
- Circuit compilation: decompose arbitrary unitaries into native gate sets; optimize for connectivity and gate count
- Measurement: projective (von Neumann) in computational basis; generalized (POVM) for optimal state discrimination

**Entanglement Measures:**

- **Von Neumann entropy:** S(rho_A) = -Tr(rho_A \* log(rho_A)); maximum entanglement when S = log(d)
- **Renyi entropies:** S_n = (1/(1-n)) \* log(Tr(rho_A^n)); n=2 is experimentally accessible via random measurements
- **Negativity:** N(rho) = (||rho^{T_A}||\_1 - 1) / 2; detects entanglement in mixed states; zero for PPT entangled states
- **Concurrence:** C = max(0, lambda_1 - lambda_2 - lambda_3 - lambda_4) for two qubits; exact entanglement monotone
- **Entanglement entropy for many-body systems:** Area law in gapped systems (S ~ L^{d-1}); logarithmic correction at critical points in 1D (S ~ (c/3)\*log(L) with c the central charge)

**Quantum Error Correction:**

- Stabilizer codes: defined by commuting Pauli operators (stabilizer group); codeword space is simultaneous +1 eigenspace
- Surface code: 2D topological code; threshold ~1%; distance d protects against (d-1)/2 errors
- CSS codes (Calderbank-Shor-Steane): separate X and Z error correction; includes Steane [[7,1,3]] code
- Knill-Laflamme conditions: necessary and sufficient for error correction; <i|E_a^dag E_b|j> = C_ab \* delta_ij
- Fault tolerance: gates, measurements, and corrections designed so errors don't spread uncontrollably; threshold theorem

**Quantum Channels:**

- Completely positive trace-preserving (CPTP) maps: rho -> sum_k K_k rho K_k^dag with sum K_k^dag K_k = I
- Kraus representation: operator-sum representation; not unique (related by unitary mixing of Kraus operators)
- Choi-Jamiolkowski isomorphism: channel <-> positive semidefinite matrix (Choi matrix)
- Standard channels: depolarizing, dephasing, amplitude damping, erasure
- Channel capacity: maximum rate of faithful information transmission; quantum capacity Q requires coherent information maximization

**Tensor Networks for Quantum Information:**

- MPS/MPO: represent quantum states/operators as contraction of local tensors; bond dimension controls entanglement
- PEPS: 2D tensor networks; encode area-law entanglement naturally
- MERA: hierarchical; captures scale-invariant (critical) states; also models holographic duality (AdS/CFT)
- Tensor network contraction: exact is exponential in general; approximate methods (boundary MPS, corner transfer matrix)

**Variational Quantum Algorithms:**

- VQE (Variational Quantum Eigensolver): parameterized circuit U(theta); minimize <psi(theta)|H|psi(theta)>
- QAOA (Quantum Approximate Optimization Algorithm): alternating cost and mixer unitaries for combinatorial optimization
- Barren plateaus: gradients vanish exponentially with system size for sufficiently random circuits; major challenge
- Classical optimization: gradient-free (COBYLA, Nelder-Mead), gradient-based (parameter shift rule, SPSA)

## Key Tools and Software

| Tool                  | Purpose                                 | Notes                                                                        |
| --------------------- | --------------------------------------- | ---------------------------------------------------------------------------- |
| **Qiskit**            | Full-stack quantum computing (IBM)      | Circuit design, simulation, hardware access; Python                          |
| **Cirq**              | Quantum circuits (Google)               | NISQ-focused; noise models; Python                                           |
| **PennyLane**         | Differentiable quantum computing        | Automatic differentiation of quantum circuits; interfaces with ML frameworks |
| **Stim**              | Clifford circuit simulator              | Fast stabilizer simulation; error correction analysis; millions of qubits    |
| **ITensor**           | Tensor network library (Julia/C++)      | MPS, DMRG, TEBD, MERA                                                        |
| **TeNPy**             | Tensor networks (Python)                | DMRG, TEBD, MPS; well-suited for condensed matter + QI                       |
| **QuTiP**             | Quantum toolbox in Python               | Open quantum systems, Lindblad master equation, optimal control              |
| **Strawberry Fields** | Continuous-variable quantum computing   | Photonic quantum computing; Gaussian and Fock backends                       |
| **pyMatching**        | Minimum-weight perfect matching decoder | Surface code decoding; fast                                                  |
| **XACC**              | Hardware-agnostic quantum programming   | Multiple backend support                                                     |
| **Amazon Braket SDK** | Quantum computing on AWS                | Access to multiple hardware providers                                        |
| **ProjectQ**          | Quantum circuit compiler                | Optimization, decomposition, multiple backends                               |

## Validation Strategies

**State Fidelity:**

- Fidelity: F(rho, sigma) = (Tr[sqrt(sqrt(rho)*sigma*sqrt(rho))])^2; F = 1 iff rho = sigma
- For pure states: F = |<psi|phi>|^2
- Check: prepared state fidelity with target state using state tomography
- Process fidelity: F_process = Tr(chi_ideal \* chi_actual) for quantum process tomography

**Entanglement Verification:**

- Bell inequality violation: CHSH inequality S <= 2 classically; quantum maximum S = 2\*sqrt(2)
- Entanglement witnesses: Tr(W \* rho) < 0 implies entanglement; construct witness from target state
- PPT criterion: partial transpose of separable state is positive semidefinite; violation implies entanglement (necessary and sufficient for 2x2 and 2x3)

**Error Correction Verification:**

- Syndrome extraction must correctly identify errors
- Logical error rate must decrease with code distance (threshold behavior)
- Check: run Monte Carlo simulation of error model; verify logical error rate below physical rate for p < p_threshold
- Decoder performance: compare with minimum-weight perfect matching or union-find decoder

**Circuit Identities:**

- Known circuit equivalences: HXH = Z, HZH = X, CNOT^2 = I, etc.
- Check: simulate circuit and verify unitary matrix matches expected
- Tomographic verification: reconstruct process matrix and compare with ideal

**No-Cloning and No-Communication:**

- Any purported cloning circuit must violate linearity of quantum mechanics
- Any entanglement-based protocol must not enable superluminal communication
- Check: verify that reduced density matrix of one party is independent of other party's measurement choice

## Common Pitfalls

- **Confusing trace distance and fidelity:** They are related (Fuchs-van de Graaf inequalities) but not interchangeable. Trace distance is metric; fidelity is not
- **Barren plateaus in VQE:** Deep random circuits have exponentially vanishing gradients. Use problem-inspired ansatze (UCCSD, hardware-efficient with structure)
- **Ignoring decoherence in circuit design:** T1 and T2 times limit circuit depth. A mathematically optimal circuit may be useless if it exceeds coherence time
- **Overcounting entanglement:** Entanglement of formation != distillable entanglement for mixed states. Bound entanglement exists (PPT entangled states)
- **NISQ noise models:** Assuming depolarizing noise when hardware has correlated, non-Markovian errors leads to wrong error rate predictions
- **Neglecting measurement errors:** State preparation and measurement (SPAM) errors can dominate gate errors for shallow circuits
- **Wrong Schmidt decomposition for mixed states:** Schmidt decomposition applies to pure bipartite states only; for mixed states, use singular value decomposition of the density matrix after vectorization

---

## Research Frontiers (2024-2026)

| Frontier | Key question | GPD suitability |
|----------|-------------|-----------------|
| **Quantum error correction thresholds** | Surface code with realistic noise — what overhead for fault-tolerant computation? | Good — stabilizer simulations, threshold estimates |
| **Quantum advantage for useful problems** | Beyond random circuit sampling — quantum speedup for optimization, chemistry, ML? | Moderate — circuit design + classical simulation bounds |
| **Measurement-based quantum computation** | Cluster states, fusion-based QC, photonic architectures | Good — graph state analysis, entanglement tracking |
| **Quantum many-body entanglement** | Entanglement phase transitions, monitored circuits, magic | Excellent — stabilizer + tensor network methods |
| **Quantum algorithms for physics** | Quantum simulation of gauge theories, chemistry, condensed matter | Good — Hamiltonian decomposition + circuit design |
| **Classical simulation boundaries** | Tensor network contraction, Clifford + T decomposition, MPS simulability | Excellent — computational complexity analysis |

## Methodology Decision Tree

```
What type of quantum information problem?
├── Quantum state analysis
│   ├── Pure state? → Schmidt decomposition, entanglement entropy
│   ├── Mixed state? → Density matrix, partial trace, concurrence/negativity
│   └── Many-body? → Tensor network (MPS/PEPS), stabilizer formalism
├── Quantum circuit design
│   ├── NISQ (< 100 qubits, noisy)? → VQE/QAOA with noise-aware ansatz
│   ├── Fault-tolerant? → Surface/color code, magic state distillation
│   └── Simulation of physics? → Trotterization, product formulas, LCU
├── Quantum channels / noise
│   ├── Markovian? → Lindblad master equation, Kraus operators
│   ├── Non-Markovian? → Process tensor, transfer tensor method
│   └── Error correction? → Stabilizer codes, decoder design, threshold analysis
└── Entanglement theory
    ├── Bipartite? → Entanglement measures (EoF, distillable, squashed)
    ├── Multipartite? → GME, tensor rank, SLOCC classification
    └── Operational? → Channel capacity, key rates, resource theory
```

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | Design and analyze one quantum algorithm or error correction scheme | "Quantum simulation of the Schwinger model with Trotterized time evolution" |
| **Postdoc** | Prove a quantum advantage result or develop new error correction technique | "Constant-overhead fault tolerance via quantum LDPC codes" |
| **Faculty** | New paradigm or resolution of fundamental question | "Classification of topological quantum error-correcting codes"
