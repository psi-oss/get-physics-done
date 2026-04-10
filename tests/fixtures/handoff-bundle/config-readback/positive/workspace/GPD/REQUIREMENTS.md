# Requirements: Error thresholds in holographic codes

**Defined:** 2026-04-09
**Core Research Question:** What threshold landscape is already established for holographic codes, and where is the strongest still-open gap once we separate results by channel, decoder, and code-rate regime?

## Primary Requirements

### Analysis

- [ ] **ANLY-01**: Build a primary-source threshold table covering erasure, depolarizing, and biased-noise results for representative holographic stabilizer codes.
- [ ] **ANLY-02**: Tag every threshold claim by decoder family, noise channel, and zero-rate versus finite-rate regime.
- [ ] **ANLY-03**: Separate true threshold claims from weaker proxies such as fixed-size non-detectable-error probabilities or bulk-specific recovery metrics.

### Comparisons

- [ ] **COMP-01**: Compare the erasure-threshold story across HaPPY-style and heptagon/Steane constructions.
- [ ] **COMP-02**: Compare depolarizing-noise benchmarks across integer-optimization and tensor-network decoders without collapsing decoder differences.
- [ ] **COMP-03**: Determine whether biased-noise threshold results are currently strongest for zero-rate codes and identify any finite-rate counterexamples.

### Validations

- [ ] **VALD-01**: Ensure every threshold statement in the report is backed by a primary reference.
- [ ] **VALD-02**: Flag every cross-paper comparison whose decoder or channel definitions are not directly comparable.
- [ ] **VALD-03**: State the strongest unresolved frontier together with its weakest anchor and disconfirming observation.

### Planning

- [ ] **PLAN-01**: Produce a roadmap for a follow-on threshold project that can close the identified frontier gap.

## Follow-up Requirements

### Numerical Extensions

- **NUMX-01**: Reproduce one published depolarizing-threshold crossing with an independent decoder implementation.
- **NUMX-02**: Generate new finite-rate biased-noise threshold data for at least one holographic code family.

## Out of Scope

| Topic | Reason |
| ----- | ------ |
| Circuit-level syndrome-noise thresholds | Different problem class than code-capacity threshold synthesis |
| Hardware-specific noise tailoring | Requires architecture-specific inputs not present here |
| Non-stabilizer holographic constructions | Would widen scope beyond the current primary benchmark literature |

## Accuracy and Validation Criteria

| Requirement | Accuracy Target | Validation Method |
| ----------- | --------------- | ----------------- |
| ANLY-01 | No missing primary anchor for any threshold value included in the report | Source-by-source audit against cited papers |
| ANLY-02 | Every threshold row names channel, decoder, and rate regime | Manual comparison audit |
| COMP-03 | Frontier claim survives explicit search for finite-rate biased-noise counterexamples | Contradiction search through cited literature |
| VALD-03 | Weakest anchor and disconfirming condition are named explicitly | Report review |

## Contract Coverage

| Requirement | Decisive Output / Deliverable | Anchor / Benchmark / Reference | Prior Inputs / Baselines | False Progress To Reject |
| ----------- | ----------------------------- | ------------------------------ | ------------------------ | ------------------------ |
| ANLY-01 | Final report threshold table | Pastawski 2015; Harris 2018; Harris 2020; Farrelly 2022; Fan 2025 | `project_contract` reference list | Thresholds copied without channel/decoder tags |
| ANLY-03 | Report caveat section | Harris 2020 and Farrelly 2022 decoder contexts | Published benchmark statements only | Treating proxies as asymptotic thresholds |
| COMP-03 | Open-problem statement | Fan 2025 vs earlier finite-rate literature | Current literature sweep | Declaring a frontier without checking for finite-rate counterexamples |
| PLAN-01 | `GPD/ROADMAP.md` | Approved project contract | Current report synthesis | Roadmap that does not surface contract anchors |

## Traceability

| Requirement | Phase | Status |
| ----------- | ----- | ------ |
| ANLY-01 | Phase 1: Literature threshold baseline | Pending |
| ANLY-02 | Phase 1: Literature threshold baseline | Pending |
| ANLY-03 | Phase 2: Decoder and rate normalization | Pending |
| COMP-01 | Phase 1: Literature threshold baseline | Pending |
| COMP-02 | Phase 2: Decoder and rate normalization | Pending |
| COMP-03 | Phase 3: Frontier gap and study design | Pending |
| VALD-01 | Phase 4: Verification and synthesis | Pending |
| VALD-02 | Phase 4: Verification and synthesis | Pending |
| VALD-03 | Phase 4: Verification and synthesis | Pending |
| PLAN-01 | Phase 3: Frontier gap and study design | Pending |

**Coverage:**

- Primary requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---

_Requirements defined: 2026-04-09_
_Last updated: 2026-04-09 after project initialization_
