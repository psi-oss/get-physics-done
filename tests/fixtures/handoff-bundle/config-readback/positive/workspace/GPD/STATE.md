# Research State

## Project Reference

See: GPD/PROJECT.md

**Machine-readable scoping contract:** `GPD/state.json` field `project_contract`

**Core research question:** What are the erasure, depolarizing, and biased-noise thresholds of holographic quantum codes, and which code families approach or exceed known channel benchmarks?
**Current focus:** Bootstrap literature-backed roadmap for threshold studies in HaPPY, heptagon/Steane, and zero-rate holographic codes.

## Current Position

**Current Phase:** 01
**Current Phase Name:** Literature threshold baseline
**Total Phases:** 4
**Current Plan:** —
**Total Plans in Phase:** —
**Status:** Researching
**Last Activity:** 2026-04-09

**Progress:** [░░░░░░░░░░] 0%

## Active Calculations

None yet.

## Intermediate Results

- [res-threshold-source-set] Core threshold anchor set fixed to Pastawski 2015, Harris 2018, Harris 2020, Farrelly 2022, and Fan arXiv:2408.06232v3 for this project. (phase 1)
- [res-happy-erasure-baseline] Pastawski et al. (2015) established the canonical HaPPY-style erasure-threshold benchmark and the threshold picture that later holographic-code papers compare against. (valid: erasure channel; HaPPY-style tensor-network holographic code, phase 1) [deps: res-threshold-source-set]
- [res-heptagon-erasure] Harris et al. (2018) introduced the CSS heptagon holographic code and reported a stronger erasure-channel benchmark than the earlier mixed pentagon/hexagon family under an optimal erasure decoder. (valid: erasure channel; central logical qubit recovery with optimal erasure decoder, phase 1) [deps: res-happy-erasure-baseline]
- [res-pauli-rate-range] Harris et al. (2020) found phenomenological Pauli-error thresholds ranging from 7% to 16%, with the range depending on code rate. (units: probability, valid: Pauli-error phenomenology with integer-optimization decoding for bulk qubits, phase 2) [deps: res-threshold-source-set]
- [res-heptagon-depolarizing-94] Farrelly et al. (2022) computed a 9.4% bulk depolarizing threshold for the max-rate holographic Steane code using a parallel tensor-network decoder. (units: probability, valid: depolarizing noise; bulk logical qubits; max-rate holographic Steane code, phase 2) [deps: res-pauli-rate-range]
- [res-zero-rate-biased-hashing] Fan et al., arXiv:2408.06232v3 (submitted 2024; revised 2025), found that all tested zero-rate holographic codes reach the hashing bound in some bias regime, with several constructions surpassing prior 2-Pauli-noise benchmarks. (valid: biased Pauli noise; zero-rate holographic code families under tensor-network decoding, phase 3) [deps: res-heptagon-depolarizing-94]
- [res-frontier-gap] Within the inspected anchor set, the next decisive missing comparison is a finite-rate biased-noise threshold map under decoder-controlled comparisons. (valid: literature synthesis as of 2026-04-09, phase 3) [deps: res-zero-rate-biased-hashing]

## Open Questions

- Do any finite-rate holographic codes have published biased-noise threshold maps comparable to the new zero-rate results?
- Which decoder and noise-model normalizations are strict enough for apples-to-apples comparison across the current literature?
- How should central-logical, bulk-logical, and full-code thresholds be normalized across holographic-code papers before direct comparison?
- Are the strongest biased-noise gains generic to holographic geometry, or are they currently specific to zero-rate constructions and tailored seed tensors?

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 2]: Treat decoder, channel, and logical-qubit location as hard comparison boundaries for threshold claims. — The cited literature mixes erasure, depolarizing, and biased-noise channels plus different decoders and observables; collapsing them would overstate the evidence.

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| ------------- | -------------- | --------------------- | ------------- | ------ |
| Cross-paper threshold comparability | Valid only when noise channel, decoder, and logical-qubit observable are aligned | benchmark alignment discipline | Partially satisfied | active |
| Bulk-threshold proxy | Useful only when the source paper explicitly studies logical qubits at fixed bulk depth | logical-qubit location | Source-dependent | caution |

**Convention Lock:**

- Metric signature: mostly plus (-,+,+,+) when relativistic notation appears; otherwise code-level Pauli/stabilizer notation
- Natural units: Thresholds reported as dimensionless physical error probabilities; use hbar=c=1 only when translating holographic/AdS notation from source papers
- Coordinate system: Hyperbolic-disk / Schlaefli-tiling geometry; layers indexed by graph distance from the central logical qubit

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| ------- | ------------- | ----------- | -------------------- | ------ |
| Finite-rate biased-noise frontier gap | Open | High | 3 | Primary-source literature comparison |
| Threshold comparability after decoder normalization | Plausible but not fully secure | Medium | 2 | Cross-paper decoder/channel audit |

### Pending Todos

None yet.

### Blockers/Concerns

None

## Session Continuity

**Last session:** —
**Stopped at:** —
**Resume file:** —
**Last result ID:** —
**Hostname:** —
**Platform:** —
