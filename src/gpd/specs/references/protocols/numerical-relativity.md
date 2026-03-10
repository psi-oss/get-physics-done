---
load_when:
  - "numerical relativity"
  - "binary black hole"
  - "gravitational wave"
  - "BSSN"
  - "3+1 decomposition"
  - "ADM formalism"
  - "neutron star merger"
tier: 3
context_cost: high
---

# Numerical Relativity Protocol

Numerical relativity solves Einstein's field equations on a computer, enabling the study of strong-field gravitational phenomena: binary black hole and neutron star mergers, gravitational wave generation, gravitational collapse, and cosmological spacetimes. The 3+1 decomposition reformulates the Einstein equations as a Cauchy initial value problem, but this introduces gauge freedom, constraint equations, and numerical stability issues that are the primary source of errors.

## Related Protocols

- See `numerical-computation.md` for general numerical stability, convergence testing, and error propagation
- See `symmetry-analysis.md` for identifying symmetries of the spacetime and using them to reduce computational cost
- See `asymptotic-symmetries.md` for Bondi gauge, BMS frame fixing, memory, and null-infinity charges
- See `order-of-limits.md` for continuum limit extrapolation and finite extraction radius corrections

## Overview

The standard approach to numerical relativity:

1. **3+1 decomposition:** Foliate spacetime into spatial hypersurfaces Σ_t. Specify the spatial metric γ_{ij} and extrinsic curvature K_{ij} on each slice.
2. **Constraint equations:** The Hamiltonian constraint H = 0 and momentum constraints M_i = 0 must be satisfied on the initial slice AND preserved by evolution.
3. **Evolution system:** BSSN (Baumgarte-Shapiro-Shibata-Nakamura) or generalized harmonic formulation. The choice of formulation affects stability.
4. **Gauge conditions:** Lapse α and shift β^i are freely specifiable (gauge freedom). Standard choices: 1+log slicing for α, Gamma-driver for β^i.
5. **Gravitational wave extraction:** Compute the Newman-Penrose scalar Ψ₄ or use Cauchy-characteristic extraction (CCE) for gauge-invariant waveforms.

## Step 1: 3+1 Decomposition (ADM Formalism)

The ADM decomposition splits the spacetime metric as:

```
ds² = -α² dt² + γ_{ij}(dx^i + β^i dt)(dx^j + β^j dt)
```

where α is the lapse function, β^i is the shift vector, and γ_{ij} is the spatial metric on the hypersurface Σ_t.

**Checklist:**

1. **Define the extrinsic curvature.** K_{ij} = -(1/2α)(∂_t γ_{ij} - D_i β_j - D_j β_i), where D_i is the covariant derivative compatible with γ_{ij}. The sign convention varies between references (Misner-Thorne-Wheeler vs York). State the convention and be consistent.
2. **Verify the constraint equations on the initial data.** Hamiltonian constraint: R + K² - K_{ij}K^{ij} = 16πρ. Momentum constraint: D_j K^{ij} - D^i K = 8πS^i. These must be satisfied to machine precision on the initial slice.
3. **Use the conformal thin-sandwich or puncture method for initial data.** For binary black holes: Bowen-York puncture data (conformally flat, with analytic extrinsic curvature) is standard. For more physical initial data: solve the extended conformal thin-sandwich equations with an elliptic solver. Verify the ADM mass and angular momentum of the initial data match the intended physical parameters.

## Step 2: BSSN Evolution System

The ADM equations are numerically unstable. The BSSN reformulation introduces conformal variables:

```
φ = (1/12) ln(det(γ_{ij}))    or    χ = exp(-4φ) = (det(γ_{ij}))^{-1/3}
γ̃_{ij} = e^{-4φ} γ_{ij}     (conformal metric, det = 1)
Ã_{ij} = e^{-4φ}(K_{ij} - (1/3)γ_{ij}K)   (conformal traceless extrinsic curvature)
K = γ^{ij} K_{ij}             (trace of extrinsic curvature)
Γ̃^i = γ̃^{jk} Γ̃^i_{jk}      (conformal connection functions)
```

**Checklist:**

1. **Enforce the algebraic constraints at every timestep.** det(γ̃_{ij}) = 1 and γ̃^{ij}Ã_{ij} = 0. These are algebraic consequences of the conformal decomposition but can drift numerically. Enforce them by explicit projection after each substep of the time integrator.
2. **Use the correct form of the BSSN equations.** The BSSN system is NOT just a variable substitution of ADM — it adds the Γ̃^i as independent variables with their own evolution equations, and the Ricci tensor is computed using the conformal connection functions. Using the ADM Ricci tensor instead of the BSSN-decomposed version makes the system weakly hyperbolic and numerically unstable.
3. **Kreiss-Oliger dissipation.** Add numerical dissipation of the form ε(-1)^{n+1} h^{2n} (∂/∂x)^{2n} to the right-hand side of the evolution equations. Standard: n=2 (fourth-order dissipation) with ε ∈ [0.01, 0.1]. Too much dissipation smears out physical features; too little allows high-frequency noise to grow. Verify convergence is unaffected (dissipation should be sub-leading at the order of accuracy of the finite difference scheme).
4. **Choose the finite difference order.** Standard: fourth-order (4th) or eighth-order (8th) finite differences for spatial derivatives. Higher order allows coarser grids but requires wider stencils. At mesh refinement boundaries, the order may drop — verify that convergence is maintained across refinement levels.

## Step 3: Gauge Conditions

The lapse α and shift β^i are pure gauge — they describe how the coordinates evolve but do not affect the physics. However, bad gauge choices cause coordinate singularities, slice stretching, and numerical instability.

**Checklist:**

1. **1+log slicing for the lapse:** ∂_t α - β^i ∂_i α = -2αK. This is singularity-avoiding (α → 0 near the singularity, so the slice never reaches it). Verify that α > 0 everywhere on the computational domain. If α becomes negative, the simulation has a gauge pathology.
2. **Gamma-driver shift condition:** ∂_t β^i = (3/4) B^i, ∂_t B^i = ∂_t Γ̃^i - η B^i. The damping parameter η controls how quickly the shift adjusts. Typical values: η ∈ [1/M, 2/M] where M is the total mass. Too small η: coordinate drift. Too large η: oscillations and instability. For moving punctures: η may need to vary in space (larger near the punctures).
3. **Verify gauge independence of physical observables.** Gravitational waveforms extracted at finite radius, constraint violations, and horizon properties should be independent of the gauge parameters (to within numerical error). Vary η by 50% and verify that the waveform phase changes by less than the estimated numerical error.

## Step 4: Constraint Monitoring

The Hamiltonian and momentum constraints must be preserved by the evolution. Numerical errors cause constraint violations to grow.

**Checklist:**

1. **Monitor constraint violations at every timestep.** Compute the L2 norm of the Hamiltonian constraint violation ||H||₂ and momentum constraint violation ||M_i||₂ over the computational domain (excluding the interior of apparent horizons). These should converge to zero at the expected order as resolution increases.
2. **Verify convergence order.** If using n-th order finite differences, the constraint violations should scale as h^n where h is the grid spacing. Compute the convergence factor Q = ||H||_{h_1}/||H||_{h_2} and verify Q = (h_1/h_2)^n ± 10%. If convergence is lost, investigate: common causes are boundary conditions, mesh refinement interfaces, or singularities.
3. **Constraint-damping terms.** The Z4c formulation adds dynamical constraint-damping terms that drive constraint violations exponentially to zero: ∂_t Z_μ = ... - κ₁ Z_μ. Verify that the damping parameter κ₁ > 0 and that constraint violations decay exponentially at the expected rate.
4. **Constraint violation vs physical error.** Small constraint violations do not necessarily mean small physical errors. The constraint violations measure how well the discrete solution satisfies the continuum equations. Physical errors (e.g., waveform phase error) may converge at a different rate. Monitor both.

## Step 5: Gravitational Wave Extraction

**Checklist:**

1. **Newman-Penrose scalar Ψ₄.** The standard extraction method: compute Ψ₄ = C_{αβγδ} n^α m̄^β n^γ m̄^δ on a coordinate sphere of radius r_ext, where n^α and m^α are the null tetrad vectors. Decompose into spin-weighted spherical harmonics: Ψ₄ = Σ_{ℓm} Ψ₄^{ℓm}(t) Y^{-2}_{ℓm}(θ,φ).
2. **Finite extraction radius correction.** Ψ₄ is extracted at finite radius r_ext, not at future null infinity. The waveform contains near-field contributions that fall off as 1/r^n with n ≥ 2. Correct by: (a) extracting at multiple radii and extrapolating to r → ∞, or (b) using Cauchy-characteristic extraction (CCE) to propagate the waveform to future null infinity.
3. **Time integration for strain.** The gravitational wave strain h = h₊ - ih_× is related to Ψ₄ by h̄̈ = Ψ₄ (two time integrations). The integration introduces two integration constants (corresponding to memory effects and BMS supertranslations). Use the fixed-frequency integration (FFI) method to handle low-frequency noise: h(f) = -Ψ₄(f)/((2πf)² + f₀²) with a suitable cutoff frequency f₀.
4. **Verify the balance laws.** Total radiated energy: E_rad = ∫ |ḣ|² dΩ dt/(16π). Total radiated angular momentum: J_rad from the angular momentum flux. The Bondi mass M_B(t) = M_ADM - E_rad(t) must be non-negative and monotonically decreasing. The final remnant mass and spin must satisfy the Kerr bound: J_f/(M_f²) ≤ 1.

**Common error modes (wave extraction):**

- Extracting at too small r_ext → large near-field contamination
- Wrong null tetrad normalization → wrong Ψ₄ amplitude
- Integration constants in h from Ψ₄ → unphysical drift in strain
- Not decomposing into spherical harmonics → mixing physical modes with coordinate effects
- Missing the gravitational wave memory (DC component of h₊)

## Step 6: Standard Test Problems

Before trusting a numerical relativity code for new physics, verify against standard benchmarks:

| Test | What It Checks | Expected Result |
|---|---|---|
| Robust stability test | Random perturbations of flat spacetime | Perturbations remain bounded for >10⁴ M |
| Gauge wave | Single-frequency gauge perturbation | Amplitude preserved, no growing modes |
| Linear gravitational wave | Teukolsky wave on flat background | Amplitude and phase match analytic solution |
| Single Schwarzschild BH | Stationary black hole in moving puncture gauge | Horizon area constant, constraints decay to truncation error |
| Head-on binary BH merger | Two equal-mass BHs from rest | Radiated energy ~0.055% of total mass; compare with Rezzolla et al. |
| Quasi-circular binary inspiral | Equal-mass non-spinning BBH | Waveform phase agrees with EOB/NR catalog to < 0.1 rad |

## Worked Example: Equal-Mass Non-Spinning Binary Black Hole Merger

**Problem:** Simulate the last ~10 orbits, merger, and ringdown of an equal-mass non-spinning binary black hole system using the BSSN formulation with moving puncture gauge conditions. Extract the gravitational waveform and verify convergence, energy balance, and consistency with the SXS NR catalog. This example targets three common errors: insufficient resolution causing constraint growth, wrong gauge parameters causing coordinate pathologies, and neglecting finite extraction radius corrections.

### Step 1: Initial Data

Use Bowen-York puncture data for two equal-mass non-spinning black holes:
- Total ADM mass: M_ADM = 1 (geometric units, G = c = 1)
- Individual bare masses: m_1 = m_2 = 0.4872 (chosen so M_ADM = 1 after accounting for binding energy)
- Initial separation: d = 11.0 M (for ~10 orbits before merger)
- Momenta: p_y = +/- 0.0953 M (tangential, for quasi-circular orbit)
- p_x = -/+ 0.00050 M (small radial correction for low eccentricity, from iterative eccentricity reduction)
- Spins: S_i = 0

Solve the Hamiltonian constraint (nonlinear elliptic equation) for the conformal factor psi using a multigrid elliptic solver. Verify:
- ||H||_2 < 10^{-10} on the initial slice (to machine precision of the solver)
- M_ADM computed from the 1/r falloff of psi agrees with the target mass to 10^{-6}
- J_ADM = d * p_y / 2 + d * p_y / 2 = 11.0 * 0.0953 = 1.048 M^2

### Step 2: Grid Setup (Adaptive Mesh Refinement)

Use Berger-Oliger AMR with 7 refinement levels centered on each puncture:

| Level | Grid spacing h/M | Domain size | Purpose |
|---|---|---|---|
| 0 (coarsest) | 4.0 | 512 M | Outer boundary, wave extraction |
| 1 | 2.0 | 256 M | Wave propagation region |
| 2 | 1.0 | 128 M | Orbital region |
| 3 | 0.5 | 32 M | Near-zone, both BHs |
| 4 | 0.25 | 8 M per BH | Individual BH regions |
| 5 | 0.125 | 4 M per BH | Near-horizon |
| 6 (finest) | 0.0625 | 2 M per BH | Puncture resolution |

The finest resolution h_6 = M/16 is the baseline. For convergence testing, run at:
- Low: h_6 = M/12 (coarser by factor 4/3)
- Medium: h_6 = M/16 (baseline)
- High: h_6 = M/24 (finer by factor 2/3)

Outer boundary at 512 M: at the speed of light, no spurious reflections return to the extraction sphere (r_ext = 100 M) before t = 2*(512-100) = 824 M. The merger occurs at t ~ 3000 M, so we need absorbing boundary conditions (Sommerfeld) to prevent reflections from arriving during the evolution.

### Step 3: Evolution

Use the chi-variant of BSSN (chi = exp(-4 phi)) which is better behaved at punctures (chi -> 0 at the puncture, avoiding division by zero in phi-variant):
- Time integrator: 4th-order Runge-Kutta (RK4)
- Spatial finite differences: 8th-order centered
- Courant factor: dt = 0.25 * h (on each refinement level)
- Kreiss-Oliger dissipation: epsilon = 0.1, 5th-order (one higher than the convergence order)

Gauge conditions:
- Lapse: 1+log slicing, d_t alpha = -2 alpha K, initial alpha = 1 - 0.5*(m_1/r_1 + m_2/r_2)
- Shift: Gamma-driver, d_t beta^i = (3/4) B^i, d_t B^i = d_t Gamma_tilde^i - eta B^i, with eta = 1/M

**After ~50 M of evolution:** The punctures settle into the "trumpet" solution. Check that alpha > 0 everywhere. If alpha becomes negative, the damping parameter eta is too large or the initial lapse is poorly chosen.

### Step 4: Constraint Monitoring

Monitor ||H||_2 and ||M_i||_2 (excluding the interior of apparent horizons) throughout the evolution:

| Time (M) | ||H||_2 (low res) | ||H||_2 (medium) | ||H||_2 (high) | Convergence factor |
|---|---|---|---|---|
| 0 | 8.3e-11 | 8.3e-11 | 8.3e-11 | -- (initial data) |
| 500 | 2.1e-4 | 3.8e-5 | 8.2e-6 | 4.6 (expect ~5.3 for 8th order, reduced by AMR boundaries) |
| 1000 | 4.5e-4 | 7.8e-5 | 1.5e-5 | 5.2 |
| 2000 | 9.2e-4 | 1.4e-4 | 2.4e-5 | 5.8 |
| 3000 (merger) | 1.8e-3 | 2.5e-4 | 3.8e-5 | 6.6 |
| 3200 (ringdown) | 5.1e-4 | 7.2e-5 | 1.1e-5 | 6.4 |

Constraints grow during inspiral (accumulated truncation error), peak at merger (strongest fields), then decay during ringdown (constraint damping). The convergence factor should be between n and n+1 for nth-order finite differences. If the convergence factor drops below 2, resolution is insufficient.

### Step 5: Gravitational Wave Extraction

Extract Psi_4 on coordinate spheres at r_ext = 60, 80, 100, 120 M. Decompose into spin-weighted spherical harmonics:

```
r * Psi_4^{22}(t_ret) = A_22(t_ret) * exp(-i Phi_22(t_ret))
```

where t_ret = t - r* is the retarded time (r* = r + 2M ln(r/2M - 1) for Schwarzschild background).

The dominant (2,2) mode at r_ext = 100 M:
- Inspiral phase: frequency chirps from omega_22 ~ 0.056/M at t = 500 M to omega_22 ~ 0.2/M at merger
- Peak amplitude at merger: |r Psi_4^{22}|_max ~ 0.10
- Ringdown: quasi-normal mode with omega_QNM = 0.5294/M_f, tau_QNM = 11.55 M_f

**Finite extraction radius correction:** Extrapolate to r_ext -> infinity using data at multiple radii:

```
r * Psi_4^{22}(r_ext) = r * Psi_4^{22}(inf) + C_1/r_ext + C_2/r_ext^2 + ...
```

Fit C_1, C_2 from the four extraction radii. The correction is ~1-3% in amplitude and ~0.01-0.05 rad in phase. Without this extrapolation, the waveform has systematic errors from near-field contamination.

### Step 6: Remnant Properties and Energy Balance

After ringdown (t ~ 3500 M), the remnant is a Kerr black hole:

From apparent horizon diagnostics:
- M_remnant = 0.9515 M (from horizon area via Christodoulou formula)
- a_f = J_f / M_f^2 = 0.6864 (from approximate Killing vector on the horizon)

From gravitational wave flux:
- E_rad = integral |dh/dt|^2 d Omega dt / (16 pi) = 0.0484 M
- J_rad = 0.361 M^2

**Energy balance:**
- M_ADM = M_remnant + E_rad = 0.9515 + 0.0484 = 0.9999 M (should be 1.000)
- Error: 0.1% — consistent with numerical truncation error at medium resolution

**Angular momentum balance:**
- J_ADM = J_remnant + J_rad = 0.6864 * 0.9515^2 + 0.361 = 0.621 + 0.361 = 0.982 M^2
- J_ADM (from initial data) = 1.048 M^2
- Discrepancy: 0.066 M^2 (6.3%). This is larger than the energy error because angular momentum flux is harder to compute accurately (higher multipole moments contribute, and finite extraction radius corrections are larger for J than for E).

**Kerr bound:** a_f = 0.686 < 1. Satisfied. A value > 1 would indicate a fundamental error (super-extremal Kerr is unphysical).

### Verification

1. **Constraint convergence:** The ratio ||H||_{h}/||H||_{h/2} at t = 1000 M is 5.2 for the 8th-order scheme. Expected: (4/3)^8 = 11.0 for 8th order on a uniform grid. The reduced factor (~5) is expected from AMR interfaces where the effective order drops. If this ratio falls below 2.0, the simulation is not in the convergence regime.

2. **Self-convergence of the waveform:** Compute the phase difference between medium and high resolution: delta_phi_{med-high} = 0.06 rad at merger. Between low and medium: delta_phi_{low-med} = 0.25 rad. Richardson extrapolation: convergence order p = log(0.25/0.06) / log(4/3) = 4.9. The extrapolated waveform phase error is delta_phi ~ 0.06 * (2/3)^5 / (1 - (2/3)^5) ~ 0.01 rad. This is well below the 0.1 rad requirement for LIGO data analysis.

3. **Energy balance:** |M_ADM - M_remnant - E_rad| / M_ADM = 0.1%. Must be < 1% for a credible simulation.

4. **Comparison with SXS catalog:** The SXS:BBH:0180 simulation (equal-mass non-spinning, similar initial separation) gives: E_rad/M = 0.0485, a_f = 0.6864, M_f/M = 0.9516. Our results agree to < 0.1%, confirming the simulation is correct.

5. **Gauge independence:** Vary the Gamma-driver damping parameter from eta = 0.5/M to eta = 2.0/M. The waveform phase at merger should change by less than the numerical error (< 0.01 rad). The coordinate location of the punctures will change (gauge-dependent), but Psi_4 at the extraction sphere should not.

6. **Quasi-normal mode frequency:** The ringdown frequency omega_22 = 0.529/M_f and damping time tau_22 = 11.6 M_f should match the Kerr QNM prediction for a = 0.686: omega_22 = 0.5294/M_f, tau_22 = 11.55 M_f. Agreement within 1% confirms the remnant is correctly described as a Kerr black hole.

## Worked Example: Constraint Violation Diagnosis — When Good-Looking Simulations Go Wrong

**Problem:** A binary black hole simulation appears to run successfully (no crashes, waveforms look reasonable) but constraint violations grow unexpectedly at a mesh refinement boundary. Diagnose the source, distinguish numerical from physical effects, and demonstrate systematic resolution convergence testing. This example targets the most common silent failure in numerical relativity: simulations that produce plausible-looking output but have hidden errors from incorrect boundary treatment at mesh refinement interfaces.

### Step 1: Symptom — Anomalous Constraint Growth

An equal-mass non-spinning BBH simulation at medium resolution (h = M/16 on the finest level, 7 AMR levels) shows the following constraint history:

| Time (M) | ||H||_2 (expected) | ||H||_2 (observed) | Ratio |
|-----------|-------------------|-------------------|-------|
| 0 | 8e-11 | 8e-11 | 1.0 |
| 200 | 1e-5 | 1e-5 | 1.0 |
| 500 | 4e-5 | 2e-4 | 5.0 |
| 1000 | 8e-5 | 3e-3 | 37 |
| 1500 | 1e-4 | 2e-2 | 200 |
| 2000 | 1.5e-4 | 8e-2 | 530 |

The constraint violation is growing exponentially rather than linearly. By t = 2000 M, it exceeds the expected value by 500x. Despite this, the simulation has not crashed and the gravitational waveform looks superficially correct.

### Step 2: Localization — Where Are the Constraints Violated?

Output the constraint violation as a function of position at t = 1000 M. The Hamiltonian constraint violation ||H(x)|| peaks at the boundary between refinement level 3 (h = 0.5 M) and level 4 (h = 0.25 M):

```
Max ||H|| at refinement boundary (level 3/4): 0.15
Max ||H|| in the bulk of level 4: 3e-5
Max ||H|| in the bulk of level 3: 1e-4
Max ||H|| at the puncture (level 6): 2e-4
```

The constraint violation at the refinement boundary is 1000x larger than in the bulk. This is a clear signature of an inter-level boundary condition error.

### Step 3: Diagnosis

Common causes of constraint growth at refinement boundaries:

1. **Prolongation order mismatch.** The prolongation operator (interpolation from coarse to fine grid) must be at least as accurate as the evolution scheme. If the evolution uses 8th-order finite differences but the prolongation uses 2nd-order interpolation, the effective accuracy drops to 2nd order at every refinement boundary, introducing large truncation errors that violate the constraints.

2. **Restriction operator asymmetry.** The restriction operator (coarsening from fine to coarse) must be consistent with the prolongation. If restriction uses simple injection (copy the fine-grid value) while prolongation uses polynomial interpolation, a systematic mismatch accumulates at every timestep.

3. **Buffer zone too narrow.** The fine grid must extend beyond the region where it communicates with the coarse grid by enough points to support the stencil width. For 8th-order finite differences, the stencil extends 4 points in each direction. If the buffer zone has only 2 points, the fine grid uses inconsistent data near its boundary.

**In this case:** The prolongation order was set to 3 (cubic interpolation) while the evolution uses 8th-order finite differences. The mismatch introduces a 4th-order error at every refinement boundary at every timestep.

### Step 4: Fix and Verification

Change the prolongation order from 3 to 5 (matching the dissipation order). Rerun:

| Time (M) | ||H||_2 (before fix) | ||H||_2 (after fix) |
|-----------|---------------------|---------------------|
| 500 | 2e-4 | 5e-5 |
| 1000 | 3e-3 | 9e-5 |
| 1500 | 2e-2 | 1.2e-4 |
| 2000 | 8e-2 | 1.6e-4 |

After the fix, constraint violations grow linearly (as expected from accumulated truncation error), not exponentially. The ratio observed/expected is now ~1.1 rather than 530.

### Step 5: Convergence Test

Run at three resolutions to verify the convergence order is restored:

| Resolution | h_finest | ||H||_2 at t=1000M | ratio to next |
|-----------|---------|-------------------|---------------|
| Low | M/12 | 4.8e-4 | -- |
| Medium | M/16 | 9.0e-5 | 5.3 |
| High | M/24 | 8.5e-6 | 10.6 |

Expected convergence factor for 8th-order: (4/3)^8 = 11.0 (low/medium), (3/2)^8 = 25.6 (medium/high). The observed factors (5.3 and 10.6) are lower than the theoretical maximum because AMR boundaries reduce the effective order, but they are consistent with a mix of 8th-order bulk and 5th-order boundary behavior.

**Before the fix (with 3rd-order prolongation):** The convergence factor was 1.2 (low/medium) — nearly no convergence, indicating the error was dominated by the boundary, not the bulk.

### Step 6: Impact on the Waveform

Compare the (2,2) mode gravitational waveform before and after the fix:

| Quantity | Before fix | After fix | Reference (high-res) |
|----------|-----------|-----------|---------------------|
| Phase at merger | 42.3 rad | 45.1 rad | 45.2 rad |
| Peak amplitude | 0.092 | 0.098 | 0.099 |
| E_rad / M | 0.043 | 0.048 | 0.0485 |

The bad simulation had a phase error of 2.9 rad (60% of a gravitational wave cycle) and underestimated the radiated energy by 11%. Despite this, the waveform LOOKED qualitatively correct — it still showed an inspiral chirp, merger, and ringdown. Without the convergence test and constraint monitoring, the error would be invisible.

### Verification

1. **Constraint localization is the first diagnostic.** When constraint violations are anomalously large, always check WHERE they are largest. Bulk violations suggest a formulation or gauge issue. Boundary violations suggest AMR interface errors. Puncture violations are often benign (the puncture is a coordinate singularity). Output a constraint violation map, not just the global L2 norm.

2. **Convergence factor is the definitive test.** A simulation that shows constraint violations scaling as h^n (with n matching the expected order) is in the convergent regime. A simulation with constraint violations that do not decrease with resolution has an error that does not converge away — it will persist at any resolution. Never trust a simulation without a convergence test.

3. **Waveform self-convergence.** Compute Delta_phi_{low-med} and Delta_phi_{med-high}. The ratio should be (h_low/h_med)^n / (h_med/h_high)^n. If the ratio is much larger than expected, the low-resolution simulation is not in the convergent regime.

4. **Energy balance survives boundary errors.** Even with the boundary error, the energy balance (M_ADM = M_remnant + E_rad) was satisfied to 1% — because the error was localized to the refinement boundary and partially cancels in the integrated flux. This makes energy balance a NECESSARY but NOT SUFFICIENT check. A simulation can satisfy energy balance and still have large phase errors.

5. **Do NOT increase resolution as a substitute for fixing bugs.** The exponentially-growing constraint violation from the prolongation mismatch does not converge away with higher resolution — it converges at 3rd order (the prolongation order) rather than 8th order (the bulk order). The only fix is to match the prolongation order to the evolution order.

## Verification Criteria

1. **Constraint convergence.** ||H||₂ and ||M_i||₂ scale as h^n at the order n of the finite difference scheme. Monitor at every timestep. Growth indicates instability.
2. **Self-convergence.** Run at three resolutions h, h/2, h/4. The Richardson extrapolation should give the expected convergence order. Deviations indicate bugs or insufficient resolution.
3. **Energy balance.** M_ADM = M_remnant + E_rad (± numerical error). The remnant mass is computed from the apparent horizon area (Christodoulou formula: M² = M_irr² + J²/(4M_irr²), M_irr = √(A_AH/(16π))).
4. **Angular momentum balance.** J_ADM = J_remnant + J_rad. The remnant spin is computed from the apparent horizon spin diagnostic (approximate Killing vector method or isolated horizon formalism).
5. **Waveform convergence.** The phase and amplitude of h_22 (dominant mode) should converge. Phase error δφ < 0.1 rad for astrophysically relevant comparisons. Amplitude error < 1%.
6. **Gauge invariance.** Physical observables (waveform, remnant mass/spin, radiated energy) should be independent of gauge parameters. Vary the damping parameter η and verify stability.
7. **Kerr bound.** The final remnant must satisfy a_f = J_f/M_f² ≤ 1. Violation indicates a numerical error (physical black holes cannot be super-extremal).

## Worked Example: Gauge Instability from Wrong Gamma-Driver Parameter — The eta Catastrophe

**Problem:** Demonstrate that the Gamma-driver shift condition with an inappropriate damping parameter eta produces a gauge instability that crashes a single Schwarzschild black hole simulation, even though the physical spacetime is completely static. Diagnose the instability by monitoring the shift vector, the lapse function, and the coordinate speed of the puncture. This targets the LLM error class of treating gauge parameters as unimportant tunables when they can cause catastrophic numerical failure, and of confusing gauge instability (coordinate pathology) with physical instability (spacetime pathology).

### Step 1: Setup — Single Schwarzschild Black Hole

A single non-spinning black hole (M = 1) at the origin, evolved with BSSN + moving puncture gauge. This is a STATIONARY spacetime — nothing physical should happen. The only dynamics are gauge evolution (the coordinates adjust from the initial gauge to the "trumpet" steady state).

Grid: 7 refinement levels, finest resolution h = M/16, outer boundary at 256 M.

Gauge conditions:
- Lapse: 1+log slicing, d_t alpha - beta^i d_i alpha = -2 alpha K
- Shift: Gamma-driver, d_t beta^i = (3/4) B^i, d_t B^i = d_t Gamma_tilde^i - eta B^i

The damping parameter eta controls how quickly the shift adjusts to the evolving geometry. Standard value: eta = 1/M to 2/M.

### Step 2: The eta Catastrophe

Run the same simulation with different eta values:

| eta (1/M) | Status at t = 100M | alpha_min | |beta|_max | ||H||_2 |
|-----------|-------------------|-----------|-----------|---------|
| 0.5 | Stable | 0.301 | 0.28 | 3.2e-5 |
| 1.0 | Stable | 0.302 | 0.27 | 3.1e-5 |
| 2.0 | Stable | 0.304 | 0.25 | 3.5e-5 |
| 5.0 | Oscillating | 0.18-0.42 | 0.55 | 8.1e-3 |
| 10.0 | Crashed at t = 45M | 0.0 (lapse collapse) | 2.3 | 0.85 |
| 0.01 | Coordinate drift | 0.301 | 0.005 | 4.2e-5 |

At eta = 5/M: the shift vector oscillates with growing amplitude. The lapse develops oscillations (alpha bouncing between 0.18 and 0.42 instead of settling to the trumpet value 0.30). These are GAUGE oscillations — the spacetime is still Schwarzschild, but the coordinates are oscillating around the trumpet solution.

At eta = 10/M: the oscillations grow exponentially, the lapse collapses to zero (the coordinates "freeze"), and the simulation crashes. The constraint violations are enormous (||H|| ~ 1), not because the physical solution is wrong but because the coordinates have become pathological.

At eta = 0.01/M: the shift barely adjusts (severely underdamped). The puncture drifts slowly through the grid, eventually reaching a refinement boundary where resolution is insufficient. No crash, but the coordinates are poorly adapted and the effective resolution is wasted.

### Step 3: Diagnosis — Gauge vs Physical Instability

**How to distinguish gauge from physical instability:**

1. **Physical invariants.** Compute the Kretschmann scalar K = R_{abcd} R^{abcd} and the apparent horizon area A_AH. For Schwarzschild: K = 48 M^2/r^6 and A_AH = 16 pi M^2 (constant). If these are constant while the simulation crashes, the instability is purely gauge.

| eta (1/M) | K at r = 2M (t = 40M) | A_AH (t = 40M) | Physical? |
|-----------|----------------------|-----------------|-----------|
| 1.0 | 3.00 (exact) | 50.27 (exact) | Stable |
| 5.0 | 2.95 +/- 0.15 | 50.3 +/- 0.2 | OK (gauge oscillation) |
| 10.0 | N/A (crashed) | N/A | Gauge crash |

At eta = 5/M: the physical invariants are correct to within 5%, but the coordinate quantities (alpha, beta) are oscillating wildly. This confirms the instability is gauge-only.

2. **Constraint violations localization.** At eta = 10/M before the crash: ||H|| is largest AT the puncture (where the gauge is most strained), not at the outer boundary or in the wave zone. Physical instabilities (e.g., from wrong boundary conditions) are typically largest at the boundary.

3. **Resolution dependence.** Increase resolution from h = M/16 to h = M/24. The gauge instability at eta = 10/M still crashes (at t = 48M instead of t = 45M — barely later). Physical instabilities improve dramatically with resolution; gauge instabilities do not.

### Step 4: The Correct eta Range

The Gamma-driver equation d_t B^i = d_t Gamma_tilde^i - eta B^i is a damped oscillator for the shift. The natural frequency of the gauge mode is omega_gauge ~ 1/M (set by the light-crossing time of the black hole). Critical damping requires eta ~ 2 omega_gauge ~ 2/M.

```
eta < omega_gauge (underdamped): shift oscillates, slowly settles → too slow
eta ~ 2 omega_gauge (critically damped): shift adjusts in ~2M time → optimal
eta >> omega_gauge (overdamped at first, then UNSTABLE): for eta > eta_crit ~ 4/M,
    the discrete Gamma-driver becomes a negative-diffusion equation → exponential growth
```

The critical eta depends on the grid spacing h. For the finite-difference discretization of the Gamma-driver, the CFL-like stability condition is:

```
eta_crit ~ C / (h * dt) where C ~ 0.5
```

For h = M/16 and dt = M/64 (Courant factor 0.25): eta_crit ~ 0.5 * 64 / 16 = 2/M. The measured instability onset at eta = 5/M is consistent with this estimate.

### Step 5: For Binary Black Holes

For binaries, the situation is more complex because the system has TWO scales: the individual BH size (~M) and the orbital separation (~10M). The optimal eta depends on position:

```
Near the punctures: eta ~ 1/M_individual (fast gauge adjustment for strong-field region)
In the wave zone: eta ~ 1/M_total (slow gauge adjustment, no strong fields)
```

A spatially varying eta (e.g., eta(r) = eta_0 * M / max(r, M)) prevents the oscillation near the punctures while keeping the outer region stable. This is the standard approach in modern NR codes.

### Verification

1. **Trumpet convergence.** For a single BH, the gauge should settle to the trumpet solution within ~50M. Monitor the lapse at the puncture: alpha_punct should converge to alpha_trumpet = 0.301 (for Schwarzschild). If it oscillates indefinitely, eta is wrong.

2. **Coordinate velocity of the puncture.** For a single BH at rest, the puncture should remain at the grid origin. The coordinate velocity |d r_punct / dt| should be < 10^{-6} M per M of coordinate time after the initial gauge adjustment. If the puncture drifts, the shift is not doing its job (eta too small or grid asymmetry).

3. **Gauge independence of waveform.** For a binary, extract Psi_4 at r = 100M. Vary eta from 0.5/M to 2.0/M. The waveform phase should change by less than the numerical error (< 0.01 rad). If it changes by more, the gauge is not fully settled at the extraction radius.

4. **Do NOT set eta = 0.** Without damping, the Gamma-driver has undamped oscillations that grow linearly (secular instability). This is slower than the exponential growth at large eta but still destroys long-duration simulations. Some eta > 0 is always required.

5. **Log the gauge quantities.** Always output alpha_min, |beta|_max, and the puncture location alongside constraint norms. A crash caused by lapse collapse (alpha -> 0) or shift blow-up (|beta| -> inf) is immediately identifiable as a gauge problem. A crash with bounded alpha and beta but growing constraints indicates a formulation or resolution problem.
