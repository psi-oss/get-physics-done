---
load_when:
  - "supersymmetry"
  - "SUSY"
  - "superfield"
  - "superpartner"
  - "gaugino"
  - "squark"
  - "slepton"
  - "Wess-Zumino"
tier: 2
context_cost: medium
---

# Supersymmetry Protocol

Supersymmetric calculations require careful treatment of Grassmann-valued superspace coordinates, superfield expansions, and the interplay between bosonic and fermionic degrees of freedom. Convention mismatches between different SUSY formulations (N=1 vs extended, 4D vs higher-dimensional) are a major source of errors.

## Related Protocols

- See `derivation-discipline.md` for sign tracking and convention annotation in all derivations
- See `effective-field-theory.md` for SUSY EFT construction, soft breaking terms, and matching
- See `renormalization-group.md` for SUSY non-renormalization theorems and RG running
- See `group-theory.md` for supergroup representations and Casimir invariants
- See `perturbation-theory.md` for SUSY Feynman rules and loop calculations

## Step 1: Declare SUSY Framework and Conventions

Before writing any supersymmetric expression, declare:

1. **SUSY algebra:** N=1, N=2, N=4, or extended. State the number of supercharges.
2. **Superspace conventions:** Two-component (Weyl) vs four-component (Dirac) spinor notation. State the spinor metric convention: epsilon^{12} = +1 or -1.
3. **Superfield type:** Chiral, vector, linear, or general superfield. State the constraints (e.g., D-bar_alpha-dot Phi = 0 for chiral).
4. **R-symmetry:** State the R-charge assignments for all fields.
5. **Soft breaking terms:** If SUSY is broken, state the breaking mechanism (F-term, D-term, gravity mediation, gauge mediation) and the soft breaking Lagrangian explicitly.

## Step 2: Superfield Expansion Verification

1. **Component expansion:** Expand every superfield in components and verify the correct number of bosonic and fermionic degrees of freedom match. For a chiral superfield: phi (scalar), psi (Weyl fermion), F (auxiliary) = 2B + 2F off-shell.
2. **Auxiliary field elimination:** Solve the equations of motion for auxiliary fields (F, D) and substitute back. Verify the resulting scalar potential is bounded below (for unbroken SUSY) or has the correct vacuum structure.
3. **Mass spectrum:** Verify the supertrace relation: STr(M^2) = Sum_J (-1)^{2J} (2J+1) m_J^2 = 0 for unbroken SUSY. Nonzero supertrace indicates explicit breaking.

## Step 3: Grassmann Algebra Discipline

1. **Sign tracking:** Every interchange of Grassmann-valued objects (theta, theta-bar, fermionic fields) produces a sign. Track signs at every step using the anticommutation relations.
2. **Integration conventions:** State the Berezin integration convention: integral d(theta) theta = 1, integral d(theta) 1 = 0. For full superspace: d^4 theta = d^2 theta d^2 theta-bar.
3. **Fierz identities:** When rearranging spinor bilinears, use the 2-component Fierz identities (simpler than 4-component). Verify by contracting with test spinors.

## Step 4: Non-Renormalization Theorems

1. **Holomorphy:** The superpotential W is holomorphic in chiral superfields (depends on Phi, not Phi-dagger). This constrains the form of quantum corrections.
2. **Non-renormalization of W:** In N=1 SUSY, the superpotential receives no perturbative corrections beyond one loop (Seiberg's argument). Verify any claimed loop correction against this theorem.
3. **Kahler potential:** The Kahler potential K(Phi, Phi-dagger) IS renormalized at all loop orders. Do not confuse with the superpotential non-renormalization.
4. **Gauge coupling:** In N=2 SUSY, the prepotential receives corrections only at one loop (perturbatively). In N=4, the coupling does not run.

## Step 5: SUSY Breaking Verification

1. **Vacuum energy:** If SUSY is unbroken, the vacuum energy is exactly zero: V_min = 0. A positive vacuum energy signals spontaneous SUSY breaking.
2. **Goldstino:** Spontaneous SUSY breaking produces a massless Goldstino (absorbed by the gravitino in supergravity via the super-Higgs mechanism).
3. **Sum rules:** The mass sum rules for broken SUSY (e.g., STr M^2 for soft breaking) constrain the spectrum. Verify these are satisfied.
4. **Soft terms:** Verify that soft breaking terms do not reintroduce quadratic divergences. The allowed soft terms are: gaugino masses, scalar masses, A-terms, B-terms, and linear terms (for singlets).

## Step 6: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| DOF counting | Count bosonic = fermionic off-shell and on-shell | Wrong superfield content |
| Supertrace | STr(M^2) = 0 (unbroken) or known value (broken) | Mass spectrum errors |
| Holomorphy | W depends only on Phi, not Phi-dagger | Spurious corrections |
| R-symmetry | Verify R-charge conservation at every vertex | Wrong Feynman rules |
| Dimensional reduction | Check d=4 N=1 from d=10 N=1 gives correct d=4 N=4 | Convention errors in dimensional reduction |
| Gauge invariance | Verify D-term potential is gauge-invariant | Wrong gauge kinetic function |

## Common LLM Errors in SUSY

1. **Wrong spinor conventions:** Mixing dotted/undotted index conventions between sources
2. **Missing factors of 2:** In the relation between real and complex scalar fields in superfield expansions
3. **Wrong sign in D-term:** The D-term potential is V_D = (1/2) g^2 (phi^dagger T^a phi)^2, with the sign of g^2 positive
4. **Confusing N=1 and N=2:** Using N=1 non-renormalization for the Kahler potential (which IS renormalized) or N=2 non-renormalization for the gauge coupling in an N=1 theory
5. **Forgetting the superpotential phase:** CP violation in SUSY comes from complex phases in the superpotential and soft terms

## Standard References

- Wess & Bagger: *Supersymmetry and Supergravity* (standard 4D N=1 conventions)
- Weinberg: *The Quantum Theory of Fields, Vol. 3* (comprehensive treatment)
- Martin: *A Supersymmetry Primer* (arXiv:hep-ph/9709356, widely used review)
- Terning: *Modern Supersymmetry* (pedagogical, with worked examples)
- Seiberg: *Naturalness versus Supersymmetric Non-renormalization Theorems* (holomorphy arguments)
