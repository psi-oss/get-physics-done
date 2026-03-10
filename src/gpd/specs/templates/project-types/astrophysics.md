---
template_version: 1
---

# Astrophysics Project Template

Default project structure for astrophysics calculations: stellar structure and evolution, compact objects (neutron stars, black holes), accretion disks, gravitational waves, galactic dynamics, interstellar medium, supernovae, gamma-ray bursts, high-energy astrophysics, and multi-messenger astronomy.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Setup** - Identify the astrophysical system, fix units and conventions, catalog observational constraints
- [ ] **Phase 2: Physical Model** - Construct the physical model (equations of state, energy transport, nucleosynthesis, gravitational physics)
- [ ] **Phase 3: Analytical Estimates** - Order-of-magnitude estimates, scaling laws, characteristic timescales, Eddington limits, virial theorem
- [ ] **Phase 4: Numerical Calculation** - Implement numerical model (stellar evolution code, N-body, hydro), solve governing equations
- [ ] **Phase 5: Observational Comparison** - Compare predictions with observational data (spectra, light curves, gravitational wave signals)
- [ ] **Phase 6: Parameter Study** - Explore parameter space, identify degeneracies, assess observational distinguishability
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Establish conventions, identify the astrophysical system, and catalog prior models and observational constraints
**Success Criteria:**

1. [System clearly defined: object type, mass/luminosity range, metallicity, evolutionary phase or dynamical state]
2. [Observational constraints cataloged: spectra, photometry, light curves, gravitational wave detections, multi-messenger data]
3. [Conventions fixed: unit system (CGS, solar units), coordinate frame, abundance notation (X, Y, Z), cosmological parameters if extragalactic]
4. [Prior models and calculations cataloged with key results and discrepancies]

Plans:

- [ ] 01-01: [Survey literature for existing models and observational constraints]
- [ ] 01-02: [Fix notation and conventions; document in NOTATION_GLOSSARY.md]

### Phase 2: Physical Model

**Goal:** Construct the governing equations and specify all physics inputs for the astrophysical system
**Success Criteria:**

1. [Governing equations specified: hydrostatic/hydrodynamic equilibrium, energy transport, energy generation, mass conservation, or N-body dynamics]
2. [Boundary and initial conditions defined: surface/photosphere, center regularity, inflow/outflow, or cosmological initial conditions]
3. [Microphysics assembled: equation of state, opacities, nuclear reaction networks, neutrino losses, cooling functions]
4. [Gravitational physics chosen: Newtonian, post-Newtonian, or full GR (TOV, Kerr metric) as appropriate for the system]

Plans:

- [ ] 02-01: [Write governing equations with all source terms and identify dominant physics]
- [ ] 02-02: [Specify boundary conditions, microphysics inputs, and gravitational treatment]

### Phase 3: Analytical Estimates

**Goal:** Derive order-of-magnitude estimates, scaling laws, and characteristic scales to guide and validate the numerical calculation
**Success Criteria:**

1. [Characteristic timescales estimated: dynamical (t_ff), thermal (Kelvin-Helmholtz), nuclear, viscous, cooling, orbital]
2. [Key dimensionless ratios evaluated: GM/Rc^2 (compactness), L/L_Edd, optical depth, Mach number, Reynolds number]
3. [Scaling laws derived or cited: mass-luminosity, mass-radius, Tully-Fisher, Faber-Jackson, or relevant power laws]
4. [Limiting cases checked: Eddington limit, Chandrasekhar mass, Jeans mass, Bondi radius, virial temperature]
5. [Expected observable signatures estimated: luminosity, temperature, frequency, strain amplitude]

Plans:

- [ ] 03-01: [Compute characteristic timescales and dimensionless ratios for the system]
- [ ] 03-02: [Derive or verify scaling laws and check known limiting cases]

### Phase 4: Numerical Calculation

**Goal:** Implement and run the numerical model, solving the governing equations through the target evolutionary or dynamical phase
**Success Criteria:**

1. [Numerical code selected and configured: MESA, Athena++, FLASH, N-body, or custom solver with documented inlist/parameter files]
2. [Model converges with correct boundary conditions and initial state]
3. [Evolution/simulation completed through target phases with key diagnostics tracked]
4. [Numerical convergence verified: resolution study (spatial mesh, timestep, particle number)]
5. [Conservation laws checked: energy, mass, momentum, angular momentum as appropriate]

Plans:

- [ ] 04-01: [Configure numerical code and compute initial model or initial conditions]
- [ ] 04-02: [Run simulation through target phases; track diagnostics]
- [ ] 04-03: [Verify convergence with resolution study and conservation law checks]

### Phase 5: Observational Comparison

**Goal:** Convert model output to observable quantities and compare with astronomical data
**Success Criteria:**

1. [Synthetic observables computed: spectra, photometric magnitudes, light curves, gravitational wave strain, neutrino flux as appropriate]
2. [Observational dataset identified and assembled with calibration and systematic uncertainties]
3. [Model-data comparison performed: chi-squared, likelihood, or Bayesian posterior computed]
4. [Key agreements and discrepancies identified with physical interpretation]

Plans:

- [ ] 05-01: [Generate synthetic observables from model output]
- [ ] 05-02: [Assemble observational data and perform model-data comparison]

### Phase 6: Parameter Study

**Goal:** Explore parameter space, identify degeneracies, and assess which model variations are observationally distinguishable
**Success Criteria:**

1. [Key parameters varied: mass, metallicity, spin, magnetic field, accretion rate, or initial conditions]
2. [Parameter sensitivity mapped: which inputs dominate observable variations]
3. [Degeneracies identified: parameter combinations that produce indistinguishable observables]
4. [Observational distinguishability assessed: what precision is needed to break degeneracies]
5. [Uncertainty budget constructed: dominant sources of theoretical and observational uncertainty]

Plans:

- [ ] 06-01: [Run parameter grid or MCMC over key model parameters]
- [ ] 06-02: [Map parameter sensitivity, identify degeneracies, and assess distinguishability]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with all sections and figures]
2. [All model assumptions and microphysics inputs clearly stated]
3. [Comparison with prior models and observations clearly presented]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 2 splits:** Create parallel plans for different physical assumptions (e.g., different equations of state, with vs without rotation, different mass loss prescriptions, Newtonian vs GR treatment). Compare at phase boundary.
- **Phase 3 branches:** If multiple scaling regimes or limiting approximations exist, branch and evaluate. Test whether the system lies in a clean asymptotic regime or a transition region.
- **Extra phase:** Add "Phase 3.5: Physics Sensitivity" — vary microphysics inputs (nuclear reaction rates, opacities, EOS, cooling functions) within their uncertainties. Identify which inputs dominate the error budget before committing to the numerical calculation.
- **Literature depth:** 15+ papers, including discrepant observations, alternative models, and multi-messenger constraints.

### Exploit Mode
- **Phases 1-2 compressed:** Skip deep literature survey if the system and physics are well-studied. Go directly from known governing equations to model setup in one plan.
- **Phase 3 focused:** Use standard estimates from textbooks. No derivation of new scaling laws.
- **Skip Phase 7:** If results feed into a population synthesis, survey, or larger multi-messenger study, skip paper writing. Output is SUMMARY.md with verified results.
- **Skip researcher:** If the model follows a well-established setup (e.g., solar-metallicity main sequence star with standard physics, standard binary merger waveform).

### Adaptive Mode
- Start in explore for Phases 1-3 (physics selection, analytical estimates, sensitivity analysis).
- Switch to exploit for Phases 4-6 once the physical model is fixed and validated against analytical estimates.

---

## Standard Verification Checks for Astrophysics

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-astrophysics.md` for astrophysics-specific verification (hydrostatic equilibrium, Eddington luminosity, Jeans mass, nuclear burning, accretion physics, gravitational wave sources).

---

## Typical Approximation Hierarchy

| Level | Approximation | When valid | When it breaks |
|-------|--------------|------------|----------------|
| Newtonian gravity | GM/Rc^2 << 1 | Main sequence, giants, galactic dynamics | Neutron stars (GM/Rc^2 ~ 0.2), black holes, GW emission |
| Hydrostatic equilibrium | t_dyn << t_thermal | Quiescent stellar evolution, equilibrium structures | Core collapse, dynamical instabilities, pulsations, mergers |
| Spherical symmetry (1D) | Slow rotation, weak B-field, no companion | Most single-star evolution, isolated compact objects | Rapidly rotating stars, jets, accretion disks, binary interactions |
| Local thermodynamic equilibrium (LTE) | Collision rates >> radiative rates | Deep stellar interiors, cool atmospheres | Hot star atmospheres (NLTE), coronae, accretion disk coronae |
| Mixing length theory (MLT) | Convection as local diffusive process | Bulk of convective envelopes | Convective boundaries, semiconvection, 3D turbulence |
| Optically thick diffusion | tau >> 1, photon mean free path << system size | Stellar interiors, inner accretion disks | Stellar atmospheres, optically thin winds, nebulae |
| Thin disk (Shakura-Sunyaev) | H/R << 1, local thermal equilibrium | Sub-Eddington accretion disks | Super-Eddington accretion, ADAFs, thick tori, jets |
| Newtonian N-body | v << c, weak fields | Galactic dynamics, star clusters, planetary systems | Compact binary inspiral, relativistic jets, cosmological scales |

**When to go beyond standard approximations:**

- Compact objects (neutron stars, white dwarfs near Chandrasekhar limit): use general relativistic structure (TOV equation)
- Gravitational wave sources: full numerical relativity for merger phase; post-Newtonian for inspiral
- Super-Eddington accretion: radiation-hydrodynamic simulations with photon trapping
- Hot star atmospheres, accretion disk coronae: NLTE radiative transfer
- Convective boundaries, supernova engines: 3D hydrodynamic simulations
- Galactic scales with dark matter: include collisionless dynamics and cosmological context

---

## Common Pitfalls for Astrophysics Calculations

1. **Comoving vs physical distances:** In cosmological or expanding contexts, comoving distance = physical distance * (1+z). Confusing the two introduces factors of (1+z) in volumes, densities, and luminosities. For extragalactic sources, always state whether distances are comoving, luminosity, or angular diameter distances
2. **Wrong factors of (1+z):** Observed flux ~ L / (4*pi*d_L^2), where d_L = (1+z)*d_comoving is the luminosity distance. Frequencies redshift as nu_obs = nu_emit / (1+z). Time intervals dilate as dt_obs = dt_emit * (1+z). Surface brightness dims as (1+z)^4. Missing any of these factors corrupts photometry, spectra, and light curve comparisons
3. **Incorrect Eddington luminosity:** L_Edd = 4*pi*G*M*m_p*c / sigma_T assumes electron scattering opacity. For cool stars or metal-rich environments, the effective opacity is higher (Kramers: kappa ~ rho*T^{-3.5}), and the effective Eddington limit is lower. Using the wrong opacity regime gives incorrect stability criteria
4. **Wrong opacity regime:** Electron scattering dominates at T > 10^7 K; Kramers (bound-free, free-free) dominates at intermediate T; molecular and grain opacities dominate at T < 10^4 K. Applying the wrong opacity law to a given temperature regime produces incorrect radiative transfer, luminosities, and convective boundary locations
5. **Gravitational radius vs Schwarzschild radius:** The gravitational radius r_g = GM/c^2 is HALF the Schwarzschild radius r_s = 2GM/c^2. Confusing the two changes the ISCO, photon sphere, and all relativistic corrections by factors of 2. Always state which definition is used and verify factors in key formulae
6. **Incorrect Jeans mass:** M_J depends on temperature, density, and mean molecular weight. For molecular gas (mu ~ 2.33) vs atomic gas (mu ~ 1.27), the Jeans mass differs by a factor of ~3. In numerical simulations, the Jeans length must be resolved by at least 4 cells (Truelove criterion) to avoid artificial fragmentation
7. **Wrong treatment of optical depth:** tau = integral(kappa*rho*ds) along the line of sight, not through the center of the object. For geometrically thick or aspherical systems, the optical depth depends on viewing angle. The photosphere is at tau ~ 2/3, not tau = 1
8. **Ignoring GR corrections for compact objects:** Newtonian gravity underestimates the central pressure of a neutron star by factors of 2-3. The TOV equation, not Newtonian hydrostatic equilibrium, is required for any object with GM/Rc^2 > 0.01. For accretion disks around black holes, the ISCO and radiative efficiency are purely GR effects with no Newtonian analog
9. **Neglecting redshift and cosmological effects for distant sources:** K-corrections, cosmological dimming, and time dilation must be applied when comparing models with observations at z > 0.1. The choice of cosmological parameters (H_0, Omega_m, Omega_Lambda) affects derived luminosities and distances at the few-percent level

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Astrophysics projects should populate:

- **Unit System:** CGS (cm, g, s, erg) is traditional in stellar astrophysics. State explicitly if using SI or geometrized units (G = c = 1)
- **Solar Units:** M_sun = 1.989 x 10^33 g, R_sun = 6.957 x 10^10 cm, L_sun = 3.828 x 10^33 erg/s. Cite IAU 2015 nominal values
- **Abundance Notation:** Mass fractions X (hydrogen), Y (helium), Z (metals). Alternatively [Fe/H] = log(N_Fe/N_H) - log(N_Fe/N_H)_sun
- **Distance Measure:** For extragalactic sources, state assumed cosmology (H_0, Omega_m, Omega_Lambda) and whether distances are luminosity, angular diameter, or comoving
- **Magnitude System:** AB magnitudes (flux density) vs Vega magnitudes (reference star). State which system and provide zero points
- **Gravitational Radius Convention:** r_g = GM/c^2 vs r_s = 2GM/c^2. State which is used in all relativistic expressions
- **Opacity Convention:** Rosseland mean (for diffusion approximation) vs Planck mean (for optically thin). Per gram (kappa) vs per cm (kappa * rho)
- **Nuclear Reaction Rate Convention:** Thermonuclear rate <sigma*v> in cm^3/s or S-factor in MeV*barn. State screening prescription (weak, intermediate, strong)
- **Metric Signature:** (-,+,+,+) or (+,-,-,-) for any GR calculation. This affects all signs in the stress-energy tensor and geodesic equations

---

## Computational Environment

**Stellar evolution:**

- `MESA` (Modules for Experiments in Stellar Astrophysics) — 1D stellar evolution, nucleosynthesis, asteroseismology, binary evolution. The standard tool for stellar structure and evolution
- `MESA SDK` — Compiler and library bundle for building MESA on Linux/macOS

**Hydrodynamics and MHD:**

- `Athena++` — High-performance adaptive mesh refinement (AMR) MHD code. Ideal for accretion disks, ISM turbulence, jets, and magnetized flows
- `FLASH` — Multi-physics AMR code for astrophysical hydrodynamics: supernovae, detonations, stellar convection, cosmological structure formation
- `Pluto` — Godunov-type MHD code for astrophysical fluid dynamics

**Gravitational waves:**

- `LALSuite` — LIGO Algorithm Library: gravitational waveform generation, matched filtering, parameter estimation. Essential for compact binary coalescence analysis
- `PyCBC` — Python toolkit for gravitational wave data analysis built on LALSuite
- `Einstein Toolkit` / `Cactus` — Numerical relativity framework for binary black hole and neutron star merger simulations

**N-body and galactic dynamics:**

- `Gadget-4` / `AREPO` — Cosmological N-body + SPH/moving-mesh simulations
- `GALA` — Python package for galactic dynamics: orbits, potentials, action-angle variables

**Numerical and data analysis (Python):**

- `numpy` + `scipy` — Numerical integration, interpolation, ODE solving, optimization
- `astropy` — Astronomical constants, unit conversions, coordinate transforms, FITS I/O, cosmological calculations
- `emcee` — Affine-invariant MCMC ensemble sampler for parameter estimation
- `matplotlib` — Publication-quality plotting (HR diagrams, evolutionary tracks, spectra, waveforms)

**Radiative transfer and atmospheres:**

- `Cloudy` — Photoionization, nebular emission, non-equilibrium chemistry
- `PHOENIX` — NLTE model atmospheres and synthetic spectra

**LaTeX:**

- `aastex63` — AAS journal class (ApJ, ApJL, ApJS)
- `mnras` — MNRAS journal class
- `revtex4-2` — Physical Review journal class (for GW and high-energy astrophysics papers)

**Setup:**

```bash
pip install numpy scipy astropy emcee matplotlib
# MESA installation: follow https://docs.mesastar.org/
# Athena++: git clone https://github.com/PrincetonUniversity/athena && python configure.py
# LALSuite: conda install -c conda-forge lalsuite pycbc
# Cloudy: download from https://nublado.org/
```

---

## Bibliography Seeds

Every astrophysics project should cite or consult these references as starting points:

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Carroll & Ostlie, *An Introduction to Modern Astrophysics* | Broad coverage of stellar physics, galactic dynamics, cosmology, and observational techniques | Starting reference for any astrophysics project; order-of-magnitude estimates and physical intuition |
| Shapiro & Teukolsky, *Black Holes, White Dwarfs, and Neutron Stars* | Compact object physics: TOV equation, white dwarf structure, neutron star EOS, black hole accretion | Compact object calculations, general relativistic corrections, accretion disk physics |
| Kippenhahn, Weigert & Weiss, *Stellar Structure and Evolution* (2nd ed.) | Standard stellar structure equations, evolutionary phases, nucleosynthesis | Core reference for all stellar evolution calculations |
| Rybicki & Lightman, *Radiative Processes in Astrophysics* | Radiation physics: bremsstrahlung, synchrotron, Compton, radiative transfer | Spectral modeling, opacity calculations, emission mechanisms, high-energy astrophysics |
| Binney & Tremaine, *Galactic Dynamics* (2nd ed.) | Gravitational dynamics: potentials, orbits, distribution functions, relaxation, disk/bar/spiral dynamics | Galactic dynamics, star clusters, dark matter halos, N-body simulations |
| Frank, King & Raine, *Accretion Power in Astrophysics* (3rd ed.) | Accretion disk theory: thin disks, ADAFs, Eddington limit, X-ray binaries, AGN | Accretion onto compact objects, disk structure, jet launching |
| Maggiore, *Gravitational Waves* Vol. 1-2 | GW theory, source modeling, detection, data analysis, cosmological sources | Gravitational wave signal prediction, matched filtering, compact binary analysis |
| Arnett, *Supernovae and Nucleosynthesis* | Explosion mechanisms, nucleosynthetic yields, light curves, remnant formation | Core-collapse and thermonuclear supernovae, chemical evolution |

**For specific objects/processes:** Search NASA ADS for `abs:"[object type]" AND abs:"[process]" year:2020-2026` to find recent models and observations. For gravitational wave events, consult the LIGO-Virgo-KAGRA collaboration papers on GWTC catalogs.

---

## Worked Example: Neutron Star Maximum Mass from TOV Equation

A complete 3-phase mini-project illustrating the template:

**Phase 1 — Setup:** Conventions fixed (CGS units, geometrized units G = c = 1 for TOV integration, gravitational radius r_g = GM/c^2). System: static, non-rotating neutron star. Goal: determine maximum mass for a given equation of state. Prior models cataloged: Oppenheimer-Volkoff (1939) original, modern polytropic and tabulated EOS results. Observational constraint: PSR J0740+6620 at 2.08 M_sun sets a lower bound on maximum mass. Key timescale: dynamical t_dyn ~ 0.1 ms (millisecond), confirming hydrostatic equilibrium is an excellent approximation.

**Phase 2 — Calculation:** TOV equation integrated from center (rho_c) to surface (P = 0) for a range of central densities. EOS: SLy (Skyrme-Lyon) nuclear matter model, tabulated P(rho). For each rho_c, obtain M(rho_c) and R(rho_c). The M(rho_c) curve rises to a maximum M_max ~ 2.05 M_sun at rho_c ~ 10^15 g/cm^3, then decreases (unstable branch). Analytical estimate: for a polytrope P ~ rho^{5/3}, M_max ~ 1.4 M_sun (Chandrasekhar-like); the stiffer nuclear EOS at high density increases this to ~2 M_sun.

**Phase 3 — Validation:**
- Dimensional check: M_max ~ (hbar*c/G)^{3/2} / m_n^2 ~ a few M_sun. Correct order of magnitude.
- Newtonian limit: at low rho_c, TOV reduces to Newtonian hydrostatic equilibrium. Verified: M(rho_c) agrees with Newtonian polytrope for rho_c < 10^{13} g/cm^3.
- Compactness: at M_max, GM/Rc^2 ~ 0.2, confirming GR is essential (Newtonian would give ~30% error in mass).
- Stability: dM/d(rho_c) < 0 beyond the maximum confirms the onset of gravitational instability (correct).
- Observational comparison: M_max = 2.05 M_sun is consistent with PSR J0740+6620 (2.08 +/- 0.07 M_sun), validating the EOS choice. A softer EOS (e.g., M_max < 2.0 M_sun) would be ruled out by this observation.
- Causality check: sound speed c_s = sqrt(dP/d(rho)) < c throughout the star. Verified for SLy EOS.
