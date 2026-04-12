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

| Placeholder | Purpose |
| --- | --- |
| `{issue_id}` | Issue slug used inside `GPD/debug/{slug}.md` and the `issue` heading above. This usually matches the verification truth label. |
| `{issue_summary}` | The failed expectation (previously referred to as `truth`) that the subagent investigates and fills the `summary` field above. |
| `{truth_short}` | A condensed label for short UI strings such as the `description` argument in the runtime `task(...)` block. Runtimes may reuse `{issue_id}` if no shorter text is available. |
| `{expected}` | Verification target value (the expected/normally correct physics result). |
| `{actual}` | Observation reported in the gap or issue (what actually happened). |
| `{discrepancy}` | Short characterisation of the mismatch (wrong sign, missing factor, numerical instability, etc.). |
| `{errors}` | Errors, tracebacks, or anomalous values reported along with the failure. |
| `{reproduction}` | Repro instructions such as `Check {check_num}` or a script path. |
| `{timeline}` | When the issue was noticed, or how it evolved during validation. |
| `{domain}` | Physics domain (e.g., `condensed matter`, `plasma`). |
| `{formalism}` | Mathematical/physical formalism (e.g., `effective field theory`, `tight-binding`). |
| `{key_equations}` | The equations that capture the phenomenon under investigation. |
| `{conventions}` | Coordinate/momentum/Fourier/metric conventions to respect. |
| `{approximations}` | Known approximations or truncations that could explain the discrepancy. |
| `{goal}` | Typically `find_root_cause_only` for verification debug flows. |
| `{slug}` | Same as `{issue_id}` above; used for file paths and session contracts. |

The runtime also receives `{truth_short}` so the high-level `task(...)` description can stay concise, even if the template itself only references the longer `{issue_summary}`.

---

## Usage

Delegate to `gpd-debugger` with a filled prompt and a short description such as `Debug {slug}` or `Debug VAL-001`. Runtime-specific adapters choose the concrete delegation call shape and model argument policy.

## Continuation

For checkpoints, spawn a fresh agent with the same debug contract and the debug file path, then continue from `next_action`. Keep the goal vocabulary and `GPD/debug/{slug}.md` path unchanged.

If progress stalls after a few loops, return a structured checkpoint: blocker, evidence gathered, and the smallest unblocker needed.
