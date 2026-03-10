---
load_when:
  - "string theory"
  - "superstring"
  - "worldsheet"
  - "D-brane"
  - "compactification"
  - "Calabi-Yau"
  - "flux compactification"
  - "heterotic"
  - "F-theory"
  - "mirror symmetry"
  - "M-theory"
  - "swampland"
  - "string phenomenology"
  - "string field theory"
tier: 2
context_cost: medium
---

# String Theory

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/supersymmetry.md`, `references/protocols/holography-ads-cft.md`, `references/protocols/de-sitter-space.md`, `references/protocols/path-integrals.md`, `references/protocols/string-field-theory.md` (for off-shell formulations), `references/protocols/effective-field-theory.md`, `references/protocols/renormalization-group.md`, `references/protocols/group-theory.md`, and `references/protocols/topological-methods.md`.

**Worldsheet CFT and BRST Structure:**

- Start by stating the theory: bosonic, type IIA/IIB, heterotic, type I, topological string, or a string-field-theory reformulation
- In perturbative string theory, the worldsheet CFT is the core consistency object: Virasoro constraints, ghosts, BRST cohomology, GSO projections, and modular invariance are not optional details
- Keep `alpha'` and `g_s` conceptually separate: `alpha'` controls derivative/stringy corrections while `g_s` controls topology/genus expansion
- Beta-function or conformal-invariance statements must specify the background fields and approximation order before being translated into spacetime equations

**Strings, Branes, and Dualities:**

- Open-string boundary conditions define D-branes and their worldvolume gauge sectors; Chan-Paton data, RR charges, and supersymmetry conditions must be explicit
- Duality claims require a matched dictionary of charges, moduli, protected spectra, and effective actions; slogans like "T-dual" or "S-dual" are not enough
- BPS branes and protected sectors are often the only quantities that remain under full control across strong/weak-coupling comparisons
- AdS/CFT should be treated as a string-theoretic duality with a particularly sharp dictionary, not as a generic template for every background

**Compactification, Moduli, and Low-Energy EFT:**

- Define the internal geometry, orientifold/orbifold data, fluxes, tadpoles, and preserved supersymmetry before discussing the four-dimensional EFT
- Moduli stabilization requires a scalar potential and a hierarchy analysis; "stabilized" is incomplete without identifying which moduli are fixed and at what scale
- Keep track of the EFT hierarchy explicitly: low-energy scale `<< M_KK <= M_s`, together with the size of `alpha'`, loop, and non-perturbative corrections
- Consistent truncation is stronger than dimensional reduction; do not assume every KK reduction is consistent

**Swampland, Landscape, and String Phenomenology:**

- Swampland statements are conjectural consistency criteria, not automatic theorems of all quantum-gravity frameworks
- Whenever a swampland argument is used, state which conjecture is being invoked and what explicit constructions or counterexamples are relevant
- String phenomenology requires more than field content: couplings, hierarchies, and selection rules depend on the compactification data
- Low-energy predictions should be framed as compactification-dependent unless protected or otherwise shown to be robust

**String Field Theory and Off-Shell Structure:**

- String field theory is the right language when off-shell control, tachyon condensation, picture-changing ambiguities, or formal unitarity/UV arguments are central
- The relevant algebraic structure (`A_infinity`, `L_infinity`, BV) and the worldsheet input data should be stated explicitly
- Do not import string-field-theory conclusions into ordinary worldsheet perturbation theory unless the map between the two formulations is clear
- For dedicated SFT workflows, load `references/subfields/string-field-theory.md` and `references/protocols/string-field-theory.md`

## Key Tools and Software

| Tool | Purpose | Notes |
|------|---------|-------|
| **Cadabra** | Tensor and field-theory algebra | Useful for supergravity reductions, brane actions, and index-heavy manipulations |
| **xAct / xTensor** | Supergravity and compactification algebra | Good for curvature, flux, and KK-reduction bookkeeping |
| **SageMath** | Modular forms, lattices, and geometry | Useful for worldsheet/modular checks and compactification arithmetic |
| **Macaulay2 / Singular** | Algebraic geometry and sheaf/cohomology tasks | Helpful for Calabi-Yau, bundle, and intersection computations |
| **PALP / cohomCalg / CYTools** | Toric and Calabi-Yau data analysis | Common in compactification and string-phenomenology workflows |
| **Mathematica / Python notebooks** | Symbolic + numerical exploration | Typical for flux vacua scans, spectrum calculations, and Yukawa computations |

## Validation Strategies

**Worldsheet Consistency:**

- Verify central-charge cancellation and the critical-dimension logic appropriate to the theory
- Check BRST nilpotency, level matching, GSO projection, and modular invariance before trusting the spectrum or partition function
- String amplitudes must factorize correctly on physical poles and respect the declared genus order

**Branes and Dualities:**

- Check boundary conditions, RR charge assignments, tadpole cancellation, anomaly inflow, and preserved supersymmetry
- For duality claims, match protected data on both sides: charges, moduli, BPS spectra, or exact partition functions
- Do not claim two descriptions are equivalent because a subset of low-energy fields looks similar

**Compactification Control:**

- State which moduli are stabilized, which remain flat, and what corrections are included
- Check flux quantization, tadpole constraints, and the scale hierarchy between moduli, KK, and string scales
- Four-dimensional EFT claims are only trustworthy below the KK and string thresholds and after truncation assumptions are stated

**Swampland and Phenomenology Discipline:**

- Distinguish no-go theorems, explicit constructions, and conjectural constraints
- Compare swampland reasoning against explicit string examples rather than presenting one side as settled
- For phenomenological claims, translate compactification data into observables instead of stopping at qualitative field-content statements

## Common Pitfalls

- **Confusing the `alpha'` expansion with the `g_s` expansion**
- **Ignoring ghosts, BRST cohomology, GSO projection, or modular invariance when discussing spectra or amplitudes**
- **Claiming moduli stabilization or de Sitter control without tadpole, hierarchy, and correction bookkeeping**
- **Treating swampland conjectures, de Sitter no-go claims, or landscape constructions as more settled than they are**
- **Importing AdS/CFT dictionary entries into generic compactifications or non-AdS backgrounds**
- **Assuming that a compactification's particle content automatically fixes its couplings and phenomenology**

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Exact worldsheet string theory** | Which AdS and flux backgrounds admit a controlled worldsheet description with exact spectra/correlators? | Eberhardt, Gaberdiel, Gopakumar, Troost | Good - consistency checks, CFT bookkeeping, and protected observables are central |
| **Flux compactification and moduli stabilization** | Which compactifications achieve controlled moduli stabilization with reliable scale separation? | Denef, Graña, Quevedo, McAllister | Good - hierarchy tracking and correction bookkeeping are a natural fit |
| **Precision string phenomenology** | How much of low-energy flavor, Yukawa, and hierarchy data can be computed from explicit compactifications? | Anderson, Berglund, Buchmuller, Nilles | Good - strongest when the geometry-to-observable pipeline is explicit |
| **Swampland and landscape** | Which low-energy constraints are universal to quantum gravity and which are framework-dependent? | Vafa, Palti, Hebecker, Rudelius, Walcher | Good - especially for separating conjecture, evidence, and counterexample classes |
| **String field theory / off-shell control** | How far can string field theory sharpen non-perturbative definitions, unitarity, and tachyon dynamics? | Sen, Zwiebach, Erler, Maccaferri | Moderate - formal structure is strong, but workflows are specialized |

## Methodology Decision Tree

```
What regime of string theory?
├── Perturbative spectrum, vertex operators, BRST, modular invariance
│   └── Worldsheet CFT / perturbative string theory
├── Open strings, D-branes, RR charge, gauge sectors, dualities
│   └── Branes and duality dictionary
├── 4d EFT from extra dimensions, fluxes, or Yukawa data
│   └── Compactification / moduli stabilization / string phenomenology
├── Strong coupling with a sharp boundary dual
│   └── Holography / AdS-CFT
├── Conjectural EFT consistency criteria
│   └── Swampland reasoning + explicit string constructions
└── Off-shell or non-perturbative formalism
    └── String field theory (also load `references/subfields/string-field-theory.md`)
```

## Common Collaboration Patterns

- **String theory + quantum gravity:** Use `references/subfields/quantum-gravity.md` when the core question is holography, black-hole information, or semiclassical gravity rather than string-specific worldsheet or compactification structure
- **String theory + particle phenomenology:** Compactification data, selection rules, and Yukawas often feed directly into `references/protocols/phenomenology.md`
- **String theory + cosmology:** de Sitter, inflation, axions, and moduli cosmology need `references/protocols/de-sitter-space.md` plus explicit compactification control
- **String theory + mathematical physics:** Mirror symmetry, topological strings, modular forms, and category-theoretic structure often need `references/subfields/mathematical-physics.md` alongside this guide

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One controlled sector or one compactification family | "BRST and modular-invariance analysis of a worldsheet background" |
| **Postdoc** | New calculational control or explicit phenomenological pipeline | "Controlled moduli stabilization and Yukawa extraction in a compactification class" |
| **Faculty** | New duality framework, broader landscape result, or non-perturbative definition | "A robust criterion separating absolute from framework-dependent swampland constraints" |
