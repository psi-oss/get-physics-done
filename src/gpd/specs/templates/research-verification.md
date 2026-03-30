---
template_version: 1
---

# Research Verification Template

Template for `GPD/phases/XX-name/{phase}-VERIFICATION.md` -- persistent research verification session tracking.

A conversational walkthrough of research results, checking derivation logic, physical intuition, edge cases, and overall soundness.
Use `@{GPD_INSTALL_DIR}/templates/verification-report.md` for the canonical verification frontmatter contract. This template adds the researcher-session body scaffold (`Current Check`, conversational logs, and diagnosis flow) on top of that same verification ledger.
The verification-side `suggested_contract_checks` entries are part of the same canonical schema surface, so the body scaffold must stay aligned with the frontmatter contract rather than inventing a parallel checklist format.
The contract-backed frontmatter example below keeps `uncertainty_markers` explicit and non-empty so the strict contract-results validator sees unresolved anchors before the report is written.
If the project has an active convention lock, include a machine-readable `ASSERT_CONVENTION` comment immediately after the YAML frontmatter using canonical lock keys and exact lock values. Changed phase verification artifacts now fail `gpd pre-commit-check` if this required header is missing or mismatched.

---

## File Template

```markdown
---
phase: XX-name
verified: [ISO timestamp of latest ledger update]
status: passed | gaps_found | expert_needed | human_needed
score: [N]/[M] contract targets verified
plan_contract_ref: GPD/phases/XX-name/{phase}-{plan}-PLAN.md#/contract
contract_results:
  claims:
    claim-main:
      status: not_attempted
      summary: "[verification not started yet]"
      linked_ids: [deliverable-main, acceptance-test-main, reference-main]
      evidence:
        - verifier: gpd-verifier
          method: benchmark reproduction
          confidence: high
          claim_id: claim-main
          deliverable_id: deliverable-main
          acceptance_test_id: acceptance-test-main
          reference_id: reference-main
          forbidden_proxy_id: forbidden-proxy-main
          evidence_path: "GPD/phases/XX-name/{phase}-VERIFICATION.md"
  deliverables:
    deliverable-main:
      status: not_attempted
      path: path/to/artifact
      summary: "[verification not started yet]"
      linked_ids: [claim-main, acceptance-test-main]
  acceptance_tests:
    acceptance-test-main:
      status: not_attempted
      summary: "[verification not started yet]"
      linked_ids: [claim-main, deliverable-main, reference-main]
  references:
    reference-main:
      status: missing
      completed_actions: []
      missing_actions: [read]
      summary: "[verification not started yet]"
  forbidden_proxies:
    forbidden-proxy-main:
      status: unresolved
      notes: "[verification not started yet]"
  uncertainty_markers:
    weakest_anchors: [anchor-1]
    unvalidated_assumptions: [assumption-1]
    competing_explanations: [alternative-1]
    disconfirming_observations: [observation-1]
comparison_verdicts:
  - subject_id: claim-main
    subject_kind: claim
    subject_role: decisive
    reference_id: reference-main
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: inconclusive
    recommended_action: "[close the decisive benchmark once the evidence is written]"
    notes: "[template placeholder; replace with the first decisive verdict]"
suggested_contract_checks:
  - check: "[missing decisive benchmark comparison]"
    reason: "[why the missing check matters]"
    suggested_subject_kind: acceptance_test
    suggested_subject_id: acceptance-test-main
    evidence_path: "[artifact path or expected evidence path]"
  - check: "[missing decisive reference comparison]"
    reason: "[why the missing compare-required reference matters]"
    suggested_subject_kind: reference
    suggested_subject_id: reference-main
    evidence_path: "[artifact path or expected evidence path]"
source:
  - "[SUMMARY.md file validated]"
  - "[additional SUMMARY.md file validated]"
started: "ISO timestamp"
updated: "ISO timestamp"
session_status: validating | completed | diagnosed
---

<!-- ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-minus, fourier_convention=physics -->

## Current Check

<!-- OVERWRITE each check - shows where we are -->
<!-- Include only the ID keys that actually bind this check.
Omit unused `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`,
and `forbidden_proxy_id` fields instead of leaving blank placeholder strings. -->

number: 1
name: "[check name]"
check_subject_kind: [claim | deliverable | acceptance_test | reference]
subject_id: "claim-main"
claim_id: "claim-main"
reference_ids: ["reference-id", "..."]
comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]
comparison_reference_id: "reference-id"
# If this check is not comparison-backed yet, omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders.
expected: |
  [what the researcher should confirm or evaluate]
# Use `comparison_kind: benchmark` for benchmark acceptance tests and
# `comparison_kind: cross_method` for cross-method acceptance tests.
suggested_contract_checks:
  # If you cannot bind the gap to a known contract target yet, omit both
  # `suggested_subject_kind` and `suggested_subject_id` instead of leaving one blank.
  - check: "missing decisive check"
    reason: "why the missing check matters"
    suggested_subject_kind: [claim | deliverable | acceptance_test | reference]
    suggested_subject_id: "matching contract id"
    evidence_path: "artifact path or expected evidence path"
  # Add a reference-backed decisive gap here whenever a benchmark reference or
  # a reference with required_actions including `compare` is still incomplete.
awaiting: researcher response

## Checks

### 1. [Check Name]

<!-- Include only the ID keys that actually bind this check.
Omit unused `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`,
and `forbidden_proxy_id` fields instead of leaving blank placeholder strings. -->

check_subject_kind: [claim | deliverable | acceptance_test | reference]
subject_id: "claim-main"
claim_id: "claim-main"
reference_ids: ["reference-id", "..."]
comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]
comparison_reference_id: "reference-id"
# If this check is not comparison-backed yet, omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders.
expected: "what should hold - physical reasoning, derivation step, or result property"
suggested_contract_checks:
  # If you cannot bind the gap to a known contract target yet, omit both
  # `suggested_subject_kind` and `suggested_subject_id` instead of leaving one blank.
  - check: "missing decisive check"
    reason: "why the missing check matters"
    suggested_subject_kind: [claim | deliverable | acceptance_test | reference]
    suggested_subject_id: "matching contract id"
    evidence_path: "artifact path or expected evidence path"
result: "pending"

### 2. [Check Name]

expected: "what should hold"
result: pass

### 3. [Check Name]

expected: "what should hold"
result: issue
reported: "[verbatim researcher response]"
severity: major

### 4. [Check Name]

expected: "what should hold"
result: skipped
reason: "why skipped"

...

## Summary

total: [N]
passed: [N]
issues: [N]
pending: [N]
skipped: [N]
comparison_verdicts_recorded: [N]
forbidden_proxies_rejected: [N]

## Comparison Verdicts

<!-- APPEND decisive benchmark / prior-work / experiment / cross-method outcomes.
The frontmatter `comparison_verdicts` ledger is authoritative; this section is a readable mirror. -->

- subject_kind: claim | deliverable | acceptance_test | reference
  subject_id: "contract-id"
  subject_role: decisive | supporting | supplemental | other
  reference_id: "reference-id"
  comparison_kind: benchmark | prior_work | experiment | cross_method | baseline | other
  verdict: pass | tension | fail | inconclusive
  metric: ""
  threshold: ""
  notes: ""

Only `subject_role: decisive` closes a required decisive comparison; the other roles are informative context only.

## Suggested Contract Checks

<!-- APPEND if the verifier finds missing decisive checks that should be added to the contract -->

- check: "Add decisive normalization benchmark comparison"
  reason: "The phase conclusion depends on an explicit benchmark acceptance test that is not yet named in the contract."
  suggested_subject_kind: acceptance_test
  suggested_subject_id: "acceptance-test-main"
  evidence_path: "GPD/phases/01-benchmark/benchmark-comparison.csv"

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->

<!-- Include only the ID keys that actually bind the gap.
Omit unused `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`,
and `forbidden_proxy_id` fields instead of leaving blank placeholder strings. -->

- gap_subject_kind: "claim | deliverable | acceptance_test | reference"
  subject_id: "claim-main"
  expectation: "[expected physics property from check]"
  expected_check: "[expected physics property from check]"
  claim_id: "claim-main"
  reference_ids: ["reference-id"]
  comparison_kind: "benchmark | prior_work | experiment | cross_method | baseline | other"
  comparison_reference_id: "reference-id"
  status: failed
  reason: "Researcher reported: [verbatim response]"
  suggested_contract_checks: []
  severity: blocker | major | minor | cosmetic
  check: 1
  root_cause: "" # Filled by diagnosis
  artifacts: [] # Filled by diagnosis
  missing: [] # Filled by diagnosis
  debug_session: "" # Filled by diagnosis
```

---

<section_rules>

**Frontmatter:**

- `status`: OVERWRITE using verification-report vocabulary - `passed | gaps_found | expert_needed | human_needed`
- `phase`: IMMUTABLE - set on creation
- `verified`: OVERWRITE - latest verification timestamp
- `score`: OVERWRITE - contract-backed verification progress summary
- `plan_contract_ref`, `contract_results`, `comparison_verdicts`, `suggested_contract_checks`: must follow `verification-report.md` / `contract-results-schema.md`
- `source`: IMMUTABLE - SUMMARY files being validated; keep this as a YAML list even when only one SUMMARY path is present
- `started`: IMMUTABLE - set on creation
- `updated`: OVERWRITE - update on every change
- `session_status`: optional session-progress field for `validating | completed | diagnosed`

**Current Check:**

- OVERWRITE entirely on each check transition
- Shows which check is active and what's awaited
- On completion: "[verification complete]"

**Checks:**

- Each check: OVERWRITE result field when researcher responds
- `result` values: [pending], pass, issue, skipped
- If issue: add `reported` (verbatim) and `severity` (inferred)
- If skipped: add `reason` if provided
- Use `check_subject_kind` for body-only verification checkpoints so it cannot be confused with frontmatter `comparison_verdicts.subject_kind`
- Every check should carry `check_subject_kind` / `subject_id` when the PLAN contract provides one
- Keep `check_subject_kind` and `gap_subject_kind` aligned with the canonical frontmatter-safe subject vocabulary
- Use `forbidden_proxy_id` for explicit proxy-rejection checks
- Use `comparison_kind` / `comparison_reference_id` when the check should later emit a comparison verdict
- Use `suggested_contract_checks` only when the verifier believes the contract omitted a decisive check, or when a decisive benchmark / cross-method check remains partial, not attempted, or still lacks a decisive verdict
- Keep `suggested_contract_checks` schema-tight: only `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id`, and `evidence_path` are valid keys
- `suggested_subject_kind` and `suggested_subject_id` travel together; if the missing check is not bound to a known contract target yet, omit both keys instead of leaving one blank

**Summary:**

- OVERWRITE counts after each response
- Tracks: total, passed, issues, pending, skipped, comparison_verdicts_recorded, forbidden_proxies_rejected

**Comparison Verdicts:**

- APPEND when a decisive comparison is performed
- Record verdicts against contract IDs rather than prose labels
- Use `subject_kind: claim|deliverable|acceptance_test|reference` only; contract-backed verdicts do not accept ad-hoc `artifact` or `other` subject kinds
- Only `subject_role: decisive` closes a decisive requirement; `supporting` / `supplemental` verdicts are informative context
- Keep the matching frontmatter `comparison_verdicts` array synchronized; body-only verdicts do not satisfy contract validation

**Suggested Contract Checks:**

- APPEND when the verifier identifies a missing decisive check
- Keep these generic and actionable: what to add, why, and where the evidence should come from
- Required before final validation whenever a decisive benchmark / cross-method check remains `partial` / `not_attempted` or a decisive comparison verdict is still missing

**Gaps:**

- APPEND only when issue found (YAML format)
- Use `gap_subject_kind` for the body scaffold that feeds `/gpd:plan-phase --gaps`; reserve bare `subject_kind` for canonical frontmatter ledgers such as `comparison_verdicts`
- Keep `gap_subject_kind` to `claim | deliverable | acceptance_test | reference`; use `forbidden_proxy_id` for explicit proxy-rejection gaps and `suggested_contract_checks` for missing decisive work
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
- "A benchmark comparison was required for claim `claim-main`. Do the observed numbers justify a pass, tension, fail, or inconclusive verdict?"
- "The plan forbids treating the intermediate fit quality as a success proxy. Did we accidentally rely on that instead of the decisive observable?"

### 6. Robustness and Sensitivity

Probe how sensitive results are to assumptions and approximations.

- "If we change the UV cutoff by a factor of 2, how much does the result change?"
- "The result depends on the regularization scheme. Have we checked scheme independence of physical observables?"
- "We used 5000 disorder realizations. Is the statistical error bar reliable, or do we need more?"

</check_categories>

<diagnosis_lifecycle>

**After verification complete (`session_status: completed`), if gaps exist:**

1. Researcher triggers diagnosis (from verify-work offer or manually)
2. debug workflow spawns parallel debug agents
3. Each agent investigates one gap, returns root cause
4. VERIFICATION.md Gaps section updated with diagnosis:
   - Each gap gets `root_cause`, `artifacts`, `missing`, `debug_session` filled
5. `session_status` -> "diagnosed" while final `status` stays in verification-report vocabulary (typically `gaps_found` until every gap is explicitly closed)
6. Ready for /gpd:plan-phase --gaps with root causes

**After diagnosis:**

```yaml
## Gaps

- gap_subject_kind: "claim"
  subject_id: "claim-critical-decay"
  expectation: "Correlation function decays as power law at criticality"
  expected_check: "Correlation function decays as power law at criticality"
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
  debug_session: "GPD/debug/wrong-critical-temp.md"
```

</diagnosis_lifecycle>

<lifecycle>

**Creation:** When /gpd:verify-work starts new verification session

- Extract checks from the PLAN `contract` first, then use SUMMARY.md files and verification report as evidence maps
- Use PLAN `contract` IDs as canonical check names. SUMMARY `contract_results` tells you where evidence lives, not what counts as success.
- Organize by check category (derivation logic, intuition, limits, edges, consistency, robustness)
- Include explicit forbidden-proxy rejection checks and decisive comparison checks when the contract requires them
- Add `suggested_contract_checks` if the verifier finds a missing decisive check
- Set session_status to "validating"
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

- `status` stays in canonical verification vocabulary (`passed | gaps_found | expert_needed | human_needed`)
- `session_status` -> "completed"
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
status: gaps_found
verified: 2026-03-15T14:45:00Z
score: 3/4 contract targets verified
phase: 03-phase-diagram
source:
  - "03-01-SUMMARY.md"
  - "03-02-SUMMARY.md"
  - "03-03-SUMMARY.md"
started: 2026-03-15T14:00:00Z
updated: 2026-03-15T14:45:00Z
session_status: diagnosed
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
comparison_verdicts_recorded: 0
forbidden_proxies_rejected: 0

## Gaps

- gap_subject_kind: "claim"
  subject_id: "claim-order-parameter-zero-T"
  expectation: "Order parameter reaches saturation value 1.0 at T=0"
  expected_check: "Order parameter reaches saturation value 1.0 at T=0"
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
    debug_session: "GPD/debug/mc-equilibration.md"

- gap_subject_kind: "acceptance_test"
  subject_id: "test-equilibration-convergence"
  expectation: "Results are insensitive to doubling the equilibration time"
  expected_check: "Results are insensitive to doubling the equilibration time"
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
    debug_session: "GPD/debug/mc-equilibration.md"
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

- During or after a research phase when automated verification needs human physics judgment
- When results need human physics judgment beyond automated checks
- Before publishing or building on results in later phases
- When the verification report frontmatter honestly remains `human_needed`, `expert_needed`, or `gaps_found`

**When NOT to use:**

- As a second incompatible verification format; keep using the same frontmatter contract as `verification-report.md`
- When all checks can be performed programmatically
- For implementation bugs (use standard debugging)

</guidelines>
