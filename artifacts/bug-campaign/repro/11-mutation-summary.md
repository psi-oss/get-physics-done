# Phase 11 Mutation Summary

## phase-add-ordering

- kind: `sequential`
- promotion_state: `held`
- oracle_verdict: `fail`
- threshold_hits: `0/2`
- failure_reason_code: `sequential_threshold_not_met`

## state-update-serialization

- kind: `sequential`
- promotion_state: `promoted`
- oracle_verdict: `pass`
- threshold_hits: `2/2`

## manual-plan-drift

- kind: `sequential`
- promotion_state: `promoted`
- oracle_verdict: `pass`
- threshold_hits: `2/2`

## session-refresh-repair

- kind: `sequential`
- promotion_state: `promoted`
- oracle_verdict: `pass`
- threshold_hits: `2/2`

## contract-shape-misuse

- kind: `sequential`
- promotion_state: `held`
- oracle_verdict: `fail`
- threshold_hits: `0/2`
- failure_reason_code: `sequential_threshold_not_met`

## dual-writer-ordering-race

- kind: `race`
- promotion_state: `held`
- oracle_verdict: `fail`
- threshold_hits: `0/5`
- failure_reason_code: `race_threshold_not_met_after_retry`
