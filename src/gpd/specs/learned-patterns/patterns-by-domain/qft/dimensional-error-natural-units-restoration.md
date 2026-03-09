---
domain: qft
category: dimensional-error
severity: high
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Dimensional mismatch when restoring hbar and c

**What goes wrong:** When converting from natural units to SI, each quantity needs specific powers of hbar and c.

**Why it happens:** See cross-project-patterns.md for root cause analysis.

**How to detect:** Check final expression has correct SI dimensions. Evaluate numerically in both systems.

**How to prevent:** Use systematic procedure based on mass dimension.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
