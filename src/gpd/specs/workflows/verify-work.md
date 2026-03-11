<purpose>
Validate research results through conversational research validation with persistent state. Creates VERIFICATION.md that tracks verification progress, survives /clear, and feeds gaps into /gpd:plan-phase --gaps.

Researcher validates, the AI records. One check at a time. Plain text responses.

**Key upgrade: checks now include computational spot-checks that the AI performs before presenting to the researcher, and the researcher is guided through numerical verification rather than just qualitative confirmation.**
</purpose>

<philosophy>
**Show expected physics AND computational evidence, ask if reality matches.**

The AI does not just present what the research SHOULD show — it COMPUTES what the research should show at specific test points, then asks the researcher to confirm.

- "yes" / "y" / "next" / empty -> pass
- Anything else -> logged as issue, severity inferred

Walk through derivation logic, perform numerical spot-checks, re-derive limiting cases, probe edge cases with actual computations. No formal review forms. Just: "Here is what I independently computed. Does your result match?"

**Verification independence:** Derive validation checks from the phase goal and the actual research artifacts — not from SUMMARY.md claims about what was accomplished. SUMMARY.md tells you WHERE to look (file paths, deliverable names), but expected physics outcomes come from the phase goal and domain knowledge. See @{GPD_INSTALL_DIR}/references/verification/meta/verification-independence.md.
</philosophy>

<template>
@{GPD_INSTALL_DIR}/templates/research-verification.md
</template>

<required_reading>
@{GPD_INSTALL_DIR}/references/protocols/error-propagation-protocol.md
</required_reading>

<process>

<step name="check_type_selection">
## Check Type Selection

Parse `$ARGUMENTS` for specific check flags:
- `--dimensional` — Run only dimensional analysis checks
- `--limits` — Run only limiting case checks
- `--convergence` — Run only numerical convergence checks
- `--regression` — Run regression check (re-verify previous truths)
- `--all` or no flags — Run full verification suite

This allows targeted verification without running the full suite.
</step>

<step name="initialize" priority="first">
If $ARGUMENTS contains a phase number, load context:

```bash
INIT=$(gpd init verify-work "${PHASE_ARG}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `planner_model`, `checker_model`, `commit_docs`, `autonomy`, `research_mode`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `has_verification`, `has_validation`.

**Mode-aware behavior:**
- `autonomy=babysit`: Pause after each verification round for user review. Present findings and wait for confirmation before writing `VERIFICATION.md`.
- `autonomy=balanced` (default): Run the full verification pipeline. Pause only if verification reveals critical issues that require user judgment or claim-level decisions.
- `autonomy=yolo`: Run verification but skip optional cross-checks and literature comparison.
- `research_mode=explore`: Thorough verification — run all check types, compare against literature, verify intermediate steps. More spawned verifier agents.
- `research_mode=exploit`: Focused verification — run priority checks only, verify final results. Minimal agent spawning.
- `research_mode=adaptive`: Start with exploit-level checks, escalate to explore if any check fails.

**If `phase_found` is false:**

```
ERROR: Phase not found: ${PHASE_ARG}

Available phases:
$(gpd phase list)

Usage: /gpd:verify-work <phase-number>
```

Exit.
</step>

<step name="check_active_session">
**First: Check for active verification sessions**

```bash
find .gpd/phases -name "*-VERIFICATION.md" -type f 2>/dev/null | head -5
```

**If active sessions exist AND no $ARGUMENTS provided:**

Read each file's frontmatter (status, phase) and Current Check section.

Display inline:

```
## Active Verification Sessions

| # | Phase | Status | Current Check | Progress |
|---|-------|--------|---------------|----------|
| 1 | 04-dispersion | validating | 3. Limiting Cases | 2/6 |
| 2 | 05-numerics | validating | 1. Convergence Test | 0/4 |

Reply with a number to resume, or provide a phase number to start new.
```

Wait for user response.

- If user replies with number (1, 2) -> Load that file, go to `resume_from_file`
- If user replies with phase number -> Treat as new session, go to `create_verification_file`

**If active sessions exist AND $ARGUMENTS provided:**

Check if session exists for that phase. If yes, offer to resume or restart.
If no, continue to `create_verification_file`.

**If no active sessions AND no $ARGUMENTS:**

```
No active verification sessions.

Provide a phase number to start validation (e.g., /gpd:verify-work 4)
```

**If no active sessions AND $ARGUMENTS provided:**

Continue to `create_verification_file`.
</step>

<step name="find_summaries">
**Find what to validate:**

Use `phase_dir` from init (or run init if not already done).

```bash
ls "$phase_dir"/*-SUMMARY.md 2>/dev/null
```

Read each SUMMARY.md to extract **deliverable names and file paths only**. Do NOT trust SUMMARY.md claims about correctness, convergence, or agreement with literature — those are exactly what you are validating. Use SUMMARY.md as a map to find artifacts, not as evidence that they are correct.

Also load the phase goal from ROADMAP.md to derive expected physics outcomes independently:

```bash
gpd roadmap get-phase "${phase_number}"
```

</step>

<step name="extract_checks">
**Extract validatable deliverables from SUMMARY.md:**

Parse for:

1. **Derivations** - Analytical results, equations derived, proofs completed
2. **Calculations** - Numerical results, computed quantities, simulation outputs
3. **Plots and figures** - Visualizations of results, comparison plots
4. **Physical claims** - Statements about physics supported by the work

Focus on VERIFIABLE RESEARCH OUTCOMES, not implementation details.

For each deliverable, create a validation check that includes **both qualitative expectations and a concrete computational test:**

- name: Brief check name
- expected: What the physics should show (specific, verifiable)
- computation: A specific numerical test the AI will perform before presenting to the researcher

**Examples with computational verification:**

- Derivation: "Derived Boltzmann equation from BBGKY hierarchy"
  -> Check: "Derivation of Boltzmann Equation"
  -> Expected: "Starting from the BBGKY hierarchy, the two-particle correlation is factored in the dilute gas limit. The collision integral should have the form of gain minus loss terms with cross-section weighting."
  -> Computation: "I will evaluate the collision integral at a test point (v1=[1,0,0], v2=[0,1,0]) and verify it has the correct structure: gain - loss with appropriate cross-section weighting."

- Calculation: "Computed critical temperature for 3D Ising model"
  -> Check: "Critical Temperature Value"
  -> Expected: "Tc/J should be approximately 4.51 for simple cubic lattice."
  -> Computation: "I will extract the computed Tc from the artifact, compute the exact value Tc/J = 4.5115..., and report the relative error."

- Plot: "Phase diagram as function of temperature and coupling"
  -> Check: "Phase Diagram Features"
  -> Expected: "Phase boundary should show expected topology: ordered phase at low T, disordered at high T."
  -> Computation: "I will evaluate the order parameter at 3 test points: (T=0.5*Tc, g=1) should be non-zero, (T=2*Tc, g=1) should be zero, and the boundary should cross at T=Tc."

- Limiting case: "Free-particle limit of interacting Green's function"
  -> Check: "Free-particle Limit"
  -> Expected: "G(k, omega) should reduce to 1/(omega - epsilon_k + i\*eta) when interaction V -> 0."
  -> Computation: "I will take V=0 in the expression from the artifact, simplify, and verify it equals the free-particle propagator. Then I will evaluate both at k=pi/2, omega=1.0 and compare numerically."

Skip internal/non-observable items (code refactors, file reorganization, etc.).
</step>

<step name="minimum_verification_floor">
**Regardless of profile (including exploratory), the pre-computation phase must satisfy these minimums:**

1. **Dimensional analysis**: At least one equation checked symbol-by-symbol for dimensional consistency
2. **Limiting case**: At least one limiting case independently re-derived (not just discussed qualitatively)
3. **Numerical spot-check with code execution**: At least one Python/SymPy script actually executed via shell, with the output captured and presented to the researcher

**Code output requirement:** The final VERIFICATION.md must contain at least one fenced code block showing actual execution output. A verification report with only text analysis and zero computational evidence is INCOMPLETE. If the pre-computation step produces no code outputs, flag the verification as incomplete before presenting to the researcher.

These 3 minimum checks must be among the checks presented to the researcher, even when the exploratory profile reduces the total check count.
</step>

<step name="precompute_checks">
**Before presenting checks to the researcher, perform computational verification on each deliverable.**

For each check:

1. **Read the artifact** to extract the actual expression/result/code
2. **Perform the computational test** specified in the check definition
3. **Record the result** (pass/fail/inconclusive) as pre-computed evidence

This gives the researcher concrete numbers to compare against, not just qualitative expectations.

```bash
# Example: pre-compute a spot-check before presenting to researcher
python3 -c "
import numpy as np
# Extract key expression from artifact
# Evaluate at test point
# Compare with expected
# print('Pre-check result: ...')
"
```

**If the pre-computation reveals an obvious error:** Still present the check to the researcher, but include your finding:
"I computed X at test point Y and got Z, but expected W. This suggests a possible error. Can you confirm?"

**If the pre-computation confirms the result:** Present with confidence:
"I independently computed X at test point Y and got Z, which matches the artifact. Does this agree with your understanding?"
</step>

<step name="create_verification_file">
**Create or extend verification file with all checks:**

```bash
mkdir -p "$phase_dir"
```

**Check for existing VERIFICATION.md** (e.g., from a prior `/gpd:execute-phase` → `verify-phase` run):

```bash
EXISTING_VERIFICATION=$(ls "$phase_dir"/*-VERIFICATION.md 2>/dev/null | head -1)
```

If an existing VERIFICATION.md is found (e.g., from a prior `/gpd:execute-phase` → `verify-phase` automated run):
1. Read it to preserve any prior automated verification results
2. Do NOT overwrite — instead, append a `## Researcher Validation` section after the existing content
3. The new researcher checks go under this section, keeping the automated checks intact
4. **Status merge rule:** The combined status is the MORE RESTRICTIVE of the two results. If automated verification passed but the researcher finds issues, the combined status becomes `gaps_found`. If automated found gaps but the researcher confirms they are acceptable, the combined status stays `gaps_found` unless the researcher explicitly upgrades each gap to `pass`. Update the frontmatter `status` to reflect the combined result.
5. The `independently_confirmed` count in the report should aggregate both automated and researcher-confirmed checks

If no existing VERIFICATION.md exists, create a new one from scratch.

Build check list from extracted deliverables, including computational test specifications.

Create file (or extend existing):

```markdown
---
status: validating
phase: {phase_number}-{phase_name}
source: [list of SUMMARY.md files]
started: [ISO timestamp]
updated: [ISO timestamp]
---

## Current Check

<!-- OVERWRITE each check - shows where we are -->

number: 1
name: [first check name]
expected: |
[what the physics should show]
computation: |
[what computational test was performed]
precomputed_result: |
[result of AI's independent computation]
awaiting: researcher response

## Checks

### 1. [Check Name]

expected: [verifiable physics outcome]
computation: [specific numerical test performed]
precomputed_result: [AI's independent computation result]
result: [pending]

### 2. [Check Name]

expected: [verifiable physics outcome]
computation: [specific numerical test performed]
precomputed_result: [AI's independent computation result]
result: [pending]

...

## Summary

total: [N]
passed: 0
issues: 0
pending: [N]
skipped: 0

## Gaps

[none yet]
```

Write to `${phase_dir}/{phase}-VERIFICATION.md`

Proceed to `present_check`.
</step>

<step name="present_check">
**Present current check to researcher with computational evidence:**

Read Current Check section from verification file.

Display using checkpoint box format:

```
+==============================================================+
|  CHECKPOINT: Research Validation Required                      |
+==============================================================+

**Check {number}: {name}**

{expected}

**Independent computation:**
{computation description and result}

--------------------------------------------------------------
-> Confirm this matches your result, or describe what differs
--------------------------------------------------------------
```

The key upgrade: instead of just asking "does it look right?", present concrete numbers from your independent computation so the researcher has something specific to compare against.

**Guide the researcher through numerical spot-checks when appropriate:**

For derivation checks:

```
I independently evaluated your expression at [test point]:
  Your expression gives: [value]
  Expected (from [source]): [value]
  Relative error: [value]

Does this match what you see when you evaluate at this point?
```

For limiting case checks:

```
I took the [limit name] limit of your final expression:
  Your expression in the limit: [simplified form]
  Known result in this limit: [known form]
  Agreement: [yes/no, with details]

Can you confirm this is the correct limiting behavior?
```

For numerical checks:

```
I ran your code at resolutions N=[50, 100, 200]:
  N=50:  result = [value]
  N=100: result = [value]
  N=200: result = [value]
  Convergence rate: O(1/N^[p])

Does this convergence rate match the expected order of your method?
```

Wait for researcher response (plain text).
</step>

<step name="process_response">
**Process researcher response and update file:**

**If response indicates pass:**

- Empty response, "yes", "y", "ok", "pass", "next", "confirmed", "correct"

Update Checks section:

```
### {N}. {name}
expected: {expected}
computation: {computation performed}
precomputed_result: {AI's result}
result: pass
confidence: {independently confirmed | structurally present}
```

**If response indicates skip:**

- "skip", "cannot check", "n/a", "not applicable"

Update Checks section:

```
### {N}. {name}
expected: {expected}
computation: {computation performed}
precomputed_result: {AI's result}
result: skipped
reason: [researcher's reason if provided]
```

**If response is anything else:**

- Treat as issue description

Infer severity from description:

- Contains: wrong, error, diverges, blows up, unphysical, violates -> blocker
- Contains: disagrees, inconsistent, does not match, off by, missing -> major
- Contains: approximate, close but, small discrepancy, minor -> minor
- Contains: label, formatting, axis, legend, cosmetic -> cosmetic
- Default if unclear: major

Update Checks section:

```
### {N}. {name}
expected: {expected}
computation: {computation performed}
precomputed_result: {AI's result}
result: issue
reported: "{verbatim researcher response}"
severity: {inferred}
```

Append to Gaps section (structured YAML for plan-phase --gaps):

```yaml
- truth: "{expected physics outcome from check}"
  status: failed
  reason: "Researcher reported: {verbatim researcher response}"
  computation_evidence: "{what AI independently computed and found}"
  severity: { inferred }
  check: { N }
  artifacts: [] # Filled by diagnosis
  missing: [] # Filled by diagnosis
```

**After any response:**

Update Summary counts.
Update frontmatter.updated timestamp.

**REQUIREMENTS.md traceability update (on pass only):**

If the check passed AND the check name or expected outcome corresponds to a requirement ID (REQ-*) from `.gpd/REQUIREMENTS.md`, update the requirement's status:

1. Read `.gpd/REQUIREMENTS.md` (skip if file doesn't exist)
2. Search for the matching REQ-ID in the requirements table
3. Update the requirement row's validation status:
   - Change status cell to `Validated`
   - Append ` (Phase {phase}, Check {N})` to the evidence/notes cell
4. Write back the updated REQUIREMENTS.md

**Matching logic:**

- Check name contains `REQ-NNN` literally -> direct match
- Check expected outcome references a requirement by ID -> direct match
- Check validates a deliverable that maps to a known requirement -> fuzzy match (note the match in VERIFICATION.md but don't auto-update REQUIREMENTS.md for fuzzy matches)

Skip this sub-step silently if no REQUIREMENTS.md exists or no REQ-IDs match.

If more checks remain -> Update Current Check, go to `present_check`
If no more checks -> Go to `complete_session`
</step>

<step name="resume_from_file">
**Resume validation from file:**

Read the full verification file.

Find first check with `result: [pending]`.

Announce:

```
Resuming: Phase {phase} Research Validation
Progress: {passed + issues + skipped}/{total}
Issues found so far: {issues count}

Continuing from Check {N}...
```

Update Current Check section with the pending check.
Proceed to `present_check`.
</step>

<step name="researcher_custom_checks">
**After presenting all automated checks, invite researcher to add their own:**

```
All {N} automated checks complete ({passed} passed, {issues} issues, {skipped} skipped).

Are there any additional physics checks you'd like to verify?
Examples: "check Ward identity", "verify sum rule", "test at strong coupling"
(Type "done" to skip)
```

**If researcher provides custom checks:**

For each custom check:
1. Parse the description into a check name and expected behavior
2. Attempt to pre-compute the check (read relevant artifacts, run test if possible)
3. Present the result using the same checkpoint box format as automated checks
4. Process the response identically to automated checks (pass/issue/skip)
5. Append to the Checks section in VERIFICATION.md with `source: researcher`

Custom checks are numbered continuing from the last automated check (e.g., if 6 automated checks, first custom check is 7).

**If researcher says "done", "no", "skip", or empty:** Proceed to `cross_phase_uncertainty_audit`.
</step>

<step name="cross_phase_uncertainty_audit">
**Audit uncertainty propagation across phases with researcher.**

This step checks that uncertainties from prior phases propagate correctly into the current phase's results — the #1 gap found by physics verification audits.

**1. Identify inherited quantities:**

Read phase SUMMARY.md files (current and prior phases). Find quantities consumed by the current phase that were produced by earlier phases.

```bash
# Check if prior phases declared uncertainty budgets
for PRIOR_SUMMARY in $(ls .gpd/phases/*/SUMMARY.md 2>/dev/null | sort); do
  grep -l "Uncertainty Budget\|uncertainty\|±\|\\\\pm" "$PRIOR_SUMMARY" 2>/dev/null
done
```

**2. If inherited quantities exist, present uncertainty audit to researcher:**

For each inherited quantity used in the current phase:

```
+==============================================================+
|  UNCERTAINTY CHECK: {quantity_name}                            |
+==============================================================+

Source: Phase {N} SUMMARY.md
Value: {central_value} ± {uncertainty}
Used in: {current phase equation/computation}

Propagated uncertainty in final result:
{independently computed propagated uncertainty}

Does this uncertainty budget look correct? (yes/no/skip)
```

**3. Check for catastrophic cancellation (Error #102):**

If two quantities with comparable magnitudes are subtracted, compute the relative uncertainty of the difference:

```bash
python3 -c "
a, da = ${VALUE_A}, ${UNCERT_A}
b, db = ${VALUE_B}, ${UNCERT_B}
diff = abs(a - b)
d_diff = (da**2 + db**2)**0.5
if diff > 0:
    rel = d_diff / diff
    print(f'Relative uncertainty of difference: {rel:.2%}')
    if rel > 1.0:
        print('WARNING: Catastrophic cancellation — uncertainty exceeds the difference')
else:
    print('WARNING: Exact cancellation — difference is zero')
"
```

**4. Record findings in VERIFICATION.md:**

Add an "Uncertainty Propagation Audit" section with:
- List of inherited quantities and their declared uncertainties
- Propagation check results (pass/fail per quantity)
- Any catastrophic cancellation warnings
- Researcher responses

If no inherited quantities exist (Phase 1 or self-contained): note "N/A — no cross-phase uncertainty dependencies" and proceed.

Proceed to `complete_session`.
</step>

<step name="complete_session">
**Complete validation and commit:**

Update frontmatter:

- status: completed
- updated: [now]

Clear Current Check section:

```
## Current Check

[validation complete]
```

Commit the verification file:

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${phase_dir}/{phase}-VERIFICATION.md" 2>&1) || true
echo "$PRE_CHECK"

gpd commit "verify({phase}): complete research validation - {passed} passed, {issues} issues" --files "${phase_dir}/{phase}-VERIFICATION.md"
```

Present summary:

```
## Research Validation Complete: Phase {phase}

| Result | Count |
|--------|-------|
| Passed | {N}   |
| Issues | {N}   |
| Skipped| {N}   |

### Verification Confidence

| Confidence Level | Count |
|------------------|-------|
| Independently Confirmed | {N} |
| Structurally Present    | {N} |
| Unable to Verify        | {N} |

[If issues > 0:]
### Issues Found

[List from Issues section, including computation evidence for each]
```

**If issues > 0:** Proceed to `diagnose_issues`

**If issues == 0:**

```
All checks passed. Research validated. Ready to continue.

- `/gpd:plan-phase {next}` -- Plan next research phase
- `/gpd:execute-phase {next}` -- Execute next research phase
```

</step>

<step name="diagnose_issues">
**Diagnose root causes before planning fixes:**

**Severity gate:** Only spawn parallel diagnosis agents for major+ issues. Minor and cosmetic issues are reported directly without investigation overhead.

**1. Partition issues by severity:**

- **Major+ issues** (blocker, major): Collect into `investigate_issues` list
- **Minor/cosmetic issues** (minor, cosmetic): Collect into `report_directly` list

**2. Present minor/cosmetic issues directly:**

If `report_directly` is non-empty:

```
### Minor/Cosmetic Issues (no investigation needed)

| # | Check | Severity | Reported |
|---|-------|----------|----------|
| {N} | {name} | {severity} | {verbatim response} |
```

These are noted in VERIFICATION.md but do not trigger investigation agents.

**3. Investigate major+ issues:**

If `investigate_issues` is non-empty:

```
---

{N} major+ issues found. Diagnosing root causes...

Spawning parallel investigation agents for each major+ issue.
({M} minor/cosmetic issues reported directly — no investigation needed.)
```

- Load debug workflow
- Follow @{GPD_INSTALL_DIR}/workflows/debug.md
- Spawn parallel investigation agents for each issue in `investigate_issues`
- **Include computation evidence from pre-checks and researcher reports in the diagnosis context** — the investigator should know what specific test failed and what values were obtained
- Collect root causes
- Update VERIFICATION.md with root causes
- Proceed to `diagnosis_review`

**4. If only minor/cosmetic issues exist (no major+ issues):**

Skip investigation entirely. Present summary and offer options:

```
All {N} issues are minor or cosmetic — no root cause investigation needed.

Options:
1. Plan fixes for minor issues
2. Accept as-is — issues are low-impact
3. Investigate anyway — I want deeper analysis
```

Diagnosis runs automatically for major+ issues — no researcher prompt. Parallel agents investigate simultaneously, so overhead is minimal and fixes are more accurate.
</step>

<step name="diagnosis_review">
## Diagnosis Review

Present the diagnosis results to the user:

| Issue | Root Cause | Confidence |
|-------|-----------|------------|
{diagnosis results from investigation agents}

Use ask_user:

- header: "Fix Approach"
- question: "How would you like to handle the identified issues?"
- options:
  - "Auto-plan fixes (Recommended)" — Spawn planner for systematic gap closure
  - "Investigate manually" — I want to explore the issues myself first
  - "Accept as-is" — The issues are minor, results are acceptable

**If "Auto-plan fixes":** Continue to plan_gap_closure step.
**If "Investigate manually":** Present the detailed diagnosis and pause. Offer `/gpd:debug` for structured investigation.
**If "Accept as-is":** Skip gap closure, mark phase verified with noted caveats.
</step>

<step name="plan_gap_closure">
**Auto-plan fixes from diagnosed gaps:**

Display:

```
====================================================
 GPD > PLANNING FIXES
====================================================

* Spawning planner for gap closure...
```

Spawn gpd-planner in --gaps mode:
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="""First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.

<planning_context>

**Phase:** {phase_number}
**Mode:** gap_closure

<files_to_read>
Read these files using the file_read tool:
- Validation with diagnoses: .gpd/phases/{phase_dir}/{phase}-VERIFICATION.md
- State: .gpd/STATE.md
- Roadmap: .gpd/ROADMAP.md
</files_to_read>

</planning_context>

<downstream_consumer>
Output consumed by /gpd:execute-phase
Plans must be executable prompts.
</downstream_consumer>
""",
  subagent_type="gpd-planner",
  model="{planner_model}",
  description="Plan gap fixes for Phase {phase}"
)
```

On return:

**If the planner agent fails to spawn or returns an error:** Check if any PLAN.md files were written to the phase directory. If plans exist, proceed to `verify_gap_plans`. If no plans, offer: 1) Retry planner, 2) Create fix plans manually in the main context, 3) Skip gap closure and mark gaps as deferred.

- **PLANNING COMPLETE:** Proceed to `verify_gap_plans`
- **PLANNING INCONCLUSIVE:** Report and offer manual intervention
  </step>

<step name="verify_gap_plans">
**Verify fix plans with checker:**

Display:

```
====================================================
 GPD > VERIFYING FIX PLANS
====================================================

* Spawning plan checker...
```

Initialize: `iteration_count = 1`

Spawn gpd-plan-checker:

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="""First, read {GPD_AGENTS_DIR}/gpd-plan-checker.md for your role and instructions.

<verification_context>

**Phase:** {phase_number}
**Phase Goal:** Close diagnosed gaps from research validation

<files_to_read>
Read all PLAN.md files in .gpd/phases/{phase_dir}/ using the file_read tool.
</files_to_read>

</verification_context>

<expected_output>
Return one of:
- ## VERIFICATION PASSED -- all checks pass
- ## ISSUES FOUND -- structured issue list
</expected_output>
""",
  subagent_type="gpd-plan-checker",
  model="{checker_model}",
  description="Verify Phase {phase} fix plans"
)
```

On return:

**If the plan-checker agent fails to spawn or returns an error:** Proceed without plan verification — the plans will still be executable. Note that plans were not verified and recommend running `/gpd:plan-phase --gaps` to re-verify if needed.

- **VERIFICATION PASSED:** Proceed to `present_ready`
- **ISSUES FOUND:** Proceed to `revision_loop`
  </step>

<step name="revision_loop">
**Iterate planner <-> checker until plans pass (max 3):**

**If iteration_count < 3:**

Display: `Sending back to planner for revision... (iteration {N}/3)`

Spawn gpd-planner with revision context:

> **Runtime delegation:** Omit `model` if null. Adapt to your runtime if needed.

```
task(
  prompt="""First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.

<revision_context>

**Phase:** {phase_number}
**Mode:** revision

<files_to_read>
Read all PLAN.md files in .gpd/phases/{phase_dir}/ using the file_read tool.
</files_to_read>

**Checker issues:**
{structured_issues_from_checker}

</revision_context>

<instructions>
Read existing PLAN.md files. Make targeted updates to address checker issues.
Do NOT replan from scratch unless issues are fundamental.
</instructions>
""",
  subagent_type="gpd-planner",
  model="{planner_model}",
  description="Revise Phase {phase} plans"
)
```

**If the revision planner agent fails to spawn or returns an error:** Check if any revised PLAN.md files were written to the phase directory. If revisions exist, proceed to re-check via `verify_gap_plans`. If no revisions, offer: 1) Retry revision planner, 2) Apply revisions manually in the main context, 3) Force proceed with current gap-fix plans despite checker issues.

After planner returns -> spawn checker again (verify_gap_plans logic)
Increment iteration_count

**If iteration_count >= 3:**

Display: `Max iterations reached. {N} issues remain.`

Offer options:

1. Force proceed (execute despite issues)
2. Provide guidance (researcher gives direction, retry)
3. Abandon (exit, researcher runs /gpd:plan-phase manually)

Wait for researcher response.
</step>

<step name="present_ready">
**Present completion and next steps:**

```
====================================================
 GPD > FIXES READY
====================================================

**Phase {X}: {Name}** -- {N} gap(s) diagnosed, {M} fix plan(s) created

| Gap | Root Cause | Computation Evidence | Fix Plan |
|-----|------------|---------------------|----------|
| {truth 1} | {root_cause} | {what test showed} | {phase}-04 |
| {truth 2} | {root_cause} | {what test showed} | {phase}-04 |

Plans verified and ready for execution.

---------------------------------------------------------------

## > Next Up

**Execute fixes** -- run fix plans

`/clear` then `/gpd:execute-phase {phase} --gaps-only`

---------------------------------------------------------------
```

</step>

</process>

<update_rules>
**Batched writes for efficiency:**

Keep results in memory. Write to file only when:

1. **Issue found** -- Preserve the problem immediately
2. **Session complete** -- Final write before commit
3. **Checkpoint** -- Every 5 passed checks (safety net)

| Section             | Rule      | When Written      |
| ------------------- | --------- | ----------------- |
| Frontmatter.status  | OVERWRITE | Start, complete   |
| Frontmatter.updated | OVERWRITE | On any file write |
| Current Check       | OVERWRITE | On any file write |
| Checks.{N}.result   | OVERWRITE | On any file write |
| Summary             | OVERWRITE | On any file write |
| Gaps                | APPEND    | When issue found  |

On context reset: File shows last checkpoint. Resume from there.
</update_rules>

<severity_inference>
**Infer severity from researcher's natural language:**

| Researcher says                                                 | Infer    |
| --------------------------------------------------------------- | -------- |
| "wrong sign", "diverges", "unphysical", "violates conservation" | blocker  |
| "disagrees with literature", "off by factor", "missing term"    | major    |
| "close but not exact", "small discrepancy", "approximate"       | minor    |
| "axis label", "legend", "formatting", "color"                   | cosmetic |

Default to **major** if unclear. Researcher can correct if needed.

**Never ask "how severe is this?"** - just infer and move on.
</severity_inference>

<success_criteria>

- [ ] Verification file created with all checks from SUMMARY.md, including computational test specifications
- [ ] **Minimum verification floor met**: dimensional analysis + limiting case + numerical spot-check with code execution
- [ ] **VERIFICATION.md contains at least one code output block** (actual execution result, not just text analysis)
- [ ] **Pre-computation performed** on each check before presenting to researcher
- [ ] Checks presented one at a time with expected physics outcome AND computation evidence
- [ ] **Numerical spot-checks** presented with concrete values for researcher to compare
- [ ] **Limiting cases independently re-derived** and presented to researcher for confirmation
- [ ] **Convergence data** computed and presented for numerical results
- [ ] Researcher responses processed as pass/issue/skip
- [ ] Confidence rating assigned to each passed check (independently confirmed / structurally present)
- [ ] Severity inferred from description (never asked)
- [ ] Batched writes: on issue, every 5 passes, or completion
- [ ] Committed on completion
- [ ] Cross-phase uncertainty audit performed (or N/A noted for Phase 1)
- [ ] Catastrophic cancellation check for subtracted inherited quantities
- [ ] If issues: parallel investigation agents diagnose root causes (with computation evidence)
- [ ] If issues: gpd-planner creates fix plans (gap_closure mode)
- [ ] If issues: gpd-plan-checker verifies fix plans
- [ ] If issues: revision loop until plans pass (max 3 iterations)
- [ ] Ready for `/gpd:execute-phase --gaps-only` when complete
- [ ] REQUIREMENTS.md updated for any passed checks matching REQ-IDs (if REQUIREMENTS.md exists)

</success_criteria>
