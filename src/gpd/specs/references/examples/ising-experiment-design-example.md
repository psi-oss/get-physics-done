# Worked Example: 2D Ising Model Phase Diagram via Monte Carlo

This demonstrates a complete experiment design for mapping the ferromagnetic-paramagnetic phase transition of the square-lattice Ising model using Monte Carlo simulation. It covers every step from observable identification through cost estimation with concrete numbers.

---

### Step 1: Identify Target Quantities

| Quantity | Symbol | Dimensions | Expected Range | Required Accuracy | Validation |
|----------|--------|------------|----------------|-------------------|------------|
| Magnetization | \|m\| = \|M\|/L^2 | dimensionless | [0, 1] | 1% relative | m -> 0 as T -> infinity; m -> 1 as T -> 0 |
| Susceptibility | chi = L^2 (<m^2> - <\|m\|>^2) / T | 1/J | [0, ~L^{gamma/nu}] | 5% relative | Diverges at T_c as chi ~ |t|^{-gamma} |
| Specific heat | C_v = (<E^2> - <E>^2) / (T^2 L^2) | k_B | [0, ~2] | 5% relative | Log divergence at T_c (alpha = 0 for 2D Ising) |
| Binder cumulant | U_4 = 1 - <m^4> / (3<m^2>^2) | dimensionless | [0, 2/3] | 0.1% absolute | U_4 = 2/3 ordered; U_4 -> 0 disordered; crossing gives T_c |

**Derived quantities:**
- T_c from Binder cumulant crossing (known exact: T_c = 2/ln(1+sqrt(2)) ~ 2.2692 J/k_B)
- Critical exponent nu from finite-size scaling of Binder crossing
- Critical exponent gamma/nu from susceptibility scaling at T_c

### Step 2: Control Parameters

| Parameter | Symbol | Range | Sampling | Rationale |
|-----------|--------|-------|----------|-----------|
| Temperature | T | [1.5, 3.5] J/k_B | Adaptive: log-spaced near T_c, coarse elsewhere | Spans ordered (T << T_c) through disordered (T >> T_c) |
| System size | L | {8, 16, 32, 64, 128} | Geometric (ratio 2) | 5 sizes for finite-size scaling; L=128 for production |

### Step 3: Design Temperature Grid

**Three regimes with different spacing:**

| Regime | T range | Spacing | N_points | Rationale |
|--------|---------|---------|----------|-----------|
| Deep ordered | [1.5, 2.0] | Uniform, dT = 0.25 | 3 | Slow variation; validation against low-T expansion |
| Critical region | [2.0, 2.6] | Log-spaced in \|T - T_c\| | 15 | Physics concentrates here; need resolution for Binder crossing |
| Deep disordered | [2.6, 3.5] | Uniform, dT = 0.3 | 4 | Slow variation; validation against high-T expansion |

**Explicit critical-region temperatures:**

```
T_c = 2.2692 J/k_B
Below T_c (log-spaced in T_c - T):
  T = [2.000, 2.080, 2.140, 2.190, 2.220, 2.245, 2.260, 2.267]
Above T_c (log-spaced in T - T_c):
  T = [2.272, 2.280, 2.295, 2.320, 2.360, 2.420, 2.530]
```

This gives 14 temperatures with resolution concentrated where the physics changes fastest.

### Step 4: Convergence Study Design

**Numerical parameter: Equilibration sweeps**

The only numerical parameter is the number of MC sweeps. Convergence means the observable is independent of the starting configuration.

```
Parameter: N_equil (equilibration sweeps)
Expected behavior: Observable drift should vanish after O(tau_auto) sweeps
Protocol:
  - Start from ordered (all spins up) AND disordered (random) configurations
  - Monitor |m| vs sweep number for first 10^4 sweeps
  - Equilibration is complete when: |<m>_ordered - <m>_random| < 2*sigma
  - Minimum equilibration: max(1000, 20 * tau_auto) sweeps
```

**Algorithm choice: Wolff cluster vs Metropolis**

Near T_c, Metropolis has dynamic exponent z ~ 2.17 (critical slowing down). Wolff cluster has z ~ 0.25.

| L | tau_auto (Metropolis) | tau_auto (Wolff) | Speedup |
|---|----------------------|-----------------|---------|
| 8 | ~20 sweeps | ~2 sweeps | 10x |
| 16 | ~90 sweeps | ~3 sweeps | 30x |
| 32 | ~400 sweeps | ~4 sweeps | 100x |
| 64 | ~1,800 sweeps | ~5 sweeps | 360x |
| 128 | ~8,000 sweeps | ~6 sweeps | 1,300x |

**Decision:** Use Wolff cluster algorithm. The speedup at L=128 is 3 orders of magnitude.

### Step 5: Statistical Analysis Plan

**Pilot run specification (per parameter point):**

```
Algorithm: Wolff single-cluster
Equilibration: 1,000 cluster flips (>> 20 * tau_auto ~ 120 for L=128)
Pilot production: 10,000 cluster flips
Measurements: every cluster flip (already decorrelated for Wolff)
Purpose: estimate tau_auto, <m>, <m^2>, <E>, <E^2>
```

**Production run specification:**

Target: 1% relative error on magnetization at each (T, L) point.

For magnetization m with variance sigma_m^2:
  N_ind >= (sigma_m / (0.01 * <m>))^2

Near T_c where sigma_m / <m> ~ O(1): need N_ind >= 10,000 independent samples.
Far from T_c where sigma_m / <m> ~ 0.01: need N_ind >= 1.

Conservative: 50,000 cluster flips per point (provides 50,000 / tau_auto independent samples; for Wolff tau_auto ~ 5 at L=128, this gives ~10,000 independent samples).

**Error estimation:** Block averaging (Flyvbjerg-Petersen)
- Block sizes: [1, 2, 4, 8, 16, ..., N/8]
- Error estimate: plateau value from block-averaged standard error
- Cross-check: jackknife for derived quantities (Binder cumulant, chi)

**Reproducibility:** 3 independent runs with different seeds per (T_c, L=128) point. Agreement within error bars required.

### Step 6: Validation Points

| T (J/k_B) | Observable | Known Value | Source |
|------------|-----------|-------------|--------|
| 0 (extrapolation) | \|m\| | 1.0 | Ground state |
| T_c = 2.2692 | U_4 crossing | 0.6107 | Exact (Binder, Kaul 2009) |
| T_c | m(L) | ~ L^{-beta/nu} = L^{-1/8} | Exact exponents (Onsager) |
| T_c | chi(L) | ~ L^{gamma/nu} = L^{7/4} | Exact exponents |
| T >> T_c | m | 0 | Disordered phase |
| 2.5 | chi | ~ 4.5 (L -> inf) | High-T expansion |

### Step 7: Computational Cost Estimate

Pilot run per point: 11,000 cluster flips. Cost per flip ~ O(L^2) operations (each flip touches ~L^2/cluster_size sites, but total work per flip is O(L^2) on average).

| Run Type | N_points | System Size | Flips/Point | Time/Point (est.) | Total |
|----------|----------|-------------|-------------|--------------------|----|
| Pilot (all T, all L) | 22 * 5 = 110 | L = 8-128 | 11,000 | 0.5-30 sec | ~15 min |
| Production (critical, all L) | 15 * 5 = 75 | L = 8-128 | 50,000 | 2-120 sec | ~1.5 hr |
| Production (wings, L=64,128) | 7 * 2 = 14 | L = 64, 128 | 50,000 | 60-120 sec | ~25 min |
| Reproducibility (T_c, L=128) | 3 | L = 128 | 100,000 | 240 sec | ~12 min |
| Convergence check (tau_auto) | 5 * 5 = 25 | L = 8-128 | 100,000 | 5-240 sec | ~40 min |
| **Total** | **227** | | | | **~3.5 hr CPU** |

Budget: 4 CPU-hours. Estimated cost: 3.5 hours. Margin: 15%. Acceptable.

### Step 8: Execution Order

```
1. Pilot runs (all T, L=8 only)           [15 min, validates code]
2. Pilot runs (T_c, all L)                [5 min, measures tau_auto vs L]
3. Convergence study (equilibration)       [40 min, confirms thermalization]
4. Production: critical region, all L      [1.5 hr, core data]
5. Production: wing regions, L=64,128     [25 min, validates limits]
6. Reproducibility: T_c, L=128            [12 min, consistency check]
7. Analysis: Binder crossing -> T_c        [post-processing]
8. Analysis: FSS collapse -> nu, gamma     [post-processing]
```

**Dependencies:**
- Step 2 must complete before step 3 (tau_auto determines equilibration)
- Step 3 must complete before steps 4-5 (validates thermalization protocol)
- Steps 4-6 can run concurrently once equilibration is validated
- Steps 7-8 require all production data

### Step 9: Expected Outcomes

If the experiment design is correct:
- Binder cumulant curves for different L cross at T = 2.269(2) J/k_B
- Magnetization at T_c scales as m ~ L^{-0.125} (beta/nu = 1/8)
- Susceptibility at T_c scales as chi ~ L^{1.75} (gamma/nu = 7/4)
- Scaling collapse of m * L^{beta/nu} vs (T - T_c) * L^{1/nu} yields a single curve
- All results agree with exact Onsager solution within error bars

If any of these fail, the experimental design has a problem (wrong algorithm, insufficient statistics, or a bug in the code --- not new physics, since the 2D Ising model is exactly solved).

---

This example demonstrates: physics-motivated temperature grid with log-spacing near T_c, algorithm choice driven by critical slowing down, concrete sample size calculations from target precision, validation points from known exact results, cost estimation with margins, and staged execution with dependencies.
