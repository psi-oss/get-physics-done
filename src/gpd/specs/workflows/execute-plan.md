<purpose>
Execute a research plan (PLAN.md) -- carry out derivations, calculations, simulations, or analysis -- and create the outcome summary (SUMMARY.md).
</purpose>

<required_reading>
Read STATE.md before any operation to load project context.
Read config.json for planning behavior settings.

Read these reference files using the Read tool:
- {GPD_INSTALL_DIR}/references/git-integration.md
- {GPD_INSTALL_DIR}/references/execute-plan-recovery.md
- {GPD_INSTALL_DIR}/references/execute-plan-validation.md
- {GPD_INSTALL_DIR}/references/execute-plan-checkpoints.md
- {GPD_INSTALL_DIR}/references/reproducibility.md
- {GPD_INSTALL_DIR}/references/error-propagation-protocol.md -- Cross-phase uncertainty propagation protocol (Uncertainty Budget declaration format, verification checks, phase handoff format)
- {GPD_INSTALL_DIR}/references/executor-index.md -- Maps execution scenarios (QFT, condensed matter, numerical, paper writing, debugging) to the correct domain-specific reference files
- {GPD_INSTALL_DIR}/templates/calculation-log.md -- Template for CALCULATION_LOG.md (detailed derivation records within a phase)
- {GPD_INSTALL_DIR}/templates/recovery-plan.md -- Template for RECOVERY.md (structured recovery after plan execution failure)
</required_reading>

<process>

<step name="init_context" priority="first">
Load execution context (uses `init execute-phase` for full context, including file contents):

```bash
INIT=$(gpd init execute-phase "${phase}" --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  exit 1
fi
```

Extract from init JSON: `executor_model`, `commit_docs`, `phase_dir`, `phase_number`, `plans`, `summaries`, `incomplete_plans`.

**File contents (from --include):** `state_content`, `config_content`. Access with:

```bash
STATE_CONTENT=$(echo "$INIT" | gpd json get .state_content --default "")
CONFIG_CONTENT=$(echo "$INIT" | gpd json get .config_content --default "")
```

If `.planning/` missing: error.
</step>

<step name="verify_conventions">
Before execution, verify convention lock is consistent and non-empty:

```bash
CONV_CHECK=$(gpd convention check --raw)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — review before executing"
  echo "$CONV_CHECK"
fi
```

If the project has existing phases and the convention lock is empty, this is an error. Conventions must be established before execution proceeds.

**Load authoritative conventions** (canonical protocol from `agent-infrastructure.md`):

```bash
CONVENTIONS=$(gpd convention list --raw 2>/dev/null)
```

Single source of truth is `state.json` convention_lock. Before using any equation from a prior phase or external source, verify conventions match the lock. See `shared-protocols.md` Convention Tracking Protocol for the 5-point checklist (metric, Fourier, normalization, coupling, renormalization scheme).
</step>

<step name="identify_plan">
```bash
# Use plans/summaries from INIT JSON, or list files
ls "${phase_dir}"/*-PLAN.md 2>/dev/null | sort
ls "${phase_dir}"/*-SUMMARY.md 2>/dev/null | sort
```

Find first PLAN without matching SUMMARY. Decimal phases supported (`01.1-hotfix/`):

```bash
phase=$(echo "$PLAN_PATH" | grep -oE '[0-9]+(\.[0-9]+)?-[0-9]+')
# config_content already loaded via --include config in init_context
```

<if mode="yolo">
Auto-approve: `>> Execute {phase}-{plan}-PLAN.md [Plan X of Y for Phase Z]` -> parse_segments.
</if>

<if mode="interactive" OR="custom with gates.execute_next_plan true">
Present plan identification, wait for confirmation.
</if>
</step>

<step name="record_start_time">
```bash
PLAN_START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PLAN_START_EPOCH=$(date +%s)
```

Start execution trace for debugging (if trace module available):

```bash
gpd trace start "${phase}" "${plan}" 2>/dev/null || true
```
</step>

<step name="resolve_autonomy_mode">
Read autonomy mode from init JSON to control checkpoint frequency throughout execution:

```bash
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default guided)
```

**Checkpoint behavior by mode:**

| Mode | Task Checkpoints | Physics Decision Checkpoints | Verification Failure |
|------|-----------------|------------------------------|---------------------|
| **supervised** | After EVERY task | Always | Always stop |
| **guided** (default) | None (auto tasks flow) | On physics choices (deviation rules 5-6, approximation selection, convention conflict) | Always stop |
| **autonomous** | None | Only on deviation rules 5-6 and convergence failure after 3 attempts | Always stop |
| **yolo** | None | None (attempt one alternative before escalating) | Stop only on unrecoverable errors |

</step>

<step name="create_checkpoint">
Create a git checkpoint tag before plan execution. See `execute-plan-checkpoints.md` for full protocol.

```bash
CHECKPOINT_TAG="gpd-checkpoint/phase-${phase}-plan-${plan}-$(date +%s)"
git tag "${CHECKPOINT_TAG}"
```
</step>

<step name="detect_previous_attempt">
Check for prior commits from this plan. See `execute-plan-checkpoints.md` for full detection and resume protocol.

```bash
PRIOR_COMMITS=$(git log --oneline --grep="(${phase}-${plan}):" | head -20)
```

If prior commits found: offer resume or fresh start. If none: proceed normally.
</step>

<step name="parse_segments">
```bash
grep -n "type=\"checkpoint" "${phase_dir}/${phase}-${plan}-PLAN.md"
```

**Routing by checkpoint type:**

| Checkpoints | Pattern        | Execution                                                                                              |
| ----------- | -------------- | ------------------------------------------------------------------------------------------------------ |
| None        | A (autonomous) | Single subagent: full plan + SUMMARY + commit                                                          |
| Verify-only | B (segmented)  | Segments between checkpoints. After none/human-verify -> SUBAGENT. After decision/human-action -> MAIN |
| Decision    | C (main)       | Execute entirely in main context                                                                       |

**Pattern A:** init_agent_tracking -> spawn Task(subagent_type="gpd-executor", model=executor_model) with prompt: execute plan at [path], all tasks + SUMMARY + commit, follow deviation/validation rules, **load conventions from `gpd convention list` before starting work**, `<autonomy_mode>{AUTONOMY}</autonomy_mode>` (controls checkpoint frequency and decision authority — see gpd-executor.md autonomy_modes section), report: plan name, tasks, SUMMARY path, commit hash -> track agent_id -> wait -> update tracking -> report.

**If the executor agent fails to spawn or returns an error (Pattern A):** Check if any work was committed (`git log --oneline -3`). If commits with the plan's work exist, the executor may have completed but failed to report — verify output files and proceed to post-execution checks. If no work was done, offer: 1) Retry executor spawn, 2) Fall back to Pattern C (execute in main context), 3) Abort. Update agent tracking status to "failed" with error details.

**Pattern B:** Execute segment-by-segment. Autonomous segments: spawn subagent for assigned tasks only (no SUMMARY/commit). Checkpoints: main context. After all segments: aggregate, create SUMMARY, commit. See segment_execution.

**If a segment executor fails to spawn or returns an error (Pattern B):** Check if the segment's tasks produced any output files. If work exists, proceed to the next segment. If no work, offer: 1) Retry this segment, 2) Execute the segment's tasks in the main context, 3) Skip this segment and continue. Do not abort the entire plan for a single segment failure. Record the failure in agent tracking.

**Pattern C:** Execute in main using standard flow (step name="execute").

Fresh context per subagent preserves peak quality. Main context stays lean.
</step>

<step name="init_agent_tracking">
```bash
if [ ! -f .planning/agent-history.json ]; then
  echo '{"version":"1.0","max_entries":50,"entries":[]}' > .planning/agent-history.json
fi
if [ -f .planning/current-agent-id.txt ]; then
  INTERRUPTED_ID=$(cat .planning/current-agent-id.txt)
  echo "Found interrupted agent: $INTERRUPTED_ID"
fi
```

If interrupted: ask user to resume (Task `resume` parameter) or start fresh.

**Tracking protocol:** On spawn: write agent_id to `current-agent-id.txt`, append to agent-history.json: `{"agent_id":"[id]","task_description":"[desc]","phase":"[phase]","plan":"[plan]","segment":[num|null],"timestamp":"[ISO]","status":"spawned","completion_timestamp":null}`. On completion: status -> "completed", set completion_timestamp, delete current-agent-id.txt. Prune: if entries > max_entries, remove oldest "completed" (never "spawned").

Run for Pattern A/B before spawning. Pattern C: skip.
</step>

<step name="segment_execution">
Pattern B only (verify-only checkpoints). Skip for A/C.

1. Parse segment map: checkpoint locations and types
2. Per segment:
   - Subagent route: spawn gpd-executor for assigned tasks only. Prompt: task range, plan path, read full plan for context, execute assigned tasks, track deviations, `<autonomy_mode>{AUTONOMY}</autonomy_mode>`, NO SUMMARY/commit. Track via agent protocol.
   - Main route: execute tasks using standard flow (step name="execute")
3. After ALL segments: aggregate files/deviations/decisions -> create SUMMARY.md -> commit -> self-check:

   - Verify key-files.created exist on disk with `[ -f ]`
   - Check `git log --oneline --grep="{phase}-{plan}"` returns >=1 commit
   - Append `## Self-Check: PASSED` or `## Self-Check: FAILED` to SUMMARY
   - Run physics validation checks (dimensional consistency, limiting cases) -> Append `## Validation: PASSED` or `## Validation: FAILED`

   > **Known bug workaround:** The `classifyHandoffIfNeeded` bug may report successful subagents as failed. Always spot-check output files and git commits before treating a result as failed. See `{GPD_INSTALL_DIR}/references/known-bugs.md` §1 for details.

</step>

<step name="load_prompt">
```bash
cat "${phase_dir}/${phase}-${plan}-PLAN.md"
```
This IS the execution instructions. Follow exactly. If plan references CONTEXT.md: honor user's research direction throughout.
</step>

<step name="previous_phase_check">
```bash
ls .planning/phases/*/*-SUMMARY.md 2>/dev/null | sort -r | head -2 | tail -1
```
> **Platform note:** If `AskUserQuestion` is not available, present these options in plain text and wait for the user's freeform response.

If previous SUMMARY has unresolved "Issues Encountered" or "Next Phase Readiness" blockers: AskUserQuestion(header="Previous Issues", options: "Proceed anyway" | "Address first" | "Review previous").
</step>

<step name="execute">
Deviations are normal -- handle via deviation rules in `execute-plan-validation.md`.

1. Read @context files from prompt
2. Per task:
   - `type="auto"`: Execute derivation/calculation/simulation. Verify done criteria including dimensional checks. Commit (see task_commit). Track hash for Summary.
     ```bash
     gpd trace log checkpoint --data "{\"description\":\"Task ${TASK_NUM} done: ${TASK_DESCRIPTION}\"}" 2>/dev/null || true
     ```
     **Supervised mode post-task checkpoint:** If `AUTONOMY="supervised"`, insert a `checkpoint:human-verify` after EVERY completed task. Present the task result with all intermediate values and wait for user approval before proceeding to the next task.
   - `type="checkpoint:*"`: Route by autonomy mode:
     - **supervised/guided:** STOP -> checkpoint protocol (see `execute-plan-checkpoints.md`) -> wait for user -> continue only after confirmation.
     - **autonomous:** Skip `checkpoint:human-verify` types. Stop only for `checkpoint:decision` if it involves deviation rules 5-6 or convergence failure. All other checkpoints are logged but execution continues.
     - **yolo:** Skip ALL checkpoint types. Log checkpoint events to trace but never stop. Only hard stops: unrecoverable computation error, context pressure RED, or explicit STOP in plan.
3. Run `<verification>` checks including physics validation (see `execute-plan-validation.md`)
   ```bash
   gpd trace log assertion --data "{\"description\":\"Verification: ${VERIFICATION_RESULT}\"}" 2>/dev/null || true
   ```
4. Confirm `<success_criteria>` met
5. Document deviations in Summary

**Context awareness (after each task):**

Context is finite (~200k tokens, ~80% usable). After completing each task:

1. Check statusline context percentage
2. If >60% with heavy work remaining: consider proactive pause
3. If >80%: save intermediate results and trigger `$gpd-pause-work` before quality degrades

Signs of context pressure: re-reading files you already read, losing track of parameter values or sign conventions, derivation steps getting sloppy. A fresh context with saved state outperforms a saturated one.

If pausing mid-plan: commit current work, create `.continue-here.md` with full derivation state, recommend `/clear` + `$gpd-resume-work`. See `{GPD_INSTALL_DIR}/references/context-budget.md` for budget guidelines.

**Auto-checkpoint protocol (autonomy-aware):**

After completing each task, check context usage. Checkpoint frequency varies by autonomy mode:

| Mode | Context checkpoint at 60% | Context checkpoint at 75% | Verification failure |
|------|--------------------------|--------------------------|---------------------|
| **supervised** | Yes + present to user | Yes + force pause + user approval | Always stop, present details |
| **guided** | Yes (write silently) | Yes + proactive pause | Always stop, present details |
| **autonomous** | Yes (write silently) | Yes + proactive pause (no user prompt, auto-resume if possible) | Stop only on deviation rules 5-6 |
| **yolo** | Write checkpoint file only | Auto-pause only at context RED (>85%) | Stop only on unrecoverable error |

1. Write auto-checkpoint to phase directory:
```bash
cat > "${phase_dir}/auto-checkpoint.json" << CHECKPOINT
{
  "task_completed": "${CURRENT_TASK}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "key_results": "${KEY_RESULTS_SO_FAR}",
  "autonomy_mode": "${AUTONOMY}"
}
CHECKPOINT
```

2. If above 75% (or 85% in yolo mode): Proactively trigger pause protocol:
   - Commit all current work
   - Create `.continue-here.md` with full derivation state
   - Update STATE.md session info
   - **supervised/guided:** Suggest `/clear` + `$gpd-resume-work`
   - **autonomous/yolo:** Auto-trigger `$gpd-resume-work` if context allows (otherwise suggest `/clear`)

This prevents quality degradation and ensures no work is lost if the session ends unexpectedly.
</step>

<task_commit>

## Task Commit Protocol

After each task (verification passed, done criteria met), commit immediately.

**1. Check:** `git status --short`

**2. Stage individually** (NEVER `git add .` or `git add -A`):

```bash
git add src/derivations/hamiltonian.py
git add results/spectrum.json
```

**3. Commit type:**

| Type       | When                                       | Example                                                             |
| ---------- | ------------------------------------------ | ------------------------------------------------------------------- |
| `calc`     | New derivation or calculation              | calc(08-02): derive spin-wave dispersion relation                   |
| `fix`      | Error correction                           | fix(08-02): correct sign in exchange coupling term                  |
| `verify`   | Verification or cross-check                | verify(08-02): verify Goldstone theorem in broken-symmetry phase    |
| `simplify` | Reorganization or simplification           | simplify(08-02): consolidate dispersion branches into matrix form   |
| `sim`      | Simulation or numerical computation        | sim(08-02): compute ground state energy via exact diagonalization   |
| `data`     | Data analysis, fitting, or processing      | data(08-02): extract critical exponents from scaling collapse       |
| `docs`     | Documentation or writeup                   | docs(08-02): document perturbation expansion to third order         |
| `chore`    | Config/deps/setup                          | chore(08-02): add QuTiP dependency                                  |

**4. Format:** `{type}({phase}-{plan}): {description}` with bullet points for key changes.

**5. Pre-commit validation** runs automatically inside `gpd commit`. If it fails (NaN in state.json, missing frontmatter fields), the commit is blocked — fix the errors and retry.

**6. Record hash:**

```bash
TASK_COMMIT=$(git rev-parse --short HEAD)
TASK_COMMITS+=("Task ${TASK_NUM}: ${TASK_COMMIT}")
```

**6. Persist commit hash to disk (crash resilience):**

The in-memory `TASK_COMMITS` array is lost if the agent crashes. Write each hash to a JSON file as it is created:

```bash
# Pattern A/C: shared file (single writer, no race)
# Pattern B: per-segment file to avoid concurrent read-modify-write corruption
if [ -n "${SEGMENT_NUM:-}" ]; then
  COMMITS_FILE="${phase_dir}/plan-commits-seg-${SEGMENT_NUM}.json"
else
  COMMITS_FILE="${phase_dir}/plan-commits.json"
fi

# Append this task's commit hash (atomic JSON update)
gpd json set --file "$COMMITS_FILE" --path "task_${TASK_NUM}" --value "${TASK_COMMIT}"
```

**Pattern B merge (after all segments complete):** Merge per-segment files into a single `plan-commits.json`:

```bash
if ls "${phase_dir}"/plan-commits-seg-*.json 1>/dev/null 2>&1; then
  gpd json merge-files --out "${phase_dir}/plan-commits.json" "${phase_dir}"/plan-commits-seg-*.json
  rm -f "${phase_dir}"/plan-commits-seg-*.json
fi
```

On resume (in `detect_previous_attempt`), read `plan-commits.json` to reconstruct the `TASK_COMMITS` array and identify which tasks already have committed work.

</task_commit>

<step name="checkpoint_protocol">
See `execute-plan-checkpoints.md` for the full checkpoint protocol (display format, types, resume signals) and `{GPD_INSTALL_DIR}/references/checkpoints.md` for general checkpoint details.

WAIT for user -- do NOT hallucinate completion.
</step>

<step name="verification_failure_gate">
See `execute-plan-validation.md` for physics-specific verification failure handling (dimensional mismatch, limiting case failure, conservation violation).

Verification failure handling by autonomy mode:

- **supervised/guided:** STOP. Present failure details. Options: Retry | Skip (mark incomplete) | Stop (investigate). If skipped -> SUMMARY "Issues Encountered".
- **autonomous:** Attempt ONE automated fix (re-derive with corrected step, adjust numerical parameters). If fix succeeds, log and continue. If fix fails, STOP and return to orchestrator with failure details.
- **yolo:** Attempt ONE alternative approach before escalating. If the alternative works, continue. If the original AND alternative both fail, STOP (this is a hard stop even in yolo mode — physics correctness is non-negotiable).
</step>

<step name="record_completion_time">
```bash
PLAN_END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PLAN_END_EPOCH=$(date +%s)

DURATION_SEC=$(( PLAN_END_EPOCH - PLAN_START_EPOCH ))
DURATION_MIN=$(( DURATION_SEC / 60 ))

if [[ $DURATION_MIN -ge 60 ]]; then
HRS=$(( DURATION_MIN / 60 ))
  MIN=$(( DURATION_MIN % 60 ))
DURATION="${HRS}h ${MIN}m"
else
  DURATION="${DURATION_MIN} min"
fi
```
</step>

<step name="create_summary">
Create `${phase}-${plan}-SUMMARY.md` at `${phase_dir}/`. Use `{GPD_INSTALL_DIR}/templates/summary.md`.

Note: DERIVATION-STATE.md is updated by $gpd-pause-work for session handoff. On natural completion (no pause), key equations and results are captured in SUMMARY.md instead. If you want cumulative derivation state across sessions, run $gpd-pause-work before ending.

**Frontmatter:** phase, plan, depth (minimal/standard/full/complex), subsystem, tags | requires/provides/affects | methods.added/approximations | key-files.created/modified | key-decisions | duration ($DURATION), completed ($PLAN_END_TIME date).

Title: `# Phase [X] Plan [Y]: [Name] Summary`

One-liner SUBSTANTIVE: "Exact diagonalization of XXZ chain yields gapless spectrum with central charge c=1 confirmed by entanglement entropy scaling" not "Hamiltonian diagonalized"

Include: duration, start/end times, task count, file count.

**Physics-specific summary sections:**
- **Key Results:** Main quantitative results with uncertainties
- **Uncertainty Budget:** For each key result, declare: central value, uncertainty (absolute and relative), propagation method (quadrature/Monte Carlo/analytic), and which input uncertainties dominate. This section is consumed by downstream phases and verify-phase.md's uncertainty propagation check. If a result has no meaningful uncertainty (exact symmetry argument, integer quantum number), state why.
- **Limiting Cases Verified:** Which limits were checked and outcomes
- **Validation Events:** Any physics validation gates triggered during execution
- **Open Questions:** Unresolved issues or unexpected findings for future phases

Next: more plans -> "Ready for {next-plan}" | last -> "Phase complete, ready for transition".
</step>

<step name="update_current_position">
**Do NOT write STATE.md directly.** Return state updates in the `gpd_return` envelope so the orchestrator (execute-phase.md) can apply them sequentially after each executor finishes. This prevents parallel write conflicts.

Include these fields in your return envelope:

```yaml
gpd_return:
  state_updates:
    advance_plan: true
    update_progress: true
    record_metric:
      phase: "${phase}"
      plan: "${plan}"
      duration: "${DURATION}"
      tasks: "${TASK_COUNT}"
      files: "${FILE_COUNT}"
```

**Exception:** If executing in Pattern C (main context, no subagent), you ARE the orchestrator — apply state updates directly:

```bash
gpd state advance
gpd state update-progress
gpd state record-metric \
  --phase "${phase}" --plan "${plan}" --duration "${DURATION}" \
  --tasks "${TASK_COUNT}" --files "${FILE_COUNT}"
```

</step>

<step name="extract_decisions_and_issues">
From SUMMARY: Extract decisions and blockers. Include them in the `gpd_return` envelope:

```yaml
gpd_return:
  decisions:
    - phase: "${phase}"
      summary: "${DECISION_TEXT}"
      rationale: "${RATIONALE}"
  blockers:
    - text: "Blocker description"
```

**Exception:** If executing in Pattern C (main context, no subagent), apply directly:

```bash
gpd state add-decision \
  --phase "${phase}" --summary "${DECISION_TEXT}" --rationale "${RATIONALE}"
gpd state add-blocker --text "Blocker description"
```

</step>

<step name="update_session_continuity">
Include session update in the `gpd_return` envelope:

```yaml
gpd_return:
  session_update:
    stopped_at: "Completed ${phase}-${plan}-PLAN.md"
    resume_file: "None"
```

**Exception:** If executing in Pattern C (main context, no subagent), apply directly:

```bash
gpd state record-session \
  --stopped-at "Completed ${phase}-${plan}-PLAN.md" \
  --resume-file "None"
```

Keep STATE.md under 150 lines.
</step>

<step name="issues_review_gate">
If SUMMARY "Issues Encountered" != "None", route by autonomy mode:

- **supervised:** Present ALL issues with full details. Wait for user acknowledgment before proceeding.
- **guided:** Present issues. Wait for acknowledgment only if any issue is physics-critical (dimensional error, limiting case failure, conservation violation). Log-only for minor issues.
- **autonomous:** Log issues to trace. Continue automatically. Issues appear in SUMMARY.md for review at phase boundary.
- **yolo:** Log and continue immediately. Issues visible only in SUMMARY.md.
</step>

<step name="update_roadmap">
More plans -> update plan count, keep "In progress". Last plan -> mark phase "Complete", add date.
</step>

<step name="git_commit_metadata">
Task work already committed per-task. Run pre-commit validation, then commit plan metadata:

```bash
# Validate staged files before final commit (physics checks, format checks)
PRE_CHECK=$(gpd pre-commit-check --files "${phase_dir}/${phase}-${plan}-SUMMARY.md" .planning/STATE.md .planning/ROADMAP.md 2>&1) || true
echo "$PRE_CHECK"
```

If pre-commit-check reports issues, review them but proceed with the commit — issues are advisory at this stage since task work is already committed.

```bash
gpd commit "docs(${phase}-${plan}): complete ${PLAN_NAME} plan" --files "${phase_dir}/${phase}-${plan}-SUMMARY.md" .planning/STATE.md .planning/ROADMAP.md
```

</step>

<step name="stop_trace">
Stop execution trace (captures event summary):

```bash
gpd trace stop 2>/dev/null || true
```
</step>

<step name="track_cost">
Record token consumption for cost analysis:

```bash
gpd cost-track --phase "${phase}" --plan "${plan}" --agent executor --tokens "${tokens_used:-0}" 2>/dev/null || true
```
</step>

<step name="cleanup_checkpoint">
After successful plan completion, remove the checkpoint tag. See `execute-plan-checkpoints.md` for cleanup rules.

```bash
git tag -d "${CHECKPOINT_TAG}" 2>/dev/null
```
</step>

<step name="offer_next">

```bash
ls -1 "${phase_dir}"/*-PLAN.md 2>/dev/null | wc -l
ls -1 "${phase_dir}"/*-SUMMARY.md 2>/dev/null | wc -l
```

| Condition                                  | Route                 | Action                                                                                                                                                  |
| ------------------------------------------ | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| summaries < plans                          | **A: More plans**     | Find next PLAN without SUMMARY. **yolo/autonomous:** auto-continue to next plan. **guided:** show next plan, suggest `$gpd-execute-phase {phase}` + `$gpd-verify-work`. **supervised:** show next plan + completion summary, wait for explicit "proceed" before continuing. STOP here. |
| summaries = plans, current < highest phase | **B: Phase done**     | Show completion, suggest `$gpd-plan-phase {Z+1}` + `$gpd-verify-work {Z}` + `$gpd-discuss-phase {Z+1}`                                                  |
| summaries = plans, current = highest phase | **C: Milestone done** | Show banner, suggest `$gpd-complete-milestone` + `$gpd-verify-work` + `$gpd-add-phase`                                                                  |

All routes: `/clear` first for fresh context.
</step>

</process>

<failure_recovery>
When plan execution fails, see `execute-plan-recovery.md` for the full recovery protocol including rollback, partial work preservation, and RECOVERY.md creation. For physics-specific failure diagnosis (sign errors, convergence failures, numerical instability, dimensional mismatches), use the template at `{GPD_INSTALL_DIR}/templates/recovery-plan.md`.
</failure_recovery>

<success_criteria>

- All tasks from PLAN.md completed
- All verifications pass (including physics validation gates)
- Dimensional consistency verified for all quantitative results
- Limiting cases checked where specified
- SUMMARY.md created with substantive content including key results
- STATE.md updated (position, decisions, issues, session)
- ROADMAP.md updated
- Validation events documented
- Checkpoint tag cleaned up on success (retained on failure)
</success_criteria>
