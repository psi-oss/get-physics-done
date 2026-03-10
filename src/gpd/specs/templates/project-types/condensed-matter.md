---
template_version: 1
---

# Condensed Matter Project Template

Default project structure for condensed matter theory: strongly correlated systems, topological phases, electronic structure, magnetism, and superconductivity.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Model Definition** - Review prior work, define the model Hamiltonian, establish parameter regime
- [ ] **Phase 2: Mean-Field Theory** - Obtain mean-field phase diagram, identify order parameters, establish qualitative picture
- [ ] **Phase 3: Beyond Mean-Field** - Include fluctuations via perturbative corrections, RPA, or self-consistent methods
- [ ] **Phase 4: Numerical Methods** - Exact diagonalization, DMRG, QMC, or DFT to validate and extend analytic results
- [ ] **Phase 5: Phase Diagram and Observables** - Map out parameter space, compute measurable quantities, compare with experiment
- [ ] **Phase 6: Validation and Cross-Checks** - Verify known limits, check sum rules, compare independent methods
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Model Definition

**Goal:** Define the model, establish the parameter regime, and catalogue prior results
**Success Criteria:**

1. [Model Hamiltonian written with all terms justified from microscopic considerations]
2. [Parameter regime identified: which couplings are large/small, relevant energy scales]
3. [Symmetries of the Hamiltonian catalogued: translational, point group, spin rotation, time-reversal, particle-hole]
4. [Prior results for this model/parameter regime compiled with their methods and limitations]

Plans:

- [ ] 01-01: [Survey literature; identify the state of the art for this model]
- [ ] 01-02: [Write model Hamiltonian; analyze symmetries; fix conventions]

### Phase 2: Mean-Field Theory

**Goal:** Establish the qualitative phase diagram and identify candidate ground states
**Success Criteria:**

1. [Mean-field decoupling performed with order parameter(s) defined]
2. [Self-consistency equations derived and solved]
3. [Mean-field phase boundaries determined in relevant parameter space]
4. [Goldstone modes counted: N_broken = N_generators - N_unbroken; verify Goldstone theorem]
5. [Ginzburg criterion estimated: where do fluctuations become important?]

Plans:

- [ ] 02-01: [Perform mean-field decoupling and derive self-consistency equations]
- [ ] 02-02: [Solve self-consistency equations; map mean-field phase diagram]

### Phase 3: Beyond Mean-Field

**Goal:** Include fluctuation corrections to improve upon mean-field results
**Success Criteria:**

1. [Fluctuation method chosen and justified: RPA, 1/N expansion, epsilon expansion, Gaussian fluctuations, DMFT]
2. [Leading corrections to mean-field computed: shifts in T_c, modified exponents, or renormalized parameters]
3. [Collective excitations identified: magnons, phonons, particle-hole continuum, etc.]
4. [Response functions computed: susceptibility, spectral function, optical conductivity]

Plans:

- [ ] 03-01: [Set up fluctuation expansion around mean-field saddle point]
- [ ] 03-02: [Compute leading corrections and collective mode spectrum]
- [ ] 03-03: [Calculate response functions and dynamic structure factors]

### Phase 4: Numerical Methods

**Goal:** Validate analytic results and access non-perturbative regimes with numerical methods
**Success Criteria:**

1. [Numerical method chosen and justified for this model: ED, DMRG, QMC, DFT, DMFT]
2. [Convergence verified: system size, bond dimension, MC statistics, k-point mesh]
3. [Results compared with mean-field/beyond-MF predictions at overlapping parameter values]
4. [Non-perturbative features captured: e.g., quantum phase transitions, strong-coupling regime]

Plans:

- [ ] 04-01: [Implement numerical calculation; verify against known benchmarks]
- [ ] 04-02: [Run production calculations across parameter space]
- [ ] 04-03: [Perform finite-size scaling or convergence analysis]

### Phase 5: Phase Diagram and Observables

**Goal:** Construct the phase diagram and compute experimentally measurable quantities
**Success Criteria:**

1. [Phase diagram mapped combining analytic and numerical results]
2. [Critical exponents determined (if continuous transitions present)]
3. [Measurable quantities computed: specific heat, susceptibility, resistivity, spectral weight, etc.]
4. [Comparison with experimental data where available]

Plans:

- [ ] 05-01: [Combine results into phase diagram; identify transition lines and critical points]
- [ ] 05-02: [Compute experimentally relevant observables; compare with data]

### Phase 6: Validation and Cross-Checks

**Goal:** Confirm results via independent checks and known constraints
**Success Criteria:**

1. [Sum rules satisfied: f-sum rule, spectral weight, Kramers-Kronig consistency]
2. [Luttinger theorem verified: Fermi surface volume matches electron count]
3. [Known limiting cases reproduced: non-interacting limit, strong-coupling limit, high-T limit]
4. [Independent methods agree: analytic vs numerical at overlapping parameters]

Plans:

- [ ] 06-01: [Check sum rules, Luttinger theorem, and limiting cases]
- [ ] 06-02: [Cross-validate analytic and numerical results]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with phase diagram figure, response function plots, comparison with experiment]
2. [Approximations and their limitations clearly stated]
3. [Results placed in context of prior work]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 2 branches:** Try multiple many-body methods in parallel: mean-field, DMRG, exact diagonalization, QMC. Compare accuracy vs cost for the specific model.
- **Phase 3 expands:** Scan broader parameter range. Add phases for different interaction types (nearest-neighbor, next-nearest, long-range).
- **Extra phase:** Add "Phase 3.5: Method Benchmarking" — run all methods on a known exactly-solvable limit and compare.
- **Literature:** Survey experimental AND theoretical papers across multiple methods.

### Exploit Mode
- **Phases 1-2 compressed:** If the model and method are known (e.g., "Hubbard model with DMRG"), go directly to computation setup.
- **Phase 3 focused:** Use only the validated method. No method comparison. Tight parameter range around the region of interest.
- **Skip Phase 6 benchmarking** if the method was benchmarked in a prior milestone.
- **Skip researcher:** For well-established models with known phase diagrams.

### Adaptive Mode
- Start in explore for Phase 1 (method selection based on model properties).
- After Phase 2 validates a method against known results, switch to exploit for production runs.

---

## Standard Verification Checks for Condensed Matter

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-condmat.md` for condensed matter-specific verification (sum rules, Kramers-Kronig, Luttinger theorem).

---

## Typical Approximation Hierarchy

| Level                                  | Method                      | Captures                                                 | Misses                                     |
| -------------------------------------- | --------------------------- | -------------------------------------------------------- | ------------------------------------------ |
| Non-interacting                        | Band theory / tight-binding | Band structure, topology, Fermi surface                  | Correlations, Mott physics                 |
| Mean-field                             | Hartree-Fock, BCS, Stoner   | Ordered phases, qualitative phase diagram                | Fluctuations, critical exponents           |
| Gaussian fluctuations                  | RPA, spin-wave theory, BdG  | Collective modes, leading corrections to T_c             | Strong fluctuation effects                 |
| Self-consistent (DMFT)                 | Local quantum fluctuations  | Mott transition, Kondo physics, spectral weight transfer | Non-local correlations, d-wave pairing     |
| Cluster extensions                     | DCA, CDMFT                  | Short-range spatial correlations                         | Long-range order (finite cluster)          |
| Numerically exact (for finite systems) | ED, DMRG, QMC               | All correlations at finite size                          | Thermodynamic limit (extrapolation needed) |

---

## Common Pitfalls for Condensed Matter

1. **DFT band gap problem:** LDA/GGA underestimates band gaps systematically. Never compare DFT Kohn-Sham gaps directly with experiment. Use GW, hybrid functionals, or scissors correction
2. **Wrong Hubbard U:** DFT+U results are extremely sensitive to U. Use constrained RPA or linear response to determine U; do not fit to experiment
3. **Finite-size effects in ED/QMC:** Small systems have artificial gaps and level repulsion. Always extrapolate to thermodynamic limit using finite-size scaling
4. **Sign problem in QMC:** Away from special symmetry points (half-filling, bipartite lattice), fermionic QMC has exponential sign problem. Results may have uncontrolled systematic errors
5. **DMRG in 2D:** Required bond dimension grows exponentially with cylinder circumference. Results on wide cylinders may not be converged
6. **Neglecting spin-orbit coupling:** Critical for topological phases, heavy elements (5d), and magnetocrystalline anisotropy
7. **Confusing spectral function and DOS:** DOS integrates A(k,omega) over k. Sharp quasiparticle features in A(k,omega) can be smeared in DOS
8. **Mean-field critical exponents in low d:** Mean-field exponents are quantitatively wrong below the upper critical dimension (d_c = 4 for Ising/O(n)). Do not use mean-field for quantitative predictions near T_c in d = 2 or 3
9. **Pseudopotential transferability:** A pseudopotential validated for bulk may fail for surfaces, defects, or high-pressure phases. Test against all-electron calculations

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Condensed matter projects should populate:

- **Unit System:** Natural units or lattice units with explicit conversions
- **Lattice Convention:** Site-centered vs bond-centered, lattice spacing, Brillouin zone definition
- **Spin Convention:** Spin quantization axis, SU(2) vs U(1) symmetry
- **Fourier Convention:** Lattice Fourier transform normalization (1/N vs 1/sqrt(N))
- **Ensemble:** Canonical, grand canonical, or microcanonical with justification
- **Order Parameter Convention:** Definition and normalization of order parameter

---

## Computational Environment

**Exact diagonalization and many-body:**

- `QuSpin` (Python) — Exact diagonalization for quantum spin systems, Hubbard models, Bose-Hubbard
- `ITensor` (Julia/C++) — Tensor network methods: DMRG, TEBD, MPS/MPO
- `ALPS` — Quantum Monte Carlo, exact diagonalization, DMFT
- `PETSc` + `SLEPc` — Large-scale sparse eigenvalue problems

**Band structure and DFT:**

- `Quantum ESPRESSO` — Plane-wave DFT, phonons, electron-phonon coupling
- `VASP` — Projector-augmented wave DFT (commercial)
- `Wannier90` — Maximally-localized Wannier functions from DFT bands
- `PythTB` (Python) — Tight-binding models, topological invariants

**Analysis and visualization:**

- `numpy`, `scipy` — Numerical linear algebra, FFT, optimization
- `matplotlib` — Band structures, spectral functions, phase diagrams
- `kwant` (Python) — Quantum transport in mesoscopic systems

**Setup:**

```bash
pip install numpy scipy matplotlib quspin kwant pythtb
# For ITensor: julia> using Pkg; Pkg.add("ITensors")
```

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Altland & Simons, *Condensed Matter Field Theory* | Field theory methods for condensed matter; path integrals, RG | Theoretical framework |
| Bruus & Flensberg, *Many-Body Quantum Theory in CM Physics* | Green's functions, diagrammatics, superconductivity | Perturbative many-body |
| Sachdev, *Quantum Phase Transitions* | Critical phenomena, scaling, quantum criticality | Phase transitions |
| Auerbach, *Interacting Electrons and Quantum Magnetism* | Spin models, mean-field, spin waves, frustration | Magnetism |
| Mahan, *Many-Particle Physics* | Green's functions, transport, optical properties | Response functions |
| Ashcroft & Mermin, *Solid State Physics* | Band theory, Fermi surfaces, phonons | Band structure reference |

---

## Worked Example: Hubbard Model Phase Diagram at Half-Filling

**Phase 1 — Setup:** 2D square lattice Hubbard model H = -t sum_{<ij>} c†_i c_j + U sum_i n_↑ n_↓ at half-filling (one electron per site). Conventions: t=1 (energy unit), lattice spacing a=1. Goal: map the metal-insulator (Mott) transition as a function of U/t.

**Phase 2 — Mean-field:** Hartree-Fock decoupling → antiferromagnetic (AFM) order for any U>0 at T=0 (artifact of mean-field). Staggered magnetization m = <S^z_A> - <S^z_B>. Gap Delta ~ U*m. This overestimates ordering — known limitation.

**Phase 3 — Beyond mean-field:** DMRG on 2D cylinders (Lx x Ly with Ly=4,6,8). Monitor: (1) charge gap Delta_c = E(N+1) + E(N-1) - 2E(N) → finite for Mott insulator, zero for metal; (2) spin structure factor S(pi,pi) → AFM order; (3) entanglement entropy → area law (gapped) vs log correction (critical). Convergence: bond dimension chi = 200, 400, 800; extrapolate in 1/chi.

**Validation:** At U=0: free fermion, metallic, Delta_c=0 (exact). At U>>t: Heisenberg model, J=4t²/U, staggered magnetization m~0.307 (known QMC result). At U_c~8t: Mott transition (compare with cluster DMFT: U_c=6-8t depending on method).
