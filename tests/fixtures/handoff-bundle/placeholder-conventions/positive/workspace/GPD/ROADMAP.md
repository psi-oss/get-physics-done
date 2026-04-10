# Roadmap: Quantum-Information Route To The Ryu-Takayanagi Formula

## Overview

This roadmap tracks a staged investigation of whether the leading Ryu-Takayanagi formula can be recovered from quantum-information structure, and where the existing literature still imports semiclassical gravity. The phase list is intentionally populated through `gpd phase add` so that the resulting roadmap and directories are created through GPD’s own phase machinery rather than by manual editing alone.

## Contract Overview

| Contract Item | Advanced By Phase(s) | Status |
| ------------- | -------------------- | ------ |
| RT dependency map | 1, 2, 3 | Planned |
| Frontier gap analysis | 4 | Planned |
| False-progress rejection criteria | 3, 4 | Planned |

## Phases

- [x] **Phase 1: Literature and anchor map for RT from quantum information** - Establish the anchor papers and the baseline derivation question. (completed 2026-04-09)
- [ ] **Phase 2: JLMS and operator-algebra QEC backbone for entanglement wedge reconstruction** - Separate reconstruction logic from assumptions already importing RT.
- [ ] **Phase 3: Tensor-network and entropy-inequality routes to the RT formula** - Test which quantum-information toy models genuinely explain the area term and which only mimic it.
- [ ] **Phase 4: Frontier gap analysis for modular flow and post-2024 advances** - Identify which recent results sharpen the open problem and which leave the leading-area gap intact.

## Phase Details

### Phase 1: Literature and anchor map for RT from quantum information

**Goal:** Fix the non-negotiable literature anchors and separate the derivation question from adjacent reconstruction and correction questions.
**Depends on:** None
**Requirements:** `DERV-01`, `VALD-01`
**Contract Coverage:**
- Advances: RT dependency map
- Deliverables: anchor audit, dependency baseline
- Anchor coverage: RT06, ADH14, JLMS15, DHW16, RTN16, Gao24
- Forbidden proxies: unanchored synthesis claims
**Success Criteria** (what must be TRUE):

1. The core anchor papers are catalogued and tied to the project contract.
2. The difference between RT origin, bulk corrections, and wedge reconstruction is explicit.
3. Open research questions are phrased against concrete anchors rather than general intuition.

**Plans:** 1/1 plans complete

Plans:
- [x] TBD (run plan-phase 1 to break down) (completed 2026-04-09)

### Phase 2: JLMS and operator-algebra QEC backbone for entanglement wedge reconstruction

**Goal:** Determine how far JLMS and OAQEC go toward explaining RT before the area term has already been assumed.
**Depends on:** Phase 1
**Requirements:** `DERV-01`
**Contract Coverage:**
- Advances: RT dependency map
- Deliverables: JLMS/OAQEC dependency note
- Anchor coverage: ADH14, JLMS15, DHW16
- Forbidden proxies: treating wedge reconstruction as the derivation of RT
**Success Criteria** (what must be TRUE):

1. The logical dependence of entanglement wedge reconstruction on RT/JLMS assumptions is explicit.
2. Reconstruction and relative-entropy arguments are separated from the origin of the area term.
3. Any residual gravitational input is named, not hidden inside the formalism.

**Plans:** 0 plans

Plans:
- [ ] TBD (run plan-phase 2 to break down)

### Phase 3: Tensor-network and entropy-inequality routes to the RT formula

**Goal:** Test whether tensor-network and entropy-inequality arguments derive the leading area term or only provide controlled heuristics.
**Depends on:** Phase 2
**Requirements:** `DERV-02`, `VALD-02`
**Contract Coverage:**
- Advances: RT dependency map, false-progress rejection criteria
- Deliverables: heuristic-gap audit
- Anchor coverage: RTN16 and related entropy-inequality work
- Forbidden proxies: minimal-cut analogy treated as proof
**Success Criteria** (what must be TRUE):

1. Imported geometric assumptions in the tensor-network story are explicitly listed.
2. The entropy-inequality story is classified as derivation, heuristic support, or consistency check.
3. False-progress modes are recorded in language strong enough for later verification.

**Plans:** 0 plans

Plans:
- [ ] TBD (run plan-phase 3 to break down)

### Phase 4: Frontier gap analysis for modular flow and post-2024 advances

**Goal:** Assess whether recent modular-flow and related results narrow the derivation gap or only strengthen the post-RT reconstruction picture.
**Depends on:** Phase 3
**Requirements:** `ANAL-01`, `VALD-02`
**Contract Coverage:**
- Advances: frontier gap analysis, false-progress rejection criteria
- Deliverables: frontier gap map and working hypothesis
- Anchor coverage: Gao24, Bao25, plus any newer confirmed arXiv anchors
- Forbidden proxies: calling a paper “frontier progress” without checking what question it actually answers
**Success Criteria** (what must be TRUE):

1. Recent papers are classified by what problem they actually solve.
2. The remaining gap in the origin of the leading area term is stated precisely.
3. The project ends with concrete next-step research directions rather than a generic literature summary.

**Plans:** 0 plans

Plans:
- [ ] TBD (run plan-phase 4 to break down)

## Progress

**Execution Order:**
Phases execute in numeric order: `01 -> 02 -> 03 -> 04`

| Phase | Plans Complete | Status | Completed |
| ----- | -------------- | ------ | --------- |
| 1. Literature and anchor map for RT from quantum information | 1/1 | Complete    | 2026-04-09 |
| 2. JLMS and operator-algebra QEC backbone for entanglement wedge reconstruction | 0/0 | Not started | - |
| 3. Tensor-network and entropy-inequality routes to the RT formula | 0/0 | Not started | - |
| 4. Frontier gap analysis for modular flow and post-2024 advances | 0/0 | Not started | - |
