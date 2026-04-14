---
template_version: 1
type: plan-contract-schema-notes
---

# PLAN Contract Schema Notes

## Contract Alignment Rules

- Reduced contracts are legal only when the plan is explicitly scoping or exploratory; otherwise keep the full non-scoping shape with claims, deliverables, acceptance tests, and forbidden proxies.
- Even reduced contracts need a real decision surface: preserve at least one target, open question, or carry-forward input instead of emitting a hollow scaffold.
- When in doubt, classify the plan as non-scoping and retain the full shape.
- References are mandatory only when the contract does not already expose enough grounding through `context_intake`, preserved scoping inputs, or other anchors; `context_gaps`, `crucial_inputs`, and `stop_and_rethink_conditions` keep uncertainty visible but do not satisfy grounding on their own.
- If concrete grounding is missing elsewhere, at least one reference must set `must_surface: true`; otherwise a missing `must_surface` reference is a warning, not a blocker.
- Defaultable semantic fields (`observables[].kind`, `deliverables[].kind`, `acceptance_tests[].kind`, `references[].kind`, `references[].role`, `links[].relation`) default to `other`. Omit them only when `other` is intended, and set a specific literal when the semantics are already known.
- Surface `links[]` explicitly whenever the plan depends on traceable handoffs or decisive comparisons.
- All ID cross-links must resolve to declared IDs, IDs must stay unique across `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `references[]`, and canonical IDs or other required strings are trimmed before validation so blank-after-trim values are invalid.
- A non-object `contract:` value is invalid; treat it as a schema error rather than “missing.”
- Do not assume any contract field is optional unless the active PLAN validator or workflow explicitly allows it.

## Contract Addendum Guidance

- `draft` addenda should note missing gating anchors, blockers, or unresolved questions that keep the contract unapproved.
- `approved` addenda should summarize the approved scope, decisive anchors/baselines, and the deliverables or acceptance tests that carry the approval.
- `proof` addenda should list the proof-specific claim, deliverables, acceptance tests, and metadata that justify the proof stage.
- Limit each addendum to the status label plus one or two short bullets so the schema stays the authoritative source of truth; use the template fields above for detailed coverage.

## Validation Commands

- `gpd frontmatter validate GPD/phases/XX-name/XX-YY-PLAN.md --schema plan`
- `gpd validate plan-contract GPD/phases/XX-name/XX-YY-PLAN.md`

All ID cross-links referenced by these commands must resolve to declared IDs.
