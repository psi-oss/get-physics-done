<purpose>
Initialize a new physics research project through unified flow: questioning, literature survey (optional), mathematical framework, computational setup, target venue identification. This is the most leveraged moment in any research project — deep questioning here means better formulations, better methods, better results. One workflow takes you from research idea to ready-for-investigation.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<auto_mode>

## Auto Mode Detection

Check if `--auto` flag is present in $ARGUMENTS.

**If auto mode:**

- Skip existing-work mapping offer (assume fresh project)
- Skip deep questioning (extract context from provided document)
- Config questions still required (Step 5)
- After config: run Steps 6-9 automatically with smart defaults:
  - Literature survey: Always yes
  - Research questions: Include all from provided document
  - Research questions approval: Auto-approve
  - Roadmap approval: Auto-approve

**Document requirement:**
Auto mode requires a research document via @ reference (e.g., `/gpd:new-project --auto @proposal.md`). If no document provided, error:

```
Error: --auto requires a research document via @ reference.

Usage: /gpd:new-project --auto @your-proposal.md

The document should describe the physics problem you want to investigate.
```

</auto_mode>

<minimal_mode>

## Minimal Mode Detection

Check if `--minimal` flag is present in $ARGUMENTS.

**If minimal mode:** After Step 1 (Setup), skip the entire standard flow (Steps 2-9) and execute the **Minimal Initialization Path** below instead.

Minimal mode creates the SAME directory structure and file set as the full path -- just with less content in each file. This ensures all downstream workflows (`/gpd:plan-phase`, `/gpd:execute-phase`, etc.) work identically.

**Two variants:**

1. `--minimal @file.md` — Input file provided. Parse it for research context.
2. `--minimal` (no file) — Ask ONE question, then generate everything from the response.

---

### Minimal Initialization Path

**After Step 1 completes (init checks, git, project_exists guard):**

#### M1. Gather Research Context

**If `--minimal` with file** (`/gpd:new-project --minimal @plan.md`):

Parse the input markdown for:

- **Research question** — Look for headings like "Research Question", "Objective", "Goal", or the first substantive paragraph
- **List of phases** — Look for numbered lists, headings like "Phases", "Plan", "Steps", or "Milestones"
- **Key parameters** — Look for mentions of physical parameters, coupling constants, energy scales, system sizes
- **Theoretical framework** — Infer from terminology (QFT, condensed matter, GR, statistical mechanics, etc.)
- **Computational tools** — Any mentioned software, libraries, or numerical methods

If the file cannot be parsed (no discernible research question or phases), error:

```
Error: Could not extract research context from the provided file.

The file should contain at minimum:
- A research question or objective
- A list of investigation phases or steps

Example structure:
  # Research Question
  What is the critical exponent of the 3D Ising model?

  # Phases
  1. Set up Monte Carlo simulation
  2. Run finite-size scaling analysis
  3. Extract critical exponent and compare with known results
```

**If `--minimal` without file** (`/gpd:new-project --minimal`):

Ask ONE question inline (freeform, NOT ask_user):

"Describe your research project: what's the physics question, and what are the main phases of investigation?"

Wait for response. From the single response, extract:

- Research question
- Theoretical framework
- Phases of investigation
- Any mentioned parameters, tools, or constraints

#### M2. Create PROJECT.md

Populate `.gpd/PROJECT.md` using the template from `templates/project.md`.

Fill in what was extracted. For sections without enough information, use sensible placeholder text that signals incompleteness:

```markdown
# [Extracted Research Title]

## What This Is

[Extracted research description — keep it concise, 2-3 sentences from the input]

## Core Research Question

[Extracted research question]

## Physics Subfield

[Inferred from input, e.g., "Condensed matter — phase transitions"]

## Mathematical Framework

[Inferred from input, or "To be determined during Phase 1"]

## Notation Conventions

To be established during initial phases.

## Unit System

[Inferred from input, or "Natural units (hbar = c = 1)"]

## Computational Tools

[Extracted from input, or "To be determined"]

## Requirements

### Validated

(None yet — derive and validate to confirm)

### Active

- [ ] [One requirement per extracted phase goal]

### Out of Scope

(To be refined as project progresses)

## Key References

(To be populated during literature review)

## Target Publication

(To be determined)

## Constraints

(None specified)

## Key Decisions

| Decision                                    | Rationale              | Outcome   |
| ------------------------------------------- | ---------------------- | --------- |
| Minimal initialization — defer deep scoping | Fast project bootstrap | — Pending |

---

_Last updated: [today's date] after initialization (minimal)_
```

#### M3. Create REQUIREMENTS.md

Auto-generate REQ-IDs from the phase goals extracted in M1.

For each phase, create one or more requirements using the standard format:

```markdown
# Research Requirements

## Current Requirements

### Phase-Derived Requirements

[For each phase, generate requirements with REQ-IDs:]

- [ ] **REQ-01**: [Goal of phase 1, made specific and testable]
- [ ] **REQ-02**: [Goal of phase 2, made specific and testable]
- [ ] **REQ-03**: [Goal of phase 3, made specific and testable]
      [... one per phase minimum ...]

## Future Work

(To be identified as project progresses)

## Out of Scope

(To be refined — use /gpd:settings or edit REQUIREMENTS.md directly)

## Traceability

| REQ-ID | Phase | Status  |
| ------ | ----- | ------- |
| REQ-01 | 1     | Planned |
| REQ-02 | 2     | Planned |
| REQ-03 | 3     | Planned |
```

#### M4. Create ROADMAP.md

Create `.gpd/ROADMAP.md` directly from the phase descriptions (no roadmapper agent).

Use the standard roadmap template structure:

```markdown
# Roadmap: [Research Project Title]

## Overview

[One paragraph synthesized from the research description]

## Phases

- [ ] **Phase 1: [Phase name]** - [One-line description]
- [ ] **Phase 2: [Phase name]** - [One-line description]
- [ ] **Phase 3: [Phase name]** - [One-line description]
      [... from extracted phases ...]

## Phase Details

### Phase 1: [Phase name]

**Goal:** [Extracted from input]
**Depends on:** Nothing (first phase)
**Requirements:** [REQ-01]
**Success Criteria** (what must be TRUE):

1. [Derived from phase goal — one concrete observable outcome]
2. [Second criterion if obvious from context]

Plans:

- [ ] 01-01: [TBD — created during /gpd:plan-phase]

[... repeat for each phase ...]

## Progress

| Phase     | Plans Complete | Status      | Completed |
| --------- | -------------- | ----------- | --------- |
| 1. [Name] | 0/TBD          | Not started | -         |
| 2. [Name] | 0/TBD          | Not started | -         |
| 3. [Name] | 0/TBD          | Not started | -         |
```

#### M5. Create STATE.md and config.json

**STATE.md** — Initialize using the standard template:

```markdown
# Research State

## Project Reference

See: .gpd/PROJECT.md (updated [today's date])

**Core research question:** [From PROJECT.md]
**Current focus:** Phase 1 — [Phase 1 name]

## Current Position

**Current Phase:** 1
**Current Phase Name:** [Phase 1 name]
**Total Phases:** [N]
**Current Plan:** 0
**Total Plans in Phase:** 0
**Status:** Ready to plan
**Last Activity:** [today's date]
**Last Activity Description:** Project initialized (minimal)

**Progress:** [░░░░░░░░░░] 0%

## Active Calculations

None yet.

## Intermediate Results

None yet.

## Open Questions

None yet.

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 1]: Minimal mode — deep scoping deferred to phase planning

### Active Approximations

None yet.

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

**Last session:** [today's date]
**Stopped at:** Project initialized (minimal)
**Resume file:** None
```

**config.json** — Create with sensible defaults (no config questions asked):

```json
{
  "mode": "yolo",
  "depth": "standard",
  "parallelization": true,
  "commit_docs": true,
  "model_profile": "review",
  "workflow": {
    "research": true,
    "plan_checker": true,
    "verifier": true
  },
  "initialized_with": "minimal"
}
```

#### M6. Commit All Artifacts

Create the directory structure and commit everything in a single commit:

```bash
mkdir -p .gpd

PRE_CHECK=$(gpd pre-commit-check --files .gpd/PROJECT.md .gpd/REQUIREMENTS.md .gpd/ROADMAP.md .gpd/STATE.md .gpd/config.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: initialize research project (minimal)" --files .gpd/PROJECT.md .gpd/REQUIREMENTS.md .gpd/ROADMAP.md .gpd/STATE.md .gpd/config.json
```

#### M7. Done — Offer Next Step

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> RESEARCH PROJECT INITIALIZED (MINIMAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**[Research Project Name]**

| Artifact     | Location                    |
|--------------|-----------------------------|
| Project      | `.gpd/PROJECT.md`      |
| Config       | `.gpd/config.json`     |
| Requirements | `.gpd/REQUIREMENTS.md` |
| Roadmap      | `.gpd/ROADMAP.md`      |
| State        | `.gpd/STATE.md`        |

**[N] phases** | **[N] requirements** | Ready to investigate

Note: Initialized with --minimal. Literature survey and deep scoping
were skipped. Use /gpd:settings to adjust workflow preferences.

---------------------------------------------------------------

## >> Next Up

**Phase 1: [Phase Name]** — [Goal from ROADMAP.md]
```

Use ask_user:

- header: "Next Step"
- question: "Plan phase 1 now?"
- options:
  - "Plan phase 1" — Run /gpd:plan-phase 1
  - "Review artifacts first" — I want to check the generated files
  - "Done for now" — I'll continue later

**If "Plan phase 1":** Tell the user to run `/gpd:plan-phase 1` (and suggest `/clear` first for a fresh context window).

**If "Review artifacts first":** List the files and let the user inspect them. Suggest edits if needed, then re-offer planning.

**If "Done for now":** Exit. Remind them to use `/gpd:resume-work` or `/gpd:plan-phase 1` when ready.

---

**End of Minimal Initialization Path.** The standard flow (Steps 2-9) is not executed when `--minimal` is active.

</minimal_mode>

<process>

## 1. Setup

**MANDATORY FIRST STEP — Execute these checks before ANY user interaction:**

```bash
INIT=$(gpd init new-project)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed with the workflow.
fi
```

Parse JSON for: `researcher_model`, `synthesizer_model`, `roadmapper_model`, `commit_docs`, `autonomy`, `research_mode`, `project_exists`, `has_theory_map`, `planning_exists`, `has_research_files`, `has_project_manifest`, `has_existing_project`, `needs_theory_map`, `has_git`.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause for user confirmation after each major step (questioning, research, roadmap). Show summaries and wait for approval before proceeding.
- `autonomy=guided` (default): Pause only if research results are ambiguous or roadmap has gaps. Auto-proceed through clear steps.
- `autonomy=autonomous`: Execute full pipeline without pausing. Present final PROJECT.md + ROADMAP.md at end.
- `autonomy=yolo`: Execute full pipeline, skip optional literature survey, auto-approve roadmap.
- `research_mode=explore`: Expand literature survey (spawn 5+ researchers), broader questioning, include speculative research directions in roadmap.
- `research_mode=exploit`: Focused literature survey (2-3 researchers), targeted questioning, lean roadmap with minimal exploratory phases.
- `research_mode=adaptive`: Start with exploit-depth survey, expand to explore if initial results reveal unexpected complexity.

**If `project_exists` is true:** Error — project already initialized. Use `/gpd:progress`.

**If `has_git` is false:** Initialize git:

```bash
git init
```

**Check for previous initialization attempt:**

```bash
if [ -f .gpd/init-progress.json ]; then
  # Guard against corrupted JSON (e.g., from interrupted write)
  PREV_STEP=""
  PREV_DESC=""
  INIT_PROGRESS_RAW=$(cat .gpd/init-progress.json 2>/dev/null || echo "")
  if [ -n "$INIT_PROGRESS_RAW" ]; then
    PREV_STEP=$(echo "$INIT_PROGRESS_RAW" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('step',''))" 2>/dev/null)
    PREV_DESC=$(echo "$INIT_PROGRESS_RAW" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('description',''))" 2>/dev/null)
  fi

  # If JSON was corrupted (empty step), treat as fresh start
  if [ -z "$PREV_STEP" ]; then
    echo "WARNING: init-progress.json exists but is corrupted or empty. Starting fresh."
    rm -f .gpd/init-progress.json
  fi
fi
```

If `init-progress.json` exists and is valid, offer to resume:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PREVIOUS INITIALIZATION DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Completed through step {PREV_STEP}: {PREV_DESC}

──────────────────────────────────────────────────────
Options:
  1. "Resume from step {PREV_STEP + 1}" -- continue where you left off
  2. "Start fresh" -- re-run from the beginning
──────────────────────────────────────────────────────
```

If resume: skip to the step after PREV_STEP (check which artifacts already exist on disk to confirm).
If start fresh: delete `init-progress.json` and proceed normally.

## 2. Existing Work Offer

**If auto mode:** Skip to Step 4 (assume fresh project, synthesize PROJECT.md from provided document).

**If `needs_theory_map` is true** (from init — existing research artifacts detected but no work map):

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

Use ask_user:

- header: "Existing Research"
- question: "I detected existing research artifacts in this directory. Would you like to map the existing work first?"
- options:
  - "Map existing work first" — Run /gpd:map-theory to understand current research state (Recommended)
  - "Skip mapping" — Proceed with fresh project initialization

**If "Map existing work first":**

```
Run `/gpd:map-theory` first, then return to `/gpd:new-project`
```

Exit command.

**If "Skip mapping" OR `needs_theory_map` is false:** Continue to Step 3.

## 3. Deep Questioning

**If auto mode:** Skip. Extract research context from provided document instead and proceed to Step 4.

**Display stage banner:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> RESEARCH QUESTION FORMULATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Open the conversation:**

Ask inline (freeform, NOT ask_user):

"What physics problem do you want to investigate?"

Wait for their response. This gives you the context needed to ask intelligent follow-up questions.

**Follow the thread:**

Based on what they said, ask follow-up questions that dig into their response. Use ask_user with options that probe what they mentioned — interpretations, clarifications, concrete examples.

Keep following threads. Each answer opens new threads to explore. Ask about:

- What physical system or phenomenon motivated this
- What they already know or suspect about the answer
- What theoretical framework they are working in
- What approximations or limits they are considering
- What observable or measurable quantities they care about
- What computational resources they have access to
- Whether this connects to existing experimental data

Consult `{GPD_INSTALL_DIR}/references/questioning.md` for techniques:

- Challenge vagueness ("What do you mean by 'interesting regime'?")
- Make abstract concrete ("Can you write down the Hamiltonian?")
- Surface assumptions ("Are you assuming equilibrium? Why?")
- Find edges ("What happens at strong coupling?")
- Reveal motivation ("What would change if you solved this?")

**Check context (background, not out loud):**

As you go, mentally check the context checklist from `{GPD_INSTALL_DIR}/references/questioning.md`. If gaps remain, weave questions naturally. Don't suddenly switch to checklist mode.

Context to gather:

- Research question (precise, falsifiable or answerable)
- Physical system and regime
- Theoretical framework (QFT, condensed matter, GR, statistical mechanics, etc.)
- Key parameters and scales
- Known results in the field (what has been done)
- What is new or open (what has NOT been done)
- Computational vs analytical approach preference
- Target audience and venue (journal, conference)
- Timeline and collaboration context
- Available computational resources

**Decision gate:**

When you could write a clear PROJECT.md, use ask_user:

- header: "Ready?"
- question: "I think I understand the research direction. Ready to create PROJECT.md?"
- options:
  - "Create PROJECT.md" — Let's move forward
  - "Keep exploring" — I want to share more / ask me more

If "Keep exploring" — ask what they want to add, or identify gaps and probe naturally.

**Maximum 6 questioning iterations.** After iteration 6, proceed to PROJECT.md creation with gathered context, noting any unresolved questions in the project's `open_questions`. Loop until "Create PROJECT.md" selected or iteration limit reached.

## 4. Write PROJECT.md

**If auto mode:** Synthesize from provided document. No "Ready?" gate was shown — proceed directly to commit.

Synthesize all context into `.gpd/PROJECT.md` using the template from `templates/project.md`.

**For fresh research projects:**

Initialize research questions as hypotheses:

```markdown
## Research Questions

### Answered

(None yet — investigate to answer)

### Active

- [ ] [Research question 1]
- [ ] [Research question 2]
- [ ] [Research question 3]

### Out of Scope

- [Question 1] — [why: e.g., requires experiment, different subfield]
- [Question 2] — [why]
```

**For continuation projects (existing work map exists):**

Infer answered questions from existing work:

1. Read `.gpd/research-map/ARCHITECTURE.md` and `FORMALISM.md`
2. Identify what has already been established
3. These become the initial Answered set

```markdown
## Research Questions

### Answered

- [checkmark] [Existing result 1] — established
- [checkmark] [Existing result 2] — established
- [checkmark] [Existing result 3] — established

### Active

- [ ] [New question 1]
- [ ] [New question 2]

### Out of Scope

- [Question 1] — [why]
```

**Key Decisions:**

Initialize with any decisions made during questioning:

```markdown
## Key Decisions

| Decision                  | Rationale | Outcome   |
| ------------------------- | --------- | --------- |
| [Choice from questioning] | [Why]     | — Pending |
```

**Research Context:**

```markdown
## Research Context

### Physical System

[Description of the system under study]

### Theoretical Framework

[QFT / condensed matter / GR / statistical mechanics / etc.]

### Key Parameters and Scales

| Parameter | Symbol | Regime  | Notes   |
| --------- | ------ | ------- | ------- |
| [param 1] | [sym]  | [range] | [notes] |

### Known Results

- [Prior work 1] — [reference]
- [Prior work 2] — [reference]

### What Is New

[What this project contributes beyond existing work]

### Target Venue

[Journal or conference, with rationale]

### Computational Environment

[Available resources: local workstation, cluster, cloud, specific codes]
```

**Last updated footer:**

```markdown
---

_Last updated: [date] after initialization_
```

Do not compress. Capture everything gathered.

**Commit PROJECT.md:**

```bash
mkdir -p .gpd

PRE_CHECK=$(gpd pre-commit-check --files .gpd/PROJECT.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: initialize research project" --files .gpd/PROJECT.md
```

**Checkpoint step 4:**

```bash
cat > .gpd/init-progress.json << CHECKPOINT
{"step": 4, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "PROJECT.md created and committed"}
CHECKPOINT
```

## 5. Workflow Preferences

**Quick setup gate — offer recommended defaults before individual questions:**

Use ask_user:

- header: "Workflow Setup"
- question: "How would you like to configure the project?"
- options:
  - "Use recommended defaults (Recommended)" — YOLO mode, standard depth, parallel execution, all agents enabled, review profile. Saves 3-5 minutes.
  - "Customize settings" — Choose mode, depth, agents, and model profile individually

**If "Use recommended defaults":** Skip all 8 config questions below. Create config.json directly with:

```json
{
  "mode": "yolo",
  "depth": "standard",
  "parallelization": true,
  "commit_docs": true,
  "model_profile": "review",
  "workflow": {
    "research": true,
    "plan_checker": true,
    "verifier": true
  },
  "initialized_with": "quick-setup"
}
```

Display confirmation:

```
Config: YOLO mode | Standard depth | Parallel | All agents | Review profile
(Change anytime with /gpd:settings)
```

Skip to "Commit config.json" below.

**If "Customize settings":** Proceed through Round 1 and Round 2 below.

---

**Round 1 — Core workflow settings (4 questions):**

```
questions: [
  {
    header: "Mode",
    question: "How do you want to work?",
    multiSelect: false,
    options: [
      { label: "YOLO (Recommended)", description: "Auto-approve, just execute" },
      { label: "Interactive", description: "Confirm at each step" }
    ]
  },
  {
    header: "Depth",
    question: "How thorough should planning be?",
    multiSelect: false,
    options: [
      { label: "Quick", description: "Fast exploration (3-5 phases, 1-3 plans each)" },
      { label: "Standard", description: "Balanced rigor and speed (5-8 phases, 3-5 plans each)" },
      { label: "Comprehensive", description: "Thorough investigation (8-12 phases, 5-10 plans each)" }
    ]
  },
  {
    header: "Execution",
    question: "Run plans in parallel?",
    multiSelect: false,
    options: [
      { label: "Parallel (Recommended)", description: "Independent plans run simultaneously" },
      { label: "Sequential", description: "One plan at a time" }
    ]
  },
  {
    header: "Git Tracking",
    question: "Commit planning docs to git?",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Planning docs tracked in version control" },
      { label: "No", description: "Keep .gpd/ local-only (add to .gitignore)" }
    ]
  }
]
```

**Round 2 — Workflow agents (only if customizing):**

These spawn additional agents during planning/execution. They add tokens and time but improve quality.

| Agent                   | When it runs               | What it does                                                                        |
| ----------------------- | -------------------------- | ----------------------------------------------------------------------------------- |
| **Literature Scout**    | Before planning each phase | Surveys relevant literature, finds key references, surfaces known results           |
| **Derivation Checker**  | After plan is created      | Verifies mathematical consistency and completeness of proposed approach             |
| **Validation Verifier** | After phase execution      | Confirms results satisfy physical constraints, limiting cases, and known benchmarks |

All recommended for rigorous research. Skip for quick exploratory calculations.

```
questions: [
  {
    header: "Literature Survey",
    question: "Survey literature before planning each phase? (adds tokens/time)",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Find relevant references, known results, standard methods" },
      { label: "No", description: "Plan directly from research questions" }
    ]
  },
  {
    header: "Derivation Check",
    question: "Verify mathematical approach before execution? (adds tokens/time)",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Catch errors in formulation before computing" },
      { label: "No", description: "Execute approach without mathematical pre-check" }
    ]
  },
  {
    header: "Validation",
    question: "Validate results against known limits after each phase? (adds tokens/time)",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Check limiting cases, conservation laws, dimensional analysis" },
      { label: "No", description: "Trust results, skip systematic validation" }
    ]
  },
  {
    header: "Model Profile",
    question: "Which AI models for planning agents?",
    multiSelect: false,
    options: [
      { label: "Review (Recommended)", description: "Balanced cost/quality — tier-1 for critical agents, tier-2 for others" },
      { label: "Deep Theory", description: "Maximum capability — tier-1 for most agents — higher cost, deeper analysis" },
      { label: "Exploratory", description: "Fast iteration — tier-2/tier-3 where possible — fastest, lowest cost" }
    ]
  }
]
```

Create `.gpd/config.json` with all settings:

```json
{
  "mode": "yolo|interactive",
  "depth": "quick|standard|comprehensive",
  "parallelization": true|false,
  "commit_docs": true|false,
  "model_profile": "deep-theory|review|exploratory",
  "workflow": {
    "research": true|false,
    "plan_checker": true|false,
    "verifier": true|false
  }
}
```

**If commit_docs = No:**

- Set `commit_docs: false` in config.json
- Add `.gpd/` to `.gitignore` (create if needed)

**If commit_docs = Yes:**

- No additional gitignore entries needed

**Commit config.json:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/config.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "chore: add project config" --files .gpd/config.json
```

**Checkpoint step 5:**

```bash
cat > .gpd/init-progress.json << CHECKPOINT
{"step": 5, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "config.json created and committed"}
CHECKPOINT
```

**Note:** Run `/gpd:settings` anytime to update these preferences.

## 5.5. Resolve Model Profile

Use models from init: `researcher_model`, `synthesizer_model`, `roadmapper_model`.

## 6. Literature Survey Decision

**If auto mode:** Default to "Survey first" without asking.

Use ask_user:

- header: "Literature Survey"
- question: "Survey the research landscape before defining the investigation plan?"
- options:
  - "Survey first (Recommended)" — Discover known results, standard methods, open problems, available data
  - "Skip survey" — I know this field well, go straight to planning

**If "Survey first":**

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> SURVEYING RESEARCH LANDSCAPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Surveying [research domain] landscape...
```

Create research directory:

```bash
mkdir -p .gpd/research
```

**Determine project context:**

Check if this is a fresh project or continuation:

- If no "Answered" research questions in PROJECT.md → Fresh project (starting from scratch)
- If "Answered" questions exist → Continuation (building on existing results)

Display spawning indicator:

```
>>> Spawning 4 literature scouts in parallel...
  -> Known results survey
  -> Methods and techniques survey
  -> Computational approaches survey
  -> Open problems and pitfalls survey
```

Spawn 4 parallel gpd-project-researcher agents with rich context:

> See `{GPD_INSTALL_DIR}/references/known-bugs.md` for workarounds to known platform bugs affecting subagent spawning.

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolved to `null`, omit it. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Known Results dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: Survey the landscape of known results in [research domain].
Continuation: Survey what's new since the existing results. Don't re-survey established ground.
</project_context_type>

<question>
What are the key known results, exact solutions, and established techniques in [research domain]?
</question>

<project_context>
[PROJECT.md summary - research question, physical system, theoretical framework, key parameters]
</project_context>

<downstream_consumer>
Your PRIOR-WORK.md feeds into research planning. Be precise:
- Specific results with references (author, year, journal)
- Conditions under which results hold
- Limitations and assumptions
- What remains open or contested
</downstream_consumer>

<quality_gate>
- [ ] References are specific (not vague citations)
- [ ] Conditions and assumptions stated for each result
- [ ] Relevance to our specific problem explained
</quality_gate>

<output>
Write to: .gpd/research/PRIOR-WORK.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/PRIOR-WORK.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", description="Prior work research")

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Methods dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: What methods and computational tools are standard for [research domain]?
Continuation: What methods are appropriate for the new research questions?
</project_context_type>

<question>
What analytical techniques, numerical methods, and computational tools are standard for [research domain]?
</question>

<project_context>
[PROJECT.md summary]
</project_context>

<downstream_consumer>
Your METHODS.md feeds into approach selection. Categorize clearly:
- Analytical methods (exact solutions, perturbation theory, RG, etc.)
- Numerical methods (Monte Carlo, exact diagonalization, tensor networks, DFT, MD, etc.)
- Computational tools (specific codes, libraries, frameworks with versions)
- Validation techniques (benchmarks, limiting cases, sum rules)
</downstream_consumer>

<quality_gate>
- [ ] Methods are specific to this physics domain (not generic advice)
- [ ] Computational cost and scaling noted for numerical methods
- [ ] Known limitations and failure modes identified
</quality_gate>

<output>
Write to: .gpd/research/METHODS.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/METHODS.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", description="Methods research")

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Computational Approaches dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: What computational tools and algorithms are available for [research domain]?
Continuation: What computational extensions are needed for the new questions?
</project_context_type>

<question>
What computational approaches, algorithms, and software tools are available for [research domain]? What are the convergence criteria and resource requirements?
</question>

<project_context>
[PROJECT.md summary]
</project_context>

<downstream_consumer>
Your COMPUTATIONAL.md informs the computational strategy. Include:
- Algorithms with convergence criteria and scaling behavior
- Software packages, libraries, and frameworks (with versions)
- Integration with existing code or workflows
- Resource estimates (memory, CPU/GPU, storage)
- Known numerical pitfalls and stability issues
</downstream_consumer>

<quality_gate>
- [ ] Algorithms defined with convergence criteria
- [ ] Software versions current and dependencies mapped
- [ ] Resource estimates provided for key calculations
</quality_gate>

<output>
Write to: .gpd/research/COMPUTATIONAL.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/COMPUTATIONAL.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", description="Computational approaches research")

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Open Problems and Pitfalls dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: What are the known open problems and common pitfalls in [research domain]?
Continuation: What pitfalls are specific to extending existing results in the new directions?
</project_context_type>

<question>
What are the open problems, common mistakes, and known pitfalls in [research domain]?
</question>

<project_context>
[PROJECT.md summary]
</project_context>

<downstream_consumer>
Your PITFALLS.md prevents wasted effort. For each pitfall:
- Warning signs (how to detect early)
- Prevention strategy (how to avoid)
- Which research phase should address it
- References to papers that fell into this trap
</downstream_consumer>

<quality_gate>
- [ ] Pitfalls are specific to this physics domain (not generic research advice)
- [ ] Known incorrect results or retracted papers noted
- [ ] Numerical stability and convergence issues identified
- [ ] Common sign errors, factor-of-2 mistakes, gauge issues flagged
</quality_gate>

<output>
Write to: .gpd/research/PITFALLS.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/PITFALLS.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", description="Pitfalls research")
```

**If any research agent fails to spawn or returns an error:** Check which output files were created (PRIOR-WORK.md, METHODS.md, COMPUTATIONAL.md, PITFALLS.md). For each missing file, note the gap and continue with available outputs. If 3+ agents failed, offer: 1) Retry all agents, 2) Skip literature survey and proceed with manual research context, 3) Stop initialization. If 1-2 agents failed, proceed with the synthesizer using available files — the synthesis will be partial but usable.

After all 4 agents complete (or partial completion handled), spawn synthesizer to create SUMMARY.md:

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-research-synthesizer.md for your role and instructions.

<task>
Synthesize literature survey outputs into SUMMARY.md.
</task>

<research_files>
Read these files:
- .gpd/research/PRIOR-WORK.md
- .gpd/research/METHODS.md
- .gpd/research/COMPUTATIONAL.md
- .gpd/research/PITFALLS.md
</research_files>

<output>
Write to: .gpd/research/SUMMARY.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/SUMMARY.md
Do NOT commit — the orchestrator handles commits.
</output>
", subagent_type="gpd-research-synthesizer", model="{synthesizer_model}", description="Synthesize research")
```

**If the synthesizer agent fails to spawn or returns an error:** Check if individual research files exist. If they do, create a minimal SUMMARY.md in the main context by reading each file's key findings. The individual research files are more important than the synthesis — proceed with what exists.

Display research complete banner and key findings:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> LITERATURE SURVEY COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Key Findings

**Known Results:** [from SUMMARY.md]
**Standard Methods:** [from SUMMARY.md]
**Watch Out For:** [from SUMMARY.md]

Files: `.gpd/research/`
```

**Commit research files:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/research/PRIOR-WORK.md .gpd/research/METHODS.md .gpd/research/COMPUTATIONAL.md .gpd/research/PITFALLS.md .gpd/research/SUMMARY.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: literature survey complete" \
  --files .gpd/research/PRIOR-WORK.md .gpd/research/METHODS.md \
  .gpd/research/COMPUTATIONAL.md .gpd/research/PITFALLS.md \
  .gpd/research/SUMMARY.md
```

**Checkpoint step 6:**

```bash
cat > .gpd/init-progress.json << CHECKPOINT
{"step": 6, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "Literature survey completed"}
CHECKPOINT
```

**If "Skip survey":** Continue to Step 7.

## 7. Define Research Questions and Requirements

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> DEFINING RESEARCH REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Load context:**

Read PROJECT.md and extract:

- Core research question (the ONE thing that must be answered)
- Stated constraints (computational resources, timeline, method limitations)
- Any explicit scope boundaries

**If literature survey exists:** Read research/METHODS.md and PRIOR-WORK.md and extract available approaches.

**If auto mode:**

- Auto-include all essential research requirements (directly answer the core question)
- Include requirements explicitly mentioned in provided document
- Auto-defer tangential investigations not mentioned in document
- Skip per-category ask_user loops
- Skip "Any additions?" question
- Skip requirements approval gate
- Generate REQUIREMENTS.md and commit directly

**Present requirements by category (interactive mode only):**

```
Here are the research requirements for [domain]:

## Analytical Derivations
**Essential:**
- Derive the effective Hamiltonian in the [regime] limit
- Compute the [observable] to leading order in [parameter]

**Extended:**
- Include next-to-leading order corrections
- Explore connection to [related framework]

**Literature notes:** [any relevant notes]

---

## Numerical Validation
...
```

**If no literature survey:** Gather requirements through conversation instead.

Ask: "What are the key results you need to establish?"

For each objective mentioned:

- Ask clarifying questions to make it precise
- Probe for related calculations
- Group into categories (analytical, numerical, phenomenological)

**Scope each category:**

For each category, use ask_user:

- header: "[Category name]"
- question: "Which [category] requirements are in scope?"
- multiSelect: true
- options:
  - "[Objective 1]" — [brief description]
  - "[Objective 2]" — [brief description]
  - "[Objective 3]" — [brief description]
  - "None for now" — Defer entire category

Track responses:

- Selected requirements → current investigation
- Unselected essential → future work
- Unselected extended → out of scope

**Identify gaps:**

Use ask_user:

- header: "Additions"
- question: "Any requirements the literature survey missed? (Calculations specific to your approach)"
- options:
  - "No, survey covered it" — Proceed
  - "Yes, let me add some" — Capture additions

**Validate core question:**

Cross-check requirements against Core Research Question from PROJECT.md. If gaps detected, surface them.

**Generate REQUIREMENTS.md:**

Create `.gpd/REQUIREMENTS.md` with:

- Current Requirements grouped by category (checkboxes, REQ-IDs)
- Future Requirements (deferred)
- Out of Scope (explicit exclusions with reasoning)
- Traceability section (empty, filled by roadmap)

**REQ-ID format:** `[CATEGORY]-[NUMBER]` (ANAL-01, NUMR-02, PHENO-03)

**Objective quality criteria:**

Good research requirements are:

- **Specific and testable:** "Compute the spectral gap as a function of coupling g" (not "Study the spectrum")
- **Result-oriented:** "Derive expression for X" or "Determine whether Y holds" (not "Think about Z")
- **Atomic:** One calculation or result per requirement (not "Derive and numerically validate the phase diagram")
- **Independent:** Minimal dependencies on other requirements

Reject vague requirements. Push for specificity:

- "Study the phase transition" → "Determine the critical exponent nu for the [model] phase transition using [method]"
- "Compute correlators" → "Compute the two-point correlation function G(r) in the [regime] and extract the correlation length"

**Present full requirements list (interactive mode only):**

Show every requirement (not counts) for user confirmation:

```
## Current Research Requirements

### Analytical Derivations
- [ ] **ANAL-01**: Derive the effective low-energy Hamiltonian by integrating out high-energy modes
- [ ] **ANAL-02**: Compute the one-loop correction to the self-energy
- [ ] **ANAL-03**: Establish the Ward identity relating vertex and propagator

### Numerical Validation
- [ ] **NUMR-01**: Benchmark the derived spectral gap against exact diagonalization for N <= 16
- [ ] **NUMR-02**: Verify the predicted scaling exponent using finite-size scaling

[... full list ...]

---

Does this capture the research program? (yes / adjust)
```

If "adjust": Return to scoping.

**Commit requirements:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: define research requirements" --files .gpd/REQUIREMENTS.md
```

**Checkpoint step 7:**

```bash
cat > .gpd/init-progress.json << CHECKPOINT
{"step": 7, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "REQUIREMENTS.md created and committed"}
CHECKPOINT
```

## 8. Create Roadmap

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> CREATING RESEARCH ROADMAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>>> Spawning roadmapper...
```

Spawn gpd-roadmapper agent with context:

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-roadmapper.md for your role and instructions.

<planning_context>

**Read these files before proceeding:**
- `.gpd/PROJECT.md` — Project definition and research question
- `.gpd/REQUIREMENTS.md` — Derived requirements
- `.gpd/research/SUMMARY.md` — Literature survey (if exists)
- `.gpd/config.json` — Project configuration

</planning_context>

<instructions>
Create research roadmap:
1. Derive phases from requirements — typical physics research phases:
   - Literature deep-dive and framework setup
   - Analytical derivations (ordered by dependency)
   - Numerical implementation and validation
   - Parameter exploration and phenomenology
   - Paper drafting and peer review preparation
2. Map every requirement to exactly one phase
3. Derive 2-5 success criteria per phase (concrete, verifiable results)
4. Validate 100% coverage
5. Write files immediately (ROADMAP.md, STATE.md, update REQUIREMENTS.md traceability)
6. Return ROADMAP CREATED with summary

Write files first, then return. This ensures artifacts persist even if context is lost.
</instructions>
", subagent_type="gpd-roadmapper", model="{roadmapper_model}", description="Create research roadmap")
```

**Handle roadmapper return:**

**If the roadmapper agent fails to spawn or returns an error:** Check if ROADMAP.md was partially written (the agent writes files first). If ROADMAP.md exists, verify it has phases and offer to proceed with it. If no ROADMAP.md exists, offer: 1) Retry the roadmapper, 2) Create ROADMAP.md in the main context using PROJECT.md and REQUIREMENTS.md. Do not leave the project in a state with REQUIREMENTS.md but no ROADMAP.md. **Also check if STATE.md exists** — the roadmapper creates both. If STATE.md is missing, create a minimal STATE.md (using the template from Step M5 in the minimal mode section above) so that downstream commands (`convention set`, `state validate`, etc.) can function.

**If `## ROADMAP BLOCKED`:**

- Present blocker information
- Work with user to resolve
- Re-spawn when resolved

**If `## ROADMAP CREATED`:**

Read the created ROADMAP.md and present it nicely inline:

```
---

## Proposed Research Roadmap

**[N] phases** | **[X] requirements mapped** | All requirements covered

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|------------|------------------|
| 1 | [Name] | [Goal] | [REQ-IDs] | [count] |
| 2 | [Name] | [Goal] | [REQ-IDs] | [count] |
| 3 | [Name] | [Goal] | [REQ-IDs] | [count] |
...

### Phase Details

**Phase 1: [Name]**
Goal: [goal]
Requirements: [REQ-IDs]
Success criteria:
1. [criterion]
2. [criterion]
3. [criterion]

**Phase 2: [Name]**
Goal: [goal]
Requirements: [REQ-IDs]
Success criteria:
1. [criterion]
2. [criterion]

[... continue for all phases ...]

---
```

**If auto mode:** Skip approval gate — auto-approve and commit directly.

**CRITICAL: Ask for approval before committing (interactive mode only):**

Use ask_user:

- header: "Roadmap"
- question: "Does this research roadmap structure work for you?"
- options:
  - "Approve" — Commit and continue
  - "Adjust phases" — Tell me what to change
  - "Review full file" — Show raw ROADMAP.md

**If "Approve":** Continue to commit.

**If "Adjust phases":**

- Get user's adjustment notes
- Re-spawn roadmapper with revision context:

  ```
  task(prompt="First, read {GPD_AGENTS_DIR}/gpd-roadmapper.md for your role and instructions.

  <revision>
  User feedback on roadmap:
  [user's notes]

  Read `.gpd/ROADMAP.md` for the current roadmap.

  Update the roadmap based on feedback. Edit files in place.
  Return ROADMAP REVISED with changes made.
  </revision>
  ", subagent_type="gpd-roadmapper", model="{roadmapper_model}", description="Revise roadmap")
  ```

  **If the revision roadmapper agent fails to spawn or returns an error:** Check if ROADMAP.md was updated (compare with pre-revision content). If changes were made, proceed to present the revised roadmap. If no changes, offer: 1) Retry the revision agent, 2) Apply the user's adjustment notes manually in the main context by editing ROADMAP.md directly.

- Present revised roadmap
- Loop until user approves (**maximum 3 revision iterations** — after 3, commit the current version with user's notes recorded as open questions in ROADMAP.md, and note: "Roadmap committed after 3 revision rounds. Further adjustments via `/gpd:add-phase` or `/gpd:remove-phase`.")

**If "Review full file":** Display raw `cat .gpd/ROADMAP.md`, then re-ask.

**Commit roadmap (after approval or auto mode):**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: create research roadmap ([N] phases)" --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/REQUIREMENTS.md
```

**Checkpoint step 8:**

```bash
cat > .gpd/init-progress.json << CHECKPOINT
{"step": 8, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "ROADMAP.md created and committed"}
CHECKPOINT
```

## 8.5. Establish Conventions

**After roadmap is committed, spawn gpd-notation-coordinator to establish notation conventions.**

This step is critical for multi-phase projects where convention mismatches cause silent errors (wrong signs, factors of 2*pi, metric signature confusion).

**If auto mode:** Auto-approve subfield defaults without user confirmation.

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> ESTABLISHING CONVENTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>>> Spawning notation coordinator...
```

```bash
NOTATION_MODEL=$(gpd resolve-model gpd-notation-coordinator --raw)
```

Spawn gpd-notation-coordinator:

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-notation-coordinator.md for your role and instructions.

<task>
Establish initial conventions for this research project.
</task>

<project_context>
Read these files:
- .gpd/PROJECT.md — Project definition, physics subfield, theoretical framework
- .gpd/ROADMAP.md — Phase structure (what conventions will be needed)
- .gpd/REQUIREMENTS.md — Research requirements
- .gpd/research/SUMMARY.md — Literature survey (if exists)
</project_context>

<mode>
{auto | interactive}
Auto mode: Use subfield defaults, lock all, skip user confirmation.
Interactive mode: Present suggested conventions, wait for user confirmation/override.
</mode>

<output>
1. Create: .gpd/CONVENTIONS.md (full convention reference)
2. Lock conventions via: gpd convention set
3. Return CONVENTIONS ESTABLISHED with summary
</output>
", subagent_type="gpd-notation-coordinator", model="{notation_model}", description="Establish project conventions")
```

**Handle notation-coordinator return:**

**If the notation-coordinator agent fails to spawn or returns an error:** Conventions are not critical for project initialization to succeed, BUT the convention_lock in state.json must be populated for downstream defense layers (L1-L4) to function. Fallback:

1. Create a minimal CONVENTIONS.md with the project's unit system and metric signature from PROJECT.md (if specified)
2. **Populate the convention_lock** with at minimum the unit system and metric signature:

   ```bash
   # Populate convention_lock so downstream L1-L4 defense layers are active
   gpd convention set natural_units "natural" 2>/dev/null || true
   gpd convention set metric_signature "mostly_minus" 2>/dev/null || true
   ```

   Adjust values based on what PROJECT.md specifies. If PROJECT.md doesn't specify conventions, use the subfield defaults from `{GPD_INSTALL_DIR}/references/subfield-convention-defaults.md`.

3. Note that full convention establishment was skipped. The user can run `/gpd:settings` or `/gpd:validate-conventions` later to complete convention setup.

- **`CONVENTIONS ESTABLISHED`:** Display confirmation with convention summary. Commit CONVENTIONS.md:

  ```bash
  PRE_CHECK=$(gpd pre-commit-check --files .gpd/CONVENTIONS.md 2>&1) || true
  echo "$PRE_CHECK"

  gpd commit "docs: establish notation conventions" --files .gpd/CONVENTIONS.md
  ```

- **`CONVENTION CONFLICT`:** Display conflicts. Ask user to resolve before proceeding.

**Checkpoint step 8.5:**

```bash
cat > .gpd/init-progress.json << CHECKPOINT
{"step": 8.5, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "Conventions established and committed"}
CHECKPOINT
```

## 9. Done

**Delete init-progress.json — initialization is complete:**

```bash
rm -f .gpd/init-progress.json
```

Present completion with next steps:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> RESEARCH PROJECT INITIALIZED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**[Project Name]**

| Artifact       | Location                    |
|----------------|-----------------------------|
| Project        | `.gpd/PROJECT.md`      |
| Config         | `.gpd/config.json`     |
| Literature     | `.gpd/research/`       |
| Requirements   | `.gpd/REQUIREMENTS.md` |
| Roadmap        | `.gpd/ROADMAP.md`      |
| Conventions    | `.gpd/CONVENTIONS.md`  |

**[N] phases** | **[X] requirements** | Ready to investigate

---------------------------------------------------------------

## >> Next Up

**Phase 1: [Phase Name]** — [Goal from ROADMAP.md]

/gpd:discuss-phase 1 — gather context and clarify approach

<sub>/clear first -> fresh context window</sub>

---

**Also available:**
- /gpd:plan-phase 1 — skip discussion, plan directly

---------------------------------------------------------------
```

</process>

<output>

- `.gpd/PROJECT.md`
- `.gpd/config.json`
- `.gpd/research/` (if literature survey selected)
  - `PRIOR-WORK.md`
  - `METHODS.md`
  - `COMPUTATIONAL.md`
  - `PITFALLS.md`
  - `SUMMARY.md`
- `.gpd/REQUIREMENTS.md`
- `.gpd/ROADMAP.md`
- `.gpd/STATE.md`
- `.gpd/CONVENTIONS.md` (established by gpd-notation-coordinator)

</output>

<success_criteria>

- [ ] .gpd/ directory created
- [ ] Git repo initialized
- [ ] Existing work detection completed
- [ ] Deep questioning completed (threads followed, not rushed)
- [ ] PROJECT.md captures full research context — **committed**
- [ ] config.json has workflow mode, depth, parallelization — **committed**
- [ ] Literature survey completed (if selected) — 4 parallel agents spawned — **committed**
- [ ] Research requirements gathered (from survey or conversation)
- [ ] User scoped each category (current/future/out of scope)
- [ ] REQUIREMENTS.md created with REQ-IDs — **committed**
- [ ] gpd-roadmapper spawned with context
- [ ] Roadmap files written immediately (not draft)
- [ ] User feedback incorporated (if any)
- [ ] ROADMAP.md created with phases, requirement mappings, success criteria
- [ ] STATE.md initialized
- [ ] REQUIREMENTS.md traceability updated
- [ ] gpd-notation-coordinator spawned to establish conventions
- [ ] CONVENTIONS.md created with subfield-appropriate conventions — **committed**
- [ ] Convention lock populated via `gpd convention set`
- [ ] User knows next step is `/gpd:discuss-phase 1`

**Atomic commits:** Each phase commits its artifacts immediately. If context is lost, artifacts persist.

</success_criteria>
