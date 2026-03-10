---
load_when:
  - "resummation"
  - "Borel summation"
  - "Pade approximant"
  - "asymptotic series"
  - "divergent series"
  - "conformal mapping"
  - "optimized perturbation theory"
  - "Borel transform"
  - "renormalon"
tier: 2
context_cost: medium
---

# Resummation Protocol

Perturbative series in physics are generically divergent (asymptotic). The coefficients grow as n! or faster, and the series has zero radius of convergence. Resummation methods extract finite, physically meaningful results from these divergent series. This protocol covers Borel summation, Pade approximants, conformal mapping, and optimized perturbation theory.

## Related Protocols

- See `perturbation-theory.md` for generating the perturbative series that needs resummation
- See `renormalization-group.md` for RG improvement (a complementary approach to large-log resummation)
- See `analytic-continuation.md` for analytic structure and branch cuts relevant to Borel transforms

## When to Use Resummation

1. **Factorial divergence:** Coefficients grow as c_n ~ A^n * n! * n^b — the hallmark of an asymptotic series (appears in QFT, quantum mechanics, statistical mechanics)
2. **Renormalons:** Perturbative series in QCD have IR and UV renormalon singularities on the positive Borel axis — these cause irreducible ambiguity of order Lambda_QCD^p / Q^p
3. **Large logarithms already resummed:** After RG improvement, residual series may still diverge factorially
4. **Instantons/non-perturbative effects:** The factorial divergence encodes information about non-perturbative saddle points (instantons, bounces). Resummation connects perturbative and non-perturbative physics
5. **Low-order truncation unreliable:** When only a few terms are known but their growth pattern suggests divergence

## Step-by-Step: Borel Summation

### Step 1: Construct the Borel Transform

Given a formal power series f(g) = sum_{n=0}^{inf} c_n * g^n with c_n ~ n!, define the Borel transform:

```
B(t) = sum_{n=0}^{inf} c_n / n! * t^n
```

This has a FINITE radius of convergence (the n! growth is tamed by the 1/n! denominator).

**Checkpoint:** Verify that B(t) converges for |t| < t_0 where t_0 is set by the nearest singularity. If the original series had c_n ~ A^n * n!, then B(t) has a singularity at t = 1/A.

### Step 2: Identify Borel Plane Singularities

Map all singularities of B(t) in the complex t-plane:

- **UV renormalons** (QFT): singularities at t = -k/(2*beta_0) for k = 1, 2, ... on the NEGATIVE real axis
- **IR renormalons** (QFT): singularities at t = +k/(2*beta_0) for k = 1, 2, ... on the POSITIVE real axis
- **Instanton singularities:** at t = n * S_inst for n = 1, 2, ... where S_inst is the instanton action
- **Branch cuts vs poles:** Determine whether singularities are poles (removable by Cauchy principal value) or branch points (produce ambiguity)

**Checkpoint:** If singularities lie on the POSITIVE real axis (the integration contour), the Borel sum is ambiguous. The imaginary part of the ambiguity has a physical interpretation (non-perturbative effects). This ambiguity must cancel against explicit non-perturbative contributions.

### Step 3: Perform the Borel Integral

The Borel-resummed function is:

```
f_B(g) = integral_0^{inf} dt * exp(-t/g) * B(t)
```

If B(t) has no singularities on the positive real axis, this integral is well-defined and gives a unique result (the series is Borel summable).

If there ARE singularities on the positive real axis:
- Take the integral along a contour slightly above (or below) the real axis
- The imaginary part Im[f_B(g)] ~ exp(-1/(A*g)) gives the non-perturbative ambiguity
- This must be cancelled by adding explicit non-perturbative contributions (instantons, condensates)

### Step 4: Verify the Result

1. **Asymptotic check:** Expand f_B(g) in powers of g. The expansion must reproduce the original coefficients c_n to the order they are known.
2. **Non-perturbative structure:** If the ambiguity is ~ exp(-S/g), verify that S matches the known instanton action or condensate scale.
3. **Physical consistency:** The resummed result should be real for physical values of the coupling. If Im[f_B] != 0, identify the non-perturbative sector that cancels it.

## Step-by-Step: Pade Approximants

### When to Use

- Only a few perturbative coefficients are known (3-10 terms)
- Borel singularity structure is unknown
- Quick estimate of the all-orders sum is needed

### Construction

Given N known coefficients c_0, ..., c_{N-1}, construct the [L/M] Pade approximant:

```
[L/M](g) = P_L(g) / Q_M(g)
```

where P_L is a polynomial of degree L, Q_M of degree M, Q_M(0) = 1, and L + M + 1 = N.

### Which Pade to Use

- **[N/2, N/2] or [(N-1)/2, (N+1)/2]:** Near-diagonal Pade approximants are most robust
- **Pade-Borel:** Apply Pade to the Borel transform B(t), THEN perform the Borel integral. This combines the convergence acceleration of Pade with the resummation power of Borel

### Verification

1. **Pade table stability:** Compute [L/M] for multiple (L,M) with L+M = N-1. If results vary wildly, the Pade method is unreliable for this series.
2. **Spurious poles:** Check that no Pade pole lies near the physical region. If a pole appears at a coupling value of interest, that Pade order is unreliable.
3. **Convergence with order:** As more terms are added, the Pade should converge. If it oscillates, the series has structure (e.g., branch cuts) that Pade handles poorly.

## Step-by-Step: Conformal Mapping

### When to Use

- Borel plane singularity locations are known (at least approximately)
- Need to accelerate convergence of the Borel series
- Pade alone is insufficient due to branch cuts

### Procedure

1. Map the Borel plane cut(s) to the unit circle boundary via a conformal transformation w(t). For a single cut starting at t = t_0 on the positive real axis:

```
w(t) = (sqrt(1 + t/t_0) - 1) / (sqrt(1 + t/t_0) + 1)
```

This maps t in [0, inf) to w in [0, 1) and the cut [t_0, inf) to the unit circle |w| = 1.

2. Re-expand B(t(w)) in powers of w. The new series converges inside the unit disk (which maps to the entire cut Borel plane).

3. Perform the Borel integral in the w variable.

**Checkpoint:** The conformal mapping must be chosen based on the ACTUAL singularity structure. Using the wrong t_0 gives incorrect results. If multiple singularities exist, the mapping must account for all of them.

## Step-by-Step: Optimized Perturbation Theory (OPT)

### When to Use

- Need a non-perturbative estimate from low-order perturbation theory
- Applicable when there is an artificial parameter that can be optimized (e.g., a mass scale, a variational parameter)

### Procedure (Principle of Minimal Sensitivity)

1. Introduce an arbitrary parameter lambda into the perturbative expansion such that the exact result is lambda-independent.
2. Truncate at order N: f_N(g, lambda).
3. Choose lambda by the **principle of minimal sensitivity (PMS):** d(f_N)/d(lambda) = 0. This makes the truncated result locally stationary, mimicking the exact lambda-independence.
4. Alternatively, use the **fastest apparent convergence (FAC)** criterion: choose lambda so that the N-th order correction vanishes.

### Verification

1. **Convergence with order:** The PMS value should stabilize as N increases.
2. **Lambda independence:** Higher orders should give smaller residual lambda dependence.
3. **Comparison with exact results:** If known (e.g., anharmonic oscillator), verify accuracy improves with order.

## Common Pitfalls

1. **Borel non-summability mistaken for calculation error.** If the Borel integral diverges on the positive real axis, this is NOT an error — it signals genuine non-perturbative ambiguity. The ambiguity has physical meaning and must be resolved by including non-perturbative sectors (instantons, condensates).

2. **Stokes phenomenon.** The asymptotic expansion of a function can differ in different sectors of the complex plane. When crossing a Stokes line, exponentially small terms (e.g., exp(-1/g)) switch on or off. Ignoring this gives discontinuous resummed results.

3. **Wrong growth rate assumption.** Not all divergent series have n! growth. Alternating series, series with (2n)! growth, or sub-factorial growth require different resummation strategies. Always determine the large-order behavior BEFORE choosing a method.

4. **Pade poles in the physical region.** A spurious Pade pole near the coupling of interest invalidates that particular [L/M] approximant. Use multiple Pade orders and check for pole stability.

5. **Conformal mapping with wrong singularity.** The conformal mapping requires knowledge of the nearest Borel singularity. Using an incorrect value gives a convergent but WRONG result. Cross-check the singularity location against large-order behavior: c_n ~ (1/t_0)^n * n^b * n! determines t_0.

6. **Ignoring sub-leading non-perturbative sectors.** The leading instanton gives the dominant non-perturbative effect ~ exp(-S_1/g), but multi-instanton effects ~ exp(-k*S_1/g) also contribute and may be needed for precise results.

## Worked Example: Anharmonic Oscillator Ground State Energy via Borel-Pade

**Problem:** Compute the ground state energy of the quantum anharmonic oscillator H = p^2/2 + x^2/2 + g*x^4 for g = 1 (strong coupling) using the first 10 perturbative coefficients.

### Step 1: The Perturbative Series

The ground state energy as a function of coupling g:

```
E(g) = 1/2 + 3/4 g - 21/8 g^2 + 333/16 g^3 - 30885/128 g^4 + ...
```

The coefficients grow as c_n ~ (-1)^n * (6/pi)^{1/2} * 3^n * Gamma(n + 1/2) — factorial divergence with alternating signs.

### Step 2: Borel Transform

```
B(t) = sum_{n=0} c_n / Gamma(n + 1/2) * t^n
```

(Using Gamma(n+1/2) instead of n! because the large-order behavior is ~ Gamma(n+1/2).)

The nearest Borel singularity is at t = -1/3 (on the NEGATIVE real axis — the series IS Borel summable because the singularity is NOT on the positive axis). The singularity comes from the instanton at the top of the inverted potential barrier.

### Step 3: Pade-Borel Resummation

Construct the [5/4] Pade approximant of B(t) using the 10 known coefficients. Then evaluate:

```
E_resummed(g) = integral_0^inf dt * exp(-t) * [5/4](g*t)
```

### Step 4: Numerical Result and Verification

For g = 1: E_resummed = 0.8038 (exact numerical: E_exact = 0.80377...).

**Verification checks:**
1. **Weak coupling:** At g = 0.01, the resummed result matches the 5th-order truncation to 10 digits.
2. **Strong coupling scaling:** For g >> 1, dimensional analysis gives E ~ g^{1/3}. The resummed result gives E(100) ~ 4.7, consistent with E ~ (3/4)^{1/3} * g^{1/3} * Gamma(1/3)/(sqrt(pi)) ~ 4.64 from WKB.
3. **Pade table stability:** [4/5], [5/4], and [3/6] all give E(1) between 0.803 and 0.805. Stable.
4. **No spurious poles:** The Pade denominator has no real positive roots (verified numerically). The approximant is smooth on the integration contour.
5. **Borel singularity location:** The Pade approximant of B(t) has a pole near t = -0.333, consistent with the known singularity at t = -1/3. This confirms the method is correctly capturing the analytic structure.
