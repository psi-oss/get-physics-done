<purpose>
Execute small, ad-hoc physics tasks with GPD guarantees (atomic commits, STATE.md tracking) while skipping optional agents (literature search, plan-checker, verifier). Quick mode spawns gpd-planner (quick mode) + gpd-executor(s), tracks tasks in `.gpd/quick/`, and updates STATE.md's "Quick Tasks Completed" table. Typical quick tasks include: quick derivation, dimensional check, order-of-magnitude estimate, limiting case verification, and bibliography lookup.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>
**Step 1: Get task description**

Prompt user interactively for the task description:

```
> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

ask_user(
  header: "Quick Task",
  question: "What do you want to do? Examples:
  - Quick derivation of the equation of motion from the Lagrangian
  - Dimensional check on the cross-section formula in eq. (3.14)
  - Order-of-magnitude estimate for the tunneling rate
  - Verify the non-relativistic limiting case of the dispersion relation
  - Look up the original reference for the Mermin-Wagner theorem",
  followUp: null
)
```

Store response as `$DESCRIPTION`.

If empty, re-prompt: "Please provide a task description."

---

**Step 2: Initialize**

```bash
INIT=$(gpd init quick "$DESCRIPTION")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `planner_model`, `executor_model`, `commit_docs`, `autonomy`, `next_num`, `slug`, `date`, `timestamp`, `quick_dir`, `task_dir`, `roadmap_exists`, `planning_exists`.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after plan for user approval before execution.
- `autonomy=guided` (default): Execute without pausing (quick tasks are inherently lightweight).
- `autonomy=autonomous/yolo`: Execute and commit without pausing.

**If `planning_exists` is false:** Error -- Quick mode requires an initialized project with `.gpd/`. Run `/gpd:new-project` first.

Quick tasks can run mid-phase and do NOT require ROADMAP.md. They only need `.gpd/` to exist for directory structure.

---

**Step 3: Create task directory**

Use `task_dir` from init JSON (`.gpd/quick/${next_num}-${slug}`):

```bash
QUICK_DIR="${task_dir}"
mkdir -p "$QUICK_DIR"
```

Report to user:

```
Creating quick task ${next_num}: ${DESCRIPTION}
Directory: ${QUICK_DIR}
```

---

**Step 4: Spawn planner (quick mode)**

Spawn gpd-planner with quick mode context:

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolved to `null`, omit it. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.

<planning_context>

**Mode:** quick
**Directory:** ${QUICK_DIR}
**Description:** ${DESCRIPTION}

**Project State:**
Read the file at .gpd/STATE.md

</planning_context>

<constraints>
- Create a SINGLE plan with 1-3 focused tasks
- Quick tasks should be atomic and self-contained
- No literature review phase, no checker phase
- Target ~30% context usage (simple, focused)
</constraints>

<output>
Write plan to: ${QUICK_DIR}/${next_num}-PLAN.md
Return: ## PLANNING COMPLETE with plan path
</output>
",
  subagent_type="gpd-planner",
  model="{planner_model}",
  description="Quick plan: ${DESCRIPTION}"
)
```

**If the planner agent fails to spawn or returns an error:** Check if a plan file was written to `${QUICK_DIR}/${next_num}-PLAN.md` (agents write files first). If the plan exists, proceed to step 5. If no plan, offer: 1) Retry planner, 2) Create the plan in the main context, 3) Abort. Do not silently continue without a plan.

After planner returns:

1. Verify plan exists at `${QUICK_DIR}/${next_num}-PLAN.md`
2. Extract plan count (typically 1 for quick tasks)
3. Report: "Plan created: ${QUICK_DIR}/${next_num}-PLAN.md"

If plan not found, error: "Planner failed to create ${next_num}-PLAN.md"

---

**Step 5: Spawn executor**

Spawn gpd-executor with plan reference:
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolved to `null`, omit it. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

Execute quick task ${next_num}.

Plan: Read the file at ${QUICK_DIR}/${next_num}-PLAN.md
Project state: Read the file at .gpd/STATE.md

<constraints>
- Execute all tasks in the plan
- Commit each task atomically
- Create summary at: ${QUICK_DIR}/${next_num}-SUMMARY.md
- Do NOT update ROADMAP.md (quick tasks are separate from planned phases)
</constraints>
",
  subagent_type="gpd-executor",
  model="{executor_model}",
  description="Execute: ${DESCRIPTION}"
)
```

**If the executor agent fails to spawn or returns an error:** Check if any work was committed (run `git log --oneline -3`). If commits exist with the task's work, proceed to step 6 — the executor may have completed but failed to report back. If no commits, offer: 1) Retry executor, 2) Execute the plan in the main context, 3) Abort. The plan file is still available for re-execution.

After executor returns:

1. Verify summary exists at `${QUICK_DIR}/${next_num}-SUMMARY.md`
2. Extract commit hash from executor output
3. Report completion status

> **Runtime caveat:** Some runtimes may misreport a completed subagent as failed (`classifyHandoffIfNeeded`). Spot-check expected output files and git commits before treating the result as a real failure.

If summary not found, error: "Executor failed to create ${next_num}-SUMMARY.md"

Note: For quick tasks producing multiple plans (rare), spawn executors in parallel waves per execute-phase patterns.

---

**Step 6: Update project state**

Update project state with quick task completion record using gpd commands (ensures STATE.md + state.json stay in sync):

**6a. Record quick task completion as a decision:**

```bash
gpd state add-decision --phase "quick-${next_num}" --summary "Quick task ${next_num}: ${DESCRIPTION}" --rationale "Ad-hoc task completed outside planned phases"
```

**6b. Update last activity:**

```bash
gpd state update "Last Activity" "${date}"
```

**6c. Append quick task table row (file_edit + sync):**

If the "Quick Tasks Completed" table section in STATE.md does not exist, create it using file_edit tool after the `### Blockers/Concerns` section:

```markdown
### Quick Tasks Completed

| #   | Description | Date | Commit | Directory |
| --- | ----------- | ---- | ------ | --------- |
```

Append new row to the table using file_edit tool:

```markdown
| ${next_num} | ${DESCRIPTION} | ${date} | ${commit_hash} | [${next_num}-${slug}](./quick/${next_num}-${slug}/) |
```

**6d. Force state.json re-sync after the file_edit:**

```bash
gpd state load
```

This ensures the table content added via file_edit is synced to state.json. Do NOT skip this step — direct file_edit of STATE.md without `state load` causes STATE.md/state.json divergence.

---

**Step 7: Final commit and completion**

Stage and commit quick task artifacts:

```bash
PRE_CHECK=$(gpd pre-commit-check --files ${QUICK_DIR}/${next_num}-PLAN.md ${QUICK_DIR}/${next_num}-SUMMARY.md .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs(quick-${next_num}): ${DESCRIPTION}" --files ${QUICK_DIR}/${next_num}-PLAN.md ${QUICK_DIR}/${next_num}-SUMMARY.md .gpd/STATE.md
```

Get final commit hash:

```bash
commit_hash=$(git rev-parse --short HEAD)
```

Display completion output:

```
---

GPD > QUICK TASK COMPLETE

Quick Task ${next_num}: ${DESCRIPTION}

Summary: ${QUICK_DIR}/${next_num}-SUMMARY.md
Commit: ${commit_hash}

---

Ready for next task: /gpd:quick
```

</process>

<success_criteria>

- [ ] `.gpd/` directory exists
- [ ] User provides task description
- [ ] Slug generated (lowercase, hyphens, max 40 chars)
- [ ] Next number calculated (001, 002, 003...)
- [ ] Directory created at `.gpd/quick/NNN-slug/`
- [ ] `${next_num}-PLAN.md` created by planner
- [ ] `${next_num}-SUMMARY.md` created by executor
- [ ] STATE.md updated with quick task row
- [ ] Artifacts committed
</success_criteria>
