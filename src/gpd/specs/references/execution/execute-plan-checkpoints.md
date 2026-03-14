# Execute-Plan: Checkpoint Protocol

Referenced by `src/gpd/specs/workflows/execute-plan.md`. Governs checkpoint creation, previous attempt detection, checkpoint handling during execution, and cleanup.

## Create Rollback Tag

**Create a git rollback tag before any plan execution begins.** This enables clean recovery if the plan fails partway through. The git tag is a rollback primitive, not the bounded execution checkpoint state itself.

```bash
CHECKPOINT_TAG="gpd-checkpoint/phase-${PHASE}-plan-${PLAN}-$(date +%s)"
git tag "${CHECKPOINT_TAG}"
```

Store the tag name for use in failure recovery:

```bash
echo "Checkpoint: ${CHECKPOINT_TAG}"
```

The tag marks the exact repository state before this plan's first task commit. If execution fails, the tag provides the rollback target.

## Detect Previous Attempt

**Check if this plan was previously attempted (partial completion).** Detect by searching for task-level commits matching this plan's identifier.

```bash
PRIOR_COMMITS=$(git log --oneline --grep="(${PHASE}-${PLAN}):" | head -20)
```

**If prior commits found:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PREVIOUS ATTEMPT DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Plan {PHASE}-{PLAN} has prior task commits:

{PRIOR_COMMITS}

These tasks already have committed work:
{list of task numbers extracted from commit messages}

──────────────────────────────────────────────────────
Options:
  1. "Resume from task N" -- skip already-committed tasks, continue from first incomplete
  2. "Start fresh" -- execute all tasks (existing commits remain in history)
──────────────────────────────────────────────────────
```

**If user chooses resume:**

- Parse prior commit messages to identify completed task numbers
- Set `RESUME_FROM_TASK` to the first task number without a commit
- Skip tasks 1 through `RESUME_FROM_TASK - 1` during execution
- Load prior commit hashes into `TASK_COMMITS` array for the SUMMARY

**If user chooses start fresh:**

- Proceed normally -- new commits will not duplicate prior ones because task content will differ or be re-derived
- Note in SUMMARY: "Re-execution of previously attempted plan"

**If no prior commits found:** Proceed normally (first attempt).

**Duplicate prevention:** Before committing any task, check:

```bash
git log --oneline --grep="(${PHASE}-${PLAN}): ${TASK_NAME}" | head -1
```

If an exact match exists and the task output is identical, skip the commit with a note: "Task N already committed ({hash}), skipping duplicate."

## Checkpoint Protocol (During Execution)

On `type="checkpoint:*"`: automate everything possible first. Checkpoints are for verification/decisions only.

Display: `CHECKPOINT: [Type]` box -> Progress {X}/{Y} -> Task name -> type-specific content -> `YOUR ACTION: [signal]`

| Type               | Content                                                                                                     | Resume signal                 |
| ------------------ | ----------------------------------------------------------------------------------------------------------- | ----------------------------- |
| human-verify (90%) | What was derived/computed + verification steps (reproduce key result, check limit)                          | "approved" or describe issues |
| decision (9%)      | Methodological decision needed + context + options with tradeoffs                                           | "Select: option-id"           |
| human-action (1%)  | What was automated + ONE manual step (e.g., run external code, check experimental data) + verification plan | "done"                        |

After response: verify if specified. Pass -> continue. Fail -> inform, wait. WAIT for user -- do NOT hallucinate completion.

See references/orchestration/checkpoints.md for details.

## Checkpoint Return (For Orchestrator)

When spawned via task and hitting checkpoint: return structured state (cannot interact with user directly).

**Required return:** 1) Completed Tasks table (hashes + files) 2) Current task (what's blocking) 3) Checkpoint Details (user-facing content) 4) Awaiting (what's needed from user) 5) `execution_segment` payload with cursor, checkpoint cause, completed tasks, resume preconditions, and any first-result or pre-fanout gate state.

If the stop is tied to first-result, skeptical, or pre-fanout review, the `execution_segment` must say which gate is still pending. A gate clear must name the specific reason being retired, and `fanout unlock` never substitutes for that clear. For `pre_fanout`, return `pre_fanout_review_cleared: true` when the review outcome is known but downstream unlock is still outstanding.

Orchestrator parses -> presents to user -> spawns fresh continuation with your completed tasks state plus the `execution_segment` payload. You will NOT be resumed. In main context: use checkpoint protocol above.

## Cleanup Checkpoint

**After successful plan completion (all tasks done, SUMMARY created, metadata committed):**

Remove the checkpoint tag -- it is no longer needed for rollback.

```bash
git tag -d "${CHECKPOINT_TAG}" 2>/dev/null
```

The tag is only kept when failures occur (see `references/execution/execute-plan-recovery.md`).
