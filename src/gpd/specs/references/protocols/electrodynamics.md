---
load_when:
  - "electrodynamics"
  - "Maxwell equations"
  - "electromagnetic"
  - "radiation"
  - "Poynting vector"
  - "unit system"
  - "Gaussian units"
  - "SI units"
tier: 2
context_cost: high
---

# Electrodynamics Protocol

Electrodynamics calculations are plagued by unit system confusion more than any other subfield. The factor-of-4pi, epsilon_0, mu_0, and c placement differences between Gaussian and SI units produce wrong answers that look dimensionally correct within each system. This protocol ensures consistent electrodynamics calculations and catches the most common LLM errors.

## Related Protocols

- See `derivation-discipline.md` for sign tracking and convention annotation in all derivations
- See `integral-evaluation.md` for Green's function integrals and radiation integrals
- See `effective-field-theory.md` for low-energy effective descriptions of electrodynamics (Euler-Heisenberg, NRQED)

## Step 1: Declare and Lock the Unit System

Before writing any equation, declare the unit system and commit to it for the entire calculation.

1. **State the unit system explicitly.** The three common systems and their defining relations:

| System | Coulomb force | Maxwell: div E | Maxwell: curl B | Fine structure constant |
|---|---|---|---|---|
| **SI** | F = q_1 q_2 / (4 pi epsilon_0 r^2) | div E = rho / epsilon_0 | curl B = mu_0 J + mu_0 epsilon_0 dE/dt | alpha = e^2 / (4 pi epsilon_0 hbar c) |
| **Gaussian (CGS)** | F = q_1 q_2 / r^2 | div E = 4 pi rho | curl B = (4 pi / c) J + (1/c) dE/dt | alpha = e^2 / (hbar c) |
| **Heaviside-Lorentz** | F = q_1 q_2 / (4 pi r^2) | div E = rho | curl B = J + dE/dt (with c = 1) | alpha = e^2 / (4 pi) (with hbar = c = 1) |

2. **Record the charge conversion.** Charge has genuinely different dimensions in SI and Gaussian. This is not just a units rescaling — it reflects a fundamental choice in how electromagnetism is built into the dimensional system.

   **Why the dimensions differ:** SI introduces a fourth base dimension — the Ampere — independent of mass, length, and time. The permittivity of free space epsilon_0 carries dimensions [A^2 s^4 / (kg m^3)] and acts as a dimensional coupling constant relating mechanical and electromagnetic quantities. Charge in SI therefore has dimensions [A * s], irreducible to mass/length/time.

   Gaussian units have no independent electromagnetic dimension. Charge is derived entirely from mechanics via Coulomb's law: F = q^2 / r^2 implies [q^2] = [F][r^2] = [M L^3 T^{-2}], so [q] = [M^{1/2} L^{3/2} T^{-1}] (statcoulombs = g^{1/2} cm^{3/2} s^{-1}). There is no epsilon_0 in Gaussian units — it does not exist, not even implicitly.

   **Consequence:** A symbolic formula like q_SI = q_Gaussian / sqrt(4 pi epsilon_0) is dimensionally incoherent. The left side has dimensions [A s] and the right side has dimensions [M^{1/2} L^{3/2} T^{-1}] / [A s^2 / (M^{1/2} L^{3/2})] = [M L^3 T^{-2}]^{1/2} / [A s^2 / (M^{1/2} L^{3/2})], which only works if you treat epsilon_0 as a dimensional conversion factor — but then you are asserting that the Ampere is not truly independent, which contradicts the SI premise.

   **The correct approach:** Convert through a physical observable. In Gaussian units, F = q_G^2 / r^2. In SI, F = q_SI^2 / (4 pi epsilon_0 r^2). For the same physical force at the same distance:
   - q_G^2 [in CGS force * distance^2 units] = q_SI^2 / (4 pi epsilon_0) [in SI force * distance^2 units]
   - Numerically: 1 statC corresponds to 3.336 * 10^{-10} C
   - But this is a numerical correspondence, not a symbolic identity. The two q's live in different dimensional spaces.

3. **Record the field conversion.** Electric and magnetic fields have different dimensions in different systems:
   - E: E_SI (V/m) = E_Gaussian (statV/cm) * sqrt(4 pi epsilon_0). Numerically: 1 statV/cm = 2.998 * 10^4 V/m.
   - B: B_SI (Tesla) = B_Gaussian (Gauss) * 10^{-4}. But the Gaussian B has dimensions of E/c, while SI B has separate dimensions.
   - In Gaussian units: E and B have the same dimensions. In SI: they do not. This is the deepest source of conversion errors.

4. **If using natural units (hbar = c = 1):** State whether the electromagnetic sector is Heaviside-Lorentz (no 4pi in Maxwell equations, 4pi in Coulomb force) or Gaussian-natural (4pi in Maxwell equations, no 4pi in Coulomb force). Most particle physics uses Heaviside-Lorentz natural units. Most AMO and condensed matter uses Gaussian.

### Unit System Conversion Reference

To convert a formula from Gaussian to SI, apply these substitutions simultaneously:

```
Gaussian → SI substitutions (apply ALL at once, not sequentially):
  E → E                        (but dimensions change)
  B → B                        (but dimensions change)
  q → q                        (but dimensions change)
  rho → rho                    (but dimensions change)
  J → J                        (but dimensions change)

  In Coulomb's law and all electrostatic formulas:
    q^2 → q^2 / (4 pi epsilon_0)

  In all magnetostatic formulas:
    (1/c) → mu_0 / (4 pi)   [for current-related terms]

  In Maxwell equations:
    4 pi rho → rho / epsilon_0
    (4 pi / c) J → mu_0 J
    (1/c) dE/dt → mu_0 epsilon_0 dE/dt
    (1/c) dB/dt → dB/dt       [Faraday's law]

  In the Lagrangian density:
    -(1/16pi) F_{mu nu} F^{mu nu}  →  -(1/4) F_{mu nu} F^{mu nu}  [Heaviside-Lorentz]
```

**Verification:** After converting, check that alpha = e^2 / (4 pi epsilon_0 hbar c) ≈ 1/137 in SI, or alpha = e^2 / (hbar c) ≈ 1/137 in Gaussian. If alpha comes out different, the conversion is wrong.

## Step 2: Maxwell Equations and Constitutive Relations

1. **Write the full Maxwell equations** in the declared unit system. In SI:
   - div E = rho / epsilon_0 (Gauss's law)
   - div B = 0 (no magnetic monopoles)
   - curl E = -dB/dt (Faraday's law)
   - curl B = mu_0 J + mu_0 epsilon_0 dE/dt (Ampere-Maxwell)

2. **Distinguish E from D, and B from H.** In matter:
   - D = epsilon_0 E + P (SI) or D = E + 4 pi P (Gaussian)
   - H = B / mu_0 - M (SI) or H = B - 4 pi M (Gaussian)
   - The macroscopic Maxwell equations use (D, H) with free charges and currents.
   - The microscopic Maxwell equations use (E, B) with total charges and currents.
   - **Common LLM error:** Using E where D is needed (or vice versa) in boundary conditions. The boundary conditions are: [D_perp] = sigma_free, [E_parallel] = 0, [B_perp] = 0, [H_parallel] = K_free, where [] denotes the discontinuity across the interface.

3. **Boundary conditions at interfaces.** For an interface between media 1 and 2 with surface charge sigma_f and surface current K_f:
   - n_hat . (D_2 - D_1) = sigma_f
   - n_hat x (E_2 - E_1) = 0
   - n_hat . (B_2 - B_1) = 0
   - n_hat x (H_2 - H_1) = K_f
   - Here n_hat points from medium 1 into medium 2. Getting the sign convention for n_hat wrong flips the boundary conditions.

4. **Linear media.** For linear, isotropic media: D = epsilon E, B = mu H, J = sigma E. The permittivity epsilon, permeability mu, and conductivity sigma can be frequency-dependent (dispersive media). For anisotropic media, these become tensors. Always state whether epsilon means the relative permittivity epsilon_r or the absolute permittivity epsilon_0 * epsilon_r.

## Step 3: Electromagnetic Wave Propagation

1. **Wave equation in vacuum.** From Maxwell equations:
   - nabla^2 E - (1/c^2) d^2E/dt^2 = 0 (SI, vacuum)
   - nabla^2 B - (1/c^2) d^2B/dt^2 = 0
   - c = 1/sqrt(mu_0 epsilon_0) in SI. In Gaussian units c appears explicitly.

2. **Plane wave solutions.** E = E_0 exp(i(k.r - omega t)), B = (k_hat x E) / c (in vacuum).
   - The dispersion relation is omega = c |k| in vacuum, omega = c |k| / n in a medium with refractive index n = sqrt(epsilon_r mu_r).
   - **Sign convention:** exp(i(k.r - omega t)) vs exp(-i(k.r - omega t)). State which is in use. Physics convention typically uses exp(-i omega t) for time dependence; engineering convention uses exp(+j omega t). Mixing these reverses the sign of the imaginary part of epsilon, which flips absorption into gain.

3. **Energy and momentum.** The Poynting vector and energy density:
   - SI: S = E x H = (1/mu_0) E x B. Energy density: u = (epsilon_0/2) |E|^2 + (1/(2 mu_0)) |B|^2.
   - Gaussian: S = (c/4pi) E x B. Energy density: u = (1/8pi)(|E|^2 + |B|^2).
   - The factor-of-4pi and factor-of-c differences are the most common source of errors when computing power, intensity, and radiation pressure.

4. **Fresnel equations at interfaces.** For a plane wave incident on a planar interface between media with refractive indices n_1 and n_2:
   - r_s = (n_1 cos theta_i - n_2 cos theta_t) / (n_1 cos theta_i + n_2 cos theta_t)
   - r_p = (n_2 cos theta_i - n_1 cos theta_t) / (n_2 cos theta_i + n_1 cos theta_t)
   - Snell's law: n_1 sin theta_i = n_2 sin theta_t
   - **Sign convention warning:** The sign of r_p depends on the convention for the direction of E_p. Different textbooks use different conventions (Jackson vs Griffiths vs Born & Wolf). State which convention is used and verify against the known result: at normal incidence, r_s = r_p = (n_1 - n_2)/(n_1 + n_2).

5. **Waveguides and cavities.** For rectangular waveguides:
   - TE modes: E_z = 0, cutoff k_c^2 = (m pi/a)^2 + (n pi/b)^2
   - TM modes: B_z = 0, same cutoff formula
   - The propagation constant: k_z = sqrt(omega^2/c^2 - k_c^2). Below cutoff, k_z is imaginary (evanescent).
   - **Common error:** Confusing the mode indices (m, n) starting from 0 or 1. For TE modes in rectangular waveguides: m, n >= 0 but not both zero. For TM modes: m, n >= 1.

## Step 4: Electrostatics and Magnetostatics

1. **Electrostatic boundary value problems.** The electrostatic potential satisfies Laplace's equation (nabla^2 phi = 0) in charge-free regions and Poisson's equation (nabla^2 phi = -rho/epsilon_0 in SI, nabla^2 phi = -4 pi rho in Gaussian) in regions with charge.
   - **Uniqueness theorem:** The solution is unique given either the potential on all boundaries (Dirichlet) or the normal derivative on all boundaries (Neumann), or a combination (Robin). Over-specifying or under-specifying boundary conditions gives wrong results.
   - **Method of images:** Replace boundary conditions with image charges that produce the same boundary conditions. Verify by checking that the boundary conditions are satisfied and that the image charges are outside the region of interest.
   - **Multipole expansion:** phi(r) = (1/4pi epsilon_0) sum_{l,m} (4pi/(2l+1)) q_{lm} Y_{lm}(theta, phi) / r^{l+1} for r > R (source region). The multipole moments q_{lm} = integral rho(r') r'^l Y_{lm}^*(theta', phi') d^3r'. Watch for factors of 4pi/(2l+1) vs 1/(2l+1) depending on convention.

2. **Magnetostatics.** The vector potential satisfies nabla^2 A = -mu_0 J (SI, Coulomb gauge) or nabla^2 A = -(4pi/c) J (Gaussian, Coulomb gauge).
   - B = curl A always. But A is not unique: A → A + grad Lambda gives the same B.
   - **Magnetic multipole expansion:** The leading term for a localized current distribution is the magnetic dipole: m = (1/2) integral r' x J(r') d^3r'. The dipole field: B_dip = (mu_0/4pi)(3(m.r_hat)r_hat - m)/r^3 + (2 mu_0/3) m delta^3(r). The delta function term is often forgotten but matters for hyperfine structure and NMR.

## Step 5: Dispersive Media

In dispersive media, the permittivity epsilon(omega) and permeability mu(omega) are frequency-dependent. This frequency dependence is not optional — it is required by causality and has profound consequences for wave propagation, energy transport, and signal velocity. Treating dispersive media with constant epsilon produces wrong results for any broadband or transient phenomenon.

1. **Dispersion models.** The frequency-dependent dielectric function for common media:
   - **Drude model (metals):** epsilon(omega) = 1 - omega_p^2 / (omega^2 + i gamma omega), where omega_p is the plasma frequency and gamma is the damping rate. Valid for free-electron metals (alkali metals, noble metals below interband transitions).
   - **Lorentz model (dielectrics):** epsilon(omega) = 1 + sum_j f_j omega_{0j}^2 / (omega_{0j}^2 - omega^2 - i gamma_j omega), where omega_{0j} are resonance frequencies, f_j are oscillator strengths, and gamma_j are damping rates. Each resonance contributes a pole.
   - **Debye model (polar liquids):** epsilon(omega) = epsilon_inf + (epsilon_s - epsilon_inf) / (1 - i omega tau), where epsilon_s is the static permittivity, epsilon_inf is the high-frequency permittivity, and tau is the relaxation time. This is the omega -> 0 limit of the Lorentz model.
2. **Kramers-Kronig relations.** Causality requires that the real and imaginary parts of epsilon(omega) are not independent:
   Re[epsilon(omega)] - 1 = (2/pi) P integral_0^infinity omega' Im[epsilon(omega')] / (omega'^2 - omega^2) d omega'
   Im[epsilon(omega)] = -(2 omega / pi) P integral_0^infinity (Re[epsilon(omega')] - 1) / (omega'^2 - omega^2) d omega'
   Every model for epsilon(omega) MUST satisfy Kramers-Kronig. If it does not, the model violates causality. Verify Kramers-Kronig numerically for any fitted dielectric function.
3. **Group velocity vs phase velocity.** In a dispersive medium:
   - Phase velocity: v_p = omega / k = c / n(omega) where n(omega) = sqrt(epsilon(omega) mu(omega)).
   - Group velocity: v_g = d omega / dk = c / (n + omega dn/d omega). This is the velocity of a wavepacket near frequency omega. In regions of anomalous dispersion (dn/d omega < 0), v_g can exceed c or become negative — this does NOT violate relativity.
   - Signal velocity (Sommerfeld/Brillouin): the velocity of the front of a signal in a causal medium. Always <= c. This is the physically meaningful velocity for information propagation.
4. **Energy density in dispersive media.** The time-averaged energy density for a monochromatic wave in a dispersive, lossless medium:
   <u> = (1/4) d(omega epsilon)/d omega |E|^2 + (1/4) d(omega mu)/d omega |H|^2
   This reduces to the usual (epsilon/2)|E|^2 + (mu/2)|H|^2 only for non-dispersive media. Using the non-dispersive formula in a dispersive medium gives wrong energy balance. For lossy media (Im[epsilon] > 0), energy dissipation must be included and the time-averaged expression requires additional care.
5. **Negative index materials and metamaterials.** When both epsilon(omega) < 0 and mu(omega) < 0 in some frequency band, the refractive index n = -sqrt(|epsilon||mu|) (negative square root). This reverses: the direction of refraction (Snell's law with negative n), the Doppler shift, and Cherenkov radiation direction. Verify the sign of n from the requirement that the wave attenuates in the direction of propagation (Im[k] > 0 for a passive medium).

## Step 6: Radiation from Moving Charges

1. **Lienard-Wiechert potentials.** For a point charge q moving along trajectory r_0(t):
   - phi(r, t) = q / (4 pi epsilon_0) * 1 / (R - R_hat . v/c * R) |_{t_ret} (SI)
   - A(r, t) = (mu_0 q / 4pi) * v / (R - R_hat . v/c * R) |_{t_ret} (SI)
   - where R = r - r_0(t_ret), R = |R|, R_hat = R/R, and t_ret is the retarded time satisfying t_ret = t - R(t_ret)/c.
   - In Gaussian units: phi = q / (R - R_hat . v/c * R), A = q v / (c (R - R_hat . v/c * R)), all evaluated at t_ret.

2. **Retarded time.** The retarded time t_ret satisfies the implicit equation:
   - c(t - t_ret) = |r - r_0(t_ret)|
   - This is the most common source of errors. The fields depend on the charge's position and velocity at t_ret, not at t. Computing t_ret requires solving a transcendental equation.

3. **Radiation fields.** In the radiation zone (r >> lambda >> d, where d is the source size):
   - E_rad = (q / 4pi epsilon_0 c) * R_hat x ((R_hat - v/c) x a) / (1 - R_hat . v/c)^3 * 1/R |_{t_ret} (SI)
   - B_rad = R_hat x E_rad / c
   - The (1 - R_hat . v/c)^3 factor in the denominator produces relativistic beaming: radiation is concentrated in the forward direction for v ~ c.

4. **Larmor formula and its relativistic generalization.** Power radiated by an accelerated charge:
   - Non-relativistic (v << c): P = q^2 a^2 / (6 pi epsilon_0 c^3) (SI) = 2 q^2 a^2 / (3 c^3) (Gaussian)
   - Relativistic (Lienard formula): P = q^2 gamma^6 / (6 pi epsilon_0 c) * (a^2 - |v x a|^2/c^2) (SI)
   - **Common LLM error:** Using the non-relativistic Larmor formula for relativistic particles. The gamma^6 factor makes an enormous difference. For synchrotron radiation with gamma ~ 10^3, the relativistic formula gives 10^18 times the non-relativistic result.

5. **Angular distribution of radiation.** The power radiated per solid angle:
   - dP/dOmega = (q^2 / 16 pi^2 epsilon_0 c) * |R_hat x ((R_hat - beta) x a)|^2 / (1 - R_hat . beta)^5 (SI)
   - For v << c: dP/dOmega = (q^2 a^2 sin^2 theta) / (16 pi^2 epsilon_0 c^3) where theta is the angle between the acceleration and the observation direction.
   - **Common LLM error:** Wrong power of (1 - R_hat . beta) in the denominator. The correct power is 5 for the angular distribution and 3 for the fields. Confusion between these produces wrong beaming patterns.

## Step 7: Electromagnetic Duality

1. **Source-free duality.** In vacuum with no charges or currents, Maxwell's equations are invariant under the duality rotation:
   - E → E cos alpha + c B sin alpha
   - c B → -E sin alpha + c B cos alpha
   - (In Gaussian units: E → E cos alpha + B sin alpha, B → -E sin alpha + B cos alpha)
   - This is an SO(2) rotation in the (E, cB) plane. The energy density and Poynting vector are invariant.

2. **Duality with magnetic charges.** If magnetic monopoles exist (magnetic charge g, magnetic current K):
   - div B = mu_0 rho_m (SI) or div B = 4 pi rho_m (Gaussian)
   - curl E = -dB/dt - mu_0 K (SI) or curl E = -(1/c) dB/dt - (4 pi/c) K (Gaussian)
   - Full duality: (q, g) → (q cos alpha + g sin alpha, -q sin alpha + g cos alpha)
   - **Dirac quantization condition:** e g = n hbar c / 2 (Gaussian) or e g = n h / (2 mu_0) (SI), where n is an integer. This constrains the allowed values of magnetic charge.

3. **Duality in the covariant formulation.** The dual field strength tensor:
   - F*^{mu nu} = (1/2) epsilon^{mu nu rho sigma} F_{rho sigma}
   - Duality rotation: F^{mu nu} → F^{mu nu} cos alpha + F*^{mu nu} sin alpha
   - The source-free Maxwell equations can be written: d_mu F^{mu nu} = 0, d_mu F*^{mu nu} = 0. With sources: d_mu F^{mu nu} = J^{nu}_e, d_mu F*^{mu nu} = J^{nu}_m.

## Step 8: Multipole Radiation

1. **Electric dipole radiation.** For a time-varying electric dipole moment p(t):
   - E_rad = -(1/4 pi epsilon_0 c^2) * (r_hat x (r_hat x p_double_dot)) / r (SI)
   - P = p_double_dot^2 / (6 pi epsilon_0 c^3) (SI) = 2 p_double_dot^2 / (3 c^3) (Gaussian)
   - Angular distribution: dP/dOmega proportional to sin^2 theta (donut pattern).

2. **Magnetic dipole radiation.** For a time-varying magnetic dipole moment m(t):
   - P = mu_0 m_double_dot^2 / (6 pi c^3) (SI) = 2 m_double_dot^2 / (3 c^5) (Gaussian)
   - **Unit system trap:** In SI, the magnetic dipole power has mu_0 in the numerator. In Gaussian, it has c^5 in the denominator (because m has different dimensions). The ratio P_M1/P_E1 ~ (v/c)^2 in both systems, but the individual formulas look very different.

3. **Electric quadrupole radiation.** For a time-varying quadrupole moment Q_{ij}(t):
   - P = (1/180 pi epsilon_0 c^5) sum_{ij} Q_triple_dot_{ij}^2 (SI)
   - The ratio P_E2/P_E1 ~ (ka)^2 ~ (omega a / c)^2 where a is the source size. This is small for sources much smaller than the wavelength.

4. **Multipole ordering.** The hierarchy of radiation powers:
   - P_E1 >> P_M1 ~ P_E2 >> P_M2 ~ P_E3 >> ...
   - Each successive multipole is suppressed by (ka)^2 ~ (v/c)^2. Only include higher multipoles when lower ones vanish by symmetry (e.g., no electric dipole radiation from a symmetric oscillation).

## Common Pitfalls

- **Gaussian/SI factor confusion.** The most common error. The factor of 4pi appears in different places in different systems. In Gaussian: 4pi appears in Maxwell's equations but not in Coulomb's law. In SI: 4pi appears in Coulomb's law but not in Maxwell's equations. Mixing conventions from different sources silently introduces factors of 4pi.
- **c = 1 restoration errors.** When converting from natural units to SI or Gaussian, factors of c must be restored based on the dimensions of each quantity. E has dimensions [M L T^{-3} A^{-1}] in SI but [M^{1/2} L^{-1/2} T^{-1}] in Gaussian. The number of c's needed depends on the quantity. Restoring c incorrectly produces results off by powers of 3 * 10^8.
- **E vs D, B vs H confusion.** In vacuum these are proportional, but in matter they differ by the polarization P and magnetization M. The boundary conditions use D and H (with free sources), not E and B. Using E where D is needed changes the answer by a factor of epsilon_r. Using B where H is needed changes the answer by a factor of mu_r.
- **Missing delta function in dipole field.** The magnetic dipole field B = (mu_0/4pi)(3(m.r_hat)r_hat - m)/r^3 is incomplete: it misses the contact term (2 mu_0/3) m delta^3(r). This term is essential for hyperfine structure calculations and for getting the correct average field inside a magnetic sphere.
- **Wrong retarded time evaluation.** The Lienard-Wiechert fields must be evaluated at the retarded time. Computing t_ret wrong changes both the amplitude and the direction of the radiation fields. For relativistic particles, the retarded time effect is dramatic due to the (1 - R_hat . v/c) factor.
- **Fresnel coefficient sign convention.** The sign of the p-polarization reflection coefficient depends on whether E_p is defined as parallel to the plane of incidence pointing toward or away from the interface. Jackson, Griffiths, and Born & Wolf use different conventions. Verify at normal incidence: r_s = r_p = (n_1 - n_2)/(n_1 + n_2).
- **Non-relativistic Larmor for relativistic charges.** The Larmor formula P = q^2 a^2 / (6 pi epsilon_0 c^3) is only valid for v << c. For relativistic particles, the gamma^6 factor in the Lienard formula is enormous. Always check whether v/c is negligible before using the non-relativistic formula.
- **Confusing near-field and far-field.** The near field (r << lambda) is dominated by the 1/r^3 static-like terms. The far field (r >> lambda) is dominated by the 1/r radiation terms. Intermediate formulas that mix these regions produce nonsensical results. The Poynting vector in the near field does not represent radiation; only the 1/r^2 part of |S| contributes to radiated power.
- **Radiation reaction omission.** An accelerating charge radiates and therefore loses energy, which must be accounted for as a radiation reaction force. The Abraham-Lorentz force is F_rad = (mu_0 q^2 / 6 pi c) da/dt (SI). Omitting this produces energy non-conservation in self-consistent dynamics. Including it naively produces runaway solutions and acausal pre-acceleration.

## Verification Checklist

- [ ] Unit system declared and locked: all equations use the same system throughout
- [ ] Dimensional analysis: every term in every equation has consistent dimensions in the declared system
- [ ] Factor of 4pi: appears in the correct location (Maxwell equations for Gaussian, Coulomb force for SI)
- [ ] E vs D, B vs H: correct field used in each context (free vs total sources, boundary conditions)
- [ ] Coulomb's law recovers F = k q_1 q_2 / r^2 with k = 1/(4 pi epsilon_0) (SI) or k = 1 (Gaussian)
- [ ] Fine structure constant: alpha = e^2 / (4 pi epsilon_0 hbar c) ≈ 1/137 (SI) or alpha = e^2 / (hbar c) ≈ 1/137 (Gaussian)
- [ ] Poynting vector: S gives energy flux in correct units (W/m^2 for SI, erg/(cm^2 s) for Gaussian)
- [ ] Wave equation: c = 1/sqrt(mu_0 epsilon_0) ≈ 3 * 10^8 m/s (SI)
- [ ] Boundary conditions: correct fields (D_perp, E_parallel, B_perp, H_parallel) with correct sign of n_hat
- [ ] Fresnel coefficients: reduce to r = (n_1 - n_2)/(n_1 + n_2) at normal incidence for both polarizations
- [ ] Larmor/Lienard: correct formula used for the velocity regime (non-relativistic vs relativistic)
- [ ] Retarded time: fields evaluated at t_ret, not t, for moving charges
- [ ] Radiation power: positive definite and scales correctly with charge, acceleration, and velocity
- [ ] Multipole hierarchy: P_E1 >> P_M1 ~ P_E2, each suppressed by (v/c)^2
- [ ] Duality: source-free equations invariant under E -> cB, cB -> -E rotation
- [ ] Dirac quantization: e g = n hbar c / 2 (Gaussian) gives integer n for any monopole calculation

## Worked Example: Synchrotron Radiation Power — Relativistic vs Non-Relativistic Larmor

**Problem:** An electron with Lorentz factor gamma = 1000 moves in a circular orbit in a magnetic field B = 1 T. Compute the radiated power. This targets the LLM error class of using the non-relativistic Larmor formula for ultrarelativistic particles, which underestimates the power by a factor of gamma^4 ~ 10^{12}.

### Setup

**Unit system:** SI throughout. The electron has charge e = 1.602 x 10^{-19} C, mass m_e = 9.109 x 10^{-31} kg.

For circular motion in a magnetic field, the centripetal acceleration is provided by the Lorentz force:
```
gamma m_e v^2 / r = e v B
→ a = v^2 / r = e v B / (gamma m_e)
```

For gamma = 1000, v ~ c (specifically, beta = sqrt(1 - 1/gamma^2) = 0.9999995).

```
a = e c B / (gamma m_e) = (1.602e-19)(3e8)(1) / (1000)(9.109e-31)
  = 4.806e-11 / 9.109e-28 = 5.276e16 m/s^2
```

### Step 1: Non-Relativistic Larmor (WRONG for this problem)

The non-relativistic Larmor formula:
```
P_NR = e^2 a^2 / (6 pi epsilon_0 c^3)
     = (1.602e-19)^2 (5.276e16)^2 / (6 pi (8.854e-12)(2.998e8)^3)
     = (2.566e-38)(2.784e33) / (6 pi (8.854e-12)(2.694e25))
     = 7.143e-5 / (4.521e15)
     = 1.580e-20 W
```

This is WRONG by a factor of gamma^4 = 10^{12}.

### Step 2: Relativistic Lienard Formula (CORRECT)

For circular motion (acceleration perpendicular to velocity), the relativistic formula is:
```
P_rel = e^2 c / (6 pi epsilon_0) * gamma^4 * (a/c^2)^2    [perpendicular acceleration]
      = gamma^4 * P_NR
```

The key: for perpendicular acceleration (circular motion), P = gamma^4 P_NR. For parallel acceleration (linear), P = gamma^6 P_NR. The exponent depends on the geometry.

```
P_rel = (1000)^4 * 1.580e-20 W = 10^12 * 1.580e-20 = 1.580e-8 W = 15.8 nW
```

Per electron. For a beam of N = 10^{10} electrons (typical synchrotron):
```
P_total = 10^10 * 1.580e-8 = 0.158 W
```

### Step 3: Alternative Formula (Cross-Check)

The synchrotron radiation power can also be written as:
```
P = C_gamma c e^4 B^2 gamma^2 / (m_e^2)    where C_gamma = 1/(6 pi epsilon_0 (m_e c^2)^2)
```

This is the standard accelerator physics formula. Using:
```
C_gamma = 8.85e-5 m/(GeV)^3 (from accelerator physics tables)
E = gamma m_e c^2 = 1000 * 0.511 MeV = 511 MeV = 0.511 GeV
P = C_gamma c E^4 / (m_e c^2)^2 / rho^2    where rho = gamma m_e c / (eB) is the orbit radius
```

Both formulations must give the same answer.

### Verification

1. **Dimensional analysis:** [P] = [e^2][a^2] / [epsilon_0][c^3] = C^2 * m^2/s^4 / (C^2 s^2/(kg m^3) * m^3/s^3) = kg m^2/s^3 = Watts. Correct.

2. **Non-relativistic limit:** At gamma = 1: P_rel = P_NR. The two formulas agree. Correct.

3. **Scaling check:** P ~ gamma^4 B^2 for circular motion. Doubling the energy (gamma) increases power by 16x. Doubling B increases power by 4x. These match synchrotron light source design rules.

4. **Energy loss per revolution:** The orbit period is T = 2 pi rho / (beta c) where rho = gamma m_e c / (eB). Energy loss per turn: Delta E = P * T. For GeV-scale electrons: Delta E ~ 88.5 keV * (E/GeV)^4 / rho[m]. This is the standard synchrotron radiation loss formula. Verify agreement.

5. **Numerical cross-check:** At the Advanced Photon Source (APS): E = 7 GeV, rho = 38.96 m, P_total ~ 5 MW for I = 100 mA. Our formula should reproduce this order of magnitude.

**The typical LLM error** uses P = e^2 a^2 / (6 pi epsilon_0 c^3) without the gamma^4 factor, getting 10^{-20} W instead of 10^{-8} W per electron. Some LLMs apply gamma^6 instead of gamma^4, confusing perpendicular and parallel acceleration geometries. The exponent depends on whether a is perpendicular to v (circular: gamma^4) or parallel to v (linear: gamma^6).

## Concrete Example: Factor of 4pi From Mixed Unit Systems

**Problem:** Compute the energy stored in the electric field of a uniformly charged sphere of radius R and total charge Q.

**Wrong approach (common LLM error):** Mix SI and Gaussian formulas in the same calculation. For example, use the Gaussian electric field E = Q/r^2 (no 4pi epsilon_0) but the SI energy density u = epsilon_0 E^2 / 2.

This produces u = epsilon_0 Q^2 / (2 r^4), which is wrong by a factor of (4pi)^2.

**Correct approach (SI):**

Step 1. **State the unit system:** SI throughout. Convention: E in V/m, energy in J, charge in C.

Step 2. **Electric field outside the sphere (r > R):**
```
E(r) = Q / (4 pi epsilon_0 r^2)     [Gauss's law in SI]
```

Step 3. **Energy density:**
```
u = (1/2) epsilon_0 E^2 = Q^2 / (32 pi^2 epsilon_0 r^4)
```

Step 4. **Total energy (integrate from R to infinity):**
```
U = integral_R^inf u * 4pi r^2 dr = (Q^2 / (8 pi epsilon_0)) * integral_R^inf r^{-2} dr
  = Q^2 / (8 pi epsilon_0 R)
```

**Correct approach (Gaussian, as cross-check):**

In Gaussian units: E = Q/r^2 (no 4pi epsilon_0), u = E^2/(8pi).
```
U = integral_R^inf (Q^2 / r^4) * (1/(8pi)) * 4pi r^2 dr = Q^2 / (2R)
```
Converting: Q^2/(2R) in Gaussian = Q^2/(8pi epsilon_0 R) in SI (since Q_SI = Q_Gauss / sqrt(4pi epsilon_0)). Results agree.

**Checkpoint:**
- Dimensional analysis (SI): [Q^2/(epsilon_0 R)] = C^2 / (C^2 s^2 / (kg m^3) * m) = kg m^2/s^2 = J. Correct.
- Limiting case R -> infinity: U -> 0 (no energy stored in infinitely spread charge). Correct.
- Limiting case R -> 0: U -> infinity (infinite self-energy of a point charge -- the classical electron radius problem). Physically expected.
- For Q = e, R = r_e (classical electron radius): U = m_e c^2 / 2. This defines r_e = e^2/(8pi epsilon_0 m_e c^2) = 1.41 fm.

**The typical LLM error** produces an answer off by 4pi or (4pi)^2 because it uses E from one unit system and u from another. The dimensional analysis checkpoint catches this: if 4pi appears or disappears unexpectedly, the units are mixed.

## Worked Example: Brewster's Angle and Fresnel Sign Convention Trap

**Problem:** Compute Brewster's angle for light incident from air (n_1 = 1) onto glass (n_2 = 1.5), and verify that the p-polarized reflection coefficient vanishes. This targets the LLM error class of using inconsistent Fresnel coefficient conventions — different textbooks define the sign of r_p differently, and mixing conventions produces wrong Brewster angles or wrong reflected field directions.

### Step 1: State the Convention

```
% Convention: Griffiths (Introduction to Electrodynamics, 4th ed.)
% s-polarization (TE): E perpendicular to plane of incidence
% p-polarization (TM): E in the plane of incidence
% r_p sign: positive when reflected E_p is in the same direction as incident E_p
%           (Griffiths convention — Jackson uses the OPPOSITE sign convention)
```

The Fresnel coefficients (Griffiths convention):

```
r_s = (n_1 cos(theta_i) - n_2 cos(theta_t)) / (n_1 cos(theta_i) + n_2 cos(theta_t))
r_p = (n_2 cos(theta_i) - n_1 cos(theta_t)) / (n_2 cos(theta_i) + n_1 cos(theta_t))
```

where theta_t satisfies Snell's law: n_1 sin(theta_i) = n_2 sin(theta_t).

### Step 2: Find Brewster's Angle

Brewster's angle is where r_p = 0:

```
n_2 cos(theta_B) = n_1 cos(theta_t)
```

Combined with Snell's law (n_1 sin(theta_B) = n_2 sin(theta_t)):

```
tan(theta_B) = n_2/n_1
```

For n_1 = 1, n_2 = 1.5:

```
theta_B = arctan(1.5) = 56.31 degrees
```

### Step 3: Verify r_p = 0

At theta_i = theta_B = 56.31 degrees:

```
cos(theta_B) = 0.5547
sin(theta_B) = 0.8321
theta_t = arcsin(n_1 sin(theta_B) / n_2) = arcsin(0.8321/1.5) = arcsin(0.5547) = 33.69 degrees
cos(theta_t) = 0.8321
```

Check: n_2 cos(theta_B) = 1.5 * 0.5547 = 0.8321. n_1 cos(theta_t) = 1 * 0.8321 = 0.8321. Equal. So r_p = 0. Confirmed.

**Also note:** theta_B + theta_t = 56.31 + 33.69 = 90.00 degrees. This is the geometric meaning of Brewster's angle: the reflected and refracted rays are perpendicular.

### Step 4: The Convention Trap

**Jackson convention:** Jackson (Classical Electrodynamics) defines r_p with the OPPOSITE sign:

```
r_p^{Jackson} = (n_1 cos(theta_t) - n_2 cos(theta_i)) / (n_1 cos(theta_t) + n_2 cos(theta_i))
              = -r_p^{Griffiths}
```

Both conventions give r_p = 0 at Brewster's angle (zero is sign-independent). But they differ for other angles:

```
| theta_i | r_p (Griffiths) | r_p (Jackson) |
|---------|-----------------|---------------|
| 0       | +0.200          | -0.200        |
| 30      | +0.148          | -0.148        |
| 56.31   | 0               | 0             |
| 70      | -0.175          | +0.175        |
| 90      | -1              | +1            |
```

**The sign flip matters** for: (a) computing the phase of the reflected wave, (b) multilayer interference calculations where phases accumulate, (c) the direction of the reflected electric field vector.

### Step 5: Common LLM Errors

**Error 1: Wrong Brewster formula.** Writing tan(theta_B) = n_1/n_2 instead of n_2/n_1. This gives theta_B = arctan(1/1.5) = 33.69 degrees. Checking: r_p(33.69) = (1.5 * 0.8321 - 1 * 0.5547)/(1.5 * 0.8321 + 1 * 0.5547) = (1.248 - 0.555)/(1.248 + 0.555) = 0.693/1.803 = 0.384, which is NOT zero. The normal-incidence check catches this: at theta = 0, r_p = (n_2 - n_1)/(n_2 + n_1) = 0.5/2.5 = 0.2, not zero. So Brewster's angle must be between 0 and 90 degrees, and at 33.69 degrees r_p is still positive — no zero crossing yet.

**Error 2: Claiming r_s = 0 at Brewster's angle.** r_s(theta_B) = (cos(56.31) - 1.5 * cos(33.69))/(cos(56.31) + 1.5 * cos(33.69)) = (0.555 - 1.248)/(0.555 + 1.248) = -0.693/1.803 = -0.384. This is NOT zero. Only r_p vanishes at Brewster's angle. The s-polarization is always partially reflected.

**Error 3: Mixing conventions.** Using Griffiths' formula for r_p with Jackson's sign convention for the reflected field direction produces a phase error of pi in the reflected wave. In a thin-film interference calculation (e.g., antireflection coating), this phase error shifts the interference condition from constructive to destructive or vice versa, giving the wrong optimal film thickness.

### Verification

1. **Normal incidence check.** At theta = 0: r_s = r_p = (n_1 - n_2)/(n_1 + n_2) = -0.2 (Griffiths) or +0.2 (Jackson). Both conventions MUST agree at normal incidence (up to the sign, which depends on convention). If r_s != r_p at theta = 0, the formulas are wrong.

2. **Reflectance.** R_p = |r_p|^2, R_s = |r_s|^2. These are convention-independent (magnitude squared). At Brewster's angle: R_p = 0, R_s = 0.147. The reflectance must be between 0 and 1 for all angles. Verify at grazing incidence: R_s = R_p = 1.

3. **Energy conservation.** R + T = 1 where T is the transmittance (corrected for the beam cross-section change): T = (n_2 cos(theta_t))/(n_1 cos(theta_i)) * |t|^2. Check: at Brewster's angle, T_p = 1 (since R_p = 0).

4. **Total internal reflection.** For n_1 > n_2 (glass to air), total internal reflection occurs at theta_c = arcsin(n_2/n_1). Verify: |r_s| = |r_p| = 1 for theta > theta_c. Brewster's angle is below the critical angle, so r_p = 0 still occurs for internal reflection.
