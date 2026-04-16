# Research State

## Project Reference

See: GPD/PROJECT.md

**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`

**Core research question:** Does DSSYK have a semiclassical dS bulk dual?
**Current focus:** Literature-based assessment of semiclassical de Sitter bulk dual proposals for double-scaled SYK

## Current Position

**Current Phase:** 01
**Current Phase Name:** Map the primary literature and competing bulk-duality claims
**Total Phases:** 3
**Current Plan:** —
**Total Plans in Phase:** 0
**Status:** Researching
**Last Activity:** 2026-04-09: verified citations against arXiv/INSPIRE-linked records, audited retained equations, and rewrote the manuscript

**Progress:** [░░░░░░░░░░] 0%

## Active Calculations

None yet.

## Intermediate Results

- [r-nv-correlator] Narovlansky-Verlinde: in a doubled infinite-temperature DSSYK sector with an equal-energy constraint, dressed two-point functions match a scalar Green function in dS_3 and motivate a JT/dS-style bulk interpretation.: `m^2 R_{\\mathrm{dS}}^2 = 4\\Delta(1-\\Delta)` (valid: large N; doubled sector; constrained dressed operators; radius restored explicitly for dimensional clarity, phase 01, ✓, evidence: 1)
- [r-liouville-exact] Verlinde-Zhang: a 2D Liouville-de Sitter gravity model reproduces the exact DSSYK two-point function to all orders in the double-scaling parameter and is argued to arise from quantizing 3D de Sitter gravity.: `G^{(2)}_{\\mathrm{Liouville-dS}}(\\lambda) = G^{(2)}_{\\mathrm{DSSYK}}(\\lambda)` (valid: normalized two-point functions; doubled sector; all orders in lambda = p^2/N, phase 02, ✓, evidence: 1) [deps: r-nv-correlator]
- [r-sinedilaton] Blommaert-Mertens-Papalini: sine-dilaton gravity provides a precise holographic dual of DSSYK at the q-Schwarzian level, reproduces thermodynamics with the positivity constraint, and implies a discrete bulk Hilbert space.: `Z_{q-\\mathrm{Sch}} = Z_{\\mathrm{sine-dilaton}}` (valid: q-Schwarzian / thermodynamic sector; semi-classical sine-dilaton regime, phase 02, ✓, evidence: 1) [deps: r-liouville-exact]
- [r-dsjt-upper-edge] Okuyama: a scaling limit near the upper edge of the DSSYK spectrum reproduces de Sitter JT gravity and is consistent with the classical behavior of sine-dilaton gravity.: `E \\to E_0 \\Rightarrow \\mathrm{dS\ JT}` (valid: upper-edge spectral scaling limit of DSSYK, phase 02, ✓, evidence: 1) [deps: r-sinedilaton]
- [r-splitting-gluing] Cui-Rozali: splitting and gluing in sine-dilaton gravity reproduces DSSYK matter correlators, including OTOCs and double-trumpet observables, and builds a wormhole Hilbert-space picture.: `G_{\\mathrm{bulk}}^{\\mathrm{matter}} = G_{\\mathrm{DSSYK}}^{\\mathrm{chord}}` (valid: bulk matter sector in sine-dilaton gravity; chord-diagram observables, phase 02, ✓, evidence: 1) [deps: r-sinedilaton]
- [r-entropic-puzzle] Blommaert et al.: periodic dilaton gravity and DSSYK exhibit an entropic puzzle; gauging a discrete shift symmetry discretizes lengths, leads to a finite-dimensional Hilbert space, and spoils a naive Bekenstein-Hawking interpretation.: `S \\neq A/4G\\ \text{(naively)}` (valid: periodic/sine-dilaton realization; entropy and state-counting sector, phase 03, ✓, evidence: 1) [deps: r-sinedilaton]
- [r-verdict] Current literature supports a restricted, sector-specific semiclassical de Sitter interpretation for parts of DSSYK, but not a settled complete semiclassical dS bulk dual for DSSYK as a whole. (valid: assessment based on correlator, thermodynamic, and Hilbert-space evidence across restricted sectors, phase 03, ✓, evidence: 1) [deps: r-nv-correlator, r-liouville-exact, r-sinedilaton, r-dsjt-upper-edge, r-splitting-gluing, r-entropic-puzzle]

## Open Questions

- Does the upper-edge dS JT scaling limit describe the same bulk physics as the doubled DSSYK construction, or only a related limit of the model?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase ?]: Use the local CLI surface rather than the unavailable runtime-only new-project command — The workspace prompt lists GPD commands, but the installed local CLI exposes init/state/phase/result workflows rather than a direct new-project mutation command; proceeding with the available commands preserves auditability and documents the gap.
- [Phase 03]: Adopt a restricted-sector verdict rather than a full semiclassical-bulk-dual claim — Primary-source evidence from 2023-2026 supports correlator and low-dimensional bulk reconstructions for specific DSSYK sectors and limits, but entropy and Hilbert-space objections prevent a clean claim that full DSSYK already has a settled semiclassical de Sitter bulk dual.

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| ------------- | -------------- | --------------------- | ------------- | ------ |
| Large-N semiclassical limit | Large N with suppressed 1/N fluctuations in the proposed bulk regime | 1/N | formal large-N limit in cited papers | active |
| Double-scaling limit | DSSYK with q and N scaled so lambda stays finite; semiclassical claims strongest at small lambda or edge scaling limits | lambda = p^2/N (or equivalent fixed double-scaling parameter) | finite lambda; small-lambda and edge-of-spectrum limits emphasized | active |
| Doubled constrained infinite-temperature sector | Applies to the doubled DSSYK construction with equal-energy or constrained-sector dressing used in de Sitter proposals | Sector restriction / equal-energy constraint | central in Narovlansky-Verlinde and related doubled constructions | active |

**Convention Lock:**

- Metric signature: mostly-plus (-,+,...) Lorentzian signature for de Sitter/JT bulk formulas
- Natural units: hbar = c = k_B = 1
- Coordinate system: Global dS2/dS3 time with static-patch interpretation when discussing horizon thermodynamics

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| ------- | ------------- | ----------- | -------------------- | ------ |
| Scope of the bulk dual (restricted sector vs full DSSYK) | undetermined | high | 03 | primary-source synthesis across positive and critical papers |
| Entropy and horizon-area dictionary | contested | high | 03 | compare Narovlansky-Verlinde assumptions with Rahman-Susskind comments and later periodic-dilaton entropy analysis |
| Whether sine-dilaton gravity should count as de Sitter gravity for this duality claim | ambiguous | medium | 02 | compare the 2025-2026 bulk constructions with the original dS3/JT interpretations |

### Pending Todos

None yet.

### Blockers/Concerns

None

## Session Continuity

**Last session:** 2026-04-09T15:06:36.244414+00:00
**Stopped at:** 2026-04-09T15:06:31Z
**Resume file:** HANDOFF.md
**Last result ID:** r-verdict
**Hostname:** Sergios-MacBook-Pro
**Platform:** Darwin 25.3.0 arm64
