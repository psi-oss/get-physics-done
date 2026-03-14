---
load_when:
  - "finite temperature"
  - "thermal field theory"
  - "Matsubara"
  - "quark-gluon plasma"
  - "HTL resummation"
  - "imaginary time"
  - "Schwinger-Keldysh"
tier: 2
context_cost: high
---

# Finite-Temperature Field Theory Protocol

Quantum field theory at finite temperature underpins quark-gluon plasma physics, cosmological phase transitions, condensed matter response functions, and Bose-Einstein condensation. The interplay between thermal and quantum fluctuations introduces subtleties (Matsubara frequencies, analytic continuation, infrared problems) that are major error sources.

## Related Protocols

- See `analytic-continuation.md` for Matsubara-to-real-frequency continuation and spectral representations
- See `perturbation-theory.md` for loop calculations with Matsubara sums instead of frequency integrals
- See `renormalization-group.md` for thermal RG flows and dimensional reduction at high T
- See `kinetic-theory.md` for Boltzmann equation approach to transport at finite temperature (semiclassical regime)
- See `resummation.md` for HTL resummation and dealing with IR divergences in thermal perturbation theory

## Overview

Two complementary formalisms exist:

| Formalism | Time variable | Frequencies | Natural for |
|---|---|---|---|
| Imaginary-time (Matsubara) | τ ∈ [0, β] | Discrete: iωₙ | Equilibrium thermodynamics, static properties |
| Real-time (Schwinger-Keldysh) | t ∈ (-∞, +∞) | Continuous: ω | Transport, spectral functions, non-equilibrium |

Both give the same physical results when applied correctly. Errors arise from mixing conventions, incorrect analytic continuation, or missing thermal effects.

## Step 1: Imaginary-Time Formalism (Matsubara)

Replace real time t → -iτ (Wick rotation) with τ ∈ [0, β], β = 1/(k_B T). Fields satisfy periodicity conditions:

- **Bosons:** φ(τ + β) = φ(τ) → frequencies ωₙ = 2nπT (n = 0, ±1, ±2, ...)
- **Fermions:** ψ(τ + β) = -ψ(τ) → frequencies ωₙ = (2n+1)πT (n = 0, ±1, ±2, ...)

**Checklist:**

1. **Verify the periodicity condition.** Bosonic fields are periodic, fermionic fields are antiperiodic. Getting this wrong changes the Matsubara frequencies (`references/verification/errors/llm-physics-errors.md` #9). The KMS condition ⟨A(τ)B(0)⟩ = ⟨B(0)A(τ + β)⟩ (bosonic) or = -⟨B(0)A(τ + β)⟩ (fermionic) is the fundamental statement.
2. **Replace frequency integrals with Matsubara sums.** ∫ dω/(2π) → T Σₙ. The factor T (not 1/β) comes from the convention where Matsubara frequencies include the factor of T. State the convention explicitly.
3. **Evaluate Matsubara sums correctly.** Standard technique: convert the sum to a contour integral using the identity T Σₙ f(iωₙ) = ∮ dz/(2πi) n_B(z) f(z) (bosonic) or T Σₙ f(iωₙ) = -∮ dz/(2πi) n_F(z) f(z) (fermionic), where n_B = 1/(e^{βz}-1) and n_F = 1/(e^{βz}+1) provide the poles at the Matsubara frequencies.
4. **Handle the bosonic zero mode (n=0) carefully.** In 3D finite-temperature gauge theories, the ω₀ = 0 Matsubara mode reduces to a 3D theory (dimensional reduction). This mode requires separate treatment in perturbation theory because it has enhanced IR sensitivity.

**Standard Matsubara sums (verify these as reference):**

```
T Σₙ 1/(iωₙ - ε) = n_F(ε)                          (fermionic)
T Σₙ 1/(iωₙ - ε) = -n_B(ε) - 1/2                   (bosonic, depends on convention)
T Σₙ 1/((iωₙ - ε₁)(iωₙ - ε₂)) = [n_F(ε₁) - n_F(ε₂)]/(ε₁ - ε₂)   (fermionic)
```

## Step 2: Real-Time Formalism (Schwinger-Keldysh)

For spectral functions and transport: work directly with real frequencies.

**Checklist:**

1. **Define the 2×2 matrix propagator.** The real-time formalism uses a doubled field content (fields on the forward and backward branches of the time contour). The propagator is a 2×2 matrix with components G^{11} = G^T, G^{12} = G^<, G^{21} = G^>, G^{22} = G^T̃.
2. **Perform the Keldysh rotation** to the retarded/advanced/Keldysh basis (see `non-equilibrium-transport.md`). In equilibrium, the Keldysh component is fixed by the FDT: G^K = (G^R - G^A) coth(ω/(2T)).
3. **Verify the spectral function** A(ω) = -Im[G^R(ω)]/π is non-negative for all ω. This is a consequence of unitarity and is violated by approximations that break spectral positivity (e.g., inconsistent self-energy truncations).

## Step 3: Analytic Continuation (iωₙ → ω + iη)

The connection between the Matsubara and real-time formalisms is analytic continuation.

**Checklist:**

1. **The retarded function is obtained by iωₙ → ω + iη (η → 0⁺).** This is valid when the Matsubara Green's function is analytic in the upper half-plane. Verify that there are no branch cuts crossed during the continuation.
2. **For numerical continuation:** Matsubara data at discrete points → continuous real-frequency function. This is an ill-posed inverse problem. Methods: Padé approximants (fast but unstable), Maximum Entropy Method (MaxEnt, stable but resolution-limited), stochastic analytic continuation. Always check the sum rule ∫ A(ω) dω = 1 (spectral weight) and non-negativity A(ω) ≥ 0 after continuation.
3. **Verify Kramers-Kronig consistency.** After continuation, check that Re[G^R] and Im[G^R] satisfy the Kramers-Kronig relations. Violation indicates a continuation error.

## Step 4: Hard Thermal Loop (HTL) Resummation

In hot gauge theories (QCD at T ≫ Λ_QCD, QED plasma), perturbation theory breaks down for soft momenta p ~ gT because thermal corrections to propagators and vertices are O(1), not O(g²).

**Checklist:**

1. **Identify the HTL regime.** For momenta p ~ gT (soft scale), the HTL self-energies Π ~ g²T² are comparable to p². Naive perturbation theory gives IR-divergent or gauge-dependent results. HTL resummation is required.
2. **Use HTL-resummed propagators for soft internal lines.** The HTL gluon propagator has two branches: transverse (with thermal mass m_T ~ gT) and longitudinal (with Debye screening mass m_D ~ gT). The longitudinal mode is absent at T = 0 — it is purely a thermal effect.
3. **Include HTL vertex corrections consistently.** The HTL effective action generates both propagator corrections and vertex corrections. Using HTL propagators without HTL vertices violates the Ward identity.
4. **Be aware of the magnetic mass problem.** In non-Abelian gauge theories, the static magnetic sector (transverse gluons at zero Matsubara frequency) is non-perturbative at O(g⁶T⁴) — the magnetic mass m_mag ~ g²T cannot be computed perturbatively. This limits the perturbative computation of the QCD pressure to O(g⁵) at best; O(g⁶) requires lattice input.
5. **Check the plasmon sum rule.** The thermal photon/gluon spectral function must satisfy ∫ dω ω ρ_T(ω, k) = k² + m_T² (transverse) and a corresponding rule for the longitudinal sector.

## Step 5: Infrared Problems in Hot Gauge Theories

**Checklist:**

1. **Dimensional reduction at high T.** For static quantities, the heavy Matsubara modes (ωₙ ≠ 0) can be integrated out, leaving an effective 3D theory (electrostatic QCD for the gluon sector). This 3D theory is super-renormalizable but still has IR problems in the magnetic sector.
2. **Linde's problem.** The perturbative expansion of the free energy in QCD has the form: f = c₀T⁴ + c₂g²T⁴ + c₃g³T⁴ + c₄g⁴T⁴ + c₅g⁵T⁴ + (c₆g⁶ + c₆' g⁶ ln g)T⁴ + O(g⁷). The coefficient c₆ cannot be determined perturbatively — it requires non-perturbative (lattice) input. The coefficients c₀ through c₅ are known analytically.
3. **Sign problem awareness.** At finite baryon chemical potential μ_B ≠ 0, the fermion determinant in QCD is complex, making Monte Carlo integration impossible (sign problem). Lattice methods fail for μ_B/T > ~1. This is NOT a technical limitation — it is a fundamental obstacle. Methods that claim to circumvent it (complex Langevin, Lefschetz thimbles, Taylor expansion, reweighting) have limited and well-characterized applicability.

## Common Error Modes

| Error | Detection | See Also |
|---|---|---|
| Wrong Matsubara frequency (bosonic 2nπT vs fermionic (2n+1)πT) | Check periodicity: bosons periodic, fermions antiperiodic | `references/verification/errors/llm-physics-errors.md` #9 |
| Wrong analytic continuation iωₙ → ω + iε instead of ω + iη | Check causality: G^R analytic in upper half-plane | `references/verification/errors/llm-physics-errors.md` #21 |
| Missing HTL resummation for soft momenta | Result is IR divergent or gauge-dependent | — |
| Treating sign problem as solvable | Check μ_B/T regime; be honest about limitations | — |
| Wrong factor in Matsubara sum ↔ integral replacement | Verify T Σₙ vs (1/β) Σₙ convention | — |
| Ignoring bosonic zero mode in dimensional reduction | Check n=0 mode contribution separately | — |
| Using T=0 Feynman rules at finite T | Verify propagators include thermal occupation factors | `references/verification/errors/llm-physics-errors.md` #20 |

## Verification Criteria

1. **T → 0 limit.** All finite-T results must reduce to the known T = 0 results. The Matsubara sum becomes a frequency integral: T Σₙ → ∫ dω/(2π).
2. **T → ∞ limit.** For non-interacting systems: classical equipartition (energy per mode = k_B T/2 for quadratic Hamiltonian). For QCD: Stefan-Boltzmann limit f → -(π²/90)(N² - 1 + 7N N_f/4)T⁴ for SU(N) with N_f flavors.
3. **Spectral positivity.** A(ω) ≥ 0 for all ω. Violation indicates a broken approximation.
4. **Sum rules.** Spectral weight: ∫ A(ω) dω/(2π) = 1. Energy-weighted: ∫ ω A(ω) dω gives the first moment. f-sum rule for conductivity.
5. **KMS condition.** G^>(ω) = e^{βω} G^<(ω) in equilibrium. This is exact and provides a strong consistency check.
6. **Gauge independence.** Physical observables (pressure, transport coefficients, screening masses) must be gauge-parameter independent. Compute in two gauges as a cross-check.

## Concrete Example: Wrong Matsubara Frequency Gives Wrong Sign

**Problem:** Compute the thermal propagator for a free scalar (boson) at temperature T.

**Wrong approach (common LLM error):** "The Matsubara frequencies are omega_n = (2n+1) pi T." This uses FERMIONIC frequencies for a BOSON.

Bosonic Matsubara frequencies: omega_n = 2n pi T (n = 0, +/-1, +/-2, ...)
Fermionic Matsubara frequencies: omega_n = (2n+1) pi T (n = 0, +/-1, +/-2, ...)

**Correct approach:**

Step 1. **Identify the statistics.** Scalar field = boson. Periodic boundary conditions in imaginary time: phi(tau + beta) = phi(tau). This gives EVEN Matsubara frequencies: omega_n = 2n pi T.

Step 2. **Propagator in Matsubara formalism:**
```
G(i omega_n, k) = 1 / (omega_n^2 + k^2 + m^2)     [Euclidean, bosonic]
```
Note: omega_n^2 = (2n pi T)^2 is always non-negative. The propagator is real and positive for all n, k.

Step 3. **Matsubara sum for the tadpole:**
```
T * sum_n G(i omega_n, k) = T * sum_n 1/(omega_n^2 + E_k^2)
                          = [1 + 2 n_B(E_k)] / (2 E_k)
```
where n_B(E) = 1/(exp(E/T) - 1) is the Bose-Einstein distribution and E_k = sqrt(k^2 + m^2).

**Checkpoint: T -> 0 limit.** As T -> 0: n_B(E_k) -> 0. Result: 1/(2 E_k), which is the T = 0 vacuum propagator. Correct.

**Checkpoint: high-T limit.** For T >> E_k: n_B(E_k) -> T/E_k. Result: T/E_k^2, which is the classical equipartition result. Correct.

**The typical LLM error** uses fermionic frequencies (2n+1)pi T for a boson, producing:
```
T * sum_n 1/((2n+1)^2 pi^2 T^2 + E_k^2) = tanh(E_k/(2T)) / (2 E_k)
```
This gives a FERMIONIC distribution tanh instead of coth. The T -> infinity limit gives 1/(2 E_k) instead of T/E_k^2, failing the classical limit check. The KMS condition G^>(omega) = e^{beta omega} G^<(omega) also fails because the wrong statistics produce the wrong periodicity.

## Worked Example: Free Energy of a Relativistic Bose Gas (Stefan-Boltzmann Law)

**Problem:** Compute the free energy density of a free massless scalar field at temperature T using the Matsubara formalism, and recover the Stefan-Boltzmann T^4 law. This targets the LLM error class of wrong Matsubara sum evaluation, incorrect treatment of the n=0 mode, and factor-of-pi errors in thermal integrals.

### Step 1: Matsubara Free Energy

The free energy density of a free scalar field:

```
F/V = (T/2) sum_{n=-inf}^{inf} integral d^3k/(2pi)^3 * ln(omega_n^2 + k^2)
```

where omega_n = 2n pi T (bosonic frequencies) and we set m = 0 for a massless field.

### Step 2: Evaluate the Matsubara Sum

Using the standard result for the bosonic Matsubara sum:

```
T sum_n ln(omega_n^2 + E^2) = E + 2T ln(1 - e^{-E/T}) + const
```

where E = |k| for a massless field. The constant is T-independent and is subtracted as vacuum renormalization.

The thermal contribution to the free energy:

```
F_thermal/V = integral d^3k/(2pi)^3 * T * ln(1 - e^{-|k|/T})
```

### Step 3: Evaluate the Momentum Integral

In spherical coordinates:

```
F_thermal/V = (4pi)/(2pi)^3 * T * integral_0^inf k^2 dk * ln(1 - e^{-k/T})
```

Substituting x = k/T:

```
F_thermal/V = T^4 / (2pi^2) * integral_0^inf x^2 * ln(1 - e^{-x}) dx
```

The integral:

```
integral_0^inf x^2 ln(1 - e^{-x}) dx = -2 * zeta(4) * Gamma(3) / (something?)
```

More directly, integrate by parts or use the series expansion ln(1 - e^{-x}) = -sum_{l=1}^inf e^{-lx}/l:

```
integral_0^inf x^2 * (-sum_{l=1}^inf e^{-lx}/l) dx = -sum_{l=1}^inf (1/l) * 2/l^3 = -2 sum_{l=1}^inf 1/l^4 = -2 zeta(4)
```

Using zeta(4) = pi^4/90:

```
F_thermal/V = T^4/(2pi^2) * (-2 pi^4/90) = -pi^2 T^4 / 90
```

### Step 4: Stefan-Boltzmann Result

The pressure P = -F/V:

```
P = pi^2 T^4 / 90
```

This is the Stefan-Boltzmann law for a single real scalar field (one degree of freedom).

### Verification

1. **Photon gas (2 polarizations):** P_photon = 2 * pi^2 T^4 / 90 = pi^2 T^4 / 45. The energy density u = 3P = pi^2 T^4 / 15. The Stefan-Boltzmann constant sigma = pi^2/(60) (in natural units). With c and k_B restored: sigma = pi^2 k_B^4 / (60 hbar^3 c^2) = 5.67 x 10^{-8} W m^{-2} K^{-4}. If the numerical value is wrong, there is a factor-of-pi or factor-of-2 error.

2. **Entropy density:** s = -dF/dT = 4 * pi^2 T^3 / 90 = 2 pi^2 T^3 / 45. For a single scalar: s = (2pi^2/45) T^3. This is always positive. If s < 0, there is a sign error.

3. **Specific heat:** c_V = T * ds/dT = 6 pi^2 T^3 / 45. This is proportional to T^3 (the Debye T^3 law for photons). The ratio c_V/s = 3 (valid for a relativistic gas). If this ratio is not exactly 3, there is an error.

4. **Zero-mass limit from massive case:** For a massive scalar, F_thermal -> -pi^2 T^4/90 as m/T -> 0. For m/T >> 1, F_thermal ~ -(m T)^{3/2} * T * exp(-m/T) (Boltzmann suppression). The interpolation must be smooth and monotonic.

5. **Fermion comparison:** For a single Dirac fermion (4 degrees of freedom): P_fermion = (7/8) * 4 * pi^2 T^4/90 = 7 pi^2 T^4/180. The factor 7/8 is the ratio of the fermionic zeta function (1 - 2^{1-s}) zeta(s) at s=4 to the bosonic one. If you get 7/8 for a boson, you used fermionic frequencies.

## Worked Example: Debye Screening Mass in QED at Finite Temperature

**Problem:** Compute the Debye screening mass m_D for QED with N_f massless fermion flavors at temperature T using the one-loop photon self-energy in the Matsubara formalism. This targets the LLM error class of using bosonic Matsubara frequencies for fermion loops, dropping the factor of T in the sum-integral replacement, and confusing the static (omega=0) limit with the full self-energy.

### Step 1: Set Up the One-Loop Self-Energy

The photon self-energy (polarization tensor) at one loop is a fermion bubble:

```
Pi^{mu nu}(Q) = -e^2 T sum_{n} integral d^3p/(2pi)^3 Tr[gamma^mu S(P) gamma^nu S(P+Q)]
```

where P = (i omega_n, p) with FERMIONIC Matsubara frequencies omega_n = (2n+1) pi T, and S(P) = -i gamma^mu P_mu / P^2 is the free fermion propagator in Euclidean space.

**Checkpoint:** The frequencies in the loop are fermionic (odd multiples of pi T) because the internal lines are fermions. Using bosonic frequencies (even multiples) here is a common LLM error that changes the thermal distribution from n_F to n_B.

### Step 2: Extract the Debye Mass from the Static Limit

The Debye mass is defined from the longitudinal part of the self-energy in the static limit:

```
m_D^2 = -Pi^{00}(omega=0, q->0)
```

The minus sign arises because the screened potential in momentum space is V(q) = e^2/(q^2 + m_D^2), and the self-energy enters as a correction to the photon propagator.

For the static limit (Q = (0, q->0)), the Matsubara sum over the fermion loop gives:

```
Pi^{00}(0, 0) = -2 N_f e^2 T sum_n integral d^3p/(2pi)^3 * (omega_n^2 + p^2 + 2p^2/3) / (omega_n^2 + p^2)^2
```

After simplification, the key Matsubara sum is:

```
T sum_n 1/(omega_n^2 + E^2) = [1 - 2 n_F(E)] / (2E)    (fermionic sum)
```

and:

```
T sum_n omega_n^2/(omega_n^2 + E^2)^2 = derivative with respect to E of the above
```

### Step 3: Evaluate

After performing the Matsubara sum and the angular integration, the result for N_f fermion flavors is:

```
m_D^2 = (N_f e^2 / pi^2) integral_0^inf dp * p * [-d n_F(p) / dp]
```

where n_F(p) = 1/(e^{p/T} + 1). Using the identity:

```
integral_0^inf dp * p * [-d n_F(p) / dp] = T^2 * integral_0^inf dx * x * e^x/(e^x + 1)^2
                                           = T^2 * pi^2/12     [via -Li_0(-1) = 1/2]
```

We find:

```
m_D^2 = N_f e^2 T^2 / 12     [QED Debye mass, per fermion flavor, one-loop]
```

For N_f = 1 (single electron flavor): m_D^2 = e^2 T^2 / 12.

### Step 4: Common LLM Errors

**Error 1: Using bosonic frequencies.** If we mistakenly use omega_n = 2n pi T (bosonic) in the fermion loop:

```
T sum_n(bosonic) 1/(omega_n^2 + E^2) = [1 + 2 n_B(E)] / (2E)
```

This gives n_B (Bose-Einstein) instead of n_F (Fermi-Dirac). The resulting integral:

```
integral_0^inf dp * p * [-d n_B(p) / dp] = T^2 * pi^2/6
```

produces m_D^2 = N_f e^2 T^2/6, which is WRONG by a factor of 2. The Bose distribution diverges as 1/p for small p, changing the integral value.

**Error 2: Wrong overall sign.** Confusing m_D^2 = +Pi^{00} vs m_D^2 = -Pi^{00}. The correct sign gives m_D^2 > 0 (screening). The wrong sign gives m_D^2 < 0 (anti-screening/tachyonic), which is unphysical for QED.

### Verification

1. **Coupling constant check.** m_D^2 is proportional to e^2 = 4 pi alpha. At T = 10^9 K (early universe): m_D ~ alpha^{1/2} T ~ 0.085 T ~ 7 MeV. This is the correct order of magnitude for electromagnetic screening in the early universe.

2. **QCD comparison.** For QCD with N_c colors and N_f flavors, the analogous result is m_D^2 = g^2 T^2 (N_c/3 + N_f/6). The N_c/3 term comes from the gluon loop (bosonic) and the N_f/6 from quark loops (fermionic). The ratio of fermionic to bosonic contributions is (N_f/6)/(N_c/3) = N_f/(2 N_c), which is 1/2 for N_f = N_c = 3. If you get 1 instead of 1/2, you used the wrong statistics in one of the loops.

3. **High-T expansion.** For massive fermions at T >> m: m_D^2 = e^2 T^2/12 * [1 - 3/(pi T)^2 * m^2 + ...]. The leading correction is O(m^2/T^2). Verify the massive result reduces to the massless one.

4. **Screening length.** The Debye screening length lambda_D = 1/m_D should be large compared to the interparticle spacing n^{-1/3} for the screening picture to be valid. For a weakly coupled plasma (e << 1), lambda_D ~ 1/(eT) >> 1/T ~ n^{-1/3}. This confirms self-consistency.
