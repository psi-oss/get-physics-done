# Phase 00 Scope

## In Scope

- Ingest all `1356` verifier candidates.
- Preserve raw provenance from nested JSON fields, especially raw source paths and raw spans.
- Separate product-local findings from environment, expected-behavior, and insufficient-detail records.
- Reconstruct only checked-in Phase 08/09 coverage unless original repro artifacts are present.
- Track missing exact repro/transcript gaps explicitly.

## Out Of Scope

- Mutating original stress-test workspaces under `/Users/sergio/GitHub/gpd-stress-test/automation/runs/full-main-pass-20260409T013855`.
- Treating verifier status as fresh reproduction status.
- Promoting `heuristic_candidate` records into closed product bugs without repro packets.
- Copying the full `/tmp/gpd-bug-campaign` workspace tree into git.
