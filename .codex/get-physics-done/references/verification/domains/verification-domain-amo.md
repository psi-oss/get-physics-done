---
load_when:
  - "AMO verification"
  - "atomic physics verification"
  - "quantum optics"
  - "selection rule"
  - "Rabi oscillation"
  - "laser cooling"
  - "cold atoms"
  - "dipole transition"
tier: 2
context_cost: large
---

# Verification Domain — AMO Physics & Quantum Optics

Selection rules, dipole approximation, rotating wave approximation, sum rules, decoherence, and laser-atom interaction checks for atomic, molecular, and optical physics.

**Load when:** Working on atomic structure, molecular spectroscopy, quantum optics, cold atoms, laser-atom interaction, or trapped ion/atom physics.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-qft.md` — QFT (for QED corrections, radiative processes)
- `references/verification/domains/verification-domain-condmat.md` — condensed matter (for many-body AMO systems)

---

<selection_rules>

## Selection Rule Compliance

Selection rules are absolute constraints from symmetry. A non-zero matrix element for a forbidden transition is always an error.

**Electric dipole (E1) selection rules:**

```
For single-electron atoms in the non-relativistic limit:
  Delta l = +/- 1            (parity change required)
  Delta m_l = 0, +/- 1       (angular momentum projection)
  Delta m_s = 0               (spin unchanged in E1)
  Delta J = 0, +/- 1          (but J=0 -> J=0 FORBIDDEN)
  Parity: must change ((-1)^l -> (-1)^{l+1})

Verification:
1. COMPUTE: <f|r|i> for claimed forbidden transition; must be EXACTLY zero by symmetry
2. CHECK: If Delta l = 0 or |Delta l| > 1, the transition must be labeled as forbidden (M1, E2, etc.)
3. COMPUTE: Sum over m_f of |<n'l'm'|r_q|nlm>|^2 = (2l'+1) * (Wigner 3j)^2 * |<n'l'||r||nl>|^2
```

**Thomas-Reiche-Kuhn (TRK) sum rule:**

```
sum_f f_{if} = Z  (number of electrons)

where f_{if} = (2m*omega_{if})/(3*hbar) * |<f|r|i>|^2 is the oscillator strength.

Verification: Sum oscillator strengths over all final states. Must equal Z (exactly for complete basis,
approximately for truncated basis — report the fraction of sum rule exhausted).
If sum > Z: there is an error in the matrix elements or transition frequencies.
If sum << Z: important transitions are missing from the calculation.
```

</selection_rules>

<dipole_approximation>

## Dipole Approximation and Beyond

**Dipole approximation validity:**

```
The electric dipole approximation exp(ik.r) ~ 1 is valid when k*a_0 << 1,
equivalently when the photon wavelength lambda >> atomic size a_0.

For visible light (lambda ~ 500 nm) and atoms (a_0 ~ 0.5 A): k*a_0 ~ 0.006 << 1. Valid.
For X-rays (lambda ~ 1 A) and atoms: k*a_0 ~ 3. NOT valid — need multipole expansion.
For nuclear transitions (lambda ~ fm, nucleus ~ fm): k*R ~ 1. Need full multipole.

Verification:
1. COMPUTE: k*a_0 (or k*<r>) for the transition. If > 0.1: dipole approximation is suspect.
2. If dipole approximation used for k*a_0 > 0.1: compute the next-order correction
   (magnetic dipole M1 and electric quadrupole E2) and verify they are small compared to E1.
```

**Rotating wave approximation (RWA):**

```
RWA is valid when the Rabi frequency Omega_R << optical frequency omega_0.

For a two-level system driven near resonance (delta = omega - omega_0):
  Full Hamiltonian has counter-rotating terms at frequency 2*omega_0.
  RWA drops these terms. Error is O(Omega_R / omega_0).

Verification:
1. COMPUTE: Omega_R / omega_0. If > 0.1: RWA breaks down (ultrastrong coupling regime).
2. For pulsed excitation: also need pulse duration t_p >> 1/omega_0 for RWA to hold.
3. Bloch-Siegert shift: delta_BS = Omega_R^2 / (4*omega_0). If delta_BS > linewidth: measurable RWA correction.
```

</dipole_approximation>

<quantum_optics_checks>

## Quantum Optics Consistency

**Rabi frequency normalization:**

```
Rabi frequency: Omega_R = d*E_0/hbar  (semiclassical)
where d = <e|er|g> is the transition dipole moment and E_0 is the electric field amplitude.

Verification:
1. COMPUTE: Dimensions: [d*E/hbar] = (C*m)*(V/m)/(J*s) = C*V/(J*s) = 1/s = rad/s. Correct.
2. For resonant excitation: population oscillates as P_e(t) = sin^2(Omega_R*t/2).
   At t = pi/Omega_R: complete inversion (pi-pulse). Verify this timing.
3. For off-resonant: effective Rabi = sqrt(Omega_R^2 + delta^2). On resonance (delta=0): reduces to Omega_R.
```

**AC Stark shift (light shift):**

```
For far-detuned light (|delta| >> Omega_R, Gamma):
  V_dipole = -hbar*Omega_R^2 / (4*delta)   (per beam, two-level model)

Sign: Red-detuned (delta < 0) -> V < 0 (attractive potential, atoms trapped at intensity maxima).
      Blue-detuned (delta > 0) -> V > 0 (repulsive, atoms trapped at intensity minima).

Verification:
1. COMPUTE: Sign of V_dipole. Red-detuned MUST give negative (trapping) potential.
   If positive for red-detuned: sign error in the detuning convention.
2. COMPUTE: Scattering rate Gamma_sc = Gamma * (Omega_R/(2*delta))^2. Must be << trap frequency
   for stable trapping. If Gamma_sc > trap frequency: heating destroys the trap.
```

**Decoherence rate positivity:**

```
For open quantum systems (Lindblad master equation):
  d(rho)/dt = -i[H,rho] + sum_k gamma_k (L_k rho L_k^dagger - (1/2){L_k^dagger L_k, rho})

Verification:
1. All decay rates gamma_k >= 0 (required for complete positivity).
   Negative gamma_k makes the evolution non-physical (rho eigenvalues can become negative).
2. Steady state rho_ss must be a valid density matrix: Tr(rho_ss) = 1, eigenvalues in [0,1].
3. For two-level system: T_1 = 1/Gamma (population decay), T_2 <= 2*T_1 (coherence decay).
   If T_2 > 2*T_1: unphysical (pure dephasing can only add to decoherence, not subtract).
```

</quantum_optics_checks>

<scattering_checks>

## Atomic Scattering Checks

**Optical theorem for atomic scattering:**

```
sigma_total = (4*pi/k) * Im[f(0)]
where f(0) is the forward scattering amplitude and k is the incident wavevector.

Verification: Compute sigma_total by integrating |f(theta)|^2 over angles;
compute Im[f(0)] independently. They must agree.
```

**Low-energy scattering (s-wave):**

```
For ultracold atoms (k -> 0):
  f(k) -> -a / (1 + ika)    (effective range expansion, leading order)
  sigma_total -> 4*pi*a^2     (for distinguishable particles)
  sigma_total -> 8*pi*a^2     (for identical bosons, factor of 2 from symmetrization)

Verification:
1. COMPUTE: scattering length a. Must have correct sign (a > 0 repulsive, a < 0 attractive in standard convention).
2. Near Feshbach resonance: a diverges. Verify a(B) = a_bg * (1 - Delta/(B - B_0)) reproduces known parameters.
```

**Franck-Condon overlaps (molecular transitions):**

```
Franck-Condon factor: FCF = |<v'|v">|^2
where |v'> and |v"> are vibrational wavefunctions of the upper and lower electronic states.

Verification:
1. sum_{v'} FCF(v',v") = 1 for each v" (completeness of upper vibrational states)
2. All FCF >= 0 (squared overlap)
3. For similar potential curves: diagonal FCF(v,v) ~ 1 (vertical transitions favored)
```

</scattering_checks>

## Worked Examples

### RWA breakdown detected by Bloch-Siegert shift

**Scenario:** Computing Rabi oscillations for a driven two-level atom. The drive strength is Omega_R = 0.3*omega_0 (approaching ultrastrong coupling).

**Verification:** Compute the Bloch-Siegert shift and compare with detuning.

```python
import numpy as np

omega_0 = 2 * np.pi * 5e14  # optical frequency (500 nm)
Omega_R = 0.3 * omega_0     # strong drive

# Bloch-Siegert shift
delta_BS = Omega_R**2 / (4 * omega_0)
print(f"Bloch-Siegert shift: {delta_BS/omega_0:.4f} * omega_0")
# = 0.0225 * omega_0 = 2.25% of optical frequency

# For typical atomic linewidth Gamma ~ 10 MHz << delta_BS ~ 10^13 Hz
# RWA error is HUGE — counter-rotating terms shift the resonance measurably
# Full numerical solution of the time-dependent Schrodinger equation is required
```

### TRK sum rule violation revealing missing transitions

**Scenario:** Computing oscillator strengths for sodium D-line transitions. Only 3s -> 3p is included.

```python
# f_{3s->3p} = 0.978 (known value for Na D-line)
# TRK sum rule: sum f = Z = 11 for sodium
# Missing sum rule fraction: 1 - 0.978/11 = 91%!
# The D-line alone exhausts only 9% of the total sum rule.
# Most oscillator strength is in transitions to the continuum (photoionization).
# A calculation claiming completeness with only bound-bound transitions
# would violate the TRK sum rule badly.
```
