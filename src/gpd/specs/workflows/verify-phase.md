<purpose>
Verify research phase goal achievement through computational verification. Check that the research delivers what the phase promised by actually testing the physics — substituting values, re-deriving limits, parsing dimensions, and cross-checking by independent methods.

Executed by a verification subagent spawned from execute-phase.md.

Can also be invoked directly via `/gpd:verify-work` for re-verification after manual fixes. When invoked standalone, the workflow runs identically but returns results to the user instead of to the execute-phase orchestrator.
</purpose>

<core_principle>
**Task completion != Goal achievement**

A task "derive dispersion relation" can be marked complete when the derivation has placeholder steps. The task was done -- but the goal "verified dispersion relation with correct limiting behavior" was not achieved.

Goal-backward verification:

1. What contract-backed outcomes must be TRUE for the research goal to be achieved?
2. What must EXIST for those outcomes to hold (derivations, calculations, plots, baselines, benchmark evidence)?
3. What must be VALIDATED for those artifacts to be trustworthy?
4. What must be explicitly REJECTED because it would be a forbidden proxy for real progress?

Then verify each level against the actual research artifacts — **by doing physics, not by pattern-matching**.

**Fundamental rule: every verification check must involve COMPUTATION, not just text search.**

| Verification theater (NEVER DO)               | Real verification (ALWAYS DO)                                |
| --------------------------------------------- | ------------------------------------------------------------ |
| Use `search_files` for "limit" to see if limits are mentioned   | Take the limit yourself and compare with known result        |
| Use `search_files` for "dimensions" to see if they are discussed | Assign dimensions to each symbol and verify term consistency |
| Use `search_files` for "convergence" to see if the word appears | Run at 2+ resolutions and measure convergence rate           |
| Count scipy imports as proof of computation   | Run the code with known inputs and verify output             |
| Check if reference is cited                   | Extract the benchmark value and compare numerically          |

</core_principle>

<required_reading>
@{GPD_INSTALL_DIR}/references/verification/core/verification-core.md
@{GPD_INSTALL_DIR}/references/verification/core/verification-numerical.md
@{GPD_INSTALL_DIR}/references/protocols/error-propagation-protocol.md
@{GPD_INSTALL_DIR}/templates/verification-report.md
</required_reading>

<process>

<step name="load_context" priority="first">
Load phase operation context:

```bash
INIT=$(gpd init phase-op "${PHASE_ARG}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `has_plans`, `plan_count`.

**If `phase_found` is false:**

```
ERROR: Phase not found: ${PHASE_ARG}

Available phases:
$(gpd phase list)
```

Exit.

Then load phase details:

```bash
gpd roadmap get-phase "${phase_number}"
grep -E "^| ${phase_number}" .gpd/REQUIREMENTS.md 2>/dev/null
```

Extract **phase goal** from ROADMAP.md (the research outcome to verify, not tasks) and **requirements** from REQUIREMENTS.md if it exists.

**Verification independence:** Load only what the verifier needs to judge results on their own merits. See @{GPD_INSTALL_DIR}/references/verification/meta/verification-independence.md.

**INCLUDE in verification context:**

- Phase goal from ROADMAP.md
- `contract` from PLAN.md frontmatter (primary verification target definition)
- Artifact file paths (the actual research outputs to inspect)
- .gpd/STATE.md (project conventions, active approximations, unit system)
- .gpd/config.json (project configuration)

**EXCLUDE from verification context:**

- Full PLAN.md body (task breakdowns, implementation details)
- SUMMARY.md files (what executors claimed they did)
- Execution logs or agent conversation history

Extract the contract target definition from frontmatter only:

```bash
for plan in "$phase_dir"/*-PLAN.md; do
  gpd frontmatter get "$plan" --field contract
done
```

</step>

<step name="establish_contract_targets">
**Primary option: contract in PLAN frontmatter**

Use the PLAN `contract` block as the canonical target definition. Verification must be keyed to contract IDs (`claim`, `deliverable`, `acceptance_test`, `reference`, `forbidden_proxy`) instead of re-deriving names from prose.
Verification targets must stay user-visible: a researcher should be able to point to the promised claim, artifact, comparison, or forbidden proxy in both the contract and the report. Do not promote bookkeeping fields, tool invocations, or agent/process milestones into verification targets.

Treat these as separate verification obligations:

- `claims` -> determine whether the physics claim is actually established
- `deliverables` -> determine whether the required artifact exists and is substantively correct
- `acceptance_tests` -> determine whether decisive checks actually passed
- `references` -> determine whether must-read anchors were read/compared/cited as required
- `forbidden_proxies` -> determine whether tempting but non-decisive substitutes were explicitly rejected

If the phase depends on a decisive comparison (benchmark, prior work, experiment, cross-method, baseline), emit a `comparison_verdicts` entry in the report keyed to the relevant contract IDs. Missing or purely implicit comparison evidence keeps the supported target below VERIFIED. If the comparison was attempted but not closed, record that honestly with `verdict: inconclusive` or `verdict: tension` instead of omitting the entry.
Before finalizing the check list, call `suggest_contract_checks(contract)` through the verification server and fold the returned contract-aware checks into the verification plan unless they are clearly inapplicable.

**Option B: Derive contract-like targets from phase goal**

If no `contract` is available in frontmatter:

1. State the goal from ROADMAP.md
2. Derive **claims** (3-7 verifiable physics outcomes, each testable by computation)
3. Derive **deliverables** (concrete file paths for each claim: derivations, notebooks, plots, data)
4. Derive **acceptance tests** (critical validation steps where errors hide)
5. Derive **required comparisons** (benchmarks, prior work, experiments, cross-method checks) when they are clearly decisive
6. Derive **forbidden proxies** (outputs that would look like progress but do not establish the claim)
7. Document this derived contract-like target set before proceeding

**Important: every derived claim must be testable by substituting values, taking limits, or performing an independent computation. Outcomes that can only be checked by grepping are process claims, not verification targets.**

If the plan contract is materially incomplete but the verifier can see an obvious decisive check that should exist, record it as a `suggested_contract_check` in the report rather than silently ignoring the gap.
Record `suggested_contract_checks` only for clearly decisive, user-visible gaps. Do not use them for administrative preferences, nicer formatting, or generic paperwork. Every such entry must stay structured with `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id` when known, and `evidence_path`.
</step>

<step name="batch_verification_triage">
**For phases with 10+ checks, use batch verification to reduce researcher burden.**

Count total checks across all contract-backed targets (claims + deliverables + acceptance tests + must-surface references + forbidden proxies + decisive comparisons).

**If TOTAL_CHECKS >= 10:**

1. Run ALL automated checks first (dimensional analysis, file existence, structural validation, limiting cases, numerical spot-checks)
2. Present results in a summary table:

```
## Verification Triage: {TOTAL_CHECKS} checks

| # | Check | Type | Auto-Result | Action |
|---|-------|------|-------------|--------|
| 1 | Derivation exists | artifact | PASSED | batch |
| 2 | Dimensions consistent | physics | PASSED | batch |
| 3 | k=0 limit correct | limiting | PASSED | batch |
| 4 | Convergence rate O(1/N^2) | numerical | FAILED | review |
| 5 | Novel result interpretation | expert | N/A | review |
...

**Auto-passed:** {N} checks (batch-approve all?)
**Needs review:** {M} checks (presented one at a time)
```

3. Let the researcher batch-approve all trivially passing checks (e.g., "yes, approve all passed")
4. Present only non-trivial checks (FAILED, N/A, or researcher-declined) one at a time for detailed review

**If TOTAL_CHECKS < 10:** Present all checks one at a time as usual.
</step>

<step name="verify_contract_targets">
For each contract-backed target, determine if the research artifacts support it.

**Status:** VERIFIED (all supporting artifacts and decisive checks pass) | PARTIAL (some evidence exists but decisive checks, anchor actions, or decisive comparisons remain open) | FAILED (artifact missing/incomplete/unvalidated or decisive comparison fails) | UNCERTAIN (needs human expert)

For each claim or acceptance test: identify supporting artifacts -> check artifact status -> run computational physics checks -> determine target status. State the verdict in terms of the user-visible outcome, not internal task completion.

For each reference target: verify the required actions (`read`, `compare`, `cite`, etc.) were actually completed and note any missing decisive anchor work.

For each forbidden proxy: verify the phase did not treat the proxy as success evidence. A forbidden proxy must be explicitly rejected, not merely omitted from prose.

For each decisive comparison: emit a `comparison_verdict` (`pass`, `tension`, `fail`, `inconclusive`) with the relevant subject ID, reference ID if applicable, comparison kind, metric, threshold, and outcome. A nearby sentence like "agrees with literature" or an unlabeled plot does not satisfy a decisive comparison. Use `inconclusive` or `tension` for exploratory or partial verification when the comparison was started but does not yet justify a decisive pass.

**Example:** Claim "Dispersion relation is correct in all limiting cases" depends on derivation.tex (full derivation), limits_check.py (numerical verification), dispersion_plot.pdf (visual confirmation).

Verification approach:

1. **Read** the derived dispersion relation omega(k) from the artifact
2. **Substitute** test values: k=0 (gap), k -> infinity (free particle), k = pi/a (zone boundary)
3. **Take limits** independently: long-wavelength limit (should give acoustic dispersion omega ~ v\*k), tight-binding limit, etc.
4. **Cross-check**: evaluate omega(k) numerically at several k points and compare with independent calculation

If the limits you compute do not match known results -> FAILED. If some supporting evidence exists but a decisive comparison, anchor action, or suggested decisive check is still open -> PARTIAL. If all independently-computed checks pass -> VERIFIED.
</step>

<step name="verify_artifacts">
Use gpd for initial artifact structural verification:

```bash
for plan in "$phase_dir"/*-PLAN.md; do
  ARTIFACT_RESULT=$(gpd verify artifacts "$plan")
  echo "=== $plan ===" && echo "$ARTIFACT_RESULT"
done
```

Parse JSON result: `{ all_passed, passed, total, artifacts: [{path, exists, issues, passed}] }`

**Artifact status from structural check:**

- `exists=false` -> MISSING
- `issues` not empty -> INCOMPLETE (check issues for "Only N lines" or "Missing pattern")
- `passed=true` -> Levels 1-2 pass (structural)

**Level 3 -- Content Validation (the critical addition):**

For each artifact that passes structural checks, perform content validation:

1. **Read the artifact** and identify its key equations, expressions, or computed values
2. **Spot-check** key expressions by substituting 2-3 test parameter sets where the answer is known
3. **Verify** at least one limiting case by independently taking the limit of the final expression
4. **Check dimensions** of the key equations by tracing physical dimensions of each symbol

```bash
# Example: content validation of a derivation artifact
python3 -c "
import numpy as np
# Read key result from artifact
# Substitute test values
# Compare with independently known answer
# Report match/mismatch
"
```

**Level 4 -- Integration:**

```bash
grep -r "import.*$artifact_name" src/ --include="*.py" --include="*.tex" --include="*.ipynb"  # REFERENCED
grep -r "$artifact_name" src/ --include="*.py" --include="*.tex" | grep -v "import"  # USED
```

VALIDATED = referenced AND used in downstream analysis AND content-validated. ORPHANED = exists but not referenced/used.

| Exists | Substantive | Content Valid | Integrated | Status     |
| ------ | ----------- | ------------- | ---------- | ---------- |
| yes    | yes         | yes           | yes        | VERIFIED   |
| yes    | yes         | yes           | no         | ORPHANED   |
| yes    | yes         | no            | -          | INCORRECT  |
| yes    | no          | -             | -          | INCOMPLETE |
| no     | -           | -             | -          | MISSING    |

</step>

<step name="verify_physics_computationally">
**This is the core verification step. Perform actual computations, not text searches.**

For each artifact, execute the applicable checks from the following protocols. Every check must produce a concrete numerical or algebraic result.

**CRITICAL**: The code templates below are SKELETONS. You MUST:
1. Replace ALL placeholder comments with actual expressions from the phase artifacts
2. Actually EXECUTE the resulting Python scripts via shell
3. Report the numerical output — do NOT just reason about what the output would be
4. If a script fails to run, report the failure explicitly

A verification that was not actually computed is NOT a verification.

### Protocol 1: Numerical Spot-Check

For each key equation or result in the artifact:

1. Choose 2-3 test parameter sets where the answer is independently known
2. Evaluate the expression at those parameter values
3. Compare with the expected answer

```bash
python3 -c "
import numpy as np

# From artifact: the expression/function to test
# def result_function(params):
#     ...

# Test point 1: trivial case (zero coupling, single particle, unit values)
# computed_1 = result_function(trivial_params)
# expected_1 = known_answer_trivial
# print(f'Test 1: computed={computed_1}, expected={expected_1}, match={np.isclose(computed_1, expected_1)}')

# Test point 2: known benchmark
# computed_2 = result_function(benchmark_params)
# expected_2 = benchmark_value
# print(f'Test 2: computed={computed_2}, expected={expected_2}, match={np.isclose(computed_2, expected_2)}')

# Test point 3: limiting case
# computed_3 = result_function(limit_params)
# expected_3 = known_limit
# print(f'Test 3: computed={computed_3}, expected={expected_3}, match={np.isclose(computed_3, expected_3)}')
"
```

### Protocol 2: Independent Limiting Case Derivation

For each key result, identify the relevant physical limits and take them yourself:

1. Write the final expression
2. Substitute the limiting parameter value
3. Simplify (series expand if needed)
4. Compare with the known result in that limit

```bash
python3 -c "
import sympy as sp

# Define symbols
# x, y, z = sp.symbols('x y z', positive=True)

# Final expression from artifact
# expr = ...

# Take limit independently
# limit_result = sp.limit(expr, x, 0)  # or sp.series(expr, x, 0, n=2)
# print(f'Limit as x -> 0: {limit_result}')
# print(f'Expected: {known_limit}')
# print(f'Match: {sp.simplify(limit_result - known_limit) == 0}')
"
```

### Protocol 3: Dimensional Analysis Trace

For each key equation:

1. List every symbol and its physical dimensions
2. Compute the dimensions of each term
3. Verify all terms have the same dimensions

Write this analysis explicitly — do not just assert "dimensions check out."

### Protocol 4: Independent Cross-Check

For at least one key result, verify by an independent method:

- Analytical result -> evaluate numerically at specific points
- Numerical result -> compare with analytical approximation
- Perturbative result -> check against exact result for solvable special case
- Any result -> check against a known benchmark value from literature

### Protocol 5: Convergence Test (for numerical artifacts)

Run the computation at 2-3 resolution levels and verify convergence:

```bash
python3 -c "
import numpy as np

# Run at multiple resolutions
# for N in [50, 100, 200]:
#     result_N = run_computation(N=N)
#     print(f'N={N}: result={result_N}')

# Measure convergence rate
# error_50_100 = abs(result_50 - result_100)
# error_100_200 = abs(result_100 - result_200)
# rate = np.log(error_50_100 / error_100_200) / np.log(2)
# print(f'Convergence rate: O(1/N^{rate:.1f})')
"
```

**Record results for every check with confidence rating:**

- **INDEPENDENTLY CONFIRMED**: re-derived/re-computed and matches
- **STRUCTURALLY PRESENT**: can't fully verify but structure is correct
- **UNABLE TO VERIFY**: requires capabilities beyond current context
  </step>

<step name="verify_physics_checks">
Use gpd for initial physics check verification:

```bash
for plan in "$phase_dir"/*-PLAN.md; do
  CHECKS_RESULT=$(gpd verify plan "$plan")
  echo "=== $plan ===" && echo "$CHECKS_RESULT"
done
```

Parse JSON result: `{ all_verified, verified, total, checks: [{type, description, verified, detail}] }`

**Supplement gpd structural checks with computational verification:**

For each check from gpd CLI, the structural verification tells you WHETHER a check exists in the code. Your job is to verify whether that check ACTUALLY PASSES by performing the computation yourself (or by running the existing check code and evaluating the output).

| Check                         | Structural (gpd CLI)            | Computational (you do this)                                   |
| ----------------------------- | --------------------------------- | ------------------------------------------------------------- |
| Dimensional analysis          | "Found unit annotations in file"  | Trace dimensions through each equation term by term           |
| Limiting cases                | "Found limit check in code"       | Take the limit yourself and verify it matches                 |
| Symmetry checks               | "Found symmetry test function"    | Apply the symmetry transformation to the result and check     |
| Numerical convergence         | "Found convergence loop"          | Run at 2+ resolutions and measure convergence rate            |
| Comparison with known results | "Found literature reference"      | Extract both values and compute relative error                |
| Conservation laws             | "Found energy conservation check" | Compute conserved quantity at 2+ times/configurations, verify |
| Order-of-magnitude            | "Found magnitude estimate"        | Independently estimate the expected magnitude and compare     |

Record status and computation evidence for each physics check.
</step>

<step name="verify_requirements">
If REQUIREMENTS.md exists:

REQUIREMENTS.md uses a traceability table mapping REQ-IDs to phases. The table format is: `| REQ-XXX | description | Phase N, Phase M |`. Match rows where the phase column contains the current phase number:

```bash
# Match traceability table rows referencing this phase (handles "Phase 3", "Phase 3," and "Phase 3 |")
grep -E "\|.*Phase\s*${PHASE_NUM}(\s*[,|]|\s*$)" .gpd/REQUIREMENTS.md 2>/dev/null
```

If the traceability table is not found, fall back to a broader search:

```bash
# Fallback: match any row containing the phase number in a table context
grep -E "^\|.*\b${PHASE_NUM}\b" .gpd/REQUIREMENTS.md 2>/dev/null
```

For each requirement: parse description -> identify supporting contract targets / artifacts -> status: SATISFIED / BLOCKED / NEEDS EXPERT.

A requirement is SATISFIED only if the supporting user-visible claims / deliverables / acceptance tests were VERIFIED with computation evidence, required anchors were handled, and no forbidden proxy is masking a missing result.
</step>

<step name="verify_numerical_results">
**For computational phases** (phases containing simulations, numerical calculations, or code):

1. **Run convergence checks** on all numerical results by executing at 2-3 resolution levels
2. **Verify conservation laws** numerically by computing conserved quantities at multiple time steps
3. **Check numerical results against analytical limiting cases** by evaluating at parameter values where analytical results are known
4. **Spot-check output values** against independently computed test cases
5. Reference: @{GPD_INSTALL_DIR}/workflows/numerical-convergence.md for detailed methodology

For each numerical result, record:

- What test you ran
- What inputs you used
- What output you got
- What you expected
- Whether they agree (and to what precision)
  </step>

<step name="scan_antipatterns">
Extract files modified in this phase from SUMMARY.md, scan each:

| Pattern                    | Search                                                                | Severity |
| -------------------------- | --------------------------------------------------------------------- | -------- |
| TODO/FIXME/PLACEHOLDER     | `grep -n -E "TODO\|FIXME\|PLACEHOLDER\|HACK"`                         | Warning  |
| Placeholder content        | `grep -n -iE "placeholder\|will derive later\|TBD\|to be determined"` | Blocker  |
| Hardcoded values           | `grep -n -E "[0-9]+\.[0-9]+" ` (check for unexplained magic numbers)  | Warning  |
| Missing error handling     | Functions with no convergence checks or NaN guards                    | Warning  |
| Skipped derivation steps   | Comments like "it can be shown that" without proof                    | Warning  |
| Unjustified approximations | Approximations without stated validity conditions                     | Blocker  |

Categorize: Blocker (prevents research goal) | Warning (incomplete) | Info (notable).
</step>

<step name="cross_phase_consistency">
**Lightweight cross-phase consistency check at phase boundaries.**

Skip this step if `phase_number` is the first phase (no prior phase to compare against).

Otherwise, locate the previous phase's SUMMARY.md and read the current phase's SUMMARY.md:

```bash
# Find previous phase summary (phase N-1)
PREV_PHASE_DIR=$(ls -d .gpd/phases/*/ | sort | grep -B1 "$phase_dir" | head -1)
PREV_SUMMARY=$(ls "$PREV_PHASE_DIR"/*-SUMMARY.md 2>/dev/null | tail -1)
CURR_SUMMARY=$(ls "$phase_dir"/*-SUMMARY.md 2>/dev/null | tail -1)
```

If both summaries exist, check for cross-phase consistency by reading:

1. **Current SUMMARY.md** — "Cross-Phase Dependencies" section (consumed results, convention changes)
2. **Previous SUMMARY.md** — "Approximations Used" table and "Key Results" / "Equations Derived"
3. **STATE.md** — "Active Approximations" table and "Convention Lock"

Reference: @{GPD_INSTALL_DIR}/references/verification/core/verification-core.md (+ relevant domain verification file)

**Check the four most common cross-phase errors:**

| Check                            | Method                                                                                                                                                                                        | Severity |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| **Notation drift**               | Compare symbols in current phase's equations against previous phase's "Equations Derived" — same symbol must mean same quantity                                                               | Warning  |
| **Convention change**            | Verify "Convention Changes" table in current SUMMARY.md is populated; compare against STATE.md "Convention Lock" (metric signature, Fourier convention, units)                                | Warning  |
| **Approximation regime overlap** | Cross-reference current phase's "Approximations Used" against STATE.md "Active Approximations" — new parameter values must remain within validity ranges of prior approximations still in use | Blocker  |
| **Unit system consistency**      | Check that the unit system (natural units, SI, CGS) in current phase matches what STATE.md "Convention Lock" declares                                                                         | Warning  |

**Computational check for cross-phase consistency:** If both phases produce a value for the same physical quantity (e.g., energy at a specific parameter set), evaluate both and verify they agree.

Record findings as `cross_phase_warnings` (list of warnings) and `cross_phase_blockers` (list of blockers). Include in the verification report under a "Cross-Phase Consistency" section.

If no issues found: note "Cross-phase consistency: OK (checked against Phase {N-1})".
</step>

<step name="identify_expert_verification">
**Always needs expert:** Physical interpretation of results, comparison with experimental data, assessment of approximation validity, evaluation of novel theoretical claims, judgment on whether results are publishable.

**Needs expert if uncertain:** Complex multi-step derivations that computational checks cannot fully trace, parameter regime validity, connection to broader physical context, novelty assessment.

**Needs expert because of verifier limitations:** Checks rated "unable to verify" or "structurally present" for critical results. Be explicit about why the computational check could not be completed.

Format each as: Check Name -> What to verify -> Expected result -> Why cannot verify computationally in this context.
</step>

<step name="determine_status">
**passed:** All decisive contract targets VERIFIED with computation evidence, all artifacts pass levels 1-4, all required comparison verdicts are acceptable, all must-surface references are handled, all forbidden proxies are rejected, no unresolved `suggested_contract_checks` remain on decisive targets, no blocker anti-patterns, no cross-phase blockers.

**gaps_found:** Any decisive contract target FAILED, artifact MISSING/INCOMPLETE/INCORRECT, required comparison verdict missing/FAIL/TENSION without resolution, required reference action missing, forbidden proxy VIOLATED/UNRESOLVED, physics check NOT_PERFORMED/FAILED, blocker anti-pattern found, cross-phase blocker found, or an omitted decisive check is recorded in `suggested_contract_checks` without an equivalent closing check elsewhere.

**human_needed:** All automated and computational checks pass but expert verification items remain.

**Score:** `verified_contract_targets / total_contract_targets`
**Independently confirmed:** `independently_confirmed_checks / total_applicable_checks`
</step>

<step name="generate_fix_plans">
If gaps_found:

1. **Cluster related gaps:** Missing derivation + unverified limit -> "Complete and validate derivation". Multiple missing plots -> "Generate analysis figures". Physics checks failing -> "Debug calculation errors".

2. **Include computation evidence in each gap:** What test you ran, what you expected, what you got. This makes fix plans actionable — the executor knows exactly what is wrong.

3. **Generate plan per cluster:** Objective, 2-3 tasks (files/action/verify each), re-verify step. Keep focused: single concern per plan.

4. **Order by dependency:** Fix missing derivations -> fix incomplete calculations -> validate physics -> verify.
   </step>

<step name="create_report">
```bash
REPORT_PATH="$phase_dir/${phase_number}-VERIFICATION.md"
```

Fill template sections: frontmatter (phase/timestamp/status/score/plan_contract_ref/contract_results/comparison_verdicts/suggested_contract_checks/independently_confirmed), goal achievement, contract targets table, artifact table, computational verification details (spot-checks, limits re-derived, cross-checks, dimensional analysis traces), physics checks table, requirements coverage, anti-patterns, cross-phase consistency, expert verification, gaps summary with computation evidence, fix plans (if gaps_found), metadata. The contract targets table should read like a user-visible outcome ledger, not a workflow checklist.

If the verifier identifies a decisive check that the contract omitted but downstream work clearly depends on, record it under `suggested_contract_checks` with a reason and recommended evidence path. Do not hide this by marking the parent target VERIFIED; keep the target PARTIAL or FAILED until the missing decisive check is resolved or explicitly re-scoped.

See {GPD_INSTALL_DIR}/templates/verification-report.md for complete template.
</step>

<step name="oracle_gate_check">
**Before returning, verify that VERIFICATION.md contains at least one computational oracle block.**

Scan the written VERIFICATION.md for evidence of actual code execution:

```bash
# Check for code output blocks in VERIFICATION.md
VERIFICATION_FILE="${phase_dir}/${phase}-VERIFICATION.md"
if [ -f "$VERIFICATION_FILE" ]; then
  # Look for output blocks (```output or **Output:** followed by ```)
  HAS_OUTPUT=$(grep -cE '(^\*\*Output:?\*\*|^```(output|text)|computed=|PASS|FAIL|match=True|match=False)' "$VERIFICATION_FILE")
  if [ "$HAS_OUTPUT" -lt 1 ]; then
    echo "WARNING: VERIFICATION.md has no computational oracle output blocks."
    echo "The verifier must execute at least one code check and include the output."
    echo "See computational-verification-templates.md for templates."
  else
    echo "Oracle gate: PASSED ($HAS_OUTPUT output blocks found)"
  fi
fi
```

If no computational output blocks are found, the verification is INCOMPLETE. The verifier must go back and execute at least one computational check before the workflow can proceed.

This gate enforces the principle that verification must involve external computation, not just LLM reasoning about physics.
</step>

<step name="return_to_orchestrator">
Return status (`passed` | `gaps_found` | `human_needed`), score (N/M contract targets), independently confirmed count (K/M), report path.

If gaps_found: list gaps with contract IDs, computation evidence, comparison verdict failures or forbidden-proxy violations, and recommended fix plan names.
If human_needed: list items requiring expert review with explanation of why computational verification was insufficient.

Orchestrator routes: `passed` -> update_roadmap | `gaps_found` -> create/execute fixes, re-verify | `human_needed` -> present to researcher.
</step>

</process>

<success_criteria>

- [ ] Contract-backed targets established from PLAN frontmatter
- [ ] Verification scoped to user-visible contract targets rather than internal process milestones
- [ ] All contract-backed claims / deliverables / acceptance tests verified with status, computation evidence, and confidence rating
- [ ] All artifacts checked at all four levels (exists, substantive, content-validated, integrated)
- [ ] **Numerical spot-checks performed** on key expressions (2-3 test points each)
- [ ] **Limiting cases independently re-derived** by taking limits of final expressions
- [ ] **Dimensional analysis traced** through key equations symbol by symbol
- [ ] **Independent cross-checks** performed where feasible
- [ ] All physics checks verified computationally (not just structurally)
- [ ] Convergence tested at multiple resolutions for numerical results
- [ ] Literature benchmarks compared with actual numerical values
- [ ] Required `comparison_verdicts` emitted for decisive benchmarks / prior-work / experiment / cross-method checks, including `inconclusive` / `tension` when honest
- [ ] Missing decisive comparison verdicts keep the supported target below VERIFIED
- [ ] Required references handled and forbidden proxies explicitly audited
- [ ] Missing decisive checks recorded as structured `suggested_contract_checks`
- [ ] Requirements coverage assessed (if applicable)
- [ ] Anti-patterns scanned and categorized
- [ ] Cross-phase consistency checked (notation, conventions, approximations, units) if 2+ phases exist
- [ ] Expert verification items identified with explanation of computational limitations
- [ ] Overall status determined with independently-confirmed count
- [ ] Fix plans generated with computation evidence (if gaps_found)
- [ ] VERIFICATION.md created with complete computational verification details
- [ ] Results returned to orchestrator
</success_criteria>
