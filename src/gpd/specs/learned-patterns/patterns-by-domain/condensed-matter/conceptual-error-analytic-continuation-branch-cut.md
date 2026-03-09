---
domain: condensed-matter
category: conceptual-error
severity: critical
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Wrong branch cut in analytic continuation

**What goes wrong:** Choosing the wrong Riemann sheet when analytically continuing flips the sign of Im[G].

**Why it happens:** See primary pattern at `patterns-by-domain/qft/conceptual-error-analytic-continuation-branch-cut.md`.

**How to detect:** Check spectral function positivity A(k,w) >= 0. Check causality G^R(t<0) = 0.

**How to prevent:** Always continue iwn -> w + ie for retarded functions. Verify poles in lower half-plane.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
