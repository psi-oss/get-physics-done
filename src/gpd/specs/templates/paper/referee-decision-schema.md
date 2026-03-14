---
template_version: 1
type: referee-decision-schema
---

# Referee Decision Schema

Canonical source of truth for `.gpd/review/REFEREE-DECISION.json`.

This JSON is the machine-readable adjudication summary consumed by `gpd validate referee-decision`. It must stay semantically aligned with `.gpd/REFEREE-REPORT.md` and `.gpd/review/REVIEW-LEDGER.json`.

---

## Required Shape

```json
{
  "manuscript_path": "paper/main.tex",
  "target_journal": "jhep",
  "final_recommendation": "major_revision",
  "final_confidence": "medium",
  "stage_artifacts": [
    ".gpd/review/STAGE-reader.json",
    ".gpd/review/STAGE-literature.json",
    ".gpd/review/STAGE-math.json",
    ".gpd/review/STAGE-physics.json",
    ".gpd/review/STAGE-interestingness.json"
  ],
  "central_claims_supported": true,
  "claim_scope_proportionate_to_evidence": false,
  "physical_assumptions_justified": true,
  "unsupported_claims_are_central": false,
  "reframing_possible_without_new_results": true,
  "mathematical_correctness": "adequate",
  "novelty": "adequate",
  "significance": "weak",
  "venue_fit": "adequate",
  "literature_positioning": "adequate",
  "unresolved_major_issues": 2,
  "unresolved_minor_issues": 1,
  "blocking_issue_ids": ["REF-001", "REF-004"]
}
```

---

## Field Rules

- `final_recommendation` must be one of: `accept`, `minor_revision`, `major_revision`, `reject`.
- `final_confidence` must be one of: `high`, `medium`, `low`.
- Adequacy fields (`mathematical_correctness`, `novelty`, `significance`, `venue_fit`, `literature_positioning`) must be one of: `strong`, `adequate`, `weak`, `insufficient`.
- `stage_artifacts` should list every specialist stage artifact used by the final referee. In strict mode, fewer than five stage artifacts fails validation.
- `blocking_issue_ids` should be a subset of `REVIEW-LEDGER.json` `issues[].issue_id`.
- Recommendation, confidence, issue counts, and blocking issue IDs must match the markdown referee report.

---

## Validation Command

```bash
gpd validate referee-decision .gpd/review/REFEREE-DECISION.json --strict
```
