# Research State

## Project Reference

See: GPD/PROJECT.md

**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`

**Core research question:** Which quantum-information ingredients are sufficient to recover the leading Ryu-Takayanagi formula, and which steps still require semiclassical gravitational input?
**Current focus:** Phase 02 — JLMS and operator algebra QEC backbone for entanglement wedge reconstruction

## Current Position

**Current Phase:** 02
**Current Phase Name:** JLMS and operator algebra QEC backbone for entanglement wedge reconstruction
**Total Phases:** 4
**Current Plan:** 0
**Total Plans in Phase:** 0
**Status:** Ready to plan
**Last Activity:** 2026-04-09

**Progress:** 25% (1 of 4 phases complete)

## Active Calculations

- Dependency map: RT leading term versus JLMS, OAQEC, and entanglement wedge reconstruction
- Heuristic gap audit: random tensor networks, Gao24 modular flow, and Bao25 multi-boundary ensemble advances

## Intermediate Results

- [R-01-01-8vira8e] Leading Ryu-Takayanagi formula for static semiclassical states: `S(A) = Area(gamma_A)/(4 G_N)` (units: dimensionless entropy, valid: static semiclassical AdS/CFT, phase 01, ✓, evidence: 1)
- [R-02-01-93spcbe] JLMS relative entropy equality in the semiclassical code-subspace regime: `S_rel^CFT(A) = S_rel^bulk(a)` (units: dimensionless relative entropy, valid: semiclassical code subspace, phase 02) [deps: R-01-01-8vira8e]
- [R-02-02-9boq83b] Entanglement wedge reconstruction follows from JLMS plus operator-algebra QEC in the code subspace: `O_a reconstructed from A` (units: conceptual statement, valid: semiclassical code subspace with subregion duality, phase 02) [deps: R-02-01-93spcbe]
- [R-03-01-9lv6dcc] Random tensor networks reproduce RT-like weighted-minimal-cut structure with a bulk entropy correction: `S(A) ≈ S_cut(A) + S_bulk` (units: dimensionless entropy, valid: large-bond-dimension tensor-network toy model, phase 03) [deps: R-01-01-8vira8e]
- [R-04-01-9qs2c18] Current frontier assessment: Bao25 supplies a restricted-scope derivation claim, but the generic gap remains the leading geometric area term: `General QI-only derivation remains unverified beyond special multi-boundary AdS3/CFT2 ensembles` (units: conceptual statement, valid: based on the current anchor set through Gao24 and Bao25, phase 04) [deps: R-02-02-9boq83b, R-03-01-9lv6dcc]

## Open Questions

- Can the leading area term be derived from quantum-information structure alone without importing semiclassical geometric input?
- Does Bao25 generalize beyond multi-boundary AdS3/CFT2 large-c ensemble states?
- How much of the JLMS plus operator-algebra QEC chain is logically independent of the RT formula itself?
- Which post-2024 modular-flow or entropy-inequality papers materially change the RT derivation question rather than only the reconstruction story?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 01]: Anchor the project on explicit arXiv references from RT06 through Bao25 — Keeps the RT-from-QI story tied to auditable literature rather than analogy-driven summaries
- [Phase 01]: Keep RT06 as benchmark input and do not collapse downstream reconstruction results into an origin derivation. — The current anchor chain still needs the leading semiclassical formula as a target rather than a consequence.
- [Phase 03]: Treat random tensor networks as heuristic support rather than a derivation of the area term — The toy model reproduces RT-like structure, but the geometric input is not eliminated and must stay visible as an imported assumption
- [Phase 04]: Treat Gao24 as reconstruction-side progress and Bao25 as a restricted-scope derivation claim, not a generic closure of the RT-origin problem — The frontier now contains real post-2024 progress, but its scope stays narrower than the full holographic derivation question.
- [Phase 04]: Working hypothesis: reconstruction and correction results remain more general than current derivations of the leading area term — Bao25 narrows the gap in a special AdS3/CFT2 ensemble, but it does not yet settle the generic holographic case.

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| ------------- | -------------- | --------------------- | ------------- | ------ |
| Semiclassical large-N bulk limit | large N, small G_N, code-subspace regime | 1/N and G_N | assumed baseline | Valid |
| Random tensor networks as heuristic stand-ins for geometry | structural intuition, not full derivation | fidelity of network-to-geometry mapping | heuristic only | Marginal |

**Convention Lock:**

- Metric signature: mostly-plus (-,+,+,+) for Lorentzian bulk conventions
- Natural units: hbar = c = k_B = 1
- Coordinate system: boundary time t with spatial region A; bulk AdS uses Poincare coordinates (z,t,vec{x}) unless a cited anchor specifies otherwise

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| ------- | ------------- | ----------- | -------------------- | ------ |
| QI-only derivation status of the RT area term | unresolved in general; special-case progress exists | high conceptual uncertainty | 01 | anchor-paper audit plus self-review update |
| Frontier literature coverage beyond 2024 | Gao24 and Bao25 verified; broader search still incomplete | moderate literature uncertainty | 01 | arXiv self-review scan |

### Pending Todos

None yet.

### Blockers/Concerns

None

## Session Continuity

**Last session:** 2026-04-09T12:24:31.346840+00:00
**Stopped at:** Session 5 probed repair paths, reran validators, audited dependency/state surfaces, and updated journal.md, report.md, and HANDOFF.md
**Resume file:** HANDOFF.md
**Last result ID:** R-04-01-9qs2c18
**Hostname:** Sergios-MacBook-Pro
**Platform:** Darwin 25.3.0 arm64
