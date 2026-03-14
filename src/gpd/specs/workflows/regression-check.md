<purpose>
Re-verify all previously verified physics claims, checks, and decisive evidence across completed phases to detect regressions. Finds VERIFICATION.md files, extracts VERIFIED targets, re-checks each against the current project state, and produces a regression report.

A regression is a previously VERIFIED claim, check, or decisive comparison that no longer holds given the current state of the project. Common causes: notation drift, convention changes, modified shared derivations, approximation regime violations from later phases.
</purpose>

<process>

<step name="initialize" priority="first">
**Load project context:**

```bash
INIT=$(gpd init phase-op "${PHASE_ARG:-}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `phase_found`, `phase_dir`, `phase_number` (if scoped to single phase).

**If a phase argument was provided and `phase_found` is false:**

```
ERROR: Phase not found: ${PHASE_ARG}

Available phases:
$(gpd phase list)
```

Exit.

If no phase argument, load full project state:

```bash
PROGRESS=$(gpd init progress --include state,roadmap,config)
gpd roadmap analyze
```

Parse `project_exists` and `state_exists` from PROGRESS JSON.
Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context regression-check "${PHASE_ARG:-}")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Determine scope:

- **Single phase:** Re-check verified targets only from that phase's VERIFICATION.md
- **All phases:** Re-check verified targets from all completed phases
  </step>

<step name="chunking_strategy">
**Determine batch size for context management.**

For projects with many phases (10+), reading all VERIFICATION.md files at once can blow the context window. Process phases in batches to stay within limits.

```bash
PHASE_COUNT=$(find .gpd/phases -name "*-VERIFICATION.md" -type f 2>/dev/null | wc -l | tr -d ' ')
echo "Found $PHASE_COUNT VERIFICATION.md files"
```

**Batching rules:**

- **1-5 phases:** Process all at once (no batching needed)
- **6-10 phases:** Process in batches of 5
- **11+ phases:** Process in batches of 3

**Batch processing protocol:**

1. Divide phases into batches (sorted numerically by phase number)
2. For each batch:
   a. Read the VERIFICATION.md files in the batch
   b. Extract verified targets and run re-checks (steps discover_verifications through recheck_remaining)
   c. Record batch results: `{still_verified: N, regressions: [...], needs_recheck: [...]}`
   d. Release the batch file contents from working memory before loading the next batch
3. After all batches complete, merge the running tallies into a single result set
4. Proceed to classify_regressions with the merged results

**Running tally structure:**

```
tally = {
  phases_checked: 0,
  targets_checked: 0,
  still_verified: 0,
  regressions: [],       # accumulated across batches
  needs_recheck: [],     # accumulated across batches
  batch_summaries: []    # one-line summary per batch for the final report
}
```

If running in single-phase scope, skip batching entirely.
</step>

<step name="discover_verifications">
**Find all VERIFICATION.md files:**

```bash
find .gpd/phases -name "*-VERIFICATION.md" -type f 2>/dev/null | sort
```

For each file, read frontmatter to check status:

```bash
gpd frontmatter get "$VERIF_FILE" --field status
```

**Filter:**

- Include files with `status: passed` or `status: gaps_found` (both contain verified targets)
- Skip files with `status: human_needed` that have no VERIFIED targets
- If scoped to a single phase, filter to that phase directory only

Build verification inventory:

```
| Phase | VERIFICATION.md Path | Status | Verified Truths Count |
|-------|---------------------|--------|----------------------|
| 01-setup | .gpd/phases/01-setup/01-VERIFICATION.md | passed | 5 |
| 02-derivation | .gpd/phases/02-derivation/02-VERIFICATION.md | passed | 7 |
| 03-numerics | .gpd/phases/03-numerics/03-VERIFICATION.md | gaps_found | 4 |
```

**If batching is active:** Only load the current batch's files. Update the running tally after processing each batch.

If no VERIFICATION.md files found:

```
No completed verifications found. Nothing to regression-check.

Run /gpd:verify-work <phase> to verify a completed phase first.
```

Exit.
</step>

<step name="extract_verified_targets">
**Extract all verified targets from each VERIFICATION.md:**

Read each file's contract-target coverage and verified-outcomes sections:

```markdown
## Contract Coverage

| ID                 | Kind  | Expectation                                          | Status   | Evidence                         |
| ------------------ | ----- | ---------------------------------------------------- | -------- | -------------------------------- |
| claim-dispersion   | claim | Dispersion relation is correct in all limiting cases | VERIFIED | derivation.tex + limits_check.py |
| claim-spectrum     | claim | Energy spectrum matches exact diagonalization for N=8| VERIFIED | exact_diag_comparison.py         |
| claim-sum-rule     | claim | Spectral function satisfies sum rule                 | FAILED   | ...                              |
```

**Extract only targets with status: VERIFIED.**

Also extract from each VERIFICATION.md:

- **Dimensional Analysis** section -- equations that were checked
- **Limiting Cases** section -- limits that were verified (status: PASS)
- **Symmetry Checks** section -- symmetries that were confirmed
- **Conservation Laws** section -- conservation laws verified
- **Required Artifacts** section -- artifacts confirmed to exist

Build master target registry:

```
targets = [
  {
    phase: "01-setup",
    number: 1,
    expectation: "Hamiltonian dimensions are [Energy]",
    evidence: "dimensional_check.md",
    verification_file: ".gpd/phases/01-setup/01-VERIFICATION.md",
    category: "dimensional"
  },
  {
    phase: "02-derivation",
    number: 1,
    expectation: "Dispersion relation is correct in all limiting cases",
    evidence: "derivation.tex + limits_check.py",
    verification_file: ".gpd/phases/02-derivation/02-VERIFICATION.md",
    category: "limiting_case"
  },
  ...
]
```

Categorize each target:

- **dimensional** -- Claims about dimensions/units
- **limiting_case** -- Claims about behavior in specific limits
- **symmetry** -- Claims about symmetry properties
- **conservation** -- Claims about conserved quantities
- **numerical** -- Claims about numerical results or convergence
- **artifact** -- Claims about existence/content of specific files
- **analytical** -- Claims about analytical derivations or equations
- **comparison** -- Claims about agreement with literature

Display extraction summary:

```
====================================================
 GPD > REGRESSION CHECK
====================================================

Extracted {N} verified targets from {M} phases:

| Category | Count |
|----------|-------|
| dimensional | 5 |
| limiting_case | 8 |
| symmetry | 3 |
| conservation | 4 |
| numerical | 6 |
| artifact | 7 |
| analytical | 4 |
| comparison | 3 |

Re-checking all targets against current project state...
```

</step>

<step name="recheck_artifacts">
**Re-check artifact-backed targets first (fast, filesystem-only):**

For each target with category `artifact`:

1. Parse the evidence field for file paths
2. Check each path still exists:
   ```bash
   gpd verify-path "$ARTIFACT_PATH"
   ```
3. If the file exists, check it is substantive (not a stub):
   ```bash
   wc -l "$ARTIFACT_PATH"
   ```
4. Check the file was not modified after the verification timestamp:
   ```bash
   git log --oneline --since="$VERIFICATION_DATE" -- "$ARTIFACT_PATH" 2>/dev/null | head -5
   ```

**Status assignment:**

- File exists, unchanged since verification -> **STILL_VERIFIED**
- File exists, modified since verification -> **NEEDS_RECHECK** (content may have changed)
- File missing -> **REGRESSION** (artifact deleted or moved)
- File is now a stub (< 5 lines where it was substantive) -> **REGRESSION**
  </step>

<step name="recheck_dimensional">
**Re-check dimensional targets:**

For each target with category `dimensional`:

1. Locate the equation or expression referenced in the evidence
2. Read the current version of the file containing the expression
3. Verify dimensions still hold by:

   - Checking the expression hasn't been modified (git diff against verification commit)
   - If modified: re-derive dimensions term by term
   - Cross-reference against STATE.md "Convention Lock" for unit system consistency

4. Check for convention changes since verification:
   ```bash
   find .gpd/phases -type f \( -name "SUMMARY.md" -o -name "*-SUMMARY.md" \) -exec grep -l "Convention Change\|unit system\|natural units\|hbar\s*=" {} + 2>/dev/null
   ```

**Status assignment:**

- Expression unchanged, conventions unchanged -> **STILL_VERIFIED**
- Expression unchanged, but convention changed in later phase -> **NEEDS_RECHECK**
- Expression modified -> **NEEDS_RECHECK** (must re-derive dimensions)
- Dimensional inconsistency found -> **REGRESSION**
  </step>

<step name="recheck_limiting_cases">
**Re-check limiting-case targets:**

For each target with category `limiting_case`:

1. Identify the result and the limit from the target expectation
2. Read the current version of the derivation or computation
3. Check if the result expression has been modified since verification
4. Check if any upstream dependency was modified:
   ```bash
   # Find files the derivation depends on
   grep -l "import\|\\\\input\|@" "$DERIVATION_FILE" 2>/dev/null
   ```
5. Check if the parameter regime has changed in later phases:
   - Read STATE.md "Active Approximations" table
   - Compare parameter values against validity ranges assumed in the limit

**Status assignment:**

- Result unchanged, dependencies unchanged, regime still valid -> **STILL_VERIFIED**
- Result or dependencies modified -> **NEEDS_RECHECK**
- Parameter regime now outside validity range of the limit -> **REGRESSION**
  </step>

<step name="recheck_cross_phase">
**Cross-phase consistency re-check:**

This is the most important regression check -- later phases can silently break earlier ones.

1. **Notation consistency:**
   Read STATE.md "Convention Lock" and each phase's summary artifact (`SUMMARY.md` or `*-SUMMARY.md`) "Convention Changes" section.
   For each verified target, check that symbols used in the target expectation still mean the same thing:

   ```bash
   find .gpd/phases -type f \( -name "SUMMARY.md" -o -name "*-SUMMARY.md" \) -exec grep -n "$SYMBOL" {} + 2>/dev/null
   ```

   Flag if a symbol was redefined in a later phase.

2. **Approximation regime overlap:**
   For each verified target that assumes a specific regime (e.g., "valid for T >> Tc"):

   - Check if later phases explored parameter values outside that regime
   - Check STATE.md "Active Approximations" for regime updates

3. **Shared derivation integrity:**
   For verified targets that depend on shared derivations or results from other phases:
   - Check if the upstream result was modified after the downstream verification
   ```bash
   git log --oneline --since="$DOWNSTREAM_VERIFICATION_DATE" -- "$UPSTREAM_FILE" 2>/dev/null
   ```

**Status assignment:**

- No notation drift, regime still valid, upstream unchanged -> **STILL_VERIFIED**
- Notation inconsistency detected -> **REGRESSION** (severity: MINOR if cosmetic, MAJOR if semantic)
- Regime violation detected -> **REGRESSION** (severity: CRITICAL)
- Upstream modified -> **NEEDS_RECHECK**
  </step>

<step name="recheck_cross_phase_consistency">
## Cross-Phase Consistency Check

After re-verifying individual targets, run a rapid cross-phase consistency check:

For each target whose supporting artifacts were modified since last verification:
1. Trace the provides/consumes chain across phases
2. Verify convention consistency at each transfer point
3. Check that sign conventions, unit systems, and normalization match

This catches compensating errors where two changes individually preserve local checks but together break cross-phase transfers.

Use the convention diff to compare the last verified phase against the current phase:
```bash
gpd convention diff <last-verified-phase> <current-phase>
```
</step>

<step name="recheck_remaining">
**Re-check symmetry, conservation, numerical, analytical, and comparison targets:**

For each remaining target:

1. Locate the supporting evidence (files referenced in the Evidence column)
2. Check if the evidence files were modified since verification:
   ```bash
   git log --oneline --since="$VERIFICATION_DATE" -- "$EVIDENCE_PATH" 2>/dev/null
   ```
3. If modified, read the current content and assess whether the previously verified target still holds
4. For numerical targets: check if computation code or input parameters changed
5. For comparison targets: check if the result being compared changed

**Status assignment:**

- Evidence unchanged -> **STILL_VERIFIED**
- Evidence modified but the target still holds on re-examination -> **STILL_VERIFIED** (note: "re-confirmed after modification")
- Evidence modified and the target no longer holds -> **REGRESSION**
- Evidence modified, cannot determine -> **NEEDS_RECHECK**
  </step>

<step name="classify_regressions">
**Classify each regression by severity:**

| Regression Type                | Default Severity | Override Conditions                               |
| ------------------------------ | ---------------- | ------------------------------------------------- |
| Artifact missing               | MAJOR            | CRITICAL if downstream phases depend on it        |
| Dimensional inconsistency      | CRITICAL         | Always critical                                   |
| Limiting case failure          | CRITICAL         | MAJOR if the limit is non-essential               |
| Notation drift (semantic)      | MAJOR            | CRITICAL if equations were combined across phases |
| Notation drift (cosmetic)      | MINOR            | --                                                |
| Approximation regime violation | CRITICAL         | MAJOR if violation is marginal (within 10%)       |
| Upstream result modified       | MAJOR            | CRITICAL if it changes the conclusion             |
| Numerical result changed       | MAJOR            | MINOR if within original error bars               |
| Conservation law broken        | CRITICAL         | Always critical                                   |
| Symmetry broken                | CRITICAL         | MAJOR if approximate symmetry                     |

**For each regression, determine affected phases:**

A regression in phase N may affect phases N+1, N+2, ... if they consume results from phase N. Trace the dependency chain:

```bash
# Check which later phases reference this phase's results
find .gpd/phases -type f \( -name "SUMMARY.md" -o -name "*-SUMMARY.md" \) -exec grep -rl "phase.*${PHASE_NUM}\|${PHASE_NAME}" {} + 2>/dev/null
```

</step>

<step name="generate_report">
**Generate `.gpd/REGRESSION-REPORT.md`:**

```markdown
---
checked: YYYY-MM-DDTHH:MM:SSZ
scope: all | phase-{N}
phases_checked: N
targets_checked: M
regressions_found: K
needs_recheck: J
status: clean | regressions_found
---

# Regression Report

**Checked:** {timestamp}
**Scope:** {all phases | phase N only}
**Status:** {clean | regressions_found}

## Summary

| Metric               | Count |
| -------------------- | ----- |
| Phases checked       | {N}   |
| Targets re-verified  | {M}   |
| Still verified       | {V}   |
| Regressions found    | {K}   |
| Needs manual recheck | {J}   |

## Regressions

{If no regressions:}
**No regressions detected.** All {M} verified targets still hold against the current project state.

{If regressions found:}

### CRITICAL

| #   | Phase   | Target            | Regression Type | Details        | Affected Phases     |
| --- | ------- | ----------------- | --------------- | -------------- | ------------------- |
| 1   | {phase} | {target summary}  | {type}          | {what changed} | {downstream phases} |

### MAJOR

| #   | Phase   | Target            | Regression Type | Details        | Affected Phases     |
| --- | ------- | ----------------- | --------------- | -------------- | ------------------- |
| 1   | {phase} | {target summary}  | {type}          | {what changed} | {downstream phases} |

### MINOR

| #   | Phase   | Target            | Regression Type | Details        | Affected Phases     |
| --- | ------- | ----------------- | --------------- | -------------- | ------------------- |
| 1   | {phase} | {target summary}  | {type}          | {what changed} | {downstream phases} |

## Needs Manual Recheck

| #   | Phase   | Target            | Reason                                |
| --- | ------- | ----------------- | ------------------------------------- |
| 1   | {phase} | {target summary}  | {why automated check is insufficient} |

## Phase Impact Map

{Show which phases are affected by regressions:}

| Phase         | Own Regressions | Upstream Regressions | Total Impact | Recommended Action       |
| ------------- | --------------- | -------------------- | ------------ | ------------------------ |
| 01-setup      | 0               | 0                    | clean        | --                       |
| 02-derivation | 1 CRITICAL      | 0                    | blocked      | re-verify phase          |
| 03-numerics   | 0               | 1 CRITICAL (from 02) | blocked      | re-verify after 02 fixed |

## Recommended Fix Order

{If regressions found, suggest fix order based on dependency chain:}

1. **Phase {X}: {fix description}** -- fixes {N} CRITICAL regressions, unblocks phases {Y, Z}
2. **Phase {Y}: {fix description}** -- fixes {M} MAJOR regressions after phase X is fixed
3. **Re-run `/gpd:regression-check`** -- confirm all regressions resolved

## Detailed Regression Analysis

### Regression {N}: {Brief title}

- **Phase:** {phase number and name}
- **Target:** {the verified claim, deliverable, or check that regressed}
- **Category:** {dimensional | limiting_case | symmetry | ...}
- **Original verification:** {date from VERIFICATION.md}
- **What changed:** {specific description of what broke the target}
- **Evidence:**
  - Original: {what the verification found}
  - Current: {what the re-check found}
- **Severity:** {CRITICAL | MAJOR | MINOR}
- **Affected downstream phases:** {list}
- **Recommended fix:** {specific action to restore the target}

---

_Generated: {timestamp}_
_Scope: {all | phase N}_
```

Write the report:

```bash
mkdir -p .gpd
```

Write to `.gpd/REGRESSION-REPORT.md`.

Commit:

```bash
PRE_CHECK=$(gpd pre-commit-check --files ".gpd/REGRESSION-REPORT.md" 2>&1) || true
echo "$PRE_CHECK"

gpd commit "verify: regression check - {V}/{M} verified targets hold, {K} regressions" --files ".gpd/REGRESSION-REPORT.md"
```

</step>

<step name="present_results">
**Present results to researcher:**

**If clean (no regressions):**

```
====================================================
 GPD > REGRESSION CHECK: CLEAN
====================================================

Re-verified {M} targets across {N} phases.
All previously verified results still hold.

Report: .gpd/REGRESSION-REPORT.md
```

**If regressions found:**

```
====================================================
 GPD > REGRESSION CHECK: {K} REGRESSIONS FOUND
====================================================

Re-verified {M} targets across {N} phases.

| Severity | Count |
|----------|-------|
| CRITICAL | {C}   |
| MAJOR    | {J}   |
| MINOR    | {I}   |

{For each CRITICAL regression:}
**CRITICAL: Phase {X} -- {target}**
  {what changed} -> affects phases {downstream}

Report: .gpd/REGRESSION-REPORT.md

---------------------------------------------------------------

## > Recommended Next Steps

{If CRITICAL regressions:}
1. Fix critical regressions first (see report for fix order)
2. `/gpd:verify-work {affected_phase}` -- re-verify affected phases
3. `/gpd:regression-check` -- confirm all regressions resolved

{If only MAJOR/MINOR:}
1. Review regressions in report
2. `/gpd:verify-work {affected_phase}` -- re-verify flagged phases
3. `/gpd:regression-check` -- confirm clean

---------------------------------------------------------------
```

</step>

</process>

<success_criteria>

- [ ] Chunking strategy determined based on phase count (batches of 3-5 for 6+ phases)
- [ ] All VERIFICATION.md files discovered and inventoried
- [ ] All VERIFIED targets extracted with category and evidence
- [ ] Artifact integrity checked (existence, modification, substantiveness)
- [ ] Dimensional targets re-checked against current conventions
- [ ] Limiting-case targets re-checked against current parameter regimes
- [ ] Cross-phase consistency verified (notation, approximations, shared derivations)
- [ ] Remaining targets re-checked against current evidence files
- [ ] Regressions classified by severity (CRITICAL / MAJOR / MINOR)
- [ ] Affected downstream phases identified for each regression
- [ ] REGRESSION-REPORT.md generated with full results
- [ ] Report committed
- [ ] Results presented with recommended next steps

</success_criteria>
