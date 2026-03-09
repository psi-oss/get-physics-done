# Executor Deviation Rules

Load this reference during plan execution. The inline executor prompt has a compact summary of rule priorities and escalation thresholds. This file provides the full rules, examples, and escalation protocols.

---

## Deviation Rules

**While executing, you WILL encounter situations not anticipated in the plan.** Apply these rules automatically. Track all deviations in the research log and Summary.

**Shared process for Rules 1-4:** Diagnose the issue --> apply the appropriate fix or workaround --> verify the fix --> document in research log --> continue task --> track as `[Rule N - Type] description`

No user permission needed for Rules 1-4.

---

**RULE 1: Auto-fix computational bugs**

**Trigger:** Code doesn't produce correct results (numerical errors, wrong output, crashes)

**Examples:** Off-by-one in indexing, wrong sign in a Hamiltonian term, incorrect unit conversion, mismatched array dimensions, wrong integration bounds, transposed matrix indices, floating-point overflow/underflow, memory allocation failure, wrong FFT normalization convention

---

**RULE 2: Auto-fix convergence and numerical issues**

**Trigger:** A calculation doesn't converge, produces NaN/Inf, or fails numerical validation

**Examples:** Iterative solver not converging (increase iterations, switch algorithm, improve initial guess), step size too large in ODE integration (reduce step, switch to adaptive), matrix nearly singular (add regularization, switch to SVD), quadrature insufficient (increase points, switch to Gauss-Kronrod), mesh too coarse (refine, switch to adaptive mesh), eigenvalue solver missing states (increase basis size, shift-invert)

**Action:** Try standard numerical remedies automatically. If the issue is fundamental (wrong physics, not wrong numerics), escalate to Rule 5.

---

**RULE 3: Auto-handle approximation breakdowns**

**Trigger:** An approximation used in the plan breaks down in the regime being studied

**Examples:** Perturbation series diverges (resum, switch to Pade approximant), WKB breaks down near turning point (apply connection formulas), mean-field fails (add fluctuation corrections), linear response insufficient (include next-order terms), small-angle approximation invalid (use exact expression), non-relativistic limit inappropriate (use relativistic expressions)

**Action:** Apply the standard physics remedy for the approximation breakdown. Document the regime where the approximation fails and what was used instead.

---

**RULE 4: Auto-add missing components**

**Trigger:** Execution reveals missing prerequisites that should have been in the plan

**Examples:** Missing normalization, forgotten boundary term in integration by parts, missing symmetry factor, absent convergence check, no error estimation, missing dimensional analysis verification, forgotten Jacobian in coordinate transformation, missing regularization for divergent integral, absent gauge-fixing term

**Action:** Add the missing component inline. These are correctness requirements, not scope expansion.

---

**RULE 5: Ask about physics redirections**

**Trigger:** Results contradict expectations, or a fundamentally different approach is needed

**Examples:** Calculated result disagrees with known values by orders of magnitude, symmetry that should be present is broken, new terms needed that change the structure of the theory, phase transition found where none expected, instability discovered in supposedly stable solution, sign problem prevents Monte Carlo evaluation, topological obstruction to proposed approach

**Action:** STOP --> return checkpoint with: what was found, comparison with expectations, proposed alternative approach, impact on downstream tasks, assessment of whether this invalidates prior results. **Researcher decision required.**

---

**RULE 6: Ask about scope changes**

**Trigger:** Completing the task properly requires significant expansion beyond the plan

**Examples:** Need to solve an auxiliary problem first, additional physical regime must be explored, new observable must be computed for validation, substantial new code infrastructure required, need to implement a different algorithm entirely, database of material parameters needed

**Action:** STOP --> return checkpoint with: what additional work is needed, why it's needed, estimated effort, alternatives (including proceeding with caveats), impact on timeline. **Researcher decision required.**

---

**RULE PRIORITY:**

1. Rules 5-6 apply --> STOP (researcher decision)
2. Rules 1-4 apply --> Fix automatically
3. Genuinely unsure --> Rule 5 (ask)

**Edge cases:**

- NaN in output --> Rule 1 or 2 (diagnose: if code bug, Rule 1; if numerical issue, Rule 2)
- Perturbation series diverges --> Rule 3 (approximation breakdown)
- Result off by factor of 2 --> Rule 4 (likely missing symmetry factor)
- Result off by factor of 1000 --> Rule 5 (possible fundamental issue)
- Need to implement Lanczos algorithm from scratch --> Rule 6 (scope change)
- Missing import statement --> Rule 1 (code bug)

**When in doubt:** "Does this affect correctness of the physics?" YES --> Rules 1-4. "Does this change what physics we're doing?" YES --> Rules 5-6.

---

## Automatic Failure Escalation

The deviation rules above handle individual events. The following escalation logic detects patterns of repeated failures that signal a deeper problem requiring human judgment. These escalations are mandatory --- they override the auto-fix behavior of Rules 1-4.

### Escalation 1: Repeated approximation breakdown --> forced stop

If Rule 3 (auto-handle approximation breakdown) is applied **twice within the same plan execution** --- even for different approximations or different tasks --- escalate to Rule 5 (stop and ask).

Rationale: A single approximation breakdown is a local issue with a standard remedy. Two breakdowns in the same plan suggest the theoretical framework or parameter regime chosen in the plan is not well-suited to the problem. The researcher needs to reassess the approach.

When escalating, provide:

- Both approximation breakdowns: what approximation, what regime, what remedy was applied
- Whether the two breakdowns are related (e.g., both arise from strong coupling)
- Assessment: is the current approach salvageable with better approximations, or is a fundamentally different method needed?
- Proposed alternatives (e.g., non-perturbative method, different expansion parameter, numerical approach)

### Escalation 2: Context window pressure --> forced checkpoint

If the current task execution has consumed more than **50% of the available context window**, trigger an immediate checkpoint regardless of task status:

1. **Checkpoint immediately:** Save all work completed so far using the task checkpoint protocol.
2. **Flag for plan splitting:** In the checkpoint message, include a `[CONTEXT PRESSURE]` warning indicating that the remaining tasks may need to be split into a separate plan or executed by a continuation agent.
3. **Preserve state completely:** Write all running state (conventions, equations derived, numerical parameters, approximations in use, intermediate results) to the state tracking file so a continuation agent can resume without loss.
4. **Recommend plan restructuring:** If more than 2 tasks remain, recommend to the researcher that the plan be split. Large plans that consume the context window risk degraded reasoning quality in later tasks.

This escalation is automatic and does not require researcher approval to checkpoint. It DOES require researcher awareness before continuation.

### Escalation 3: Persistent numerical convergence failure --> forced stop

If a numerical computation fails to converge and Rule 2 (auto-fix convergence) has been applied with **3 successive parameter adjustments** without achieving convergence, escalate to Rule 5 (stop and ask).

The 3 adjustments must be meaningfully different attempts, not minor variations of the same fix. Examples of distinct adjustments:

- Attempt 1: Increase grid resolution / basis size
- Attempt 2: Switch algorithm (e.g., direct diagonalization -> iterative, Euler -> RK4 -> adaptive)
- Attempt 3: Reformulate the numerical problem (e.g., change variables, precondition, regularize)

When escalating, provide a structured diagnostic:

```markdown
### Convergence Failure Diagnostic

**Computation:** [what was being computed]
**Expected result:** [order of magnitude, sign, known limits]

**Attempt 1:** [what was tried]

- Parameters: [specific values]
- Result: [what happened --- NaN, oscillation, slow drift, wrong limit]

**Attempt 2:** [what was tried]

- Parameters: [specific values]
- Result: [what happened]

**Attempt 3:** [what was tried]

- Parameters: [specific values]
- Result: [what happened]

**Diagnosis:**

- [ ] Possible code bug (but Rule 1 checks passed)
- [ ] Possible ill-posed problem (e.g., singular matrix, stiff system beyond solver capability)
- [ ] Possible wrong physics (e.g., phase transition, instability, sign problem)
- [ ] Possible insufficient resolution (need resources beyond current capability)

**Recommended next step:** [specific recommendation for the researcher]
```
