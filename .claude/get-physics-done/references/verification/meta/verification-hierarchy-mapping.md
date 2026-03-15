---
load_when:
  - "verification hierarchy"
  - "plan-checker verifier mapping"
  - "cross-agent verification"
tier: 2
context_cost: small
---
# Verification Hierarchy Mapping

Maps verification responsibilities across the three verification agents: plan-checker, verifier, and consistency-checker. Load this when you need to understand scope boundaries or cross-reference checks between agents.

---

## Agent Scope Boundaries

| Agent | Scope | Timing | Subject | Key Question |
|---|---|---|---|---|
| **gpd-plan-checker** | Plan DESIGN quality | Before execution | Plans (PLAN.md) | Will these plans achieve the goal? |
| **gpd-verifier** | Within-phase RESULT correctness | After execution | Research outputs | Did the results achieve the goal? |
| **gpd-consistency-checker** | Between-phase CONSISTENCY | After any phase | Convention locks, provides/consumes chains | Are phases consistent with each other? |

**Non-overlapping responsibilities:**
- Plan-checker does NOT verify mathematical correctness — that requires execution results
- Verifier does NOT evaluate plan design or scope — the plan is already executed
- Consistency-checker does NOT assess within-phase correctness — that's localized to one phase

---

## Plan-Checker 16 Dimensions → Verifier 15 Checks

| Plan-Checker Dimension | Step | Verifier Check(s) | Relationship |
|---|---|---|---|
| Dim 1: Research Question Coverage | 4 | — | Plan design only |
| Dim 2: Task Completeness | 5 | — | Plan design only |
| Dim 3: Mathematical Prerequisites | 6 | 5.8 Math Consistency | Plan: prerequisites available → Verifier: math is correct |
| Dim 4: Approximation Validity | 7 | 5.3 Limiting Cases, 5.11 Plausibility | Plan: regime valid → Verifier: limits recover known results |
| Dim 5: Computational Feasibility | 8 | 5.9 Convergence, 5.12 Statistics | Plan: scaling feasible → Verifier: convergence achieved |
| Dim 6: Validation Strategy | 9 | 5.1-5.15 (all) | Plan: validation planned → Verifier: validation executed |
| Dim 7: Anomaly/Topological | inline | 5.15 Anomalies/Topology | Plan: anomaly awareness → Verifier: anomaly coefficients computed |
| Dim 8: Result Wiring | 10 | Artifact Level 3 (Integration) | Plan: notation consistent → Verifier: artifacts integrated |
| Dim 9: Dependency Correctness | 11 | — | Plan design only |
| Dim 10: Scope Sanity | 12 | — | Plan design only |
| Dim 11: Artifact Derivation | 13 | Step 2 (Must-Haves) | Plan: physics-meaningful truths → Verifier: truths verified |
| Dim 12: Literature Awareness | 14 | 5.10 Literature Agreement | Plan: references exist → Verifier: numerical values match |
| Dim 13: Path to Publication | 15 | — | Plan design only |
| Dim 14: Failure Mode Identification | 16 | — | Plan design only |
| Dim 15: Context Compliance | conditional | — | Plan design only |
| Dim 16: Environment Validation | 16.5 | Code Execution Protocol | Plan: tools available → Verifier: static fallback if not |

---

## Plan-Checker Validation Hierarchy (Dim 6) → Verifier Checks

The plan-checker's Dimension 6 contains an 8-level validation hierarchy that maps to the verifier's detailed checks:

| Plan-Checker Validation Level | Verifier Check | What Plan-Checker Validates | What Verifier Validates |
|---|---|---|---|
| 1. Dimensional analysis | 5.1 Dimensional Analysis | Plan includes unit/dimension checks | Every term traced symbol-by-symbol |
| 2. Symmetry checks | 5.6 Symmetry | Plan verifies transformation properties | Symmetry transformations applied and invariance confirmed |
| 3. Limiting cases | 5.3 Limiting Cases | Plan identifies which limits to check | Each limit independently re-derived with algebra shown |
| 4. Conservation laws | 5.7 Conservation | Plan checks conserved quantities | Conserved quantity computed at multiple points |
| 5. Sum rules / identities | 5.14 Spectral (partially) | Plan includes sum rule verification | Both sides evaluated at test points |
| 6. Numerical cross-checks | 5.2, 5.4, 5.5, 5.9 | Plan includes independent verification method | Spot-checks, cross-checks, convergence tests executed |
| 7. Comparison with literature | 5.10 Literature Agreement | Plan references benchmark values | Computed values compared numerically |
| 8. Comparison with experiment | 5.10 (partially) | Plan includes data comparison | Relative errors computed against data |

---

## Quick-Reference 14 Checks → Verifier 15 Checks

The `../core/verification-quick-reference.md` file lists 14 numbered checks. The verifier uses 15 checks numbered 5.1-5.15. Mapping:

| Quick-Ref # | Quick-Ref Name | Verifier # | Verifier Name |
|---|---|---|---|
| 1 | Dimensional analysis | 5.1 | Dimensional Analysis |
| 2 | Limiting cases | 5.3 | Independent Limiting Case Derivation |
| 3 | Symmetry verification | 5.6 | Symmetry |
| 4 | Conservation laws | 5.7 | Conservation |
| 5 | Numerical convergence | 5.9 | Convergence |
| 6 | Cross-check with literature | 5.10 | Literature Agreement |
| 7 | Order-of-magnitude estimation | 5.11 | Plausibility (includes magnitude checks) |
| 8 | Physical plausibility | 5.11 | Plausibility |
| 9 | Ward identities / sum rules | 5.6, 5.14 | Symmetry + Spectral (distributed) |
| 10 | Unitarity bounds | 5.11 | Plausibility (includes unitarity) |
| 11 | Causality constraints | 5.11 | Plausibility (includes causality) |
| 12 | Positivity constraints | 5.14 | Spectral (includes positivity) |
| 13 | Kramers-Kronig consistency | 5.14 | Spectral |
| 14 | Statistical validation | 5.12 | Statistics |

**Verifier checks without direct quick-reference counterpart:**
- 5.2 Numerical Spot-Check (subsumes quick-ref 7 partially)
- 5.4 Independent Cross-Check
- 5.5 Intermediate Result Spot-Check
- 5.8 Math Consistency (sign errors, index contractions, algebra)
- 5.13 Thermodynamic Consistency (Maxwell relations, response function positivity)
- 5.15 Anomalies/Topology (anomaly coefficients, topological invariants)

---

## Verifier Check Tiers (Priority Under Context Pressure)

| Tier | Checks | Error Coverage | Priority |
|---|---|---|---|
| **Tier 1 (Core)** | 5.1-5.5 (Dimensional, Spot-check, Limits, Cross-check, Intermediate) | ~80% of physics errors | Always complete first |
| **Tier 2 (Structure)** | 5.6-5.8 (Symmetry, Conservation, Math Consistency) | Structural correctness | Complete if budget allows |
| **Tier 3 (Validation)** | 5.9-5.12 (Convergence, Literature, Plausibility, Statistics) | External validation | Complete if budget allows |
| **Tier 4 (Domain)** | 5.13-5.15 (Thermodynamic, Spectral, Anomalies/Topology) | Domain-specific | Skip under pressure unless directly relevant |

---

## Consistency-Checker Audit Points

The consistency-checker operates orthogonally to both plan-checker and verifier. Its checks don't map 1:1 to their hierarchies but instead cross-cut all phases:

| Consistency Check | What It Catches | Related Plan-Checker Dim | Related Verifier Check |
|---|---|---|---|
| Convention compliance | Metric signature drift, Fourier convention change | Dim 8 (Result Wiring) | Convention Assertion Verification (Step 7) |
| Provides/requires chains | Broken data flow between phases | Dim 9 (Dependencies) | Artifact Level 3 (Integration) |
| Sign/factor spot-checks | Factor-of-2pi errors at phase boundaries | Dim 4 (Approximation Validity) | 5.2 Numerical Spot-Check |
| Approximation validity ranges | New parameters violating old approximations | Dim 4 (Approximation Validity) | 5.3 Limiting Cases |
| Notation consistency | Symbol meaning drift across phases | Dim 8 (Result Wiring) | 5.8 Math Consistency |

---

## Profile Comparison Across Agents

| Profile | Plan-Checker | Verifier | Consistency-Checker |
|---|---|---|---|
| **deep-theory** | All 16 dimensions | All 15 checks (5.1-5.15) | Full semantic verification + test values |
| **numerical** | All 16, emphasize 5,6,9,14,16 | All 15, emphasize 5.9,5.2,5.12 | Focus on numerical value consistency |
| **exploratory** | 9 dimensions (skip 3,6,7,12-15) | 7 checks: 5.1,5.2,5.3,5.6,5.7,5.8,5.10 | Structural floor: dimensions + symmetry + conservation + math consistency |
| **review** | All 16 + literature cross-ref | All 15 + literature comparison | Full + literature cross-referencing |
| **paper-writing** | All 16, emphasize 8,11,12,13 | All 15 + notation/figure checks | Notation consistency focus |

## See Also

- `../core/verification-quick-reference.md` — Compact 14-check checklist
- `../core/verification-core.md` — Universal checks (dimensional, limiting cases, symmetry, conservation)
- `../core/verification-patterns.md` — Index pointing to modular verification files
