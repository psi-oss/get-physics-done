---
domain: qft
category: factor-error
severity: high
confidence: systematic
first_seen: 2026-03-09
last_seen: 2026-03-09
occurrence_count: 5
---

## Pattern: Missing factor of 2pi in density of states

**What goes wrong:** The density of states picks up factors of 2pi from Fourier convention and momentum measure.

**Why it happens:** See primary pattern at `patterns-by-domain/condensed-matter/factor-error-density-of-states-2pi.md`.

**How to detect:** Check dimensional analysis. Verify free-particle DOS reproduces known results.

**How to prevent:** Always write momentum integration measure explicitly with (2pi)^d factor.

**Example:** [Example to be added]

**Test value:** [Numerical test to be added]
