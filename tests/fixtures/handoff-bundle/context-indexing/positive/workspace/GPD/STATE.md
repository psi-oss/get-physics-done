# Research State

## Project Reference

See: GPD/PROJECT.md

**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`

**Core research question:** Can ML-optimized modular-bootstrap searches in the finite-central-charge window 1 < c <= 8/7 reproduce or sharpen the established Virasoro gap constraints without overclaiming exact CFT existence?
**Current focus:** Phase 01: Literature and contract anchoring

## Current Position

**Current Phase:** 01
**Current Phase Name:** Literature and contract anchoring
**Total Phases:** 5
**Current Plan:** —
**Total Plans in Phase:** —
**Status:** Ready to plan
**Last Activity:** 2026-04-09

**Progress:** [░░░░░░░░░░] 0%

## Active Calculations

None yet.

## Intermediate Results

- [R-01-foundation] Foundational modular-invariance constraint for 2d CFT partition functions from arXiv:1307.6562: `Z(\tau,\bar\tau) = Z(-1/\tau,-1/\bar\tau)` (units: dimensionless, valid: unitary compact 2d CFTs, phase 01)
- [R-02-gap-bound] Canonical near-c=1 finite-c gap benchmark from arXiv:1608.06241: `\Delta_{\rm gap} \le c/6 + 1/3` (units: dimensionless, valid: finite-c Virasoro modular bootstrap near c=1, phase 02, ✓, evidence: 1) [deps: R-01-foundation]
- [R-03-integrality] Integrality can slightly strengthen the near-c=1 numerical upper bound, per arXiv:2308.08725: `(schematic) \Delta_{\rm gap}^{\rm int}(c\approx 1) < \Delta_{\rm gap}^{\rm 2016}` (units: dimensionless, valid: finite-c regime with integrality assumptions, phase 03) [deps: R-02-gap-bound]
- [R-04-geometry] Geometric modular-bootstrap threshold window from arXiv:2308.11692: `(c-1)/12 < \Delta_{\rm gap}^* < c/12` (units: dimensionless, valid: spinless geometric modular-bootstrap analysis, phase 03) [deps: R-02-gap-bound]
- [R-05-ml-window] ML-optimized search window with candidate truncated spectra reported in arXiv:2604.01275: `1 < c \le 8/7` (units: dimensionless, valid: candidate finite-c Virasoro spectra only, phase 04) [deps: R-03-integrality, R-04-geometry]

## Open Questions

- Which diagnostics best separate genuine nearby CFT solutions from optimizer artifacts in the 1 < c <= 8/7 window?
- How much of the near-c=1 gap improvement survives once truncation and integrality systematics are combined?
- Can the continuous family suggested by the 2026 ML paper be constrained further by analytic or geometric bootstrap input?
- Can the candidate spectra reported for 1 < c <= 8/7 survive stricter truncation and integrality diagnostics?
- Can integrality and geometric constraints be integrated directly into an ML search objective?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 01]: Use finite central charge as the meaning of c throughout the project — Prevents notation drift and keeps the benchmark chain coherent
- [Phase 01]: Treat ML-generated spectra as candidates until non-ML diagnostics agree — Low loss alone is not enough evidence for an exact CFT

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| ------------- | -------------- | --------------------- | ------------- | ------ |
| Truncated primary spectrum | Finite-c candidate searches with explicit truncation audit | N_trunc | not fixed yet | active |
| Virasoro-only chiral algebra | Current project scope | scope choice | fixed | active |

**Convention Lock:**

- Metric signature: Euclidean torus signature (+,+)
- Natural units: Dimensionless CFT normalization; c denotes central charge, not speed of light
- Coordinate system: Complex modular parameter tau in the upper half-plane; q = exp(2 pi i tau)
- State normalization: Vacuum character normalized to the identity baseline in the cited modular-bootstrap literature
- Index positioning: Primarily scalar observables c, Delta_gap, h, and tau; no active tensor-index convention

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| ------- | ------------- | ----------- | -------------------- | ------ |
| near-c=1 gap improvement | unresolved | unresolved | 01 | literature comparison pending |

### Pending Todos

None yet.

### Blockers/Concerns

None

## Session Continuity

**Last session:** 2026-04-09T20:36:25.756984+00:00
**Stopped at:** 2026-04-09T20:36:05Z
**Resume file:** HANDOFF.md
**Last result ID:** R-05-ml-window
**Hostname:** Sergios-MacBook-Pro
**Platform:** Darwin 25.3.0 arm64
