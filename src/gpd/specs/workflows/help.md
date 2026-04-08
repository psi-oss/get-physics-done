<purpose>
Display the complete GPD command reference. Output ONLY the reference content. Do NOT add project-specific analysis, git status, next-step suggestions, or any commentary beyond the reference.
</purpose>

<process>

<step name="contextual_help">
## Contextual Help (State-Aware Variant)

When a state-aware help view is requested, show only the commands relevant to the current project state:

**No project exists:**
```
Getting started:
  gpd:start               — Guided router for create, map, resume, or explain decisions
  gpd:tour               — Read-only guided tour of the main commands
  gpd:new-project         — Start a new research project with full scoping
  gpd:new-project --minimal — Faster one-question project bootstrap
  gpd:map-research        — Map an existing research project
```

**Project exists, paused or resumable:**
```
Returning to work:
  gpd resume             — Current-workspace read-only recovery snapshot from your normal terminal
  gpd resume --recent    — Find the workspace first when you need to reopen a different one
  gpd:resume-work         — Continue in-runtime from the selected project's canonical state
  gpd:progress            — Review the broader project snapshot
  gpd:suggest-next        — Fastest post-resume next command
  gpd observe execution    — Read-only live status from your normal terminal; use this for progress / waiting state, then follow its suggested read-only checks rather than runtime hotkeys
  gpd cost                 — Read-only machine-local usage / cost summary from your normal terminal
  gpd:tangent             — Choose stay / quick / defer / branch when a side investigation appears
```

**Project exists, no plans yet:**
```
Phase {N}: {name}
  gpd:discuss-phase {N}   — Gather context before planning
  gpd:plan-phase {N}      — Create execution plan
  gpd:progress --full     — See full project status
```

**Plans exist, not executed:**
```
Ready to execute:
  gpd:execute-phase {N}   — Execute phase {N} plans
  gpd:show-phase {N}      — Review phase details first
```

**Phase complete:**
```
Phase {N} complete:
  gpd:discuss-phase {N+1}  — Gather context before planning the next phase
  gpd:plan-phase {N+1}    — Create execution plan
  gpd:complete-milestone   — If all phases done
```

**Manuscript exists, no referee report yet:**
```
Publication workflow:
  gpd:peer-review         — Run manuscript peer review inside the current project
  gpd:arxiv-submission    — Package only after review passes and the paper-build contract succeeds
  gpd doctor --runtime <runtime> --local|--global — Check runtime-local paper-toolchain readiness for the paper/manuscript workflow preset. Add `--live-executable-probes` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`. Inspect the preset with `gpd presets list`, preview it with `gpd presets show <preset>`, and apply it from your normal terminal with `gpd presets apply <preset>` or through your runtime-specific settings command; failed preset rows degrade `write-paper`, but `paper-build` remains the build contract and `arxiv-submission` requires the built manuscript
  gpd integrations status wolfram — Inspect the shared optional Wolfram integration config only; this does not prove local Mathematica availability or plan readiness, and optional doctor probes do not change that
```

**Referee report exists:**
```
Revision workflow:
  gpd:respond-to-referees — Draft responses and revise the manuscript
  gpd:peer-review         — Re-run peer review after revision
```

For the compact command index: `gpd:help --all`
For one detailed command entry: `gpd:help --command gpd:plan-phase`
</step>

<step name="concepts">
## GPD Concepts

GPD organizes physics research into a clear hierarchy:

```
Project ─── the overall research goal
  └─ Milestone ─── a major research objective (e.g., "v1.0: derive and validate")
       └─ Phase ─── one investigation step (e.g., "Phase 3: Monte Carlo validation")
            └─ Plan ─── a concrete execution plan (e.g., "Plan 01: implement Metropolis")
                 └─ Task ─── an atomic work unit (e.g., "Task 2: run thermalization")
```

**Typical workflow:**
1. `gpd:new-project` — Define research question, survey literature, create roadmap
2. `gpd:discuss-phase N` — Clarify the phase before planning
3. `gpd:plan-phase N` — Create detailed plans for phase N
4. `gpd:execute-phase N` — Run all plans (derivations, simulations, analysis)
5. `gpd:verify-work` — Verify physics correctness
6. Repeat 2-5 for each phase
7. `gpd:write-paper` — Generate publication from results
8. `gpd:peer-review` — Run manuscript review before submission inside the current project
9. `gpd:respond-to-referees` — Address reviewer comments if needed
10. `gpd:arxiv-submission` — Package the approved manuscript

**Example:** Studying the 3D Ising critical exponent:
- Phase 1: Set up Wolff cluster MC algorithm
- Phase 2: Run simulations at multiple temperatures and system sizes
- Phase 3: Finite-size scaling analysis to extract nu
- Phase 4: Compare with known results, write paper
</step>

</process>

<reference>
# GPD Command Reference

**GPD** (Get Physics Done) creates hierarchical research plans optimized for solo agentic physics research with AI research agents.

## Startup Checklist

Use the shared onboarding surfaces in the README or installer output for the longer beginner-first startup order and prerequisites.

1. `gpd:help` - See the command reference first.
2. `gpd:start` - Let GPD choose the safest first step for the current folder.
3. `gpd:tour` - Get a read-only walkthrough before you choose.
4. `gpd:new-project` or `gpd:map-research` - Begin the actual work path once you know the folder state.
5. `gpd:resume-work` - Continue later from the selected project's canonical state.
6. `gpd:settings` - Change autonomy, permissions, or runtime preferences after your first successful start or later.
7. `gpd:set-tier-models` - Directly pin concrete `tier-1`, `tier-2`, and `tier-3` model ids for the active runtime.

## Invocation Surfaces

This reference lists the canonical in-runtime command names for the installed runtime's public command surface.
Depending on the runtime, those names may be rendered with slash prefixes, dollar prefixes, or another adapter-specific convention.

- If you are new to terminals or runtime setup, start with the Beginner Onboarding Hub linked from the README and installer output.
- That shared onboarding surface keeps the OS guides, runtime guides, and startup checklist in one place.
- Use these names inside the installed agent/runtime command surface.
- Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly.
- Use `gpd permissions status --runtime <runtime> --autonomy balanced` when you want the read-only runtime-owned approval/alignment snapshot from your normal terminal.
- Use `gpd doctor` to check the selected install target and runtime-local readiness signals. Use `gpd validate unattended-readiness --runtime <runtime> --autonomy balanced` for the unattended or overnight verdict, `gpd permissions sync --runtime <runtime> --autonomy balanced` when runtime-owned permissions need realignment, and `--live-executable-probes` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`.
- If you need to validate whether a public runtime command can run in the current workspace, use `gpd validate command-context gpd:<name>`.
- If a plan declares specialized `tool_requirements`, use `gpd validate plan-preflight <PLAN.md>` from your normal terminal before execution.
- For a normal-terminal, current-workspace read-only recovery snapshot without launching the runtime, use `gpd resume`.
- For cross-project discovery from your normal terminal, use `gpd resume --recent` to find the workspace first, then open the selected project and continue there with the runtime `resume-work` command.
- After resuming inside the runtime, use `gpd:suggest-next` when you only need the next action.
- For a normal-terminal, read-only machine-local usage / cost summary, use `gpd cost`.

## Quick Start

If you only remember one order, use this: `help -> start -> tour -> new-project / map-research -> resume-work`.
In runtime terms, that means `gpd:help`, then `gpd:start`, then `gpd:tour`, then `gpd:new-project` or `gpd:map-research`, and later `gpd:resume-work` when you return.

Use the path that matches your current situation:

**New work**
1. `gpd:start` - Guided first-run router that chooses the safest first step for this folder
2. `gpd:tour` - Get a read-only overview before choosing
3. `gpd:new-project` - Create a full GPD project
4. `gpd:new-project --minimal` - Create a project through the shortest setup path

**Existing work**
1. `gpd:map-research` - Map an existing folder before turning it into a GPD project
2. `gpd:new-project` - Turn that mapped context into a full GPD project

**Returning work**
1. `gpd resume` - Reopen the current-workspace recovery snapshot from your normal terminal
2. `gpd resume --recent` - Find a different workspace first from your normal terminal
3. `gpd:resume-work` - Continue inside the reopened project's canonical state
4. `gpd:progress` - See the broader project snapshot
5. `gpd:suggest-next` - Get the fastest next action
6. `gpd observe execution` - Watch progress / waiting state, conservative `possibly stalled` wording, and the next read-only checks from your normal terminal
7. `gpd cost` - Review recorded machine-local usage / cost from your normal terminal

**Post-startup settings**
1. `gpd:settings` - Change autonomy, permissions, and broader runtime preferences after your first successful start or later
2. `gpd:set-tier-models` - Pin concrete `tier-1`, `tier-2`, and `tier-3` model ids only

When a side investigation appears later, use `gpd:tangent` first. It is the chooser for stay / quick / defer / branch. Use `gpd:branch-hypothesis` only when that tangent needs its own git-backed branch.

## Command Index

This is the compact grouped list of runtime commands. For normal-terminal install, readiness, and diagnostics commands, use `gpd --help`.

### Starter commands

- `gpd:help` - Show the quick start or command index
- `gpd:start` - Guided first-run router for the safest first path in the current folder
- `gpd:tour` - Show a read-only overview of the main commands
- `gpd:new-project` - Create a full GPD project
- `gpd:new-project --minimal` - Create a GPD project through the shortest setup path
- `gpd:map-research` - Map an existing research folder before planning
- `gpd:resume-work` - Resume the selected project's canonical state inside the runtime
- `gpd:progress` - Review project status and likely next steps
- `gpd:suggest-next` - Ask only for the next best action
- `gpd:explain [concept]` - Explain a concept, method, result, or paper
- `gpd:quick` - Run one small bounded task without the full phase workflow

### Planning and execution

- `gpd:discuss-phase <number>` - Capture phase context before planning
- `gpd:research-phase <number>` - Run a focused phase literature survey
- `gpd:list-phase-assumptions <number>` - Preview the planned phase approach
- `gpd:discover [phase or topic]` - Survey methods, literature, and tools before planning
- `gpd:show-phase <number>` - Inspect one phase's artifacts and status
- `gpd:plan-phase <number>` - Build a detailed execution plan for a phase
- `gpd:execute-phase <phase-number>` - Run all plans in a phase
- `gpd:derive-equation` - Run a rigorous derivation workflow

### Roadmap and milestones

- `gpd:add-phase <description>` - Append a new phase to the roadmap
- `gpd:insert-phase <after> <description>` - Insert urgent work between phases
- `gpd:remove-phase <number>` - Remove a future phase and renumber later ones
- `gpd:revise-phase <number> "<reason>"` - Supersede a completed phase with a replacement
- `gpd:merge-phases <source> <target>` - Fold one phase's results into another
- `gpd:new-milestone <name>` - Start the next milestone
- `gpd:complete-milestone <version>` - Archive a completed milestone

### Validation and analysis

- `gpd:verify-work [phase]` - Run physics verification checks
- `gpd:debug [issue description]` - Start a persistent debug session
- `gpd:dimensional-analysis` - Check dimensional consistency
- `gpd:limiting-cases` - Check known limits
- `gpd:numerical-convergence` - Run convergence checks for numerical work
- `gpd:compare-experiment` - Compare results against external data
- `gpd:compare-results` - Compare internal results or baselines
- `gpd:validate-conventions [phase]` - Check notation and convention consistency
- `gpd:regression-check [phase]` - Scan for regressions in recorded verification state
- `gpd:health` - Run project health checks
- `gpd:parameter-sweep [phase]` - Run a structured parameter sweep
- `gpd:sensitivity-analysis` - Rank which inputs matter most
- `gpd:error-propagation` - Track uncertainties through a calculation chain

### Knowledge authoring

- `gpd:digest-knowledge [topic|arXiv id|source file|knowledge path]` - Create or update a draft knowledge doc from a topic, arXiv paper, source file, or explicit `GPD/knowledge/` path
- `gpd:review-knowledge [knowledge path|knowledge id]` - Review a knowledge doc, write the review artifact, and promote fresh approved drafts to stable

### Writing and publication

- `gpd:literature-review [topic]` - Create a structured literature review
- `gpd:write-paper [title or topic] [--from-phases 1,2,3]` - Draft a paper from project results
- `gpd:peer-review [paper directory or manuscript path]` - Run the staged review workflow
- `gpd:respond-to-referees` - Draft referee responses and revise the paper
- `gpd:arxiv-submission` - Package a built manuscript for arXiv
- `gpd:slides [topic, audience, or source path]` - Create presentation slides

### Tangents, memory, and exports

- `gpd:tangent [description]` - Chooser for stay / quick / defer / branch when a side investigation appears
- `gpd:branch-hypothesis <description>` - Explicit git-backed alternative path for a side investigation
- `gpd:compare-branches` - Compare results across hypothesis branches
- `gpd:pause-work` - Save a continuation handoff before stepping away
- `gpd:add-todo [description]` - Capture a task or idea
- `gpd:check-todos [area]` - Review pending todos and pick one
- `gpd:decisions [phase or keyword]` - Search the decision log
- `gpd:graph` - Visualize phase dependencies
- `gpd:export [--format html|latex|zip|all]` - Export project artifacts
- `gpd:export-logs [--format jsonl|json|markdown] [--session <id>] [--last N] [--no-traces] [--output-dir <path>]` - Export observability logs
- `gpd:error-patterns [category]` - Review common project-specific errors
- `gpd:record-insight [description]` - Save a project-specific lesson
- `gpd:audit-milestone [version]` - Audit milestone completion against goals
- `gpd:plan-milestone-gaps` - Turn audit gaps into new phases

### Configuration and maintenance

- `gpd:settings` - Guided autonomy, permissions, and runtime configuration after your first successful start or later
- `gpd:set-tier-models` - Directly pin concrete tier model ids
- `gpd:set-profile <profile>` - Switch the abstract model profile
- `gpd:compact-state` - Archive old `STATE.md` entries
- `gpd:sync-state` - Repair diverged `STATE.md` and `state.json`
- `gpd:undo` - Roll back the last GPD operation with a safety checkpoint
- `gpd:update` - Update GPD to the latest version
- `gpd:reapply-patches` - Reapply local modifications after updating

## Detailed Command Reference

Use `gpd:help --command <name>` when you want the detailed notes for one runtime command at a time.

### Core Workflow

```
gpd:new-project -> gpd:discuss-phase -> gpd:plan-phase -> gpd:execute-phase -> gpd:verify-work -> repeat
```

### Project Initialization

**`gpd:start`**
Guide a first-time user to the right GPD entry point for the current folder.

- Detects whether the current folder is an existing GPD project, existing non-GPD research, or a new folder
- Recommends the right entry point instead of forcing the user to guess
- Routes into `gpd:resume-work`, `gpd:suggest-next`, `gpd:progress`, `gpd:tour`, `gpd:map-research`, `gpd:new-project`, `gpd:new-project --minimal`, `gpd:help --all`, or `gpd:explain`
- Does not create project artifacts itself; it is an onboarding router

Usage: `gpd:start`

**`gpd:tour`**
Show a guided beginner tour of the core GPD commands without taking action.

- Explains the main commands and when to use them
- Stays read-only and does not create files or route into another workflow
- Good optional first stop if you want a quick orientation before choosing a path

Usage: `gpd:tour`

**`gpd:new-project`**
Initialize a new research project through questioning, optional survey, scoping, and roadmap generation.

One command takes you from idea to ready-for-investigation:

- Deep questioning to understand the physics problem
- Optional literature survey (spawns 4 parallel scout agents)
- Research objectives definition with scoping
- Roadmap creation with phase breakdown and success criteria

Creates all `GPD/` artifacts:

- `PROJECT.md` — research question, theoretical framework, key parameters
- `config.json` — workflow settings (`autonomy`, `research_mode`, `execution.review_cadence`, `planning.commit_docs`, agent toggles)
- `research/` — literature survey (if selected)
- `REQUIREMENTS.md` — scoped research requirements with REQ-IDs
- `ROADMAP.md` — phases mapped to requirements
- `STATE.md` — project memory

**Flags:**

- `--minimal` — Skip deep questioning and literature survey. Creates project from a single description. Asks one question ("Describe your research project and phases"), then generates all `GPD/` artifacts with sensible defaults. Same file set as full mode, so all downstream commands work identically.
- `--minimal @file.md` — Create project directly from a markdown file describing your research and phases. Parses research question, phase list, and key parameters from the file. No interactive questions asked.
- `--auto` — Automatic mode with full depth. Expects research proposal via @ reference. Runs literature survey, requirements, and roadmap without interaction.

Usage: `gpd:new-project`
Usage: `gpd:new-project --minimal`
Usage: `gpd:new-project --minimal @plan.md`

**`gpd:map-research`**
Map an existing research project — theoretical framework, computations, conventions, and open questions.

- Spawns 4 parallel research-mapper agents to analyze project artifacts
- Creates `GPD/research-map/` with 7 structured documents
- Covers formalism, references, computational architecture, structure, conventions, validation, concerns
- Use before `gpd:new-project` on existing research projects

Usage: `gpd:map-research`

### Phase Planning

**`gpd:discuss-phase <number>`**
Help articulate your vision for a research phase before planning.

- Captures how you imagine this phase proceeding
- Creates CONTEXT.md with your approach, essentials, and boundaries
- Use when you have specific ideas about methods or approximations

Usage: `gpd:discuss-phase 2`

**`gpd:research-phase <number>`**
Comprehensive literature survey for a specific phase.

- Discovers known results, standard methods, available data
- Creates {phase}-RESEARCH.md with domain expert knowledge
- Use for phases involving unfamiliar techniques or contested results
- Goes beyond "which method" to deep domain knowledge

Usage: `gpd:research-phase 3`

**`gpd:list-phase-assumptions <number>`**
See what the agent plans to do before it starts.

- Shows the agent's intended approach for a phase
- Lets you course-correct if the approach is wrong
- No files created - conversational output only

Usage: `gpd:list-phase-assumptions 3`

**`gpd:discover [phase or topic] [--depth quick|medium|deep]`**
Run discovery phase to investigate methods, literature, and approaches before planning.

- Surveys known results, standard methods, and computational tools
- Depth levels: quick (summary), medium (detailed), deep (comprehensive)
- Creates discovery artifacts consumed by planner or standalone analysis
- Use when entering an unfamiliar subfield or technique

Usage: `gpd:discover 3`
Usage: `gpd:discover "finite-temperature RG flow" --depth deep`
Usage: `gpd:discover 3 --depth deep`

**`gpd:show-phase <number>`**
Inspect a single phase's artifacts, status, and results.

- Shows phase goal, plans, summaries, and verification status
- Displays frontmatter metadata (wave, dependencies, status)
- Quick way to review what a phase produced

Usage: `gpd:show-phase 3`

**`gpd:plan-phase <number>`**
Create detailed execution plan for a specific phase.

- Generates `GPD/phases/XX-phase-name/XX-YY-PLAN.md`
- Breaks phase into concrete, actionable steps
- Includes verification criteria (limiting cases, consistency checks)
- Multiple plans per phase supported (XX-01, XX-02, etc.)

**Flags:**

- `--research` — Force literature research even if RESEARCH.md already exists
- `--skip-research` — Skip literature research entirely
- `--gaps` — Gap closure mode: plan from VERIFICATION.md issues instead of fresh research
- `--skip-verify` — Skip plan checker verification after planning
- `--light` — Produce simplified strategic outline (contract, constraints, high-level approach only)
- `--inline-discuss` — Run discuss-phase inline before planning (skip if already done)

Usage: `gpd:plan-phase 1`
Usage: `gpd:plan-phase 3 --research`
Usage: `gpd:plan-phase 5 --light --skip-verify`
Result: Creates `GPD/phases/01-framework-setup/01-01-PLAN.md`

### Execution

**`gpd:execute-phase <phase-number>`**
Execute all plans in a phase.

- Groups plans by wave (from frontmatter), executes waves sequentially
- Plans within each wave run in parallel via task tool
- Verifies phase goal after all plans complete (limiting cases, dimensional analysis, benchmarks)
- Updates REQUIREMENTS.md, ROADMAP.md, STATE.md

Usage: `gpd:execute-phase 5`

### Derivation

**`gpd:derive-equation`**
Perform a rigorous physics derivation with systematic verification at each step.

- States assumptions explicitly, establishes notation and conventions
- Performs step-by-step derivation with dimensional analysis at each stage
- Verifies intermediate results against known limits and symmetry properties
- Justifies and bounds all approximations with error estimates
- For theorem-bearing work, spawns `gpd-check-proof` and blocks completion until the proof audit passes
- Produces a complete, self-contained derivation document with boxed final result

Usage: `gpd:derive-equation "derive the one-loop beta function"`

### Quick Mode

**`gpd:quick`**
Execute small, ad-hoc calculations with GPD guarantees but skip optional agents.

Quick mode uses the same system with a shorter path:

- Spawns planner + executor (skips literature scout, checker, validator)
- Quick tasks live in `GPD/quick/` separate from planned phases
- Updates STATE.md tracking (not ROADMAP.md)

Use when you know exactly what to calculate and the task is small enough to not need literature survey or validation.

Usage: `gpd:quick`
Result: Creates `GPD/quick/NNN-slug/PLAN.md`, `GPD/quick/NNN-slug/SUMMARY.md`

### Roadmap Management

**`gpd:add-phase <description>`**
Add new phase to end of current milestone.

- Appends to ROADMAP.md
- Uses next sequential number
- Updates phase directory structure

Usage: `gpd:add-phase "Compute finite-temperature corrections"`

**`gpd:insert-phase <after> <description>`**
Insert urgent work as decimal phase between existing phases.

- Creates intermediate phase (e.g., 7.1 between 7 and 8)
- Useful for discovered work that must happen mid-investigation
- Maintains phase ordering

Usage: `gpd:insert-phase 7 "Fix sign error in vertex function"`
Result: Creates Phase 7.1

**`gpd:remove-phase <number>`**
Remove a future phase and renumber subsequent phases.

- Deletes phase directory and all references
- Renumbers all subsequent phases to close the gap
- Only works on future (unstarted) phases
- Git commit preserves historical record

Usage: `gpd:remove-phase 17`
Result: Phase 17 deleted, phases 18-20 become 17-19

**`gpd:revise-phase <number> "<reason>"`**
Supersede a completed phase and create a replacement for iterative revision.

- Marks original phase as superseded (preserved as historical record)
- Creates replacement phase with decimal numbering (e.g., 3.1)
- Pre-populates replacement with context: what worked, what didn't, what to change
- Updates downstream dependency references
- Flags downstream phases that may also need revision
- Only works on completed phases (use gpd:remove-phase for future phases)

Usage: `gpd:revise-phase 3 "Sign error in vertex correction"`
Result: Phase 3 superseded, Phase 3.1 created with inherited context

**`gpd:merge-phases <source> <target>`**
Merge results from one phase into another.

- Copies artifacts (summaries, plans, data files) from source to target
- Merges intermediate results and decisions with phase attribution
- Updates roadmap to reflect the merge
- Useful for folding decimal phases back into parents or converging parallel branches

Usage: `gpd:merge-phases 2.1 2`

### Milestone Management

**`gpd:new-milestone <name>`**
Start a new research milestone through unified flow.

- Deep questioning to understand the next research direction
- Optional literature survey (spawns 4 parallel scout agents)
- Objectives definition with scoping
- Roadmap creation with phase breakdown
- Uses `planning.commit_docs` from init to decide whether milestone artifacts are committed immediately

Mirrors `gpd:new-project` flow for continuation projects (existing PROJECT.md).

Usage: `gpd:new-milestone "v2.0 Higher-order corrections"`

**`gpd:complete-milestone <version>`**
Archive completed milestone and prepare for next direction.

- Creates MILESTONES.md entry with results summary
- Archives full details to milestones/ directory
- Creates git tag for the release
- Prepares workspace for next research direction

Usage: `gpd:complete-milestone 1.1.0`

### Progress Tracking

**`gpd:progress`**
Check research status and intelligently route to next action.

- Shows visual progress bar and completion percentage
- Summarizes recent work from SUMMARY files
- Displays current position and what's next
- Lists key results and open issues
- Offers to execute next plan or create it if missing
- Detects 100% milestone completion
- Use `--brief` when returning and you only need orientation
- Use `--reconcile` when state appears out of sync with disk artifacts

Usage: `gpd:progress`
Usage: `gpd:progress --full` (detailed view with all phase artifacts)
Usage: `gpd:progress --brief` (compact one-line status)
Usage: `gpd:progress --reconcile` (fix diverged STATE.md and state.json)

### Session Management

**`gpd:resume-work`**
Resume research from a previous session with full context restoration.

@{GPD_INSTALL_DIR}/references/orchestration/resume-vocabulary.md

- Use the recovery ladder (`gpd resume` -> `gpd resume --recent` -> `gpd:resume-work`) to pick up where you left off
- Best first in-runtime command when returning to paused or interrupted work

Usage: `gpd:resume-work`

**`gpd:pause-work`**
Create a continuation handoff artifact when pausing work mid-phase.

- Creates the canonical `.continue-here.md` continuation handoff artifact with current state
- Updates the mirrored STATE.md session continuity entry
- Captures in-progress work context
- Run this before leaving mid-phase so `gpd:resume-work` has an explicit recorded handoff artifact to restore from canonical continuation state

Usage: `gpd:pause-work`

### Todo Management

**`gpd:add-todo [description]`**
Capture idea or task as todo from current conversation.

- Extracts context from conversation (or uses provided description)
- Creates structured todo file in `GPD/todos/pending/`
- Infers area from context for grouping
- Checks for duplicates before creating
- Updates STATE.md todo count

Usage: `gpd:add-todo` (infers from conversation)
Usage: `gpd:add-todo Check if vertex correction satisfies Ward identity`

**`gpd:check-todos [area]`**
List pending todos and select one to work on.

- Lists all pending todos with title, area, age
- Optional area filter (e.g., `gpd:check-todos numerical`)
- Loads full context for selected todo
- Routes to appropriate action (work now, add to phase, think more)
- Moves todo to done/ when work begins

Usage: `gpd:check-todos`
Usage: `gpd:check-todos analytical`

### Validation

**`gpd:verify-work [phase]`**
Validate research results through systematic checks.

- Extracts testable results from SUMMARY.md files
- Checks limiting cases, dimensional analysis, conservation laws
- Compares against known benchmarks
- Automatically diagnoses failures and creates fix plans
- Ready for re-execution if issues found

Usage: `gpd:verify-work 3`

### Debugging

**`gpd:debug [issue description]`**
Systematic debugging of physics calculations with persistent state across context resets.

- Spawns gpd-debugger agent with scientific method approach
- Maintains debug session state in `GPD/debug/`
- Survives context window resets — resumes from last checkpoint
- Archives resolved issues to `GPD/debug/resolved/`

Usage: `gpd:debug Sign error in self-energy diagram`

### Physics Validation

**`gpd:dimensional-analysis`**
Check dimensional consistency of equations and expressions.

- Verifies all terms have consistent units
- Checks final results have correct dimensions
- Flags dimensionless ratios and magic numbers

Usage: `gpd:dimensional-analysis 3`
Usage: `gpd:dimensional-analysis results/01-SUMMARY.md`

**`gpd:limiting-cases`**
Verify results reduce correctly in known limiting cases.

- Tests classical, non-relativistic, weak-coupling, thermodynamic limits
- Compares against textbook expressions in each limit
- Flags limits that are not recovered

Usage: `gpd:limiting-cases 3`
Usage: `gpd:limiting-cases results/01-SUMMARY.md`

**`gpd:numerical-convergence`**
Run systematic convergence tests on numerical computations.

- Tests convergence with grid refinement, time step, basis size
- Estimates convergence order via Richardson extrapolation
- Constructs error budgets for computed quantities

Usage: `gpd:numerical-convergence 3`
Usage: `gpd:numerical-convergence results/mesh-study.csv`

**`gpd:compare-experiment`**
Compare theoretical/numerical results against experimental data.

- Loads published experimental values and error bars
- Computes chi-squared or other goodness-of-fit measures
- Identifies systematic deviations and their possible origins

Usage: `gpd:compare-experiment predictions.csv experiment.csv`

**`gpd:compare-results [phase, artifact, or comparison target]`**
Compare internal results, baselines, or methods and emit a decisive verdict.

- Compares phase outputs, artifacts, or named comparison targets
- Surfaces agreement, tension, or failure in a single verdict-oriented view
- Useful when you need to compare internal baselines without reaching for external data

Usage: `gpd:compare-results 3`
Usage: `gpd:compare-results results/01-SUMMARY.md`

**`gpd:validate-conventions [phase]`**
Validate convention consistency across all phases.

- Checks metric signature, Fourier convention, natural units, gauge choice
- Detects convention drift where a symbol is redefined in a later phase
- Cross-checks locked conventions against all phase artifacts
- Scope to a single phase using the optional phase argument, or run across all completed phases

Usage: `gpd:validate-conventions`
Usage: `gpd:validate-conventions 3`

**`gpd:regression-check [phase]`**
Scan-only audit for regressions in already-recorded verification state.

- Detects convention conflicts where the same symbol is redefined with different values across completed SUMMARY artifacts
- Scans `SUMMARY.md` and `VERIFICATION.md` frontmatter rather than re-running numerical or physics verification
- Flags non-passing, invalid, or non-canonical `VERIFICATION.md` statuses in completed phases
- Uses canonical statuses `passed`, `gaps_found`, `expert_needed`, and `human_needed`
- Reports the affected phases and files for follow-up verification or repair
- Scope to a single phase using the optional phase argument, or run across all completed phases

Usage: `gpd:regression-check`
Usage: `gpd:regression-check 3`

**`gpd:health`**
Run project health checks and optionally auto-fix issues.

- Checks state, frontmatter, storage-path policy, and other project health surfaces
- Reports warnings and fixable issues before they become workflow blockers
- Supports `--fix` for automatic repair of common problems

Usage: `gpd:health`
Usage: `gpd:health --fix`

### Quantitative Analysis

**`gpd:parameter-sweep [phase]`**
Systematic parameter sweep with parallel execution and result aggregation.

- Varies one or more parameters across a specified range
- Uses wave-based parallelism for independent parameter values
- Collects results and produces summary tables
- Supports adaptive refinement near interesting features

Usage: `gpd:parameter-sweep 3 --param coupling --range 0:1:20`
Usage: `gpd:parameter-sweep 3 --adaptive`

**`gpd:sensitivity-analysis`**
Determine which input parameters most strongly affect output quantities.

- Computes partial derivatives and condition numbers
- Ranks parameters by sensitivity
- Identifies which measurements or calculations would most improve results
- Supports analytical and numerical methods

Usage: `gpd:sensitivity-analysis --target cross_section --params g,m,Lambda`
Usage: `gpd:sensitivity-analysis --target cross_section --params g,m,Lambda --method numerical`

**`gpd:error-propagation`**
Track how uncertainties propagate through multi-step calculations.

- Traces input uncertainties through intermediate results to final quantities
- Identifies dominant error sources
- Produces error budgets
- Scope to specific phases or full derivation chain

Usage: `gpd:error-propagation --target final_mass`
Usage: `gpd:error-propagation --phase-range 1:5`

### Research Publishing

**`gpd:write-paper [title or topic] [--from-phases 1,2,3]`**
Structure and write a physics paper from research results.

- Loads research digest from milestone completion (if available)
- Runs paper-readiness audit (conventions, verification, figures, citations)
- Spawns gpd-paper-writer agents for each section (Results first, Abstract last)
- Drafts the manuscript and uses `gpd paper-build` for the canonical scaffold/build contract
- Spawns gpd-bibliographer to verify all references
- Runs the staged peer-review panel with gpd-referee as final adjudicator
- Supports revision mode for referee responses (bounded 3-iteration loop)

Usage: `gpd:write-paper "Critical exponents via RG"`
Usage: `gpd:write-paper --from-phases 1,3,5` (subset of phases)

**`gpd:peer-review [paper directory or manuscript path]`**
Run skeptical peer review on an existing manuscript within the current GPD project.

- Runs strict review preflight checks against project state, manuscript, artifacts, and reproducibility support
- Loads manuscript files, phase summaries, verification reports, bibliography audit, and artifact manifest
- Spawns a six-agent review panel plus the auxiliary `gpd-check-proof` critic when theorem-bearing claims are present
- Produces stage artifacts under `GPD/review/` plus `GPD/REFEREE-REPORT{round_suffix}.md` and `GPD/REFEREE-REPORT{round_suffix}.tex`
- Routes the result to `gpd:respond-to-referees` or `gpd:arxiv-submission`
- Requires an initialized `GPD/PROJECT.md` workspace; manuscript paths do not bypass project preflight

Usage: `gpd:peer-review`
Usage: `gpd:peer-review paper/`

**`gpd:respond-to-referees`**
Structure point-by-point response to referee reports and revise the manuscript.
- Parses referee comments into structured items with severity levels
- Drafts both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md` with REF-xxx issue tracking (fixed/rebutted/acknowledged/needs-calculation)
- Consumes `GPD/review/REVIEW-LEDGER*.json` and `GPD/review/REFEREE-DECISION*.json` when present to preserve blocking-issue context
- Spawns paper-writer agents for targeted section revisions
- Tracks new calculations required by referees as revision tasks
- Produces response letter from `templates/paper/referee-response.md`
- Bounded revision loop (max 3 iterations with re-review)

Usage: `gpd:respond-to-referees`

**`gpd:arxiv-submission`**
Prepare a completed paper for arXiv submission with validation and packaging.

- Requires a successful `gpd paper-build` before packaging
- Optional local compiler smoke check if available
- Bibliography flattening (inline .bbl or resolve .bib)
- Figure format and resolution checking
- `\input` resolution into single .tex file (optional)
- Metadata verification (title, authors, abstract)
- Ancillary file packaging
- Generates submission-ready `.tar.gz`
- Produces checklist of remaining manual steps

Usage: `gpd:arxiv-submission`

**`gpd:explain [concept]`**
Explain a concept, method, notation, result, or paper in project context or from a standalone question.

- Spawns a `gpd-explainer` agent and grounds the explanation in the active phase, manuscript, or local workflow when available
- Produces a structured explanation under `GPD/explanations/`
- Audits cited papers with `gpd-bibliographer` and includes a reading path with openable links

Usage: `gpd:explain "Ward identity"`

**`gpd:suggest-next`**
Suggest the most impactful next action based on current project state.

- Scans phases, plans, verification status, blockers, and todos
- Produces a prioritized action list
- Local CLI fallback: `gpd --raw suggest`
- Fastest way to answer "what should I do next?" without reading through progress reports
- Fastest post-resume command when you only need the next action

Usage: `gpd:suggest-next`

**`gpd:literature-review [topic]`**
Structured literature review for a physics research topic.

- Citation network analysis and open question identification
- Spawns `gpd-literature-reviewer` for the structured review
- Spawns gpd-bibliographer agent for citation verification
- Creates structured review with key papers, methods, and gaps

Usage: `gpd:literature-review "Sachdev-Ye-Kitaev model thermodynamics"`

**`gpd:digest-knowledge [topic|arXiv id|source file|knowledge path]`**
Create or update a knowledge document draft from a topic, paper, source file, or explicit knowledge path.

- Accepts an explicit knowledge-doc path, a source file path, a modern or legacy arXiv ID, or a topic string
- Resolves one canonical `GPD/knowledge/{knowledge_id}.md` target or stops on ambiguity
- Reopens existing draft knowledge docs in place and routes approval or stable-state requests to `gpd:review-knowledge`
- Drafts stay `draft` until reviewed, and they move into `in_review` while a review round is open
- If the target is `stable` or `superseded`, route the user to `gpd:review-knowledge`
- Stable knowledge is already visible through the shared runtime reference surfaces, but it remains reviewed background synthesis rather than a separate authority tier
- Migration/backfill for older or provisional docs remains deferred; use canonical `GPD/knowledge/{knowledge_id}.md` targets for now.

- Example topic: `gpd:digest-knowledge "renormalization group fixed points"`
- Example modern arXiv: `gpd:digest-knowledge 2401.12345v2`
- Example legacy arXiv: `gpd:digest-knowledge hep-th/9901001`
- Example source file: `gpd:digest-knowledge ./notes/rg-notes.md`
- Example explicit knowledge path: `gpd:digest-knowledge GPD/knowledge/K-renormalization-group-fixed-points.md`

Usage: `gpd:digest-knowledge "renormalization group fixed points"`

**`gpd:review-knowledge [knowledge path or knowledge id]`**
Review a knowledge document, record typed approval evidence, and promote a fresh approved draft to stable.

- Resolves an exact existing knowledge target by canonical path or knowledge id
- Writes a deterministic review artifact under `GPD/knowledge/reviews/`
- Records review round, reviewer identity, approval artifact hash, reviewed content hash, and stale state
- Promotes the document to `stable` only when the review is fresh and explicitly approved
- Keeps `needs_changes` and `rejected` outcomes in the review loop without pretending they are stable
- `stable` docs can later become `superseded`; superseded docs remain addressable and traceable rather than disappearing
- Stable knowledge is available through the shared runtime reference surfaces, but it does not override stronger evidence or explicit dependency gates

Usage: `gpd:review-knowledge GPD/knowledge/K-renormalization-group-fixed-points.md` or `gpd:review-knowledge K-renormalization-group-fixed-points`

### Optional Local CLI Add-Ons

**Workflow presets**

- `Paper/manuscript workflows` - First supported workflow preset for `write-paper`, `paper-build`, `peer-review`, and `arxiv-submission`; inspect it with `gpd presets list`, preview it with `gpd presets show <preset>`, and apply it from your normal terminal with `gpd presets apply <preset>` or through your runtime-specific `settings` command
- `gpd doctor --runtime <runtime> --local` / `gpd doctor --runtime <runtime> --global` - Check the local or global runtime target from your normal terminal before using that preset. Add `--live-executable-probes` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`. Failed preset rows degrade `write-paper`, but `paper-build` remains the build contract and `arxiv-submission` still requires the built manuscript
- `gpd presets list` - Inspect the local preset catalog; presets resolve to the existing config keys and do not add a separate persisted preset block
- `gpd presets show <preset>` - Preview one preset's bundle before applying it
- `gpd presets apply <preset> [--dry-run]` - Apply or preview one preset from your normal terminal without inventing a separate preset schema

Workflow presets are bundles over the existing config keys only; they do not add a separate persisted preset block.

**Wolfram integration**

- `gpd integrations status wolfram` - Inspect the shared optional Wolfram integration config only; this does not prove local Mathematica availability or plan readiness, and optional doctor probes do not change that
- `gpd integrations enable wolfram` - Enable the shared optional Wolfram integration config
- `gpd integrations disable wolfram` - Disable the shared optional Wolfram integration config

Local Mathematica installs are separate from the shared optional Wolfram integration config.

Workflow preset tooling is layered on top of the base install; it does not change runtime permission alignment.

### Tangents & Hypothesis Branches

**`gpd:tangent [description]`**
Choose what to do with a possible side investigation without immediately committing to a git branch.

- Acts as the tangent chooser: stay on the current line, do a quick tangent, defer it, or escalate to a branch
- Use when an interesting sub-question appears but you have not yet decided whether it deserves isolated branch state
- Keeps hypothesis branching as an explicit follow-on decision rather than the default for every tangent
- If `gpd observe execution` surfaces an alternative-path follow-up or `branch later` recommendation, run `gpd:tangent` first rather than skipping straight to `gpd:branch-hypothesis`

Usage: `gpd:tangent "Check whether the 2D case is degenerate before branching"`

**`gpd:branch-hypothesis <description>`**
Create a hypothesis branch for parallel investigation of an alternative approach.

- Creates git branch with isolated `GPD/` state
- Allows exploring alternative methods without disrupting main line
- Use when the tangent should become an explicit git-backed alternative path you intend to compare

Usage: `gpd:branch-hypothesis "Try perturbative RG instead of exact RG"`

**`gpd:compare-branches`**
Compare results across hypothesis branches side-by-side.

- Reads SUMMARY.md and VERIFICATION.md from each branch
- Shows which approach produced better results
- Helps decide which branch to merge back

Usage: `gpd:compare-branches`

### Decision Tracking

**`gpd:decisions [phase or keyword]`**
Display and search the cumulative decision log.

- Shows all recorded decisions across phases
- Filter by phase number or keyword
- Tracks sign conventions, approximation choices, gauge choices
- Reads from `GPD/DECISIONS.md`

Usage: `gpd:decisions`
Usage: `gpd:decisions 3`
Usage: `gpd:decisions "gauge"`

### Visualization & Export

**`gpd:graph`**
Visualize dependency graph across phases and identify gaps.

- Builds Mermaid diagram from phase frontmatter (provides/requires/affects)
- Identifies gaps where a phase requires something no other phase provides
- Computes critical path through the research project

Usage: `gpd:graph`

> **Note:** Wave dependency validation runs automatically when executing phases. To validate manually, use `gpd phase validate-waves <phase>` — checks depends_on targets, file overlap within waves, wave consistency, and circular dependencies.

**`gpd:export [--format html|latex|zip|all]`**
Export research results to HTML, LaTeX, or ZIP package.

- HTML: standalone page with MathJax rendering
- LaTeX: document with proper equations and bibliography
- ZIP: complete archive of all planning artifacts

Usage: `gpd:export --format html`
Usage: `gpd:export --format all`

**`gpd:export-logs [--format jsonl|json|markdown] [--session <id>] [--last N] [--no-traces] [--output-dir <path>]`**
Export observability sessions and optional traces to files for review, sharing, or archival.

- Reads session event streams from `GPD/observability/sessions/` and optional traces from `GPD/traces/`
- Writes filtered exports to `GPD/exports/logs/` or a custom directory
- Supports JSONL, JSON, and markdown output
- Useful when you need to share or inspect the recorded execution history outside the runtime

Usage: `gpd:export-logs`
Usage: `gpd:export-logs --format markdown`
Usage: `gpd:export-logs --last 5`

**`gpd:slides [topic, audience, or source path]`**
Create presentation slides from a GPD project or the current folder.

- Audits papers, figures, notes, code, and data to build a talk brief
- Asks targeted questions about audience, duration, format/toolchain, templates, technical depth, and whether to refresh or extend existing slide assets
- Defaults toward Beamer for equation-heavy talks and uses markdown or native decks when that fits better
- Produces an outline plus deck source files in `slides/`

Usage: `gpd:slides "Group meeting update on finite-temperature RG"`
Usage: `gpd:slides -- "20 minute seminar for condensed matter theorists"`

**`gpd:error-patterns [category]`**
View accumulated physics error patterns for this project.

- Shows common mistakes discovered during debugging and verification
- Optional category filter (sign, dimension, approximation, etc.)
- Helps avoid repeating known pitfalls

Usage: `gpd:error-patterns`
Usage: `gpd:error-patterns sign`

**`gpd:record-insight [description]`**
Record a project-specific learning or pattern to the insights ledger.

- Records error patterns, convention pitfalls, verification lessons
- Checks for duplicates before adding
- Categorizes into appropriate section (Debugging Patterns, Verification Lessons, etc.)
- Updates `GPD/INSIGHTS.md`

Usage: `gpd:record-insight`
Usage: `gpd:record-insight Sign error in Wick contractions with mostly-minus metric`

### Milestone Auditing

**`gpd:audit-milestone [version]`**
Audit milestone completion against original objectives.

- Reads all phase VERIFICATION.md files
- Checks objectives coverage
- Spawns cross-check agent for consistency between phases
- Creates MILESTONE-AUDIT.md with gaps and open questions

Usage: `gpd:audit-milestone`

**`gpd:plan-milestone-gaps`**
Create phases to close gaps identified by audit.

- Reads MILESTONE-AUDIT.md and groups gaps into phases
- Prioritizes by objective priority
- Adds gap closure phases to ROADMAP.md
- Ready for `gpd:plan-phase` on new phases

Usage: `gpd:plan-milestone-gaps`

### Configuration

**`gpd:settings`**
Primary guided setup for autonomy, unattended execution budgets, runtime permission sync, model profile, `execution.review_cadence`, and runtime-specific tier model overrides.

- Choose how often GPD should pause for you (`Balanced (Recommended)` is the best default for most unattended runs)
- Review unattended execution budgets and other bounded continuation limits before leaving runs alone
- Start with a qualitative model-cost posture: `Max quality`, `Balanced`, or `Budget-aware`
- Sync runtime-owned permissions after autonomy changes when the active runtime supports it
- If settings reports a relaunch is required, the new autonomy level is not unattended-ready yet
- Toggle plan researcher, plan checker, and execution verifier agents
- Configure inter-wave verification gates (`execution.review_cadence`: `dense`, `adaptive`, or `sparse`)
- Toggle parallel execution of wave plans
- Select model profile (deep-theory/numerical/exploratory/review/paper-writing); `review` with runtime defaults is the safest first choice
- Let that posture drive whether you keep runtime defaults or pin concrete runtime model strings for `tier-1`, `tier-2`, and `tier-3`
- Configure whether planning artifacts are committed (`planning.commit_docs`)
- Configure git branching strategy (`git.branching_strategy`: `none`, `per-phase`, or `per-milestone`)
- Use `gpd cost` after runs when you want the read-only machine-local usage / cost summary
- Updates `GPD/config.json`

Usage: `gpd:settings`

**`gpd:set-tier-models`**
Direct concrete model-id setup for `tier-1`, `tier-2`, and `tier-3` on the active runtime.

- `tier-1` — highest capability, usually highest cost
- `tier-2` — balanced default
- `tier-3` — fastest / most economical
- Clears or writes only `model_overrides.<runtime>` in `GPD/config.json`
- Leaves `model_profile`, autonomy, `execution.review_cadence`, budgets, and workflow toggles unchanged
- Use runtime defaults if you are unsure; pin exact ids only when you want explicit control
- Use `gpd cost` after runs for the read-only recorded local usage / cost view

Usage: `gpd:set-tier-models`

**`gpd:set-profile <profile>`**
Quick switch model profile for GPD agents. Use `gpd:set-tier-models` for the direct concrete tier-id path, or `gpd:settings` when you want broader unattended/configuration changes too.

- `deep-theory` — tier-1 (highest capability) for all reasoning-intensive agents (formal derivations, proofs)
- `numerical` — tier-1 for planning/verification, tier-2 for execution (simulations, numerics)
- `exploratory` — tier-1 for planner/researchers, tier-2 for execution (hypothesis generation)
- `review` (default) — tier-1 for verifier/checker/debugger, tier-2 for execution (validation focus)
- `paper-writing` — tier-1 for planner/executor/synthesizer, tier-2 for verification

Usage: `gpd:set-profile deep-theory`

### Utility Commands

**`gpd:compact-state`**
Archive historical entries from STATE.md to keep it lean.

- Moves old decisions, metrics, and resolved blockers to STATE-ARCHIVE.md
- Keeps STATE.md under the target line budget (~150 lines)
- Triggered automatically when STATE.md exceeds 1500 lines

Usage: `gpd:compact-state`
Usage: `gpd:compact-state --force` (skip line-count check)

**`gpd:sync-state`**
Reconcile diverged STATE.md and state.json after manual edits or corruption.

- Detects mismatches between human-readable STATE.md and structured state.json
- Resolves by choosing the more recent or more complete source
- Fixes broken convention locks, missing phase counters, or stale progress bars
- Use after manual edits to STATE.md or after a crash during state updates

Usage: `gpd:sync-state`

**`gpd:undo`**
Rollback last GPD operation with safety checkpoint.

- Creates a safety tag before reverting so the undo itself is reversible
- Reverts only GPD-related commits (not arbitrary git history)
- Rejects merge commits — manual resolution required

Usage: `gpd:undo`

**`gpd:update`**
Update GPD to latest version with changelog display.

- Runs the public bootstrap update command for the active runtime
- Shows changelog of what changed since your version
- Preserves local modifications via patch backups (use `gpd:reapply-patches` after if needed)

Usage: `gpd:update`

**`gpd:reapply-patches`**
Reapply local modifications after a GPD update.

- Detects and replays customizations you made to GPD files
- Use after `gpd:update` if you have local workflow or template modifications

Usage: `gpd:reapply-patches`

**`gpd:help`**
Show this command reference.

## Files & Structure

The literature survey lives under `GPD/literature/`, and reviewed knowledge docs live under `GPD/knowledge/` with review artifacts in `GPD/knowledge/reviews/`.

```
GPD/
|-- PROJECT.md            # Research question, framework, parameters
|-- REQUIREMENTS.md       # Scoped research requirements with REQ-IDs
|-- ROADMAP.md            # Current phase breakdown
|-- STATE.md              # Project memory & context
|-- MILESTONES.md         # Milestone history
|-- config.json           # Workflow mode & gates
|-- literature/           # Literature survey results and citation artifacts
|   |-- PRIOR-WORK.md     # Established results in the field
|   |-- METHODS.md        # Standard methods and tools
|   |-- COMPUTATIONAL.md  # Computational approaches and tools
|   |-- PITFALLS.md       # Known pitfalls and open problems
|   +-- SUMMARY.md        # Synthesized survey
|-- knowledge/            # Knowledge docs and typed review artifacts
|   |-- K-*.md            # Draft, in_review, stable, or superseded knowledge docs
|   +-- reviews/          # Deterministic review artifacts
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

Set during `gpd:new-project` or changed later with `gpd:settings`:

**Supervised**

- Confirms each major step
- Uses the most checkpoints
- Best for high-stakes work or learning the workflow
- Best when you plan to stay nearby and approve each physics-bearing move

**Balanced (Recommended)**

- Handles routine work automatically
- Pauses on physics decisions, ambiguities, blockers, or scope changes
- Best default for most projects
- Best first choice for unattended runs because it still pauses on important physics, scope, and blocker decisions

**YOLO**

- Fastest and least interactive
- Auto-approves checkpoints and keeps going unless a hard stop fires
- Best when you want maximum speed and minimal interruptions
- Use only after `gpd:settings` reports runtime permissions are synchronized and no relaunch is still required

Change anytime with `gpd:settings`. If it says a relaunch is required, the new autonomy level is not unattended-ready yet.

## Planning Configuration

Configure how planning artifacts are managed in `GPD/config.json`:

**`planning.commit_docs`** (default: `true`)

- `true`: Planning artifacts committed to git (standard workflow)
- `false`: Planning artifacts kept local-only, not committed

When `planning.commit_docs: false`:

- Add `GPD/` to your `.gitignore`
- Useful for collaborative projects, shared repos, or keeping planning private
- All planning files still work normally, just not tracked in git

Example config:

```json
{
  "execution": {
    "review_cadence": "adaptive"
  },
  "planning": {
    "commit_docs": false
  }
}
```

## Common Workflows

**Starting a new research project:**

```
gpd:new-project        # Unified flow: questioning -> survey -> discuss -> objectives -> roadmap
/clear                  # then run gpd:discuss-phase 1
gpd:discuss-phase 1    # Gather context and clarify approach
/clear                  # then run gpd:plan-phase 1
gpd:plan-phase 1       # Create plans for first phase
/clear                  # then run gpd:execute-phase 1
gpd:execute-phase 1    # Execute all plans in phase
```

**Fast project bootstrap (skip deep questioning):**

```
gpd:new-project --minimal              # One question, then auto-generate everything
gpd:new-project --minimal @plan.md     # Generate from existing research plan file
```

**Leaving and returning after a break:**

```
gpd:pause-work        # Before leaving mid-phase, capture a continuation handoff artifact
/clear                 # then run gpd resume in your normal terminal for the current workspace
gpd resume             # Current-workspace read-only recovery snapshot from your normal terminal
gpd resume --recent    # Find the workspace first in your normal terminal when you need to reopen a different one
gpd:resume-work       # Continue in-runtime from the reopened project's canonical state after reopening that workspace
gpd:suggest-next      # Fastest post-resume next command when you only need the next action
gpd:progress --brief  # Short orientation snapshot if you need more context
```

**Normal terminal, read-only recovery snapshot:**

```
gpd resume
```

**Normal terminal, read-only machine-local usage / cost summary:**

```
gpd cost
```

Read-only machine-local usage / cost summary from recorded local telemetry, optional USD budget guardrails, and the current profile tier mix; advisory only, not live budget enforcement or provider billing truth. If telemetry is missing, the USD view stays partial or estimated rather than exact.

**Adding urgent mid-milestone work:**

```
gpd:insert-phase 5 "Fix sign error in renormalization group equation"
gpd:plan-phase 5.1
gpd:execute-phase 5.1
```

**Completing a milestone:**

```
gpd:complete-milestone 1.1.0
/clear                 # then run gpd:new-milestone for the next milestone
gpd:new-milestone  # Start next milestone (questioning -> survey -> objectives -> roadmap)
```

**Capturing ideas during work:**

```
gpd:add-todo                                      # Capture from conversation context
gpd:add-todo Check finite-size scaling exponent    # Capture with explicit description
gpd:check-todos                                    # Review and work on todos
gpd:check-todos numerical                          # Filter by area
```

## Getting Help

- Read `GPD/PROJECT.md` for research question and framework
- Read `GPD/STATE.md` for current context and key results
- Check `GPD/ROADMAP.md` for phase status
- Run `gpd:progress` to check where you are
  </reference>

<success_criteria>
- [ ] Available commands listed with descriptions
- [ ] Common workflows shown with examples
- [ ] Quick reference table presented
- [ ] Next action guidance provided based on current project state
</success_criteria>
