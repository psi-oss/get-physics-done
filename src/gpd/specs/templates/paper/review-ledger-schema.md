---
template_version: 1
type: review-ledger-schema
---

# Review Ledger Schema

Canonical source of truth for `.gpd/review/REVIEW-LEDGER.json` (or `.gpd/review/REVIEW-LEDGER{round_suffix}.json` in revision rounds).

This ledger is the persistent issue tracker shared between staged peer review, final adjudication, and author response.

---

## Required Shape

```json
{
  "version": 1,
  "round": 1,
  "manuscript_path": "paper/main.tex",
  "issues": [
    {
      "issue_id": "REF-001",
      "opened_by_stage": "physics",
      "severity": "major",
      "blocking": true,
      "claim_ids": ["CLM-001"],
      "summary": "The physical interpretation outruns the evidence.",
      "rationale": "The manuscript extrapolates beyond the tested regime.",
      "evidence_refs": ["paper/main.tex#discussion"],
      "required_action": "Restrict the claim or add the missing comparison.",
      "status": "open"
    }
  ]
}
```

---

## Field Rules

- `opened_by_stage` must be one of: `reader`, `literature`, `math`, `physics`, `interestingness`, `meta`.
- `severity` must be one of: `critical`, `major`, `minor`, `suggestion`.
- `status` must be one of: `open`, `carried_forward`, `resolved`.
- Keep issue IDs stable across rounds whenever the concern is the same issue being carried forward.
- Every blocking issue that remains unresolved at final adjudication should appear in `REFEREE-DECISION.json` `blocking_issue_ids`.
- If you validate the matching referee decision with `--ledger`, duplicate `issue_id` values or missing blocker cross-links should fail that cross-artifact check.

---

## Validation Command

```bash
gpd validate review-ledger .gpd/review/REVIEW-LEDGER{round_suffix}.json
```
