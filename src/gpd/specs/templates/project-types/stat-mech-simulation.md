---
template_version: 1
---

# Statistical Mechanics Simulation Project Template

Default project structure for computational statistical mechanics: Monte Carlo simulations, phase transitions, critical phenomena, and classical/quantum lattice models.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Model Definition** - Review prior work, define the model and parameter space, identify target observables
- [ ] **Phase 2: Algorithm Design** - Choose and implement simulation algorithm, verify detailed balance, benchmark against known results
- [ ] **Phase 3: Equilibration and Thermalization** - Establish equilibration protocols, measure autocorrelation times, validate thermalization
- [ ] **Phase 4: Production Measurements** - Run production simulations across parameter space, accumulate statistics for target observables
- [ ] **Phase 5: Analysis and Phase Diagram** - Finite-size scaling, critical exponent extraction, phase diagram construction
- [ ] **Phase 6: Validation and Cross-Checks** - Verify against exact solutions, check thermodynamic consistency, compare with literature
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Model Definition

**Goal:** Define the model, identify target observables, and compile known results for benchmarking
**Success Criteria:**

1. [Model Hamiltonian/energy function written with all parameters defined]
2. [Target observables identified: order parameter, susceptibility, specific heat, correlation function, etc.]
3. [Exact solutions or high-precision prior results compiled for benchmarking]
4. [Universality class hypothesis stated: expected critical exponents and scaling relations]
5. [Parameter space mapped: which regions to simulate, expected phase structure]

Plans:

- [ ] 01-01: [Survey literature; compile exact results and high-precision numerical benchmarks]
- [ ] 01-02: [Define model, target observables, and simulation parameter grid]

### Phase 2: Algorithm Design

**Goal:** Implement simulation algorithm with verified detailed balance and correct sampling
**Success Criteria:**

1. [Algorithm chosen and justified: Metropolis, Wolff cluster, Wang-Landau, parallel tempering, etc.]
2. [Detailed balance verified analytically for the transition probabilities]
3. [Code validated against exact solution for small system or known benchmark]
4. [Random number generator tested: period and quality sufficient for simulation size]
5. [Performance benchmarks: updates per second, scaling with system size]

Plans:

- [ ] 02-01: [Implement simulation algorithm; derive and verify detailed balance]
- [ ] 02-02: [Validate against exact solution: e.g., 1D Ising, 2D Ising at Onsager T_c]

### Phase 3: Equilibration and Thermalization

**Goal:** Establish reliable equilibration protocols and quantify autocorrelation times
**Success Criteria:**

1. [Equilibration time determined for each temperature/parameter point]
2. [Autocorrelation time tau_auto measured via binning or autocorrelation function analysis]
3. [Thermalization verified: independent runs from different initial conditions converge]
4. [Critical slowing down characterized: tau_auto vs system size near T_c]
5. [Measurement frequency set: sample every ~2*tau_auto for independent measurements]

Plans:

- [ ] 03-01: [Measure equilibration time and autocorrelation for representative parameter points]
- [ ] 03-02: [Characterize critical slowing down; adjust algorithm if tau_auto too large]

### Phase 4: Production Measurements

**Goal:** Accumulate high-statistics data for target observables across parameter space
**Success Criteria:**

1. [Simulations run for multiple system sizes: L = [L_min, ..., L_max]]
2. [Temperature/parameter grid covers critical region with sufficient density]
3. [Statistical errors estimated via jackknife or bootstrap with autocorrelation correction]
4. [Energy, order parameter, susceptibility, and Binder cumulant measured at each point]
5. [Raw data stored with full metadata: system size, parameters, statistics, seed]

Plans:

- [ ] 04-01: [Run production simulations for all system sizes at coarse parameter grid]
- [ ] 04-02: [Refine grid near critical point; increase statistics where needed]

### Phase 5: Analysis and Phase Diagram

**Goal:** Extract critical parameters, exponents, and construct the phase diagram
**Success Criteria:**

1. [Critical point located: e.g., Binder cumulant crossing or susceptibility peak scaling]
2. [Critical exponents extracted via finite-size scaling: nu, beta, gamma, eta]
3. [Scaling relations verified: gamma = nu*(2-eta), 2-alpha = d*nu (hyperscaling)]
4. [Data collapse achieved: all system sizes collapse onto universal scaling function]
5. [Phase diagram constructed with transition lines and error bars]

Plans:

- [ ] 05-01: [Locate critical point via Binder cumulant crossing analysis]
- [ ] 05-02: [Extract critical exponents via finite-size scaling; verify scaling relations]
- [ ] 05-03: [Construct phase diagram; perform data collapse]

### Phase 6: Validation and Cross-Checks

**Goal:** Confirm results through independent checks and known constraints
**Success Criteria:**

1. [Exact solution comparison: e.g., 2D Ising T_c, critical exponents match Onsager values]
2. [Thermodynamic consistency: specific heat from energy fluctuations matches numerical derivative of <E>]
3. [Universality class confirmed: exponents match expected universality class within errors]
4. [High-temperature and low-temperature limits reproduced]
5. [Comparison with published simulation results at overlapping parameters]

Plans:

- [ ] 06-01: [Check thermodynamic consistency and known limiting cases]
- [ ] 06-02: [Compare critical exponents with exact/conformal bootstrap values; verify universality]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript includes phase diagram, scaling plots, data collapse, and exponent table]
2. [Error analysis clearly presented: statistical and systematic]
3. [Algorithm details sufficient for reproducibility]
```

### Mode-Specific Phase Adjustments

**Explore mode:**
- Phase 2: Try multiple algorithms (Metropolis, Wolff cluster, Wang-Landau) and compare autocorrelation times, acceptance rates, and scaling with system size
- Phase 3: Test equilibration from both ordered and disordered initial conditions for each algorithm
- Phase 4: Run preliminary scans across a broad parameter range with moderate statistics to map the phase structure before committing to production
- Phase 5: Try multiple analysis approaches (Binder cumulant, histogram reweighting, microcanonical inflection point) to cross-check critical point location

**Exploit mode:**
- Phase 2: Use the validated best algorithm (e.g., Wolff cluster for O(n) models) without comparison runs
- Phase 3: Use known equilibration times from prior work; minimal thermalization study
- Phase 4: Production runs only at pre-identified parameter points with target statistics
- Phase 5: Apply the established finite-size scaling procedure directly

**Adaptive:** Explore algorithms and parameter space in Phases 1-2, then exploit the validated algorithm for production runs in Phases 3+.

---

## Standard Verification Checks for Statistical Mechanics Simulations

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-statmech.md` for stat mech-specific verification (detailed balance, finite-size scaling, thermodynamic consistency).

---

## Typical Approximation Hierarchy

| Level                  | Method                                     | Strengths                                    | Limitations                                              |
| ---------------------- | ------------------------------------------ | -------------------------------------------- | -------------------------------------------------------- |
| Mean-field             | Weiss/Bragg-Williams, Landau theory        | Qualitative phase diagram, correct above d_c | Wrong exponents below d_c, no fluctuations               |
| Series expansions      | High-T, low-T, linked-cluster              | Systematic, controlled                       | Finite convergence radius; Pade needed near T_c          |
| RG (epsilon expansion) | Wilson-Fisher fixed point, d = 4 - epsilon | Universal exponents, scaling functions       | Asymptotic series; limited precision at epsilon = 1 or 2 |
| Conformal bootstrap    | Rigorous bounds on CFT data                | Highest precision exponents in d=3           | Limited to critical point; no off-critical physics       |
| Monte Carlo            | Metropolis, cluster, Wang-Landau           | Exact (up to statistics) for any parameter   | Critical slowing down, sign problem, finite-size effects |

---

## Common Pitfalls for Statistical Mechanics Simulations

1. **Critical slowing down:** Local-update MC near T_c has tau_auto ~ L^z with z ~ 2. Use cluster algorithms (Wolff: z ~ 0.2) or non-local updates for O(n) models
2. **Ignoring autocorrelations:** Reporting statistical errors without autocorrelation correction underestimates uncertainty by factor of sqrt(2\*tau_int). Always measure tau_int via binning analysis
3. **Premature thermalization diagnosis:** System may appear equilibrated but be trapped in a metastable state. Run multiple independent simulations from hot and cold starts; check for hysteresis
4. **Wrong transition order identification:** A steep but continuous transition looks first-order for small systems. Use Binder cumulant (minimum for first-order), energy histogram (double peak), or Lee-Yang zero analysis
5. **Neglecting corrections to scaling:** Naive finite-size scaling fits without L^{-omega} corrections give biased exponents. Include the leading irrelevant exponent in fits
6. **Confusing ensembles for small systems:** Canonical and grand-canonical ensembles give different results for finite systems. Specify and be consistent
7. **Forgetting the 1/N! factor:** Classical partition function for identical particles requires Gibbs 1/N! factor. Without it, entropy is non-extensive
8. **Poor random number generator:** Linear congruential generators fail for large simulations. Use Mersenne Twister (MT19937) or better (PCG, xoshiro256)
9. **Insufficient system sizes for scaling:** Need at least 4-5 system sizes spanning a factor of 4-8 in L to extract reliable critical exponents

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Statistical mechanics projects should populate:

- **Unit System:** Natural units (k_B = 1) or SI with explicit Boltzmann factor
- **Temperature Convention:** beta = 1/(k_B T) or beta = 1/T with k_B = 1
- **Ensemble:** Canonical, grand canonical, or microcanonical with justification
- **Lattice Convention:** Site-centered, lattice spacing a, system sizes L
- **Order Parameter Convention:** Normalization (per-site vs total)
- **Partition Function Normalization:** Include or exclude 1/N! for identical particles
- **Random Number and Sampling:** Generator type and Metropolis acceptance criterion

---

## Computational Environment

**Monte Carlo:**

- `numpy` — Random number generation (PCG64 default), array operations
- `numba` — JIT compilation for tight MC loops (100x speedup over pure Python)
- `emcee` — Ensemble MCMC sampler (for parameter estimation, not lattice MC)
- Custom C/Fortran with Python wrapper for production runs at large L

**Molecular dynamics:**

- `LAMMPS` — Classical MD with many force fields
- `OpenMM` — GPU-accelerated MD
- `ASE` (Python) — Atomic simulation environment

**Analysis:**

- `scipy.optimize` — Curve fitting for critical exponents, finite-size scaling
- `uncertainties` (Python) — Error propagation through derived quantities
- `matplotlib` — Phase diagrams, scaling collapses, autocorrelation plots
- `h5py` — HDF5 storage for large simulation datasets

**Setup:**

```bash
pip install numpy numba scipy matplotlib h5py uncertainties
```

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Landau & Binder, *Monte Carlo Simulations in Statistical Physics* | MC algorithms, finite-size scaling, error analysis | Simulation methodology |
| Newman & Barkema, *Monte Carlo Methods in Statistical Physics* | Cluster algorithms, advanced sampling, convergence | Algorithm selection |
| Kardar, *Statistical Physics of Fields* | Field theory for stat mech, RG, scaling | Theoretical framework |
| Goldenfeld, *Lectures on Phase Transitions and RG* | Critical phenomena, universality, RG flow | Phase transitions |
| Pathria & Beale, *Statistical Mechanics* | Ensemble theory, quantum statistics, phase transitions | Reference textbook |
| Krauth, *Statistical Mechanics: Algorithms and Computations* | Event-chain MC, rejection-free methods, data analysis | Advanced algorithms |

---

## Worked Example: 3D Ising Critical Exponents via Finite-Size Scaling

**Phase 1 — Setup:** 3D cubic lattice Ising model, H = -J sum_{<ij>} sigma_i sigma_j. Goal: determine critical temperature T_c and exponents nu, beta, gamma to 3 significant figures. Conventions: J=1, k_B=1. System sizes L = 8, 12, 16, 24, 32, 48.

**Phase 2 — Simulation:** Wolff cluster algorithm (z ~ 0.33 for 3D Ising, vs z ~ 2 for Metropolis). Measurements: magnetization |m|, susceptibility chi, Binder cumulant U4 = 1 - <m^4>/(3<m^2>^2). Temperature grid: 30 points log-spaced around T_c ~ 4.5115 J/k_B. Production: 10^5 cluster flips per point after 10^4 equilibration. Error: Flyvbjerg-Petersen block averaging.

**Phase 3 — Analysis:** Binder cumulant crossing → T_c = 4.5115(1). FSS collapse: m*L^{beta/nu} vs (T-T_c)*L^{1/nu} → nu = 0.630(2), beta = 0.326(1). chi*L^{-gamma/nu} collapse → gamma = 1.237(2). Compare: conformal bootstrap (nu=0.62999, beta=0.32642, gamma=1.2372). Agreement within MC error bars validates the simulation.
