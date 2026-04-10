# Does DSSYK Have a Semiclassical dS Bulk Dual?

## What This Is

This project studies whether double-scaled SYK admits a genuinely semiclassical de Sitter bulk dual, or only a weaker holographic sector that reproduces selected correlators. The focus is on the analytic large-N double-scaled regime and on the literature proposing dS JT, dS3, Liouville-dS, and sine-dilaton descriptions. The deliverable is a skeptical research report that classifies the status of the bulk-dual claim rather than presuming it.

## Core Research Question

Does DSSYK have a semiclassical de Sitter bulk dual, and if so is it a full bulk dual or only a constrained-sector correspondence?

## Scoping Contract Summary

### Contract Coverage

- Bulk-dual verdict: decide whether the literature supports a full semiclassical dS bulk dual, only a sector-restricted correspondence, or no simple semiclassical dual.
- Acceptance signal: correlator evidence must be checked together with thermal, entropic, and operator-dictionary consistency.
- False progress to reject: a correlator match in a doubled or infinite-temperature sector does not by itself certify a full semiclassical bulk dual.

### User Guidance To Preserve

- **User-stated observables:** the decisive observable is whether DSSYK has a semiclassical dS bulk dual, not merely whether some correlator resembles a dS Green's function.
- **User-stated deliverables:** a final report that compares the major candidate duals and gives a defended classification.
- **Must-have references / prior outputs:** arXiv:2209.09997, arXiv:2310.16994, arXiv:2402.02584, and arXiv:2404.03535 must remain visible throughout the project.
- **Stop / rethink conditions:** if the evidence stays confined to correlator matching while temperature, entropy, or the bulk operator map remain unresolved, do not promote the claim to a full bulk dual.

### Scope Boundaries

**In scope**

- Literature-based audit of the semiclassical evidence connecting DSSYK to candidate de Sitter bulk descriptions.
- Comparison of correlator, thermodynamic, and dictionary evidence across the main anchor papers.

**Out of scope**

- Building a new microscopic bulk model beyond the candidate descriptions already in the literature.
- Finite-N numerics outside the analytic double-scaled regime.

### Active Anchor Registry

- `Ref-2209-09997`: Adel A. Rahman, *dS JT Gravity and Double-Scaled SYK*, arXiv:2209.09997
  - Why it matters: early explicit positive-cosmological-constant JT proposal for a high-temperature DSSYK limit.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-2310-16994`: Vladimir Narovlansky and Herman Verlinde, *Double-scaled SYK and de Sitter Holography*, arXiv:2310.16994
  - Why it matters: central doubled-SYK to dS3 correlator match behind the modern claim.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-2402-02584`: Herman Verlinde and Mengyang Zhang, *SYK Correlators from 2D Liouville-de Sitter Gravity*, arXiv:2402.02584
  - Why it matters: strongest exact two-point-function claim in a Liouville-dS setting.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-2404-03535`: Andreas Blommaert, Thomas G. Mertens, and Jacopo Papalini, *The dilaton gravity hologram of double-scaled SYK*, arXiv:2404.03535
  - Why it matters: clarifies the fake-temperature and defect subtleties that obstruct a naive semiclassical reading.
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite

### Carry-Forward Inputs

- Fresh workspace; no prior local outputs to preserve.
- Contract baseline: reproduce the exact scope and regime assumptions in the anchor papers before drawing any global verdict.

### Skeptical Review

- **Weakest anchor:** whether the doubled equal-energy constrained construction captures the full DSSYK notion relevant to the user's question.
- **Unvalidated assumptions:** that all candidate bulk models are compared in the same normalization and regime.
- **Competing explanation:** the literature may be isolating a useful semiclassical proxy or auxiliary holographic sector rather than a full semiclassical DSSYK bulk dual.
- **Disconfirming observation:** if no candidate simultaneously matches correlators and yields a coherent semiclassical interpretation of temperature and entropy, the simple full-dual claim fails.
- **False progress to reject:** rhetoric about de Sitter holography that skips the concrete DSSYK dictionaries.

### Open Contract Questions

- Is the doubled equal-energy constrained system the decisive notion of DSSYK relevant for the bulk-dual question, or only one auxiliary sector?
- Can fake temperature be given a genuinely smooth semiclassical bulk interpretation without collapsing the claim to a proxy notion of thermality?

## Research Questions

### Answered

(None yet.)

### Active

- [ ] Which anchor papers provide exact or semiclassical correlator matches, and in what regime?
- [ ] Do those same papers provide a coherent thermal and entropic bulk dictionary?
- [ ] Is the best-supported verdict a full dual, a constrained-sector dual, or a negative answer for simple semiclassical duality?

### Out of Scope

- Constructing a brand-new bulk completion from scratch.
- Finite-N numerical tests beyond the analytic literature audit.

## Research Context

### Physical System

The system is double-scaled SYK and closely related doubled or equal-energy-constrained sectors used in recent de Sitter holography proposals. The project compares boundary observables to low-dimensional positive-cosmological-constant gravity models.

### Theoretical Framework

Large-N double-scaled SYK, doubled-SYK constructions, dS JT gravity, reduced 3D de Sitter gravity, Liouville-de Sitter gravity, and sine-dilaton gravity.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| System size | N | large-N | Double-scaled analytic control requires large N. |
| Double-scaling parameter | lambda | fixed in double-scaled limit | Paper-specific normalization must be tracked explicitly. |
| Boundary temperature / auxiliary temperature | beta or T | paper-dependent | Fake-temperature issues are part of the central skepticism. |
| Boundary time or frequency | t or omega | semiclassical comparison window | Correlator claims depend strongly on the regime and continuation used. |

### Known Results

- Rahman (2022) proposes a high-temperature DSSYK limit dual to dS JT gravity.
- Narovlansky and Verlinde (2023) argue that a doubled-SYK construction reproduces a scalar Green's function in dS3.
- Verlinde and Zhang (2024) claim an exact all-orders two-point-function match from 2D Liouville-de Sitter gravity.
- Blommaert, Mertens, and Papalini (2024) sharpen the holographic picture but expose the fake-temperature puzzle.

### What Is New

The project does not aim to add a new formal construction. Its novelty is a skeptical synthesis: it asks whether the strongest available claims really add up to a full semiclassical dS bulk dual, or whether the evidence is better interpreted as a constrained-sector or proxy correspondence.

### Target Venue

Internal research note first. If a sharp clarifying verdict emerges, the natural external style target would be a short high-energy theory paper in a venue such as JHEP.

### Computational Environment

This run is literature- and consistency-analysis heavy. The main resources are the GPD tracking stack, symbolic reasoning, and paper-by-paper comparison rather than large numerical compute.

## Notation and Conventions

See `GPD/CONVENTIONS.md` for the locked conventions used in this project.

## Unit System

Natural units with hbar = c = 1.

## Requirements

See `GPD/REQUIREMENTS.md` for the detailed requirements specification.

## Key References

- `Ref-2209-09997`
- `Ref-2310-16994`
- `Ref-2402-02584`
- `Ref-2404-03535`

## Constraints

- **Interpretive discipline**: do not infer a full bulk dual from correlator evidence alone.
- **Normalization discipline**: preserve paper-specific conventions and regimes instead of silently harmonizing them.
- **Scope discipline**: stay in the analytic double-scaled regime and within the cited candidate bulk models.

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Treat correlator-only evidence as insufficient | The user asked about a semiclassical bulk dual, not a weaker proxy correspondence | Adopted |
| Anchor the project on four papers | They span the strongest positive claims and the main interpretive caveat | Adopted |

---

_Last updated: 2026-04-09 after project initialization_
