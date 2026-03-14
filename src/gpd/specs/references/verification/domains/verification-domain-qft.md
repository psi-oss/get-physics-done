---
load_when:
  - "QFT verification"
  - "Ward identity"
  - "unitarity check"
  - "crossing symmetry"
  - "scattering amplitude"
tier: 2
context_cost: large
---

# Verification Domain — QFT and Particle Physics

Ward identities, unitarity, causality, positivity, crossing symmetry, and subfield-specific checks for quantum field theory and particle physics.

> **Note:** For GR/cosmology, see `references/verification/domains/verification-domain-gr-cosmology.md`. For mathematical physics, see `references/verification/domains/verification-domain-mathematical-physics.md`. For algebraic QFT and operator algebras, see `references/verification/domains/verification-domain-algebraic-qft.md`. For string field theory, see `references/verification/domains/verification-domain-string-field-theory.md`. For nuclear/particle, see `references/verification/domains/verification-domain-nuclear-particle.md`.

**Load when:** Working on QFT calculations, scattering amplitudes, renormalization, general relativity, or mathematical physics.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-condmat.md` — condensed matter, quantum information, AMO
- `references/verification/domains/verification-domain-statmech.md` — statistical mechanics, cosmology, fluids

---

<ward_identities>

## Ward Identities

Exact relations between Green's functions that follow from gauge symmetries. Violations indicate broken symmetries or computational errors.

**Principle:** Every continuous symmetry yields a Ward identity relating different correlation functions. These are exact (non-perturbative) constraints that any valid calculation must satisfy.

**QED Ward-Takahashi identity:**

```
q_mu Gamma^mu(p+q, p) = S^{-1}(p+q) - S^{-1}(p)

Consequences:
- At q -> 0: vertex correction related to self-energy derivative
- Z_1 = Z_2 (vertex and wavefunction renormalization)
- Charge is not renormalized: physical charge = bare charge * Z_3^{1/2}

Verification: Compute Gamma^mu and S independently; contract with q_mu; compare sides
```

**Goldstone theorem (spontaneous symmetry breaking):**

```
If a continuous symmetry is spontaneously broken:
- There must be a massless (Goldstone) mode for each broken generator
- <0|J^mu|pi(p)> = i f_pi p^mu (pion decay constant relates current to Goldstone)

Verification: Check that pole in propagator appears at p^2 = 0 for each broken generator
```

**Verification protocol:**

```python
def verify_ward_identity(vertex, propagator_inv, momentum_transfer):
    """
    Verify Ward-Takahashi identity: q_mu Gamma^mu = S^{-1}(p+q) - S^{-1}(p).
    """
    lhs = np.einsum('i,i...->...', momentum_transfer, vertex)
    rhs = propagator_inv['p_plus_q'] - propagator_inv['p']
    deviation = np.max(np.abs(lhs - rhs))
    status = "PASS" if deviation < 1e-10 else "FAIL"
    print(f"{status} Ward identity: max deviation = {deviation:.2e}")
    return deviation < 1e-10
```

</ward_identities>

<soft_asymptotic_symmetries>

## Soft Limits and Asymptotic Symmetry Checks

Large gauge symmetries and BMS-type symmetries control the infrared structure of scattering with massless gauge bosons or gravitons. A soft theorem should not be treated as an isolated amplitude identity; it should match a boundary charge and a flux/conservation statement.

```
Leading soft structure:
  soft theorem  <->  Ward identity of asymptotic charge

Operational split:
  Q_total = Q_hard + Q_soft

Verification:
1. Take the soft limit of the amplitude and verify factorization onto the universal soft factor.
2. Check that the corresponding charge acts correctly on the hard external states.
3. State the boundary conditions at null infinity or the infrared regulator used.
4. If memory or asymptotic charges are invoked, verify the same convention for the radiative field is used throughout.
```

</soft_asymptotic_symmetries>

<generalized_symmetry_checks>

## Generalized Symmetry and Defect Checks

Generalized symmetries are encoded by topological defects acting on extended operators. The claim "this theory has a `p`-form symmetry" is incomplete unless the charged operator, background field, and breaking mechanism are all specified.

```
For a claimed p-form symmetry in d dimensions:
  charged operator dimension  = p
  symmetry generator          = codimension-(p+1) topological defect
  background gauge field      = (p+1)-form

Core logic:
  genuine charged operator + topological defect + consistent background coupling
  -> well-defined generalized symmetry statement
```

**Verification:**

```
1. Identify the charged extended operator explicitly (Wilson line, 't Hooft line, surface defect, etc.).
2. Check whether the operator is genuine or can end on dynamical matter. If it can end, the symmetry is broken or absent.
3. Verify the symmetry defect is topological away from charged insertions.
4. For invertible p>0 symmetries, verify the symmetry action/fusion is abelian.
5. If center symmetry or confinement is discussed, verify the matter content does or does not screen the relevant Wilson lines.
6. If gauging or anomaly matching is invoked, write the correct background-field degree and the inflow/anomaly term explicitly.
7. If higher-group or non-invertible language is used, state the mixed background transformation or the defect fusion rule explicitly.
```

</generalized_symmetry_checks>

<supersymmetry_bps_localization>

## Supersymmetry, BPS, and Localization Checks

Supersymmetric results are often protected rather than generic. A valid SUSY calculation must say whether it relies on algebraic shortening, an index, localization, duality, or a direct component computation.

```
For a claimed SUSY/protected result:
  choose the supercharge(s) Q
  state the regime: rigid SUSY or supergravity
  state the object: BPS mass, index, localized partition function, duality map, or ordinary correlator
```

**Verification:**

```
1. State the dimension, amount of SUSY, and whether the setup is rigid SUSY or local SUSY/supergravity.
2. If a BPS statement is made, derive the bound from the superalgebra and include the relevant central charge or R-charge combination.
3. If an index is used, verify it is a protected quantity and do not equate it with a raw degeneracy count without extra control.
4. If localization is used, state Q, Q^2, the fixed locus, one-loop determinants, contour prescription, and zero-mode treatment.
5. If Seiberg duality or another SUSY duality is invoked, match global symmetries, 't Hooft anomalies, moduli spaces, operator maps, and protected observables.
6. If supergravity is involved, verify Killing-spinor/BPS equations or the correct supergravity potential instead of importing rigid-SUSY vacuum formulas.
```

</supersymmetry_bps_localization>

<unitarity_causality_positivity>

## Unitarity, Causality, and Positivity Constraints

Fundamental constraints from quantum mechanics and special relativity that any physical result must satisfy. Non-negotiable.

### Unitarity bounds

**Principle:** The S-matrix is unitary (S*S = 1), which means probability is conserved in scattering. This imposes absolute constraints on cross sections and amplitudes.

```
Optical theorem:
  Im[f(0)] = (k/(4*pi)) * sigma_total
  where f(0) is the forward scattering amplitude

  This is exact. Verification: compute Im[f(0)] from your amplitude
  and sigma_total from integrating |f(theta)|^2; they must agree.

Partial wave unitarity:
  |S_l| <= 1 for each partial wave (elastic unitarity: |S_l| = 1)
  Equivalently: 0 <= sigma_l <= 4*pi*(2l+1)/k^2

  At high energies (Froissart bound):
  sigma_total <= (pi/m_pi^2) ln^2(s/s_0)
  If your cross section grows faster than ln^2(s), unitarity is violated.

Unitarity of time evolution:
  If psi(t) = U(t)*psi(0), then U*U = 1
  - Norm preserved: <psi(t)|psi(t)> = <psi(0)|psi(0)>
  - Density matrix: Tr[rho(t)] = 1 for all t
  - Eigenvalues of rho: 0 <= lambda_i <= 1 for all i (complete positivity)

Perturbative unitarity bound (scalar scattering):
  |a_0| <= 1/2 (s-wave partial wave amplitude)
  Gives upper bound on coupling: e.g., lambda <= 8*pi for phi^4 theory
  Higgs mass bound from WW scattering: m_H <= 870 GeV (before discovery)
```

**Verification protocol:**

```python
def verify_unitarity_bound(partial_wave_amplitudes, k, tolerance=1e-8):
    """Check |S_l| <= 1 for all partial waves."""
    for l, a_l in enumerate(partial_wave_amplitudes):
        S_l = 1 + 2j * k * a_l
        if abs(S_l) > 1 + tolerance:
            print(f"FAIL Unitarity violated: |S_{l}| = {abs(S_l):.6f} > 1")
            return False
    print("PASS Partial wave unitarity satisfied for all l")
    return True

def verify_optical_theorem(forward_amplitude, total_cross_section, k, tolerance=0.01):
    """Check Im[f(0)] = k sigma_total / (4*pi)."""
    lhs = forward_amplitude.imag
    rhs = k * total_cross_section / (4 * np.pi)
    relative_diff = abs(lhs - rhs) / abs(rhs) if rhs != 0 else abs(lhs)
    status = "PASS" if relative_diff < tolerance else "FAIL"
    print(f"{status} Optical theorem: Im[f(0)] = {lhs:.6e}, "
          f"k sigma/(4*pi) = {rhs:.6e}, diff = {relative_diff:.2e}")
    return relative_diff < tolerance
```

### Causality constraints

**Principle:** Effects cannot precede causes. Information cannot travel faster than light. This constrains the analytic structure of response functions.

```
Retarded response functions:
  G^R(t) = 0 for t < 0 (no response before perturbation)
  Equivalently: G^R(omega) is analytic in upper half of complex omega-plane
  Poles/branch cuts only in lower half-plane (or on real axis for stable systems)

Microcausality (QFT):
  [phi(x), phi(y)] = 0 for (x-y)^2 < 0 (spacelike separation)
  Commutator/propagator must vanish outside light cone

Signal velocity:
  Group velocity v_g = d(omega)/dk may exceed c (anomalous dispersion)
  But signal velocity (front velocity) v_f = lim_{omega->inf} omega/k(omega) <= c always
  A computed dispersion relation with v_f > c is wrong.
```

**Verification:**

```python
def verify_retarded_causality(G_R_time, time_grid, tolerance=1e-10):
    """Check G^R(t < 0) = 0."""
    negative_time_mask = time_grid < 0
    max_violation = np.max(np.abs(G_R_time[negative_time_mask]))
    status = "PASS" if max_violation < tolerance else "FAIL"
    print(f"{status} Retarded causality: max |G^R(t<0)| = {max_violation:.2e}")
    return max_violation < tolerance
```

### Positivity constraints

**Principle:** Certain physical quantities are inherently non-negative. Violation is a definitive error signal.

```
Spectral function positivity:
  A(k, omega) >= 0 for all k, omega (spectral weight is non-negative)
  Related to ImG^R: A(k, omega) = -(1/pi) Im G^R(k, omega) (with correct sign convention)
  Negative spectral weight = unphysical = error in self-energy or analytic continuation

Cross section positivity:
  d(sigma)/d(Omega) >= 0 for all angles (|amplitude|^2 is non-negative)

Entropy positivity:
  S >= 0 always (von Neumann entropy for quantum states)
  S = -Tr[rho ln rho] >= 0 when rho is a valid density matrix

Positive semi-definiteness of density matrix:
  All eigenvalues lambda_i >= 0
  rho = rho* (Hermitian)
  Tr[rho] = 1

Positive energy (stable vacuum):
  <psi|H|psi> >= E_0 for all |psi>
  Spectrum bounded below (Hamiltonians of physical systems)

Reflection positivity (Euclidean QFT):
  <O*(tau) O(0)> >= 0 for tau > 0
  Required for Osterwalder-Schrader reconstruction of Hilbert space
  Violated -> theory has no sensible quantum mechanical interpretation

Convexity of free energy:
  F(T, V, N) is concave in T, convex in V (thermodynamic stability)
  d^2F/dV^2 > 0 -> positive compressibility
  -d^2F/dT^2 > 0 -> positive specific heat
```

</unitarity_causality_positivity>

## Worked Examples

### Sign error in scattering amplitude — caught by crossing symmetry

**Scenario:** An LLM computes tree-level 2->2 scattering of identical scalars in phi^3 theory. The amplitude has s-, t-, and u-channel contributions, but the LLM introduces a sign error in the t-channel propagator.

**The error:** M = -g^2 [1/(s-m^2) **-** 1/(t-m^2) + 1/(u-m^2)] instead of the correct M = -g^2 [1/(s-m^2) **+** 1/(t-m^2) + 1/(u-m^2)].

**Verification check:** Crossing symmetry. For identical particles, the amplitude must be invariant under s <-> t.

```python
import numpy as np

m2, g2 = 1.0, 0.5  # m^2 and g^2

def M_claimed(s, t, u):
    """LLM's amplitude: sign error in t-channel."""
    return -g2 * (1 / (s - m2) - 1 / (t - m2) + 1 / (u - m2))

def M_correct(s, t, u):
    """Correct amplitude: all channels have same sign."""
    return -g2 * (1 / (s - m2) + 1 / (t - m2) + 1 / (u - m2))

# Kinematics: s + t + u = 4m^2 for equal-mass scattering
s, t = 6.0, -1.5
u = 4 * m2 - s - t  # = -0.5

# CROSSING SYMMETRY CHECK: M(s,t,u) must equal M(t,s,u) for identical particles
M_st = M_claimed(s, t, u)
M_ts = M_claimed(t, s, u)
print(f"  M_claimed(s,t,u) = {M_st:+.6f}")
print(f"  M_claimed(t,s,u) = {M_ts:+.6f}")
print(f"  Difference: {abs(M_st - M_ts):.6e}  FAIL (not crossing-symmetric)")
```

**Lesson:** Crossing symmetry is a powerful algebraic check that requires no numerical evaluation of integrals — just substitute s <-> t and compare.

---

### Missing identical-particle symmetrization — caught by spot-check

**Scenario:** An LLM computes the differential cross section for Coulomb scattering of identical spin-0 bosons. It uses the Rutherford formula directly, forgetting that identical particles require amplitude symmetrization: d(sigma)/d(Omega) = |f(theta) + f(pi-theta)|^2.

**Verification check:** Spot-check at theta = 90 degrees against the known Mott result. At 90 degrees, the exchange amplitude equals the direct amplitude, so the Mott cross section is exactly 4x the Rutherford value.

```python
import numpy as np

a = 1.0

def f_rutherford(theta):
    return -a / (2 * np.sin(theta / 2)**2)

def dsigma_claimed(theta):
    """No symmetrization."""
    return np.abs(f_rutherford(theta))**2

def dsigma_correct(theta):
    """Mott formula: symmetrized amplitude for identical bosons."""
    return np.abs(f_rutherford(theta) + f_rutherford(np.pi - theta))**2

theta_90 = np.pi / 2
ratio = dsigma_correct(theta_90) / dsigma_claimed(theta_90)
# Ratio must be 4 at 90 degrees for identical bosons
```

**Lesson:** Spot-checking against known results at special kinematic points is fast and definitive. The pattern — LLM forgetting identical-particle quantum statistics — is one of the most common physics errors.

---

## Subfield-Specific Checks

### Quantum Field Theory

**Priority checks:**

1. Ward identities (gauge invariance): q_mu * Gamma^mu must equal propagator difference
2. Unitarity: optical theorem relates Im[forward amplitude] to total cross section
3. Gauge independence: compute same observable in two gauges; results must agree
4. UV divergence structure: poles match power counting; beta function coefficient is scheme-independent at one loop
5. Crossing symmetry: amplitude in s-channel analytically continues to t-channel correctly

**Red flags:**

- Cross section that grows faster than ln^2(s) at high energy (Froissart bound violation)
- Non-zero result when replacing polarization vector epsilon_mu -> k_mu for gauge-invariant observable
- Amplitude that depends on gauge-fixing parameter xi for physical process
- Missing fermion loop (-1) factor or wrong symmetry factors in Feynman diagrams

### Nuclear/Particle Physics

**Priority checks:**

1. Branching ratios sum to 1
2. Mandelstam variables: s + t + u = sum of squared masses
3. CKM unitarity: first row |V_ud|^2 + |V_us|^2 + |V_ub|^2 = 1
4. Color factors: C_F = 4/3, C_A = 3, T_R = 1/2 for SU(3)
5. PDF sum rules: momentum sum rule integral x*(q + q-bar + g) dx = 1

**Red flags:**

- Cross section with wrong flux factor (off by factor of 4 or 2*s)
- NLO K-factor borrowed from different process
- PDF uncertainties not propagated to theory predictions
- Missing spin-averaging factor (1/(2s+1) for each initial-state particle)

### General Relativity

**Priority checks:**

1. Constraint monitoring: Hamiltonian and momentum constraints converge to zero with resolution
2. ADM mass conservation: M_ADM constant throughout evolution (or decreasing by GW energy radiated)
3. Convergence order: Richardson extrapolation gives expected convergence rate
4. QNM frequencies: ringdown matches perturbation theory predictions
5. Gauge invariance: physical observables independent of gauge choice

**Red flags:**

- Constraint violations growing during evolution (unstable formulation or insufficient resolution)
- Coordinate singularity mistaken for physical singularity (check curvature invariants)
- Waveform extraction at single finite radius without extrapolation to infinity
- Junk radiation not excluded from waveform analysis

### Mathematical Physics

**Priority checks:**

1. All hypotheses of applied theorems must be verified
2. Topological invariants must be integers (or appropriate rational numbers)
3. Representation dimensions must match Weyl dimension formula
4. Index theorem: analytic index (zero mode count) = topological index (curvature integral)
5. Consistency of limiting operations (interchange of limits, integral, sum justified)

**Red flags:**

- Interchange of limit and integral without dominated convergence or uniform convergence argument
- Formal power series treated as convergent without Borel summability analysis
- Self-adjointness claimed without checking domain equality of H and H^dag
- Classification theorem applied without verifying all hypotheses (e.g., compactness, connectedness)

## See Also

- `../core/verification-quick-reference.md` -- Compact checklist (default entry point)
- `../core/verification-core.md` -- Dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` -- Convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-condmat.md` -- Condensed matter, quantum information, AMO
- `references/verification/domains/verification-domain-statmech.md` -- Statistical mechanics, cosmology, fluids
