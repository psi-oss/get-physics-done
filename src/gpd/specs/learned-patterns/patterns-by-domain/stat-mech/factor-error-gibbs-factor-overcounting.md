---
domain: stat-mech
category: factor-error
severity: high
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Missing 1/N! for identical particles

**What goes wrong:** Classical partition function for N identical particles requires 1/N! Gibbs factor.

**Why it happens:** See cross-project-patterns.md for root cause analysis.

**How to detect:** Check entropy extensivity. Check mixing entropy vanishes for identical gases.

**How to prevent:** Always include 1/(N! h^{3N}) in classical partition functions.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
