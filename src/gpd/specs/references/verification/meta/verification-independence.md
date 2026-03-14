# Verification Independence

## Why Verification Independence Matters

When the same system that executed a plan also verifies the results, **confirmation bias** is the primary risk. An agent that knows the plan's approach will unconsciously verify _whether the plan was followed_ rather than _whether the physics is correct_.

This is the difference between:

- **Auditing:** "Did you do what you said you would?" (process-focused)
- **Verification:** "Is what you produced actually correct?" (outcome-focused)

GPD verification is outcome-focused. A derivation that deviates from the plan but produces correct physics passes. A derivation that follows the plan exactly but has a sign error fails.

### Confirmation bias in self-audit

When a verifier has access to the full execution context (PLAN.md body, SUMMARY.md claims, execution logs), it tends to:

1. **Accept claimed results at face value** -- "SUMMARY says convergence was achieved" becomes a substitute for checking convergence
2. **Follow the plan's logic instead of the physics** -- checking whether step 3 follows from step 2 in the plan, rather than whether the equation is dimensionally consistent
3. **Miss errors the executor also missed** -- if the executor didn't notice a factor-of-2 error, a verifier following the same reasoning path will miss it too
4. **Rationalize discrepancies** -- "The plan said to use this approximation, so the limiting case not matching must be acceptable"

Structural separation eliminates these failure modes by ensuring the verifier cannot access process information.

## What the Verifier Receives vs. What It Doesn't

### RECEIVES (outcome information)

| Item                    | Source                                | Purpose                                                            |
| ----------------------- | ------------------------------------- | ------------------------------------------------------------------ |
| Phase goal              | ROADMAP.md                            | What the research should achieve                                   |
| Plan contract           | PLAN.md frontmatter `contract` block  | Decisive claims, deliverables, anchors, acceptance tests, links    |
| Artifact files          | Disk (paths from contract deliverables) | The actual research outputs to inspect                           |
| Active reference context | init/verification context             | Approved anchors, baselines, must-read references, prior outputs   |
| STATE.md                | .gpd/STATE.md                         | Project conventions, active approximations, unit system            |
| config.json             | .gpd/config.json                      | Project configuration                                              |
| INSIGHTS.md             | .gpd/INSIGHTS.md (if exists)          | Known problem patterns for extra scrutiny                          |
| ERROR-PATTERNS.md       | .gpd/ERROR-PATTERNS.md (if exists)    | Previous error patterns to check against                           |

### DOES NOT RECEIVE (process information)

| Item              | Why excluded                                                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Full PLAN.md body | Contains task breakdowns and implementation strategy -- knowing _how_ something was done biases toward confirming that approach |
| SUMMARY.md files  | Contains executor claims about what was accomplished -- "claimed convergence" is not evidence of convergence                    |
| Execution logs    | Contains agent reasoning and debugging history -- irrelevant to whether final results are correct                               |
| Agent identities  | Who wrote what is irrelevant to physics correctness                                                                             |
| Attempt count     | How many tries it took is irrelevant to whether the final result is right                                                       |

## Verification by Re-Derivation vs. Verification by Pattern Matching

There are two fundamentally different approaches to verification. GPD requires the first and forbids the second.

### Verification by Re-Derivation (REQUIRED)

The verifier independently computes or re-derives the result (or aspects of it) and compares with the artifact. This catches errors regardless of how convincing the presentation is.

**What it looks like:**

1. Read the final expression from the artifact
2. Substitute specific test parameter values and evaluate
3. Compare the result with an independently known answer
4. Take limits of the expression and compare with known limiting forms
5. Trace physical dimensions through each term and verify consistency
6. Cross-check by an alternative computational method

**Why it works:** A sign error, a missing factor of 2pi, or a wrong index contraction will produce a wrong numerical answer at a test point, a wrong limit, or an inconsistent dimension -- regardless of how the executor described their work. The computation does not lie.

**Example:**

The artifact claims: `Z(T) = sum_n exp(-E_n / (k_B * T))`

Re-derivation check:

- Evaluate at T -> infinity: Z should approach the total number of states
- Evaluate at T -> 0: Z should approach g*0 * exp(-E*0 / (k_B * T)) where g_0 is ground state degeneracy
- For a known system (e.g., two-level system with E_0=0, E_1=epsilon): Z(T) = 1 + exp(-epsilon/(k_B\*T)). Substitute T = epsilon/k_B: Z = 1 + exp(-1) = 1.368. Evaluate the artifact's expression at the same point and compare.

### Verification by Pattern Matching (FORBIDDEN)

The verifier searches the artifact text for keywords associated with correct physics, without actually checking whether the physics is correct. This is "verification theater" -- it looks like verification but catches almost nothing.

**What it looks like:**

```bash
# WRONG: checking if the word "limit" appears
grep -nE "(limit|lim_|->.*0|->.*inf)" artifact.py

# WRONG: checking if dimensional analysis is mentioned
grep -nE "(units|dimensions|\\[.*\\])" artifact.py

# WRONG: checking if conservation is discussed
grep -nE "(conserv|Ward|Noether)" artifact.py

# WRONG: checking if convergence is mentioned
grep -nE "(convergence|converge|Richardson)" artifact.py

# WRONG: counting physics library imports as evidence of computation
grep -cE "(np\.|scipy\.|solve|integrate)" artifact.py
```

**Why it fails:** An artifact can mention "dimensional analysis" while having dimensionally inconsistent equations. It can mention "convergence" while being unconverged. It can import numpy while returning hardcoded values. It can discuss Ward identities while violating them. Pattern matching tells you about the TEXT, not about the PHYSICS.

**The critical distinction:**

| Question                                 | Pattern matching says              | Re-derivation says                                                                 |
| ---------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------- |
| "Does the limit work?"                   | "The word 'limit' appears 3 times" | "Setting g=0 gives Z=1, but it should be Z=N!. WRONG."                             |
| "Are dimensions consistent?"             | "Units are mentioned on line 12"   | "Line 23: [Energy] + [Length]. INCONSISTENT."                                      |
| "Is the Ward identity satisfied?"        | "Ward identity is referenced"      | "q_mu \* Gamma^mu at q=(1,0,0,0): gives 0.5, S^-1 difference gives 0.3. VIOLATED." |
| "Does the result agree with literature?" | "A reference is cited"             | "Computed Tc=4.21, literature Tc=4.51. 7% error. DISAGREES."                       |

## The "Results, Not Process" Principle

**A correct result derived by an unexpected method is still correct. An incorrect result derived by the planned method is still incorrect.**

The verifier's job:

1. Read the phase goal -- what should be true when this phase succeeds?
2. Read the approved contract -- what specific, testable outcomes must hold?
3. Inspect the actual artifacts -- do the derivations, calculations, and results support those claims?
4. **Perform computational verification** -- substitute test values, take limits, check dimensions, cross-check by independent methods
5. Report what holds and what doesn't -- with **computation evidence** from independent verification

The verifier does NOT:

- Check whether the plan was followed
- Confirm SUMMARY.md claims
- Evaluate whether the execution approach was optimal
- Judge whether deviations from the plan were justified
- Use `search_files` for physics keywords as a substitute for doing physics

## How This Mirrors Physics Peer Review

In physics peer review:

- **Reviewers see:** The manuscript (results, derivations, figures, methodology description)
- **Reviewers do NOT see:** Lab notebooks, code repositories, email threads about the approach, rejected drafts, failed experiments

A good referee does not just read the paper and check if the right words appear. A good referee:

- Re-derives key steps to check for errors
- Substitutes test values into equations to verify they work
- Checks limiting cases independently
- Verifies dimensional consistency
- Compares numerical results against known benchmarks
- Tests whether symmetry arguments actually hold

A bad referee checks if the paper "looks right" -- correct format, correct citations, plausible-sounding conclusions. This is pattern matching, not verification.

GPD's verification separation follows the same principle, combined with the requirement for computational verification:

| Good peer review                   | GPD computational verification            |
| ---------------------------------- | ----------------------------------------- |
| Re-derive key equation             | Evaluate expression at test points        |
| Check limiting cases independently | Take limit of final expression, compare   |
| Verify dimensional consistency     | Trace dimensions symbol by symbol         |
| Compare with known results         | Compute relative error against benchmark  |
| Test symmetry arguments            | Apply transformation, verify invariance   |
| Assess convergence of numerics     | Run at multiple resolutions, measure rate |

| Bad peer review                        | GPD pattern matching (FORBIDDEN)      |
| -------------------------------------- | ------------------------------------- |
| "The derivation looks reasonable"      | `grep -c "derive"` returns > 0        |
| "Units seem fine"                      | `grep "units"` finds a mention        |
| "They cite the right references"       | `grep "literature"` finds a reference |
| "The paper mentions convergence tests" | `grep "convergence"` finds the word   |

## Practical Implications for Plan Authors

Because the verifier only sees the PLAN frontmatter contract plus final artifacts, those contract targets must be **self-contained, independently testable, and computationally verifiable**:

### Good contract-backed targets (computationally testable)

```yaml
contract:
  claims:
    - id: claim-partition-limit
      statement: "Partition function reduces to the ideal-gas result when coupling g -> 0"
      deliverables: [deliv-partition]
      acceptance_tests: [test-free-limit]
    - id: claim-ground-state
      statement: "Ground state energy agrees with exact diagonalization to 0.1% for N<=8"
      deliverables: [deliv-spectrum]
      acceptance_tests: [test-ed-match]
  deliverables:
    - id: deliv-partition
      kind: derivation
      path: derivations/partition_function.py
      description: "Analytical partition function with saddle-point expansion"
    - id: deliv-spectrum
      kind: table
      path: analysis/ground_state.json
      description: "Ground-state energies across N<=8"
  acceptance_tests:
    - id: test-free-limit
      subject: claim-partition-limit
      kind: limiting_case
      procedure: "Evaluate Z at g=0 and compare with ideal-gas closed form"
      pass_condition: "Z(T=1, N=4, g=0) = 256"
      evidence_required: [deliv-partition]
    - id: test-ed-match
      subject: claim-ground-state
      kind: benchmark
      procedure: "Compare ground-state energies to exact diagonalization for N<=8"
      pass_condition: "relative error <= 1e-3 at every tested N"
      evidence_required: [deliv-spectrum]
  links:
    - id: link-thermo
      source: claim-partition-limit
      target: deliv-partition
      relation: supports
      verified_by: [test-free-limit]
```

The verifier can check these by performing the specified computations, without knowing anything about the plan's task structure.

### Bad contract-backed targets (only pattern-matchable)

```yaml
contract:
  claims:
    - id: claim-task-done
      statement: "Task 3 was completed successfully" # Process, not outcome
    - id: claim-plan-works
      statement: "The approach from the plan works" # Self-referential
    - id: claim-dimensions
      statement: "Dimensional analysis was performed" # Claims process, not outcome
    - id: claim-limits
      statement: "Limiting cases were checked" # Claims process, not outcome
  deliverables:
    - id: deliv-output
      kind: data
      path: output.dat
      description: "Output from the simulation" # What does it provide physically?
  acceptance_tests:
    - id: test-circular
      subject: claim-plan-works
      kind: proxy
      procedure: "Confirm the output matches the SUMMARY.md claim" # Circular
      pass_condition: "Limits are correct" # No specific test
      evidence_required: [deliv-output]
```

**Rule of thumb:** If a contract target cannot be verified by someone who has never seen the plan body and who must check it by performing a computation rather than by reading prose, rewrite it.

### The test for a good contract target

Ask: "Can a verifier check this by substituting numbers, taking a limit, tracing dimensions, or computing something?" If the answer is no, then it is not a good contract target.

| Contract target                                       | Can verify by computation?  | Verdict |
| ----------------------------------------------------- | --------------------------- | ------- |
| "Z(T=1, N=2, g=0) = 4"                                | Yes (evaluate expression)   | Good    |
| "Classical limit (hbar->0) gives Z = kT/omega"        | Yes (take limit)            | Good    |
| "Ground state energy E0(N=6) = -1.7726 (exact diag)"  | Yes (compare values)        | Good    |
| "All equations are dimensionally consistent"          | Yes (trace dimensions)      | Good    |
| "Spectral function is non-negative for all omega"     | Yes (evaluate on grid)      | Good    |
| "Convergence was tested"                              | No (process claim)          | Bad     |
| "The derivation is correct"                           | No (too vague)              | Bad     |
| "Literature references are cited"                     | No (text search only)       | Bad     |
| "The result is physically reasonable"                 | Partially (needs specifics) | Rewrite |

**See also:** `../errors/llm-physics-errors.md` — pattern-matching (checking for keywords rather than computing) is exactly the LLM failure mode this document guards against; the error catalog provides concrete computational checks to replace pattern-matching.
