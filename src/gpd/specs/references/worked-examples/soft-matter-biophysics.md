# Worked Example: Polymer Brush Height Scaling Under Solvent Quality Variation (SCFT)

This demonstrates a complete mini-project for a soft matter / biophysics calculation: computing the equilibrium brush height h* of end-grafted polymer chains as a function of grafting density and Flory-Huggins parameter using self-consistent field theory. It shows realistic PROJECT.md, ROADMAP.md, PLAN.md, and SUMMARY.md examples that train the roadmapper and planner agents.

---

## 1. PROJECT.md Example

```markdown
# Polymer Brush Height Scaling Under Solvent Quality Variation

## Core Research Question

How does the equilibrium height of a polymer brush scale with grafting density and
solvent quality across the good/theta/poor solvent regimes?

## Physical System

End-grafted polymer chains of N monomers tethered to a flat, impenetrable surface at
grafting density sigma (chains per unit area). The chains are immersed in a solvent
characterized by the Flory-Huggins interaction parameter chi. At low chi (good solvent),
excluded-volume interactions swell the brush; at chi = 0.5 (theta solvent), two-body
interactions vanish and three-body terms dominate; at high chi (poor solvent), the brush
collapses into a dense layer.

## Theoretical Framework

- **Flory-Huggins lattice theory**: free energy of mixing
  f = (phi/N) ln(phi) + (1 - phi) ln(1 - phi) + chi * phi * (1 - phi)
- **Edwards self-consistent field theory (SCFT)**: the polymer density profile phi(z)
  satisfies a modified diffusion equation for the chain propagator q(z, s), coupled
  self-consistently to the mean field w(z)
- **Strong-stretching theory (SST)**: in the limit sigma*N >> 1, the classical path
  approximation gives a parabolic density profile (Milner-Witten-Cates, 1988)

## Key Parameters

| Parameter | Symbol | Range | Physical Meaning |
|-----------|--------|-------|------------------|
| Chain length | N | 100-1000 monomers | Degree of polymerization |
| Grafting density | sigma | 0.01-0.5 chains/a^2 | Surface coverage |
| Flory-Huggins parameter | chi | 0-2 | Solvent quality (0 = athermal good, 0.5 = theta, >0.5 = poor) |
| Monomer size | a | 0.5 nm (Kuhn length) | Statistical segment length |
| Temperature | T | 300 K (fixed) | Thermal energy scale k_B T |

## Conventions

| Convention | Choice | Rationale |
|------------|--------|-----------|
| Length unit | a (Kuhn length, 0.5 nm) | Natural polymer scale |
| Energy unit | k_B T | Thermal energy at T = 300 K |
| Density normalization | phi in [0, 1] | Volume fraction of polymer |
| Spatial coordinate | z >= 0 (normal to surface) | Surface at z = 0 |
| Contour variable | s in [0, 1] | Normalized chain contour (0 = grafted end, 1 = free end) |
| Grid | uniform in z, uniform in s | Crank-Nicolson discretization |
| Fourier convention | N/A (real-space SCFT) | No momentum-space quantities |

## Computational Environment

- Backend: numpy + scipy (sparse linear algebra for diffusion equation)
- Symbolic: sympy (analytical limits, scaling law verification)
- Precision: double (float64)
- Convergence tolerance: 1e-8 (relative change in free energy per iteration)

## Target Journal

Macromolecules or Soft Matter

## Profile

numerical

## Bibliography Seeds

- Alexander, S. J. Phys. (Paris) 38, 983 (1977) — scaling theory of polymer brushes
- de Gennes, P.-G. Macromolecules 13, 1069 (1980) — blob model for grafted chains
- Milner, S. T.; Witten, T. A.; Cates, M. E. Macromolecules 21, 2610 (1988) — SST parabolic profile
- Zhulina, E. B.; Borisov, O. V.; Pryamitsyn, V. A. J. Colloid Interface Sci. 137, 495 (1990) — poor solvent collapse
- Matsen, M. W. J. Chem. Phys. 117, 2351 (2002) — numerical SCFT for polymer brushes
- Netz, R. R.; Schick, M. Macromolecules 31, 5105 (1998) — SCFT phase diagrams
```

---

## 2. ROADMAP.md Example

```markdown
---
project: polymer-brush-scft
total_phases: 5
milestones:
  - version: "v1.0"
    name: "SCFT brush height scaling"
    phases: [1, 2, 3, 4, 5]
    target: "Complete h*(sigma, chi, N) phase diagram with scaling exponents"
status: in_progress
current_phase: 3
---

# Roadmap: Polymer Brush Height Scaling via SCFT

## Phase 1: Literature Review and Scaling Theory
**Depth:** standard (3-4 plans)
**Profile adjustment:** numerical — add convergence testing for any analytical estimates

### Goals
- Reproduce Alexander-de Gennes scaling: h* ~ N * sigma^{1/3} in good solvent
- Derive Milner-Witten-Cates parabolic profile from SST
- Catalog known scaling exponents across solvent regimes
- Identify discrepancies between scaling theory and numerical SCFT in the literature

### Key Deliverables
- Literature summary with scaling predictions (Table)
- Analytical expression for h*(sigma, N) in each regime
- List of open questions (crossover behavior, finite-N corrections)

### Truths (to verify)
- "In good solvent (chi < 0.5), h* ~ N * sigma^{1/3} * a (Alexander-de Gennes)"
- "In theta solvent (chi = 0.5), h* ~ N * sigma^{1/2} * a (three-body scaling)"
- "SST density profile is parabolic: phi(z) = phi_0 * (1 - (z/h*)^2) for z < h*"

### Dependencies
- None (first phase)

---

## Phase 2: SCFT Equations and Discretization
**Depth:** comprehensive (5-7 plans)
**Profile adjustment:** numerical — convergence testing for discretization scheme

### Goals
- Derive the self-consistent equations: modified diffusion equation for q(z,s),
  self-consistency condition w(z) = chi * (1 - 2*phi(z)) + incompressibility
- Discretize using Crank-Nicolson in s and finite differences in z
- Implement the SCFT iteration loop with Anderson mixing for convergence acceleration
- Validate against known analytical limits (weak-field, strong-stretching)

### Key Deliverables
- Derivation of SCFT equations from the Edwards Hamiltonian
- Discretization scheme with truncation error analysis (O(ds^2 + dz^2))
- Working SCFT solver code with convergence diagnostics

### Truths (to verify)
- "The chain propagator q(z, s) satisfies dq/ds = (a^2 N / 6) d^2q/dz^2 - w(z) q(z, s)"
- "Density profile: phi(z) = (sigma / Q) integral_0^1 ds q(z, s) q^dagger(z, 1-s)"
- "Partition function Q = integral dz q(z, s=1)"
- "Free energy F/A = -sigma ln Q + integral dz [chi phi(1-phi) - w phi]"

### Dependencies
- Phase 1 provides scaling predictions for validation targets

---

## Phase 3: Numerical Solution and Convergence Study
**Depth:** comprehensive (5-8 plans)
**Profile adjustment:** numerical — convergence testing task for EVERY numerical result

### Goals
- Solve SCFT for a reference case: N=200, sigma=0.1, chi=0 (athermal good solvent)
- Convergence study in grid resolution: Nz = 64, 128, 256, 512, 1024
- Convergence study in contour resolution: Ns = 50, 100, 200, 400
- Richardson extrapolation for grid-converged h*
- Parameter sweep over sigma at fixed chi and N

### Key Deliverables
- Converged density profiles phi(z) for reference case
- Convergence plots (h* vs 1/Nz^2, h* vs 1/Ns^2)
- Brush height h*(sigma) at chi=0 for 10 grafting densities

### Truths (to verify)
- "SCFT density profile phi(z) approaches parabola in strong-stretching limit (large sigma*N)"
- "Brush height scales as h* ~ N * sigma^{1/3} in good solvent (chi = 0)"
- "Numerical grid convergence at dz = a/10 gives < 0.1% error in h* (Richardson extrapolation)"
- "Free energy is stationary at the self-consistent solution: dF/dphi = 0"

### Dependencies
- Phase 2 provides working SCFT solver
- Phase 1 provides analytical predictions for comparison

---

## Phase 4: Scaling Analysis Across Solvent Regimes
**Depth:** comprehensive (5-8 plans)
**Profile adjustment:** numerical — convergence testing + error budget for exponent fits

### Goals
- Full parameter sweep: sigma in {0.01, 0.02, 0.05, 0.1, 0.2, 0.5} x chi in {0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0}
- Extract h* from each converged profile (first moment or half-maximum definition)
- Fit scaling exponents: h* ~ N^alpha * sigma^beta for each chi regime
- Map the good/theta/poor solvent crossover
- Identify collapsed brush regime and coexistence (vertical phase separation)

### Key Deliverables
- h*(sigma, chi) phase diagram (2D color map)
- Scaling exponents alpha(chi) and beta(chi) with confidence intervals
- Density profiles phi(z) gallery across regimes
- Comparison table: SCFT exponents vs analytical predictions

### Truths (to verify)
- "Good solvent (chi=0): h* = C_good * N * sigma^{1/3} * a with C_good ~ 1.0"
- "Theta solvent (chi=0.5): h* ~ N * sigma^{1/2} * a"
- "Poor solvent (chi=1.5): brush collapses to h* ~ N * sigma * a (dense layer)"
- "Crossover from good to theta occurs at sigma ~ |1 - 2*chi|^{3/2} / N (thermal blob argument)"

### Dependencies
- Phase 3 provides validated SCFT solver with known convergence properties
- Phase 1 provides scaling predictions for all three regimes

---

## Phase 5: Paper Writing
**Depth:** standard (3-4 plans)
**Profile adjustment:** paper-writing — notation consistency checks, equation-derivation cross-references

### Goals
- Write introduction: context, motivation, what is new (systematic SCFT across all regimes)
- Present methods: SCFT formulation, discretization, convergence validation
- Present results: phase diagram, scaling exponents, density profiles
- Discussion: comparison with Alexander-de Gennes, MWC, Zhulina et al.
- Conclusions: unified SCFT picture of brush height scaling

### Key Deliverables
- LaTeX manuscript (Macromolecules format)
- Figures: density profiles, h*(sigma) log-log plots, phase diagram, convergence plots
- Supplementary: convergence data tables, code availability statement

### Dependencies
- Phase 4 provides all numerical results and scaling analysis
- Phase 1 provides literature context and comparison targets
```

---

## 3. PLAN.md Example (Phase 3: Numerical SCFT)

```markdown
---
phase: "03"
plan: "01"
title: "SCFT Reference Solution and Grid Convergence"
depth: comprehensive
profile: numerical
estimated_plans_in_phase: 6
conventions:
  units: "k_B T energy, a length"
  coordinates: "z >= 0 (normal to surface)"
  density: "phi(z) in [0, 1] volume fraction"
  contour: "s in [0, 1] normalized (0 = grafted end)"
  grid: "uniform spacing dz = L_z / N_z, ds = 1 / N_s"
truths:
  - claim: "SCFT density profile phi(z) is parabolic in strong-stretching limit"
    test: "Fit phi(z) to phi_0 * (1 - (z/h*)^2) for sigma*N = 100; residual < 1%"
    reference: "Milner, Witten, Cates, Macromolecules 21, 2610 (1988)"
  - claim: "Brush height scales as h* ~ N * sigma^{1/3} in good solvent"
    test: "Log-log fit of h* vs sigma at chi=0, N=200; slope = 0.333 +/- 0.01"
    reference: "Alexander, J. Phys. (Paris) 38, 983 (1977)"
  - claim: "Numerical grid convergence at dz = a/10 (Richardson extrapolation)"
    test: "h*(Nz=1024) - h*(Nz=512) < 0.1% of h*(Nz=1024)"
    reference: "Standard numerical analysis (Richardson, 1911)"
---

# Phase 03 Plan 01: SCFT Reference Solution and Grid Convergence

## Overview

Solve the SCFT equations for a reference parameter set (N=200, sigma=0.1, chi=0) and
establish grid convergence. This is the numerical foundation for all subsequent parameter
sweeps.

## Tasks

### Task 1: Implement SCFT iteration loop (60 min)

Implement the self-consistent iteration:

1. Initialize w(z) = 0 (free field)
2. Solve modified diffusion equation forward: dq/ds = (a^2 N / 6) d^2q/dz^2 - w q
   with q(z, s=0) = delta(z) (grafted end at surface)
   Boundary conditions: q(0, s) = 0 (impenetrable wall), q(L_z, s) = 0 (box)
3. Solve complementary propagator backward: dq^dag/ds = (a^2 N / 6) d^2q^dag/dz^2 - w q^dag
   with q^dag(z, s=0) = 1 (free end, uniform)
4. Compute density: phi(z) = (sigma / Q) * integral_0^1 ds q(z,s) * q^dag(z, 1-s)
   where Q = integral dz q(z, s=1)
5. Update field: w_new(z) = chi * (1 - 2*phi(z)) + eta(z) (incompressibility via eta)
6. Mix: w(z) <- (1-lambda) * w_old + lambda * w_new with lambda = 0.1 (simple mixing)
   or Anderson mixing for faster convergence
7. Check convergence: |F_new - F_old| / |F_old| < 1e-8

Discretization: Crank-Nicolson in s (implicit, O(ds^2)), second-order finite differences
in z (O(dz^2)). The diffusion equation becomes a tridiagonal system at each s step,
solved by Thomas algorithm in O(Nz) operations.

**Verification:**
- Dimensional analysis: [dq/ds] = [length^{-2}] * [q], w is dimensionless in k_B T units
- At chi=0 with w=0: q(z,s) is the free-chain propagator (Gaussian)
- Conservation: integral phi(z) dz = sigma * N * a (total polymer in brush)

### Task 2: Reference case solution (30 min)

Solve for N=200, sigma=0.1, chi=0 with Nz=256, Ns=200, L_z = 5*N*sigma^{1/3}*a = 5*200*0.1^{1/3}*a ~ 464 a.

Expected results:
- Brush height h* ~ N * sigma^{1/3} * a = 200 * 0.464 * a = 92.8 a (order of magnitude)
- Profile: approximately parabolic phi(z) ~ phi_0 * (1 - (z/h*)^2)
- Peak density phi_0 ~ 3*sigma*N*a / (2*h*) ~ 3*0.1*200 / (2*92.8) ~ 0.32

**Verification:**
- Mass conservation: integral phi(z) dz = sigma * N * a = 0.1 * 200 = 20.0 a
- Free energy is lower than initial (w=0) state
- Profile is non-negative everywhere and monotonically decreasing
- h* is within factor of 2 of Alexander-de Gennes prediction

### Task 3: Grid convergence study (45 min)

Solve the same reference case at 5 grid resolutions:

| Nz | dz/a | Ns | ds | Expected convergence order |
|----|------|----|----|---------------------------|
| 64 | 7.25 | 50 | 0.02 | O(dz^2 + ds^2) |
| 128 | 3.63 | 100 | 0.01 | |
| 256 | 1.81 | 200 | 0.005 | |
| 512 | 0.91 | 400 | 0.0025 | |
| 1024 | 0.45 | 800 | 0.00125 | |

For each resolution, record: h* (half-maximum), phi_0 (peak density), F/A (free energy
per unit area), and number of iterations to converge.

**Convergence analysis:**
- Plot h* vs 1/Nz^2: should be linear (second-order convergence)
- Richardson extrapolation: h*_exact = h*(Nz) + C / Nz^2
  Using Nz=512 and 1024: h*_exact = (4 * h*(1024) - h*(512)) / 3
- Convergence criterion: |h*(1024) - h*(512)| / |h*(1024)| < 0.001

**Error budget:**
- Spatial discretization error: O(dz^2) ~ O(a^2 / Nz^2)
- Contour discretization error: O(ds^2) ~ O(1 / Ns^2)
- Self-consistency iteration error: < 1e-8 (convergence tolerance)
- Total error dominated by spatial discretization at Nz < 256

### Task 4: Validate against strong-stretching analytical limit (30 min)

In the strong-stretching limit (sigma*N >> 1), the MWC result gives:

phi(z) = phi_0 * (1 - (z/h*)^2)   for 0 < z < h*

with:
- h* = (12 / pi^2)^{1/3} * N * (v * sigma)^{1/3} * a
  where v = 1 - 2*chi is the excluded volume parameter (v = 1 for chi = 0)
- phi_0 = 3 * sigma * N * a / (2 * h*)

For the reference case (N=200, sigma=0.1, chi=0):
- v = 1
- h* = (12/pi^2)^{1/3} * 200 * 0.1^{1/3} * a = 1.063 * 200 * 0.4642 * a = 98.7 a
- phi_0 = 3 * 0.1 * 200 / (2 * 98.7) = 0.304

Compare SCFT result to SST prediction. For sigma*N = 20, deviations of 5-10% are
expected due to finite-stretching corrections. The SCFT profile should be slightly
broader than the parabola near the brush edge (tail region from fluctuations).

**Verification:**
- Fit SCFT phi(z) to A * (1 - (z/B)^2) for z < 0.8*h*; residual < 5%
- h*(SCFT) within 10% of h*(SST) for sigma*N = 20
- Discrepancy decreases as sigma*N increases (test at sigma=0.5, N=200: sigma*N=100)

## Plan Dependencies

- **Requires from Phase 2:** Working SCFT solver (diffusion equation discretization,
  field update, convergence check)
- **Provides to Phase 3 Plan 02:** Validated grid resolution (Nz=512 or 256 depending
  on convergence results), validated iteration parameters (mixing parameter, max iterations)
- **Provides to Phase 4:** Confidence that h* values are converged to < 0.1%

## Computational Cost

| Task | Grid points | Iterations (est.) | Time per iteration | Total |
|------|------------|--------------------|--------------------|-------|
| Reference case | 256 * 200 | 500 | ~5 ms | ~3 s |
| Convergence (5 grids) | 64-1024 * 50-800 | 500 each | 0.5-50 ms | ~2 min |
| SST validation (2 cases) | 256 * 200 | 500 each | ~5 ms | ~5 s |
| **Total** | | | | **< 5 min CPU** |
```

---

## 4. SUMMARY.md Example (Phase 3, Plan 01 completed)

```markdown
---
phase: "03"
plan: "01"
physics-area: polymer physics, soft matter
tags: [SCFT, polymer-brush, convergence, grid-resolution, scaling]
requires:
  - "02-03: SCFT solver implementation with Crank-Nicolson discretization"
provides:
  - "Converged brush height h* = 95.2a for N=200, sigma=0.1, chi=0"
  - "Grid convergence: Nz=512 sufficient (0.03% error vs Richardson extrapolation)"
  - "Validated SCFT profile matches SST parabola within 4.2% for sigma*N = 20"
affects:
  - "03-02: Parameter sweep can use Nz=512, Ns=200 as production resolution"
  - "04-01: Scaling analysis inherits h* extraction method (half-maximum definition)"
verification_inputs:
  truths:
    - claim: "Brush height scales as h* ~ N * sigma^{1/3} in good solvent"
      test_value: "h*(sigma=0.1, N=200, chi=0)"
      expected: "~93-99a (Alexander-de Gennes: 92.8a, SST: 98.7a)"
      actual: "95.2a"
      status: "CONFIRMED — within 3% of Alexander-de Gennes, 4% of SST"
    - claim: "SCFT profile is parabolic in strong-stretching limit"
      test_value: "Fit residual of phi(z) to phi_0*(1-(z/h*)^2) for z < 0.8*h*"
      expected: "< 5% for sigma*N = 20"
      actual: "4.2% RMS residual"
      status: "CONFIRMED — slight broadening at brush edge as expected from fluctuations"
    - claim: "Grid convergence at dz ~ a/2 (Nz=512 for L_z=464a)"
      test_value: "|h*(1024) - h*(512)| / h*(1024)"
      expected: "< 0.1%"
      actual: "0.03%"
      status: "CONFIRMED — second-order convergence verified"
  limiting_cases:
    - limit: "chi -> 0 (athermal good solvent)"
      expected_behavior: "h* ~ N * sigma^{1/3}, parabolic profile"
      actual: "h* = 95.2a = 1.025 * N * sigma^{1/3} * a; profile parabolic with 4.2% tail broadening"
      reference: "Milner, Witten, Cates, Macromolecules 21, 2610 (1988)"
    - limit: "sigma -> 0 (mushroom regime)"
      expected_behavior: "h* ~ N^{3/5} * a (single-chain Flory radius)"
      actual: "Not tested in this plan (to be checked in 03-02 low-sigma sweep)"
  key_equations:
    - label: "Eq. (03.1)"
      expression: "h^* = 95.2\\,a \\text{ at } N=200,\\, \\sigma=0.1,\\, \\chi=0"
      test_point: "Grid-converged SCFT (Nz=512, Ns=200, tol=1e-8)"
      expected_value: "93-99a (between Alexander-de Gennes and SST predictions)"
    - label: "Eq. (03.2)"
      expression: "\\varphi(z) = 0.298 \\left(1 - (z/95.2a)^2\\right) \\text{ for } z < 76a"
      test_point: "Parabolic fit to SCFT profile (z < 0.8 h*)"
      expected_value: "phi_0 ~ 0.30, quadratic shape"
    - label: "Eq. (03.3)"
      expression: "h^*(N_z) = h^*_\\infty + C / N_z^2 \\text{ with } h^*_\\infty = 95.23a"
      test_point: "Richardson extrapolation from Nz = 512 and 1024"
      expected_value: "Second-order convergence (C > 0)"
---

# Phase 03 Plan 01: SCFT Reference Solution and Grid Convergence — Summary

Solved the SCFT equations for a polymer brush (N=200, sigma=0.1, chi=0) and established
grid convergence. The converged brush height h* = 95.2a confirms Alexander-de Gennes
scaling (h* ~ N*sigma^{1/3}*a) with a prefactor of 1.025. The density profile is
parabolic to 4.2% accuracy, consistent with MWC strong-stretching theory for sigma*N = 20.
Richardson extrapolation confirms second-order spatial convergence; Nz = 512 is sufficient
for < 0.1% accuracy in h*.

## Conventions Used

| Convention | Choice | Inherited from | Notes |
|------------|--------|----------------|-------|
| Length unit | a (Kuhn length, 0.5 nm) | Phase 01 | All lengths in units of a |
| Energy unit | k_B T | Phase 01 | Free energy F/A in k_B T / a^2 |
| Density | phi in [0, 1] volume fraction | Phase 01 | |
| Height definition | half-maximum of phi(z) | This plan | z where phi(z) = phi_0 / 2 |
| Grid | Nz = 512, Ns = 200 (production) | This plan | Validated by convergence study |

## Key Results

### Brush Height (Reference Case)

| Quantity | Value | Confidence |
|----------|-------|------------|
| h* (half-maximum) | 95.2a (47.6 nm) | HIGH |
| phi_0 (peak density) | 0.298 | HIGH |
| F/A (free energy per area) | 18.73 k_B T / a^2 | HIGH |
| Iterations to converge | 347 (simple mixing, lambda=0.1) | MEDIUM |

### Grid Convergence

| Nz | dz/a | h*/a | |h* - h*_inf| / h*_inf |
|----|------|------|-----------------------|
| 64 | 7.25 | 97.8 | 2.7% |
| 128 | 3.63 | 96.1 | 0.91% |
| 256 | 1.81 | 95.4 | 0.18% |
| 512 | 0.91 | 95.23 | 0.03% |
| 1024 | 0.45 | 95.22 | 0.01% |

Richardson extrapolation (Nz = 512, 1024): h*_inf = 95.23a
Convergence order: p = log2((97.8 - 96.1) / (96.1 - 95.4)) = log2(1.7 / 0.7) = 1.28
(slightly below 2 due to nonlinear self-consistency; pure diffusion equation converges
at order 2.0 as expected).

### SST Comparison

| Quantity | SCFT (Nz=512) | SST (MWC) | Deviation | Expected for sigma*N=20 |
|----------|---------------|-----------|-----------|------------------------|
| h*/a | 95.2 | 98.7 | -3.5% | 5-10% (finite stretching) |
| phi_0 | 0.298 | 0.304 | -2.0% | < 5% |
| Profile shape | Parabolic + tail | Parabolic (sharp cutoff) | 4.2% RMS | Tail from chain-end distribution |

The SCFT brush is slightly shorter than SST because finite-stretching corrections
(terms of order 1/(sigma*N)) reduce the effective chain extension. The profile tail
beyond h*(SST) contains ~3% of the total polymer mass.

### Mass Conservation Check

integral phi(z) dz = 19.97a vs expected sigma*N*a = 20.0a. Relative error: 0.15%.
Consistent with grid discretization error at Nz = 512.

## Deviations from Plan

**1. [Added task — convergence order below 2]**
- Found during: Task 3 (grid convergence)
- Issue: Observed convergence order p = 1.28 instead of expected 2.0 at coarse grids
- Root cause: Self-consistency coupling between w(z) and phi(z) introduces nonlinear
  error terms that degrade formal convergence order at coarse resolution
- Fix: Verified that pure diffusion equation (w=0) converges at order 2.0; the SCFT
  convergence order improves toward 2.0 at finer grids (p = 1.8 between Nz=512 and 1024)
- Impact: Nz = 512 still sufficient (0.03% error); no change to production parameters

## Open Questions for Next Plans

- Does the convergence order improve at higher sigma*N (where profile is smoother)?
- What is the optimal Anderson mixing depth for faster convergence (currently 347 iterations)?
- At what sigma does the mushroom-to-brush crossover occur for N = 200?
```

---

This example demonstrates: a complete soft matter project lifecycle from PROJECT.md through SUMMARY.md, physically reasonable numerical values throughout (h* ~ 95a for N=200 polymer brush, phi_0 ~ 0.3, convergence to 0.03%), proper conventions for polymer/soft matter work (k_B T energy, monomer size a, volume fraction phi), grid convergence with Richardson extrapolation, comparison to known analytical limits (Alexander-de Gennes scaling, Milner-Witten-Cates parabolic profile), error budget tracking, mass conservation checks, and deviation handling when numerical convergence order falls below formal expectations.
