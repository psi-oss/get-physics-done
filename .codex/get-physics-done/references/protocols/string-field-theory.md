---
load_when:
  - "string field theory"
  - "open string field theory"
  - "closed string field theory"
  - "superstring field theory"
  - "heterotic string field theory"
  - "type II string field theory"
  - "tachyon condensation"
  - "BRST string field"
  - "A_infinity"
  - "L_infinity"
  - "BV master action"
  - "Schnabl"
  - "Berkovits"
tier: 3
context_cost: high
---

# String Field Theory Protocol

String field theory (SFT) is an off-shell formulation of string interactions. It combines worldsheet conformal field theory, BRST cohomology, ghost and picture bookkeeping, and a gauge structure that is often most naturally expressed in BV, `A_infinity`, or `L_infinity` language. The dominant failure mode is not a small algebra error; it is mixing incompatible formulations, Hilbert spaces, or ghost/picture conventions and then drawing physical conclusions from the mismatch.

## Related Protocols

- See `derivation-discipline.md` for convention tracking and checkpointing
- See `path-integrals.md` for BV logic, gauge fixing, and functional-integral bookkeeping
- See `supersymmetry.md` for superstring backgrounds, protected sectors, and rigid-vs-local SUSY caveats
- See `holography-ads-cft.md` for bulk-boundary interpretations of string backgrounds
- See `conformal-bootstrap.md` for boundary CFT data and crossing constraints when comparing with worldsheet or holographic results
- See `numerical-computation.md` for level-truncation convergence and numerical stability

For worldsheet backgrounds, D-brane constructions, compactification data, or duality context behind the chosen SFT background, also load `references/subfields/string-theory.md`.

## Step 1: Declare the SFT Formulation and Conventions

Before any computation, state explicitly:

1. **String theory and sector:** Open vs closed, bosonic vs heterotic vs type II, and NS vs Ramond sector.
2. **Hilbert-space choice:** Small Hilbert space vs large Hilbert space for superstrings. This is not cosmetic; it changes the field content and gauge structure.
3. **Algebraic formulation:** Cubic Witten open SFT, Berkovits WZW-like super SFT, `A_infinity` open super SFT, `L_infinity` closed/heterotic/type II SFT, or 1PI effective SFT.
4. **State-space constraints:** Ghost number, picture number, reality condition, BPZ conjugation, and any `b_0^- = 0`, `L_0^- = 0`, or level-matching constraints.
5. **Gauge choice and truncation:** Siegel gauge, Schnabl gauge, partial gauge fixing in the large Hilbert space, level truncation, stub parameter, or no gauge fixing.
6. **Normalization conventions:** `alpha'`, string coupling `g_s`, D-brane tension normalization, and whether energies are quoted in units where the reference brane tension is `1`.

## Step 2: Verify the Worldsheet Input and State Space

1. **Background CFT:** State the matter + ghost worldsheet CFT, central charge balance, and boundary conditions. The BRST operator is only meaningful once the worldsheet data are fixed.
2. **BRST nilpotency:** Verify `Q_B^2 = 0` in the chosen background and Hilbert space.
3. **Quantum numbers:** Check ghost number, picture number, Grassmann parity, and Chan-Paton structure for every field and gauge parameter.
4. **Closed-string constraints:** For closed SFT, verify level matching and the `b_0^-`, `L_0^-` constraints before manipulating vertices or propagators.
5. **Picture-changing discipline:** For superstrings, state where picture-changing operators enter and verify that collisions or contour moves do not generate spurious singularities.

## Step 3: Check the Action and the Homotopy-Algebra Structure

1. **Open bosonic cubic SFT:** If using Witten's action,

```
S = -1/2 <Psi, Q_B Psi> - g/3 <Psi, Psi * Psi>
```

verify associativity of `*`, cyclicity of the BPZ inner product, and gauge invariance under

```
delta Psi = Q_B Lambda + Psi * Lambda - Lambda * Psi .
```

2. **Berkovits/WZW-like super SFT:** State the group-like field, the large-Hilbert-space variable, and the two gauge symmetries. Do not collapse WZW-like and cubic logic into one formula.
3. **`A_infinity` / `L_infinity` formulations:** Verify the multilinear products satisfy the required higher Jacobi identities and cyclicity with respect to the symplectic form.
4. **Closed-string vertices:** For closed SFT, verify that the vertices cover moduli space once, with the correct BV master equation or quantum master equation in the chosen formulation.
5. **Background shifts:** If expanding around a nontrivial solution, re-derive the shifted BRST operator and shifted products instead of assuming the old algebra survives unchanged.

## Step 4: Gauge Fixing, Truncation, and Solver Control

1. **Gauge fixing:** Verify that the gauge condition is admissible in the sector studied. Siegel gauge is standard for level truncation but not a proof of gauge-invariant physics by itself.
2. **Level truncation:** Record the basis, maximum level, oscillator ordering, and whether the truncation is level, level + interaction level, or another scheme.
3. **Convergence study:** Compare multiple truncation levels before claiming a physical observable is stable.
4. **Spurious states:** Track BRST quartets and null states so that numerical solutions are not artifacts of an overcomplete basis.
5. **Superstring subtleties:** In Ramond sectors or mixed NS/R calculations, verify the gauge fixing and picture assignment remain consistent after truncation.

## Step 5: Benchmark Against Canonical SFT Observables

1. **Tachyon condensation:** In open bosonic SFT, the tachyon vacuum energy should approach minus the unstable D-brane tension in the standard normalization.
2. **Ellwood invariants and boundary state data:** For classical solutions, compare gauge-invariant observables with the expected boundary CFT deformation or closed-string one-point functions.
3. **Marginal deformations:** Verify that the solution reproduces the expected BCFT modulus and that gauge-invariant observables vary correctly with the deformation parameter.
4. **On-shell amplitudes:** If the SFT is used to reproduce S-matrix elements, check factorization and agreement with the worldsheet amplitude at the same order.
5. **Background dependence:** If a solution is claimed to represent a new background, verify which physical quantities actually change and which are pure gauge.

## Step 6: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Formulation declaration | State open/closed, bosonic/super, small/large Hilbert, and algebraic framework | Mixing incompatible SFT formulations |
| BRST nilpotency | Verify `Q_B^2 = 0` and background central-charge balance | Invalid state space or wrong background |
| Ghost/picture bookkeeping | Check field and gauge-parameter assignments sector by sector | Illegal vertices and vanishing/nonexistent correlators |
| Cyclicity and homotopy identities | Verify BPZ cyclicity and `A_infinity` / `L_infinity` relations | Fake gauge invariance |
| Gauge-fixing admissibility | Check Siegel/Schnabl/other gauge assumptions explicitly | Gauge artifacts mistaken for physics |
| Truncation convergence | Compare observables across levels and gauges | Numerical artifacts from low-level truncation |
| Sen-conjecture benchmark | Compare vacuum energy and gauge invariants with canonical results | Wrong normalization or bad solution branch |
| Moduli-space coverage | For closed or super SFT, verify vertex/PCO placement covers moduli space correctly | Missing regions or double counting |

## Common LLM Errors in String Field Theory

1. **Confusing worldsheet and spacetime conventions,** especially ghost number, picture number, and BRST charge normalization.
2. **Mixing small- and large-Hilbert-space formulations** as if they were different notations for the same action.
3. **Treating low-level truncation output as rigorous** without a convergence study or gauge-dependence check.
4. **Dropping `b_0^-`, `L_0^-`, or level-matching constraints** in closed-string calculations.
5. **Assuming a formal `A_infinity` / `L_infinity` statement is verified** without checking the specific multilinear products used.
6. **Using picture-changing operators heuristically** and ignoring collision singularities or contour-dependence issues.
7. **Claiming a classical solution represents a physical background** without checking gauge-invariant observables such as vacuum energy or Ellwood invariants.

## Standard References

- Witten: *Noncommutative Geometry and String Field Theory* (Nucl. Phys. B 268, 1986)
- Zwiebach: *Closed String Field Theory: Quantum Action and the Batalin-Vilkovisky Master Equation* (Nucl. Phys. B 390, 1993)
- Berkovits: *Super-Poincare Invariant Superstring Field Theory* (Nucl. Phys. B 450, 1995)
- Sen and Zwiebach: *Tachyon Condensation in Open String Field Theory* (JHEP 03, 2000)
- Schnabl: *Analytic Solution for Tachyon Condensation in Open String Field Theory* (Adv. Theor. Math. Phys. 10, 2006; first circulated 2005)
- Fuchs, Kroyter, and Potting: *A Review of Analytic Solutions in Open String Field Theory* (J. Phys. A 45, 2012)
- Sen and Zwiebach: *String Field Theory: A Review* (2024 review article)
