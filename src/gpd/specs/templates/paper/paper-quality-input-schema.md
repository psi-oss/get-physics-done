---
template_version: 1
type: paper-quality-input-schema
---

# Paper Quality Input Schema

Canonical source of truth for manual `PaperQualityInput` JSON passed to `gpd validate paper-quality`.

Prefer the artifact-driven path when possible:

```bash
gpd --raw validate paper-quality --from-project .
```

Use a manual JSON file only when the artifact-driven path cannot infer the evidence you need. In that case, match the model fields exactly and validate before relying on the score.

---

## Top-Level Fields

The JSON object accepts these top-level fields:

- `title`
- `journal`
- `equations`
- `figures`
- `citations`
- `conventions`
- `verification`
- `completeness`
- `results`
- `journal_extra_checks`

Each category is itself a structured object, not a scalar or free-form string. Omitted categories fall back to the model defaults, which are conservative and usually lower the score rather than silently marking a check as passed.

Unknown fields are rejected. Manual JSON must use the canonical field names exactly.

---

## Example Shape

```json
{
  "title": "Benchmark-validated EFT calculation",
  "journal": "prd",
  "equations": {
    "labeled": {"satisfied": 9, "total": 10},
    "symbols_defined": {"satisfied": 8, "total": 10},
    "dimensionally_verified": {"satisfied": 4, "total": 5},
    "limiting_cases_verified": {"satisfied": 3, "total": 4}
  },
  "figures": {
    "axes_labeled_with_units": {"satisfied": 5, "total": 5},
    "error_bars_present": {"satisfied": 4, "total": 5},
    "referenced_in_text": {"satisfied": 5, "total": 5},
    "captions_self_contained": {"satisfied": 4, "total": 5},
    "colorblind_safe": {"satisfied": 5, "total": 5},
    "decisive_artifacts_labeled_with_units": {"satisfied": 3, "total": 3},
    "decisive_artifacts_uncertainty_qualified": {"satisfied": 3, "total": 3},
    "decisive_artifacts_referenced_in_text": {"satisfied": 3, "total": 3},
    "decisive_artifact_roles_clear": {"satisfied": 3, "total": 3}
  },
  "citations": {
    "citation_keys_resolve": {"satisfied": 14, "total": 14},
    "missing_placeholders": {"passed": true},
    "key_prior_work_cited": {"passed": true},
    "hallucination_free": {"passed": true}
  },
  "conventions": {
    "convention_lock_complete": {"passed": true},
    "assert_convention_coverage": {"satisfied": 7, "total": 7},
    "notation_consistent": {"passed": true}
  },
  "verification": {
    "report_passed": {"passed": true},
    "contract_targets_verified": {"satisfied": 9, "total": 10},
    "key_result_confidences": [
      "INDEPENDENTLY CONFIRMED",
      "STRUCTURALLY PRESENT"
    ]
  },
  "completeness": {
    "abstract_written_last": {"passed": true},
    "required_sections_present": {"satisfied": 7, "total": 7},
    "placeholders_cleared": {"passed": true},
    "supplemental_cross_referenced": {"passed": true}
  },
  "results": {
    "uncertainties_present": {"satisfied": 5, "total": 5},
    "comparison_with_prior_work_present": {"passed": true},
    "physical_interpretation_present": {"passed": true},
    "decisive_artifacts_with_explicit_verdicts": {"satisfied": 3, "total": 3},
    "decisive_artifacts_benchmark_anchored": {"satisfied": 3, "total": 3},
    "decisive_comparison_failures_scoped": {"passed": true}
  },
  "journal_extra_checks": {
    "convergence_three_points": true
  }
}
```

---

## Important Notes

- `CoverageMetric` fields use `{ "satisfied": <int>, "total": <int>, "not_applicable": <bool, optional> }`.
- `BinaryCheck` fields use `{ "passed": <bool>, "not_applicable": <bool, optional> }`.
- `verification.key_result_confidences` accepts only `INDEPENDENTLY CONFIRMED`, `STRUCTURALLY PRESENT`, `UNABLE TO VERIFY`, or `UNRELIABLE`.
- The artifact-driven path is conservative. It can infer many figure, citation, verification, completeness, and comparison checks from project artifacts, but some equation and convention checks may still need manual evidence.
- If a category cannot be inferred automatically, do not fake certainty. Either provide a manual JSON input or treat the lower score as a real gap that still needs review.
- Validate malformed inputs before scoring:

```bash
gpd validate paper-quality paper-quality-input.json
```
