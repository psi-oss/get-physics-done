# Roadmap: ML-Optimized Modular Bootstrap at Finite c

## Overview

This roadmap starts from literature anchoring rather than from code execution. The first goal is to lock the finite-c benchmark chain and the interpretation rules for ML-generated candidate spectra, then transition into workflow design and validation criteria for later numerical work.

## Contract Overview

| Contract Item | Advanced By Phase(s) | Status |
| ------------- | -------------------- | ------ |
| Finite-c benchmark chain | Phase 1, Phase 2, Phase 4 | Planned |
| ML candidate-spectrum diagnostics | Phase 3, Phase 5 | Planned |
| Overclaim guardrails | Phase 1, Phase 5 | Planned |
| Continuation path to reproducible numerics | Phase 3, Phase 4, Phase 5 | Planned |

## Phases

- [ ] **Phase 1: Literature and contract anchoring** - Fix the benchmark chain and define what later claims must be compared against
- [ ] **Phase 2: Finite-c benchmarks and conventions** - Align notation, observables, and scope across the decisive references
- [ ] **Phase 3: ML-optimized workflow design** - Specify what a trustworthy search pipeline would need to report
- [ ] **Phase 4: Candidate-spectrum and gap-constraint synthesis** - Compare the finite-c benchmark chain and the 1 < c <= 8/7 candidate window
- [ ] **Phase 5: Validation, uncertainties, and continuation plan** - Convert the literature synthesis into executable next steps and explicit guardrails

## Phase Details

### Phase 1: Literature and contract anchoring

**Goal:** Lock the finite-c modular-bootstrap benchmark chain and the skeptical reading standard for ML-generated candidates
**Depends on:** None
**Requirements:** CALC-01, ANLY-01
**Contract Coverage:**
- Advances: finite-c benchmark chain, overclaim guardrails
- Deliverables: `GPD/literature/finite-c-modular-bootstrap.md`
- Anchor coverage: arXiv:1307.6562, arXiv:1608.06241, arXiv:1903.06272, arXiv:2308.08725, arXiv:2308.11692, arXiv:2604.01275
- Forbidden proxies: low-loss candidate spectra without diagnostics
**Success Criteria** (what must be TRUE):

1. The decisive benchmark papers are in one anchored registry.
2. The latest ML paper is positioned relative to earlier non-ML work.
3. False progress modes are stated explicitly.
   **Plans:** 0 plans

Plans:

- [ ] TBD (run plan-phase 1 to break down)

### Phase 2: Finite-c benchmarks and conventions

**Goal:** Make all benchmark statements comparable by locking notation, central-charge semantics, and the main observables
**Depends on:** Phase 1
**Requirements:** DERV-01, VALD-03
**Contract Coverage:**
- Advances: convention lock, finite-c benchmark chain
- Deliverables: `GPD/CONVENTIONS.md`
- Anchor coverage: gap definition, state normalization, central-charge meaning of c
- Forbidden proxies: comparing results with inconsistent Delta_gap conventions
**Success Criteria** (what must be TRUE):

1. The convention ledger covers the project-critical finite-c definitions.
2. Central charge c is never confused with an unrelated unit symbol.
3. The benchmark equations are transcribed in a consistent notation.
   **Plans:** 0 plans

Plans:

- [ ] TBD (run plan-phase 2 to break down)

### Phase 3: ML-optimized workflow design

**Goal:** Define what a trustworthy ML-style finite-c modular-bootstrap run would have to report
**Depends on:** Phase 2
**Requirements:** CALC-02, ANLY-02
**Contract Coverage:**
- Advances: ML candidate-spectrum diagnostics
- Deliverables: `GPD/phases/03-ml-optimized-workflow-design/README.md`
- Anchor coverage: truncation uncertainty, integrality, geometric cross-checks
- Forbidden proxies: one-shot loss minimization with no residual audit
**Success Criteria** (what must be TRUE):

1. Required diagnostics are named before any new run is attempted.
2. Integrality and geometric checks are represented as part of the workflow.
3. The continuation path to reproducible numerics is explicit.
   **Plans:** 0 plans

Plans:

- [ ] TBD (run plan-phase 3 to break down)

### Phase 4: Candidate-spectrum and gap-constraint synthesis

**Goal:** Compare the finite-c gap narrative and the ML candidate window in one benchmark table
**Depends on:** Phase 3
**Requirements:** DERV-02, ANLY-01
**Contract Coverage:**
- Advances: finite-c benchmark chain, candidate-spectrum interpretation
- Deliverables: `GPD/phases/04-candidate-spectrum-and-gap-constraint-synthesis/benchmark-gap-comparison.md`
- Anchor coverage: Delta_gap benchmarks, geometric threshold window, ML candidate window
- Forbidden proxies: quoting the 1 < c <= 8/7 window as proof of exact new CFTs
**Success Criteria** (what must be TRUE):

1. The benchmark table states what is bound, what is candidate, and what remains conjectural.
2. Dependencies among the tracked results are visible.
3. The near-c=1 story is described without mixing methods or conventions.
   **Plans:** 0 plans

Plans:

- [ ] TBD (run plan-phase 4 to break down)

### Phase 5: Validation, uncertainties, and continuation plan

**Goal:** Convert the current synthesis into explicit next-step checks and continuation criteria
**Depends on:** Phase 4
**Requirements:** VALD-01, VALD-02
**Contract Coverage:**
- Advances: diagnostics checklist, continuation path
- Deliverables: `GPD/phases/05-validation-uncertainties-and-continuation-plan/ml-diagnostics-checklist.md`
- Anchor coverage: uncertainty language, overclaim guardrails, reproducibility path
- Forbidden proxies: claiming completion when only literature synthesis exists
**Success Criteria** (what must be TRUE):

1. Minimum diagnostics for future ML runs are written down.
2. Current uncertainties are named rather than hidden.
3. The next command-level action is explicit.
   **Plans:** 0 plans

Plans:

- [ ] TBD (run plan-phase 5 to break down)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
| ----- | -------------- | ------ | --------- |
| 1. Literature and contract anchoring | 0/0 | Pending | - |
| 2. Finite-c benchmarks and conventions | 0/0 | Pending | - |
| 3. ML-optimized workflow design | 0/0 | Pending | - |
| 4. Candidate-spectrum and gap-constraint synthesis | 0/0 | Pending | - |
| 5. Validation, uncertainties, and continuation plan | 0/0 | Pending | - |
