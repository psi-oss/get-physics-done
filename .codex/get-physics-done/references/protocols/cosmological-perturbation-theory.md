---
load_when:
  - "cosmological perturbation"
  - "CMB"
  - "power spectrum"
  - "inflation"
  - "primordial"
  - "scalar perturbation"
  - "tensor perturbation"
  - "gauge invariant perturbation"
  - "Bardeen potential"
  - "curvature perturbation"
tier: 2
context_cost: medium
---

# Cosmological Perturbation Theory Protocol

Cosmological perturbation theory is plagued by gauge ambiguities: the same physical perturbation looks different in different coordinate systems. The Bardeen formalism (gauge-invariant variables) or explicit gauge-fixing (conformal Newtonian, synchronous, comoving) must be declared and tracked throughout. Mixing gauges within a single calculation produces unphysical results.

## Related Protocols

- See `derivation-discipline.md` for sign tracking and convention annotation in all derivations
- See `perturbation-theory.md` for general perturbative expansion techniques
- See `effective-field-theory.md` for EFT of inflation and EFT of large-scale structure
- See `numerical-computation.md` for Boltzmann code validation (CLASS, CAMB)
- See `analytic-continuation.md` for in-in formalism and Schwinger-Keldysh techniques

## Step 1: Declare Background and Perturbation Conventions

Before writing any perturbation equation, declare:

1. **Background metric:** FRW metric ds^2 = a^2(tau)[-d(tau)^2 + delta_{ij} dx^i dx^j] (conformal time) or ds^2 = -dt^2 + a^2(t) delta_{ij} dx^i dx^j (cosmic time). State which time variable is used.
2. **Metric signature:** State (+,-,-,-) or (-,+,+,+). This affects the sign of the Einstein equations.
3. **Perturbation decomposition:** Scalar-Vector-Tensor (SVT) decomposition. State whether the perturbation variables are the metric perturbation delta g_{mu nu} or the gauge-invariant Bardeen potentials Phi, Psi.
4. **Gauge choice:** Conformal Newtonian (longitudinal), synchronous, comoving, spatially flat, uniform density, or gauge-invariant. State explicitly.
5. **Fourier convention:** State the Fourier convention for spatial modes: delta(x) = integral d^3k/(2pi)^3 delta_k e^{ik.x} or delta(x) = integral d^3k delta_k e^{ik.x}. The power spectrum definition depends on this.

## Step 2: SVT Decomposition

The metric perturbation decomposes into scalar, vector, and tensor parts that decouple at linear order:

1. **Scalar perturbations (4 functions):** In conformal Newtonian gauge:
   ds^2 = a^2(tau)[-(1+2Phi)d(tau)^2 + (1-2Psi)delta_{ij}dx^i dx^j]
   With anisotropic stress sigma = 0: Phi = Psi.

2. **Vector perturbations (2 functions):** Rotational modes, decaying in expanding universe. Usually neglected unless sourced by specific mechanisms (topological defects, magnetic fields).

3. **Tensor perturbations (2 polarizations):** Gravitational waves h_{ij} with h^i_i = 0, partial_i h^{ij} = 0. Two independent polarizations h_+ and h_x.

**Verification:** At linear order, scalar, vector, and tensor perturbations evolve independently. If they appear coupled, either (a) the calculation has gone to second order (verify this is intended) or (b) there is an error.

## Step 3: Gauge Invariance Verification

1. **Bardeen potentials:** Under a gauge transformation x^mu -> x^mu + xi^mu, the Bardeen potentials Phi_B = Phi + (1/a)[a(B - E')]' and Psi_B = Psi - (a'/a)(B - E') are gauge-invariant. Verify that final physical results (power spectrum, transfer functions) are expressed in terms of gauge-invariant quantities.

2. **Comoving curvature perturbation:** R = Psi - (H/rho+p) delta q is gauge-invariant and conserved on super-Hubble scales for adiabatic perturbations. This is the key quantity linking inflation to CMB observations.

3. **Consistency check:** Compute the same observable (e.g., CMB temperature anisotropy) in two different gauges and verify they agree. If they disagree, a gauge artifact has leaked into the physical result.

4. **Super-Hubble conservation:** For adiabatic perturbations, R is conserved outside the Hubble radius: R' = 0 for k << aH. Verify this conservation law holds in your calculation. Violation indicates either non-adiabatic pressure perturbations (which should be tracked) or an error.

## Step 4: Power Spectrum Conventions

The power spectrum P(k) and dimensionless power spectrum Delta^2(k) are defined by:

<delta_k delta_{k'}> = (2pi)^3 delta^3(k+k') P(k)
Delta^2(k) = k^3 P(k) / (2pi^2)

**Verification checklist:**
1. The (2pi)^3 factor must be consistent with the Fourier convention from Step 1.
2. For a scale-invariant spectrum: Delta^2(k) = const (Harrison-Zel'dovich). This corresponds to n_s = 1. Current measurement: n_s = 0.9649 +/- 0.0042 (Planck 2018).
3. The scalar amplitude A_s = Delta^2_R(k_*) at pivot scale k_* = 0.05 Mpc^{-1}: A_s ~ 2.1 x 10^{-9}.
4. The tensor-to-scalar ratio r = Delta^2_h / Delta^2_R. Current bound: r < 0.036 (BICEP/Keck 2021).

## Step 5: Inflationary Perturbation Theory

1. **Slow-roll parameters:** epsilon = -H'/H^2 (conformal time) or epsilon = -dot{H}/H^2 (cosmic time). State which definition. Also eta = epsilon'/epsilon H (or eta_V = M_Pl^2 V''/V for potential slow-roll). The spectral index n_s = 1 - 2epsilon - eta (to first order in slow-roll).

2. **Mukhanov-Sasaki equation:** The equation for the gauge-invariant variable v = z R (where z = a sqrt(2 epsilon)) is: v'' + (k^2 - z''/z) v = 0. Verify the z''/z term using the background evolution.

3. **Bunch-Davies vacuum:** The initial condition for modes deep inside the Hubble radius (k >> aH) is v_k -> (1/sqrt(2k)) e^{-ik tau}. This is the positive-frequency Minkowski vacuum.

4. **Power spectrum from inflation:**
   Delta^2_R(k) = (1/2 epsilon)(H/(2pi))^2 evaluated at horizon crossing k = aH.
   Delta^2_h(k) = (2/pi^2)(H/M_Pl)^2 evaluated at horizon crossing.
   r = 16 epsilon (consistency relation). Verify this holds in your model.

## Step 6: Boltzmann Hierarchy and Transfer Functions

1. **Boltzmann equation:** The photon distribution function f(x, p, hat{n}, tau) evolves via the collisional Boltzmann equation. The hierarchy of multipole moments Theta_l couples l to l+/-1 (free streaming) and is sourced by Thompson scattering at l = 0, 1, 2.

2. **Tight-coupling approximation:** Before recombination (tau << tau_*), photons and baryons are tightly coupled. Theta_l ~ 0 for l >= 2. Verify this approximation breaks down at recombination.

3. **Transfer function:** T(k) relates the primordial power spectrum to the observed CMB power spectrum: C_l = integral dk/k Delta^2_R(k) |T_l(k)|^2. Verify numerically using CLASS or CAMB.

4. **Numerical validation:** Compare analytical approximations against Boltzmann code output (CLASS, CAMB) for at least 3 benchmark cosmologies (LCDM, open, dark energy).

## Step 7: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Gauge invariance | Compute in two gauges, compare | Gauge artifacts in physical results |
| Super-Hubble conservation | Verify R' = 0 for k << aH (adiabatic) | Errors in perturbation equations |
| Slow-roll consistency | r = 16 epsilon, n_s = 1 - 2epsilon - eta | Wrong slow-roll relations |
| Sachs-Wolfe limit | delta T/T = (1/3) Phi for large scales | Wrong transfer function normalization |
| Acoustic peaks | Peak locations at l_n ~ n pi d_A / r_s | Wrong background cosmology |
| Silk damping | Exponential suppression at high l | Wrong recombination physics |
| Planck best-fit | Compare with Planck 2018 best-fit parameters | Numerical errors |

## Common LLM Errors in Cosmological Perturbation Theory

1. **Mixing conformal and cosmic time:** H = a'/a^2 (cosmic) vs calH = a'/a (conformal). Using one when the other is meant changes every perturbation equation.
2. **Wrong Fourier convention:** Factor of (2pi)^3 in the power spectrum definition depends on the Fourier convention. Getting this wrong changes A_s by (2pi)^3.
3. **Gauge mixing:** Starting in conformal Newtonian gauge, importing a result derived in synchronous gauge without converting.
4. **Forgetting the anisotropic stress:** Setting Phi = Psi when there is anisotropic stress (neutrinos, second-order effects). Phi = Psi only holds for perfect fluids with no anisotropic stress.
5. **Wrong sign in the Sachs-Wolfe effect:** delta T/T = (1/3) Phi (not -1/3 Phi) for the ordinary Sachs-Wolfe effect in conformal Newtonian gauge with our sign conventions.

## Standard References

- Mukhanov: *Physical Foundations of Cosmology* (comprehensive textbook)
- Weinberg: *Cosmology* (rigorous treatment of perturbation theory)
- Dodelson & Schmidt: *Modern Cosmology* (2nd edition, pedagogical)
- Bardeen: *Gauge-Invariant Cosmological Perturbations* (Phys. Rev. D 22, 1882, 1980)
- Kodama & Sasaki: *Cosmological Perturbation Theory* (Prog. Theor. Phys. Suppl. 78, 1984)
- Malik & Wands: *Cosmological perturbations* (Phys. Rept. 475, 1-51, 2009, arXiv:0809.4944)
- Planck 2018 results (arXiv:1807.06205 for parameters, 1807.06211 for inflation)
