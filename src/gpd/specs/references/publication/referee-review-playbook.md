---
load_when:
  - "referee adjudication"
  - "journal review"
  - "publication review"
  - "review rubric"
  - "revision round"
type: referee-review-playbook
tier: 2
context_cost: medium
---

# Referee Review Playbook

Use this pack when the referee needs the detailed rubric, response strategy, or revision-round guidance. Keep the base referee prompt lean and load this only when the review task needs more than the compact decision contract.

## Compact Adjudication Rule

Start from the manuscript itself. Check claim-evidence proportionality, theorem-to-proof alignment, literature context, and venue fit. If the strongest defensible claim is narrower than the abstract or conclusion, that is a real publication problem.

## Rubric Summary

Judge the paper on these dimensions:

- novelty
- correctness
- clarity
- completeness
- significance
- reproducibility
- literature context
- presentation quality
- technical soundness
- publishability

For each dimension, ask whether the manuscript states a claim, supports it with evidence, and keeps the claim scope proportionate to that evidence.

## Recommendation Floors

- `minor_revision` only for local clarity, citation, or presentation fixes.
- `major_revision` when the physics may survive but the interpretation, significance, or theorem alignment needs narrowing or repair.
- `reject` when the central claim is unsupported, the novelty collapses, or the venue fit is fundamentally weak.

## Revision-Round Guidance

When author responses exist, re-check only the changed content first. Treat new content with the same physical and theorem-proof checks as the original. If a fix introduces a new inconsistency, report that explicitly instead of assuming the revision is globally better.

## Response Strategy

When the journal matters, tune the response style to the venue:

- PRL and Nature-style outlets need strong significance and tight scope.
- PRD/PRB/JHEP-style outlets can tolerate more technical detail, but not unsupported claims.
- Multi-round responses should keep the action items finite and clearly prioritized.

## Report Hygiene

Keep the report concise and machine-readable:

- issue IDs must stay stable across markdown and JSON outputs
- blocking issues should be explicit
- strengths should be acknowledged
- report prose should not duplicate long rubric text
