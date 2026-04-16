# Does DSSYK Have a Semiclassical dS Bulk Dual?

## What This Is

This project evaluates whether double-scaled SYK admits a semiclassical de Sitter bulk interpretation, and if so in what restricted sense. The immediate deliverable is a literature-grounded research note that separates genuinely semiclassical evidence from kinematic matching, toy-model analogies, and known obstructions.

## Core Research Question

Does existing primary-source evidence support a bona fide semiclassical de Sitter bulk dual for DSSYK, or only a narrower sector-specific correspondence?

## Scoping Contract Summary

### Contract Coverage

- Literature verdict: produce a source-grounded yes/no-with-caveats assessment of the semiclassical dS-dual claim.
- Acceptance signal: correlate positive evidence from correlators and semiclassical control with negative evidence from entropy, temperature, and Hilbert-space structure.
- False progress to reject: treating two-point-function matching by itself as decisive proof of a full semiclassical bulk dual.

### User Guidance To Preserve

- **User-stated observables:** correlator matching, semiclassical regime, entropy/temperature interpretation, and bulk-dual status.
- **User-stated deliverables:** journaled analysis of GPD output plus a final report.
- **Must-have references / prior outputs:** Narovlansky-Verlinde on doubled DSSYK/dS holography, sine-dilaton gravity follow-ups, and later entropy/Hilbert-space critiques.
- **Stop / rethink conditions:** if the positive case reduces to a kinematic correlator match with no thermodynamic or state-space control, do not overclaim a full dS bulk dual.

### Scope Boundaries

**In scope**

- Primary-source assessment of DSSYK/de Sitter duality claims through April 9, 2026.
- Distinguishing evidence for doubled infinite-temperature constrained sectors from claims about DSSYK as a whole.
- Tracking tool/workflow limitations that affect how much of GPD can be exercised in this workspace.

**Out of scope**

- Constructing a new bulk dual from first principles.
- Performing original DSSYK path-integral calculations beyond literature synthesis.
- Surveying unrelated de Sitter holography models not directly tied to DSSYK.

### Active Anchor Registry

- `NV-2023`: Narovlansky and Verlinde, "Double-scaled SYK and de Sitter Holography" (arXiv:2310.16994)
  - Why it matters: primary positive claim for a doubled DSSYK realization of low-dimensional dS holography.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `BMP-2025`: Blommaert, Mertens, Papalini, "The dilaton gravity hologram of double-scaled SYK" (JHEP 06, 2025)
  - Why it matters: strongest 2d periodic/sine-dilaton bulk proposal reproducing q-Schwarzian structure.
  - Carry forward: execution, verification, writing
  - Required action: read, compare, cite
- `BLMPP-2025`: Blommaert et al., "An entropic puzzle in periodic dilaton gravity and DSSYK" (JHEP 07, 2025)
  - Why it matters: major obstruction for naive semiclassical/Bekenstein-Hawking interpretation.
  - Carry forward: execution, verification, writing
  - Required action: read, compare, cite
- `CR-2026`: Cui and Rozali, "Splitting and gluing in sine-dilaton gravity" (JHEP 02, 2026)
  - Why it matters: latest positive evidence for bulk matter correlators and wormhole Hilbert-space structure.
  - Carry forward: execution, verification, writing
  - Required action: read, compare, cite

### Carry-Forward Inputs

- `journal.md` for command-by-command analysis of GPD behavior.
- Primary-source abstracts and article metadata gathered during this session.

### Skeptical Review

- **Weakest anchor:** whether the later sine-dilaton/periodic-dilaton constructions count as semiclassical de Sitter gravity rather than a different toy hologram.
- **Unvalidated assumptions:** that large-`N`, doubled, infinite-temperature, equal-energy-constrained sectors diagnose the bulk dual of full DSSYK.
- **Competing explanation:** DSSYK may admit semiclassical geometry only in restricted observables while its full state space stays too discrete or too non-Einstein-like for a standard semiclassical dS bulk.
- **Disconfirming observation:** entropy, Hilbert-space dimension, or thermal interpretation remain irreconcilable with semiclassical de Sitter expectations even after the newest bulk reconstructions.
- **False progress to reject:** counting exact chord-diagram or q-Schwarzian reproduction as sufficient without checking what geometry and Hilbert space those structures actually imply.

### Open Contract Questions

- Is the best-supported bulk picture genuinely 3d de Sitter, 2d JT/dS reduction, or periodic/sine-dilaton gravity with only partial dS interpretation?
- Do the latest entropy and Hilbert-space results rule out a full semiclassical dS dual, or only constrain the most naive version?

## Research Questions

### Answered

(None yet — investigate to answer)

### Active

- [ ] What is the strongest published evidence for a semiclassical de Sitter bulk description of DSSYK?
- [ ] Which observables are matched exactly, semiclassically, or only heuristically?
- [ ] Do entropy and Hilbert-space results force the verdict below "full semiclassical bulk dual"?

### Out of Scope

- Explicit construction of a new bulk path integral — requires original derivation work beyond this session.

## Research Context

### Physical System

The system is double-scaled SYK, especially the doubled infinite-temperature sector with an equal-energy constraint used in de Sitter holography proposals.

### Theoretical Framework

Quantum gravity / holography, SYK and q-Schwarzian dynamics, de Sitter holography, and periodic/sine-dilaton gravity.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| System size | `N` | Large `N` | Needed for semiclassical control in proposed dualities |
| Double-scaling parameter | `\lambda` or `p^2/N` | Small for semiclassical regime | Controls suppression of fluctuations in semiclassical-geometry arguments |
| Operator dimension | `\Delta` | `0 < \Delta < 1` | Appears in the scalar mass formula `m^2 = 4\Delta(1-\Delta)` |

### Known Results

- Doubled DSSYK two-point functions were matched to a scalar Green's function in 3d de Sitter in 2023/2025.
- Sine-dilaton and related periodic-dilaton models reproduce large parts of DSSYK/q-Schwarzian structure and correlators.
- Later work found significant entropy and Hilbert-space puzzles, including departures from Bekenstein-Hawking expectations.

### What Is New

This project does not seek a new derivation. It produces a tighter verdict on what the existing literature actually establishes about semiclassical de Sitter bulk duality, distinguishing suggestive evidence from decisive evidence.

### Target Venue

Internal research note / briefing report.

### Computational Environment

Local GPD workspace, shell-accessible GPD CLI, and external literature lookup for primary sources.

## Notation and Conventions

See `GPD/CONVENTIONS.md` for all notation and sign conventions.

## Unit System

Natural units (`hbar = c = k_B = 1`).

## Requirements

See `GPD/REQUIREMENTS.md` for the detailed requirements specification.

## Key References

- Narovlansky and Verlinde, arXiv:2310.16994 / JHEP 05 (2025) 032
- Blommaert, Mertens, Papalini, JHEP 06 (2025) 050
- Blommaert et al., JHEP 07 (2025) 093
- Cui and Rozali, JHEP 02 (2026) 160

## Constraints

- **Scope**: literature-grounded synthesis only — no new DSSYK derivation is attempted.
- **Tooling**: the local GPD CLI lacks a direct `new-project` mutation command, so project scaffolding must be assembled around the available init/state/phase/result commands.
- **Claim discipline**: full bulk-dual claims must survive entropy/Hilbert-space objections, not just correlator matches.

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Use the local CLI surface plus minimal scaffold files | The installed CLI exposes init/state/phase/result workflows but not a direct `new-project` mutation path | Adopted |

---

_Last updated: 2026-04-09 after project initialization_
