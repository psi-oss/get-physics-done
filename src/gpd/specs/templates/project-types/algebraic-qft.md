---
template_version: 1
---

# Algebraic QFT Project Template

Default project structure for algebraic quantum field theory: Haag-Kastler or locally covariant nets, GNS representations, modular theory, von Neumann factor types, DHR sectors, split and duality properties, and benchmark structural theorems for relativistic QFT.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Axioms** - Fix the AQFT framework, benchmark theorems, and notation
- [ ] **Phase 2: Net and Representation Setup** - Define the net, the state, the GNS representation, and structural assumptions
- [ ] **Phase 3: Modular and Factor Structure** - Analyze modular objects, factor properties, and von Neumann type claims
- [ ] **Phase 4: Structural Theorems and Sectors** - Prove or verify duality, split/nuclearity, DHR, or inclusion statements
- [ ] **Phase 5: Model Benchmarks and Physical Interpretation** - Compare with standard AQFT results and extract the physical meaning
- [ ] **Phase 6: Validation and Paper Writing** - Consolidate proofs, checks, and narrative

## Phase Details

### Phase 1: Literature and Axioms

**Goal:** Fix the exact AQFT/operator-algebra framework and the canonical benchmark literature
**Success Criteria:**

1. [Spacetime category, region class, and net formalism fixed]
2. [Core axioms fixed: isotony, locality, covariance, additivity/time-slice, duality or split status]
3. [Canonical benchmark papers and theorems catalogued]
4. [Notation fixed for states, GNS triples, modular objects, and factor-type language]

Plans:

- [ ] 01-01: [Survey AQFT and operator-algebra literature relevant to the target theorem or model]
- [ ] 01-02: [Lock notation and structural assumptions in CONVENTIONS.md or NOTATION_GLOSSARY.md]

### Phase 2: Net and Representation Setup

**Goal:** Define the local net, the reference state, and the representation in which structural questions are asked
**Success Criteria:**

1. [Net `O -> A(O)` or locally covariant functor specified precisely]
2. [State `omega` and GNS triple `(pi_omega, H_omega, Omega_omega)` written explicitly]
3. [C*- vs von Neumann completion distinguished clearly]
4. [Cyclic/separating and positivity-of-energy hypotheses stated where needed]

Plans:

- [ ] 02-01: [Define the net and all structural assumptions]
- [ ] 02-02: [Construct or specify the relevant GNS representation and reference vector]

### Phase 3: Modular and Factor Structure

**Goal:** Establish the modular data and justify any factor-type classification
**Success Criteria:**

1. [Tomita operator, modular operator, and modular conjugation defined in the chosen setting]
2. [Any geometric interpretation of modular flow justified by theorem]
3. [Factor property checked via center triviality]
4. [Type `I/II/III` or `III_lambda` claim supported by trace/modular-spectrum criteria]

Plans:

- [ ] 03-01: [Compute or characterize modular data for the relevant algebra-state pair]
- [ ] 03-02: [Verify factor status and type-classification criteria]

### Phase 4: Structural Theorems and Sectors

**Goal:** Prove or verify the main AQFT structural statements
**Success Criteria:**

1. [Duality, split property, nuclearity, additivity, or time-slice claim established]
2. [DHR sector or charge structure formulated with correct localization assumptions]
3. [Subnet/subfactor or conformal-net inclusion structure written explicitly where relevant]
4. [All theorem hypotheses stated and checked]

Plans:

- [ ] 04-01: [Prove the structural theorem or verify its hypotheses in the model]
- [ ] 04-02: [Analyze sector, inclusion, or gauge-reconstruction structure if relevant]

### Phase 5: Model Benchmarks and Physical Interpretation

**Goal:** Anchor the structural result to standard AQFT benchmarks and explain its physical meaning
**Success Criteria:**

1. [Comparison with canonical benchmarks performed: Reeh-Schlieder, HHW/KMS, Bisognano-Wichmann, type `III_1` local algebras]
2. [Physical meaning of modular or factor-type statements explained without finite-dimensional shortcuts]
3. [Representation dependence of all claims made explicit]
4. [Connections to ordinary QFT, curved spacetime, conformal nets, or holography stated where relevant]

Plans:

- [ ] 05-01: [Benchmark the result against standard AQFT theorems]
- [ ] 05-02: [Write the physical interpretation and scope limits]

### Phase 6: Validation and Paper Writing

**Goal:** Produce publication-ready, structurally sound documentation

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [All structural assumptions, theorems, and representation choices are stated explicitly]
2. [All AQFT verification checks pass]
3. [Manuscript or summary clearly distinguishes theorem, assumption, and interpretation]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 1 expanded:** Compare multiple frameworks: Haag-Kastler, locally covariant AQFT, conformal nets, and sector-based approaches if relevant.
- **Phase 3 branches:** Compare modular-theoretic and direct operator-algebraic routes to the same factor-type claim.
- **Phase 4 extra branch:** If both sector and inclusion approaches exist, follow both and compare.

### Exploit Mode
- **Phase 1 compressed:** Use the standard framework already established for the target theorem or model.
- **Phase 4 focused:** Prove one structural claim cleanly rather than surveying neighboring frameworks.
- **Skip full manuscript:** If the result feeds into a larger project, write `SUMMARY.md` with theorem statements, hypotheses, and benchmark checks.

### Adaptive Mode
- Start in explore while the right AQFT framework and representation are unsettled.
- Switch to exploit once the net/state pair and the target structural theorem are fixed.

---

## Standard Verification Checks for Algebraic QFT

See `references/verification/domains/verification-domain-algebraic-qft.md` for AQFT-specific checks and `references/verification/core/verification-core.md` for universal checks.

- Haag-Kastler axiom bookkeeping
- GNS and cyclic/separating-vector discipline
- Modular-theory identification checks
- Factor-type and modular-spectrum justification
- Split, duality, nuclearity, and DHR verification

---

## Common Pitfalls for Algebraic QFT

1. **Type confusion:** Treating a local algebra as if it were a type-I tensor factor.
2. **Modular shorthand:** Equating modular flow with physical time or a boost with no theorem.
3. **Representation blindness:** Making a factor-type claim without naming the state and representation.
4. **Silent axioms:** Using split property, Haag duality, or nuclearity without stating them.
5. **Finite-dimensional entanglement intuition:** Importing reduced-density-matrix language into a type-III local setting without reinterpretation.

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Algebraic QFT projects should populate:

- **Spacetime and region class:** Minkowski vs curved, double cones vs wedges vs intervals
- **Net level:** C*-net, von Neumann net, or locally covariant functor
- **State choice:** vacuum, KMS, charged sector, boundary state
- **Representation:** vacuum GNS, thermal GNS, sector representation, universal representation
- **Modular notation:** `S`, `Delta`, `J`, relative modular operators
- **Type language:** factor, type `I/II/III`, `III_lambda`, hyperfinite/injective status
- **Duality/split/nuclearity assumptions:** assumed vs proved

---

## Computational Environment

**Proof-heavy work:**

- `Lean`, `Coq`, `Isabelle` — theorem organization and formal verification
- `SageMath` — algebraic experiments, category/index checks
- `Mathematica` / `Python` — toy-model symbolic checks for modular generators or simple examples

**Practical note:** Most AQFT work is dominated by precise theorem tracking rather than heavy numerics. The highest-value "tooling" is explicit bookkeeping of assumptions, representations, and theorem dependencies.

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|------------------|-------------|
| Haag and Kastler, *An Algebraic Approach to Quantum Field Theory* | Original local-net framework | Any Haag-Kastler setup |
| Haag, *Local Quantum Physics* | Standard AQFT monograph | Global framing and benchmark theorems |
| Haag, Hugenholtz, and Winnink, *On the Equilibrium States in Quantum Statistical Mechanics* | KMS/HHW equilibrium structure | Thermal-state and modular-equilibrium questions |
| Doplicher-Haag-Roberts papers | Superselection sectors and reconstruction | Charge and sector problems |
| Bisognano-Wichmann papers | Wedge modular flow and duality | Modular/geometric identifications |
| Driessler, local algebra type results | Type-`III` structure in relativistic QFT | Factor-type classification |
| Borchers, *On Revolutionizing Quantum Field Theory with Tomita's Modular Theory* | Modular-theory overview in QFT | Modular localization and structural interpretation |
| Yngvason, *The Role of Type III Factors in Quantum Field Theory* | Why local QFT algebras are type `III` | Von Neumann type questions |
| Brunetti et al. (eds.), *Advances in Algebraic Quantum Field Theory* | Modern AQFT reference volume | Current framework overview |
