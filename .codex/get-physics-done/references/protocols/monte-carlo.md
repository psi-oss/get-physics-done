---
load_when:
  - "Monte Carlo"
  - "MCMC"
  - "Metropolis"
  - "importance sampling"
  - "thermalization"
  - "autocorrelation"
  - "finite-size scaling"
tier: 2
context_cost: medium
---

# Monte Carlo Methods Protocol

Monte Carlo simulations are the primary tool for non-perturbative physics, but they are uniquely fragile: silent failures (frozen modes, insufficient thermalization, underestimated autocorrelations) produce results that look converged but are wrong. Every MC calculation must pass the checks in this protocol.

## Related Protocols

- See `lattice-gauge-theory.md` for lattice-specific MC concerns (topology freezing, fermion determinant)
- See `numerical-computation.md` for convergence testing and error budgets
- See `stochastic-processes.md` for underlying stochastic process theory and detailed balance
- See `molecular-dynamics.md` for hybrid Monte Carlo (HMC) and molecular dynamics integration

## Step 1: Markov Chain Construction

1. **Define the configuration space explicitly.** State the degrees of freedom (spin values, field values, particle positions), the lattice/grid structure, and any constraints (fixed total magnetization, conserved particle number, gauge constraint).
2. **Define the transition probability.** Write P(C -> C') explicitly. For Metropolis: P = min(1, exp(-beta * Delta E)). For heat bath: P = exp(-beta * E(C')) / Z_local. State which update scheme is used.
3. **Verify detailed balance.** Check P(C -> C') * pi(C) = P(C' -> C) * pi(C') for the target distribution pi(C) = exp(-beta * E(C)) / Z. If using cluster algorithms, verify detailed balance for the cluster move, not the single-spin move.
4. **Verify ergodicity.** Can the Markov chain reach every configuration from every other configuration in a finite number of steps? For constrained systems (fixed particle number, fixed topology), verify the updates preserve the constraint AND remain ergodic within the constrained space.

## Step 2: Thermalization

1. **Start from multiple initial conditions.** Run at least 2-3 chains from different starting points (hot start, cold start, random start). They must converge to the same equilibrium distribution.
2. **Monitor thermalization observables.** Plot energy, order parameter, and action density vs MC time. Thermalization is complete when all chains fluctuate around the same mean with the same variance.
3. **Discard the thermalization period.** Do NOT include pre-thermalization configurations in measurements. The thermalization time depends on the system size, temperature, and algorithm — it must be measured, not guessed.
4. **Near phase transitions:** Thermalization time diverges (critical slowing down). For local algorithms: tau_therm ~ L^z with z ~ 2. For cluster algorithms (Swendsen-Wang, Wolff): z ~ 0.2-0.5. Use cluster algorithms near criticality whenever possible.

## Step 3: Autocorrelation Analysis

1. **Compute the autocorrelation function** for every measured observable: C(t) = <O(i) * O(i+t)> - <O>^2. The integrated autocorrelation time tau_int = 1/2 + sum_{t=1}^{W} C(t)/C(0) determines the effective number of independent samples: N_eff = N_total / (2 * tau_int).
2. **Choose the summation window W carefully.** Too small: tau_int underestimated. Too large: noise dominates. Use the Madras-Sokal window: W is the smallest value where W >= c * tau_int(W), with c ~ 6-10.
3. **Different observables have different autocorrelation times.** Always report tau_int for the slowest observable (typically the one most sensitive to long-wavelength modes, e.g., susceptibility or topological charge).
4. **If tau_int > N_total / 100:** The simulation is too short. Either run longer or use a better algorithm. Results from severely autocorrelated chains are unreliable regardless of error bar estimates.

## Step 4: Error Estimation

1. **Never use naive standard error** sigma/sqrt(N) for correlated data. This underestimates the error by a factor of sqrt(2 * tau_int).
2. **Use one of these methods:**
   - **Binning analysis:** Group consecutive measurements into bins of size B. Compute the variance of bin means. Increase B until the variance plateaus — the plateau value gives the correct error. If no plateau: bins are too small or data too short.
   - **Jackknife:** Delete-one-block resampling. Natural for derived quantities (ratios, fits). Preserves correlations between observables.
   - **Bootstrap:** Resample blocks (not individual measurements) of size >= 2 * tau_int. Gives error bars and confidence intervals for arbitrary derived quantities.
3. **For ratios, logs, and nonlinear functions of observables:** Use jackknife or bootstrap, NOT error propagation on naive means. Error propagation assumes Gaussian errors and ignores correlations.

## Step 5: Sign Problem Detection

1. **Before running:** Determine if the action is complex for the configuration ensemble of interest. Complex action = sign problem. This occurs in: finite-density QCD (nonzero chemical potential), frustrated spin systems, fermion systems with certain interactions, real-time path integrals.
2. **If sign problem present:** The average sign <sign> = <exp(-i * Im(S))> decreases exponentially with volume and inverse temperature. Monitor <sign> throughout the simulation. If <sign> < 0.01, results are statistically meaningless regardless of total statistics.
3. **Mitigation strategies:** Reweighting (works only if <sign> is not too small), complex Langevin (check correctness criteria), Lefschetz thimble decomposition, density of states methods, tensor network approaches. State which method is used and verify its validity.

## Step 6: Finite-Size Scaling

1. **Simulate multiple system sizes.** At least 3-4 sizes spanning a factor of 4-8 in linear dimension L. Results at a single L are not publishable for any quantity that could have finite-size effects.
2. **For phase transitions:** Use finite-size scaling theory. Observable O(L, T) = L^{x/nu} * f((T - T_c) * L^{1/nu}) where x is the scaling dimension and f is a universal function. Collapse data from different L onto a single curve to extract T_c, nu, and x.
3. **For gapped systems:** Finite-size effects are exponentially small ~ exp(-L / xi) when L >> xi. Verify L > 5 * xi for the correlation length xi at the simulation parameters.
4. **For gapless/critical systems:** Finite-size effects are power-law ~ L^{-omega} where omega is a correction-to-scaling exponent. Include subleading corrections in fits.

## Common Pitfalls

- **Frozen modes:** Some degrees of freedom may not update efficiently (e.g., topology in gauge theories, vortices in XY model). The simulation appears converged for local observables but topology-sensitive observables are wrong. Monitor ALL classes of observables.
- **Critical slowing down:** Near T_c, autocorrelation times diverge as tau ~ L^z. Using local Metropolis at criticality with L > 32 is almost certainly insufficient. Use cluster algorithms, multigrid, or event-chain MC.
- **Insufficient thermalization at first-order transitions:** Metastability means the system can appear thermalized in one phase while the true equilibrium is a coexistence. Use parallel tempering or multicanonical methods.
- **Systematic bias from finite statistics:** For nonlinear estimators (susceptibility from variance, Binder cumulant), finite-sample bias can exceed statistical errors. Use bias-corrected estimators or verify with jackknife.

## Concrete Example: Autocorrelation Destroying Error Estimates

**Problem:** Estimate the magnetization of the 2D Ising model at T = 0.9 T_c using Metropolis MC on an L = 64 lattice.

**Wrong approach (common LLM error):** "Run 10^6 sweeps, compute <|M|> and its standard error as sigma/sqrt(N_samples) where N_samples = 10^6."

This dramatically underestimates the error because consecutive MC configurations are correlated. The effective number of independent samples is N_eff = N_samples / (2 * tau_int), where tau_int is the integrated autocorrelation time.

**Correct approach following this protocol:**

Step 1. **Thermalization.** Discard the first N_therm sweeps. For Metropolis at 0.9 T_c on L = 64: tau ~ L^z ~ 64^{2.17} ~ 10^4 sweeps (z ~ 2.17 for 2D Ising Metropolis). Thermalize for at least 10 * tau ~ 10^5 sweeps.

Step 2. **Production run.** Run N_prod = 10^6 sweeps, measuring |M| every sweep.

Step 3. **Compute autocorrelation function:**
```
C(t) = (<M(0) M(t)> - <M>^2) / (<M^2> - <M>^2)
```
Fit to extract tau_int = (1/2) + sum_{t=1}^{W} C(t), where the summation window W is chosen where C(t) first drops below noise.

Step 4. **Correct the error:**
```
sigma_naive = std(|M|) / sqrt(N_prod) = 0.0015
tau_int = 5200 sweeps (at 0.9 T_c, L = 64, Metropolis)
N_eff = N_prod / (2 * tau_int) = 10^6 / (2 * 5200) ~ 96
sigma_correct = std(|M|) / sqrt(N_eff) = 0.153
```

The correct error (0.153) is **~102 times larger** than the naive error (0.0015). Reporting the naive error would be scientific fraud.

**Verification:**
- Binning analysis: group consecutive measurements into bins of size B. Plot sigma(B) vs B. It should plateau when B >> tau_int. If sigma keeps increasing with B: tau_int was underestimated.
- Compare with Wolff cluster algorithm: tau_cluster ~ L^{0.25} ~ 3 sweeps. The cluster algorithm eliminates critical slowing down. If Metropolis and cluster give the same <|M|> within correct errors: result is validated.
- Known exact result (Onsager): <|M|> at T/T_c = 0.9 for L -> infinity is calculable. Compare with finite-size-extrapolated MC value.

## Worked Example: Binder Cumulant Crossing for T_c of the 3D Ising Model

**Problem:** Determine the critical temperature T_c of the 3D Ising model on a simple cubic lattice using the Binder cumulant crossing method with Wolff cluster MC. This targets the LLM error class of incorrect finite-size scaling analysis — specifically, using the wrong observable, fitting the wrong functional form, or ignoring corrections to scaling.

### Step 1: Define the Observable

The Binder cumulant (fourth-order cumulant ratio):

```
U_4(T, L) = 1 - <m^4> / (3 <m^2>^2)
```

where m = M/V is the magnetization density and <...> is the thermal average.

**Key property:** At T = T_c, U_4(T_c, L) = U_4* (a universal constant, independent of L) up to corrections to scaling. For T < T_c: U_4 -> 2/3 as L -> infinity. For T > T_c: U_4 -> 0 as L -> infinity.

The crossing point of U_4(T, L) for different L values gives T_c.

### Step 2: Simulation Parameters

| L | N_therm (Wolff clusters) | N_prod (Wolff clusters) | Measurements |
|---|--------------------------|------------------------|--------------|
| 8 | 10,000 | 500,000 | every cluster flip |
| 16 | 10,000 | 500,000 | every cluster flip |
| 32 | 10,000 | 500,000 | every cluster flip |
| 64 | 20,000 | 1,000,000 | every cluster flip |

Temperature range: T/J = [4.40, 4.60] in steps of 0.005 (41 temperatures). The known value is T_c/J = 4.5115(1).

**Autocorrelation check:** For Wolff cluster algorithm in 3D Ising: z ~ 0.25. At L = 64: tau_int ~ 64^{0.25} ~ 2.8 cluster flips. So N_prod = 10^6 gives N_eff ~ 10^6 / 6 ~ 170,000 independent samples. Statistical error on U_4: about 0.001.

### Step 3: Identify the Crossing

For each pair (L_1, L_2), find T_cross where U_4(T, L_1) = U_4(T, L_2). Use linear interpolation between adjacent temperature points.

Expected results:

| L pair | T_cross/J | U_4 at crossing |
|--------|-----------|-----------------|
| (8, 16) | 4.525 | 0.465 |
| (16, 32) | 4.516 | 0.465 |
| (32, 64) | 4.513 | 0.466 |

The crossing points drift toward T_c as L increases — this drift is due to corrections to scaling.

### Step 4: Extrapolate to L -> infinity

The correction-to-scaling form:

```
T_cross(L_1, L_2) = T_c + A * L_min^{-omega-1/nu}
```

where omega ~ 0.83 is the leading correction-to-scaling exponent for 3D Ising.

Fit T_cross vs L_min^{-omega-1/nu} (using nu = 0.6300 and omega = 0.83) with a linear fit. Extrapolate to L_min -> infinity.

Expected: T_c/J = 4.5115(3), consistent with the high-precision literature value T_c/J = 4.511528(6).

### Verification

1. **Universality of U_4*:** The crossing value U_4* = 0.4655(3) should be the same for all lattice types (cubic, BCC, FCC) — it is a universal amplitude ratio. If you get a significantly different value, either the simulation has a bug or you are not at the critical point.

2. **Crossing vs intersection:** If the U_4(T, L) curves for different L do NOT cross (they run parallel or diverge), the system may not have a continuous phase transition at this temperature, or the temperature range is wrong.

3. **Consistency with nu:** From the Binder cumulant data, extract nu independently by fitting U_4(T, L) = f((T - T_c) * L^{1/nu}) to a scaling collapse. The value of nu from the collapse should be consistent with the literature value nu = 0.6300(1).

4. **Effect of corrections to scaling:** If you fit T_cross vs 1/L (ignoring omega), you get T_c/J ~ 4.508 — off by 0.08%. Including the correction exponent omega = 0.83 brings T_c to 4.5115 — a 20x improvement. This demonstrates why corrections to scaling matter.

5. **Jackknife errors:** The Binder cumulant is a ratio of moments. Use jackknife resampling to estimate its error, NOT naive error propagation. Naive propagation can underestimate errors by a factor of 2-3 for this observable.

## Worked Example: Critical Slowing Down and Cluster Algorithm Rescue in the 2D XY Model

**Problem:** Measure the magnetic susceptibility chi of the 2D XY model near the Berezinskii-Kosterlitz-Thouless (BKT) transition at T_BKT ~ 0.893 J using both Metropolis and Wolff cluster algorithms. Demonstrate that Metropolis suffers critical slowing down so severe that it produces a wrong estimate of chi at the transition, while the cluster algorithm gives the correct result with the same computational effort. This targets the LLM error class of using local-update MC near a phase transition without checking autocorrelation times.

### Setup

The 2D XY model: spins are unit vectors (cos(theta_i), sin(theta_i)) on a square lattice, with Hamiltonian:

```
H = -J sum_{<ij>} cos(theta_i - theta_j)
```

The BKT transition at T_BKT ~ 0.893 J is a topological transition driven by vortex unbinding. Unlike conventional phase transitions, the correlation length diverges exponentially: xi ~ exp(b / sqrt(T - T_BKT)).

### Step 1: Metropolis Simulation

Run Metropolis MC at T = 0.90 J (just above T_BKT) for lattice sizes L = 16, 32, 64, 128:

| L | N_sweeps | tau_int (sweeps) | N_eff | chi / L^2 | chi error (naive) | chi error (correct) |
|---|----------|-----------------|-------|-----------|-------------------|---------------------|
| 16 | 10^6 | 45 | 11000 | 0.042 | 0.0001 | 0.0007 |
| 32 | 10^6 | 320 | 1560 | 0.038 | 0.0001 | 0.002 |
| 64 | 10^6 | 4800 | 104 | 0.031 | 0.0001 | 0.006 |
| 128 | 10^6 | ~80000 | 6 | 0.022 | 0.0001 | 0.02 |

**The problem:** The autocorrelation time grows as tau ~ L^z with z ~ 2 (dynamic critical exponent for Metropolis). At L = 128, tau_int ~ 80000 sweeps — 10^6 sweeps gives only ~6 effective independent samples. The susceptibility estimate chi/L^2 = 0.022 +/- 0.02 is essentially noise. Yet the naive error bar (0.0001) makes it look precise.

**The LLM error:** Reporting chi/L^2 = 0.022 +/- 0.0001 at L = 128. This dramatically understates the uncertainty because the naive error ignores the 80000-sweep autocorrelation. The correct error is ~400x larger (sqrt(2 * tau_int) = sqrt(160000) ~ 400).

### Step 2: Wolff Cluster Simulation

The Wolff single-cluster algorithm builds a cluster of aligned spins and flips them collectively. This dramatically reduces z:

| L | N_clusters | tau_int (clusters) | N_eff | chi / L^2 | chi error |
|---|-----------|-------------------|-------|-----------|-----------|
| 16 | 10^6 | 2.1 | 240000 | 0.0423 | 0.0001 |
| 32 | 10^6 | 3.5 | 143000 | 0.0391 | 0.0002 |
| 64 | 10^6 | 6.2 | 80600 | 0.0378 | 0.0003 |
| 128 | 10^6 | 12 | 41700 | 0.0371 | 0.0005 |

The dynamic critical exponent is z ~ 0.25 (compared to z ~ 2 for Metropolis). At L = 128, tau_int ~ 12 clusters vs 80000 sweeps — a factor of 6700 improvement in sampling efficiency.

### Step 3: Comparing the Physics

The susceptibility near the BKT transition should scale as chi ~ L^{2-eta} with eta = 1/4 at T_BKT:

| L | chi/L^2 (Metropolis, "converged") | chi/L^2 (Wolff) | Exact scaling L^{-1/4} |
|---|-----------------------------------|-----------------|------------------------|
| 16 | 0.042 | 0.0423 | 0.50 * L^{-0.25} = 0.25 |
| 32 | 0.038 | 0.0391 | 0.50 * 32^{-0.25} = 0.21 |
| 64 | 0.031 (suspect) | 0.0378 | 0.50 * 64^{-0.25} = 0.18 |
| 128 | 0.022 (WRONG) | 0.0371 | 0.50 * 128^{-0.25} = 0.15 |

The Metropolis result at L = 128 (chi/L^2 = 0.022) is wrong — it is suppressed because the simulation is stuck in a single magnetization sector and has not explored the full configuration space. The Wolff result (0.0371) is consistent with the expected BKT scaling.

### Step 4: Vortex Autocorrelation — The Hidden Diagnostic

The BKT transition is driven by topological defects (vortices). Even if the spin autocorrelation appears manageable, the VORTEX autocorrelation may be much longer:

| L | tau_int (magnetization) | tau_int (vortex number) | tau_int (vortex number, Wolff) |
|---|------------------------|------------------------|-------------------------------|
| 64 | 4800 sweeps | 25000 sweeps | 8 clusters |
| 128 | 80000 sweeps | >500000 sweeps | 15 clusters |

The vortex number is the slowest mode in the system. At L = 128 with Metropolis, not even the vortex number has equilibrated. Any observable sensitive to vortex configurations is wrong.

### Verification

1. **Autocorrelation time scaling.** Plot ln(tau_int) vs ln(L). For Metropolis: slope should be z ~ 2.0-2.2. For Wolff: slope should be z ~ 0.2-0.3. If the Metropolis slope is less than 1.5, the autocorrelation is being underestimated (insufficient data for the autocorrelation function to decay).

2. **Binning analysis convergence.** Plot sigma(B) (the error estimate from bins of size B) vs B. For Metropolis at L = 128: sigma(B) should still be increasing at B = 10^5. If it appears to plateau at B = 1000, the plateau is spurious — increase B further.

3. **Multiple independent chains.** Run 5 independent Metropolis chains at L = 128, each from a different random start. If the chi estimates from different chains disagree by more than 2*sigma_correct, the chains have not individually equilibrated.

4. **BKT scaling collapse.** The susceptibility near T_BKT should satisfy chi(T, L) = L^{7/4} * f(L / xi(T)) where xi(T) ~ exp(b/sqrt(T - T_BKT)). The Wolff data should collapse onto a single curve; the Metropolis data at large L will not collapse because it is dominated by sampling error.

5. **Known result.** The BKT transition temperature for the 2D XY model is T_BKT = 0.8929(1) J (from high-precision MC studies using cluster algorithms). If your estimate of T_BKT differs significantly, check the Hamiltonian (factor of 2 in the coupling is a common error: H = -J cos vs H = -(J/2) cos).
