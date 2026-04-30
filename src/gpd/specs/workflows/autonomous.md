<purpose>

Drive all remaining milestone phases autonomously. For each incomplete phase: discuss → plan → execute → verify by invoking each phase command directly. Pauses only for explicit user decisions (gray area acceptance, blockers, verification routing). Re-reads ROADMAP.md after each phase to catch dynamically inserted phases.

</purpose>

<required_reading>

Read all files referenced by the invoking prompt's execution_context before starting.

</required_reading>

<process>

<step name="initialize" priority="first">

## 1. Initialize

Parse `$ARGUMENTS` for `--from N` flag:

```bash
FROM_PHASE=""
if echo "$ARGUMENTS" | grep -qE '\-\-from\s+[0-9]'; then
  FROM_PHASE=$(echo "$ARGUMENTS" | grep -oE '\-\-from\s+[0-9]+\.?[0-9]*' | awk '{print $2}')
fi
```

Bootstrap via milestone-level init:

```bash
INIT=$(gpd --raw init milestone-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `milestone_version`, `milestone_name`, `phase_count`, `completed_phases`, `roadmap_exists`, `state_exists`, `commit_docs`.

```bash
milestone_version=$(echo "$INIT" | gpd json get .milestone_version --default "")
milestone_name=$(echo "$INIT" | gpd json get .milestone_name --default "")
phase_count=$(echo "$INIT" | gpd json get .phase_count --default 0)
completed_phases=$(echo "$INIT" | gpd json get .completed_phases --default 0)
roadmap_exists=$(echo "$INIT" | gpd json get .roadmap_exists --default false)
state_exists=$(echo "$INIT" | gpd json get .state_exists --default false)
commit_docs=$(echo "$INIT" | gpd json get .commit_docs --default true)
```

**If `roadmap_exists` is false:** Error — "No ROADMAP.md found. Run `gpd:new-project` first."
**If `state_exists` is false:** Error — "No STATE.md found. Run `gpd:new-project` first."

Read the model profile for physics-aware smart discuss depth:

```bash
MODEL_PROFILE=$(gpd config get model_profile 2>/dev/null || echo "review")
```

Display startup banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD ► AUTONOMOUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Milestone: {milestone_version} — {milestone_name}
 Phases: {phase_count} total, {completed_phases} complete
 Profile: {MODEL_PROFILE}
```

If `FROM_PHASE` is set, display: `Starting from phase ${FROM_PHASE}`

</step>

<step name="discover_phases">

## 2. Discover Phases

Run phase discovery:

```bash
ROADMAP=$(gpd --raw roadmap analyze)
```

Parse the JSON `phases` array.

**Filter to incomplete phases:** Keep only phases where `disk_status !== "complete"` OR `roadmap_complete === false`.

**Apply `--from N` filter:** If `FROM_PHASE` was provided, additionally filter out phases where `number < FROM_PHASE` (use numeric comparison — handles decimal phases like "5.1").

**Sort by `number`** in numeric ascending order.

**If no incomplete phases remain:**

Before completion, stale/missing/non-passing verification blocks audit/paper.

```bash
for COMPLETE_PHASE in "${COMPLETED_PHASES[@]}"; do
  D=$(gpd --raw init phase-op "${COMPLETE_PHASE}" | gpd json get .phase_dir --default "")
  VS=$(grep -iE "^status:" "$D"/*-VERIFICATION.md 2>/dev/null | head -1 | cut -d: -f2 | tr -d ' ' | tr '[:upper:]' '[:lower:]')
  case "$VS" in
    passed|verified|complete|completed) ;;
    *)
      echo "Phase ${COMPLETE_PHASE}: verify before closeout."
      echo "Next: gpd:verify-work ${COMPLETE_PHASE}"
      exit 1 ;;
  esac
done
```

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD ► AUTONOMOUS ▸ COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 All phases complete! Nothing left to do.
```

Exit cleanly.

**Display phase plan:**

```
## Phase Plan

| # | Phase | Status |
|---|-------|--------|
| 3 | Monte Carlo Implementation | In Progress |
| 4 | Finite-Size Scaling Analysis | Not Started |
| 5 | Results Comparison & Paper | Not Started |
```

**Fetch details for each phase:**

```bash
DETAIL=$(gpd --raw roadmap get-phase ${PHASE_NUM})
```

Extract `phase_name`, `goal`, `success_criteria` from each. Store for use in execute_phase and transition messages.

</step>

<step name="execute_phase">

## 3. Execute Phase

Re-read model profile in case the user changed it between phases:

```bash
MODEL_PROFILE=$(gpd config get model_profile 2>/dev/null || echo "review")
```

For the current phase, display the progress banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD ► AUTONOMOUS ▸ Phase {N}/{T}: {Name} [████░░░░] {P}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Where N = current phase number (from the ROADMAP, e.g., 3), T = total milestone phases (from `phase_count` parsed in initialize step, e.g., 5), P = percentage of all milestone phases completed so far. Calculate P as: (number of phases with `disk_status` "complete" from the latest `roadmap analyze` / T * 100). Use filled and empty bar segments (8 characters wide).

**3a. Paper-Writing Phase Detection**

Before starting the normal discuss→plan→execute flow, check if this phase is a paper-writing phase:

```bash
PHASE_GOAL=$(gpd --raw roadmap get-phase ${PHASE_NUM} | gpd json get .goal --default "")
```

Check if the phase goal matches paper-writing indicators. Require BOTH paper keywords AND absence of derivation/computation keywords to avoid false positives on phases like "Derive equations for paper":

```bash
echo "$PHASE_GOAL" | grep -qiE "write.*(paper|manuscript)|draft.*(paper|manuscript)|prepare.*(paper|manuscript|submission)|paper.writing|manuscript.preparation"
IS_PAPER_PHASE=$?
# Guard: if goal also mentions derivation/computation, it's NOT a pure paper phase
if [ "$IS_PAPER_PHASE" = "0" ]; then
  echo "$PHASE_GOAL" | grep -qiE "derive|compute|simulate|calculate|implement|analyze.data"
  if [ $? -eq 0 ]; then IS_PAPER_PHASE=1; fi
fi
```

**If `IS_PAPER_PHASE` is 0 (paper-writing indicators found):**

Display:

```
Phase ${PHASE_NUM}: Paper-writing phase detected.
```

Ask user via ask_user:
- **question:** "Phase ${PHASE_NUM} appears to be a paper-writing phase. Use the dedicated write-paper workflow?"
- **options:** "Use gpd:write-paper" / "Use normal discuss→plan→execute"

On **"Use gpd:write-paper":**

```
Invoke the runtime-installed `gpd:write-paper` command.
```

After write-paper completes, proceed to iterate step (skip normal discuss/plan/execute/verify).

On **"Use normal discuss→plan→execute":** Continue to 3b.

**If `IS_PAPER_PHASE` is 1 (no paper indicators):** Continue to 3b.

**3b. Smart Discuss**

Check if CONTEXT.md already exists for this phase:

```bash
PHASE_STATE=$(gpd --raw init phase-op ${PHASE_NUM})
```

Parse `has_context`, `phase_dir`, `phase_slug`, `padded_phase`, `phase_name` from JSON.

**If has_context is true:** Skip discuss — context already gathered. Display:

```
Phase ${PHASE_NUM}: Context exists — skipping discuss.
```

Proceed to 3c.

**If has_context is false:** Execute the smart_discuss step for this phase.

There is no supported config key for skipping discuss. Do not read one, do not invent one, and do not auto-generate a minimal CONTEXT.md as a substitute for smart discuss. If a future real skip-discuss setting is added, it must be represented in `GPDProjectConfig`, surfaced in settings, and tested before this workflow may branch on it.

After smart_discuss completes, verify context was written:

```bash
PHASE_STATE=$(gpd --raw init phase-op ${PHASE_NUM})
```

Check `has_context`. If false → go to handle_blocker: "Smart discuss for phase ${PHASE_NUM} did not produce CONTEXT.md."

**3c. Plan**

Before plan/execute, keep the lifecycle authority blocker from `gpd:plan-phase`/`gpd:execute-phase`:

```bash
PHASE_CONTRACT_GATE=$(gpd --raw validate lifecycle-contract-gate plan-phase "${PHASE_NUM}")
if [ $? -ne 0 ]; then
  echo "$PHASE_CONTRACT_GATE"
  echo "Next: gpd:sync-state or gpd:new-project; then gpd:plan-phase ${PHASE_NUM}"
  # STOP -- route to handle_blocker. Do not relabel this as missing plan authority.
fi
```

```
Invoke the runtime-installed `gpd:plan-phase` command with `${PHASE_NUM}`.
```

Verify plan produced output — re-run `init phase-op` and check `has_plans`. If false → go to handle_blocker: "Plan phase ${PHASE_NUM} did not produce any plans."

**3d. Execute**

```
Invoke the runtime-installed `gpd:execute-phase` command with `${PHASE_NUM}`.
```

`gpd:execute-phase` owns its normal phase transition / closeout path. Autonomous mode invokes it with only the phase number and must not run a duplicate transition for the same successful phase.

**3e. Post-Execution Verification Routing**

After execute-phase returns, refetch the phase state and assign `PHASE_DIR` before reading any verification artifact:

```bash
PHASE_STATE=$(gpd --raw init phase-op ${PHASE_NUM})
PHASE_DIR=$(echo "$PHASE_STATE" | gpd json get .phase_dir --default "")
if [ -z "$PHASE_DIR" ]; then
  echo "ERROR: could not resolve phase directory for phase ${PHASE_NUM}"
  # STOP — route to handle_blocker.
fi
VERIFY_STATUS=$(grep "^status:" "${PHASE_DIR}"/*-VERIFICATION.md 2>/dev/null | head -1 | cut -d: -f2 | tr -d ' ')
```

**If VERIFY_STATUS is empty** (no VERIFICATION.md or no status field):

Run verification explicitly:

```
Invoke the runtime-installed `gpd:verify-work` command with `${PHASE_NUM}`.
```

Re-read verification status:

```bash
VERIFY_STATUS=$(grep "^status:" "${PHASE_DIR}"/*-VERIFICATION.md 2>/dev/null | head -1 | cut -d: -f2 | tr -d ' ')
```

If still empty after explicit verification: go to handle_blocker: "Verification for phase ${PHASE_NUM} did not produce results."

**If `passed`:**

Display:
```
Phase ${PHASE_NUM} -- {PHASE_NAME} — Verification passed
```

Proceed to convention_check step.

**If `human_needed`:**

Read the human_verification section from VERIFICATION.md to get items requiring manual review.

Display the items, then ask user via ask_user:
- **question:** "Phase ${PHASE_NUM} has items needing manual verification. Validate now or continue?"
- **options:** "Validate now" / "Continue without validation"

On **"Validate now"**: Present the specific items. After user reviews, ask:
- **question:** "Validation result?"
- **options:** "All good — continue" / "Found issues"

On "All good": Display `Phase ${PHASE_NUM} -- Human validation passed` and proceed to convention_check step.
On "Found issues": Go to handle_blocker with the user's reported issues.

On **"Continue without validation"**: Display `Phase ${PHASE_NUM} -- Human validation deferred` and proceed to convention_check step.

**If `gaps_found`:**

Read gap summary from VERIFICATION.md (score and missing items). Display:
```
Phase ${PHASE_NUM}: {PHASE_NAME} — Gaps Found
Score: {N}/{M} checks verified
```

Ask user via ask_user:
- **question:** "Gaps found in phase ${PHASE_NUM}. How to proceed?"
- **options:** "Run gap closure" / "Continue without fixing" / "Stop autonomous mode"

On **"Run gap closure"**: Execute gap closure cycle (limit: 1 attempt):

```
Invoke the runtime-installed `gpd:plan-phase` command with `${PHASE_NUM} --gaps`.
```

Verify gap plans were created — re-run `init phase-op ${PHASE_NUM}` and check `has_plans`. If no new gap plans → go to handle_blocker: "Gap closure planning for phase ${PHASE_NUM} did not produce plans."

Re-execute with `--gaps-only` to run ONLY the gap-closure plans (not re-run original plans):
```
Invoke the runtime-installed `gpd:execute-phase` command with `${PHASE_NUM} --gaps-only`.
```

Force fresh verification after gap closure — do NOT read stale VERIFICATION.md:
```
Invoke the runtime-installed `gpd:verify-work` command with `${PHASE_NUM}`.
```

Re-read verification status from the FRESH artifact:
```bash
VERIFY_STATUS=$(grep "^status:" "${PHASE_DIR}"/*-VERIFICATION.md 2>/dev/null | head -1 | cut -d: -f2 | tr -d ' ')
```

If `passed`: Route normally (continue to convention_check).

If still `gaps_found` after this retry: Display "Gaps persist after closure attempt." and ask via ask_user:
- **question:** "Gap closure did not fully resolve issues. How to proceed?"
- **options:** "Continue anyway" / "Stop autonomous mode"

On "Continue anyway": Proceed to convention_check step.
On "Stop autonomous mode": Go to handle_blocker.

This limits gap closure to 1 automatic retry to prevent infinite loops.

On **"Continue without fixing"**: Display `Phase ${PHASE_NUM} -- Gaps deferred` and proceed to convention_check step.

On **"Stop autonomous mode"**: Go to handle_blocker with "User stopped — gaps remain in phase ${PHASE_NUM}".

</step>

<step name="smart_discuss">

## Smart Discuss

Run smart discuss for the current phase. Proposes gray area answers in batch tables — the user accepts or overrides per area. Produces CONTEXT.md following the same template as regular discuss-phase (all 9 sections from templates/context.md).

> **Note:** Smart discuss is an autonomous-optimized variant of the `gpd:discuss-phase` skill. It produces identical CONTEXT.md output but uses batch table proposals instead of sequential questioning.

**Inputs:** `PHASE_NUM` from execute_phase. Run init to get phase paths:

```bash
PHASE_STATE=$(gpd --raw init phase-op ${PHASE_NUM})
```

Parse from JSON: `phase_dir`, `phase_slug`, `padded_phase`, `phase_name`.

---

### Sub-step 1: Load prior context

Read project-level and prior phase context to avoid re-asking decided questions.

**Read project files:**

```bash
cat GPD/PROJECT.md 2>/dev/null || true
cat GPD/REQUIREMENTS.md 2>/dev/null || true
cat GPD/STATE.md 2>/dev/null || true
cat GPD/CONVENTIONS.md 2>/dev/null || true
```

Extract from these:
- **PROJECT.md** — Research question, theoretical framework, key parameters, non-negotiables
- **REQUIREMENTS.md** — Acceptance criteria, constraints, must-haves
- **STATE.md** — Current progress, decisions logged so far
- **CONVENTIONS.md** — Locked notation conventions, metric signature, unit system, gauge choice

**Read all prior CONTEXT.md files:**

```bash
(find GPD/phases -name "*-CONTEXT.md" 2>/dev/null || true) | sort
```

For each CONTEXT.md where phase number < current phase:
- Read the `<decisions>` section — these are locked methodological preferences
- Read `<assumptions>` — physical assumptions already committed to
- Read `<limiting_cases>` — limits already identified
- Note patterns (e.g., "user consistently prefers perturbative approaches", "user chose Matsubara formalism")

**Build internal prior_decisions context** (do not write to file):

```
<prior_decisions>
## Project-Level
- [Key principle or constraint from PROJECT.md]
- [Requirement affecting this phase from REQUIREMENTS.md]
- [Locked convention from CONVENTIONS.md]

## From Prior Phases
### Phase N: [Name]
- [Decision relevant to current phase]
- [Physical assumption that carries forward]
</prior_decisions>
```

If no prior context exists, continue without — expected for early phases.

---

### Sub-step 2: Scout Prior Work

Lightweight scan of existing project artifacts to inform gray area identification and proposals. Keep under ~5% context.

**Check for existing literature survey:**

```bash
ls GPD/literature/*.md 2>/dev/null || true
ls GPD/research-map/*.md 2>/dev/null || true
```

**If literature survey exists:** Read the most relevant files (METHODS.md, PRIOR-WORK.md based on phase type). Extract known methods, established approaches, potential pitfalls.

**If no literature survey, do targeted scan:**

Look at prior phase artifacts for relevant results:

```bash
find GPD/phases -name "*-SUMMARY.md" 2>/dev/null | sort
```

Read the 2-3 most recent SUMMARY.md files to understand what has been established so far.

**Build internal prior_work_context** (do not write to file):
- **Established results** — what prior phases have proven or computed
- **Known methods** — approaches already used in this project
- **Integration points** — where this phase connects to prior work

---

### Sub-step 3: Analyze Phase and Generate Proposals

**Get phase details:**

```bash
DETAIL=$(gpd --raw roadmap get-phase ${PHASE_NUM})
```

Extract `goal`, `requirements`, `success_criteria` from the JSON response.

**Infrastructure detection — check FIRST before generating gray areas:**

A phase is pure infrastructure when ALL of these are true:
1. Goal keywords match: "setup", "configuration", "install", "scaffold", "initialize", "migrate", "restructure"
2. AND success criteria are all technical: "file exists", "script runs", "test passes", "config valid"
3. AND no physics methodology is described (no "derive", "compute", "simulate", "analyze", "verify")

**If infrastructure-only:** Skip Sub-step 4. Jump directly to Sub-step 5 with minimal CONTEXT.md. Display:

```
Phase ${PHASE_NUM}: Infrastructure phase — skipping discuss, writing minimal context.
```

Use these defaults for the CONTEXT.md:
- `<domain>`: Phase boundary from ROADMAP goal
- `<decisions>`: Single "### Agent's Discretion" subsection — "All implementation choices are at the agent's discretion — pure infrastructure phase"
- `<assumptions>`: "No physical assumptions — infrastructure phase"
- `<limiting_cases>`: "None — infrastructure phase"
- `<deferred>`: "None"

**If NOT infrastructure — generate gray area proposals:**

**Model profile awareness:** Adjust gray area depth based on `MODEL_PROFILE` (read in initialize step):

- **deep-theory:** Emphasize formalism questions — regularization scheme, gauge choice, renormalization prescription, proof strategy, mathematical rigor level. Generate 4 gray areas with deeper formalism probes.
- **numerical:** Emphasize algorithm questions — discretization method, convergence criteria, error estimation, parallelization strategy, numerical stability. Generate 4 gray areas with computational focus.
- **exploratory:** Keep gray areas broad and method-comparative — which approaches to try first, when to pivot, what constitutes a promising lead. Generate 3 gray areas.
- **review:** Balanced mix of formalism and methodology. Generate 3-4 gray areas.
- **paper-writing:** Emphasize presentation decisions — narrative structure, which results to highlight, notation consistency, target audience. Generate 3 gray areas.

Determine physics domain type from the phase goal:
- Something being DERIVED → formalism, approximation scheme, convention choice, gauge/frame
- Something being COMPUTED → algorithm, discretization, convergence, error tolerance
- Something being SIMULATED → initial conditions, boundary conditions, ensemble, equilibration
- Something being ANALYZED → statistical methods, fitting, error propagation, systematics
- Something being COMPARED → benchmarks, metrics, agreement criteria

Check prior_decisions — skip gray areas already decided in prior phases.

Generate **3-4 gray areas** (adjusted by profile) with **~4 questions each**. For each question:
- **Pre-select a recommended answer** based on: prior decisions (consistency), established conventions (CONVENTIONS.md), prior phase results (what methods worked), ROADMAP success criteria
- Generate **1-2 alternatives** per question
- **Annotate** with prior decision context ("You chose X in Phase N") and convention context ("CONVENTIONS.md locks Y") where relevant

---

### Sub-step 4: Present Proposals Per Area

Present gray areas **one at a time**. For each area (M of N):

Display a table:

```
### Gray Area {M}/{N}: {Area Name}

| # | Question | Recommended | Alternative(s) |
|---|----------|-------------|-----------------|
| 1 | {question} | {answer} — {rationale} | {alt1}; {alt2} |
| 2 | {question} | {answer} — {rationale} | {alt1} |
| 3 | {question} | {answer} — {rationale} | {alt1}; {alt2} |
| 4 | {question} | {answer} — {rationale} | {alt1} |
```

Then prompt the user via **ask_user**:
- **header:** "Area {M}/{N}"
- **question:** "Accept these answers for {Area Name}?"
- **options:** Build dynamically — always "Accept all" first, then "Change Q1" through "Change QN" for each question (up to 4), then "Discuss deeper" last. Cap at 6 explicit options max (ask_user adds "Other" automatically).

**On "Accept all":** Record all recommended answers for this area. Move to next area.

**On "Change QN":** Use ask_user with the alternatives for that specific question:
- **header:** "{Area Name}"
- **question:** "Q{N}: {question text}"
- **options:** List the 1-2 alternatives plus "You decide" (maps to Agent's Discretion)

Record the user's choice. Re-display the updated table with the change reflected. Re-present the full acceptance prompt so the user can make additional changes or accept.

**On "Discuss deeper":** Switch to interactive mode for this area only — ask questions one at a time using ask_user with 2-3 concrete physics options per question plus "You decide". After 4 questions, prompt:
- **header:** "{Area Name}"
- **question:** "More questions about {area name}, or move to next?"
- **options:** "More questions" / "Next area"

If "More questions", ask 4 more. If "Next area", display final summary table of captured answers for this area and move on.

**On "Other" (free text):** Interpret as either a specific change request or general feedback. Incorporate into the area's decisions, re-display updated table, re-present acceptance prompt.

**Scope creep handling:** If user mentions something outside the phase domain:

```
"{Topic} is an important physics question — but it belongs in its own phase.
I'll note it as a deferred idea.

Back to {current area}: {return to current question}"
```

Track deferred ideas internally for inclusion in CONTEXT.md.

---

### Sub-step 5: Write CONTEXT.md

After all areas are resolved (or infrastructure skip), write the CONTEXT.md file.

**File path:** `${phase_dir}/${padded_phase}-CONTEXT.md`

Use **exactly** this structure (all 9 sections from templates/context.md):

```markdown
# Phase {PHASE_NUM}: {Phase Name} - Context

**Gathered:** {date}
**Status:** Ready for planning

<domain>
## Phase Boundary

{Domain boundary statement from analysis — what research question this phase answers}

Requirements: [{REQ-IDs from ROADMAP.md phase details}]

</domain>

<contract_coverage>
## Contract Coverage

- [Claim / deliverable]: [What counts as success]
- [Acceptance signal]: [Benchmark match, proof obligation, figure, dataset, or note]
- [False progress to reject]: [Proxy that must not count]

</contract_coverage>

<user_guidance>
## User Guidance To Preserve

- **User-stated observables:** {From discussion answers or prior context — specific quantities/figures}
- **User-stated deliverables:** {Specific table, plot, derivation, dataset, or code output}
- **Must-have references / prior outputs:** {Papers, notebooks, baselines that must stay visible}
- **Stop / rethink conditions:** {When to pause or re-scope}

</user_guidance>

<decisions>
## Methodological Decisions

### {Area 1 Name}
- {Accepted/chosen answer for Q1}
- {Accepted/chosen answer for Q2}
- {Accepted/chosen answer for Q3}
- {Accepted/chosen answer for Q4}

### {Area 2 Name}
- {Accepted/chosen answer for Q1}
- {Accepted/chosen answer for Q2}
...

### Agent's Discretion
{Any "You decide" answers collected — note the agent has flexibility here}

</decisions>

<assumptions>
## Physical Assumptions

- [Assumption 1]: [Justification] | [What breaks if wrong]
- [Assumption 2]: [Justification] | [What breaks if wrong]

</assumptions>

<limiting_cases>
## Expected Limiting Behaviors

- [Limit 1]: When [parameter] -> [value], result should -> [expected behavior]
- [Limit 2]: When [parameter] -> [value], result should -> [expected behavior]

</limiting_cases>

<anchor_registry>
## Active Anchor Registry

{References, baselines, prior outputs that must remain visible during planning and execution.}

- [Anchor]: [Why it matters] | Carry forward: [planning | execution | verification] | Action: [read | compare | cite]

</anchor_registry>

<skeptical_review>
## Skeptical Review

- **Weakest anchor:** {Least-certain assumption or prior result}
- **Unvalidated assumptions:** {What is assumed rather than checked}
- **Competing explanation:** {Alternative physical picture that could also fit}
- **Disconfirming check:** {Earliest observation that would force a re-think}
- **False progress to reject:** {What looks promising but should not count}

</skeptical_review>

<deferred>
## Deferred Ideas

{Ideas that came up but belong in other phases}
{If none: "None — discussion stayed within phase scope"}

</deferred>
```

Write the file. Ensure `mkdir -p "${phase_dir}"` first.

**Commit:**

```bash
gpd commit "docs(${padded_phase}): smart discuss context" --files "${phase_dir}/${padded_phase}-CONTEXT.md"
```

Display confirmation:

```
Created: {path}
Decisions captured: {count} across {area_count} areas
```

</step>

<step name="convention_check">

## 3f. Convention Propagation Check

After each phase completes (verification passed or gaps accepted), check convention consistency with prior phases. This is a GPD-specific gate that GSD does not need.

**Check if CONVENTIONS.md exists:**

```bash
ls GPD/CONVENTIONS.md 2>/dev/null
```

**If CONVENTIONS.md does not exist:** Skip this step — no conventions to check against.

**If CONVENTIONS.md exists:** Run the command-backed convention validation on the just-completed phase. This is the authoritative check — no ad-hoc scanning.

```
Invoke the runtime-installed `gpd:validate-conventions` command with `${PHASE_NUM}`.
```

Read the validation result. The command writes a validation artifact or reports to stdout.

**If validation passes (no issues reported):**

Display:
```
Phase ${PHASE_NUM}: Convention check passed — consistent with CONVENTIONS.md
```

Proceed to iterate step.

**If validation reports issues (convention drift, symbol redefinition, unit mismatch, sign conflict):**

Display the specific issues found, then ask user via ask_user:
- **question:** "Convention issues found in phase ${PHASE_NUM}. How to proceed?"
- **options:** "Continue — drift is intentional" / "Stop autonomous mode"

On **"Continue — drift is intentional":** Display `Phase ${PHASE_NUM}: Convention drift accepted by user` and proceed to iterate step.

On **"Stop autonomous mode":** Go to handle_blocker with "Convention issues in phase ${PHASE_NUM} — user stopped to investigate."

</step>

<step name="iterate">

## 4. Iterate

After each phase completes (including convention check), re-read ROADMAP.md to catch phases inserted mid-execution (decimal phases like 3.1):

```bash
ROADMAP=$(gpd --raw roadmap analyze)
```

Re-filter incomplete phases using the same logic as discover_phases:
- Keep phases where `disk_status !== "complete"` OR `roadmap_complete === false`
- Apply `--from N` filter if originally provided
- Sort by number ascending

Read STATE.md fresh:

```bash
cat GPD/STATE.md
```

Check for blockers in the Blockers/Concerns section. If blockers are found, go to handle_blocker with the blocker description.

If incomplete phases remain: proceed to next phase, loop back to execute_phase.

If all phases complete, proceed to lifecycle step.

</step>

<step name="lifecycle">

## 5. Lifecycle

After all phases complete, run the milestone lifecycle sequence: audit → complete.

Display lifecycle transition banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD ► AUTONOMOUS ▸ LIFECYCLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 All phases complete → Starting lifecycle: audit → complete
 Milestone: {milestone_version} — {milestone_name}
```

**5a. Audit**

```
Invoke the runtime-installed `gpd:audit-milestone` command.
```

After audit completes, detect the result:

```bash
AUDIT_FILE="GPD/v${milestone_version}-MILESTONE-AUDIT.md"
AUDIT_STATUS=$(grep "^status:" "${AUDIT_FILE}" 2>/dev/null | head -1 | cut -d: -f2 | tr -d ' ')
```

**If AUDIT_STATUS is empty** (no audit file or no status field):

Go to handle_blocker: "Audit did not produce results — audit file missing or malformed."

**If `passed`:**

Display:
```
Audit passed — proceeding to complete milestone
```

Proceed to 5b.

**If `gaps_found`:**

Read the gaps summary from the audit file. Display:
```
Audit: Gaps Found
```

Ask user via ask_user:
- **question:** "Milestone audit found gaps (e.g., unchecked limits, missing cross-phase consistency, unsupported claims). How to proceed?"
- **options:** "Plan gap closure phases" / "Continue anyway — accept gaps" / "Stop — fix gaps manually"

On **"Plan gap closure phases":**
```
Invoke the runtime-installed `gpd:plan-milestone-gaps` command.
```

After gap phases are planned, display: "Gap closure phases added to roadmap. Returning to autonomous execution." and loop back to discover_phases to pick up the new phases.

On **"Continue anyway"**: Display `Audit gaps accepted — proceeding to complete milestone` and proceed to 5b.

On **"Stop"**: Go to handle_blocker with "User stopped — audit gaps remain. Run `gpd:audit-milestone` to review, then `gpd:plan-milestone-gaps` to create fix phases."

**If `tech_debt` or `issues_found`:**

Read the summary from the audit file. Display the summary, then ask user via ask_user:
- **question:** "Milestone audit found issues. How to proceed?"
- **options:** "Continue with known issues" / "Stop — address issues first"

On **"Continue with known issues"**: Display `Audit issues acknowledged — proceeding to complete milestone` and proceed to 5b.

On **"Stop"**: Go to handle_blocker with "User stopped — audit issues to address. Run `gpd:audit-milestone` to review details."

**5b. Complete Milestone**

```
Invoke the runtime-installed `gpd:complete-milestone` command with `${milestone_version}`.
```

After complete-milestone returns, verify it produced output:

```bash
ls GPD/milestones/v${milestone_version}-ROADMAP.md 2>/dev/null || true
```

If the archive file does not exist, go to handle_blocker: "Complete milestone did not produce expected archive files."

**5c. Final Completion**

Display final completion banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD ► AUTONOMOUS ▸ COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Milestone: {milestone_version} — {milestone_name}
 Status: Complete
 Lifecycle: audit → complete

 Research milestone archived. Run gpd:new-milestone to start the next phase of investigation.
```

</step>

<step name="handle_blocker">

## 6. Handle Blocker

When any phase operation fails or a blocker is detected, present 3 options via ask_user:

**Prompt:** "Phase {N} ({Name}) encountered an issue: {description}"

**Options:**
1. **"Fix and retry"** — Re-run the failed step (discuss, plan, execute, or verify) for this phase
2. **"Skip this phase"** — Mark phase as skipped, continue to the next incomplete phase
3. **"Stop autonomous mode"** — Display summary of progress so far and exit cleanly

**On "Fix and retry":** Loop back to the failed step within execute_phase. Track retry count per phase. If the same step fails again after retry, re-present these options. **Hard limit: 3 retries per phase.** After 3 retries on the same phase, remove "Fix and retry" from options — only "Skip" or "Stop" remain.

**On "Skip this phase":** Log `Phase {N} -- {Name} — Skipped by user` and proceed to iterate.

**On "Stop autonomous mode":** Display progress summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD ► AUTONOMOUS ▸ STOPPED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Completed: {list of completed phases}
 Skipped: {list of skipped phases}
 Remaining: {list of remaining phases}

 Resume with: gpd:autonomous --from {next_phase}
```

</step>

</process>

<success_criteria>
- [ ] All incomplete phases executed in order (smart discuss → plan → execute → verify each)
- [ ] Smart discuss proposes gray area answers in tables, user accepts or overrides per area
- [ ] Smart discuss gray areas are physics-domain-aware (formalism for derivation phases, algorithm for numerical phases)
- [ ] Model profile (deep-theory/numerical/exploratory/review/paper-writing) adjusts smart discuss depth and focus
- [ ] Progress banners displayed between phases
- [ ] Execute-phase invoked with only the phase number; execute-phase owns normal phase transition / closeout
- [ ] Post-execution verification reads VERIFICATION.md and routes on status
- [ ] Missing VERIFICATION.md triggers explicit gpd:verify-work invocation
- [ ] Passed verification → automatic continue to convention check then next phase
- [ ] Gaps-found → user offered gap closure, continue, or stop
- [ ] Gap closure limited to 1 retry (prevents infinite loops)
- [ ] Plan-phase and execute-phase failures route to handle_blocker
- [ ] ROADMAP.md re-read after each phase (catches inserted phases)
- [ ] STATE.md checked for blockers before each phase
- [ ] Blockers handled via user choice (retry / skip / stop)
- [ ] Convention propagation check after each phase (if CONVENTIONS.md exists)
- [ ] Convention drift detected → user offered validation, accept, or stop
- [ ] Paper-writing phases detected and routed to gpd:write-paper when user confirms
- [ ] Prior phase CONTEXT.md decisions respected (no re-asking decided questions)
- [ ] CONVENTIONS.md consulted during smart discuss (locked conventions are not re-proposed)
- [ ] Final completion or stop summary displayed
- [ ] After all phases complete, lifecycle step is invoked (not manual suggestion)
- [ ] Lifecycle transition banner displayed before audit
- [ ] Audit invoked via the runtime-installed `gpd:audit-milestone` command
- [ ] Audit result routing: passed → auto-continue, gaps_found → user decides
- [ ] Audit gap closure offered via gpd:plan-milestone-gaps (loops back to phase execution)
- [ ] Audit technical failure (no file/no status) routes to handle_blocker
- [ ] Complete-milestone invoked via the runtime-installed command with `${milestone_version}` arg
- [ ] Final completion banner displayed after lifecycle
- [ ] Progress bar uses phase number / total milestone phases (not position among incomplete)
- [ ] Smart discuss documents relationship to discuss-phase
- [ ] Smart discuss produces the same CONTEXT.md contract as discuss-phase
- [ ] No UI-phase or frontend-specific detection (GPD is physics research, not software)
- [ ] Local CLI invocations use current `gpd` surfaces
- [ ] Project artifacts stay under canonical `GPD/` paths
- [ ] Workflow stays runtime/provider-neutral and relies only on installed runtime command delegation
</success_criteria>
