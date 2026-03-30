---
template_version: 1
---

<!-- Used by: pause-work workflow as the canonical temporary pause/resume handoff artifact. -->

# Canonical Temporary Continue-Here Handoff Template

Copy and fill this structure for `GPD/phases/XX-name/.continue-here.md`.
This is the canonical temporary phase handoff artifact written by `/gpd:pause-work` and consumed by `/gpd:resume-work` plus the local `gpd resume` recovery surface. The machine-readable backend remains `gpd init resume`, and this file is only a one-way projection of canonical continuation.

This file is **not** the authoritative store for project position, session continuity, or resume ranking. Current public behavior keeps those responsibilities split across `GPD/state.json` (authoritative storage), `GPD/state.json.bak` (recovery backup), `GPD/STATE.md` (editable mirror), append-only execution lineage, and the derived execution head / `GPD/observability/current-execution.json` compatibility mirror. `gpd init resume` resolves the current canonical continuation view across those surfaces and may reach this file through session continuity or the derived execution head. The body below is a readable projection for humans and recovery tooling, not a second state source:

If this pause follows a successful derivation write-back, the canonical `result_id` for that derivation should be carried forward explicitly as `last_result_id`. That is the rerun anchor; do not rely on prose alone to recover it later.

```yaml
---
phase: XX-name
task: 3
total_tasks: 7
status: in_progress
last_updated: 2026-03-15T14:30:00Z
---
```

```markdown
<current_state>
[Where exactly are we in the research? What's the immediate physics context?]
</current_state>

<completed_work>
[What got done this session - be specific about physics content]

- Task 1: [name] - Done
  - Key result: [formula, value, or finding]
- Task 2: [name] - Done
  - Key result: [formula, value, or finding]
- Task 3: [name] - In progress, [what's done on it]
  - Partial result: [where we are in the derivation/computation]
    </completed_work>

<remaining_work>
[What's left in this phase]

- Task 3: [name] - [what's left to do]
- Task 4: [name] - Not started
- Task 5: [name] - Not started
  </remaining_work>

<decisions_made>
[Key physics decisions and reasoning - so next session doesn't re-debate]

- Chose [approximation/method X] because [physical reason]
- Using [convention/normalization] because [consistency with paper Y]
- Discarded [approach Z] because [it fails when / gives unphysical result]
  </decisions_made>

<intermediate_results>
[Expressions, values, and partial derivations that the next session needs.
Each entry should have: LaTeX equation, explicit units, and validity range.]

If a canonical derived result was persisted this session, record its `result_id` here and repeat it as `last_result_id` so a later rerun can target the same registry entry directly.

Equations:

- `H_eff = H_0 + \lambda V_1 + \lambda^2 V_2` (units: energy, valid: \lambda << 1)
- `\alpha_s(\mu) = 0.118 \pm 0.001` (units: dimensionless, valid: \mu = m_Z)
- `T_c = 0.893 \pm 0.005` (units: J/k_B, valid: L >= 32, method: finite-size scaling)

Numerical values:

- Coupling at critical point: [value +/- uncertainty, units, scheme]
- Eigenvalues computed for N = [values], stored in [file path]

Convention snapshot (must match state.json convention_lock):

- Metric: [signature used in this session]
- Fourier: [convention used]
- Regularization: [scheme, if relevant]
- Any other conventions chosen this session
  </intermediate_results>

<blockers>
[Anything stuck or waiting on external factors]

- [Blocker 1]: [status/workaround]
  - Physics impact: [what this blocks and what we can still do without it]
    </blockers>

<context>
[Research state, reasoning chain, anything that helps resume smoothly]

[What was the physical reasoning? What was the plan for the next step?
What approximations are we tracking? What should we be worried about?
This is the "pick up exactly where you left off" context.]
</context>

<next_action>
[The very first thing to do when resuming]

Start with: [specific action - e.g., "evaluate the matrix element <n|V|m> for n,m = 0,...,4 using the expressions in derivations/perturbation_theory.tex"]
</next_action>
```

<persistent_state>

## Persistent Derivation State (appended to GPD/DERIVATION-STATE.md on pause)

This section captures derivation content that must survive across ALL sessions.
Unlike the rest of this file, this section is NOT ephemeral -- the pause-work
workflow extracts it and appends it to `GPD/DERIVATION-STATE.md` before
the handoff is consumed on resume. That file is append-only and cumulative.

### Equations Established This Session

<!-- List every equation derived with its LaTeX form, units, and validity range -->
<!-- These persist permanently -- they are NOT deleted on resume -->

- `[LaTeX equation]` (units: [units], valid: [validity range], derived from: [source/method])

### Conventions Applied This Session

<!-- Any new convention choices or confirmations made during this session -->
<!-- Include: metric signature, Fourier convention, normalization, regularization scheme -->

- [Convention]: [choice made] -- [reason/reference]

### Intermediate Results Recorded

<!-- Reference the result IDs added to state.json this session -->
<!-- Each entry links back to the state.json intermediate_results key -->
<!-- If a derived result is the rerun anchor, repeat it explicitly as last_result_id. -->

- Result ID: [id] -- [brief description of what was computed]

### Approximations Used

<!-- Any approximation invoked and its validity check -->
<!-- Include: name, regime of validity, how validity was verified -->

- [Approximation]: valid when [condition] -- checked by [method/comparison]
  </persistent_state>

<yaml_fields>
Required YAML frontmatter:

- `phase`: Directory name (e.g., `02-perturbation-theory`)
- `task`: Current task number
- `total_tasks`: How many tasks in phase
- `status`: `in_progress`, `blocked`, `almost_done`
- `last_updated`: ISO timestamp
  </yaml_fields>

<guidelines>
- Be specific enough that a fresh agent instance understands immediately
- Include WHY decisions were made, not just what (physics reasoning)
- Preserve these canonical section names so pause/resume tooling and humans see the same structure every time
- Record intermediate results as structured entries: LaTeX equation + units + validity range
- Every equation must have explicit units (even if dimensionless) and validity domain
- Note sign conventions and normalization choices (these are the #1 source of errors on resume)
- Convention snapshot in intermediate_results must be consistent with state.json convention_lock
- The `<next_action>` should be actionable without reading anything else
- The `<intermediate_results>` section is critical for physics - unlike software, you can't just "run the code" to recover state
- This file is the canonical temporary handoff artifact. `/gpd:resume-work`, `gpd resume`, and the `gpd init resume` backend reach it through session continuity or live execution pointers, and it may be deleted once the handoff is consumed
- Deleting or missing this file does not erase project state by itself; it only removes one temporary handoff input to the canonical continuation view
- This template must not be treated as the storage authority for project status, session continuity, or bounded resume ranking
- The canonical continuation hierarchy and append-only lineage remain the authoritative sources; this file is a projection used to make pause/resume readable
- The `<persistent_state>` section is the exception: its content is appended to `GPD/DERIVATION-STATE.md` BEFORE this file is deleted, so equations/conventions/results accumulate permanently across all sessions
- Fill `<persistent_state>` carefully -- it is the antidote to lossy compression across context resets
</guidelines>
