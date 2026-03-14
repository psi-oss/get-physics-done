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

## Required Top-Level Categories

The JSON object must contain:

- `title`
- `journal`
- `equations`
- `figures`
- `citations`
- `conventions`
- `verification`
- `completeness`
- `results`

Each category is itself a structured object, not a scalar or free-form string.

---

## Example Shape

```json
{
  "title": "Benchmark-validated EFT calculation",
  "journal": "prd",
  "equations": {
    "labeled_displayed_equations": {"satisfied": 9, "total": 10},
    "symbols_defined": {"satisfied": 8, "total": 10},
    "dimensional_checks_passed": {"satisfied": 4, "total": 5},
    "limiting_cases_checked": {"satisfied": 3, "total": 4}
  },
  "figures": {
    "decisive_with_units": {"satisfied": 3, "total": 3},
    "decisive_with_uncertainty": {"satisfied": 3, "total": 3},
    "decisive_referenced_in_text": {"satisfied": 3, "total": 3},
    "captions_self_contained": {"satisfied": 4, "total": 5},
    "colorblind_safe": true
  },
  "citations": {
    "all_citations_resolve": true,
    "missing_placeholders": false,
    "key_prior_work_cited": true,
    "hallucination_free": "passed"
  },
  "conventions": {
    "lock_complete": true,
    "assert_convention_coverage": {"satisfied": 7, "total": 7},
    "notation_consistent": true
  },
  "verification": {
    "report_exists": true,
    "contract_targets_verified": {"satisfied": 9, "total": 10},
    "independent_confirmations": {"satisfied": 4, "total": 5},
    "has_unreliable_results": false
  },
  "completeness": {
    "abstract_matches_results": true,
    "all_required_sections_present": true,
    "has_placeholders": false,
    "supplement_cross_referenced": true
  },
  "results": {
    "key_results_include_uncertainties": true,
    "decisive_comparisons_present": {"satisfied": 3, "total": 3},
    "physical_interpretation_present": true
  }
}
```

---

## Important Notes

- The artifact-driven path is conservative. It can infer many figure, citation, verification, completeness, and comparison checks from project artifacts, but some equation and convention checks may still need manual evidence.
- If a category cannot be inferred automatically, do not fake certainty. Either provide a manual JSON input or treat the lower score as a real gap that still needs review.
- Validate malformed inputs before scoring:

```bash
gpd validate paper-quality paper-quality-input.json
```
