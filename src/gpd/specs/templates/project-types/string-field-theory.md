---
template_version: 1
---

# String Field Theory Project Template

Default project structure for string field theory: worldsheet input, BRST and ghost structure, open/closed or superstring formulations, homotopy-algebra identities, gauge fixing, level truncation or analytic solutions, and benchmark observables such as tachyon condensation, marginal deformations, and off-shell amplitudes.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Formulation Choice** - Identify the relevant SFT formulation, benchmark results, and conventions
- [ ] **Phase 2: Worldsheet Input and State Space** - Fix the background CFT, BRST operator, ghost/picture assignments, and admissible state space
- [ ] **Phase 3: Action and Algebraic Structure** - Write the action, products, and gauge structure in the chosen formulation
- [ ] **Phase 4: Gauge Fixing and Solution Strategy** - Choose analytic or truncation-based methods and establish solver control
- [ ] **Phase 5: Observables and Benchmarks** - Compute tachyon, marginal, amplitude, or boundary-state observables
- [ ] **Phase 6: Validation and Interpretation** - Verify gauge invariance, convergence, and physical interpretation
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting the formulation, checks, and results

## Phase Details

### Phase 1: Literature and Formulation Choice

**Goal:** Fix the exact SFT framework and identify the canonical benchmark literature for the sector of interest
**Success Criteria:**

1. [Open/closed, bosonic/super, and sector choice fixed]
2. [Formulation fixed: cubic, WZW-like, `A_infinity`, `L_infinity`, or 1PI]
3. [Canonical benchmark papers and observables catalogued]
4. [Conventions fixed: `alpha'`, `g_s`, ghost number, picture number, BPZ/reality]

Plans:

- [ ] 01-01: [Survey the canonical SFT literature for the chosen sector]
- [ ] 01-02: [Lock conventions and benchmark observables in CONVENTIONS.md]

### Phase 2: Worldsheet Input and State Space

**Goal:** Define the worldsheet background and the allowed string fields and gauge parameters
**Success Criteria:**

1. [Matter + ghost CFT and BRST operator specified]
2. [Hilbert-space choice fixed: small or large Hilbert space where relevant]
3. [Ghost number, picture number, Grassmann parity, and Chan-Paton structure assigned]
4. [Closed-string constraints or Ramond-sector constraints stated explicitly]

Plans:

- [ ] 02-01: [Define the background CFT, BRST charge, and constraint subspace]
- [ ] 02-02: [Catalogue allowed fields, gauge parameters, and quantum-number assignments]

### Phase 3: Action and Algebraic Structure

**Goal:** Build the action and verify the multilinear products and gauge transformations
**Success Criteria:**

1. [Action written explicitly in the chosen formulation]
2. [Gauge transformations stated with all products and constraints]
3. [BPZ cyclicity or symplectic-form cyclicity verified]
4. [`A_infinity` / `L_infinity` / BV identities verified for the products used]

Plans:

- [ ] 03-01: [Write the action and gauge transformations]
- [ ] 03-02: [Verify algebraic identities and cyclicity]

### Phase 4: Gauge Fixing and Solution Strategy

**Goal:** Establish an analytic or numerical strategy with controlled gauge and truncation choices
**Success Criteria:**

1. [Gauge choice fixed and justified]
2. [Truncation or analytic ansatz documented]
3. [Solver or algebraic pipeline reproducible]
4. [A convergence or consistency plan exists before physics claims are made]

Plans:

- [ ] 04-01: [Choose and justify gauge fixing or analytic ansatz]
- [ ] 04-02: [Implement level truncation, wedge-state algebra, or shifted-background pipeline]

### Phase 5: Observables and Benchmarks

**Goal:** Compute the target observable and compare with canonical SFT benchmarks
**Success Criteria:**

1. [Target observable computed: vacuum energy, Ellwood invariant, amplitude, or deformation modulus]
2. [Benchmark comparison performed against known results]
3. [Gauge-invariant observables extracted where possible]
4. [Background interpretation stated clearly]

Plans:

- [ ] 05-01: [Compute the target observable]
- [ ] 05-02: [Compare with benchmark solutions and worldsheet expectations]

### Phase 6: Validation and Interpretation

**Goal:** Establish that the result is not a gauge or truncation artifact and interpret the background correctly
**Success Criteria:**

1. [BRST, ghost/picture, and cyclicity checks pass]
2. [Gauge choice and truncation dependence characterized]
3. [Physical interpretation distinguishes rigorous from truncation-limited claims]
4. [Open/closed or boundary-state interpretation checked where relevant]

Plans:

- [ ] 06-01: [Run final algebraic and truncation checks]
- [ ] 06-02: [Write the physical interpretation and scope limits]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with explicit formulation and convention statements]
2. [All benchmark checks and convergence evidence documented]
3. [Comparison with canonical SFT literature clearly stated]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 1 expanded:** Compare cubic, WZW-like, `A_infinity`, `L_infinity`, and 1PI formulations before locking the main route.
- **Phase 4 branches:** Explore both analytic and level-truncation strategies when both are viable.
- **Extra phase option:** Add "Phase 4.5: Formulation Comparison" if multiple formalisms claim the same observable.

### Exploit Mode
- **Phase 1 compressed:** Use the standard formulation already established for the target problem.
- **Phase 4 focused:** Pick one gauge/truncation or one analytic ansatz and push it through.
- **Skip Phase 7:** If results feed into a larger project, write `SUMMARY.md` rather than a full manuscript.

### Adaptive Mode
- Start in explore while formulation and gauge choices are unsettled.
- Switch to exploit once the algebraic framework and benchmark checks are fixed.

---

## Standard Verification Checks for String Field Theory

See `references/verification/domains/verification-domain-string-field-theory.md` for string-field-theory-specific checks and `references/verification/core/verification-core.md` for universal physics checks.

- BRST nilpotency and admissible state-space constraints
- Ghost-number and picture-number consistency
- BPZ cyclicity and homotopy-algebra identities
- Gauge-fixing admissibility and truncation convergence
- Benchmark agreement with tachyon-condensation, marginal-deformation, or amplitude results

---

## Common Pitfalls for String Field Theory

1. **Formulation mixing:** Combining cubic, WZW-like, and `A_infinity` formulas without translating conventions.
2. **Ghost/picture mistakes:** The most common source of apparently nonzero but actually illegal terms.
3. **Gauge-artifact physics:** Reading too much into a gauge-fixed or low-level-truncation result.
4. **PCO ambiguity:** Treating picture-changing insertions as harmless when they control singularity structure.
5. **Background misidentification:** Claiming a new background without gauge-invariant observables or boundary-state data.

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. String field theory projects should populate:

- **Units:** whether `alpha' = 1`, `alpha' = 2`, or another normalization
- **String coupling:** `g_s` normalization and relation to any action prefactors
- **Hilbert space:** small vs large Hilbert space
- **Ghost number:** field and gauge-parameter assignments
- **Picture number:** NS/R sector assignments and PCO convention
- **BPZ / reality:** conjugation and reality condition
- **Gauge choice:** Siegel, Schnabl, or unfixed
- **Truncation scheme:** level definition and maximum level
- **Closed-string constraints:** level matching and `b_0^-`, `L_0^-` if relevant

---

## Computational Environment

**Symbolic work:**

- `Mathematica` — oscillator algebra, conformal maps, wedge-state and level-truncation manipulations
- `Cadabra` — graded tensor and BRST algebra
- `SageMath` / `sympy` — homological algebra, symbolic manipulation, custom basis generation

**Numerical work:**

- `numpy`, `scipy`, `mpmath` — sparse linear algebra, continuation methods, high-precision convergence studies
- Custom scripts for oscillator-basis bookkeeping and level truncation

**Practical note:** Serious SFT projects usually require custom symbolic code tuned to the chosen formulation and basis.

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|------------------|-------------|
| Witten, *Noncommutative Geometry and String Field Theory* | Cubic open bosonic SFT | Foundational open SFT setup |
| Zwiebach, *Closed String Field Theory: Quantum Action and the Batalin-Vilkovisky Master Equation* | Closed-string BV structure | Closed SFT and moduli-space control |
| Berkovits, *Super-Poincare Invariant Superstring Field Theory* | WZW-like open superstring SFT | Open superstring setup |
| Sen and Zwiebach, *Tachyon Condensation in Open String Field Theory* | Canonical level-truncation benchmark | Tachyon vacuum studies |
| Schnabl, *Analytic Solution for Tachyon Condensation in Open String Field Theory* | Exact open-string benchmark solution | Analytic OSFT solutions |
| Fuchs, Kroyter, Potting, *A Review of Analytic Solutions in Open String Field Theory* | Modern review of open-string analytic solutions | Solution taxonomy and pitfalls |
| Sen and Zwiebach, *String Field Theory: A Review* | Broad modern review of the field | Current landscape and formulation map |
