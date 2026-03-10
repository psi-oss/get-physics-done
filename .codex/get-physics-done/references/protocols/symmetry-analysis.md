---
load_when:
  - "symmetry"
  - "group theory"
  - "representation theory"
  - "selection rule"
  - "spontaneous symmetry breaking"
  - "Goldstone boson"
  - "anomaly"
  - "Noether"
tier: 2
context_cost: medium
---

# Symmetry Analysis Protocol

Symmetry determines what is possible, what is forbidden, and what is exactly zero. Errors in symmetry analysis cascade through every subsequent calculation: wrong selection rules, wrong degeneracy structures, wrong phase diagrams. This protocol ensures symmetries are correctly identified, applied, and distinguished from approximate symmetries.

## Related Protocols
- `topological-methods.md` — Topological invariants often follow from symmetry classification
- `lattice-gauge-theory.md` — Gauge symmetries on the lattice
- `effective-field-theory.md` — Symmetry-constrained operator bases
- `asymptotic-symmetries.md` — Boundary symmetries, large gauge transformations, BMS charges, and soft theorems
- `generalized-symmetries.md` — Higher-form, higher-group, and non-invertible symmetry structures

## Step 1: Identifying Symmetries from the Lagrangian/Hamiltonian

1. **List all transformations that leave the action (or Hamiltonian) invariant.** For each candidate transformation, verify invariance explicitly — do not assume. Check:
   - **Continuous symmetries:** Spatial translations, rotations, Lorentz boosts, internal rotations (U(1), SU(N), etc.), scale transformations, conformal transformations, and when appropriate asymptotic/boundary symmetries such as BMS or large gauge transformations.
   - **Discrete symmetries:** Parity P (spatial inversion), time reversal T, charge conjugation C, lattice translations, point group operations, particle exchange.
   - **Gauge symmetries:** Local transformations that leave the action invariant. These are redundancies in the description, not physical symmetries — but they constrain the physical Hilbert space and observables.
2. **Distinguish global from local (gauge) symmetries.** Global symmetries have physical consequences (conserved charges via Noether's theorem, selection rules). Gauge symmetries constrain the Hilbert space (Gauss's law, physical state conditions). Spontaneous breaking of global symmetries produces Goldstone bosons; "spontaneous breaking" of gauge symmetries is the Higgs mechanism (no true Goldstone boson — the would-be Goldstone is eaten).
3. **Check if the symmetry is exact or approximate.** Small explicit breaking terms (quark masses break chiral symmetry, gravity breaks global symmetries) may be present. Quantify the breaking: is the breaking parameter small enough that the symmetry is a useful organizing principle?
4. **Do not stop at the local action if generalized symmetry is suspected.** Higher-form and non-invertible symmetries are often diagnosed by topological defects and extended operators rather than by varying the local Lagrangian alone.

## Step 2: Representation Theory

1. **Identify the symmetry group** and its structure (simple, semi-simple, direct product, semi-direct product). For Lie groups: identify the Lie algebra, rank, and Dynkin diagram.
2. **Construct irreducible representations (irreps).** For the states/fields of interest:
   - Identify the representation by its quantum numbers (dimension, Casimir values, highest weight).
   - For SU(2): representations labeled by spin j, dimension 2j+1, Casimir j(j+1).
   - For SU(3): representations labeled by (p,q) or dimension (3, 3-bar, 8, etc.), two Casimirs.
   - For point groups: use character tables. The character (trace of the representation matrix) determines the decomposition into irreps.
3. **Tensor product decomposition.** When combining representations (coupling angular momenta, forming multi-particle states, constructing interaction vertices):
   - Write the Clebsch-Gordan decomposition: R_1 ⊗ R_2 = direct sum of R_i.
   - For SU(2): j_1 ⊗ j_2 = |j_1 - j_2| ⊕ ... ⊕ (j_1 + j_2). Verify the dimensions match: (2j_1+1)(2j_2+1) = sum of (2j_i+1).
   - For SU(3): Use Young tableaux or weight diagrams. Verify dimension counting.
   - **The decomposition determines selection rules.** A matrix element <R_f | O | R_i> vanishes unless R_f appears in the decomposition R_O ⊗ R_i.

## Step 3: Selection Rules and Matrix Elements

1. **Wigner-Eckart theorem.** For any symmetry group, a matrix element of a tensor operator factorizes: <j', m' | T^k_q | j, m> = <j, m; k, q | j', m'> * <j' || T^k || j>. The geometric factor (Clebsch-Gordan coefficient) is universal; the reduced matrix element encodes the dynamics.
2. **Apply Schur's lemma.** An operator that commutes with all group elements and maps between irreps is either zero (different irreps) or proportional to the identity (same irrep). This gives orthogonality of states in different irreps and determines the form of invariant tensors.
3. **Selection rules from symmetry:**
   - **Parity:** Electric dipole transitions require parity change. Magnetic dipole and electric quadrupole preserve parity.
   - **Angular momentum:** Delta_j determined by the multipole order of the operator.
   - **Time reversal:** Forbids electric dipole moments for non-degenerate states.
   - **Crystal field:** Point group irreps determine which transitions are allowed in solids.
4. **Verify selection rules numerically** by computing the forbidden matrix element explicitly. It must vanish to numerical precision. If it does not: either the symmetry assignment is wrong, the operator transform incorrectly, or the states have the wrong quantum numbers.

## Step 4: Spontaneous Symmetry Breaking

1. **Identifying SSB.** The Hamiltonian has a symmetry G, but the ground state is invariant only under a subgroup H ⊂ G. The order parameter transforms non-trivially under G/H and has a nonzero expectation value in the ground state.
2. **Goldstone theorem.** For each broken continuous symmetry generator, there is a massless excitation (Goldstone boson). Count: the number of Goldstone bosons = dim(G) - dim(H) = dim(G/H). Verify this count matches the spectrum.
   - **Type I (relativistic):** Linear dispersion omega ~ |k|. One Goldstone per broken generator. (Examples: pions, phonons in crystals.)
   - **Type II (non-relativistic):** Quadratic dispersion omega ~ k^2. Occurs when two broken generators form a canonical pair. One Goldstone per two broken generators. (Examples: ferromagnetic magnons.)
3. **Order parameter construction.** The order parameter must:
   - Transform non-trivially under the broken symmetry
   - Be gauge-invariant (for gauge theories)
   - Have the correct dimension
   - Vanish in the symmetric phase and be nonzero in the broken phase
4. **Finite-size systems.** True SSB only occurs in the thermodynamic limit. In finite systems, the ground state is always the symmetric superposition. Detect SSB via: long-range order in correlation functions, tower of states (Anderson tower), or finite-size scaling of the order parameter.

## Step 5: Anomalies

1. **Classical symmetry that fails quantum mechanically.** The path integral measure is not invariant under the classical symmetry transformation. This produces an anomalous Ward identity with a computable anomaly coefficient.
2. **Chiral anomaly (ABJ).** For a chiral fermion coupled to a gauge field: partial_mu j^mu_5 = (1/16pi^2) F_{mu nu} F-tilde^{mu nu}. The coefficient is exact (Adler-Bardeen theorem) and determined by the fermion representation. Verify: the triangle diagram gives the same coefficient as the Fujikawa (path integral measure) calculation.
3. **Anomaly matching ('t Hooft).** If a global symmetry has an anomaly in the UV theory, the SAME anomaly must appear in the IR theory. This constrains the low-energy spectrum — if the IR theory is confining, there must be massless composite fermions or the symmetry must be spontaneously broken.
4. **Gauge anomaly cancellation.** A gauge symmetry with a non-vanishing anomaly renders the theory inconsistent (non-unitary). Verify anomaly cancellation for any gauge theory: sum over all fermion species of the anomaly coefficients must vanish. In the Standard Model: anomaly cancellation requires exactly the observed fermion content (quarks + leptons per generation).
5. **Gravitational anomalies.** Chiral fermions in 4D can have a mixed gauge-gravitational anomaly proportional to Tr[T_a] (sum of charges). This must vanish for consistency. It does in the Standard Model because the charges in each generation sum to zero.

## Common Pitfalls

- **Missing discrete symmetries.** The Hamiltonian may have a Z_2, Z_N, or other discrete symmetry that is not obvious from inspection. These can protect degeneracies, forbid transitions, or stabilize topological phases. Systematically check all point group operations, particle-hole symmetry, and time reversal.
- **Confusing symmetry of H with symmetry of the ground state.** H has full rotational symmetry; the ferromagnetic ground state does not. The broken symmetry is still physically relevant — it determines the Goldstone spectrum, the domain structure, and the response to external fields.
- **Wrong representation assignment.** Assigning a particle to the wrong irrep produces wrong selection rules. Verify by checking Casimir eigenvalues, dimensions, and branching rules under subgroups.
- **Ignoring accidental symmetries.** Some Lagrangians have more symmetry than intended. The free massless Dirac Lagrangian has a U(1)_V x U(1)_A symmetry, not just U(1)_V. The QCD Lagrangian with N_f massless quarks has SU(N_f)_L x SU(N_f)_R, not just SU(N_f)_V. Missing an accidental symmetry means missing Goldstone bosons or conservation laws.
- **Anomaly miscounting.** Forgetting a fermion species, using the wrong representation dimension, or double-counting Weyl vs Dirac fermions. Always count carefully: Tr[T_a {T_b, T_c}] summed over ALL chiral fermions, with the correct sign for left-handed vs right-handed.

## Concrete Example: Wrong Group Theory (LLM Error Class #4)

**Problem:** Decompose the tensor product of two spin-1 representations of SU(2).

**Wrong answer (common LLM error):** "1 x 1 = 0 + 1 + 2, so the decomposition is a scalar, vector, and tensor. Three irreps of dimensions 1, 3, 5."

This is correct for spin, but LLMs frequently get the SYMMETRIC vs ANTISYMMETRIC structure wrong when it matters for identical particles or operator construction.

**Correct analysis:**

For j_1 = j_2 = 1: j_1 x j_2 = (j_1 + j_2) + (j_1 + j_2 - 1) + ... + |j_1 - j_2| = 2 + 1 + 0.

Dimension check: (2*1+1)^2 = 9 = (2*2+1) + (2*1+1) + (2*0+1) = 5 + 3 + 1 = 9. Correct.

The key detail LLMs miss: under exchange of the two spin-1 particles:
- j = 2 (quintet): SYMMETRIC under exchange
- j = 1 (triplet): ANTISYMMETRIC under exchange
- j = 0 (singlet): SYMMETRIC under exchange

General rule: the representation with j = j_1 + j_2 - n has parity (-1)^n under exchange.

**Why this matters:** For two identical bosons (e.g., two photons), only the symmetric representations (j = 2 and j = 0) are physical. The j = 1 state is forbidden by Bose statistics. This is why two photons cannot form a J = 1 state (Landau-Yang theorem).

**Verification strategy:**
1. **Dimension counting:** Always verify sum of irrep dimensions = product of factor dimensions.
2. **Abelian limit:** For SU(2), set j = 0 in one factor. The decomposition should give back a single irrep.
3. **Casimir check:** C_2(j) = j(j+1). Verify the quadratic Casimir of each irrep in the decomposition.
4. **Cross-check with character formula:** chi(j_1) * chi(j_2) = sum of chi(j_i). Characters are traces of representation matrices: chi_j(theta) = sin((2j+1)theta/2) / sin(theta/2).

## Worked Example: Selection Rules for Electric Dipole Transitions in Hydrogen

**Problem:** Determine which transitions between hydrogen atom states are allowed by electric dipole selection rules, and verify by explicit calculation that the forbidden transition |2,0,0> -> |1,0,0> has zero matrix element. This targets the LLM error class of incorrectly applying selection rules — stating rules without verifying them, or confusing magnetic dipole and electric dipole rules.

### Step 1: Identify the Symmetry

The electric dipole operator is d = -e * r, which transforms as a vector (l=1) under rotations. The selection rules follow from the Wigner-Eckart theorem: the matrix element <n'l'm'|r_q|nlm> is nonzero only if the Clebsch-Gordan coefficient <l,m; 1,q | l',m'> is nonzero.

### Step 2: Derive Selection Rules

From the properties of Clebsch-Gordan coefficients:

1. **Delta l = +/- 1** (parity change required: the dipole operator has odd parity, so initial and final states must have opposite parity)
2. **Delta m = 0, +/- 1** (from the three components r_0, r_{+1}, r_{-1} of the position vector)
3. **No l = 0 -> l = 0** transition (both states have even parity, but the dipole operator is odd)

### Step 3: Verify the Forbidden Transition

Consider the transition |2,0,0> -> |1,0,0> (2s -> 1s). Both states have l = 0. The dipole matrix element:

```
<1,0,0| r cos(theta) |2,0,0> = integral_0^inf R_{10}(r) * r * R_{20}(r) * r^2 dr
                                 * integral Y_0^0(theta,phi) * cos(theta) * Y_0^0(theta,phi) d Omega
```

The angular integral:

```
integral Y_0^0 * cos(theta) * Y_0^0 d Omega = (1/4pi) integral cos(theta) sin(theta) d theta d phi
= (1/4pi) * 2pi * integral_0^pi cos(theta) sin(theta) d theta
= (1/2) * [-(1/2) cos^2(theta)]_0^pi = (1/2) * (-1/2 + 1/2) = 0
```

The angular integral vanishes because cos(theta) = sqrt(4pi/3) * Y_1^0, and the integral of Y_0^0 * Y_1^0 * Y_0^0 over angles vanishes by orthogonality (the product Y_0^0 * Y_0^0 = Y_0^0 / sqrt(4pi) has no l=1 component).

### Verification

1. **Parity check:** |1,0,0> has parity (-1)^0 = +1. |2,0,0> has parity (-1)^0 = +1. Both even parity. The dipole operator has odd parity. So the matrix element must vanish by parity: (+1) * (-1) * (+1) = -1, which is odd, so the integral is zero. Confirmed.

2. **Group theory check:** l=0 x l=1 = l=1 (by angular momentum addition). The final state has l=0, which is NOT in the decomposition 0 x 1 = {1}. So the matrix element vanishes.

3. **Physical consequence:** The 2s state cannot decay to 1s via single-photon emission. It decays instead via two-photon emission (lifetime ~ 0.14 s, compared to ~ 1.6 ns for the allowed 2p -> 1s transition). An LLM that claims 2s -> 1s is dipole-allowed will predict a decay rate that is wrong by 8 orders of magnitude.

4. **Metastability check:** The 2s state is metastable precisely because Delta l = 0 forbids the electric dipole transition. In astrophysical contexts (hydrogen 21-cm line, Lyman-alpha forest), confusing allowed and forbidden transitions produces entirely wrong spectral predictions.

## Worked Example: Goldstone Boson Counting for Chiral Symmetry Breaking in QCD

**Problem:** Count the number of Goldstone bosons when the chiral symmetry SU(2)_L x SU(2)_R of two-flavor QCD is spontaneously broken to the diagonal SU(2)_V (isospin). Identify these Goldstone bosons physically, and verify against the observed meson spectrum. This targets the LLM error class of miscounting the dimension of the coset space G/H, confusing global and gauge symmetries in the counting, and misidentifying the physical Goldstone bosons.

### Step 1: Identify the Symmetry and Its Breaking Pattern

The QCD Lagrangian with two massless quarks (u, d) has the global symmetry:

```
G = SU(2)_L x SU(2)_R x U(1)_V x U(1)_A
```

The U(1)_V is baryon number (exact). The U(1)_A is broken by the axial anomaly (ABJ anomaly) — it is NOT a true symmetry of the quantum theory despite being a classical symmetry. So the relevant symmetry for Goldstone counting is:

```
G_eff = SU(2)_L x SU(2)_R    (dim = 3 + 3 = 6)
```

The QCD vacuum (quark condensate <q-bar q> != 0) breaks this to:

```
H = SU(2)_V    (dim = 3)
```

where SU(2)_V is the diagonal subgroup (simultaneous L and R rotations).

### Step 2: Count Goldstone Bosons

By the Goldstone theorem, the number of massless Goldstone bosons equals dim(G/H):

```
N_Goldstone = dim(G_eff) - dim(H) = 6 - 3 = 3
```

These 3 Goldstone bosons transform as a triplet under the unbroken SU(2)_V (isospin).

### Step 3: Physical Identification

The 3 Goldstone bosons are the **pions**: pi^+, pi^-, pi^0. They are:
- Pseudoscalar (J^P = 0^-) because they are associated with the broken axial generators
- Isospin triplet (I = 1): matches the adjoint representation of SU(2)_V
- Massless in the chiral limit (m_u = m_d = 0)

In reality, the pions have mass m_pi ~ 140 MeV because the quark masses (m_u ~ 2 MeV, m_d ~ 5 MeV) explicitly break chiral symmetry. The Gell-Mann-Oakes-Renner relation gives:

```
m_pi^2 = -(m_u + m_d) <q-bar q> / f_pi^2
```

The pions are pseudo-Goldstone bosons: light (compared to other hadrons ~1 GeV) but not massless.

### Step 4: Common LLM Errors

**Error 1: Counting U(1)_A as unbroken symmetry.** If we naively include U(1)_A:

```
G_wrong = SU(2)_L x SU(2)_R x U(1)_A    (dim = 7)
H_wrong = SU(2)_V                         (dim = 3)
N_wrong = 7 - 3 = 4
```

The 4th Goldstone boson would be the eta' meson. But the eta' has mass 958 MeV — far too heavy to be a Goldstone boson. This is the U(1)_A problem (resolved by 't Hooft's instanton mechanism). The U(1)_A is broken by the anomaly, not by spontaneous symmetry breaking, so it does not produce a Goldstone boson.

**Error 2: Counting as SU(2) -> nothing.** If we mistakenly think the FULL SU(2)_L x SU(2)_R is broken (no unbroken subgroup): N = 6 - 0 = 6. This predicts 6 Goldstone bosons. But only 3 light pseudoscalars (pions) are observed. The error is forgetting that the diagonal SU(2)_V (isospin) remains unbroken — isospin is an excellent approximate symmetry of the strong interactions.

**Error 3: Confusing with gauge symmetry breaking.** In the electroweak sector, SU(2)_L x U(1)_Y -> U(1)_EM is a GAUGE symmetry breaking (Higgs mechanism). The 3 "would-be Goldstone bosons" are eaten by the W^+, W^-, Z bosons (they become the longitudinal polarizations). LLMs sometimes confuse this with QCD chiral symmetry breaking and claim the pions are "eaten" — but QCD chiral symmetry is a GLOBAL symmetry, so the Goldstone bosons are physical particles, not eaten.

### Verification

1. **Dimension check.** dim(G/H) = dim(SU(2)_L x SU(2)_R) - dim(SU(2)_V) = 6 - 3 = 3. The coset space SU(2) x SU(2)/SU(2)_diag is isomorphic to S^3 (the 3-sphere), which has dimension 3. Correct.

2. **Representation check.** The broken generators are the three axial generators Q_A^a. Under the unbroken SU(2)_V, these transform as a triplet (adjoint representation). The pion field pi^a(x) transforms identically. If the Goldstone bosons transformed as a singlet or doublet under SU(2)_V, the symmetry analysis would be wrong.

3. **Three-flavor extension.** For N_f = 3 (u, d, s): G = SU(3)_L x SU(3)_R (dim = 16), H = SU(3)_V (dim = 8), N_Goldstone = 8. These are the pseudoscalar octet: pi^+, pi^-, pi^0, K^+, K^-, K^0, K-bar^0, eta. All 8 are observed with masses below 550 MeV, confirming the counting.

4. **Vafa-Witten theorem.** The SU(2)_V (isospin) symmetry cannot be spontaneously broken at zero baryon density (Vafa-Witten theorem). This confirms that H = SU(2)_V is correct and not further broken.

5. **PCAC check.** The divergence of the axial current is d_mu A^{a,mu} = f_pi m_pi^2 pi^a + O(m_q^2). In the chiral limit (m_q -> 0), d_mu A^{a,mu} = 0, confirming the axial current is conserved and the pions are exactly massless. This is the defining property of Goldstone bosons.
## Concrete Example: Wrong Branching Rules

**Problem:** How does the adjoint representation (8) of SU(3) decompose under the SU(2) x U(1) subgroup?

**Wrong answer (common LLM error):** "8 -> 3 + 2 + 2 + 1" (dimensions: 3 + 2 + 2 + 1 = 8). Dimensions match but the U(1) charges are wrong or missing.

**Correct answer:** Under SU(3) -> SU(2) x U(1) (with T_8 as the U(1) generator):

8 -> 3_0 + 2_{1/2} + 2_{-1/2} + 1_0

where the subscripts are the U(1) hypercharge values. The 3 is an SU(2) triplet (the isospin I = 1 states: pi+, pi0, pi-), the two doublets are (K+, K0) and (K0-bar, K-), and the singlet is the eta.

**Verification:**
1. Dimension counting: 3 + 2 + 2 + 1 = 8. Correct.
2. U(1) charge must sum to zero (tracelessness of SU(3) generators): 3*0 + 2*(1/2) + 2*(-1/2) + 1*0 = 0. Correct.
3. Cross-check with weight diagram: the octet has 8 weights in the (I_3, Y) plane. They must decompose correctly into the SU(2) x U(1) representations.
