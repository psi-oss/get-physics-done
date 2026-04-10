# Requirements: Cosmological singularity from entangled CFTs

**Defined:** 2026-04-09
**Core Research Question:** Which boundary observables distinguish genuine singularity resolution from singularity encoding or coarse-graining in holographic cosmologies built from entangled CFT states?

## Primary Requirements

### Derivations

- [ ] **DERV-01**: Define a precise taxonomy separating singularity resolution, singularity encoding, and observer-limited access.
- [ ] **DERV-02**: Derive the common boundary-to-bulk dictionary elements that each anchor construction uses to access the cosmological region.
- [ ] **DERV-03**: Identify the entanglement-dependent regime changes that matter for closed universes, wormholes, and microstate cosmologies.

### Calculations

- [ ] **CALC-01**: Extract the singularity-relevant observables from each anchor paper and place them in a single comparison table.
- [ ] **CALC-02**: Track how large-subsystem entanglement, BCFT strip data, and final-state data map onto interior cosmological information.
- [ ] **CALC-03**: Formulate one candidate singularity diagnostic that could be used in a follow-up derivation phase.

### Analysis

- [ ] **ANLY-01**: Compare the microstate, random-entanglement, braneworld, and closed-universe constructions on equal footing.
- [ ] **ANLY-02**: Identify which claims in the literature are about geometry, which are about encoding, and which are about coarse-grained observables.
- [ ] **ANLY-03**: Produce a skeptical note describing what the current literature still does not establish.

### Validations

- [ ] **VALD-01**: Recover the behind-the-horizon entanglement probe claim from arXiv:1810.10601 in the language of the project taxonomy.
- [ ] **VALD-02**: Verify that the braneworld construction in arXiv:2405.18465 reduces to the confinement/cosmology logic of arXiv:2102.05057.
- [ ] **VALD-03**: Verify that the closed-universe encoding story in arXiv:2507.10649 reproduces the no-entanglement breakdown limit it claims.

## Follow-up Requirements

### Extensions

- **EXT-01**: Test the candidate singularity diagnostic in a concrete toy model or simplified holographic setup.
- **EXT-02**: Connect the diagnostic to coarse-grained observables that can be computed beyond the literature review phase.

## Out of Scope

| Topic | Reason |
| ----- | ------ |
| New UV completion of the crunch | requires a deeper string-theory construction than the current phase targets |
| Full Lorentzian bulk simulation | not needed to settle the bootstrap diagnostic question |
| Non-holographic cosmological singularities | outside the entangled-CFT scope |

## Accuracy and Validation Criteria

| Requirement | Accuracy Target | Validation Method |
| ----------- | --------------- | ----------------- |
| CALC-01 | No anchor paper omitted | direct paper-by-paper cross-check against the literature table |
| DERV-01 | Conceptual definitions remain mutually exclusive | compare every later claim against the taxonomy |
| VALD-01 | No change in the meaning of the original observable | read the cited abstract and paper discussion against the summary |
| VALD-03 | Preserve the stated entanglement/no-entanglement limit | compare the project note to the cited source statement |

## Contract Coverage

| Requirement | Decisive Output / Deliverable | Anchor / Benchmark / Reference | Prior Inputs / Baselines | False Progress To Reject |
| ----------- | ----------------------------- | ------------------------------ | ------------------------ | ------------------------ |
| CALC-01 | `GPD/literature/SINGULARITY-DIAGNOSTICS.md` | arXiv:1810.10601, arXiv:2206.14821, arXiv:2405.18465, arXiv:2507.10649 | bootstrap literature notes | qualitative narrative without per-paper observable mapping |
| DERV-01 | taxonomy section in `GPD/literature/SUMMARY.md` | all anchor papers | project contract and journal | using "resolution" and "encoding" interchangeably |
| ANLY-03 | skeptical note in `GPD/literature/PITFALLS.md` | arXiv:2507.10649 and arXiv:1810.10601 | bootstrap comparison table | claiming a settled conclusion while unresolved access issues remain |
| VALD-02 | comparison note in `GPD/literature/PRIOR-WORK.md` | arXiv:2102.05057, arXiv:2405.18465 | none | treating the braneworld model as conceptually unrelated to confinement |

## Traceability

| Requirement | Phase | Status |
| ----------- | ----- | ------ |
| DERV-01 | Phase 1: Core holographic constructions and anchors | Pending |
| CALC-01 | Phase 2: Boundary observables and singularity diagnostics | Pending |
| ANLY-01 | Phase 3: Cross-model synthesis | Pending |
| VALD-01 | Phase 3: Cross-model synthesis | Pending |
| CALC-03 | Phase 4: Candidate criterion and next-step verification targets | Pending |

**Coverage:**

- Primary requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---

_Requirements defined: 2026-04-09_
_Last updated: 2026-04-09 after bootstrap_
