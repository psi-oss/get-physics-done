---
load_when:
  - "perturbative calculation"
  - "loop integral"
  - "Feynman diagram"
  - "coupling expansion"
  - "Ward identity"
  - "symmetry factor"
  - "renormalization"
tier: 2
context_cost: medium
---

# Perturbation Theory Protocol

Perturbative calculations are the workhorse of theoretical physics. They are also the most common source of combinatorial, sign, and bookkeeping errors. This protocol applies to any expansion in a small parameter: coupling constants, 1/N, epsilon = 4-d, v/c, etc.

## Related Protocols

- See `renormalization-group.md` for RG improvement of large logarithms and resummation of leading-log series
- See `effective-field-theory.md` for matching calculations and power counting in EFT perturbation theory
- See `path-integrals.md` for saddle-point expansion as a perturbative method
- See `resummation.md` for extracting finite results from divergent perturbative series (Borel, Pade, conformal mapping)
- See `large-n-expansion.md` for 1/N expansion as a non-perturbative reorganization of the coupling expansion

## Organization by Order

- **Enumerate all contributions at each order.** At O(g^n), list every term that contributes. For Feynman diagrams: draw or list every diagram at the given loop order. Do not rely on "the important diagrams" --- include all of them.
- **Track the expansion parameter explicitly.** Write every term with its explicit power of g (or 1/N, or epsilon, etc.). Never absorb it into a coefficient without annotation.
- **Never mix orders.** If working to O(g^2), include ALL O(g^2) terms. Do not include some O(g^3) terms "because they're easy" while dropping others.

## Combinatorial and Symmetry Factors

- **Derive every symmetry factor from the Feynman rules.** Do not assert "the symmetry factor is 1/2" without showing the derivation.
- For each diagram:
  1. Write the number of ways to connect the vertices (counting argument)
  2. Divide by the symmetry factor of the diagram (automorphisms)
  3. Verify against the generating functional derivation if possible
- **Common sources of factor errors:**
  - 1/n! from the Taylor expansion of exp(-S_int)
  - 1/n! from identical particles
  - Factor of 2 from identical vertices
  - Factor of 2 from real vs complex fields
  - Combinatorial factor from Wick contractions

## Ward Identities and Gauge Invariance

- **After computing at each order: verify Ward identities.**
  - QED: q_mu \* Gamma^mu(p, p+q) = S^{-1}(p+q) - S^{-1}(p) (Ward-Takahashi)
  - QCD: Slavnov-Taylor identities
  - General: conservation of the Noether current associated with the gauge symmetry
- If a Ward identity fails at a given order: the calculation has an error. Do not proceed. Common causes:
  - Missing diagram at that order
  - Wrong routing of external momentum
  - Inconsistent regularization (cutoff breaks gauge invariance; use dimensional reg)

## Gauge Invariance of Physical Observables

- **At each order: verify that physical observables are gauge-parameter independent.**
  - In covariant gauges with parameter xi: verify d(sigma)/d(xi) = 0 for cross sections
  - Compute in two different gauges (e.g., Feynman gauge xi=1 and Landau gauge xi=0) and verify agreement
- If gauge dependence found in a physical observable: missing diagrams or wrong Feynman rules. Do not proceed.

## UV and IR Divergence Structure

- **Before computing: perform power counting.** For each diagram, determine the superficial degree of divergence D = d\*L - sum(propagator powers) + sum(vertex dimensions). This tells you what divergence to expect.
- **After computing: verify the divergence structure matches power counting.**
  - Quadratic divergence (D=2) should give Lambda^2 or 1/epsilon terms
  - Logarithmic divergence (D=0) should give log(Lambda) or 1/epsilon terms
  - If the actual divergence is WORSE than power counting predicts: error in calculation
  - If BETTER (e.g., finite when D>0): a symmetry (gauge invariance, chiral symmetry) is protecting the result. Identify which symmetry.
- **Track IR divergences separately from UV.** IR divergences in intermediate steps may cancel in physical observables (e.g., Bloch-Nordsieck cancellation in QED). Verify the cancellation explicitly.

## Renormalization

- **State the renormalization scheme.** MS-bar, on-shell, momentum subtraction, etc.
- **Verify counterterms have the form of existing Lagrangian terms.** If a counterterm appears that is not in the original Lagrangian, either: (a) the theory is non-renormalizable at this order, or (b) there is an error.
- **Verify the renormalization group equation.** Physical quantities must satisfy mu \* d(Gamma)/d(mu) = 0. The running of couplings must be consistent with the beta function.
- **Check scheme independence of physical observables.** The pole mass, the S-matrix, and cross sections must be scheme-independent. Running couplings and anomalous dimensions are scheme-dependent but their physical predictions are not.

## Concrete Example: Missing Diagram Changes the Sign

**Problem:** Compute the one-loop correction to the photon propagator in QED (vacuum polarization).

**Wrong approach (common LLM error):** Draw only the fermion bubble diagram and compute:

Pi^{mu nu}(q) = (-1) * (ie)^2 * integral d^d k / (2pi)^d * Tr[gamma^mu S(k) gamma^nu S(k-q)]

LLMs frequently get the overall sign wrong by forgetting the (-1) from the fermion loop or by incorrect Wick rotation sign.

**Correct approach following this protocol:**

1. **Enumerate all contributions at O(e^2):** There is exactly ONE diagram: the fermion bubble. The photon self-energy has no tadpole at this order (by Furry's theorem: odd numbers of photon vertices vanish in QED).

2. **Track signs explicitly:**
   - Factor of (-1) from the closed fermion loop (Grassmann trace)
   - Factor of (ie)^2 = -e^2 from two QED vertices
   - Combined overall sign: (-1) * (-e^2) = +e^2

3. **Compute with Lorentz decomposition:**
   ```
   Pi^{mu nu}(q) = (q^mu q^nu - g^{mu nu} q^2) * Pi(q^2)
   ```
   This form is REQUIRED by the Ward identity (gauge invariance): q_mu Pi^{mu nu} = 0.

4. **Ward identity checkpoint:** After computing, verify q_mu Pi^{mu nu}(q) = 0 explicitly. If it fails, there is a calculational error. Do NOT proceed.

5. **Power counting checkpoint:** D = 4 - 2*1 = 2 (quadratically divergent by naive counting). But gauge invariance reduces it to logarithmic: the q^mu q^nu structure ensures the quadratic divergence cancels, leaving only log(Lambda^2/m^2) terms.

6. **Known result cross-check:**
   ```
   Pi(q^2) = -(e^2 / (12 pi^2)) * [1/epsilon - gamma + log(4pi) - integral_0^1 dx * 6x(1-x) * log(m^2 - x(1-x)q^2)]
   ```
   In the limit q^2 >> m^2: Pi(q^2) -> -(e^2/(12pi^2)) * log(-q^2/m^2). This gives the running coupling alpha(q^2) = alpha / (1 - alpha/(3pi) * log(q^2/m^2)), which is the correct one-loop QED beta function.

**The typical LLM error** is getting the overall sign of Pi(q^2) wrong (positive instead of negative), which would make the coupling DECREASE with energy (asymptotic freedom). QED is NOT asymptotically free -- the coupling INCREASES with energy. This sign error changes the physics qualitatively.

## Worked Example: Electron Self-Energy at One Loop in QED

**Problem:** Compute the one-loop electron self-energy Sigma(p) in QED using dimensional regularization in MS-bar, and extract the electron mass renormalization and wavefunction renormalization. This targets the LLM error class of incorrect Dirac algebra (wrong trace identities, dropped gamma matrix terms, incorrect Feynman parameterization).

### Step 1: Identify All Diagrams at O(alpha)

At one loop, there is exactly one diagram: the electron emits and reabsorbs a virtual photon. The self-energy is:

```
-i Sigma(p) = (ie)^2 integral d^d k / (2pi)^d * gamma^mu * i(p-slash - k-slash + m) / ((p-k)^2 - m^2) * (-i g_{mu nu}) / (k^2) * gamma^nu
```

In Feynman gauge (xi = 1). The (ie)^2 = -e^2 from the two QED vertices.

### Step 2: Simplify Dirac Structure

Contract gamma^mu ... gamma_mu using the d-dimensional identity:

```
gamma^mu gamma^alpha gamma_mu = -(d-2) gamma^alpha = -(2-2epsilon) gamma^alpha
```

where d = 4 - 2*epsilon. This gives:

```
Sigma(p) = -e^2 integral d^d k / (2pi)^d * [-(2-2epsilon)(p-slash - k-slash) + d*m] / [(p-k)^2 - m^2] * 1/k^2
```

**Checkpoint:** The numerator must have exactly two Dirac structures: a term proportional to p-slash and a term proportional to m (by Lorentz covariance). Write Sigma(p) = A(p^2) p-slash + B(p^2) m, where A and B are scalar functions.

### Step 3: Feynman Parameterization and Momentum Integration

Introduce Feynman parameter x:

```
1/[k^2 * ((p-k)^2 - m^2)] = integral_0^1 dx / [l^2 - Delta]^2
```

where l = k - x*p and Delta = -x(1-x)p^2 + x*m^2.

After shifting to l and performing the d-dimensional momentum integral:

```
A(p^2) = -(alpha/(4pi)) * (2/epsilon - gamma + ln(4pi)) * 1 + finite terms
B(p^2) = -(alpha/(4pi)) * (2/epsilon - gamma + ln(4pi)) * 4 + finite terms
```

In MS-bar, subtract the (2/epsilon - gamma + ln(4pi)) poles:

```
Sigma_R(p) = (alpha/(4pi)) integral_0^1 dx [(2-2epsilon)(1-x) p-slash - (4-2epsilon) m] * ln(Delta/mu^2)
```

### Step 4: Extract Renormalization Constants

The mass renormalization:

```
delta_m / m = -B(m^2) = (3 alpha)/(4pi) * [1/epsilon + finite]
```

The wavefunction renormalization:

```
Z_2 - 1 = -A(m^2) - 2m^2 * A'(m^2) = -(alpha/(4pi)) * [1/epsilon + finite]
```

### Verification

1. **Gauge invariance check:** The self-energy is gauge-dependent (it depends on xi). However, the pole mass m_pole = m + delta_m is gauge-independent. Verify by computing in Landau gauge (xi = 0): the pole position must be the same.

2. **Ward identity check:** The QED Ward identity Z_1 = Z_2 (vertex renormalization = wavefunction renormalization) must hold. If Z_1 differs from Z_2, there is an error in the vertex calculation or the self-energy. At one loop: delta_Z_1 = delta_Z_2 = -(alpha/(4pi epsilon)).

3. **Dimensional check:** [Sigma] = [mass]. The self-energy has the form A * p-slash + B * m, where A is dimensionless and B is dimensionless. Correct: [A * p-slash] = [mass] and [B * m] = [mass].

4. **Known limit — massless electron:** Setting m = 0, the self-energy reduces to Sigma(p) = A(p^2) * p-slash with A proportional to alpha * ln(-p^2/mu^2). The mass counterterm vanishes (chiral symmetry protects the massless limit). If a mass term is generated at m = 0, chiral symmetry is broken — this signals an error.

5. **Numerical cross-check:** The anomalous dimension gamma_m = mu * d(ln m)/d(mu) = 3*alpha/(2*pi) at one loop. For alpha = 1/137: gamma_m = 0.00348. The electron mass runs very slowly. If gamma_m is O(1), there is a factor error.

## Worked Example: Stark Effect in Hydrogen n=2 — Degenerate Perturbation Theory

**Problem:** Compute the first-order energy splitting of the hydrogen n=2 level in a uniform electric field E along z (linear Stark effect). The n=2 level is 4-fold degenerate: |2,0,0>, |2,1,0>, |2,1,1>, |2,1,-1>. This targets the most common LLM error in quantum perturbation theory: applying non-degenerate formulas to degenerate states, which produces divergent (1/0) energy corrections instead of the correct level splitting.

### The Wrong Way (Non-Degenerate Formula Applied to Degenerate States)

The non-degenerate first-order correction is:

```
E_n^(1) = <n|H'|n>
```

For H' = eEz = eEr cos(theta), the diagonal matrix elements in the |n,l,m> basis are:

```
<2,0,0|eEr cos(theta)|2,0,0> = 0  (parity)
<2,1,0|eEr cos(theta)|2,1,0> = 0  (parity)
<2,1,1|eEr cos(theta)|2,1,1> = 0  (parity)
<2,1,-1|eEr cos(theta)|2,1,-1> = 0 (parity)
```

All diagonal elements vanish by parity (H' is odd under r -> -r, while |n,l,m|^2 is even). A common LLM conclusion: "The first-order Stark effect vanishes for hydrogen n=2."

**This is wrong.** The non-degenerate formula E_n^(1) = <n|H'|n> is invalid when states are degenerate. The second-order correction would give:

```
E_n^(2) = sum_{m != n} |<m|H'|n>|^2 / (E_n - E_m)
```

But the sum includes other n=2 states with E_n - E_m = 0, producing a divergence. This divergence is the signature that degenerate perturbation theory is required.

### Step 1: Identify the Degenerate Subspace

The n=2 hydrogen level has 4 degenerate states: {|2,0,0>, |2,1,0>, |2,1,1>, |2,1,-1>} all at energy E_2 = -13.6/4 = -3.4 eV.

The degeneracy is "accidental" — it arises from the hidden SO(4) symmetry of the Coulomb potential, not just angular momentum. The electric field breaks this symmetry.

### Step 2: Construct the Perturbation Matrix in the Degenerate Subspace

Compute all 4x4 matrix elements of H' = eEr cos(theta):

```
V_{ij} = <2,l_i,m_i|eEr cos(theta)|2,l_j,m_j>
```

**Selection rules first:** H' = eEr cos(theta) = eEr Y_1^0 * sqrt(4pi/3). The angular integration gives:

- Delta_m = 0 (cos(theta) = Y_1^0 does not change m)
- Delta_l = +/-1 (parity selection rule: <l|Y_1^0|l'> vanishes unless l' = l +/- 1)

These rules eliminate most matrix elements:

| | |2,0,0> | |2,1,0> | |2,1,1> | |2,1,-1> |
|---|--------|---------|---------|----------|
| <2,0,0| | 0 | V | 0 | 0 |
| <2,1,0| | V* | 0 | 0 | 0 |
| <2,1,1| | 0 | 0 | 0 | 0 |
| <2,1,-1| | 0 | 0 | 0 | 0 |

Only one independent off-diagonal element survives: V = <2,0,0|eEr cos(theta)|2,1,0>.

### Step 3: Compute the Matrix Element

The radial wavefunctions for n=2:

```
R_{20}(r) = (1/2)(1/a_0)^{3/2} (2 - r/a_0) exp(-r/(2a_0))
R_{21}(r) = (1/(2 sqrt(6)))(1/a_0)^{3/2} (r/a_0) exp(-r/(2a_0))
```

The angular integral:

```
integral Y_0^0 cos(theta) Y_1^0 d Omega = integral (1/sqrt(4pi)) * cos(theta) * sqrt(3/(4pi)) cos(theta) sin(theta) d theta d phi
= sqrt(3)/(4pi) * 2pi * integral_0^pi cos^2(theta) sin(theta) d theta = sqrt(3)/(4pi) * 2pi * 2/3 = 1/sqrt(3)
```

The radial integral:

```
integral_0^inf R_{20}(r) * r * R_{21}(r) * r^2 dr = -3 sqrt(6) a_0
```

Combining: V = <2,0,0|eEr cos(theta)|2,1,0> = -3eEa_0.

### Step 4: Diagonalize the Perturbation Matrix

The 4x4 matrix is block diagonal: the |2,1,+/-1> states are decoupled (zero matrix elements). The 2x2 block involving |2,0,0> and |2,1,0> is:

```
H'_{2x2} = ( 0      -3eEa_0 )
            ( -3eEa_0    0   )
```

Eigenvalues: E^(1) = +/- 3eEa_0.

Eigenstates:

```
|+> = (1/sqrt(2))(|2,0,0> - |2,1,0>)   with E^(1) = +3eEa_0
|-> = (1/sqrt(2))(|2,0,0> + |2,1,0>)   with E^(1) = -3eEa_0
```

The other two states |2,1,+/-1> remain at E^(1) = 0.

### Step 5: Physical Result

The n=2 level splits into three sub-levels:

```
E_2 + 3eEa_0      (1 state: |+>)
E_2                (2 states: |2,1,+1>, |2,1,-1>)
E_2 - 3eEa_0      (1 state: |->)
```

The splitting is LINEAR in E — this is the linear Stark effect, unique to hydrogen (the accidental l-degeneracy allows l=0 and l=1 to mix). For non-hydrogenic atoms (no l-degeneracy), the first-order Stark effect vanishes and the leading effect is quadratic in E.

Numerically: 3eEa_0 = 3 * (1.6e-19 C) * E * (5.29e-11 m) = 2.54e-29 * E [J] = 1.59e-10 * E [eV/(V/m)]. For E = 10^6 V/m (laboratory field): splitting = 0.16 meV = 38 GHz.

### Verification

1. **Parity check on eigenstates.** The perturbation mixes |2,0,0> (even parity) with |2,1,0> (odd parity). The eigenstates |+/-> have no definite parity — this is correct because the electric field breaks parity symmetry. If the eigenstates had definite parity, the mixing would be zero and there would be no linear Stark effect.

2. **Trace check.** The sum of eigenvalues must equal the trace of the perturbation matrix: (+3eEa_0) + 0 + 0 + (-3eEa_0) = 0 = Tr(H'). The total energy shift summed over all states is zero at first order — the center of gravity of the level is unchanged.

3. **Selection rule consistency.** The |2,1,+/-1> states are unshifted because Delta_m = 0 for the electric field along z. If the field were along x, the m = +/-1 states would mix via the m-changing matrix elements. The physics must not depend on the choice of axis — rotating the field direction and repeating must give the same splitting magnitude.

4. **Comparison with non-degenerate second order.** For states outside the n=2 manifold, the second-order Stark effect gives E^(2) ~ -alpha_d * E^2 / 2 where alpha_d is the polarizability. For n=2 hydrogen: alpha_d = -2 * sum_{n'!=2} |<n'|eEz|2>|^2 / (E_{n'} - E_2). This gives alpha_d ~ 120 a_0^3 for the |2,1,+/-1> states. The quadratic shift should be much smaller than the linear splitting at laboratory field strengths: E^(2) / E^(1) ~ alpha_d * E / (6 a_0) ~ 10^{-4} for E = 10^6 V/m.

5. **Dimensional analysis.** The splitting 3eEa_0 has dimensions of [charge] * [electric field] * [length] = [energy]. Correct. The Bohr radius a_0 = hbar^2 / (m_e e^2) sets the natural scale — any perturbative correction to hydrogen energy levels must involve a_0 to the appropriate power.
