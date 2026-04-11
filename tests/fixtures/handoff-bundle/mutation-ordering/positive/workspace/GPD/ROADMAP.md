# Roadmap: Extending the restricted QFC beyond braneworlds

## Overview

This roadmap treats the braneworld proof of rQFC as the benchmark anchor, then moves outward to the `Theta -> 0` limit and the latest non-braneworld tests. The project is complete only if it yields a concrete extension strategy or a sharp obstruction ledger grounded in those benchmark papers rather than in generic optimism about QNEC-like behavior.

## Contract Overview

| Contract Item | Advanced By Phase(s) | Status |
| ------------- | -------------------- | ------ |
| `claim-main` beyond-braneworld extension strategy | Phase 1, Phase 2, Phase 3, Phase 4 | Planned |
| `deliv-map` benchmark literature map | Phase 1, Phase 2 | Planned |
| `deliv-strategy` candidate strategy and failure modes | Phase 3, Phase 4 | Planned |
| `Ref-rqfc` braneworld benchmark anchor | Phase 1, Phase 3 | Planned |
| `Ref-inec` `Theta -> 0` anchor | Phase 2, Phase 3 | Planned |
| `Ref-tests` JT-gravity and d>2 anchor | Phase 2, Phase 3, Phase 4 | Planned |

## Phases

- [ ] **Phase 1: Benchmark braneworld rQFC proof and extract indispensable ingredients** - Produce the benchmark ingredient map and baseline assumptions.
- [ ] **Phase 2: Map non-braneworld evidence: Theta -> 0 limit, JT gravity, and d>2 consequences** - Build the benchmark comparison table for non-braneworld evidence.
- [ ] **Phase 3: Formulate and stress-test candidate beyond-braneworld extension strategy** - Convert the comparison map into a candidate minimal assumption set.
- [ ] **Phase 4: Verify consistency, record obstructions, and define next derivation targets** - Decide whether the extension strategy is viable or blocked and record the reason clearly.
- [ ] **Phase 5: Draft manuscript-level extension note and bibliography handoff** - Package the extension program into a manuscript-facing note once the obstruction ledger is stable.

## Phase Details

### Phase 1: Benchmark braneworld rQFC proof and extract indispensable ingredients

**Goal:** Reconstruct the proof logic of arXiv:2212.03881 and separate structural ingredients from braneworld-specific conveniences.
**Depends on:** Nothing
**Requirements:** DERV-01, DERV-02, VALD-01
**Contract Coverage:**
- Advances: `claim-main`, `deliv-map`
- Deliverables: benchmark ingredient map, assumption ledger
- Anchor coverage: `Ref-rqfc`
- Forbidden proxies: vague statements that the proof is "holographic" without isolating the exact dependence
**Success Criteria** (what must be TRUE):

1. Every explicit assumption in the benchmark proof is listed and categorized.
2. The map distinguishes indispensable versus plausibly replaceable ingredients.
3. The resulting note is detailed enough to use as the baseline comparison for later phases.
**Plans:** 3 plans

Plans:

- [ ] 01-01: Read and annotate the benchmark rQFC proof chain.
- [ ] 01-02: Classify proof steps as structural, technical, or braneworld-specific.
- [ ] 01-03: Record benchmark assumptions and comparison hooks for later phases.

### Phase 2: Map non-braneworld evidence: Theta -> 0 limit, JT gravity, and d>2 consequences

**Goal:** Translate the two main non-braneworld anchors into the same ingredient language built in Phase 1.
**Depends on:** Phase 1
**Requirements:** DERV-03, CALC-01, VALD-02
**Contract Coverage:**
- Advances: `claim-main`, `deliv-map`
- Deliverables: limiting-case interpretation note, JT/d>2 benchmark table
- Anchor coverage: `Ref-inec`, `Ref-tests`
- Forbidden proxies: treating the improved energy condition or JT success as automatic general proof
**Success Criteria** (what must be TRUE):

1. The `Theta -> 0` result is mapped to explicit structural inputs and outputs.
2. The JT-gravity proof and d>2 strengthened consequence are summarized in benchmark-comparison form.
3. Any mismatch with Phase 1 ingredients is named explicitly rather than blurred over.
**Plans:** 3 plans

Plans:

- [ ] 02-01: Extract the logical content of the `Theta -> 0` improved-energy-condition paper.
- [ ] 02-02: Compare the JT-gravity proof against the benchmark ingredient map.
- [ ] 02-03: Interpret the stronger d>2 consequence as a constraint on any extension strategy.

### Phase 3: Formulate and stress-test candidate beyond-braneworld extension strategy

**Goal:** Use the benchmark comparison map to formulate a candidate minimal assumption set for beyond-braneworld rQFC.
**Depends on:** Phase 1, Phase 2
**Requirements:** DERV-04, CALC-02, VALD-03
**Contract Coverage:**
- Advances: `claim-main`, `deliv-strategy`
- Deliverables: candidate ingredient set, compatibility table, failure-mode list
- Anchor coverage: `Ref-rqfc`, `Ref-inec`, `Ref-tests`
- Forbidden proxies: generic QNEC intuition without benchmark-by-benchmark support
**Success Criteria** (what must be TRUE):

1. The candidate strategy explicitly states its minimal assumptions.
2. Every assumption is checked against the benchmark, limiting-case, and non-braneworld anchors.
3. The strategy names where evidence is missing or where the logic is still conjectural.
**Plans:** 3 plans

Plans:

- [ ] 03-01: Draft the candidate minimal assumption set.
- [ ] 03-02: Stress-test the candidate set against all three benchmark anchors.
- [ ] 03-03: Separate viable structural assumptions from still-unjustified conjectural steps.

### Phase 4: Verify consistency, record obstructions, and define next derivation targets

**Goal:** Decide whether the candidate strategy is viable, partially viable, or blocked, and record the strongest obstruction if blocked.
**Depends on:** Phase 2, Phase 3
**Requirements:** VALD-04, ANLY-01
**Contract Coverage:**
- Advances: `claim-main`, `deliv-strategy`
- Deliverables: obstruction ledger, false-progress ledger, next-derivation queue
- Anchor coverage: all three benchmark references
- Forbidden proxies: concluding success from partial compatibility without a decisive obstruction audit
**Success Criteria** (what must be TRUE):

1. The final status is stated clearly: viable, partially viable, or blocked.
2. At least one decisive obstruction or missing proof target is recorded.
3. The next derivation target is concrete enough to seed the next phase of work.
**Plans:** 2 plans

Plans:

- [ ] 04-01: Cross-check the candidate strategy against known stronger-QFC failures and null limits.
- [ ] 04-02: Finalize the obstruction ledger and the next-derivation queue.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
| ----- | -------------- | ------ | --------- |
| 1. Benchmark braneworld rQFC proof and extract indispensable ingredients | 0/3 | Ready to plan | - |
| 2. Map non-braneworld evidence: Theta -> 0 limit, JT gravity, and d>2 consequences | 0/3 | Not started | - |
| 3. Formulate and stress-test candidate beyond-braneworld extension strategy | 0/3 | Not started | - |
| 4. Verify consistency, record obstructions, and define next derivation targets | 0/2 | Not started | - |
| 5. Draft manuscript-level extension note and bibliography handoff | 0/0 | Not started | - |

### Phase 5: Draft manuscript-level extension note and bibliography handoff

**Goal:** [To be planned]
**Depends on:** Phase 4
**Plans:** 0 plans

Plans:
- [ ] TBD (run plan-phase 5 to break down)
