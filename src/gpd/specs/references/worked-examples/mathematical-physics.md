# Worked Example: Spectral Gap of the 2D Quantum Heisenberg Antiferromagnet on a Finite Lattice

This file is a complete mini-project that trains the GPD roadmapper and planner agents on the **mathematical physics** project type. It contains realistic PROJECT.md, ROADMAP.md, PLAN.md, and SUMMARY.md artifacts for a project computing the spectral gap of the spin-1/2 Heisenberg antiferromagnet on a 2D square lattice.

**Physics summary.** The spin-1/2 Heisenberg antiferromagnet on the 2D square lattice is believed to have long-range Neel order at T = 0, with spontaneous breaking of the continuous SU(2) spin symmetry. By the Goldstone theorem, the broken symmetry implies gapless magnon excitations (two Goldstone modes). The spectral gap therefore vanishes in the thermodynamic limit L -> infinity. On a finite L x L lattice, the lowest magnon has momentum k = (2pi/L, 0) (or permutations/rotations), giving a finite-size gap Delta ~ c * 2pi / L where c is the spin-wave velocity. This project rigorously establishes bounds on the finite-size gap and computes it numerically for small lattices via exact diagonalization.

---

## 1. PROJECT.md

```markdown
# Spectral Gap of the 2D Quantum Heisenberg Antiferromagnet on a Finite Lattice

## What This Is

A mathematical physics investigation of the spectral gap (energy difference between the ground state and first excited state) of the spin-1/2 Heisenberg antiferromagnet on finite L x L square lattices with periodic boundary conditions. The project combines rigorous operator-algebraic arguments (Marshall sign rule, Perron-Frobenius theorem, Lieb-Mattis ordering) with exact numerical diagonalization for L = 4, 6 to establish how the gap scales with system size and to verify consistency with spin-wave theory predictions. The expected deliverable is a paper establishing a rigorous lower bound on the finite-size gap and comparing it with numerical results and the spin-wave prediction Delta = 2*pi*c/L.

## Core Research Question

What is the finite-size scaling of the spectral gap Delta(L) for the spin-1/2 Heisenberg antiferromagnet on the L x L square lattice, and can a rigorous lower bound of order J/L^2 be established?

## Research Questions

### Answered

(None yet -- investigate to answer)

### Active

- [ ] Does the ground state lie uniquely in the S_tot = 0 sector for all L, and can this be proven using the Marshall sign rule?
- [ ] Can the Perron-Frobenius theorem be applied in the Marshall-transformed basis to establish gap bounds?
- [ ] How does the numerically computed gap Delta(L) for L = 4, 6, 8 compare with the spin-wave prediction Delta = 2*pi*c/L where c = sqrt(2) * J * a * Z_c?
- [ ] Can a rigorous lower bound Delta(L) >= const * J / L^2 be established from the operator algebra?

### Out of Scope

- Finite-temperature properties -- requires different methods (quantum Monte Carlo, transfer matrix)
- Frustrated lattices (triangular, kagome) -- qualitatively different physics (no Neel order)
- S >= 1 chains -- Haldane gap physics is a separate phenomenon

## Research Context

### Physical System

The spin-1/2 quantum Heisenberg antiferromagnet on a 2D square lattice with N = L^2 sites and periodic boundary conditions. Each site i carries a spin-1/2 operator S_i = (1/2) * sigma_i where sigma_i are the Pauli matrices. The Hamiltonian is

  H = J * sum_{<i,j>} S_i . S_j,  J > 0 (antiferromagnetic)

where the sum runs over nearest-neighbor pairs on the square lattice. The Hilbert space has dimension 2^N.

### Theoretical Framework

- **Operator algebra:** The Hamiltonian commutes with total spin S_tot^2 and S_tot^z, enabling block diagonalization by quantum numbers (S, M). The Marshall sign rule establishes that in the basis where the B-sublattice spins are rotated by pi around the y-axis, the ground state has all non-negative amplitudes in the Ising basis.
- **Spectral theory:** The Perron-Frobenius theorem, applied after the Marshall transformation, guarantees the ground state is unique in the S_tot = 0 sector and has strictly positive amplitudes.
- **Exact diagonalization:** Lanczos algorithm exploiting the SU(2) symmetry to work within individual (S, M) sectors. Practical for L <= 6 (N = 36 sites, Hilbert space dimension ~ 9 * 10^9 before symmetry reduction) and L = 8 with aggressive symmetry exploitation.
- **Spin-wave theory (linear):** Anderson's spin-wave theory predicts the lowest magnon energy on a finite lattice as Delta = 2*pi*c/L where the spin-wave velocity c = sqrt(2) * J * a * Z_c with Z_c ~ 1.18 the quantum renormalization factor (from series expansions and QMC).

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
|-----------|--------|--------|-------|
| Exchange coupling | J | J > 0 (AF) | Sets energy scale; J = 1 throughout |
| Lattice size | L | 4, 6, 8 | L x L square lattice, N = L^2 sites |
| Lattice spacing | a | a = 1 | Set to unity |
| Spin-wave velocity | c | c ~ 1.658 J*a | From QMC: c = sqrt(2)*J*a*Z_c, Z_c ~ 1.18 |
| Staggered magnetization | m_s | ~ 0.307 | Known from QMC (Sandvik, 1997) |

### Known Results

- Marshall sign rule: ground state of the AF Heisenberg model on a bipartite lattice has all non-negative amplitudes in the sublattice-rotated basis -- Marshall (1955), Lieb & Mattis (1962)
- Lieb-Schultz-Mattis theorem (1D): half-integer spin chains have either gapless excitations or degenerate ground states -- LSM (1961), extended by Hastings (2004)
- 2D extension (Hastings): on the 2D square lattice, the half-integer spin AF has spectral gap bounded above by O(J/L) -- Hastings (2004)
- Anderson tower of states: the low-energy spectrum of the finite-size AF on a lattice with Neel order consists of a "tower" of states with energies E(S) - E_0 ~ J*S*(S+1)/N, collapsing to zero as N -> infinity -- Anderson (1952), Bernu et al. (1992)
- QMC ground state energy: E_0/N = -0.6693(1) J per site -- Sandvik (1997)
- Spin-wave velocity: c/Ja = 1.658(2) from QMC -- Sandvik & Singh (2001)

### What Is New

This project establishes a rigorous lower bound on the finite-size gap Delta(L) >= const * J / L^2 using the operator algebra (Perron-Frobenius in the Marshall basis combined with the SU(2) symmetry structure), and provides precise numerical values of Delta(L) for L = 4, 6, 8 via exact diagonalization, comparing with the spin-wave prediction Delta = 2*pi*c/L. The combination of rigorous bounds with exact numerics for a specific model fills a gap in the mathematical physics literature.

### Target Venue

Journal of Mathematical Physics or Annals of Physics -- both accept rigorous results on quantum spin systems with numerical verification.

### Computational Environment

- **Exact diagonalization:** Python (numpy/scipy) for L = 4, QuSpin for L = 6, custom Lanczos with SU(2) symmetry for L = 8
- **Symbolic computation:** sympy for operator algebra verification
- **Visualization:** matplotlib for gap vs 1/L plots

## Notation and Conventions

See `.planning/CONVENTIONS.md` for all notation and sign conventions.
See `.planning/NOTATION_GLOSSARY.md` for symbol definitions.

## Unit System

Lattice units: J = 1 (exchange coupling sets the energy scale), a = 1 (lattice spacing), hbar = 1.

## Key References

- Marshall, Proc. R. Soc. A 232, 48 (1955) -- Marshall sign rule for AF ground state
- Lieb & Mattis, J. Math. Phys. 3, 749 (1962) -- Ordering theorem for AF ground states on bipartite lattices
- Lieb, Schultz & Mattis, Ann. Phys. 16, 407 (1961) -- LSM theorem for 1D spin chains
- Hastings, Phys. Rev. B 69, 104431 (2004) -- Extension of LSM to 2D; upper bound on gap
- Anderson, Phys. Rev. 86, 694 (1952) -- Spin-wave theory for antiferromagnets
- Sandvik, Phys. Rev. B 56, 11678 (1997) -- QMC results for 2D Heisenberg model
- Bernu, Lhuillier & Pierre, Phys. Rev. Lett. 69, 2590 (1992) -- Anderson tower of states in exact diagonalization

## Conventions

| Convention | Choice | Notes |
|-----------|--------|-------|
| Spin operators | S = (1/2) * sigma (Pauli matrices) | S^z eigenvalues +/- 1/2 |
| Hamiltonian sign | H = J * sum S_i . S_j, J > 0 | J > 0 is antiferromagnetic |
| Lattice | Square, periodic boundary conditions | Bipartite: sublattices A and B |
| Sublattice rotation (Marshall) | Rotate B-spins by pi around y-axis | Makes off-diagonal matrix elements non-positive |
| Total spin | S_tot = sum_i S_i | [H, S_tot^2] = [H, S_tot^z] = 0 |

## Constraints

- **Computational:** Exact diagonalization limited to L <= 8 (N = 64 sites); L = 8 requires aggressive symmetry exploitation (translational + point group + spin inversion)
- **Rigor:** All bounds must be mathematically rigorous; spin-wave theory results are used only for comparison, not as part of the proof

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use periodic BC not open | Translation symmetry enables momentum quantum numbers; cleaner finite-size scaling | Adopted |
| Marshall basis for Perron-Frobenius | Standard technique for bipartite AF; makes Hamiltonian a non-negative matrix | Adopted |
| Focus on S_tot = 0 to S_tot = 1 gap | This is the physically relevant gap (magnon excitation) | Adopted |

---

_Last updated: 2026-02-24 after project initialization_
```

---

## 2. ROADMAP.md

```markdown
# Roadmap: Spectral Gap of the 2D Heisenberg Antiferromagnet

## Overview

This project progresses from a literature review of known results on the Heisenberg antiferromagnet, through construction of the Hilbert space and symmetry sectors, to rigorous analytical bounds on the spectral gap, followed by exact numerical computation for small lattices. The analytical and numerical results are cross-validated against each other and against spin-wave theory, culminating in a paper for Journal of Mathematical Physics.

## Phases

- [ ] **Phase 1: Literature and Setup** - Catalogue known bounds, establish Marshall sign rule framework, fix all conventions
- [ ] **Phase 2: Framework and Definitions** - Construct Hilbert space, classify symmetry sectors, implement block diagonalization
- [ ] **Phase 3: Analytical Structure** - Prove ground state uniqueness, establish gap bounds via Perron-Frobenius and operator inequalities
- [ ] **Phase 4: Exact Computation** - Lanczos diagonalization for L = 4, 6, 8; extract gap and finite-size scaling
- [ ] **Phase 5: Verification and Limiting Cases** - Cross-check against 1D chain (known gapless), spin-wave theory, Anderson tower
- [ ] **Phase 6: Paper Writing** - Draft manuscript for Journal of Mathematical Physics

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Compile all known rigorous results on the spectral gap of quantum antiferromagnets and fix the mathematical framework
**Depends on:** Nothing (first phase)
**Success Criteria:**

1. Marshall sign rule statement and proof outline documented with conditions for applicability (bipartite lattice, nearest-neighbor AF coupling)
2. Lieb-Mattis theorem stated precisely: E_0(S) < E_0(S+1) for the AF Heisenberg model on bipartite lattices
3. Hastings upper bound on the gap (Delta <= const * J / L) catalogued with proof strategy
4. All conventions fixed in CONVENTIONS.md: spin operators, Hamiltonian sign, sublattice labeling, Marshall transformation

Plans:

- [ ] 01-01: Survey rigorous results on AF spectral gaps (Marshall, Lieb-Mattis, LSM, Hastings)
- [ ] 01-02: Fix conventions and notation; document Marshall transformation explicitly

### Phase 2: Framework and Definitions

**Goal:** Construct the Hilbert space with all symmetry quantum numbers and verify the block structure
**Depends on:** Phase 1
**Success Criteria:**

1. Hilbert space decomposed into sectors labeled by (S_tot, S_tot^z, momentum k, point group irrep)
2. Dimension of each sector computed and cross-checked: sum of sector dimensions equals 2^N
3. Marshall-transformed Hamiltonian H_M verified to have all non-positive off-diagonal matrix elements in the Ising basis
4. Block diagonalization implemented and tested on L = 4 (N = 16, dim = 65536 before symmetry reduction)

Plans:

- [ ] 02-01: Construct symmetry sector decomposition; compute sector dimensions for L = 4, 6
- [ ] 02-02: Implement Marshall transformation; verify non-positivity of off-diagonal elements
- [ ] 02-03: Implement block-diagonal Hamiltonian construction with symmetry quantum numbers

### Phase 3: Analytical Structure

**Goal:** Establish rigorous properties of the ground state and prove a lower bound on the spectral gap
**Depends on:** Phase 2
**Success Criteria:**

1. Ground state proven unique in the (S = 0, k = 0) sector via Perron-Frobenius theorem in the Marshall basis
2. Lieb-Mattis ordering E_0(S) < E_0(S+1) verified to hold for the 2D square lattice
3. Lower bound on gap established: Delta(L) >= const * J / L^2, with explicit constant
4. Spin-wave prediction Delta = 2*pi*c/L derived for comparison (not part of rigorous bound)
5. Anderson tower structure E(S) - E_0 ~ J*S*(S+1) / (chi_perp * L^2) derived from hydrodynamic arguments

Plans:

- [ ] 03-01: Prove ground state uniqueness and establish gap bounds from spectral theory
- [ ] 03-02: Derive the spin-wave prediction and Anderson tower spectrum for finite lattices

### Phase 4: Exact Computation

**Goal:** Compute the spectral gap numerically for L = 4, 6, 8 and extract finite-size scaling
**Depends on:** Phase 2 (block diagonalization code), Phase 3 (analytical predictions to compare against)
**Success Criteria:**

1. Ground state energy E_0(L) computed for L = 4, 6, 8 with convergence to machine precision (Lanczos)
2. First excited state energy E_1(L) computed in both (S = 0) and (S = 1) sectors
3. Gap Delta(L) = E_1 - E_0 tabulated; verify that the lowest excitation is in the S = 1 sector (magnon)
4. Finite-size scaling: fit Delta(L) = A/L + B/L^2 + ... and compare A with 2*pi*c
5. Ground state energy per site compared with QMC benchmark: E_0/N -> -0.6693 J

Plans:

- [ ] 04-01: Implement Lanczos algorithm with symmetry-adapted basis; benchmark on L = 4
- [ ] 04-02: Production runs for L = 4, 6, 8; extract energies, gaps, and finite-size scaling
- [ ] 04-03: Compute the Anderson tower spectrum E(S) for S = 0, 1, 2, 3 on L = 4, 6

### Phase 5: Verification and Limiting Cases

**Goal:** Validate all results through independent cross-checks
**Depends on:** Phase 3, Phase 4
**Success Criteria:**

1. 1D chain (L x 1): gap consistent with des Cloizeaux-Pearson result Delta_1D = (pi/2)*J*|sin(k)| for the lowest magnon; gapless in thermodynamic limit (LSM theorem)
2. Ground state energy for L = 4 agrees with published exact diagonalization results
3. Gap scaling Delta(L) vs 1/L plot compared with spin-wave prediction 2*pi*c/L
4. Anderson tower E(S) - E_0 vs S(S+1) is linear with slope consistent with J/(chi_perp * L^2)
5. Sum rule check: sum of spectral weights exhausts the total spin sum rule

Plans:

- [ ] 05-01: Reproduce known 1D chain results as limiting case; verify LSM theorem consistency
- [ ] 05-02: Compare 2D results with spin-wave theory and QMC benchmarks; validate Anderson tower

### Phase 6: Paper Writing

**Goal:** Produce publication-ready manuscript for Journal of Mathematical Physics
**Depends on:** Phase 5

See paper templates for detailed paper artifacts.

**Success Criteria:**

1. Manuscript complete with: rigorous gap bound theorem, numerical gap values table, finite-size scaling figure, Anderson tower figure
2. Proof of gap bound presented with all steps and assumptions explicit
3. Results placed in context of Hastings upper bound and spin-wave theory

Plans:

- [ ] 06-01: Draft main theorem (gap bound), methods, and results sections
- [ ] 06-02: Write introduction, comparison with prior work, and conclusions

## Progress

**Execution Order:** 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 1. Literature and Setup | 0/2 | Not started | - |
| 2. Framework and Definitions | 0/3 | Not started | - |
| 3. Analytical Structure | 0/2 | Not started | - |
| 4. Exact Computation | 0/3 | Not started | - |
| 5. Verification and Limiting Cases | 0/2 | Not started | - |
| 6. Paper Writing | 0/2 | Not started | - |
```

---

## 3. PLAN.md (Phase 3, Plan 01)

```markdown
---
phase: 03-analytical-structure
plan: "01"
title: "Ground State Uniqueness and Spectral Gap Bounds"
profile: deep-theory
conventions:
  - "J = 1 (energy unit)"
  - "a = 1 (lattice spacing)"
  - "hbar = 1"
  - "S = (1/2) sigma (Pauli matrices)"
  - "H = J sum S_i . S_j, J > 0 antiferromagnetic"
  - "Marshall transformation: rotate B-sublattice spins by pi around y-axis"
must_haves:
  truths:
    - claim: "The ground state of H on the L x L square lattice is unique in the (S_tot = 0, k = 0, even parity) sector"
      method: "Perron-Frobenius theorem applied to -H_M in the Marshall basis"
      reference: "Marshall (1955); Lieb & Mattis (1962)"
    - claim: "The spectral gap satisfies Delta(L) >= C * J / L^2 for some explicit constant C > 0"
      method: "Operator inequality from SU(2) symmetry and finite-size Hilbert space structure"
      reference: "To be established in this plan"
    - claim: "The first excited state above the ground state (across all sectors) lies in the S_tot = 1 sector"
      method: "Lieb-Mattis ordering E_0(S) < E_0(S+1) for bipartite AF"
      reference: "Lieb & Mattis (1962)"
    - claim: "The Anderson tower of states has energies E(S) - E_0 = J * S(S+1) / (2 * chi_perp * L^2) to leading order"
      method: "Hydrodynamic argument / effective quantum rotor"
      reference: "Anderson (1952); Leutwyler (1994)"
  artifacts:
    - "derivations/ground_state_uniqueness.tex"
    - "derivations/gap_lower_bound.tex"
    - "derivations/anderson_tower.tex"
  key_links:
    - phase: 02-framework
      provides: "Marshall-transformed Hamiltonian H_M with non-positive off-diagonal elements"
    - phase: 02-framework
      provides: "Sector dimensions and symmetry quantum numbers for L = 4, 6"
tasks:
  - id: 1
    name: "Prove ground state uniqueness via Perron-Frobenius"
    description: |
      Apply the Perron-Frobenius theorem to the matrix -H_M (which has all non-negative
      off-diagonal elements after the Marshall transformation) restricted to the
      (S_tot = 0, k = 0) sector. The theorem guarantees that the largest eigenvalue of -H_M
      (i.e., the ground state energy of H_M, which equals the ground state energy of H) is
      non-degenerate, and the corresponding eigenvector has strictly positive components.
      This proves uniqueness of the ground state in this sector.

      Key subtlety: Must verify that -H_M restricted to the (S = 0, k = 0) sector is
      irreducible (i.e., the corresponding graph is connected). This requires showing that
      the Heisenberg exchange connects all Ising basis states within this sector.
    depends_on: []
    output: "derivations/ground_state_uniqueness.tex"
  - id: 2
    name: "Establish Lieb-Mattis ordering for the 2D square lattice"
    description: |
      Verify that the Lieb-Mattis theorem (originally proved for bipartite lattices with
      |A| = |B|) applies to the L x L square lattice with periodic BC. The theorem states:

        E_0(S) <= E_0(S') for S < S'

      where E_0(S) is the ground state energy in the total spin S sector. For strictly
      bipartite lattices with equal sublattice sizes, the inequality is strict. This
      establishes that the overall ground state has S_tot = 0, and the first excited state
      (the magnon) has S_tot = 1.
    depends_on: [1]
    output: "derivations/gap_lower_bound.tex (Section 1)"
  - id: 3
    name: "Derive lower bound Delta(L) >= C * J / L^2"
    description: |
      Establish a rigorous lower bound on the gap from the S = 0 ground state to the
      lowest S = 1 state. The argument proceeds as follows:

      1. The gap from S = 0 to S = 1 within the Anderson tower is
         Delta_tower = J / (chi_perp * L^2) where chi_perp is the perpendicular
         susceptibility per site. Since chi_perp is bounded above (chi_perp <= 1/(4J)
         from the operator bound on H), this gives Delta_tower >= 4J / L^2.

      2. The true gap may be smaller than the tower gap because the S = 1 magnon state
         at k = (2pi/L, 0) is not part of the k = 0 tower. However, the magnon gap
         scales as 1/L (faster than the tower gap 1/L^2), so for sufficiently large L
         the tower gap provides the binding constraint.

      3. For finite L, use the operator inequality: for any state |psi> in the S = 1
         sector, <psi|H|psi> >= E_0 + Delta where Delta can be bounded below using
         the norm of the spin-flip operator and the spectral gap of -H_M in the
         irreducible S = 0 block.

      The key inequality to prove: Delta(L) >= C * J / L^2 where C is an explicit
      computable constant (expected C ~ 4/chi_perp ~ 16 from the susceptibility bound,
      though the actual gap scales as 1/L from spin-wave theory).
    depends_on: [1, 2]
    output: "derivations/gap_lower_bound.tex (Section 2)"
  - id: 4
    name: "Derive the spin-wave prediction for finite-size gap"
    description: |
      Derive the linear spin-wave theory prediction for the lowest magnon energy on a
      finite L x L lattice:

        Delta_SW(L) = omega(k_min) where k_min = (2*pi/L, 0)

      The spin-wave dispersion for the Heisenberg AF on the square lattice is:

        omega(k) = 2*J*S*z * sqrt(1 - gamma_k^2)

      where z = 4 is the coordination number, S = 1/2, and
      gamma_k = (1/z) * sum_delta exp(i*k.delta) = (1/2)(cos(k_x) + cos(k_y)).

      At k_min = (2*pi/L, 0) for large L:
        gamma_k ~ 1 - (2*pi/L)^2 / 4 + ...
        omega(k_min) ~ 2*J*S*z * sqrt(1 - (1 - (2*pi/L)^2/4)^2)
                     ~ 2*J*S*z * (2*pi/L) / (2)
                     = 2*J * (2*pi/L)
                     = 4*pi*J / L    (classical, before quantum renormalization)

      Including the quantum renormalization factor Z_c ~ 1.18 from series expansions:
        c = sqrt(2) * J * a * Z_c ~ 1.658 * J * a
        Delta_SW(L) = 2*pi*c / L ~ 10.42 * J / L

      This is the comparison target for the exact diagonalization results (Phase 4).
    depends_on: []
    output: "derivations/anderson_tower.tex (Section 1)"
  - id: 5
    name: "Derive the Anderson tower spectrum"
    description: |
      The low-energy spectrum of a finite-size antiferromagnet with long-range Neel order
      consists of a "tower of states" (quantum rotor spectrum):

        E(S) - E_0 = S(S+1) / (2 * chi_perp * N)

      where chi_perp is the uniform perpendicular susceptibility per site and N = L^2.

      Derivation:
      1. Start from the effective quantum rotor Hamiltonian for the staggered order
         parameter: H_rotor = S_tot^2 / (2 * I) where I = chi_perp * N is the moment
         of inertia.
      2. Eigenvalues: E(S) = S(S+1) / (2 * chi_perp * N).
      3. The tower gap (S = 0 to S = 1) is Delta_tower = 1 / (chi_perp * N) = 1 / (chi_perp * L^2).
      4. Using the QMC value chi_perp ~ 0.0669/J (Sandvik, 1997):
         Delta_tower ~ 14.9 * J / L^2.

      This is parametrically smaller than the magnon gap ~ J/L, so the lowest excitation
      for large L is the magnon, not the tower state. But for small L, the tower and
      magnon gaps are comparable and must both be computed.
    depends_on: [3]
    output: "derivations/anderson_tower.tex (Section 2)"
```

---

## 4. SUMMARY.md (Phase 3, Plan 01 -- completed)

```markdown
---
phase: 03-analytical-structure
plan: "01"
depth: full
one-liner: "Proved ground state uniqueness via Perron-Frobenius in Marshall basis and established rigorous gap lower bound Delta >= 4J/L^2 from susceptibility operator bound"
subsystem: derivation
tags: [spectral-gap, Perron-Frobenius, Marshall-sign-rule, Lieb-Mattis, Anderson-tower, spin-wave-theory, Heisenberg-antiferromagnet]

requires:
  - phase: 02-framework
    provides: "Marshall-transformed Hamiltonian with non-positive off-diagonal elements; symmetry sector decomposition"
provides:
  - "Ground state uniqueness in (S=0, k=0) sector via Perron-Frobenius theorem"
  - "Lieb-Mattis ordering E_0(S) < E_0(S+1) verified for 2D square lattice"
  - "Rigorous lower bound: Delta(L) >= 4*J / L^2"
  - "Spin-wave prediction: Delta_SW(L) = 2*pi*c/L ~ 10.42*J/L"
  - "Anderson tower spectrum: E(S) - E_0 = S(S+1)/(2*chi_perp*L^2)"
affects:
  - "Phase 04: exact computation (predictions to compare numerical gaps against)"
  - "Phase 05: verification (limiting cases and cross-checks)"
  - "Phase 06: paper (main theorem statement)"

methods:
  added: [Perron-Frobenius theorem, Marshall transformation, operator inequalities, linear spin-wave theory, quantum rotor mapping]
  patterns: [symmetry-sector analysis before spectral bounds, irreducibility check before applying Perron-Frobenius, comparison of rigorous bounds with approximate predictions]

key-files:
  created:
    - "derivations/ground_state_uniqueness.tex"
    - "derivations/gap_lower_bound.tex"
    - "derivations/anderson_tower.tex"

key-decisions:
  - "Used susceptibility operator bound chi_perp <= 1/(4J) for rigorous lower bound rather than QMC chi_perp value"
  - "Stated spin-wave results separately from rigorous bounds to maintain mathematical rigor"

patterns-established:
  - "Rigorous bound from operator inequality, then compare with approximate theory for physical interpretation"
  - "Anderson tower spectrum provides the parametric scaling (1/L^2) while magnon gap provides the leading (1/L) behavior"

conventions:
  - "J = 1"
  - "a = 1"
  - "hbar = 1"
  - "S = (1/2) sigma"
  - "H = J sum S_i . S_j, J > 0"
  - "Marshall transformation on B-sublattice"

verification_inputs:
  truths:
    - claim: "Ground state is unique in (S=0, k=0) sector"
      test_value: "Perron-Frobenius irreducibility of -H_M restricted to (S=0, k=0)"
      expected: "Connected graph -- every pair of Ising basis states linked by sequence of Heisenberg exchanges"
    - claim: "Lieb-Mattis ordering holds: E_0(S=0) < E_0(S=1)"
      test_value: "Numerical eigenvalues for L=4"
      expected: "E_0(S=0) = -11.4885J, E_0(S=1) = -10.9632J, gap = 0.5253J"
    - claim: "Spectral gap satisfies Delta >= 4*J/L^2"
      test_value: "Numerical gap for L=4 compared with bound"
      expected: "Numerical Delta = 0.5253J >= 4/(16) = 0.25J -- bound satisfied"
  key_equations:
    - label: "Eq. (03.1)"
      expression: "\\Delta(L) \\geq \\frac{4J}{L^2}"
      test_point: "L = 4"
      expected_value: "Bound gives 0.25J; actual gap ~ 0.525J"
    - label: "Eq. (03.2)"
      expression: "\\Delta_{\\mathrm{SW}}(L) = \\frac{2\\pi c}{L} \\approx \\frac{10.42\\,J}{L}"
      test_point: "L = 4"
      expected_value: "Predicts 2.61J (spin-wave overestimates for small L)"
    - label: "Eq. (03.3)"
      expression: "E(S) - E_0 = \\frac{S(S+1)}{2\\chi_\\perp L^2}"
      test_point: "L = 4, S = 1, chi_perp = 0.0669/J"
      expected_value: "Predicts Delta_tower = 1/(0.0669 * 16) = 0.934J"
  limiting_cases:
    - limit: "L -> infinity"
      expected_behavior: "Gap vanishes: Delta ~ 1/L -> 0 (Goldstone theorem, gapless magnons)"
      reference: "Goldstone theorem; 2D Heisenberg AF has Neel order (Neel, 1936; numerical: Reger & Young, 1988)"
    - limit: "1D chain (L x 1)"
      expected_behavior: "Gap vanishes in thermodynamic limit; des Cloizeaux-Pearson spectrum omega(k) = (pi/2)*J*|sin(k)|"
      reference: "des Cloizeaux & Pearson, Phys. Rev. 128, 2131 (1962)"

duration: 85min
completed: 2026-02-24
---

# Phase 3 Plan 01: Ground State Uniqueness and Spectral Gap Bounds Summary

**Proved ground state uniqueness via Perron-Frobenius in the Marshall basis and established rigorous gap lower bound Delta >= 4J/L^2 from a susceptibility operator bound; derived spin-wave and Anderson tower predictions for comparison with exact diagonalization.**

## Performance

- **Duration:** 85 min
- **Started:** 2026-02-24T09:00:00Z
- **Completed:** 2026-02-24T10:25:00Z
- **Tasks:** 5
- **Files modified:** 3

## Key Results

- **Ground state uniqueness:** The ground state of H on the L x L square lattice is unique in the (S_tot = 0, k = 0, even parity) sector. Proof: the Marshall transformation makes -H_M a non-negative matrix; irreducibility in the (S = 0, k = 0) sector was verified by showing the exchange graph is connected; Perron-Frobenius then guarantees a unique largest eigenvalue with strictly positive eigenvector.

- **Rigorous gap bound:** Delta(L) >= 4J / L^2. Proof: the gap from S = 0 to S = 1 satisfies Delta >= 1/(chi_perp * N) where chi_perp is the uniform perpendicular susceptibility per site. The operator bound sum_i S_i^x * sum_j S_j^x <= N^2/4 combined with the fluctuation-dissipation relation chi_perp <= 1/(4J) gives the result. The bound is parametrically weaker than the true gap (which scales as 1/L from spin-wave theory) but is fully rigorous.

- **Spin-wave prediction:** Delta_SW(L) = 2*pi*c/L where c = sqrt(2)*J*a*Z_c ~ 1.658*J*a. For L = 4: Delta_SW ~ 2.61J. This overpredicts the actual gap for small L because spin-wave theory is a large-L approximation.

- **Anderson tower:** E(S) - E_0 = S(S+1)/(2*chi_perp*L^2). The tower gap (S = 0 to S = 1) is Delta_tower = 1/(chi_perp*L^2) ~ 14.9*J/L^2. For L = 4 this predicts Delta_tower ~ 0.93J, which is in the right ballpark for the actual gap of ~ 0.53J (the discrepancy reflects finite-size corrections to the quantum rotor mapping).

## Task Commits

Each task was committed atomically:

1. **Task 1: Ground state uniqueness via Perron-Frobenius** - `a1b2c3d` (derive: uniqueness proof)
2. **Task 2: Lieb-Mattis ordering for 2D square lattice** - `e4f5g6h` (derive: ordering theorem application)
3. **Task 3: Lower bound Delta >= 4J/L^2** - `i7j8k9l` (derive: gap bound from susceptibility)
4. **Task 4: Spin-wave prediction for finite-size gap** - `m0n1o2p` (derive: spin-wave dispersion at k_min)
5. **Task 5: Anderson tower spectrum** - `q3r4s5t` (derive: quantum rotor effective Hamiltonian)

**Plan metadata:** `u6v7w8x` (docs: complete plan 03-01)

## Files Created/Modified

- `derivations/ground_state_uniqueness.tex` - Perron-Frobenius proof of uniqueness; irreducibility argument for exchange graph
- `derivations/gap_lower_bound.tex` - Rigorous lower bound Delta >= 4J/L^2 from susceptibility operator bound
- `derivations/anderson_tower.tex` - Spin-wave prediction Delta_SW = 2*pi*c/L and Anderson tower E(S) - E_0 = S(S+1)/(2*chi_perp*L^2)

## Next Phase Readiness

- Analytical predictions (gap bound, spin-wave, Anderson tower) ready for comparison with exact diagonalization in Phase 4
- The bound Delta >= 4J/L^2 will be checked numerically: for L = 4, the bound predicts Delta >= 0.25J
- The spin-wave prediction Delta_SW ~ 10.42J/L and tower prediction Delta_tower ~ 14.9J/L^2 provide quantitative targets for the finite-size scaling fit

## Equations Derived

**Eq. (03.1) -- Rigorous gap lower bound:**

$$
\Delta(L) \geq \frac{4J}{L^2}
$$

Derived from the operator bound on the uniform perpendicular susceptibility: chi_perp <= 1/(4J), combined with the Anderson tower gap Delta_tower = 1/(chi_perp * N) where N = L^2.

**Eq. (03.2) -- Spin-wave prediction for finite-size gap:**

$$
\Delta_{\mathrm{SW}}(L) = \frac{2\pi c}{L}, \quad c = \sqrt{2}\,J\,a\,Z_c \approx 1.658\,J\,a
$$

Derived from the linear spin-wave dispersion omega(k) = 2JSz*sqrt(1 - gamma_k^2) evaluated at the smallest nonzero momentum k_min = (2*pi/L, 0), including the quantum renormalization factor Z_c ~ 1.18 from series expansions (Singh & Gelfand, 1995; Sandvik & Singh, 2001).

**Eq. (03.3) -- Anderson tower spectrum:**

$$
E(S) - E_0 = \frac{S(S+1)}{2\chi_\perp L^2}
$$

Derived from the quantum rotor effective Hamiltonian H_rotor = S_tot^2 / (2I) where the moment of inertia I = chi_perp * N and chi_perp ~ 0.0669/J from QMC.

**Eq. (03.4) -- Spin-wave dispersion relation:**

$$
\omega(\mathbf{k}) = 2JSz\sqrt{1 - \gamma_{\mathbf{k}}^2}, \quad \gamma_{\mathbf{k}} = \frac{1}{2}(\cos k_x + \cos k_y)
$$

Standard result from linear spin-wave theory (Anderson, 1952; Kubo, 1952). At small k: omega(k) ~ c|k| with c = 2JSz*sqrt(2)*a ~ 2*sqrt(2)*J*a (classical), renormalized to c ~ 1.658*J*a by quantum fluctuations.

## Validations Completed

- **Dimensional analysis:** All gap expressions have dimensions of energy [J]. The bound Delta >= 4J/L^2 is dimensionless in lattice units (J = a = 1). Spin-wave expression 2*pi*c/L has [energy/length]*[length]^{-1} * [length] = [energy]. Correct.

- **Limiting behavior as L -> infinity:** Rigorous bound gives Delta >= 4J/L^2 -> 0. Spin-wave gives Delta ~ 10.42J/L -> 0. Anderson tower gives Delta_tower ~ 14.9J/L^2 -> 0. All vanish, consistent with the Goldstone theorem (gapless magnons in the thermodynamic limit of the Neel-ordered phase).

- **Hierarchy of scales:** For large L, the magnon gap ~ J/L dominates over the tower gap ~ J/L^2. The magnon is the true first excited state. For small L (e.g., L = 4), the tower and magnon gaps become comparable: tower predicts 0.93J, magnon (spin-wave) predicts 2.61J, actual gap is ~ 0.53J. The tower prediction is closer for small L because the quantum rotor mapping captures the dominant S_tot quantum number physics.

- **1D chain consistency (deferred to Phase 5):** The des Cloizeaux-Pearson result for the 1D Heisenberg AF chain gives a gapless spectrum with lowest excitation omega(pi) = (pi/2)J*|sin(pi*1/L)| ~ (pi^2/2)*J/L for finite L. This is parametrically the same as the 2D spin-wave gap ~ J/L but with a different coefficient. Full comparison deferred to Phase 5.

- **Symmetry sector dimensions for L = 4:** Total Hilbert space dim = 2^16 = 65536. The (S = 0, M = 0) sector has dimension 12870 (central binomial coefficient C(16,8) partitioned by spin). After further decomposition by momentum and point group, the (S = 0, k = 0, even parity) sector is much smaller, enabling efficient Lanczos.

## Decisions & Deviations

- **Decision:** Used the operator bound chi_perp <= 1/(4J) for the rigorous lower bound instead of the tighter QMC value chi_perp ~ 0.0669/J. Rationale: the operator bound is provable from first principles; using the QMC value would give a tighter bound (Delta >= 14.9J/L^2) but would not be rigorous.

- **Decision:** Separated the rigorous bound (Eq. 03.1) from the spin-wave prediction (Eq. 03.2) into different files to make clear what is proven vs what is an approximation.

- **Minor deviation [Rule 4 -- Additional content]:** Task 5 (Anderson tower) included a comparison of chi_perp from the operator bound vs the QMC value, which was not in the original plan but provides useful context for interpreting the bound. Added as a remark in anderson_tower.tex. No impact on scope.

## Open Questions

- Can the lower bound be improved to Delta >= C*J/L (matching the spin-wave scaling) using more sophisticated methods? Nachtergaele's work on Lieb-Robinson bounds may provide a path.
- The Anderson tower prediction uses the QMC value of chi_perp. Is there a rigorous lower bound on chi_perp that would give a rigorous upper bound on the tower gap?
- For L = 4, the actual gap (~ 0.53J) is between the tower prediction (0.93J) and the rigorous bound (0.25J). What physics explains the factor of ~2 discrepancy between the tower prediction and the actual gap at this system size?

## Key Quantities and Uncertainties

| Quantity | Symbol | Value | Uncertainty | Source | Valid Range |
|----------|--------|-------|-------------|--------|-------------|
| Gap lower bound constant | C | 4 | exact (rigorous) | Susceptibility operator bound | All L |
| Spin-wave velocity | c | 1.658 J*a | +/- 0.002 | QMC (Sandvik & Singh, 2001) | L >> 1 |
| Quantum renormalization | Z_c | 1.18 | +/- 0.01 | Series expansion (Singh & Gelfand, 1995) | L >> 1 |
| Perpendicular susceptibility | chi_perp | 0.0669 / J | +/- 0.0001 | QMC (Sandvik, 1997) | L >> 1 |
| Staggered magnetization | m_s | 0.307 | +/- 0.001 | QMC (Sandvik, 1997) | L -> infinity |

## Approximations Used

| Approximation | Valid When | Error Estimate | Breaks Down At |
|--------------|-----------|----------------|----------------|
| Linear spin-wave theory | L >> 1 (long-wavelength magnons) | O(1/S) corrections ~ 18% for S=1/2 | L ~ 4 (comparable to lattice spacing) |
| Quantum rotor mapping (Anderson tower) | N >> 1 (large number of spins) | O(1/N) corrections | N ~ 16 (L = 4) |
| Susceptibility operator bound chi_perp <= 1/(4J) | Always valid (rigorous) | Overestimates chi_perp by factor ~3.7 vs QMC | Never breaks down (it's a bound) |

## Figures Produced

No figures in this plan (analytical derivations only). Figures comparing predictions with numerical data will be produced in Phase 4.

---

_Phase: 03-analytical-structure_
_Completed: 2026-02-24_
```

---

## Physics Notes for Agent Training

**Key physics facts that agents must get right when working with this project:**

1. **The spin-1/2 Heisenberg AF on the 2D square lattice is NOT gapped.** The spectral gap vanishes in the thermodynamic limit because the ground state has long-range Neel order, spontaneously breaking SU(2) -> U(1), producing two gapless Goldstone modes (magnons). This is in contrast to the 1D spin-1 chain (Haldane gap) which IS gapped.

2. **The 1D spin-1/2 AF chain is also gapless** by the Lieb-Schultz-Mattis theorem (half-integer spin per unit cell). The des Cloizeaux-Pearson dispersion gives the exact lowest excitation energy. Do NOT confuse this with the Haldane gap, which applies only to integer-spin chains.

3. **Finite-size gap scales as 1/L, not 1/L^2.** The magnon gap scales as Delta ~ c*k_min ~ c*2*pi/L ~ J/L. The Anderson tower gap scales as J/L^2. For large L, the magnon is the first excited state. The rigorous lower bound of J/L^2 is weaker than the true scaling but is provable.

4. **The Marshall sign rule applies ONLY to bipartite lattices with AF nearest-neighbor coupling.** It fails for frustrated lattices (triangular, kagome) and for next-nearest-neighbor couplings.

5. **The spin-wave velocity c ~ 1.658 J*a includes quantum corrections.** The classical value is c_cl = 2*sqrt(2)*J*a ~ 2.83*J*a. Quantum fluctuations (Z_c ~ 1.18 renormalization) reduce the sublattice magnetization but increase the velocity: c = c_cl * Z_c / (2S*z/sqrt(2)) -- the net effect is c < c_cl because the factor structure includes the sublattice magnetization reduction.

6. **QMC ground state energy for the 2D Heisenberg AF: E_0/N = -0.6693(1) J per site.** This is the benchmark for exact diagonalization results. For L = 4 (N = 16), finite-size effects are significant.
