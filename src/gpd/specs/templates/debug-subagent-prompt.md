---
template_version: 1
---

# Debug Subagent Prompt Template

Template for spawning `gpd-debugger`. The agent provides the debugging expertise; this template only supplies problem context.

---

## Canonical Debug Session Contract

The spawned debugger must satisfy this contract before producing output:

- Session artifact: `GPD/debug/{slug}.md`
- Lifecycle/status vocabulary: `gathering | investigating | fixing | verifying | resolved`
- Goal vocabulary: `find_root_cause_only | find_and_fix`
- Continuation semantics: read `GPD/debug/{slug}.md` first, then continue from next_action

## Debug Template

```markdown
<debug_session_contract>
session_artifact: GPD/debug/{slug}.md
status: gathering | investigating | fixing | verifying | resolved
goal: find_root_cause_only | find_and_fix
continuation: Read the file at GPD/debug/{slug}.md first, then continue from next_action.
</debug_session_contract>

<objective>
Investigate issue: {issue_id}

**Summary:** {issue_summary}
</objective>

<symptoms>
expected: {expected}
actual: {actual}
discrepancy: {discrepancy}
errors: {errors}
reproduction: {reproduction}
timeline: {timeline}
</symptoms>

<physics_context>
domain: {domain}
formalism: {formalism}
key_equations: {key_equations}
conventions: {conventions}
approximations: {approximations}
</physics_context>

<mode>
symptoms_prefilled: {true_or_false}
goal: {find_root_cause_only | find_and_fix}
</mode>
```

---

## Placeholders

| Placeholder | Source | Example |
| --- | --- | --- |
| `{issue_id}` | Orchestrator-assigned | `wrong-berry-phase` |
| `{issue_summary}` | User description | `Berry phase computation gives pi instead of 2pi` |
| `{expected}` | From symptoms | `Berry phase = 2pi for bilayer graphene` |
| `{actual}` | From symptoms | `Numerical integration yields pi` |
| `{discrepancy}` | From symptoms | `Factor of 2 (exact), consistent across parameters` |
| `{errors}` | From symptoms | `No runtime errors, result is finite and smooth` |
| `{reproduction}` | From symptoms | `Run berry_phase.py with default parameters` |
| `{timeline}` | From symptoms | `After switching from rectangular to hexagonal BZ mesh` |
| `{domain}` | From context | `condensed matter, topological bands` |
| `{formalism}` | From context | `tight-binding, Berry connection on discretized BZ` |
| `{key_equations}` | From context | `gamma = oint A(k) . dk, A = -i ⟨u_k∣∇_k∣u_k⟩` |
| `{conventions}` | From context | `Bloch convention ∣psi_k⟩ = e^{ikr}∣u_k⟩, BZ in 1st zone` |
| `{approximations}` | From context | `Discretized Berry connection via log of overlap matrix` |
| `{goal}` | Orchestrator sets | `find_and_fix` |
| `{slug}` | Generated | `wrong-berry-phase` |

---

## Usage

Delegate to `gpd-debugger` with a filled prompt and a short description such as `Debug {slug}` or `Debug VAL-001`. Runtime-specific adapters choose the concrete delegation call shape and model argument policy.

## Continuation

For checkpoints, spawn a fresh agent with the same debug contract and the debug file path, then continue from `next_action`. Keep the goal vocabulary and `GPD/debug/{slug}.md` path unchanged.

If progress stalls after a few loops, return a structured checkpoint: blocker, evidence gathered, and the smallest unblocker needed.
