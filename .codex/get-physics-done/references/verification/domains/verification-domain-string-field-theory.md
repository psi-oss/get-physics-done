---
load_when:
  - "string field theory verification"
  - "string field theory"
  - "open string field theory"
  - "closed string field theory"
  - "superstring field theory"
  - "tachyon condensation"
  - "ghost number"
  - "picture number"
  - "BRST"
tier: 2
context_cost: large
---

# Verification Domain — String Field Theory

BRST cohomology, ghost and picture bookkeeping, BV / `A_infinity` / `L_infinity` consistency, gauge fixing, level truncation, and benchmark observables for open and closed string field theory.

**Load when:** Working on covariant string field theory, tachyon condensation, marginal deformations, off-shell string amplitudes, or algebraic formulations of open/closed superstring interactions.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `references/verification/domains/verification-domain-qft.md` — BRST and gauge-theory checks with field-theory language
- `references/verification/domains/verification-domain-mathematical-physics.md` — homotopy-algebra and structural consistency
- `references/protocols/string-field-theory.md` — formulation-specific workflow

---

<brst_and_quantum_numbers>

## BRST, Ghost Number, and Picture Verification

```
Core checks:
1. Verify Q_B^2 = 0 in the chosen worldsheet background.
2. Verify the string field and gauge parameters carry the required ghost number.
3. For superstrings, verify every field and product has the required picture number.
4. For closed strings, verify level matching and the b_0^-, L_0^- constraints before using a state in a vertex or propagator.
```

**Failure signals:**

- A kinetic term with the wrong total ghost number
- A nonvanishing expression in a sector where the picture number forbids it
- BRST-exact states contributing to a claimed gauge-invariant observable

</brst_and_quantum_numbers>

<algebraic_consistency>

## BPZ, Cyclicity, and Homotopy-Algebra Checks

```
For cubic or homotopy-algebra formulations:
1. Verify BPZ odd/even properties of the BRST operator and multilinear products.
2. Check cyclicity of the symplectic form or BPZ inner product.
3. Verify the specific A_infinity or L_infinity relations used in the computation.
4. If the calculation uses a shifted background, re-check the shifted products and shifted BRST operator.
```

**Minimal benchmark logic:**

- Cubic OSFT: associativity of `*` plus cyclicity should imply gauge invariance.
- Closed or super SFT: the multilinear identities should close exactly in the subspace actually used, not only formally in the abstract.

</algebraic_consistency>

<gauge_fixing_and_truncation>

## Gauge Fixing and Level-Truncation Verification

```
Gauge-fixing discipline:
1. State the gauge (Siegel, Schnabl, partial large-Hilbert-space gauge, etc.).
2. Verify the gauge condition is compatible with the solution sector.
3. Check whether gauge-fixed observables remain stable under truncation changes.

Truncation discipline:
1. Record the truncation basis and maximum level.
2. Compute key observables at multiple levels.
3. Verify monotone or stabilizing convergence before making a physical claim.
```

**Failure signals:**

- A vacuum solution that moves substantially when the level increases
- A gauge-invariant observable that changes sign or branch under small gauge/truncation changes
- A purported physical state dominated by BRST-trivial or null-state contamination

</gauge_fixing_and_truncation>

<moduli_and_pco>

## Moduli-Space and Picture-Changing Verification

```
For superstring or closed-string SFT:
1. Verify that the vertex construction covers moduli space exactly once.
2. Check that stubs, local coordinates, or cell decompositions are compatible with the formulation.
3. For picture-changing operators, verify collision-free placement or a prescription known to be equivalent.
4. If amplitudes are compared with worldsheet results, verify the same moduli-space region and normalization are used.
```

**Failure signals:**

- Missing or double-counted moduli regions
- PCO placements that depend on arbitrary contour choices in a way that changes the answer
- Boundary terms omitted when varying the action or comparing amplitudes

</moduli_and_pco>

<benchmark_observables>

## Benchmark Observables and Canonical Checks

```
Open bosonic tachyon vacuum:
1. Vacuum energy should approach -T_D in standard normalization.
2. Gauge-invariant observables should match the disappearance of the original D-brane boundary condition.

Marginal deformations:
1. Ellwood invariants or boundary-state data should reproduce the expected BCFT modulus.
2. The energy should remain flat along an exactly marginal direction.

Amplitude reproduction:
1. Factorization poles and residues must agree with the worldsheet amplitude.
2. Background-shifted amplitudes must use the shifted BRST operator and vertices consistently.
```

</benchmark_observables>

## Verification Checklist

| Check | What to verify |
|-------|----------------|
| BRST nilpotency | `Q_B^2 = 0`, correct background CFT, correct constraint subspace |
| Ghost/picture number | Every term has the allowed total ghost/picture number |
| BPZ/reality | BPZ parity, cyclicity, and reality conditions are consistent |
| Homotopy identities | `A_infinity` / `L_infinity` relations close for the products actually used |
| Gauge choice | Gauge fixing is admissible and not silently changing the physical sector |
| Truncation convergence | Physical observables stabilize with increasing level |
| Sen-conjecture benchmark | Vacuum energy and gauge-invariant observables match canonical results |
| Moduli/PCO control | No missing regions, no uncontrolled PCO collision ambiguities |
