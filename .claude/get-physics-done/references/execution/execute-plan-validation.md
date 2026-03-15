# Execute-Plan: Physics Validation & Deviation Rules

Referenced by `src/gpd/specs/workflows/execute-plan.md`. Governs physics validation gates, deviation handling, and verification failures during plan execution.

## Physics Execution Discipline

Before and during each calculation:

- Before each calculation: state expected dimensional form of the answer
- After each derivation step: verify dimensional consistency
- At natural breakpoints: check limiting cases specified in the plan
- For numerical work: monitor convergence and compare against analytic estimates
- Record all intermediate results for cross-checking

## Physics Validation Gates

Validation failures during execution are critical checkpoints, not bugs.

**Indicators:** Dimensional mismatch, wrong limiting behavior, conservation law violation, divergence in supposedly convergent series, unphysical values (negative probabilities, superluminal velocities, negative entropy)

**Protocol:**

1. Recognize validation failure (not a code bug)
2. STOP task execution
3. Diagnose: Is this an error in the derivation, a wrong approximation, or a numerical issue?
4. If derivation error: trace back to source, fix, re-derive from that point
5. If approximation breakdown: document the regime boundary, flag for plan revision
6. If numerical issue: adjust method (step size, basis size, regularization), retry
7. Document the failure and resolution in the deviation log

**In Summary:** Document under "## Validation Events", not as deviations unless they required plan changes.

## Deviation Rules

You WILL discover unplanned work. Apply automatically, track all for Summary.

**Full rules:** See `references/execution/executor-deviation-rules.md` for complete 6-rule system with examples and escalation protocols. The compact table below maps to the full rules as noted.

| Rule                    | Full Rules | Trigger                                                                                                                                    | Action                                                                | Permission |
| ----------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- | ---------- |
| **1: Computational Bug**   | Rules 1-2 | Mathematical error, sign mistake, wrong index contraction, divergent integral, convergence failure, NaN/Inf | Fix -> re-derive -> verify -> track `[Rule 1 - Bug]` or `[Rule 2 - Convergence]`                | Auto       |
| **2: Missing Component** | Rules 3-4 | Missing normalization, boundary condition, regularization, convergence check, gauge fixing, symmetry factor, approximation breakdown                                | Add -> verify -> track `[Rule 3 - Approximation]` or `[Rule 4 - Missing]`                  | Auto       |
| **3: Physics Redirection**   | Rule 5  | Results contradict expectations, fundamentally different approach needed, calculated result disagrees with known values by orders of magnitude | STOP -> present decision (below) -> track `[Rule 5 - Physics]` | Ask user   |
| **4: Scope Change**   | Rule 6 | Significant expansion beyond the plan, auxiliary problem must be solved first, substantial new infrastructure required | STOP -> present decision (below) -> track `[Rule 6 - Scope]` | Ask user   |

**Rules 3-4 format:**

```
!! Methodological Decision Needed

Current task: [task name]
Discovery: [what prompted this]
Proposed change: [modification]
Why needed: [rationale -- what went wrong with original approach]
Impact: [what this affects downstream]
Alternatives: [other approaches with tradeoffs]

Proceed with proposed change? (yes / different approach / defer)
```

**Priority:** Rules 3-4 (STOP, ask user) > Rules 1-2 (auto-fix) > unsure -> Rule 3 (ask)
**Edge cases:** missing normalization -> R2 | sign error -> R1 | new ansatz -> R3 | different basis set -> R1/2 | need auxiliary problem -> R4
**Heuristic:** Affects correctness/convergence/completion? -> R1-2 (auto). Changes the physics? -> R3. Changes the scope? -> R4.

## Documenting Deviations

Summary MUST include deviations section. None? -> `## Deviations from Plan\n\nNone - plan executed exactly as written.`

Per deviation: **[Rule N - Category] Title** -- Found during: Task X | Issue | Fix | Files modified | Verification | Commit hash

End with: **Total deviations:** N auto-fixed (breakdown). **Impact:** assessment.

## Verification Failure Gate

If verification fails: STOP. Present: "Verification failed for Task [X]: [name]. Expected: [criteria]. Actual: [result]." Options: Retry | Skip (mark incomplete) | Stop (investigate).

**Physics-specific verification failures:**

- Dimensional mismatch: Show expected vs actual dimensions, trace to source
- Limiting case failure: Show which limit failed and by how much
- Conservation violation: Show which quantity is not conserved and the magnitude of violation

If skipped -> SUMMARY "Issues Encountered".
