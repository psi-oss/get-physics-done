---
template_version: 1
---

# General Relativity Project Template

Default project structure for general relativity calculations: perturbation theory, numerical relativity, gravitational waves, black hole physics, and cosmological applications.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Formalism Setup** - Review prior work, fix coordinate conventions, identify the spacetime and perturbation scheme
- [ ] **Phase 2: Linearized Theory and Perturbations** - Set up perturbation equations, choose gauge, derive equations of motion for perturbations
- [ ] **Phase 3: Numerical Methods and Implementation** - Implement numerical evolution (BSSN/GH), set up initial data, choose gauge conditions
- [ ] **Phase 4: Simulation and Evolution** - Run simulations, monitor constraints, extract physical quantities
- [ ] **Phase 5: Observable Extraction** - Extract gravitational waveforms, compute quasi-normal modes, measure masses and spins
- [ ] **Phase 6: Convergence Testing and Validation** - Resolution studies, constraint convergence, comparison with known solutions and perturbation theory
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Formalism Setup

**Goal:** Establish conventions, identify the spacetime background, and catalogue prior results for this system
**Success Criteria:**

1. [Spacetime background and physical scenario clearly defined: binary inspiral, isolated BH, cosmological perturbation, etc.]
2. [Prior calculations and numerical results at relevant approximation level catalogued]
3. [Conventions fixed: metric signature, index placement, sign convention for Riemann tensor, units (G = c = 1 vs SI)]
4. [Symmetries identified: stationarity, axisymmetry, asymptotic flatness, cosmological symmetry]

Plans:

- [ ] 01-01: [Survey literature for existing results on this spacetime/scenario]
- [ ] 01-02: [Fix notation, conventions, and coordinate system; document in NOTATION_GLOSSARY.md]

### Phase 2: Linearized Theory and Perturbations

**Goal:** Derive perturbation equations in chosen gauge and establish the linearized system
**Success Criteria:**

1. [Background spacetime specified: Schwarzschild, Kerr, FLRW, or numerical initial data]
2. [Gauge chosen and justified: Lorenz gauge, Regge-Wheeler, radiation gauge, harmonic gauge]
3. [Perturbation equations derived: Regge-Wheeler/Zerilli (Schwarzschild), Teukolsky (Kerr), or full linearized Einstein equations]
4. [Source terms included if matter is present: stress-energy tensor perturbation specified]
5. [Boundary conditions established: regularity at horizon, outgoing radiation at infinity, initial data on Cauchy surface]

Plans:

- [ ] 02-01: [Derive linearized Einstein equations or master equations in chosen gauge]
- [ ] 02-02: [Specify boundary and initial conditions; verify well-posedness]

### Phase 3: Numerical Methods and Implementation

**Goal:** Set up the computational infrastructure for evolving Einstein's equations or perturbation equations
**Success Criteria:**

1. [Formulation chosen and justified: BSSN, generalized harmonic, Z4c, or perturbation ODE/PDE system]
2. [Gauge conditions specified: 1+log slicing, Gamma-driver shift, or harmonic gauge with damping]
3. [Spatial discretization implemented: finite differences, spectral methods, or discontinuous Galerkin]
4. [Initial data solver implemented: conformal thin-sandwich, Bowen-York, or superposed Kerr-Schild]
5. [Constraint monitoring set up: Hamiltonian and momentum constraints computed at each timestep]

Plans:

- [ ] 03-01: [Implement evolution system and gauge conditions]
- [ ] 03-02: [Implement initial data solver; verify constraints satisfied on initial slice]
- [ ] 03-03: [Set up mesh refinement, boundary conditions, and constraint monitors]

### Phase 4: Simulation and Evolution

**Goal:** Run the numerical evolution and monitor stability and constraint preservation
**Success Criteria:**

1. [Evolution runs stably through the physically relevant timescale (inspiral, merger, ringdown)]
2. [Hamiltonian and momentum constraints remain bounded and converge to zero with resolution]
3. [Gauge dynamics settle: lapse and shift reach quasi-stationary state]
4. [Apparent horizons tracked: masses, spins, and positions extracted throughout evolution]

Plans:

- [ ] 04-01: [Run evolution; monitor constraints and gauge dynamics]
- [ ] 04-02: [Track apparent horizons; measure BH parameters through evolution]
- [ ] 04-03: [Identify and resolve numerical instabilities if present]

### Phase 5: Observable Extraction

**Goal:** Extract physically meaningful observables from the simulation or perturbation calculation
**Success Criteria:**

1. [Gravitational waveform extracted: Psi_4 or h decomposed into (l,m) modes at multiple extraction radii]
2. [Quasi-normal mode frequencies and damping times measured from ringdown signal]
3. [Final state parameters determined: remnant mass, spin, recoil velocity]
4. [Energy and angular momentum radiated computed from waveform flux integrals]

Plans:

- [ ] 05-01: [Extract Psi_4 or metric perturbation h at extraction surfaces; decompose into spherical harmonics]
- [ ] 05-02: [Fit ringdown to QNM overtones; extract frequencies, damping times, and amplitudes]

### Phase 6: Convergence Testing and Validation

**Goal:** Verify numerical accuracy through convergence tests and comparison with known results
**Success Criteria:**

1. [Resolution study performed: at least 3 resolutions showing expected convergence order]
2. [Constraint convergence: Hamiltonian and momentum constraints converge to zero at expected rate]
3. [Extraction radius extrapolation: waveform extrapolated to r -> infinity or computed via CCE]
4. [Comparison with perturbation theory: PN waveform agrees in early inspiral; QNM frequencies match BH perturbation theory]
5. [Energy balance: radiated energy + final BH mass = initial ADM mass to within numerical error]

Plans:

- [ ] 06-01: [Run convergence series; verify convergence order of evolution and waveform]
- [ ] 06-02: [Compare with perturbation theory, PN results, and published NR waveforms]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with waveform plots, convergence figures, and comparison with analytic results]
2. [Numerical accuracy and systematic errors clearly quantified]
3. [Results placed in context of prior NR simulations and analytic approximations]
```

### Mode-Specific Phase Adjustments

**Explore mode:**
- Phase 1: Compare post-Newtonian (PN), numerical relativity (NR), and effective-one-body (EOB) approaches to identify the best method for the target regime
- Phase 2: Test multiple gauge choices (harmonic, Lorenz, Regge-Wheeler) and quantify gauge artifacts in extracted observables
- Phase 3: Try different formulations (BSSN vs generalized harmonic vs Z4c) and gauge conditions to find stable evolution
- Phase 5: Extract waveforms at multiple radii and compare with perturbation theory to assess systematic errors

**Exploit mode:**
- Phase 1: Use the validated waveform model or formulation known to work for this spacetime class
- Phase 2: Apply the established gauge and perturbation scheme directly
- Phase 3: Use proven gauge conditions (1+log slicing, Gamma-driver shift) and validated initial data solver
- Phase 5: Extract at standard radii with established CCE or extrapolation procedure

**Adaptive:** Explore gauge choices and formulations in Phase 1, then exploit the validated setup for production waveforms in Phases 3+.

---

## Standard Verification Checks for GR

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-gr-cosmology.md` for GR-specific verification (constraint propagation, ADM mass conservation, gauge mode contamination, energy conditions, Penrose diagram consistency, gravitational wave energy balance).

---

## Typical Approximation Hierarchy

| Level                       | Approximation           | Expansion Parameter     | Typical Accuracy                                 |
| --------------------------- | ----------------------- | ----------------------- | ------------------------------------------------ |
| Post-Newtonian (PN)         | Weak-field, slow-motion | v/c, GM/(rc^2)          | Excellent for early inspiral (v/c < 0.2)         |
| Effective One Body (EOB)    | Resummed PN + NR tuning | Resums v/c expansion    | ~1% through merger when calibrated to NR         |
| Black hole perturbation     | Small mass ratio        | q = m_1/m_2 << 1       | Exact at leading order for extreme mass ratios   |
| Numerical relativity (NR)   | Full nonlinear solution | Truncation error only   | Limited by resolution; ~0.1% for well-resolved   |
| Post-Minkowskian (PM)       | Weak-field, any speed   | GM/(rc^2), exact in v/c | Useful for scattering and unbound orbits         |

**When to go beyond each approximation:**

- PN breaks down when v/c > 0.3 (last ~10 orbits before merger)
- BH perturbation theory fails when mass ratio q > 0.1
- NR is needed for the merger and ringdown of comparable-mass binaries
- EOB/NR hybrids are used for full inspiral-merger-ringdown waveforms

---

## Common Pitfalls for GR Calculations

1. **Gauge mode contamination:** Coordinate artifacts masquerading as physical gravitational waves. Verify gauge-invariance by extracting observables at infinity or comparing different gauge choices
2. **Constraint violation growth:** Unchecked constraint violations can destabilize the evolution. Use constraint-damping formulations (Z4c, CCZ4) or constraint projection
3. **Singularity handling:** Must use appropriate slicing (1+log) and shift (Gamma-driver) to avoid coordinate singularity at horizons. Puncture or excision techniques required for BH interiors
4. **Incorrect boundary conditions:** Outer boundary too close reflects gravitational waves back into the domain. Use constraint-preserving boundary conditions, Sommerfeld conditions, or absorbing BCs. Domain must be large enough that boundary effects do not reach the extraction region
5. **Spurious radiation from initial data:** Non-equilibrium initial data (e.g., conformally flat Bowen-York for spinning BHs) produces junk radiation. Must evolve long enough for junk radiation to leave the extraction region before measuring physical waveforms
6. **Finite extraction radius errors:** GW extraction at finite r has systematic errors of order M/r. Extrapolate to r -> infinity using multiple extraction radii, or use Cauchy-characteristic extraction (CCE) for gauge-invariant waveforms at null infinity
7. **Wrong sign convention for metric:** Mixing (-,+,+,+) and (+,-,-,-) signature conventions produces wrong signs in the Einstein tensor, Ricci scalar, and stress-energy coupling. Verify sign convention is consistent throughout all equations
8. **Neglecting tidal effects for neutron stars:** Tidal deformability enters the GW phase at 5PN order. For binary neutron star mergers, tidal effects are essential and encode the equation of state
9. **Post-Newtonian truncation errors:** Missing spin-orbit terms (1.5PN), spin-spin terms (2PN), or tail effects (1.5PN) at high PN order causes systematic dephasing. Always include all known terms at the working PN order

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. GR projects should populate:

- **Metric Signature:** (-,+,+,+) or (+,-,-,-) — specify explicitly and consistently
- **Curvature Sign:** Riemann tensor sign convention and Ricci contraction indices
- **Unit System:** Geometric units (G = c = 1) for derivations, SI for final results
- **Coordinate Convention:** Harmonic, Boyer-Lindquist, isotropic, etc.
- **Gauge Choice:** Lorenz, Regge-Wheeler, radiation gauge, harmonic with damping
- **Fourier Convention:** Time-to-frequency convention (physicist f vs angular omega)

---

## Computational Environment

**Symbolic tensor calculus:**

- `xAct` (Mathematica) — Tensor computer algebra: xTensor, xPert (perturbation theory), xCoba (component calculations)
- `cadabra2` (Python) — Tensor algebra with index notation, Riemann tensor manipulation
- `sympy.diffgeom` — Differential geometry module (limited but useful for simple metrics)
- `SageManifolds` (SageMath) — Differential geometry and tensor calculus on manifolds

**Numerical relativity:**

- `Einstein Toolkit` (C/C++) — Cactus framework for numerical GR: ADM evolution, gauge conditions, matter coupling
- `SpECTRE` (C++) — Next-generation NR code: discontinuous Galerkin methods, task-based parallelism
- `GRChombo` (C++) — AMR numerical relativity

**Gravitational waves:**

- `PyCBC` (Python) — GW data analysis, matched filtering, parameter estimation
- `LALSuite` — LIGO Algorithm Library: waveform generation, detector characterization
- `gwpy` (Python) — GW data access and visualization
- `NRPy+` (Python) — Code generation for numerical relativity

**Analysis:**

- `numpy`, `scipy` — Geodesic integration, ODE solvers for perturbation equations
- `matplotlib` — Penrose diagrams, embedding diagrams, waveform plots

**Setup:**

```bash
pip install numpy scipy matplotlib gwpy pycbc
# For xAct: install Mathematica, then xAct from xact.es
```

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Wald, *General Relativity* | Rigorous mathematical formulation, global methods | Formal derivations |
| Misner, Thorne & Wheeler, *Gravitation* | Physical intuition, detailed calculations, exercises | Comprehensive reference |
| Carroll, *Spacetime and Geometry* | Modern pedagogical treatment | Teaching and first reference |
| Poisson & Will, *Gravity* | Post-Newtonian methods, self-force, radiation reaction | Weak-field, slow-motion regime |
| Baumgarte & Shapiro, *Numerical Relativity* | 3+1 decomposition, gauge conditions, numerical methods | Numerical GR |
| Maggiore, *Gravitational Waves* (2 vols) | GW theory, sources, detection | GW calculations |

---

## Worked Example: Schwarzschild Geodesics and Light Bending

**Phase 1 — Setup:** Schwarzschild metric ds^2 = -(1-r_s/r)dt^2 + (1-r_s/r)^{-1}dr^2 + r^2 dOmega^2, with r_s=2GM/c^2. Conventions: G=c=1 (geometric units), metric signature (-,+,+,+). Goal: compute light deflection angle to post-Newtonian order and compare with GR exact result.

**Phase 2 — Geodesic equation:** Use conserved quantities E=-p_t, L=p_phi. Effective potential: (dr/dlambda)^2 = E^2 - V_eff(r) where V_eff = (1-r_s/r)(L^2/r^2 + epsilon) with epsilon=0 (null) or 1 (timelike). For light: orbit equation (du/dphi)^2 = 1/b^2 - u^2 + r_s u^3 where u=1/r, b=L/E. Solve perturbatively: u = sin(phi)/b + (r_s/2b^2)(1 + cos^2(phi)/3) + ...

**Phase 3 — Validation:** Deflection angle Delta_phi = 4GM/(c^2 b) = 2r_s/b for grazing incidence at the Sun: Delta_phi = 1.75 arcsec. Compare: (1) exact numerical integration of orbit equation; (2) Virbhadra-Ellis lens equation for strong lensing. Dimensional check: Delta_phi is dimensionless. Limit: r_s/b → 0 gives Delta_phi → 0 (flat space, no bending). Newtonian limit: Delta_phi_Newton = 2GM/(c^2 b) = half the GR result.
