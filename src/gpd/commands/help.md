---
name: gpd:help
description: Show available GPD commands and usage guide
argument-hint: "[--all]"
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Display the complete GPD command reference.

Output ONLY the reference content below. Do NOT add:

- Project-specific analysis
- Git status or file context
- Next-step suggestions
- Any commentary beyond the reference
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/help.md
</execution_context>

<process>

## Step 1: Parse Arguments

Check if the user passed `--all` as an argument.

- If `$ARGUMENTS` contains `--all`: display the **Full Command Reference** (step 3).
- If `$ARGUMENTS` is empty or does not contain `--all`: display the **Quick Start** (step 2) only.

## Step 2: Quick Start (Default Output)

Output this and STOP (do not display the full reference):

# GPD Command Reference

**GPD** (Get Physics Done) — agentic physics research with AI research agents.

## Quick Start

1. `/gpd:new-project` — Initialize research project
2. `/gpd:plan-phase <N>` — Plan a research phase
3. `/gpd:execute-phase <N>` — Execute phase plans
4. `/gpd:verify-work [phase]` — Verify research results
5. `/gpd:progress` — Check status and get next action
6. `/gpd:complete-milestone` — Archive completed milestone
7. `/gpd:help --all` — Full command reference

**Workflow:** new-project → plan-phase → execute-phase → verify-work → repeat → complete-milestone

Run `/gpd:help --all` for all 58 commands.

--- END of default output. STOP here. ---

## Step 3: Full Command Reference (--all)

Output the complete GPD command reference from @{GPD_INSTALL_DIR}/workflows/help.md.
Display the reference content directly — no additions or modifications.

# GPD Command Reference

**GPD** (Get Physics Done) creates hierarchical research plans optimized for solo agentic physics research with AI research agents.

## Quick Start

1. `/gpd:new-project` - Initialize research project (includes literature survey, objectives, roadmap)
2. `/gpd:plan-phase 1` - Create detailed plan for first phase
3. `/gpd:execute-phase 1` - Execute the phase

## Core Workflow

```
/gpd:new-project -> /gpd:plan-phase -> /gpd:execute-phase -> repeat
```

### Project Initialization

**`/gpd:new-project`**
Initialize new research project through unified flow.

One command takes you from research idea to ready-for-investigation:

- Deep questioning to understand the physics problem
- Optional literature survey (spawns 4 parallel scout agents)
- Research objectives definition with scoping
- Roadmap creation with phase breakdown and success criteria

Creates all `.gpd/` artifacts:

- `PROJECT.md` — research question, theoretical framework, key parameters
- `config.json` — workflow settings (`autonomy`, `research_mode`, agent toggles)
- `research/` — literature survey (if selected)
- `REQUIREMENTS.md` — scoped research requirements with REQ-IDs
- `ROADMAP.md` — phases mapped to requirements
- `STATE.md` — project memory

**Flags:**

- `--minimal` — Skip deep questioning and literature survey. Creates project from a single description. Asks one question ("Describe your research project and phases"), then generates all `.gpd/` artifacts with sensible defaults. Same file set as full mode, so all downstream commands work identically.
- `--minimal @file.md` — Create project directly from a markdown file describing your research and phases. Parses research question, phase list, and key parameters from the file. No interactive questions asked.
- `--auto` — Automatic mode with full depth. Expects research proposal via @ reference. Runs literature survey, requirements, and roadmap without interaction.

Usage: `/gpd:new-project`
Usage: `/gpd:new-project --minimal`
Usage: `/gpd:new-project --minimal @plan.md`

**`/gpd:map-theory`**
Map an existing research project — theoretical framework, computations, conventions, and open questions.

- Spawns 4 parallel theory-mapper agents to analyze project artifacts
- Creates `.gpd/research-map/` with 7 structured documents
- Covers formalism, references, computational architecture, structure, conventions, validation, concerns
- Use before `/gpd:new-project` on existing research projects

Usage: `/gpd:map-theory`

### Phase Planning

**`/gpd:discuss-phase <number>`**
Help articulate your vision for a research phase before planning.

- Captures how you imagine this phase proceeding
- Creates CONTEXT.md with your approach, essentials, and boundaries
- Use when you have specific ideas about methods or approximations

Usage: `/gpd:discuss-phase 2`

**`/gpd:research-phase <number>`**
Comprehensive literature survey for a specific phase.

- Discovers known results, standard methods, available data
- Creates {phase}-RESEARCH.md with domain expert knowledge
- Use for phases involving unfamiliar techniques or contested results
- Goes beyond "which method" to deep domain knowledge

Usage: `/gpd:research-phase 3`

**`/gpd:list-phase-assumptions <number>`**
See what the agent plans to do before it starts.

- Shows the agent's intended approach for a phase
- Lets you course-correct if the approach is wrong
- No files created - conversational output only

Usage: `/gpd:list-phase-assumptions 3`

**`/gpd:discover <phase> [--depth quick|medium|deep]`**
Run discovery phase to investigate methods, literature, and approaches before planning.

- Surveys known results, standard methods, and computational tools
- Depth levels: quick (summary), medium (detailed), deep (comprehensive)
- Creates discovery artifacts consumed by planner
- Use when entering an unfamiliar subfield or technique

Usage: `/gpd:discover 3`
Usage: `/gpd:discover 3 --depth deep`

**`/gpd:show-phase <number>`**
Inspect a single phase's artifacts, status, and results.

- Shows phase goal, plans, summaries, and verification status
- Displays frontmatter metadata (wave, dependencies, status)
- Quick way to review what a phase produced

Usage: `/gpd:show-phase 3`

**`/gpd:plan-phase <number>`**
Create detailed execution plan for a specific phase.

- Generates `.gpd/phases/XX-phase-name/XX-YY-PLAN.md`
- Breaks phase into concrete, actionable steps
- Includes verification criteria (limiting cases, consistency checks)
- Multiple plans per phase supported (XX-01, XX-02, etc.)

**Flags:**

- `--research` — Force literature research even if RESEARCH.md already exists
- `--skip-research` — Skip literature research entirely
- `--gaps` — Gap closure mode: plan from VERIFICATION.md issues instead of fresh research
- `--skip-verify` — Skip plan checker verification after planning
- `--light` — Produce simplified strategic outline (must_haves, constraints, high-level approach only)
- `--inline-discuss` — Run discuss-phase inline before planning (skip if already done)

Usage: `/gpd:plan-phase 1`
Usage: `/gpd:plan-phase 3 --research`
Usage: `/gpd:plan-phase 5 --light --skip-verify`
Result: Creates `.gpd/phases/01-framework-setup/01-01-PLAN.md`

### Execution

**`/gpd:execute-phase <phase-number>`**
Execute all plans in a phase.

- Groups plans by wave (from frontmatter), executes waves sequentially
- Plans within each wave run in parallel via task tool
- Verifies phase goal after all plans complete (limiting cases, dimensional analysis, benchmarks)
- Updates REQUIREMENTS.md, ROADMAP.md, STATE.md

Usage: `/gpd:execute-phase 5`

### Derivation

**`/gpd:derive-equation`**
Perform a rigorous physics derivation with systematic verification at each step.

- States assumptions explicitly, establishes notation and conventions
- Performs step-by-step derivation with dimensional analysis at each stage
- Verifies intermediate results against known limits and symmetry properties
- Justifies and bounds all approximations with error estimates
- Produces a complete, self-contained derivation document with boxed final result

Usage: `/gpd:derive-equation`

### Quick Mode

**`/gpd:quick`**
Execute small, ad-hoc calculations with GPD guarantees but skip optional agents.

Quick mode uses the same system with a shorter path:

- Spawns planner + executor (skips literature scout, checker, validator)
- Quick tasks live in `.gpd/quick/` separate from planned phases
- Updates STATE.md tracking (not ROADMAP.md)

Use when you know exactly what to calculate and the task is small enough to not need literature survey or validation.

Usage: `/gpd:quick`
Result: Creates `.gpd/quick/NNN-slug/PLAN.md`, `.gpd/quick/NNN-slug/SUMMARY.md`

### Roadmap Management

**`/gpd:add-phase <description>`**
Add new phase to end of current milestone.

- Appends to ROADMAP.md
- Uses next sequential number
- Updates phase directory structure

Usage: `/gpd:add-phase "Compute finite-temperature corrections"`

**`/gpd:insert-phase <after> <description>`**
Insert urgent work as decimal phase between existing phases.

- Creates intermediate phase (e.g., 7.1 between 7 and 8)
- Useful for discovered work that must happen mid-investigation
- Maintains phase ordering

Usage: `/gpd:insert-phase 7 "Fix sign error in vertex function"`
Result: Creates Phase 7.1

**`/gpd:remove-phase <number>`**
Remove a future phase and renumber subsequent phases.

- Deletes phase directory and all references
- Renumbers all subsequent phases to close the gap
- Only works on future (unstarted) phases
- Git commit preserves historical record

Usage: `/gpd:remove-phase 17`
Result: Phase 17 deleted, phases 18-20 become 17-19

**`/gpd:revise-phase <number> "<reason>"`**
Supersede a completed phase and create a replacement for iterative revision.

- Marks original phase as superseded (preserved as historical record)
- Creates replacement phase with decimal numbering (e.g., 3.1)
- Pre-populates replacement with context: what worked, what didn't, what to change
- Updates downstream dependency references
- Flags downstream phases that may also need revision
- Only works on completed phases (use /gpd:remove-phase for future phases)

Usage: `/gpd:revise-phase 3 "Sign error in vertex correction"`
Result: Phase 3 superseded, Phase 3.1 created with inherited context

**`/gpd:merge-phases <source> <target>`**
Merge results from one phase into another.

- Copies artifacts (summaries, plans, data files) from source to target
- Merges intermediate results and decisions with phase attribution
- Updates roadmap to reflect the merge
- Useful for folding decimal phases back into parents or converging parallel branches

Usage: `/gpd:merge-phases 2.1 2`

### Milestone Management

**`/gpd:new-milestone <name>`**
Start a new research milestone through unified flow.

- Deep questioning to understand the next research direction
- Optional literature survey (spawns 4 parallel scout agents)
- Objectives definition with scoping
- Roadmap creation with phase breakdown

Mirrors `/gpd:new-project` flow for continuation projects (existing PROJECT.md).

Usage: `/gpd:new-milestone "v2.0 Higher-order corrections"`

**`/gpd:complete-milestone <version>`**
Archive completed milestone and prepare for next direction.

- Creates MILESTONES.md entry with results summary
- Archives full details to milestones/ directory
- Creates git tag for the release
- Prepares workspace for next research direction

Usage: `/gpd:complete-milestone 1.0.0`

### Progress Tracking

**`/gpd:progress`**
Check research status and intelligently route to next action.

- Shows visual progress bar and completion percentage
- Summarizes recent work from SUMMARY files
- Displays current position and what's next
- Lists key results and open issues
- Offers to execute next plan or create it if missing
- Detects 100% milestone completion

Usage: `/gpd:progress`
Usage: `/gpd:progress --full` (detailed view with all phase artifacts)
Usage: `/gpd:progress --brief` (compact one-line status)
Usage: `/gpd:progress --reconcile` (fix diverged STATE.md and state.json)

**`/gpd:suggest-next`**
Suggest the most impactful next action based on current project state.

- Scans phases, plans, verification status, blockers, and todos
- Produces a prioritized action list
- Fastest way to answer "what should I do next?" without reading through progress reports

Usage: `/gpd:suggest-next`

### Session Management

**`/gpd:resume-work`**
Resume research from previous session with full context restoration.

- Reads STATE.md for project context
- Shows current position and recent progress
- Offers next actions based on project state

Usage: `/gpd:resume-work`

**`/gpd:pause-work`**
Create context handoff when pausing work mid-phase.

- Creates .continue-here file with current state
- Updates STATE.md session continuity section
- Captures in-progress work context

Usage: `/gpd:pause-work`

### Todo Management

**`/gpd:add-todo [description]`**
Capture idea or task as todo from current conversation.

- Extracts context from conversation (or uses provided description)
- Creates structured todo file in `.gpd/todos/pending/`
- Infers area from context for grouping
- Checks for duplicates before creating
- Updates STATE.md todo count

Usage: `/gpd:add-todo` (infers from conversation)
Usage: `/gpd:add-todo Check if vertex correction satisfies Ward identity`

**`/gpd:check-todos [area]`**
List pending todos and select one to work on.

- Lists all pending todos with title, area, age
- Optional area filter (e.g., `/gpd:check-todos numerical`)
- Loads full context for selected todo
- Routes to appropriate action (work now, add to phase, think more)
- Moves todo to done/ when work begins

Usage: `/gpd:check-todos`
Usage: `/gpd:check-todos analytical`

### Validation

**`/gpd:verify-work [phase]`**
Validate research results through systematic checks.

- Extracts testable results from SUMMARY.md files
- Checks limiting cases, dimensional analysis, conservation laws
- Compares against known benchmarks
- Automatically diagnoses failures and creates fix plans
- Ready for re-execution if issues found

Usage: `/gpd:verify-work 3`

### Debugging

**`/gpd:debug [issue description]`**
Systematic debugging of physics calculations with persistent state across context resets.

- Spawns gpd-debugger agent with scientific method approach
- Maintains debug session state in `.gpd/debug/`
- Survives context window resets — resumes from last checkpoint
- Archives resolved issues to `.gpd/debug/resolved/`

Usage: `/gpd:debug Sign error in self-energy diagram`

### Physics Validation

**`/gpd:dimensional-analysis`**
Check dimensional consistency of equations and expressions.

- Verifies all terms have consistent units
- Checks final results have correct dimensions
- Flags dimensionless ratios and magic numbers

Usage: `/gpd:dimensional-analysis`

**`/gpd:limiting-cases`**
Verify results reduce correctly in known limiting cases.

- Tests classical, non-relativistic, weak-coupling, thermodynamic limits
- Compares against textbook expressions in each limit
- Flags limits that are not recovered

Usage: `/gpd:limiting-cases`

**`/gpd:numerical-convergence`**
Run systematic convergence tests on numerical computations.

- Tests convergence with grid refinement, time step, basis size
- Estimates convergence order via Richardson extrapolation
- Constructs error budgets for computed quantities

Usage: `/gpd:numerical-convergence`

**`/gpd:compare-experiment`**
Compare theoretical/numerical results against experimental data.

- Loads published experimental values and error bars
- Computes chi-squared or other goodness-of-fit measures
- Identifies systematic deviations and their possible origins

Usage: `/gpd:compare-experiment`

**`/gpd:validate-conventions [phase]`**
Validate convention consistency across all phases.

- Checks metric signature, Fourier convention, natural units, gauge choice
- Detects convention drift where a symbol is redefined in a later phase
- Cross-checks locked conventions against all phase artifacts
- Scope to a single phase or run across all phases

Usage: `/gpd:validate-conventions`
Usage: `/gpd:validate-conventions 3`

**`/gpd:regression-check [phase]`**
Re-verify all previously verified truths to catch regressions after changes.

- Extracts verified results from VERIFICATION.md files
- Re-runs dimensional analysis, limiting cases, and numerical checks
- Reports any results that no longer hold
- Scope to a single phase or run across all phases

Usage: `/gpd:regression-check`
Usage: `/gpd:regression-check 3`

### Quantitative Analysis

**`/gpd:parameter-sweep [phase]`**
Systematic parameter sweep with parallel execution and result aggregation.

- Varies one or more parameters across a specified range
- Uses wave-based parallelism for independent parameter values
- Collects results and produces summary tables
- Supports adaptive refinement near interesting features

Usage: `/gpd:parameter-sweep 3 --param coupling --range 0:1:20`
Usage: `/gpd:parameter-sweep 3 --adaptive`

**`/gpd:sensitivity-analysis`**
Determine which input parameters most strongly affect output quantities.

- Computes partial derivatives and condition numbers
- Ranks parameters by sensitivity
- Identifies which measurements or calculations would most improve results
- Supports analytical and numerical methods

Usage: `/gpd:sensitivity-analysis --target cross_section --params g,m,Lambda`
Usage: `/gpd:sensitivity-analysis --method numerical`

**`/gpd:error-propagation`**
Track how uncertainties propagate through multi-step calculations.

- Traces input uncertainties through intermediate results to final quantities
- Identifies dominant error sources
- Produces error budgets
- Scope to specific phases or full derivation chain

Usage: `/gpd:error-propagation --target final_mass`
Usage: `/gpd:error-propagation --phase-range 1:5`

### Research Publishing

**`/gpd:write-paper [title or topic] [--from-phases 1,2,3]`**
Structure and write a physics paper from research results.

- Loads research digest from milestone completion (if available)
- Runs paper-readiness audit (conventions, verification, figures, citations)
- Spawns gpd-paper-writer agents for each section (Results first, Abstract last)
- Generates LaTeX with proper equations, figures, and citations
- Spawns gpd-bibliographer to verify all references
- Spawns gpd-referee for pre-submission mock peer review
- Supports revision mode for referee responses (bounded 3-iteration loop)

Usage: `/gpd:write-paper "Critical exponents via RG"`
Usage: `/gpd:write-paper --from-phases 1,3,5` (subset of phases)

**`/gpd:respond-to-referees`**
Structure point-by-point response to referee reports and revise the manuscript.

- Parses referee comments into structured items with severity levels
- Drafts AUTHOR-RESPONSE.md with REF-xxx issue tracking (fixed/rebutted/acknowledged)
- Spawns paper-writer agents for targeted section revisions
- Tracks new calculations required by referees as revision tasks
- Produces response letter from `templates/paper/referee-response.md`
- Bounded revision loop (max 3 iterations with re-review)

Usage: `/gpd:respond-to-referees`

**`/gpd:arxiv-submission`**
Prepare a completed paper for arXiv submission with validation and packaging.

- LaTeX validation and compilation check
- Bibliography flattening (inline .bbl or resolve .bib)
- Figure format and resolution checking
- `\input` resolution into single .tex file (optional)
- Metadata verification (title, authors, abstract)
- Ancillary file packaging
- Generates submission-ready `.tar.gz`
- Produces checklist of remaining manual steps

Usage: `/gpd:arxiv-submission`

**`/gpd:literature-review [topic]`**
Structured literature review for a physics research topic.

- Citation network analysis and open question identification
- Spawns gpd-literature-reviewer agent
- Creates structured review with key papers, methods, and gaps
- Spawns gpd-bibliographer to verify citations

Usage: `/gpd:literature-review "Sachdev-Ye-Kitaev model thermodynamics"`

### Hypothesis Branches

**`/gpd:branch-hypothesis <description>`**
Create a hypothesis branch for parallel investigation of an alternative approach.

- Creates git branch with isolated `.gpd/` state
- Allows exploring alternative methods without disrupting main line
- Use when two valid approaches exist and you want to compare

Usage: `/gpd:branch-hypothesis "Try perturbative RG instead of exact RG"`

**`/gpd:compare-branches`**
Compare results across hypothesis branches side-by-side.

- Reads SUMMARY.md and VERIFICATION.md from each branch
- Shows which approach produced better results
- Helps decide which branch to merge back

Usage: `/gpd:compare-branches`

### Decision Tracking

**`/gpd:decisions [phase or keyword]`**
Display and search the cumulative decision log.

- Shows all recorded decisions across phases
- Filter by phase number or keyword
- Tracks sign conventions, approximation choices, gauge choices
- Reads from `.gpd/DECISIONS.md`

Usage: `/gpd:decisions`
Usage: `/gpd:decisions 3`
Usage: `/gpd:decisions "gauge"`

### Visualization & Export

**`/gpd:graph`**
Visualize dependency graph across phases and identify gaps.

- Builds Mermaid diagram from phase frontmatter (provides/requires/affects)
- Identifies gaps where a phase requires something no other phase provides
- Computes critical path through the research project

Usage: `/gpd:graph`

![1773117521686](image/help/1773117521686.png)![1773117527461](image/help/1773117527461.png)> **Note:** Wave dependency validation runs automatically when executing phases. To validate manually, use `gpd phase validate-waves <phase>` — checks depends_on targets, file overlap within waves, wave consistency, and circular dependencies.

**`/gpd:export [--format html|latex|zip|all]`**
Export research results to HTML, LaTeX, or ZIP package.

- HTML: standalone page with MathJax rendering
- LaTeX: document with proper equations and bibliography
- ZIP: complete archive of all planning artifacts

Usage: `/gpd:export --format html`
Usage: `/gpd:export --format all`

**`/gpd:estimate-cost [phase|remaining|all]`**
Estimate token usage and API cost for phases.

- Per-phase and per-agent-type token breakdown
- Uses 3-tier model cost data (tier-1/tier-2/tier-3)
- Accounts for current model profile setting

Usage: `/gpd:estimate-cost 3`
Usage: `/gpd:estimate-cost remaining`

**`/gpd:error-patterns [category]`**
View accumulated physics error patterns for this project.

- Shows common mistakes discovered during debugging and verification
- Optional category filter (sign, dimension, approximation, etc.)
- Helps avoid repeating known pitfalls

Usage: `/gpd:error-patterns`
Usage: `/gpd:error-patterns sign`

**`/gpd:record-insight [description]`**
Record a project-specific learning or pattern to the insights ledger.

- Records error patterns, convention pitfalls, verification lessons
- Checks for duplicates before adding
- Categorizes into appropriate section (Debugging Patterns, Verification Lessons, etc.)
- Updates `.gpd/INSIGHTS.md`

Usage: `/gpd:record-insight`
Usage: `/gpd:record-insight Sign error in Wick contractions with mostly-minus metric`

### Milestone Auditing

**`/gpd:audit-milestone [version]`**
Audit milestone completion against original objectives.

- Reads all phase VERIFICATION.md files
- Checks objectives coverage
- Spawns cross-check agent for consistency between phases
- Creates MILESTONE-AUDIT.md with gaps and open questions

Usage: `/gpd:audit-milestone`

**`/gpd:plan-milestone-gaps`**
Create phases to close gaps identified by audit.

- Reads MILESTONE-AUDIT.md and groups gaps into phases
- Prioritizes by objective priority
- Adds gap closure phases to ROADMAP.md
- Ready for `/gpd:plan-phase` on new phases

Usage: `/gpd:plan-milestone-gaps`

### Configuration

**`/gpd:settings`**
Configure workflow toggles and model profile interactively.

- Toggle literature scout, plan checker, verification verifier agents
- Configure inter-wave verification gates (auto/always/never)
- Toggle parallel execution of wave plans
- Select model profile (deep-theory/numerical/exploratory/review/paper-writing)
- Updates `.gpd/config.json`

Usage: `/gpd:settings`

**`/gpd:set-profile <profile>`**
Quick switch model profile for GPD agents.

- `deep-theory` — tier-1 (highest capability) for all reasoning-intensive agents (formal derivations, proofs)
- `numerical` — tier-1 for planning/verification, tier-2 for execution (simulations, numerics)
- `exploratory` — tier-1 for planner/researchers, tier-2 for execution (hypothesis generation)
- `review` (default) — tier-1 for verifier/checker/debugger, tier-2 for execution (validation focus)
- `paper-writing` — tier-1 for planner/executor/synthesizer, tier-2 for verification

Usage: `/gpd:set-profile deep-theory`

### Utility Commands

**`/gpd:compact-state`**
Archive historical entries from STATE.md to keep it lean.

- Moves old decisions, metrics, and resolved blockers to STATE-ARCHIVE.md
- Keeps STATE.md under the target line budget (~150 lines)
- Triggered automatically when STATE.md exceeds 1500 lines

Usage: `/gpd:compact-state`
Usage: `/gpd:compact-state --force` (skip line-count check)

**`/gpd:sync-state`**
Reconcile diverged STATE.md and state.json after manual edits or corruption.

- Detects mismatches between human-readable STATE.md and structured state.json
- Resolves by choosing the more recent or more complete source
- Fixes broken convention locks, missing phase counters, or stale progress bars
- Use after manual edits to STATE.md or after a crash during state updates

Usage: `/gpd:sync-state`

**`/gpd:undo`**
Rollback last GPD operation with safety checkpoint.

- Creates a safety tag before reverting so the undo itself is reversible
- Reverts only GPD-related commits (not arbitrary git history)
- Rejects merge commits — manual resolution required

Usage: `/gpd:undo`

**`/gpd:update`**
Update GPD to latest version with changelog display.

- Pulls latest GPD files from the repository
- Shows changelog of what changed since your version
- Preserves local modifications (use `/gpd:reapply-patches` after if needed)

Usage: `/gpd:update`

**`/gpd:reapply-patches`**
Reapply local modifications after a GPD update.

- Detects and replays customizations you made to GPD files
- Use after `/gpd:update` if you have local workflow or template modifications

Usage: `/gpd:reapply-patches`

**`/gpd:health`**
Run comprehensive project health checks.

- Validates state.json, STATE.md sync, convention locks, config.json, orphaned phases, ROADMAP.md consistency, missing plans, stale artifacts, and git status
- Use `--fix` to auto-repair detected issues

Usage: `/gpd:health`
Usage: `/gpd:health --fix`

**`/gpd:help`**
Show this command reference.

## Files & Structure

```
.gpd/
|-- PROJECT.md            # Research question, framework, parameters
|-- REQUIREMENTS.md       # Scoped research requirements with REQ-IDs
|-- ROADMAP.md            # Current phase breakdown
|-- STATE.md              # Project memory & context
|-- MILESTONES.md         # Milestone history
|-- config.json           # Workflow mode & gates
|-- research/             # Literature survey results
|   |-- PRIOR-WORK.md     # Established results in the field
|   |-- METHODS.md        # Standard methods and tools
|   |-- COMPUTATIONAL.md  # Computational approaches and tools
|   |-- PITFALLS.md       # Known pitfalls and open problems
|   +-- SUMMARY.md        # Synthesized survey
|-- research-map/         # Theory map (existing research projects)
|   |-- FORMALISM.md      # Mathematical framework and key equations
|   |-- REFERENCES.md     # Key papers and their relationships
|   |-- ARCHITECTURE.md   # Computation flow and methodology
|   |-- STRUCTURE.md      # Project layout, key files
|   |-- CONVENTIONS.md    # Notation standards, unit systems
|   |-- VALIDATION.md     # Known results for benchmarking
|   +-- CONCERNS.md       # Open questions, known issues
|-- todos/                # Captured ideas and research tasks
|   |-- pending/          # Todos waiting to be worked on
|   +-- done/             # Completed todos
|-- debug/                # Active debug sessions
|   +-- resolved/         # Archived resolved issues
|-- quick/                # Ad-hoc task plans and summaries
|-- milestones/           # Archived milestone data
+-- phases/
    |-- 01-analytical-setup/
    |   |-- 01-01-PLAN.md
    |   |-- 01-01-SUMMARY.md
    |   +-- 01-VERIFICATION.md
    +-- 02-numerical-validation/
        |-- 02-01-PLAN.md
        +-- 02-01-SUMMARY.md
```

## Workflow Modes

Set during `/gpd:new-project`:

**Interactive Mode**

- Confirms each major decision
- Pauses at checkpoints for approval
- More guidance throughout

**YOLO Mode**

- Auto-approves most decisions
- Executes plans without confirmation
- Only stops for critical checkpoints (e.g., sign convention choices)

Change anytime by editing `.gpd/config.json`

## Planning Configuration

Configure how planning artifacts are managed in `.gpd/config.json`:

**`planning.commit_docs`** (default: `true`)

- `true`: Planning artifacts committed to git (standard workflow)
- `false`: Planning artifacts kept local-only, not committed

When `commit_docs: false`:

- Add `.gpd/` to your `.gitignore`
- Useful for collaborative projects, shared repos, or keeping planning private
- All planning files still work normally, just not tracked in git

**`planning.search_gitignored`** (default: `false`)

- `true`: Add `--no-ignore` to broad ripgrep searches
- Only needed when `.gpd/` is gitignored and you want project-wide searches to include it

Example config:

```json
{
  "planning": {
    "commit_docs": false,
    "search_gitignored": true
  }
}
```

## Common Workflows

**Starting a new research project:**

```
/gpd:new-project        # Unified flow: questioning -> survey -> objectives -> roadmap
/clear
/gpd:plan-phase 1       # Create plans for first phase
/clear
/gpd:execute-phase 1    # Execute all plans in phase
```

**Fast project bootstrap (skip deep questioning):**

```
/gpd:new-project --minimal              # One question, then auto-generate everything
/gpd:new-project --minimal @plan.md     # Generate from existing research plan file
```

**Resuming work after a break:**

```
/gpd:progress  # See where you left off and continue
```

**Adding urgent mid-milestone work:**

```
/gpd:insert-phase 5 "Fix sign error in renormalization group equation"
/gpd:plan-phase 5.1
/gpd:execute-phase 5.1
```

**Completing a milestone:**

```
/gpd:complete-milestone 1.0.0
/clear
/gpd:new-milestone  # Start next milestone (questioning -> survey -> objectives -> roadmap)
```

**Capturing ideas during work:**

```
/gpd:add-todo                                      # Capture from conversation context
/gpd:add-todo Check finite-size scaling exponent    # Capture with explicit description
/gpd:check-todos                                    # Review and work on todos
/gpd:check-todos numerical                          # Filter by area
```

## Getting Help

- Read `.gpd/PROJECT.md` for research question and framework
- Read `.gpd/STATE.md` for current context and key results
- Check `.gpd/ROADMAP.md` for phase status
- Run `/gpd:progress` to check where you are
  </process>
