# Phase 10 Wave Summary

- reconstruction_scope: `checked_in_fixture_covered_subset`
- strict_phase10_exit_criteria_met: `false`
- post_fix_copy_run_criteria_met: `true`
- family_count: `5`

## Families

- `state-progress-contradictions`
  - priority_family: `state/progress contradictions`
  - oracle: `repro/10-oracles/state-progress-contradictions.json`
  - script: `repro/10-scripts/state-progress-contradictions.sh`
  - transcript: `repro/10-transcripts/state-progress-contradictions.txt`
  - promotion_status: `not_promoted_partial_reconstruction`
- `query-vs-result-blindness`
  - priority_family: `query-vs-result blindness`
  - oracle: `repro/10-oracles/query-vs-result-blindness.json`
  - script: `repro/10-scripts/query-vs-result-blindness.sh`
  - transcript: `repro/10-transcripts/query-vs-result-blindness.txt`
  - promotion_status: `not_promoted_partial_reconstruction`
- `phase-content-blindness`
  - priority_family: `phase-content blindness`
  - oracle: `repro/10-oracles/phase-content-blindness.json`
  - script: `repro/10-scripts/phase-content-blindness.sh`
  - transcript: `repro/10-transcripts/phase-content-blindness.txt`
  - promotion_status: `not_promoted_partial_reconstruction`
- `unsupported-cli-surface-drift`
  - priority_family: `unsupported CLI surface drift`
  - oracle: `repro/10-oracles/unsupported-cli-surface-drift.json`
  - script: `repro/10-scripts/unsupported-cli-surface-drift.sh`
  - transcript: `repro/10-transcripts/unsupported-cli-surface-drift.txt`
  - promotion_status: `not_promoted_partial_reconstruction`
- `convention-placeholder-completeness`
  - priority_family: `convention placeholder completeness`
  - oracle: `repro/10-oracles/convention-placeholder-completeness.json`
  - script: `repro/10-scripts/convention-placeholder-completeness.sh`
  - transcript: `repro/10-transcripts/convention-placeholder-completeness.txt`
  - promotion_status: `not_promoted_partial_reconstruction`

## Blocking Gap

The checked-in fixture subset makes the priority families runnable and regression-guarded, but the missing historical Phase 10 failure transcripts still block retroactive failure-promotion claims.

## Local Post-Fix Copy Runs

- evidence_json: `repro/10-copy-run-evidence.json`
- evidence_markdown: `repro/10-copy-run-evidence.md`
- green_families: `5/5`
