---
template_version: 1
purpose: Benchmark record for fixed comparison surfaces, baseline expectations, failure conditions, and preserved blockers
---

# Benchmark Record Template

Template for `.gpd/benchmarks/BM-001.md` -- a durable benchmark record for one decisive benchmark, baseline, or fixed comparison surface.

**Purpose:** Capture the benchmark surface itself before it gets flattened into passing prose or a single comparison verdict. Use one benchmark record when a project needs to preserve the exact baseline, corpus scope, pass condition, blocker state, or failure mode that later comparisons should keep visible.

**Relationship to other files:**

- `REQUIREMENTS.md` names decisive outputs, anchors, benchmarks, and false-progress traps; a benchmark record carries the reusable fixed comparison surface behind those rows
- `paper/internal-comparison.md` records the later verdict of a specific comparison run; a benchmark record defines the benchmark surface that comparison is supposed to respect
- Per-source evidence review notes are for what one source supports or does not support; a benchmark record is for the fixed baseline or comparison target itself
- `BIBLIOGRAPHY.md` may track benchmark citations or prior artifacts; a benchmark record tracks the project-local baseline expectations and blocker state attached to that benchmark
- Phase `SUMMARY.md` and `VERIFICATION.md` files may cite benchmark record IDs when a result depends on a preserved baseline or known failure condition

---

## File Template

```markdown
---
benchmark_record_id: BM-001
benchmark_kind: literature | baseline_run | prior_artifact | dataset | experiment | oracle | other
status: draft | active | retired | superseded
updated: YYYY-MM-DD
contract_links:
  requirements:
    - [REQ-ID]
  claims:
    - [claim-id]
  deliverables:
    - [deliverable-id]
  acceptance_tests:
    - [test-id]
  references:
    - [reference-id]
comparison_artifacts:
  - .gpd/comparisons/example-COMPARISON.md
---

# Benchmark Record: [short benchmark label]

## Benchmark Surface

- Benchmark Kind: [literature / baseline_run / prior_artifact / ...]
- Benchmark Source: [citation, artifact path, dataset ID, or experiment description]
- Shared Regime / Parameters: [what must match for a fair comparison]
- Benchmark Owner: [agent or user]
- Last Reviewed: [YYYY-MM-DD]

## Fixed Scope

- [what corpus, regime, observable, or artifact family this record covers]
- [what later comparisons should not silently swap out]

## Baseline Expectations

| Quantity / Artifact | Expected Surface | Pass Condition | Why It Matters |
| ------------------- | ---------------- | -------------- | -------------- |
| [observable] | [reference value, artifact, or trend] | [threshold or rule] | [decisive reason] |

## Canonical Failure Conditions

- [what counts as a real miss]
- [which weaker proxy should not be accepted instead]

## Preserved Blockers / Known Tensions

- [missing normalization, unresolved convention mismatch, absent dataset slice, or known benchmark tension]
- [anything that must stay visible even after partial progress]

## Downstream Uses

- [artifact path] — [how this record constrains or supports it]

## Rerun / Recheck Triggers

- [what should cause this record to be revisited]
```

<lifecycle>

**Creation:** When a benchmark, baseline, or fixed comparison surface becomes load-bearing

- Create one record per decisive benchmark surface, not one giant benchmark dump
- Start from the exact thing later comparisons must stay faithful to
- Link the record to the closest requirements, claims, deliverables, or acceptance tests it constrains

**Appending / Updating:** After new comparison runs, normalization fixes, or benchmark rereads

- Tighten pass conditions when the decisive threshold becomes clearer
- Update canonical failure conditions when a misleading proxy shows up in practice
- Keep preserved blockers visible until they are truly resolved
- Mark `status: superseded` when a more accurate benchmark record replaces this one

**Reading:** By planning, verification, comparison, and paper-writing agents

- Use benchmark records before deciding whether a new comparison actually checks the decisive target
- Carry forward preserved blockers and known tensions into verification and writing
- Cite the benchmark record ID when a figure, table, or referee response depends on the exact same baseline surface

</lifecycle>

<guidelines>

**What belongs in a benchmark record:**

- One decisive benchmark, baseline, or fixed comparison surface
- The exact scope later work should preserve
- Baseline expectations and pass conditions
- Canonical failure conditions and preserved blockers
- Pointers to the artifacts that rely on this benchmark surface

**What does NOT belong here:**

- Full comparison verdict tables for each rerun
- Per-source support-boundary notes
- General literature review prose
- Whole-project status tracking unrelated to a specific benchmark surface

**When filling this template:**

- Prefer one benchmark record per decisive surface rather than combining unrelated baselines
- Name the shared regime or parameters explicitly so later comparisons stay honest
- Record blockers that should survive a partial improvement instead of getting buried
- Write failure conditions in terms of what should be rejected, not only what success looks like
- Link only the contract or artifact surfaces that genuinely depend on this benchmark

**Why this artifact matters:**

- Prevents benchmark expectations from dissolving into vague “looks close enough” prose
- Preserves blocker state across long projects and paper rewrites
- Makes baseline-vs-current comparisons easier to audit because the decisive surface is already written down
- Creates a durable bridge between requirement anchors and later comparison verdicts without changing contract results machinery

</guidelines>
