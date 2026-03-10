---
load_when:
  - "condensed matter verification"
  - "sum rule"
  - "Kramers-Kronig"
  - "spectral function"
  - "response function"
tier: 2
context_cost: large
---

# Verification Domain — Condensed Matter

Sum rules, Kramers-Kronig relations, spectral representations, and subfield-specific checks for condensed matter physics.

> **Note:** For quantum information, see `references/verification/domains/verification-domain-quantum-info.md`. For AMO, see `references/verification/domains/verification-domain-amo.md`. For soft matter, see `references/verification/domains/verification-domain-soft-matter.md`.

**Load when:** Working on condensed matter calculations, many-body physics, spectral functions, response functions, quantum information, or atomic/molecular/optical physics.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-qft.md` — QFT, particle, GR, mathematical physics
- `references/verification/domains/verification-domain-statmech.md` — statistical mechanics, cosmology, fluids

---

<spectral_sum_rules>

## Spectral Sum Rules

Exact integrals over spectral functions that follow from fundamental symmetries and conservation laws. Violations indicate missing spectral weight, wrong normalization, or incorrect physics.

### f-sum rule (oscillator strength)

```
integral_0^inf omega Im[epsilon(omega)] d(omega) = (pi/2) omega_p^2
where omega_p^2 = 4*pi*n*e^2/m is the plasma frequency

Verification: Numerically integrate Im[epsilon(omega)] and compare with omega_p^2.
This is exact regardless of interactions -- failure indicates:
- Missing spectral weight (incomplete frequency range)
- Wrong normalization of dielectric function
- Incorrect electron count or mass
```

### Optical sum rule (conductivity)

```
integral_0^inf Re[sigma(omega)] d(omega) = (pi/2) (n*e^2/m) = (omega_p^2)/(8)
Equivalent to f-sum rule via sigma = -i*omega*(epsilon-1)/(4*pi)
```

### Spectral weight sum rule

```
integral_{-inf}^{inf} A(k, omega) d(omega)/(2*pi) = 1
where A is the single-particle spectral function
Violation means missing quasiparticle weight or incoherent background
```

### Friedel sum rule (scattering)

```
Phase shift at Fermi energy determines displaced charge:
  Z = (2/pi) sum_l (2l+1) delta_l(E_F)

Verification: Compute scattering phase shifts; sum must give impurity charge Z.
Failure indicates incomplete partial wave sum or wrong boundary conditions.
```

### Ward identities in condensed matter

```
Charge conservation -> continuity equation -> Ward identity:
  q_0 Pi^{00}(q) - q_i Pi^{i0}(q) = 0
  (density-density and current-density response are related)

Gauge invariance of electromagnetic response:
  q_mu Pi^{mu nu}(q) = 0 (transversality)
  In lattice calculations, must use consistent vertex and propagator
  (conserving approximations: Baym-Kadanoff)
```

### Moment sum rules

```
Moment sum rules for spectral functions:
  integral omega^n rho(omega) d(omega) = <[...[H, A]..., A*]> (n nested commutators)
  First few moments can be computed exactly; useful for checking numerical spectra
```

**Verification protocol:**

```python
def verify_sum_rule(spectral_fn, omega_range, expected_integral, name="", tolerance=0.01):
    """
    Verify a spectral sum rule by numerical integration.
    """
    from scipy.integrate import quad
    result, error = quad(spectral_fn, omega_range[0], omega_range[1])
    relative_diff = abs(result - expected_integral) / abs(expected_integral)
    status = "PASS" if relative_diff < tolerance else "FAIL"
    print(f"{status} {name}: integral = {result:.6e}, "
          f"expected = {expected_integral:.6e}, "
          f"relative diff = {relative_diff:.2e}")
    return relative_diff < tolerance
```

**When to apply:**

- After computing any response function or Green's function
- When using approximations (verify the approximation respects the Ward identity)
- After renormalization (check Ward identities order by order)
- When spectral functions are computed numerically (sum rules test completeness)

</spectral_sum_rules>

<kramers_kronig>

## Kramers-Kronig Relations and Spectral Representations

Kramers-Kronig (KK) relations connect the real and imaginary parts of causal response functions. They are a consequence of causality and analyticity.

**Principle:** If chi(omega) is a causal linear response function (analytic in upper half-plane, vanishing as |omega| -> inf), then:

```
Re[chi(omega)] = (1/pi) P integral_{-inf}^{inf} Im[chi(omega')] / (omega' - omega) d(omega')
Im[chi(omega)] = -(1/pi) P integral_{-inf}^{inf} Re[chi(omega')] / (omega' - omega) d(omega')

where P denotes the Cauchy principal value.
```

**Concrete applications:**

### Dielectric function

```
Re[epsilon(omega)] - 1 = (2/pi) P integral_0^inf omega' Im[epsilon(omega')] / (omega'^2 - omega^2) d(omega')
Im[epsilon(omega)] = -(2*omega/pi) P integral_0^inf [Re[epsilon(omega')] - 1] / (omega'^2 - omega^2) d(omega')

Verification: Compute epsilon(omega) independently (e.g., from band structure).
Perform KK transform of Im[epsilon] and compare with Re[epsilon]. Must agree.
Disagreement indicates: missing spectral weight, wrong high-frequency tail,
or causality violation in the model.
```

### Optical conductivity

```
Re[sigma(omega)] and Im[sigma(omega)] are KK-related:
Re[sigma(omega)] = (1/pi) P integral Im[sigma(omega')] / (omega' - omega) d(omega')

The static conductivity sigma_DC = Re[sigma(0)] must be consistent with:
sigma_DC = (1/pi) P integral Im[sigma(omega')] / omega' d(omega')
```

### Self-energy (many-body physics)

```
Retarded self-energy Sigma^R(omega) satisfies KK:
Re[Sigma^R(omega)] = (1/pi) P integral Im[Sigma^R(omega')] / (omega' - omega) d(omega')

Critical check for DMFT and other numerical many-body methods:
- Compute Sigma on Matsubara axis, analytically continue to real axis
- The continued Sigma^R must satisfy KK
- If it doesn't, the analytic continuation is unreliable
```

### Spectral representations (Lehmann/Kallen-Lehmann)

```
Propagator spectral representation:
  G(omega) = integral rho(omega') / (omega - omega') d(omega')
  where rho(omega) >= 0 is the spectral function

  This guarantees:
  1. Correct analytic structure (poles and branch cuts on real axis only)
  2. Positivity of spectral weight
  3. KK relations are automatically satisfied
  4. High-frequency behavior: G(omega) -> 1/omega as omega -> inf

Matsubara -> real frequency:
  G(i*omega_n) = integral rho(omega') / (i*omega_n - omega') d(omega')
  Analytic continuation: i*omega_n -> omega + i*eta
  Ill-conditioned problem: MaxEnt, Pade, or stochastic analytic continuation needed
  ALWAYS verify KK relations for the continued function
```

**Verification protocol:**

```python
def verify_kramers_kronig(re_chi, im_chi, omega_grid, tolerance=0.05):
    """
    Verify Kramers-Kronig consistency between Re[chi] and Im[chi].

    Uses singularity subtraction for stable principal-value integration.
    The identity:
        P integral Im[chi(omega')]/(omega'-omega) d(omega')
          = integral [Im[chi(omega')] - Im[chi(omega)]] / (omega'-omega) d(omega')  [regular]
            + Im[chi(omega)] * ln|(omega_max - omega)/(omega - omega_min)|           [analytical]
    eliminates the 1/(omega'-omega) singularity from the numerical integral.
    """
    from scipy.integrate import quad

    omega_min, omega_max = omega_grid[0], omega_grid[-1]
    margin = 1e-3 * (omega_max - omega_min)
    max_relative_error = 0

    for omega in omega_grid:
        if omega <= omega_min + margin or omega >= omega_max - margin:
            continue

        im_at_omega = im_chi(omega)

        def subtracted_integrand(omega_prime, _omega=omega, _im_at=im_at_omega):
            diff = omega_prime - _omega
            if abs(diff) < 1e-15 * (1 + abs(_omega)):
                h = max(1e-10 * (1 + abs(_omega)), 1e-14)
                return (im_chi(_omega + h) - im_chi(_omega - h)) / (2 * h)
            return (im_chi(omega_prime) - _im_at) / diff

        integral, _ = quad(subtracted_integrand, omega_min, omega_max,
                          limit=200, epsabs=1e-12, epsrel=1e-10)

        pv_log = np.log(abs((omega_max - omega) / (omega - omega_min)))
        kk_re = (integral + im_at_omega * pv_log) / np.pi

        re_actual = re_chi(omega)
        if abs(re_actual) > 1e-10:
            rel_err = abs(kk_re - re_actual) / abs(re_actual)
            max_relative_error = max(max_relative_error, rel_err)

    status = "PASS" if max_relative_error < tolerance else "FAIL"
    print(f"{status} Kramers-Kronig: max relative error = {max_relative_error:.2e}")
    return max_relative_error < tolerance
```

**When to apply:**

- After computing any complex response function (dielectric, conductivity, susceptibility)
- After analytic continuation from Matsubara to real frequencies
- When constructing model spectral functions (must be KK-consistent)
- As independent validation of numerical results

</kramers_kronig>

## Worked Example: Wrong Fourier convention in density of states — caught by spectral sum rule

**Scenario:** An LLM computes the single-particle density of states from a retarded Green's function G^R(omega) = 1/(omega - epsilon_0 + i*eta). It writes the spectral function as A(omega) = -2 Im[G^R(omega)] but then claims integral A(omega) d(omega) = 1 (which holds for a different convention).

**The error:** Using A(omega) = -2 Im[G^R(omega)] but applying the sum rule integral n(omega) d(omega) = 1 that belongs to n(omega) = -(1/pi) Im[G^R(omega)].

**Verification check:** Spectral sum rule. For a single level, the integrated density of states must equal 1.

```python
import numpy as np
from scipy.integrate import quad

epsilon_0, eta = 0.0, 0.01

def G_R(omega):
    """Retarded Green's function for a single level."""
    return 1.0 / (omega - epsilon_0 + 1j * eta)

def A_claimed(omega):
    """LLM's spectral function: A(omega) = -2 Im[G^R(omega)]."""
    return -2.0 * G_R(omega).imag

def dos_correct(omega):
    """Correct normalized DOS: n(omega) = -(1/pi) Im[G^R(omega)]."""
    return -(1.0 / np.pi) * G_R(omega).imag

# SUM RULE CHECK: integral n(omega) d(omega) = number of states = 1
integral_claimed, _ = quad(A_claimed, -1000, 1000)
integral_correct, _ = quad(dos_correct, -1000, 1000)

# integral_claimed ~ 6.2832 (off by 2*pi) FAIL
# integral_correct ~ 1.0 PASS
```

**Lesson:** Fourier convention mismatches are invisible in the algebra but produce concrete numerical factors (typically 2*pi or (2*pi)^d). Sum rules catch them because they give a number with a known exact value.

---

## Subfield-Specific Checks

### Condensed Matter

**Priority checks:**

1. Sum rules: f-sum rule for optical conductivity, spectral weight sum for Green's functions
2. Luttinger theorem: Fermi surface volume matches electron count
3. Goldstone theorem: number of gapless modes matches broken continuous symmetries
4. Mermin-Wagner theorem: no continuous symmetry breaking in d <= 2 at T > 0 (short-range interactions)
5. Band gap validation: DFT-LDA underestimates gaps; GW should give ~1.1 eV for silicon (experiment: 1.17 eV)

**Red flags:**

- DFT gap being compared directly with experiment without GW/hybrid correction
- DMRG in 2D with insufficient bond dimension (check entanglement entropy vs chi)
- QMC results at parameters where sign problem is severe (check average sign)
- Neglected spin-orbit coupling for topological phase calculations

### Quantum Information

**Priority checks:**

1. Trace preservation: Tr(rho) = 1 throughout all quantum operations
2. Complete positivity: physical quantum channels must be CPTP; check Choi matrix is positive semidefinite
3. Fidelity bounds: F(rho, sigma) in [0, 1]; F = 1 iff states are identical
4. No-cloning: any protocol that appears to clone must violate linearity or unitarity
5. Error threshold: logical error rate decreases with code distance for p < p_threshold

**Red flags:**

- Quantum channel that is trace-preserving but not completely positive (unphysical)
- Bell inequality violation beyond Tsirelson bound (S > 2*sqrt(2)) without post-selection
- VQE optimization that ignores barren plateau problem for deep circuits
- Entanglement measure applied to mixed states without proper generalization

### AMO Physics

**Priority checks:**

1. Optical theorem: sigma_total = (4*pi/k)*Im[f(0)]
2. Thomas-Reiche-Kuhn sum rule: sum of oscillator strengths = number of electrons
3. Detailed balance: Einstein A and B coefficients related by A = (8*pi*h*nu^3/c^3)*B
4. Dipole selection rules: Delta_l = +/-1, Delta_m = 0, +/-1 for electric dipole transitions
5. Kato cusp conditions: electron-nucleus cusp at r = 0

**Red flags:**

- RWA used when Rabi frequency approaches transition frequency
- Wrong factor of 2 in scattering cross section (identical vs distinguishable particles)
- Markov approximation for structured or low-temperature reservoirs
- Missing AC Stark shifts in driven systems

## See Also

- `../core/verification-quick-reference.md` -- Compact checklist (default entry point)
- `../core/verification-core.md` -- Dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` -- Convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-qft.md` -- QFT, particle physics, GR, mathematical physics
- `references/verification/domains/verification-domain-statmech.md` -- Statistical mechanics, cosmology, fluids
