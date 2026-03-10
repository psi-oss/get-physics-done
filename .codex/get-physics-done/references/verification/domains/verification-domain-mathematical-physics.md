---
load_when:
  - "mathematical physics verification"
  - "operator self-adjointness"
  - "spectral theorem"
  - "index theorem"
  - "modular invariance"
  - "anomaly cancellation"
  - "topological invariant"
  - "rigorous proof"
  - "conformal bootstrap"
  - "crossing symmetry"
  - "OPE"
  - "CFT"
tier: 2
context_cost: large
---

# Verification Domain — Mathematical Physics

Operator theory, spectral analysis, conformal bootstrap, index theorems, topological invariants, modular properties, and proof verification for rigorous mathematical physics.

**Load when:** Working on rigorous quantum mechanics, functional analysis applications in physics, topological field theory, integrable systems, conformal field theory, or any calculation requiring mathematical rigor.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `references/verification/domains/verification-domain-qft.md` — QFT (for anomalies, Ward identities, renormalization)
- `references/verification/domains/verification-domain-algebraic-qft.md` — Haag-Kastler nets, modular theory, and factor-type verification
- `references/verification/domains/verification-domain-condmat.md` — condensed matter (for topological phases, spectral functions)
- `references/protocols/conformal-bootstrap.md` — crossing equations, conformal blocks, SDPB, extremal functionals

---

<operator_theory>

## Operator Self-Adjointness and Spectral Theory

Self-adjoint operators have real spectrum, complete eigenfunctions, and well-defined spectral decomposition. Symmetric operators that are NOT self-adjoint can have complex eigenvalues and incomplete spectra.

**Self-adjointness verification:**

```
An operator A is self-adjoint if:
  1. A is symmetric: <Af, g> = <f, Ag> for all f, g in D(A)
  2. D(A) = D(A*) (domains match)

For bounded operators: symmetric = self-adjoint. No subtlety.
For unbounded operators (most quantum mechanics Hamiltonians): symmetric != self-adjoint.
  Must check domains carefully.

Common issues:
- Momentum operator p = -i*hbar*d/dx on [0,L]: self-adjoint ONLY with appropriate boundary conditions
  (periodic: self-adjoint; Dirichlet at both ends: symmetric but deficiency indices (1,1) -> self-adjoint extensions)
- Coulomb Hamiltonian: self-adjoint on D(H) = {psi: H*psi in L^2, psi in L^2} (Kato's theorem)

Verification:
1. COMPUTE: <Af, g> and <f, Ag> for test functions f, g. Must agree.
2. For boundary value problems: verify boundary terms vanish after integration by parts.
3. CHECK: Deficiency indices (n_+, n_-) = dim(ker(A* +/- i)). Self-adjoint iff n_+ = n_- = 0.
   If n_+ = n_- > 0: self-adjoint extensions exist (each parameterized by a unitary matrix).
```

**Spectral theorem applicability:**

```
The spectral theorem applies to self-adjoint (or normal) operators on Hilbert spaces:
  A = integral lambda dE(lambda)   (spectral decomposition)

Verification:
1. COMPUTE: All eigenvalues. For self-adjoint: must be REAL. Complex eigenvalue -> not self-adjoint.
2. COMPUTE: Eigenfunctions. Must form a complete set: sum_n |psi_n><psi_n| = I (resolution of identity).
   Test: expand a known function in eigenfunctions and verify convergence.
3. For continuous spectrum: verify generalized eigenfunctions satisfy delta-normalization.
```

</operator_theory>

<convergence_and_functional>

## Convergence, Sobolev Spaces, and Functional Analysis

**Convergence radius for perturbative series:**

```
Most perturbation series in QFT are asymptotic, not convergent.
The large-order behavior determines the convergence properties:
  a_n ~ n! * A^n * n^b   (factorial growth -> zero convergence radius)

Verification:
1. COMPUTE: Ratio a_{n+1}/a_n for successive coefficients. If it grows linearly with n: factorial divergence.
2. Borel summability: B(t) = sum a_n * t^n / n! may converge. If so, the series is Borel summable.
3. Check for renormalon singularities in B(t): poles at t = 2/beta_0, 4/beta_0, ... (IR renormalons)
   and t = -1/beta_0, -2/beta_0, ... (UV renormalons).
4. For quantum mechanics (not QFT): perturbation series MAY converge for bounded potentials (Kato-Rellich).
```

**Sobolev embedding verification:**

```
Sobolev embedding: W^{k,p}(R^d) embeds into C^m(R^d) when k - d/p > m.

Verification:
1. COMPUTE: k - d/p for your function space. If > 0: functions are continuous (almost everywhere).
   If > 1: functions have continuous derivatives. Important for: regularity of solutions to PDEs.
2. For numerical methods: Sobolev regularity determines convergence rate of approximation.
   A function in H^s (Sobolev space of order s) can be approximated to O(h^s) by finite elements of order s.
3. Trace theorem: W^{k,p}(Omega) restricts to W^{k-1/p,p}(partial Omega). Boundary values lose 1/p
   orders of regularity. If your boundary data is smoother than this allows: check assumptions.
```

</convergence_and_functional>

<index_and_topology>

## Index Theorems and Topological Invariants

**Atiyah-Singer index theorem:**

```
ind(D) = integral_M ch(V) * Td(M)

where ind(D) = dim(ker D) - dim(ker D*) is the analytic index, ch(V) is the Chern character
of the vector bundle, and Td(M) is the Todd class of the manifold.

Special cases:
- Gauss-Bonnet: ind = chi(M) = integral (R/4pi) dA  (2D, Euler characteristic)
- Hirzebruch signature: ind = sigma(M) = integral L(M)  (signature of intersection form)
- Dirac index: ind = integral A-hat(M) * ch(V)  (number of zero modes)

Verification:
1. COMPUTE: Both sides independently. Analytic index (count zero modes) must equal topological integral.
2. The index is an INTEGER. Non-integer result indicates: wrong manifold topology, computation error,
   or the operator is not Fredholm.
3. For gauge theories: the index counts the number of fermion zero modes in an instanton background.
   For SU(2): n_+ - n_- = k (instanton number). Verify.
```

**Modular invariance (CFT on torus):**

```
The partition function Z(tau) on a torus with modular parameter tau must be invariant under:
  T: tau -> tau + 1    (Dehn twist)
  S: tau -> -1/tau      (modular S-transformation)

These generate SL(2,Z). Physical partition functions must satisfy:
  Z(tau + 1) = Z(tau)
  Z(-1/tau) = Z(tau)

Verification:
1. COMPUTE: Z(tau) and Z(tau+1). Must agree to machine precision.
2. COMPUTE: Z(tau) and Z(-1/tau). Must agree.
3. For c = 1 (free boson): Z = |eta(tau)|^{-2} / sqrt(Im tau). Verify against known modular forms.
4. For minimal models: Z = sum |chi_r,s(tau)|^2 where chi are Virasoro characters. Verify ADE classification.
```

**Anomaly cancellation:**

```
For a consistent gauge theory, gauge anomalies must cancel:
  sum_fermions Tr[T^a {T^b, T^c}] = 0   (gauge anomaly cancellation)

For the Standard Model (per generation):
  SU(3)^3: 2 + (-1) + (-1) = 0     (from u_R, d_R, Q_L)
  SU(2)^2 U(1): 3*(1/6) + (-1/2) = 0  (from Q_L, L_L)
  U(1)^3: sum Y^3 = 0
  Gravitational: sum Y = 0

Verification:
1. COMPUTE: Each anomaly coefficient for the given fermion content. All must vanish.
2. Mixed anomalies (e.g., SU(3)^2 U(1)): also must vanish. Often forgotten.
3. For BSM models: verify ALL anomaly conditions (there are 6 for the SM gauge group).
   A single non-zero anomaly coefficient makes the theory inconsistent.
4. 't Hooft anomaly MATCHING: global anomalies must match between UV and IR descriptions.
```

</index_and_topology>

<cft_and_bootstrap>

## Conformal Bootstrap and CFT Verification

Crossing-based CFT calculations mix exact symmetry constraints with numerical approximation. The dominant failure mode is not a small algebraic slip, but claiming a truncated or unstable computation is a rigorous bootstrap result.

**Crossing equation setup:**

```
For a four-point bootstrap problem:
1. State the correlator basis explicitly: <phi phi phi phi>, mixed correlators, spinning correlators, etc.
2. Write the OPE channel decomposition and identify which operator representations appear in each channel.
3. Include the identity operator with its fixed normalization.
4. State the spacetime dimension d and the conformal block convention.

Verification:
- CHECK: the identity block is present with the expected coefficient.
- CHECK: crossing equations match the symmetry representations of the external operators.
- CHECK: scalar, current, and stress-tensor unitarity bounds use the correct d.
```

**Unitarity, protected operators, and sector bookkeeping:**

```
Verification:
1. Protected operators must appear at their exact dimensions:
   conserved current: Delta = d - 1
   stress tensor: Delta = d
2. Global-symmetry sectors must be assigned correctly:
   singlet vs traceless-symmetric vs antisymmetric sectors are not interchangeable.
3. For mixed correlators: every OPE coefficient and gap assumption must be tagged by sector.

Failure signals:
- stress tensor drifts away from Delta = d
- current appears in the wrong representation
- a bound changes when relabeling sectors that should be equivalent
```

**Numerical bootstrap stability:**

```
The key controls are derivative order Lambda, spin truncation, block precision, and SDP precision.

Verification:
1. COMPUTE bounds at multiple Lambda values. Allowed regions should tighten or stabilize monotonically.
2. CHECK that islands or kinks persist when solver precision is increased.
3. CHECK that exclusion results are reproducible under small changes in derivative basis or block tables.
4. RECORD the solver settings used for every quoted bound.
```

**OPE convergence and truncation discipline:**

```
Truncated OPE sums are diagnostics, not rigorous bootstrap outputs.

Verification:
1. If a finite operator sum is used, report it as an OPE truncation test, not as proof of crossing.
2. CHECK convergence in the conformal radius rho for the kinematic point used.
3. For extremal spectrum extraction: verify the recovered spectrum reproduces the crossing equations within the quoted numerical tolerance.
4. Distinguish clearly:
   - rigorous bound or exclusion region
   - approximate spectrum extraction
   - analytic large-spin or inversion-formula estimate
```

</cft_and_bootstrap>

<representation_completeness>

## Representation Theory Verification

**Completeness of representations:**

```
For a finite group G of order |G|:
  sum_R dim(R)^2 = |G|     (sum of squared dimensions equals group order)

For compact Lie groups:
  Peter-Weyl theorem: matrix elements of irreps form a complete orthonormal basis for L^2(G).

Verification:
1. COMPUTE: sum dim(R)^2 for all irreps found. If < |G|: irreps are missing.
2. For tensor product decompositions: dim(R1) * dim(R2) = sum dim(R_i). Must be exact.
3. Character table: verify orthogonality of rows AND columns. Both must hold independently.
4. Branching rules (G -> H): sum_{R_H} dim(R_H) = dim(R_G). Dimension preserved.
```

**Topological invariant computation:**

```
Chern number: C = (1/2pi) integral_BZ F d^2k   (must be integer)
Berry phase: gamma = oint A . dk   (modulo 2pi)
Winding number: W = (1/2pi) integral d(arg f)   (must be integer for closed contour)

Verification:
1. All topological invariants must be integers (or rational in specific fractional cases).
   Non-integer result = numerical error or topological obstruction.
2. Use gauge-invariant methods (Fukui-Hatsugai-Suzuki for Chern, Wilson loop for Z_2).
3. Verify bulk-boundary correspondence: boundary mode count = bulk topological invariant.
4. Under continuous deformation: invariant must not change unless gap closes.
```

</representation_completeness>

## Worked Examples

### Detecting non-self-adjoint operator in quantum mechanics

```python
import numpy as np

# The momentum operator p = -i d/dx on [0, L] with Dirichlet BCs psi(0) = psi(L) = 0
# This operator is symmetric but NOT self-adjoint (deficiency indices (1,1)).
# The eigenvalues of p are k_n = n*pi/L (real), but p has no complete set of eigenvectors
# that satisfy the BCs (sin functions are eigenfunctions of p^2, not p).

# Test: <f|p|g> vs <p*f|g> for test functions
L = 1.0
N = 1000
x = np.linspace(0, L, N+1)
dx = L / N

# f(x) = sin(pi*x/L), g(x) = sin(2*pi*x/L)
f = np.sin(np.pi * x / L)
g = np.sin(2 * np.pi * x / L)

# p*g = -i*dg/dx
dg = np.gradient(g, dx)
pg = -1j * dg

# <f|p|g>
fpg = np.trapz(f.conj() * pg, x)

# p*f = -i*df/dx
df = np.gradient(f, dx)
pf = -1j * df

# <p*f|g>
pfg = np.trapz(pf.conj() * g, x)

print(f"<f|p|g> = {fpg:.6f}")
print(f"<p*f|g> = {pfg:.6f}")
print(f"Difference: {abs(fpg - pfg):.6e}")
# For Dirichlet BCs: these SHOULD agree (p is symmetric) but the boundary terms
# from integration by parts contribute when the domain is extended.
# The key test is: does p have a COMPLETE set of eigenvectors?
# For Dirichlet BCs on [0,L]: eigenvectors of p^2 are complete (sin functions),
# but p itself has no eigenvectors satisfying the BCs (exp(ikx) doesn't vanish at boundaries).
```

### Anomaly cancellation check for BSM model

```python
# Check anomaly cancellation for a proposed BSM extension with an extra U(1)' gauge symmetry.
# Fermion content: SM + right-handed neutrino nu_R with U(1)' charges.

# SM fermion U(1)' charges (per generation):
charges = {
    'Q_L': 1/3,    # quark doublet (3 colors)
    'u_R': 1/3,    # up-type singlet (3 colors)
    'd_R': 1/3,    # down-type singlet (3 colors)
    'L_L': -1,     # lepton doublet
    'e_R': -1,     # charged lepton singlet
    'nu_R': -1,    # right-handed neutrino (NEW)
}

# [U(1)']^3 anomaly: sum of cubed charges (with multiplicity)
A_111 = (3*2 * charges['Q_L']**3 +   # 3 colors, 2 components
         3   * charges['u_R']**3 +     # 3 colors
         3   * charges['d_R']**3 +     # 3 colors
         2   * charges['L_L']**3 +     # 2 components
         1   * charges['e_R']**3 +
         1   * charges['nu_R']**3)

# [gravity]^2 [U(1)'] anomaly: sum of charges (with multiplicity)
A_grav = (3*2 * charges['Q_L'] +
          3   * charges['u_R'] +
          3   * charges['d_R'] +
          2   * charges['L_L'] +
          1   * charges['e_R'] +
          1   * charges['nu_R'])

print(f"[U(1)']^3 anomaly: {A_111:.4f} (must be 0)")
print(f"[grav]^2 [U(1)'] anomaly: {A_grav:.4f} (must be 0)")
# If either is non-zero: the model is anomalous and inconsistent
```
