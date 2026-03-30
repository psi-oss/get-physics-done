---
template_version: 1
---

# Verification Report Template

Template for `GPD/phases/XX-name/{phase}-VERIFICATION.md` -- physics verification of research phase results.

---

## Verification Depth

**Quick Verification:** For simple phases (single analytical result, no numerical computation), use Quick mode: complete only sections 1 (Dimensional Analysis), 3 (Limiting Cases), and 7 (Literature Comparison). All other sections can be marked N/A with justification.

**Standard Verification:** All applicable sections for your project type (default).

`status: passed` is strict: use it only when every claim, deliverable, and acceptance_test entry in `contract_results` is `passed`, every reference entry is `completed`, every `must_surface` reference has all `required_actions` recorded in `completed_actions`, every forbidden_proxy is `rejected` or `not_applicable`, every required decisive comparison has a decisive verdict, and `suggested_contract_checks` is empty. If any contract target is `partial`, `failed`, `blocked`, `missing`, or `unresolved`, use `gaps_found`, `expert_needed`, or `human_needed` instead of `passed`.

---

## Verification Section Selection by Project Type

Not all verification sections apply to every project. Select based on physics domain:

| Section | QFT | Cond. Matter | GR/Cosmo | Stat. Mech | AMO | Nuclear |
|---------|-----|-------------|----------|-----------|-----|---------|
| Dimensional analysis | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Limiting cases | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Symmetry checks | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Conservation laws | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Numerical convergence | If numerical | ✓ | If numerical | ✓ | If numerical | ✓ |
| Literature comparison | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Ward identities/sum rules | ✓ | Sometimes | — | — | — | ✓ |
| Kramers-Kronig | If response fn | ✓ | — | If response fn | ✓ | — |
| Unitarity/causality | ✓ | — | ✓ | — | ✓ | ✓ |
| Physical plausibility | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Statistical validation | If MC | If MC/MD | If MCMC | ✓ | If MC | If MC |
| Thermodynamic consistency | — | ✓ | — | ✓ | — | ✓ |
| Spectral/analytic structure | ✓ | ✓ | — | — | ✓ | ✓ |
| Anomalies/topology | ✓ | Sometimes | Sometimes | — | — | — |

**Omit sections marked "—" for your project type.** Include "Sometimes" sections only if relevant to your specific calculation.

---

## File Template

Use `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` as the schema source of truth for `plan_contract_ref`, `contract_results`, `comparison_verdicts`, and verification-side `suggested_contract_checks`.
If the project has an active convention lock, include a machine-readable `ASSERT_CONVENTION` comment immediately after the YAML frontmatter using canonical lock keys and exact lock values.
For phase verification artifacts, changed files now fail `gpd pre-commit-check` when this required header is missing or mismatched against the active lock.
For exploratory or partial phases, keep the report honest without inventing certainty: leave affected contract targets at `partial` when decisive work remains open, and use explicit `comparison_verdicts` entries such as `inconclusive` or `tension` when a decisive comparison was attempted but not resolved.
If a decisive benchmark / cross-method check remains `partial`, `not_attempted`, or still lacks its decisive verdict, add structured `suggested_contract_checks` entries before final validation.
The same structured suggestion is required when a benchmark-style reference anchors the subject or a reference with `required_actions` including `compare` is still incomplete.
Those `suggested_contract_checks` entries belong to the same canonical schema surface as the rest of the verification ledger, not freeform prose.
Every declared claim, deliverable, acceptance test, reference, and forbidden proxy ID from the source PLAN contract must appear in the matching `contract_results` section. Use explicit negative or incomplete statuses instead of omitting IDs.
Keep `uncertainty_markers` explicit in the `contract_results` ledger, and use non-empty placeholder anchors in `weakest_anchors` and `disconfirming_observations` so unresolved uncertainty is visible before final validation.
Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing the YAML and apply it literally rather than paraphrasing from memory.
`plan_contract_ref` must be a project-local PLAN path, not absolute or parent-traversing, and must end with the exact `#/contract` fragment. For reference-backed decisive comparisons, `comparison_kind: benchmark|prior_work|experiment|baseline|cross_method` can satisfy the requirement; `comparison_kind: other` cannot.
Even singleton values must stay YAML lists in strict contract-backed ledgers: use `linked_ids: [claim-id]`, `completed_actions: [read]`, and `weakest_anchors: [anchor-1]`, never scalar strings.

```markdown
---
phase: XX-name
verified: YYYY-MM-DDTHH:MM:SSZ
status: passed | gaps_found | expert_needed | human_needed
score: N/M contract targets verified
plan_contract_ref: GPD/phases/XX-name/{phase}-{plan}-PLAN.md#/contract
# Use `contract_results` only for user-visible contract targets. Do not encode internal tool/process milestones here.
contract_results:
  # Every ID declared in the PLAN contract must appear in its matching section below.
  claims:
    claim-id:
      status: passed|partial|failed|blocked|not_attempted
      summary: "[verification verdict for this claim]"
      linked_ids: [deliverable-id, acceptance-test-id, reference-id]
      evidence:
        - verifier: gpd-verifier
          method: benchmark reproduction
          confidence: high
          claim_id: claim-id
          deliverable_id: deliverable-id
          acceptance_test_id: acceptance-test-id
          reference_id: reference-id
          forbidden_proxy_id: forbidden-proxy-id
          evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md
  deliverables:
    deliverable-id:
      status: passed|partial|failed|blocked|not_attempted
      path: path/to/artifact
      summary: "[artifact verification verdict]"
      linked_ids: [claim-id, acceptance-test-id]
  acceptance_tests:
    acceptance-test-id:
      status: passed|partial|failed|blocked|not_attempted
      summary: "[test verification verdict]"
      linked_ids: [claim-id, deliverable-id, reference-id]
  references:
    reference-id:
      status: completed|missing|not_applicable
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "[how the anchor was checked]"
  forbidden_proxies:
    forbidden-proxy-id:
      status: rejected|violated|unresolved|not_applicable
      notes: "[proxy status]"
  uncertainty_markers:
    weakest_anchors: [anchor-1]
    unvalidated_assumptions: [assumption-1]
    competing_explanations: [alternative-1]
    disconfirming_observations: [observation-1]
# Required whenever a decisive comparison was required or attempted for a user-visible target.
# If the comparison was started but not resolved, record `verdict: inconclusive` or `verdict: tension`
# instead of omitting the entry or upgrading the parent target to `passed`.
comparison_verdicts:
  - subject_id: claim-id
    subject_kind: claim|deliverable|acceptance_test|reference
    subject_role: decisive|supporting|supplemental|other
    reference_id: reference-id
    comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass|tension|fail|inconclusive
    recommended_action: "[what to do next]"
    notes: "[optional context]"
# Required when the verifier can name a missing decisive check on a user-visible target.
# Also required when a decisive benchmark / cross-method check remains partial, not attempted,
# or still lacks the decisive comparison verdict that would let the target pass honestly.
# Keep these entries structured; do not replace them with freeform prose or invented keys.
# If you can bind the gap to a known contract target, include `suggested_subject_kind`
# and `suggested_subject_id` together. Otherwise omit both keys instead of leaving one blank.
suggested_contract_checks:
  - check: "Add decisive normalization benchmark comparison"
    reason: "The reported agreement depends on a normalization-sensitive benchmark that is not yet explicit."
    suggested_subject_kind: acceptance_test
    suggested_subject_id: acceptance-test-id
    evidence_path: GPD/phases/01-benchmark/benchmark-comparison.csv
---

<!-- ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-minus, fourier_convention=physics -->

# Phase {X}: {Name} Verification Report

**Phase Goal:** {goal from ROADMAP.md}
**Verified:** {timestamp}
**Status:** {passed | gaps_found | expert_needed | human_needed}

## Contract Targets

| ID | Kind | Status | Decisive? | Evidence Path | Notes |
| -- | ---- | ------ | --------- | ------------- | ----- |
| {claim-id} | claim | {passed/failed} | {yes/no} | {path} | {why} |
| {deliverable-id} | deliverable | {passed/failed} | {yes/no} | {path} | {why} |
| {acceptance-test-id} | acceptance test | {passed/failed} | {yes/no} | {path} | {why} |
| {reference-id} | reference anchor | {completed/missing} | {yes/no} | {path} | {why} |

Use contract IDs consistently throughout the report. The PLAN contract defines what must be verified. `SUMMARY.md` `contract_results` and `comparison_verdicts` tell you what evidence was produced, not what success means.
Record only user-visible contract targets here: things a researcher could point to in the promised outcome or artifact set. Internal workflow steps, tool invocations, and generic "validation happened" statements do not belong in this table.

If the verifier identifies a decisive check that the contract omitted, record it under `suggested_contract_checks` instead of silently treating the missing check as acceptable.
When a decisive comparison was attempted but remains unresolved, keep the affected target at `partial` and emit a `comparison_verdict` with `inconclusive` or `tension`; do not convert promising trends or proxy evidence into a pass.

## Forbidden Proxy Audit

| Forbidden Proxy ID | What Was Forbidden | Status | Evidence Path | Notes |
| ------------------ | ------------------ | ------ | ------------- | ----- |
| {forbidden-proxy-id} | {proxy description} | {rejected/violated/unresolved} | {path} | {why this matters} |
| {forbidden-proxy-id} | {proxy description} | {status} | {path} | {notes} |

**Rule:** A forbidden proxy must be explicitly rejected or escalated. Silence is not sufficient evidence that the phase stayed on target.

## Comparison Verdict Ledger

| Subject ID | Subject Kind | Subject Role | Comparison Kind | Anchor / Source | Metric | Threshold | Verdict | Notes |
| ---------- | ------------ | ------------ | --------------- | --------------- | ------ | --------- | ------- | ----- |
| {claim-id} | claim | decisive | benchmark | {reference-id or prior artifact} | {relative_error} | {<= 0.01} | {pass/tension/fail/inconclusive} | {why} |
| {deliverable-id} | deliverable | supporting | cross_method | {reference-id or artifact path} | {difference} | {threshold} | {verdict} | {notes} |

Emit comparison verdicts whenever the contract or decisive anchor context requires a benchmark, prior-work, experiment, baseline, or cross-method comparison. If a comparison is decisive, absence of a verdict is itself a gap; a prose claim like "agrees with literature" is not a substitute. For partial or exploratory phases, `inconclusive` and `tension` are valid honest outcomes when the check was started but not closed.
Only `subject_role: decisive` closes a decisive benchmark/cross-method requirement or contradicts a passed contract target. `supporting` and `supplemental` verdicts are recorded context, not decisive blockers on their own.
- Benchmark acceptance tests require `comparison_kind: benchmark`; cross-method acceptance tests require `comparison_kind: cross_method`.

## Suggested Contract Checks

Reserve this section for obvious missing decisive checks on user-visible targets. Do not populate it with style requests, paperwork wishes, or generic process polish. Each row should name one missing check, why it matters, which user-visible target it affects, and the artifact or evidence path that would close it.
Allowed keys are exactly `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id`, and `evidence_path`.
If the missing check is already tied to a known contract target, fill `Suggested Subject Kind` and `Suggested Subject ID` together; otherwise omit both keys in frontmatter instead of leaving one blank.
Include a `suggested_contract_checks` entry whenever a decisive benchmark / cross-method comparison is still partial or unresolved, and also whenever a benchmark-style reference or a reference with `required_actions` containing `compare` is still incomplete.

| Suggested Check | Why It Seems Required | Suggested Subject Kind | Suggested Subject ID | Evidence Path |
| --------------- | --------------------- | ---------------------- | -------------------- | ------------- |
| {missing check} | {why the verifier thinks it is decisive} | {claim|deliverable|acceptance_test|reference} | {matching contract id} | {where evidence would come from} |
| {missing check} | {reason} | {kind} | {id} | {path} |

## Dimensional Analysis

| Expression        | Expected Dimensions | Actual Dimensions   | Status      | Details               |
| ----------------- | ------------------- | ------------------- | ----------- | --------------------- |
| {expression name} | {[M^a L^b T^c ...]} | {[M^a L^b T^c ...]} | PASS / FAIL | {notes on any issues} |
| {expression name} | {[M^a L^b T^c ...]} | {[M^a L^b T^c ...]} | PASS / FAIL | {notes}               |

**Dimensional analysis:** {N}/{M} expressions verified

### Notes

- {Any expressions where natural units obscure dimensional analysis}
- {Convention: hbar = c = k_B = 1 used in sections X, Y}
- {Dimensions restored for final physical results: yes/no}

## Limiting Cases

| Limit                | Expected Behavior                      | Obtained Behavior | Status                | Source                            |
| -------------------- | -------------------------------------- | ----------------- | --------------------- | --------------------------------- |
| {parameter -> value} | {known result or physical expectation} | {what we get}     | PASS / FAIL / PARTIAL | {reference for expected behavior} |
| {parameter -> value} | {known result}                         | {what we get}     | PASS / FAIL / PARTIAL | {reference}                       |
| {parameter -> value} | {known result}                         | {what we get}     | PASS / FAIL / PARTIAL | {reference}                       |

**Limiting cases:** {N}/{M} verified

### Detailed Limit Analysis

{For any FAIL or PARTIAL:}

**{Limit name}:**

- Expected: {expression or value}
- Obtained: {expression or value}
- Discrepancy: {quantify the difference}
- Likely cause: {sign error, missing factor, wrong branch, etc.}
- Impact: {how this affects the main result}

## Symmetry Checks

| Symmetry        | What It Implies                                                               | Test Performed     | Status      | Details    |
| --------------- | ----------------------------------------------------------------------------- | ------------------ | ----------- | ---------- |
| {symmetry name} | {physical consequence - e.g., "H commutes with P implies parity eigenstates"} | {what was checked} | PASS / FAIL | {evidence} |
| {symmetry name} | {consequence}                                                                 | {test}             | PASS / FAIL | {evidence} |
| {symmetry name} | {consequence}                                                                 | {test}             | PASS / FAIL | {evidence} |

**Symmetry checks:** {N}/{M} passed

### Symmetry Details

- {E.g., "Time-reversal: verified K(t) = K(-t)\* for all computed t values"}
- {E.g., "Particle-hole: spectrum symmetric about E=0, verified for N=16,24,32"}

## Conservation Laws

| Conserved Quantity | Conservation Test                            | Violation Magnitude          | Status      | Details   |
| ------------------ | -------------------------------------------- | ---------------------------- | ----------- | --------- |
| {quantity}         | {how tested - e.g., "dE/dt over trajectory"} | {numerical value or "exact"} | PASS / FAIL | {details} |
| {quantity}         | {test}                                       | {violation}                  | PASS / FAIL | {details} |

**Conservation laws:** {N}/{M} verified

### Acceptable Violation Thresholds

- Energy conservation: |Delta E / E| < {threshold} (set by integrator tolerance)
- Probability conservation: |1 - Tr(rho)| < {threshold}
- {Other relevant thresholds with justification}

## Numerical Convergence

| Quantity   | Parameter Varied                        | Values Tested            | Convergence Behavior                          | Converged Value                      | Status                               |
| ---------- | --------------------------------------- | ------------------------ | --------------------------------------------- | ------------------------------------ | ------------------------------------ |
| {quantity} | {e.g., grid size, dt, basis truncation} | {e.g., 32, 64, 128, 256} | {e.g., "power-law convergence, exponent ~ 2"} | {extrapolated value +/- uncertainty} | CONVERGED / NOT CONVERGED / MARGINAL |
| {quantity} | {parameter}                             | {values}                 | {behavior}                                    | {value}                              | {status}                             |

**Convergence:** {N}/{M} quantities converged

### Convergence Details

{For each non-trivial convergence study:}

**{Quantity name}:**

- Parameter: {what was varied}
- Values tested: {list}
- Results: {values at each parameter setting}
- Extrapolated value: {Richardson extrapolation or similar}
- Estimated error: {from convergence rate}
- Convergence order: {observed order vs expected order}

## Comparison with Known Results

| Our Result              | Published Value         | Source           | Agreement                            | Discrepancy                |
| ----------------------- | ----------------------- | ---------------- | ------------------------------------ | -------------------------- |
| {value +/- uncertainty} | {value +/- uncertainty} | {paper/textbook} | {within N sigma / exact / disagrees} | {quantify if disagreement} |
| {value +/- uncertainty} | {value +/- uncertainty} | {source}         | {agreement level}                    | {discrepancy}              |

**Literature comparison:** {N}/{M} results agree with published values

### Discrepancy Analysis

{For any disagreements:}

**{Result name}:**

- Our value: {value}
- Published value: {value} (from {source})
- Discrepancy: {quantify}
- Possible explanations:
  1. {Different convention / normalization}
  2. {Different parameter regime}
  3. {Genuine error in our work or theirs}
- Resolution: {what to do - recheck, contact authors, note in paper}

## Ward Identities and Sum Rules

| Identity / Sum Rule                    | Expected Value      | Computed Value    | Deviation        | Status      | Source       |
| -------------------------------------- | ------------------- | ----------------- | ---------------- | ----------- | ------------ |
| {e.g., "f-sum rule: ∫ω Im[ε] dω"}      | {π ω_p²/2}          | {numerical value} | {relative error} | PASS / FAIL | {reference}  |
| {e.g., "Ward identity: q_μ Γ^μ"}       | {S⁻¹(p+q) - S⁻¹(p)} | {numerical value} | {max deviation}  | PASS / FAIL | {derivation} |
| {e.g., "spectral weight: ∫ A(k,ω) dω"} | {2π}                | {numerical value} | {relative error} | PASS / FAIL | {sum rule}   |

**Ward identities / sum rules:** {N}/{M} verified

### Details

- {Which sum rules are applicable to this problem and why}
- {Any sum rules that cannot be checked and reason}
- {If a sum rule fails: is it due to truncation, finite frequency range, or a real error?}

## Kramers-Kronig Consistency

| Response Function | KK Transform of Im Part | Direct Re Part | Max Relative Error | Status      |
| ----------------- | ----------------------- | -------------- | ------------------ | ----------- |
| {e.g., "ε(ω)"}    | {KK[Im ε]}              | {Re ε}         | {error}            | PASS / FAIL |
| {e.g., "σ(ω)"}    | {KK[Im σ]}              | {Re σ}         | {error}            | PASS / FAIL |

**KK consistency:** {N}/{M} response functions verified

### Details

- {Frequency range used for KK integration}
- {High-frequency extrapolation method}
- {Any issues with numerical integration near singularities}

## Unitarity and Causality

| Check                                 | Method                | Result          | Tolerance   | Status      |
| ------------------------------------- | --------------------- | --------------- | ----------- | ----------- |
| {e.g., "S-matrix unitarity: S†S = I"} | {`max \|S†S - I\|`}   | {value}         | {tolerance} | PASS / FAIL |
| {e.g., "optical theorem"}             | {Im f(0) vs k σ/(4π)} | {relative diff} | {tolerance} | PASS / FAIL |
| {e.g., "retarded causality"}          | {`max \|G^R(t<0)\|`}  | {value}         | {tolerance} | PASS / FAIL |
| {e.g., "spectral positivity"}         | {min A(k,ω)}          | {value}         | {tolerance} | PASS / FAIL |
| {e.g., "partial wave bounds"}         | {`max \|S_l\|`}       | {value}         | {≤ 1}       | PASS / FAIL |

**Unitarity/Causality:** {N}/{M} checks passed

## Physical Plausibility

| Check        | Criterion                                      | Result               | Status      | Notes   |
| ------------ | ---------------------------------------------- | -------------------- | ----------- | ------- |
| Positivity   | {e.g., "partition function > 0"}               | {value}              | PASS / FAIL | {notes} |
| Monotonicity | {e.g., "entropy increases with temperature"}   | {behavior observed}  | PASS / FAIL | {notes} |
| Boundedness  | {e.g., "correlation function `\|C(r)\|` <= 1"} | {max value observed} | PASS / FAIL | {notes} |
| Causality    | {e.g., "response function = 0 for t < 0"}      | {behavior}           | PASS / FAIL | {notes} |
| Unitarity    | {e.g., "S-matrix eigenvalues on unit circle"}  | {max deviation}      | PASS / FAIL | {notes} |
| Stability    | {e.g., "free energy is convex"}                | {behavior}           | PASS / FAIL | {notes} |
| Analyticity  | {e.g., "no unphysical poles in propagator"}    | {structure}          | PASS / FAIL | {notes} |

**Plausibility:** {N}/{M} checks passed

## Statistical Validation

| Test                           | Method                      | Result                      | Interpretation                    | Status      |
| ------------------------------ | --------------------------- | --------------------------- | --------------------------------- | ----------- |
| {e.g., "autocorrelation time"} | {binning analysis}          | {τ_int = value}             | {N_eff = value effective samples} | PASS / WARN |
| {e.g., "thermalization"}       | {first-half vs second-half} | {drift = Nσ}                | {< 2σ = thermalized}              | PASS / FAIL |
| {e.g., "goodness of fit"}      | {chi-squared}               | {χ²/dof = value, p = value} | {acceptable fit}                  | PASS / FAIL |
| {e.g., "error estimation"}     | {bootstrap, N=10000}        | {σ_bootstrap = value}       | {consistent with jackknife}       | PASS / WARN |
| {e.g., "finite-size scaling"}  | {L = 16,32,64,128}          | {exponent = value}          | {matches universality class}      | PASS / FAIL |

**Statistical validation:** {N}/{M} tests passed

### Error Budget

| Source                   | Type        | Magnitude | Dominant? |
| ------------------------ | ----------- | --------- | --------- |
| {e.g., "MC sampling"}    | Statistical | {value}   | {Yes/No}  |
| {e.g., "finite-size"}    | Systematic  | {value}   | {Yes/No}  |
| {e.g., "truncation"}     | Systematic  | {value}   | {Yes/No}  |
| {e.g., "discretization"} | Systematic  | {value}   | {Yes/No}  |
| **Total**                | Combined    | {value}   | —         |

## Uncertainty Audit

### Checklist

- [ ] All numerical results have stated uncertainties
- [ ] Error propagation verified for derived quantities
- [ ] Statistical and systematic errors separated where applicable
- [ ] Uncertainties from upstream phases correctly propagated
- [ ] Dominant uncertainty source identified for each key result

### Uncertainty Budget

| Result                | Statistical  | Systematic   | Truncation   | Total        | Dominant Source            |
| --------------------- | ------------ | ------------ | ------------ | ------------ | -------------------------- |
| {e.g., T_c = 0.893}   | {+/- 0.001}  | {+/- 0.004}  | {+/- 0.001}  | {+/- 0.005}  | {systematic: finite-size}  |
| {e.g., E_0 = -0.4327} | {+/- 0.0002} | {+/- 0.0001} | {+/- 0.0001} | {+/- 0.0003} | {statistical: MC sampling} |

### Propagation Verification

[For each derived quantity that depends on upstream results, verify that uncertainties were propagated correctly.]

| Derived Quantity   | Depends On | Propagation Method         | Input Uncertainty                       | Output Uncertainty   | Verified |
| ------------------ | ---------- | -------------------------- | --------------------------------------- | -------------------- | -------- |
| {e.g., kappa(T_c)} | {T_c, E_0} | {linear error propagation} | {delta_T_c = 0.005, delta_E_0 = 0.0003} | {delta_kappa = 0.02} | {Yes/No} |

## Contract Claim Coverage

| Claim ID | Claim Summary | Status | Evidence | Notes |
| -------- | ------------- | ------ | -------- | ----- |
| {claim-id} | {contract-backed claim} | VERIFIED / PARTIAL / FAILED / UNCERTAIN | {what confirmed it} | {why} |
| {claim-id} | {contract-backed claim} | VERIFIED / PARTIAL / FAILED / UNCERTAIN | {what's wrong or why uncertain} | {notes} |

**Score:** {N}/{M} contract claims verified

## Required Artifacts

| Artifact    | Expected                 | Status                                | Details    |
| ----------- | ------------------------ | ------------------------------------- | ---------- |
| {file path} | {what it should contain} | EXISTS + SUBSTANTIVE / STUB / MISSING | {evidence} |
| {file path} | {what it should contain} | EXISTS + SUBSTANTIVE / STUB / MISSING | {evidence} |

**Artifacts:** {N}/{M} verified

## Key Link Verification

| From             | To                  | Via                      | Status            | Details                             |
| ---------------- | ------------------- | ------------------------ | ----------------- | ----------------------------------- |
| {derivation.tex} | {implementation.py} | {formula implementation} | WIRED / NOT WIRED | {line reference showing connection} |
| {computation.py} | {results.json}      | {output generation}      | WIRED / NOT WIRED | {details}                           |

**Wiring:** {N}/{M} connections verified

## Overall Confidence Assessment

### Per-Section Scores

| Section                     | Score | Weight            | Weighted Score |
| --------------------------- | ----- | ----------------- | -------------- |
| Dimensional analysis        | {N/M} | {HIGH/MEDIUM/LOW} | {assessment}   |
| Limiting cases              | {N/M} | {HIGH}            | {assessment}   |
| Symmetry checks             | {N/M} | {MEDIUM}          | {assessment}   |
| Conservation laws           | {N/M} | {HIGH}            | {assessment}   |
| Ward identities / sum rules | {N/M} | {HIGH}            | {assessment}   |
| Kramers-Kronig consistency  | {N/M} | {MEDIUM}          | {assessment}   |
| Unitarity / causality       | {N/M} | {HIGH}            | {assessment}   |
| Numerical convergence       | {N/M} | {HIGH}            | {assessment}   |
| Statistical validation      | {N/M} | {MEDIUM}          | {assessment}   |
| Literature comparison       | {N/M} | {HIGH}            | {assessment}   |
| Physical plausibility       | {N/M} | {MEDIUM}          | {assessment}   |

### Overall Confidence: {HIGH / MEDIUM / LOW / INSUFFICIENT}

**Rationale:** {2-3 sentences explaining the overall confidence level}

**Strongest evidence:** {What gives us most confidence}
**Weakest link:** {What we're least confident about and why}
**Recommended actions:** {What would increase confidence}

## Gaps Summary

{If no gaps:}
**No gaps found.** All physics verification checks passed. Results are reliable within stated assumptions.

{If gaps found:}

### Critical Gaps (Block Progress)

1. **{Gap name}**
   - Failing check: {which verification section}
   - Impact: {why this blocks the research goal}
   - Fix: {what needs to happen}
   - Estimated effort: {Small / Medium / Large}

### Non-Critical Gaps (Can Note and Proceed)

1. **{Gap name}**
   - Issue: {what's wrong}
   - Impact: {limited impact because...}
   - Recommendation: {fix now, note in paper, or defer}

## Recommended Fix Plans

{If gaps found, generate fix plan recommendations:}

### {phase}-{next}-PLAN.md: {Fix Name}

**Objective:** {What this fixes}

**Tasks:**

1. {Task to fix gap 1}
2. {Task to fix gap 2}
3. {Re-verification task}

**Estimated scope:** {Small / Medium}

## Related Debug Sessions

| Debug File                                                                | Status                    | Root Cause                           | Lesson                              |
| ------------------------------------------------------------------------- | ------------------------- | ------------------------------------ | ----------------------------------- |
| {GPD/debug/[slug].md where frontmatter `phase:` matches this phase} | {status from frontmatter} | {Resolution.root_cause or "pending"} | {Resolution.lessons_learned or "—"} |

{If no debug files match this phase: "No debug sessions recorded for this phase."}

---

## Verification Metadata

**Verification approach:** Goal-backward + contract-first + physics-first (dimensional analysis, limits, symmetries, decisive comparisons, forbidden-proxy rejection)
**Verification target source:** {PLAN `contract` | derived contract-like target set from ROADMAP.md goal}
**Dimensional checks:** {N} performed
**Limiting cases checked:** {N} checked, {M} passed
**Symmetry checks:** {N} performed
**Conservation law checks:** {N} performed
**Ward identities / sum rules:** {N} checked, {M} satisfied
**Kramers-Kronig checks:** {N} response functions tested
**Unitarity / causality checks:** {N} performed
**Statistical validation tests:** {N} performed
**Convergence studies:** {N} quantities studied
**Literature comparisons:** {N} values compared
**Comparison verdicts:** {N} recorded
**Forbidden proxy audits:** {N} performed
**Suggested contract checks:** {N} recorded
**Total verification time:** {duration}

---

_Verified: {timestamp}_
_Verifier: {agent name or "AI assistant (subagent)"}_
```

---

## Guidelines

**Status values:**

- `passed` -- All physics checks pass, results are reliable
- `gaps_found` -- One or more critical verification failures
- `expert_needed` -- Domain expert review required for specialized physics judgment
- `human_needed` -- Automated checks pass but human physics judgment required

**Verification priority (ordered by diagnostic power):**

1. **Dimensional analysis** -- catches the most errors with least effort
2. **Limiting cases** -- if known limits fail, something is fundamentally wrong
3. **Conservation laws** -- violations indicate implementation or derivation errors
4. **Ward identities / sum rules** -- exact constraints that must hold non-perturbatively
5. **Symmetry checks** -- broken symmetries reveal sign errors or missing terms
6. **Unitarity / causality** -- fundamental quantum mechanical and relativistic constraints
7. **Kramers-Kronig** -- causality-based consistency check for response functions
8. **Numerical convergence** -- ensures results are not artifacts of discretization
9. **Statistical validation** -- ensures error bars are honest and conclusions warranted
10. **Literature comparison** -- validates against independent calculations
11. **Physical plausibility** -- catches results that are "technically correct but unphysical"

**Evidence types:**

- For PASS: "Dimensions match: [E] = [M L^2 T^{-2}]" or "Limit yields known result: E_0 = -1.0 (exact: -1.0)"
- For FAIL: "Dimensions mismatch: got [M L T^{-2}], expected [M L^2 T^{-2}]" or "Limit gives E_0 = +1.0 but exact is -1.0"
- For UNCERTAIN: "Cannot check without experimental data" or "Convergence unclear - need larger system sizes"

**Confidence levels:**

- HIGH: All dimensional, limiting case, and conservation checks pass; literature agreement within uncertainties
- MEDIUM: Minor issues in some checks but core results are solid; some convergence questions remain
- LOW: Significant failures in limiting cases or conservation laws; results should not be trusted
- INSUFFICIENT: Multiple critical failures; results are unreliable and must be rederived/recomputed

**Fix plan generation:**

- Only generate if gaps_found
- Group related fixes into single plans
- Keep to 2-3 tasks per plan
- Include re-verification task in each plan
- Prioritize fixes by diagnostic power: fix dimensional issues before convergence issues

---

## Example

```markdown
---
phase: 02-syk-sff
verified: 2026-03-15T16:00:00Z
status: gaps_found
score: 8/11 contract targets verified
---

# Phase 2: SYK Spectral Form Factor Verification Report

**Phase Goal:** Compute disorder-averaged SFF for N=24,28,32 Majorana SYK and verify dip-ramp-plateau structure
**Verified:** 2026-03-15T16:00:00Z
**Status:** gaps_found

## Dimensional Analysis

| Expression            | Expected Dimensions | Actual Dimensions | Status | Details                               |
| --------------------- | ------------------- | ----------------- | ------ | ------------------------------------- |
| K(t, beta)            | [dimensionless]     | [dimensionless]   | PASS   | SFF is `\|Z(beta+it)\|`^2 / Z(beta)^2 |
| Z(beta)               | [dimensionless]     | [dimensionless]   | PASS   | Tr(exp(-beta H)), H in units of J     |
| t_H (Heisenberg time) | [1/J]               | [1/J]             | PASS   | 2 pi L / bandwidth, bandwidth ~ J     |

**Dimensional analysis:** 3/3 expressions verified

## Limiting Cases

| Limit         | Expected Behavior           | Obtained Behavior               | Status | Source                                       |
| ------------- | --------------------------- | ------------------------------- | ------ | -------------------------------------------- |
| t -> 0        | K(0) = 1 (by normalization) | K(0) = 1.0000                   | PASS   | Definition                                   |
| t -> infinity | K -> 1/L (connected)        | K -> 0.0039 (N=32, L=2^16)      | FAIL   | RMT prediction: 1/65536 = 1.53e-5; see below |
| beta -> 0     | Ramp slope = 1/(2 pi)       | Slope = 0.159 +/- 0.002         | PASS   | 1/(2pi) = 0.1592                             |
| N -> infinity | Sharper dip-ramp transition | Observed in N=24,28,32 sequence | PASS   | Expected from RMT                            |

**Limiting cases:** 3/4 verified

### Detailed Limit Analysis

**t -> infinity plateau value:**

- Expected: K_connected -> 1/L = 1/2^{N/2} for the connected SFF
- Obtained: K = 0.0039 for N=32 but L = 2^{16} = 65536, so 1/L = 1.5e-5
- Discrepancy: Off by factor of ~256 = 2^8
- Likely cause: Computing |Z|^2 instead of |Z|^2 / Z(0)^2, or using wrong L
- Impact: Plateau height wrong means normalization error propagates to ramp slope interpretation

## Symmetry Checks

| Symmetry                        | What It Implies                   | Test Performed                    | Status | Details                                  |
| ------------------------------- | --------------------------------- | --------------------------------- | ------ | ---------------------------------------- |
| Time-reversal of SFF            | K(t) = K(-t)                      | Computed K for t and -t           | PASS   | Max deviation: 1e-14 (machine precision) |
| Disorder average self-averaging | Variance decreases with N_samples | Checked at 100, 500, 1000 samples | PASS   | Variance ~ 1/N_samples as expected       |

**Symmetry checks:** 2/2 passed

## Conservation Laws

| Conserved Quantity       | Conservation Test                | Violation Magnitude                 | Status | Details                             |
| ------------------------ | -------------------------------- | ----------------------------------- | ------ | ----------------------------------- |
| Probability (Tr rho = 1) | Checked normalization of Z(beta) | `\|1 - Tr(e^{-beta H})/Z\|` < 1e-13 | PASS   | Exact diag preserves unitarity      |
| Particle-hole symmetry   | Spectrum symmetric about E=0     | Max asymmetry: 1e-12                | PASS   | q=4 SYK with even N has PH symmetry |

**Conservation laws:** 2/2 verified

## Numerical Convergence

| Quantity   | Parameter Varied | Values Tested        | Convergence Behavior          | Converged Value        | Status    |
| ---------- | ---------------- | -------------------- | ----------------------------- | ---------------------- | --------- |
| SFF at t=1 | Disorder samples | 100, 500, 1000, 5000 | 1/sqrt(N_samples) convergence | K(1) = 0.342 +/- 0.003 | CONVERGED |
| Ramp slope | N                | 24, 28, 32           | Approaching RMT prediction    | 0.159 +/- 0.002        | CONVERGED |

**Convergence:** 2/2 quantities converged

## Comparison with Known Results

| Our Result          | Published Value    | Source               | Agreement             | Discrepancy                                   |
| ------------------- | ------------------ | -------------------- | --------------------- | --------------------------------------------- |
| Ramp slope (beta=0) | 1/(2pi) = 0.1592   | Cotler et al. 2017   | Within 1 sigma        | None                                          |
| Dip time (N=32)     | t_dip ~ 0.5 J^{-1} | Cotler et al. Fig. 3 | Qualitative agreement | Our t_dip ~ 0.6, within expected N-dependence |

**Literature comparison:** 2/2 results agree

## Physical Plausibility

| Check                | Criterion                | Result                              | Status | Notes                                     |
| -------------------- | ------------------------ | ----------------------------------- | ------ | ----------------------------------------- |
| Positivity           | K(t) >= 0                | Min K = 2.3e-4                      | PASS   | SFF is `\|Z\|`^2, inherently non-negative |
| Monotonicity of ramp | dK/dt > 0 in ramp region | Verified for t in [0.5, 10]         | PASS   | Clean linear ramp                         |
| Plateau saturation   | K constant for t > t_H   | Plateau reached at t ~ 100 for N=24 | PASS   | Clean plateau                             |

**Plausibility:** 3/3 checks passed

## Overall Confidence Assessment

### Overall Confidence: MEDIUM

**Rationale:** Core physics (ramp slope, dip-ramp-plateau structure) is verified and agrees with literature. However, the plateau height discrepancy for N=32 indicates a normalization issue that must be resolved before publishing results.

**Strongest evidence:** Ramp slope matches RMT prediction to within statistical uncertainty.
**Weakest link:** Plateau normalization for N=32 is off by a factor of 2^8.
**Recommended actions:** Debug the normalization in the plateau calculation; likely a Hilbert space dimension counting issue (full vs symmetry-reduced sector).

## Gaps Summary

### Critical Gaps (Block Progress)

1. **Plateau height normalization error (N=32)**
   - Failing check: Limiting case t -> infinity
   - Impact: Incorrect normalization means all absolute SFF values may be wrong; ramp slope agreement may be coincidental if normalization cancels
   - Fix: Check whether code uses full Hilbert space dim 2^N vs physical sector dim 2^{N/2}; verify for N=24 where both are tractable
   - Estimated effort: Small

## Recommended Fix Plans

### 02-04-PLAN.md: Fix SFF Normalization

**Objective:** Resolve plateau height discrepancy by correcting Hilbert space dimension in normalization

**Tasks:**

1. Audit normalization: trace through code path from Z(beta) computation to K(t) normalization, identify where L = 2^N vs 2^{N/2} is used
2. Fix and re-run: correct the dimension, recompute SFF for N=24,28,32
3. Re-verify: check all limiting cases with corrected normalization

**Estimated scope:** Small

---

## Verification Metadata

**Verification approach:** Physics-first (dimensional analysis, limits, symmetries, conservation) + goal-backward
**Contract source:** 02-01-PLAN.md frontmatter
**Dimensional checks:** 3 performed, 3 passed
**Limiting cases checked:** 4 checked, 3 passed
**Symmetry checks:** 2 performed, 2 passed
**Conservation law checks:** 2 performed, 2 passed
**Convergence studies:** 2 quantities studied, 2 converged
**Literature comparisons:** 2 values compared, 2 agree
**Total verification time:** 15 min

---

_Verified: 2026-03-15T16:00:00Z_
_Verifier: AI assistant (subagent)_
```
