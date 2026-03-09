# Worked Example: Post-Newtonian Corrections to Binary Pulsar Orbital Decay

This demonstrates complete PROJECT.md, ROADMAP.md, PLAN.md, and SUMMARY.md for a gravitational wave emission project. The calculation derives the 1PN-corrected orbital period derivative for PSR B1913+16 (Hulse-Taylor binary pulsar) and compares with the Peters (1964) quadrupole formula.

---

## 1. PROJECT.md Example

```markdown
# Post-Newtonian Corrections to Binary Pulsar Orbital Decay from Gravitational Wave Emission

## Core Research Question

What is the 1PN-corrected orbital period derivative for the Hulse-Taylor binary (PSR B1913+16),
and how does it compare with the Peters (1964) leading-order quadrupole formula?

## Physical System

Binary neutron star system PSR B1913+16 (Hulse & Taylor 1975).

| Parameter | Symbol | Value | Source |
|---|---|---|---|
| Pulsar mass | m_1 | 1.4414 M_sun | Weisberg & Huang (2016) |
| Companion mass | m_2 | 1.3867 M_sun | Weisberg & Huang (2016) |
| Orbital eccentricity | e | 0.6171334 | Weisberg & Huang (2016) |
| Orbital period | P_b | 27906.9796 s (7.7519 h) | Weisberg & Huang (2016) |
| Projected semi-major axis | a_p sin i | 2.341776 lt-s | Weisberg & Huang (2016) |
| Total mass | M | 2.8281 M_sun | Derived |
| Reduced mass | mu | 0.7069 M_sun | Derived |
| Symmetric mass ratio | eta = mu/M | 0.2499 | Derived |
| Chirp mass | M_c | 1.2185 M_sun | Derived |

## Theoretical Framework

Post-Newtonian (PN) expansion of general relativity applied to gravitational wave energy loss
from a bound binary system. The expansion parameter is v^2/c^2 ~ GM/(ac^2), which for the
Hulse-Taylor system is approximately 4.3 x 10^{-6} — comfortably in the weak-field regime
but with measurable 1PN corrections due to the extraordinary precision of pulsar timing.

Key aspects:
- **Leading order (0PN):** Peters & Mathews (1963) quadrupole radiation formula
- **1PN corrections:** Relative O(v^2/c^2) corrections from Damour & Deruelle (1986)
  including tail terms, hereditary contributions, and relativistic orbit parameterization
- **Observable:** Intrinsic orbital period derivative dP_b/dt (after subtracting the
  Shklovskii effect, Galactic acceleration, and other kinematic contributions)

## Conventions

```yaml
conventions:
  units: "geometrized (G = c = 1)"
  metric_signature: "(-,+,+,+) — mostly minus"
  coordinates: "center-of-mass frame, Keplerian orbital elements"
  time: "coordinate time t (not proper time)"
  pn_counting: "v^{2n}/c^{2n} is nPN — relative to leading quadrupole"
  angles: "radians"
  masses: "m_1 >= m_2 by convention"
  eccentricity: "time eccentricity e_t from Damour-Deruelle (DD) timing model"
```

**SI restoration rule:** To convert a geometrized expression to SI, restore factors of
G and c by dimensional analysis. Energy flux: multiply by c^5/G. Period derivative: dimensionless.

## Profile

deep-theory

## Computational Environment

Python 3.11+ with numpy, scipy, mpmath (for arbitrary-precision evaluation of enhancement functions).

## Target Journal

Physical Review D

## Bibliography Seeds

- Peters, P. C. & Mathews, J. (1963). Phys. Rev. 131, 435. [Gravitational radiation from point masses in Keplerian orbit]
- Peters, P. C. (1964). Phys. Rev. 136, B1224. [Gravitational radiation and the motion of two point masses]
- Damour, T. & Deruelle, N. (1986). Ann. Inst. Henri Poincare A, 44, 263. [General relativistic celestial mechanics]
- Weisberg, J. M. & Taylor, J. H. (2005). ASP Conf. Ser. 328, 25. [The relativistic binary pulsar B1913+16]
- Weisberg, J. M. & Huang, Y. (2016). ApJ, 829, 55. [Relativistic measurements from timing the binary pulsar PSR B1913+16]
- Blanchet, L. & Schaefer, G. (1989). MNRAS, 239, 845. [Higher-order gravitational radiation losses in binary systems]
- Blanchet, L. (2014). Living Rev. Rel. 17, 2. [Gravitational radiation from post-Newtonian sources]
- Taylor, J. H. & Weisberg, J. M. (1982). ApJ, 253, 908. [A new test of general relativity — gravitational radiation and the binary pulsar PSR 1913+16]
- Hulse, R. A. & Taylor, J. H. (1975). ApJ, 195, L51. [Discovery of a pulsar in a binary system]
```

---

## 2. ROADMAP.md Example

```markdown
# ROADMAP — Post-Newtonian Binary Pulsar Orbital Decay

## Phase 1: Literature Review and Parameter Compilation

**Objective:** Establish the theoretical foundation, collect all measured orbital parameters for
PSR B1913+16, and identify the precise contributions that enter the observed period derivative.

**Key references:**
- Peters & Mathews (1963): Quadrupole energy loss formula for eccentric orbits
- Peters (1964): Orbit-averaged energy and angular momentum loss; secular evolution of a and e
- Damour & Deruelle (1986): DD timing model, relativistic parameterization of Keplerian orbits
- Weisberg & Taylor (2005): Updated system parameters, observed period derivative
- Weisberg & Huang (2016): Most precise parameter values to date
- Blanchet & Schaefer (1989): 1PN corrections to gravitational wave energy flux

**Deliverables:**
- Complete parameter table with uncertainties and sources
- Identification of all contributions to the observed Ṗ_b (intrinsic GW + Shklovskii + Galactic)
- Clear statement of what "intrinsic" Ṗ_b means and its measured value

**Estimated depth:** standard (2-3 plans)

---

## Phase 2: Quadrupole Formula Derivation

**Objective:** Derive the Peters (1964) leading-order (0PN) quadrupole formula for dP_b/dt for
an eccentric binary, and verify the numerical result against the known value for the Hulse-Taylor
system: Ṗ_b^GR = -2.4025 x 10^{-12} (dimensionless).

**Key equations:**
- Quadrupole moment: I_{ij} = mu * x_i * x_j (traceless part)
- Energy flux: dE/dt = -(1/5)(d^3 I_{ij}/dt^3)(d^3 I^{ij}/dt^3)  [in G=c=1]
- Orbit-averaged: <dE/dt> = -(32/5) * mu^2 * M^3 / a^5 * f(e)
- Period derivative: Ṗ_b/P_b = (3/2) * <dE/dt> / E_orb  (via Kepler's third law)

**Enhancement function:**
F(e) = (1 + 73e^2/24 + 37e^4/96) * (1 - e^2)^{-7/2}

**Verification target:** Ṗ_b = -2.4025 x 10^{-12} s/s

**Estimated depth:** standard (3-4 plans)

---

## Phase 3: 1PN Corrections

**Objective:** Compute the 1PN (relative O(v^2/c^2)) corrections to the quadrupole formula.

**Key contributions at 1PN:**
1. **Relativistic orbital parameterization:** The DD timing model uses the time eccentricity e_t,
   not the Keplerian eccentricity. The relation e_t = e_K(1 + delta_1PN) introduces corrections.
2. **1PN energy flux corrections:** Additional terms in the instantaneous energy loss from
   Blanchet & Schaefer (1989), proportional to (GM/ac^2).
3. **Tail terms:** Hereditary contributions from the interaction of the radiation with the
   static gravitational field of the source (backscattering off the curved background).
   These enter at 1.5PN but are often grouped with 1PN analysis.
4. **Periastron advance effect:** The relativistic advance of periastron (omega_dot = 4.2 deg/yr)
   modifies the orbit-averaging procedure.

**Key references:**
- Damour & Deruelle (1986): DD parameterization, relativistic orbit elements
- Blanchet & Schaefer (1989): 1PN energy loss for eccentric binaries
- Blanchet (2014), Living Reviews: Systematic PN expansion to high orders

**Estimated depth:** comprehensive (5-7 plans)

---

## Phase 4: Numerical Evaluation and Comparison with Observations

**Objective:** Plug the Hulse-Taylor parameters into both the 0PN and 1PN formulas, compute
the predicted Ṗ_b, and compare with the observed value.

**Key comparisons:**

| Quantity | Value |
|---|---|
| Ṗ_b (Peters, 0PN) | -2.4025 x 10^{-12} |
| Ṗ_b (1PN corrected) | To be computed |
| Ṗ_b (observed, intrinsic) | (-2.4056 +/- 0.0051) x 10^{-12} |
| (Ṗ_b^obs - Ṗ_b^GR) / Ṗ_b^GR | 0.9983 +/- 0.0021 (Weisberg & Huang 2016) |

**Deliverables:**
- Numerical code evaluating F(e) and the 1PN correction factor
- Error propagation from parameter uncertainties to Ṗ_b uncertainty
- Comparison table: 0PN vs 1PN vs observed
- Discussion of the 0.13% residual and whether 1PN corrections account for it

**Estimated depth:** standard (3-4 plans)

---

## Phase 5: Paper Writing

**Objective:** Compile the derivation, numerical results, and comparison into a Physical Review D
manuscript.

**Structure:**
1. Introduction — historical significance, discovery (Hulse & Taylor 1975), Nobel Prize context
2. Setup — binary parameters, DD timing model, conventions
3. Quadrupole formula — derivation, enhancement function, Peters (1964) result
4. 1PN corrections — Damour-Deruelle, tail terms, corrected period derivative
5. Numerical results — evaluation, error analysis, comparison with observations
6. Discussion — agreement with GR, constraints on alternative theories, future prospects
7. Conclusion

**Estimated depth:** standard (3-4 plans)
```

---

## 3. PLAN.md Example (Phase 2, Plan 1: Quadrupole Formula)

```markdown
# Phase 02 Plan 01 — Quadrupole Radiation Formula for Eccentric Binaries

## Scope

Derive the orbit-averaged gravitational wave energy loss for a binary system in an eccentric
Keplerian orbit (Peters & Mathews 1963, Peters 1964). Compute the resulting orbital period
derivative. Evaluate numerically for the Hulse-Taylor system and verify against the known
value Ṗ_b = -2.4025 x 10^{-12}.

## Conventions (inherited from Phase 01)

```yaml
conventions:
  units: "geometrized (G = c = 1)"
  metric_signature: "(-,+,+,+)"
  pn_counting: "0PN = quadrupole (leading order)"
  masses: "m_1 >= m_2"
```

SI restoration: Energy flux formula in geometrized units is P = -(32/5) mu^2 M^3 / a^5 f(e).
In SI: P = -(32/5) (G^4/c^5) m_1^2 m_2^2 (m_1+m_2) / a^5 f(e).

## Truths

These are statements that must hold at the end of the plan. Each is independently verifiable.

1. "The quadrupole formula gives instantaneous power dE/dt = -(G^4/c^5)(32/5) m_1^2 m_2^2 (m_1+m_2) / r^5 g(v,r) where g encodes the velocity-dependent angular structure."

2. "Orbit-averaging the power over one eccentric period using the Keplerian parametric solution yields <dE/dt> = -(32/5)(G^4/c^5) m_1^2 m_2^2 (m_1+m_2) / a^5 f(e), matching Peters & Mathews (1963) Eq. 5.6."

3. "The eccentricity enhancement function is F(e) = (1 + 73e^2/24 + 37e^4/96)(1-e^2)^{-7/2}."

4. "The predicted period derivative is Ṗ_b/P_b = -(96/5)(G^3/c^5) m_1 m_2 (m_1+m_2) / a^4 (1-e^2)^{-7/2} F_P(e) where F_P(e) incorporates the Peters enhancement, obtained via Kepler's third law dP/dt = (3/2)(P/E)(dE/dt)."

5. "Numerical evaluation with m_1 = 1.4414 M_sun, m_2 = 1.3867 M_sun, e = 0.6171334, P_b = 27906.98 s gives Ṗ_b = -2.4025 x 10^{-12} to 4 significant figures."

## Tasks

### Task 1: Derive instantaneous quadrupole energy loss

Starting from the quadrupole formula for gravitational wave luminosity:

```
P_GW = -dE/dt = (1/5) <d^3 Q_{ij}/dt^3 d^3 Q^{ij}/dt^3>
```

where Q_{ij} = I_{ij} - (1/3) delta_{ij} I_{kk} is the traceless quadrupole moment.

For a binary system with reduced mass mu and separation vector r_i:
- Q_{ij} = mu (r_i r_j - (1/3) r^2 delta_{ij})
- Compute the third time derivatives using the Keplerian equations of motion
- Express dE/dt as a function of orbital elements (r, dr/dt, d(theta)/dt)

**Verification:** Dimensional analysis — [P_GW] = [energy/time] = G^4 M^5 / (c^5 a^5) in SI.

### Task 2: Orbit-average over the eccentric Keplerian orbit

The Keplerian parametric solution for an eccentric orbit:

```
r = a(1 - e cos(u))                         (radial distance)
l = u - e sin(u) = n(t - t_0)               (mean anomaly, n = 2*pi/P_b)
dt = (1 - e cos(u)) du / n                  (time element)
```

Average the instantaneous power over one period:

```
<P_GW> = (1/P_b) integral_0^{P_b} P_GW(t) dt = (1/2*pi) integral_0^{2*pi} P_GW(u) (1 - e cos(u)) du
```

The integral involves powers of 1/(1 - e cos(u))^n, which yield closed-form expressions via the
integrals tabulated in Peters & Mathews (1963) Appendix.

**Verification:** At e = 0 (circular orbit), <P_GW> must reduce to -(32/5) mu^2 M^3 / a^5.

### Task 3: Extract the period derivative via Kepler's third law

From Kepler's third law in geometrized units: P_b^2 = (4*pi^2 / M) a^3.

Differentiating: dP_b/dt = (3/2)(P_b/a)(da/dt).

The semi-major axis evolves via: da/dt = -(2a^2 / (G M mu)) <dE/dt> (energy-orbit relation for
Keplerian motion, where E_orb = -G M mu / (2a)).

Combining: Ṗ_b = -(192*pi/5) (G^{5/3}/c^5) (P_b/(2*pi))^{-5/3} m_1 m_2 (m_1+m_2)^{-1/3} F(e)

where F(e) = (1 + 73e^2/24 + 37e^4/96)(1-e^2)^{-7/2}.

**Verification:** Check that this matches Peters (1964) Eq. 5.6 exactly.

### Task 4: Numerical evaluation for PSR B1913+16

```python
import numpy as np

# Constants in SI
G = 6.67430e-11       # m^3 kg^-1 s^-2
c = 2.99792458e8      # m/s
M_sun = 1.98892e30    # kg

# Hulse-Taylor system parameters (Weisberg & Huang 2016)
m1 = 1.4414 * M_sun   # kg
m2 = 1.3867 * M_sun   # kg
e = 0.6171334
P_b = 27906.9796       # s (7.75194 hours)

# Derived quantities
M = m1 + m2
mu = m1 * m2 / M
eta = mu / M            # symmetric mass ratio ~ 0.2499

# Semi-major axis from Kepler's third law
a = (G * M * (P_b / (2 * np.pi))**2)**(1.0/3.0)

# Enhancement function F(e)
Fe = (1 + (73.0/24.0)*e**2 + (37.0/96.0)*e**4) * (1 - e**2)**(-3.5)

# Peters formula for Ṗ_b
P_dot = -(192 * np.pi / 5) * (G**(5.0/3.0) / c**5) \
        * (P_b / (2*np.pi))**(-5.0/3.0) \
        * m1 * m2 * M**(-1.0/3.0) * Fe

print(f"Semi-major axis: a = {a:.4e} m = {a/c:.4f} lt-s")
print(f"Enhancement F(e=0.6171) = {Fe:.4f}")
print(f"Orbital velocity v/c ~ {(2*np.pi*a/P_b)/c:.4e}")
print(f"PN parameter GM/(ac^2) = {G*M/(a*c**2):.4e}")
print(f"Ṗ_b = {P_dot:.4e}")
```

Expected output:
- F(0.6171) approximately 11.85
- Ṗ_b approximately -2.4025 x 10^{-12}

**Verification:** Compare with Weisberg & Huang (2016) Table 3: Ṗ_b^GR = (-2.40242 +/- 0.00002) x 10^{-12}.
```

---

## 4. SUMMARY.md Example (Phase 2 Completed)

```yaml
---
phase: "02"
plan: "01"
physics-area: gravitational waves, post-Newtonian, binary pulsars
tags: [quadrupole-formula, Peters-formula, orbital-decay, PSR-B1913+16, GW-emission]
requires:
  - "01-01: System parameters and DD timing model"
  - "01-02: Convention lock (geometrized units, mostly-minus metric)"
provides:
  - "Ṗ_b = -2.4025 x 10^{-12} (Peters 0PN quadrupole formula)"
  - "Enhancement function F(e) = (1 + 73e^2/24 + 37e^4/96)(1-e^2)^{-7/2}"
  - "Peters formula: Ṗ_b = -(192*pi/5)(G^{5/3}/c^5)(P_b/2pi)^{-5/3} m1 m2 M^{-1/3} F(e)"
  - "Numerical code evaluating Ṗ_b from binary parameters"
affects:
  - "03-01: 1PN corrections (baseline 0PN result needed for comparison)"
  - "04-01: Numerical evaluation (Peters formula is the leading term)"
  - "05-01: Paper writing (Section 3: quadrupole derivation)"
verification_inputs:
  truths:
    - claim: "Peters formula reproduces the known GR prediction for PSR B1913+16"
      test_value: "Ṗ_b computed from m1, m2, e, P_b"
      expected: "-2.4025 x 10^{-12}"
      tolerance: "0.01%"
    - claim: "Enhancement function F(e) gives ~11.85 at e = 0.6171"
      test_value: "F(0.6171334)"
      expected: "11.85 (to 4 significant figures)"
    - claim: "Circular orbit limit F(0) = 1"
      test_value: "F(e=0)"
      expected: "1.0 exactly"
  limiting_cases:
    - limit: "e -> 0 (circular orbit)"
      expected_behavior: "F(e) -> 1; Ṗ_b reduces to -(192*pi/5)(G^{5/3}/c^5)(P_b/2pi)^{-5/3} m1 m2 M^{-1/3}"
      reference: "Peters (1964) Eq. 5.4"
    - limit: "e -> 1 (radial plunge)"
      expected_behavior: "F(e) -> infinity as (1-e^2)^{-7/2}; physically, highly eccentric orbits radiate much more efficiently near periastron"
      reference: "Peters & Mathews (1963) Section V"
    - limit: "m2 -> 0 (test particle)"
      expected_behavior: "Ṗ_b -> 0; no gravitational radiation from a test particle (quadrupole moment vanishes)"
      reference: "Dimensional analysis"
    - limit: "m1 = m2 (equal mass)"
      expected_behavior: "Ṗ_b = -(192*pi/5)(G^{5/3}/c^5)(P_b/2pi)^{-5/3} (M/4)(M)^{-1/3} F(e) = -(48*pi/5)(G^{5/3}/c^5)(P_b/2pi)^{-5/3} M^{2/3} F(e)"
      reference: "Symmetry"
  key_equations:
    - label: "Eq. (02.1)"
      expression: "\\dot{P}_b = -\\frac{192\\pi}{5} \\frac{G^{5/3}}{c^5} \\left(\\frac{P_b}{2\\pi}\\right)^{-5/3} m_1 m_2 M^{-1/3} F(e)"
      test_point: "m_1 = 1.4414 M_sun, m_2 = 1.3867 M_sun, e = 0.6171334, P_b = 27906.98 s"
      expected_value: "-2.4025 x 10^{-12}"
    - label: "Eq. (02.2)"
      expression: "F(e) = \\frac{1 + \\frac{73}{24}e^2 + \\frac{37}{96}e^4}{(1-e^2)^{7/2}}"
      test_point: "e = 0.6171334"
      expected_value: "11.85"
    - label: "Eq. (02.3)"
      expression: "\\left\\langle\\frac{dE}{dt}\\right\\rangle = -\\frac{32}{5} \\frac{G^4}{c^5} \\frac{m_1^2 m_2^2 (m_1+m_2)}{a^5} f(e)"
      test_point: "Hulse-Taylor parameters"
      expected_value: "~7.35 x 10^{24} W (verify dimensionally)"
---

# Phase 02 Plan 01: Quadrupole Radiation and Orbital Decay — Summary

Derived the Peters (1964) quadrupole formula for gravitational wave energy loss from an
eccentric binary orbit. Orbit-averaged the instantaneous power loss over the Keplerian
parametric solution. Extracted the orbital period derivative via Kepler's third law.
Evaluated numerically for the Hulse-Taylor binary PSR B1913+16.

## Conventions Used

| Convention | Choice | Inherited from | Notes |
|---|---|---|---|
| Units | Geometrized (G=c=1) | Phase 01 | SI restored for numerical evaluation |
| Metric | (-,+,+,+) mostly minus | Phase 01 | |
| PN counting | 0PN = quadrupole | Phase 01 | Leading order in this plan |
| Masses | m_1 >= m_2 | Phase 01 | m_1 = 1.4414 M_sun (pulsar) |
| Eccentricity | Keplerian e_K | Phase 01 | At 0PN, e_K = e_t (DD time eccentricity) |

## Key Results

### Enhancement function

F(e) = (1 + 73e^2/24 + 37e^4/96)(1 - e^2)^{-7/2}

Evaluated at e = 0.6171334:

F(0.6171334) = 11.8494 [CONFIDENCE: HIGH]

Verification:
- F(0) = 1 exactly (circular orbit limit) -- PASS
- F(e) -> infinity as e -> 1 (expected: periastron dominance) -- PASS
- Value matches Peters & Mathews (1963) Table I interpolation -- PASS

### Peters formula for orbital period derivative

Ṗ_b = -(192*pi/5)(G^{5/3}/c^5)(P_b/2pi)^{-5/3} m_1 m_2 M^{-1/3} F(e) [CONFIDENCE: HIGH]

### Numerical evaluation

| Quantity | Value |
|---|---|
| Semi-major axis a | 1.950 x 10^9 m (6.506 lt-s) |
| Orbital velocity v/c | 4.39 x 10^{-4} (at mean anomaly) |
| PN expansion parameter GM/(ac^2) | 4.29 x 10^{-6} |
| F(e = 0.6171) | 11.8494 |
| **Ṗ_b (Peters, 0PN)** | **-2.4025 x 10^{-12}** |
| Ṗ_b (observed, intrinsic) | (-2.4056 +/- 0.0051) x 10^{-12} |
| Ratio Ṗ_b^obs / Ṗ_b^Peters | 1.0013 +/- 0.0021 |
| **Agreement** | **0.13% (within 1-sigma)** |

The Peters quadrupole formula agrees with the observed intrinsic period derivative to 0.13%.
The residual is consistent with the expected size of 1PN corrections (~v^2/c^2 ~ 4 x 10^{-6}),
higher-order PN effects, and measurement uncertainties.

### Checks performed

1. **Dimensional analysis** at every step — all expressions have correct dimensions [PASS]
2. **Circular orbit limit** e -> 0: F(0) = 1, formula reduces to known circular result [PASS]
3. **Test particle limit** m_2 -> 0: Ṗ_b -> 0 as expected (no quadrupole radiation) [PASS]
4. **Literature comparison:** Ṗ_b = -2.4025 x 10^{-12} matches Weisberg & Huang (2016) Table 3 value of (-2.40242 +/- 0.00002) x 10^{-12} [PASS]
5. **Numerical cross-check:** Independent evaluation using chirp mass formulation M_c^{5/3} = m_1 m_2 (m_1+m_2)^{-1/3} gives the same Ṗ_b to 10 significant figures [PASS]
6. **Sign check:** Ṗ_b < 0 (orbit shrinks due to energy loss) — physically correct [PASS]

Overconfidence check: "What could be wrong that I have not checked?"
- The formula assumes point masses; finite-size (tidal) effects are negligible for neutron stars at this separation (~10^{-10} relative correction) -- safe to ignore
- The Shklovskii contribution and Galactic acceleration correction are not rederived here; they are taken from Weisberg & Huang (2016) -- acceptable for this plan

No unchecked failure modes that could affect the 4-significant-figure result.

**Result: [CONFIDENCE: HIGH]** — Dimensional analysis, three limiting cases (circular, test-particle, equal-mass), literature comparison to 5 significant figures, and independent numerical cross-check all pass.

## Deviations from Plan

None. All four tasks completed as planned. The orbit-averaging integrals required the
standard Keplerian integrals (Peters & Mathews 1963, Appendix), which were evaluated
analytically using the substitution u = eccentric anomaly. No unexpected difficulties.
```

---

## Usage Notes

This worked example trains the roadmapper and planner agents on:

1. **PROJECT.md conventions for GR/astrophysics:** geometrized units, mostly-minus metric, PN counting, explicit SI restoration rules, binary system parameter tables with full provenance.

2. **ROADMAP.md phase structure for a derivation-then-evaluate project:** literature review first, leading-order derivation before corrections, numerical evaluation as a distinct phase, paper writing last. Each phase states its verification target.

3. **PLAN.md truth statements:** each truth is a testable assertion with a concrete numerical target. The enhancement function F(e) is stated explicitly so the verifier can evaluate it independently.

4. **SUMMARY.md verification depth:** multiple limiting cases (circular, test-particle, equal-mass, radial plunge), literature comparison with specific equation numbers, independent numerical cross-check via chirp mass reformulation, and honest assessment of what was NOT checked.

5. **The 0.13% residual as a science driver:** the agreement between Peters formula and observation is extraordinary but not perfect. The residual motivates Phase 3 (1PN corrections), demonstrating how a worked example connects phases in the roadmap.
