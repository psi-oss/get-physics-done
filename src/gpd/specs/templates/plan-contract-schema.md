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

- `schema_version` (required and must be the integer `1`; no other value is supported)
- `scope`
- `context_intake`
- `claims`
- `deliverables`
- `acceptance_tests`
- `forbidden_proxies`
- `uncertainty_markers`
- `references` when the plan does not already carry explicit grounding through `context_intake`, `approach_policy`, or preserved scoping inputs

Optional sections:

- `approach_policy`
- `observables`
- `links`

Every list named above must contain objects, not strings.
`context_intake`, `approach_policy`, and `uncertainty_markers` are object-valued sections, not strings or lists.

---

## Object Rules

### `schema_version`

```yaml
schema_version: 1
```

Rules:

- `schema_version` is required in the YAML frontmatter and must be the integer `1`.
- No other value is supported.

### `scope`

```yaml
scope:
  question: "[The decisive question this plan advances]"
  in_scope: ["[Optional boundary or objective]"]
  out_of_scope: ["[Optional excluded boundary]"]
  unresolved_questions: ["[Optional open question that still blocks planning]"]
```

Rules:

- `scope` must be an object, not a string or list.
- `scope.question` is required and must be non-empty after trimming whitespace.
- `in_scope`, `out_of_scope`, and `unresolved_questions` are optional arrays of non-empty strings.
- Use `scope.unresolved_questions` for genuinely undecided anchors; do not hide them in prose or placeholder text.
- Only concrete anchors count as grounding. `must_include_prior_outputs`, `user_asserted_anchors`, and `known_good_baselines` can ground the plan only when they name a durable path, citation, DOI, arXiv ID, or similarly concrete handle. `context_gaps` and `crucial_inputs` preserve uncertainty and workflow visibility, but they do not satisfy the hard grounding/anchor requirement by themselves.

### `claims[]`

```yaml
- id: claim-main
  statement: "[Physics statement this plan must establish]"
  claim_kind: theorem | lemma | corollary | proposition | result | claim | other
  observables: [obs-main]
  deliverables: [deliv-main]
  acceptance_tests: [test-main]
  references: [ref-main]
  parameters:
    - symbol: r_0
      domain_or_type: "nonnegative real"
      aliases: [r0]
      required_in_proof: true
      notes: "Parameter that must stay visible through the proof"
  hypotheses:
    - id: hyp-r0
      text: "r_0 >= 0"
      symbols: [r_0]
      category: assumption | precondition | regime | definition | lemma | other
      required_in_proof: true
  quantifiers: ["for all x > 0", "for all r_0 >= 0"]
  conclusion_clauses:
    - id: concl-main
      text: "[Conclusion clause the proof must establish]"
  proof_deliverables: [deliv-proof]
```

Rules:

- Every claim must declare a stable `id`.
- `observables[]` may only reference declared `observables[].id`.
- `deliverables[]` must not be empty.
- `acceptance_tests[]` must not be empty.
- `deliverables[]` may only reference declared `deliverables[].id`.
- `acceptance_tests[]` may only reference declared `acceptance_tests[].id`.
- `references[]` may only reference declared `references[].id`.
- `claim_kind` is optional and defaults to `other`; set it explicitly for theorem-bearing claims.
- For theorem/proof work, enumerate `parameters[]`, `hypotheses[]`, `quantifiers[]`, `conclusion_clauses[]`, and `proof_deliverables[]` so the proof audit can detect dropped assumptions, silently specialized parameters, and narrowed conclusions.
- Nested proof lists stay list-shaped even for one item: `parameters[].aliases`, `hypotheses[].symbols`, `quantifiers`, and `proof_deliverables` must stay YAML arrays, not scalar strings.
- `proof_deliverables[]` may only reference declared `deliverables[].id`.
- When a claim is theorem-bearing or references an `observables[].kind: proof_obligation`, the contract must declare at least one proof-specific acceptance test in `acceptance_tests[]`.
- `required_in_proof` must be a literal JSON boolean (`true` or `false`), not a quoted string or synonym such as `"yes"` / `"no"`.

### `context_intake`

```yaml
context_intake:
  must_read_refs: [ref-main]
  must_include_prior_outputs: ["GPD/phases/00-baseline/00-01-SUMMARY.md"]
  user_asserted_anchors: ["Use the lattice normalization from the user notes"]
  known_good_baselines: ["Published large-N curve from Smith et al."]
  context_gaps: ["Comparison source still undecided before planning"]
  crucial_inputs: ["Check the user's finite-volume cutoff choice before proceeding"]
```

Rules:

- `contract.context_intake` is required and must be a non-empty object, not a string or list.
- Every field above is optional inside the object, but the object itself must not be empty.
- `must_read_refs[]` may only reference declared `references[].id`.
- Use `context_gaps`, `scope.unresolved_questions`, or `uncertainty_markers.weakest_anchors` for unresolved anchors; do not invent placeholder references.

### `approach_policy`

```yaml
approach_policy:
  formulations: [Euclidean correlator fit]
  allowed_estimator_families: [bootstrap]
  forbidden_estimator_families: [jackknife]
  allowed_fit_families: [power_law]
  forbidden_fit_families: [polynomial]
  stop_and_rethink_conditions: ["Benchmark normalization shifts outside tolerance"]
```

Rules:

- `approach_policy` must be a YAML object, not a string or list.
- Every field above is optional, but when present it must be an array of non-empty strings.
- `allowed_*` and `forbidden_*` lists are closed-world guardrails for downstream check selection; do not bury them in prose.

### `observables[]`

```yaml
- id: obs-main
  name: "Benchmark residual"
  kind: scalar|curve|map|classification|proof_obligation|other
  definition: "[What quantity or behavior is being established]"
  regime: "large-k"
  units: "dimensionless"
```

Rules:

- Every observable must declare `id`, `name`, and `definition`.
- `kind` is optional and defaults to `other`; set it when the plan knows a more specific semantic category.
- When `kind: proof_obligation`, make `definition` name the theorem/result plus the hypotheses or parameter regime the proof must cover. Do not hide proof scope in body prose alone.
- `regime` and `units` are optional strings; omit them instead of fabricating placeholders.
- Claims may only reference observables that appear in `observables[]`.

### `deliverables[]`

```yaml
- id: deliv-main
  kind: figure | table | dataset | data | derivation | code | note | report | other
  path: path/to/output
  description: "[Primary artifact this plan produces]"
  must_contain: ["optional checklist item"]
```

Rules:

- Every deliverable must declare `id` and `description`.
- `kind` is optional and defaults to `other`; set it when the deliverable type is already known.
- `path` is optional, but preferred whenever the plan already knows the durable artifact location.
- `must_contain` is optional, but if present it must be an array of strings.

### `forbidden_proxies[]`

```yaml
- id: fp-main
  subject: claim-main
  proxy: "[False-success pattern]"
  reason: "[Why this would be false progress]"
```

Rules:

- `subject` must reference a declared claim or deliverable ID.

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
  required_actions: [read, compare, cite, avoid]
```

Rules:

- Every reference must declare a stable `id`.
- `kind` and `role` are optional and default to `other`; set them when the anchor semantics are already known.
- `aliases[]` is optional and stores stable human-facing labels or citation shorthands that downstream anchor-resolution logic may use.
- `applies_to[]` may only reference declared claim or deliverable IDs.
- `carry_forward_to[]` is optional free-text workflow scope (for example `planning`, `verification`, `writing`); do not overload it with contract IDs.
- `required_actions[]` values must use the closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`.
- `must_surface` is a boolean scalar. Use the YAML literals `true` and `false`; do not quote them or replace them with synonyms such as `yes`, `no`, `required`, or `optional`.
- If `must_surface: true`, `required_actions` must not be empty.
- If `must_surface: true`, `applies_to[]` must not be empty.
- If `must_surface: true`, the locator must still be concrete enough to re-find later: a citation, DOI, arXiv identifier, durable external URL, or project-local artifact path. Placeholder locators such as `TBD`, `unknown`, or bare section/table labels do not count.

### `acceptance_tests[]`

```yaml
- id: test-main
  subject: claim-main
  kind: existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | proof_hypothesis_coverage | proof_parameter_coverage | proof_quantifier_domain | claim_to_proof_alignment | lemma_dependency_closure | counterexample_search | human_review | other
  procedure: "[How this plan will check the claim]"
  pass_condition: "[Concrete decisive pass condition]"
  evidence_required: [deliv-main, ref-main]
  automation: automated | hybrid | human
```

Rules:

- `kind` is optional and defaults to `other`; set it when the test category is already known.
- `subject` must reference a declared claim or deliverable ID.
- `evidence_required[]` may only reference declared claim, deliverable, acceptance-test, or reference IDs.
- `automation` is optional and defaults to `hybrid`, but if present it must be `automated`, `hybrid`, or `human`.
- Use the proof-specific kinds to force explicit theorem coverage checks rather than burying them in prose. In particular, theorem-bearing claims should include at least one of `claim_to_proof_alignment`, `proof_hypothesis_coverage`, `proof_parameter_coverage`, `proof_quantifier_domain`, `lemma_dependency_closure`, or `counterexample_search`.

### `links[]`

```yaml
- id: link-main
  source: claim-main
  target: deliv-main
  relation: supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other
  verified_by: [test-main]
```

Rules:

- `relation` is optional and defaults to `other`; set it when the dependency type is already known.
- `source` and `target` may only reference declared claim, deliverable, acceptance-test, or reference IDs.
- `verified_by[]` may only reference declared `acceptance_tests[].id`.

### `uncertainty_markers`

```yaml
uncertainty_markers:
  weakest_anchors: ["[Least-certain anchor still carrying load]"]
  unvalidated_assumptions: ["[Optional assumption still carrying load]"]
  competing_explanations: ["[Optional competing explanation]"]
  disconfirming_observations: ["[Observation that would force a rethink]"]
```

Rules:

- `weakest_anchors` must not be empty.
- `disconfirming_observations` must not be empty.
- `uncertainty_markers` must be a YAML object, not a string or list.
- `unvalidated_assumptions` and `competing_explanations` are optional arrays of non-empty strings, but when present they must stay explicit in the contract.

---

## Contract Alignment Rules

- Reduced contracts are legal only when the plan is explicitly scoping or exploratory.
- If the plan will execute, verify, or publish a concrete result, use the full non-scoping shape.
- A reduced contract still needs a real decision surface: preserve at least one target, open question, or carry-forward input instead of emitting a hollow scaffold.
- If you are unsure, classify the plan as non-scoping and use the full shape.
- `references[]` are mandatory only when the contract does not already expose enough concrete grounding through `context_intake` or preserved scoping inputs. `context_gaps`, `crucial_inputs`, and `stop_and_rethink_conditions` keep uncertainty visible, but they do not satisfy the grounding/anchor requirement by themselves. When concrete grounding already exists, omit `references[]` rather than padding the contract with decorative anchors.
- The schema still exposes the semantic fields `observables[].kind`, `deliverables[].kind`, `acceptance_tests[].kind`, `references[].kind`, `references[].role`, and `links[].relation`; their default is `other`. Omit them only when `other` is genuinely intended, and set the specific value explicitly when the semantics are already known.
- For non-scoping plans, `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` are all required.
- The defaultable semantic fields above do not relax the hard requirements on `context_intake` or `uncertainty_markers`, and they do not replace required contract targets for non-scoping plans.
- For non-scoping plans, include `references[]` unless explicit concrete grounding context survives elsewhere in the contract.
- When a plan depends on traceable handoffs or decisive comparisons, surface `links[]` explicitly instead of burying the dependency in prose.
- All ID cross-links must resolve to declared IDs. Unresolved IDs are validation errors, not TODO placeholders.
- IDs must be unique across each section.
- Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; target resolution becomes ambiguous.
- Canonical IDs and other required strings are trimmed before validation; blank-after-trim values are invalid.
- A cross-reference must fail loudly if it points to an undeclared ID.
- A non-object `contract:` value is invalid. Treat it as a schema error, not as “missing”.
- If `references[]` is non-empty, at least one reference must set `must_surface: true`.
- Do not assume any contract field is optional unless the active PLAN validator or workflow explicitly says so.

---

## Validation Commands

Use one of these before approving or committing a plan:

```bash
gpd frontmatter validate GPD/phases/XX-name/XX-YY-PLAN.md --schema plan
gpd validate plan-contract GPD/phases/XX-name/XX-YY-PLAN.md
```
