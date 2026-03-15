<purpose>
Check research progress, summarize recent work and what lies ahead, then intelligently route to the next action — either executing an existing plan or creating the next one. Provides situational awareness before continuing research.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="mode_detection">
## Mode Detection

Check if `$ARGUMENTS` contains `--brief`, `--full`, or `--reconcile`.

**If --brief:**
Show compact 3-line status:
```
Phase {N} of {M} ({phase_name}) | Plan {X} of {Y} | [{progress_bar}] {percent}%
Last: {last_summary_one_liner}
>> Next: {recommended_next_command}
```
STOP here. Do not show full report.

**If --reconcile:**
Go to `reconcile_state` step.

**Default (no flag) or --full:**
Continue to full report below. With `--full`, also include detailed per-phase artifact listings.
</step>

<step name="reconcile_state">
## Reconcile Mode

When STATE.md appears out of sync with disk reality (e.g., a plan was completed but state not updated, or a phase was manually modified), reconcile by comparing disk artifacts against STATE.md.

```bash
# Get the structured current position instead of scraping STATE.md with regexes
PROGRESS_JSON=$(gpd --raw progress)
STATE_PHASE=$(echo "$PROGRESS_JSON" | gpd json get .current_phase.number --default "")
STATE_PLAN=$(echo "$PROGRESS_JSON" | gpd json get .current_execution.plan --default "")

# Count actual disk state from the canonical roadmap inventory
ROADMAP=$(gpd roadmap analyze)
echo "$ROADMAP" | gpd json get .phases --default "[]"
```

**If discrepancies found between STATE.md and disk:**

```
## State Reconciliation

| Source | Phase | Plan | Status |
|--------|-------|------|--------|
| STATE.md | {X} | {Y} | {claimed_status} |
| Disk | {X} | {Z} | {actual_status} |

Discrepancy: STATE.md says plan {Y} is current, but disk shows {Z} plans complete.

Options:
1. "Sync STATE.md to disk" (Recommended) — update STATE.md to match actual artifacts
2. "Keep STATE.md" — trust the state file, investigate missing artifacts
3. "Show details" — list all mismatches before deciding
```

If user chooses sync: update STATE.md position, progress bar, and plan counters to match disk reality using `gpd state` commands.

**If no discrepancies:** Report "STATE.md is consistent with disk artifacts." and continue to full report.
</step>

<step name="init_context">
**Load progress context (with file contents to avoid redundant reads):**

```bash
INIT=$(gpd init progress --include state,roadmap,project,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `project_exists`, `roadmap_exists`, `state_exists`, `phases`, `current_phase`, `next_phase`, `milestone_version`, `completed_count`, `phase_count`, `paused_at`, `autonomy`, `research_mode`, `project_contract`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`.

**File contents (from --include):** `state_content`, `roadmap_content`, `project_content`, `config_content`. These are null if files don't exist.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context progress "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

If missing STATE.md: suggest `/gpd:new-project`.

**If ROADMAP.md missing but PROJECT.md exists:**

This means a milestone was completed and archived. Go to **Route F** (between milestones).

If missing both ROADMAP.md and PROJECT.md: suggest `/gpd:new-project`.
</step>

<step name="load">
**Use project context from INIT:**

All file contents are already loaded via `--include` in init_context step:

- `state_content` — living memory (position, decisions, issues)
- `roadmap_content` — phase structure and objectives
- `project_content` — current state (Research Question, Framework, Answered Questions)
- `config_content` — settings (model_profile, workflow toggles)
- `project_contract` — machine-readable scoping and anchor contract
- `effective_reference_intake` — structured carry-forward ledger for refs, baselines, prior outputs, and context gaps
- `active_reference_context` / `reference_artifacts_content` — readable anchor context to explain the next-step recommendation

No additional file reads needed.
</step>

<step name="analyze_roadmap">
**Get comprehensive roadmap analysis (replaces manual parsing):**

```bash
ROADMAP=$(gpd roadmap analyze)
```

This returns structured JSON with:

- All phases with disk status (complete/partial/planned/empty/no_directory)
- Goal and dependencies per phase
- Plan and summary counts per phase
- Aggregated stats: total plans, summaries, progress percent
- Current and next phase identification

Use this instead of manually reading/parsing ROADMAP.md.
</step>

<step name="recent">
**Gather recent work context:**

- Find the 2-3 most recent SUMMARY.md files
- Use `summary-extract` for efficient parsing:
  ```bash
  gpd summary-extract <path> --field one_liner
  ```
- This shows "what we've been working on"
  </step>

<step name="position">
**Parse current position from init context and roadmap analysis:**

- Use `current_phase` and `next_phase` from roadmap analyze
- Use phase-level `has_context` and `has_literature` flags from analyze
- Note `paused_at` if work was paused (from init context)
- Count pending items: use `init todos` or `list-todos`
- Check for active debug sessions: `ls .gpd/debug/*.md 2>/dev/null | grep -v resolved | wc -l`
- Check state compaction health: `gpd state compact 2>&1` — if output contains `"warn": true`, STATE.md is growing large. Note this for the report.
  </step>

<step name="report">
**Generate progress bar from gpd CLI, then present rich status report:**

```bash
# Get formatted progress bar
PROGRESS_BAR=$(gpd --raw progress bar)
```

Present:

```
# [Research Project Name]

**Progress:** {PROGRESS_BAR}
**Profile:** [deep-theory/numerical/exploratory/review/paper-writing]

## Recent Work
- [Phase X, Plan Y]: [what was accomplished - 1 line from summary-extract]
- [Phase X, Plan Z]: [what was accomplished - 1 line from summary-extract]

## Current Position
Phase [N] of [total]: [phase-name]
Plan [M] of [phase-total]: [status]
CONTEXT: [present if has_context | - if not]

## Key Results Established
- [result 1 from STATE.md — e.g., "Spectral gap scales as Delta ~ 1/N^2 (Phase 2)"]
- [result 2]

## Key Decisions Made
- [decision 1 from STATE.md — e.g., "Using dimensional regularization with MS-bar scheme"]
- [decision 2]

## Blockers/Concerns
- [any blockers or concerns from STATE.md — e.g., "Series diverges for g > 2, need resummation"]

## Pending Items
- [count] pending — /gpd:check-todos to review

## Active Derivation Sessions
- [count] active — /gpd:debug to continue
(Only show this section if count > 0)

## What's Next
[Next phase/plan objective from roadmap analyze]
```

If STATE.md exceeds 1500 lines, append after the report:

```
STATE.md is large (N lines). Consider running `/gpd:compact-state` to archive historical entries.
```

If the compaction health check reported `"warn": true`, append:

```
STATE.md is approaching compaction threshold (N lines). Will auto-compact at next phase transition.
```

**Deep diagnostics (--full mode only):** Run the health dashboard for comprehensive system checks:

```bash
HEALTH=$(gpd --raw health 2>/dev/null)
```

If health reports any issues (non-empty `issues` array), append a summary:

```
## System Health
{issue_count} issue(s) detected. Run `gpd health --fix` to auto-repair.
```

</step>

<step name="route">
**Determine next action based on verified counts.**

**Step 1: Count plans, summaries, and validation issues in current phase**

List files in the current phase directory:

```bash
ls -1 .gpd/phases/[current-phase-dir]/*-PLAN.md 2>/dev/null | wc -l
ls -1 .gpd/phases/[current-phase-dir]/*-SUMMARY.md 2>/dev/null | wc -l
ls -1 .gpd/phases/[current-phase-dir]/*-VERIFICATION.md 2>/dev/null | wc -l
```

State: "This phase has {X} plans, {Y} summaries."

**Step 1.5: Check for unaddressed validation gaps**

Check for VERIFICATION.md files with gaps or review requirements. This includes `gaps_found` (verification found issues), `diagnosed` (root causes identified), `human_needed` (human review required), and `expert_needed` (domain expert review required).

```bash
# Check for validation with gaps or review requirements
grep -l -E "status: (gaps_found|diagnosed|human_needed|expert_needed)" .gpd/phases/[current-phase-dir]/*-VERIFICATION.md 2>/dev/null
```

Track:

- `validation_with_gaps`: VERIFICATION.md files with status "gaps_found", "diagnosed", "human_needed", or "expert_needed"

**Step 1.75: Check for existing gap-closure plans**

If `validation_with_gaps > 0`, check whether gap-closure plans already exist but are unexecuted:

```bash
# Check for gap_closure plans without matching SUMMARYs
GAP_PLANS_UNEXECUTED=0
for plan in .gpd/phases/[current-phase-dir]/*-PLAN.md; do
  if grep -q "gap_closure: true" "$plan" 2>/dev/null; then
    SUMMARY="${plan%-PLAN.md}-SUMMARY.md"
    if [ ! -f "$SUMMARY" ]; then
      GAP_PLANS_UNEXECUTED=$((GAP_PLANS_UNEXECUTED + 1))
    fi
  fi
done
```

**Step 2: Route based on counts**

| Condition                                              | Meaning                             | Action             |
| ------------------------------------------------------ | ----------------------------------- | ------------------ |
| validation_with_gaps > 0 AND GAP_PLANS_UNEXECUTED > 0 | Gap-closure plans exist, unexecuted | Go to **Route E2** |
| validation_with_gaps > 0                               | Validation gaps need fix plans      | Go to **Route E**  |
| summaries < plans                                      | Unexecuted plans exist              | Go to **Route A**  |
| summaries = plans AND plans > 0                        | Phase complete                      | Go to Step 3       |
| plans = 0                                              | Phase not yet planned               | Go to **Route B**  |

---

**Route A: Unexecuted plan exists**

Find the first PLAN.md without matching SUMMARY.md.
Read its `<objective>` section.

```
---

## >> Next Up

**{phase}-{plan}: [Plan Name]** — [objective summary from PLAN.md]

`/gpd:execute-phase {phase}`

<sub>`/clear` first -> fresh context window</sub>

---
```

---

**Route B: Phase needs planning**

Check if `{phase}-CONTEXT.md` exists in phase directory.

**If CONTEXT.md exists:**

```
---

## >> Next Up

**Phase {N}: {Name}** — {Goal from ROADMAP.md}
<sub>Context gathered, ready to plan</sub>

`/gpd:plan-phase {phase-number}`

<sub>`/clear` first -> fresh context window</sub>

---
```

**If CONTEXT.md does NOT exist:**

```
---

## >> Next Up

**Phase {N}: {Name}** — {Goal from ROADMAP.md}

`/gpd:discuss-phase {phase}` — gather context and clarify approach

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:plan-phase {phase}` — skip discussion, plan directly
- `/gpd:list-phase-assumptions {phase}` — see what the agent assumes about the approach

---
```

---

**Route E: Validation gaps need fix plans**

VERIFICATION.md exists with gaps (diagnosed issues like failing limiting cases or inconsistent dimensions). User needs to plan fixes.

```
---

## !! Validation Gaps Found

**{phase}-VERIFICATION.md** has {N} gaps requiring fixes.

Examples: [e.g., "Dimension mismatch in eq. 14", "Wrong sign in g -> 0 limit"]

`/gpd:plan-phase {phase} --gaps`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:execute-phase {phase}` — execute phase plans
- `/gpd:verify-work {phase}` — run more validation checks

---
```

---

**Route E2: Gap-closure plans exist but are unexecuted**

Gap-closure plans were created by `/gpd:plan-phase --gaps` but have not been executed yet. Suggest executing them instead of re-planning.

```
---

## !! Gap-Closure Plans Ready

**{GAP_PLANS_UNEXECUTED} gap-closure plan(s)** exist but have not been executed.

`/gpd:execute-phase {phase} --gaps-only`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:plan-phase {phase} --gaps` — re-plan gap fixes (if current plans are stale)
- `/gpd:verify-work {phase}` — re-run validation checks

---
```

---

**Step 3: Check milestone status (only when phase complete)**

Read ROADMAP.md and identify:

1. Current phase number
2. All phase numbers in the current milestone section

Count total phases and identify the highest phase number.

State: "Current phase is {X}. Milestone has {N} phases (highest: {Y})."

**Route based on milestone status:**

| Condition                     | Meaning            | Action            |
| ----------------------------- | ------------------ | ----------------- |
| current phase < highest phase | More phases remain | Go to **Route C** |
| current phase = highest phase | Milestone complete | Go to **Route D** |

---

**Route C: Phase complete, more phases remain**

Read ROADMAP.md to get the next phase's name and goal.

```
---

## Phase {Z} Complete

## >> Next Up

**Phase {Z+1}: {Name}** — {Goal from ROADMAP.md}

`/gpd:discuss-phase {Z+1}` — gather context and clarify approach

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:plan-phase {Z+1}` — skip discussion, plan directly
- `/gpd:verify-work {Z}` — validate results before continuing

---
```

---

**Route D: Milestone complete**

```
---

## Milestone Complete

All {N} phases finished!

## >> Next Up

**Complete Milestone** — archive results and prepare for next

`/gpd:complete-milestone`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:verify-work` — validate all results before completing milestone

---
```

---

**Route F: Between milestones (ROADMAP.md missing, PROJECT.md exists)**

A milestone was completed and archived. Ready to start the next milestone cycle.

Read MILESTONES.md to find the last completed milestone version.

```
---

## Milestone v{X.Y} Complete

Ready to plan the next research direction.

## >> Next Up

**Start Next Milestone** — questioning -> literature survey -> objectives -> roadmap

`/gpd:new-milestone`

<sub>`/clear` first -> fresh context window</sub>

---
```

</step>

<step name="edge_cases">
**Handle edge cases:**

- Phase complete but next phase not planned -> offer `/gpd:plan-phase [next]`
- All work complete -> offer milestone completion
- Blockers present -> highlight before offering to continue
- Handoff file exists -> mention it, offer `/gpd:resume-work`
- Derivation session active -> mention it, offer `/gpd:debug` to continue
  </step>

</process>

<success_criteria>

- [ ] Rich context provided (recent work, key results, decisions, issues)
- [ ] Current position clear with visual progress
- [ ] What's next clearly explained
- [ ] Smart routing: /gpd:execute-phase if plans exist, /gpd:plan-phase if not
- [ ] User confirms before any action
- [ ] Seamless handoff to appropriate gpd command

</success_criteria>
