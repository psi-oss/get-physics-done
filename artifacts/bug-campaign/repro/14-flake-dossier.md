# Phase 14 Flake Dossier

## Summary

- deterministic_slices: `5`
- flaky_slices: `0`
- not_actionable_slices: `0`
- parked_slices: `1`

## Slice Results

### `01-summary-missing-return-20-hubeny`

- final_status: `deterministic`
- stable_signature: `summary validate=true; validate-return=true; health=warn; latest return envelope present; warnings stable across 5/5 runs`
- attempt_count: `5`

### `02-summary-missing-return-05-silverstein`

- final_status: `deterministic`
- stable_signature: `frontmatter validate missing phase/plan/depth/provides/completed; validate-return reports No gpd_return YAML block found; health fails on the latest return envelope with the same orphan-summary and empty-phase warnings`
- attempt_count: `5`

### `03-placeholder-conventions-04-wang`

- final_status: `deterministic`
- stable_signature: `health: overall=warn, fail=0, warn=4; convention check: complete=false, missing_count=12, set_count=6`
- attempt_count: `5`

### `04-placeholder-conventions-21-weng`

- final_status: `deterministic`
- stable_signature: `complete=true; missing=[]; set_count=18; missing_count=0; literal_not_set_counted_as_populated`
- attempt_count: `5`

### `05-placeholder-conventions-07-maxfield`

- final_status: `deterministic`
- stable_signature: `list_sha256=e3d519dcf2ef4a6ed2a37aa57921b53a36719152c5d0e0f93fc08adae295d9d3; check_sha256=517db2e7ce4ac95fdf426bd4865b85152f5f269d15a8fc0fe600849632aa072a; convention list => total=18, set_count=18, unset_count=0; convention check => complete=true, missing=[], set_count=18`
- attempt_count: `5`

### `06-residual-queue-parking`

- final_status: `parked`
- stable_signature: `missing comparator or replay anchor`
- attempt_count: `1`

## Interpretation

- `summary-missing-return` is not flaky. Its clean-miss slice on `20-hubeny` and its repro slice on `05-silverstein` are each internally deterministic.
- `placeholder-conventions` is not flaky. The `04-wang` clean-miss slice and the `21-weng` / `07-maxfield` repro slices are each internally deterministic.
- The remaining queue entries still lack a stable comparator or replay anchor and stay parked rather than entering soak.
