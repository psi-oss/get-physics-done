---
load_when:
  - "GR verification"
  - "cosmology verification"
  - "Einstein equations"
  - "Friedmann equation"
  - "gravitational wave"
  - "black hole"
  - "CMB"
  - "perturbation theory cosmology"
tier: 2
context_cost: large
---

# Verification Domain — General Relativity & Cosmology

Constraint propagation, gauge invariance of perturbations, energy conditions, asymptotic structure, and cosmological consistency checks for general relativity and cosmology.

**Load when:** Working on GR calculations, black holes, gravitational waves, cosmological perturbation theory, CMB physics, or dark energy models.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-qft.md` — QFT, particle physics (for quantum gravity overlap)
- `references/verification/domains/verification-domain-astrophysics.md` — astrophysics (for observational cosmology overlap)

---

<constraint_propagation>

## Constraint Propagation and ADM Conservation

In the 3+1 decomposition, the Einstein equations split into constraint equations (Hamiltonian and momentum constraints) and evolution equations. Constraint violations propagate and grow if not controlled.

**Hamiltonian constraint:**

```
H = R^(3) + K^2 - K_ij K^ij - 16*pi*rho = 0
where R^(3) is the 3D Ricci scalar, K_ij is the extrinsic curvature, rho is the energy density.

Verification: Evaluate H at every time step. |H| must remain < tolerance (typically 10^{-6} to 10^{-10}).
If H grows exponentially: constraint-damping scheme is needed (Z4, CCZ4, or BSSN with constraint damping).
```

**Momentum constraint:**

```
M^i = D_j (K^ij - gamma^ij K) - 8*pi*j^i = 0
where D_j is the covariant derivative of the 3-metric, j^i is the momentum density.

Verification: Same as Hamiltonian — monitor |M^i| at every step.
```

**ADM mass conservation:**

```
M_ADM = -(1/16*pi) lim_{r->inf} oint (d_i gamma_{ij} - d_j gamma_{ii}) dS^j

For isolated systems (no radiation escaping): M_ADM = const.
For radiating systems: dM_ADM/dt = -P_GW (gravitational wave luminosity).

Verification: Compute M_ADM at extraction radii; verify it decreases by exactly the radiated energy.
```

**Verification protocol:**

```python
def verify_constraints(hamiltonian_data, momentum_data, tolerance=1e-6):
    """
    Verify Hamiltonian and momentum constraints remain satisfied.
    """
    H_max = max(abs(h) for h in hamiltonian_data)
    M_max = max(max(abs(m) for m in mi) for mi in momentum_data)
    h_status = "PASS" if H_max < tolerance else "FAIL"
    m_status = "PASS" if M_max < tolerance else "FAIL"
    print(f"Hamiltonian constraint: max |H| = {H_max:.2e} [{h_status}]")
    print(f"Momentum constraint: max |M| = {M_max:.2e} [{m_status}]")
    return H_max < tolerance and M_max < tolerance
```

</constraint_propagation>

<gauge_invariance>

## Gauge Mode Contamination and Perturbation Gauge Invariance

GR has coordinate freedom (diffeomorphism invariance). Numerical simulations must fix a gauge, and cosmological perturbation theory must use gauge-invariant variables or explicit gauge fixing.

**Gauge conditions in numerical relativity:**

```
Common gauge choices:
- 1+log slicing: d_t alpha = -2*alpha*K (avoids singularity in collapse)
- Gamma-driver shift: d_t beta^i = (3/4)*B^i, d_t B^i = d_t tilde{Gamma}^i - eta*B^i

Verification:
1. Physical observables (gravitational wave strain, apparent horizon area) must be
   gauge-independent. Compute in TWO different gauge conditions and verify agreement.
2. Gauge modes should not grow: monitor |d_t alpha / alpha| and |d_t beta^i / alpha|
   for secular growth. Growing gauge modes indicate gauge instability.
```

**Cosmological perturbation gauge invariance:**

```
Bardeen potentials (gauge-invariant combinations):
  Phi_B = phi + (1/a) d_t [a(B - E')]     (Bardeen potential)
  Psi_B = psi - (a'/a)(B - E')             (Bardeen curvature potential)

where phi, psi, B, E are metric perturbations in a general gauge.

Verification:
1. Compute Phi_B and Psi_B in conformal Newtonian gauge (B=E=0) and synchronous gauge (phi=B=0).
   They must agree to machine precision.
2. Physical observables (CMB temperature anisotropy, matter power spectrum) must be identical
   in both gauges. Disagreement > 10^{-10} indicates a gauge artifact.
```

</gauge_invariance>

<energy_conditions>

## Energy Conditions and Penrose Diagram Consistency

**Energy condition verification:**

```
For stress-energy T_{mu nu} and timelike vector u^mu, null vector k^mu:

Weak energy condition (WEC):   T_{mu nu} u^mu u^nu >= 0  (energy density non-negative)
Null energy condition (NEC):   T_{mu nu} k^mu k^nu >= 0  (required for area theorem)
Strong energy condition (SEC):  (T_{mu nu} - (1/2)T g_{mu nu}) u^mu u^nu >= 0  (gravity attractive)
Dominant energy condition (DEC): T_{mu nu} u^mu is future-directed non-spacelike

Verification: Evaluate each condition for the computed T_{mu nu} at representative points.
NEC violation: signals exotic matter (wormholes, warp drives — flag as unphysical unless intentional).
WEC violation: negative energy density — check if quantum effects justify it (Casimir, squeezed states).
SEC violation: acceptable for dark energy (Lambda > 0 violates SEC).
```

**Penrose diagram consistency:**

```
For any spacetime solution:
1. Light cones must tilt correctly: dr/dt = +/- (1 - 2M/r) for Schwarzschild (ingoing light slows near horizon)
2. Horizons: verify g_{tt} = 0 at claimed horizon location
3. Singularities: verify Kretschmann scalar R_{abcd}R^{abcd} diverges
4. Asymptotic structure: verify metric -> Minkowski as r -> infinity (asymptotic flatness)
   or metric -> de Sitter as r -> infinity (cosmological horizon)
```

</energy_conditions>

<de_sitter_horizons>

## de Sitter Horizon and Positive-Cosmological-Constant Checks

**Background curvature and horizon data:**

```
Pure de Sitter in d spacetime dimensions:
  R_{mu nu} = (d-1) H^2 g_{mu nu}
  R = d(d-1) H^2
  Lambda = (d-1)(d-2) H^2 / 2

Static patch:
  ds^2 = -(1-r^2/L^2) dt^2 + dr^2/(1-r^2/L^2) + r^2 dOmega_{d-2}^2
  horizon at r = L = H^{-1}

Thermodynamics:
  T_dS = H/(2*pi)
  S_GH = A_H/(4G_N)
```

**Verification:**

```
1. Flat limit: take L -> infinity and verify the metric approaches Minkowski and all curvature invariants vanish.
2. Euclidean regularity: Wick rotate the static-patch time and verify the same temperature T_dS = H/(2*pi)
   follows from the absence of a conical defect at the cosmological horizon.
3. Curvature normalization: compute R_{mu nu} and R directly from the metric; verify the positive-Lambda relation above.
4. Inflationary observables: compare gauge-invariant data (zeta, gamma_ij, Bardeen potentials), not gauge-dependent field perturbations.
5. Higher-spin consistency: for massive spin-2 in 4d, verify the Higuchi bound m^2 >= 2H^2.
   Violation means the helicity-0 mode is ghostlike.
6. Schwarzschild-de Sitter: if both black-hole and cosmological horizons are present, verify which temperature or ensemble is being used.
   Generic SdS is not in global thermal equilibrium away from special limits such as Nariai/lukewarm constructions.
```

</de_sitter_horizons>

<null_infinity_bms>

## Null Infinity, Bondi Charges, and Memory

**Asymptotic radiative data:**

```
At future null infinity in Bondi gauge, track:
  C_AB        = Bondi shear
  N_AB        = partial_u C_AB   (news tensor)
  M_B         = Bondi mass / mass aspect data

Physical content:
  N_AB = 0    -> no gravitational radiation
  Delta C_AB  -> memory observable
```

**Verification:**

```
1. Residual symmetry check: verify the claimed BMS transformation preserves the chosen Bondi falloffs.
2. Translation limit: check that the l=0,1 supertranslation modes reduce to ordinary spacetime translations.
3. Balance law: verify the change in Bondi charge between two cuts equals the integrated flux through null infinity.
4. No-news limit: if N_AB = 0, verify Bondi mass is constant and no radiative memory is generated.
5. Waveform comparison: fix the BMS frame (or use CCE / large-radius extrapolation consistently) before comparing h, Psi_4, or memory observables between simulations.
6. Soft-memory consistency: when a soft theorem or memory statement is invoked, confirm the same convention for the asymptotic charge, waveform variable, and radiative field is being used throughout.
```

</null_infinity_bms>

<cosmological_consistency>

## Cosmological Consistency Checks

**Friedmann equation conservation:**

```
First Friedmann: H^2 = (8*pi*G/3)*rho - k/a^2 + Lambda/3
Second Friedmann: a''/a = -(4*pi*G/3)*(rho + 3P) + Lambda/3
Continuity: rho' + 3H(rho + P) = 0

These three are NOT independent — any two imply the third.
Verification: Compute all three independently at 10+ time steps. Verify consistency to machine precision.
If all three are satisfied independently: redundant confirmation (very strong check).
If continuity is violated while Friedmann holds: energy is not conserved (unphysical source term).
```

**CMB power spectrum normalization:**

```
Angular power spectrum C_l from Boltzmann code (CLASS/CAMB):

Verification:
1. Sachs-Wolfe plateau: l*(l+1)*C_l/(2*pi) ~ const for l < 30 (temperature)
2. First acoustic peak: l_1 ~ 220 (for Planck best-fit cosmology)
3. Peak ratios: constrain baryon density (odd/even peak ratio)
4. Normalization: A_s ~ 2.1e-9 (from Planck 2018 TT,TE,EE+lowE)
5. Spectral index: n_s ~ 0.965 (tilt from scale invariance)

Cross-check: If your C_l disagrees with Planck 2018 best-fit by > 3 sigma
for standard LCDM parameters, there is likely a bug (not new physics).
```

**Distance-redshift consistency:**

```
Comoving distance: d_C(z) = c * integral_0^z dz'/H(z')
Luminosity distance: d_L(z) = (1+z) * d_C(z)
Angular diameter distance: d_A(z) = d_C(z) / (1+z)

Etherington reciprocity: d_L = (1+z)^2 * d_A (EXACT, follows from photon conservation)

Verification:
1. Low-z limit: d_L ~ c*z/H_0 * (1 + (1-q_0)*z/2 + ...) where q_0 is deceleration parameter
2. Etherington relation must hold exactly — violation indicates a bug in distance calculation
3. d_A has a maximum at z ~ 1.6 for standard LCDM — if d_A is monotonically increasing, there is an error
```

**Gravitational wave energy balance:**

```
Quadrupole formula: P_GW = (G/5c^5) <I_ij^{(3)} I^{ij(3)}>

For a circular binary with masses m_1, m_2, separation R:
P_GW = (32/5) * (G^4/c^5) * m_1^2 * m_2^2 * (m_1+m_2) / R^5

Verification:
1. Energy radiated = orbital energy lost: dE_orb/dt = -P_GW
2. Chirp mass: M_c = (m_1*m_2)^{3/5} / (m_1+m_2)^{1/5} determines waveform frequency evolution
3. For inspiral: df/dt = (96/5) * pi^{8/3} * (G*M_c/c^3)^{5/3} * f^{11/3}
4. Peters formula for orbit decay: da/dt must be negative (orbit shrinks)
```

</cosmological_consistency>

## Worked Examples

### Gauge artifact in cosmological perturbation theory

**Scenario:** Computing the matter power spectrum P(k) from linear perturbation theory. The result depends on whether conformal Newtonian or synchronous gauge is used.

**The error:** The density contrast delta(k) is gauge-dependent at superhorizon scales (k*eta << 1). Computing delta in synchronous gauge and comparing directly with conformal Newtonian gives different results.

**Verification check:** Use gauge-invariant variables.

```python
import numpy as np

# The comoving curvature perturbation zeta is gauge-invariant
# zeta = -psi - H*delta*rho / rho'  (conformal Newtonian)
# zeta = -psi_sync + (1/3)*delta_sync / (1 + w)  (synchronous, for constant w)

# Compute zeta in both gauges
def zeta_newtonian(psi_N, H, delta_rho, rho_dot):
    return -psi_N - H * delta_rho / rho_dot

def zeta_synchronous(psi_S, delta_S, w):
    return -psi_S + delta_S / (3 * (1 + w))

# These must agree to machine precision for the same mode k
# If they disagree: gauge transformation was applied incorrectly
```

### Constraint violation growth in binary black hole merger

**Scenario:** Simulating binary black hole inspiral with BSSN formulation. The Hamiltonian constraint violation grows during the merger phase.

**Verification:** Monitor constraint at each time step. Constraint violation should peak at merger but NOT grow secularly post-merger.

```python
def check_constraint_growth(H_vs_time, t_merger, post_merger_window=100):
    """
    Verify constraint violation doesn't grow secularly after merger.
    """
    post_merger = [(t, H) for t, H in H_vs_time if t > t_merger]
    if len(post_merger) < post_merger_window:
        return "INSUFFICIENT_DATA"

    # Fit log|H| vs t in post-merger region
    # If slope > 0: constraint is growing (BAD — needs constraint damping)
    # If slope <= 0: constraint is decaying or constant (OK)
    ts = [t for t, _ in post_merger[:post_merger_window]]
    Hs = [abs(H) for _, H in post_merger[:post_merger_window]]
    log_Hs = [np.log(max(h, 1e-30)) for h in Hs]

    # Simple linear regression
    n = len(ts)
    t_mean = sum(ts) / n
    lH_mean = sum(log_Hs) / n
    slope = sum((t - t_mean) * (lH - lH_mean) for t, lH in zip(ts, log_Hs)) / \
            sum((t - t_mean)**2 for t in ts)

    status = "PASS" if slope <= 0 else "FAIL"
    print(f"Post-merger constraint growth rate: {slope:.4e} [{status}]")
    return slope <= 0
```
