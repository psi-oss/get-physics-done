# Quantum-Information Route To The Ryu-Takayanagi Formula

## What This Is

This project investigates whether the leading Ryu-Takayanagi formula and its first controlled corrections can be recovered from quantum-information structure rather than taken as input from bulk gravity. The focus is the interface among holographic entanglement entropy, operator-algebra quantum error correction, relative entropy and modular flow, and tensor-network toy models, with an output of literature-grounded synthesis plus a frontier gap map.

## Core Research Question

Which quantum-information ingredients are sufficient to recover the leading Ryu-Takayanagi formula, and which steps still require semiclassical gravitational input?

## Scoping Contract Summary

### Contract Coverage

- Dependency map: Trace which pieces of the RT story follow from quantum-information structure and which do not.
- Acceptance signal: Produce an anchor-by-anchor synthesis note and a gap analysis tied to explicit arXiv references.
- False progress to reject: Do not treat tensor-network analogies or entanglement wedge reconstruction alone as a derivation of the RT area term.

### User Guidance To Preserve

- **User-stated observables:** Leading RT area term, entanglement wedge reconstruction, and frontier modular-flow / entropy-inequality constraints.
- **User-stated deliverables:** A research-grade synthesis and a gap map for the RT-from-quantum-information program.
- **Must-have references / prior outputs:** RT06 (`hep-th/0603001`), ADH14 (`1411.7041`), JLMS15 (`1512.06431`), DHW16 (`1601.05416`), RTN16 (`1601.01694`), Gao24 (`2402.18655`), Bao25 (`2504.12388`).
- **Stop / rethink conditions:** If every candidate quantum-information derivation still imports the area term or semiclassical geometry, reframe the project as a gap analysis rather than a derivation claim.

### Scope Boundaries

**In scope**

- Map the logical chain linking holographic entanglement entropy, operator-algebra quantum error correction, JLMS relative entropy, entanglement wedge reconstruction, and tensor-network toy models.
- Benchmark each step against foundational and recent arXiv anchors relevant to the RT formula from a quantum-information viewpoint.

**Out of scope**

- Deriving bulk Einstein equations or the gravitational replica trick from first principles.
- Full quantum extremal surface or island computations beyond identifying where they modify the RT story.
- Explicit numerical AdS/CFT calculations for specific holographic CFT states.

### Active Anchor Registry

- `RT06`: Shinsei Ryu and Tadashi Takayanagi, *Holographic Derivation of Entanglement Entropy from AdS/CFT*, `hep-th/0603001`
  - Why it matters: Benchmark statement of the leading RT formula.
  - Carry forward: `planning | execution | verification | writing`
  - Required action: `read | compare | cite`
- `ADH14`: Ahmed Almheiri, Xi Dong, and Daniel Harlow, *Bulk Locality and Quantum Error Correction in AdS/CFT*, `1411.7041`
  - Why it matters: Establishes the QEC language behind subregion duality.
  - Carry forward: `planning | execution | verification | writing`
  - Required action: `read | use | cite`
- `JLMS15`: Daniel L. Jafferis, Aitor Lewkowycz, Juan Maldacena, and S. Josephine Suh, *Relative entropy equals bulk relative entropy*, `1512.06431`
  - Why it matters: Anchors the relative-entropy route to entanglement wedge reconstruction.
  - Carry forward: `planning | execution | verification | writing`
  - Required action: `read | use | cite`
- `DHW16`: Xi Dong, Daniel Harlow, and Aron C. Wall, *Reconstruction of Bulk Operators within the Entanglement Wedge in Gauge-Gravity Duality*, `1601.05416`
  - Why it matters: Sharpens the reconstruction consequences of JLMS/QEC.
  - Carry forward: `planning | execution | verification | writing`
  - Required action: `read | use | cite`
- `RTN16`: Patrick Hayden, Sepehr Nezami, Xiao-Liang Qi, Nathaniel Thomas, Michael Walter, and Zhao Yang, *Holographic duality from random tensor networks*, `1601.01694`
  - Why it matters: Best toy-model reproduction of RT and bulk-entropy corrections from a quantum-information perspective.
  - Carry forward: `planning | execution | verification | writing`
  - Required action: `read | compare | cite`
- `Gao24`: Ping Gao, *Modular flow in JT gravity and entanglement wedge reconstruction*, `2402.18655`
  - Why it matters: Recent frontier result on modular flow and reconstruction.
  - Carry forward: `planning | execution | verification | writing`
  - Required action: `read | compare | cite`
- `Bao25`: Ning Bao, Hao Geng, and Yikun Jiang, *Ryu-Takayanagi Formula for Multi-Boundary Black Holes from 2D Large-$c$ CFT Ensemble*, `2504.12388`
  - Why it matters: Explicit 2025 derivation claim in a restricted AdS\(_3\)/CFT\(_2\) multi-boundary large-`c` ensemble setting.
  - Carry forward: `planning | execution | verification | writing`
  - Required action: `read | compare | cite`

### Carry-Forward Inputs

- `Bao25` is now a verified post-2024 anchor, but its claim is limited to a special AdS\(_3\)/CFT\(_2\) multi-boundary large-`c` ensemble.
- Frontier emphasis: prioritize conceptual derivation and failure-mode analysis over a generic literature survey.

### Skeptical Review

- **Weakest anchor:** Whether any existing quantum-information argument derives the leading area term without importing semiclassical geometry.
- **Unvalidated assumptions:** Large-`N` semiclassical factorization is sufficient background; random tensor networks encode the same geometric notion of area as semiclassical gravity.
- **Competing explanation:** The RT formula may fundamentally require the gravitational replica trick, with quantum information organizing only consistency conditions and reconstruction structure.
- **Disconfirming observation:** Every proposed quantum-information derivation step presupposes the area term or an equivalent geometric ingredient upstream.
- **False progress to reject:** Qualitative QEC/tensor-network analogies that never isolate the source of the area term.

### Open Contract Questions

- Can the leading area term be derived from quantum-information structure alone?
- Which post-2024 modular-flow or entropy-inequality results materially change the derivation question?

## Research Questions

### Answered

(None yet — investigate to answer)

### Active

- [ ] Can one separate genuine derivations of the RT area term from arguments that only explain entanglement wedge reconstruction after RT is assumed?
- [ ] How much of the JLMS plus OAQEC chain is logically independent of semiclassical bulk input?
- [ ] Does the Bao25 derivation generalize beyond multi-boundary AdS\(_3\)/CFT\(_2\) ensemble states?
- [ ] Which recent modular-flow or entropy-inequality papers sharpen the frontier beyond the 2014-2016 anchor set?

### Out of Scope

- Exact gravitational replica-trick derivations beyond literature benchmarking — requires a bulk-gravity project in its own right.
- Phenomenological or numerical holographic entropy calculations for specific CFT states — not the conceptual target here.

## Research Context

### Physical System

Boundary subregions of holographic CFT states with semiclassical AdS duals, viewed through entanglement entropy, relative entropy, and subregion reconstruction.

### Theoretical Framework

AdS/CFT, holographic entanglement entropy, operator-algebra quantum error correction, modular flow, relative entropy, tensor-network toy models, and holographic entropy inequalities.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| Gauge-group size / central charge | `N`, `c` | Large | Semiclassical bulk limit |
| Newton constant | `G_N` | Small | Controls area-term normalization |
| Code-subspace dimension | `dim H_code` | Restricted | Matters for OAQEC reasoning |
| Bulk quantum correction strength | `S_bulk` | Subleading | Relevant for RT corrections and JLMS |

### Known Results

- Leading RT area formula proposed in static AdS/CFT — RT06 (`hep-th/0603001`)
- QEC interpretation of bulk locality and subregion duality — ADH14 (`1411.7041`)
- Relative entropy equality between boundary and bulk subregions — JLMS15 (`1512.06431`)
- Entanglement wedge reconstruction theorem-level sharpening — DHW16 (`1601.05416`)
- Random tensor network realization of RT-like behavior — RTN16 (`1601.01694`)
- Recent modular-flow refinement in JT gravity — Gao24 (`2402.18655`)
- Restricted-scope RT derivation claim for multi-boundary AdS\(_3\)/CFT\(_2\) large-`c` ensembles — Bao25 (`2504.12388`)

### What Is New

The project aims to separate what quantum information actually derives from what it merely organizes, then identify which frontier results could close or clarify the remaining gap. Bao25 raises the standard by providing a restricted-scope derivation claim, but it does not yet establish a generic RT-from-QI result.

### Target Venue

Research memo / review-style note first; journal target remains open pending whether the work stays at the synthesis level or becomes a sharper conceptual result.

### Computational Environment

Text-centric local research environment with GPD tracking, no heavy numerical workload planned in the current scope.

## Notation and Conventions

See `GPD/CONVENTIONS.md` for the project convention record and the structured convention lock in `GPD/state.json`.

## Unit System

Natural units with `\hbar = c = k_B = 1`, unless an anchor paper forces a different temporary convention for comparison.

## Requirements

See `GPD/REQUIREMENTS.md` for the detailed requirement set.

Key requirement categories: `DERV`, `ANAL`, `VALD`

## Key References

Contract-critical anchors are the seven arXiv references listed in the Active Anchor Registry.

## Constraints

- **Conceptual rigor**: Every major claim must be tied to explicit anchor papers — otherwise it remains marked as conjectural.
- **Scope control**: Do not drift into full bulk-gravity derivations, QES/island calculations, or numerical holography without a roadmap update.
- **Methodological skepticism**: Toy models may support intuition but do not count as derivations unless imported assumptions are spelled out.

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Treat the project as a derivation-plus-gap-analysis study | The current frontier may not support a clean QI-only derivation of the RT area term | Active |
| Use explicit arXiv anchors as the research backbone | Prevents drift into analogy-only claims | Active |
| Separate RT origin, bulk corrections, wedge reconstruction, and frontier advances | These layers are often conflated in the literature | Active |

Full log: `GPD/DECISIONS.md`

---

_Last updated: 2026-04-09 after initialization bootstrap_
