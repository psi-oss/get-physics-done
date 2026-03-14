---
template_version: 1
---

# Phase Plan Prompt Template

Canonical PLAN.md structure for `gpd-planner`. PLAN.md is the executor prompt, so every field must be specific enough to execute and verify without interpretation.

Before authoring or revising the `contract:` block, use `@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md` as the schema source of truth. The contract must stay a YAML object with object arrays and fully resolved ID cross-links.

---

## File Template

```markdown
---
phase: XX-name
plan: NN
type: execute | tdd | gap_closure
wave: N
depends_on: []
files_modified: []
interactive: false
researcher_setup: [] # Optional. Omit if empty.

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
  scope:
    question: "[The decisive question this plan advances]"
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
@{GPD_INSTALL_DIR}/workflows/execute-plan.md
@{GPD_INSTALL_DIR}/templates/summary.md
</execution_context>

<context>
@.gpd/PROJECT.md
@.gpd/ROADMAP.md
@.gpd/STATE.md
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
After completion, create `.gpd/phases/XX-name/{phase}-{plan}-SUMMARY.md`.
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
The `contract` block is still required in light mode, including any `links` needed to make downstream handoffs explicit.

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
  scope:
    question: What benchmark must this plan recover?
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
