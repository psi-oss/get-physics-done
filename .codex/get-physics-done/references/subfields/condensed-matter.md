---
load_when:
  - "condensed matter"
  - "solid state"
  - "band theory"
  - "superconductivity"
  - "magnetism"
  - "Bloch theorem"
  - "Fermi liquid"
tier: 2
context_cost: medium
---

# Condensed Matter Physics

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/tensor-networks.md`, `references/protocols/monte-carlo.md`, `references/protocols/density-functional-theory.md`, `references/protocols/exact-diagonalization.md`, `references/protocols/many-body-perturbation-theory.md`, `references/protocols/non-equilibrium-transport.md`, `references/protocols/analytic-continuation.md`, `references/protocols/numerical-computation.md`, `references/protocols/green-functions.md`, `references/protocols/generalized-symmetries.md`, `references/protocols/wkb-semiclassical.md`, `references/protocols/bethe-ansatz.md` (integrable 1D models), `references/protocols/random-matrix-theory.md` (spectral statistics, quantum chaos), `references/protocols/large-n-expansion.md` (1/N methods for O(N) and SU(N) models), `references/protocols/kinetic-theory.md` (Boltzmann transport).

**Band Theory and Electronic Structure:**

- Bloch theorem: psi_{n,k}(r) = u_{n,k}(r) * exp(i*k\*r) for periodic potentials
- Band structure: E_n(k) gives energy vs crystal momentum for band index n
- Tight-binding models: expand in atomic orbitals; hopping parameters from overlap integrals
- k.p perturbation theory: expand near high-symmetry points for effective mass and band curvature
- Topological band theory: Chern numbers, Z2 invariants, Berry phase/curvature

**Density Functional Theory (DFT):**

- Hohenberg-Kohn theorems: ground state energy is a functional of electron density n(r)
- Kohn-Sham equations: map interacting system to non-interacting system with same density
- Exchange-correlation functionals: LDA, GGA (PBE), meta-GGA (SCAN), hybrid (HSE06, PBE0)
- Pseudopotentials: norm-conserving (Troullier-Martins), ultrasoft (Vanderbilt), PAW (projector augmented wave)
- Plane-wave basis with kinetic energy cutoff; convergence with respect to cutoff and k-point mesh

**Dynamical Mean-Field Theory (DMFT):**

- Maps lattice problem to self-consistent quantum impurity problem
- Impurity solvers: continuous-time QMC (CT-HYB, CT-INT), exact diagonalization, NRG
- Self-consistency: local Green's function G_loc(omega) = integral dk G(k, omega) must equal impurity G
- DFT+DMFT: combines DFT band structure with local DMFT correlations
- Cluster extensions: DCA (dynamical cluster approximation), CDMFT (cellular DMFT)

**Many-Body Perturbation Theory:**

- **GW approximation:** Self-energy Sigma = i*G*W; standard for quasiparticle band gaps. G0W0 (one-shot) vs self-consistent GW
- **Bethe-Salpeter equation (BSE):** Two-particle equation for optical response; captures excitons
- **T-matrix approximation:** Resummation for strong short-range interactions
- **Random Phase Approximation (RPA):** Screening and dielectric function; exact for long-range correlations at high density

**Tensor Network Methods:**

- **DMRG (Density Matrix Renormalization Group):** Ground state of 1D systems; MPS representation; scales as chi^3 _ d _ L
- **MPS (Matrix Product States):** Variational ansatz for 1D; entanglement entropy bounded by log(chi)
- **PEPS (Projected Entangled Pair States):** 2D generalization of MPS; contraction is #P-hard; approximate contraction needed
- **MERA (Multiscale Entanglement Renormalization Ansatz):** Captures scale invariance; log corrections to area law
- **Time-dependent DMRG (tDMRG):** Real-time evolution via Suzuki-Trotter or TDVP; limited by entanglement growth

**Quantum Monte Carlo:**

- **Variational MC (VMC):** Sample from |psi_T|^2; optimize variational parameters
- **Diffusion MC (DMC):** Project out ground state via imaginary-time evolution; fixed-node approximation for fermions
- **Auxiliary-field QMC (AFQMC):** Hubbard-Stratonovich transformation; sign problem for general interactions
- **Determinantal QMC (DQMC):** Exact for specific models (half-filled Hubbard on bipartite lattice); sign problem away from these points

**Exact Diagonalization:**

- Full diagonalization: all eigenvalues and eigenstates; limited to ~20 sites (Hubbard) or ~40 spins (S=1/2)
- Lanczos: ground state and low-lying excitations; can reach ~36 sites
- Shift-invert: target specific energy windows
- Symmetry reduction: exploit translational, point group, spin symmetries to block-diagonalize

**Hubbard and Lattice Models:**

- Hubbard model: H = -t _ sum c^dag c + U _ sum n_up n_down; minimal model for correlated electrons
- Heisenberg model: H = J \* sum S_i . S_j; effective model in strong-coupling limit (U >> t)
- t-J model: Hubbard projected to no double occupancy; relevant for cuprate superconductors
- Anderson model: single impurity coupled to bath; fundamental to DMFT and Kondo physics
- Holstein model: electron-phonon coupling on lattice

**Topological Phases:**

- Topological insulators: bulk gap with protected edge/surface states; Z2 classification
- Quantum Hall effect: integer (IQHE, Chern number) and fractional (FQHE, anyonic excitations)
- Topological superconductors: Majorana edge modes; potential for topological quantum computation
- Symmetry-protected topological phases: classification by symmetry class (ten-fold way)
- Berry phase and Berry curvature: geometric phase from parameter space; Chern number = integral of Berry curvature over BZ

## Key Tools and Software

| Tool                 | Purpose                                           | Notes                                              |
| -------------------- | ------------------------------------------------- | -------------------------------------------------- |
| **VASP**             | DFT with PAW; band structure, relaxation          | Commercial; widely used; excellent PAW potentials  |
| **Quantum ESPRESSO** | DFT with plane waves and pseudopotentials         | Open-source; phonons, DFPT, GW, BSE (via Yambo)    |
| **Wien2k**           | All-electron DFT (LAPW)                           | Full-potential; precise core-level properties      |
| **ABINIT**           | DFT, DFPT, many-body perturbation theory          | Open-source; GW, BSE built-in                      |
| **Yambo**            | GW and BSE                                        | Post-processing for QE and ABINIT                  |
| **TRIQS**            | DMFT toolkit                                      | Python; CT-HYB solver; DFT+DMFT interface          |
| **ALPS**             | Quantum lattice models                            | MC, DMRG, exact diag; community-maintained         |
| **ITensor**          | Tensor network library (Julia/C++)                | DMRG, MPS, MPO; excellent for 1D systems           |
| **TeNPy**            | Tensor networks (Python)                          | DMRG, TEBD, MPS; well-documented                   |
| **PETSc / SLEPc**    | Sparse linear algebra / eigensolvers              | Large-scale exact diagonalization                  |
| **Wannier90**        | Maximally localized Wannier functions             | Interface to DFT codes; tight-binding Hamiltonians |
| **Z2Pack**           | Topological invariant computation                 | Z2 invariant, Chern number from DFT                |
| **WannierTools**     | Topological properties from Wannier tight-binding | Surface states, Wilson loops, Berry curvature      |
| **CASINO**           | Quantum Monte Carlo                               | VMC, DMC; periodic systems                         |
| **QMCPACK**          | Quantum Monte Carlo (open-source)                 | VMC, DMC, AFQMC; GPU-accelerated                   |
| **QuSpin**           | Exact diagonalization (Python)                    | Symmetry-aware; dynamics; user-friendly            |

## Validation Strategies

**Sum Rules:**

- f-sum rule: integral of Re[sigma(omega)] _ omega d(omega) = pi _ n * e^2 / (2*m) (optical conductivity)
- Spectral weight sum rule: integral of A(k, omega) d(omega) = 1 for each k (spectral function)
- Kramers-Kronig relations: Re and Im parts of response functions are Hilbert transforms of each other

**Luttinger Theorem:**

- Volume enclosed by Fermi surface = number of electrons (mod filled bands)
- Holds for interacting systems (with caveats for topological order)
- Check: count k-points inside Fermi surface vs electron count in DFT/DMFT

**Symmetry Breaking Patterns:**

- Goldstone theorem: each spontaneously broken continuous symmetry gives one gapless mode (or two for non-relativistic systems with type-B Goldstone modes)
- Check: number of gapless excitations matches count of broken generators
- Mermin-Wagner theorem: no spontaneous breaking of continuous symmetry in d <= 2 at T > 0 (for short-range interactions)

**Standard Benchmarks:**

- 2D Hubbard model: compare with auxiliary-field QMC at half-filling (no sign problem)
- 1D Heisenberg chain: exact Bethe ansatz ground state energy E_0/J = 1/4 - ln(2) per site
- Hydrogen chain: compare with CCSD(T) and DMRG
- Silicon band gap: DFT-LDA gives ~0.5 eV (underestimate); GW gives ~1.1-1.2 eV; experiment ~1.17 eV
- Homogeneous electron gas: QMC correlation energy (Ceperley-Alder) is the standard reference for LDA

**Convergence Checks:**

- k-point mesh convergence: total energy vs k-mesh density
- Plane-wave cutoff convergence: total energy vs E_cut
- Basis set convergence: DMRG bond dimension chi; exact diag system size
- QMC: statistical error bars, autocorrelation time, finite-size extrapolation

## Common Pitfalls

- **DFT band gap problem:** LDA/GGA systematically underestimates band gaps. Do not compare DFT gaps directly with experiment without correction (GW, hybrid functionals, scissors operator)
- **Pseudopotential transferability:** A pseudopotential tested for bulk may fail for surfaces, defects, or high-pressure phases. Always check against all-electron results or use PAW
- **Sign problem in QMC:** Away from special symmetry points (e.g., half-filling on bipartite lattice), fermionic QMC has exponential sign problem. Results may have uncontrolled errors
- **Finite-size effects:** Small system sizes introduce artificial gaps, level repulsion, and finite-size scaling artifacts. Always extrapolate to thermodynamic limit
- **DMRG in 2D:** DMRG is variational for MPS (1D). In 2D, the required bond dimension grows exponentially with cylinder circumference. Results may not be converged
- **Neglecting spin-orbit coupling:** Critical for topological phases, heavy elements, and magnetocrystalline anisotropy. DFT without SOC misses Z2 invariant entirely
- **Wrong Hubbard U:** DFT+U results are extremely sensitive to the value of U. Use constrained RPA or linear response to determine U, not fitting to experiment
- **Confusing spectral function and DOS:** The density of states integrates the spectral function over k. Features in A(k,omega) can be smeared out in the DOS

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Topological phases beyond TI/TSC** | Higher-order topology, fragile topology, non-Hermitian topology | Bernevig, Vishwanath, Hasan | Good — band structure + symmetry analysis |
| **Generalized / non-invertible symmetries** | How do defect algebras and higher-form or non-invertible symmetries diagnose topological order and beyond-Landau phases? | McGreevy, Senthil, Gaiotto, Thorngren | Good — strongest when paired with lattice, tensor-network, or exactly solvable diagnostics |
| **Moiré materials** | Flat bands, correlated insulators, unconventional SC in twisted bilayer graphene, TMDs | Mak, Shan, Young, Efetov | Moderate — requires large-scale numerics |
| **Quantum spin liquids** | Experimental confirmation, entanglement signatures, spinon Fermi surfaces | Savary, Balents, Broholm | Good — DMRG, VMC, parton mean-field |
| **Non-equilibrium many-body** | MBL fate in thermodynamic limit, prethermal phases, Floquet engineering | Abanin, Altman, Nandkishore | Good — TEBD/TDVP for dynamics |
| **Altermagnets** | New magnetic order with spin-split bands but zero net magnetization | Šmejkal, Sinova, Jungwirth | Excellent — DFT band structure + symmetry |
| **Quantum error correction in condensed matter** | Topological codes, measurement-based phases, fractons | Kitaev, Nayak, Raussendorf | Good — exact diag + entanglement |

## Methodology Decision Tree

```
What is the primary question?
├── Ground state properties
│   ├── Weakly correlated? → DFT (PBE/HSE) + Wannier downfolding
│   ├── Strongly correlated, 1D? → DMRG (bond dim 200-2000)
│   ├── Strongly correlated, 2D? → VMC/DMRG cylinder or DQMC (if no sign problem)
│   └── Topological? → Band topology (Z2, Chern) + edge state calculation
├── Excited states / spectral properties
│   ├── Quasiparticle bands? → GW approximation (on top of DFT)
│   ├── Optical spectra? → BSE (Bethe-Salpeter equation)
│   └── Strongly correlated spectra? → DMFT + analytic continuation (MaxEnt)
├── Finite temperature
│   ├── Classical phase transition? → Monte Carlo (Wolff cluster near Tc)
│   ├── Quantum phase transition? → QMC (world-line, SSE) if sign-free
│   └── Transport? → Kubo formula (DMFT or Boltzmann equation)
└── Dynamics
    ├── Short time (< 100 J^{-1})? → TEBD / TDVP
    ├── Steady state? → Lindblad master equation or Keldysh
    └── Hydrodynamic? → Generalized hydrodynamics or Boltzmann
```

## Common Collaboration Patterns

- **Theory + ARPES/STM:** Theorists provide spectral functions A(k,omega); experimentalists measure via ARPES. Direct comparison validates electronic structure.
- **Condensed matter + Quantum info:** Entanglement measures (entanglement entropy, mutual information) characterize phases. Tensor network methods bridge both fields.
- **Condensed matter + Cold atoms:** Optical lattice experiments realize model Hamiltonians (Hubbard, Heisenberg). Theory provides phase diagrams; experiment provides quantum simulation.
- **Materials science + Condensed matter theory:** DFT practitioners compute specific materials; theorists extract universal physics. Wannier downfolding bridges ab initio and model Hamiltonians.

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | Phase diagram of one model by one method, or DFT study of one material class | "DMRG phase diagram of the J1-J2 Heisenberg model on the triangular lattice" |
| **Postdoc** | Multi-method comparison, new algorithm, or theory-experiment collaboration | "Comparison of DMFT and DMRG for the doped Hubbard model; connection to cuprate experiments" |
| **Faculty** | New theoretical framework, new phase of matter, or definitive numerical result | "Classification of symmetry-protected topological phases in interacting systems"
