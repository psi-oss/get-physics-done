---
load_when:
  - "algebraic quantum field theory"
  - "AQFT"
  - "Haag-Kastler"
  - "net of algebras"
  - "operator algebraic QFT"
  - "operator algebra"
  - "von Neumann factor"
  - "Tomita-Takesaki"
  - "type III"
  - "DHR"
tier: 2
context_cost: medium
---

# Algebraic Quantum Field Theory

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/algebraic-qft.md`, `references/protocols/group-theory.md`, `references/protocols/generalized-symmetries.md`, `references/protocols/topological-methods.md`, `references/protocols/holography-ads-cft.md`, and `references/protocols/conformal-bootstrap.md` (for conformal nets and chiral-CFT structural data).

**Haag-Kastler and local-covariant structure:**

- Local observables are organized as a net `O -> A(O)` of C*- or von Neumann algebras
- Core structural properties are isotony, locality, covariance, additivity, time-slice, and physically relevant spectrum conditions
- In curved spacetime, the modern extension is locally covariant AQFT: a functor from spacetimes to algebras

**Operator algebras and factor types:**

- Distinguish C*-algebraic nets from their von Neumann closures in a chosen GNS representation
- Check whether local algebras are factors before discussing type classification
- Type `I`, `II`, and `III` are structural claims about projections, traces, and modular data; they are not stylistic labels
- Local relativistic QFT algebras are typically hyperfinite type `III_1` under standard assumptions, which explains why naive tensor-factor density matrices fail locally

**Modular theory and thermal structure:**

- Tomita-Takesaki theory requires a cyclic and separating vector
- Modular automorphism groups, modular conjugations, and relative modular operators encode intrinsic operator-algebraic dynamics
- Bisognano-Wichmann and HHW/KMS are canonical benchmarks linking modular theory to Lorentz boosts and thermal equilibrium

**Charges, sectors, and inclusions:**

- DHR sectors are described by localized, transportable charges or endomorphisms
- Field-algebra and gauge-group reconstruction are structural theorems, not ad hoc symmetry arguments
- Subfactors, Jones index, and conformal-net extensions become central in low-dimensional AQFT and chiral CFT

## Key Tools and Software

| Tool | Purpose | Notes |
|------|---------|-------|
| **Lean / Coq / Isabelle** | Formal proof organization for theorem-heavy work | Best suited to structural proofs, not heavy numerics |
| **SageMath** | Algebraic experimentation, categories, graph/index calculations | Useful for examples and subnet inclusion bookkeeping |
| **Mathematica / Python notebooks** | Symbolic checks of modular generators or toy-model examples | Helpful for sanity checks, not substitutes for proofs |
| **Cadabra** | Graded-algebra and symbolic identity checking | Useful when AQFT work meets BRST or operator identities |

**Practical note:** AQFT is proof-heavy and model-light. Most serious work relies on careful theorem organization and hand-checked structural arguments rather than a standard numerical software stack.

## Validation Strategies

**Net and representation checks:**

- State the region class, the algebraic level, and the representation before discussing local properties
- Verify isotony, locality, covariance, and the status of additivity, duality, and split assumptions
- Write the GNS triple explicitly and check cyclic/separating hypotheses before using modular theory

**Modular and factor-type checks:**

- Distinguish modular flow from physical time evolution unless a theorem identifies them
- Justify any factor-type claim by center, trace, and modular-spectrum criteria
- For type `III_1` claims, state the theorem or model result used rather than extrapolating from "infinite entanglement"

**Sector and inclusion checks:**

- DHR claims require localization and transportability, not just a conserved charge
- Subfactor or conformal-net index claims require the actual inclusion and conditional-expectation structure
- In curved spacetime, specify the locally covariant functor and the admissible morphisms before comparing different backgrounds

## Common Pitfalls

- **Local algebra = tensor factor:** False in AQFT and lethal for entanglement arguments.
- **Type by slogan:** "Local QFT algebras are type III" is not a derivation; representation and theorem matter.
- **Modular Hamiltonian confusion:** `-log rho` language often fails or requires reinterpretation in type `III` settings.
- **Unstated axioms:** Haag duality, split property, and nuclearity are often assumed silently and then used as if automatic.
- **GNS amnesia:** Modular claims made without naming the state and representation are usually meaningless.

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Locally covariant AQFT** | How much of AQFT survives in curved spacetime with dynamical geometry or semiclassical inputs? | Fewster, Sanders, Verch, Rejzner communities | Excellent — theorem and assumption bookkeeping dominate |
| **Modular theory, entanglement, and holography** | Which modular and relative-entropy structures are universal across AQFT, semiclassical gravity, and holography? | Longo, Morinelli, Hollands, Lechner communities | Good — structural checks are strong; interpretation must stay disciplined |
| **Generalized symmetries and defects in operator-algebra language** | How should higher-form or non-invertible structures be encoded by nets, inclusions, and defects? | Naaijkens, Carpi, Kawahigashi, Weiner communities | Good — algebraic structure is explicit but conventions matter |
| **Conformal nets and subfactor methods** | Which chiral or low-dimensional QFT structures can be classified via conformal nets, extensions, and Jones index data? | Longo, Kawahigashi, Carpi, Weiner | Excellent — rigorous and structurally constrained |

## Methodology Decision Tree

```
What kind of AQFT problem is it?
├── Structural net theorem
│   ├── Axiom verification? -> isotony, locality, covariance, duality, split
│   └── Representation-dependent? -> specify GNS data first
├── Modular or thermal question
│   ├── Vacuum wedge/causal domain? -> Tomita-Takesaki + Bisognano-Wichmann
│   └── Equilibrium state? -> KMS + HHW + modular automorphism analysis
├── Factor-type question
│   ├── Need factor test? -> compute center first
│   └── Need type `III_lambda` claim? -> modular/Connes spectrum, not density-matrix intuition
├── Charge or sector question
│   └── DHR sectors, localized endomorphisms, Doplicher-Roberts reconstruction
└── Low-dimensional or conformal net question
    └── Conformal nets, subnet inclusions, Jones index, category-theoretic structure
```

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One structural property or one family of model nets | "Split property and type `III_1` structure for a class of free-field nets" |
| **Postdoc** | New theorem connecting modular/sector structure to physical interpretation | "Relative entropy and modular inclusions in locally covariant AQFT" |
| **Faculty** | New framework or classification program spanning nets, sectors, and spacetime structure | "Operator-algebraic classification of symmetry defects in relativistic QFT" |
