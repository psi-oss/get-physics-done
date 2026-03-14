---
template_version: 1
---

# Cosmology Project Template

Default project structure for cosmological theory and computation: background evolution, cosmological perturbations, CMB and large-scale structure observables, and comparison with data.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Model Setup** - Review prior work, define the cosmological model, establish parameter space
- [ ] **Phase 2: Background Evolution** - Solve Friedmann equations, compute distances and expansion history
- [ ] **Phase 3: Perturbation Theory** - Derive and solve perturbation equations, compute transfer functions
- [ ] **Phase 4: Observable Predictions** - Compute CMB power spectra, matter power spectrum, BAO, and other observables
- [ ] **Phase 5: Data Comparison and Parameter Estimation** - Confront predictions with data via MCMC or Fisher matrix analysis
- [ ] **Phase 6: Validation and Cross-Checks** - Verify against Boltzmann codes, check limiting cases, test energy conservation
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Model Setup

**Goal:** Define the cosmological model and establish the parameter space to explore
**Success Criteria:**

1. [Model specified: matter content (CDM, baryons, photons, neutrinos, dark energy), gravity theory (GR or modified)]
2. [Free parameters identified with prior ranges (flat or informative priors)]
3. [Prior constraints compiled: Planck 2018 best-fit, BAO measurements, SNe Ia, local H_0]
4. [Conventions fixed: metric signature (-,+,+,+), Fourier conventions, normalization of power spectrum]

Plans:

- [ ] 01-01: [Survey literature on this model class; compile existing constraints]
- [ ] 01-02: [Define model, parameter space, and conventions]

### Phase 2: Background Evolution

**Goal:** Solve the background cosmology and compute derived quantities
**Success Criteria:**

1. [Friedmann equation solved: H(z) for the model across full redshift range]
2. [Derived quantities computed: comoving distance chi(z), angular diameter distance D_A(z), luminosity distance D_L(z)]
3. [Energy conservation verified: continuity equation satisfied for each component]
4. [Key epochs identified: matter-radiation equality z_eq, recombination z_*, reionization z_re]
5. [Comparison with LCDM: deviations quantified as function of model parameters]

Plans:

- [ ] 02-01: [Solve Friedmann equation; compute H(z), distances, and derived background quantities]
- [ ] 02-02: [Verify energy conservation; compare with LCDM baseline]

### Phase 3: Perturbation Theory

**Goal:** Derive perturbation equations and compute transfer functions for the model
**Success Criteria:**

1. [Gauge choice specified and justified: conformal Newtonian, synchronous, or gauge-invariant]
2. [Perturbation equations derived for each matter component + metric perturbations]
3. [Initial conditions set: adiabatic from inflation, or specified isocurvature modes]
4. [Transfer functions computed: relate primordial spectrum to late-time observables]
5. [Modified gravity effects (if any) correctly implemented in perturbation equations]

Plans:

- [ ] 03-01: [Derive linearized perturbation equations in chosen gauge]
- [ ] 03-02: [Solve Boltzmann hierarchy; compute transfer functions]

### Phase 4: Observable Predictions

**Goal:** Compute observable power spectra and derived quantities
**Success Criteria:**

1. [CMB TT, EE, TE, and BB power spectra computed]
2. [Matter power spectrum P(k) computed at relevant redshifts]
3. [BAO scale r_d and D_V(z)/r_d computed for comparison with surveys]
4. [Lensing convergence power spectrum computed (if relevant)]
5. [Predictions tabulated/plotted as function of model parameters]

Plans:

- [ ] 04-01: [Compute CMB angular power spectra C_l^TT, C_l^EE, C_l^TE]
- [ ] 04-02: [Compute matter power spectrum P(k, z) and BAO-derived quantities]
- [ ] 04-03: [Compute secondary observables: lensing, ISW, SZ (if relevant)]

### Phase 5: Data Comparison and Parameter Estimation

**Goal:** Confront model predictions with observational data and estimate parameters
**Success Criteria:**

1. [Likelihood function defined for each dataset: Planck, BAO, SNe, etc.]
2. [MCMC chains converged: Gelman-Rubin R-1 < 0.01 for all parameters]
3. [Posterior distributions obtained: marginalized constraints on all parameters]
4. [Model comparison: Bayesian evidence or chi^2/dof relative to LCDM]
5. [Tension quantified: if relevant, tension between datasets expressed in sigma]

Plans:

- [ ] 05-01: [Set up likelihood and MCMC sampler; run chains]
- [ ] 05-02: [Analyze chains: posteriors, derived constraints, model comparison]

### Phase 6: Validation and Cross-Checks

**Goal:** Verify results through independent checks and code comparison
**Success Criteria:**

1. [CAMB and CLASS agree on C_l to < 0.1% for standard LCDM parameters]
2. [Energy conservation: |1 - sum(Omega_i)| < 10^{-6} at all redshifts for flat model]
3. [Known limits reproduced: matter-dominated growth D(a) ~ a, radiation-dominated D = const, etc.]
4. [LCDM recovery: setting model-specific parameters to zero recovers LCDM exactly]
5. [Comparison with published constraints for this model (if available)]

Plans:

- [ ] 06-01: [Code comparison: CAMB vs CLASS; verify energy conservation and limiting cases]
- [ ] 06-02: [Compare constraints with published results; check LCDM limit recovery]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript includes: model definition, observable predictions, posterior contour plots, model comparison]
2. [Datasets and methodology clearly described for reproducibility]
3. [Results placed in context of existing constraints and tensions]
```

### Mode-Specific Phase Adjustments

**Explore mode:**
- Phase 2: Compare analytic integration of Friedmann equations with Boltzmann code output (CLASS, CAMB) to build intuition for the model
- Phase 3: Test multiple inflation models or dark energy parametrizations; compare perturbation growth across scenarios
- Phase 4: Compute observables for a broad grid of model parameters before narrowing to the viable region
- Phase 5: Run MCMC with multiple dataset combinations to identify which data drives the constraints

**Exploit mode:**
- Phase 2: Run CLASS/CAMB directly with known best-fit parameters; skip analytic re-derivation
- Phase 3: Use standard adiabatic initial conditions and the default Boltzmann hierarchy
- Phase 4: Compute observables only at the target parameter points needed for the paper
- Phase 5: Run MCMC with the established dataset combination and validated likelihood

**Adaptive:** Explore models and dataset sensitivities in Phases 1-2, then exploit known cosmology and validated pipelines for production in Phases 3+.

---

## Standard Verification Checks for Cosmology

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-gr-cosmology.md` for GR/cosmology-specific verification (Friedmann equation conservation, CMB power spectrum normalization, distance-redshift consistency, perturbation gauge invariance, gravitational wave energy balance).

---

## Typical Approximation Hierarchy

| Level                | Approximation                             | Valid Regime                       | Breaks Down When                                  |
| -------------------- | ----------------------------------------- | ---------------------------------- | ------------------------------------------------- |
| Homogeneous (FLRW)   | Friedmann equations, perfect fluids       | Large scales, background evolution | Perturbations become order 1 (non-linear scales)  |
| Linear perturbations | Boltzmann + Einstein equations            | delta << 1, scales > ~10 Mpc       | Small scales, late times (structure formation)    |
| Standard PT (SPT)    | Perturbative expansion of fluid equations | Mildly non-linear: delta ~ 0.1-1   | Fully non-linear scales, shell crossing           |
| EFT of LSS           | Effective field theory with counterterms  | Extends PT range by ~50% in k      | Deep non-linear regime                            |
| Halo model           | Halos as building blocks of structure     | All scales (approximate)           | Transition regime between 1-halo and 2-halo terms |
| N-body simulation    | Direct gravitational dynamics             | All scales above force softening   | Resolution-limited; baryonic physics sub-grid     |

---

## Common Pitfalls for Cosmology

1. **Confusing comoving and physical distances:** Physical = a(t) \* comoving. Factor-of-(1+z) errors propagate everywhere. Be explicit about which distance measure you mean
2. **H_0 tension:** Planck gives H_0 ~ 67.4; SH0ES gives ~73. Do not assume one is correct without specifying dataset and model assumptions
3. **Wrong power spectrum normalization:** Confusion between sigma_8 and A_s; or computing sigma_8 with wrong transfer function. Always specify which definition and at what redshift
4. **Neglecting neutrino mass:** Even minimal sum(m_nu) ~ 0.06 eV suppresses small-scale power by ~1%. Precision cosmology requires massive neutrinos in the Boltzmann equations
5. **Gauge artifacts:** Compare only gauge-invariant quantities between codes or with data. The density contrast delta depends on the gauge at large scales
6. **N-body initial conditions:** Use 2LPT (second-order Lagrangian PT) for initial conditions; 1LPT (Zel'dovich) introduces transient errors. Start at sufficiently high redshift (z_init ~ 50-100)
7. **Resolution effects in simulations:** Force softening, mass resolution, and box size all affect results. Always quote resolution and run convergence tests
8. **Forgetting to marginalize nuisance parameters:** Fixing nuisance parameters (bias, calibration, foreground) artificially tightens error bars. Always marginalize
9. **Prior volume effects in Bayesian evidence:** The Bayesian evidence penalizes models with large prior volumes. Choice of prior range directly affects evidence ratios. Report prior choices explicitly
10. **Assuming flat universe:** Unless imposed by the model, allow curvature Omega_k as a free parameter and let the data constrain it

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Cosmology projects should populate:

- **Metric Signature:** Usually (-,+,+,+) following Weinberg/Dodelson convention
- **Fourier Convention:** 3D Fourier with (2pi)^3 placement specified
- **Unit System:** Natural units (c = hbar = 1) with Mpc, km/s, and eV for final results
- **Coordinate Convention:** Conformal time vs cosmic time, comoving vs physical distances
- **Gauge Choice:** Conformal Newtonian, synchronous, or gauge-invariant variables

---

## Computational Environment

**Boltzmann solvers:**

- `CLASS` (C + Python wrapper) — Cosmic Linear Anisotropy Solving System: CMB spectra, matter power spectrum, background evolution
- `CAMB` (Fortran + Python) — Code for Anisotropies in the Microwave Background
- `hi_class` — Modified gravity extension of CLASS
- `MontePython` / `cobaya` — MCMC parameter estimation against CMB/LSS data

**N-body and structure formation:**

- `Gadget-4` (C) — Cosmological N-body + SPH simulations
- `nbodykit` (Python) — Large-scale structure analysis: power spectra, correlation functions, halo catalogs
- `Halofit` (built into CLASS/CAMB) — Non-linear matter power spectrum fitting

**Analysis:**

- `numpy`, `scipy` — Numerical integration of Friedmann equations, transfer functions
- `healpy` (Python) — HEALPix spherical harmonics for CMB maps
- `astropy` — Cosmological distance calculations, unit conversions
- `getdist` — MCMC chain analysis and triangle plots

**Setup:**

```bash
pip install numpy scipy matplotlib astropy healpy getdist cobaya classy
```

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Dodelson & Schmidt, *Modern Cosmology* (2nd ed) | Perturbation theory, CMB anisotropies, LSS | Primary reference |
| Weinberg, *Cosmology* | Rigorous derivations, thermal history, nucleosynthesis | Formal treatment |
| Mukhanov, *Physical Foundations of Cosmology* | Inflation, perturbations, quantum origin of structure | Inflation calculations |
| Baumann, *Cosmology* (Cambridge) | Modern pedagogical treatment, EFT of inflation | Lecture-course style |
| Planck 2018 results VI (arXiv: 1807.06209) | Current cosmological parameter constraints | Parameter values |
| Ma & Bertschinger, ApJ 455, 7 (1995) | Boltzmann hierarchy derivation | Perturbation implementation |

---

## Worked Example: CMB Temperature Power Spectrum from Inflation

**Phase 1 — Background:** Solve Friedmann equations for flat LCDM (Omega_m=0.315, Omega_Lambda=0.685, H_0=67.4 km/s/Mpc). Compute: a(t), H(z), conformal time eta(z), comoving distance chi(z). Validate: age of universe t_0=13.8 Gyr, matter-radiation equality z_eq~3400, recombination z_*~1090.

**Phase 2 — Perturbations:** Solve coupled Boltzmann-Einstein equations in conformal Newtonian gauge. Scalar perturbations: Phi, Psi (metric), delta (matter), Theta_l (photon multipoles), N_l (neutrinos). Initial conditions: adiabatic from slow-roll inflation with n_s=0.965, A_s=2.1e-9. Compute transfer functions T(k) at recombination.

**Phase 3 — Validation:** C_l^TT from Theta_l(eta_0, k) via line-of-sight integration. Compare with CLASS output and Planck data. Check: (1) Sachs-Wolfe plateau C_l ~ l(l+1) ~ const at l<30; (2) acoustic peaks at l~220, 540, 810; (3) silk damping exponential suppression at l>1000. Agreement with CLASS to <0.1% validates the implementation.
