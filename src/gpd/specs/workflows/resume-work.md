<trigger>
Use this workflow when:
- Starting a new session on an existing research project
- User says "continue", "what's next", "where were we", "resume"
- Any planning operation when GPD/ already exists
- User returns after time away from project
</trigger>

<purpose>
Restore the selected project's full context so "Where were we?" has an immediate answer.

@{GPD_INSTALL_DIR}/references/orchestration/resume-vocabulary.md
</purpose>

<required_reading>
@{GPD_INSTALL_DIR}/references/orchestration/continuation-format.md
@{GPD_INSTALL_DIR}/references/orchestration/state-portability.md
@{GPD_INSTALL_DIR}/templates/state-json-schema.md
</required_reading>

<process>

<step name="initialize">
Load the shared resume context in one call. `gpd:resume-work` is the guided runtime path, `gpd resume` is the public local read-only summary, `gpd resume --recent` is the cross-project discovery surface and workspace picker, and `gpd --raw resume` returns the canonical public view:

```bash
INIT=$(gpd --raw resume)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON once and read it semantically:

- **Requested workspace availability:** `workspace_state_exists`, `workspace_roadmap_exists`, `workspace_project_exists`, `workspace_planning_exists`
- **Availability and contract authority:** `state_exists`, `roadmap_exists`, `project_exists`, `planning_exists`, `commit_docs`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`
- **Canonical continuation and recovery authority:** `resume_surface_schema_version`, `active_resume_kind`, `active_resume_origin`, `active_resume_pointer`, `active_bounded_segment`, `derived_execution_head`, `active_resume_result`, `continuity_handoff_file`, `recorded_continuity_handoff_file`, `missing_continuity_handoff_file`, `has_continuity_handoff`, `resume_candidates`, `execution_resumable`, `execution_paused_at`, `execution_review_pending`, `execution_pre_fanout_review_pending`, `execution_skeptical_requestioning_required`, `execution_downstream_locked`, `has_interrupted_agent`, `interrupted_agent_id`
- **Machine advisory state:** `machine_change_detected`, `machine_change_notice`, `current_hostname`, `current_platform`, `session_hostname`, `session_platform`

@{GPD_INSTALL_DIR}/references/orchestration/resume-vocabulary.md

The recent-project list is advisory and machine-local; once you choose a workspace, `gpd:resume-work` reloads that project's canonical state.

When `active_resume_result` is present, treat it as the hydrated canonical result context for the current resume target. Use its `id` as the continuity anchor, but prefer its structured fields for the user-facing resume summary instead of restating only the raw identifier.

`workspace_state_exists` means the requested workspace could recover usable state from `GPD/state.json`, `GPD/state.json.bak`, or `GPD/STATE.md`. A stray unreadable file path by itself does not count as recoverable state.
`state_exists` means the selected project root could recover usable state from `GPD/state.json`, `GPD/state.json.bak`, or `GPD/STATE.md`.
Use `workspace_*` to judge the user-requested workspace before auto-selection; use the selected-project fields after re-entry resolution.

The shared resume resolver distinguishes canonical continuation authority, continuity mirrors, and the derived execution head:

- **storage authority:** `GPD/state.json`, with `GPD/state.json.bak` as the recovery backup; canonical `continuation` lives here
- **editable mirror:** `GPD/STATE.md`
- **temporary handoff artifact:** `GPD/phases/.../.continue-here.md`
- **derived execution head / live execution overlay:** `GPD/observability/current-execution.json`, used as a compatibility projection when canonical bounded-segment state is absent

The shared resume resolver is canonical-first: `state.json.continuation` wins, the canonical bounded segment and recorded handoff fields define the primary resume target, and the derived execution head only fills compatibility gaps when bounded-segment state is missing. Do not treat a single `.continue-here.md` file or compatibility snapshot as the sole authority.

**If `planning_exists` is false:** This is a new project - route to gpd:new-project and do not attempt STATE.md reconstruction.
**If `state_exists` is false but `roadmap_exists` or `project_exists` is true:** Offer to reconstruct STATE.md from the existing project artifacts.

If `active_resume_kind="bounded_segment"` and `active_bounded_segment` exists, treat that as the primary bounded resume target. The derived execution head may still project the bounded segment when canonical continuation is missing or incomplete, but it does not define a second resume system.

`active_resume_kind` is narrower than the overall recovery status. A recorded handoff, a missing recorded handoff artifact, or advisory live execution can still exist when `active_resume_kind` is `None`; those compatibility cues still surface through `continuity_handoff_file` and `missing_continuity_handoff_file`, but the canonicalized `gpd --raw resume` surface keeps only the top-level public fields.

If `active_resume_result` exists, surface it alongside the primary resume target so `gpd:resume-work` can recover the last canonical result context immediately. If a resume candidate carries a hydrated `last_result`, prefer that payload over `last_result_id`-only notes while still preserving the ID as the rerun anchor.

If `derived_execution_head` exists but `execution_resumable` is false, treat that live snapshot as advisory context only. If `active_resume_pointer` is empty, non-project, or missing on disk, call that out explicitly; in all such cases it is not a ranked bounded-segment resume candidate and does not justify `active_resume_kind="bounded_segment"`.

If `active_bounded_segment.pre_fanout_review_pending` is true, the gate is still live even when a resume file exists. If `active_bounded_segment.pre_fanout_review_cleared` is true, the review outcome was recorded but the separate fanout unlock is still missing.

If `active_bounded_segment.first_result_gate_pending` is true, do not treat later routine work or a resume artifact as proof that the first-result gate passed. Resume must still verify whether decisive evidence was actually produced or explicitly waived.
</step>

<step name="load_state">

**machine_change_detection:** Compare the current hostname/platform with `state.json.continuation.machine.hostname` and `state.json.continuation.machine.platform`. If they differ, display the non-blocking machine-change notice from INIT and recommend rerunning the installer so runtime-local config stays current.

**canonical handoff path:** `gpd:pause-work` records a canonical phase handoff in `GPD/phases/.../.continue-here.md` and stores the durable pointer in `state.json.continuation.handoff`. That handoff file is temporary, not the authoritative store for project position or resume ranking. If a handoff file is missing but state authority is intact, report the missing artifact rather than treating the whole project as lost. Use `gpd resume --recent` first when you need to rediscover the project.

Read and parse STATE.md, then PROJECT.md:

```bash
cat GPD/STATE.md
cat GPD/PROJECT.md
```

**From STATE.md extract:**

- **Project Reference**: Core research question and current focus
- **Current Position**: Phase X of Y, Plan A of B, Status
- **Progress**: Visual progress bar
- **Recent Decisions**: Key decisions affecting current work (method choices, convention selections, approximation schemes)
- **Pending Todos**: Ideas captured during sessions
- **Blockers/Concerns**: Issues carried forward (divergences, instabilities, missing data)
- **Session Continuity**: Last session timestamp, stopped-at continuation point, resume file pointer, previous hostname/platform, and any machine-change notice

**From PROJECT.md extract:**

- **What This Is**: Current accurate description of the research
- **Research Questions**: Primary and secondary questions being investigated
- **Requirements:** Validated, Active, Out of Scope
- **Key Decisions**: Full decision log with outcomes (conventions, methods, approximations)
- **Constraints**: Hard limits on the research (computational resources, time, available data)

**Machine-readable carry-forward context from INIT JSON:**

- `project_contract` is the authoritative structured scoping and anchor contract only when `project_contract_gate.authoritative` is true.
- `project_contract_load_info` and `project_contract_validation` remain visible gate inputs and diagnostics; they explain why the gate is blocked, but they are not the authority themselves.
- `effective_reference_intake` is the authoritative carry-forward ledger for must-read refs, prior outputs, baselines, user anchors, and context gaps.
- `active_reference_context` and `reference_artifacts_content` are readability aids for that ledger, not substitutes for it.
- Do not reconstruct contract-critical anchors only from `STATE.md` / `PROJECT.md` prose when INIT already provided the structured ledger, and do not use reconstruction to override a missing planning workspace.
- If the current readable `state.json` carries a malformed `project_contract`, surface that primary-state block. Do not silently promote `state.json.bak` as the current authoritative contract while the live state file is still readable.
- If `project_contract_gate.authoritative` is false, present that contract as visible-but-blocked and route the next action to contract repair before planning or execution.

</step>

<step name="restore_persistent_state">
**Read cumulative derivation history from `GPD/DERIVATION-STATE.md`:**

This step reconstructs the full derivation history that has accumulated across
all previous sessions, preventing lossy compression across context resets.

```bash
# Check if persistent derivation state exists
if [ -f GPD/DERIVATION-STATE.md ]; then
  echo "=== DERIVATION-STATE.md found ==="
  cat GPD/DERIVATION-STATE.md
else
  echo "No DERIVATION-STATE.md found (first session or pre-persistence project)"
fi
```

**If DERIVATION-STATE.md exists:**

### Enforce Session Cap (Last 5 Sessions)

Before loading DERIVATION-STATE.md into context, enforce the hard cap to keep the file bounded:

```bash
SESSION_COUNT=$(grep -c "^## Session:" GPD/DERIVATION-STATE.md 2>/dev/null || echo 0)

if [ "$SESSION_COUNT" -gt 5 ]; then
  echo "DERIVATION-STATE.md has ${SESSION_COUNT} session blocks (cap: 5). Pruning oldest..."

  # Atomic read-modify-write: write to PID-unique .tmp, validate, then replace
  TMP_FILE="GPD/DERIVATION-STATE.md.tmp.$$"
  trap "rm -f '$TMP_FILE'" EXIT

  KEEP_FROM=$(grep -n "^## Session:" GPD/DERIVATION-STATE.md | tail -5 | head -1 | cut -d: -f1)
  HEADER_END=$(grep -n "^## Session:" GPD/DERIVATION-STATE.md | head -1 | cut -d: -f1)
  HEADER_END=$((HEADER_END - 1))
  {
    head -n "$HEADER_END" GPD/DERIVATION-STATE.md
    echo ""
    echo "> Older session entries archived in git history."
    echo "> Use \`git log -p -- GPD/DERIVATION-STATE.md\` to recover."
    echo ""
    tail -n +"$KEEP_FROM" GPD/DERIVATION-STATE.md
  } > "$TMP_FILE"

  TMP_LINES=$(wc -l < "$TMP_FILE")
  if [ "$TMP_LINES" -lt 5 ]; then
    echo "WARNING: Pruned file suspiciously small (${TMP_LINES} lines). Keeping original."
    rm -f "$TMP_FILE"
  elif ! grep -q "^# Derivation State" "$TMP_FILE"; then
    echo "WARNING: Pruned file missing required header. Keeping original."
    rm -f "$TMP_FILE"
  else
    cp "$TMP_FILE" GPD/DERIVATION-STATE.md && \
      rm -f "$TMP_FILE" || \
      echo "WARNING: Failed to replace DERIVATION-STATE.md. Original preserved."
  fi
  trap - EXIT
fi
```

This is the same cap enforcement logic used by pause-work.md. It keeps the 5 most recent `## Session:` blocks and archives older entries via git history.

1. **Read the full file** to reconstruct the complete equation/convention/result history across all sessions. If the latest handoff or session continuity metadata already carries a canonical `last_result_id`, prefer that value as the rerun anchor before rediscovering the target from prose or older summaries.
2. **Cross-reference against state.json intermediate_results** to find any gaps:
   - Are there result IDs in DERIVATION-STATE.md that are missing from state.json? (suggests state.json was reset or corrupted)
   - Are there intermediate_results in state.json that are NOT in DERIVATION-STATE.md? (suggests a session did not properly pause)
   - Does the newest handoff/session record expose a `last_result_id` that should be reused on rerun instead of searching again? If so, surface it as the preferred continuity anchor.
3. **Count and summarize** what was restored:
   - Total equations established across all sessions
   - Total conventions locked in
   - Total intermediate results recorded
   - Total approximations catalogued
4. **Present the restoration summary:**

```
>> Persistent derivation state restored:
   - Equations: [X] established across [N] sessions
   - Conventions: [Y] locked (metric: [sig], Fourier: [conv], ...)
   - Intermediate results: [Z] recorded (IDs: [list])
   - Approximations: [W] catalogued
   [If gaps found:]
   >> WARNING: [description of gaps found between DERIVATION-STATE.md and state.json]
```

**If DERIVATION-STATE.md does NOT exist:**

- This is either the first session or a project that predates the persistence mechanism.
- If state.json has intermediate_results, offer to bootstrap DERIVATION-STATE.md from them.
- Flag: "No persistent derivation history (will be created on next pause)"

</step>

<step name="verify_conventions">
**Convention verification** — after days away, convention drift is the most common source of silent errors when resuming:

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — conventions may have drifted since last session"
  echo "$CONV_CHECK"
fi
```

If convention check fails, flag in the status presentation (step present_status) so the user sees it before resuming work. Convention mismatches between locked conventions and CONVENTIONS.md should be resolved before any new derivations.
</step>

<step name="check_incomplete_work">
Look for incomplete work that needs attention:

```bash
# Check for plans without summaries (incomplete execution)
for plan in GPD/phases/*/*-PLAN.md; do
  summary="${plan/PLAN/SUMMARY}"
  [ ! -f "$summary" ] && echo "Incomplete: $plan"
done 2>/dev/null

# Check for interrupted agents (use has_interrupted_agent and interrupted_agent_id from init)
if [ "$has_interrupted_agent" = "true" ]; then
  echo "Interrupted agent: $interrupted_agent_id"
fi
```

**Bounded execution segment detection:** If `active_resume_kind` is `bounded_segment`, `execution_resumable` is true, and `active_resume_pointer` is present, treat that bounded continuation as the primary resume target. The runtime currently ranks three semantic recovery families into `resume_candidates`: a resumable live execution snapshot, a recorded handoff, and an interrupted-agent marker. The backend may still retain compatibility intake for those families. If the live snapshot lacks a portable usable resume file, keep it visible only as advisory context. Do NOT invent additional candidates from plan files without summaries, auto-checkpoints, or other ad hoc checkpoints.

The shared resume resolver keeps the derived execution head and the temporary handoff artifact subordinate to the storage authority chain. They refine the continuation target; they do not replace `GPD/state.json > GPD/state.json.bak > GPD/STATE.md`, and the compatibility mirror only backfills bounded-segment state for legacy compatibility when canonical bounded-segment state is absent. Nested raw-envelope aliases never outrank canonical fields.

Reason-scoped clears still matter on resume: a `first_result` clear does not retire `pre_fanout` or skeptical fields, and a `fanout unlock` does not clear the review gate by itself.

When resuming from `first_result` or skeptical state, ask one concrete question first: "What decisive evidence is still owed before downstream work is trustworthy?" Do not resume fanout based only on proxy-looking success or "seems on track" prose.

**Context budget note:** Context restoration (loading STATE.md, DERIVATION-STATE.md, PROJECT.md, the active execution snapshot, and roadmap) consumes approximately 15-20% of a fresh context window. Budget the remaining ~80% for actual research work. If the project has extensive derivation history or many prior decisions, restoration may consume up to 25%.

**If PLAN without SUMMARY exists:**

- Execution was started but not completed
- Flag: "Found incomplete plan execution"

**If interrupted agent found and no newer bounded execution segment exists:**

- Subagent was spawned but session ended before completion
- Read agent-history.json for task details
- Flag: "Found interrupted agent"
  </step>

<step name="present_status">
Present complete research project status to user:

```
+================================================+
|  RESEARCH PROJECT STATUS                       |
+================================================+
|  Investigating:                                |
|  [one-liner from PROJECT.md "What This Is"]    |
|                                                |
|  Phase: [X] of [Y] - [Phase name]              |
|  Plan:  [A] of [B] - [Status]                  |
|  Progress: [||||||....] XX%                    |
|                                                |
|  Last activity: [date] - [what happened]       |
+================================================+

[If DERIVATION-STATE.md found:]
>> Persistent derivation history restored:
    - Equations: [X] across [N] sessions
    - Conventions: [Y] locked
    - Intermediate results: [Z] recorded
    - Approximations: [W] catalogued

[If `active_resume_kind` is `bounded_segment` and `active_bounded_segment` has a resume file:]
>> Research checkpoint detected:
    - Resume artifact: [resume_file]
    - Derivation state: [brief summary from the active execution snapshot]
    - Parameters in scope: [key parameter values]
    - Last result obtained: [most recent intermediate result]
    - Next planned step: [what was planned before pausing]

[If `continuity_handoff_file` exists and `execution_resumable` is false:]
>> Recorded handoff available:
    - Resume artifact: [continuity_handoff_file]
    - Status: recoverable recorded handoff; no resumable live execution snapshot is currently active
    - Note: this can coexist with an advisory live execution snapshot

[If `missing_continuity_handoff_file` exists:]
>> Recorded handoff artifact is missing:
    - Resume artifact: [missing_continuity_handoff_file]
    - Status: continuity metadata exists, but the recorded handoff file is missing from this workspace
    - Action: repair or recreate the handoff target before treating it as a resumable local target

[If `derived_execution_head` exists and `execution_resumable` is false:]
>> Live execution snapshot detected:
    - Status: advisory only; no bounded resume segment is currently active
    - [If `active_resume_pointer` is empty, non-project, or missing on disk:] the stored resume pointer is not portable or no longer resolves
    - Use: recover context about the last gate or paused task, but do not treat it as a resumable bounded segment

[If machine_change_detected is true:]
>> Machine change detected:
    - Last active on: [session_hostname] ([session_platform])
    - Current machine: [current_hostname] ([current_platform])
    - Action: rerun the installer if runtime-local config may be stale

[If `project_contract_gate.authoritative` is false:]
>> Contract repair required:
    - Load status: [project_contract_load_info.status]
    - Blocking detail: [first blocker or validation error]
    - Action: repair the contract/state integrity issue before planning or execution
    - Note: the structured contract stays visible for context, but it is not approved execution scope

[If `active_bounded_segment` is waiting on review:]
>> Live execution gate detected:
    - Gate: [checkpoint_reason]
    - First result ready: [yes/no]
    - Downstream fanout locked: [yes/no]
    - Review accepted but unlock still pending: [yes/no from pre_fanout_review_cleared && downstream_locked]
    - Skeptical re-questioning required: [yes/no]
    - Why the gate fired: [skeptical_requestioning_summary if present]
    - Weakest unchecked anchor: [if present]
    - Fastest disconfirming observation: [if present]

[If incomplete work found:]
>> Incomplete work detected:
    - [active execution gate or incomplete plan]

[If interrupted agent found:]
>> Interrupted agent detected:
    Agent ID: [id]
    Task: [task description from agent-history.json]
    Interrupted: [timestamp]

    Resume with: task tool (resume parameter with agent ID)

[If pending todos exist:]
[N] pending todos -- gpd:check-todos to review

[If blockers exist:]
>> Carried concerns:
    - [blocker 1]
    - [blocker 2]

[If alignment is not checked:]
>> Brief alignment: [status] - [assessment]
```

</step>

<step name="determine_next_action">
Based on project state, determine the most logical next action:

**If `project_contract_gate.authoritative` is false:**
-> Primary: Repair the blocked contract or state-integrity issue before planning or execution
-> Option: Inspect the blocked contract context and supporting diagnostics without resuming downstream work

**If `active_resume_kind="bounded_segment"` and `active_bounded_segment` exists:**
-> Primary: Continue the bounded execution segment using its current cursor, checkpoint cause, downstream-lock state, and resume preconditions
-> If `checkpoint_reason=first_result`, `checkpoint_reason=pre_fanout`, or skeptical re-questioning is required: treat the next action as a review/replan decision whenever decisive evidence is still missing, not a routine execution resume
-> Do not resume downstream fanout until the gate has an explicit clear/override outcome and, for `pre_fanout`, the matching fanout-unlock transition
-> Option: Review another ranked resume candidate from `resume_candidates`

**If `derived_execution_head` exists and `execution_resumable` is false:**
-> Primary: Treat the live snapshot as advisory continuity context only and prefer a valid recorded handoff or repair action
-> Option: Inspect the live gate state without claiming the bounded segment is directly resumable

**If interrupted agent exists:**
-> Primary: Resume interrupted agent (Task tool with resume parameter)
-> Option: Start fresh (abandon agent work)

**If `continuity_handoff_file` exists and `execution_resumable` is false and no interrupted agent exists:**
-> Primary: Continue from the recorded handoff in the current workspace
-> Option: Inspect any advisory live execution context without claiming a bounded segment is active

**If `missing_continuity_handoff_file` exists and no interrupted agent exists:**
-> Primary: Repair or recreate the recorded handoff artifact before treating it as a resumable local target
-> Option: Inspect advisory live execution context or other recorded recovery state without claiming a bounded segment is active

**If incomplete plan (PLAN without SUMMARY) and no higher-priority blocker is active:**
-> Primary: Complete the incomplete plan
-> Option: Abandon and move on

**If phase in progress, all plans complete:**
-> Primary: Transition to next phase
-> Option: Review completed work

**If phase ready to plan:**
-> Check if CONTEXT.md exists for this phase:

- If CONTEXT.md missing:
  -> Primary: Discuss phase vision (how user imagines the physics working out)
  -> Secondary: Plan directly (skip context gathering)
- If CONTEXT.md exists:
  -> Primary: Plan the phase
  -> Option: Review roadmap

**If phase ready to execute:**
-> Primary: Execute next plan
-> Option: Review the plan first
</step>

<step name="offer_options">
Present contextual options based on project state:

```
What would you like to do?

[Primary action based on state - e.g.:]
1. Resume interrupted agent [if interrupted agent found]
   OR
1. Execute phase (gpd:execute-phase {phase})
   OR
1. Discuss Phase 3 context (gpd:discuss-phase 3) [if CONTEXT.md missing]
   OR
1. Plan Phase 3 (gpd:plan-phase 3) [if CONTEXT.md exists or discuss option declined]

[Secondary options:]
2. Review current phase status
3. Check pending todos ([N] pending)
4. Review brief alignment
5. Something else
```

**Note:** When offering phase planning, check for CONTEXT.md existence first:

```bash
ls GPD/phases/${current_phase_slug}/*-CONTEXT.md 2>/dev/null
```

If missing, suggest discuss-phase before plan. If exists, offer plan directly.

Wait for user selection.
</step>

<step name="route_to_workflow">
Based on user selection, route to appropriate workflow:

- **Execute plan** -> Show the exact next command after clearing:

  ```
  ---

  ## Next Up

  **{phase}-{plan}: [Plan Name]** -- [objective from PLAN.md]

  `gpd:execute-phase {phase}`

  <sub>`/clear` first, then run `gpd:execute-phase {phase}`</sub>

  ---
  ```

- **Plan phase** -> Show the exact next command after clearing:

  ```
  ---

  ## Next Up

  **Phase [N]: [Name]** -- [Goal from ROADMAP.md]

  `gpd:plan-phase [phase-number]`

  <sub>`/clear` first, then run `gpd:plan-phase [phase-number]`</sub>

  ---

  **Also available:**
  - `gpd:discuss-phase [N]` -- gather context first
  - `gpd:research-phase [N]` -- investigate unknowns

  ---
  ```

- **Transition** -> ./transition.md
- **Check todos** -> Read GPD/todos/pending/, present summary
- **Review alignment** -> Read PROJECT.md, compare to current state
- **Something else** -> Ask what they need
  </step>

<step name="update_continuation">
Before proceeding to routed workflow, refresh canonical continuation via CLI
(which then reprojects STATE.md and the legacy `session` continuity mirror):

```bash
gpd state record-session \
  --stopped-at "Session resumed, proceeding to [action]" \
  --resume-file "[updated if applicable; omit to keep the current pointer, or pass `—` to clear it]"
```

This ensures the canonical continuation payload reflects the resumed handoff state if the session ends unexpectedly. STATE.md and the legacy `session` fields should mirror that authoritative update after persistence.
</step>

</process>

<reconstruction>
If STATE.md is missing but other artifacts exist and `planning_exists` is true:

"STATE.md missing. Reconstructing from artifacts..."

1. Read PROJECT.md -> Extract "What This Is" and Core Research Question
2. Read ROADMAP.md -> Determine phases, find current position
3. Scan \*-SUMMARY.md files -> Extract decisions, concerns
4. Count pending todos in GPD/todos/pending/
5. Check current execution snapshot -> Session continuity

Reconstruct and write STATE.md, then proceed normally.

If `planning_exists` is false, skip reconstruction and route to `gpd:new-project` instead.

This handles cases where:

- Project predates STATE.md introduction
- File was accidentally deleted
- Cloning repo without full GPD/ state
  </reconstruction>

<quick_resume>
If user says "continue" or "go":

- Load state silently
- Determine primary action
- Execute immediately without presenting options

"Continuing from [state]... [action]"
</quick_resume>

<success_criteria>
Resume is complete when:

- [ ] STATE.md loaded (or reconstructed)
- [ ] DERIVATION-STATE.md read and cross-referenced with state.json (if it exists)
- [ ] DERIVATION-STATE.md pruned and capped to last 5 sessions (if applicable)
- [ ] Persistent derivation history restored and summarized (equations, conventions, results, approximations)
- [ ] Any gaps between DERIVATION-STATE.md and state.json flagged to user
- [ ] Incomplete work detected and flagged
- [ ] Research context restored (derivation state, parameters, intermediate results, approximations)
- [ ] Clear status presented to user
- [ ] Contextual next actions offered
- [ ] User knows exactly where the research project stands
- [ ] Session continuity updated
</success_criteria>
