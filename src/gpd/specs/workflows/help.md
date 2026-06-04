<purpose>
Display the complete GPD command reference. Output ONLY the reference content. Do NOT add project-specific analysis, git status, next-step suggestions, or any commentary beyond the reference.
</purpose>

<reference>
# GPD Command Reference

**GPD** (Get Physics Done) creates hierarchical research plans optimized for solo agentic physics research with AI research agents.

## Startup Checklist

Use the shared README/installer onboarding for prerequisites. Runtime order: `gpd:help` -> `gpd:start` -> `gpd:tour` -> `gpd:new-project` or `gpd:map-research`; return later with `gpd:resume-work`, and tune with `gpd:settings` or `gpd:set-tier-models`.

## Invocation Surfaces

This reference lists the canonical in-runtime command names for the installed runtime's public command surface. Runtime label: Show `gpd:` as native labels; keep local CLI `gpd ...` unchanged. Use `gpd --help` for the executable local install/readiness/permissions/diagnostics surface, `gpd doctor` for runtime readiness, `gpd validate plan-preflight <PLAN.md>` for plan tool requirements, and `gpd validate command-context <name>` as the generic typed command-policy check for the public runtime surface. Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly. Runtime permissions are runtime-owned permission alignment only; use the local CLI for install and runtime-local readiness checks. Today, `gpd validate review-contract <command>` and `gpd validate review-preflight <command> [subject] --strict` are specialized typed surfaces for commands that expose review/publication contracts. New terminal users should start with the Beginner Onboarding Hub linked from the README and installer output.

<!-- gpd-public-surface:local-cli-bridge-summary:start -->
Use `gpd --help` from your normal terminal for the broader local CLI surface: install/readiness checks, typed command validation, permissions, observability, diagnostics, recovery, cost from recorded local telemetry, presets, and shared Wolfram integration.

- `gpd --help`
- `gpd doctor`
- `gpd validate unattended-readiness --runtime <runtime> --autonomy <mode>`
- `gpd permissions status --runtime <runtime> --autonomy <mode>`
- `gpd permissions sync --runtime <runtime> --autonomy <mode>`
- `gpd resume`
- `gpd resume --recent`
- `gpd observe execution`
- `gpd cost`
- `gpd presets list`
- `gpd validate plan-preflight <PLAN.md>`
- `gpd integrations status wolfram`
<!-- gpd-public-surface:local-cli-bridge-summary:end -->

<!-- gpd-public-surface:recovery-note:start -->
Recovery ladder: use `gpd resume` for the current-workspace read-only recovery snapshot. If that is the wrong workspace, use `gpd resume --recent` to find the workspace first, then continue inside that workspace with `resume-work`. After resuming, `suggest-next` is the fastest next command. Before stepping away mid-phase, run `pause-work` so that ladder has an explicit handoff to restore later. Fresh context resets are for context management, not as a recovery step; run `gpd resume` in your normal terminal only when workspace rediscovery is needed.
<!-- gpd-public-surface:recovery-note:end -->

<!-- gpd-help:quick-start:start -->
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
6. `gpd observe execution` - Read-only progress / waiting state snapshot, conservative `possibly stalled` wording, and the next read-only checks from your normal terminal
7. `gpd cost` - Review recorded local telemetry usage / cost from your normal terminal

**Post-startup settings**
1. `gpd:settings` - Change autonomy, permissions, and broader runtime preferences after your first successful start or later
2. `gpd:set-tier-models` - Pin concrete `tier-1`, `tier-2`, and `tier-3` model ids only

When a side investigation appears later, use `gpd:tangent` first. It is the chooser for stay / quick / defer / branch. Use `gpd:branch-hypothesis` only when that tangent needs its own git-backed branch.
<!-- gpd-help:quick-start:end -->
<!-- gpd-help:command-index:start -->
## Command Index

This is the compact grouped list of runtime commands. For normal-terminal install, readiness, and diagnostics commands, use `gpd --help`.

### Starter commands

- `gpd:help` - Show the quick start or command index
- `gpd:start` - Guided first-run router for the safest first path in the current folder
- `gpd:tour` - Show a read-only overview of the main commands
- `gpd:new-project` - Create a full GPD project
- `gpd:new-project --minimal` - Create a GPD project through the shortest setup path
- `gpd:zen` - Print a short research koan and take no action
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
- `gpd:discover [phase or topic]` - Survey methods, literature, and tools before planning; `quick` is verification-only
- `gpd:show-phase <number>` - Inspect one phase's artifacts and status
- `gpd:route [--frozen=yes|no] [--change=extend|revise] [--layer=new|change]` - Route a scope change to the right milestone/phase workflow
- `gpd:plan-phase <number>` - Build a detailed execution plan for a phase
- `gpd:execute-phase <phase-number> [--gaps-only]` - Run all plans in a phase, or only gap-closure plans
- `gpd:autonomous [--from N]` - Run all remaining phases autonomously (discuss→plan→execute→verify each)
- `gpd:derive-equation` - Run a rigorous derivation workflow from project context or one explicit current-workspace target

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
- `gpd:dimensional-analysis` - Check dimensional consistency for a project phase or one explicit current-workspace file
- `gpd:limiting-cases` - Check known limits for a project phase or one explicit current-workspace file
- `gpd:numerical-convergence` - Run convergence checks for a project phase or one explicit current-workspace artifact
- `gpd:compare-experiment` - Compare results against external data
- `gpd:compare-results` - Compare internal results or baselines and write the verdict under `GPD/comparisons/`
- `gpd:validate-conventions [phase]` - Check notation and convention consistency
- `gpd:regression-check [phase]` - Scan for regressions in recorded verification state
- `gpd:health` - Run project health checks
- `gpd:parameter-sweep [phase | computation anchor]` - Run a structured parameter sweep
- `gpd:sensitivity-analysis` - Rank which inputs matter most from project context or explicit current-workspace flags
- `gpd:error-propagation` - Track uncertainties through a calculation chain

### Knowledge authoring

- `gpd:digest-knowledge [topic|arXiv id|source file|knowledge path]` - Create or update a draft knowledge doc under `GPD/knowledge/` in the current workspace
- `gpd:review-knowledge [knowledge path|knowledge id]` - Review one canonical current-workspace knowledge doc and write its review artifact

### Writing and publication

- `gpd:literature-review [topic or research question]` - Create a structured literature review under `GPD/literature/` in the current workspace
- `gpd:write-paper [--intake path/to/write-paper-authoring-input.json]` - Draft a paper from current project results or one explicit external-authoring intake manifest into the resolved manuscript lane
- `gpd:peer-review [paper directory | manuscript path | explicit artifact path]` - Run the staged review workflow on the current project manuscript or one explicit artifact
- `gpd:respond-to-referees [--manuscript PATH --report PATH | report path | paste]` - Draft referee responses and revise the resolved manuscript root
- `gpd:arxiv-submission [manuscript root or .tex entrypoint]` - Package a built manuscript for arXiv from the resolved GPD-owned manuscript root or entrypoint
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
- `gpd:export [--format html|latex|zip|all] [--commit]` - Export project artifacts; generated text exports are committed only with explicit `--commit`
- `gpd:export-logs [--format jsonl|json|markdown] [--session <id>] [--last N] [--command <label>] [--phase <phase>] [--category <name>] [--no-traces] [--output-dir <path>]` - Export observability logs
- `gpd:error-patterns [category]` - Review common project-specific errors
- `gpd:record-backtrack [--reverted-commit=<sha>] [--trigger=<text>] [--phase=<NN-slug>] [description]` - Capture a backtrack event (what went wrong, what got reverted)
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
<!-- gpd-help:command-index:end -->
<!-- gpd-help:detailed-command-reference:start -->
## Detailed Command Reference

Use `gpd:help --command <name>` when you want the detailed notes for one runtime command at a time.

Core workflow: `gpd:new-project` -> `gpd:discuss-phase` -> `gpd:plan-phase` -> `gpd:execute-phase` -> `gpd:verify-work` -> repeat.

Project-aware technical-analysis lane: `gpd:derive-equation`, `gpd:dimensional-analysis`, `gpd:limiting-cases`, `gpd:numerical-convergence`, `gpd:sensitivity-analysis`, `GPD/analysis/`, and `GPD/sweeps/`. `gpd:graph` and `gpd:error-propagation` are separate commands and are not part of this relaxed current-workspace lane.

The full generated command detail reference is installed at `{GPD_INSTALL_DIR}/references/help/detailed-command-reference.md`; the runtime bridge serves that detail one command at a time.

Current-workspace durable outputs can be created from a project context or outside a project only when the user supplies an explicit derivation target or explicit file path. Parameter and sensitivity helpers keep their explicit flags visible: `--param`, `--range`, `--target`, and `--params`.

**`gpd:new-project`**
Initialize a new physics research project with deep context gathering and PROJECT.md
Usage: `gpd:new-project --minimal`; `gpd:new-project --minimal @file.md`; `gpd:new-project --auto`
Notes: All modes build a scoping contract before downstream artifacts. Blocking gaps get one targeted repair prompt, and scope must be explicitly approved before requirements or roadmap generation. `--minimal @file.md` still repairs blocking gaps and asks for scoping approval. `--auto` follows the configured autonomy gates. `GPD/state.json.bak` and `GPD/state.json.lock` are local recovery/coordination files.

**`gpd:map-research`**
Map existing research project — theoretical framework, computations, conventions, and open questions

**`gpd:resume-work`**
Resume research from previous session with full context restoration
Notes: `state.json.continuation` is the durable authority. Canonical continuation fields define the public resume vocabulary: `active_resume_kind`, `active_resume_origin`, `active_resume_pointer`, `active_bounded_segment`, `derived_execution_head`, `active_resume_result`, `continuity_handoff_file`, `recorded_continuity_handoff_file`, `missing_continuity_handoff_file`, `resume_candidates`.

**`gpd:pause-work`**
Create continuation handoff when pausing research mid-phase

**`gpd:progress [--brief | --full | --reconcile]`**
Check research progress, show context, and route to next action (execute or plan)
Usage: `gpd:progress --full`; `gpd:progress --brief`; `gpd:progress --reconcile`
Notes: The local CLI `gpd progress` is a read-only renderer with `json|bar|table` output. Local CLI: `gpd progress json|bar|table`.

**`gpd:suggest-next`**
Suggest the most impactful next action based on current project state

**`gpd:explain [concept, result, method, notation, or paper]`**
Explain a physics concept rigorously in the context of the active project or a standalone question with an explicit topic
Usage: `gpd:explain "Ward identity"`

**`gpd:discover [phase or topic] [--depth quick|medium|deep]`**
Run discovery phase to investigate methods, literature, and approaches before planning
Usage: `gpd:discover --depth medium "finite-size scaling"`
Notes: Depth quick is verification-only and writes no file; medium and deep write discovery artifacts. Discovery artifacts feed planning or standalone analysis.

**`gpd:show-phase <phase-number>`**
Inspect a single phase's artifacts, status, and results

**`gpd:plan-phase [phase] [--research] [--skip-research] [--gaps] [--skip-verify] [--light] [--inline-discuss]`**
Create detailed execution plan for a phase (PLAN.md) with verification loop
Notes: `--skip-verify` may skip routine verification, but proof-bearing plans still require checker review or an equivalent main-context audit.

**`gpd:execute-phase <phase-number> [--gaps-only]`**
Execute all plans in a phase with wave-based parallelization

**`gpd:verify-work [phase] [--dimensional] [--limits] [--convergence] [--regression] [--all]`**
Verify research results through physics consistency checks

**`gpd:derive-equation [equation or topic to derive]`**
Perform a rigorous physics derivation with systematic verification at each step
Usage: `gpd:derive-equation "effective mass from self-energy"`
Notes: Part of the project-aware technical-analysis lane for explicit current-workspace derivations.

**`gpd:dimensional-analysis [phase number or file path]`**
Systematic dimensional analysis audit on all equations in a derivation or phase
Usage: `gpd:dimensional-analysis results/01-SUMMARY.md`
Notes: Part of the project-aware technical-analysis lane; analysis artifacts belong under GPD/analysis/ when a standalone target is supplied.

**`gpd:limiting-cases [phase number or file path]`**
Systematically identify and verify all relevant limiting cases for a result or phase
Usage: `gpd:limiting-cases results/01-SUMMARY.md`
Notes: Part of the project-aware technical-analysis lane for explicit current-workspace limit checks.

**`gpd:numerical-convergence [phase number or file path]`**
Systematic convergence testing for numerical physics computations
Usage: `gpd:numerical-convergence results/mesh-study.csv`
Notes: Part of the project-aware technical-analysis lane for explicit current-workspace convergence checks.

**`gpd:parameter-sweep [phase | computation anchor] [--param name --range start:end:steps] [--adaptive] [--log]`**
Systematic parameter sweep with parallel execution and result aggregation
Usage: `gpd:parameter-sweep --param beta --range 0.1:1.0`

**`gpd:compare-experiment [prediction, dataset, phase, or comparison target]`**
Systematically compare theoretical predictions with experimental or observational data
Usage: `gpd:compare-experiment data/results.csv`

**`gpd:compare-results [phase, artifact, or comparison target]`**
Compare internal results, baselines, or methods and emit decisive verdicts
Usage: `gpd:compare-results GPD/comparisons/baseline.md`
Notes: Writes a decisive comparison artifact under GPD/comparisons/ for the current workspace.

**`gpd:sensitivity-analysis [--target quantity] [--params p1,p2,...] [--method analytical|numerical]`**
Systematic sensitivity analysis -- which parameters matter most and how uncertainties propagate
Usage: `gpd:sensitivity-analysis --target observable --params alpha,beta --method sobol`
Notes: Part of the project-aware technical-analysis lane for ranking influential inputs from project context or explicit current-workspace flags.

**`gpd:graph`**
Visualize dependency graph across phases and identify gaps
Notes: Complements the technical-analysis lane; use separate commands such as gpd:error-propagation for uncertainty flow.

**`gpd:error-propagation [--target quantity] [--phase-range start:end]`**
Track how uncertainties propagate through multi-step calculations across phases

**`gpd:digest-knowledge [topic|arXiv id|source file|knowledge path]`**
Create or update a draft knowledge document in the current workspace from a topic, source file, arXiv ID, or canonical knowledge path
Usage: `gpd:digest-knowledge "renormalization group fixed points"`; `gpd:digest-knowledge 2401.12345v2`; `gpd:digest-knowledge hep-th/9901001`; `gpd:digest-knowledge ./notes/rg-notes.md`; `gpd:digest-knowledge ./sources/review.docx`; `gpd:digest-knowledge ./data/observables.csv`; `gpd:digest-knowledge GPD/knowledge/K-renormalization-group-fixed-points.md`
Notes: Creates a current-workspace knowledge document draft from a topic, paper, source file, or explicit knowledge path. Example document source: `gpd:digest-knowledge ./sources/review.docx`; example tabular source: `gpd:digest-knowledge ./data/observables.csv`. Knowledge lifecycle states are draft, in_review, stable, and superseded; use gpd:review-knowledge for approval. Stable knowledge enters shared runtime reference surfaces as reviewed background synthesis; it is a separate authority tier and does not override stronger evidence. Resolves one canonical `GPD/knowledge/{knowledge_id}.md` target in the current workspace and stops on ambiguity. Supports an arXiv identifier with accepted prefixes.

**`gpd:review-knowledge [knowledge path or knowledge id]`**
Review a current-workspace knowledge document for approval, changes, or promotion gating
Usage: `gpd:review-knowledge GPD/knowledge/K-example.md`
Notes: Reviews a canonical current-workspace knowledge document using typed approval evidence. Approval can promote stable knowledge; stable and superseded states remain addressable and traceable by canonical path or knowledge id. Writes review artifacts under GPD/knowledge/reviews/.

**`gpd:literature-review [topic or research question]`**
Structured literature review for a physics research topic with citation network analysis and open question identification
Usage: `gpd:literature-review "holographic superconductors"`
Notes: Runs on the current project or an explicit topic: a physics research topic or research question, and writes under GPD/literature/ in the current workspace.

**`gpd:write-paper [--intake path/to/write-paper-authoring-input.json]`**
Structure and write a physics paper from project research results or a bounded external-authoring intake
Usage: `gpd:write-paper`; `gpd:write-paper --intake intake/write-paper-authoring-input.json`
Notes: Uses a bounded external-authoring lane driven by an explicit intake manifest only. GPD-authored outputs live under `GPD/publication/{subject_slug}/...`; `GPD/publication/{subject_slug}/intake/` stores intake/provenance state only. It does not mine arbitrary folders, and embedded external staged-review parity is out of scope. Project-backed review/response/package outputs remain in the resolved GPD manuscript lane.

**`gpd:peer-review [paper directory | manuscript path | explicit artifact path]`**
Conduct a staged six-pass peer review of a manuscript and supporting research artifacts from the current GPD project or an explicit external artifact
Usage: `gpd:peer-review draft.docx`; `gpd:peer-review data/observables.csv`
Notes: Explicit artifact intake follows command-policy supported suffixes for publication-artifact paths. Use `gpd validate artifact-text <path> --output <txt-path>` when explicit artifact text extraction is needed. Project-backed mode uses the resolved manuscript entrypoint before staged review.

**`gpd:respond-to-referees [--manuscript PATH --report PATH | report path | paste]`**
Structure a point-by-point response to referee reports for an explicit manuscript target or the current GPD manuscript
Usage: `gpd:respond-to-referees --manuscript paper/main.tex --report reports/referee-report.md`; `gpd:respond-to-referees reports/referee-report.md`; `gpd:respond-to-referees paste`
Notes: Uses a bounded external-authoring lane when an explicit intake manifest or subject is allowed by command policy. Manuscript edits stay beside the resolved manuscript; GPD-authored response artifacts use the selected GPD roots (`GPD/` and `GPD/review/` for project-backed response rounds, or `GPD/publication/{subject_slug}` plus its `review/` subtree for managed/external subjects).

**`gpd:arxiv-submission [manuscript root or .tex entrypoint]`**
Prepare a GPD-owned manuscript for arXiv submission with validation and packaging
Usage: `gpd:arxiv-submission paper/`
Notes: Packages the GPD-owned manuscript root or a supported .tex entrypoint; it does not package arbitrary external material.

**`gpd:settings`**
Configure autonomy, unattended execution budgets, runtime permission sync, workflow preset bundles, model-cost posture, runtime-specific tier model overrides, review cadence, and git preferences
Notes: Autonomy vocabulary: Supervised, Max quality, Balanced, Budget-aware, runtime defaults, YOLO. Configuration keys include `execution.review_cadence`, `planning.commit_docs`, `git.branching_strategy`, and statuses such as `needs-calculation`; model tiers are `tier-1`, `tier-2`, and `tier-3`. Use `gpd observe execution` and `gpd cost` from the normal terminal for read-only status and usage review.

**`gpd:route [--frozen=yes|no] [--change=extend|revise] [--layer=new|change]`**
Decide whether a scope change is a new phase, a revision, a new milestone, or a milestone completion
Notes: The frozen scope-expansion path renders the ordered compound sequence `gpd:complete-milestone` then `gpd:new-milestone`.

**`gpd:record-backtrack [--reverted-commit=<sha>] [--trigger=<text>] [--phase=<NN-slug>] [description]`**
Record a backtrack event (what went wrong, what got reverted) to the backtracks ledger

**`gpd:compact-state [--force]`**
Archive historical entries from STATE.md to keep it under the 150-line target
Notes: Suggested by `gpd:progress` when STATE.md grows large.

**`gpd:update`**
Update GPD to latest version with changelog display
Notes: Runs the public bootstrap update command for the active runtime. Preserves local modifications via patch backups.
<!-- gpd-help:detailed-command-reference:end -->

### Research Publishing

Publication lane boundary:

- `gpd:write-paper` supports current-project manuscripts plus one bounded external-authoring lane driven by an explicit intake manifest only.
- GPD-authored outputs live under `GPD/publication/{subject_slug}/...`; `GPD/publication/{subject_slug}/intake/` stores intake/provenance state.
- External-lane outputs live under `GPD/publication/{subject_slug}/...`; `GPD/publication/{subject_slug}/manuscript` is the only manuscript/build root, and `GPD/publication/{subject_slug}/intake/` keeps intake/provenance state only.
- It does not mine arbitrary folders or infer claim/evidence bindings from loose notes; embedded external staged-review parity is out of scope.
- `gpd:peer-review` can review the current project manuscript or one explicit subject allowed by its command policy; it remains the standalone follow-on command when the bounded external-authoring lane needs review.
- Project-backed review/response/package outputs stay on the `GPD/` and `GPD/review/` paths. `gpd:respond-to-referees` stays tied to the resolved manuscript root; `gpd:arxiv-submission` packages only a GPD-owned manuscript root or `.tex` entrypoint and does not package arbitrary external material. This is not a full publication-root migration.

### Optional Local CLI Add-Ons

- `gpd doctor --runtime <runtime> --local` / `gpd doctor --runtime <runtime> --global` - Check local/global runtime readiness; add `--live-executable-probes` for cheap executable probes such as `pdflatex`, `tectonic`, or `wolframscript`.
- **Workflow presets** tooling: `gpd presets list`, `gpd presets show <preset>`, `gpd presets apply <preset>`.
- Paper/manuscript workflows can degrade when optional tooling is missing; paper-toolchain readiness may degrade `write-paper` gracefully. `paper-build` remains the build contract, and `arxiv-submission` requires the built manuscript. Probe optional tools with `pdflatex --version`, `tectonic --version`, and `wolframscript -version`.
- Wolfram integration status is separate from plan readiness; it does not replace `gpd validate plan-preflight <PLAN.md>`. Use `gpd integrations enable wolfram` or `gpd integrations disable wolfram` from the local CLI for shared Wolfram integration.

Workflow presets are bundles over the existing config keys only; they do not add a separate persisted preset block. Workflow preset tooling is layered on top of the base install and does not change runtime permission alignment.

### Generated Detail Compatibility Notes

Regression checks scan recorded `SUMMARY` frontmatter, convention conflicts, `VERIFICATION` artifacts, and canonical statuses; they do not rerun full verification workflows. The project-aware technical-analysis lane is documented in the generated detail reference and keeps explicit current-workspace targets plus flags visible: `--param`, `--range`, `--target`, and `--params`.

## Files & Structure

- Core project state: `GPD/PROJECT.md`, `GPD/REQUIREMENTS.md`, `GPD/ROADMAP.md`, `GPD/STATE.md`, `GPD/MILESTONES.md`, `GPD/config.json`.
- Literature and reviewed knowledge: `GPD/literature/`, `GPD/knowledge/`, `GPD/knowledge/reviews/`.
- Existing-work map: `GPD/research-map/` with formalism, references, architecture, structure, conventions, validation, and concerns.
- Work queues and support lanes: `GPD/todos/`, `GPD/debug/`, `GPD/quick/`, `GPD/milestones/`.
- Phase artifacts: `GPD/phases/<phase>/PLAN.md` or `*-PLAN.md`, matching `SUMMARY.md` or `*-SUMMARY.md`, and `*-VERIFICATION.md`.

## Workflow Modes

Set mode during `gpd:new-project` or later with `gpd:settings`.

| Mode | Use when | Boundary |
| --- | --- | --- |
| Supervised | New, high-stakes, or closely reviewed work | Frequent checkpoints and user veto at physics-bearing decisions |
| Balanced | Routine work after you trust the project boundary | Fewer routine pauses; still stops on physics choices, ambiguities, blockers, or scope changes |
| YOLO | Maximum speed after readiness is verified | Least interactive; hard stops and required gates still fire |

Model posture and profile terms include runtime defaults, Max quality, Budget-aware, `tier-1`, `tier-2`, and `tier-3`. Use `gpd:set-tier-models`, `gpd:settings`, and `gpd:discuss-phase` when changing these choices.

If `gpd:settings` says a relaunch is required, the new autonomy level is not unattended-ready yet.

## Planning Configuration

Configure planning artifact commits in `GPD/config.json`:

```json
{
  "execution": { "review_cadence": "dense" },
  "planning": {
    "commit_docs": false
  }
}
```

`planning.commit_docs: true` tracks GPD planning artifacts in git; `false` keeps them local-only. Add `GPD/state.json.bak` and `GPD/state.json.lock` to `.gitignore` when planning docs are tracked; these are local recovery/coordination files.

Related knobs: `execution.review_cadence`, `planning.commit_docs`, and `git.branching_strategy`. Review-cadence surfaces may label calculation-needed stops as `needs-calculation`.

## Common Workflows

- Start: `gpd:start` -> `gpd:tour` -> `gpd:new-project` or `gpd:map-research`; then use fresh context windows for `gpd:discuss-phase 1`, `gpd:plan-phase 1`, and `gpd:execute-phase 1`.
- Fast bootstrap: `gpd:new-project --minimal` or `gpd:new-project --minimal @plan.md`.
- Return: `gpd:pause-work`, then `gpd resume` or `gpd resume --recent` from a normal terminal, then `gpd:resume-work`, `gpd:suggest-next`, or `gpd:progress --brief`.
- Cost/status: `gpd observe execution` and `gpd cost` are read-only machine-local snapshots from recorded local telemetry, optional USD budget guardrails, and the current profile tier mix; cost is advisory only, may be partial or estimated when telemetry is missing, and is not live budget enforcement or provider billing truth.
- Scope changes: `gpd:insert-phase 5 "Fix sign error in renormalization group equation"` -> `gpd:plan-phase 5.1` -> `gpd:execute-phase 5.1`.
- Milestones and todos: `gpd:complete-milestone v2.0`, `gpd:new-milestone`, `gpd:add-todo`, `gpd:check-todos`, `gpd:check-todos numerical`.
- Suggested by `gpd:progress`: run `gpd:compact-state` when state compaction is useful.
- Updates: `gpd:update` runs the public bootstrap update command for the active runtime and preserves local modifications via patch backups.
- Compound route example: ordered compound sequence `gpd:complete-milestone` then `gpd:new-milestone`.

## Getting Help

- Read `GPD/PROJECT.md` for research question and framework
- Read `GPD/STATE.md` for current context and key results
- Check `GPD/ROADMAP.md` for phase status
- Run `gpd:progress` to check where you are
- Run `gpd:start` when you need the safest route for this folder
- Run `gpd:suggest-next` when you only need the next action

<!-- gpd-help:default:start -->
## Quick Start

Choose the path that matches this folder:

**New folder**
1. `gpd:start` - Let GPD inspect the folder and route the safest first step
2. `gpd:new-project` - Create a full GPD project here
3. `gpd:new-project --minimal` - Use the shortest setup path

**Existing research folder**
1. `gpd:map-research` - Map files and context before planning
2. `gpd:new-project` - Turn the mapped context into a full GPD project

**Returning project**
1. `gpd resume` - Reopen this workspace from your normal terminal
2. `gpd resume --recent` - Choose a different recent workspace from your normal terminal
3. `gpd:resume-work` - Continue inside the reopened project's canonical state
<!-- gpd-help:default:end -->
  </reference>

<success_criteria>
- [ ] Available commands listed with descriptions
- [ ] Common workflows shown with examples
- [ ] Quick reference table presented
- [ ] Static reference stays project-independent; current-state routing is delegated to `gpd:start`, `gpd:progress`, or `gpd:suggest-next`
</success_criteria>
