---
template_version: 1
---

# Executor Continuation Prompt Template

Template for spawning a fresh gpd-executor agent to continue plan execution after a checkpoint pause. Uses a fresh agent with explicit state instead of resume to avoid serialization issues with parallel tool calls.

Referenced by `workflows/execute-phase.md` checkpoint_handling step.

---

## Template

```markdown
<objective>
Continue executing plan {plan_number} of phase {phase_number}-{phase_name} from task {resume_task_number}.

Previous tasks are completed and committed. Verify prior commits exist, then continue from task {resume_task_number}: {resume_task_name}.

Return state updates (position, decisions, metrics) in your response -- do NOT write STATE.md directly.
</objective>

<prior_state>

### Completed Tasks

{completed_tasks_table}

### Checkpoint That Was Reached

**Type:** {checkpoint_type}
**User response:** {user_response}

</prior_state>

<resume_instructions>
{resume_instructions}
</resume_instructions>

<files_to_read>
Read these files at execution start using the file_read tool:
- Workflow: {GPD_INSTALL_DIR}/workflows/execute-plan.md
- Summary template: {GPD_INSTALL_DIR}/templates/summary.md
- Checkpoints ref: {GPD_INSTALL_DIR}/references/checkpoints.md
- Validation ref: {GPD_INSTALL_DIR}/references/verification-core.md
- Plan: {phase_dir}/{plan_file}
- State: .gpd/STATE.md
- Config: .gpd/config.json (if exists)
</files_to_read>

<verification_before_continuing>
Before executing task {resume_task_number}, verify that prior tasks' commits exist:

git log --oneline --grep="({phase}-{plan}):" | head -20

Compare against the completed tasks table above. If any expected commits are missing, STOP and report the discrepancy -- do not proceed with incomplete prior state.
</verification_before_continuing>

<success_criteria>

- [ ] Prior task commits verified on disk
- [ ] Checkpoint response incorporated into task {resume_task_number}
- [ ] Remaining tasks executed with mathematical rigor
- [ ] Each task committed individually
- [ ] Dimensional consistency verified at each step
- [ ] SUMMARY.md created in plan directory
- [ ] State updates returned (NOT written to STATE.md directly)
</success_criteria>
```

---

## Placeholders

| Placeholder               | Source                              | Example                                                                   |
| ------------------------- | ----------------------------------- | ------------------------------------------------------------------------- |
| `{plan_number}`           | Plan frontmatter                    | `03`                                                                      |
| `{phase_number}`          | Phase context                       | `03`                                                                      |
| `{phase_name}`            | Phase context                       | `phase-diagram`                                                           |
| `{resume_task_number}`    | Current task from checkpoint return | `3`                                                                       |
| `{resume_task_name}`      | Current task name from checkpoint   | `Review phase diagram topology`                                           |
| `{completed_tasks_table}` | From checkpoint return              | Markdown table: `\| Task \| Status \| Commit \| Files \|` with one row per completed task |
| `{checkpoint_type}`       | From checkpoint return              | `human-verify`                                                            |
| `{user_response}`         | User's response to checkpoint       | `approved` or `Select: option-a` or `done`                                |
| `{resume_instructions}`   | Generated from checkpoint type      | See table below                                                           |
| `{phase_dir}`             | Phase directory path                | `.gpd/phases/03-phase-diagram`                                       |
| `{plan_file}`             | Plan filename                       | `03-03-PLAN.md`                                                           |
| `{phase}`                 | Phase prefix                        | `03`                                                                      |
| `{plan}`                  | Plan prefix                         | `03`                                                                      |

---

## Resume Instructions by Checkpoint Type

| Checkpoint Type    | Resume Instructions Template                                                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `human-verify`     | User approved the result. Continue to task {resume_task_number} ({resume_task_name}) and proceed normally.                                   |
| `decision`         | User selected: {user_response}. Apply this choice in task {resume_task_number} and all subsequent tasks. Record as a decision in the SUMMARY. |
| `human-action`     | User completed the manual step. Verify the expected output exists before continuing to task {resume_task_number}.                             |

---

## Usage

**From execute-phase.md checkpoint_handling step:**

```python
task(
  subagent_type="gpd-executor",
  model="{executor_model}",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.\n\n" + filled_template,
  description="Continue {phase}-{plan} from task {resume_task_number}"
)
```

<!-- task() subagent_type and model parameters are runtime-specific. The installer adapts these to the target platform's delegation mechanism. -->

**Why fresh agent, not resume:** Resume relies on internal serialization that can break with parallel tool calls. Fresh agents with explicit prior state are more reliable and produce consistent results across platforms.

---

## Continuation Protocol

1. Orchestrator detects checkpoint return from executor agent
2. Orchestrator presents checkpoint details to user (execute-phase.md step 4)
3. User responds with approval/decision/action confirmation
4. Orchestrator fills this template with checkpoint state + user response
5. Orchestrator spawns fresh gpd-executor with filled template
6. New executor verifies prior commits, incorporates user response, continues execution
7. If executor hits another checkpoint, cycle repeats (step 1)
