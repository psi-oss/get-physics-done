# DSSYK and a Semiclassical de Sitter Bulk Dual

## What This Is

This project investigates whether double-scaled SYK admits a controlled semiclassical de Sitter bulk dual, or whether the strongest available statement is instead an exact but non-semiclassical dilaton-gravity dual with only de Sitter-flavored sectors. The work is a literature-driven theoretical audit aimed at a short research report and a GPD-tracked verdict. The emphasis is on separating precise holographic claims from suggestive but incomplete de Sitter interpretations.

## Core Research Question

Does DSSYK have a controlled semiclassical de Sitter bulk dual as of April 9, 2026, and if not, which observables support only a narrower de Sitter-flavored or sine-dilaton bulk description?

## Scoping Contract Summary

### Contract Coverage

- Verdict deliverable: produce a dated, source-grounded answer to the bulk-dual question.
- Acceptance signal: every must-read anchor is mapped to support, caveat, or unresolved tension.
- False progress to reject: inferring a full semiclassical de Sitter dual from a single correlator match.

### User Guidance To Preserve

- **User-stated observables:** correlator matching, entropy scaling, temperature dictionary, Hilbert-space interpretation.
- **User-stated deliverables:** `journal.md`, GPD-tracked research state, and `report.md` as the project-local report artifact. The automation harness may mirror that file into `../../results/01-almheiri-r02-report.md`.
- **Must-have references / prior outputs:** Rahman 2022, Narovlansky-Verlinde 2023, the 2024-2026 sine-dilaton line, and the entropy-puzzle follow-up.
- **Stop / rethink conditions:** pause if a later anchor resolves the entropy and fake-temperature issues in favor of a controlled semiclassical de Sitter geometry.

### Scope Boundaries

**In scope**

- Literature evidence for semiclassical de Sitter interpretations of DSSYK.
- Entropy, Hilbert-space, and temperature-dictionary consistency checks.
- Comparison with the exact sine-dilaton and periodic-dilaton hologram literature.

**Out of scope**

- New DSSYK correlator derivations.
- Finite-`N` numerics.
- General de Sitter holography outside the DSSYK setting.

### Active Anchor Registry

- `Ref-RS-2022`: Rahman, `arXiv:2209.09997`
  - Why it matters: introduces the dS JT interpretation and semiclassical thermodynamic language.
  - Carry forward: `planning`, `execution`, `verification`, `writing`
  - Required action: `read`, `compare`, `cite`
- `Ref-Semiclassical-2022`: Susskind, `arXiv:2209.09999`
  - Why it matters: argues for a separation-of-scales regime supporting a semiclassical dS story.
  - Carry forward: `planning`, `execution`, `verification`, `writing`
  - Required action: `read`, `compare`, `cite`
- `Ref-NV-2023`: Narovlansky and Verlinde, `arXiv:2310.16994`
  - Why it matters: gives the sharpest doubled-model dS proposal and a 3D dS correlator match.
  - Carry forward: `planning`, `execution`, `verification`, `writing`
  - Required action: `read`, `compare`, `cite`
- `Ref-Comment-2023`: Rahman and Susskind, `arXiv:2312.04097`
  - Why it matters: disputes the entropy and temperature interpretation of `Ref-NV-2023`.
  - Carry forward: `planning`, `execution`, `verification`, `writing`
  - Required action: `read`, `compare`, `cite`
- `Ref-Dilaton-2024`: Blommaert, Mertens, Papalini, `arXiv:2404.03535`
  - Why it matters: states a precise sine-dilaton hologram for DSSYK and reframes the bulk-dual question.
  - Carry forward: `planning`, `execution`, `verification`, `writing`
  - Required action: `read`, `compare`, `cite`
- `Ref-Entropic-2024`: Blommaert et al., `arXiv:2411.16922`
  - Why it matters: highlights finite-dimensional Hilbert-space and entropy puzzles.
  - Carry forward: `planning`, `execution`, `verification`, `writing`
  - Required action: `read`, `compare`, `cite`
- `Ref-Wormhole-2026`: Cui and Rozali, JHEP 02 (2026) 160
  - Why it matters: latest extension of the sine-dilaton picture to general correlators and wormhole Hilbert spaces.
  - Carry forward: `planning`, `execution`, `verification`, `writing`
  - Required action: `read`, `compare`, `cite`

### Carry-Forward Inputs

- `GPD/state.json` authoritative `project_contract`
- `journal.md` as the running analysis log of GPD outputs and failed commands

### Skeptical Review

- **Weakest anchor:** whether the doubled equal-energy model and the later sine-dilaton literature address exactly the same notion of a DSSYK bulk dual.
- **Unvalidated assumptions:** that a literature-only pass can yield a reliable verdict without new analytic work.
- **Competing explanation:** DSSYK may have de Sitter-flavored observables while its precise bulk dual is periodic or sine-dilaton gravity rather than a semiclassical dS spacetime.
- **Disconfirming observation:** a post-2025 paper that resolves the entropy and fake-temperature issues in favor of a controlled semiclassical dS geometry.
- **False progress to reject:** treating exact q-Schwarzian or sine-dilaton control as automatic proof of semiclassical de Sitter.

### Open Contract Questions

- Does any controlled limit recover a genuine semiclassical de Sitter entropy-area relation?
- Which observables, if any, are matched only in a special doubled or constrained sector rather than the full DSSYK theory?

## Research Questions

### Answered

(None yet.)

### Active

- [ ] Which concrete observables are matched by the 2022-2023 de Sitter proposals?
- [ ] Do the entropy, confinement, and Hilbert-space arguments block a clean semiclassical de Sitter dual?
- [ ] Does the sine-dilaton hologram replace, subsume, or merely coexist with the earlier de Sitter interpretation?

### Out of Scope

- Non-DSSYK de Sitter holography — too broad for this report.

## Research Context

### Physical System

Double-scaled SYK and closely related doubled or constrained variants proposed as holographic models of low-dimensional de Sitter gravity.

### Theoretical Framework

Quantum gravity and holography, with emphasis on low-dimensional de Sitter constructions, q-Schwarzian dynamics, and periodic or sine-dilaton gravity.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| SYK size | `N` | `N -> infinity` | needed for semiclassical scaling claims |
| Double-scaling control | `lambda = p^2/N` | fixed in DSSYK | controls the exact q-Schwarzian regime |
| dS radius to Newton coupling | `R_dS / G_N` | large for semiclassical limit | proposed to scale like `4 pi N / p^2 = 4 pi / lambda` in `Ref-NV-2023`; large ratio therefore needs small `lambda`, not large `N` alone |
| Chord number / geodesic length | `n`, `ell` | non-negative or discretized | central to the q-Schwarzian and sine-dilaton dictionary |

### Known Results

- Early papers argue that infinite-temperature DSSYK and related doubled models reproduce static-patch de Sitter observables in a semiclassical limit.
- `Ref-NV-2023` claims a precise 3D de Sitter Green-function match in a doubled equal-energy construction.
- `Ref-Dilaton-2024` and its follow-ups argue for a precise sine-dilaton gravity hologram of DSSYK, with nontrivial implications for temperature, discreteness, and Hilbert-space structure.

### What Is New

This project does not add new correlator technology. Its novelty is a skeptical synthesis: it asks whether the literature currently justifies the stronger phrase "semiclassical de Sitter bulk dual" or only a weaker statement about de Sitter-like sectors plus an exact non-semiclassical bulk description.

### Target Venue

Short internal report or research memo. A paper target is premature until the verdict stabilizes.

### Computational Environment

Local GPD workflow, shell access, and web-based literature lookup. No external compute cluster is required for this pass.

## Notation and Conventions

See `GPD/CONVENTIONS.md` for notation and sign conventions.

## Unit System

Natural units with `hbar = c = k_B = 1`, unless a cited paper uses a different normalization that matters for the dictionary.

## Requirements

See `GPD/REQUIREMENTS.md`.

## Key References

- A. Rahman, `arXiv:2209.09997`
- L. Susskind, `arXiv:2209.09999`
- V. Narovlansky and H. Verlinde, `arXiv:2310.16994`
- A. Rahman and L. Susskind, `arXiv:2312.04097`
- A. Blommaert, T.G. Mertens, J. Papalini, `arXiv:2404.03535`
- A. Blommaert et al., `arXiv:2411.16922`
- C. Cui and M. Rozali, JHEP 02 (2026) 160

## Constraints

- **Methodological**: This pass is literature-grounded rather than a new calculation.
- **Interpretive**: Exact duality claims must be kept distinct from semiclassical de Sitter claims.
- **Workflow**: Physics tracking should flow through GPD commands wherever the CLI exposes it.

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Use a literature-audit roadmap rather than direct derivation plans | The question is interpretive and source-driven on this first pass | Pending |
| Treat the sine-dilaton literature as decisive evidence about exact duality, not automatic evidence for semiclassical dS | Prevents overstating what the exact dual establishes | Pending |

Full log: `GPD/DECISIONS.md`

---

_Last updated: 2026-04-09 after project bootstrap_
