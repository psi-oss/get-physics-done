---
domain: qft
category: sign-error
severity: critical
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Metric signature mismatch in propagator

**What goes wrong:** Mixing (+,-,-,-) and (-,+,+,+) conventions in the same calculation.

**Why it happens:** See cross-project-patterns.md for root cause analysis.

**How to detect:** Check what k^2 = m^2 means. If on-shell condition looks wrong, suspect signature mismatch.

**How to prevent:** State metric signature at top of every derivation. Check external source conventions.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
