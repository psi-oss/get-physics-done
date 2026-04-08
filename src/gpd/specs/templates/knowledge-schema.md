---
template_version: 1
type: knowledge-schema
---

# Knowledge Schema

Canonical source of truth for knowledge-doc frontmatter and naming rules.

Use this file when you author, revise, or validate a knowledge document through
`gpd:digest-knowledge` or direct frontmatter validation. Do not invent ad-hoc
keys, let filename and ID drift apart, or treat the schema as permissive prose.
Knowledge docs are closed, versioned artifacts.

---

## Required Shape

A knowledge document must be a markdown file at:

```text
GPD/knowledge/{knowledge_id}.md
```

The frontmatter must include these required fields:

- `knowledge_schema_version`
- `knowledge_id`
- `title`
- `topic`
- `status`
- `created_at`
- `updated_at`
- `sources`
- `coverage_summary`

Optional sections may include:

- `review`
- `superseded_by`

Every list named above must contain objects, not strings. Every object-valued
section must stay an object, not a string or list.

---

## `knowledge_schema_version`

```yaml
knowledge_schema_version: 1
```

Rules:

- `knowledge_schema_version` is required and must be the literal integer `1`.
- No other version is supported by this schema.
- Version drift must fail closed instead of being guessed.

---

## `knowledge_id`

```yaml
knowledge_id: K-renormalization-group-fixed-points
```

Rules:

- `knowledge_id` is required and must be a non-empty string.
- `knowledge_id` must be ASCII-safe, lowercase, and slug-like.
- `knowledge_id` must equal the filename stem exactly.
- The canonical filename is `{knowledge_id}.md` under `GPD/knowledge/`.
- Do not encode status, review level, or date in the filename.
- Do not silently repair a mismatched filename or ID.
- If a normalized ID already exists, creation should fail closed unless the caller
  explicitly chooses update or supersede behavior in a later phase.

Recommended character policy:

- lowercase ASCII letters, digits, and hyphens
- no spaces
- no hidden mapping between a display slug and a different stored ID

---

## `title`

```yaml
title: Renormalization Group Fixed Points
```

Rules:

- `title` is required and must be a non-empty string.
- `title` is the human-readable label for the document, not the canonical ID.

---

## `topic`

```yaml
topic: renormalization-group
```

Rules:

- `topic` is required and must be a non-empty string.
- `topic` describes the subject area or question space of the document.
- `topic` may be broader than `knowledge_id`, but it must not contradict it.

---

## `status`

```yaml
status: draft
```

Allowed values:

- `draft`
- `stable`
- `superseded`

Rules:

- `status` is required and must use one of the allowed lowercase literals.
- `draft` is the default authoring state.
- `stable` means the document has been reviewed and carries typed evidence.
- `superseded` means the document has been replaced by a newer knowledge doc.
- `under_review` is intentionally deferred for now and is not part of v1.

---

## `created_at` And `updated_at`

```yaml
created_at: "2026-04-07T00:00:00Z"
updated_at: "2026-04-07T00:00:00Z"
```

Rules:

- Both fields are required.
- Both fields must be ISO 8601 timestamps.
- `updated_at` must be greater than or equal to `created_at`.
- Timestamp drift that cannot be validated should fail closed.

---

## `sources`

```yaml
sources:
  - source_id: lit-ref-einstein-1905
    kind: paper
    locator: "doi:10.1002/andp.19053221004"
    title: "On the Electrodynamics of Moving Bodies"
    why_it_matters: "Foundational anchor for the topic"
```

Rules:

- `sources` is required and must be a list of objects.
- `sources` must be non-empty.
- `sources` are typed records, not prose strings.
- Each source should carry a stable identifier plus a concrete locator.
- Source entries should remain closed and machine-readable; do not add ad-hoc keys.
- Prefer stable IDs and explicit provenance over path-only references.

Recommended minimum source fields:

- `source_id`
- `kind`
- `locator`
- `title`
- `why_it_matters`

Recommended optional source fields:

- `source_artifacts`
- `reference_id`
- `arxiv_id`
- `doi`
- `url`

---

## `coverage_summary`

```yaml
coverage_summary:
  covered_topics: [renormalization-group]
  excluded_topics: [publication-pipeline]
  open_gaps: [numerical-stability]
```

Rules:

- `coverage_summary` is required and must be an object.
- `coverage_summary` must not be a prose blob.
- At minimum, it should expose what the document covers, what it excludes, and what
  remains open.

Recommended fields:

- `covered_topics`
- `excluded_topics`
- `open_gaps`

All list-valued subfields must remain YAML lists.

---

## `review`

```yaml
review:
  reviewed_at: "2026-04-07T12:00:00Z"
  reviewer: gpd-knowledge-reviewer
  decision: approved
  summary: "The document is reviewed and ready for downstream use."
  evidence_path: "GPD/knowledge/reviews/K-renormalization-group-fixed-points-REVIEW.md"
  evidence_sha256: "[optional sha256]"
```

Rules:

- `review` is optional for `draft`.
- `review` is required for `stable`.
- `review` must be a typed object, not a freeform string.
- `stable` without typed review evidence is invalid.
- The review object should include reviewer identity, review timestamp, decision, and
  at least one concrete evidence pointer.
- `evidence_path`, `audit_artifact_path`, `commit_sha`, or `trace_id` are acceptable
  evidence anchors when present, but at least one concrete evidence pointer must exist.

Recommended fields:

- `reviewed_at`
- `reviewer`
- `decision`
- `summary`
- `evidence_path`
- `evidence_sha256`

---

## `superseded_by`

```yaml
superseded_by: K-renormalization-group-fixed-points-v2
```

Rules:

- `superseded_by` is optional for `draft` and `stable`.
- `superseded_by` is required when `status: superseded`.
- `superseded_by` must reference another knowledge document ID, not a prose title.
- `superseded` docs preserve their history in place; do not delete or rewrite away the
  prior record.

---

## Conditional Rules

The following conditional rules are mandatory:

1. `status: draft`
   - `review` must be absent.
   - `superseded_by` must be absent.
2. `status: stable`
   - `review` must be present and non-empty.
   - `sources` must be non-empty.
3. `status: superseded`
   - `superseded_by` must be present and non-empty.
   - `review` must remain present if it existed before supersession.
   - The document must preserve historical content rather than collapsing into an
     in-place rewrite without trace.
4. `updated_at`
   - must not precede `created_at`.
5. `knowledge_id`
   - must equal the filename stem.
6. `knowledge_schema_version`
   - must be exactly `1`.

---

## Explicit Deferrals

Public command registration and shared help coverage are part of the supported
authoring surface now. The remaining runtime-facing behaviors are still
deferred:

1. `under_review` as a shipped status
2. automatic migration of older knowledge files
3. `knowledge_deps` or `related_artifacts` as accepted frontmatter fields
4. runtime ingestion into planner/verifier/executor context
5. project-wide mandatory `GPD/knowledge/` creation
6. heuristic filename repair
7. implicit ID aliasing between differently named files
8. path-only discovery across `GPD/`

These belong to later execution and hardening phases.

---

## Validation Commands

```bash
gpd frontmatter validate GPD/knowledge/{knowledge_id}.md --schema knowledge
```
