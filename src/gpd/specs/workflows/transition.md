<required_reading>

**Read these files NOW:**

1. `.gpd/STATE.md`
2. `.gpd/PROJECT.md`
3. `.gpd/ROADMAP.md`
4. Current phase's plan files (`*-PLAN.md`)
5. Current phase's summary files (`*-SUMMARY.md`)

</required_reading>

<purpose>

Mark current research phase complete and advance to next. This is the natural point where progress tracking and PROJECT.md evolution happen. Handles transitions between research phases: from analytical to numerical, from derivation to validation, from calculation to paper writing.

"Planning next phase" = "current phase is done"

</purpose>

<process>

<step name="load_project_state" priority="first">

Before transition, read project state:

```bash
for f in .gpd/STATE.md .gpd/PROJECT.md .gpd/ROADMAP.md; do
  if [ -f "$f" ]; then cat "$f"; else echo "WARNING: $f not found"; fi
done
```

Parse current position to verify we're transitioning the right phase.
Note accumulated context that may need updating after transition.

**Extract current phase variables from STATE.md:**

```bash
CURRENT_PHASE=$(grep "^Phase:" .gpd/STATE.md | head -1 | grep -oE '[0-9]+(\.[0-9]+)?' | head -1)
PHASE_DIR=$(ls -d .gpd/phases/${CURRENT_PHASE}-* 2>/dev/null | head -1)
```

These are used throughout the workflow as `${CURRENT_PHASE}` (phase number) and `${PHASE_DIR}` (full path to phase directory).

**Already-transitioned guard:** Check the ROADMAP.md checkbox for the current phase. If it already shows `[x]` with `(completed YYYY-MM-DD)`, this phase was already transitioned:

```
Phase {N} was already transitioned on {date}. Nothing to do.
```

Exit without further action. This prevents duplicate entries in DECISIONS.md and DERIVATION-STATE.md if the workflow is re-run after a context reset.

</step>

<step name="verify_completion">

Check current phase has all plan summaries:

```bash
ls ${PHASE_DIR}/*-PLAN.md 2>/dev/null | sort
ls ${PHASE_DIR}/*-SUMMARY.md 2>/dev/null | sort
```

**Verification logic:**

- Count PLAN files
- Count SUMMARY files
- If counts match: all plans complete
- If counts don't match: incomplete

<config-check>

```bash
if [ -f .gpd/config.json ]; then cat .gpd/config.json; else echo "WARNING: config.json not found — using defaults"; fi
```

</config-check>

**If all plans complete:**

<if mode="yolo">

```
>>> Auto-approved: Transition Phase [X] -> Phase [X+1]
Phase [X] complete — all [Y] plans finished.

Proceeding to mark done and advance...
```

Proceed directly to cleanup_handoff step.

</if>

<if mode="interactive" OR="custom with gates.confirm_transition true">

Ask: "Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?"

Wait for confirmation before proceeding.

</if>

**If plans incomplete:**

**SAFETY RAIL: always_confirm_destructive applies here.**
Skipping incomplete plans is destructive — ALWAYS prompt regardless of mode.

Present:

```
Phase [X] has incomplete plans:
- {phase}-01-SUMMARY.md   Complete
- {phase}-02-SUMMARY.md   Missing
- {phase}-03-SUMMARY.md   Missing

!! Safety rail: Skipping plans requires confirmation (destructive action)

Options:
1. Continue current phase (execute remaining plans)
2. Mark complete anyway (skip remaining plans — results may be incomplete)
3. Review what's left
```

Wait for user decision.

</step>

<step name="cleanup_handoff">

Check for lingering handoffs:

```bash
ls ${PHASE_DIR}/.continue-here*.md 2>/dev/null
```

If found, delete them — phase is complete, handoffs are stale.

</step>

<step name="update_roadmap_and_state">

**Delegate ROADMAP.md and STATE.md updates to gpd CLI:**

```bash
TRANSITION=$(gpd phase complete "${CURRENT_PHASE}")
if [ $? -ne 0 ]; then
  echo "STOP: phase complete failed: $TRANSITION"
  # Do not proceed — phase state may be inconsistent.
fi
```

The tool handles:

- Marking the phase checkbox as `[x]` complete with today's date
- Updating plan count to final (e.g., "3/3 plans complete")
- Updating the Progress table (Status -> Complete, adding date)
- Advancing STATE.md to next phase (Current Phase, Status -> Ready to plan, Current Plan -> Not started)
- Detecting if this is the last phase in the milestone

Extract from result: `completed_phase`, `plans_executed`, `next_phase`, `next_phase_name`, `is_last_phase`.

</step>

<step name="archive_prompts">

If prompts were generated for the phase, they stay in place within the phase directory. No archival action needed — phase directories accumulate across milestones.

</step>

<step name="evolve_project">

Evolve PROJECT.md to reflect learnings from completed phase.

**Read phase summaries:**

```bash
cat ${PHASE_DIR}/*-SUMMARY.md
```

**Assess research question changes:**

1. **Questions answered?**

   - Any Active research questions resolved in this phase?
   - Move to Answered with phase reference: `- [checkmark] [Question] — Phase X`

2. **Questions invalidated?**

   - Any Active questions discovered to be ill-posed or irrelevant?
   - Move to Out of Scope with reason: `- [Question] — [why invalidated, e.g., "gauge artifact, not physical"]`

3. **Questions emerged?**

   - Any new research questions discovered during the calculation?
   - Add to Active: `- [ ] [New question]`

4. **Decisions to log?**

   - Extract decisions from SUMMARY.md files (convention choices, method selections, approximation schemes)
   - Add to Key Decisions table with outcome if known

5. **Research context still accurate?**
   - If the understanding of the physical system has changed, update the description
   - Update key parameters if new regimes were explored
   - Keep it current and accurate

**Physics-specific evolution patterns:**

- **After analytical phase:** Log derived expressions, update "Known Results" with own results, note regime of validity
- **After numerical phase:** Log benchmark results, update computational environment notes, note convergence behavior
- **After validation phase:** Update confidence in results, note which limiting cases were checked, flag any discrepancies
- **After paper phase:** Update target venue, note submission status, log referee feedback

**Update PROJECT.md:**

Make the edits inline. Update "Last updated" footer:

```markdown
---

_Last updated: [date] after Phase [X]_
```

**Example evolution:**

Before:

```markdown
### Active

- [ ] Compute spectral gap as function of coupling g
- [ ] Determine critical exponent nu
- [ ] Check universality across lattice geometries

### Out of Scope

- Finite-temperature effects — save for v2
```

After (Phase 2 computed spectral gap, discovered anomalous scaling):

```markdown
### Answered

- [checkmark] Compute spectral gap as function of coupling g — Phase 2 (Delta ~ g^{-0.73})

### Active

- [ ] Determine critical exponent nu
- [ ] Check universality across lattice geometries
- [ ] Understand anomalous scaling exponent (0.73 vs predicted 0.75)

### Out of Scope

- Finite-temperature effects — save for v2
```

**Step complete when:**

- [ ] Phase summaries reviewed for results and learnings
- [ ] Answered questions moved from Active
- [ ] Invalidated questions moved to Out of Scope with reason
- [ ] Emerged questions added to Active
- [ ] New decisions logged with rationale (conventions, methods, approximations)
- [ ] Research context updated if understanding changed
- [ ] "Last updated" footer reflects this transition

</step>

<step name="append_decisions_log">

**Append decisions from this phase to .gpd/DECISIONS.md.**

This step captures decisions in the cumulative decision log (separate from the PROJECT.md Key Decisions table updated in evolve_project).

**1. Extract decisions from phase summaries:**

```bash
cat ${PHASE_DIR}/*-SUMMARY.md
```

Look for the `key-decisions` field in SUMMARY.md frontmatter. Also check CONTEXT.md for decisions made during planning:

```bash
cat ${PHASE_DIR}/*-CONTEXT.md 2>/dev/null
```

Collect all decisions: convention choices, method selections, approximation schemes, algorithm choices, parameter values with rationale.

**2. Check for existing entries from this phase (idempotency guard):**

```bash
EXISTING=$(grep -c "| ${CURRENT_PHASE} |" .gpd/DECISIONS.md 2>/dev/null || echo 0)
```

If `EXISTING > 0`, this phase's decisions were already logged (likely from a previous run that was interrupted after this step). Skip to the next step.

**3. Determine next decision ID:**

```bash
LAST_ID=$(grep -c '^| DEC-' .gpd/DECISIONS.md 2>/dev/null || echo 0)
```

Next ID = LAST_ID + 1, formatted as `DEC-NNN` (zero-padded to 3 digits).

**4. Create DECISIONS.md if it doesn't exist:**

If `.gpd/DECISIONS.md` doesn't exist, create it with the header from the template:

```markdown
# Decision Log

Cumulative record of research decisions. Append-only — never edit or remove past entries.

| ID  | Decision | Rationale | Alternatives Considered | Phase | Date | Impact |
| --- | -------- | --------- | ----------------------- | ----- | ---- | ------ |
```

**5. Append new entries:**

For each decision found, append a row to the table:

```markdown
| DEC-NNN | [Decision summary] | [Rationale] | [Alternatives] | [Phase number] | [Today's date] | [High/Medium/Low] |
```

**Impact classification:**

- **High:** Affects multiple phases or is irreversible (regularization scheme, gauge choice, metric signature)
- **Medium:** Affects current phase significantly (algorithm selection, truncation order)
- **Low:** Local to one calculation, easily revisited (numerical tolerance, plot style)

**6. Skip if no decisions found:**

If no decisions are present in the phase summaries or CONTEXT.md, skip this step silently. Not every phase produces logged decisions.

**Step complete when:**

- [ ] Phase SUMMARY.md and CONTEXT.md checked for decisions
- [ ] New entries appended to .gpd/DECISIONS.md (or file created)
- [ ] IDs assigned sequentially with no gaps
- [ ] Each entry has all fields filled (Decision, Rationale, Alternatives, Phase, Date, Impact)

</step>

<step name="update_current_position_after_transition">

**Note:** Basic position updates (Current Phase, Status, Current Plan, Last Activity) were already handled by `gpd phase complete` in the update_roadmap_and_state step.

Verify the updates are correct by reading STATE.md. If the progress bar needs updating, use:

```bash
PROGRESS=$(gpd --raw progress bar)
```

Update the progress bar line in STATE.md with the result.

**Step complete when:**

- [ ] Phase number incremented to next phase (done by phase complete)
- [ ] Plan status reset to "Not started" (done by phase complete)
- [ ] Status shows "Ready to plan" (done by phase complete)
- [ ] Progress bar reflects total completed plans


</step>

<step name="update_project_reference">

Update Project Reference section in STATE.md.

```markdown
## Project Reference

See: .gpd/PROJECT.md (updated [today])

**Core question:** [Current core research question from PROJECT.md]
**Current focus:** [Next phase name]
```

Update the date and current focus to reflect the transition.

</step>

<step name="review_accumulated_context">

Review and update Accumulated Context section in STATE.md.

**Key Results:**

- Note results established in this phase (specific: equations, values, plots)
- Full log lives in phase SUMMARY.md files

**Decisions:**

- Note recent decisions from this phase (3-5 max)
- Convention choices, method selections, approximation schemes
- Full log lives in DECISIONS.md

**Blockers/Concerns:**

- Review blockers from completed phase
- If addressed in this phase: Remove from list
- If still relevant for future: Keep with "Phase X" prefix
- Add any new concerns from completed phase's summaries (e.g., "series convergence questionable for g > 2")

**Example:**

Before:

```markdown
### Blockers/Concerns

- !! [Phase 1] Regularization scheme dependence not checked
- !! [Phase 2] Numerical instability at large N
```

After (if regularization was checked in Phase 3):

```markdown
### Blockers/Concerns

- !! [Phase 2] Numerical instability at large N (still present, need resummation)
```

**Step complete when:**

- [ ] Key results from this phase noted
- [ ] Recent decisions noted (full log in DECISIONS.md)
- [ ] Resolved blockers removed from list
- [ ] Unresolved blockers kept with phase prefix
- [ ] New concerns from completed phase added
- [ ] state.json synced from STATE.md

**Sync state.json after all STATE.md updates are complete:**

```bash
# Backup state.json before regeneration (never delete without backup)
if [ -f .gpd/state.json ]; then
  mv .gpd/state.json .gpd/state.json.bak
fi

gpd --raw state snapshot > /dev/null
if [ $? -ne 0 ]; then
  echo "WARNING: gpd state snapshot failed — restoring backup"
  if [ -f .gpd/state.json.bak ]; then
    mv .gpd/state.json.bak .gpd/state.json
  fi
else
  # Regeneration succeeded — remove backup
  rm -f .gpd/state.json.bak
fi
```

This is the single markdown-to-json sync point for this workflow. The backup + `gpd --raw state snapshot` sequence intentionally uses the loader's `STATE.md` fallback to merge the schema-backed markdown edits from this workflow into authoritative `state.json` while preserving JSON-only fields from the backup. Earlier steps deliberately skip syncing to avoid multiple writes.

</step>

<step name="commit_transition">

**Commit all transition changes to git.**

All planning artifacts have been updated (ROADMAP.md, STATE.md, PROJECT.md, DECISIONS.md). Commit them atomically before presenting next steps. DERIVATION-STATE.md is committed separately in the `autofill_derivation_state` step.

If DECISIONS.md doesn't exist (no decisions logged), it will be silently skipped by the commit tool.

```bash
# Run pre-commit validation on planning files
PRE_CHECK=$(gpd pre-commit-check --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/PROJECT.md 2>&1) || true
echo "$PRE_CHECK"
```

If the explicit `PRE_CHECK` command reports issues, treat it as early visibility only. `gpd commit` re-runs the same validation on the requested files and remains the blocking gate, even for metadata-only transitions.

```bash
gpd commit "docs(phase-${CURRENT_PHASE}): transition to next phase" --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/PROJECT.md .gpd/DECISIONS.md
```

If commit fails with "nothing to commit", the changes were already committed — proceed.

**Step complete when:**

- [ ] All modified `.gpd/` files committed
- [ ] Commit message references the completed phase

</step>

<step name="auto_compact_state">

**Auto-compact STATE.md if it has grown large.**

After committing the transition, check whether STATE.md has grown past the warning threshold and compact it if needed. This prevents STATE.md from bloating across many phase transitions.

```bash
AUTO_COMPACT=$(gpd state compact 2>&1)
```

**If compaction occurred** (output contains `"compacted": true`):

Commit the compacted files:

```bash
if echo "$AUTO_COMPACT" | grep -q '"compacted": true'; then
  PRE_CHECK=$(gpd pre-commit-check --files .gpd/STATE.md .gpd/STATE-ARCHIVE.md .gpd/state.json 2>&1) || true
  echo "$PRE_CHECK"

  gpd commit "chore: auto-compact state after phase-${CURRENT_PHASE} transition" --files .gpd/STATE.md .gpd/STATE-ARCHIVE.md .gpd/state.json
fi
```

**If not compacted** (within budget or nothing to archive): Proceed silently.

</step>

<step name="quick_regression_check">

**Run a quick regression check on previously verified phases.**

After committing the transition, verify that the completed phase hasn't introduced regressions in previously verified results. This catches convention redefinitions, symbol conflicts, and result inconsistencies early.

```bash
gpd regression-check --quick
```

The `--quick` flag limits the check to the most recent 2 completed phases. It:

- Reads all completed phase VERIFICATION.md files
- Checks for convention redefinitions across SUMMARYs (e.g., same symbol defined with different values)
- Reports any symbols redefined with different values
- Flags results that contradict earlier verified claims

**If issues found:**

Present them before offering next phase:

```
## Regression Check Warning

The following regressions were detected after completing Phase {X}:

| Issue | Phase | Details |
|-------|-------|---------|
| Convention redefinition | Phase {A} vs Phase {B} | Symbol `g` redefined: 0.3 → 0.5 |
| Result conflict | Phase {A} vs Phase {B} | Critical temperature differs by >5% |

Options:
1. Acknowledge and proceed (issues may be intentional updates)
2. Investigate before continuing
3. Run full regression check: `/gpd:regression-check`
```

Wait for user response before proceeding.

**If no issues found:**

Proceed silently to next step.

</step>

<step name="autofill_derivation_state">

**Extract key equations and conventions from phase SUMMARYs into DERIVATION-STATE.md.**

This ensures derivation state is captured even without explicit `/gpd:pause-work`. After phase completion, scan the phase's SUMMARY.md files for equations, conventions, and key results, then append them to `.gpd/DERIVATION-STATE.md`.

**1. Read phase summaries:**

```bash
cat ${PHASE_DIR}/*-SUMMARY.md
```

**2. Extract from SUMMARYs:**

- `conventions` frontmatter field -> convention definitions
- `## Key Results` body section -> key equations and results (use `gpd summary-extract --field key_results` to extract)
- `provides` frontmatter field -> artifacts provided by this phase

**3. Create DERIVATION-STATE.md if it doesn't exist:**

Use the same header format as pause-work.md (session-block format):

```bash
if [ ! -f .gpd/DERIVATION-STATE.md ]; then
  cat > .gpd/DERIVATION-STATE.md << 'HEADER'
# Derivation State (Cumulative)

This file is append-only. Each session or phase transition appends its equations,
conventions, and results here. This prevents lossy compression across context resets.

HEADER
fi
```

**4. Append a phase-transition session block:**

Append a `## Session:` block (same format as pause-work) capturing the phase's key results:

```bash
timestamp=$(gpd --raw timestamp full)

cat >> .gpd/DERIVATION-STATE.md << EOF

---

## Session: ${timestamp} | Phase Transition: ${PHASE_DIR}

### Equations Established
[Fill from SUMMARY key_results: LaTeX equations with units and validity ranges]

### Conventions Applied
[Fill from SUMMARY conventions frontmatter: convention choices active in this phase]

### Intermediate Results
[Fill from SUMMARY provides frontmatter: result IDs with brief descriptions]
[Mark Verified: yes if VERIFICATION.md exists with status passed, otherwise pending]

### Approximations Used
[Fill from SUMMARY approximations frontmatter if present]

EOF
```

Fill the `[Fill ...]` placeholders with actual content extracted in step 2. For each convention, check if it already appears in an earlier session block (idempotency guard — prevents duplication on re-run). Skip conventions already present with identical value. For each key result, check if a result with the same ID or expression already appears for this phase number.

**5. Skip if no extractable data:**

If the summaries have no `conventions` frontmatter or `## Key Results` body section, skip silently. Not every phase produces trackable derivation state.

**6. Commit DERIVATION-STATE.md:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/DERIVATION-STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs(phase-${CURRENT_PHASE}): autofill derivation state" --files .gpd/DERIVATION-STATE.md
```

If no DERIVATION-STATE.md was created or updated (step 5 skipped), the commit will be a no-op.

**Step complete when:**

- [ ] SUMMARY.md files scanned for conventions and key results
- [ ] New entries appended to DERIVATION-STATE.md (or file created)
- [ ] No duplicate conventions added (skip if already present with same value)
- [ ] Verified status reflects VERIFICATION.md state

</step>

<step name="update_session_continuity_after_transition">

Update Session Continuity section in STATE.md to reflect transition completion.

**Format:**

```markdown
Last session: [today]
Stopped at: Phase [X] complete, ready to plan Phase [X+1]
Resume file: —
```

**Step complete when:**

- [ ] Last session timestamp updated to current date and time
- [ ] Stopped at describes phase completion and next phase
- [ ] Resume file confirmed as `—` (transitions don't use resume files)

**Commit the session continuity update** (commit_transition already ran, so this is a follow-up commit):

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "chore: update session continuity after phase-${CURRENT_PHASE} transition" --files .gpd/STATE.md
```

</step>

<step name="identify_parallel_phases">

**Check whether upcoming phases can run in parallel.**

This step inspects the dependency graph to find phases whose `requires` are
already satisfied by completed phases. When multiple phases are unblocked at
the same time, they are candidates for parallel execution.

**1. Read the roadmap and collect completed phases:**

```bash
ROADMAP=$(gpd roadmap analyze)
if [ $? -ne 0 ]; then echo "WARNING: roadmap analyze failed — parallel phase detection may be incomplete"; fi
```

Parse the output. Build two sets:

- `completed_phases`: all phases whose status is "Complete".
- `upcoming_phases`: all phases whose status is NOT "Complete" (i.e., "Ready to plan", "Not started", etc.).

**2. Build a lightweight dependency view from SUMMARY frontmatter:**

Read phase SUMMARY files directly and extract `provides`, `requires`, and `affects` (including nested `dependency-graph.*` fields when present). Combine that metadata with explicit ROADMAP phase dependencies from step 1.

If the project has too little frontmatter metadata to infer dependencies reliably, emit a warning and fall back to sequential execution.

**3. Compute the set of all artifacts provided by completed phases:**

```
provided_artifacts = union of provides[phase] for every phase in completed_phases
```

**4. Identify unblocked upcoming phases:**

For each phase in `upcoming_phases`:

- Fetch its `requires` from the SUMMARY metadata you assembled in step 2.
- If `requires` is empty OR every entry in `requires` is present in `provided_artifacts`, the phase is **unblocked**.

Collect all unblocked phases into `ready_phases`.

**5. Read parallelization config:**

```bash
if [ -f .gpd/config.json ]; then cat .gpd/config.json; else echo "WARNING: config.json not found — parallelization defaults apply"; fi
```

Check for `"parallelization": true` in the config. If the key is absent or
set to `false`, parallelization is disabled — skip to the `offer_next_phase`
step with the lowest-numbered ready phase (sequential fallback).

**6. Branch on ready phase count:**

- **0 ready phases:** All upcoming phases have unmet dependencies. Present a
  warning listing the unmet requires and suggest the user review the roadmap.
  Do NOT proceed to `offer_next_phase`.

- **1 ready phase:** Only one phase is unblocked. Fall through to
  `offer_next_phase` with that phase (normal sequential behavior).

- **2+ ready phases AND `parallelization: true`:**

  <if mode="yolo">

  ```
  >>> Parallel execution: Phases [X], [Y], [Z] are all unblocked.
  Launching parallel execution...
  ```

  Launch parallel `/gpd:execute-phase` for each ready phase simultaneously.

  </if>

  <if mode="interactive" OR="custom with gates.confirm_transition true">

  Present to user:

  ```
  ## Parallel Phases Available

  The following phases have no blocking dependencies — all their
  `requires` are provided by already-completed phases:

  | Phase | Name               | Requires (all met)      |
  | ----- | ------------------ | ----------------------- |
  | X     | [Phase X name]     | [list or "none"]        |
  | Y     | [Phase Y name]     | [list or "none"]        |
  | Z     | [Phase Z name]     | [list or "none"]        |

  Options:
  1. Execute all in parallel (launch simultaneous /gpd:execute-phase for each)
  2. Execute sequentially starting with Phase [lowest] (standard path)
  ```

  Wait for user decision.

  - **If parallel (option 1):** Launch parallel `/gpd:execute-phase` for each
    ready phase.
  - **If sequential (option 2):** Fall through to `offer_next_phase` with the
    lowest-numbered ready phase.

  </if>

- **2+ ready phases AND `parallelization: false` (or absent):**
  Fall through to `offer_next_phase` with the lowest-numbered ready phase.
  Optionally note: "N phases are unblocked, but parallelization is disabled
  in config.json."

</step>

<parallel_phase_scheduling>

**Post-parallel consistency reconciliation.**

After parallel `/gpd:execute-phase` invocations all complete, run the
following reconciliation before advancing to the next batch of phases.

**1. Rapid cross-phase consistency check:**

```bash
gpd validate consistency
```

Additionally, for each pair of just-completed parallel phases, check:

- **Convention conflicts:** Did they adopt incompatible conventions (e.g.,
  different metric signatures, conflicting variable names, inconsistent
  notation)?

  ```bash
  cat .gpd/phases/XX-phase-a/*-SUMMARY.md .gpd/phases/YY-phase-b/*-SUMMARY.md
  ```

  Compare `conventions` fields in frontmatter. Flag any overlapping convention
  domains with differing values.

- **Result conflicts:** Did they produce inconsistent numerical or analytical
  results for the same quantity? Cross-reference `key-results` fields in
  SUMMARY frontmatter.

- **Shared-artifact conflicts:** Did they both modify the same code files,
  data files, or planning documents? Check `key_links` paths for overlap.

**2. Present reconciliation results:**

<if conflicts_found="true">

```
## Parallel Execution Reconciliation

Phases [X], [Y], [Z] completed in parallel. Conflicts detected:

### Convention Conflicts
- [Phase X] uses (+,-,-,-) metric; [Phase Y] uses (-,+,+,+) metric
  -> Must reconcile before proceeding

### Result Conflicts
- [Phase X] finds m = 1.23; [Phase Z] finds m = 1.31 for same quantity
  -> Discrepancy needs investigation

### File Conflicts
- Both [Phase X] and [Phase Y] modified `scripts/compute.py`
  -> Manual merge required

Recommend: Resolve conflicts before advancing to next batch.
```

Do NOT advance to the next batch of unblocked phases until the user
acknowledges or resolves the conflicts.

</if>

<if conflicts_found="false">

```
## Parallel Execution Reconciliation

Phases [X], [Y], [Z] completed in parallel. No conflicts detected.

- Conventions: consistent across all phases
- Results: no overlapping quantities with discrepant values
- Files: no shared modifications

Advancing to next batch of unblocked phases...
```

</if>

**3. Update provided artifacts and repeat scheduling:**

After reconciliation (with or without conflict resolution):

- Add the newly completed phases to `completed_phases`.
- Recompute `provided_artifacts` with their `provides`.
- Re-run the `identify_parallel_phases` logic to find the next batch of
  unblocked phases.
- Continue until all phases are complete or only blocked phases remain.

**Deadlock detection:**
If `ready_phases == 0` AND `in_progress_phases == 0` AND `remaining_phases > 0`:
This is a permanent deadlock — circular dependencies exist in the phase graph.

Present to user:

```
ERROR: Dependency deadlock detected.

Phases remaining: [list]
Each phase's unmet dependencies: [list]

This indicates circular dependencies in the roadmap. Options:
1. Remove a dependency to break the cycle
2. Merge the deadlocked phases into one
3. Manually mark a dependency as satisfied
```

</parallel_phase_scheduling>

<step name="offer_next_phase">

**MANDATORY: Verify milestone status before presenting next steps.**

**Use the transition result from `gpd phase complete`:**

The `is_last_phase` field from the phase complete result tells you directly:

- `is_last_phase: false` -> More phases remain -> Go to **Route A**
- `is_last_phase: true` -> Milestone complete -> Go to **Route B**

The `next_phase` and `next_phase_name` fields give you the next phase details.

If you need additional context, use:

```bash
ROADMAP=$(gpd roadmap analyze)
```

This returns all phases with goals, disk status, and completion info.

---

**Route A: More phases remain in milestone**

Read ROADMAP.md to get the next phase's name and goal.

**Detect research phase transitions** (for helpful context):

- Analytical -> Numerical: "Analytical results established. Next phase moves to numerical validation."
- Derivation -> Phenomenology: "Core derivations complete. Next phase explores parameter space."
- Calculation -> Paper: "Key results obtained. Next phase focuses on manuscript preparation."

**If next phase exists:**

<if mode="yolo">

```
Phase [X] marked complete.

Next: Phase [X+1] — [Name]
[Phase transition note if applicable]

>>> Auto-continuing: Plan Phase [X+1] in detail
```

Exit skill and invoke slash_command("/gpd:plan-phase [X+1]")

</if>

<if mode="interactive" OR="custom with gates.confirm_transition true">

```
## Phase [X] Complete

[Phase transition note if applicable, e.g.:
"Analytical derivations complete. Transitioning to numerical validation.
Key results to benchmark against: [list from SUMMARY.md]"]

---

## >> Next Up

**Phase [X+1]: [Name]** — [Goal from ROADMAP.md]

`/gpd:plan-phase [X+1]`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:discuss-phase [X+1]` — gather context first
- `/gpd:research-phase [X+1]` — investigate unknowns in literature
- Review roadmap

---
```

</if>

---

**Route B: Milestone complete (all phases done)**

<if mode="yolo">

```
Phase {X} marked complete.

Milestone {version} is 100% complete — all {N} phases finished!

>>> Auto-continuing: Complete milestone and archive
```

Exit skill and invoke slash_command("/gpd:complete-milestone {version}")

</if>

<if mode="interactive" OR="custom with gates.confirm_transition true">

```
## Phase {X}: {Phase Name} Complete

Milestone {version} is 100% complete — all {N} phases finished!

---

## >> Next Up

**Complete Milestone {version}** — archive results and prepare for next direction

`/gpd:complete-milestone {version}`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- Review all results before archiving
- `/gpd:verify-work` — systematic validation before completing milestone

---
```

</if>

</step>

</process>

<implicit_tracking>
Progress tracking is IMPLICIT: planning phase N implies phases 1-(N-1) complete. No separate progress step — forward motion IS progress.
</implicit_tracking>

<partial_completion>

If user wants to move on but phase isn't fully complete:

```
Phase [X] has incomplete plans:
- {phase}-02-PLAN.md (not executed)
- {phase}-03-PLAN.md (not executed)

Options:
1. Mark complete anyway (results may be partial)
2. Defer remaining work to later phase
3. Stay and finish current phase
```

Respect user judgment — they may realize a calculation is unnecessary or can be deferred.

**If marking complete with incomplete plans:**

- Update ROADMAP: "2/3 plans complete" (not "3/3")
- Note in transition message which plans were skipped
- If skipped plans contain validation steps, flag this explicitly: "Warning: validation plan {phase}-03 was skipped. Results from this phase are unvalidated."

</partial_completion>

<success_criteria>

Transition is complete when:

- [ ] Current phase plan summaries verified (all exist or user chose to skip)
- [ ] Any stale handoffs deleted
- [ ] ROADMAP.md updated with completion status and plan count
- [ ] PROJECT.md evolved (research questions, decisions, context if needed)
- [ ] DECISIONS.md updated with new decisions from this phase (if any)
- [ ] STATE.md updated (position, project reference, context, session)
- [ ] Progress table updated
- [ ] Auto-compact run on STATE.md (compacted and committed if over budget)
- [ ] Quick regression check run (issues presented if found)
- [ ] DERIVATION-STATE.md updated with equations/conventions from completed phase (if extractable)
- [ ] Phase transition context provided (analytical->numerical, etc.)
- [ ] User knows next steps

</success_criteria>
