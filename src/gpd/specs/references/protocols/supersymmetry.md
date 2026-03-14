---
load_when:
  - "supersymmetry"
  - "SUSY"
  - "superfield"
  - "superconformal"
  - "superconformal index"
  - "BPS"
  - "Seiberg duality"
  - "Seiberg-Witten"
  - "localization"
  - "supergravity"
  - "superpartner"
  - "gaugino"
  - "squark"
  - "slepton"
  - "Wess-Zumino"
tier: 2
context_cost: medium
---

# Supersymmetry Protocol

Supersymmetric calculations require careful treatment of Grassmann-valued superspace coordinates, superfield expansions, and the interplay between bosonic and fermionic degrees of freedom. But modern SUSY work is also organized by protected sectors: BPS bounds, indices, localization, holomorphy, dualities, and superconformal representation theory. Convention mismatches between global and local SUSY, N=1 and extended SUSY, or Lorentzian and Euclidean setups are a major source of errors.

## Related Protocols

- See `derivation-discipline.md` for sign tracking and convention annotation in all derivations
- See `effective-field-theory.md` for SUSY EFT construction, soft breaking terms, and matching
- See `renormalization-group.md` for SUSY non-renormalization theorems and RG running
- See `group-theory.md` for supergroup representations and Casimir invariants
- See `perturbation-theory.md` for SUSY Feynman rules and loop calculations
- See `holography-ads-cft.md` for protected observables and AdS/CFT uses of supersymmetry
- See `conformal-bootstrap.md` for superconformal multiplets and protected operator data

## Step 1: Declare SUSY Framework and Conventions

Before writing any supersymmetric expression, declare:

1. **Dimension and amount of SUSY:** 4d `N=1`, 4d `N=2`, 4d `N=4`, 3d `N=2`, etc. State the number of supercharges explicitly.
2. **Global vs local supersymmetry:** Distinguish rigid SUSY from supergravity. Many vacuum-energy and scalar-potential formulas change once SUSY is local.
3. **Superspace and spinor conventions:** Two-component (Weyl) vs four-component notation, metric signature, and the spinor metric convention `epsilon^{12} = +1` or `-1`.
4. **Multiplet type and background:** Chiral, vector, hyper, tensor, gravity multiplet, etc. If working on a curved manifold or Euclidean background for localization/index computations, state the background geometry and preserved supercharges.
5. **R-symmetry and central charges:** State the R-charge assignments and whether central charges enter the SUSY algebra.
6. **Observable type:** Distinguish component Lagrangian, BPS mass formula, Witten index, superconformal index, localized partition function, Seiberg-Witten data, or duality claim.
7. **Breaking terms:** If SUSY is broken, state the mechanism (F-term, D-term, gauge mediation, gravity mediation, anomaly mediation, etc.) and the soft-breaking or supergravity data explicitly.

## Step 2: Verify Multiplets, Auxiliary Fields, and Moduli Space

1. **Component expansion:** Expand every superfield in components and verify the correct number of bosonic and fermionic degrees of freedom match off-shell and on-shell.
2. **Auxiliary fields:** Solve the equations of motion for `F` and `D` fields and substitute back with the correct Kähler/gauge conventions. Verify the resulting vacuum equations rather than eliminating auxiliaries by memory.
3. **Branch structure:** State whether the vacuum lies on a Coulomb, Higgs, mixed, or confining branch. In extended SUSY this choice controls which low-energy variables are physical.
4. **Mass relations:** In an unbroken supermultiplet, boson and fermion masses match. Supertrace formulas are assumption-dependent; do not use `STr M^2 = 0` blindly outside the renormalizable global-SUSY context where its hypotheses are satisfied.

## Step 3: Grassmann Algebra Discipline

1. **Sign tracking:** Every interchange of Grassmann-valued objects (theta, theta-bar, fermionic fields) produces a sign. Track signs at every step using the anticommutation relations.
2. **Integration conventions:** State the Berezin integration convention: integral d(theta) theta = 1, integral d(theta) 1 = 0. For full superspace: d^4 theta = d^2 theta d^2 theta-bar.
3. **Fierz identities:** When rearranging spinor bilinears, use the 2-component Fierz identities (simpler than 4-component). Verify by contracting with test spinors.

## Step 4: Use Protected Quantities, BPS Bounds, and Localization Correctly

1. **BPS bounds:** Derive the relevant bound directly from the SUSY algebra, including any central charge or angular-momentum/R-charge combination. State which supercharges annihilate the BPS state or operator.
2. **Short multiplets and recombination:** Protected operators live in shortened multiplets. If a dimension or charge is claimed to be protected, state the shortening condition or recombination rule that enforces it.
3. **Indices:** The Witten index and superconformal index count protected `Q`-cohomology data and are invariant under continuous deformations, but they are not automatically equal to the full degeneracy of states.
4. **Localization:** State the supercharge `Q`, the bosonic symmetry generated by `Q^2`, the `Q`-exact deformation used to localize, the fixed locus, and the one-loop/zero-mode measure. A formal "localization argument" without contour and determinant data is incomplete.
5. **Protected observables:** BPS Wilson loops, defect operators, and localized partition functions must preserve the same supercharge used in the computation.

## Step 5: Track Holomorphy, Dualities, and Non-Perturbative Dynamics

1. **Holomorphy:** In 4d `N=1`, the superpotential `W` is holomorphic in chiral superfields and does not receive perturbative renormalization. Do not confuse this with the holomorphic gauge coupling or with non-perturbative instanton effects.
2. **Kähler and D-terms:** The Kähler potential and D-terms are generally renormalized. Non-renormalization of `W` is not a license to ignore wavefunction renormalization or D-term corrections.
3. **Seiberg-Witten / extended SUSY:** In 4d `N=2`, the low-energy Coulomb-branch prepotential is one-loop exact perturbatively and receives instanton corrections. Seiberg-Witten geometry encodes the central charges, BPS masses, and singular loci of the moduli space.
4. **Seiberg duality and related SUSY dualities:** Verify global symmetry matching, 't Hooft anomalies, moduli-space matching, operator maps, and protected quantities such as indices or partition functions where available.
5. **Maximally supersymmetric theories:** In 4d `N=4` SYM, the beta function vanishes and many observables are constrained by exact symmetry, integrability, and holography. Do not import `N=1` or `N=2` statements without checking the preserved algebra.

## Step 6: SUSY Breaking and Supergravity Checks

1. **Global SUSY breaking:** In rigid SUSY, the scalar potential is non-negative and unbroken SUSY requires all `F` and `D` terms to vanish.
2. **Local SUSY / supergravity:** In supergravity, use the supergravity scalar potential and Killing-spinor equations. A vanishing or negative cosmological constant does not by itself diagnose unbroken SUSY, and the global-SUSY vacuum-energy logic does not carry over unchanged.
3. **Goldstino and super-Higgs:** Spontaneous breaking produces a Goldstino in global SUSY, while in supergravity it is eaten by the gravitino. Verify the regime before invoking either statement.
4. **Soft terms:** Check that gaugino masses, scalar masses, A-terms, B-terms, and any singlet tadpoles are genuinely soft and that the mediation scale and EFT regime are stated.

## Step 7: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Framework declaration | State dimension, amount of SUSY, global vs local, and observable type | Mixing rigid SUSY, supergravity, and protected-sector formulas |
| DOF counting | Count bosonic = fermionic degrees of freedom in each multiplet off-shell and on-shell | Wrong superfield or multiplet content |
| BPS bound | Derive the bound from the superalgebra and central charge data | Fake protected masses or wrong shortening claim |
| Index interpretation | Verify the quantity is an index or protected partition function rather than a raw degeneracy count | Overclaiming state counting or black-hole microstate matching |
| Localization data | State `Q`, `Q^2`, fixed locus, contour, determinants, and zero modes | Formal localization with missing measure data |
| Holomorphy | `W` is holomorphic and perturbatively non-renormalized; Kähler and D-terms are not generically protected | Spurious corrections or missing allowed ones |
| Duality matching | Match anomalies, moduli spaces, operator maps, and protected observables | Slogan-level Seiberg duality claims |
| Global vs local potential | Use the correct scalar potential and BPS/Killing-spinor equations for rigid SUSY vs supergravity | Importing global-SUSY formulas into string or AdS setups |

## Common LLM Errors in SUSY

1. **Mixing global SUSY and supergravity formulas** for the scalar potential, vacuum energy, or Goldstino/gravitino physics.
2. **Claiming the superpotential gets perturbative loop corrections,** or confusing the superpotential with the holomorphic gauge coupling.
3. **Treating an index as the full degeneracy of states** without explaining the protected limit or chamber.
4. **Using universal supertrace formulas without their assumptions** (for example inside EFTs or supergravity).
5. **Confusing N=1, N=2, and N=4 protection statements** or importing one theory's non-renormalization theorem into another.
6. **Claiming Seiberg duality from field content alone** without anomaly, moduli-space, and operator-map checks.
7. **Ignoring wall-crossing or chamber dependence** when discussing BPS spectra.

## Standard References

- Wess & Bagger: *Supersymmetry and Supergravity* (standard 4D N=1 conventions)
- Martin: *A Supersymmetry Primer* (arXiv:hep-ph/9709356, widely used review)
- Freedman and Van Proeyen: *Supergravity* (local SUSY and supergravity conventions)
- Terning: *TASI-2002 Lectures: Non-perturbative Supersymmetry* (holomorphy, Seiberg duality, dynamical SUSY breaking)
- Pestun and Zabzine: *Introduction to Localization in Quantum Field Theory* (localization overview)
- Gadde: *Lectures on the Superconformal Index* (protected indices and SCFT counting)
- Martone: *The Constraining Power of Coulomb Branch Geometry: Lectures on Seiberg-Witten Theory* (4d `N=2` low-energy structure)
- Akhond et al.: *The Hitchhiker's Guide to 4d N=2 Superconformal Field Theories* (modern SCFT overview)
