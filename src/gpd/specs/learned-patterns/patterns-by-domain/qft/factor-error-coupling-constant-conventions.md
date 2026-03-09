---
domain: qft
category: factor-error
severity: high
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Confusing coupling constant conventions

**What goes wrong:** Different sources define coupling as g, g^2, g^2/(4pi), alpha. Combining without converting gives wrong coefficients.

**Why it happens:** See cross-project-patterns.md for root cause analysis.

**How to detect:** Check tree-level amplitude. Verify alpha ~ 1/137.

**How to prevent:** Convert all couplings to single convention before combining.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
