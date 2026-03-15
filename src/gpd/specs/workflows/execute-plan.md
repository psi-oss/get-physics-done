<purpose>
Execute a research plan (PLAN.md) -- carry out derivations, calculations, simulations, or analysis -- and create the outcome summary (SUMMARY.md).
</purpose>

<required_reading>
Read STATE.md before any operation to load project context.
Read config.json for planning behavior settings.

Read these reference files using the file_read tool:
- {GPD_INSTALL_DIR}/references/execution/git-integration.md
- {GPD_INSTALL_DIR}/references/execution/execute-plan-recovery.md
- {GPD_INSTALL_DIR}/references/execution/execute-plan-validation.md
- {GPD_INSTALL_DIR}/references/execution/execute-plan-checkpoints.md
- {GPD_INSTALL_DIR}/references/protocols/reproducibility.md
- {GPD_INSTALL_DIR}/references/protocols/error-propagation-protocol.md -- Cross-phase uncertainty propagation protocol (Uncertainty Budget declaration format, verification checks, phase handoff format)
- {GPD_INSTALL_DIR}/references/execution/executor-index.md -- Maps execution scenarios (QFT, condensed matter, numerical, paper writing, debugging) to the correct domain-specific reference files
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

Extract from init JSON: `executor_model`, `commit_docs`, `phase_dir`, `phase_number`, `plans`, `summaries`, `incomplete_plans`, `autonomy`, `review_cadence`, `max_unattended_minutes_per_plan`, `max_unattended_minutes_per_wave`, `checkpoint_after_n_tasks`, `checkpoint_after_first_load_bearing_result`, `checkpoint_before_downstream_dependent_tasks`, `project_contract`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`.

**File contents (from --include):** `state_content`, `config_content`. Access with:

```bash
STATE_CONTENT=$(echo "$INIT" | gpd json get .state_content --default "")
CONFIG_CONTENT=$(echo "$INIT" | gpd json get .config_content --default "")
```

If `.gpd/` missing: error.
</step>

<step name="load_contract_anchor_context">
Treat `project_contract` as authoritative machine-readable scope when present. Do not execute from PLAN markdown alone if the contract or active-anchor ledger says a decisive reference, prior output, or forbidden proxy still constrains the work.

Treat `effective_reference_intake` as the structured carry-forward ledger for must-read refs, baselines, prior outputs, user anchors, and context gaps. Use `active_reference_context` and `reference_artifacts_content` to interpret that ledger quickly, not to replace it with prose-only reconstruction.
</step>

<step name="load_protocol_bundle_context">
If `selected_protocol_bundle_ids` is non-empty, treat `protocol_bundle_context` as the primary specialized-loading guide for this plan.

- Read the bundle-listed core assets before starting substantive work.
- Carry bundle estimator policies and decisive artifact guidance into task execution and SUMMARY evidence.
- If no bundle is selected, fall back to shared protocols plus on-demand routing through the executor index.
</step>

<step name="verify_conventions">
Before execution, verify convention lock is consistent and non-empty:

```bash
CONV_CHECK=$(gpd --raw convention check)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — review before executing"
  echo "$CONV_CHECK"
fi
```

If the project has existing phases and the convention lock is empty, this is an error. Conventions must be established before execution proceeds.

**Load authoritative conventions** (canonical protocol from `agent-infrastructure.md`):

```bash
CONVENTIONS=$(gpd --raw convention list 2>/dev/null)
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

Record workflow start in the local observability stream, then start the plan-local execution trace:

```bash
gpd observe event workflow execute-plan.start --phase "${phase}" --plan "${plan}" 2>/dev/null || true
```

Start execution trace for debugging:

```bash
gpd trace start "${phase}" "${plan}" 2>/dev/null || true
```
</step>

<step name="resolve_autonomy_mode">
Read autonomy mode from init JSON to control decision authority throughout execution:

```bash
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
```

**Checkpoint behavior by mode:**

| Mode | Task Checkpoints | Physics Decision Checkpoints | Verification Failure |
|------|-----------------|------------------------------|---------------------|
| **supervised** | After EVERY task plus every required first-result gate | Always | Always stop |
| **balanced** (default) | Auto-flow between clean tasks, but required bounded gates still run | On physics choices, deviation rules 5-6, convention conflicts, or convergence failure after 3 attempts | Attempt one bounded fix, then stop if unresolved |
| **yolo** | No user prompt on clean passes, but required bounded gates still run | Attempt one alternative before escalating; never skip first-result, skeptical, or pre-fanout gates | Stop only on unrecoverable errors, failed sanity gates, or unresolved skeptical review |

**Invariant:** `autonomy` changes who is asked and when. It does NOT disable first-result sanity checks, bounded execution segments, contract/anchor gates, or physics hard stops.

Task checkpoints are task-level, not every internal algebra line. Model profile and research mode may change depth or task granularity, but they do NOT remove required first-result, skeptical, or pre-fanout gates.

</step>

<step name="resolve_execution_cadence">
Read cadence controls from init JSON. Use these to decide whether a plan can run unbounded or must be segmented even without authored checkpoints.

```bash
REVIEW_CADENCE=$(echo "$INIT" | gpd json get .review_cadence --default adaptive)
MAX_UNATTENDED_MINUTES_PER_PLAN=$(echo "$INIT" | gpd json get .max_unattended_minutes_per_plan --default 45)
CHECKPOINT_AFTER_N_TASKS=$(echo "$INIT" | gpd json get .checkpoint_after_n_tasks --default 3)
CHECKPOINT_AFTER_FIRST_RESULT=$(echo "$INIT" | gpd json get .checkpoint_after_first_load_bearing_result --default true)
CHECKPOINT_BEFORE_DOWNSTREAM=$(echo "$INIT" | gpd json get .checkpoint_before_downstream_dependent_tasks --default true)
```

Resolve plan-local bounds using orchestrator tags first, then plan shape:

- if the orchestrator passed `<first_result_gate>true</first_result_gate>`, honor it
- if the orchestrator passed `<segment_task_cap>N</segment_task_cap>`, honor it
- otherwise require bounded execution when the plan has no authored checkpoints and `task_count >= CHECKPOINT_AFTER_N_TASKS`
- also require bounded execution when the uninterrupted segment is likely to exceed `MAX_UNATTENDED_MINUTES_PER_PLAN`, even if the work feels smooth
- also require bounded execution when the plan establishes a new baseline, new estimator, new ansatz, or a first decisive-comparison path that many downstream tasks depend on
- phase ordering, prior momentum, or "we are already deep into execution" never waive a required bounded stop

Set:

- `FIRST_RESULT_GATE_REQUIRED=true|false`
- `SEGMENT_TASK_CAP=${CHECKPOINT_AFTER_N_TASKS}` unless overridden
- `BOUNDED_EXECUTION=true|false`
- `PRE_FANOUT_REVIEW_REQUIRED=${CHECKPOINT_BEFORE_DOWNSTREAM}` when downstream work would rely on a not-yet-decisive result

**Skeptical re-questioning rule:** if the first material result only validates a proxy, internal consistency check, or supporting artifact while the contract still owes a decisive comparison, benchmark anchor, or acceptance-test outcome, STOP and ask whether the framing still deserves belief before continuing.

Required gates are only considered passed when an explicit clear/override transition is recorded. "No obvious issue" prose is not enough to resume fanout.

Clear transitions are reason-scoped: clearing `first_result` must not silently clear `pre_fanout` or skeptical review state, and a `fanout unlock` never substitutes for the matching review clear.

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
| None        | A (non-interactive) | Single subagent: full plan + SUMMARY + commit                                                    |
| Verify-only | B (segmented)  | Segments between checkpoints. After none/human-verify -> SUBAGENT. After decision/human-action -> MAIN |
| Decision    | C (main)       | Execute entirely in main context                                                                       |
| Auto-bounded | D (virtual checkpoints) | Segment automatically at first-result, task-cap, context-pressure, or pre-fanout review boundaries |

**Pattern A:** init_agent_tracking -> spawn task(subagent_type="gpd-executor", model=executor_model, readonly=false) with prompt: execute plan at [path], all tasks + SUMMARY + structured return envelope, follow deviation/validation rules, **load conventions from `gpd convention list` before starting work**, `<autonomy_mode>{AUTONOMY}</autonomy_mode>`, `<review_cadence>{REVIEW_CADENCE}</review_cadence>`, `<bounded_execution>false</bounded_execution>` (only for genuinely low-risk short plans), return: plan name, tasks, SUMMARY path, commit hash, and state updates -> track agent_id -> wait -> update tracking -> report.

**If the executor agent fails to spawn or returns an error (Pattern A):** Check if any work was committed (`git log --oneline -3`). If commits with the plan's work exist, the executor may have completed but failed to report — verify output files and proceed to post-execution checks. If no work was done, offer: 1) Retry executor spawn, 2) Fall back to Pattern C (execute in main context), 3) Abort. Update agent tracking status to "failed" with error details.

**Pattern B:** Execute segment-by-segment. Non-interactive segments: spawn subagent for assigned tasks only (no SUMMARY/commit). Checkpoints: main context. After all segments: aggregate, create SUMMARY, commit. See segment_execution.

**If a segment executor fails to spawn or returns an error (Pattern B):** Check if the segment's tasks produced any output files. If work exists, proceed to the next segment. If no work, offer: 1) Retry this segment, 2) Execute the segment's tasks in the main context, 3) Skip this segment and continue. Do not abort the entire plan for a single segment failure. Record the failure in agent tracking.

**Pattern C:** Execute in main using standard flow (step name="execute").

**Pattern D:** Execute via virtual checkpoints even if the authored plan contains no checkpoint tasks. Stop at the first material result, at `SEGMENT_TASK_CAP`, at context-pressure auto-pause, or before downstream fanout when anchors still need review. Use the same continuation flow as authored checkpoints.

Fresh context per subagent preserves peak quality. Main context stays lean.
</step>

<step name="init_agent_tracking">
```bash
if [ ! -f .gpd/agent-history.json ]; then
  echo '{"version":"1.0","max_entries":50,"entries":[]}' > .gpd/agent-history.json
fi
if [ -f .gpd/current-agent-id.txt ]; then
  INTERRUPTED_ID=$(cat .gpd/current-agent-id.txt)
  echo "Found interrupted agent: $INTERRUPTED_ID"
fi
```

If interrupted: ask user to resume (Task `resume` parameter) or start fresh.

**Tracking protocol:** On spawn: write agent_id to `current-agent-id.txt`, append to agent-history.json: `{"agent_id":"[id]","task_description":"[desc]","phase":"[phase]","plan":"[plan]","segment":[num|null],"timestamp":"[ISO]","status":"spawned","completion_timestamp":null}`. On completion: status -> "completed", set completion_timestamp, delete current-agent-id.txt. Prune: if entries > max_entries, remove oldest "completed" (never "spawned").

Run for Pattern A/B before spawning. Pattern C: skip.
</step>

<step name="segment_execution">
Pattern B/D only (authored or virtual checkpoints). Skip for A/C.

1. Parse segment map: checkpoint locations and types, then merge in virtual boundaries from `FIRST_RESULT_GATE_REQUIRED`, `SEGMENT_TASK_CAP`, `MAX_UNATTENDED_MINUTES_PER_PLAN`, and context pressure
2. Per segment:
   - Subagent route: spawn gpd-executor for assigned tasks only. Prompt: task range, plan path, read full plan for context, execute assigned tasks, track deviations, `<autonomy_mode>{AUTONOMY}</autonomy_mode>`, `<review_cadence>{REVIEW_CADENCE}</review_cadence>`, `<segment_task_cap>{SEGMENT_TASK_CAP}</segment_task_cap>`, `<max_unattended_minutes_per_plan>{MAX_UNATTENDED_MINUTES_PER_PLAN}</max_unattended_minutes_per_plan>`, `<first_result_gate>{FIRST_RESULT_GATE_REQUIRED}</first_result_gate>`, NO SUMMARY/commit, but RETURN `contract_updates` keyed by claim/deliverable/acceptance-test/reference/forbidden-proxy IDs and any `execution_segment` fields needed to keep bounded gates live across continuation. Track via agent protocol.
   - Main route: execute tasks using standard flow (step name="execute")
3. After ALL segments: aggregate files/deviations/decisions/`contract_updates` -> create SUMMARY.md -> apply returned state updates in main context -> final metadata commit -> self-check:

   - Verify key-files.created exist on disk with `[ -f ]`
   - Check `git log --oneline --grep="{phase}-{plan}"` returns >=1 commit
   - Append `## Self-Check: PASSED` or `## Self-Check: FAILED` to SUMMARY
   - Run physics validation checks (dimensional consistency, limiting cases) -> Append `## Validation: PASSED` or `## Validation: FAILED`

   > **Handoff verification:** Do not trust the runtime handoff status by itself. Verify expected output files, the return envelope, and git commits before treating a subagent as failed.

</step>

<step name="load_prompt">
```bash
cat "${phase_dir}/${phase}-${plan}-PLAN.md"
```
This IS the execution instructions. Follow exactly. If plan references CONTEXT.md: honor user's research direction throughout.
</step>

<step name="previous_phase_check">
```bash
ls .gpd/phases/*/*-SUMMARY.md 2>/dev/null | sort -r | head -2 | tail -1
```
> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

If previous SUMMARY has unresolved "Issues Encountered" or "Next Phase Readiness" blockers: ask_user(header="Previous Issues", options: "Proceed anyway" | "Address first" | "Review previous").
</step>

<step name="execute">
Deviations are normal -- handle via deviation rules in `execute-plan-validation.md`.

1. Read @context files from prompt
2. Per task:
   - `type="auto"`: Execute derivation/calculation/simulation. Verify done criteria including dimensional checks. Commit (see task_commit). Track hash for Summary.
     ```bash
     gpd observe event task task-complete --phase "${phase}" --plan "${plan}" --data "{\"task\":\"${TASK_NUM}\",\"description\":\"${TASK_DESCRIPTION}\"}" 2>/dev/null || true
     gpd trace log checkpoint --data "{\"description\":\"Task ${TASK_NUM} done: ${TASK_DESCRIPTION}\"}" 2>/dev/null || true
     ```
     **Required first-result sanity gate:** At the earliest of (a) first quantitative result, (b) first derived core equation, (c) first produced artifact, (d) first benchmark-style comparison, or (e) two completed auto tasks, STOP and check:
     - which claim, deliverable, or acceptance test would this result unlock if it held up?
     - is this a load-bearing result or only a proxy?
     - did one quick sanity/benchmark/convention check already pass?
     - which decisive comparison, benchmark anchor, or user-visible acceptance-test result is still missing?
     - if decisive evidence is still missing, what is the disconfirming observation that would most quickly break the current framing?

     Record this gate with:

     ```bash
     gpd observe event execution gate --action enter --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"first_result\",\"review_cadence\":\"${REVIEW_CADENCE}\",\"first_result_ready\":true,\"first_result_gate_pending\":true,\"current_task\":\"${TASK_DESCRIPTION}\"}}" 2>/dev/null || true
     ```

     When the first-result stop is accepted, record the matching clear before any dependent work resumes:

     ```bash
     gpd observe event execution gate --action clear --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"first_result\"}}" 2>/dev/null || true
     ```

     If the first result is still proxy-only, benchmark-thin, or otherwise lacks the decisive evidence the contract still owes, strengthen the same stop into skeptical review instead of silently continuing:

     ```bash
     gpd observe event execution gate --action enter --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"first_result\",\"review_cadence\":\"${REVIEW_CADENCE}\",\"first_result_ready\":true,\"first_result_gate_pending\":true,\"skeptical_requestioning_required\":true,\"skeptical_requestioning_summary\":\"${SKEPTICAL_SUMMARY}\",\"weakest_unchecked_anchor\":\"${WEAKEST_ANCHOR}\",\"disconfirming_observation\":\"${DISCONFIRMING_OBSERVATION}\",\"downstream_locked\":true,\"current_task\":\"${TASK_DESCRIPTION}\"}}" 2>/dev/null || true
     ```

     When skeptical re-questioning is resolved, clear that state explicitly. Do not assume the first-result clear retires it:

     ```bash
     gpd observe event execution gate --action clear --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"skeptical_requestioning\"}}" 2>/dev/null || true
     ```

     Before any downstream dependent tasks or fanout continue, emit an explicit pre-fanout stop whenever later work would rely on this result as if the decisive evidence already existed:

     ```bash
     gpd observe event execution fanout --action lock --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"pre_fanout\",\"pre_fanout_review_pending\":true,\"downstream_locked\":true,\"last_result_label\":\"${FIRST_RESULT_LABEL}\"}}" 2>/dev/null || true
     gpd observe event execution gate --action enter --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"pre_fanout\",\"pre_fanout_review_pending\":true,\"downstream_locked\":true,\"last_result_label\":\"${FIRST_RESULT_LABEL}\"}}" 2>/dev/null || true
     ```

     Only after the review outcome is accepted should execution retire the pre-fanout gate and unlock fanout. These are separate transitions; neither one implies the other:

     ```bash
     gpd observe event execution gate --action clear --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"pre_fanout\"}}" 2>/dev/null || true
     gpd observe event execution fanout --action unlock --phase "${phase}" --plan "${plan}" \
       --data "{\"execution\":{\"checkpoint_reason\":\"pre_fanout\"}}" 2>/dev/null || true
     ```

     If the pre-fanout stop also carried skeptical re-questioning, clear that state explicitly before or alongside the pre-fanout clear; a `pre_fanout` clear must not wipe skeptical fields implicitly.

     **Supervised mode post-task checkpoint:** If `AUTONOMY="supervised"`, insert a `checkpoint:human-verify` after EVERY completed task. Present the task result with all intermediate values and wait for user approval before proceeding to the next task.
   - `type="checkpoint:*"`: Route by autonomy mode:
     - **supervised:** STOP -> checkpoint protocol (see `execute-plan-checkpoints.md`) -> wait for user -> continue only after confirmation.
     - **balanced:** Stop for `checkpoint:decision`, `checkpoint:human-verify`, required first-result gates, any checkpoint tied to deviation rules 5-6 or unresolved convergence failure, and any case where decisive evidence is still missing but the next tasks would assume it. Log routine checkpoint markers and continue when no judgment is needed.
     - **yolo:** Do NOT skip required first-result, bounded-segment, skeptical, or pre-fanout checkpoints. Auto-continue only after the gate is explicitly cleared and the remaining work is genuinely independent of the unresolved decisive comparison. STOP on failed sanity, unresolved skeptical review, anchor-gate failure, or unrecoverable computation error.
3. Run `<verification>` checks including physics validation (see `execute-plan-validation.md`)
   ```bash
   gpd observe event verification verification-complete --phase "${phase}" --plan "${plan}" --data "{\"description\":\"${VERIFICATION_RESULT}\"}" 2>/dev/null || true
   gpd trace log assertion --data "{\"description\":\"Verification: ${VERIFICATION_RESULT}\"}" 2>/dev/null || true
   ```
4. Confirm `<success_criteria>` met
5. Document deviations in Summary

**Context awareness (after each task):**

Context is finite (~200k tokens, ~80% usable). After completing each task:

1. Check statusline context percentage
2. If >60% with heavy work remaining: consider proactive pause
3. If >80%: save intermediate results and trigger `/gpd:pause-work` before quality degrades

Signs of context pressure: re-reading files you already read, losing track of parameter values or sign conventions, derivation steps getting sloppy. A fresh context with saved state outperforms a saturated one.

If pausing mid-plan: commit current work, create `.continue-here.md` with full derivation state, recommend `/clear` + `/gpd:resume-work`. See `{GPD_INSTALL_DIR}/references/orchestration/context-budget.md` for budget guidelines.

**Auto-checkpoint protocol (autonomy-aware):**

After completing each task, check context usage. Checkpoint frequency varies by autonomy mode:

| Mode | Context checkpoint at 60% | Context checkpoint at 75% | Verification failure |
|------|--------------------------|--------------------------|---------------------|
| **supervised** | Yes + present to user | Yes + force pause + user approval | Always stop, present details |
| **balanced** | Yes (write silently) | Yes + proactive pause | Attempt one bounded fix, then stop if unresolved |
| **yolo** | Write checkpoint file only | Auto-pause only at context RED (>85%) | Stop only on unrecoverable error or failed required gate |

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
   - Create `.continue-here.md` with full derivation state and a bounded execution segment summary
   - Update STATE.md session info
  - **supervised/balanced:** Suggest `/clear` + `/gpd:resume-work`
  - **yolo:** Prepare the bounded resume handoff automatically and continue only if the runtime can spawn the continuation with explicit segment state; otherwise suggest `/clear` + `/gpd:resume-work`

Also stop when either bound is hit, even if context looks healthy:

- uninterrupted wall-clock time since the current segment started reaches `MAX_UNATTENDED_MINUTES_PER_PLAN`
- completed tasks since the last bounded checkpoint reach `SEGMENT_TASK_CAP`

These are bounded-segment stops, not optional hints. They exist to keep long runs reviewable before a wrong early assumption fans out.

This prevents quality degradation and ensures no work is lost if the session ends unexpectedly.
</step>

<task_commit>

## Task Commit Protocol

After each task (verification passed, done criteria met), commit immediately.

**1. Check:** `git status --short`

**2. Choose the exact files for `gpd commit --files`** (NEVER commit broad paths like `git add .` or `git add -A`):

```bash
TASK_FILES=(
  src/derivations/hamiltonian.py
  artifacts/phases/08-example/data/spectrum.json
)
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

**5. Commit via gpd:**

```bash
gpd commit "{type}({phase}-{plan}): {description}" --files "${TASK_FILES[@]}"
```

**6. Pre-commit validation** runs automatically inside `gpd commit`. If it fails (invalid frontmatter or serialized NaN/Inf in the checked files), the commit is blocked — fix the errors and retry.

**7. Record hash:**

```bash
TASK_COMMIT=$(git rev-parse --short HEAD)
TASK_COMMITS+=("Task ${TASK_NUM}: ${TASK_COMMIT}")
```

**8. Persist commit hash to disk (crash resilience):**

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
See `execute-plan-checkpoints.md` for the full checkpoint protocol (display format, types, resume signals) and `{GPD_INSTALL_DIR}/references/orchestration/checkpoints.md` for general checkpoint details.

WAIT for user -- do NOT hallucinate completion.
</step>

<step name="verification_failure_gate">
See `execute-plan-validation.md` for physics-specific verification failure handling (dimensional mismatch, limiting case failure, conservation violation).

Verification failure handling by autonomy mode:

- **supervised:** STOP. Present failure details. Options: Retry | Skip (mark incomplete) | Stop (investigate). If skipped -> SUMMARY "Issues Encountered".
- **balanced:** Attempt ONE automated fix (re-derive with corrected step, adjust numerical parameters) when the remedy is local and verifiable. If the fix succeeds, log it and continue. If it fails or requires a judgment call, STOP and return to the orchestrator with failure details.
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

Note: DERIVATION-STATE.md is updated by /gpd:pause-work for session handoff. On natural completion (no pause), key equations and results are captured in SUMMARY.md instead. If you want cumulative derivation state across sessions, run /gpd:pause-work before ending.

**Frontmatter:** phase, plan, depth (minimal/standard/full/complex), subsystem, tags | requires/provides/affects | methods.added/approximations | key-files.created/modified | key-decisions | duration ($DURATION), completed ($PLAN_END_TIME date).

**Contract-backed plans:** if the PLAN frontmatter includes `contract`, SUMMARY frontmatter must also include:
- `plan_contract_ref`
- `contract_results` keyed by claim IDs, deliverable IDs, acceptance test IDs, reference IDs, and forbidden proxy IDs
- `comparison_verdicts` for decisive internal/external comparisons when they exist

`contract_results` is authoritative. Do not reintroduce ad hoc summary-side success criteria that are absent from the PLAN contract.
Before treating the summary as complete, run `gpd validate summary-contract ${phase_dir}/${phase}-${plan}-SUMMARY.md` and fix any contract-linkage or verdict-ledger errors.

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

Autonomy mode (`supervised` / `balanced` / `yolo`) and profile may change cadence or verbosity, but they do NOT relax contract-result emission.
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
  contract_updates:
    plan_contract_ref: ".gpd/phases/${phase_dir_name}/${phase}-${plan}-PLAN.md#/contract"
    contract_results: { ... keyed by claim/deliverable/test/reference/proxy ids ... }
    comparison_verdicts: []
    contract_completion_status: complete | partial | blocked
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
gpd observe event session continuity-updated --phase "${phase}" --plan "${plan}" --data "{\"stopped_at\":\"Completed ${phase}-${plan}-PLAN.md\",\"resume_file\":\"None\"}" 2>/dev/null || true
```

Keep STATE.md under 150 lines.
</step>

<step name="issues_review_gate">
If SUMMARY "Issues Encountered" != "None", route by autonomy mode:

- **supervised:** Present ALL issues with full details. Wait for user acknowledgment before proceeding.
- **balanced:** Present issues. Wait for acknowledgment only if any issue is physics-critical (dimensional error, limiting case failure, conservation violation) or changes interpretation. Log-only for minor issues.
- **yolo:** Log and continue immediately. Issues visible only in SUMMARY.md.
</step>

<step name="update_roadmap">
More plans -> update plan count, keep "In progress". Last plan -> mark phase "Complete", add date.
</step>

<step name="git_commit_metadata">
Task work already committed per-task. By this step the main context has already applied any returned state updates. Run pre-commit validation, then commit plan metadata:

```bash
# Validate staged files before final commit (physics checks, format checks)
PRE_CHECK=$(gpd pre-commit-check --files "${phase_dir}/${phase}-${plan}-SUMMARY.md" .gpd/STATE.md .gpd/ROADMAP.md 2>&1) || true
echo "$PRE_CHECK"
```

If the explicit `PRE_CHECK` command reports issues, treat it as early visibility only. `gpd commit` re-runs the same validation on the commit paths and remains the blocking gate, so fix any reported issues before retrying when the commit is rejected.

```bash
gpd commit "docs(${phase}-${plan}): complete ${PLAN_NAME} plan" --files "${phase_dir}/${phase}-${plan}-SUMMARY.md" .gpd/STATE.md .gpd/ROADMAP.md
```

</step>

<step name="stop_trace">
Record workflow completion in the local observability stream, then stop the plan-local trace:

```bash
gpd observe event workflow execute-plan.complete --phase "${phase}" --plan "${plan}" 2>/dev/null || true
```

Stop execution trace (captures event summary):

```bash
gpd trace stop 2>/dev/null || true
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
| summaries < plans                          | **A: More plans**     | Find next PLAN without SUMMARY. **balanced/yolo:** auto-continue to next plan when no blockers remain. **supervised:** show next plan + completion summary, wait for explicit "proceed" before continuing. STOP here. |
| summaries = plans, current < highest phase | **B: Phase done**     | Show completion, suggest `/gpd:plan-phase {Z+1}` + `/gpd:verify-work {Z}` + `/gpd:discuss-phase {Z+1}`                                                  |
| summaries = plans, current = highest phase | **C: Milestone done** | Show banner, suggest `/gpd:complete-milestone` + `/gpd:verify-work` + `/gpd:add-phase`                                                                  |

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
- Contract-backed plans emit contract_results and comparison_verdicts when applicable
- STATE.md updated (position, decisions, issues, session)
- ROADMAP.md updated
- Validation events documented
- Checkpoint tag cleaned up on success (retained on failure)
</success_criteria>
