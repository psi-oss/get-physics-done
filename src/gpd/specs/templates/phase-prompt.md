---
template_version: 1
---

# Phase Plan Prompt Template

Canonical PLAN.md structure for `gpd-planner`. PLAN.md is the executor prompt, so every field must be specific enough to execute and verify without interpretation.

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

must_haves:
  truths:
    - "Testable physics statement the executor must establish"
  artifacts:
    - path: "path/to/output"
      provides: "What this artifact contains"
      physics_check: "Independent check tied to the artifact"
  key_links:
    - from: "upstream artifact or result"
      to: "downstream artifact or result"
      via: "Why the dependency matters"
      check: "How to verify the link"
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
- `must_haves`

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

Do not omit `must_haves`, conventions, or approximation validity just because the plan is light.

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

must_haves:
  truths:
    - "Vacuum polarization tensor is transverse: q_mu Pi^{mu nu} = 0"
  artifacts:
    - path: "derivations/vacuum-polarization.tex"
      provides: "One-loop vacuum polarization Pi^{mu nu}(q)"
      physics_check: "Transversality and correct mass dimension"
  key_links: []
---
```
