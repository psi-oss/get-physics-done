# Phase 00 Campaign Charter

## Frozen Source Corpus

- copied bundle root: `tmp/handoff-bundle`
- original batch root: `/Users/sergio/GitHub/gpd-stress-test/automation/runs/full-main-pass-20260409T013855`
- original verification root: `/Users/sergio/GitHub/gpd-stress-test/automation/runs/full-main-pass-20260409T013855/verification-02`
- generated_at: `2026-04-09T20:22:54.484195`
- candidate_count: `1356`
- experiment_instance_count: `66`
- status_counts: `{'heuristic_candidate': 314, 'needs_manual_repro': 1041, 'verified_from_source': 1}`
- category_counts: `{'citation_verification': 52, 'crash': 192, 'cross_system_inconsistency': 492, 'data_loss': 57, 'incorrect_output': 204, 'missing_feature': 69, 'other': 107, 'schema_validation': 182, 'verification_gap': 1}`

## Output Root

The tracked campaign output root is `artifacts/bug-campaign`.  The ignored
`tmp/handoff-bundle` tree is treated as read-only source evidence.

## Source Hashes

```json
{
  "master_plan_sha256": "2175a1586761f96e40e499c8aae7a76cdec6a32025462f573d30f97aaaa83eb2",
  "raw_bugs_json_sha256": "dbe6390f2153325b71c279f482743c75cecbdee28bce0e7b195468b297e2f765",
  "verified_json_sha256": "89c15673157ec21ec4b29ffb152bf676168c0b4684c874ea68f566efbb374bc4"
}
```
