---
template_version: 1
type: internal-comparison
---

# Internal Comparison Template

Template for machine-readable internal comparisons such as analytics vs numerics, cross-method checks, or baseline vs current runs.

---

## File Template

```markdown
---
comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other
comparison_sources:
  - label: theory
    kind: derivation|simulation|summary|verification|artifact|other
    path: .gpd/phases/01-example/01-SUMMARY.md
  - label: benchmark
    kind: summary|verification|artifact|reference|other
    path: .gpd/phases/02-example/02-VERIFICATION.md
comparison_verdicts:
  - subject_id: claim-id
    subject_kind: claim|deliverable|acceptance_test|artifact
    subject_role: decisive|supporting|supplemental
    reference_id: ref-id
    comparison_kind: benchmark|prior_work|experiment|cross_method|baseline
    metric: relative_error|chi2_ndof|pull|consistency
    threshold: "<= 0.01"
    verdict: pass|tension|fail|inconclusive
    recommended_action: "[what to do next]"
---

# Internal Comparison: [Short Title]

## What Is Being Compared

| Quantity / Artifact | Source A | Source B | Shared Parameters | Metric | Threshold |
| ------------------- | -------- | -------- | ----------------- | ------ | --------- |
| [observable] | [artifact or path] | [artifact or path] | [regime / settings] | [metric] | [rule] |

## Convention And Normalization Check

- [ ] Observable definitions match
- [ ] Units / normalization match
- [ ] Threshold is tied to the right contract target or benchmark anchor
- [ ] No decisive target was replaced by a weaker proxy

## Results

| Subject | Metric Value | Verdict | Notes |
| ------- | ------------ | ------- | ----- |
| [claim-id] | [value] | [pass/tension/fail] | [why] |

## Follow-Up

- [Action to take if any verdict is not a clean pass]
```

When the comparison is decisive for a contract-backed claim or deliverable, `comparison_verdicts` is required.
