---
template_version: 1
---

# Phase Plan Prompt Template

Canonical PLAN.md structure for `gpd-planner`. PLAN.md is the executor prompt, so every field must be specific enough to execute and verify without interpretation.

Use the canonical schema below before drafting any `contract:` block.

@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md

Quick contract rules:
- `contract` must be a YAML object with `schema_version: 1`; full rules live in the schema.
- Put machine-checkable prerequisites in `tool_requirements`; keep human-only setup in `researcher_setup`. `tool_requirements[].id` values must be unique within the list.
- Gap-closure plans still use `type: execute`; mark verification-repair plans with `gap_closure: true`.
- Keep `scope.in_scope`, `context_intake`, `claim_kind`, `observables[].kind`, `deliverables[].kind`, `acceptance_tests[].kind`, `references[].kind`, `references[].role`, `links[].relation`, `must_surface`, `required_actions[]`, `applies_to[]`, `carry_forward_to[]`, `uncertainty_markers`, `approach_policy`, and `proof_obligation` visible. When `must_surface` is `true`, keep `required_actions[]` and `applies_to[]` non-empty, and treat `carry_forward_to[]` as workflow scope only.
- `links[].relation` uses `supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`.
- `references[].required_actions` uses `read | use | compare | cite | avoid`.
- `context_intake`, `approach_policy`, and `uncertainty_markers` must stay YAML objects.
- Validator tool vocabulary is closed: `wolfram` and `command`. For `tool: command`, a non-empty `command` field is mandatory; for other tools, omit `command`.
- For proof-bearing work, use an explicit non-`other` `claim_kind`, keep hypotheses, parameters, and conclusions auditable, and name `observables[].kind: proof_obligation` items with the theorem or claim plus the hypotheses or parameter regime they cover.
- If a proof or theorem statement changes after a proof audit, treat that audit as stale before `status: passed` is possible for the affected target.

---

## File Template

```markdown
---
phase: XX-name
plan: NN
type: execute | tdd
wave: N
depends_on: []
files_modified: []
interactive: false
# gap_closure: true # Optional. Use only for verification repair plans.
researcher_setup: [] # Optional. Omit if empty.
# tool_requirements: # Optional machine-checkable specialized tools. Omit entirely if none.
#   - id: "wolfram-cas"
#     tool: "wolfram"
#     purpose: "[Why this specialized tool is needed]"
#     required: false
#     fallback: "[Standard-tool fallback when feasible]"
#   - id: "latex-compiler"
#     tool: "command"
#     command: "pdflatex --version"
#     purpose: "[Executable probe when a specific local command must exist]"
#     # `required` defaults to true when omitted.
#     # A fallback does not make a missing required tool non-blocking.

conventions:
  units: "natural"
  metric: "(+,-,-,-)"
  coordinates: "Cartesian"

dimensional_check:
  quantity_name: "[expected dimension]"

approximations:
  - name: "approximation name"
    parameter: "small parameter or control regime"
    validity: "where it is trusted"
    breaks_when: "failure regime"
    check: "verification that guards the approximation"

contract:
  schema_version: 1
  scope:
    question: "[The decisive question this plan advances]"
    in_scope: ["[Concrete objective or boundary this plan owns]"]
  context_intake:
    must_read_refs: [ref-main]
    must_include_prior_outputs: ["GPD/phases/00-baseline/00-01-SUMMARY.md"]
    user_asserted_anchors: ["GPD/phases/00-baseline/00-01-SUMMARY.md#vacuum-polarization-normalization"]
    known_good_baselines: ["GPD/phases/00-baseline/00-01-SUMMARY.md#accepted-reference-curve"]
    context_gaps: ["Comparison source still undecided before planning"]
    crucial_inputs: ["Check the user's finite-volume cutoff choice before proceeding"]
  claims:
    - id: "claim-main"
      statement: "[Physics statement this plan must establish]"
      deliverables: ["deliv-main"]
      acceptance_tests: ["test-main"]
      references: ["ref-main"]
  deliverables:
    - id: "deliv-main"
      kind: "figure"
      path: "path/to/output"
      description: "[Primary artifact this plan produces]"
  references:
    - id: "ref-main"
      kind: "paper"
      locator: "[Citation, dataset identifier, or prior artifact path]"
      role: "benchmark"
      why_it_matters: "[What this anchor constrains]"
      applies_to: ["claim-main"]
      must_surface: true
      required_actions: ["read", "compare", "cite"]
  acceptance_tests:
    - id: "test-main"
      subject: "claim-main"
      kind: "benchmark"
      procedure: "[How this plan will check the claim]"
      pass_condition: "[Concrete decisive pass condition]"
      evidence_required: ["deliv-main", "ref-main"]
  forbidden_proxies:
    - id: "fp-main"
      subject: "claim-main"
      proxy: "[What might look successful but should not count]"
      reason: "[Why this would be false progress]"
  links:
    - id: "link-main"
      source: "claim-main"
      target: "deliv-main"
      relation: "supports"
      verified_by: ["test-main"]
  uncertainty_markers:
    weakest_anchors: ["[Least-certain anchor still carrying load]"]
    disconfirming_observations: ["[Observation that would force a rethink]"]
---

<objective>
[What physics question this plan answers]

Purpose: [Why this matters for the milestone]
Output: [Derivations, code, data, figures, or notes created by this plan]
</objective>

<execution_context>
Downstream execution reads its execution workflow and summary template later. Do not inline those late-stage materials into the planning template itself.
</execution_context>

<context>
@GPD/PROJECT.md
@GPD/ROADMAP.md
@GPD/STATE.md
@path/to/reference-or-benchmark-anchor.md
@path/to/prior-summary-or-input.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: [Action-oriented task name]</name>
  <files>path/to/file.ext</files>
  <action>[Concrete derivation, implementation, or analysis steps]</action>
  <verify>[Physics checks: dimensions, limits, symmetry, conservation, benchmarks]</verify>
  <done>[Completion condition grounded in the physics outcome]</done>
</task>

<task type="checkpoint:decision">
  <name>Task 2: [Human decision point]</name>
  <files>docs/decision.md</files>
  <action>[Present the tradeoff or ambiguity]</action>
  <verify>[What evidence must be assembled before asking]</verify>
  <done>[What user choice or artifact unblocks the rest of the plan]</done>
</task>

</tasks>

<verification>
[Plan-level checks that apply across tasks]
</verification>

<success_criteria>
[Observable completion criteria: known limits recovered, code converged, literature benchmark matched, etc.]
</success_criteria>

<output>
After completion, create `GPD/phases/XX-name/{phase}-{plan}-SUMMARY.md`.
</output>
```

---

## Required Frontmatter

These fields must always be present:

- `phase`
- `plan`
- `type`
- `wave`
- `depends_on`
- `files_modified`
- `interactive`
- `conventions`
- `contract`

Contract visibility rules: keep at least one observable, claim, or deliverable; if `references[]` is present before approval and grounding is not already concrete, at least one reference must set `must_surface: true`; every `must_surface: true` reference needs a concrete `locator` and concrete `applies_to[]` coverage; project-local paths must resolve when `project_root` is available.

Add `dimensional_check` whenever the plan produces quantitative results. Add `approximations` whenever any truncation, asymptotic regime, discretization, or numerical cutoff is active.

---

## Task Rules

- Use XML `<task>` blocks inside `<tasks>`.
- Each task should produce one verifiable result.
- Every task must include an explicit physics verification step.
- Use checkpoint task types when the plan is interactive.
- Reference only the prior summaries, anchor documents, or artifacts the executor genuinely needs.

---

## Light Plan Variant

For `plan depth: light`, keep the same frontmatter but reduce the body to:

- `<objective>`
- `<tasks>` with one high-level task block per plan
- `<verification>`
- `<success_criteria>`

Do not omit the `contract`, conventions, or approximation validity just because the plan is light.
The `contract` block is still required in light mode, including `contract.context_intake` and any `links` needed to make downstream handoffs explicit.
If the plan is intentionally scoping-only, keep that limited shape explicit and preserve at least one target, open question, or carry-forward input.

## Contract Shape Classifier

- Reduced contract: legal only when the plan is explicitly scoping or exploratory.
- Full contract: required when the plan will execute, verify, or publish a concrete result.
- A reduced contract still needs `scope`, `contract.context_intake`, and `uncertainty_markers` explicit, plus at least one target, open question, or carry-forward input.
- Light mode changes the body only; it does not change the contract classifier above.

---

## Worked Example Snippet

```markdown
---
phase: 02-one-loop-renormalization
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [derivations/vacuum-polarization.tex, code/vac_pol_numerical.py]
interactive: false

conventions:
  units: "natural"
  metric: "(+,-,-,-)"
  gauge: "Feynman"

dimensional_check:
  Pi_munu: "[mass^2]"

contract:
  schema_version: 1
  scope:
    question: What benchmark must this plan recover?
    in_scope: ["Recover the benchmark curve within tolerance"]
  context_intake:
    must_read_refs: [ref-textbook]
    must_include_prior_outputs: ["GPD/phases/00-baseline/00-01-SUMMARY.md"]
    user_asserted_anchors: ["GPD/phases/00-baseline/00-01-SUMMARY.md#vacuum-polarization-normalization"]
    known_good_baselines: ["GPD/phases/00-baseline/00-01-SUMMARY.md#accepted-reference-curve"]
    context_gaps: ["Need the exact comparison source before planning"]
    crucial_inputs: ["Confirm the user's cutoff convention before writing the plan"]
  claims:
    - id: claim-polarization
      statement: Vacuum polarization tensor is transverse
      deliverables: [deliv-vac-pol]
      acceptance_tests: [test-transversality]
      references: [ref-textbook]
  deliverables:
    - id: deliv-vac-pol
      kind: derivation
      path: derivations/vacuum-polarization.tex
      description: One-loop vacuum polarization Pi^{mu nu}(q)
  references:
    - id: ref-textbook
      kind: paper
      locator: Peskin & Schroeder, Ch. 7
      role: definition
      why_it_matters: Standard convention and benchmark derivation
      applies_to: [claim-polarization]
      must_surface: true
      required_actions: [read, use, cite]
  acceptance_tests:
    - id: test-transversality
      subject: claim-polarization
      kind: consistency
      procedure: Contract Pi^{mu nu} with q_mu
      pass_condition: q_mu Pi^{mu nu} = 0
      evidence_required: [deliv-vac-pol, ref-textbook]
  forbidden_proxies:
    - id: fp-clean-algebra
      subject: claim-polarization
      proxy: Clean-looking algebra without explicit transversality check
      reason: Would not establish the decisive gauge-consistency result
  links:
    - id: link-transversality
      source: claim-polarization
      target: deliv-vac-pol
      relation: supports
      verified_by: [test-transversality]
  uncertainty_markers:
    weakest_anchors: ["Choice of gauge-fixing convention"]
    disconfirming_observations: ["Longitudinal term survives after simplification"]
---
```
