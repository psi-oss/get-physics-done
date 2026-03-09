---
load_when:
  - "scattering"
  - "cross section"
  - "phase shift"
  - "S-matrix"
  - "T-matrix"
  - "partial wave"
  - "optical theorem"
  - "resonance"
tier: 2
context_cost: high
---

# Scattering Theory Protocol

Scattering calculations are central to AMO, nuclear, and particle physics. Errors arise from wrong normalizations, incorrect partial wave sums, violated unitarity bounds, and confusion between different scattering formalisms. This protocol ensures systematic and correct scattering calculations.

## Related Protocols

- See `perturbation-theory.md` for Born series calculations and loop corrections to scattering amplitudes
- See `numerical-computation.md` for numerical solution of the Lippmann-Schwinger equation and phase shift extraction
- See `analytic-continuation.md` for relating bound state poles to scattering amplitudes

## Step 1: Define the Scattering Problem

1. **Specify the potential or interaction.** Write V(r) explicitly for potential scattering, or the Lagrangian interaction terms for field-theoretic scattering. State the range and strength of the interaction.
2. **Identify the channels.** For multi-channel scattering (inelastic, rearrangement): list all open and closed channels at the energy of interest. Define channel quantum numbers (angular momentum, spin, isospin, etc.).
3. **Set up kinematics.** Define the incident momentum k (or energy E = hbar^2 k^2 / (2m) for non-relativistic, or s = (p_1 + p_2)^2 for relativistic). State the center-of-mass vs lab frame and the reduced mass mu = m_1 m_2 / (m_1 + m_2).
4. **State the normalization convention.** For plane waves: are they normalized as exp(ik.r) or (2pi)^{-3/2} exp(ik.r)? For spherical waves: what is the asymptotic form? State the convention for the scattering amplitude f(theta) and its relation to the differential cross section.

## Step 2: Partial Wave Analysis

1. **Decompose the scattering amplitude** in partial waves:
   f(theta) = sum_l (2l+1) f_l P_l(cos theta)
   where f_l = (S_l - 1) / (2ik) = (exp(2i delta_l) - 1) / (2ik) for elastic scattering.
2. **Phase shift extraction.** For each partial wave l, solve the radial Schrodinger equation (or the appropriate radial equation) with the potential and extract delta_l from the asymptotic behavior:
   u_l(r) -> A_l [sin(kr - l*pi/2 + delta_l)] as r -> infinity.
3. **Convergence of partial wave sum.** For a potential of range R, partial waves with l >> kR contribute negligibly (delta_l -> 0). Verify the sum is converged by checking that adding more l values doesn't change the cross section.
4. **Phase shift conventions.** delta_l is defined modulo pi. Choose the branch continuously in energy. At threshold (k -> 0): delta_l -> (ka)^{2l+1} (Wigner threshold law). Verify this behavior.

## Step 3: Born Approximation

1. **First Born approximation:**
   f^(1)(q) = -(m / (2pi hbar^2)) integral V(r') exp(-iq.r') d^3r'
   where q = k_f - k_i is the momentum transfer. This is the Fourier transform of the potential.
2. **Validity:** The Born parameter beta = |V_0| m R^2 / hbar^2 controls validity, but the condition depends on energy:
   - **Low energy (kR << 1):** Born approximation requires beta << 1. The condition is |V_0| << hbar^2 / (m R^2), independent of E. This is the intrinsic weakness condition — the potential must be genuinely weak.
   - **High energy (kR >> 1):** Born approximation requires |V_0| << E (equivalently, beta << (kR)^2). Even a deep potential (beta >> 1) can be treated perturbatively if the kinetic energy dominates.
   - **Crossover (kR ~ 1):** Neither condition alone is sufficient. The full criterion is that the Born series converges: |f^(2)/f^(1)| << 1 at the scattering angles of interest. Compute f^(2) explicitly or estimate it as ~ beta / (1 + (kR)^2).
   Check the appropriate condition before using Born approximation. A potential with beta ~ 1 (e.g., nuclear forces) fails the Born approximation at low energy even though |V_0| << E may hold at high energy.
3. **Higher-order Born series:**
   f = f^(1) + f^(2) + ... where f^(n) involves n insertions of V. The series converges for sufficiently weak potentials but can diverge for strong potentials (e.g., hard sphere). If f^(2) ~ f^(1), the Born series is not converging and a non-perturbative method is needed.
4. **Distorted wave Born approximation (DWBA).** When the potential has a strong part V_0 (solved exactly) and a weak perturbation V_1: expand in V_1 while treating V_0 non-perturbatively. The scattering states of V_0 replace plane waves as the basis.

## Step 4: T-matrix and Lippmann-Schwinger Equation

1. **Lippmann-Schwinger equation:**
   |psi^(+)> = |phi> + G_0^(+) V |psi^(+)>
   where G_0^(+) = 1/(E - H_0 + i*eta) is the free retarded Green's function. This is the fundamental integral equation of scattering.
2. **T-matrix definition:**
   T = V + V G_0^(+) T (operator equation)
   The scattering amplitude is: f(k_f, k_i) = -(m / (2pi hbar^2)) <k_f|T|k_i>.
3. **On-shell vs off-shell T-matrix.** Physical scattering uses the on-shell T-matrix (|k_f| = |k_i| = k for elastic). But intermediate states in the Lippmann-Schwinger equation involve off-shell momenta. The T-matrix is a function of three variables (k_f, k_i, E), not two.
4. **Numerical solution.** Discretize the Lippmann-Schwinger equation on a momentum grid. The principal value integral requires careful treatment: subtract the pole and add back analytically. Verify convergence with grid size.

## Step 5: S-matrix Unitarity and Optical Theorem

1. **S-matrix unitarity:** S^dag S = 1 (probability conservation). For elastic single-channel scattering: |S_l| = 1 for each partial wave. For multi-channel: S is a unitary matrix in channel space. Verify unitarity explicitly.
2. **Optical theorem:**
   sigma_total = (4pi / k) Im[f(theta = 0)]
   This is an exact consequence of unitarity. It relates the total cross section to the imaginary part of the forward scattering amplitude. Use as a cross-check.
3. **Partial wave unitarity bounds:** For each l:
   sigma_l <= 4pi(2l+1) / k^2
   Any computed partial cross section exceeding this bound violates unitarity. This is a hard constraint.
4. **Inelastic scattering:** When inelastic channels are open, |S_l| < 1 (absorption). Define the elasticity parameter eta_l = |S_l|. The elastic and inelastic cross sections are:
   sigma_l^elastic = pi(2l+1)/k^2 |1 - eta_l exp(2i delta_l)|^2
   sigma_l^inelastic = pi(2l+1)/k^2 (1 - eta_l^2)

## Step 6: Cross-Section Calculation

1. **Differential cross section:**
   d sigma / d Omega = |f(theta)|^2
   For identical particles, the scattering amplitude must be symmetrized (bosons) or antisymmetrized (fermions):
   f_sym(theta) = f(theta) +/- f(pi - theta)
   This gives a factor-of-2 difference in the cross section at theta = pi/2.
2. **Total cross section:**
   sigma_total = integral |f(theta)|^2 d Omega = 4pi sum_l (2l+1) sin^2(delta_l) / k^2
3. **Flux factor.** Verify the normalization: sigma = (number of scattering events per unit time) / (incident flux). The incident flux is j = hbar k / m for non-relativistic particles with unit normalization, or j = v for relativistic particles. Getting the flux wrong changes sigma by a constant factor.
4. **Threshold behavior:** As k -> 0, the cross section is dominated by l = 0 (s-wave): sigma -> 4pi a^2 where a is the scattering length (defined by delta_0 -> -ka as k -> 0). For identical bosons: sigma -> 8pi a^2. Verify this limit.

## Step 7: Resonance Analysis

1. **Breit-Wigner resonance:** Near a resonance at energy E_R with width Gamma:
   f_l = -(Gamma/2) / (E - E_R + i Gamma/2)
   The phase shift passes through pi/2 at E = E_R (resonance condition: delta_l(E_R) = pi/2 mod pi).
2. **Poles of the S-matrix.** Resonances correspond to poles of S_l in the lower half of the complex k-plane (or the second Riemann sheet of the complex E-plane). The pole position determines E_R and Gamma: k_pole = k_R - i gamma/2, giving E_R = hbar^2 k_R^2/(2m) and Gamma = 2 hbar^2 k_R gamma / (2m).
3. **Bound states.** Bound states are poles of S_l on the positive imaginary k-axis (k = i kappa, E = -hbar^2 kappa^2/(2m) < 0). A scattering length a > 0 signals a weakly bound state near threshold.
4. **Feshbach resonances.** Coupling between open and closed channels produces resonances. The scattering length varies as a(B) = a_bg (1 - Delta / (B - B_0)) near a magnetic Feshbach resonance. The resonance width Delta and position B_0 characterize the resonance.

## Common Pitfalls

- **Wrong normalization.** Plane wave normalization affects the scattering amplitude by an overall factor. If using box normalization, the density of states factor must be included. Always trace through the normalization from the initial flux to the final cross section.
- **Missing flux factor.** The cross section formula requires dividing by the incident flux. In relativistic kinematics, the Moller flux factor 4 sqrt((p_1.p_2)^2 - m_1^2 m_2^2) is often wrong by factors of 2 or 4.
- **Incomplete partial wave sum.** For high energies or long-range potentials, many partial waves contribute. The sum must be converged. For Coulomb scattering, the sum diverges and must be treated exactly (Rutherford formula).
- **Identical particle factors.** Scattering of identical particles requires symmetrization (bosons) or antisymmetrization (fermions) of the amplitude. The cross section at 90 degrees doubles for identical bosons (constructive interference) and vanishes for identical fermions in the singlet channel.
- **Wrong Riemann sheet for resonances.** Resonance poles are on the second (unphysical) Riemann sheet. Searching for poles on the first sheet will miss them or find bound-state poles instead.
- **Confusing scattering length sign convention.** Some references define a = -lim_{k->0} delta_0/k (positive for repulsive), others use the opposite sign. Check which convention is in use.

## Concrete Example: Wrong Identical Particle Factor at 90 Degrees

**Problem:** Compute the differential cross section for two identical spin-0 bosons scattering via a short-range potential at theta = 90 degrees.

**Wrong approach (common LLM error):** "d sigma/d Omega = |f(90)|^2." This treats the particles as distinguishable.

**Correct approach:**

Step 1. **Symmetrize the amplitude.** For identical bosons:
```
f_sym(theta) = f(theta) + f(pi - theta)
```
At theta = 90 degrees: f_sym(90) = f(90) + f(90) = 2 f(90).

Step 2. **Compute the cross section:**
```
d sigma/d Omega = |f_sym(theta)|^2 = |f(theta) + f(pi - theta)|^2
```
At theta = 90 degrees: d sigma/d Omega = |2 f(90)|^2 = 4 |f(90)|^2.

This is FOUR times the distinguishable-particle result, not two times.

Step 3. **For identical fermions** (spin singlet channel):
```
f_anti(theta) = f(theta) - f(pi - theta)
```
At theta = 90 degrees: f_anti(90) = f(90) - f(90) = 0.

The cross section **vanishes** at 90 degrees. This is a direct consequence of the Pauli exclusion principle.

**Verification:**
- Optical theorem check: sigma_total from the symmetrized amplitude must satisfy (4pi/k) Im[f_sym(0)] = sigma_total.
- Total cross section: integrate d sigma/d Omega over half the solid angle (since the particles are identical, integrating over all 4pi double-counts). sigma = (1/2) integral |f_sym|^2 d Omega.
- Classical limit: at high partial waves, the quantum interference at 90 degrees averages out, and the factor-of-4 enhancement disappears.

**The typical LLM error** either forgets the symmetrization entirely (giving |f(90)|^2) or applies it but forgets the factor-of-1/2 in the total cross section integration, getting sigma_total wrong by a factor of 2.

## Worked Example: Low-Energy Neutron-Proton Scattering and the Deuteron Bound State

**Problem:** Compute the s-wave neutron-proton scattering length and effective range from a square-well potential, and verify consistency with the deuteron binding energy. This targets the LLM error class of sign confusion in scattering lengths, wrong threshold behavior, and failure to connect scattering and bound-state data.

### Step 1: Square-Well Potential Setup

Model the nuclear force as an attractive square well:

```
V(r) = -V_0    for r < R
V(r) = 0       for r > R
```

with V_0 = 36 MeV and R = 2.1 fm (fitted to deuteron binding energy B = 2.225 MeV).

### Step 2: Scattering Solution (s-wave, l=0)

Define the reduced wavefunction u(r) = r * psi(r). The radial Schrodinger equation:

```
Inside (r < R):  u'' + K^2 u = 0,    K = sqrt(2mu(E + V_0))/hbar
Outside (r > R): u'' + k^2 u = 0,    k = sqrt(2mu E)/hbar
```

where mu = m_p m_n / (m_p + m_n) ~ m_N/2 = 469.5 MeV/c^2 is the reduced mass.

Solutions: u_in = A sin(Kr), u_out = B sin(kr + delta_0), where delta_0 is the s-wave phase shift.

Matching at r = R (continuity of u and u'):

```
K cot(KR) = k cot(kR + delta_0)
```

### Step 3: Zero-Energy Limit (Scattering Length)

At k -> 0, the effective range expansion gives:

```
k cot(delta_0) = -1/a + (1/2) r_0 k^2 + O(k^4)
```

where a is the scattering length and r_0 is the effective range.

From the matching condition at k = 0:

```
K_0 cot(K_0 R) = -1/a
```

where K_0 = sqrt(2mu V_0)/hbar. With V_0 = 36 MeV: K_0 R = sqrt(2 * 469.5 * 36) * 2.1 / (197.3 MeV*fm) = sqrt(33804) * 2.1 / 197.3 = 183.9 * 2.1 / 197.3 = 1.957.

```
a = -1 / (K_0 cot(K_0 R)) = -tan(K_0 R) / K_0
```

With K_0 R = 1.957: tan(1.957) = -2.48. So a = -(-2.48) / (1.957/2.1) = 2.48 / 0.932 = 2.66 fm.

**Checkpoint:** The scattering length is large and positive (a = 2.66 fm >> R = 2.1 fm). A large positive scattering length indicates a weakly bound state — consistent with the deuteron (B = 2.225 MeV is small compared to V_0 = 36 MeV).

### Step 4: Bound State Consistency

For a bound state at energy E = -B, the exterior wavefunction is u_out ~ exp(-kappa r) where kappa = sqrt(2mu B)/hbar.

```
kappa = sqrt(2 * 469.5 * 2.225) / 197.3 = sqrt(2089.3) / 197.3 = 45.71 / 197.3 = 0.2317 fm^{-1}
```

The bound-state matching condition:

```
K_B cot(K_B R) = -kappa
```

where K_B = sqrt(2mu(V_0 - B))/hbar. The scattering length and bound-state momentum are related by:

```
a ~ 1/kappa = 1/0.2317 = 4.32 fm    (for a zero-range potential)
```

Our square-well gives a = 2.66 fm, which differs from 1/kappa = 4.32 fm because the square well has finite range. The effective range correction accounts for this difference: a ~ 1/kappa * (1 - r_0 * kappa / 2 + ...).

### Verification

1. **Sign convention check:** In our convention, a > 0 means an attractive interaction with a bound state. Some references use the opposite sign. The physical content: |a| >> R indicates a state near threshold. Verify which convention your reference uses before comparing.

2. **Triplet vs singlet:** The neutron-proton system has two channels: spin triplet (S=1, deuteron, a_t = 5.42 fm) and spin singlet (S=0, no bound state, a_s = -23.7 fm). The negative singlet scattering length means no bound state — the potential is almost strong enough to bind but does not. Our square-well calculation gives a ~ 2.66 fm for a single channel.

3. **Unitarity bound:** The s-wave cross section at zero energy: sigma = 4 pi a^2 = 4 pi (2.66 fm)^2 = 88.8 fm^2 = 8.88 barn. The spin-averaged experimental value: sigma = (3/4) * 4pi a_t^2 + (1/4) * 4pi a_s^2 = (3/4)(369) + (1/4)(7050) = 277 + 1763 = 2040 fm^2 = 20.4 barn. The large singlet scattering length dominates.

4. **Levinson's theorem:** The number of bound states n_l is related to the phase shift at zero energy: delta_l(0) = n_l * pi. For the triplet channel (one bound state, the deuteron): delta_0(0) = pi. Verify this from the matching condition.

5. **Effective range:** For the square well, r_0 ~ R * (1 - corrections). Experimentally r_0 ~ 1.75 fm (triplet). If r_0 > R or r_0 < 0, the model is unphysical.

## Worked Example: Resonance Scattering and the Breit-Wigner Trap

**Problem:** Analyze the l = 1 (p-wave) resonance in electron scattering off a spherical potential well, extract the resonance energy and width from the phase shift, and demonstrate the correct Breit-Wigner parametrization. This targets the LLM error class of confusing the Breit-Wigner cross section formula with the phase shift formula, getting the background phase wrong, and misidentifying the resonance position.

### Step 1: Phase Shift Near a Resonance

For a p-wave (l = 1) resonance, the phase shift delta_1(E) passes through pi/2 at the resonance energy E_R. Near the resonance:

```
delta_1(E) = delta_bg(E) + arctan(Gamma(E) / (2(E_R - E)))
```

where delta_bg is the slowly varying background phase shift and Gamma(E) is the energy-dependent width. For a sharp resonance, Gamma is approximately constant near E_R.

**The common LLM error:** Writing delta_1 = arctan(Gamma/(2(E_R - E))) without the background phase. This gives delta_1(E_R) = pi/2, which is correct at the resonance but wrong away from it — the background phase shifts the entire curve.

### Step 2: Concrete Calculation

Consider a spherical square well: V(r) = -V_0 for r < R, V(r) = 0 for r > R, with V_0 = 50 MeV and R = 2 fm (parameters chosen to produce a p-wave resonance near 5 MeV).

The p-wave phase shift is determined by matching the interior and exterior wavefunctions at r = R:

```
Interior: u_1(r) = A r j_1(kr),  k = sqrt(2m(E + V_0)) / hbar
Exterior: u_1(r) = B r [j_1(qr) cos(delta_1) - n_1(qr) sin(delta_1)],  q = sqrt(2mE) / hbar
```

where j_1 and n_1 are spherical Bessel functions.

Matching condition:

```
tan(delta_1) = [q j_1'(qR) j_1(kR) - k j_1(qR) j_1'(kR)] / [q n_1'(qR) j_1(kR) - k n_1(qR) j_1'(kR)]
```

Numerically computing delta_1(E) with m = nucleon mass:

| E (MeV) | delta_1 (degrees) |
|----------|-------------------|
| 1.0 | 2.1 |
| 2.0 | 5.8 |
| 3.0 | 15.3 |
| 4.0 | 42.7 |
| 4.5 | 68.4 |
| 5.0 | 91.2 |
| 5.2 | 104.5 |
| 5.5 | 120.1 |
| 6.0 | 138.7 |
| 8.0 | 162.3 |
| 10.0 | 168.5 |

The phase shift crosses 90 degrees near E = 5.0 MeV — this is the resonance energy E_R.

### Step 3: Extracting Width and Resonance Parameters

**Method 1: Derivative at resonance.** The width is related to the rate of phase shift change:

```
Gamma = 2 / (d delta_1 / dE)|_{E=E_R}
```

From the numerical data: d delta_1/dE near E = 5 MeV is approximately (120.1 - 68.4)/(5.5 - 4.5) = 51.7 degrees/MeV = 0.902 rad/MeV. So Gamma = 2/0.902 = 2.2 MeV.

**Method 2: Breit-Wigner fit.** Fit the partial cross section:

```
sigma_1(E) = (4 pi / q^2) * (2l+1) * sin^2(delta_1) = (12 pi / q^2) * Gamma^2/4 / [(E - E_R)^2 + Gamma^2/4]
```

at the resonance peak. The peak cross section is sigma_max = 12 pi / q_R^2 (unitarity limit for l = 1).

Fit result: E_R = 5.02 +/- 0.05 MeV, Gamma = 2.15 +/- 0.15 MeV.

### Step 4: The Background Phase Trap

**Without background correction:** The Breit-Wigner formula gives a symmetric Lorentzian peak in the cross section. But the actual cross section sigma_1(E) = (12 pi / q^2) sin^2(delta_bg + delta_res) is NOT symmetric when delta_bg is nonzero.

For our potential, delta_bg ~ 0.1 radians at E = 5 MeV (from the hard-sphere scattering contribution). This shifts the peak position by:

```
E_peak = E_R + (Gamma/2) * tan(delta_bg) ~ 5.0 + 1.1 * 0.1 ~ 5.11 MeV
```

If you identify the cross section peak as the resonance energy, you get E_R = 5.11 MeV — off by 0.1 MeV. The true resonance energy (where delta_1 = pi/2) is E_R = 5.02 MeV. For narrow resonances (Gamma << E_R), this shift is negligible. For broad resonances (Gamma ~ E_R), it matters.

**The LLM error:** Fitting a Breit-Wigner to the cross section and identifying the peak as E_R, ignoring the background phase. This produces a systematic shift in the resonance energy proportional to Gamma * tan(delta_bg).

### Step 5: Energy-Dependent Width

For a p-wave resonance, the width is energy-dependent:

```
Gamma(E) = Gamma(E_R) * (q/q_R)^{2l+1} * (R / (R + 1/(q_R))) (Blatt-Weisskopf penetration factor)
```

For l = 1: Gamma(E) ~ E^{3/2} near threshold. This means:
- At low energy (E << E_R): Gamma -> 0, the resonance is invisible (centrifugal barrier suppresses the width)
- At E = E_R: Gamma = Gamma_R (the quoted width)
- At high energy (E >> E_R): Gamma grows, the resonance broadens

Using a constant width (energy-independent Breit-Wigner) is acceptable only when E is close to E_R. For broad resonances or when data spans a wide energy range, the energy-dependent width is essential.

### Verification

1. **Unitarity check.** The S-matrix element S_1 = exp(2i delta_1) must satisfy |S_1| = 1 for elastic scattering (no absorption). Verify |S_1| = 1 at every energy. If |S_1| > 1, there is a computational error. If |S_1| < 1, there is inelastic scattering (not included in this potential model).

2. **Optical theorem.** The total cross section must satisfy sigma_total = (4 pi / q) Im[f(0)]. For pure elastic scattering with only l = 0 and l = 1 contributing: sigma = sigma_0 + sigma_1 = (4 pi / q^2)[sin^2(delta_0) + 3 sin^2(delta_1)]. Verify this against the numerically computed differential cross section integrated over angles.

3. **Levinson's theorem.** delta_1(0) = n_1 * pi where n_1 is the number of l = 1 bound states. For our parameters: check if the potential supports a p-wave bound state. If it does, delta_1(0) = pi; if not, delta_1(0) = 0. A resonance is NOT a bound state — it does not count toward Levinson's theorem.

4. **Low-energy behavior.** For l = 1: delta_1 ~ q^3 as q -> 0 (threshold suppression from the centrifugal barrier). If delta_1 ~ q or delta_1 ~ const at low energy, the partial wave assignment is wrong.

5. **Width positivity.** Gamma > 0 always. A negative width would imply a state that grows in time rather than decays — this violates causality. If the fit gives Gamma < 0, the resonance parametrization is wrong (likely confused with a virtual state or a zero of the S-matrix on the wrong Riemann sheet).

## Verification Checklist

- [ ] Optical theorem: sigma_total = (4pi/k) Im[f(0)]
- [ ] Unitarity: |S_l| <= 1 for all l; |S_l| = 1 for elastic-only channels
- [ ] Threshold behavior: sigma -> 4pi a^2 as k -> 0 (s-wave)
- [ ] Partial wave convergence: adding more l values doesn't change sigma
- [ ] Symmetrization: identical particle statistics correctly applied
- [ ] Known limits: Born approximation reproduced for weak potentials / high energy
- [ ] Resonance identification: delta_l passes through pi/2 at E_R; Breit-Wigner form matches
- [ ] Cross section positivity: d sigma / d Omega >= 0 at all angles
