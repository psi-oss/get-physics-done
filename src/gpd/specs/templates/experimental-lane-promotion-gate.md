---
template_version: 1
purpose: Bounded pilot artifact for deciding whether an optional tool or workflow lane should be promoted, kept experimental, or paused
---

# Experimental Lane Promotion Gate Template

Template for `.gpd/experimental-lanes/XL-001.md` -- a bounded pilot record for one optional tool, workflow variant, or helper lane.

**Purpose:** Capture the decision surface for an experimental lane before it spreads into normal project use. Use one promotion-gate artifact when a project needs to define pilot scope, benchmark surface, success criteria, blocking conditions, and the final `promote` / `keep_experimental` / `pause` decision for a non-core lane.

**Relationship to other files:**

- `settings.md` configures the current runtime and workflow toggles; a promotion gate records whether an optional lane should keep existing at all
- `record-insight.md` captures lessons discovered during work; a promotion gate captures the bounded pilot and resulting scope decision
- `learned-pattern.md` is for reusable recurring patterns; a promotion gate is for deciding whether one optional lane should graduate into standard project use
- A benchmark artifact or other fixed comparison surface may define the decisive test for the pilot; a promotion gate points to that benchmark surface rather than replacing it
- `SUMMARY.md` and `VERIFICATION.md` may cite promotion-gate IDs when a result or recommendation depends on the lane decision

---

## File Template

```markdown
---
experimental_lane_id: XL-001
lane_name: [tool, workflow variant, or helper name]
lane_kind: tool | workflow | verifier | integration | helper | other
status: draft | active_pilot | decided | superseded
decision: undecided | promote | keep_experimental | pause
updated: YYYY-MM-DD
pilot_scope:
  - [what the lane is allowed to touch in this pilot]
benchmark_artifacts:
  - .gpd/benchmarks/BM-001.md
downstream_artifacts:
  - .gpd/phases/01-example/01-VERIFICATION.md
---

# Experimental Lane Promotion Gate: [short lane label]

## Lane Under Review

- Lane Name: [tool / workflow / helper]
- Lane Kind: [tool / workflow / verifier / integration / ...]
- Owner: [agent or user]
- Review Date: [YYYY-MM-DD]

## Pilot Scope

- [what the pilot is allowed to do]
- [what it is explicitly not allowed to broaden into]

## Benchmark Surface

- [which benchmark record, comparison artifact, or acceptance test defines success]
- [what the lane must preserve to be considered honest]

## Promotion Criteria

| Criterion | Evidence Needed | Pass Condition | Failure Trigger |
| --------- | --------------- | -------------- | --------------- |
| [criterion] | [artifact / benchmark / review surface] | [rule] | [what blocks promotion] |

## Pilot Results

| Surface | Result | Status | Notes |
| ------- | ------ | ------ | ----- |
| [benchmark or artifact] | [what happened] | [pass / partial / fail / unresolved] | [why] |

## Decision

- Decision: [promote / keep_experimental / pause / undecided]
- Rationale: [short explanation tied to pilot evidence]

## Next Allowed Scope

- [what the lane may do next if promoted or kept experimental]
- [what should stay blocked]

## Revisit Triggers

- [what new evidence or blocker resolution should reopen this gate]
```

<lifecycle>

**Creation:** When a new optional lane becomes tempting enough that the project needs a bounded pilot instead of informal drift

- Create one promotion gate per optional lane, not one file for every experimental idea
- Define pilot scope before the lane fans out into multiple artifacts
- Link the gate to the benchmark surface that will judge the lane honestly

**Appending / Updating:** After pilot runs, reviewer feedback, or benchmark rereads

- Tighten promotion criteria when the benchmark surface becomes clearer
- Record partial or unresolved outcomes instead of flattening them into success language
- Update the next allowed scope so the lane does not silently widen
- Mark `status: superseded` when a later gate replaces this one

**Reading:** By planners, verifiers, and project leads

- Use promotion gates to keep optional lanes bounded while they are still uncertain
- Check the decision and next-allowed-scope fields before assuming a lane is part of normal project flow
- Cite the gate ID when a manuscript, verification note, or roadmap choice depends on the lane decision

</lifecycle>

<guidelines>

**What belongs in a promotion gate:**

- One optional lane and one bounded pilot decision surface
- Explicit pilot scope and non-goals
- The benchmark or acceptance surface used to judge the lane
- Promotion criteria, failure triggers, and revisit triggers
- A final decision tied to actual pilot evidence

**What does NOT belong here:**

- Runtime configuration details that belong in `.gpd/config.json`
- General project status tracking unrelated to the lane
- Whole-program roadmap prose
- Benchmark details that should live in a benchmark record

**When filling this template:**

- Keep scope narrow enough that the decision can actually be made
- Prefer benchmark-backed criteria over vague “seems useful” language
- Record blocked or partial outcomes directly
- Write the next allowed scope as a constraint, not as a wishlist
- Use `keep_experimental` when the lane is useful but not yet safe to normalize

**Why this artifact matters:**

- Prevents optional lanes from becoming de facto project policy without review
- Preserves the difference between a promising pilot and a promoted default
- Makes later audits easier because the promotion decision is already tied to evidence
- Creates a small governance surface without entangling runtime config or core execution state

</guidelines>
