---
load_when:
  - "string field theory"
  - "open string field theory"
  - "closed string field theory"
  - "superstring field theory"
  - "tachyon condensation"
  - "BRST"
  - "A_infinity"
  - "L_infinity"
tier: 2
context_cost: medium
---

# String Field Theory

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/string-field-theory.md`, `references/protocols/path-integrals.md`, `references/protocols/supersymmetry.md`, `references/protocols/holography-ads-cft.md`, `references/protocols/group-theory.md`, `references/protocols/numerical-computation.md`, and `references/protocols/analytic-continuation.md`.

**Foundational formulations:**

- **Witten cubic open bosonic SFT:** Associative star product, BPZ inner product, ghost-number-one string field, and covariant gauge invariance
- **Closed bosonic SFT:** BV master action and string vertices that tile moduli space without overcounting
- **Berkovits WZW-like open super SFT:** Large-Hilbert-space formulation with separate `eta` and BRST structures
- **Modern `A_infinity` / `L_infinity` formulations:** Algebraic organization of open, heterotic, and type II superstring field theory
- **1PI effective SFT:** Off-shell amplitudes and vacuum shifts encoded directly in an effective action

**State-space and worldsheet input:**

- Matter + ghost BCFT/CFT with the correct central charge and BRST operator
- Ghost number, picture number, Grassmann parity, Chan-Paton factors, and reality/BPZ conditions
- Closed-string constraints: level matching and `b_0^-`, `L_0^-` restrictions
- Worldsheet moduli-space coverage and picture-changing prescriptions for superstrings

**Physical questions where SFT is standard:**

- Tachyon condensation and unstable D-brane decay
- Marginal deformations and background shifts
- Off-shell amplitudes and field redefinitions
- Open/closed coupling, boundary states, and gauge-invariant observables
- Homotopy-algebra formulations of gauge structure and perturbation theory

## Key Tools and Software

| Tool | Purpose | Notes |
|------|---------|-------|
| **Mathematica** | Oscillator algebra, wedge-state manipulations, level truncation, symbolic BRST checks | The de facto workhorse; many projects rely on custom notebooks rather than public packages |
| **Cadabra** | Graded algebra, BRST manipulations, tensor bookkeeping | Useful when sign and grading discipline matter |
| **SageMath / SymPy** | Homological algebra, symbolic manipulation, sparse linear algebra | Good for custom `A_infinity` / `L_infinity` experimentation |
| **numpy / scipy / mpmath** | Level-truncation numerics, eigenvalue problems, continuation methods | Standard numerical stack for truncated actions |
| **Custom sparse-matrix code** | Large oscillator-basis computations | Often unavoidable for serious level-truncation studies |

**Practical note:** Unlike collider QFT or lattice QCD, string field theory still relies heavily on custom symbolic and numerical code built around the specific formulation and truncation scheme.

## Validation Strategies

**BRST and quantum-number checks:**

- Verify `Q_B^2 = 0` in the chosen background
- Check ghost number and picture number for every field, vertex, and gauge parameter
- For closed strings, verify `b_0^- Psi = 0` and `L_0^- Psi = 0`

**Algebraic consistency:**

- Cubic open SFT: associativity of `*` and cyclicity of the BPZ pairing
- Superstring and closed-string SFT: `A_infinity` / `L_infinity` identities for the multilinear products actually used
- BV master equation or 1PI consistency when the formulation demands it

**Gauge and truncation control:**

- Gauge choice stated explicitly and checked for admissibility
- Observables compared across truncation levels and, when possible, across gauges
- Null states and BRST-trivial states separated from physical observables

**Physical benchmarks:**

- Tachyon vacuum energy approaches minus the unstable D-brane tension
- Gauge-invariant observables (Ellwood invariants, boundary-state data) match the intended BCFT deformation
- Reproduced amplitudes factorize correctly and agree with worldsheet results

## Common Pitfalls

- **Hilbert-space confusion:** Large-Hilbert-space and small-Hilbert-space variables are not interchangeable.
- **Ghost/picture errors:** A formally plausible expression can vanish or become ill-defined if the ghost or picture number is wrong.
- **Truncation theater:** A numerical minimum at low level is not evidence for a physical vacuum until convergence is checked.
- **PCO collisions:** Superstring calculations can fail due to picture-changing singularities even when the algebra otherwise looks clean.
- **Worldsheet vs spacetime ambiguity:** Claims about spacetime physics must be tied to gauge-invariant observables, not only to gauge-fixed string fields.

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Comprehensive modern review and synthesis** | How do cubic, WZW-like, `A_infinity`, `L_infinity`, and 1PI formulations fit together conceptually? | Sen, Zwiebach, Erler | Excellent — synthesis, conventions, and cross-formulation bookkeeping |
| **Algebraic structures in closed super SFT** | How should homotopy transfer and effective actions organize the closed superstring interactions? | Sen and collaborators; Erler-lineage algebraic work | Excellent — algebraic consistency and symbolic derivation heavy |
| **Manifest spacetime supersymmetry in heterotic SFT** | Can heterotic SFT be written with cleaner supersymmetry control and practical perturbation theory? | Sen and collaborators | Good — convention-heavy but structurally constrained |
| **Open/closed normalization and boundary terms** | How should off-shell normalization, boundary terms, and open-closed couplings be fixed unambiguously? | Zwiebach, Erler, Maccaferri, related groups | Good — ideal for careful derivation and consistency checking |
| **Rolling tachyons and symplectic structure** | What is the correct phase-space or symplectic description of time-dependent SFT solutions? | Erler, Fırat, collaborators | Moderate — technically subtle but verification-rich |

## Methodology Decision Tree

```
What kind of SFT problem is it?
├── Open bosonic, off-shell vacuum structure
│   ├── Need nonperturbative vacuum? → cubic OSFT + level truncation or analytic wedge-state methods
│   └── Need exact benchmark? → tachyon vacuum / marginal deformation observables
├── Open superstring
│   ├── Large Hilbert space preferred? → Berkovits WZW-like formulation
│   ├── Small Hilbert space / homotopy algebra? → A_infinity formulation
│   └── Ramond sector central? → use a formulation with explicit Ramond consistency
├── Closed / heterotic / type II
│   ├── Need moduli-space and BV control? → L_infinity or BV/1PI formulation
│   └── Need amplitudes around shifted vacuum? → background shift + effective action
└── Comparison to spacetime or BCFT observables
    ├── D-brane / boundary deformation? → Ellwood invariants, boundary states
    └── Scattering / on-shell amplitude? → compare with worldsheet factorization
```

## Common Collaboration Patterns

- **String field theory + string theory:** Use `references/subfields/string-theory.md` when the problem depends on worldsheet CFT, D-brane constructions, compactification, or duality dictionary rather than on off-shell SFT structure alone
- **String field theory + mathematical physics:** Homotopy algebra, BV structure, and cyclicity questions often also need `references/subfields/mathematical-physics.md`
- **String field theory + holography:** When an SFT background is interpreted holographically, also load `references/protocols/holography-ads-cft.md` and the relevant string-theory context

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One formulation in one sector with one benchmark observable | "Level-truncation study of marginal deformations in cubic open SFT" |
| **Postdoc** | Cross-formulation comparison or new algebraic control of a difficult sector | "Ramond-sector consistency in open superstring field theory" |
| **Faculty** | New formulation or background-independent framework | "Closed superstring effective action and homotopy-transfer structure" |
