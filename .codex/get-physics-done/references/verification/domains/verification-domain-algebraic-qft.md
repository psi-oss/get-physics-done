---
load_when:
  - "algebraic qft verification"
  - "algebraic quantum field theory"
  - "AQFT"
  - "Haag-Kastler"
  - "operator algebra"
  - "von Neumann factor"
  - "modular theory"
  - "Tomita-Takesaki"
  - "type III"
  - "DHR"
tier: 2
context_cost: large
---

# Verification Domain — Algebraic Quantum Field Theory

Haag-Kastler nets, GNS representations, modular theory, superselection sectors, split and duality properties, and von Neumann factor-type verification for AQFT and operator-algebraic QFT.

**Load when:** Working on local nets of observables, modular localization, DHR sectors, type `I/II/III` claims, conformal nets, or locally covariant/operator-algebraic formulations of QFT.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `references/verification/domains/verification-domain-qft.md` — Ward identities and ordinary field-theoretic checks
- `references/verification/domains/verification-domain-mathematical-physics.md` — self-adjointness, spectral theory, general rigor checks
- `references/protocols/algebraic-qft.md` — formulation-specific workflow

---

<net_axioms>

## Haag-Kastler Net Verification

```
Core checks:
1. Verify isotony: O_1 subset O_2 implies A(O_1) subset A(O_2).
2. Verify locality or graded locality for spacelike separated regions.
3. Verify covariance and identify the implementing symmetry representation or automorphism action.
4. State whether additivity, strong additivity, Haag duality, split property, and time-slice are assumptions or derived results.
```

**Failure signals:**

- Locality used in a proof without a stated spacelike-separation criterion
- Haag duality invoked even though only isotony/locality were established
- Switching between C*- and von Neumann net language without specifying the representation

</net_axioms>

<gns_and_states>

## GNS, Vacuum, and Thermal-State Verification

```
For any state-dependent claim:
1. Write the state omega and the GNS triple (pi_omega, H_omega, Omega_omega).
2. Verify whether Omega_omega is cyclic and separating for the algebra under discussion.
3. If the state is thermal, verify the KMS condition with respect to the declared dynamics.
4. If Reeh-Schlieder is invoked, check the theorem's hypotheses in the chosen model or spacetime.
```

**Failure signals:**

- Tomita-Takesaki language used with no cyclic/separating vector
- Vacuum properties imported into arbitrary KMS or charged states
- Thermal modular flow confused with a Hamiltonian that was never declared

</gns_and_states>

<modular_theory>

## Modular-Theory and Bisognano-Wichmann Verification

```
For modular claims:
1. Define the Tomita operator S, modular operator Delta, and modular conjugation J.
2. Verify the algebra and state on which these are defined.
3. If modular flow is identified with boosts or geometric flow, cite the specific theorem and region class.
4. For relative modular operators or relative entropy, specify both states and the common algebra.
```

**Failure signals:**

- Interpreting modular flow as physical time without theorem support
- Using `-log rho` language in a type `III` setting as if a trace-class density matrix exists
- Treating `J` as CPT or spatial reflection automatically rather than theorem-conditionally

</modular_theory>

<factor_types>

## von Neumann Factor-Type Verification

```
Before stating type I, II, or III:
1. Verify the center is trivial (factor test).
2. State whether a faithful normal semifinite trace exists.
3. Check the modular/Connes spectrum if a type III_lambda claim is made.
4. Distinguish local algebras, global quasilocal algebras, and thermal representation algebras.
```

**Minimal decision logic:**

- **Type I:** ordinary tensor-factor picture and density-matrix reasoning available
- **Type II:** semifinite trace exists but no minimal tensor-factor picture in general
- **Type III:** no nonzero finite trace; local subsystem density matrices fail in the naive finite-dimensional sense
- **Type `III_1`:** full modular/Connes spectrum `R_+` in the standard operator-algebraic classification

**Failure signals:**

- "Infinite entanglement" offered as the sole proof of type `III`
- Type `III_1` claimed with no modular-spectrum or theorem input
- Switching between type claims in different representations as though type were representation-independent

</factor_types>

<structural_properties>

## Split Property, Nuclearity, Duality, and Sectors

```
For structural AQFT claims:
1. State whether Haag duality is assumed, proved, or known to fail in the model.
2. If the split property is used, identify the inclusion and the type I interpolating factor.
3. If nuclearity or modular nuclearity is used, specify the map and norm criterion.
4. For DHR sectors, verify localization, transportability, and the morphism or representation framework.
5. For subfactor or conformal-net index claims, write the inclusion explicitly.
```

**Failure signals:**

- Split-property conclusions without a type I interpolant or nuclearity input
- DHR language used for charges that are not localizable in bounded regions
- Jones-index statements made without a concrete inclusion of algebras

</structural_properties>

<benchmarks>

## Canonical AQFT Benchmarks

```
Benchmark checks:
1. Vacuum local algebras in standard relativistic models should align with the established type III_1 expectation.
2. Wedge modular flow in the vacuum should reproduce Lorentz boosts when Bisognano-Wichmann applies.
3. KMS states should satisfy the HHW equilibrium criterion for the declared dynamics.
4. DHR sector analyses should recover the known charge/statistics structure of benchmark models.
```

</benchmarks>

## Verification Checklist

| Check | What to verify |
|-------|----------------|
| Net declaration | Spacetime, region class, representation level, and axioms are explicit |
| GNS data | State, representation, and cyclic/separating vector are fixed |
| Locality/covariance | Commutation and symmetry implementation are proved or cited |
| Modular structure | `S`, `Delta`, `J`, and any geometric identification are justified |
| Factor type | Center, trace, and modular-spectrum criteria support the type claim |
| Structural properties | Duality, split, nuclearity, and additivity status are explicit |
| Sector logic | DHR/localization/endomorphism assumptions are matched to the problem |
| Canonical benchmarks | Reeh-Schlieder, HHW/KMS, Bisognano-Wichmann, and type `III_1` expectations are checked where relevant |
