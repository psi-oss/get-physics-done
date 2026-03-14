---
load_when:
  - "algebraic quantum field theory"
  - "AQFT"
  - "Haag-Kastler"
  - "net of algebras"
  - "operator algebraic QFT"
  - "von Neumann algebra"
  - "Tomita-Takesaki"
  - "modular theory"
  - "type III"
  - "DHR sector"
  - "Reeh-Schlieder"
tier: 3
context_cost: high
---

# Algebraic Quantum Field Theory Protocol

Algebraic quantum field theory (AQFT) formulates QFT in terms of local operator algebras and their structural relations. The dominant failure mode is not an isolated sign mistake; it is claiming a modular, superselection, or factor-type result without specifying the net, the state, the representation, and the von Neumann completion being used.

## Related Protocols

- See `derivation-discipline.md` for convention tracking and checkpointing
- See `group-theory.md` for symmetry representations and charge labels
- See `generalized-symmetries.md` for higher-form or defect symmetry structure
- See `topological-methods.md` for inclusions, indices, and topological obstructions
- See `holography-ads-cft.md` when modular or entanglement arguments are being compared with holographic constructions

## Step 1: Declare the Kinematic AQFT Framework

Before proving or using any AQFT statement, state explicitly:

1. **Spacetime and region class:** Minkowski vs curved spacetime, double cones vs wedges vs intervals, and whether the net is Haag-Kastler or locally covariant.
2. **Algebraic level:** Net of C*-algebras vs von Neumann algebras in a chosen representation.
3. **Axioms in force:** Isotony, locality or graded locality, covariance, additivity or strong additivity, time-slice property, Haag duality, split property, and any positivity-of-energy assumption.
4. **State choice:** Vacuum, KMS/thermal, charged sector, boundary state, or another reference state.
5. **Representation:** Vacuum GNS representation, thermal GNS representation, sector representation, or universal representation.

## Step 2: Fix the State and GNS Data

1. **State functional:** Write the state `omega` and the GNS triple `(pi_omega, H_omega, Omega_omega)`.
2. **Cyclic and separating properties:** Do not use Tomita-Takesaki theory until the relevant vector is known to be cyclic and separating for the algebra in question.
3. **Vacuum assumptions:** If invoking Reeh-Schlieder, positivity of energy, or Bisognano-Wichmann, state the hypotheses that make these theorems available.
4. **Thermal/KMS states:** If the state is thermal, specify the dynamics, inverse temperature `beta`, and whether the KMS condition is being used in the C*- or von Neumann setting.
5. **Sector language:** If working in a charged sector, state whether charges are described by representations, localized endomorphisms, or field algebra data.

## Step 3: Verify the Net Structure Before Interpreting Physics

1. **Isotony:** Confirm `O_1 subset O_2` implies `A(O_1) subset A(O_2)`.
2. **Locality:** Confirm spacelike separated algebras commute, or state the graded-local variant if fermions are present.
3. **Covariance:** Identify the symmetry group action and the unitary or automorphic implementation.
4. **Additivity/time-slice:** State which additivity or causal propagation property is used before making reconstruction claims.
5. **Duality claims:** Haag duality or wedge duality are substantial properties, not notation. State whether they are assumptions, theorems, or conjectured in the model at hand.

## Step 4: Handle Modular Theory Carefully

1. **Tomita operator:** Define the Tomita operator `S` from the cyclic-separating vector before talking about modular objects.
2. **Modular operator and conjugation:** Distinguish the modular operator `Delta` and conjugation `J` from any physical Hamiltonian, CPT operator, or geometric reflection unless a theorem identifies them.
3. **Bisognano-Wichmann:** If a modular flow is claimed to equal Lorentz boosts, state that this is a theorem for specific wedge algebras under specific hypotheses.
4. **Thermal structure:** For KMS states, distinguish the modular automorphism group from externally imposed time evolution unless they are known to coincide.
5. **Relative modular data:** If relative entropy or relative modular operators are used, state both states and the von Neumann algebra on which they are defined.

## Step 5: Make Factor-Type Claims Only with Real Criteria

1. **Factor test:** Verify the center is trivial before calling an algebra a factor.
2. **Type I vs II vs III:** Do not infer the type from finite-dimensional intuition. Type I supports ordinary tensor-factor/density-matrix reasoning; type II has a semifinite trace; type III has no nonzero finite trace and no ordinary density matrices for local restrictions.
3. **Type III_1 claims:** In relativistic AQFT, local algebras are often hyperfinite type `III_1`, but this is a structural theorem with hypotheses. State the representation and theorem used.
4. **Connes spectrum or modular spectrum:** Any `III_lambda` claim should be tied to modular data, not to vague entanglement language.
5. **Hyperfiniteness/injectivity:** Hyperfinite is not synonymous with "simple" or "approximately finite-dimensional" in a naive sense. State the precise theorem or construction.

## Step 6: Track Superselection, Charges, and Inclusions

1. **DHR sectors:** If superselection sectors are claimed, specify localization, transportability, and whether the DHR framework applies.
2. **Statistics and gauge reconstruction:** Distinguish Doplicher-Haag-Roberts reconstruction from ordinary global-symmetry classification.
3. **Subfactors and inclusions:** If Jones index, subnet inclusions, or conformal-net extensions are used, state the inclusion explicitly and identify which conditional expectation or standard invariant is relevant.
4. **Curved spacetime:** For locally covariant AQFT, state the functorial assignment of algebras and the class of admissible embeddings.
5. **Defects and boundaries:** For boundary or chiral theories, specify whether the relevant object is a net on intervals, a boundary net, or a defect inclusion.

## Step 7: Benchmark Against Canonical AQFT Results

1. **Vacuum structure:** Reeh-Schlieder should be used as a benchmark for relativistic vacuum states, not assumed blindly for arbitrary states.
2. **Thermal equilibrium:** HHW/KMS structure should match the dynamics used in the problem.
3. **Wedge modular flow:** Bisognano-Wichmann is the standard benchmark for identifying modular flow with boosts.
4. **Local factor types:** For standard relativistic models, compare any local-type statement against the expectation of hyperfinite type `III_1` local algebras.
5. **Sector reconstruction:** DHR analyses should recover known charge content and statistics in benchmark models.

## Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Net declaration | State spacetime, regions, algebraic level, and axioms | Unstated framework changes |
| GNS data | Write state, representation, cyclic/separating vector | Illicit modular-theory use |
| Locality/covariance | Verify commutation and symmetry implementation | Fake Haag-Kastler reasoning |
| Modular discipline | Define `S`, `Delta`, `J`; state theorem for geometric interpretation | Confusing modular and physical time |
| Factor-type justification | Check center, trace properties, and modular spectrum | Wrong type-I/II/III claims |
| AQFT structural properties | State duality, split, nuclearity, and additivity status explicitly | Smuggling in strong assumptions |
| Sector bookkeeping | Specify DHR/localization/endomorphism framework | Vague charge statements |
| Canonical benchmark comparison | Check against Reeh-Schlieder, HHW/KMS, Bisognano-Wichmann, type `III_1` expectations | Structural conclusions detached from the literature |

## Common LLM Errors in AQFT and Operator Algebras

1. **Treating a local algebra as `B(H)`** and then importing finite-dimensional density-matrix reasoning into a type `III` setting.
2. **Confusing modular flow with physical time evolution** without a theorem such as Bisognano-Wichmann or a KMS identification.
3. **Claiming "type III" from entanglement rhetoric** rather than from factor and modular criteria.
4. **Using Tomita-Takesaki language without a cyclic and separating vector.**
5. **Mixing Wightman-field data and Haag-Kastler net data** without stating the reconstruction or equivalence theorem being used.
6. **Assuming Haag duality, split property, or nuclearity by default** when they are substantive structural results.
7. **Using Stone-von Neumann intuition in QFT** where inequivalent representations and local type `III` behavior are the rule rather than the exception.

## Standard References

- Haag and Kastler: *An Algebraic Approach to Quantum Field Theory* (1964)
- Haag, Hugenholtz, and Winnink: *On the Equilibrium States in Quantum Statistical Mechanics* (1967)
- Haag: *Local Quantum Physics* (2nd ed.)
- Doplicher, Haag, and Roberts: superselection sector papers
- Bisognano and Wichmann: modular/wedge duality theorems
- Driessler: local algebra type results in relativistic QFT
- Borchers: *On Revolutionizing Quantum Field Theory with Tomita's Modular Theory*
- Yngvason: *The Role of Type III Factors in Quantum Field Theory*
- Brunetti, Dappiaggi, Fredenhagen, and Yngvason (eds.): *Advances in Algebraic Quantum Field Theory*
