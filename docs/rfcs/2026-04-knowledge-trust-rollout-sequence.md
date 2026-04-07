# Knowledge Trust Rollout Sequence

Status: companion rollout note for the Phase 0 scope-lock RFC
Date: 2026-04-07

This note describes the intended commit-and-push order for building knowledge-trust
without overstating what is implemented on the remote branch.

The feature should remain experimental until the push and promotion blockers listed
below are cleared.

## Delivery Principle

Knowledge trust should not advance as a single large push.

The safe order is:

1. lock scope
2. repair honesty and any help or test mismatches before public exposure
3. lock naming and schema
4. ship real authoring and update behavior
5. enforce lifecycle and review evidence
6. integrate the shared runtime seam
7. add downstream planner, verifier, and executor visibility
8. finish dependency semantics, health, docs, and migration hardening

## Suggested Commit And Push Sequence

1. Commit/Push 1: honesty cleanup and help/test repair
2. Commit/Push 2: naming and schema contract
3. Commit/Push 3: real authoring and update workflow MVP
4. Commit/Push 4: review evidence and lifecycle enforcement
5. Commit/Push 5: runtime ingestion and query support
6. Commit/Push 6: planner/verifier integration
7. Commit/Push 7: dependency semantics and optional gating
8. Commit/Push 8: health, progress, help, and docs completion
9. Commit/Push 9: migration and rollout hardening

## Push And Promotion Blockers

The branch should not be treated as more than experimental until all of these are
addressed:

1. help inventory and public docs match implemented behavior
2. filename, ID, and storage rules are explicit and enforced
3. `stable` or equivalent reviewed states require structured review evidence
4. create and update behavior is real rather than template-only
5. trusted knowledge is ingested into the shared reference runtime seam
6. downstream workflows can consume that trusted knowledge without ad hoc scraping
7. migration posture is documented and test-covered

## Operational Guardrails

During rollout:

1. do not register or advertise a public command unless help inventory and tests are
   updated in the same change
2. do not document `GPD/knowledge/` as canonical until layout and validation contracts
   exist
3. do not claim planner, verifier, or executor trust integration until the shared
   runtime seam is extended and tested
4. keep beginner onboarding and quick-start surfaces unchanged until the feature is
   stable enough to be part of the normal user path

## Migration Posture

Phase 0 does not define automatic migration.

If any experimental knowledge documents appear before the naming, schema, and
lifecycle phases are complete, they should be treated as provisional artifacts that
may need later migration.

Migration rules belong to the later hardening phases, after the canonical contracts
exist.

## Promotion Rule

Until the blockers are cleared, knowledge trust should be described only as
experimental scaffolding.
