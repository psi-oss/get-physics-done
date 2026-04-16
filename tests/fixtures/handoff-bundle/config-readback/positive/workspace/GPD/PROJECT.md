# Error thresholds in holographic codes

## What This Is

This project studies published threshold results for holographic quantum error-correcting codes, with emphasis on how erasure, depolarizing, and biased-noise thresholds depend on decoder choice and on whether the code family is zero-rate or finite-rate. The immediate deliverable is a literature-grounded threshold map and a follow-on research roadmap that turns the current comparison into a concrete frontier problem.

## Core Research Question

What threshold landscape is already established for holographic codes, and where is the strongest still-open gap once we separate results by channel, decoder, and code-rate regime?

## Scoping Contract Summary

### Contract Coverage

- Threshold map: Build a primary-source comparison across HaPPY, heptagon/Steane, SCF, and related holographic stabilizer codes.
- Acceptance signal: A channel- and decoder-normalized report plus a roadmap for the next threshold study.
- False progress to reject: Treating thresholds from different decoders or different channels as directly comparable without qualification.

### User Guidance To Preserve

- **User-stated observables:** Error thresholds in holographic codes.
- **User-stated deliverables:** A final report, journaled analysis of GPD output, and a research roadmap that can drive later phases.
- **Must-have references / prior outputs:** Pastawski et al. (2015), Harris et al. (2018), Harris et al. (2020), Farrelly et al. (2022), and Fan et al., arXiv:2408.06232v3 (submitted 2024; revised 2025).
- **Stop / rethink conditions:** If a primary source already closes the finite-rate biased-noise gap, the frontier claim must be revised.

### Scope Boundaries

**In scope**

- Primary-source threshold comparison for representative holographic stabilizer codes.
- Decoder- and channel-aware normalization of published threshold claims.
- Identification of the most defensible unresolved frontier for a follow-on study.

**Out of scope**

- Circuit-level fault-tolerant thresholds with noisy syndrome extraction.
- New Monte Carlo threshold extraction or decoder implementation in this session.
- Non-stabilizer or approximate holographic codes not anchored by the cited threshold papers.

### Active Anchor Registry

- `REF-Pastawski-2015`: Pastawski et al., JHEP 2015, 149, arXiv:1503.06237
  - Why it matters: Establishes the baseline HaPPY-style holographic code construction and erasure-threshold story.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, use, cite
- `REF-Harris-2018`: Harris et al., Phys. Rev. A 98, 052301, arXiv:1806.06472
  - Why it matters: Introduces the CSS heptagon holographic code and its erasure decoder benchmark.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `REF-Harris-2020`: Harris et al., Phys. Rev. A 102, 062417, arXiv:2008.10206
  - Why it matters: Gives phenomenological Pauli-noise thresholds across code families with explicit code-rate dependence.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `REF-Farrelly-2022`: Farrelly et al., Phys. Rev. A 105, 052446, arXiv:2012.07317
  - Why it matters: Sharpens depolarizing and dephasing benchmarks using tensor-network decoding.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `REF-Fan-2025`: Fan et al., arXiv:2408.06232v3 (submitted 2024; revised 2025)
  - Why it matters: Strongest inspected zero-rate benchmark for holographic codes under biased Pauli noise and hashing-bound comparisons.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite

### Carry-Forward Inputs

- `GPD/state.json` authoritative `project_contract`
- Current report output path: `../../results/14-bao-r02-report.md`
- No confirmed prior numerical runs or notebooks in this workspace yet

### Skeptical Review

- **Weakest anchor:** Whether finite-rate holographic codes already have a published biased-noise threshold map comparable to the zero-rate frontier results.
- **Unvalidated assumptions:** Published thresholds remain meaningfully comparable once decoder and channel mismatches are normalized.
- **Competing explanation:** Zero-rate biased-noise gains may partly reflect decoder/channel specialization rather than intrinsic holographic geometry.
- **Disconfirming observation:** A primary source with finite-rate biased-noise thresholds matching or surpassing the zero-rate hashing-bound results.
- **False progress to reject:** Fixed-size non-detectable error probabilities or bulk-local thresholds treated as universal asymptotic thresholds without warning labels.

### Open Contract Questions

- Do any finite-rate holographic codes have published biased-noise threshold maps comparable to the zero-rate results?
- Which decoder and channel normalizations are strict enough for apples-to-apples comparison?

## Research Questions

### Answered

(None yet)

### Active

- [ ] What erasure-threshold benchmark is most defensible for the original HaPPY-family constructions?
- [ ] How much of the reported depolarizing-threshold spread is explained by decoder choice rather than code geometry?
- [ ] Is the zero-rate biased-noise frontier already matched by any finite-rate holographic code family?

### Out of Scope

- Circuit-level threshold theorems for holographic codes — requires a different noise model and workflow.

## Research Context

### Physical System

Holographic tensor-network stabilizer codes defined on hyperbolic tilings, with logical information encoded from bulk to boundary and thresholds assessed under erasure, depolarizing, or biased Pauli-noise channels.

### Theoretical Framework

Quantum error correction, tensor networks, holographic code constructions, and code-capacity threshold analysis.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| Physical error probability | `p` | `0 <= p <= 1` | Channel-dependent threshold variable |
| Bias parameter | `eta` | paper-specific | Used for biased Pauli-noise families |
| Code radius / layers | `r` or `L` | increasing size | Controls finite-size threshold crossings |
| Code rate | `k/n` | zero-rate or finite-rate | Essential for comparison discipline |

### Known Results

- Pastawski et al. (2015) established the canonical HaPPY-style holographic-code construction and its erasure-threshold picture.
- Harris et al. (2018) introduced the CSS heptagon code and reported a stronger qualitative erasure benchmark than the earlier mixed pentagon/hexagon construction.
- Harris et al. (2020) and Farrelly et al. (2022) pushed depolarizing and related Pauli-noise benchmarking to more explicit decoder comparisons.
- Fan et al., arXiv:2408.06232v3 (submitted 2024; revised 2025), showed that several zero-rate holographic codes reach or exceed the hashing bound in biased-noise regimes.

### What Is New

The new contribution is not a fresh threshold simulation yet; it is a disciplined threshold map that isolates the strongest unresolved frontier instead of conflating channel, decoder, and rate effects.

### Target Venue

If this grows into new threshold data, the natural venues are `Physical Review A`, `Quantum`, or a quantum information workshop paper with a strong numerical component.

### Computational Environment

Current environment is a local Codex + GPD workspace with command-line project tracking and literature synthesis; no local simulation code is present yet.

## Notation and Conventions

See `GPD/CONVENTIONS.md` for notation and sign conventions once the convention document is generated from the lock.

## Unit System

Dimensionless physical error probabilities for threshold values; use `hbar = c = 1` only when translating continuum holography notation from source papers.

## Requirements

See `GPD/REQUIREMENTS.md` for the detailed requirements specification.

Key requirement categories: `ANLY`, `COMP`, `VALD`, `PLAN`

## Key References

- Pastawski et al., JHEP 2015, 149, arXiv:1503.06237
- Harris et al., Phys. Rev. A 98, 052301 (2018), arXiv:1806.06472
- Harris et al., Phys. Rev. A 102, 062417 (2020), arXiv:2008.10206
- Farrelly et al., Phys. Rev. A 105, 052446 (2022), arXiv:2012.07317
- Fan et al., arXiv:2408.06232v3 (submitted 2024; revised 2025)

## Constraints

- **Comparability**: Thresholds from different decoders or channels must not be merged into a single ranking without caveats.
- **Evidence quality**: Claims must stay anchored to primary papers, not tertiary summaries.
- **Scope**: This session is for threshold synthesis and project setup, not new simulation data.

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Treat decoder/channel normalization as contract-critical | Cross-paper threshold comparisons are otherwise misleading | Active |
| Focus the frontier question on finite-rate versus zero-rate biased-noise thresholds | The zero-rate literature is currently ahead of the finite-rate story | Active |

Full log: `GPD/DECISIONS.md`

---

_Last updated: 2026-04-09 after project initialization_
