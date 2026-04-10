# Extending the restricted QFC beyond braneworlds

## What This Is

This project investigates whether the restricted quantum focusing conjecture (rQFC), proved in braneworld semiclassical gravity, can be extended to non-braneworld settings. The target deliverable is a defensible extension strategy that isolates the minimal assumptions behind rQFC, checks them against known benchmark papers, and records the main obstructions still preventing a general proof.

## Core Research Question

Can rQFC be reformulated and justified beyond braneworld holographic semiclassical gravity without losing the benchmark consequences already established in the literature?

## Scoping Contract Summary

### Contract Coverage

- `claim-main`: A viable beyond-braneworld strategy must reproduce the braneworld benchmark, respect the `Theta -> 0` limit, and accommodate the 2025 JT-gravity and d>2 tests.
- `deliv-map`: A benchmark literature map of the original proof ingredients and the non-braneworld evidence.
- `deliv-strategy`: A candidate extension strategy with explicit failure modes and next derivation targets.
- False progress to reject: Generic claims that QNEC-like behavior is "probably enough" for rQFC.

### User Guidance To Preserve

- **User-stated observables:** Minimal ingredient set for rQFC and the status of non-braneworld benchmark cases.
- **User-stated deliverables:** GPD-tracked derivation notes, roadmap phases, and a final report.
- **Must-have references / prior outputs:** arXiv:2212.03881, arXiv:2310.14396, arXiv:2510.13961.
- **Stop / rethink conditions:** Pause if the proposed extension needs stronger assumptions than the JT proof or fails to recover the braneworld benchmark logic.

### Scope Boundaries

**In scope**

- Isolate the indispensable ingredients of the braneworld rQFC proof.
- Compare those ingredients with the `Theta -> 0` improved-energy-condition limit.
- Use the 2025 JT-gravity and d>2 results as non-braneworld benchmark tests.
- Produce a candidate extension strategy plus an obstruction ledger.

**Out of scope**

- A full proof of the unrestricted QFC in arbitrary semiclassical gravity.
- Numerical experiments unrelated to null deformations or generalized entropy.
- Claims that ignore explicit stronger-QFC counterexamples.

### Active Anchor Registry

- `Ref-rqfc`: Arvin Shahbazi-Moghaddam, *Restricted Quantum Focusing*, Phys. Rev. D 109 (2024) 066023, arXiv:2212.03881
  - Why it matters: benchmark proof and baseline ingredient map
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-inec`: Ido Ben-Dayan, *The Quantum Focusing Conjecture and the Improved Energy Condition*, JHEP 02 (2024) 132, arXiv:2310.14396
  - Why it matters: `Theta -> 0` limit, improved quantum null energy condition, and a possible field-theory route; not a standalone general proof of non-braneworld rQFC
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite
- `Ref-tests`: Victor Franken, Sami Kaya, François Rondeau, Arvin Shahbazi-Moghaddam, Patrick Tran, *Tests of restricted Quantum Focusing and a new CFT bound*, arXiv:2510.13961
  - Why it matters: latest non-braneworld benchmark evidence
  - Carry forward: planning, execution, verification, writing
  - Required action: read, compare, cite

### Carry-Forward Inputs

- `GPD/state.json.project_contract`
- Convention lock in `GPD/state.json`
- Benchmark references `Ref-rqfc`, `Ref-inec`, and `Ref-tests`

### Skeptical Review

- **Weakest anchor:** What replaces higher-dimensional Einstein-dual control in a general non-braneworld proof?
- **Unvalidated assumptions:** The braneworld entropy-variation data may admit a state-independent reformulation beyond holographic control.
- **Competing explanation:** Present non-braneworld successes may rely on low-dimensional or highly symmetric structure rather than a general mechanism.
- **Disconfirming observation:** Any candidate extension that needs assumptions stronger than the JT proof or misses the stronger d>2 consequence from arXiv:2510.13961.
- **False progress to reject:** Repackaging QNEC intuition without an explicit benchmark-to-benchmark comparison.

### Open Contract Questions

- Which steps in arXiv:2212.03881 are truly indispensable, and which are braneworld conveniences?
- Can the `Theta -> 0` limit be turned into a generally useful field-theory criterion for rQFC?
- What minimal data about generalized entropy variation must be controlled in non-braneworld settings?

## Research Questions

### Answered

(None yet.)

### Active

- [ ] Which pieces of the braneworld proof are structural rather than holographically accidental?
- [ ] How should the `Theta -> 0` improved-energy-condition limit be interpreted in the extension program?
- [ ] What do the JT-gravity and d>2 tests imply about the minimal acceptable ingredient set?

### Out of Scope

- Unrestricted-QFC proofs in full generality - descoped because current anchors concern the restricted conjecture.

## Research Context

### Physical System

Null deformations of generalized entropy in semiclassical gravity, including braneworld holographic models, JT gravity coupled to QFT, and higher-dimensional QFT/CFT consequences of rQFC.

### Theoretical Framework

Semiclassical gravity, quantum information in curved spacetime, holography, QNEC/QFC inequalities, and low-dimensional gravity toy models.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| Quantum expansion | `Theta` | near `Theta = 0` and generic sign | Controls the restricted limit |
| Null expansion | `theta` | local null congruence data | Appears in the improved energy condition |
| Transverse area element | `A` | small-area and finite-area limits | Important in the 2025 d>2 consequence |
| Outside entropy | `S_out` | second null variation | Central nonlocal input |
| JT dilaton | `Phi` | matter backreaction comparable / small | Relevant to the 2025 JT analysis |
| Spacetime dimension | `d` | `d = 2` and `d > 2` | Separates JT and higher-dimensional consequences |

### Known Results

- The original rQFC conjecture is proposed and proved in braneworld semiclassical gravity, subject to a technical assumption, in arXiv:2212.03881.
- The `Theta -> 0` restriction yields the improved quantum null energy condition in arXiv:2310.14396, and the paper sketches rather than completes a field-theory proof route.
- The latest non-braneworld evidence proves rQFC in a class of JT-gravity models and shows, in d>2, that rQFC forbids QNEC saturation faster than `O(A)` as the transverse area shrinks to zero.

### What Is New

This project aims to synthesize those three anchors into a minimal beyond-braneworld extension program, rather than treating them as disconnected statements.

### Target Venue

JHEP or Phys. Rev. D, because the project sits at the interface of semiclassical gravity, holography, and quantum energy conditions.

### Computational Environment

Analytic reading and derivation workflow in the local GPD workspace. No heavy numerics are currently planned.

## Notation and Conventions

See `GPD/state.json` convention lock for the currently durable conventions.

## Unit System

Natural units with `c = k_B = 1`; keep `G` and `hbar` explicit unless quoting source formulas.

## Requirements

See `GPD/REQUIREMENTS.md` for the detailed requirement set and traceability map.

## Key References

- arXiv:2212.03881 / Phys. Rev. D 109 (2024) 066023 - benchmark proof of rQFC in braneworld semiclassical gravity
- arXiv:2310.14396 / JHEP 02 (2024) 132 - `Theta -> 0` limit and improved quantum null energy condition
- arXiv:2510.13961 - JT-gravity proof and the `O(A)` d>2 consequence

## Constraints

- **Benchmark-first**: Every extension claim must map back to an explicit anchored result.
- **Scope**: Stay on restricted QFC; treat unrestricted-QFC counterexamples as constraints, not as the main target.
- **Method**: Prefer analytic structure and skeptical comparison over vague holographic analogy.

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Anchor the project on arXiv:2212.03881, arXiv:2310.14396, and arXiv:2510.13961 | These are the clearest benchmark, limiting-case, and latest non-braneworld anchors | Adopted |
| Treat unrestricted QFC as out of scope except where counterexamples constrain the restricted program | Prevents scope creep and keeps the project benchmark-driven | Adopted |

---

_Last updated: 2026-04-09 after project bootstrap_
