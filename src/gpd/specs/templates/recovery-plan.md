---
template_version: 1
---

<!-- Used by: execute-phase workflow when a plan fails unrecoverably. -->

# Recovery Plan Template

Template for `.gpd/phases/XX-name/{phase}-{plan}-RECOVERY.md` - structured recovery after a plan execution failure.

---

## File Template

```markdown
---
phase: XX-name
plan: YY
failed_at: [ISO timestamp]
failure_category: sign_error | convergence_failure | numerical_instability | dimensional_mismatch | unphysical_result | missing_dependency | tool_failure | other
severity: recoverable | needs_rollback | needs_replan
---

## What Failed

**Plan:** {plan number} - {plan name}
**Task at failure:** Task {N} of {total}
**Error summary:** [One-line description of what went wrong]

### Failure Details

[Detailed description of the failure: error messages, wrong values, inconsistencies detected]

### Diagnostic Information

**Last successful task:** Task {N-1} - {name}
**Last successful commit:** `{hash}` - {message}
**Files modified before failure:**

- `path/to/file` - [what was changed]

**Intermediate state at failure:**

- [Key quantity or expression that was incorrect/inconsistent]
- [Expected vs. actual value if applicable]

## Root Cause Analysis

**Category:** [one of the failure categories from frontmatter]

### Physics-Specific Diagnosis

**Sign error:**

- Where: [which term or equation]
- Convention involved: [metric, Fourier, etc.]
- How detected: [limiting case, dimensional analysis, numerical check]

**Convergence failure:**

- Method: [what was being computed]
- Parameters: [grid size, coupling, truncation order]
- Symptom: [divergence, oscillation, no improvement]

**Numerical instability:**

- Operation: [matrix inversion, ODE integration, etc.]
- Condition number or error growth: [if known]
- Parameter regime: [where it fails]

**Dimensional mismatch:**

- LHS dimensions: [units]
- RHS dimensions: [units]
- Where mismatch enters: [which step]

**Unphysical result:**

- What's wrong: [negative probability, acausal propagation, etc.]
- Physical constraint violated: [unitarity, causality, positivity, etc.]

[Delete categories that don't apply. Keep only the relevant diagnosis.]

## Rollback Steps

### Option A: Rollback to last good state

```bash
git log --oneline -5   # Identify last good commit
git revert {bad_hash}  # Revert failed work
```

**State after rollback:**

- Plan {N} status: reverted to pre-execution
- Files restored: [list]
- STATE.md: Current Plan back to {N}

### Option B: Partial rollback (keep completed tasks)

**Keep:** Tasks 1-{K} (commits `{hash1}` through `{hashK}`)
**Revert:** Tasks {K+1}+ (commits `{hashK+1}` through `{bad_hash}`)

```bash
git revert {hashK+1}..{bad_hash}
```

## Retry Strategy

### Immediate retry (if transient failure)

- [ ] Verify failure is not deterministic
- [ ] Adjust parameters: [what to change]
- [ ] Re-run from Task {N}

### Modified approach (if systematic failure)

- [ ] Root cause addressed: [what changed]
- [ ] New approach: [description]
- [ ] Verification that new approach avoids the failure mode: [test]

### Replan (if fundamental issue)

Run `/gpd:revise-phase` to create a replacement plan that:

- [ ] Avoids the failed approach: [what to change]
- [ ] Incorporates diagnostic findings: [what we learned]
- [ ] Adds verification steps to catch this class of error earlier

## Prevention

**What to add to future plans:**

- [ ] [Verification check that would have caught this earlier]
- [ ] [Parameter range validation]
- [ ] [Limiting case test]

---

_Recovery plan for: {phase}-{plan}_
_Created: [date]_
_Status: [pending | in_progress | resolved]_
```

<failure_categories>

### Physics Failure Categories

| Category | Typical Cause | Detection Method | Recovery Approach |
|----------|--------------|------------------|-------------------|
| **Sign error** | Convention mismatch (metric, Fourier, coupling) | Limiting case gives wrong sign, symmetry violated | Trace conventions back to source, fix sign, re-derive from error point |
| **Convergence failure** | Truncation too low, coupling too strong, grid too coarse | Series doesn't stabilize, residual grows | Increase order/resolution, switch method if in strong-coupling regime |
| **Numerical instability** | Ill-conditioned matrix, stiff ODE, catastrophic cancellation | NaN/Inf in output, result changes with precision | Use stable algorithm, increase precision, regularize |
| **Dimensional mismatch** | Missing factor of hbar, c, or 2pi; mixed unit systems | Dimensional analysis of final expression | Track dimensions at every step, use natural units consistently |
| **Unphysical result** | Approximation breaks down, sign error, boundary condition wrong | Violates unitarity, causality, positivity, or known limits | Check approximation validity, verify boundary conditions |
| **Missing dependency** | Prior phase result not available or incompatible | Import/lookup fails, quantity not in state | Check provides/requires chain, re-run upstream if needed |
| **Tool failure** | Package version, memory limit, timeout | Runtime error, OOM, hung process | Check environment, reduce problem size, use alternative tool |

</failure_categories>

<guidelines>
- Create this file immediately when a plan fails unrecoverably
- Fill the relevant physics diagnosis section; delete the rest
- Include concrete values (expected vs. actual) whenever possible
- The rollback steps must be executable without ambiguity
- Prevention section feeds back into planning for replacement/future plans
- Reference specific commits so rollback is precise
- If the failure reveals a gap in the verification strategy, note it for the verifier
</guidelines>
