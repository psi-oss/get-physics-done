# ML-Optimized Modular Bootstrap at Finite c

## What This Is

This project studies finite-central-charge Virasoro modular bootstrap for 2d unitary compact CFTs, with special attention to the window just above c = 1 where recent machine-learning-style searches reported candidate spectra and stronger gap constraints. The immediate deliverable is a literature-anchored research scaffold that makes the finite-c benchmark chain explicit, locks conventions, and states what would count as genuine progress versus optimizer-driven false positives.

## Core Research Question

Can ML-optimized modular-bootstrap searches in the finite-central-charge window 1 < c <= 8/7 reproduce or sharpen the established Virasoro gap constraints without overclaiming the existence of exact new CFTs?

## Scoping Contract Summary

### Contract Coverage

- Finite-c gap benchmark: align the 2013, 2016, 2023, and 2026 modular-bootstrap claims in one convention set
- Candidate-spectrum diagnostics: require truncation uncertainty and non-ML checks before treating ML outputs as meaningful
- False progress to reject: low loss or visually plausible spectra without benchmark or integrality support

### User Guidance To Preserve

- **User-stated observables:** finite-c modular-bootstrap spectra, gap bounds, and ML-optimized search behavior
- **User-stated deliverables:** a research-grade synthesis of the finite-c benchmark chain and next-step numerical targets
- **Must-have references / prior outputs:** arXiv:1307.6562, arXiv:1608.06241, arXiv:1903.06272, arXiv:2308.08725, arXiv:2308.11692, arXiv:2604.01275
- **Stop / rethink conditions:** stop if the supposed ML improvement vanishes under convention alignment, truncation control, or integrality checks

### Scope Boundaries

**In scope**

- Virasoro modular bootstrap for unitary compact 2d CFTs with c > 1
- The finite-c benchmark window near c = 1, especially 1 < c <= 8/7
- Literature-anchored comparison of SDP, truncation, integrality, geometry, and ML search methods

**Out of scope**

- Claiming rigorous existence proofs for new exact CFTs from candidate spectra alone
- Large-c holographic interpretations as the primary target
- Full production numerical scans in this initialization pass

### Active Anchor Registry

- `Ref-2016-CLY`: arXiv:1608.06241
  - Why it matters: canonical finite-c Virasoro gap benchmark and extremal-spectrum reference
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-2023-FL-Integrality`: arXiv:2308.08725
  - Why it matters: integrality improves finite-c modular-bootstrap bounds near c = 1
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-2023-Geometry`: arXiv:2308.11692
  - Why it matters: geometric and Hankel-SDP interpretation of finite-c modular-bootstrap bounds
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-2026-BFLT`: arXiv:2604.01275
  - Why it matters: latest ML-optimized finite-c search with candidate spectra for 1 < c <= 8/7
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite

### Carry-Forward Inputs

- `GPD/project_contract.json`
- arXiv benchmark abstracts and formulas recorded in `journal.md`
- No local numerical outputs confirmed yet

### Skeptical Review

- **Weakest anchor:** whether ML-generated low-loss candidates correspond to exact CFTs rather than near-solutions
- **Unvalidated assumptions:** that the 2026 ML diagnostics are strong enough to justify stronger finite-c conclusions
- **Competing explanation:** geometric or integrality constraints may account for the apparent improvement without new physics
- **Disconfirming observation:** the near-c=1 strengthening disappears after matching conventions with arXiv:1608.06241 and arXiv:2308.08725
- **False progress to reject:** smooth candidate spectra with no modular-residual, truncation, or integrality audit

### Open Contract Questions

- Which diagnostic best separates genuine finite-c solutions from optimizer artifacts?
- How should integrality and ML search be combined in one numerical workflow?
- What benchmark figure or table should be regenerated first in the workspace?

## Research Questions

### Answered

- What is the latest direct arXiv anchor for ML-optimized finite-c modular bootstrap? Answer: arXiv:2604.01275, submitted on April 1, 2026.

### Active

- [ ] How much stronger than the 2016 near-c=1 gap narrative is the 2026 ML claim once conventions are aligned?
- [ ] Which finite-c observables besides Delta_gap are stable enough to compare across the 2016, 2023, and 2026 methods?
- [ ] Can integrality or geometric constraints be baked into the ML search objective instead of used only as after-the-fact filters?

### Out of Scope

- Large-c black-hole bounds from modular bootstrap - outside the finite-c target window of this project
- Non-Virasoro extended chiral algebra classification - separate program

## Research Context

### Physical System

Unitary compact 2d conformal field theories on the torus, described through modular invariance of the Virasoro-character partition function.

### Theoretical Framework

Virasoro modular bootstrap, semi-definite programming, fast finite polynomial truncations, integrality constraints, Hankel-geometry constraints, and machine-learning-style loss minimization.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| Central charge | c | 1 < c <= 8/7 primary focus | Here c means CFT central charge, not speed of light |
| Primary gap | Delta_gap | finite-c benchmark observable | Lowest nontrivial primary dimension |
| Modular parameter | tau | upper half-plane | Benchmark point often near tau = i |
| Truncation depth | N_trunc | method dependent | Controls candidate-spectrum uncertainty |

### Known Results

- Friedan and Keller (arXiv:1307.6562) established improved modular-invariance gap constraints with the linear functional method.
- Collier, Lin, and Yin (arXiv:1608.06241) computed finite-c numerical bounds and extremal spectra, sharpening earlier gap results.
- Afkhami-Jeddi, Hartman, and Tajdini (arXiv:1903.06272) built a fast truncated-polynomial modular-bootstrap algorithm.
- Fitzpatrick and Li (arXiv:2308.08725) showed integrality strengthens some finite-c bounds, including a slight improvement near c = 1.
- Chiang et al. (arXiv:2308.11692) reframed modular bootstrap geometrically and linked low-order integrality to a non-convex structure.
- Benjamin, Fitzpatrick, Li, and Thaler (arXiv:2604.01275) used ML-style optimization and reported candidate truncated spectra for 1 < c <= 8/7.

### What Is New

This pass does not claim a new numerical result. It creates a GPD-native, skepticism-first research scaffold that makes the finite-c literature chain explicit and constrains how later ML-search claims may be interpreted.

### Target Venue

JHEP-style high-energy theory note or a bootstrap-focused short paper, contingent on later numerical reproduction.

### Computational Environment

Current pass: GPD-only project initialization, literature anchoring, and state tracking in this workspace. Anticipated later tools: Python numerics, high-precision linear algebra, and a reproducible modular-bootstrap search pipeline.

## Notation and Conventions

See `GPD/CONVENTIONS.md` for the active convention ledger.

## Unit System

Dimensionless CFT normalization. The symbol c denotes central charge throughout this project; it never denotes the speed of light.

## Requirements

See `GPD/REQUIREMENTS.md` for the detailed requirements specification.

## Key References

Only contract-critical anchors are mirrored here:

- arXiv:1307.6562
- arXiv:1608.06241
- arXiv:1903.06272
- arXiv:2308.08725
- arXiv:2308.11692
- arXiv:2604.01275

## Constraints

- **Scope**: Finite-c Virasoro modular bootstrap only - avoids drifting into large-c or non-Virasoro programs
- **Evidence**: No candidate spectrum counts as a result without uncertainty and cross-check language
- **Compute**: No local solver campaign has been run yet - current claims must remain literature anchored

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Treat finite c as finite central charge | Prevents notation drift and unit confusion | Accepted |
| Anchor the project on the 2016, 2023, and 2026 benchmark chain | These are the decisive finite-c references for this topic | Accepted |
| Treat ML search as heuristic unless diagnostics say otherwise | Prevents overclaiming exact CFT existence | Accepted |

---

_Last updated: 2026-04-09 after project initialization and literature anchoring_
