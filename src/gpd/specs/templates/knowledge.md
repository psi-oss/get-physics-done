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
create/update work in this phase.

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
    - downstream runtime ingestion
  open_gaps:
    - reviewer sign-off
---
```

Rules:

- `knowledge_schema_version` must be `1`.
- `knowledge_id` must be the filename stem exactly.
- `status` must be one of `draft`, `stable`, or `superseded`.
- `sources` must be a list of typed records, not free-form strings.
- `coverage_summary` must remain structured and machine-readable.
- `updated_at` should reflect the latest substantive edit to the document.

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

Document the review evidence in a typed and auditable way. Include the reviewer,
review timestamp, decision, a concise summary, and at least one concrete evidence
pointer such as an artifact path, commit SHA, trace ID, or audit artifact path.

## Supersession

This section is required only for `superseded` documents.

Record the document that replaces this one and keep the original file in place as
historical record. Supersession should be explicit and should not rely on filename
heuristics.

## Deferred Behaviors

The public authoring command and help coverage are part of the supported surface
now. The following behaviors are intentionally out of scope for Phase 1 and
later runtime phases, even if they may appear in future work:

- runtime ingestion into planner, verifier, or executor context
- beginner onboarding exposure
- automatic migration
- `knowledge_deps` and `related_artifacts` frontmatter support
- implicit discovery outside the canonical `knowledge` layout contract

## Notes

Use this file as the authoring-facing template only. The schema rules, validation
logic, and any future runtime integration must be defined and implemented
separately before this document can be treated as anything more than a template.
