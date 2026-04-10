# Phase 01 Merge Rubric

## Merge

- Same normalized surface id.
- Same broken invariant id.
- Same trigger/precondition.
- Same environment scope.

## Split

- One candidate contains multiple bullet claims with different commands or observed behaviors.
- A claim mixes environment failure with product-local behavior.
- A bridge/runtime failure and a raw CLI failure have different authority surfaces.

## Do Not Promote

- `heuristic_candidate` rows without command evidence.
- Source-confirmed rows as fresh-reproduced bugs.
- Environment-only failures as product-local bugs.
