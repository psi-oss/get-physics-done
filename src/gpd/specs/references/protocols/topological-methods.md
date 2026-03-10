---
load_when:
  - "topological invariant"
  - "Chern number"
  - "Berry phase"
  - "Berry curvature"
  - "Z2 invariant"
  - "edge state"
  - "bulk-boundary correspondence"
  - "topological insulator"
tier: 2
context_cost: high
---

# Topological Methods Protocol

Topological invariants characterize phases of matter that cannot be distinguished by local order parameters. Errors arise from gauge singularities in Berry connection computation, incorrect discretization of the Brillouin zone, and confusion between different topological classifications. This protocol ensures correct computation and interpretation of topological quantities.

## Related Protocols
- `lattice-gauge-theory.md` — Topological charge computation on the lattice
- `symmetry-analysis.md` — Symmetry classification underlying topological phases
- `generalized-symmetries.md` — Topological defects, higher-form symmetries, and beyond-Landau diagnostics
- `tensor-networks.md` — Entanglement-based topology diagnostics
- `numerical-computation.md` — Berry phase and Chern number computation

## Step 1: Identify the Topological Structure

1. **Classify the symmetry.** Determine which symmetries the system respects: time-reversal (T), particle-hole (C), chiral (S = TC), and any additional spatial symmetries. This determines the symmetry class (ten-fold way: A, AIII, AI, BDI, D, DIII, AII, CII, C, CI).
2. **Determine the spatial dimension.** The topological classification depends on both symmetry class and dimension d. Consult the periodic table of topological insulators/superconductors to determine which topological invariant is relevant (Z, Z_2, or trivial).
3. **Identify the relevant topological invariant:**
   - Class A, d=2: Chern number (Z) — integer quantum Hall effect
   - Class AII, d=2: Z_2 invariant — quantum spin Hall effect
   - Class AII, d=3: Z_2 invariant — 3D topological insulator
   - Class D, d=2: Chern number (Z) — chiral p-wave superconductor
   - Class DIII, d=1: Z_2 — Kitaev chain
4. **Check for additional crystalline symmetries.** Topological crystalline insulators require space group analysis beyond the ten-fold way. Mirror Chern numbers, glide symmetries, and higher-order topological invariants may apply.

## Step 2: Berry Phase Calculation

1. **Berry connection:** A_n(k) = i <u_n(k)| nabla_k |u_n(k)> where |u_n(k)> is the periodic part of the Bloch function for band n. This is a gauge-dependent quantity (changes under |u_n(k)> -> e^{i phi(k)} |u_n(k)>).
2. **Berry phase around a closed loop:**
   gamma_n = oint A_n(k) . dk (mod 2pi)
   This is gauge-invariant. For a 1D system, the Berry phase across the Brillouin zone gives the Zak phase, related to polarization.
3. **Numerical Berry phase (discrete formula):**
   gamma = -Im ln prod_{i=0}^{N-1} <u(k_i)| u(k_{i+1})>
   where k_N = k_0 (closed loop). This is gauge-invariant by construction and avoids the need to fix a smooth gauge. Verify convergence with number of k-points N.
4. **Gauge singularities.** The Berry connection A_n(k) can be singular even when the Berry curvature is smooth (analogous to the Dirac string for a magnetic monopole). The discrete formula avoids this issue, but analytical calculations must track gauge singularities.

## Step 3: Chern Number Computation

1. **Berry curvature:** F_n(k) = nabla_k x A_n(k) (in 2D: F_n = dA_x/dk_y - dA_y/dk_x). This is gauge-invariant and physically observable (anomalous velocity contribution).
2. **Chern number:**
   C_n = (1 / 2pi) integral_BZ F_n(k) d^2k
   This must be an integer. Non-integer result indicates: insufficient k-mesh, numerical errors, or band crossings within the integration region.
3. **Numerical methods:**
   - **Direct integration:** Compute F_n on a k-grid and integrate numerically. Requires a smooth gauge, which is difficult to obtain globally. Use the Fukui-Hatsugai-Suzuki method instead.
   - **Fukui-Hatsugai-Suzuki (lattice field strength):** Compute the Berry phase around each plaquette of a k-mesh. The Chern number is the sum over all plaquettes divided by 2pi. This is gauge-invariant, gives exactly integer results (up to machine precision), and requires no smooth gauge.
   - **Wilson loop method:** Compute the Wilson loop W(k_y) = prod_{k_x} <u(k_x, k_y)|u(k_x + dk_x, k_y)> as a function of k_y. The winding of the Wilson loop eigenvalues gives the Chern number.
4. **Convergence:** The Chern number must be exactly integer. Check: increase k-mesh density until the result is integer to within 10^{-6}. If it doesn't converge to an integer, there is a band crossing or the bands are not isolated.

## Step 4: Z_2 Invariant

1. **Time-reversal invariant systems.** For systems with T^2 = -1 (Kramers degeneracy), the Chern number is always zero, but a Z_2 invariant distinguishes topological from trivial.
2. **Fu-Kane formula (2D):**
   (-1)^nu = prod_{i=1}^{4} Pf[w(Gamma_i)] / sqrt(det[w(Gamma_i)])
   where w(Gamma_i) is the sewing matrix at the four time-reversal-invariant momenta (TRIM) Gamma_i, and Pf denotes the Pfaffian. Each factor is +/- 1.
3. **Alternative: Wilson loop method.** Compute the Wilson loop spectrum as a function of one momentum component. The Z_2 invariant is determined by the number of crossings of the Wilson loop eigenvalues at the TRIM points (even = trivial, odd = topological).
4. **3D Z_2 invariants.** There are four Z_2 indices (nu_0; nu_1, nu_2, nu_3). nu_0 is the strong topological invariant; if nu_0 = 1, the surface states are robust against disorder. The weak indices nu_1, nu_2, nu_3 indicate stacking of 2D topological insulators.

### Higher-Order Topology
- Corner and hinge states: d-dimensional system with (d-n)-dimensional boundary states (n > 1)
- Nested Wilson loop diagnostic: compute Wilson loop, then compute Wilson loop of the Wilson loop eigenvalues
- Quantized multipole moments (quadrupole, octupole) as topological invariants
- Filling anomaly: mismatch between bulk band filling and boundary charge
- Key verification: check that corner/hinge states are robust against symmetry-preserving perturbations

### Topological Semimetals
- Weyl semimetals: pairs of non-degenerate band touchings with opposite chirality (Nielsen-Ninomiya theorem)
- Dirac semimetals: 4-fold degenerate points, require additional symmetry protection
- Nodal lines: 1D band crossings in 3D BZ, characterized by Berry phase around encircling loop
- Fermi arcs: open surface states connecting projections of bulk Weyl nodes
- Verification: chirality must sum to zero over all nodes (fermion doubling)

## Step 5: Bulk-Boundary Correspondence

1. **Principle:** A non-trivial bulk topological invariant implies protected boundary (edge/surface) states. The number of boundary modes is determined by the bulk invariant.
   - Chern number C: |C| chiral edge modes crossing the gap
   - Z_2 = 1: odd number of Dirac cones on the surface (Kramers pairs)
   - Winding number W: |W| zero-energy modes at domain walls
2. **Numerical verification:** Compute the spectrum of a slab/ribbon geometry (periodic in d-1 directions, open in one). Edge states appear as in-gap states localized near the boundaries. Count them and compare with the bulk invariant.
3. **Robustness.** Topological edge states are protected by the bulk gap and the relevant symmetries. Add disorder and verify the edge states persist (no gap opening) as long as the disorder strength is below the bulk gap.
4. **Corner and hinge states (higher-order TI).** Second-order topological insulators have gapped surfaces but protected corner/hinge states. The bulk-boundary correspondence generalizes: d-dimensional bulk invariant protects (d-n)-dimensional boundary modes for n-th order TI.

## Step 6: Numerical Methods for Topological Invariants

1. **Twisted boundary conditions.** Compute the ground state energy E(theta_x, theta_y) as a function of twist angles theta. The Chern number is the integral of the Berry curvature in (theta_x, theta_y) space. This works for interacting systems where single-particle Chern numbers are not defined.
2. **Entanglement spectrum.** The eigenvalues of the reduced density matrix (entanglement spectrum) reflect the edge spectrum via the Li-Haldane conjecture. A degenerate entanglement spectrum indicates topological order. This is accessible via DMRG/MPS without computing edge states directly.
3. **Many-body Chern number.** For interacting systems, the single-particle Berry phase is not defined. Use the many-body Berry phase (Niu-Thouless-Wu formula) or the Hall conductance via the Kubo formula: sigma_xy = (e^2/h) C.
4. **Disorder averaging.** For disordered systems, compute the topological invariant for many disorder realizations and check that it remains quantized. The invariant should be robust as long as the bulk mobility gap persists.

### Interacting Topological Order
- Fractional quantum Hall: ground state degeneracy on torus = number of anyon types
- Topological entanglement entropy: S = αL - γ, where γ = ln(D) with D the total quantum dimension
- Modular S and T matrices: encode anyon braiding and fusion statistics
- Interaction effects on free-fermion classification: some Z invariants reduce to Z_n
- Spin liquids: diagnosed via entanglement entropy, Wilson loop expectation values, or spectral signatures

## Common Pitfalls

- **Gauge singularities in Berry connection.** The Berry connection A(k) has Dirac strings that can produce spurious contributions to integrals. Use gauge-invariant methods (Fukui-Hatsugai-Suzuki, Wilson loops) to avoid this.
- **Insufficient Brillouin zone sampling.** The Chern number is a topological quantity and should be exactly integer, but numerical integration on a coarse k-mesh can give non-integer results. Increase k-mesh until the result is integer to high precision.
- **Band crossings.** The Chern number is defined for isolated bands. If bands touch or cross within the integration region, the Chern number is not well-defined for individual bands — compute it for the composite set of bands below the gap.
- **Wrong TRIM identification.** The Z_2 invariant depends on the Pfaffian at TRIM points. Using the wrong TRIM (or missing some) gives the wrong invariant. For a lattice with basis vectors a_1, a_2: TRIM are at k = (n_1 G_1 + n_2 G_2)/2 with n_i = 0, 1.
- **Ignoring spin-orbit coupling.** Spin-orbit coupling is essential for Z_2 topological insulators. Without SOC, the Z_2 invariant is undefined for systems with T^2 = +1 instead of T^2 = -1.
- **Confusing Chern number sign with edge chirality.** The sign of the Chern number determines the chirality of edge modes. Different conventions for the Berry curvature sign can flip the Chern number sign. Be consistent.

## Verification Checklist

- [ ] Topological invariant is quantized: Chern number exactly integer, Z_2 is 0 or 1
- [ ] Convergence: result independent of k-mesh density (beyond some threshold)
- [ ] Bulk-boundary correspondence: edge mode count matches bulk invariant
- [ ] Symmetry class correct: symmetry analysis consistent with ten-fold way classification
- [ ] Gap closure: topological phase transition accompanied by bulk gap closing
- [ ] Robustness: invariant stable under small perturbations that preserve the symmetry
- [ ] Consistency: multiple methods (Wilson loop, Fukui-Hatsugai-Suzuki, entanglement spectrum) agree

## Worked Example: Z_2 Invariant of the Kane-Mele Model via Wilson Loop

**Problem:** Compute the Z_2 topological invariant for the Kane-Mele model (graphene with spin-orbit coupling) and verify it via the bulk-boundary correspondence. This targets the LLM error class of computing a Chern number instead of a Z_2 invariant for time-reversal-invariant systems — the Chern number is always zero by Kramers' theorem, but the Z_2 invariant distinguishes the quantum spin Hall insulator from a trivial band insulator.

### Setup

The Kane-Mele model on a honeycomb lattice:
```
H = t sum_{<ij>} c^dag_i c_j + i lambda_SO sum_{<<ij>>} nu_ij c^dag_i s_z c_j + i lambda_R sum_{<ij>} c^dag_i (s x d_ij)_z c_j + lambda_v sum_i xi_i c^dag_i c_i
```

Parameters: t = 1 (nearest-neighbor hopping), lambda_SO = 0.06t (spin-orbit), lambda_R = 0.05t (Rashba), lambda_v = 0.1t (staggered sublattice potential). nu_ij = +1 (-1) for counterclockwise (clockwise) next-nearest-neighbor hopping. xi_i = +1 (-1) for A (B) sublattice.

Time-reversal symmetry: T = i s_y K with T^2 = -1 (Kramers degeneracy). This guarantees the Chern number C = 0 for each pair of Kramers-degenerate bands.

### Step 1: Band Structure

Diagonalize H(k) on a 100x100 k-mesh. The system has 4 bands (2 sublattices x 2 spins). At the K and K' points, spin-orbit opens a gap:
```
Gap at K: Delta = 6*sqrt(3)*lambda_SO - 2*lambda_v = 6*sqrt(3)*0.06 - 0.2 = 0.424t
```

**Checkpoint:** The gap must be positive for the topological phase to exist. If lambda_v > 3*sqrt(3)*lambda_SO, the gap closes and the system becomes a trivial insulator. With our parameters: 3*sqrt(3)*0.06 = 0.312 > lambda_v = 0.1. Topological phase confirmed.

### Step 2: Chern Number (Should Be Zero)

Compute the Chern number for the lower two occupied bands using the Fukui-Hatsugai-Suzuki method on a 50x50 k-mesh:
```
C = (1/2pi) sum_plaquettes Im[ln(U_1 U_2 U_1^{-1} U_2^{-1})]
```

Result: C = 0 (to machine precision).

**Checkpoint:** This MUST be zero. Time reversal pairs bands such that the Berry curvature satisfies F(k) = -F(-k), giving zero total Chern number. If C != 0, either the Hamiltonian breaks time reversal or the calculation is wrong.

### Step 3: Z_2 Invariant via Wilson Loop

Compute the Wilson loop W(k_y) = prod_{k_x} P(k_x, k_y) where P is the projection onto occupied bands, as a function of k_y across half the Brillouin zone (0 to pi/a, using time-reversal to relate the other half):

```
theta_1(k_y), theta_2(k_y) = eigenvalues of W(k_y) / (2pi)    [modulo 1]
```

The Wilson loop eigenvalues theta_1, theta_2 are Kramers-paired at the TRIM points k_y = 0 and k_y = pi/a. Between these TRIM points, the eigenvalues evolve.

**The Z_2 invariant** counts the number of times the Wilson loop eigenvalues cross each other between TRIM points (mod 2):
- Even crossings: nu = 0 (trivial)
- Odd crossings: nu = 1 (topological)

For our parameters: the Wilson loop eigenvalues cross ONCE between k_y = 0 and k_y = pi. Therefore nu = 1 (topological insulator).

### Step 4: Verify Bulk-Boundary Correspondence

Compute the band structure on a zigzag nanoribbon (periodic in x, open in y, width W = 40 unit cells). Count the number of edge states crossing the bulk gap:

```
| k_x region | Edge states crossing gap |
|------------|------------------------|
| K point    | 1 pair (left-moving on top edge, right-moving on bottom) |
| K' point   | 1 pair (right-moving on top edge, left-moving on bottom) |
```

Total: 1 Kramers pair of edge states per edge (odd number), consistent with Z_2 = 1.

**Checkpoint:** For Z_2 = 1, there must be an ODD number of Kramers pairs crossing the gap at each edge. These edge states are protected by time reversal — they cannot be gapped by any perturbation that preserves T. Verify by adding T-preserving disorder (random on-site potentials): edge states persist. Adding a magnetic field (breaks T): gap opens at the Dirac crossing point of the edge states.

### Verification

1. **Kramers degeneracy:** At all TRIM points (Gamma, M, K, K'), every energy level is exactly doubly degenerate. Verify to machine precision.

2. **lambda_R = 0 limit:** Without Rashba coupling, each spin sector has a well-defined Chern number: C_up = +1, C_down = -1. The spin Chern number C_s = (C_up - C_down)/2 = 1. This is equivalent to Z_2 = 1 when spin conservation holds.

3. **lambda_SO -> 0 limit:** The gap closes at lambda_SO = lambda_v / (3 sqrt(3)) = 0.0192t. Below this, Z_2 = 0 (trivial). The gap closing signals the topological phase transition. Verify: the gap passes through zero at this parameter value.

4. **Finite-size scaling:** The edge state velocity v_edge = d E / d k at the Dirac point should be independent of ribbon width for W > penetration depth xi ~ hbar v / Delta. Verify convergence.

5. **Spin texture:** In the topological phase, edge states have locked spin-momentum texture: right-movers are spin-up, left-movers are spin-down (or vice versa, depending on the edge). This spin-momentum locking is the physical signature of the quantum spin Hall effect.

**The typical LLM error** computes the total Chern number (which is zero by symmetry), declares the system "trivial," and misses the Z_2 topological invariant entirely. Another common error is computing spin Chern numbers C_up, C_down when Rashba coupling is present — spin is not conserved, so individual spin Chern numbers are not well-defined, and only Z_2 (computed via Wilson loops or the Fu-Kane formula) is meaningful.

## Concrete Example: Non-Integer Chern Number From Coarse k-Mesh

**Problem:** Compute the Chern number for the Haldane model on a honeycomb lattice with next-nearest-neighbor hopping t_2 = 0.1*t and flux phi = pi/2.

**Wrong approach (common LLM error):** Use a 10x10 k-mesh and compute C = (1/(2pi)) sum_k F_12(k) delta_k1 delta_k2 using finite differences for the Berry curvature. Result: C = 0.87.

A Chern number of 0.87 is WRONG. Chern numbers are exactly integer by topology. A non-integer value means the numerical method is insufficiently converged.

**Correct approach:**

Step 1. **Convergence test.** Compute C on meshes of increasing density:
```
| k-mesh  | C_numerical |
|---------|-------------|
| 10x10   | 0.872       |
| 20x20   | 0.968       |
| 50x50   | 0.997       |
| 100x100 | 1.000       |
| 200x200 | 1.000       |
```
C converges to exactly 1. The 10x10 mesh gives 13% error.

Step 2. **Use the Fukui-Hatsugai-Suzuki (FHS) method.** Instead of discretizing the Berry curvature (which requires fine meshes), compute the Chern number from the product of link variables U_12(k) around each plaquette:
```
C = (1/(2pi)) sum_plaquettes Im[ln(U_1 * U_2 * U_1^{-1} * U_2^{-1})]
```
where U_mu(k) = <u(k)|u(k + delta_k_mu)> / |<u(k)|u(k + delta_k_mu)>|.

The FHS method gives EXACTLY integer C for any mesh (up to gauge singularities), because it computes a discrete topological invariant. On the 10x10 mesh: C_FHS = 1 exactly.

Step 3. **Verify bulk-boundary correspondence.** Compute the band structure on a strip (periodic in x, open in y). Count the number of edge states crossing the gap: should be |C| = 1 chiral edge mode. If the edge state count disagrees with the bulk Chern number, there is an error in either the bulk or edge calculation.

**The typical LLM error** reports a non-integer Chern number from a coarse-mesh Berry curvature integration and doesn't flag it as unphysical. The quantization check (C must be integer) catches this immediately.

## Worked Example: Berry Phase of a Spin-1/2 in a Rotating Magnetic Field

**Problem:** Compute the Berry phase acquired by a spin-1/2 particle whose magnetic field B(t) traces a closed loop on the sphere, subtending solid angle Omega. This targets the LLM error class of confusing the Berry phase (geometric, gauge-invariant) with the dynamical phase, getting the wrong sign from inconsistent spinor conventions, and incorrectly handling the gauge singularity at the south pole.

### Setup

A spin-1/2 Hamiltonian H(t) = -gamma B(t) . sigma / 2, where B(t) = B_0 (sin(theta) cos(phi(t)), sin(theta) sin(phi(t)), cos(theta)) traces a cone of half-angle theta around the z-axis as phi goes from 0 to 2pi. The adiabatic Berry phase for the spin-up eigenstate (aligned with B) is:

```
gamma_Berry = -integral A . dR
```

where A is the Berry connection and the integral is over the parameter-space path.

### Step 1: Find the Eigenstates

The instantaneous spin-up eigenstate (aligned with B(theta, phi)):

```
|+(theta, phi)> = cos(theta/2) |up> + e^{i phi} sin(theta/2) |down>
```

**Gauge choice warning:** This is the standard gauge, smooth everywhere EXCEPT at theta = pi (south pole), where the state is e^{i phi} |down> — the phase is ill-defined as r -> south pole. This gauge singularity is the spinor analog of the Dirac string.

### Step 2: Compute the Berry Connection

```
A_phi = i <+| d/d(phi) |+> = i [cos(theta/2) <up| + e^{-i phi} sin(theta/2) <down|]
        * [i e^{i phi} sin(theta/2) |down>]
      = i * (i) * sin^2(theta/2) = -sin^2(theta/2)
```

A_theta = i <+| d/d(theta) |+> = 0 (real for this gauge choice).

### Step 3: Berry Phase Around the Loop

The parameter-space path has constant theta, phi: 0 -> 2pi.

```
gamma_Berry = -integral_0^{2pi} A_phi d(phi) = sin^2(theta/2) * 2pi
```

Using the identity sin^2(theta/2) = (1 - cos(theta))/2:

```
gamma_Berry = pi (1 - cos(theta))
```

### Step 4: Interpret as Solid Angle

The solid angle subtended by the cone:

```
Omega = integral_0^{2pi} d(phi) integral_0^{theta} sin(theta') d(theta') = 2pi (1 - cos(theta))
```

Therefore:

```
gamma_Berry = Omega / 2
```

For spin-j: gamma_Berry = j * Omega. The factor of 1/2 for spin-1/2 is exact.

### Step 5: LLM Error Analysis

**Error 1: Wrong gauge, wrong answer.** An alternative gauge:

```
|+'(theta, phi)> = e^{-i phi} cos(theta/2) |up> + sin(theta/2) |down>
```

This gauge is smooth at the south pole but singular at the north pole (theta = 0). Computing A_phi in this gauge:

```
A'_phi = -cos^2(theta/2)
```

The Berry phase: gamma' = cos^2(theta/2) * 2pi = pi(1 + cos(theta)).

This differs from the first answer by 2pi: gamma' = gamma + 2pi. Both are correct — the Berry phase is defined modulo 2pi, and the two gauges differ by a gauge transformation that winds once around the sphere. LLMs that report different answers in different gauges without noting the mod 2pi equivalence are making an error.

**Error 2: Confusing Berry and dynamical phases.** The total phase after adiabatic evolution is:

```
phi_total = phi_dynamical + phi_Berry = -(1/hbar) integral E_+(t) dt + gamma_Berry
```

LLMs sometimes absorb the Berry phase into the dynamical phase or vice versa, getting the wrong geometric contribution.

**Error 3: Wrong sign for spin-down.** The spin-down state acquires Berry phase -Omega/2 (opposite sign). LLMs sometimes give the same sign for both states, violating the constraint that the total phase (sum over a complete set) must be zero mod 2pi.

### Verification

1. **Theta = 0 (no cone):** gamma = 0. The B field doesn't rotate — no geometric phase. Correct.

2. **Theta = pi/2 (hemisphere):** gamma = pi. The cone subtends half the sphere (Omega = 2pi), giving gamma = pi. This is the phase acquired by a spin transported around the equator. Correct.

3. **Theta = pi (full sphere):** gamma = 2pi ~ 0. The path subtends the entire sphere (Omega = 4pi), and gamma = 2pi is equivalent to zero. This is consistent: a monopole of charge 1/2 inside the sphere contributes flux 4pi * (1/2) = 2pi, and the Berry phase equals the enclosed flux. Correct.

4. **Gauge invariance.** The Berry phase difference between the two gauges is exactly 2pi, which is the winding number of the gauge transformation e^{i phi} over the loop phi: 0 -> 2pi. Berry phases are gauge-invariant modulo 2pi. Confirmed.

5. **Solid angle formula.** For an ARBITRARY closed path on the sphere (not just a cone), gamma = Omega/2 where Omega is the solid angle enclosed. This follows from Stokes' theorem: gamma = integral_path A . dl = integral_surface F dS, and the Berry curvature of a spin-1/2 is F = (1/2) sin(theta), which integrates to Omega/2 over any surface bounded by the path.
