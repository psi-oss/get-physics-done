---
template_version: 1
type: knowledge-template
---

# Knowledge Template

Knowledge documents are reviewed, project-scoped topic syntheses. They are not
convention ledgers, not literature reviews, not research maps, not result stores,
and not verification artifacts.

Use this template for the canonical markdown body of a knowledge document
authored through `gpd:digest-knowledge`. The frontmatter shown below matches the
enforced schema and should be treated as the only accepted structure for draft
create/update work in this phase. Promotion to `stable` is handled by
`gpd:review-knowledge`, not by this draft-authoring workflow.

## Frontmatter

```yaml
---
knowledge_schema_version: 1
knowledge_id: K-renormalization-group-fixed-points
title: Renormalization Group Fixed Points
topic: renormalization-group
status: draft
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
sources:
  - source_id: lit-ref-einstein-1905
    kind: paper
    locator: Einstein, Annalen der Physik, 1905
    title: On the Electrodynamics of Moving Bodies
    why_it_matters: Foundational reference for the topic under review
coverage_summary:
  covered_topics:
    - fixed-point stability
  excluded_topics:
    - migration/backfill for older or provisional docs
  open_gaps:
    - review approval
---
```

Rules:

- `knowledge_schema_version` must be `1`.
- `knowledge_id` must be the filename stem exactly.
- `status` must be one of `draft`, `in_review`, `stable`, or `superseded`.
- `sources` must be a list of typed records, not free-form strings.
- `coverage_summary` must remain structured and machine-readable.
- `updated_at` should reflect the latest substantive edit to the document.
- `stable` requires a fresh approved review record and must not be used by the draft authoring workflow.

## Title And Scope

State the topic clearly and keep the scope narrow. The document should explain
what the project now intends to trust enough to reference downstream, not every
fact the team knows about the subject.

## Reviewed Synthesis

Summarize the reviewed understanding in concise prose. Prefer explicit claims,
key caveats, and the practical implications for project work.

## Sources

List the reviewed sources in the same order they appear in frontmatter. Each
source should be identifiable by stable ID and concrete locator, and it should
be clear why the source matters to the topic.

## Coverage Summary

Explain what the document covers, what it intentionally excludes, and what
remains unresolved.

## Review

This section is required only for `stable` documents.

Document the review evidence in a typed and auditable way. Include the review
round, reviewer kind, reviewer identity, review timestamp, decision, a concise
summary, a canonical approval artifact path, the artifact hash, the reviewed
content hash, and whether the approval is stale.

If the document is still in review, preserve any prior review record but mark it
stale when the content has changed or when a new round is needed.

## Supersession

This section is required only for `superseded` documents.

Record the document that replaces this one and keep the original file in place as
historical record. Supersession should be explicit and should not rely on filename
heuristics. Keep the trust boundary honest: supersession is a replacement record,
not a claim that the old synthesis is still current.

## Deferred Behaviors

The public authoring command and help coverage are part of the supported surface
now. The following behaviors are intentionally out of scope for Phase 1 and
later rollout hardening work, even if they may appear in future work:

- migration/backfill for older or provisional docs
- alias repair or filename/ID normalization for legacy docs
- beginner onboarding exposure
- `knowledge_deps` and `related_artifacts` frontmatter support
- implicit discovery outside the canonical `knowledge` layout contract
- automatic promotion of a draft to stable without review

## Notes

Use this file as the authoring-facing template only. The schema rules and
validation logic are defined separately, and any future migration/backfill or
onboarding behavior must be implemented separately before this document can be
treated as anything more than a template.
