# REFERENCES.md Template (theory focus)

```markdown
# Reference and Anchor Map

**Analysis Date:** [YYYY-MM-DD]

## Active Anchor Registry

| Anchor ID | Anchor | Type | Source / Locator | Why It Matters | Contract Subject IDs | Must Surface | Required Action | Carry Forward To |
| --------- | ------ | ---- | ---------------- | -------------- | -------------------- | ------------ | --------------- | ---------------- |
| [stable-anchor-id] | [short anchor label] | [benchmark/method/background/prior artifact] | [citation, dataset id, or path] | [claim, observable, deliverable, or convention constrained] | [claim-id, deliverable-id, or blank] | [yes/no] | [read/use/compare/cite/avoid] | [planning/execution/verification/writing] |

> `Anchor ID` should be stable across updates. Prefer an existing project-contract reference ID when one already exists.
>
> `Source / Locator` must be concrete enough to re-find the anchor later: citation, DOI, dataset identifier, artifact path, or similarly durable handle.
>
> `Contract Subject IDs` is optional and lists exact claim/deliverable IDs when known. `Carry Forward To` is workflow stage scope only.
>
> `Must Surface` marks anchors that later planners/verifiers must explicitly carry forward. If omitted, ingestion falls back to the same heuristic used in runtime context assembly: roles like `benchmark`, `definition`, `method`, or `must_consider`, plus required actions such as `use`, `compare`, or `avoid`, promote the anchor automatically.

## Benchmarks and Comparison Targets

- [Benchmark quantity or result]
  - Source: [citation or artifact]
  - Compared in: `[path]`
  - Status: [matched / pending / contested]

## Prior Artifacts and Baselines

- `[path]`: [What this artifact provides and why later phases must keep it visible]

## Open Reference Questions

- [Missing citation, unresolved benchmark, or ambiguous prior result]

## Background Reading

- [Reference]: [Why it is useful context but not currently contract-critical]

---

_Reference map: [date]_
```
