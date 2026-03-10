---
load_when:
  - "transport coefficient"
  - "Kubo formula"
  - "Keldysh"
  - "Boltzmann equation"
  - "conductivity"
  - "linear response"
  - "non-equilibrium"
  - "viscosity"
tier: 2
context_cost: high
---

# Non-Equilibrium Transport Protocol

Transport coefficients connect microscopic dynamics to macroscopic observables: electrical and thermal conductivity, viscosity, diffusion constants. Errors in transport calculations are insidious because they often produce results that are dimensionally correct and even order-of-magnitude reasonable, but miss crucial physics (vertex corrections, memory effects, non-Markovian dynamics).

## Related Protocols

- See `perturbation-theory.md` for diagrammatic expansion of response functions
- See `analytic-continuation.md` for Matsubara-to-real-frequency continuation in Kubo formulas
- See `numerical-computation.md` for numerical evaluation of transport integrals
- See `kinetic-theory.md` for Boltzmann equation approach to transport coefficients (Chapman-Enskog, relaxation time)
- See `fluid-dynamics-mhd.md` for MHD transport (Braginskii viscosity, Spitzer resistivity, anomalous transport in turbulence)

## Overview

Four major frameworks exist for non-equilibrium transport, each with its own domain of applicability:

| Framework | Regime | Key Quantity | Validity |
|---|---|---|---|
| Kubo formulas (linear response) | Weak external perturbation | Retarded current-current correlator | Perturbation linear in applied field |
| Keldysh formalism | Arbitrary non-equilibrium | Contour-ordered Green's functions | Exact (requires approximations in practice) |
| Boltzmann equation | Semiclassical, dilute | Distribution function f(r, k, t) | Quasiparticle picture valid, λ_F ≪ mean free path |
| Memory function (Mori-Zwanzig) | Any; systematic projection | Memory kernel M(t) | Exact as a formal identity; useful with physical truncation |

## Step 1: Kubo Formula (Linear Response)

The Kubo formula gives the linear response of observable A to a perturbation that couples to observable B:

```
χ_AB^R(ω) = -i ∫₀^∞ dt e^{iωt} ⟨[A(t), B(0)]⟩_eq
```

**Checklist:**

1. **Identify the correct current operator.** For electrical conductivity: j = (e/m) Σᵢ pᵢ (paramagnetic) + (e²/mc) Σᵢ A(rᵢ) (diamagnetic). The diamagnetic term is often forgotten — it contributes a frequency-independent piece.
2. **Use the RETARDED correlator, not the time-ordered one.** Kubo formula requires G^R, not G^F. At T = 0 they are related by Im[G^R] = sign(ω) Im[G^F], but at finite T they differ. `references/verification/errors/llm-physics-errors.md` #17 (correlation/response confusion).
3. **Include vertex corrections.** The bare bubble (two single-particle Green's functions) misses vertex corrections. For conserved currents, the Ward identity requires specific vertex corrections to ensure conservation. Omitting them violates gauge invariance and gives gauge-dependent transport coefficients.
4. **Take the correct order of limits.** For DC conductivity: σ_DC = lim_{ω→0} lim_{q→0} σ(q, ω). The limits do NOT commute: lim_{q→0} lim_{ω→0} gives the Drude weight (reactive), not the dissipative conductivity. See `order-of-limits.md`.
5. **Check the f-sum rule.** ∫₀^∞ Re[σ(ω)] dω = πne²/(2m). This is an exact relation that constrains the integral of the conductivity. Violation indicates an error (usually missing the diamagnetic term).

**Common error modes (Kubo):**

- Missing diamagnetic contribution → violates f-sum rule
- Using time-ordered instead of retarded correlator → wrong transport coefficient at finite T
- Missing vertex corrections → gauge-dependent result, wrong magnitude
- Wrong order of q→0 and ω→0 limits → confusing Drude weight with DC conductivity
- Forgetting the contact term (equal-time commutator) in the current-current correlator

## Step 2: Keldysh Formalism

For systems driven out of equilibrium (finite bias, time-dependent fields, quench dynamics), the Keldysh contour formalism is required.

**Checklist:**

1. **Define the Keldysh contour.** The contour runs from t = -∞ to t = +∞ (forward branch, +) and back from t = +∞ to t = -∞ (backward branch, −). Operators on the + branch are time-ordered; operators on the − branch are anti-time-ordered.
2. **Identify the four Green's functions.** G^{++} = G^T (time-ordered), G^{--} = G^T̃ (anti-time-ordered), G^{+-} = G^< (lesser), G^{-+} = G^> (greater). Only three are independent: G^T + G^T̃ = G^< + G^>.
3. **Perform the Keldysh rotation.** Transform to the retarded/advanced/Keldysh basis: G^R = G^T - G^< = G^> - G^T̃, G^A = G^T - G^> = G^< - G^T̃, G^K = G^< + G^> = G^T + G^T̃ (Keldysh component). In equilibrium: G^K = (G^R - G^A) coth(ω/(2T)) (fluctuation-dissipation theorem).
4. **Check the fluctuation-dissipation theorem (FDT).** In equilibrium, G^K(ω) = [G^R(ω) - G^A(ω)] × coth(βω/2). Violation of FDT indicates genuine non-equilibrium. If your system is supposed to be in equilibrium but FDT is violated, there is an error.
5. **Verify causality.** G^R(t < 0) = 0 (retarded vanishes for negative times). G^A(t > 0) = 0 (advanced vanishes for positive times). The Keldysh component G^K has no such constraint.

**Common error modes (Keldysh):**

- Wrong sign convention for the backward branch → all signs wrong
- Confusing G^< and G^> → wrong occupation factors
- Not performing the Keldysh rotation → unnecessarily complicated expressions with redundant components
- Applying FDT in a non-equilibrium situation → wrong distribution function
- Incorrect self-energy structure on the Keldysh contour → violating conservation laws

## Step 3: Boltzmann Equation

The semiclassical Boltzmann equation governs the distribution function f(r, k, t):

```
∂f/∂t + v_k · ∇_r f + F · ∇_k f = I_coll[f]
```

**Checklist:**

1. **Verify the semiclassical regime.** The Boltzmann equation requires: (a) well-defined quasiparticles (spectral function sharply peaked), (b) λ_F ≪ mean free path (wavelength much smaller than scattering length), (c) ℏω ≪ E_F (energy transfers small compared to Fermi energy). If any condition fails, use Keldysh or Kubo instead.
2. **Construct the collision integral correctly.** For impurity scattering: I_coll = Σ_k' W_{kk'} [f(k') - f(k)], where W_{kk'} is the scattering rate (Fermi golden rule). For electron-phonon: include both emission and absorption processes with proper Bose factors. For electron-electron: the collision integral is bilinear in f (two particles in, two out).
3. **Verify detailed balance.** In equilibrium (f = f₀), the collision integral must vanish: I_coll[f₀] = 0. This requires W_{kk'} f₀(k)(1-f₀(k')) = W_{k'k} f₀(k')(1-f₀(k)) (microscopic reversibility). Check this explicitly for your scattering rates.
4. **Check conservation laws from the collision integral.** Particle number: Σ_k I_coll = 0. Energy: Σ_k ε_k I_coll = 0 (for elastic scattering). Momentum: Σ_k k I_coll ≠ 0 in general (momentum relaxation), but = 0 for electron-electron scattering (momentum-conserving).
5. **Verify Onsager reciprocity.** The transport coefficient matrix L_{ij} (relating currents J_i to forces X_j via J_i = Σ_j L_{ij} X_j) must satisfy L_{ij}(B) = L_{ji}(-B) in a magnetic field. Without magnetic field: L_{ij} = L_{ji} (symmetric). Violation indicates missing physics or computational error.

**Common error modes (Boltzmann):**

- Using Boltzmann equation outside its validity regime (strongly correlated systems, non-quasiparticle transport)
- Wrong collision integral (missing Pauli blocking factors, wrong energy conservation delta function)
- Violating detailed balance → non-physical steady state
- Relaxation time approximation I_coll = -(f - f₀)/τ when τ depends on energy → wrong Seebeck coefficient
- Missing umklapp processes → infinite thermal conductivity in crystals

## Step 4: Memory Function Formalism (Mori-Zwanzig)

The memory function approach projects the full dynamics onto a subspace of slow variables, giving an exact generalized Langevin equation:

```
dA(t)/dt = iΩA(t) - ∫₀^t M(t-t') A(t') dt' + F(t)
```

where Ω is the frequency matrix, M(t) is the memory kernel, and F(t) is the projected (fast) force.

**Checklist:**

1. **Choose the slow variables carefully.** The set of slow variables must include all conserved quantities (energy, momentum, particle number) plus any other modes that are slow (order parameters near a phase transition, hydrodynamic modes). Missing a slow variable produces large, slowly-decaying memory functions — a sign that the projection is incomplete.
2. **Verify the exact sum rules.** The memory function formalism satisfies exact frequency sum rules: the zeroth moment of the spectral function gives the static susceptibility, the second moment gives the frequency matrix Ω. These are computable from equal-time correlators and serve as consistency checks.
3. **Truncation of the continued fraction.** The memory function can be expanded in a continued fraction. Truncating at the first level gives a single-relaxation-time result. Higher levels give better approximations. Verify convergence by comparing successive truncation levels.
4. **Check that the static limit is correct.** As ω → 0, the transport coefficient from the memory function must agree with the Kubo formula result. This is an exact identity, not an approximation.

**Common error modes (Mori-Zwanzig):**

- Incomplete set of slow variables → large memory function, poor convergence
- Wrong inner product (must use the Mori inner product ⟨A|B⟩ = β⟨A†B⟩ for classical, Kubo inner product for quantum)
- Confusing the memory function with the self-energy (related but distinct)
- Truncating the continued fraction too early without checking convergence

## Worked Example: Drude Conductivity of a Free Electron Gas via Kubo Formula

**Problem:** Compute the optical conductivity sigma(omega) of a free electron gas with impurity scattering using the Kubo formula. Verify the f-sum rule, the DC limit, and the Wiedemann-Franz law. This example targets three common LLM errors: missing the diamagnetic term, wrong order of limits, and confusing the retarded and time-ordered correlators.

### Step 1: Set Up the Kubo Formula

The optical conductivity is the retarded current-current correlator:

```
sigma(omega) = (i/omega) [Pi^R(omega) + n e^2/m]
```

where Pi^R(omega) is the retarded polarization (paramagnetic current-current correlator) and n e^2/m is the diamagnetic term. The diamagnetic contribution is frequency-independent and ensures sigma(omega -> infinity) -> 0.

**Parameters:** Free electron gas with density n = 8.5 x 10^{28} m^{-3} (roughly copper), effective mass m = m_e, elastic impurity scattering rate 1/tau = 2.5 x 10^{13} s^{-1} (tau = 40 fs).

### Step 2: Evaluate the Bubble Diagram

For non-interacting electrons with impurity scattering (self-energy Sigma^R(omega) = -i/(2 tau)), the paramagnetic retarded polarization is:

```
Pi^R(omega) = -(n e^2/m) * (1/(1 - i omega tau))^{-1}
            = -(n e^2/m) * 1/(1 - i omega tau)
```

Wait — this requires care. The bubble diagram gives:

```
Pi^R(omega) = (2/V) sum_k |<k|j_x|k>|^2 * [f(epsilon_k) - f(epsilon_{k})] / (omega + i/tau)
```

For free electrons where the current vertex is j_x = e k_x / m, evaluating the Matsubara sum and continuing to the retarded correlator:

```
Pi^R(omega) = -(n e^2/m) * [1 - i omega tau / (1 - i omega tau)]
            = -(n e^2/m) * 1/(1 - i omega tau)
```

Substituting into the Kubo formula:

```
sigma(omega) = (i/omega) [-(n e^2/m) * 1/(1 - i omega tau) + n e^2/m]
             = (i/omega) * (n e^2/m) * [1 - 1/(1 - i omega tau)]
             = (i/omega) * (n e^2/m) * [i omega tau / (1 - i omega tau)]
             = (n e^2 tau / m) * 1/(1 - i omega tau)
```

This is the Drude formula:

```
sigma(omega) = sigma_DC / (1 - i omega tau)
```

where sigma_DC = n e^2 tau / m.

### Step 3: Verify the Diamagnetic Term

**Without the diamagnetic term** (a common error):

```
sigma_WRONG(omega) = (i/omega) * Pi^R(omega) = (i/omega) * (-(n e^2/m)) / (1 - i omega tau)
```

At high frequency (omega tau >> 1):

```
sigma_WRONG(omega -> inf) = (i/omega) * (-(n e^2/m)) * (-1/(i omega tau)) = -n e^2/(m omega^2 tau)
```

This goes to zero, but the f-sum rule integral diverges logarithmically because sigma_WRONG has the wrong low-frequency behavior. Specifically:

```
Re[sigma_WRONG(omega)] = (n e^2/m) * tau / (1 + omega^2 tau^2)  [missing the sign!]
```

Actually, let us be precise. Without the diamagnetic term:

```
sigma_WRONG(omega) = -(i n e^2)/(m omega) * 1/(1 - i omega tau)
```

```
Re[sigma_WRONG(omega)] = (n e^2)/(m) * tau/(1 + omega^2 tau^2)
```

This happens to give the same Re[sigma] as the correct expression. The error shows up in Im[sigma]:

```
Im[sigma_WRONG(omega)] = -(n e^2)/(m omega) * 1/(1 + omega^2 tau^2)
```

which diverges as 1/omega at low frequency. The correct Im[sigma_Drude] has:

```
Im[sigma_Drude(omega)] = (n e^2 tau / m) * omega tau / (1 + omega^2 tau^2)
```

which vanishes at omega = 0. The missing diamagnetic term changes Im[sigma] qualitatively and violates the Kramers-Kronig relation between Re[sigma] and Im[sigma].

### Step 4: Verify the Order of Limits

**DC conductivity (correct order):** lim_{omega -> 0} lim_{q -> 0} sigma(q, omega)

```
sigma_DC = lim_{omega -> 0} sigma_Drude(omega) = n e^2 tau / m
```

For copper: sigma_DC = (8.5e28)(1.6e-19)^2(40e-15) / (9.1e-31) = 9.6 x 10^6 Ohm^{-1} m^{-1}. Experimental: ~5.9 x 10^7. Order of magnitude correct; the factor-of-6 discrepancy is from using m = m_e instead of the effective mass m* ~ 1.5 m_e and from the more complex Fermi surface of real copper.

**Wrong order:** lim_{q -> 0} lim_{omega -> 0} sigma(q, omega) gives the Drude weight D = pi n e^2 / m (a delta function at omega = 0 in the clean limit), not the dissipative conductivity. In the clean limit (tau -> infinity), sigma_Drude(omega) -> pi (n e^2/m) delta(omega) + i n e^2/(m omega), which is purely reactive — the DC conductivity diverges. Taking omega -> 0 first at any finite q gives zero (for q != 0, the current-current correlator is finite and the 1/omega prefactor gives a well-defined limit). Taking q -> 0 first gives the delta function (infinite DC conductivity of a clean metal).

### Step 5: f-Sum Rule Check

The f-sum rule:

```
integral_0^inf Re[sigma(omega)] d omega = pi n e^2 / (2m)
```

Evaluate with the Drude formula:

```
integral_0^inf (n e^2 tau/m) / (1 + omega^2 tau^2) d omega = (n e^2 tau/m) * (pi/(2 tau)) = pi n e^2 / (2m)
```

Sum rule satisfied exactly. If the integral gives a different value, either the diamagnetic term is missing or there is a normalization error.

### Step 6: Wiedemann-Franz Law

The thermal conductivity in the Boltzmann framework for elastic impurity scattering:

```
kappa = (pi^2 / 3) * (k_B^2 T / e^2) * sigma
```

The Lorenz number:

```
L_0 = kappa / (sigma T) = pi^2 k_B^2 / (3 e^2) = 2.44 x 10^{-8} W Ohm K^{-2}
```

This is exact for elastic scattering and serves as a strong consistency check: if your Kubo formula gives a different Lorenz number for the free electron gas with elastic impurity scattering, there is an error in either the electrical or thermal conductivity calculation.

### Verification

1. **Dimensional analysis:** [sigma_DC] = [n][e]^2[tau]/[m] = m^{-3} * C^2 * s / kg = C^2 s / (kg m^3) = A^2 s^3 / (kg m^3) = 1/(Ohm m). Correct.

2. **f-sum rule:** Verified analytically above. Numerically: integrate Re[sigma(omega)] from 0 to 100/tau with trapezoidal rule. The integral should be pi*n*e^2/(2m) to within the truncation error of the upper cutoff.

3. **Kramers-Kronig:** Re[sigma(omega)] = (1/pi) P integral Im[sigma(omega')] / (omega' - omega) d omega'. Verify numerically at omega = 1/tau.

4. **DC limit:** sigma(omega=0) = n e^2 tau / m = sigma_DC. Not zero, not infinity, not complex.

5. **High-frequency limit:** sigma(omega >> 1/tau) -> i n e^2 / (m omega). Purely imaginary (reactive), decaying as 1/omega. If it approaches a constant, the diamagnetic term is missing.

6. **Onsager reciprocity:** For a single-component system with no magnetic field, the conductivity tensor is symmetric: sigma_{ij} = sigma_{ji}. For the isotropic free electron gas, sigma is diagonal and trivially symmetric.

7. **Positivity:** Re[sigma(omega)] = (n e^2 tau/m) / (1 + omega^2 tau^2) >= 0 for all omega. Negative Re[sigma] would indicate an error (it would mean the system absorbs negative energy from the field).

## Worked Example 2: Seebeck Coefficient — The Relaxation Time Approximation Trap

**Problem:** Compute the Seebeck coefficient (thermopower) S of a metal with energy-dependent scattering rate, and demonstrate that using an energy-independent relaxation time tau gives qualitatively wrong results. The Seebeck coefficient is the voltage generated per unit temperature gradient: V = S * Delta T. This example targets the most common LLM error in thermoelectric transport: using I_coll = -(f - f_0)/tau with constant tau, which gives S = 0 for a free electron gas (missing the entire physics).

### Step 1: Boltzmann Equation Setup

In the presence of an electric field E and a temperature gradient nabla T, the linearized Boltzmann equation for the deviation g(k) = f(k) - f_0(k) in the relaxation time approximation is:

```
g(k) = -tau(epsilon_k) * (-df_0/d epsilon) * [v_k . (e E + (epsilon_k - mu) nabla T / T)]
```

where tau(epsilon_k) is the energy-dependent relaxation time and v_k = (1/hbar) d epsilon_k / dk is the group velocity.

The electrical current density and heat current density are:

```
J_e = (2/V) sum_k (-e) v_k g(k) = L_11 E + L_12 (-nabla T / T)
J_q = (2/V) sum_k (epsilon_k - mu) v_k g(k) = L_21 E + L_22 (-nabla T / T)
```

The Onsager coefficients L_ij are:

```
L_n = (2 e^{2-n} / (3 m V)) sum_k tau(epsilon_k) v_k^2 (epsilon_k - mu)^{n-1} (-df_0/d epsilon)
```

For a 3D free electron gas with density of states N(epsilon) = (2m)^{3/2} sqrt(epsilon) / (4 pi^2 hbar^3):

```
L_n = (e^{2-n} sigma_0 / e^2) * integral d epsilon (-df_0/d epsilon) tau(epsilon) (epsilon/E_F) (epsilon - mu)^{n-1}
```

where sigma_0 = n e^2 <tau> / m with <tau> being the Fermi-surface average.

### Step 2: The Seebeck Coefficient

The Seebeck coefficient is defined under open-circuit conditions (J_e = 0):

```
S = -L_12 / (T L_11) = -(1/eT) * integral d epsilon (-df_0/d epsilon) tau(epsilon) (epsilon - mu) epsilon / [integral d epsilon (-df_0/d epsilon) tau(epsilon) epsilon]
```

### Step 3: Constant tau (WRONG — gives S = 0 at leading order)

With tau = tau_0 (energy-independent):

```
L_12 / L_11 = integral d epsilon (-df_0/d epsilon) (epsilon - mu) epsilon / integral d epsilon (-df_0/d epsilon) epsilon
```

At low temperature, (-df_0/d epsilon) is sharply peaked at epsilon = mu. Expanding to leading order: the numerator is integral d epsilon (-df_0/d epsilon) (epsilon - mu) epsilon. Since (-df_0/d epsilon) is symmetric about mu, the factor (epsilon - mu) makes the integrand antisymmetric, and the leading-order integral vanishes.

The next-order contribution (Sommerfeld expansion):

```
S_const_tau = -(pi^2 / 3) * (k_B^2 T / e) * [d ln N(epsilon) / d epsilon]_{epsilon = mu}
```

For the free electron gas, N(epsilon) ~ epsilon^{1/2}, so d ln N / d epsilon = 1/(2 epsilon):

```
S_const_tau = -(pi^2 / 3) * (k_B^2 T / e) * 1/(2 E_F)
```

This gives S ~ -T/E_F, which IS nonzero but misses the tau-dependent contribution entirely.

### Step 4: Energy-Dependent tau (CORRECT — captures the physics)

For phonon scattering in a metal: tau(epsilon) ~ epsilon^{r} with r depending on the scattering mechanism:
- Acoustic phonon (deformation potential): r = -1/2
- Acoustic phonon (piezoelectric): r = 1/2
- Ionized impurity (Coulomb): r = 3/2
- Neutral impurity: r = 0 (constant tau)

The Seebeck coefficient with energy-dependent tau:

```
S = -(pi^2 / 3) * (k_B^2 T / e) * [d ln(tau(epsilon) N(epsilon)) / d epsilon]_{epsilon = mu}
   = -(pi^2 / 3) * (k_B^2 T / e) * [r/E_F + 1/(2 E_F)]
   = -(pi^2 / 3) * (k_B^2 T / (e E_F)) * (r + 1/2)
```

| Scattering mechanism | r | S / [-(pi^2/3)(k_B^2 T)/(e E_F)] |
|---------------------|---|----------------------------------|
| Constant tau (wrong) | 0 | 1/2 |
| Acoustic deformation | -1/2 | 0 (!) |
| Acoustic piezoelectric | 1/2 | 1 |
| Ionized impurity | 3/2 | 2 |

**THE TRAP:** For acoustic deformation potential scattering (the dominant mechanism in most metals at room temperature), using constant tau gives S proportional to 1/2, while the correct energy-dependent tau gives S = 0 (the density of states and scattering rate contributions cancel exactly). The physics is: faster electrons scatter more, slower electrons scatter less, and for this specific scattering mechanism the two effects cancel perfectly.

### Step 5: Numerical Values

For copper at T = 300 K, E_F = 7.0 eV:
- pi^2 k_B^2 T / (3 e E_F) = pi^2 * (8.617e-5)^2 * 300 / (3 * 7.0) = 1.22 x 10^{-6} V/K = 1.22 μV/K

With constant tau: S = -0.61 μV/K
With ionized impurity scattering (r = 3/2): S = -2.44 μV/K
Experimental (copper, 300 K): S = +1.84 μV/K

The sign is POSITIVE for copper, while the free-electron model gives negative S. This is because the Fermi surface of copper is not spherical — it touches the Brillouin zone boundary, creating regions where d epsilon/dk changes sign (electron-like and hole-like carriers). The positive sign requires going beyond the parabolic band approximation.

### Verification

1. **Onsager reciprocity:** L_12 = L_21 (the Peltier coefficient Pi = T * S follows from this). If L_12 ≠ L_21 in your calculation, there is an error in the collision integral or the current operators.

2. **Mott formula check:** At low T, the exact result is S = -(pi^2/3)(k_B^2 T/e) * d ln sigma(epsilon) / d epsilon |_{E_F}. This is the Mott formula. Verify your Seebeck coefficient reproduces this when sigma(epsilon) = n(epsilon) e^2 tau(epsilon) / m.

3. **Dimensional analysis:** [S] = V/K. [k_B^2 T / (e E_F)] = (J/K)^2 * K / (C * J) = J / (C * K) = V/K. Correct.

4. **Wiedemann-Franz consistency:** Compute the electronic thermal conductivity kappa_e and verify the Lorenz number L = kappa_e / (sigma T). For elastic scattering: L = L_0 = pi^2 k_B^2 / (3 e^2). If L deviates significantly from L_0, the energy integrals are inconsistent.

5. **Sign check:** For a free electron gas (parabolic band, spherical Fermi surface), S is always NEGATIVE (electrons carry heat from hot to cold, creating a potential that opposes further flow). A positive Seebeck coefficient requires non-trivial band structure. If your free-electron calculation gives S > 0, check the sign convention.

6. **High-T limit:** At T >> E_F (classical limit), S -> -k_B/e * (5/2 - ln(n lambda_th^3 / g_s)) where lambda_th is the thermal de Broglie wavelength. This is the classical entropy per particle divided by charge.

### What Goes Wrong Without This Protocol

**Scenario:** Researcher computes the thermoelectric figure of merit ZT = S^2 sigma T / kappa for a new thermoelectric material using Boltzmann transport with constant tau.

**The error:** With constant tau, the Seebeck coefficient is determined solely by the density of states slope at the Fermi level. But in real materials, energy-dependent scattering (resonant scattering, energy filtering, grain boundary scattering) is the PRIMARY mechanism used to enhance S. A constant-tau calculation misses this entirely and underestimates S by factors of 2-5 for materials engineered to have energy-dependent scattering. The resulting ZT prediction is wrong by a factor of 4-25 (since ZT goes as S^2).

**The fix:** Always use energy-dependent tau(epsilon) matching the dominant scattering mechanism. If the scattering mechanism is unknown, compute S for multiple power laws tau ~ epsilon^r and report the range.

## Verification Criteria

After any transport calculation, verify:

1. **Dimensional analysis.** Conductivity: [σ] = Ω⁻¹m⁻¹. Thermal conductivity: [κ] = W/(m·K). Viscosity: [η] = Pa·s. Diffusion: [D] = m²/s.
2. **Onsager reciprocity.** L_{ij}(B) = L_{ji}(-B). The thermoelectric tensor must be symmetric (without B field).
3. **Positivity.** σ ≥ 0, κ ≥ 0, η ≥ 0. Negative transport coefficients indicate an error (except for Hall conductivity σ_xy, which can be negative).
4. **Sum rules.** f-sum rule for optical conductivity. Kramers-Kronig relations between Re[σ(ω)] and Im[σ(ω)].
5. **Known limits.** Free electron gas: σ_Drude = ne²τ/m. Wiedemann-Franz: κ/σT = L₀ = π²k_B²/(3e²) at low T (exact for elastic scattering). Einstein relation: D = σ/(e²∂n/∂μ).
6. **Gauge independence.** Physical transport coefficients must be independent of the choice of gauge for the electromagnetic potential. Compute in two gauges and verify agreement.

## Worked Example: Shear Viscosity from the Kubo Formula — The Missing Vertex Correction

**Problem:** Compute the shear viscosity eta of a weakly interacting Fermi gas using the Kubo formula (stress-stress correlator) and demonstrate that the bare bubble diagram gives a result that violates the viscosity bound eta/s >= hbar/(4 pi k_B) at strong coupling, while including the correct vertex corrections restores the Ward identity and gives a parametrically different result. This targets the LLM error class of computing transport coefficients from bare bubble diagrams without vertex corrections, which violates conservation laws and produces gauge-dependent results.

### Step 1: Kubo Formula for Shear Viscosity

The shear viscosity is given by the retarded stress-stress correlator:

```
eta = lim_{omega->0} (1/omega) Im[G^R_{T_{xy} T_{xy}}(omega, q=0)]
```

where T_{xy} is the off-diagonal stress tensor component. For a Fermi gas with contact interaction (coupling g):

```
T_{xy} = sum_k (k_x k_y / m) c^dag_k c_k
```

### Step 2: Bare Bubble (No Vertex Corrections)

The bare bubble diagram (two Green's functions, no interaction vertex):

```
Pi^R_bare(omega) = (2/V) sum_k (k_x k_y / m)^2 * [G^R(k, omega) G^A(k, 0) + G^R(k, 0) G^A(k, -omega)]
```

With quasiparticle self-energy Im[Sigma^R] = -hbar/(2 tau):

```
eta_bare = (1/15) n E_F tau / hbar
```

where n is the density, E_F is the Fermi energy, and tau is the quasiparticle lifetime. This is the standard textbook result. For a weakly interacting Fermi gas at T << T_F: tau ~ (hbar E_F)/(k_B T)^2 and:

```
eta_bare ~ n hbar (E_F / k_B T)^2 / (k_B T)
```

### Step 3: Vertex Corrections

For the stress tensor, momentum conservation requires a vertex correction (the Aslamazov-Larkin diagram and Maki-Thompson diagram contribute). The Ward identity for the stress tensor relates the vertex to the self-energy:

```
Gamma_{xy}(k, k+q) = (k_x k_y / m) + delta Gamma(k, k+q)
```

where delta Gamma is determined by the Bethe-Salpeter equation.

For s-wave contact interactions in the unitarity limit (1/(k_F a) = 0):

```
eta_vertex = eta_bare * (1 + corrections from vertex)
```

The vertex corrections change the numerical prefactor. At unitarity:

```
eta_bare / (hbar n) = 0.50 * (E_F / k_B T)^2
eta_full / (hbar n)  = 0.30 * (E_F / k_B T)^2  (with vertex corrections)
```

The vertex corrections reduce eta by 40% at unitarity. For weaker interactions (k_F |a| << 1), the corrections are O(k_F |a|) and small.

### Step 4: The Viscosity Bound Test

The entropy density of the unitary Fermi gas at T ~ 0.5 T_F:

```
s ~ 3.5 n k_B
```

The KSS bound: eta/s >= hbar/(4 pi k_B) ~ 0.08 hbar/k_B.

| Method | eta/(hbar n) at T = 0.5 T_F | eta/s | Satisfies bound? |
|--------|----------------------------|-------|-----------------|
| Bare bubble | 2.0 | 0.57 hbar/k_B | Yes |
| With vertex | 1.2 | 0.34 hbar/k_B | Yes |
| Experiment (6Li) | 0.4-0.8 | 0.1-0.2 hbar/k_B | Yes (near bound) |

At this temperature, both methods give eta/s above the bound, but the bare bubble overestimates by 5x compared to experiment. The vertex-corrected result is still 2-3x too high because the perturbative calculation breaks down at unitarity. Quantum Monte Carlo gives eta/s ~ 0.2, close to the experimental value.

### Step 5: Why the Bare Bubble Fails

**Conservation law violation.** The stress tensor satisfies d_mu T^{mu nu} = 0. This implies a Ward identity relating the vertex to the self-energy. The bare bubble violates this Ward identity because it uses the bare vertex (k_x k_y / m) with a dressed propagator (including self-energy). This inconsistency means:

1. The result is gauge-dependent (changes if computed in a different gauge).
2. The f-sum rule for the stress-stress correlator is violated.
3. At strong coupling, the bare bubble can underestimate or overestimate eta by orders of magnitude.

**The fix:** Use a conserving approximation (Baym-Kadanoff). The self-energy Sigma and the vertex Gamma must be derived from the same generating functional Phi[G]. This guarantees the Ward identity is satisfied and transport coefficients are gauge-invariant.

### Verification

1. **f-sum rule.** integral Re[eta(omega)] d omega = n E_F / (6 pi) (for a 3D Fermi gas). This exact sum rule constrains the integral of the viscosity spectral function. Verify for both bare and vertex-corrected results. The bare bubble typically satisfies the sum rule to within 10-20%; the vertex-corrected result satisfies it exactly (by construction in a conserving approximation).

2. **Boltzmann equation cross-check.** In the weakly interacting regime (k_F |a| << 1), the Boltzmann equation gives eta = (15/(32 sqrt(2))) * (hbar n) * (k_F a)^{-2} * (E_F/(k_B T))^2 / (k_B T). Compare with the Kubo formula result. Agreement within 10% in the weakly interacting limit validates both methods.

3. **Onsager symmetry.** The viscosity tensor eta_{ijkl} relates the stress to the strain rate. For an isotropic system, there are only two independent viscosities (shear eta and bulk zeta). Verify: eta_{xyxy} = eta_{xzxz} = eta_{yxyx} (all equal by isotropy). If they differ, the calculation breaks rotational invariance.

4. **Low-T limit.** At T -> 0 for a Fermi liquid: eta ~ T^{-2} (growing as the quasiparticle lifetime tau ~ T^{-2} increases). If eta ~ T^{-1} or eta ~ const at low T, the scattering rate is wrong.

5. **Dimensional analysis.** [eta] = Pa * s = kg/(m * s). [n E_F tau] = m^{-3} * J * s = kg/(m * s). Correct.
