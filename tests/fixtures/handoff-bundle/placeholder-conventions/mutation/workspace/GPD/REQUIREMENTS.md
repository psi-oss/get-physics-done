# Requirements: Quantum-Information Route To The Ryu-Takayanagi Formula

**Defined:** 2026-04-09
**Core Research Question:** Which quantum-information ingredients are sufficient to recover the leading Ryu-Takayanagi formula, and which steps still require semiclassical gravitational input?

## Primary Requirements

### Derivations

- [ ] **DERV-01**: Map the dependency chain from RT06 through ADH14, JLMS15, and DHW16 with explicit identification of which steps assume semiclassical bulk geometry.
- [ ] **DERV-02**: Reconstruct the random-tensor-network route to RT-like behavior and isolate which geometric inputs are effectively hard-coded into the model.

### Analysis

- [ ] **ANAL-01**: Classify recent modular-flow and related post-2024 advances by whether they strengthen derivation, reconstruction, or only consistency-check layers of the RT story.

### Validations

- [ ] **VALD-01**: Ensure every major claim in the synthesis is anchored to a named arXiv reference or is explicitly labeled unresolved.
- [ ] **VALD-02**: Reject qualitative QEC or tensor-network analogies as success unless imported geometric assumptions are enumerated.

## Follow-up Requirements

### Extensions

- **EXT-01**: Extend the project to quantum extremal surfaces and islands once the RT-from-QI baseline is stable.
- **EXT-02**: Investigate whether holographic entropy-cone technology produces genuinely new constraints on derivation, not just consistency checks.

## Out of Scope

| Topic | Reason |
| ----- | ------ |
| Full gravitational replica-trick derivation | Requires a different, gravity-first project scope |
| Explicit numerical holographic CFT calculations | Not needed for the conceptual derivation/gap-analysis objective |
| Non-AdS or time-dependent generalizations as primary target | Would broaden the scope before the static RT baseline is understood |

## Accuracy and Validation Criteria

| Requirement | Accuracy Target | Validation Method |
| ----------- | --------------- | ----------------- |
| `DERV-01` | No missing logical step in the anchor chain | Cross-check against RT06, ADH14, JLMS15, and DHW16 |
| `DERV-02` | Explicit list of imported assumptions, not implicit analogy | Compare RTN16 toy-model ingredients against bulk-semiclassical inputs |
| `ANAL-01` | Recent-paper status labels are evidence-backed | Anchor each classification to the paper’s actual claim |
| `VALD-01` | Zero unanchored major claims | Audit result registry and report text against named references |
| `VALD-02` | False-progress modes named explicitly | Check the gap map before any success claim is made |

## Contract Coverage

| Requirement | Decisive Output / Deliverable | Anchor / Benchmark / Reference | Prior Inputs / Baselines | False Progress To Reject |
| ----------- | ----------------------------- | ------------------------------ | ------------------------ | ------------------------ |
| `DERV-01` | Dependency-map synthesis note | RT06, ADH14, JLMS15, DHW16 | Core anchor set from this session | Reconstruction language used as if it derived RT |
| `DERV-02` | Random-tensor-network assumptions note | RTN16 | RT leading formula and bulk-entropy correction structure | Minimal-cut analogy treated as proof |
| `ANAL-01` | Frontier gap map | Gao24 and newer anchors added during execution | 2014-2016 anchor baseline | “Recent” label used without checking whether the paper changes the derivation question |
| `VALD-01` | Anchor audit | Full arXiv anchor registry | Result registry | Unsupported synthesis claims |
| `VALD-02` | False-progress rejection checklist | ADH14, RTN16 | Gap-analysis template | Qualitative support counted as derivation |

## Traceability

| Requirement | Phase | Status |
| ----------- | ----- | ------ |
| `DERV-01` | 1 | Planned |
| `DERV-02` | 3 | Planned |
| `ANAL-01` | 4 | Planned |
| `VALD-01` | 1 | Planned |
| `VALD-02` | 4 | Planned |

**Coverage:**

- Primary requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0

---

_Requirements defined: 2026-04-09_
_Last updated: 2026-04-09 after initialization bootstrap_
