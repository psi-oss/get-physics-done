<purpose>
Display the complete GPD command reference. Output ONLY the reference content. Do NOT add project-specific analysis, git status, next-step suggestions, or any commentary beyond the reference.
</purpose>

<process>

<step name="contextual_help">
## Contextual Help (State-Aware Variant)

When a state-aware help view is requested, show guidance based on project state:

1. Check project state via gpd CLI
2. Show ONLY the 5-8 commands relevant NOW:

**No project exists:**
```
Getting started:
  /gpd:start               — Guided router when you are not sure whether to create, map, resume, or just explain something
  /gpd:tour               — Optional guided tour of the main commands and when to use them
  /gpd:new-project         — Start a new research project with full scoping
  /gpd:new-project --minimal — Faster one-question project bootstrap
  /gpd:map-research        — Map an existing research project
```

**Project exists, paused or resumable:**
```
Returning to work:
  gpd resume             — Current-workspace read-only recovery snapshot from your normal terminal
  gpd resume --recent    — Find the workspace first when you need to reopen a different one
  /gpd:resume-work         — Continue in-runtime from the selected project state
  /gpd:progress            — Review the broader project snapshot
  /gpd:suggest-next        — Fastest post-resume next command when you only need the next action
  gpd observe execution    — Read-only live status from your normal terminal; use this for progress / waiting state, then follow its suggested read-only checks rather than runtime hotkeys
  gpd cost                 — Read-only machine-local usage / cost summary from your normal terminal
  /gpd:tangent             — Choose stay / quick / defer / branch when a side investigation appears
```

**Project exists, no plans yet:**
```
Phase {N}: {name}
  /gpd:discuss-phase {N}   — Gather context before planning
  /gpd:plan-phase {N}      — Create execution plan
  /gpd:progress --full     — See full project status
```

**Plans exist, not executed:**
```
Ready to execute:
  /gpd:execute-phase {N}   — Execute phase {N} plans
  /gpd:show-phase {N}      — Review phase details first
```

**Phase complete:**
```
Phase {N} complete:
  /gpd:discuss-phase {N+1}  — Gather context before planning the next phase
  /gpd:plan-phase {N+1}    — Create execution plan
  /gpd:complete-milestone   — If all phases done
```

**Manuscript exists, no referee report yet:**
```
Publication workflow:
  /gpd:peer-review         — Run manuscript peer review inside the current project
  /gpd:arxiv-submission    — Package only after review passes and the paper-build contract succeeds
  gpd doctor --runtime <runtime> --local|--global — Check runtime-local paper-toolchain readiness for the paper/manuscript workflow preset. Add `--live-executable-probes` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`. Inspect the preset with `gpd presets list`, preview it with `gpd presets show <preset>`, and apply it from your normal terminal with `gpd presets apply <preset>` or through your runtime-specific settings command; failed preset rows degrade `write-paper`, but `paper-build` remains the build contract and `arxiv-submission` requires the built manuscript
  gpd integrations status wolfram — Inspect the shared optional Wolfram integration config only; this does not prove local Mathematica availability or plan readiness, and optional doctor probes do not change that
```

**Referee report exists:**
```
Revision workflow:
  /gpd:respond-to-referees — Draft responses and revise the manuscript
  /gpd:peer-review         — Re-run peer review after revision
```

For full command reference: `/gpd:help --all`
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
1. `/gpd:new-project` — Define research question, survey literature, create roadmap
2. `/gpd:discuss-phase N` — Clarify the phase before planning
3. `/gpd:plan-phase N` — Create detailed plans for phase N
4. `/gpd:execute-phase N` — Run all plans (derivations, simulations, analysis)
5. `/gpd:verify-work` — Verify physics correctness
6. Repeat 2-5 for each phase
7. `/gpd:write-paper` — Generate publication from results
8. `/gpd:peer-review` — Run manuscript review before submission inside the current project
9. `/gpd:respond-to-referees` — Address reviewer comments if needed
10. `/gpd:arxiv-submission` — Package the approved manuscript

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

For the exact beginner-first startup order, use the shared onboarding surfaces in the README or installer output.

1. `/gpd:help` - See the command reference first.
2. `/gpd:start` - Let GPD choose the safest first step for the current folder.
3. `/gpd:tour` - Get a read-only walkthrough before you choose.
4. `/gpd:new-project` or `/gpd:map-research` - Begin the actual work path once you know the folder state.
5. `/gpd:resume-work` - Continue later after you have an existing GPD project.
6. `/gpd:settings` - Change autonomy, permissions, or runtime preferences after your first successful start or later.

## Invocation Surfaces

This reference lists canonical in-runtime slash-command names in `/gpd:*` form.

- If you are new to terminals or runtime setup, start with the Beginner Onboarding Hub linked from the README and installer output.
- That shared onboarding surface keeps the OS guides, runtime guides, and beginner startup checklist in one place.
- Use these names inside the installed agent/runtime command surface.
- The bootstrap installer owns Node.js / Python / `venv` prerequisites. The local `gpd` CLI may expose different `gpd ...` subcommands and grouping. Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly.
- Use `gpd validate unattended-readiness --runtime <runtime> --autonomy balanced` for the unattended or overnight verdict, and `gpd permissions sync --runtime <runtime> --autonomy balanced` when runtime-owned permissions need realignment.
- `gpd doctor` checks the selected install target and runtime-local readiness signals. `gpd validate unattended-readiness ...` returns `ready`, `relaunch-required`, `not-ready`, or `unresolved`. Add `--live-executable-probes` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`. `gpd permissions ...` checks runtime-owned approval/alignment only.
- If you need to validate whether a slash-command can run in the current workspace, use `gpd validate command-context gpd:<name>`.
- If a plan declares specialized `tool_requirements`, use `gpd validate plan-preflight <PLAN.md>` from your normal terminal before execution.
- For a normal-terminal, current-workspace read-only recovery snapshot without launching the runtime, use `gpd resume`.
- For cross-project discovery from your normal terminal, use `gpd resume --recent` first, then open the selected project and continue there with the runtime `resume-work` command.
- After resuming inside the runtime, use `/gpd:suggest-next` when you only need the next action.
- For a normal-terminal, read-only machine-local usage / cost summary, use `gpd cost`.

## Quick Start

If you only remember one order, use this: `help -> start -> tour -> new-project / map-research -> resume-work`.
In runtime terms, that means `/gpd:help`, then `/gpd:start`, then `/gpd:tour`, then `/gpd:new-project` or `/gpd:map-research`, and later `/gpd:resume-work` when you return.

After that, choose the path that matches your current situation:

**New work**
1. `/gpd:start` - Guided first-run router when you are not sure whether to create a new project, map existing work, resume, or ask a standalone explanation question
2. `/gpd:tour` - Optional read-only guided tour of the main commands and when to use them
3. `/gpd:new-project` - Full project setup (deep questioning, literature survey, requirements, roadmap)
4. `/gpd:new-project --minimal` - Fast path from a single description to a working GPD project

**Existing work**
1. `/gpd:map-research` - Map an existing folder or project first
2. `/gpd:new-project` - Convert that mapped context into a structured GPD project

**Returning work**
1. `gpd resume` - Current-workspace read-only recovery snapshot from your normal terminal
2. `gpd resume --recent` - Find the workspace first when you need to reopen a different one
3. `/gpd:resume-work` - Continue in-runtime from the selected project state
4. `/gpd:progress` - Secondary manual status check; use `--brief` when you only need a short snapshot
5. `/gpd:suggest-next` - Fastest post-resume next command when you only need the next action
6. `gpd observe execution` - Read-only long-run visibility from your normal terminal; use this for progress / waiting state, conservative `possibly stalled` wording, and the next read-only checks
7. `gpd cost` - Read-only machine-local usage / cost summary from your normal terminal

**Post-startup settings**
1. `/gpd:settings` - Primary guided unattended/autonomy setup after your first successful start or later when you want to choose posture, decide whether to keep runtime defaults or pin tiers, review advisory limits, and sync runtime permissions

**Tangents**
1. `/gpd:tangent` - Chooser for stay / quick / defer / branch when a side investigation appears
2. `/gpd:branch-hypothesis` - Explicit git-backed alternative path with isolated `GPD/` state when the tangent needs to diverge cleanly

If `gpd observe execution` surfaces an alternative-path follow-up, route it through `/gpd:tangent`; use `/gpd:branch-hypothesis` only after that choice.

**Workflow presets**
1. `Paper/manuscript workflows` - First supported workflow preset for `write-paper`, `paper-build`, `peer-review`, and `arxiv-submission`; inspect it with `gpd presets list`, preview it with `gpd presets show <preset>`, and apply it from your normal terminal with `gpd presets apply <preset>` or through your runtime-specific `settings` command
2. `gpd doctor --runtime <runtime> --local|--global` - Check runtime-local paper-toolchain readiness from your normal terminal before using that preset. Add `--live-executable-probes` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`. Failed preset rows degrade `write-paper`, but `paper-build` remains the build contract and `arxiv-submission` requires the built manuscript
3. `gpd presets list` - Inspect the local preset catalog; presets resolve to the existing config keys and do not add a separate persisted preset block
4. `gpd presets show <preset>` - Preview one preset's bundle before applying it
5. `gpd presets apply <preset> [--dry-run]` - Apply or preview one preset from your normal terminal without inventing a separate preset schema

Workflow presets are bundles over the existing config keys only; they do not add a separate persisted preset block.

**Wolfram integration**
1. `gpd integrations status wolfram` - Inspect the shared optional Wolfram integration config only; this does not prove local Mathematica availability or plan readiness, and optional doctor probes do not change that
2. `gpd integrations enable wolfram` - Enable the shared optional Wolfram integration config
3. `gpd integrations disable wolfram` - Disable the shared optional Wolfram integration config

Local Mathematica installs are separate from the shared optional Wolfram integration config.

Workflow preset tooling is layered on top of the base install; it does not change runtime permission alignment.

## What comes later after startup

These are the main capability groups GPD supports once a project is underway:

- Project work: `/gpd:discuss-phase`, `/gpd:plan-phase`, `/gpd:execute-phase`, `/gpd:verify-work`
- Writing and review: `/gpd:write-paper`, `/gpd:peer-review`, `/gpd:respond-to-referees`, `/gpd:arxiv-submission`
- Side investigations and preferences: `/gpd:tangent`, `/gpd:branch-hypothesis`, `/gpd:set-profile`, `/gpd:settings`

## Core Workflow

```
/gpd:new-project -> /gpd:discuss-phase -> /gpd:plan-phase -> /gpd:execute-phase -> /gpd:verify-work -> repeat
```

### Project Initialization

**`/gpd:start`**
Guide a first-time user to the right GPD entry point for the current folder.

- Detects whether the current folder is an existing GPD project, existing non-GPD research, or a new folder
- Recommends the right entry point instead of forcing the user to guess
- Routes into `/gpd:resume-work`, `/gpd:suggest-next`, `/gpd:progress`, `/gpd:tour`, `/gpd:map-research`, `/gpd:new-project`, `/gpd:new-project --minimal`, `/gpd:help --all`, or `/gpd:explain`
- Does not create project artifacts itself; it is an onboarding router

Usage: `/gpd:start`

**`/gpd:tour`**
Show a guided beginner tour of the core GPD commands without taking action.

- Explains the main commands and when to use them
- Stays read-only and does not create files or route into another workflow
- Good optional first stop if you want a quick orientation before choosing a path

Usage: `/gpd:tour`

**`/gpd:new-project`**
Initialize new research project through unified flow.

One command takes you from research idea to ready-for-investigation:

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

Usage: `/gpd:new-project`
Usage: `/gpd:new-project --minimal`
Usage: `/gpd:new-project --minimal @plan.md`

**`/gpd:map-research`**
Map an existing research project — theoretical framework, computations, conventions, and open questions.

- Spawns 4 parallel research-mapper agents to analyze project artifacts
- Creates `GPD/research-map/` with 7 structured documents
- Covers formalism, references, computational architecture, structure, conventions, validation, concerns
- Use before `/gpd:new-project` on existing research projects

Usage: `/gpd:map-research`

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

**`/gpd:discover [phase or topic] [--depth quick|medium|deep]`**
Run discovery phase to investigate methods, literature, and approaches before planning.

- Surveys known results, standard methods, and computational tools
- Depth levels: quick (summary), medium (detailed), deep (comprehensive)
- Creates discovery artifacts consumed by planner or standalone analysis
- Use when entering an unfamiliar subfield or technique

Usage: `/gpd:discover 3`
Usage: `/gpd:discover "finite-temperature RG flow" --depth deep`
Usage: `/gpd:discover 3 --depth deep`

**`/gpd:show-phase <number>`**
Inspect a single phase's artifacts, status, and results.

- Shows phase goal, plans, summaries, and verification status
- Displays frontmatter metadata (wave, dependencies, status)
- Quick way to review what a phase produced

Usage: `/gpd:show-phase 3`

**`/gpd:plan-phase <number>`**
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

Usage: `/gpd:plan-phase 1`
Usage: `/gpd:plan-phase 3 --research`
Usage: `/gpd:plan-phase 5 --light --skip-verify`
Result: Creates `GPD/phases/01-framework-setup/01-01-PLAN.md`

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

Usage: `/gpd:derive-equation "derive the one-loop beta function"`

### Quick Mode

**`/gpd:quick`**
Execute small, ad-hoc calculations with GPD guarantees but skip optional agents.

Quick mode uses the same system with a shorter path:

- Spawns planner + executor (skips literature scout, checker, validator)
- Quick tasks live in `GPD/quick/` separate from planned phases
- Updates STATE.md tracking (not ROADMAP.md)

Use when you know exactly what to calculate and the task is small enough to not need literature survey or validation.

Usage: `/gpd:quick`
Result: Creates `GPD/quick/NNN-slug/PLAN.md`, `GPD/quick/NNN-slug/SUMMARY.md`

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
- Uses `planning.commit_docs` from init to decide whether milestone artifacts are committed immediately

Mirrors `/gpd:new-project` flow for continuation projects (existing PROJECT.md).

Usage: `/gpd:new-milestone "v2.0 Higher-order corrections"`

**`/gpd:complete-milestone <version>`**
Archive completed milestone and prepare for next direction.

- Creates MILESTONES.md entry with results summary
- Archives full details to milestones/ directory
- Creates git tag for the release
- Prepares workspace for next research direction

Usage: `/gpd:complete-milestone 1.1.0`

### Progress Tracking

**`/gpd:progress`**
Check research status and intelligently route to next action.

- Shows visual progress bar and completion percentage
- Summarizes recent work from SUMMARY files
- Displays current position and what's next
- Lists key results and open issues
- Offers to execute next plan or create it if missing
- Detects 100% milestone completion
- Use `--brief` when returning and you only need orientation
- Use `--reconcile` when state appears out of sync with disk artifacts

Usage: `/gpd:progress`
Usage: `/gpd:progress --full` (detailed view with all phase artifacts)
Usage: `/gpd:progress --brief` (compact one-line status)
Usage: `/gpd:progress --reconcile` (fix diverged STATE.md and state.json)

### Session Management

**`/gpd:resume-work`**
Resume research from previous session with full context restoration.

- Restores live execution state, recent progress, and session handoff context through the canonical continuation hierarchy
- Uses the recovery ladder (`gpd resume` -> `gpd resume --recent` when needed -> `/gpd:resume-work`) to pick up where you left off
- Best first in-runtime command when returning to paused or interrupted work
- This is the in-runtime continue path; for a current-workspace read-only recovery snapshot, use `gpd resume`
- If you need to find the workspace first, use `gpd resume --recent`, then continue inside that workspace with `/gpd:resume-work`

Usage: `/gpd:resume-work`

**`/gpd:pause-work`**
Create context handoff when pausing work mid-phase.

- Creates .continue-here file with current state
- Updates STATE.md session continuity section
- Captures in-progress work context
- Run this before leaving mid-phase so `/gpd:resume-work` has an explicit handoff to restore

Usage: `/gpd:pause-work`

### Todo Management

**`/gpd:add-todo [description]`**
Capture idea or task as todo from current conversation.

- Extracts context from conversation (or uses provided description)
- Creates structured todo file in `GPD/todos/pending/`
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
- Maintains debug session state in `GPD/debug/`
- Survives context window resets — resumes from last checkpoint
- Archives resolved issues to `GPD/debug/resolved/`

Usage: `/gpd:debug Sign error in self-energy diagram`

### Physics Validation

**`/gpd:dimensional-analysis`**
Check dimensional consistency of equations and expressions.

- Verifies all terms have consistent units
- Checks final results have correct dimensions
- Flags dimensionless ratios and magic numbers

Usage: `/gpd:dimensional-analysis 3`
Usage: `/gpd:dimensional-analysis results/01-SUMMARY.md`

**`/gpd:limiting-cases`**
Verify results reduce correctly in known limiting cases.

- Tests classical, non-relativistic, weak-coupling, thermodynamic limits
- Compares against textbook expressions in each limit
- Flags limits that are not recovered

Usage: `/gpd:limiting-cases 3`
Usage: `/gpd:limiting-cases results/01-SUMMARY.md`

**`/gpd:numerical-convergence`**
Run systematic convergence tests on numerical computations.

- Tests convergence with grid refinement, time step, basis size
- Estimates convergence order via Richardson extrapolation
- Constructs error budgets for computed quantities

Usage: `/gpd:numerical-convergence 3`
Usage: `/gpd:numerical-convergence results/mesh-study.csv`

**`/gpd:compare-experiment`**
Compare theoretical/numerical results against experimental data.

- Loads published experimental values and error bars
- Computes chi-squared or other goodness-of-fit measures
- Identifies systematic deviations and their possible origins

Usage: `/gpd:compare-experiment predictions.csv experiment.csv`

**`/gpd:compare-results [phase, artifact, or comparison target]`**
Compare internal results, baselines, or methods and emit a decisive verdict.

- Compares phase outputs, artifacts, or named comparison targets
- Surfaces agreement, tension, or failure in a single verdict-oriented view
- Useful when you need to compare internal baselines without reaching for external data

Usage: `/gpd:compare-results 3`
Usage: `/gpd:compare-results results/01-SUMMARY.md`

**`/gpd:validate-conventions [phase]`**
Validate convention consistency across all phases.

- Checks metric signature, Fourier convention, natural units, gauge choice
- Detects convention drift where a symbol is redefined in a later phase
- Cross-checks locked conventions against all phase artifacts
- Scope to a single phase using the optional phase argument, or run across all completed phases

Usage: `/gpd:validate-conventions`
Usage: `/gpd:validate-conventions 3`

**`/gpd:regression-check [phase]`**
Scan-only audit for regressions in already-recorded verification state.

- Detects convention conflicts where the same symbol is redefined with different values across completed SUMMARY artifacts
- Scans `SUMMARY.md` and `VERIFICATION.md` frontmatter rather than re-running numerical or physics verification
- Flags non-passing, invalid, or non-canonical `VERIFICATION.md` statuses in completed phases
- Uses canonical statuses `passed`, `gaps_found`, `expert_needed`, and `human_needed`
- Reports the affected phases and files for follow-up verification or repair
- Scope to a single phase using the optional phase argument, or run across all completed phases

Usage: `/gpd:regression-check`
Usage: `/gpd:regression-check 3`

**`/gpd:health`**
Run project health checks and optionally auto-fix issues.

- Checks state, frontmatter, storage-path policy, and other project health surfaces
- Reports warnings and fixable issues before they become workflow blockers
- Supports `--fix` for automatic repair of common problems

Usage: `/gpd:health`
Usage: `/gpd:health --fix`

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
Usage: `/gpd:sensitivity-analysis --target cross_section --params g,m,Lambda --method numerical`

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
- Drafts the manuscript and uses `gpd paper-build` for the canonical scaffold/build contract
- Spawns gpd-bibliographer to verify all references
- Runs the staged peer-review panel with gpd-referee as final adjudicator
- Supports revision mode for referee responses (bounded 3-iteration loop)

Usage: `/gpd:write-paper "Critical exponents via RG"`
Usage: `/gpd:write-paper --from-phases 1,3,5` (subset of phases)

**`/gpd:peer-review [paper directory or manuscript path]`**
Run skeptical peer review on an existing manuscript within the current GPD project.

- Runs strict review preflight checks against project state, manuscript, artifacts, and reproducibility support
- Loads manuscript files, phase summaries, verification reports, bibliography audit, and artifact manifest
- Spawns a six-agent review panel: reader, literature, math, physics, significance, and final gpd-referee adjudicator
- Produces stage artifacts under `GPD/review/` plus `GPD/REFEREE-REPORT{round_suffix}.md` and `GPD/REFEREE-REPORT{round_suffix}.tex`
- Routes the result to `/gpd:respond-to-referees` or `/gpd:arxiv-submission`
- Requires an initialized `GPD/PROJECT.md` workspace; manuscript paths do not bypass project preflight

Usage: `/gpd:peer-review`
Usage: `/gpd:peer-review paper/`

**`/gpd:respond-to-referees`**
Structure point-by-point response to referee reports and revise the manuscript.

- Parses referee comments into structured items with severity levels
- Drafts both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/paper/REFEREE_RESPONSE{round_suffix}.md` with REF-xxx issue tracking (fixed/rebutted/acknowledged)
- Consumes `GPD/review/REVIEW-LEDGER*.json` and `GPD/review/REFEREE-DECISION*.json` when present to preserve blocking-issue context
- Spawns paper-writer agents for targeted section revisions
- Tracks new calculations required by referees as revision tasks
- Produces response letter from `templates/paper/referee-response.md`
- Bounded revision loop (max 3 iterations with re-review)

Usage: `/gpd:respond-to-referees`

**`/gpd:arxiv-submission`**
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

Usage: `/gpd:arxiv-submission`

**`/gpd:explain [concept]`**
Explain a concept, method, notation, result, or paper in project context or from a standalone question.

- Spawns a `gpd-explainer` agent and grounds the explanation in the active phase, manuscript, or local workflow when available
- Produces a structured explanation under `GPD/explanations/`
- Audits cited papers with `gpd-bibliographer` and includes a reading path with openable links

Usage: `/gpd:explain "Ward identity"`

**`/gpd:suggest-next`**
Suggest the most impactful next action based on current project state.

- Scans phases, plans, verification status, blockers, and todos
- Produces a prioritized action list
- Local CLI fallback: `gpd --raw suggest`
- Fastest way to answer "what should I do next?" without reading through progress reports
- Fastest post-resume command when you only need the next action

Usage: `/gpd:suggest-next`

**`/gpd:literature-review [topic]`**
Structured literature review for a physics research topic.

- Citation network analysis and open question identification
- Spawns `gpd-literature-reviewer` for the structured review
- Spawns gpd-bibliographer agent for citation verification
- Creates structured review with key papers, methods, and gaps

Usage: `/gpd:literature-review "Sachdev-Ye-Kitaev model thermodynamics"`

### Tangents & Hypothesis Branches

**`/gpd:tangent [description]`**
Choose what to do with a possible side investigation without immediately committing to a git branch.

- Acts as the tangent chooser: stay on the current line, do a quick tangent, defer it, or escalate to a branch
- Use when an interesting sub-question appears but you have not yet decided whether it deserves isolated branch state
- Keeps hypothesis branching as an explicit follow-on decision rather than the default for every tangent
- If `gpd observe execution` surfaces an alternative-path follow-up or `branch later` recommendation, run `/gpd:tangent` first rather than skipping straight to `/gpd:branch-hypothesis`

Usage: `/gpd:tangent "Check whether the 2D case is degenerate before branching"`

**`/gpd:branch-hypothesis <description>`**
Create a hypothesis branch for parallel investigation of an alternative approach.

- Creates git branch with isolated `GPD/` state
- Allows exploring alternative methods without disrupting main line
- Use when the tangent should become an explicit git-backed alternative path you intend to compare

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
- Reads from `GPD/DECISIONS.md`

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

> **Note:** Wave dependency validation runs automatically when executing phases. To validate manually, use `gpd phase validate-waves <phase>` — checks depends_on targets, file overlap within waves, wave consistency, and circular dependencies.

**`/gpd:export [--format html|latex|zip|all]`**
Export research results to HTML, LaTeX, or ZIP package.

- HTML: standalone page with MathJax rendering
- LaTeX: document with proper equations and bibliography
- ZIP: complete archive of all planning artifacts

Usage: `/gpd:export --format html`
Usage: `/gpd:export --format all`

**`/gpd:slides [topic, audience, or source path]`**
Create presentation slides from a GPD project or the current folder.

- Audits papers, figures, notes, code, and data to build a talk brief
- Asks targeted questions about audience, duration, format/toolchain, templates, technical depth, and whether to refresh or extend existing slide assets
- Defaults toward Beamer for equation-heavy talks and uses markdown or native decks when that fits better
- Produces an outline plus deck source files in `slides/`

Usage: `/gpd:slides "Group meeting update on finite-temperature RG"`
Usage: `/gpd:slides -- "20 minute seminar for condensed matter theorists"`

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
- Updates `GPD/INSIGHTS.md`

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

Usage: `/gpd:settings`

**`/gpd:set-profile <profile>`**
Quick switch model profile for GPD agents. Use `/gpd:settings` to pin concrete runtime model IDs per tier only if you need explicit control.

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

**`/gpd:help`**
Show this command reference.

## Files & Structure

```
GPD/
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

Set during `/gpd:new-project` or changed later with `/gpd:settings`:

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
- Use only after `/gpd:settings` reports runtime permissions are synchronized and no relaunch is still required

Change anytime with `/gpd:settings`. If it says a relaunch is required, the new autonomy level is not unattended-ready yet.

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
/gpd:new-project        # Unified flow: questioning -> survey -> discuss -> objectives -> roadmap
/clear                  # then run /gpd:discuss-phase 1
/gpd:discuss-phase 1    # Gather context and clarify approach
/clear                  # then run /gpd:plan-phase 1
/gpd:plan-phase 1       # Create plans for first phase
/clear                  # then run /gpd:execute-phase 1
/gpd:execute-phase 1    # Execute all plans in phase
```

**Fast project bootstrap (skip deep questioning):**

```
/gpd:new-project --minimal              # One question, then auto-generate everything
/gpd:new-project --minimal @plan.md     # Generate from existing research plan file
```

**Leaving and returning after a break:**

```
/gpd:pause-work        # Before leaving mid-phase, capture a handoff
/clear                 # then run gpd resume to reopen the current workspace
gpd resume             # Current-workspace read-only recovery snapshot
gpd resume --recent    # Find the workspace first when you need to reopen a different one
/gpd:resume-work       # Continue in-runtime from the selected project state
/gpd:suggest-next      # Fastest post-resume next command when you only need the next action
/gpd:progress --brief  # Short orientation snapshot if you need more context
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
/gpd:insert-phase 5 "Fix sign error in renormalization group equation"
/gpd:plan-phase 5.1
/gpd:execute-phase 5.1
```

**Completing a milestone:**

```
/gpd:complete-milestone 1.1.0
/clear                 # then run /gpd:new-milestone for the next milestone
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

- Read `GPD/PROJECT.md` for research question and framework
- Read `GPD/STATE.md` for current context and key results
- Check `GPD/ROADMAP.md` for phase status
- Run `/gpd:progress` to check where you are
  </reference>

<success_criteria>
- [ ] Available commands listed with descriptions
- [ ] Common workflows shown with examples
- [ ] Quick reference table presented
- [ ] Next action guidance provided based on current project state
</success_criteria>
