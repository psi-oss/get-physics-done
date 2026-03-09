---
load_when:
  - "lattice gauge"
  - "lattice QCD"
  - "Wilson fermion"
  - "staggered fermion"
  - "continuum extrapolation"
  - "topology freezing"
  - "gradient flow"
tier: 2
context_cost: high
---

# Lattice Gauge Theory Protocol

Lattice gauge theory is the only first-principles, non-perturbative method for QCD and similar gauge theories. But the lattice introduces artifacts — fermion doubling, topology freezing, finite-volume effects — that can contaminate results in ways that are invisible without systematic checks. This protocol ensures correct continuum and infinite-volume extrapolations.

## Related Protocols

- See `monte-carlo.md` for MCMC sampling, thermalization, and autocorrelation analysis
- See `group-theory.md` for gauge group representations and character expansions
- See `renormalization-group.md` for continuum limit extrapolation and asymptotic scaling
- See `perturbation-theory.md` for lattice perturbation theory and improvement coefficients

## Step 1: Fermion Discretization

1. **Fermion doubling.** Naive lattice fermions produce 2^d species in d dimensions (Nielsen-Ninomiya theorem). Every lattice fermion action sacrifices something to avoid or manage doublers:
   - **Wilson fermions:** Add a dimension-5 operator (Wilson term) that gives doublers a mass ~ 1/a. Breaks chiral symmetry explicitly. Requires additive mass renormalization. Fine-tuning needed to reach the chiral limit.
   - **Staggered (Kogut-Susskind):** Distributes the 16 doublers across 4 "tastes." Preserves a remnant U(1) chiral symmetry. Requires the "rooting trick" (det^{1/4}) for single flavors — theoretically controversial but validated numerically.
   - **Domain-wall:** Places fermions on a 5D lattice; chiral modes localize on 4D boundaries. Preserves chiral symmetry up to exponentially small corrections ~ exp(-L_5 * m_res). Expensive: requires large 5th dimension L_5.
   - **Overlap (Neuberger):** Exact lattice chiral symmetry (Ginsparg-Wilson relation). Most expensive. Satisfies the index theorem exactly on the lattice.
2. **Choose the discretization based on the physics:**
   - Chiral symmetry essential (chiral condensate, pion physics, epsilon regime): domain-wall or overlap
   - Flavor physics, large-scale production: staggered (cheapest, largest volumes achieved)
   - Heavy quark physics: Wilson with non-perturbative improvement (clover term) or HQET
3. **State the fermion action explicitly** including improvement terms (clover coefficient c_SW, tadpole factor u_0, etc.) and how they were determined (tree-level, tadpole-improved, non-perturbative).

## Step 2: Topology Freezing

1. **The problem.** At fine lattice spacings (a < 0.05 fm), the topological charge Q = (1/32pi^2) integral F * F-tilde becomes frozen: the HMC algorithm cannot tunnel between topological sectors. Simulations sample a single Q sector instead of the correct Q distribution, biasing all observables.
2. **Detection:** Monitor Q as a function of MD trajectory. Compute the topological susceptibility chi_t = <Q^2>/V. If chi_t is inconsistent with expectations or Q never changes sign in a long run, topology is frozen.
3. **Autocorrelation of Q.** The integrated autocorrelation time for Q diverges ~ exp(const/a^2) as a -> 0. This is the most severe autocorrelation in lattice QCD — much longer than for local observables. Even if plaquette and hadron correlators appear thermalized, topology may not be.
4. **Mitigation strategies:**
   - Open boundary conditions in time (Luscher): topology can flow in/out through the boundaries. Eliminates freezing but requires new analysis methods.
   - Metadynamics / instanton updates: propose explicit topology-changing moves. Effective but algorithm-specific.
   - Master-field approach: single very large volume where Q fluctuates within the volume.
   - Fixed-topology corrections: correct observables for the bias from fixed Q using Brower et al. formulas. Valid only if the Q distribution is approximately Gaussian.

## Step 3: Scale Setting

1. **The lattice spacing a is not an input — it is an output.** The bare coupling beta = 2N_c/g_0^2 determines a implicitly through dimensional transmutation. The physical value of a must be determined by matching a lattice observable to its experimental value.
2. **Standard scale-setting quantities:**
   - Wilson flow scales: t_0 (Luscher), w_0 (BMW). Precisely determined on the lattice with small statistical errors.
   - Sommer parameter r_0: defined from the static quark potential V(r_0) * r_0^2 = 1.65. Requires computing the static potential.
   - Hadron masses: m_pi, m_Omega, f_pi. Physical but require chiral/continuum extrapolation themselves.
3. **Use at least two independent scale-setting quantities** and verify they give consistent values of a. Discrepancy signals discretization errors or incorrect continuum/chiral extrapolation.
4. **Propagate the scale-setting uncertainty** into all dimensionful results. A 1% error in a translates to a 1% error in masses, 2% in decay constants, and 3% in matrix elements (different dimensions).

## Step 4: Continuum Extrapolation

1. **Simulate at least 3 lattice spacings** spanning a factor of 2-3 (e.g., a ~ 0.12, 0.09, 0.06 fm). Results at a single lattice spacing are lattice artifacts, not continuum physics.
2. **Symanzik improvement.** For an O(a)-improved action (clover Wilson, tree-level improved staggered), leading discretization errors are O(a^2). The continuum extrapolation is: O_phys = O(a) + c_2 * a^2 + c_4 * a^4 + ... . For unimproved actions: O(a) corrections are present and must be included.
3. **Extrapolation procedure:** Fit O(a) to a polynomial in a^2 (for improved actions). Include enough terms to get chi^2/dof ~ 1. If the a^2 coefficient is large, the extrapolation is unreliable — simulate at finer lattice spacings or use a more improved action.
4. **Correlated fits.** The same configurations contribute to results at different a. Use correlated chi^2 fits with the full covariance matrix, or use bootstrap/jackknife to propagate correlations.

## Step 5: Finite-Volume Effects

1. **For hadron masses:** Finite-volume corrections are ~ exp(-m_pi * L) where L is the spatial box size. The rule of thumb m_pi * L > 4 ensures sub-percent corrections for stable hadrons. For resonances and multihadron states, corrections can be much larger.
2. **Luscher quantization condition.** In finite volume, scattering states have discrete energies determined by the Luscher formula relating energy shifts to infinite-volume phase shifts. This is a feature, not a bug: use it to extract scattering amplitudes. But misidentifying a finite-volume scattering state as a resonance is a serious error.
3. **Electromagnetism in finite volume.** Photons have zero mass, so QED finite-volume effects are power-law ~ 1/L^n, not exponentially suppressed. For isospin-breaking calculations, use QED_L (zero-mode subtracted) or QED_C (C-periodic boundary conditions) and understand the scheme dependence.
4. **Topology in finite volume.** The topological susceptibility chi_t has 1/V corrections. For small volumes, the distribution of Q is not Gaussian and fixed-topology corrections are more important.

## Step 6: Quenched vs Dynamical Fermions

1. **Quenched approximation** (no fermion loops) introduces uncontrolled systematic errors: 10-30% for light hadron masses, qualitatively wrong for quantities sensitive to sea quarks (eta', topological susceptibility, string breaking).
2. **Always use dynamical fermions** for production calculations. State the number of dynamical flavors (N_f = 2, 2+1, 2+1+1) and their masses. Are the light quarks at physical mass or heavier? If heavier, a chiral extrapolation is needed.
3. **Partial quenching** (valence quark masses different from sea quark masses) is sometimes used for efficiency. It introduces additional systematic errors described by partially quenched chiral perturbation theory. State clearly if partial quenching is used.

## Step 7: Gradient Flow

The Yang-Mills gradient flow smooths gauge field configurations by evolving them in a fictitious "flow time" t. It provides UV-finite composite operators without multiplicative renormalization, making it a powerful tool for scale setting, topology measurement, and defining renormalized quantities.

1. **Definition.** The gradient flow evolves the gauge field B_mu(t, x) according to:
   dB_mu/dt = D_nu G_{nu mu}
   where G_{mu nu} is the field strength of B_mu and D_nu is the covariant derivative. The initial condition is B_mu(t=0, x) = A_mu(x) (the original gauge field). Flow time t has dimension [length]^2.
2. **UV finiteness.** At positive flow time t > 0, composite operators built from B_mu(t, x) are automatically UV finite — no additional renormalization is needed. This is because the flow acts as a Gaussian smearing of the original field with smearing radius r ~ sqrt(8t). This property is exact and proven to all orders in perturbation theory (Luscher, Weisz 2011).
3. **Scale setting with flow observables.** The energy density at flow time t:
   E(t) = -(1/2) tr(G_{mu nu}(t) G_{mu nu}(t))
   defines two standard reference scales:
   - **t_0 (Luscher):** defined by t^2 <E(t)> |_{t=t_0} = 0.3. Precisely determined on the lattice with small statistical errors.
   - **w_0 (BMW):** defined by t d/dt [t^2 <E(t)>] |_{t=w_0^2} = 0.3. Uses the derivative, which is smoother and less sensitive to short-distance lattice artifacts.
   Both are computed purely from the flowed gauge field — no quark propagators, no fitting, no operator mixing. This makes them the preferred scale-setting quantities in modern lattice QCD.
4. **Topology from gradient flow.** The topological charge density at flow time t:
   q(t, x) = (1/32 pi^2) epsilon_{mu nu rho sigma} tr(G_{mu nu}(t) G_{rho sigma}(t))
   is UV finite and converges to an integer (the topological charge Q = integral d^4x q(t, x)) for sufficiently large t. Choose t large enough that Q is close to an integer (|Q - round(Q)| < 0.1) but small compared to the lattice volume (sqrt(8t) << L) to avoid finite-volume artifacts.
5. **Discretization.** On the lattice, the flow equation is integrated numerically using:
   - Euler integration (first-order, cheap but needs small step size epsilon)
   - Third-order Runge-Kutta (standard choice: Luscher's 3-stage scheme, stable for epsilon <= 0.15)
   - Adaptive step size (adjust epsilon to keep integration errors below a target). Verify by comparing results at different epsilon values.
   The gauge action used in the flow equation can be Wilson plaquette, Symanzik-improved, or Zeuthen (the Zeuthen flow has O(a^4) discretization errors).
6. **Flow time range.** The useful range of flow time is bounded:
   - Below: sqrt(8t) must exceed a few lattice spacings to suppress UV artifacts.
   - Above: sqrt(8t) must be much smaller than the box size L to avoid finite-volume contamination.
   The condition a << sqrt(8t) << L determines the window of reliable flow-time measurements. If this window is too narrow, the lattice is too coarse or the volume too small.

## Worked Example: Pion Mass and Decay Constant in 2+1 Flavor Lattice QCD

**Problem:** Compute the pion mass m_pi and decay constant f_pi in lattice QCD with N_f = 2+1 dynamical flavors. Demonstrate continuum extrapolation, chiral extrapolation, and finite-volume correction. The experimental values are m_pi = 135 MeV (neutral) / 140 MeV (charged), f_pi = 130.2 MeV.

### Step 1: Simulation Parameters

Use clover-improved Wilson fermions with non-perturbative c_SW. Three lattice spacings:

| Ensemble | beta | a (fm) | L^3 x T | m_pi L | N_configs |
|---|---|---|---|---|---|
| A | 3.40 | 0.086 | 32^3 x 64 | 4.1 | 2000 |
| B | 3.55 | 0.064 | 48^3 x 96 | 4.3 | 1500 |
| C | 3.70 | 0.050 | 64^3 x 128 | 4.0 | 1000 |

**Key checks:**
- m_pi L > 4 on all ensembles (finite-volume corrections < 1%)
- a spans a factor of ~1.7 (sufficient for continuum extrapolation with a^2 correction)
- Light quark masses tuned so m_pi ~ 300 MeV (heavier than physical; chiral extrapolation needed)
- Strange quark mass tuned to physical m_K ~ 495 MeV

### Step 2: Scale Setting

Use the Wilson flow scale w_0:

1. Compute the gradient flow energy density E(t) on each ensemble
2. Determine w_0 from t d/dt [t^2 <E(t)>] = 0.3
3. Physical value: w_0 = 0.1714(15) fm (BMW 2012)
4. Convert: a = w_0^{lat} / w_0^{phys}

Cross-check with the Sommer parameter r_0: consistent values of a confirm the scale setting.

### Step 3: Pion Correlator and Effective Mass

Compute the pseudoscalar correlator C_PP(t) = sum_x <P(x, t) P^dag(0, 0)> where P = psi_bar gamma_5 psi.

Extract the effective mass:

```
m_eff(t) = arccosh[(C(t-1) + C(t+1)) / (2 C(t))]
```

**Results at a = 0.086 fm (Ensemble A):**

| t/a | m_eff(t) * a |
|---|---|
| 6 | 0.148(1) |
| 8 | 0.141(1) |
| 10 | 0.139(1) |
| 12 | 0.139(2) |
| 14 | 0.139(2) |

Plateau at m_pi * a = 0.139(2), giving m_pi = 0.139 / (0.086 fm) * (197.3 MeV fm) = 318 MeV. The effective mass at t < 8a is above the plateau (excited state contamination). If the plateau is never reached, use a multi-exponential fit or the GEVP.

### Step 4: Chiral and Continuum Extrapolation

Perform a combined fit using NLO chiral perturbation theory with discretization corrections:

```
m_pi^2 = B * m_q * [1 + (m_pi^2 / (4 pi f_pi)^2) * ln(m_pi^2 / mu^2)] + c_a * a^2
f_pi = f * [1 - (m_pi^2 / (8 pi^2 f^2)) * ln(m_pi^2 / mu^2)] + d_a * a^2
```

| Quantity | a=0.086 fm | a=0.064 fm | a=0.050 fm | Continuum | Physical point |
|---|---|---|---|---|---|
| m_pi (MeV) | 318(3) | 315(3) | 312(3) | 308(4) | 139(3) |
| f_pi (MeV) | 138(2) | 135(2) | 133(2) | 131(2) | 130(3) |

### Step 5: Finite-Volume Correction

The Luscher formula for pion mass finite-volume effects: for m_pi L = 4, correction ~ 0.3%. Our ensembles all have m_pi L > 4, so the correction is sub-percent.

### Verification

1. **Topology check:** Verify that topological charge Q changes sign multiple times during each simulation. At a = 0.050 fm, the autocorrelation time for Q is 50-100 configs. With 1000 configs, we have ~10-20 independent tunneling events — marginal but acceptable.

2. **Effective mass plateau:** Plateau onset t_min > 1 fm. Vary t_min by 2 timeslices and verify m_pi shifts by less than 1 sigma.

3. **Continuum scaling:** Plot m_pi and f_pi vs a^2. For O(a)-improved Wilson fermions, data should be linear in a^2. Visible curvature means either add an a^4 term or improvement is incomplete.

4. **Final comparison:** m_pi = 139(3) MeV vs experimental 140 MeV; f_pi = 130(3) MeV vs experimental 130.2 MeV. Agreement within uncertainties validates the calculation.

## Worked Example: Detecting and Correcting Topology Freezing at Fine Lattice Spacing

**Problem:** Compute the topological susceptibility chi_t = <Q^2>/V of SU(3) Yang-Mills theory (pure gauge, no dynamical fermions) and demonstrate topology freezing at fine lattice spacing. Show how to detect frozen topology, estimate the bias, and apply open boundary conditions as a mitigation. This example targets the most insidious lattice QCD error: simulations that appear thermalized for local observables but have completely frozen topological charge.

### Step 1: Setup and Topology Measurement

Pure SU(3) gauge theory with Wilson plaquette action at three lattice spacings:

| Ensemble | beta | a (fm) | L^3 x T | V (fm^4) | N_configs |
|----------|------|--------|---------|----------|-----------|
| Coarse | 6.0 | 0.093 | 16^3 x 32 | 3.2 | 5000 |
| Medium | 6.2 | 0.068 | 24^3 x 48 | 5.5 | 5000 |
| Fine | 6.5 | 0.048 | 32^3 x 64 | 5.7 | 5000 |

Physical volume is roughly matched across ensembles. HMC algorithm with trajectory length tau = 1, Omelyan integrator with dt = 0.02/beta.

Topological charge measured via gradient flow: flow to t_flow = 2.0 * t_0 (where t_0 is the Wilson flow reference scale), then round Q to the nearest integer.

### Step 2: Topology History

**Coarse (a = 0.093 fm):** Q fluctuates freely between -5 and +5. Average: <Q> = 0.02 +/- 0.05. Autocorrelation time: tau_Q ~ 8 configurations. With 5000 configs, N_eff = 5000/16 ~ 310 independent measurements.

```
Q history (first 100 configs): 2, 3, 2, 1, 0, -1, 0, 2, 3, 2, 1, -1, -2, -1, 0, 1, ...
(Q changes sign frequently — topology is sampling correctly)
```

**Medium (a = 0.068 fm):** Q fluctuates but more slowly. Autocorrelation time: tau_Q ~ 85 configurations. With 5000 configs, N_eff ~ 29. Still sampling, but marginally.

```
Q history (first 100 configs): 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, ...
(Q changes rarely — topology is slow but not completely frozen)
```

**Fine (a = 0.048 fm):** Q is FROZEN. The entire run of 5000 configurations stays at Q = 2. Autocorrelation time: tau_Q > 5000 (cannot be estimated — no Q change observed). N_eff = 0 for topology.

```
Q history (all 5000 configs): 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, ...
(Q never changes — topology is completely frozen)
```

### Step 3: The Trap — Local Observables Look Fine

Despite frozen topology at a = 0.048 fm, local observables appear well-behaved:

| Observable | tau_auto (configs) | Apparently converged? |
|-----------|-------------------|----------------------|
| Plaquette <P> | 2 | Yes |
| Wilson flow E(t_0) | 5 | Yes |
| Polyakov loop | 12 | Yes |
| Topological charge Q | > 5000 | NO |

**This is the trap.** A simulation that monitors only plaquette and energy would conclude that 5000 configurations is more than sufficient. The topological charge — the only diagnostic that reveals the problem — is not routinely monitored by many lattice codes.

### Step 4: Bias from Fixed Topology

At fixed Q = 2, any observable that depends on the topological sector is biased. The topological susceptibility:

| Ensemble | <Q^2>/V (fm^{-4}) | chi_t^{1/4} (MeV) | Expected chi_t^{1/4} |
|----------|-------------------|--------------------|---------------------|
| Coarse (a = 0.093 fm) | (6.2 +/- 0.4) x 10^{-4} | 192 +/- 3 | 191 +/- 5 |
| Medium (a = 0.068 fm) | (5.8 +/- 1.2) x 10^{-4} | 188 +/- 10 | 191 +/- 5 |
| Fine (a = 0.048 fm) | 4/(5.7 fm^4) = 7.0 x 10^{-4} | 196 | WRONG — fixed Q artifact |

The fine ensemble gives chi_t = Q^2/V = 4/V, which is an artifact of being stuck at Q = 2. The correct chi_t requires sampling over all Q sectors: chi_t = <Q^2>/V where the average is over the full Q distribution.

**Fixed-topology correction (Brower et al.):** For an observable O measured at fixed Q:

```
<O>_Q = <O>_true + (1/2V chi_t) * d^2<O>/dtheta^2 |_{theta=0} * (Q^2/chi_t V - 1) + O(1/V^2)
```

This correction requires knowing chi_t (the thing we are trying to measure) and the theta-dependence of the observable. For chi_t itself, the correction is circular without additional input from other ensembles.

### Step 5: Open Boundary Conditions as Mitigation

Replace periodic temporal boundary conditions with open (Dirichlet) BC in time. Topology can now flow in and out through the temporal boundaries, eliminating freezing.

Run the fine ensemble (beta = 6.5, a = 0.048 fm, 32^3 x 64) with open temporal BC:

```
Q history (first 100 configs): 1, 0, 1, 2, 1, 0, -1, 0, 1, 1, 0, -1, -2, -1, 0, ...
(Q fluctuates freely despite fine lattice spacing)
```

Autocorrelation time for Q with open BC: tau_Q ~ 15 configurations (comparable to coarse ensemble with periodic BC).

**Cost of open BC:**
- No translation invariance in time direction — cannot average correlators over time. Must discard ~ sqrt(8 t_flow) / a timeslices near each boundary (~5-10 slices) where boundary effects dominate.
- Effective temporal extent reduced from T to T - 2*boundary_region.
- Momentum is not quantized in the temporal direction — Fourier analysis requires modified techniques.

**chi_t with open BC at a = 0.048 fm:**
- <Q^2>/V = (5.9 +/- 0.3) x 10^{-4} fm^{-4}
- chi_t^{1/4} = 190 +/- 2 MeV
- Consistent with the coarse and medium ensembles and the expected value of 191 MeV.

### Verification

1. **Topology autocorrelation is the primary diagnostic.** Before reporting any result, plot the topology history Q vs configuration number. If Q does not change sign at least ~10 times during the run, the topological sampling is insufficient. This check costs nothing (the gradient flow for Q is computed anyway for scale setting) and catches the most common systematic error in fine-lattice simulations.

2. **Compare periodic and open BC.** For local observables (plaquette, hadron masses) measured far from the boundaries, periodic and open BC should agree within statistical errors. If they disagree, the measurement region is too close to the open boundary. Move the measurement region inward.

3. **Scaling of tau_Q with lattice spacing.** The topology autocorrelation time scales as tau_Q ~ exp(const / a^2). Plot ln(tau_Q) vs 1/a^2. The data should fall on a line. Deviation suggests the topology measurement itself has issues (e.g., insufficient gradient flow time, so Q is not an integer to within rounding tolerance).

4. **Cross-check chi_t from the gradient flow plateau.** At flow time t, chi_t(t) = <Q(t)^2>/V should plateau for t_0 < t < 2*t_0 (above UV artifacts, below finite-volume artifacts). If chi_t(t) depends strongly on t in this range, the flow has not sufficiently smoothed the UV fluctuations.

5. **Consistency across lattice spacings.** After continuum extrapolation (chi_t(a) = chi_t(0) + c_a * a^2 + ...), the result from all ensembles should agree. If the fine ensemble is an outlier, topology freezing is the most likely cause.

6. **Do NOT ignore the problem.** A common practice: compute chi_t only on coarse ensembles and skip the fine ensemble, or use chi_t from the literature. This is acceptable for quantities that are insensitive to topology (many hadron masses), but not for CP-violating observables, the axial anomaly, or the theta-vacuum structure.

## Worked Example: Wilson Loop vs Polyakov Loop — Confinement Diagnostics and Strong Coupling Expansion

**Problem:** Compute the static quark potential V(R) from Wilson loops and the Polyakov loop expectation value to diagnose confinement in SU(3) pure gauge theory. Demonstrate the two most common errors: (1) confusing the Wilson loop (spatial, measures potential) with the Polyakov loop (temporal, measures free energy / deconfinement order parameter), and (2) incorrect strong coupling expansion that gives qualitatively wrong results beyond leading order.

### Step 1: Definitions and Physical Meaning

**Wilson loop W(R, T):** A rectangular R x T loop of gauge links in a spatial-temporal plane. For large T, it decays as:

```
<W(R, T)> ~ exp(-V(R) * T)
```

where V(R) is the static quark-antiquark potential. At zero temperature, V(R) = sigma * R - alpha/R + c (linear confinement + Coulomb + constant). The string tension sigma ~ (440 MeV)^2 ~ 0.18 GeV^2 characterizes the confining flux tube.

**Polyakov loop L:** The trace of the product of temporal gauge links wrapping around the periodic time direction:

```
L(x) = (1/N_c) Tr prod_{t=0}^{N_t-1} U_0(x, t)
```

The Polyakov loop expectation value <|L|> is the order parameter for the deconfinement phase transition:
- Confined phase (T < T_c): <L> = 0 (center symmetry preserved, free energy of isolated quark = infinity)
- Deconfined phase (T > T_c): <L> != 0 (center symmetry broken, finite quark free energy)

**The confusion:** Both involve products of gauge links around closed paths. But Wilson loops probe the potential between a quark-antiquark pair (both present), while the Polyakov loop probes the free energy of a single isolated quark. They answer different physical questions.

### Step 2: Lattice Setup

SU(3) pure gauge theory with Wilson plaquette action:

| Ensemble | beta | a (fm) | Lattice | T (MeV) | Phase |
|----------|------|--------|---------|---------|-------|
| Cold | 6.0 | 0.093 | 24^3 x 48 | ~44 | Confined |
| Hot-below | 6.0 | 0.093 | 24^3 x 6 | ~353 | Confined (T < T_c ~ 270 MeV for N_t=6) |
| Hot-above | 6.0 | 0.093 | 24^3 x 4 | ~530 | Deconfined (T > T_c) |

**Wait — the Hot-below ensemble.** At beta = 6.0 and N_t = 6, the temperature is T = 1/(N_t * a) = 1/(6 * 0.093 fm) = 354 MeV. The deconfinement transition for SU(3) pure gauge at N_t = 6 occurs at beta_c ~ 5.89. Since beta = 6.0 > beta_c, we are actually in the DECONFINED phase. This is the first common error: misidentifying the phase because the critical coupling depends on N_t.

**Corrected ensembles:**

| Ensemble | beta | a (fm) | Lattice | T (MeV) | Phase |
|----------|------|--------|---------|---------|-------|
| Cold | 6.0 | 0.093 | 24^3 x 48 | ~44 | Confined |
| Hot-below | 5.85 | 0.105 | 24^3 x 6 | ~313 | Confined (beta < beta_c ~ 5.89) |
| Hot-above | 6.0 | 0.093 | 24^3 x 6 | ~354 | Deconfined (beta > beta_c ~ 5.89) |

### Step 3: Wilson Loop Measurement and Potential Extraction

Compute W(R, T) for R = 1..12 and T = 1..12 (in lattice units) on the Cold ensemble. Use APE or HYP smearing on spatial links to improve the overlap with the ground state.

**Extract V(R) from the effective potential:**

```
V_eff(R, T) = ln[W(R, T) / W(R, T+1)]
```

Look for a plateau in T at each R. Results (Cold ensemble, in lattice units):

| R/a | V(R) * a | sigma * a^2 fit |
|-----|----------|-----------------|
| 1 | 0.36(1) | — |
| 2 | 0.55(1) | — |
| 3 | 0.69(1) | — |
| 4 | 0.81(1) | — |
| 6 | 1.03(2) | 0.058(2) |
| 8 | 1.24(3) | 0.060(2) |
| 10 | 1.46(5) | 0.061(3) |

Fit V(R) = sigma * R - alpha / R + c for R >= 4: sigma * a^2 = 0.060(2), alpha = 0.30(2), consistent with the Luscher term alpha = pi/12 ~ 0.26.

**Physical string tension:** sigma = 0.060 / (0.093)^2 fm^{-2} = 6.94 fm^{-2} = (424 MeV)^2. Expected: (440 MeV)^2. Agreement is within the 10% expected from quenched (no dynamical fermions) pure gauge theory.

### Step 4: Polyakov Loop and Deconfinement

**Cold ensemble (T ~ 44 MeV):** <|L|> = 0.001(1). Consistent with zero — confined phase. Center symmetry is preserved.

**Hot-below ensemble (T ~ 313 MeV, beta = 5.85):** <|L|> = 0.003(2). Still consistent with zero — confined phase, just below T_c.

**Hot-above ensemble (T ~ 354 MeV, beta = 6.0, N_t = 6):** <|L|> = 0.42(3). Non-zero — deconfined phase. Center symmetry is spontaneously broken.

### Step 5: Strong Coupling Expansion Error

The strong coupling expansion (small beta, large g) computes Wilson loops as a sum over minimal surfaces tiled by plaquettes. At leading order:

```
<W(R, T)> ~ (beta / 18)^{R*T} * [1 + O(beta)]
```

This gives V(R) ~ -R * ln(beta/18), which is linear in R — confinement at strong coupling.

**The error:** Naively extending this result to beta = 6.0 (the typical simulation value):

```
V_strong(R) = -R * ln(6.0/18) = -R * ln(1/3) = R * ln(3) ~ 1.10 * R
```

This gives sigma * a^2 ~ 1.10, which is 18x larger than the measured value of 0.060. The strong coupling expansion is quantitatively useless at beta = 6.0.

**Why the expansion fails:** The strong coupling expansion is an expansion in beta = 6/g^2. At beta = 6.0 (g^2 = 1), the expansion parameter is of order 1. The expansion converges only for beta << 1 (g^2 >> 6). At physical lattice spacings (beta ~ 5.7-6.5), the system is far from the strong coupling regime and the expansion gives wildly wrong quantitative results.

**The subtler error:** Some references extract the string tension from the strong coupling expansion and then claim "confinement is proven." The strong coupling expansion does show area-law behavior (confinement) at strong coupling. But this does NOT prove confinement at weak coupling (the continuum limit). The strong and weak coupling regimes may or may not be analytically connected — this is related to the unsolved Yang-Mills mass gap problem. Using strong coupling results to make quantitative predictions at physical beta values is incorrect.

### Verification

1. **Wilson loop vs Polyakov loop:** The Wilson loop W(R, T) at zero temperature gives the static potential V(R) = sigma * R + ... . The Polyakov loop <|L|> gives the deconfinement order parameter. Do NOT extract the string tension from the Polyakov loop correlator <L(x) L^dag(y)> ~ exp(-F(|x-y|)/T) and call it the same sigma — F(R) is the free energy, not the potential. At T > 0, F(R) < V(R) due to entropy contributions. At T > T_c, F(R) saturates to a constant (no confinement), even though V(R) from Wilson loops at the same coupling still rises linearly if T is large enough.

2. **Critical coupling is N_t-dependent.** The deconfinement transition occurs at beta_c(N_t) which increases with N_t. For SU(3): beta_c(4) ~ 5.69, beta_c(6) ~ 5.89, beta_c(8) ~ 6.06. Always look up beta_c for your specific N_t before interpreting Polyakov loop results.

3. **Strong coupling expansion convergence.** The expansion converges for beta < beta_roughening ~ 5.5 for SU(3). Beyond this value, the expansion breaks down qualitatively (the roughening transition changes the interface physics). Never use strong coupling expansion results quantitatively at beta > 5.5.

4. **Smearing artifacts.** APE/HYP smearing improves the Wilson loop signal but can introduce systematic effects at small R. Always compare smeared and unsmeared results at R >= 3-4 to verify the smearing does not shift the extracted potential.

5. **Excited state contamination in Wilson loops.** The effective potential V_eff(R, T) approaches V(R) only for T >> 1/Delta E, where Delta E is the gap to the first excited state of the flux tube. At large R, Delta E ~ pi/R (Nambu-Goto prediction), so larger R requires larger T for ground state isolation. If V_eff(R, T) has not plateaued, the extracted V(R) is contaminated by excited string states.

## Common Pitfalls

- **Ignoring topology freezing.** The simulation looks thermalized for local observables but the topological charge is stuck. All CP-odd quantities and anything sensitive to the axial anomaly will be wrong. Check Q history at every lattice spacing.
- **Wrong continuum limit ordering.** The limits a -> 0, m_q -> m_q^phys, and V -> infinity do not commute in general. Standard practice: take V -> infinity and m_q -> m_q^phys at fixed a, then extrapolate a -> 0. Reversing the order can introduce uncontrolled errors.
- **Signal-to-noise problem.** The signal for baryonic correlators decays as exp(-m_B * t) but the noise decays as exp(-3/2 * m_pi * t). At large t, noise dominates exponentially. No amount of statistics fixes this — use variance reduction techniques (distillation, momentum smearing, signal-to-noise optimization).
- **Excited state contamination.** Euclidean correlators receive contributions from all states, not just the ground state. At small source-sink separations, excited states bias the extracted mass/matrix element upward. Use multiple source-sink separations and verify plateau stability, or use the generalized eigenvalue problem (GEVP) with a variational basis.
