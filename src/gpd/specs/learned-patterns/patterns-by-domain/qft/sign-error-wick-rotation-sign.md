---
domain: qft
category: sign-error
severity: critical
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Wrong sign in Wick rotation

**What goes wrong:** Wick rotation t -> -i*tau must respect pole structure. Direction depends on metric signature.

**Why it happens:** See cross-project-patterns.md for root cause analysis.

**How to detect:** Check Euclidean action is bounded below. Verify Euclidean propagator is positive.

**How to prevent:** With (+,-,-,-), rotate k0 -> ik4 counterclockwise. Verify Minkowski -> Euclidean mapping.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
