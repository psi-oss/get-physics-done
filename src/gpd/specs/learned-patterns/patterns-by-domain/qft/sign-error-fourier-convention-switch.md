---
domain: qft
category: sign-error
severity: critical
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Sign error in Fourier convention switch

**What goes wrong:** When combining expressions derived with different Fourier conventions, sign errors appear in interference terms, propagators, and response functions.

**Why it happens:** See cross-project-patterns.md for root cause analysis.

**How to detect:** Check the sign of the imaginary part of response functions. Verify retarded/advanced structure.

**How to prevent:** Lock Fourier convention at project start. Insert explicit conversion factors when combining.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
