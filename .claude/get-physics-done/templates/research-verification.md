---
template_version: 1
---
# Research Verification Template

Template for `.gpd/phases/XX-name/{phase}-VERIFICATION.md` -- persistent research verification session tracking.

A conversational walkthrough of research results, checking derivation logic, physical intuition, edge cases, and overall soundness.

---

## File Template

```markdown
---
status: validating | completed | diagnosed
phase: XX-name
source: [list of SUMMARY.md files validated]
started: [ISO timestamp]
updated: [ISO timestamp]
---

## Current Check

<!-- OVERWRITE each check - shows where we are -->

number: [N]
name: [check name]
expected: |
[what the researcher should confirm or evaluate]
awaiting: researcher response

## Checks

### 1. [Check Name]

expected: [what should hold - physical reasoning, derivation step, or result property]
result: [pending]

### 2. [Check Name]

expected: [what should hold]
result: pass

### 3. [Check Name]

expected: [what should hold]
result: issue
reported: "[verbatim researcher response]"
severity: major

### 4. [Check Name]

expected: [what should hold]
result: skipped
reason: [why skipped]

...

## Summary

total: [N]
passed: [N]
issues: [N]
pending: [N]
skipped: [N]

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->

- truth: "[expected physics property from check]"
  status: failed
  reason: "Researcher reported: [verbatim response]"
  severity: blocker | major | minor | cosmetic
  check: [N]
  root_cause: "" # Filled by diagnosis
  artifacts: [] # Filled by diagnosis
  missing: [] # Filled by diagnosis
  debug_session: "" # Filled by diagnosis
```

---

<section_rules>

**Frontmatter:**

- `status`: OVERWRITE - "validating" or "completed" or "diagnosed"
- `phase`: IMMUTABLE - set on creation
- `source`: IMMUTABLE - SUMMARY files being validated
- `started`: IMMUTABLE - set on creation
- `updated`: OVERWRITE - update on every change

**Current Check:**

- OVERWRITE entirely on each check transition
- Shows which check is active and what's awaited
- On completion: "[verification complete]"

**Checks:**

- Each check: OVERWRITE result field when researcher responds
- `result` values: [pending], pass, issue, skipped
- If issue: add `reported` (verbatim) and `severity` (inferred)
- If skipped: add `reason` if provided

**Summary:**

- OVERWRITE counts after each response
- Tracks: total, passed, issues, pending, skipped

**Gaps:**

- APPEND only when issue found (YAML format)
- After diagnosis: fill `root_cause`, `artifacts`, `missing`, `debug_session`
- This section feeds directly into /gpd:plan-phase --gaps

</section_rules>

<check_categories>

Research verification checks fall into these categories, ordered by diagnostic power:

### 1. Derivation Logic Walkthrough

Walk through the key steps of a derivation, asking the researcher to confirm each logical step.

- "In going from Eq. (3) to Eq. (4), we commuted H_0 and V. Is this valid given [conditions]?"
- "The saddle point approximation in step 5 requires [condition]. Does this hold in our parameter regime?"
- "We dropped the O(lambda^3) terms. Given lambda = 0.3, is this justified?"

### 2. Physical Intuition Probes

Ask whether results match physical expectations without looking at the math.

- "The ground state energy increases with coupling. Does this match your intuition for this system?"
- "The correlation length diverges as T -> T_c from above. Is the exponent reasonable for this universality class?"
- "The entropy is negative at low temperature. Is this physical?"

### 3. Limiting Case Spot Checks

Pick specific limits and ask the researcher to verify the behavior.

- "In the non-interacting limit (g=0), our expression reduces to [X]. Does this match the free theory?"
- "At infinite temperature, the partition function should be [dim of Hilbert space]. We get [Y]. Agree?"
- "For a single particle (N=1), the result should reduce to [textbook formula]. Does it?"

### 4. Edge Case Probes

Explore parameter regimes where things might break.

- "What happens at the phase transition point? Our expression has a [pole/divergence/discontinuity]. Is this expected?"
- "For very large N, the computation gives [X]. Is this consistent with the thermodynamic limit?"
- "At zero temperature, the partition function should project onto the ground state. Does our expression do this?"

### 5. Consistency Cross-Checks

Verify that different parts of the research are consistent with each other.

- "The perturbative result (Phase 2) and the numerical result (Phase 3) differ by 5% at coupling g=0.1. Is this within expected error?"
- "The analytical continuation from Euclidean to Lorentzian gives [X]. Is this consistent with the real-time simulation?"
- "The Ward identity requires [relation]. Do our computed Green's functions satisfy it?"

### 6. Robustness and Sensitivity

Probe how sensitive results are to assumptions and approximations.

- "If we change the UV cutoff by a factor of 2, how much does the result change?"
- "The result depends on the regularization scheme. Have we checked scheme independence of physical observables?"
- "We used 5000 disorder realizations. Is the statistical error bar reliable, or do we need more?"

</check_categories>

<diagnosis_lifecycle>

**After verification complete (status: completed), if gaps exist:**

1. Researcher triggers diagnosis (from verify-work offer or manually)
2. debug workflow spawns parallel debug agents
3. Each agent investigates one gap, returns root cause
4. VERIFICATION.md Gaps section updated with diagnosis:
   - Each gap gets `root_cause`, `artifacts`, `missing`, `debug_session` filled
5. status -> "diagnosed"
6. Ready for /gpd:plan-phase --gaps with root causes

**After diagnosis:**

```yaml
## Gaps

- truth: "Correlation function decays as power law at criticality"
  status: failed
  reason: "Researcher reported: decay looks exponential, not power-law - probably not at the critical point"
  severity: major
  check: 4
  root_cause: "Critical temperature T_c computed with wrong normalization of coupling constant"
  artifacts:
    - path: "src/critical_point.py"
      issue: "J_eff = J / sqrt(N) but should be J / sqrt(N-1) for this convention"
  missing:
    - "Correct T_c calculation with proper coupling normalization"
  debug_session: ".gpd/debug/wrong-critical-temp.md"
```

</diagnosis_lifecycle>

<lifecycle>

**Creation:** When /gpd:verify-work starts new verification session

- Extract checks from SUMMARY.md files and verification report
- Organize by check category (derivation logic, intuition, limits, edges, consistency, robustness)
- Set status to "validating"
- Current Check points to check 1
- All checks have result: [pending]

**During verification:**

- Present check from Current Check section
- Researcher responds with confirmation or concern
- Update check result (pass/issue/skipped)
- Update Summary counts
- If issue: append to Gaps section (YAML format), infer severity
- Move Current Check to next pending check

**On completion:**

- status -> "completed"
- Current Check -> "[verification completed]"
- Commit file
- Present summary with next steps

**Resume after /clear:**

1. Read frontmatter -> know phase and status
2. Read Current Check -> know where we are
3. Find first [pending] result -> continue from there
4. Summary shows progress so far

</lifecycle>

<severity_guide>

Severity is INFERRED from researcher's natural language, never asked.

| Researcher describes                                                               | Infer    |
| ---------------------------------------------------------------------------------- | -------- |
| Wrong sign, diverges unphysically, violates conservation law, negative probability | blocker  |
| Doesn't match known limit, off by factor of 2, wrong exponent, suspicious behavior | major    |
| Slightly off, small discrepancy, could be numerical artifact, minor concern        | minor    |
| Notation inconsistency, plot formatting, labeling, style issue                     | cosmetic |

Default: **major** (safe default, researcher can clarify if wrong)

</severity_guide>

<good_example>

```markdown
---
status: diagnosed
phase: 03-phase-diagram
source: 03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md
started: 2025-07-10T14:00:00Z
updated: 2025-07-10T14:45:00Z
---

## Current Check

[verification complete]

## Checks

### 1. Derivation: Effective action saddle-point validity

expected: The saddle-point approximation for the partition function requires large N. For our N=32, the correction should be O(1/N) ~ 3%. Is the 5% discrepancy with exact diag consistent with this?
result: pass
note: "Researcher confirmed: 5% is within expected 1/N corrections plus statistical error from disorder averaging"

### 2. Intuition: Order parameter behavior near T_c

expected: The order parameter should vanish continuously at T_c (second-order transition) with mean-field exponent beta=1/2 or appropriate universality class exponent
result: pass

### 3. Limiting case: High-temperature limit of susceptibility

expected: chi(T) ~ 1/T (Curie law) for T >> T_c
result: pass

### 4. Limiting case: Zero-temperature order parameter

expected: Order parameter should saturate to maximum value at T=0
result: issue
reported: "Order parameter at T=0 is 0.87, but for this model the exact ground state has order parameter 1.0. Something is off - maybe not enough cooling in the Monte Carlo?"
severity: major

### 5. Edge case: Behavior at phase boundary for large system

expected: Finite-size scaling collapse should work with known critical exponents
result: pass

### 6. Consistency: Specific heat from energy vs from partition function

expected: C_v computed as dE/dT should match C_v = -T d^2F/dT^2
result: pass

### 7. Robustness: Sensitivity to Monte Carlo equilibration

expected: Results should be insensitive to doubling the equilibration time
result: issue
reported: "When I doubled equilibration from 10^4 to 2x10^4 sweeps, the order parameter at T=0 changed from 0.87 to 0.94. Not equilibrated."
severity: blocker

## Summary

total: 7
passed: 5
issues: 2
pending: 0
skipped: 0

## Gaps

- truth: "Order parameter reaches saturation value 1.0 at T=0"
  status: failed
  reason: "Researcher reported: Order parameter at T=0 is 0.87 but exact is 1.0. Not fully equilibrated."
  severity: major
  check: 4
  root_cause: "Monte Carlo equilibration too short - 10^4 sweeps insufficient for low-T phase"
  artifacts:

  - path: "src/monte_carlo.py"
    issue: "N_equil = 10000 is too few sweeps at low temperature"
    missing:
  - "Increase equilibration to 10^5 sweeps minimum, add autocorrelation analysis"
    debug_session: ".gpd/debug/mc-equilibration.md"

- truth: "Results are insensitive to equilibration time (converged)"
  status: failed
  reason: "Researcher reported: doubling equilibration changed order parameter from 0.87 to 0.94"
  severity: blocker
  check: 7
  root_cause: "Same root cause as check 4 - insufficient equilibration at low T"
  artifacts:
  - path: "src/monte_carlo.py"
    issue: "Fixed equilibration length doesn't adapt to critical slowing down near T_c"
    missing:
  - "Implement adaptive equilibration with autocorrelation time measurement"
  - "Add convergence diagnostic: run until autocorrelation time is measured and N_equil > 20 \* tau_auto"
    debug_session: ".gpd/debug/mc-equilibration.md"
```

</good_example>

<guidelines>

**What makes good verification checks:**

- Each check should be answerable by a physicist reviewing the results
- Checks should probe understanding, not just ask "is this right?"
- Include the expected answer or behavior so disagreement is clear
- Mix high-level intuition checks with detailed quantitative spot-checks
- Order from most diagnostic (derivation logic) to least (robustness)

**Conversation style:**

- Present one check at a time
- Frame checks as collaborative discussion, not an exam
- If the researcher spots something, explore it before moving on
- Adapt subsequent checks based on earlier findings (if a normalization is wrong, check downstream consequences)

**When to use research verification:**

- After a research phase completes and verification report passes
- When results need human physics judgment beyond automated checks
- Before publishing or building on results in later phases
- When the verification report flags `human_needed`

**When NOT to use:**

- For automated checks (use verification-report.md instead)
- When all checks can be performed programmatically
- For implementation bugs (use standard debugging)

</guidelines>
