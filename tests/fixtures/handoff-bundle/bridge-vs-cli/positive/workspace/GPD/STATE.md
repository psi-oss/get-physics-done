# Research State

## Project Reference

See: GPD/PROJECT.md

**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`

**Core research question:** Which boundary observables distinguish genuine singularity resolution from singularity encoding or coarse-graining in holographic cosmologies built from entangled CFT states?
**Current focus:** Phase 01 literature anchors and diagnostic framing

## Current Position

**Current Phase:** 01
**Current Phase Name:** Core holographic constructions and anchor papers
**Total Phases:** 4
**Current Plan:** 1
**Total Plans in Phase:** 1
**Status:** Complete
**Last Activity:** 2026-04-09

**Progress:** [██████████] 100%

## Active Calculations

- Formulate a candidate criterion separating resolved singularities from encoded-but-unresolved singularities.

## Intermediate Results

- [R-01-ENT-PROBE] Microstate-cosmology anchor from arXiv:1810.10601: `S_A(t) for sufficiently large boundary subregions probes behind-the-horizon FRW evolution` (units: qualitative observable relation, valid: within the holographic microstate constructions discussed in arXiv:1810.10601, phase 01, ✓, evidence: 1)
- [R-01-CONF-COSMO] Conceptual confinement-to-cosmology bridge from arXiv:2102.05057: `Euclidean confinement or wormhole saddles admit Lorentzian big-bang or big-crunch cosmological continuations` (units: qualitative construction statement, valid: within the class of holographic models described in arXiv:2102.05057, phase 01, ✓, evidence: 1)
- [R-01-BCFT-BRANE] Doubly-holographic braneworld anchor from arXiv:2405.18465: `A BCFT strip path integral encodes a braneworld big-bang or big-crunch cosmology and a wormhole as different continuations of the same Euclidean saddle` (units: qualitative duality statement, valid: within the magnetic braneworld and BCFT strip construction of arXiv:2405.18465, phase 01, ✓, evidence: 1) [deps: R-01-CONF-COSMO]
- [R-01-CLOSED-ENCODING] Closed-universe encoding limit from arXiv:2507.10649: `With sufficient bulk entanglement the closed-universe Hilbert space is encoded in the CFT, while the no-entanglement limit breaks direct holographic access` (units: qualitative encoding statement, valid: within the closed-universe holographic framework of arXiv:2507.10649, phase 01, ✓, evidence: 1)
- [R-01-DIAGNOSTIC-SPLIT] Bootstrap synthesis distinguishing resolution from encoding and coarse-grained access: `Current anchor papers support encoding and access claims more strongly than direct singularity-resolution claims` (units: qualitative synthesis statement, valid: within the bootstrap comparison of the five anchor papers, phase 01) [deps: R-01-ENT-PROBE, R-01-BCFT-BRANE, R-01-CLOSED-ENCODING]

## Open Questions

- Which observable provides the sharpest cross-model singularity diagnostic?
- Does entanglement modify the singularity itself or only the degree of CFT access to it?
- How closely can final-state projection be matched to ETW-brane or braneworld descriptions?
- Which boundary observable is the cleanest singularity diagnostic across microstate, braneworld, wormhole, and closed-universe constructions?
- Does bulk entanglement change the fate of the cosmological singularity itself, or only the degree of CFT access to crunch data?
- Can the closed-universe final-state projection picture be matched concretely to ETW-brane or braneworld descriptions?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 01]: Use a literature-first observable taxonomy before any new singularity claim. — The anchor papers mix geometric, informational, and observer-access language; the project needs a common diagnostic vocabulary first.
- [Phase 01]: Keep direct resolution, encoded singularity, and observer-limited access as distinct claim levels. — The anchor papers do not support collapsing those categories into one generic holographic success claim.
- [Phase 01]: Keep R-01-DIAGNOSTIC-SPLIT provisional after Phase 01 execution. — The executed summary still lacks a cross-model observable that rules out an unresolved singularity.

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| ------------- | -------------- | --------------------- | ------------- | ------ |
| Semiclassical large-N bulk description | large N, strong coupling, controlled higher-derivative corrections | 1/N and 1/lambda corrections | qualitative only in bootstrap phase | active |
| Observable-first comparison across non-identical holographic models | only for papers with explicit boundary observables or access claims | fidelity of source-level observable matching | moderate confidence | active |

**Convention Lock:**

- Metric signature: (-,+,+,+) and analogous mostly-plus extension in AdS_5
- Natural units: hbar = c = k_B = 1
- Coordinate system: boundary time t, FRW proper time tau, and explicit AdS radial coordinate only when fixed by the cited paper

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| ------- | ------------- | ----------- | -------------------- | ------ |
| singularity diagnostic sharpness | underdetermined at bootstrap | high | 01 | cross-paper comparison before dedicated derivation |
| interpretation of closed-universe encoding limit | contested | medium-high | 01 | comparison of arXiv:2507.10649 with earlier microstate and wormhole papers |

### Pending Todos

None yet.

### Blockers/Concerns

None

## Session Continuity

**Last session:** 2026-04-09T07:42:12.351589+00:00
**Stopped at:** 2026-04-09T07:40:15Z
**Resume file:** HANDOFF.md
**Last result ID:** R-01-DIAGNOSTIC-SPLIT
**Hostname:** Sergios-MacBook-Pro
**Platform:** Darwin 25.3.0 arm64
