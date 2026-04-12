---
template_version: 1
type: plan-contract-schema
---

# PLAN Contract Schema

Defaultable semantic fields remain explicit: `observables[].kind`, `deliverables[].kind`, `acceptance_tests[].kind`, `claims[].claim_kind`, `references[].kind`, `references[].role`, and `links[].relation` may default in tooling, but plans should surface them when they affect validation.
`approach_policy` is execution policy only; it can constrain planning, but it does not by itself satisfy the hard grounding/anchor requirement.
`schema_version` is required and must be the integer `1`.

Canonical source of truth for the `contract:` block embedded in PLAN frontmatter.

Use this file whenever you author, revise, or validate a PLAN contract. Do not invent ad-hoc keys, flatten object lists into strings, or leave cross-referenced IDs unresolved.
For alignment reminders, addendum notes, and validation command examples, consult the canonical addendum guidance below.

`@{GPD_INSTALL_DIR}/templates/plan-contract-schema-notes.md`

---

## Required Shape

The PLAN `contract` value must be a YAML object with these top-level sections:

| Section | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | integer | yes | Must equal `1`. |
| `scope` | object | yes | Defines the decisive question and scope boundaries. |
| `context_intake` | object | yes | Captures concrete anchors, prior outputs, and gating context. |
| `claims[]` | list | yes* | Required for non-scoping plans; scoping-only contracts may omit claims only when they preserve a target, unresolved question, or grounding input. |
| `deliverables[]` | list | yes* | Must list the decisive artifacts; optional for scoping-only contracts. |
| `acceptance_tests[]` | list | yes* | Each decisive claim or deliverable needs an executable test. |
| `forbidden_proxies[]` | list | yes* | Needed whenever there are deceptive success patterns to reject. |
| `uncertainty_markers` | object | yes | Exposes `weakest_anchors` and `disconfirming_observations`. |
| `references[]` | list | conditional | Required when grounding is not already concrete; set `must_surface: true` when the anchor drives a decision. |
| `approach_policy` | object | no | Execution guardrails; it does not count as grounding by itself. |
| `observables[]` | list | no | Declare named quantities only when a claim or proof tracks them. |
| `links[]` | list | no | Use when tracing handoffs or decisive comparisons between IDs. |

`*` Non-scoping plans must keep the full claims/deliverables/acceptance_tests/forbidden_proxies suite. Scoping-only contracts may omit claims only when they preserve a target, unresolved question, or grounding input, and still rely on this shape for the declared anchors above.

For additional alignment rules and validation command examples, revisit the canonical addendum guidance above.

## General Rules

- Every list named above must contain objects, not strings.
- Hard-schema fields must be model-visible before validation: `scope.question`, non-empty `scope.in_scope`, `context_intake`, and `uncertainty_markers` are not inferred from prose.
- `context_intake`, `approach_policy`, and `uncertainty_markers` are object-valued sections, not strings or lists.
- Do not add unknown keys at any level; strict validation rejects them. Salvage/repair flows may drop unknown keys while surfacing recoverable findings.
- All ID cross-links must resolve to declared IDs.
- Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; target resolution becomes ambiguous.
- All blank-after-trim values are invalid.
- `approach_policy` constrains execution but does not count as grounding on its own; use `context_intake`, preserved scoping inputs, or `references[]` instead.
- `context_intake` anchors must be concrete enough to re-find later. Placeholders like `TBD`, `unknown`, or `placeholder` do not count as grounding.
- Provide durable grounding inside `context_intake`: populate `must_read_refs`, `must_include_prior_outputs`, `user_asserted_anchors`, or `known_good_baselines` with artifact locators or previously surfaced references so `_has_contract_grounding_context` can detect them; when those anchors are missing, at least one `references[]` entry must set `must_surface: true` so the integrity checks still know what to dig up.
- `uncertainty_markers` must include non-empty `weakest_anchors` and `disconfirming_observations`. The blockers in `collect_plan_contract_integrity_errors` and related parsing logic expect those lists to surface the weakest assumptions and counter-observations that still need resolution.

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
  in_scope: ["Recover the benchmark curve within tolerance"]
  out_of_scope: ["[Optional excluded boundary]"]
  unresolved_questions: ["[Optional open question that still blocks planning]"]
```

Rules:

- `scope` must be an object, not a string or list.
- `scope.question` is required and must be non-empty after trimming whitespace.
- `scope.in_scope` is required and must name at least one project boundary or objective.
- `out_of_scope` and `unresolved_questions` are optional arrays of non-empty strings.
- Use `scope.unresolved_questions` for genuinely undecided anchors; do not hide them in prose or placeholder text.
- `context_gaps` and `crucial_inputs` preserve uncertainty and workflow visibility, but they do not satisfy the hard grounding requirement by themselves.

### `claims[]`

```yaml
- id: claim-main
  statement: "[Physics statement this plan must establish]"
  claim_kind: theorem
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
      category: assumption
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
- For non-scoping plans, `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` are all required.
- `deliverables[]` may only reference declared `deliverables[].id`.
- `acceptance_tests[]` may only reference declared `acceptance_tests[].id`.
- `references[]` may only reference declared `references[].id`.
- `references[]` are mandatory only when the contract does not already expose enough grounding through `context_intake` or preserved scoping inputs.
- If `references[]` is non-empty and the contract does not already carry concrete grounding elsewhere, at least one reference must set `must_surface: true`.
- When concrete grounding already exists, a missing `must_surface: true` reference is a warning, not a blocker.
- `claim_kind` is optional and defaults to `other` only for non-proof work; proof-bearing claims must set it explicitly and must not leave it at `other`.
- For optional enum fields that include `other`, their default is `other` unless a proof obligation requires an explicit choice.
- `claim_kind: theorem|lemma|corollary|proposition|result|claim|other`
- Closed-vocabulary enum fields use the exact lowercase literals shown here. Case drift such as `Theorem`, `Benchmark`, or `Read` fails strict validation.
- The defaultable semantic fields above do not relax the hard requirements on `context_intake` or `uncertainty_markers`.
- For theorem/proof work, enumerate `parameters[]`, `hypotheses[]`, `quantifiers[]`, `conclusion_clauses[]`, and `proof_deliverables[]` so proof audits can spot dropped assumptions, specialized parameters, and narrowed conclusions.
- Keep nested proof lists as YAML arrays, even for one item: `parameters[].aliases`, `hypotheses[].symbols`, `quantifiers`, and `proof_deliverables` must not collapse to scalar strings.
- `proof_deliverables[]` may only reference declared `deliverables[].id`.
- Treat a claim as proof-bearing whenever any of these is true: `claim_kind` is `theorem|lemma|corollary|proposition|claim`; the statement is theorem-like (`prove/show that`, explicit `for all` / `exists`, or uniqueness language); any proof field is already populated (`parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, or `proof_deliverables`); or `observables[]` references a `proof_obligation` target.
- Proof-bearing claims must use an explicit non-`other` `claim_kind`, declare at least one proof-specific acceptance test in `acceptance_tests[]`, and surface `proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses` so the proof obligation is auditable.
- `required_in_proof` must be a literal JSON boolean (`true` or `false`), not a quoted string or synonym such as `"yes"` / `"no"`.

### `context_intake`

```yaml
context_intake:
  must_read_refs: [ref-main]
  must_include_prior_outputs: ["GPD/phases/00-baseline/00-01-SUMMARY.md"]
  user_asserted_anchors: ["GPD/phases/00-baseline/00-01-SUMMARY.md#lattice-normalization"]
  known_good_baselines: ["GPD/phases/00-baseline/00-01-SUMMARY.md#published-large-n-curve"]
  context_gaps: ["Comparison source still undecided before planning"]
  crucial_inputs: ["Check the user's finite-volume cutoff choice before proceeding"]
```

Rules:

- `contract.context_intake` is required and must be a non-empty object, not a string or list.
- Every field above is optional inside the object, but the object itself must not be empty.
- `must_read_refs[]` may only reference declared `references[].id`.
- Use concrete anchors in `must_read_refs[]`, `must_include_prior_outputs[]`, `user_asserted_anchors[]`, and `known_good_baselines[]`; when those anchors do not already name real artifacts or references, mark at least one `references[]` entry with `must_surface: true` so `_has_contract_grounding_context` can still detect durable grounding, then rely on `context_gaps`, `scope.unresolved_questions`, or `uncertainty_markers.weakest_anchors` for unresolved anchors instead of inventing placeholder references.
- `context_gaps` and `crucial_inputs` preserve uncertainty and workflow visibility, but they do not satisfy hard grounding on their own.

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
- `approach_policy` does not count as grounding on its own; use `context_intake`, preserved scoping inputs, or `references[]` for actual anchors.

### `observables[]`

```yaml
- id: obs-main
  name: "Benchmark residual"
  kind: scalar
  definition: "[What quantity or behavior is being established]"
  regime: "large-k"
  units: "dimensionless"
```

Rules:

- Every observable must declare `id`, `name`, and `definition`.
- `kind` is optional and defaults to `other`; set it when the plan knows a more specific semantic category.
- `kind: scalar|curve|map|classification|proof_obligation|other`
- When `kind: proof_obligation`, make `definition` name the theorem/result plus the hypotheses or parameter regime the proof must cover. Do not hide proof scope in body prose alone.
- `regime` and `units` are optional strings; omit them instead of fabricating placeholders.
- Claims may only reference observables that appear in `observables[]`.

### `deliverables[]`

```yaml
- id: deliv-main
  kind: figure
  path: path/to/output
  description: "[Primary artifact this plan produces]"
  must_contain: ["optional checklist item"]
```

Rules:

- Every deliverable must declare `id` and `description`.
- `kind` is optional and defaults to `other`; set it when the deliverable type is already known.
- `kind: figure|table|dataset|data|derivation|code|note|report|other`
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
  kind: paper
  locator: "[Citation, dataset identifier, or artifact path]"
  aliases: ["optional stable label or citation shorthand"]
  role: benchmark
  why_it_matters: "[What this anchor constrains]"
  applies_to: [claim-main]
  carry_forward_to: [planning, verification]
  must_surface: true
  required_actions: [read, compare, cite, avoid]
```

Rules:

- Every reference must declare a stable `id`.
- `kind` and `role` are optional and default to `other`; set them when the anchor semantics are already known.
- `kind: paper | dataset | prior_artifact | spec | user_anchor | other`
- `role: definition | benchmark | method | must_consider | background | other`
- `aliases[]` is optional and stores stable human-facing labels or citation shorthands that downstream anchor-resolution logic may use.
- `applies_to[]` may only reference declared claim or deliverable IDs.
- `carry_forward_to[]` is optional free-text workflow scope (for example `planning`, `verification`, `writing`); do not overload it with contract IDs.
- `required_actions[]` values must use the closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`.
- `must_surface` is a boolean scalar. Use the YAML literals `true` and `false`; do not quote them or replace them with synonyms such as `yes`, `no`, `required`, or `optional`.
- If `must_surface: true`, `required_actions` must not be empty.
- If `must_surface: true`, `applies_to[]` must not be empty.
- `must_surface: true` references need concrete `applies_to[]` coverage of declared claim or deliverable IDs.
- If `must_surface: true`, the locator must still be concrete enough to re-find later: a citation, DOI, arXiv identifier, durable external URL, or project-local artifact path. Placeholder locators such as `TBD`, `unknown`, or bare section/table labels do not count.
- Project-local `locator` paths must resolve when `project_root` is available.

### `acceptance_tests[]`

```yaml
- id: test-main
  subject: claim-main
  kind: benchmark
  procedure: "[How this plan will check the claim]"
  pass_condition: "[Concrete decisive pass condition]"
  evidence_required: [deliv-main, ref-main]
  automation: automated
```

Rules:

- `kind` is optional and defaults to `other`; set it when the test category is already known.
- `kind: existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | proof_hypothesis_coverage | proof_parameter_coverage | proof_quantifier_domain | claim_to_proof_alignment | lemma_dependency_closure | counterexample_search | human_review | other`
- `subject` must reference a declared claim or deliverable ID.
- `evidence_required[]` may only reference declared claim, deliverable, acceptance-test, or reference IDs.
- `automation` is optional and defaults to `hybrid`, but if present it must be `automated`, `hybrid`, or `human`.
- Use the proof-specific kinds to force explicit theorem coverage checks rather than burying them in prose. In particular, theorem-bearing claims should include at least one of `claim_to_proof_alignment`, `proof_hypothesis_coverage`, `proof_parameter_coverage`, `proof_quantifier_domain`, `lemma_dependency_closure`, or `counterexample_search`.

### `links[]`

```yaml
- id: link-main
  source: claim-main
  target: deliv-main
  relation: supports
  verified_by: [test-main]
```

Rules:

- `relation` is optional and defaults to `other`; set it when the dependency type is already known.
- `relation: supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`
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
- `weakest_anchors` should name the least-certain anchors the contract still leans on, and `disconfirming_observations` should describe concrete evidence that would force rethinking. These lists feed the blockers in `collect_plan_contract_integrity_errors` and `_collect_strict_contract_results_errors`, so they must stay populated.
- `uncertainty_markers` must be a YAML object, not a string or list.
- `unvalidated_assumptions` and `competing_explanations` are optional arrays of non-empty strings, but when present they must stay explicit in the contract.

---
