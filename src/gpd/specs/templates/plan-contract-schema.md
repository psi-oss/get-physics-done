---
template_version: 1
type: plan-contract-schema
---

# PLAN Contract Schema

Canonical source of truth for the `contract:` block embedded in PLAN frontmatter.

Use this file whenever you author, revise, or validate a PLAN contract. Do not invent ad-hoc keys, collapse object lists into strings, or leave cross-referenced IDs unresolved.

---

## Required Shape

The PLAN `contract` value must be a YAML object with these top-level sections:

- `schema_version` (optional, defaults to `1`; no other value is supported)
- `scope`
- `claims`
- `deliverables`
- `references`
- `acceptance_tests`
- `forbidden_proxies`
- `uncertainty_markers`

Optional sections:

- `context_intake`
- `approach_policy`
- `observables`
- `links`

Every list named above must contain objects, not strings.

---

## Object Rules

### `scope`

```yaml
schema_version: 1

scope:
  question: "[The decisive question this plan advances]"
```

`scope.question` is required and must be non-empty after trimming whitespace.

### `claims[]`

```yaml
- id: claim-main
  statement: "[Physics statement this plan must establish]"
  deliverables: [deliv-main]
  acceptance_tests: [test-main]
  references: [ref-main]
```

Rules:

- Every claim must declare a stable `id`.
- `deliverables[]` must not be empty.
- `acceptance_tests[]` must not be empty.
- `deliverables[]` may only reference declared `deliverables[].id`.
- `acceptance_tests[]` may only reference declared `acceptance_tests[].id`.
- `references[]` may only reference declared `references[].id`.

### `deliverables[]`

```yaml
- id: deliv-main
  kind: figure | table | dataset | data | derivation | code | note | report | other
  path: path/to/output
  description: "[Primary artifact this plan produces]"
  must_contain: ["optional checklist item"]
```

Rules:

- Every deliverable must declare `id`, `kind`, and `description`.
- `path` is optional, but preferred whenever the plan already knows the durable artifact location.
- `must_contain` is optional, but if present it must be an array of strings.

### `references[]`

```yaml
- id: ref-main
  kind: paper | dataset | prior_artifact | spec | user_anchor | other
  locator: "[Citation, dataset identifier, or artifact path]"
  aliases: ["optional stable label or citation shorthand"]
  role: definition | benchmark | method | must_consider | background | other
  why_it_matters: "[What this anchor constrains]"
  applies_to: [claim-main]
  carry_forward_to: [planning, verification]
  must_surface: true
  required_actions: [read, compare, cite]
```

Rules:

- Every reference must declare a stable `id`.
- `aliases[]` is optional and stores stable human-facing labels or citation shorthands that downstream anchor-resolution logic may use.
- `applies_to[]` may only reference declared claim or deliverable IDs.
- `carry_forward_to[]` is optional free-text workflow scope (for example `planning`, `verification`, `writing`); do not overload it with contract IDs.
- If `must_surface: true`, `required_actions` must not be empty.
- If `must_surface: true`, `applies_to[]` must not be empty.

### `acceptance_tests[]`

```yaml
- id: test-main
  subject: claim-main
  kind: existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | human_review | other
  procedure: "[How this plan will check the claim]"
  pass_condition: "[Concrete decisive pass condition]"
  evidence_required: [deliv-main, ref-main]
  automation: automated | hybrid | human
```

Rules:

- `subject` must reference a declared claim or deliverable ID.
- `evidence_required[]` may only reference declared claim, deliverable, acceptance-test, or reference IDs.
- `automation` is optional and defaults to `hybrid`, but if present it must be `automated`, `hybrid`, or `human`.

### `forbidden_proxies[]`

```yaml
- id: fp-main
  subject: claim-main
  proxy: "[False-success pattern]"
  reason: "[Why this would be false progress]"
```

Rules:

- `subject` must reference a declared claim or deliverable ID.

### `links[]`

```yaml
- id: link-main
  source: claim-main
  target: deliv-main
  relation: supports | computes | visualizes | benchmarks | depends_on | evaluated_by | other
  verified_by: [test-main]
```

Rules:

- `source` and `target` may only reference declared claim, deliverable, acceptance-test, or reference IDs.
- `verified_by[]` may only reference declared `acceptance_tests[].id`.

### `uncertainty_markers`

```yaml
uncertainty_markers:
  weakest_anchors: ["[Least-certain anchor still carrying load]"]
  disconfirming_observations: ["[Observation that would force a rethink]"]
```

Rules:

- `weakest_anchors` must not be empty.
- `disconfirming_observations` must not be empty.

---

## Contract Alignment Rules

- IDs must be unique across each section.
- Canonical IDs and other required strings are trimmed before validation; blank-after-trim values are invalid.
- A cross-reference must fail loudly if it points to an undeclared ID.
- A non-object `contract:` value is invalid. Treat it as a schema error, not as “missing”.
- If `references[]` is non-empty, at least one reference must set `must_surface: true`.
- Do not assume any contract field is optional unless the active PLAN validator or workflow explicitly says so.

---

## Validation Commands

Use one of these before approving or committing a plan:

```bash
gpd frontmatter validate .gpd/phases/XX-name/XX-YY-PLAN.md --schema plan
gpd validate plan-contract .gpd/phases/XX-name/XX-YY-PLAN.md
```
