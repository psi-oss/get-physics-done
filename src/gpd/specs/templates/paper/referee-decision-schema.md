---
template_version: 1
type: referee-decision-schema
---

# Referee Decision Schema

Canonical source of truth for `.gpd/review/REFEREE-DECISION.json` (or `.gpd/review/REFEREE-DECISION{round_suffix}.json` in revision rounds).

This JSON is the machine-readable adjudication summary consumed by `gpd validate referee-decision`. It must stay semantically aligned with `.gpd/REFEREE-REPORT.md` and `.gpd/review/REVIEW-LEDGER{round_suffix}.json`.

---

## Required Shape

```json
{
  "manuscript_path": "paper/main.tex",
  "target_journal": "jhep",
  "final_recommendation": "major_revision",
  "final_confidence": "medium",
  "stage_artifacts": [
    ".gpd/review/STAGE-reader{round_suffix}.json",
    ".gpd/review/STAGE-literature{round_suffix}.json",
    ".gpd/review/STAGE-math{round_suffix}.json",
    ".gpd/review/STAGE-physics{round_suffix}.json",
    ".gpd/review/STAGE-interestingness{round_suffix}.json"
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

Only `final_recommendation` is strictly required by the runtime model. Most other fields have defaults, but you should set them explicitly whenever they materially affect the recommendation floor, issue accounting, or strict staged-review validation.

---

## Field Rules

- `final_recommendation` must be one of: `accept`, `minor_revision`, `major_revision`, `reject`.
- `final_confidence` must be one of: `high`, `medium`, `low`.
- Adequacy fields (`mathematical_correctness`, `novelty`, `significance`, `venue_fit`, `literature_positioning`) must be one of: `strong`, `adequate`, `weak`, `insufficient`.
- `stage_artifacts` should list every specialist stage artifact used by the final referee. In strict mode, fewer than five stage artifacts fails validation.
- When the validator has project-root access, every listed `stage_artifacts` path must exist.
- `blocking_issue_ids` should be a subset of `REVIEW-LEDGER.json` `issues[].issue_id`.
- When you validate with `--ledger`, every unresolved blocking issue in the ledger must appear in `blocking_issue_ids`.
- `unresolved_major_issues` should match the count of unresolved `critical` + `major` ledger issues. `unresolved_minor_issues` should match unresolved `minor` ledger issues.
- Recommendation, confidence, issue counts, and blocking issue IDs must match the markdown referee report.

---

## Validation Command

```bash
gpd validate referee-decision .gpd/review/REFEREE-DECISION{round_suffix}.json --strict --ledger .gpd/review/REVIEW-LEDGER{round_suffix}.json
```
