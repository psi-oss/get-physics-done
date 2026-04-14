<purpose>
Execute small, ad-hoc physics tasks with GPD guarantees (atomic commits and durable state updates) while skipping optional agents (literature search, plan-checker, verifier). Quick mode routes through the canonical planner handoff, supports staged planner loading when available, tracks artifacts in `GPD/quick/`, and records completion through the structured state commands plus the quick-task summary files. Typical quick tasks include: quick derivation, dimensional check, order-of-magnitude estimate, limiting case verification, and bibliography lookup. Quick mode is NOT authorized to close theorem-style or `proof_obligation` work.
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
INIT=$(gpd --raw init quick "$DESCRIPTION")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `planner_model`, `executor_model`, `commit_docs`, `autonomy`, `next_num`, `slug`, `date`, `timestamp`, `quick_dir`, `task_dir`, `roadmap_exists`, `project_exists`, `planning_exists`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`.

If staged planner-loading fields appear in the init payload, treat them as authoritative for the planner handoff shape rather than reconstructing a separate quick-specific prompt contract.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after the plan for user approval before execution.
- `autonomy=balanced` (default): Execute without pausing unless the quick task reveals a real decision point.
- `autonomy=yolo`: Execute and commit without pausing.

**If `project_exists` is false:** Error -- Quick mode requires an initialized project with `GPD/PROJECT.md`. Run `gpd:new-project` first.

**If `planning_exists` is false:** Error -- Quick mode requires the `GPD/` workspace directory. Run `gpd:new-project` first.

Quick tasks can run mid-phase and do NOT require ROADMAP.md. They still require an initialized project workspace with `GPD/PROJECT.md` and the `GPD/` directory.
Quick mode still inherits the approved `project_contract` only when `project_contract_gate.authoritative` is true, and it still inherits the active reference ledger. Do not bypass required anchors, baselines, or forbidden-proxy constraints just because the task is small.

**Proof-obligation command block:** If the description or inherited contract indicates theorem-style work (`proof_obligation`, `theorem`, `lemma`, `corollary`, `proposition`, `claim`, `proof`, `prove`, `show that`, `existence`, `uniqueness`), STOP instead of using quick mode. Do not bypass this by asking for a "quick sketch", "light proof", or "just the main idea". Route explicitly to:

- `gpd:plan-phase <phase>` when this belongs in planned phase work
- `gpd:derive-equation "<goal>"` when you need a derivation/proof draft
- `gpd:verify-work <phase>` only after a canonical proof-redteam artifact exists

---

**Step 3: Create task directory**

Use `task_dir` from init JSON (for example, `GPD/quick/NNN-slug/`):

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

Spawn gpd-planner with the quick-mode context:

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

Apply this delegation note to every subagent spawn in this workflow; do not repeat it before individual spawn examples.

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.

<planning_context>

**Mode:** quick
**Directory:** ${QUICK_DIR}
**Description:** ${DESCRIPTION}

**Project State:**
Read the file at GPD/STATE.md

**Project Exists:** {project_exists}

**Project Contract:** {project_contract}
**Project Contract Gate:** {project_contract_gate}
**Project Contract Load Info:** {project_contract_load_info}
**Project Contract Validation:** {project_contract_validation}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

</planning_context>

<constraints>
- Create a SINGLE plan with 1-3 focused tasks
- Quick tasks should be atomic and self-contained
- No literature review phase, no checker phase
- If staged planner-loading fields are present in the init payload, use them as the source of truth for the handoff instead of inventing a separate quick-only contract
- If `project_contract_load_info.status` starts with `blocked` or `project_contract_validation.valid` is false, return `gpd_return.status: checkpoint` instead of drafting a plan from guessed scope. The `## CHECKPOINT REACHED` heading is presentation only.
- If the task is theorem-style or proof-bearing, return `gpd_return.status: checkpoint` and tell the user quick mode is blocked pending the full proof-redteam workflow.
- Target ~30% context usage (simple, focused)
</constraints>

<output>
Write plan to: ${QUICK_DIR}/${next_num}-PLAN.md
Return a structured `gpd_return` envelope. Use `gpd_return.status: completed` only when the plan file was written and named in `gpd_return.files_written`. Use `gpd_return.status: checkpoint` when user input is needed, `blocked` when the task cannot proceed without external repair, and `failed` when the handoff did not complete. The `## PLANNING COMPLETE` heading is presentation only.
</output>
",
  subagent_type="gpd-planner",
  model="{planner_model}",
  readonly=false,
  description="Quick plan: ${DESCRIPTION}"
)
```

**If the planner agent fails to spawn or returns an error:** Check if a plan file was written to `${QUICK_DIR}/${next_num}-PLAN.md` (agents write files first). If the plan exists, proceed to step 5. If no plan, offer: 1) Retry planner, 2) Create the plan in the main context, 3) Abort. Do not silently continue without a plan.

After planner returns:

1. Route on `gpd_return.status`, not on headings.
2. Verify plan exists at `${QUICK_DIR}/${next_num}-PLAN.md` and that the same path appears in `gpd_return.files_written`.
3. Treat any preexisting plan file as stale unless the child reported that exact path in `gpd_return.files_written` for this run.
4. If the planner returned `checkpoint`, present the checkpoint to the user and wait for the updated continuation handoff before proceeding.
5. If the planner returned `blocked` or `failed`, treat the handoff as incomplete unless a fresh plan file was created and named in `gpd_return.files_written`; then offer retry, main-context planning, or abort.
6. Extract plan count (typically 1 for quick tasks).
7. Report: "Plan created: ${QUICK_DIR}/${next_num}-PLAN.md"

If the plan file is missing, unreadable, stale, or absent from `gpd_return.files_written`, error: "Planner failed to create ${next_num}-PLAN.md"

If the plan declares specialized `tool_requirements`, run `gpd validate plan-preflight <PLAN.md>` before spawning the executor:

```bash
PLAN_TOOL_REQUIREMENTS=$(gpd frontmatter get "${QUICK_DIR}/${next_num}-PLAN.md" --field tool_requirements 2>/dev/null || true)
if [ -n "$PLAN_TOOL_REQUIREMENTS" ]; then
  PLAN_PREFLIGHT=$(gpd --raw validate plan-preflight "${QUICK_DIR}/${next_num}-PLAN.md")
  if [ $? -ne 0 ]; then
    echo "ERROR: plan-preflight failed: $PLAN_PREFLIGHT"
    # STOP — display the error to the user and do not proceed.
  fi
fi
```

---

**Step 5: Spawn executor**

Spawn gpd-executor with plan reference:

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

Execute quick task ${next_num}.

Plan: Read the file at ${QUICK_DIR}/${next_num}-PLAN.md
Project state: Read the file at GPD/STATE.md
Project contract: {project_contract}
Project contract gate: {project_contract_gate}
Project contract load info: {project_contract_load_info}
Project contract validation: {project_contract_validation}
Contract intake: {contract_intake}
Effective reference intake: {effective_reference_intake}
Active references: {active_reference_context}
Reference artifacts: {reference_artifacts_content}

<constraints>
- Execute all tasks in the plan
- Commit each task atomically
- Create summary at: ${QUICK_DIR}/${next_num}-SUMMARY.md
- Do NOT update ROADMAP.md (quick tasks are separate from planned phases)
- If proof-bearing work slipped through planning, STOP and return the reroute instead of executing. Quick mode must not produce a proof result without the mandatory proof-redteam gate.
- Return a structured `gpd_return` envelope with `gpd_return.status` and `gpd_return.files_written`; the `## PLANNING COMPLETE` / `## CHECKPOINT REACHED` headings are presentation only.
</constraints>
",
  subagent_type="gpd-executor",
  model="{executor_model}",
  readonly=false,
  description="Execute: ${DESCRIPTION}"
)
```

**If the executor agent fails to spawn or returns an error:** Check if any work was committed (run `git log --oneline -3`). If commits exist with the task's work, proceed to step 6 — the executor may have completed but failed to report back. If no commits, offer: 1) Retry executor, 2) Execute the plan in the main context, 3) Abort. The plan file is still available for re-execution.

After executor returns:

1. Verify summary exists at `${QUICK_DIR}/${next_num}-SUMMARY.md`
2. Extract commit hash from executor output
3. Report completion status

> **Handoff verification:** Do not trust the runtime handoff status by itself. Verify expected output files and git commits before treating a subagent as failed.

If summary not found, error: "Executor failed to create ${next_num}-SUMMARY.md"

Note: For quick tasks producing multiple plans (rare), spawn executors in parallel waves per execute-phase patterns.

---

**Step 6: Apply child-return effects**

Treat the executor summary as the canonical child-return artifact. Before any direct quick-task state updates, validate and apply its durable subset through the shared command path:

```bash
APPLY_RETURN=$(gpd apply-return-updates "${QUICK_DIR}/${next_num}-SUMMARY.md")
if [ $? -ne 0 ]; then
  echo "ERROR: apply-return-updates failed: $APPLY_RETURN"
  # STOP — show the structured errors and do not proceed.
fi
```

Route on `gpd_return.status` and the artifact gate, not on the human-readable headings:

- `gpd_return.status: completed` means the summary file passed the artifact gate and its durable child-return effects were applied.
- `gpd_return.status: checkpoint` means the quick task needs user input; present the checkpoint and spawn a fresh continuation handoff.
- `gpd_return.status: blocked` means the task cannot be completed without external repair.
- `gpd_return.status: failed` means the task did not complete and must be retried or handled manually.

Only proceed to the quick-task completion record after `apply-return-updates` succeeds and the summary file still exists on disk.

**Step 7: Update project state**

Update project state with quick task completion record using gpd commands (ensures STATE.md + state.json stay in sync):

**7a. Record quick task completion as a decision:**

```bash
gpd state add-decision --phase "quick-${next_num}" --summary "Quick task ${next_num}: ${DESCRIPTION}" --rationale "Ad-hoc task completed outside planned phases"
```

**7b. Update last activity:**

```bash
gpd state update "Last Activity" "${date}"
```

Treat the durable record for a quick task as:

- the decision entry written above via `gpd state add-decision`
- the updated `Last Activity` field via `gpd state update`
- the artifacts in `${QUICK_DIR}` (`${next_num}-PLAN.md`, `${next_num}-SUMMARY.md`, and any committed outputs)

If you want a human-facing index, put it in `GPD/quick/README.md` or in the quick-task summary.

---

**Step 8: Final commit and completion**

Stage and commit quick task artifacts:

```bash
PRE_CHECK=$(gpd pre-commit-check --files ${QUICK_DIR}/${next_num}-PLAN.md ${QUICK_DIR}/${next_num}-SUMMARY.md GPD/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs(quick-${next_num}): ${DESCRIPTION}" --files ${QUICK_DIR}/${next_num}-PLAN.md ${QUICK_DIR}/${next_num}-SUMMARY.md GPD/STATE.md
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

Ready for next task: gpd:quick
```

</process>

<success_criteria>

- [ ] `GPD/` directory exists
- [ ] User provides task description
- [ ] Slug generated (lowercase, hyphens, max 40 chars)
- [ ] Next number calculated (001, 002, 003...)
- [ ] Directory created at `GPD/quick/NNN-slug/`
- [ ] `${next_num}-PLAN.md` created by planner
- [ ] `${next_num}-SUMMARY.md` created by executor
- [ ] Structured state updated via `gpd state` commands
- [ ] Artifacts committed
</success_criteria>
