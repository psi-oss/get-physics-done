---
template_version: 1
type: referee-decision-schema
---

# Referee Decision Schema

Canonical source of truth for `GPD/review/REFEREE-DECISION{round_suffix}.json`.

This JSON is the machine-readable adjudication summary consumed by `gpd validate referee-decision`. It must stay semantically aligned with `GPD/REFEREE-REPORT{round_suffix}.md` and `GPD/review/REVIEW-LEDGER{round_suffix}.json`.

---

## Required Shape

```json
{
  "manuscript_path": "paper/topic_stem.tex",
  "target_journal": "jhep",
  "final_recommendation": "major_revision",
  "final_confidence": "medium",
  "stage_artifacts": [
    "GPD/review/STAGE-reader{round_suffix}.json",
    "GPD/review/STAGE-literature{round_suffix}.json",
    "GPD/review/STAGE-math{round_suffix}.json",
    "GPD/review/STAGE-physics{round_suffix}.json",
    "GPD/review/STAGE-interestingness{round_suffix}.json"
  ],
  "central_claims_supported": true,
  "claim_scope_proportionate_to_evidence": false,
  "physical_assumptions_justified": true,
  "proof_audit_coverage_complete": true,
  "theorem_proof_alignment_adequate": false,
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

In loose validation, the runtime model still supplies defaults for many fields. In strict staged review, do not rely on those defaults: every policy-driving field in the example above must be written explicitly, including `final_confidence`, `stage_artifacts`, the evidence and assumption booleans, the theorem-proof audit booleans, the adequacy fields, unresolved issue counts, and `blocking_issue_ids`.

Strict validation treats omitted fields as a policy error even when the default value looks convenient. That prevents optimistic inheritance from silently strengthening the final recommendation.

---

## Field Rules

- In strict staged review, every top-level field in the required-shape example must be set explicitly. Defaults are not a substitute for policy input.
- `final_recommendation` must be one of: `accept`, `minor_revision`, `major_revision`, `reject`.
- `final_confidence` must be one of: `high`, `medium`, `low`.
- In strict staged review, `manuscript_path` must be non-empty and must match the manuscript path used by the stage artifacts and review ledger.
- `proof_audit_coverage_complete` must be `false` if any central theorem-bearing claim is missing a Stage 3 `proof_audits[]` entry.
- `theorem_proof_alignment_adequate` must be `false` if any central theorem, proposition, lemma, or corollary is not actually proved as stated, including omitted assumptions, unused quantified parameters, or silent specialization to a narrower case.
- If the matching `CLAIMS{round_suffix}.json` has no theorem-bearing claims, theorem-proof decision flags are not applicable; strict validation treats `false` as explicit N/A and `true` as vacuous coverage/alignment. If theorem-bearing claims are present or the theorem inventory cannot be read, `false` remains blocking.
- Adequacy fields (`mathematical_correctness`, `novelty`, `significance`, `venue_fit`, `literature_positioning`) must be one of: `strong`, `adequate`, `weak`, `insufficient`.
- `stage_artifacts` should list every specialist stage artifact used by the final referee. In strict mode, fewer than five stage artifacts fails validation.
- In strict mode, specialist stage artifact filenames must match `STAGE-(reader|literature|math|physics|interestingness)(-R<round>)?.json`.
- In strict mode, all specialist stage artifacts must use the same optional `-R<round>` suffix; do not mix unsuffixed and suffixed stage names in one decision.
- In strict mode, any extra noncanonical `stage_artifacts` entry fails validation instead of being ignored.
- When the validator has project-root access, every listed `stage_artifacts` path must exist.
- When the validator has project-root access, every listed specialist stage artifact must parse as a valid `StageReviewReport` and must align with the matching `CLAIMS{round_suffix}.json` claim index: filename stage/round, manuscript path, manuscript sha256, `claims_reviewed`, and nested `claim_ids` must all agree with that Stage 1 artifact.
- When the validator has project-root access, a Stage 3 artifact that reviews theorem-bearing claims must also carry matching `proof_audits[]` coverage for those claims.
- `blocking_issue_ids` should be a subset of `REVIEW-LEDGER{round_suffix}.json` `issues[].issue_id`.
- When you validate with `--ledger`, every unresolved blocking issue in the ledger must appear in `blocking_issue_ids`.
- `unresolved_major_issues` should match the count of unresolved `critical` + `major` ledger issues. `unresolved_minor_issues` should match unresolved `minor` ledger issues.
- Recommendation, confidence, issue counts, and blocking issue IDs must match the markdown referee report.
- `{round_suffix}` in path examples means empty for initial review and `-R<round>` (for example `-R2`) for revision rounds.

---

## Validation Command

```bash
gpd validate referee-decision GPD/review/REFEREE-DECISION{round_suffix}.json --strict --ledger GPD/review/REVIEW-LEDGER{round_suffix}.json
```
