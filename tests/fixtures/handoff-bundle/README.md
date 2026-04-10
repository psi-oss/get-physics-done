# Phase 09 Handoff Bundle Fixtures

This fixture bundle is the minimized Phase 09 control plane derived from the accepted Phase 08 repro queue. It is not a copy of the original handoff bundle, and it is not a copy of the stale `727`-packet scaffold.

## Source Authority

Fixture identity comes from the accepted Phase 08 artifacts:

- `/tmp/gpd-bug-campaign/repro/08-family-manifest.json`
- `/tmp/gpd-bug-campaign/repro/08-repro-queue.json`
- `/tmp/gpd-bug-campaign/repro/08-blocked-candidates.json`
- `/tmp/gpd-bug-campaign/repro/08-priority-board.md`
- `/tmp/gpd-bug-campaign/repro/08-packets/BT-*.md`

The original stress-test workspaces are extraction sources only. They provide bytes and provenance, but they no longer define bug-family identity in this phase.

## Fixture Slugs

The bundle exposes stable canonical fixture roots:

- `completed-phase`
- `empty-phase`
- `plan-only`
- `summary-missing-return`
- `query-registry-drift`
- `resume-handoff`
- `config-readback`
- `context-indexing`
- `placeholder-conventions`
- `resume-recent-noise`
- `mutation-ordering`
- `bridge-vs-cli`

Each slug is a reusable fixture corpus. Some slugs contain a `positive/` anchor only. Others contain both `positive/` and `mutation/` variants when Phase 09 needed an explicit one-axis contrast state.

## Provenance Rules

Every variant carries explicit lineage in `fixture.json`:

- covered `bug_type_id` and `packet_id` values
- anchor candidates
- source workspace paths
- source report paths
- starting snapshot hashes
- command recipes
- expected and actual assertion summaries

Do not infer missing lineage from nearby files. If the manifest and a copied artifact disagree, the manifest and sidecar metadata win.

## Read-Only Source Rule

The source stress-test workspaces are read-only. The builder may copy from them into this fixture tree, but it must never normalize, repair, or mutate the source trees in place.

All actual test execution should happen on disposable temp copies of these fixture workspaces, not inside the fixture tree itself.

## Practical Note

`positive` means canonical anchor snapshot in this phase, not necessarily “passing product behavior.” `mutation` means a deliberate one-axis contrast derived from the same lineage so later repro waves can separate anchor state from controlled perturbation.
