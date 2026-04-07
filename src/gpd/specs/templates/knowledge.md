---
template_version: 1
---

# Knowledge Document Template

Template for `GPD/knowledge/NNN-slug.md` — reviewed domain knowledge with a trust lifecycle.

**Purpose:** Capture domain understanding in a reviewable form before computation depends on it. Unlike RESEARCH.md (one-shot, phase-scoped), knowledge documents are project-scoped, reviewed, and carry an explicit trust status.

**Lifecycle:** Draft → Under Review → Stable → Superseded. Only Stable documents should be cited as dependencies by downstream results and plans.

**Relationship to other files:**

- `RESEARCH.md` is a phase-scoped exploration report — consumed by the planner, then largely forgotten
- `INSIGHTS.md` is an append-only pattern ledger — records what went wrong, not what is known
- `CONVENTIONS.md` is the prescriptive convention catalog — governs signs, normalizations, units
- Knowledge documents capture *domain understanding* — what the key results are, how they connect, where the traps lie

---

## File Template

```markdown
---
kdoc_id: K-NNN-slug
status: Draft
topic: "[topic name]"
sources:
  - "[arXiv:XXXX.XXXXX or DOI or textbook reference]"
created: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
review_rounds: 0
superseded_by: null
---

# Knowledge: [Topic Title]

## Overview

[2-5 sentences: what this document covers and why it matters for the project.]

## Key Results

1. [Result statement with equation reference, e.g., "The 4-point KZ connection matrix is given by eq. (K.3)"]
2. [...]

## Equations

[Key equations, each with context. Use LaTeX. Number as (K.1), (K.2), etc.]

(K.1) $equation$
Context: [where this comes from, when it applies]

(K.2) $equation$
Context: [...]

## Conventions

[All conventions used in this document. Cross-reference with CONVENTIONS.md where applicable.]

- Metric signature: [...]
- Normalization: [...]
- Index ranges: [...]

## Derivation Sketches

[For each key result: the essential derivation steps, or a pointer to a full derivation elsewhere.]

## Connections

[How this topic connects to other knowledge documents or project artifacts.]

- Related to K-NNN: [...]
- Used by Phase X: [...]

## Open Questions

[What is NOT known or NOT settled.]

- [...]

## Traps and Subtleties

[Common mistakes, easy-to-miss sign errors, convention clashes between papers.]

- [...]
```

---

## Guidelines

- **One topic per document.** "Metric conventions in curved-space QFT" is good. "Everything about QFT" is too broad.
- **Cite specific equations.** "Peskin-Schroeder eq. (7.84)" not "standard result."
- **Flag convention clashes.** If Paper A uses (+−−−) and Paper B uses (−+++), say so explicitly.
- **Traps section is mandatory.** Every topic has subtleties. If you can't think of any, you haven't understood the topic well enough.
- **Status discipline.** Don't mark Stable until a human has reviewed. Draft is honest; premature Stable is dangerous.
