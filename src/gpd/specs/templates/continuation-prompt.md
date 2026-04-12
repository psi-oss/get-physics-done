---
template_version: 1
---

# Executor Continuation Prompt Template

Template for spawning a fresh gpd-executor agent to continue plan execution after a checkpoint pause. This is a fresh continuation handoff owned by the orchestrator, not an in-run wait or resume-in-place. Uses a fresh agent with explicit state instead of resume to avoid serialization issues with parallel tool calls. The `<execution_segment>` block is the workflow/runtime handoff payload; persisted bounded-segment schema details are owned by the canonical schema docs listed in `docs/schema-registry-ownership.md`.

Persisted bounded-segment fields: `resume_file`, `phase`, `plan`, `segment_id`, `segment_status`, `checkpoint_reason`, `waiting_reason`, `blocked_reason`, `waiting_for_review`, `first_result_gate_pending`, `pre_fanout_review_pending`, `pre_fanout_review_cleared`, `skeptical_requestioning_required`, `downstream_locked`, `skeptical_requestioning_summary`, `weakest_unchecked_anchor`, `disconfirming_observation`, `transition_id`, `last_result_id`, `updated_at`, `source_session_id`, `recorded_by`.

If the checkpoint payload names expected artifacts, verify them on disk before continuing; returned text alone is not enough.

Referenced by `workflows/execute-phase.md` checkpoint_handling step.

---

## Continuation Template

```markdown
<objective>
This is a fresh continuation handoff owned by the orchestrator. Do not wait for the user inside the spawned run.
Continue executing plan {plan_number} of phase {phase_number}-{phase_name} from task {resume_task_number}.

Previous tasks are completed and committed. Verify prior commits exist, then continue from task {resume_task_number}: {resume_task_name}.

Return state updates (position, decisions, metrics) in your response -- do NOT write STATE.md directly. Treat this as continuation of bounded execution segment `{segment_id}`, not as a fresh unbounded run.
</objective>

<prior_state>

### Completed Tasks

{completed_tasks_table}

### Checkpoint That Was Reached

**Type:** {checkpoint_type}
**User response:** {user_response}

</prior_state>

<execution_segment>
{execution_segment}
</execution_segment>

`execution_segment` is the transient runtime handoff payload. Persisted bounded-stop and compatibility projection semantics are owned by the canonical schema docs listed in `docs/schema-registry-ownership.md`; do not duplicate the field vocabulary here. Clear or replace the persisted bounded stop when it is consumed, retired, or superseded by a newer segment.

If the execution segment indicates `pre_fanout_review_pending: true`, do not unlock downstream dependent work until the review outcome has been incorporated into this continuation.

If the execution segment also indicates `pre_fanout_review_cleared: true`, treat that as "review accepted, unlock still outstanding" rather than "gate retired." The continuation must preserve the separate fanout-unlock transition.

If the execution segment indicates `skeptical_requestioning_required: true`, treat the user response as a framing decision. Carry forward the skeptical summary, weakest unchecked anchor, and disconfirming observation into the resumed plan logic instead of treating this as a routine approval.

Do not assume a `first_result` or `pre_fanout` clear also clears skeptical re-questioning. If skeptical state was present, it must be retired explicitly in the continuation path.

If the execution segment indicates `first_result_gate_pending: true`, do not reinterpret that gate as passed just because the result looks plausible. Continue only after the review outcome has been made explicit in this continuation.

<protocol_bundles>
{protocol_bundle_context}
</protocol_bundles>

<resume_instructions>
{resume_instructions}
</resume_instructions>

<files_to_read>
Read these files at execution start using the file_read tool:
- Workflow: {GPD_INSTALL_DIR}/workflows/execute-plan.md
- Summary template: {GPD_INSTALL_DIR}/templates/summary.md
- Checkpoints ref: {GPD_INSTALL_DIR}/references/orchestration/checkpoints.md
- Validation ref: {GPD_INSTALL_DIR}/references/verification/core/verification-core.md
- Plan: {phase_dir}/{plan_file}
- State: GPD/STATE.md
- Config: GPD/config.json (if exists)
</files_to_read>

<verification_before_continuing>
Before executing task {resume_task_number}, verify that prior tasks' commits exist:

git log --oneline --grep="({phase}-{plan}):" | head -20

Compare against the completed tasks table above. If any expected commits are missing, STOP and report the discrepancy -- do not proceed with incomplete prior state.

If the checkpoint or execution segment names expected artifacts, verify them on disk before continuing; do not treat returned text alone as sufficient evidence.

Also verify the bounded execution segment still satisfies its resume preconditions:

- the checkpoint cause is understood
- any required user decision or review outcome is now present
- any first-result, skeptical, or pre-fanout gate has the matching explicit clear/override outcome
- any pre-fanout lock has the separate fanout-unlock transition before dependent work resumes
- the segment has not already been superseded by a newer continuation state
</verification_before_continuing>

<success_criteria>

- [ ] Prior task commits verified on disk
- [ ] Checkpoint response incorporated into task {resume_task_number}
- [ ] Execution segment cursor advanced or a new checkpoint segment returned
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
| `{execution_segment}`     | Runtime handoff payload             | Segment JSON or markdown block whose persisted bounded-segment subset contains exactly the canonical continuation fields listed above |
| `{protocol_bundle_context}` | Selected protocol bundle summary | Additive specialized-loading guidance carried across continuations |
| `{phase_dir}`             | Phase directory path                | `GPD/phases/03-phase-diagram`                                       |
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

**Why fresh agent, not resume:** Resume relies on internal serialization that can break with parallel tool calls. Fresh agents with explicit prior state and an explicit `execution_segment` block are more reliable and produce consistent results across platforms.

---

## Continuation Protocol

1. Orchestrator detects checkpoint return from executor agent
2. Orchestrator presents checkpoint details to user (execute-phase.md step 4)
3. User responds with approval/decision/action confirmation
4. Orchestrator fills this template with checkpoint state + bounded `execution_segment` + user response
5. Orchestrator spawns fresh gpd-executor with filled template
6. New executor verifies prior commits, incorporates user response, verifies any required artifacts, and continues execution
7. If executor hits another checkpoint, cycle repeats (step 1)
