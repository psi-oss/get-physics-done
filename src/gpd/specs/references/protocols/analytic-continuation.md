---
load_when:
  - "analytic continuation"
  - "Wick rotation"
  - "Matsubara frequency"
  - "spectral function"
  - "Kramers-Kronig"
  - "Euclidean to Minkowski"
  - "maximum entropy"
tier: 2
context_cost: medium
---

# Analytic Continuation Protocol

Analytic continuation (Minkowski <-> Euclidean, real-time <-> imaginary-time) is one of the most error-prone operations in theoretical physics. Sign errors, branch cut crossings, and wrong i*epsilon prescriptions produce results that look correct but are physically wrong.

## Related Protocols

- See `finite-temperature-field-theory.md` for Matsubara formalism and imaginary-time path integrals
- See `path-integrals.md` for Wick rotation in the path integral context
- See `integral-evaluation.md` for contour deformation and branch cut handling
- See `order-of-limits.md` for non-commuting limits in analytic continuation (e.g., epsilon -> 0 vs. volume -> infinity)

## Wick Rotation: Minkowski -> Euclidean

1. **State the rotation explicitly:** t = -i*tau (or t_E = i*t_M for the opposite convention). Write the Jacobian: dt = -i*d(tau).
2. **Substitute into the action and verify:**
   - The Euclidean action S_E must be REAL and BOUNDED BELOW for the path integral to converge
   - If S_E has an imaginary part or is unbounded below, the Wick rotation is invalid or requires modification
3. **Track every factor of i:** The measure d^d x_M -> i * d^d x_E. The exponent e^{iS_M} -> e^{-S_E}. Both factors of i must be accounted for.
4. **Verify the i*epsilon prescription is consistent:** In Minkowski, Feynman propagator has 1/(k^2 - m^2 + i*epsilon). After Wick rotation to Euclidean k_4 = i*k_0, this becomes 1/(k_E^2 + m^2) with NO i*epsilon needed (Euclidean propagator is manifestly positive).

## Matsubara Frequencies: Imaginary-Time -> Real Frequency

1. **State the boundary conditions:** Bosons: periodic in [0, beta], omega_n = 2*n*pi*T. Fermions: anti-periodic, omega_n = (2n+1)*pi*T.
2. **Perform the Matsubara sum** using standard techniques (contour integration, spectral representation). State which technique and verify the result has the correct high-frequency behavior.
3. **Analytic continuation to real frequency:** i*omega_n -> omega + i*eta (retarded) or i*omega_n -> omega - i*eta (advanced). The sign of eta determines causality.
4. **Verify the spectral function:** A(omega) = -2*Im[G^R(omega)] must be:
   - Real
   - Non-negative (for single-particle spectral function)
   - Satisfy the sum rule: integral d(omega)/(2*pi) A(omega) = 1

## Numerical Analytic Continuation

The inverse problem (Matsubara data -> real-frequency spectral function) is exponentially ill-conditioned: small noise in G(tau) produces large changes in A(omega). This is not a numerical limitation — it is a fundamental mathematical property.

1. **Maximum Entropy Method (MEM).** Bayesian inference with an entropic prior: maximize S[A] - (1/2) chi^2[A] where S is the Shannon/Jaynes entropy relative to a default model m(omega). The default model encodes prior knowledge (non-negativity, sum rule, known asymptotic behavior). Results depend on the default model — always test sensitivity by varying m(omega).
2. **Padé approximants.** Fit G(i*omega_n) to a ratio of polynomials P(z)/Q(z) and evaluate at z = omega + i*eta. Fast and model-independent, but: (a) extremely sensitive to noise — use only with high-precision Matsubara data, (b) the number of Padé coefficients controls the resolution — too many produces spurious peaks from noise, too few smooths out real features. Always vary the number of coefficients and check stability.
3. **Stochastic methods** (stochastic analytic continuation, stochastic optimization). Sample spectral functions A(omega) consistent with the Matsubara data within error bars. Advantage: provide uncertainty estimates on A(omega). Disadvantage: resolution limited by statistics and the number of Matsubara frequencies.
4. **Validation protocol for ANY numerical continuation:** (a) Generate synthetic data from a known A(omega) — compute G(tau) — add noise — recover A(omega). Verify the method reproduces the known spectrum. (b) Check the sum rule. (c) Check non-negativity. (d) Vary the noise level and verify the result degrades gracefully, not catastrophically.

## Dispersion Relations

Analytic continuation in disguise: relating real and imaginary parts of a causal response function via Kramers-Kronig relations.

1. **Kramers-Kronig relations.** For a causal response function chi(omega) analytic in the upper half-plane with chi(omega) -> 0 as |omega| -> infinity:
   - Re[chi(omega)] = (1/pi) P integral d(omega') Im[chi(omega')] / (omega' - omega)
   - Im[chi(omega)] = -(1/pi) P integral d(omega') Re[chi(omega')] / (omega' - omega)
   where P denotes the Cauchy principal value.
2. **Practical application.** Given experimental data for Im[chi(omega)] (e.g., absorption spectrum), compute Re[chi(omega)] and vice versa. Requires: data over a sufficiently wide frequency range (truncation errors from finite-range data), and the high-frequency asymptotic form to handle the tails.
3. **Subtracted dispersion relations.** If chi(omega) does not vanish fast enough at infinity, subtract known asymptotic terms: chi(omega) - chi_asymp(omega) satisfies a convergent dispersion relation. The number of subtractions needed equals the power-law growth at infinity.
4. **Sum rules from dispersion relations.** Integrating the Kramers-Kronig relation at specific frequencies gives sum rules: the f-sum rule (oscillator strength), the conductivity sum rule, the Weinberg sum rules in QCD. These provide parameter-free checks on spectral functions.

## Common Pitfalls

- **Branch cut crossing:** When rotating the k_0 contour, verify no poles or branch cuts are crossed. If they are, their contributions must be added separately.
- **Wrong sheet:** After continuation, verify you're on the physical sheet of any multi-valued function. The retarded Green's function is analytic in the upper half-plane.
- **Missing factors of i:** Every Wick rotation involves factors of i from the time coordinate, the measure, and possibly the fields. Missing one gives a factor of i error (or equivalently, a wrong sign in the exponent).
- **Non-commuting operations:** Wick rotation and regularization may not commute. If using dimensional regularization, verify the Wick rotation is valid in d dimensions.
- **Numerical noise amplification.** In numerical analytic continuation, noise at the level of 10^{-4} in G(tau) can produce O(1) errors in A(omega) at sharp features. Always perform the synthetic data test described above before trusting results on real data.
- **Wrong branch selection in Padé.** Padé approximants can have spurious poles on or near the real axis. These produce unphysical delta-function-like peaks in the spectral function. Identify and discard Padé approximants with poles close to the real axis in the region of interest.
- **Non-unique continuation.** The continuation from a finite number of noisy Matsubara points is mathematically non-unique. Different valid spectral functions can produce the same G(tau) within error bars. Report the range of consistent spectral functions, not just one "best" fit.

## Concrete Example: Wrong Retarded vs Advanced Propagator From Wrong i*epsilon

**Problem:** Analytically continue the Euclidean propagator G_E(i omega_n, k) = 1/(omega_n^2 + E_k^2) to obtain the retarded Green's function.

**Wrong approach (common LLM error):** "Replace i omega_n -> omega. Then G^R(omega, k) = 1/(omega^2 + E_k^2) = 1/((omega - E_k)(omega + E_k))." This has poles on the REAL axis, violating causality (retarded Green's function must be analytic in the upper half-plane).

**Correct approach:**

Step 1. **Analytic continuation rule:** Replace i omega_n -> omega + i eta (with eta -> 0+) to get the retarded propagator. This pushes the poles slightly below the real axis.
```
G^R(omega, k) = 1/((omega + i eta)^2 - E_k^2) = 1/((omega + i eta - E_k)(omega + i eta + E_k))
```

Step 2. **Pole positions:**
- omega = E_k - i eta (below real axis)
- omega = -E_k - i eta (below real axis)

Both poles are in the lower half-plane. Therefore G^R is analytic in the upper half-plane. This is the causality requirement: the retarded propagator has no singularities for Im(omega) > 0.

Step 3. **Spectral function:**
```
A(omega, k) = -2 Im[G^R(omega, k)] = 2 pi [delta(omega - E_k) - delta(omega + E_k)]
```

**Checkpoint: spectral positivity.** A(omega) should satisfy omega * A(omega, k) >= 0 (for bosons). At omega = E_k: omega * A > 0 (positive energy, positive spectral weight). At omega = -E_k: omega * A > 0 (negative energy times negative delta, so positive). Correct.

**Checkpoint: sum rule.**
```
integral A(omega, k) d omega / (2 pi) = 1
```
Check: (1/(2pi)) * 2pi * (1 + 1) = 2? NO -- this is wrong because the delta functions have unit weight but there are two of them. Actually: spectral function integral = [1/(2E_k)] * 2E_k = 1. Correct with proper normalization.

**Checkpoint: T -> 0 Matsubara sum recovery.** Substituting G^R into the spectral representation:
```
G_E(i omega_n) = integral d omega' A(omega') / (i omega_n - omega')
```
This must reproduce the original G_E(i omega_n) = 1/(omega_n^2 + E_k^2). Verify by direct substitution.

**The typical LLM error** either omits the i eta prescription entirely (getting poles on the real axis), or uses i omega_n -> omega - i eta (getting the ADVANCED Green's function G^A with poles in the upper half-plane). G^A describes effects propagating backward in time -- physical for certain applications but wrong when the retarded function is needed.

## Worked Example: Maximum Entropy Reconstruction of a Gapped Spectral Function

**Problem:** Given Matsubara Green's function data G(tau) for a single-band insulator with gap Delta ~ 1 eV at T = 300 K, reconstruct the spectral function A(omega) using the Maximum Entropy Method. This targets the LLM error class of treating numerical analytic continuation as a straightforward inverse problem, ignoring the exponential ill-conditioning and resolution limits.

### Step 1: Understand the Ill-Conditioning

The kernel relating A(omega) to G(tau) is:

```
G(tau) = integral d(omega) K(tau, omega) A(omega)
K(tau, omega) = exp(-tau * omega) / (1 + exp(-beta * omega))    (fermionic)
```

The singular values of K decay exponentially: sigma_n ~ exp(-c * n). This means that modes of A(omega) corresponding to small singular values are exponentially amplified by noise in G(tau). For typical QMC data with noise ~ 10^{-4}, features in A(omega) narrower than Delta_omega ~ pi * T ~ 0.08 eV (at T = 300 K) CANNOT be reliably resolved regardless of statistics.

**Checkpoint:** The resolution limit is set by temperature, not statistics. No amount of MC data can resolve features below Delta_omega ~ pi * T.

### Step 2: Prepare the Input Data

1. **Matsubara frequencies.** For beta = 1/(k_B * 300 K) = 38.7 eV^{-1}, the first ~20 Matsubara frequencies (omega_n = (2n+1) pi / beta) carry most information. Higher frequencies contribute little to A(omega) resolution.

2. **Error bars on G(tau).** Use jackknife or bootstrap ON THE QMC DATA to estimate the covariance matrix C_ij = Cov(G(tau_i), G(tau_j)). The full covariance matrix is essential — using only diagonal errors (ignoring correlations between different tau points) produces artifacts in A(omega).

3. **Normalize:** Verify the sum rule integral A(omega) d(omega) = 1. If G(tau=0) = -<n> is known, this provides a constraint.

### Step 3: Run MaxEnt

The MaxEnt functional:

```
Q[A] = alpha * S[A] - (1/2) chi^2[A]
chi^2 = sum_{ij} (G_data(tau_i) - G_fit(tau_i)) C^{-1}_{ij} (G_data(tau_j) - G_fit(tau_j))
S[A] = -integral d(omega) [A(omega) ln(A(omega)/m(omega)) - A(omega) + m(omega)]
```

where m(omega) is the default model (prior).

**Default model choices:**
- Flat: m(omega) = const. Least biased but can produce ringing artifacts.
- Gaussian: m(omega) = (1/(sigma sqrt(2pi))) exp(-omega^2/(2 sigma^2)). Smooth but imposes artificial width.
- From prior knowledge: if the gap is known, use m(omega) with weight concentrated above the gap.

**Run MaxEnt for each choice** and compare A(omega). Features present in ALL default models are robust; features present in only one are artifacts.

### Step 4: Validate

1. **Reproduce input data.** Compute G_fit(tau) from the recovered A(omega) via the kernel. chi^2 / N_data should be approximately 1. If chi^2 / N >> 1: fit is poor, increase resolution or check data quality. If chi^2 / N << 1: overfitting to noise.

2. **Sum rule.** integral A(omega) d(omega) / (2pi) = 1 to within 10^{-3}.

3. **Spectral positivity.** A(omega) >= 0 for all omega. MaxEnt enforces this by construction, but check numerical output for small negative values from discretization.

4. **Gap consistency.** For a gapped system, A(omega) should be zero (within resolution) for |omega| < Delta. If spectral weight appears inside the gap, it is an artifact from: insufficient data quality, wrong default model, or wrong alpha selection.

5. **Synthetic data test (MANDATORY).** Before trusting results on real data:
   - Choose a known A_test(omega) with the expected gap structure
   - Compute G_test(tau) = integral K(tau, omega) A_test(omega) d(omega)
   - Add noise at the same level as the real data
   - Run MaxEnt on G_test(tau)
   - Compare recovered A(omega) with A_test(omega)
   - The difference shows the resolution limit of your data

### Expected Results

For a gapped insulator at T = 300 K with QMC noise ~ 10^{-4}:
- Gap edges resolved to ~ 0.1 eV precision
- Band shape (bandwidth, peak positions) resolved to ~ 0.2 eV
- Fine structure within bands (van Hove singularities) NOT resolvable — they appear as broad humps

### Verification

1. **Default model sensitivity.** If the gap position shifts by more than pi * T when changing the default model: the data do not constrain the gap position. Report the range, not a single value.

2. **Alpha sensitivity.** MaxEnt has a regularization parameter alpha. The "classic" MaxEnt selects alpha by maximizing the posterior probability. Vary alpha by a factor of 10 above and below the optimal value. Robust features should be alpha-independent.

3. **Comparison with Pade.** Run Pade approximants as an independent check. Pade is less stable but model-independent. If MaxEnt and Pade agree on a feature (peak position, gap value), it is likely physical. If they disagree, neither result is reliable for that feature.

4. **Cross-check with moments.** The first few moments of A(omega) can be computed directly from G(tau) derivatives at tau = 0 and tau = beta. Verify that the recovered A(omega) reproduces these moments:
   - zeroth moment: integral A(omega) d(omega) = 1
   - first moment: integral omega A(omega) d(omega) = -dG/d(tau)|_{tau=0+} (related to the first-order self-energy)

## Worked Example: Pade Approximant Failure for a Two-Peak Spectral Function

**Problem:** Given Matsubara Green's function data for a system with two spectral peaks at omega = +/- Delta (e.g., a superconducting gap), demonstrate how Pade approximants produce spurious features and how to diagnose the failure. This targets the LLM error class of treating Pade continuation as a reliable black-box method, ignoring noise sensitivity, and failing to validate with synthetic data.

### Step 1: Define the Known Spectral Function

A model spectral function with a superconducting-like gap:

```
A(omega) = (1/pi) * [Gamma / ((omega - Delta)^2 + Gamma^2) + Gamma / ((omega + Delta)^2 + Gamma^2)]
```

with Delta = 1.0 (gap), Gamma = 0.1 (broadening). This has two Lorentzian peaks at omega = +/- Delta, each with width Gamma.

### Step 2: Generate Matsubara Data

Compute G(i omega_n) from the spectral representation:

```
G(i omega_n) = integral d(omega) A(omega) / (i omega_n - omega)
```

For Lorentzian peaks, this is analytic:

```
G(i omega_n) = 1/(i omega_n - Delta + i Gamma) + 1/(i omega_n + Delta + i Gamma)
```

Evaluate at fermionic Matsubara frequencies omega_n = (2n+1) pi T with T = 0.1 (beta = 10). Use N = 50 frequencies.

### Step 3: Pade Continuation Without Noise

With exact (noise-free) Matsubara data, the Pade approximant P_M(z)/Q_N(z) with M + N + 1 = 50 coefficients:

```
G^R_Pade(omega) = P_M(omega + i eta) / Q_N(omega + i eta)
```

Result: Pade perfectly reproduces the two-peak structure. A_Pade(omega) = -Im[G^R_Pade]/pi matches the original A(omega) to machine precision.

**This is misleading** — it works only because the data are exact and the spectral function is rational (a ratio of polynomials).

### Step 4: Pade Continuation WITH Noise

Add Gaussian noise at the 10^{-4} level (typical of QMC): G_noisy(i omega_n) = G(i omega_n) + eta_n with |eta_n| ~ 10^{-4}.

Run Pade with the same number of coefficients:

```
| N_coefficients | Result |
|----------------|--------|
| 10             | Two broad peaks, positions shifted by ~0.05, widths ~0.3 (3x too broad) |
| 20             | Two peaks at roughly correct positions, plus 1 spurious sharp peak at omega ~ 0.3 |
| 30             | Two peaks plus 3 spurious peaks and one negative-weight feature |
| 50             | Wildly oscillating, unphysical spectral function with A(omega) < 0 in multiple regions |
```

**Checkpoint:** Spectral positivity A(omega) >= 0 is violated at N = 30 and above. This immediately flags the continuation as untrustworthy.

### Step 5: Diagnosis and Resolution

**Why Pade fails:** The Pade approximant fits a rational function through the noisy data points. With too many coefficients, it fits the noise, producing poles near the real axis that appear as spurious delta-function-like peaks. With too few coefficients, it cannot resolve the two-peak structure.

**Resolution protocol:**

1. Vary N_coefficients from small to large. Identify the window where the main features (two peaks at +/- Delta) are stable.
2. Discard any Pade result with A(omega) < 0 anywhere.
3. Cross-check with MaxEnt: run the Maximum Entropy Method on the same data. Features present in BOTH Pade (at stable N) and MaxEnt are likely physical.
4. Report error bars: the spread in peak positions across stable Pade approximants gives an estimate of the continuation uncertainty.

### Step 6: MaxEnt Comparison

MaxEnt with flat default model on the same noisy data:

```
| Feature        | True value | Pade (N=20) | MaxEnt (flat) | MaxEnt (Gaussian) |
|----------------|------------|-------------|---------------|-------------------|
| Peak 1 pos     | +1.0       | +0.95       | +1.02         | +0.98             |
| Peak 2 pos     | -1.0       | -1.05       | -1.02         | -0.98             |
| Peak width     | 0.1        | 0.25        | 0.20          | 0.18              |
| Sum rule       | 1.0        | 0.98        | 1.000         | 1.000             |
| Positivity     | OK         | violated    | OK            | OK                |
```

MaxEnt enforces sum rule and positivity by construction. It broadens the peaks (limited by resolution ~ pi T = 0.31) but does not produce spurious features.

### Verification

1. **Sum rule.** integral A(omega) d(omega)/(2pi) must equal 1.0 (spectral weight conservation). Pade at high N violates this; MaxEnt preserves it.

2. **Kramers-Kronig.** Compute Re[G^R] from Im[G^R] via Kramers-Kronig. Compare with the direct Pade real part. Inconsistency flags continuation errors.

3. **Synthetic data test (the gold standard).** The analysis above IS the synthetic data test: we knew the true A(omega) and could quantify the error. For real data, this test uses a model A(omega) with expected features, generates noisy G(tau), and checks recovery. If the method cannot recover the synthetic spectrum, it cannot be trusted on real data.

4. **Resolution limit.** Features narrower than Delta_omega ~ pi T (here 0.31) cannot be resolved. Both peaks have true width 0.1 < 0.31, so the recovered widths will be broadened to at least ~0.2. This is a fundamental limit, not a numerical failure.

**The typical LLM error** uses Pade continuation as a black box, reports a spectral function with spurious peaks and negative spectral weight, and does not perform any of the validation checks (sum rule, positivity, synthetic data test, N-dependence).
