<trigger>
Use this workflow when:
- Starting a new session on an existing research project
- User says "continue", "what's next", "where were we", "resume"
- Any planning operation when .gpd/ already exists
- User returns after time away from project
</trigger>

<purpose>
Instantly restore full research project context so "Where were we?" has an immediate, complete answer -- including the state of derivations, parameter values, intermediate results, and theoretical assumptions.
</purpose>

<required_reading>
@{GPD_INSTALL_DIR}/references/orchestration/continuation-format.md
</required_reading>

<process>

<step name="initialize">
Load all context in one call:

```bash
INIT=$(gpd init resume)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `state_exists`, `roadmap_exists`, `project_exists`, `planning_exists`, `has_interrupted_agent`, `interrupted_agent_id`, `commit_docs`, `project_contract`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`, `active_execution_segment`, `segment_candidates`, `resume_mode`, `execution_resumable`, `execution_resume_file`, `execution_paused_at`, `execution_review_pending`, `execution_pre_fanout_review_pending`, `execution_skeptical_requestioning_required`, `execution_downstream_locked`.

**If `state_exists` is true:** Proceed to load_state
**If `state_exists` is false but `roadmap_exists` or `project_exists` is true:** Offer to reconstruct STATE.md
**If `planning_exists` is false:** This is a new project - route to /gpd:new-project

If `resume_mode="bounded_segment"` and `active_execution_segment` exists, treat that as the primary resume target. Do not infer a second resume system from ad hoc handoff files.

If `active_execution_segment.pre_fanout_review_pending` is true, the gate is still live even when a resume file exists. If `active_execution_segment.pre_fanout_review_cleared` is true, the review outcome was recorded but the separate fanout unlock is still missing.

If `active_execution_segment.first_result_gate_pending` is true, do not treat later routine work or a resume artifact as proof that the first-result gate passed. Resume must still verify whether decisive evidence was actually produced or explicitly waived.
</step>

<step name="load_state">

Read and parse STATE.md, then PROJECT.md:

```bash
cat .gpd/STATE.md
cat .gpd/PROJECT.md
```

**From STATE.md extract:**

- **Project Reference**: Core research question and current focus
- **Current Position**: Phase X of Y, Plan A of B, Status
- **Progress**: Visual progress bar
- **Recent Decisions**: Key decisions affecting current work (method choices, convention selections, approximation schemes)
- **Pending Todos**: Ideas captured during sessions
- **Blockers/Concerns**: Issues carried forward (divergences, instabilities, missing data)
- **Session Continuity**: Where we left off, any resume files

**From PROJECT.md extract:**

- **What This Is**: Current accurate description of the research
- **Research Questions**: Primary and secondary questions being investigated
- **Requirements:** Validated, Active, Out of Scope
- **Key Decisions**: Full decision log with outcomes (conventions, methods, approximations)
- **Constraints**: Hard limits on the research (computational resources, time, available data)

**Machine-readable carry-forward context from INIT JSON:**

- `project_contract` is the authoritative structured scoping and anchor contract when present.
- `effective_reference_intake` is the authoritative carry-forward ledger for must-read refs, prior outputs, baselines, user anchors, and context gaps.
- `active_reference_context` and `reference_artifacts_content` are readability aids for that ledger, not substitutes for it.
- Do not reconstruct contract-critical anchors only from `STATE.md` / `PROJECT.md` prose when INIT already provided the structured ledger.

</step>

<step name="restore_persistent_state">
**Read cumulative derivation history from `.gpd/DERIVATION-STATE.md`:**

This step reconstructs the full derivation history that has accumulated across
all previous sessions, preventing lossy compression across context resets.

```bash
# Check if persistent derivation state exists
if [ -f .gpd/DERIVATION-STATE.md ]; then
  echo "=== DERIVATION-STATE.md found ==="
  cat .gpd/DERIVATION-STATE.md
else
  echo "No DERIVATION-STATE.md found (first session or pre-persistence project)"
fi
```

**If DERIVATION-STATE.md exists:**

### Enforce Session Cap (Last 5 Sessions)

Before loading DERIVATION-STATE.md into context, enforce the hard cap to keep the file bounded:

```bash
SESSION_COUNT=$(grep -c "^## Session:" .gpd/DERIVATION-STATE.md 2>/dev/null || echo 0)

if [ "$SESSION_COUNT" -gt 5 ]; then
  echo "DERIVATION-STATE.md has ${SESSION_COUNT} session blocks (cap: 5). Pruning oldest..."

  # Atomic read-modify-write: write to PID-unique .tmp, validate, then replace
  TMP_FILE=".gpd/DERIVATION-STATE.md.tmp.$$"
  trap "rm -f '$TMP_FILE'" EXIT

  KEEP_FROM=$(grep -n "^## Session:" .gpd/DERIVATION-STATE.md | tail -5 | head -1 | cut -d: -f1)
  HEADER_END=$(grep -n "^## Session:" .gpd/DERIVATION-STATE.md | head -1 | cut -d: -f1)
  HEADER_END=$((HEADER_END - 1))
  {
    head -n "$HEADER_END" .gpd/DERIVATION-STATE.md
    echo ""
    echo "> Older session entries archived in git history."
    echo "> Use \`git log -p -- .gpd/DERIVATION-STATE.md\` to recover."
    echo ""
    tail -n +"$KEEP_FROM" .gpd/DERIVATION-STATE.md
  } > "$TMP_FILE"

  TMP_LINES=$(wc -l < "$TMP_FILE")
  if [ "$TMP_LINES" -lt 5 ]; then
    echo "WARNING: Pruned file suspiciously small (${TMP_LINES} lines). Keeping original."
    rm -f "$TMP_FILE"
  elif ! grep -q "^# Derivation State" "$TMP_FILE"; then
    echo "WARNING: Pruned file missing required header. Keeping original."
    rm -f "$TMP_FILE"
  else
    cp "$TMP_FILE" .gpd/DERIVATION-STATE.md && \
      rm -f "$TMP_FILE" || \
      echo "WARNING: Failed to replace DERIVATION-STATE.md. Original preserved."
  fi
  trap - EXIT
fi
```

This is the same cap enforcement logic used by pause-work.md. It keeps the 5 most recent `## Session:` blocks and archives older entries via git history.

1. **Read the full file** to reconstruct the complete equation/convention/result history across all sessions.
2. **Cross-reference against state.json intermediate_results** to find any gaps:
   - Are there result IDs in DERIVATION-STATE.md that are missing from state.json? (suggests state.json was reset or corrupted)
   - Are there intermediate_results in state.json that are NOT in DERIVATION-STATE.md? (suggests a session did not properly pause)
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
for plan in .gpd/phases/*/*-PLAN.md; do
  summary="${plan/PLAN/SUMMARY}"
  [ ! -f "$summary" ] && echo "Incomplete: $plan"
done 2>/dev/null

# Check for interrupted agents (use has_interrupted_agent and interrupted_agent_id from init)
if [ "$has_interrupted_agent" = "true" ]; then
  echo "Interrupted agent: $interrupted_agent_id"
fi
```

**Bounded execution segment detection:** If `active_execution_segment` is present, treat pause, checkpoint waiting, interrupted scaleout, first-result review, pre-fanout review, and skeptical re-questioning as the same family of resumable state. Do NOT treat git rollback tags, interrupted agents, and paused review gates as separate resume systems; normalize them into one ranked `segment_candidates` list.

Reason-scoped clears still matter on resume: a `first_result` clear does not retire `pre_fanout` or skeptical fields, and a `fanout unlock` does not clear the review gate by itself.

When resuming from `first_result` or skeptical state, ask one concrete question first: "What decisive evidence is still owed before downstream work is trustworthy?" Do not resume fanout based only on proxy-looking success or "seems on track" prose.

**Auto-checkpoint detection:** Check `state.json` for `auto_checkpoint` field. If present and newer than the current execution snapshot, warn: "Auto-checkpoint detected -- work may have continued after the last recorded gate. Review state.json auto_checkpoint for details."

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

[If active_execution_segment has a resume file:]
>> Research checkpoint detected:
    - Resume artifact: [resume_file]
    - Derivation state: [brief summary from the active execution snapshot]
    - Parameters in scope: [key parameter values]
    - Last result obtained: [most recent intermediate result]
    - Next planned step: [what was planned before pausing]

[If active_execution_segment is waiting on review:]
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
[N] pending todos -- /gpd:check-todos to review

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

**If `resume_mode="bounded_segment"` and `active_execution_segment` exists:**
-> Primary: Continue the bounded execution segment using its current cursor, checkpoint cause, downstream-lock state, and resume preconditions
-> If `checkpoint_reason=first_result`, `checkpoint_reason=pre_fanout`, or skeptical re-questioning is required: treat the next action as a review/replan decision whenever decisive evidence is still missing, not a routine execution resume
-> Do not resume downstream fanout until the gate has an explicit clear/override outcome and, for `pre_fanout`, the matching fanout-unlock transition
-> Option: Review another ranked resume candidate from `segment_candidates`

**If interrupted agent exists:**
-> Primary: Resume interrupted agent (Task tool with resume parameter)
-> Option: Start fresh (abandon agent work)

**If incomplete plan (PLAN without SUMMARY):**
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
1. Execute phase (/gpd:execute-phase {phase})
   OR
1. Discuss Phase 3 context (/gpd:discuss-phase 3) [if CONTEXT.md missing]
   OR
1. Plan Phase 3 (/gpd:plan-phase 3) [if CONTEXT.md exists or discuss option declined]

[Secondary options:]
2. Review current phase status
3. Check pending todos ([N] pending)
4. Review brief alignment
5. Something else
```

**Note:** When offering phase planning, check for CONTEXT.md existence first:

```bash
ls .gpd/phases/${current_phase_slug}/*-CONTEXT.md 2>/dev/null
```

If missing, suggest discuss-phase before plan. If exists, offer plan directly.

Wait for user selection.
</step>

<step name="route_to_workflow">
Based on user selection, route to appropriate workflow:

- **Execute plan** -> Show command for user to run after clearing:

  ```
  ---

  ## Next Up

  **{phase}-{plan}: [Plan Name]** -- [objective from PLAN.md]

  `/gpd:execute-phase {phase}`

  <sub>`/clear` first -> fresh context window</sub>

  ---
  ```

- **Plan phase** -> Show command for user to run after clearing:

  ```
  ---

  ## Next Up

  **Phase [N]: [Name]** -- [Goal from ROADMAP.md]

  `/gpd:plan-phase [phase-number]`

  <sub>`/clear` first -> fresh context window</sub>

  ---

  **Also available:**
  - `/gpd:discuss-phase [N]` -- gather context first
  - `/gpd:research-phase [N]` -- investigate unknowns

  ---
  ```

- **Transition** -> ./transition.md
- **Check todos** -> Read .gpd/todos/pending/, present summary
- **Review alignment** -> Read PROJECT.md, compare to current state
- **Something else** -> Ask what they need
  </step>

<step name="update_session">
Before proceeding to routed workflow, update session continuity via CLI
(keeps STATE.md and state.json in sync):

```bash
gpd state record-session \
  --stopped-at "Session resumed, proceeding to [action]" \
  --resume-file "[updated if applicable, or omit flag]"
```

This ensures if session ends unexpectedly, next resume knows the state.
</step>

</process>

<reconstruction>
If STATE.md is missing but other artifacts exist:

"STATE.md missing. Reconstructing from artifacts..."

1. Read PROJECT.md -> Extract "What This Is" and Core Research Question
2. Read ROADMAP.md -> Determine phases, find current position
3. Scan \*-SUMMARY.md files -> Extract decisions, concerns
4. Count pending todos in .gpd/todos/pending/
5. Check current execution snapshot -> Session continuity

Reconstruct and write STATE.md, then proceed normally.

This handles cases where:

- Project predates STATE.md introduction
- File was accidentally deleted
- Cloning repo without full .gpd/ state
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
