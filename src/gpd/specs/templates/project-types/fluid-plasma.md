---
template_version: 1
---

# Fluid Dynamics and Plasma Physics Project Template

Default project structure for fluid dynamics and plasma physics projects: magnetohydrodynamics, two-fluid models, instabilities, turbulence, reconnection, transport, and wave phenomena.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Setup** - Review prior work, establish conventions, identify the physical system and regime
- [ ] **Phase 2: Governing Equations** - Write down the fluid/MHD/kinetic equations, identify dimensionless parameters, determine closure scheme
- [ ] **Phase 3: Equilibrium Analysis** - Construct or identify the base equilibrium state, verify it satisfies the governing equations
- [ ] **Phase 4: Stability Analysis** - Linearize about equilibrium, derive dispersion relations, classify unstable modes
- [ ] **Phase 5: Nonlinear Dynamics and Turbulence** - Analyze nonlinear saturation, cascades, structure formation, or transport
- [ ] **Phase 6: Numerical Simulation** - Implement and run simulations, validate against analytic predictions
- [ ] **Phase 7: Validation and Comparison** - Compare with experiments/observations, verify conservation laws, check limiting cases
- [ ] **Phase 8: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Establish the physical system, identify the relevant regime, and fix conventions
**Success Criteria:**

1. [Physical system clearly defined: geometry, boundary conditions, driving mechanism]
2. [Relevant dimensionless parameters identified: Reynolds Re, magnetic Reynolds Rm, Lundquist S, beta, Mach number]
3. [Parameter regime specified: ideal vs resistive, incompressible vs compressible, sub/super-Alfvenic]
4. [Conventions fixed: CGS vs SI for EM quantities, velocity normalization, magnetic field normalization]
5. [Prior work catalogued: known instabilities, turbulence scalings, simulation results in this regime]

Plans:

- [ ] 01-01: [Survey literature for the physical system and regime]
- [ ] 01-02: [Fix conventions and document in NOTATION_GLOSSARY.md]
- [ ] 01-03: [Identify dimensionless parameter space and locate this problem within it]

### Phase 2: Governing Equations

**Goal:** Write down the complete set of equations governing the system with appropriate closure
**Success Criteria:**

1. [Equations written: continuity, momentum (Navier-Stokes or MHD), energy, induction/Maxwell]
2. [Closure scheme specified: ideal MHD, resistive MHD, two-fluid, Hall MHD, or kinetic]
3. [Equation of state chosen: isothermal, adiabatic (specify gamma), or full energy equation]
4. [Source terms and dissipation: viscosity, resistivity, thermal conductivity, radiative cooling]
5. [Boundary conditions specified: periodic, conducting wall, free-surface, inflow/outflow]
6. [Dimensional analysis: identify characteristic scales (Alfven speed, skin depth, resistive time)]

Plans:

- [ ] 02-01: [Write governing equations with all terms]
- [ ] 02-02: [Non-dimensionalize and identify control parameters]
- [ ] 02-03: [Verify equation set is well-posed: count equations vs unknowns, check hyperbolicity]

### Phase 3: Equilibrium Analysis

**Goal:** Construct the base equilibrium state and verify self-consistency
**Success Criteria:**

1. [Equilibrium satisfies all governing equations (not just force balance)]
2. [Grad-Shafranov equation solved (for axisymmetric MHD) or analogous equilibrium condition]
3. [Stability-relevant profiles identified: current density j(r), pressure p(r), flow shear]
4. [Free energy sources catalogued: pressure gradients, current gradients, flow shear, gravitational stratification]

Plans:

- [ ] 03-01: [Construct equilibrium: solve force balance, continuity, induction]
- [ ] 03-02: [Verify equilibrium self-consistency and identify free energy sources]

### Phase 4: Stability Analysis

**Goal:** Determine linear stability, derive dispersion relations, classify unstable modes
**Success Criteria:**

1. [Linearization performed correctly: perturbation equations derived from governing equations]
2. [Dispersion relation obtained: omega(k) or growth rate gamma(k)]
3. [Instabilities classified: ideal (kink, interchange, Rayleigh-Taylor, KH) vs resistive (tearing, resistive interchange)]
4. [Most dangerous mode identified: fastest growth rate, most unstable wavenumber]
5. [Stability boundaries mapped: critical parameters (beta_crit, S_crit, Re_crit)]
6. [Energy principle applied (for MHD): delta_W computed and sign determined]

Plans:

- [ ] 04-01: [Linearize equations about equilibrium, derive perturbation equations]
- [ ] 04-02: [Solve eigenvalue problem or derive dispersion relation]
- [ ] 04-03: [Map stability boundaries in parameter space]

### Phase 5: Nonlinear Dynamics and Turbulence

**Goal:** Analyze nonlinear evolution: saturation, cascades, transport, structure formation
**Success Criteria:**

1. [Nonlinear saturation mechanism identified: quasi-linear flattening, island overlap, secondary instabilities]
2. [Turbulence scaling laws derived or verified: energy spectrum E(k), structure functions]
3. [Transport coefficients estimated: turbulent viscosity, anomalous resistivity, particle diffusion]
4. [Coherent structures identified: magnetic islands, vortices, zonal flows, current sheets]
5. [Conservation laws tracked: energy, helicity (magnetic, cross, kinetic), enstrophy (2D)]

Plans:

- [ ] 05-01: [Analyze nonlinear saturation mechanism]
- [ ] 05-02: [Derive or measure turbulence scaling laws]
- [ ] 05-03: [Compute transport coefficients and identify coherent structures]

### Phase 6: Numerical Simulation

**Goal:** Implement and run simulations that validate and extend analytic results
**Success Criteria:**

1. [Code selection justified: spectral (Dedalus) vs finite-volume (Athena++) vs AMR (FLASH)]
2. [Resolution sufficient: CFL condition satisfied, dissipation scales resolved or modeled]
3. [Convergence tested: results independent of resolution (or known scaling with resolution)]
4. [Conservation laws verified: total energy, magnetic helicity (ideal), mass to machine precision]
5. [Numerical artifacts controlled: numerical diffusion distinguished from physical, no Gibbs ringing at discontinuities]
6. [Initial conditions and perturbations documented: amplitude, spectrum, random seed]

Plans:

- [ ] 06-01: [Set up simulation: code choice, grid, boundary conditions, initial conditions]
- [ ] 06-02: [Run convergence study: vary resolution, verify scaling]
- [ ] 06-03: [Production runs: scan parameter space, collect diagnostics]

### Phase 7: Validation and Comparison

**Goal:** Validate results against independent checks, experiments, and observations
**Success Criteria:**

1. [Linear growth rates from simulation match analytic dispersion relation]
2. [Conservation laws satisfied to expected accuracy (spectral methods: machine precision; finite-volume: truncation error)]
3. [Known limits reproduced: ideal MHD limit (Rm -> infinity), hydrodynamic limit (B -> 0)]
4. [Comparison with experiments or observations where available]
5. [Sensitivity analysis: results robust to parameter variations within physical uncertainty]

Plans:

- [ ] 07-01: [Compare simulation linear phase against analytic growth rates]
- [ ] 07-02: [Check conservation laws and limiting cases]
- [ ] 07-03: [Compare with experimental/observational data]

### Phase 8: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with all sections and figures]
2. [Dimensionless parameters and physical regime clearly stated]
3. [Simulation details reproducible: code, resolution, parameters, initial conditions]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 2 branches:** Compare ideal MHD vs Hall MHD vs two-fluid closures. Run all three, identify which physics matters in this regime.
- **Phase 4 expanded:** Solve for full eigenvalue spectrum, not just most unstable mode. Map stability boundaries in multi-dimensional parameter space.
- **Phase 5 branching:** Try multiple turbulence theories (Goldreich-Sridhar vs Boldyrev vs dynamic alignment) and compare predictions against simulation.
- **Extra phase:** Add "Phase 4.5: Nonlinear Theory Comparison" — compare quasi-linear, weak turbulence, and strong turbulence predictions before committing to simulations.
- **Literature depth:** 20+ papers, including experimental/observational comparisons and competing theoretical interpretations.

### Exploit Mode
- **Phases 1-2 compressed:** If the MHD model is standard, go directly to equilibrium construction with known equations.
- **Phase 4 focused:** Compute only the dominant instability with known analytic method. Skip full eigenvalue spectrum.
- **Phase 5 skip:** If only linear stability matters (e.g., threshold calculation), skip nonlinear analysis entirely.
- **Phase 6 focused:** Use established code with known-good setup. Minimal parameter scan.
- **Skip researcher:** If the instability type and saturation mechanism are well-established.

### Adaptive Mode
- Start in explore for Phases 1-4 (regime identification, instability classification).
- Switch to exploit for Phases 5-7 once the dominant physics is identified and the appropriate model closure is chosen.

---

## Standard Verification Checks for Fluid/Plasma Physics

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-fluid-plasma.md` for fluid/plasma-specific verification (MHD equilibrium, Alfven waves, reconnection, turbulence spectra, conservation laws).

### Domain-Specific Checks

1. **Dimensional consistency:** Every term in every equation has the same dimensions. Non-dimensionalized equations are truly dimensionless
2. **Conservation laws:** Total energy (kinetic + magnetic + thermal + gravitational) conserved in ideal limit. Magnetic helicity conserved in ideal MHD. Mass conserved exactly
3. **Galilean/Lorentz invariance:** Results for bulk flow should be frame-independent (non-relativistic). Alfven speed should transform correctly
4. **Frozen flux theorem:** In ideal MHD (eta=0), magnetic flux through any co-moving surface is constant. Violations indicate numerical resistivity
5. **div(B) = 0:** Solenoidal constraint must be maintained. Check: maximum |div B| * dx / |B| should be near machine precision
6. **Positive definiteness:** Density rho > 0, pressure p > 0, temperature T > 0 everywhere at all times
7. **CFL condition:** Time step satisfies dt < C * dx / max(|v| + c_s + v_A) where C < 1. For explicit schemes, violation causes blow-up
8. **Entropy condition:** In the absence of shocks, entropy should not decrease. At shocks, entropy must increase (second law)
9. **Realizability:** Turbulent transport coefficients must be positive (turbulent viscosity > 0), Reynolds stresses must satisfy Schwarz inequality
10. **Boundary condition consistency:** No unphysical reflections, correct treatment of conducting vs insulating walls, no spurious current sheets at boundaries
11. **Rankine-Hugoniot jump conditions:** At shocks and discontinuities, verify mass flux [rho*v_n], momentum flux [rho*v_n^2 + p + B_t^2/(2*mu_0)], energy flux, and tangential field [B_t*v_n - B_n*v_t] are continuous

---

## Typical Approximation Hierarchy

| Level | Approximation | Key Assumption | Typical Use |
|-------|--------------|----------------|-------------|
| Ideal MHD | Perfect conductivity, single fluid | Rm >> 1, L >> d_i | Solar corona, stellar interiors, galaxy clusters |
| Resistive MHD | Finite resistivity, single fluid | Rm large but reconnection matters | Tearing modes, sawteeth, tokamak disruptions |
| Hall MHD | Two-fluid ion-electron separation | d_i < L < d_e, sub-ion scales matter | Magnetic reconnection, neutron star crusts |
| Two-fluid | Separate ion and electron equations | Full two-fluid effects | Plasma waves, lower-hybrid drift |
| Gyrokinetic | Reduced kinetic, averaged over gyration | omega << Omega_ci, k_perp rho_i ~ 1 | Tokamak turbulence, microstabilities |
| Full Vlasov | No fluid approximation | Kinetic effects essential | Particle acceleration, wave-particle interaction |
| Incompressible | Mach << 1, density constant | Low Mach number | Subsonic turbulence, many lab plasmas |

**When to upgrade the model:**
- Reconnection rate too slow in resistive MHD: add Hall term
- Ion and electron temperatures differ: use two-fluid or kinetic
- Particle distribution non-Maxwellian: use kinetic theory
- Mach number approaches unity: use compressible equations
- Small scales below ion skin depth: Hall or kinetic required

---

## Common Pitfalls for Fluid/Plasma Physics

1. **Numerical vs physical dissipation:** Grid-scale numerical diffusion can dominate physical viscosity/resistivity. Always verify the effective Reynolds number: Re_eff = v*L/nu_numerical. If Re_eff << Re_physical, the simulation is under-resolved
2. **Magnetic reconnection resolution:** Sweet-Parker sheets thin to delta ~ L/sqrt(S). At S ~ 10^6, this requires resolving L/1000. Insufficient resolution gives wrong reconnection rate and topology
3. **CFL violations in explicit codes:** Alfven speed can locally spike (e.g., in low-density regions), causing CFL violation. Use density floors or implicit time-stepping
4. **div(B) errors:** Non-zero div(B) creates unphysical parallel magnetic forces. Use divergence cleaning (Dedner), constrained transport (CT), or vector potential formulation
5. **Boundary-driven instabilities:** Reflecting boundaries can create artificial resonances. Periodic boundaries impose a longest wavelength. Buffer zones may introduce spurious damping
6. **Incorrect adiabatic index:** gamma = 5/3 for monatomic ideal gas, gamma = 4/3 for relativistic gas, gamma = 1 for isothermal. Using wrong gamma changes stability boundaries
7. **Alfven speed singularity:** v_A = B/sqrt(4*pi*rho) diverges as rho -> 0. Low-density regions require density floors or Boris correction
8. **Gauge freedom in vector potential:** If using A instead of B, gauge must be fixed (Coulomb, Weyl, or Lorenz). Different gauges give different numerical stability properties
9. **Magnetic helicity conservation:** In ideal MHD, magnetic helicity is conserved. Resistive dissipation reduces helicity. If helicity grows in your simulation, there is a bug
10. **Non-equilibrium initial conditions:** Starting from a state that does not satisfy force balance creates transient waves that contaminate the physics of interest. Always verify equilibrium numerically before perturbing
11. **Unphysical negative pressures:** Strong rarefaction waves or subtracting magnetic pressure from total pressure in conservative schemes can produce p < 0, leading to NaN temperatures and simulation crashes. Fix: positivity-preserving limiters, dual-energy formulation, or reduced timestep
12. **Mixing CGS and SI electromagnetic units:** Factor of 4*pi and c differences. Magnetic pressure is B^2/(8*pi) in CGS but B^2/(2*mu_0) in SI. Mixing silently produces wrong forces by factors of 4*pi

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Fluid/plasma projects should populate:

- **Unit System:** CGS-Gaussian (traditional plasma physics) or SI. CGS: B in Gauss, magnetic pressure B^2/(8*pi). SI: B in Tesla, magnetic pressure B^2/(2*mu_0). Mixing causes factors-of-c errors
- **Magnetic Field Normalization:** Alfven units (B/sqrt(4*pi*rho) = 1), or physical units. In Alfven units, the induction equation has no 4*pi factors
- **Velocity Normalization:** Alfven speed v_A, sound speed c_s, or thermal speed v_th. Determines what Mach number means
- **Length Scale:** Ion skin depth d_i, ion gyroradius rho_i, system size L, or Debye length lambda_D
- **Time Scale:** Alfven transit time t_A = L/v_A, resistive time t_R = L^2/eta, ion cyclotron period, or collision time
- **Plasma Beta:** beta = 8*pi*p/B^2 (CGS) or beta = 2*mu_0*p/B^2 (SI). High-beta: pressure-dominated. Low-beta: magnetically dominated
- **Equation of State:** Ideal gas p = n*k_B*T with gamma = 5/3 (default) or isothermal (gamma = 1)
- **Resistivity Model:** Spitzer (collisional), anomalous (turbulent), or uniform constant eta

---

## Computational Environment

**Spectral solvers:**

- `Dedalus` (Python) — Spectral PDE solver, excellent for incompressible MHD, channel flows, convection
- `numpy` + `scipy` — Eigenvalue problems for linear stability, spectral analysis of simulation output

**Finite-volume / AMR codes:**

- `Athena++` (C++) — Godunov MHD with constrained transport, AMR, curvilinear grids
- `FLASH` (Fortran/C) — AMR multi-physics: MHD, radiation, nuclear burning, self-gravity
- `Pluto` (C) — Godunov MHD/RMHD with AMR, multiple Riemann solvers

**Kinetic and particle-in-cell:**

- `VPIC` — Fully kinetic PIC, massively parallel
- `Gkeyll` — Continuum gyrokinetic and Vlasov-Maxwell solver
- `GENE` — Gyrokinetic turbulence, flux-tube and global geometry

**Analysis:**

- `yt` (Python) — Analysis and visualization of AMR simulation data
- `numpy` + `matplotlib` — Time series analysis, spectrum computation, field visualization
- `h5py` — HDF5 data I/O (standard format for Athena++, FLASH, Dedalus output)

**Setup:**

```bash
pip install dedalus numpy scipy matplotlib h5py yt
# Athena++: git clone, configure with --prob=your_problem, make
# FLASH: requires registration at flash.rochester.edu
```

---

## Bibliography Seeds

Every fluid/plasma physics project should cite or consult these references as starting points:

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Freidberg, *Ideal MHD* | MHD equilibrium and stability theory, energy principle, tokamak applications | MHD stability, fusion plasma, energy principle calculations |
| Goedbloed & Poedts, *Principles of MHD* + *Advanced MHD* | Comprehensive MHD spectral theory, waves, instabilities | MHD waves, continuous spectra, advanced instabilities |
| Biskamp, *Magnetic Reconnection in Plasmas* | Reconnection theory, Sweet-Parker, Petschek, Hall effects | Magnetic reconnection, current sheet dynamics |
| Landau & Lifshitz, *Fluid Mechanics* | Classical fluid dynamics: viscous flow, turbulence, boundary layers, sound | Hydrodynamic problems, Navier-Stokes, compressible flow |
| Chandrasekhar, *Hydrodynamic and Hydromagnetic Stability* | Classical linear stability: Rayleigh-Taylor, Kelvin-Helmholtz, rotating flows, MHD | Linear stability analysis, instability classification |
| Biskamp, *Magnetohydrodynamic Turbulence* | MHD turbulence spectra, intermittency, weak vs strong turbulence | Turbulence scaling, cascade phenomenology |
| Boyd & Sanderson, *The Physics of Plasmas* | Introductory plasma physics: waves, kinetic theory, transport | First reference for plasma fundamentals |
| Batchelor, *An Introduction to Fluid Dynamics* | Rigorous incompressible fluid dynamics, vortex dynamics, exact solutions | Hydrodynamic foundations, vorticity methods |
| Bellan, *Fundamentals of Plasma Physics* | Lab and space plasma, MHD equilibria, spheromaks | Laboratory plasma experiments |

**For specific problems:** Search NASA ADS for recent reviews in the specific sub-area (e.g., "magnetic reconnection review" or "MHD turbulence review").

---

## Worked Example: Tearing Mode Instability in a Harris Current Sheet

A complete 4-phase mini-project illustrating the template:

**Phase 1 — Setup:** Conventions fixed: CGS-Gaussian, Alfven normalization (rho_0 = 1, B_0 = 1, mu_0 = 1). System: Harris current sheet B_x(y) = B_0 * tanh(y/a) with half-width a. Parameters: Lundquist number S = v_A * a / eta. Regime: S >> 1 (resistive MHD).

**Phase 2 — Equations:** Resistive MHD: rho(dv/dt) = -grad(p) + J x B + rho*nu*nabla^2(v), dB/dt = curl(v x B) + eta*nabla^2(B), with div(B) = 0 and Ohm's law E + v x B = eta*J. Non-dimensionalize with L = a, V = v_A, t = a/v_A. Control parameters: S = v_A*a/eta, Pm = nu/eta.

**Phase 3 — Equilibrium:** Harris sheet: B_x = tanh(y), B_y = 0, v = 0, p(y) = p_0 + (1 - tanh^2(y))/2 (pressure balance). Verify: J_z = -dB_x/dy = -sech^2(y), J x B balances grad(p). Current gradient provides free energy for tearing instability.

**Phase 4 — Stability:** Linearize, Fourier transform in x (exp(ikx + gamma*t)). Inner-outer matching gives the tearing mode dispersion relation: gamma ~ S^{-3/5} * (k*a)^{-2/5} for Delta' > 0. The parameter Delta' = [psi'(0+) - psi'(0-)]/psi(0) computed from outer solution. For Harris sheet: Delta' = 2(1/ka - ka), unstable for ka < 1. Maximum growth rate at ka ~ S^{-1/4}. Verified: growth rate scales as S^{-3/5} (Furth-Killeen-Rosenbluth 1963).
