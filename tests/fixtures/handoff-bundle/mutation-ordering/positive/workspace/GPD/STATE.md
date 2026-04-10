# Research State

## Project Reference

See: GPD/PROJECT.md (updated 2026-04-09)

**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`

**Core research question:** Can rQFC be reformulated and justified beyond braneworld holographic semiclassical gravity without losing the benchmark consequences already established in the literature?
**Current focus:** Phase 01 benchmark ingredient ledger, citation audit, and comparison setup

## Current Position

**Current Phase:** 01
**Current Phase Name:** Benchmark braneworld rQFC proof and extract indispensable ingredients
**Total Phases:** 5
**Current Plan:** 1
**Total Plans in Phase:** 3
**Status:** Ready to plan
**Last Activity:** 2026-04-09
**Last Activity Description:** Session 6 audited citations, equation claims, and stale state values

**Progress:** [░░░░░░░░░░] 0%

## Active Calculations

- Mapping the benchmark braneworld proof into a minimal ingredient ledger
- Comparing the benchmark ledger against the `Theta -> 0` limit and the JT/d>2 benchmark tests
- Benchmark ingredient ledger for arXiv:2212.03881
- Theta -> 0 limit comparison against the improved energy condition
- JT-gravity and d>2 consequence compatibility table

## Intermediate Results

- [R-01-benchmark] Benchmark literature result: subject to a technical assumption, rQFC is proved in brane-world semiclassical gravity theories holographically dual to higher-dimensional Einstein gravity (valid: brane-world semiclassical gravity under the assumptions of arXiv:2212.03881, phase 01, verified against arXiv/INSPIRE on 2026-04-09)
- [R-02-inec] The `Theta -> 0` limit yields the improved quantum null energy condition: `T_{kk} \ge \frac{hbar}{2\pi A}\left(S_{out}^{\prime\prime} - \frac{1}{2}\theta S_{out}^{\prime}\right)` (units: null-null stress component, valid: limiting-case constraint stated in arXiv:2310.14396 rather than a standalone general non-braneworld proof of rQFC, phase 02, verified against arXiv/INSPIRE on 2026-04-09) [deps: R-01-benchmark]
- [R-02-jt] Non-braneworld benchmark result: rQFC is proved in a class of d=2 JT-gravity plus QFT toy models (valid: class of d=2 toy models studied in arXiv:2510.13961, phase 02, verified against arXiv/INSPIRE on 2026-04-09) [deps: R-01-benchmark]
- [R-02-dgtwo] In a broad class of d>2 states, rQFC forbids QNEC saturation faster than `O(A)` as the transverse area shrinks to zero (valid: broad class of d>2 states as stated in arXiv:2510.13961, phase 02, verified against arXiv/INSPIRE on 2026-04-09) [deps: R-02-jt]

## Open Questions

- Which steps in arXiv:2212.03881 are indispensable rather than braneworld conveniences?
- What exactly replaces higher-dimensional Einstein-dual control in a general non-braneworld proof?
- How strong is the d>2 consequence of arXiv:2510.13961 as a constraint on any extension program?
- Which step in the benchmark proof depends essentially on braneworld bulk Einstein dynamics?
- Is the JT-gravity success in arXiv:2510.13961 low-dimensional accident or evidence for a general mechanism?
- What exact small-area behavior in d>2 is forced by rQFC beyond ordinary QNEC saturation?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 0]: Anchor the project on the benchmark, limit, and latest non-braneworld test papers — This preserves concrete scope and prevents the extension program from drifting into unanchored generality
- [Phase 0]: Treat unrestricted QFC as a constraint source rather than the main target — Known stronger-QFC failures should stress-test the restricted program, not redefine it

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| ------------- | -------------- | --------------------- | ------------- | ------ |
| Restricted limit as diagnostic probe | Theta close to 0 only | Theta | used only as a limiting-case benchmark | valid for limiting-case analysis |
| Semiclassical control of generalized entropy | semiclassical gravity regime | backreaction strength relative to geometric area term | model dependent across benchmarks | needs explicit benchmarking |

**Convention Lock:**

- Metric signature: mostly-plus
- Natural units: c = k_B = 1 with G and hbar explicit unless quoting source formulas
- Coordinate system: affine null generators with transverse coordinates y on codimension-2 cuts

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| ------- | ------------- | ----------- | -------------------- | ------ |
| Minimal replacement for Einstein-dual control | not yet identified | high | 00 | bootstrap literature audit |
| Generality of JT-inspired ingredient set | uncertain outside d=2 | high | 00 | bootstrap literature audit |

### Pending Todos

None yet.

### Blockers/Concerns

- No callable local new-project write pass was exposed; project files had to be bootstrapped from the canonical GPD templates after state.json contract setup.

## Session Continuity

**Last session:** 2026-04-09T17:34:35.974596+00:00
**Stopped at:** Session 5 complete: reran validations, exercised write paths, and narrowed live GPD issues
**Resume file:** HANDOFF.md
**Last result ID:** R-02-dgtwo
**Hostname:** Sergios-MacBook-Pro
**Platform:** Darwin 25.3.0 arm64
