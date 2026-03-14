---
load_when:
  - "statistical mechanics verification"
  - "thermodynamic consistency"
  - "detailed balance"
  - "finite-size scaling"
  - "KMS condition"
tier: 2
context_cost: medium
---

# Verification Domain — Statistical Mechanics

Thermodynamic consistency, detailed balance, finite-size scaling, and subfield-specific checks for statistical mechanics.

> **Note:** For cosmology/GR, see `references/verification/domains/verification-domain-gr-cosmology.md`. For fluids/plasma, see `references/verification/domains/verification-domain-fluid-plasma.md`. For astrophysics, see `references/verification/domains/verification-domain-astrophysics.md`.

**Load when:** Working on statistical mechanics, phase transitions, Monte Carlo, cosmological calculations, or fluid dynamics simulations.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-qft.md` — QFT, particle, GR, mathematical physics
- `references/verification/domains/verification-domain-condmat.md` — condensed matter, quantum information, AMO

---

<thermodynamic_sum_rules>

## Thermodynamic Sum Rules and Consistency

Exact relations between thermodynamic quantities that must hold regardless of the specific model or approximation.

### Thermodynamic sum rules

```
Compressibility sum rule:
  kappa_T = (1/n^2) integral [S(q) - 1] dq/(2*pi)^3 + 1/(n k_B T)
  Links structure factor S(q) to thermodynamic compressibility

Specific heat sum rule:
  integral_0^inf [C_V(T')/T'^2] dT' = S(inf)/T -> related to high-T entropy
```

### Thermodynamic consistency checks

```
Partition function:
  Z -> (number of states) at T -> inf
  Z -> exp(-beta E_0) at T -> 0

Free energy:
  F = U - TS must be minimized at equilibrium
  F is concave in T, convex in V

Specific heat:
  C_V >= 0 (thermodynamic stability)
  C_V from energy fluctuations: C_V = (<E^2> - <E>^2) / (k_B T^2)
  Must agree with C_V = dU/dT

Entropy:
  S >= 0 always
  S -> 0 (or constant) as T -> 0 (third law)
  S -> N k_B ln(number of microstates per particle) as T -> inf

Compressibility:
  kappa >= 0 (mechanical stability)

Phase transitions:
  Clausius-Clapeyron: dP/dT = Delta S / Delta V along coexistence
  Energy histogram: single peak for continuous, double peak for first-order
```

### Detailed balance

```
Transition rates must satisfy:
  W(A->B) * P_eq(A) = W(B->A) * P_eq(B)

For Metropolis:
  W(A->B) / W(B->A) = exp(-beta * (E_B - E_A))  (if E_B > E_A)

Verification: Compute W ratio for many random pairs of states.
All must satisfy detailed balance exactly (up to floating-point precision).
```

</thermodynamic_sum_rules>

## Worked Example: Missing factor of 2 in partition function — caught by high-T limiting case

**Scenario:** An LLM computes the partition function for a two-level system (spin-1/2 in magnetic field, states at energies +/-epsilon). It writes Z = cosh(beta*epsilon), forgetting the overall factor of 2 from the sum of two exponentials.

**The error:** Z = cosh(beta*epsilon) instead of Z = 2 cosh(beta*epsilon).

**Verification check:** High-temperature limiting case. As T -> inf (beta -> 0), Z must equal the number of microstates, which is 2.

```python
import numpy as np

epsilon = 1.0  # energy splitting |epsilon|

def Z_claimed(beta):
    """LLM's result: Z = cosh(beta*epsilon) -- missing factor of 2."""
    return np.cosh(beta * epsilon)

def Z_correct(beta):
    """Correct: Z = exp(beta*epsilon) + exp(-beta*epsilon) = 2*cosh(beta*epsilon)."""
    return 2 * np.cosh(beta * epsilon)

# LIMITING CASE CHECK: T -> inf (beta -> 0)
# Z must equal the number of microstates = 2
beta_high_T = 1e-8
print(f"High-T limit (beta -> 0):")
print(f"  Z_claimed  = {Z_claimed(beta_high_T):.6f}")   # 1.000000 FAIL
print(f"  Z_correct  = {Z_correct(beta_high_T):.6f}")   # 2.000000 PASS
print(f"  Expected: 2 (number of states)")

# Consequence: entropy is wrong at high T
S_claimed = np.log(Z_claimed(beta_high_T))    # ~ 0 (no entropy for a 2-state system?!)
S_correct = np.log(Z_correct(beta_high_T))    # ~ ln(2) = 0.693
print(f"High-T entropy:")
print(f"  S_claimed  = {S_claimed:.6f} k_B")   # 0.000000 FAIL
print(f"  S_correct  = {S_correct:.6f} k_B")   # 0.693147 = ln(2) PASS
```

**Lesson:** The high-T limit Z -> (number of states) is a universal check for any partition function. It requires no knowledge of the specific physics — only state counting.

---

## Subfield-Specific Checks

### Statistical Mechanics

**Priority checks:**

1. Exact solution comparison: 2D Ising T_c = 2J/k_B/ln(1+sqrt(2)) = 2.269...; 1D Ising no phase transition for T > 0
2. Universality class: critical exponents match known values for the universality class
3. Finite-size scaling: data collapse for multiple system sizes with correct exponents
4. Detailed balance: W(A->B)*P_eq(A) = W(B->A)*P_eq(B)
5. Thermodynamic consistency: C_V from energy fluctuations matches d<E>/dT

**Red flags:**

- Phase transition in 1D with short-range interactions at T > 0 (Perron-Frobenius forbids this)
- Mean-field exponents reported for d < 4 (d_c = 4 for Ising/O(n))
- Statistical errors computed without accounting for autocorrelation time
- Energy histogram that doesn't match expected behavior (single peak for continuous, double peak for first-order)

### KMS Relations and Fluctuation-Dissipation

```
KMS condition (quantum detailed balance):
  G^>(omega) = exp(beta*omega) G^<(omega)
  Relates emission and absorption spectral functions

Fluctuation-dissipation theorem:
  S(omega) = 2 * [n_B(omega) + 1] * Im[chi^R(omega)]
  where n_B is the Bose distribution and chi^R is the retarded susceptibility

  Verification: Compute S(omega) from correlator and Im[chi^R] independently.
  They must satisfy FDT at each frequency.

Classical FDT:
  <x^2> = k_B T / (m omega_0^2) for harmonic oscillator
  More generally: <delta A delta B> related to response function chi_AB
```

### Cosmology/Astrophysics

**Priority checks:**

1. CMB power spectrum: CAMB/CLASS output matches Planck best-fit to sub-percent
2. BAO scale: sound horizon r_d ~ 147 Mpc appears at correct scale in correlation function
3. Distance consistency: luminosity distance D_L = (1+z)*chi, angular diameter D_A = chi/(1+z)
4. Energy conservation: Friedmann + continuity equations satisfied throughout evolution
5. Normalization: sigma_8 consistent between CMB-derived and direct measurement

**Red flags:**

- Mixing comoving and physical distances (factor of (1+z) error)
- Not marginalizing over nuisance parameters (artificially tight constraints)
- N-body initial conditions at first order (2LPT or higher required)
- Neglecting massive neutrinos for precision predictions (>1% effect on small-scale power)

### Fluid Dynamics/Plasma

**Priority checks:**

1. Kolmogorov spectrum: E(k) ~ k^{-5/3} in inertial range for fully developed turbulence
2. Conservation: energy, enstrophy (2D), helicity (3D) in ideal flows
3. CFL condition: Courant number <= C_max for stability
4. Known solutions: Poiseuille flow, Couette flow, Stokes drag
5. Reynolds scaling: friction factor, drag coefficient match known correlations

**Red flags:**

- DNS claiming turbulence resolution without verifying grid reaches Kolmogorov scale
- Numerical dissipation comparable to physical viscosity (check numerical Reynolds number)
- div(B) != 0 in MHD simulations (need constrained transport or divergence cleaning)
- RANS results presented without noting model-form error (irreducible with grid refinement)

## See Also

- `../core/verification-quick-reference.md` -- Compact checklist (default entry point)
- `../core/verification-core.md` -- Dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` -- Convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-qft.md` -- QFT, particle physics, GR, mathematical physics
- `references/verification/domains/verification-domain-condmat.md` -- Condensed matter, quantum information, AMO
