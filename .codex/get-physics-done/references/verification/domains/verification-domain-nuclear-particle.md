---
load_when:
  - "nuclear physics verification"
  - "particle physics verification"
  - "phenomenology"
  - "global fit"
  - "likelihood"
  - "SMEFT"
  - "recast"
  - "collider physics"
  - "parton distribution"
  - "CKM matrix"
  - "chiral perturbation"
  - "heavy quark"
  - "cross section"
tier: 2
context_cost: large
---

# Verification Domain — Nuclear & Particle Physics

Crossing symmetry, chiral power counting, parton sum rules, heavy quark symmetry, CKM unitarity, and collider physics consistency checks.

**Load when:** Working on nuclear structure, hadron physics, collider phenomenology, flavor physics, neutrino physics, or BSM model building.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `references/verification/domains/verification-domain-qft.md` — QFT (for Feynman diagrams, renormalization, Ward identities)
- `../core/verification-numerical.md` — convergence, statistical validation

---

<crossing_and_unitarity>

## Crossing Symmetry and Partial Wave Unitarity

**Crossing symmetry:**

```
For 2->2 scattering A + B -> C + D:
  A(s, t, u) must be related to A(t, s, u) by particle exchange.
  For identical particles: A(s, t, u) = A(t, s, u) = A(s, u, t) (full crossing symmetry).
  Mandelstam constraint: s + t + u = sum of squared masses.

Verification:
1. COMPUTE: A(s,t,u) at test values. Exchange s <-> t. Compare with expected crossed amplitude.
2. COMPUTE: Verify s + t + u = m_1^2 + m_2^2 + m_3^2 + m_4^2 at every kinematic point.
3. For charged particles: crossing relates particle to antiparticle amplitudes (not same amplitude).
```

**Partial wave unitarity:**

```
|a_l(s)| <= 1    (elastic unitarity)
sigma_l <= 4*pi*(2l+1)/k^2    (per-partial-wave cross section bound)

For resonances: a_l = (Gamma_l/2) / (E_R - E - i*Gamma/2)
  At resonance (E = E_R): |a_l| = 1 (unitarity saturated)
  Below resonance: |a_l| < 1

Verification: Compute |a_l| for each partial wave. Any |a_l| > 1 indicates broken unitarity.
```

</crossing_and_unitarity>

<chiral_perturbation>

## Chiral Perturbation Theory Checks

**Power counting:**

```
Weinberg formula: D = 2 + 2L + sum_d (d-2)*N_d
  D = chiral order, L = loops, N_d = number of vertices from order-d Lagrangian.

LO (D=2): tree level from L_2
NLO (D=4): one loop from L_2 + tree from L_4
NNLO (D=6): two loops from L_2 + one loop from L_4 + tree from L_6

Verification:
1. COMPUTE: D for every diagram. Verify no diagram is included at the wrong order.
2. CHECK: At O(p^4), ALL one-loop + ALL L_4 tree diagrams must be included. Missing any -> inconsistent.
3. COMPUTE: NLO correction size. Should be O(m_pi^2/Lambda_chi^2) ~ 1-2% for well-converging quantities.
   If NLO correction > 30%: convergence is slow (check for enhancement from chiral logs or resonances).
```

**Low-energy constant (LEC) natural size:**

```
LECs in ChPT at order p^4: l_1, l_2, ..., l_7 (SU(2)) or L_1, ..., L_10 (SU(3)).

Natural size estimate (NDA): |L_i^r(mu)| ~ 1/(4*pi*f_pi)^2 ~ 7 * 10^{-4}

Verification:
1. COMPUTE: Extracted LEC values. Compare with PDG / FLAG lattice averages.
2. CHECK: LECs far from natural size (|L_i| > 10 * NDA) may indicate: fine-tuning, resonance
   saturation (rho meson dominance), or extraction error.
3. COMPUTE: l_bar_i = l_i^r + gamma_i * ln(m_pi^2/mu^2) (scale-independent). These should be O(1).
```

</chiral_perturbation>

<parton_physics>

## Parton Distribution and Fragmentation Functions

**Parton sum rules:**

```
Momentum sum rule: integral_0^1 x * [sum_q (q(x) + qbar(x)) + g(x)] dx = 1
  (quarks + gluons carry all the proton momentum)

Baryon number: integral_0^1 [u(x) - ubar(x)] dx = 2  (proton has 2 up quarks net)
               integral_0^1 [d(x) - dbar(x)] dx = 1  (proton has 1 down quark net)
Strangeness:   integral_0^1 [s(x) - sbar(x)] dx = 0  (no net strangeness)

Gottfried sum rule: integral_0^1 [F_2^p(x) - F_2^n(x)] dx / x = 1/3 + (2/3) integral [ubar - dbar] dx
  For flavor-symmetric sea (ubar = dbar): Gottfried sum = 1/3.
  Experimental: S_G ~ 0.235 (NMC), indicating ubar != dbar (sea asymmetry).

Verification:
1. COMPUTE: All sum rules numerically from your PDFs. Momentum sum must = 1 +/- 0.01.
2. Baryon number must be EXACT (integers). Deviation > 0.001 indicates PDF normalization error.
3. DGLAP evolution must PRESERVE these sum rules at all scales Q^2.
```

**Bjorken scaling violations:**

```
At leading order, structure functions F_2(x, Q^2) are Q^2-independent (Bjorken scaling).
QCD corrections introduce logarithmic Q^2 dependence: d*F_2/d*ln(Q^2) ~ alpha_s * [splitting functions (x) P_qq(x)]

Verification:
1. COMPUTE: d*ln(F_2)/d*ln(Q^2) at several x values. Must be consistent with known splitting functions.
2. At small x: F_2 should RISE with Q^2 (gluon-driven growth). At large x: F_2 should DECREASE (quark radiation).
3. The sign pattern of scaling violations distinguishes gluon-dominated from quark-dominated regimes.
```

**Fragmentation function positivity:**

```
D_h^q(z, Q^2) >= 0 for all z, Q^2 (probability interpretation)
Momentum sum: integral_0^1 z * sum_h D_h^q(z) dz <= 1 (fragmenting parton can't produce more energy than it has)

Verification: Check D >= 0 everywhere. Negative values indicate fit instability or wrong parameterization.
```

</parton_physics>

<flavor_physics>

## CKM Matrix and Heavy Quark Symmetry

**CKM unitarity:**

```
The CKM matrix V is unitary: V*V^dagger = I

Row unitarity:
  |V_ud|^2 + |V_us|^2 + |V_ub|^2 = 1    (1st row: 0.9985 +/- 0.0005 experimentally)
  |V_cd|^2 + |V_cs|^2 + |V_cb|^2 = 1    (2nd row)

Column unitarity:
  |V_ud|^2 + |V_cd|^2 + |V_td|^2 = 1    (1st column)

Unitarity triangles:
  V_ud*V_ub* + V_cd*V_cb* + V_td*V_tb* = 0  (the "bd" unitarity triangle)

Verification:
1. COMPUTE: Row/column unitarity sums. Deviation from 1 beyond experimental errors
   indicates: wrong CKM element values, or BSM physics.
2. COMPUTE: Unitarity triangle angles alpha + beta + gamma = pi. Sum != pi -> BSM.
3. Jarlskog invariant: J = Im(V_us V_cb V_ub* V_cs*) ~ 3e-5. Measures CP violation strength.
```

**Heavy quark symmetry (HQS) relations:**

```
In the m_Q -> infinity limit, heavy quark spin and flavor symmetries relate form factors:

For B -> D(*) transitions, the Isgur-Wise function xi(w) satisfies:
  xi(1) = 1   (normalization at zero recoil, EXACT from Luke's theorem)
  xi(w) <= 1  (bounded, probability interpretation)
  xi'(1) < 0  (slope at zero recoil is negative)

Verification:
1. COMPUTE: Form factors at w = 1 (zero recoil). Any form factor ratio fixed by HQS must be verified.
2. CHECK: 1/m_Q corrections from the chromomagnetic operator. These break spin symmetry and split
   B and B* masses: m_{B*} - m_B = 46 MeV (known). Verify this splitting is consistent with your calculation.
3. COMPUTE: |V_cb| from B -> D(*) l nu. Inclusive and exclusive determinations must agree within errors.
```

**Isospin decomposition:**

```
For hadronic processes, decompose amplitudes into isospin eigenstates.

Example: K -> pi pi:
  A(K^0 -> pi+ pi-) = sqrt(2/3) A_0 + sqrt(1/3) A_2
  A(K^0 -> pi^0 pi^0) = sqrt(2/3) A_0 - 2*sqrt(1/3) A_2

where A_I are amplitudes with definite isospin I.

Verification:
1. COMPUTE: Extract A_0 and A_2 from the physical amplitudes. Verify |A_0/A_2| >> 1 (Delta I = 1/2 rule).
2. CHECK: CP violation in K decays: epsilon = (A_0_bar/A_0 - 1) / (1 + ...) ~ 2.2e-3.
3. Watson's theorem: below inelastic threshold, the phase of A_I equals the pi-pi scattering phase shift delta_I.
```

</flavor_physics>

<matching_and_eft>

## Matching and EFT Scale Independence

**Matching scale independence:**

```
Physical observables must be independent of the matching scale mu:
  O_phys = C_i(mu) * <O_i>(mu) + higher-order corrections

The mu-dependence of Wilson coefficients C_i(mu) must cancel against the mu-dependence of
matrix elements <O_i>(mu) to the working order.

Verification:
1. COMPUTE: O_phys at mu = M_W, M_W/2, and 2*M_W. The variation must be within the estimated
   higher-order uncertainty (typically the next order in alpha_s).
2. If variation exceeds the estimated uncertainty: a log has been missed in the RG running,
   or the matching was done at the wrong order.
```

</matching_and_eft>

<phenomenology_likelihoods>

## Likelihood, Covariance, and EFT Validity Checks

Phenomenology constraints live or die on the exact observable definition and the correlated uncertainty model. A quoted limit or best fit without a clear likelihood object is not a finished result.

```
Inference chain:
  model / EFT parameters
    -> running / matching
    -> theory prediction
    -> detector or hadronic layer
    -> covariance / likelihood
    -> constraint or posterior
```

**Verification:**

```
1. Match the theory prediction to the published observable definition: fiducial, unfolded, detector-level, angular binning, and normalization.
2. Use the full covariance matrix or public likelihood when available. Do not collapse correlated systematics into a single uncorrelated error bar.
3. Propagate scale, PDF, hadronic, lattice, and parametric uncertainties separately from experimental systematics, and verify they are not double counted.
4. In EFT fits, state the operator basis, matching scale, running, truncation order, and any energy cut used to justify EFT validity.
5. For recasts, reproduce benchmark cutflows, efficiencies, or SM yields before scanning new-physics parameter points.
6. In global fits, inspect parameter correlations and flat directions. One-operator-at-a-time bounds are not generic multi-parameter constraints.
```

</phenomenology_likelihoods>

## Worked Examples

### CKM unitarity check catches BSM sensitivity

```python
import numpy as np

# PDG 2024 values
V_ud = 0.97373
V_us = 0.2243
V_ub = 0.00382

row_sum = V_ud**2 + V_us**2 + V_ub**2
print(f"First row unitarity: {row_sum:.6f}")
print(f"Deviation from 1: {1 - row_sum:.6f}")
# Expected: 0.9985 +/- 0.0005 (known 3-sigma tension: "Cabibbo angle anomaly")
# If your calculation gives exactly 1.0: you may have used incorrect CKM values
# or forced unitarity that should be tested
```
