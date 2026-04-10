# Conventions Ledger

**Project:** ML-Optimized Modular Bootstrap at Finite c
**Created:** 2026-04-09
**Last updated:** 2026-04-09 (Phase 01 setup)

> This file is append-only for convention entries. When a convention changes, add a new
> entry and mark the old one as superseded.

---

## Spacetime

### Metric Signature

| Field | Value |
| ----- | ----- |
| **Convention** | Euclidean torus signature (+,+) |
| **Introduced** | Phase 01 |
| **Rationale** | Modular bootstrap is formulated on the Euclidean torus partition function |
| **Dependencies** | Modular parameter tau, partition-function interpretation, sign conventions in quoted formulas |

### Coordinate System

| Field | Value |
| ----- | ----- |
| **Convention** | Complex modular parameter tau in the upper half-plane, with q = exp(2 pi i tau) |
| **Introduced** | Phase 01 |
| **Rationale** | Standard modular-bootstrap coordinate choice for the torus |
| **Dependencies** | Character expansions, modular S transformation, benchmark formula comparison |

### Index Positioning

| Field | Value |
| ----- | ----- |
| **Convention** | No active spacetime tensor-index convention; symbols are primarily c, Delta, h, hbar, and tau |
| **Introduced** | Phase 01 |
| **Rationale** | The current project is scalar in its main observables |
| **Dependencies** | Prevents accidental import of relativistic tensor notation from unrelated projects |

---

## Quantum Mechanics

### Fourier Convention

| Field | Value |
| ----- | ----- |
| **Convention** | Not central to the current project; no Fourier-transform formula is treated as contract critical yet |
| **Introduced** | Phase 01 |
| **Rationale** | Torus modular bootstrap is driven by character sums and modular transformations, not a Fourier-transform calculation |
| **Dependencies** | None currently |

### State Normalization

| Field | Value |
| ----- | ----- |
| **Convention** | Partition function normalized so the vacuum contribution is the identity-character baseline used in the cited modular-bootstrap literature |
| **Introduced** | Phase 01 |
| **Rationale** | Needed for consistent comparison of candidate spectra and degeneracies across references |
| **Dependencies** | Gap definition, degeneracy counting, extremal-spectrum comparison |

---

## Units And Naming

### Unit System

| Field | Value |
| ----- | ----- |
| **Convention** | Dimensionless CFT normalization; c always denotes central charge, never the speed of light |
| **Introduced** | Phase 01 |
| **Rationale** | The topic phrase "finite c" refers to finite central charge, and that distinction must remain explicit |
| **Dependencies** | All benchmark comparisons and later numerical scans |

### Gap Observable

| Field | Value |
| ----- | ----- |
| **Convention** | Delta_gap denotes the lowest nontrivial primary scaling dimension unless a paper explicitly states a different scalar-only or twist-gap observable |
| **Introduced** | Phase 01 |
| **Rationale** | Different papers quote related but distinct gap observables |
| **Dependencies** | Benchmark tables, claims of improvement, phase deliverables |

### Chiral Algebra Scope

| Field | Value |
| ----- | ----- |
| **Convention** | Default scope is Virasoro only unless an extended algebra is explicitly introduced and justified |
| **Introduced** | Phase 01 |
| **Rationale** | Keeps the finite-c benchmark chain aligned with the current target literature |
| **Dependencies** | Candidate-spectrum interpretation, integrality assumptions, benchmark matching |
