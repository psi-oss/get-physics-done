# 2D Ising Model: Critical Exponents via Monte Carlo

## Problem Statement

The square-lattice Ising model undergoes a continuous phase transition at T_c = 2J/ln(1 + sqrt(2)) ~ 2.269 J/k_B from a ferromagnetic (ordered) to a paramagnetic (disordered) phase. Onsager's exact solution gives the critical exponents analytically, making this system an ideal benchmark for numerical methods: we know the right answer.

**Goal:** Design and execute a Monte Carlo simulation using the Wolff cluster algorithm, extract the critical temperature and critical exponents via finite-size scaling, and verify all results against Onsager's exact solution.

## GPD Workflow

### Step 1: Initialize project and design the experiment

```
/gpd:new-project
> Map the ferromagnetic-paramagnetic phase transition of the
> square-lattice 2D Ising model using Monte Carlo simulation.
> Extract T_c, nu, beta, and gamma via finite-size scaling.
> Benchmark all results against Onsager's exact solution.
```

**Convention lock:**

| Convention | Choice |
|------------|--------|
| Hamiltonian | H = -J sum_{<ij>} s_i s_j, J > 0 (ferromagnetic), s_i = +/- 1 |
| Temperature units | k_B T / J (dimensionless) |
| Magnetization | m = \|M\|/N where M = sum_i s_i |
| Susceptibility | chi = N(<m^2> - <\|m\|>^2) / T |
| Binder cumulant | U_4 = 1 - <m^4>/(3<m^2>^2) |

### Step 2: Plan the computational experiment

```
/gpd:plan-phase 1
```

GPD produces a detailed experiment design (similar to the Ising experiment design reference). Key decisions:

**Algorithm choice: Wolff cluster vs Metropolis**

Near T_c, the Metropolis algorithm suffers critical slowing down with dynamic exponent z ~ 2.17. The Wolff single-cluster algorithm has z ~ 0.25, giving a speedup of ~1000x at L = 128.

**System sizes:** L = 8, 16, 32, 64, 128 (five sizes for finite-size scaling).

**Temperature grid:** 22 temperatures total, with log-spacing near T_c to resolve the critical region.

**Statistics:** 50,000 Wolff cluster flips per (T, L) point for production runs.

### Step 3: Execute the simulation

```
/gpd:execute-phase 1
```

GPD generates the simulation code and runs it in stages:

1. Pilot run at L = 8 (validates the code against exact small-system results)
2. Autocorrelation measurement (confirms tau_auto ~ 5 cluster flips at L = 128)
3. Production runs across all (T, L) points
4. Reproducibility check (3 independent seeds at T_c, L = 128)

**Convergence validation:**

```
/gpd:numerical-convergence
```

| L | N_flips | tau_auto (Wolff) | N_independent | sigma_m / <m> at T_c |
|---|---------|-----------------|---------------|----------------------|
| 8 | 50,000 | 2 | 25,000 | 0.3% |
| 16 | 50,000 | 3 | 16,700 | 0.5% |
| 32 | 50,000 | 3 | 16,700 | 0.7% |
| 64 | 50,000 | 4 | 12,500 | 1.0% |
| 128 | 50,000 | 5 | 10,000 | 1.2% |

All uncertainties within the 1-2% target. PASS.

### Step 4: Extract T_c from Binder cumulant crossing

The Binder cumulant U_4(T, L) is scale-invariant at T_c: curves for different L cross at a single point.

**Result:** Binder crossing at T_c = 2.269(2) J/k_B.

| L pair | Crossing T | Uncertainty |
|--------|-----------|-------------|
| (16, 32) | 2.271 | 0.004 |
| (32, 64) | 2.270 | 0.003 |
| (64, 128) | 2.269 | 0.002 |

The crossing drifts toward the exact value as L increases, consistent with corrections to scaling.

### Step 5: Extract critical exponents via finite-size scaling

```
/gpd:parameter-sweep
```

**Finite-size scaling forms at T_c:**

| Observable | Scaling form | Fit result | Exact value | Agreement |
|-----------|-------------|-----------|-------------|-----------|
| Magnetization | m(T_c, L) ~ L^{-beta/nu} | beta/nu = 0.125(3) | 1/8 = 0.125 | PASS |
| Susceptibility | chi(T_c, L) ~ L^{gamma/nu} | gamma/nu = 1.748(8) | 7/4 = 1.750 | PASS |
| Binder crossing drift | T_c(L) - T_c ~ L^{-1/nu} | 1/nu = 1.00(3) | 1 | PASS |

From the ratios:
- nu = 1.00(3) (exact: 1)
- beta = 0.125(3) (exact: 1/8)
- gamma = 1.748(8) * 1.00(3) = 1.75(1) (exact: 7/4)

### Step 6: Scaling collapse

The ultimate test: plotting m * L^{beta/nu} vs (T - T_c) * L^{1/nu} should collapse all system sizes onto a single universal curve.

Using the extracted exponents, the data for L = 16, 32, 64, 128 collapses to a single curve with chi^2/dof = 1.1. Excellent collapse.

## Results and Verification

### Final Results

| Quantity | Measured | Exact (Onsager) | Status |
|----------|---------|-----------------|--------|
| T_c | 2.269(2) J/k_B | 2.2692... J/k_B | PASS |
| nu | 1.00(3) | 1 | PASS |
| beta | 0.125(3) | 1/8 | PASS |
| gamma | 1.75(1) | 7/4 | PASS |
| beta/nu | 0.125(3) | 1/8 | PASS |
| gamma/nu | 1.748(8) | 7/4 | PASS |

### Verification Checks

```
/gpd:verify-work
```

**Scaling relation check (Rushbrooke):**

2 beta + gamma = 2 * 0.125 + 1.75 = 2.00(2). Expected: 2 - alpha = 2 (since alpha = 0 for 2D Ising, log divergence). PASS.

**Hyperscaling check:**

d * nu = 2 * 1.00 = 2.00. Expected: 2 - alpha = 2. PASS.

**Limiting cases:**

| Limit | Expected | Observed | Status |
|-------|----------|----------|--------|
| T << T_c | m -> 1 | m(T=1.5) = 0.9965(2) | PASS |
| T >> T_c | m -> 0 | m(T=3.5) = 0.002(1) | PASS |
| U_4 at T << T_c | 2/3 | 0.6665(3) | PASS |
| U_4 at T >> T_c | 0 | 0.003(2) | PASS |

**Literature comparison:**
- T_c matches Onsager (1944), Phys. Rev. 65, 117. PASS.
- Critical exponents match the exact 2D Ising universality class. PASS.
- Binder cumulant crossing value U_4* = 0.611(1) matches Kaul (2009). PASS.

**Confidence: HIGH** -- All numerical results agree with exact analytical values within statistical uncertainties. Scaling collapse confirms consistency across all system sizes.
