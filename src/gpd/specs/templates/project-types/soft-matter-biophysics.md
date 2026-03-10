---
template_version: 1
---

# Soft Matter and Biophysics Project Template

Default project structure for soft matter and biological physics: polymer physics, colloidal systems, liquid crystals, membranes and vesicles, active matter, biological networks, protein folding, molecular motors, cell mechanics, and statistical mechanics of complex fluids.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Setup** - Identify the soft matter system, relevant length/time/energy scales, establish conventions
- [ ] **Phase 2: Model Construction** - Coarse-grained Hamiltonian or free energy functional, identify order parameters, define interactions
- [ ] **Phase 3: Mean-Field / Analytical Theory** - Mean-field phase diagram, scaling arguments, Flory-Huggins or Landau theory
- [ ] **Phase 4: Fluctuation Analysis** - Gaussian fluctuations, renormalization if needed, critical phenomena
- [ ] **Phase 5: Simulation** - Molecular dynamics or Monte Carlo with coarse-grained model, validate against theory
- [ ] **Phase 6: Comparison with Experiment** - Compare predictions with experimental data (rheology, scattering, imaging)
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Define the soft matter or biological system, identify all relevant scales and dimensionless numbers, and compile known theoretical and experimental results
**Success Criteria:**

1. [System clearly defined: components, geometry, boundary conditions, physiological or experimental conditions]
2. [Characteristic scales established: length (persistence length, Debye length, capillary length), energy (k_BT, binding energy), time (Rouse time, reptation time, membrane relaxation)]
3. [Relevant dimensionless numbers identified: Peclet, Weissenberg, Deborah, Flory interaction parameter chi, packing fraction phi]
4. [Prior theoretical and experimental results catalogued with methods and key findings]
5. [Conventions fixed: units (reduced LJ, real, or SI), ensemble, boundary conditions]

Plans:

- [ ] 01-01: [Survey literature for theoretical treatments and experimental measurements of this system]
- [ ] 01-02: [Fix units, scales, and conventions; document in NOTATION_GLOSSARY.md]

### Phase 2: Model Construction

**Goal:** Build a coarse-grained Hamiltonian or free energy functional at the appropriate resolution with clearly identified order parameters
**Success Criteria:**

1. [Order parameter(s) identified and justified: concentration phi, nematic tensor Q_ij, membrane shape h(x), polarization p]
2. [Free energy functional or Hamiltonian written with all terms and their physical origin]
3. [Interaction potentials specified: excluded volume, van der Waals, electrostatic screening, Helfrich bending]
4. [Symmetry analysis: which terms are allowed by system symmetries (translational, rotational, chiral)]
5. [Relevant constraints identified: incompressibility, fixed topology, conservation laws]
6. [Coupling constants expressed in terms of microscopic parameters or fitted to experiment]

Plans:

- [ ] 02-01: [Identify order parameters and write free energy functional]
- [ ] 02-02: [Determine coupling constants from microscopic arguments or experimental fitting]
- [ ] 02-03: [Validate single-component or dilute-limit properties against known results]

### Phase 3: Mean-Field / Analytical Theory

**Goal:** Solve the model at mean-field level to obtain phase diagrams, scaling laws, and baseline predictions
**Success Criteria:**

1. [Mean-field equations derived: saddle-point of free energy, self-consistent field equations, or Euler-Lagrange equations]
2. [Phase diagram computed: phase boundaries, critical points, spinodal lines, triple points]
3. [Scaling arguments applied: Flory exponent, blob model, Alexander-de Gennes brush scaling]
4. [Analytical results obtained where possible: Flory-Huggins chi_c, Onsager nematic transition, CMC]
5. [Response functions computed: osmotic compressibility, elastic moduli, susceptibilities]
6. [Stability analysis performed: second variation of free energy, spinodal decomposition condition]

Plans:

- [ ] 03-01: [Derive and solve mean-field equations; compute phase diagram]
- [ ] 03-02: [Apply scaling arguments and identify power-law regimes]
- [ ] 03-03: [Compute response functions and check thermodynamic stability]

### Phase 4: Fluctuation Analysis

**Goal:** Go beyond mean-field to include fluctuation corrections, identify when mean-field breaks down, and characterize critical behavior
**Success Criteria:**

1. [Gaussian fluctuation spectrum computed: expand free energy to second order around mean-field solution]
2. [Ginzburg criterion evaluated: determine temperature/concentration range where mean-field fails]
3. [Correlation length and susceptibility divergence characterized near critical points]
4. [Renormalization group analysis performed if system is near upper critical dimension]
5. [Anomalous scaling exponents determined for the appropriate universality class]
6. [Fluctuation corrections to observables quantified: shift of critical point, renormalized elastic constants]

Plans:

- [ ] 04-01: [Expand free energy to Gaussian order; compute fluctuation spectrum and correlation functions]
- [ ] 04-02: [Evaluate Ginzburg criterion; determine regime of validity of mean-field theory]
- [ ] 04-03: [Perform RG analysis or identify universality class for critical behavior]

### Phase 5: Simulation

**Goal:** Validate analytical predictions with molecular dynamics or Monte Carlo simulation of a coarse-grained model
**Success Criteria:**

1. [Simulation model constructed: bead-spring, lattice, or continuum; force field parameters consistent with analytical model]
2. [Equilibration verified: energy, pressure, order parameter converged with no drift]
3. [Static observables measured: radial distribution function g(r), structure factor S(q), density profiles, R_g]
4. [Dynamic observables measured: MSD, diffusion coefficient, relaxation times, viscosity]
5. [Scaling laws verified against analytical predictions: R_g ~ N^nu, D ~ N^{-alpha}, phase boundaries]
6. [Finite-size analysis: multiple system sizes to assess finite-size corrections]
7. [Statistical errors quantified with block averaging and autocorrelation correction]

Plans:

- [ ] 05-01: [Build simulation model consistent with analytical theory; equilibrate]
- [ ] 05-02: [Measure static and dynamic observables; compare with mean-field and fluctuation predictions]
- [ ] 05-03: [Perform finite-size scaling and quantify statistical errors]

### Phase 6: Comparison with Experiment

**Goal:** Validate model predictions against experimental data and identify model limitations
**Success Criteria:**

1. [Quantitative comparison with experimental measurements: scattering (SAXS, SANS, DLS), rheology (G', G''), imaging (confocal, AFM, cryo-EM)]
2. [Discrepancies identified and attributed: missing physics, coarse-graining artifact, or finite-size effect]
3. [Predictions made for experimentally accessible but unmeasured quantities]
4. [Sensitivity analysis: which model parameters most affect key observables]
5. [Limitations clearly stated: which regimes the model can and cannot describe]

Plans:

- [ ] 06-01: [Compare theoretical and simulation results with experimental data; quantify agreement]
- [ ] 06-02: [Perform sensitivity analysis on model parameters and approximation choices]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript includes model construction, analytical theory, simulation validation, and experimental comparison]
2. [Error analysis clearly presented: statistical, systematic, and model-dependent uncertainties]
3. [Phase diagrams and scaling plots presented with clearly labeled axes and regimes]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 2 splits:** Construct free energy functionals at multiple levels of coarse-graining (microscopic, mesoscopic, continuum) and compare predictions. Evaluate which terms in the free energy are essential.
- **Phase 3 branches:** Compare Flory-Huggins, self-consistent field theory, and density functional theory for the same system. Determine which captures the target physics.
- **Phase 4 extended:** Explore multiple RG approaches (epsilon expansion, functional RG, Monte Carlo RG) to determine critical exponents. Compare with known universality classes.
- **Extra phase:** Add "Phase 3.5: Theory Comparison" — systematically compare mean-field approaches (Flory-Huggins vs Landau vs SCF) to identify which best describes the phase behavior and where each breaks down.
- **Literature depth:** 20+ papers spanning theory, simulation, and experiment for the target system.

### Exploit Mode
- **Phases 1-2 compressed:** Use established free energy functional from prior work. Skip comparison of alternative models.
- **Phase 3 focused:** Apply the standard mean-field theory (Flory-Huggins for blends, Alexander for brushes, Helfrich for membranes). No comparison of alternatives.
- **Phase 4 skipped or minimal:** If the system is far from critical points and mean-field is known to be adequate, skip fluctuation analysis.
- **Skip Phase 7:** If results feed into a larger study, output SUMMARY.md with key results and scaling exponents.
- **Skip researcher:** If the calculation follows a known pattern (same model at a new parameter value, or established scaling analysis for a new system).

### Adaptive Mode
- Start in explore for Phases 1-3 (model selection and mean-field analysis).
- Switch to exploit for Phases 4-6 once the free energy functional and mean-field behavior are validated.

---

## Standard Verification Checks for Soft Matter / Biophysics

See `references/verification/core/verification-core.md` for universal checks, `references/verification/domains/verification-domain-soft-matter.md` for soft-matter-specific verification (equilibration, scaling laws, force field validation, finite-size analysis, active matter checks), and `references/verification/domains/verification-domain-statmech.md` for statistical mechanics checks (detailed balance, thermodynamic consistency, finite-size scaling).

### Domain-Specific Verification

1. **Thermodynamic consistency:** Free energy derivatives reproduce observables — (dF/dV)_T = -P, (dF/dT)_V = -S, (d mu/d phi) > 0 for stability of homogeneous phase
2. **Detailed balance:** Transition rates satisfy w(A->B)/w(B->A) = exp(-Delta E / k_BT) for MC moves; Langevin integrator preserves Boltzmann distribution
3. **Fluctuation-dissipation theorem:** Response function related to equilibrium fluctuations — chi = beta * (<X^2> - <X>^2); violated only in active or driven systems
4. **Equipartition:** (1/2) k_BT per quadratic degree of freedom — verify kinetic energy per particle = (3/2) k_BT in simulation
5. **Polymer scaling:** R_g ~ N^nu with nu = 0.588 (good solvent, 3D), 0.5 (theta solvent), 1/3 (poor solvent/globule); R_g ~ N^{3/4} in 2D good solvent
6. **Stokes-Einstein relation:** D = k_BT / (6 pi eta R_H) for dilute particles in equilibrium; failure signals glassy dynamics or active driving
7. **Virial pressure:** P = nk_BT + (1/3V) sum_{i<j} r_ij * f_ij — must be consistent with equation of state from free energy
8. **Conservation laws:** Total energy (NVE), total momentum, center of mass; incompressibility constraint if assumed
9. **Gibbs-Duhem relation:** Along coexistence curves, sum_i x_i d(mu_i) = 0 at constant T, P

---

## Typical Approximation Hierarchy

| Level | Approximation | Key Assumption | Typical Accuracy | Limitations |
|-------|--------------|----------------|------------------|-------------|
| Flory-Huggins | Lattice mean-field | Random mixing on lattice; no correlations | Qualitative phase diagram; chi_c exact for symmetric blends | Misses fluctuation corrections near critical point; wrong exponents |
| Self-consistent field theory (SCFT) | Saddle-point of field theory | Gaussian chains in mean field; no fluctuations | Quantitative for high-MW polymers (N >> 1) | Fails near ODT for diblock copolymers (Fredrickson-Helfand corrections) |
| Landau-Ginzburg | Gradient expansion near transition | Order parameter small and slowly varying | Correct symmetry and topology of phase diagram | Mean-field exponents; breaks down within Ginzburg region |
| Gaussian fluctuations | Quadratic expansion around saddle point | Small deviations from mean-field | Correlation functions; Ginzburg criterion | Misses nonlinear effects, strong fluctuation regime |
| Renormalization group | Systematic resummation | Universality near critical point | Correct critical exponents to O(epsilon^n) | Requires proximity to critical point; perturbative in epsilon = 4 - d |
| Coarse-grained simulation | Numerical; no saddle-point approximation | Model Hamiltonian accurate; sampling sufficient | Full fluctuation effects captured; scaling exponents correct | Computational cost; finite-size artifacts; dynamics rescaled |

**When to go beyond mean-field:**

- Ginzburg criterion violated: fluctuations dominate within a temperature window |T - T_c| / T_c < Gi around the critical point
- Low-dimensional systems: 1D polymers, 2D membranes — mean-field fails; fluctuations dominate
- Near critical micelle concentration: fluctuations shift CMC and broaden the transition
- Active matter: detailed balance broken; free energy functional does not exist; mean-field misses giant number fluctuations
- Small systems: single molecules, nanopores, few-particle clusters — fluctuations comparable to mean

---

## Common Pitfalls for Soft Matter / Biophysics

1. **Persistence length vs contour length:** The persistence length l_p is the decay length of tangent-tangent correlations; the contour length L = Nb is the total chain length. Flexible chain: L >> l_p. Semiflexible: L ~ l_p. Confusing them misidentifies the polymer regime (flexible vs rigid rod) and gives wrong scaling exponents
2. **Rouse vs Zimm dynamics:** Rouse model (no hydrodynamic interactions): tau_R ~ N^2, D ~ N^{-1}. Zimm model (with HI): tau_Z ~ N^{3*nu}, D ~ N^{-nu}. Using Rouse scaling for dilute solution polymers (where Zimm applies) gives wrong dynamic exponents. Implicit solvent simulations suppress HI and give Rouse dynamics by default
3. **Flory exponent in wrong dimension:** nu = 3/(d+2) from Flory theory gives nu = 0.6 (3D), 0.75 (2D), 1.0 (1D). The exact 3D value is nu = 0.5876. Using the 3D exponent for a 2D simulation (confined polymer) gives incorrect scaling
4. **Hydrodynamic interactions:** Omitting HI (Langevin/Brownian dynamics with implicit solvent) qualitatively changes collective dynamics: sedimentation, cooperative diffusion, and active swimmer behavior all require HI. Use DPD, lattice-Boltzmann, or Stokesian dynamics to restore them
5. **Capillary length:** l_c = sqrt(gamma / (rho g)) ~ 2.7 mm for water. For systems smaller than l_c, gravity is negligible and surface tension dominates. For systems larger than l_c, gravity flattens interfaces. Using the wrong regime changes the shape equations
6. **Fluctuation corrections near critical micelle concentration:** Mean-field predicts a sharp CMC; fluctuations broaden it. The polydispersity of micelle sizes diverges near CMC. Treating micellization as a sharp transition overestimates the sharpness of onset
7. **Translational entropy of polymers vs monomers:** In Flory-Huggins, the translational entropy of a polymer chain of N monomers is (phi/N) ln(phi), NOT phi ln(phi). Missing the 1/N factor overestimates the entropy of mixing by a factor of N and gives a qualitatively wrong phase diagram (no demixing)
8. **Active vs passive noise:** Active systems (molecular motors, self-propelled particles, cytoskeletal filaments) violate detailed balance. Effective temperature T_eff from MSD does not equal the bath temperature. Applying equilibrium FDT to active systems gives incorrect susceptibilities and correlation functions

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Soft matter / biophysics projects should populate:

- **Energy Units:** k_BT (thermal energy scale); 1 k_BT = 4.114 pN*nm = 0.593 kcal/mol at T = 300K
- **Length Scales:** sigma (LJ diameter, reduced units), nm (coarse-grained), um (cell biology, colloids); persistence length l_p, Kuhn length b = 2*l_p
- **Time Scales:** tau_LJ = sigma * sqrt(m/epsilon) (reduced), ps-ns (atomistic MD), us-ms (CG), Rouse time tau_R, Zimm time tau_Z, reptation time tau_d
- **Force Units:** pN (single-molecule experiments), k_BT/nm (thermal force scale), kJ/(mol*nm) (GROMACS)
- **Temperature Convention:** T in Kelvin; beta = 1/(k_BT); reduced temperature T* = k_BT/epsilon for LJ systems
- **Concentration Units:** volume fraction phi (dimensionless), overlap concentration c* = N / (4/3 pi R_g^3), number density rho = N_chains / V
- **Solvent Treatment:** Explicit (water model: SPC/E, TIP3P), implicit (Langevin friction gamma, dielectric constant epsilon_r), or DPD
- **Ensemble:** NPT for bulk properties at fixed pressure, NVT for confined systems, grand canonical for adsorption and phase coexistence

---

## Computational Environment

**Molecular dynamics and Monte Carlo:**

- `LAMMPS` — Flexible MD with extensive pair styles; strong for coarse-grained polymers, colloids, and custom potentials
- `HOOMD-blue` — GPU-native MD and MC; excellent for coarse-grained soft matter and active matter simulations
- `ESPResSo` — Soft matter-focused MD: charged polymers, electrokinetics, lattice-Boltzmann hydrodynamics, magnetic particles
- `GROMACS` — High-performance MD; strong for atomistic biomolecular simulations; GPU-accelerated
- `oxDNA` — Coarse-grained nucleic acid simulation; sequence-dependent DNA/RNA thermodynamics and mechanics

**Analysis and computation:**

- `numpy` + `scipy` — Numerical algebra, optimization, FFT, special functions, ODE integration for mean-field equations
- `MDAnalysis` — Trajectory analysis: RDFs, MSD, hydrogen bonds, polymer end-to-end distance, R_g
- `freud` — Computational geometry: order parameters, Voronoi tessellation, clustering, bond-order analysis for colloids
- `matplotlib` — Publication-quality plots for phase diagrams, scaling plots, and structural data

**Free energy and enhanced sampling:**

- `PLUMED` — Metadynamics, umbrella sampling, steered MD (plugin for LAMMPS/GROMACS/OpenMM)
- `alchemlyb` — Free energy analysis from alchemical simulations (BAR, MBAR, TI)

**Symbolic and continuum theory:**

- `sympy` — Symbolic algebra for mean-field equations, Landau expansion, and scaling analysis
- Mathematica — Symbolic solutions of SCF equations, phase diagram computation, special functions

**Setup:**

```bash
pip install numpy scipy matplotlib MDAnalysis freud-analysis sympy
# MD engines installed separately:
# conda install -c conda-forge lammps
# conda install -c conda-forge hoomd
# conda install -c conda-forge espresso
# conda install -c conda-forge gromacs
```

---

## Bibliography Seeds

Every soft matter / biophysics project should cite or consult these references as starting points:

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Doi & Edwards, *The Theory of Polymer Dynamics* | Rouse, Zimm, reptation models; viscoelasticity; concentrated solutions | Polymer dynamics and rheology |
| de Gennes, *Scaling Concepts in Polymer Physics* | Scaling laws, Flory theory, semidilute regime, blob model | Polymer scaling and universality |
| Chaikin & Lubensky, *Principles of Condensed Matter Physics* | Symmetry, order parameters, phase transitions, liquid crystals, membranes | Theoretical framework for soft matter; Landau theory |
| Rubinstein & Colby, *Polymer Physics* | Chain statistics, thermodynamics, dynamics, networks, gels | Quantitative polymer reference; Flory-Huggins derivations |
| Nelson, *Biological Physics* | Entropic forces, random walks, molecular machines, neural physics | Physics-first approach to biophysics |
| Phillips, Rob, et al., *Physical Biology of the Cell* | Biological scales, membrane mechanics, molecular motors, gene regulation | Biophysics problems and order-of-magnitude estimates |
| Safran, *Statistical Thermodynamics of Surfaces, Interfaces, and Membranes* | Membrane elasticity (Helfrich), wetting, self-assembly, microemulsions | Membrane and interface physics |
| Frenkel & Smit, *Understanding Molecular Simulation* | MC and MD algorithms, free energy methods, enhanced sampling | Simulation methodology and algorithm validation |
| Jones, *Soft Condensed Matter* | Polymers, colloids, surfactants, liquid crystals — accessible overview | Broad soft matter context and physical intuition |
| Marchetti et al., *Hydrodynamics of soft active matter* (Rev. Mod. Phys. 2013) | Active matter field theories, self-propelled particles, active gels | Active matter and out-of-equilibrium soft matter |

**For specific systems:** Search Google Scholar for "[system] soft matter" or "[system] coarse-grained" restricted to the last 5 years for current theoretical approaches and simulation methods.

---

## Worked Example: Symmetric Diblock Copolymer Microphase Separation

A complete 3-phase mini-project illustrating the template:

**Phase 1 — Setup:** System: A-B diblock copolymer melt, equal block lengths N_A = N_B = N/2, total degree of polymerization N = 200. Order parameter: local composition difference phi(r) = phi_A(r) - phi_B(r). Key parameter: Flory-Huggins interaction parameter chi. Known result: mean-field order-disorder transition at chi*N = 10.5 for symmetric diblocks (Leibler, 1980). Conventions: lengths in units of R_g = b*sqrt(N/6), energies in units of k_BT, concentrations as volume fractions.

**Phase 2 — Mean-Field Theory:** Landau free energy expanded in powers of the order parameter phi(q) near the ODT. For symmetric diblocks, the structure factor S^{-1}(q) = F(x) / N - 2*chi where x = q^2*R_g^2 and F(x) is the Leibler function from Gaussian chain statistics. Minimum of S^{-1}(q) at q* = 1.95 / R_g gives the lamellar period d = 2*pi/q* = 3.23 * R_g. Spinodal at chi*N = 10.5 from S^{-1}(q*) = 0. Phase diagram: disordered for chi*N < 10.5, lamellar for chi*N > 10.5 (symmetric case). Computed lamellar period d = 3.23 * R_g = 3.23 * b * sqrt(N/6) = 3.23 * b * sqrt(200/6) = 18.6 * b.

**Phase 3 — Fluctuation Corrections and Validation:** Fredrickson-Helfand fluctuation correction shifts the ODT to chi*N = 10.5 + 41.0 * N^{-1/3}. For N = 200: chi*N_ODT = 10.5 + 41.0 * 200^{-1/3} = 10.5 + 7.0 = 17.5. This is a 67% shift from mean-field — fluctuations are large for this chain length. Validated by SCFT + field-theoretic simulation: CL-FTS gives chi*N_ODT = 17.1 for N = 200, consistent with Fredrickson-Helfand. Ginzburg number Gi ~ N^{-1/3} = 0.17 confirms mean-field is only valid far from the transition. Scaling check: lamellar period d ~ N^{0.5} in weak segregation, d ~ N^{2/3} in strong segregation — verified by plotting d vs N across the crossover.
