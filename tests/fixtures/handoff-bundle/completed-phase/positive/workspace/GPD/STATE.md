# Research State

## Project Reference

See: GPD/PROJECT.md

**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`

**Core research question:** Can entangled CFT sectors produce or sharply diagnose cosmological singularities, and can boundary observables distinguish singularity resolution from singularity avoidance?
**Current focus:** Benchmark the verified entangled-CFT cosmology papers against Kasner/QES/two-point-function diagnostics and sharpen the boundary observable needed to distinguish singularity resolution from avoidance.

## Current Position

**Current Phase:** 02
**Current Phase Name:** Kasner and QES singularity benchmarks
**Total Phases:** 4
**Current Plan:** —
**Total Plans in Phase:** —
**Status:** Planning
**Last Activity:** Re-audited the citations against arXiv, corrected the Antonini and Sahu benchmark descriptions, restored the Engelhardt correlator benchmark, and drafted a manuscript-ready synthesis.

**Progress:** [██████████] 100%

## Active Calculations

None yet.

## Intermediate Results

- [lit-antonini-2023] Antonini-Sasieta-Swingle construct entangled microstates of a pair of holographic CFTs whose dual semiclassical description includes big-bang/big-crunch AdS cosmologies, with the cosmology encoded in one CFT's entanglement wedge. (valid: entangled multi-CFT AdS cosmologies; arXiv:2307.14416, phase 01, ✓, evidence: 1)
- [lit-manu-2021] Quantum extremal surfaces in cosmological singularity backgrounds are driven away from the singularity into the semiclassical region. (valid: Kasner-like and reduced 2d cosmologies; arXiv:2012.07351, phase 02, ✓, evidence: 1)
- [lit-frenkel-2020] Irrelevant deformations of the CFT can drive holographic flows to Kasner universes, providing explicit singular benchmark geometries. (valid: Holographic RG flow construction; arXiv:2004.01192, phase 02, ✓, evidence: 1)
- [lit-engelhardt-2014] Boundary two-point correlators of large-dimension operators in anisotropic Kasner holography show strong horizon-scale signatures of the singularity. (valid: anisotropic Kasner gauge/gravity duality; arXiv:1404.2309, phase 02, ✓, evidence: 1)
- [lit-narayan-2024] Complexity surfaces near Kasner-like singularities become lightlike in the interior and contribute vanishingly near the singularity; entanglement probes show similar IR bending-away behaviour. (valid: Kasner-like holographic cosmologies; arXiv:2404.00761, phase 03, ✓, evidence: 1) [deps: lit-manu-2021]
- [lit-sahu-2025] Sahu and Van Raamsdonk construct big-bang/big-crunch cosmological spacetimes dual to entangled states of multiple holographic CFTs associated with black-hole second asymptotic regions. (valid: entangled multi-CFT black-hole cosmologies; arXiv:2411.14673, phase 03, ✓, evidence: 1)
- [hyp-benchmark-before-resolution] Current working hypothesis: the entangled-CFT cosmology should first be interpreted as a benchmarked singularity-diagnostic framework, not as a demonstrated mechanism of microscopic singularity resolution. (valid: Supported by current literature comparison and open questions, phase 04, ✓, evidence: 1) [deps: lit-antonini-2023, lit-manu-2021, lit-frenkel-2020, lit-engelhardt-2014, lit-narayan-2024, lit-sahu-2025]

## Open Questions

- Which boundary observable, if any, can distinguish the entangled-CFT cosmology from generic Kasner-like singularity avoidance?
- Does the Antonini construction imply resolution of the singularity or only an emergent semiclassical cosmological patch?
- What concrete CFT operation or coupling prepares the entangled boundary state beyond the random-state ansatz of Antonini et al.?
- Do all known HRT/QES probes in Kasner-like holographic benchmarks bend away from the singularity, or is there a counterexample in the current literature?
- Can complexity observables add information beyond entanglement in diagnosing the singular region, or do they simply mirror the same avoidance behaviour?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 0]: Initialized project scope for entangled-CFT cosmology — Need benchmarked scope before any derivation or singularity-resolution claim

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| ------------- | -------------- | --------------------- | ------------- | ------ |
| Large-N classical gravity limit | Semiclassical holographic regime away from the singular core | 1/N^2 or G_N/L^(d-1) | small | active |
| Random entanglement / typical-state ansatz | Large Hilbert space and coarse-grained entropy observables | Effective Hilbert-space dimension | heuristically large | caution |
| Semiclassical extremal-surface approximation | Bulk region far from stringy or Planckian singular behaviour | l_s/L and G_N/L^(d-1) | assumed small away from the crunch | active |

**Convention Lock:**

- Metric signature: mostly-plus
- Fourier convention: f(x)=int d^d k/(2pi)^d e^{ikx} f(k)
- Natural units: c = hbar = 1 with AdS radius L explicit
- Coordinate system: Conformal time eta, comoving spatial slices, holographic radial coordinate z

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| ------- | ------------- | ----------- | -------------------- | ------ |
| Boundary diagnostic of singularity resolution | open | high | 03 | Literature comparison |
| Microscopic preparation of the entangled CFT state | unknown | high | 01 | Literature comparison |
| Universality of complexity thinning near singularity | unclear | medium | 03 | Comparison of 2024-2025 benchmarks |

### Pending Todos

None yet.

### Blockers/Concerns

None

## Session Continuity

**Last session:** 2026-04-09T20:53:25.340810+00:00
**Stopped at:** 2026-04-09T16:53:14-0400
**Resume file:** HANDOFF.md
**Last result ID:** hyp-benchmark-before-resolution
**Hostname:** Sergios-MacBook-Pro
**Platform:** Darwin 25.3.0 arm64
