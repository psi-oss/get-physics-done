---
template_version: 1
---

# Debug Subagent Prompt Template

Template for spawning gpd-debugger agent. The agent contains all physics debugging expertise - this template provides problem context only.

---

## Template

```markdown
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

<debug_file>
Create: .gpd/debug/{slug}.md
</debug_file>
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

**From /gpd:debug:**

```python
task(
  prompt=filled_template,
  subagent_type="gpd-debugger",
  description="Debug {slug}"
  # model parameter from profile tier — omit on single-model platforms
)
```

**From debug (validation):**

```python
task(prompt=template, subagent_type="gpd-debugger", description="Debug VAL-001")
# model parameter from profile tier — omit on single-model platforms
```

## <!-- task() subagent_type and model parameters are runtime-specific. The installer adapts these to the target platform's delegation mechanism. -->

## Systematic Physics Debugging Strategy

The gpd-debugger agent applies a systematic approach to physics calculation errors:

1. **Quantify the discrepancy** - exact factor, sign, functional form, parameter dependence
2. **Check conventions** - metric signature, Fourier transform, normalization, active/passive
3. **Check factors** - 2pi, hbar, symmetry factors, combinatorial prefactors, Jacobians
4. **Check signs** - commutator ordering, integration orientation, branch cuts
5. **Check indices** - contraction, raising/lowering, summation ranges, Einstein convention
6. **Check approximations** - is expansion parameter small? correct order? radius of convergence?
7. **Check numerics** - convergence, grid resolution, floating-point precision, boundary effects
8. **Limiting cases** - does the result reduce correctly in all known limits?

---

## Continuation

For checkpoints, spawn fresh agent with:

```markdown
<objective>
Continue debugging {slug}. Evidence is in the debug file.
</objective>

<prior_state>
Read the file at .gpd/debug/{slug}.md
</prior_state>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>

<physics_context>
domain: {domain}
formalism: {formalism}
conventions: {conventions}
</physics_context>

<mode>
goal: {goal}
</mode>
```

<failure_protocol>

## When Investigation Stalls

If you cannot make progress after 3 investigation rounds, report structured failure:

```markdown
**Status:** Cannot proceed
**Reason:** [Specific physics/technical reason — e.g., "sign ambiguity cannot be resolved without additional input"]
**Blocked by:** [What would unblock progress — e.g., "access to reference implementation", "user decision on branch cut convention"]
**Suggested alternative:** [Different approach that might work — e.g., "try asymptotic expansion instead of numerical integration"]
**Evidence gathered:** [What WAS determined before getting stuck — partial results are valuable]
```

1. **Document what you tried** — list each hypothesis tested and why it was eliminated
2. **State what you know** — summarize confirmed facts and narrowed-down possibilities
3. **Identify the blocker** — what specific information or capability is missing
4. **Return CHECKPOINT REACHED** with the structured failure block above

Do NOT spin in circles retrying the same approaches. Escalate with structured context.

</failure_protocol>
