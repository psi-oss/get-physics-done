---
template_version: 1
type: structured-evidence-record-schema
---

# Structured Evidence Record Schema

Canonical source of truth for machine-readable accepted evidence records.

Use this file only when a project has already decided to carry accepted evidence objects in a structured form. Do not invent ad-hoc YAML blobs, flatten nuanced evidence into a bare yes/no flag, or treat this as a replacement for bibliography tracking or comparison verdicts.

---

## Purpose

A structured evidence record is the machine-usable companion to evidence review work. It captures:

- which source or artifact the evidence comes from
- what bounded claim or comparison target the evidence addresses
- what level of authority the record should carry
- what the evidence directly supports
- what it does **not** support
- what caveats or blockers must travel with it
- which downstream contract or artifact surfaces are allowed to rely on it

This is for **accepted evidence objects**, not raw literature dumps and not generic project status.

---

## Required Shape

The record must be a YAML object with these top-level fields:

- `schema_version` (optional, defaults to `1`; no other value is supported)
- `evidence_record_id`
- `status`
- `source`
- `claim_scope`
- `authority`
- `support`
- `limits`
- `downstream_links`

Optional sections:

- `comparison_context`
- `uncertainty_markers`
- `notes`

Every list named below must contain objects or strings exactly as described; do not collapse structured sections into a prose paragraph.

---

## Required Fields

### `evidence_record_id`

```yaml
evidence_record_id: er-main
```

Rules:

- Must be a non-empty string after trimming whitespace.
- Should be stable enough for downstream artifacts to reference directly.

### `status`

```yaml
status: draft | accepted | superseded
```

Rules:

- `accepted` means the record is allowed to carry weight downstream.
- `draft` means the structure exists but should not yet be treated as canonical evidence.
- `superseded` means a newer record replaced it.

### `source`

```yaml
source:
  kind: paper | dataset | benchmark | prior_artifact | experiment | review | spec | internal_note | other
  id: ref-main
  locator: "[citation, dataset identifier, or artifact path]"
```

Rules:

- `kind` and `id` are required.
- `locator` is optional but strongly preferred.
- `id` should match an existing reference, benchmark, or stable local artifact label when one exists.

### `claim_scope`

```yaml
claim_scope:
  statement: "[the exact claim, comparison target, or bounded question]"
  subject_kind: claim | deliverable | acceptance_test | reference | artifact | other
  subject_ids: [claim-main, test-main]
```

Rules:

- `statement` is required and must be non-empty after trimming.
- `subject_kind` is required.
- `subject_ids` is optional, but when present it must contain stable IDs rather than prose labels.

### `authority`

```yaml
authority:
  class: promotive | bounded | context_only | negative | mixed | unresolved
  rationale: "[why this authority class is appropriate]"
```

Rules:

- `class` is required.
- `rationale` is required.
- `class` describes how much downstream weight the record should carry, not whether the source exists.

### `support`

```yaml
support:
  direct:
    - "[what the source or artifact directly supports]"
  indirect:
    - "[what it partially suggests but does not establish]"
```

Rules:

- `direct` and `indirect` are optional lists, but at least one of them should be non-empty for an `accepted` record.
- Keep `direct` and `indirect` distinct.

### `limits`

```yaml
limits:
  does_not_support:
    - "[what this evidence does not establish]"
  caveats:
    - "[scope limits, assumptions, or missing checks]"
  blockers:
    - "[anything still preventing broader use]"
```

Rules:

- `does_not_support` and `caveats` are optional, but strongly preferred.
- `blockers` should remain visible until they are genuinely resolved.
- Do not hide material non-support or caveats only in prose notes.

### `downstream_links`

```yaml
downstream_links:
  allowed_for:
    claims: [claim-main]
    deliverables: [deliv-main]
    acceptance_tests: [test-main]
  evidence_paths:
    - .gpd/phases/01-example/01-VERIFICATION.md
```

Rules:

- `allowed_for` is optional, but when present it should only contain stable IDs.
- `evidence_paths` is optional and should point to the artifacts that rely on this record.
- A missing downstream link is better than an invented one.

---

## Optional Fields

### `comparison_context`

```yaml
comparison_context:
  benchmark_record_id: BM-001
  comparison_artifacts:
    - .gpd/comparisons/example-COMPARISON.md
```

Use this only when the evidence record is tied to a benchmark or comparison surface that should remain visible.

### `uncertainty_markers`

```yaml
uncertainty_markers:
  weakest_anchors: ["[least-certain part of the record]"]
  competing_explanations: ["[alternative interpretation]"]
  disconfirming_observations: ["[what would force revision]"]
```

Use this when the evidence object still carries meaningful uncertainty even after acceptance.

### `notes`

```yaml
notes:
  - "[short implementation or interpretation note]"
```

Use notes sparingly. Prefer structured fields first.

---

## Validation Rules

- Do not use this schema for a source that has not yet been reviewed at all.
- Do not mark a record `accepted` if `authority.class` is still effectively unknown.
- Do not replace contract-backed `comparison_verdicts` with evidence records; they serve different roles.
- Do not use `authority.class: promotive` when the same record’s `limits.blockers` still prohibit the claimed downstream use.
- If a record is superseded, keep its ID stable and update only the `status` plus any replacement note in `notes`.

---

## Relationship To Other Files

- `BIBLIOGRAPHY.md` tracks sources and anchors; this schema tracks machine-usable accepted evidence objects
- `plan-contract-schema.md` defines what a plan owes; this schema defines what accepted evidence may support downstream
- `contract-results-schema.md` records whether claims, deliverables, references, and comparisons passed; this schema records the accepted evidence object that may justify those results

If a project does not need machine-usable evidence objects yet, do not force this schema into normal flow. Stay with bibliography and prose-level evidence handling instead.
