# Get Physics Done (GPD)

### Built by physicists, for physicists

[![CI](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml/badge.svg)](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml)

Get Physics Done is an open-source AI copilot for physics research from [Physical Superintelligence](https://github.com/physicalsuperintelligence) (PSI), released as a community contribution. GPD helps turn a research question into a structured workflow: scope the problem, plan the work, derive results, verify them, and package the output.

This README is the primary public guide for installing and using GPD. Contributor notes live in [`CONTRIBUTING.md`](https://github.com/physicalsuperintelligence/get-physics-done/blob/main/CONTRIBUTING.md).

If GPD is useful in your work, please star the repo and share it with other physicists who might benefit from it.

## Inspiration

GPD takes its name in explicit analogy with [GSD (Get Shit Done)](https://github.com/gsd-build/get-shit-done), whose adoption and companion packages such as `get-shit-done-cc` helped show that AI-native command workflows can be genuinely useful in practice. GPD takes inspiration from that workflow success while focusing the system specifically on physics research.

## Install

Bootstrap prerequisites:

- Node.js with `npm`/`npx`
- Python 3.11+ with the standard `venv` module
- Network access to GitHub and PyPI

Install GPD with `npx`:

```bash
npx -y get-physics-done@latest
```

Or install directly from GitHub:

```bash
npx -y github:physicalsuperintelligence/get-physics-done
```

The `-y` skips npm's package-install confirmation prompt. That command checks for Python 3.11+, creates or reuses a managed environment under `~/.gpd/venv`, installs the companion `get-physics-done` Python release targeted by the current bootstrap package, and then runs the runtime installer.

If you want to skip the prompts, pass the runtime selection and scope directly:

```bash
npx -y get-physics-done@latest --claude --global
```

To install every supported runtime in one pass:

```bash
npx -y get-physics-done@latest --all --global
```

For a project-local install instead of a global one:

```bash
npx -y get-physics-done@latest --codex --local
```

To refresh an existing managed environment, you can either reinstall the matching release or upgrade directly from the latest GitHub `main` source:

```bash
npx -y get-physics-done@latest --reinstall --claude --local
npx -y get-physics-done@latest --upgrade --claude --local
```

`--reinstall` force-reinstalls that companion Python package version into `~/.gpd/venv`. `--upgrade` force-reinstalls from the latest GitHub `main` branch, which is useful when the bootstrap repo has moved ahead of the current PyPI release.

## Uninstall

Use the same `npx` bootstrap entrypoint to remove GPD:

```bash
npx -y get-physics-done@latest --uninstall
```

That opens the uninstall flow, lets you choose the runtime and scope, and asks for a final confirmation before removing anything. You can also preselect the runtime and scope directly:

```bash
npx -y get-physics-done@latest --uninstall --claude --global
npx -y get-physics-done@latest --uninstall --codex --local
npx -y get-physics-done@latest --uninstall --all --global
```

This removes GPD from the selected runtime config. It does not delete your project's `.gpd/` research artifacts or the shared files under `~/.gpd`. If you want a full wipe after uninstalling from all runtimes, remove `~/.gpd/` manually, or use `GPD_HOME` if you installed GPD there.

## Supported Runtimes

GPD currently installs into four AI runtimes. To preselect one during install, use the matching `npx` flag, or use `--all` to install everything in one pass:

| Runtime | `npx` flag | Help command | Start command |
|---------|------------|--------------|---------------|
| Claude Code | `--claude` | `/gpd:help` | `/gpd:new-project` |
| Gemini CLI | `--gemini` | `/gpd:help` | `/gpd:new-project` |
| Codex | `--codex` | `$gpd-help` | `$gpd-new-project` |
| OpenCode | `--opencode` | `/gpd-help` | `/gpd-new-project` |

Runtime syntax differs slightly, but the workflow is the same across all four.

After installing GPD, open your chosen runtime normally and use the installed GPD commands there.
Claude Code and Gemini CLI use `/gpd:...`, Codex installs `$gpd-...` skills, and OpenCode uses `/gpd-...`.

Gemini-specific note:
- GPD writes `.gemini/settings.json` during install, enables `experimental.enableAgents`, and configures the required hooks and built-in MCP servers as part of a complete Gemini setup.

## What GPD Does

GPD guides research in four stages:

1. **Formulate**: asks targeted questions to pin down scope, assumptions, notation, and verification targets.
2. **Plan**: creates a phased roadmap with concrete tasks, dependencies, and success criteria.
3. **Execute**: runs specialist agents for derivations, numerical checks, literature work, and writing.
4. **Verify**: checks dimensional consistency, limiting cases, symmetry constraints, conservation laws, and numerical stability.

Each phase produces real artifacts such as `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `.tex` derivations, `.py` verification scripts, and figures.

GPD also locks conventions for up to 18 physics fields across a project so notation, sign choices, and verification assumptions stay consistent as phases accumulate.

## How Work Is Structured

GPD's main workflow in `.gpd/` is organized like this:

```text
Project
└── Milestone (v1.0, v1.1, v2.0, ...)
    └── Phase (1, 2, 2.1, 3, ...)
        └── Plan (01-01, 01-02, ...)
            └── Task
```

During execution, plans are grouped into waves:

```text
Wave 1: plans with no unmet dependencies
Wave 2: plans that depend on wave 1 outputs
Wave 3: plans that depend on earlier waves
```

- **Project**: the overall research workspace and its persistent context.
- **Milestone**: a major research checkpoint such as a paper submission, revision cycle, or result package. One project can have multiple milestones.
- **Phase**: one coherent chunk of work inside a milestone. Integer phases are planned work; decimal phases like `2.1` are inserted later when urgent work appears.
- **Plan**: the detailed execution breakdown for a phase, created by the runtime-specific `plan-phase N` command.
- **Wave**: not a separate top-level planning object, but the execution order inside a phase. Plans in the same wave can run in parallel; later waves depend on earlier ones.

Phase numbers continue across the whole project, so a new milestone may start at `Phase 6` rather than resetting to `Phase 1`.

## Example

```text
> /gpd:new-project        # Claude Code / Gemini CLI
> $gpd-new-project        # Codex
> /gpd-new-project        # OpenCode
> Derive the equations of motion for a double pendulum using Lagrangian mechanics

GPD will:
- Ask clarifying questions about scope, notation, and verification targets
- Create PROJECT.md, REQUIREMENTS.md, ROADMAP.md, and STATE.md
- Break the work into phases such as kinematics, Euler-Lagrange equations, and numerical checks
- Produce derivations and Python verification scripts as artifacts
```

## Key In-Runtime Commands

These commands run inside your installed AI runtime after GPD has been installed there. The syntax below uses Claude Code and Gemini CLI form (`/gpd:...`); for Codex use `$gpd-...`, and for OpenCode use `/gpd-...`.

### Common Starting Points

| Command | What it does |
|---------|--------------|
| `new-project` | Start a new research project |
| `plan-phase N` | Plan phase `N` with task breakdown and checkpoints |
| `execute-phase N` | Execute all tasks in phase `N` |
| `verify-work` | Run verification checks against current work |
| `peer-review` | Run manuscript peer review inside the current project before submission |
| `progress` | Show project state and recommend the next step |
| `discuss-phase N` | Explore a phase before committing to a plan |
| `quick` | Run a smaller task with a lighter workflow |
| `write-paper` | Draft a manuscript from completed research artifacts |
| `respond-to-referees` | Structure referee responses and revise the manuscript |
| `arxiv-submission` | Validate and package the manuscript for arXiv |

Typical research loop: `/gpd:new-project -> /gpd:plan-phase -> /gpd:execute-phase -> /gpd:verify-work -> repeat -> /gpd:complete-milestone`

Typical publication loop: `/gpd:write-paper -> /gpd:peer-review -> /gpd:respond-to-referees -> /gpd:arxiv-submission`

### Command Context

Not every GPD command needs the same amount of project state.

- `Projectless` commands can run before `.gpd/PROJECT.md` exists. Examples: `/gpd:new-project`, `/gpd:map-theory`, `/gpd:add-todo`.
- `Project-aware` commands use project context when present, but can also run from explicit standalone inputs. Examples: `/gpd:discover "finite-temperature RG flow"`, `/gpd:explain "Ward identity"`, `/gpd:literature-review "axion monodromy"`, `/gpd:sensitivity-analysis --target ... --params ...`.
- `Project-required` commands depend on initialized GPD state and fail closed without a project. Examples: `/gpd:progress`, `/gpd:plan-phase`, `/gpd:write-paper`, `/gpd:peer-review`.

Passing a manuscript path to a project-required command such as `/gpd:peer-review paper/` selects the manuscript target, but does not bypass project initialization.

### Full Command Reference (59 Commands)

#### Project Initialization

- `/gpd:new-project` — Initialize a new physics research project with deep context gathering and `PROJECT.md`
- `/gpd:map-theory` — Map existing research project: theoretical framework, computations, conventions, and open questions

#### Phase Planning

- `/gpd:discuss-phase <number>` — Gather phase context through adaptive questioning before planning
- `/gpd:research-phase <number>` — Research how to tackle a phase (standalone; usually use `/gpd:plan-phase` instead)
- `/gpd:list-phase-assumptions <number>` — Surface the AI's assumptions about a phase approach before planning
- `/gpd:discover [phase or topic] [--depth quick|medium|deep]` — Run discovery phase to investigate methods, literature, and approaches before planning
- `/gpd:show-phase <number>` — Inspect a single phase's artifacts, status, and results
- `/gpd:plan-phase <number>` — Create detailed execution plan for a phase (`PLAN.md`) with verification loop

#### Execution

- `/gpd:execute-phase <phase-number>` — Execute all plans in a phase with wave-based parallelization

#### Derivation

- `/gpd:derive-equation` — Perform a rigorous physics derivation with systematic verification at each step

#### Quick Mode

- `/gpd:quick` — Execute a quick research task with GPD guarantees (atomic commits, state tracking) but skip optional agents

#### Roadmap Management

- `/gpd:add-phase <description>` — Add research phase to end of current milestone in roadmap
- `/gpd:insert-phase <after> <description>` — Insert urgent research work as a decimal phase (for example `72.1`) between existing phases
- `/gpd:remove-phase <number>` — Remove a future research phase from the roadmap and renumber subsequent phases
- `/gpd:revise-phase <number> "<reason>"` — Supersede a completed phase and create a replacement for iterative revision
- `/gpd:merge-phases <source> <target>` — Merge results from one phase into another

#### Milestone Management

- `/gpd:new-milestone <name>` — Start a new research milestone cycle and route back into requirements and planning
- `/gpd:complete-milestone <version>` — Archive completed research milestone and prepare for the next phase of investigation

#### Progress Tracking

- `/gpd:progress` — Check research progress, show context, and route to the next action (execute or plan)
- `/gpd:suggest-next` — Suggest the most impactful next action based on current project state

#### Research Support

- `/gpd:explain [concept]` — Explain a concept, method, notation, result, or paper rigorously in project context or from a standalone question

#### Session Management

- `/gpd:resume-work` — Resume research from a previous session with full context restoration
- `/gpd:pause-work` — Create a context handoff when pausing research mid-phase

#### Todo Management

- `/gpd:add-todo [description]` — Capture an idea or task as a todo from the current research conversation context
- `/gpd:check-todos [area]` — List pending research todos and select one to work on

#### Validation

- `/gpd:verify-work [phase]` — Verify research results through physics consistency checks

#### Debugging

- `/gpd:debug [issue description]` — Systematic debugging of physics calculations with persistent state across context resets

#### Physics Validation

- `/gpd:dimensional-analysis` — Systematic dimensional analysis audit on all equations in a derivation or phase
- `/gpd:limiting-cases` — Systematically identify and verify all relevant limiting cases for a result or phase
- `/gpd:numerical-convergence` — Systematic convergence testing for numerical physics computations
- `/gpd:compare-experiment` — Systematically compare theoretical predictions with experimental or observational data
- `/gpd:validate-conventions [phase]` — Validate convention consistency across all phases
- `/gpd:regression-check [phase]` — Re-verify all previously verified truths to catch regressions after changes

#### Quantitative Analysis

- `/gpd:parameter-sweep [phase]` — Systematic parameter sweep with parallel execution and result aggregation
- `/gpd:sensitivity-analysis` — Systematic sensitivity analysis on which parameters matter most and how uncertainties propagate
- `/gpd:error-propagation` — Track how uncertainties propagate through multi-step calculations across phases

#### Research Publishing

- `/gpd:write-paper [title or topic] [--from-phases 1,2,3]` — Structure and write a physics paper from research results
- `/gpd:peer-review [paper directory or manuscript path]` — Conduct a skeptical peer review of a manuscript and supporting research artifacts inside the current GPD project
- `/gpd:respond-to-referees` — Structure a point-by-point response to referee reports and update the manuscript
- `/gpd:arxiv-submission` — Prepare a paper for arXiv submission with validation and packaging
- `/gpd:literature-review [topic]` — Structured literature review for a physics research topic with citation network analysis and open question identification

#### Hypothesis Branches

- `/gpd:branch-hypothesis <description>` — Create a hypothesis branch for parallel investigation of an alternative approach
- `/gpd:compare-branches` — Compare results across hypothesis branches side by side

#### Decision Tracking

- `/gpd:decisions [phase or keyword]` — Display and search the cumulative decision log

#### Visualization & Export

- `/gpd:graph` — Visualize the dependency graph across phases and identify gaps
- `/gpd:export [--format html|latex|zip|all]` — Export research results to HTML, LaTeX, or a ZIP package
- `/gpd:error-patterns [category]` — View accumulated physics error patterns for this project
- `/gpd:record-insight [description]` — Record a project-specific learning or pattern to the insights ledger

#### Milestone Auditing

- `/gpd:audit-milestone [version]` — Audit research milestone completion against original research goals
- `/gpd:plan-milestone-gaps` — Create phases to close all gaps identified by the research milestone audit

#### Configuration

- `/gpd:settings` — Configure GPD workflow toggles and physics research preferences
- `/gpd:set-profile <profile>` — Switch research profile for GPD agents (`deep-theory`, `numerical`, `exploratory`, `review`, `paper-writing`)

#### Utility Commands

- `/gpd:compact-state` — Archive historical entries from `STATE.md` to keep it under the 150-line target
- `/gpd:sync-state` — Reconcile diverged `STATE.md` and `state.json` after manual edits or corruption
- `/gpd:undo` — Roll back the last GPD operation with a safety checkpoint
- `/gpd:update` — Update GPD to the latest version with changelog display
- `/gpd:reapply-patches` — Reapply local modifications after a GPD update
- `/gpd:health` — Run project health checks and optionally auto-fix issues
- `/gpd:help` — Show the available GPD commands and usage guide

For full per-command detail and examples inside your runtime, run `/gpd:help --all` or the equivalent runtime-specific help command.

## Validation Commands

The `gpd` CLI also exposes machine-readable validation commands for review-grade workflows:

| Command | What it does |
|---------|--------------|
| `gpd validate command-context <command> [arguments]` | Report whether a command is global, projectless, project-aware, or project-required in the current workspace |
| `gpd validate review-contract <command>` | Show the typed review contract for publication/review workflows |
| `gpd validate review-preflight <command> [subject] --strict` | Check state integrity, manuscript/artifact presence, and review prerequisites |
| `gpd validate paper-quality <file.json>` | Score a structured paper-quality manifest and fail on blocking issues |
| `gpd validate reproducibility-manifest <file.json> --strict` | Validate a reproducibility manifest and require review-ready coverage |

## Local Observability

GPD now keeps a project-local observability trail under `.gpd/observability/` alongside the existing state and trace artifacts.

- `events.jsonl`: append-only project event stream for workflow, command, agent, and verification activity
- `sessions/*.jsonl`: per-session event streams for reconstruction and handoff
- `current-session.json`: latest session metadata for status and resume tooling
- `.gpd/traces/`: plan-local execution traces for detailed debugging and post-mortem review
- STATE.md: concise human-readable continuity state, not the full event ledger

These layers complement each other: traces are narrow and plan-specific, while observability is broader and session-oriented.

## Requirements

- Node.js with `npm`/`npx`
- Python 3.11+ with the standard `venv` module (install a newer version with `brew install python@3.13` on macOS, `pyenv install 3.13` on Linux, or from [python.org](https://www.python.org/downloads/) on Windows)
- Network access to GitHub and PyPI for the bootstrap installer
- One of: Claude Code, Gemini CLI, Codex, or OpenCode
- API access for the model provider used by your selected runtime

## Known Limitations

- Runtime-internal tool and subagent detail is limited by what the active provider/runtime exposes. GPD records the workflow, session, and trace events it can emit locally, but it does not fabricate opaque provider internals.

## Citation

If GPD contributes to published research, please cite the software using [`CITATION.cff`](https://github.com/physicalsuperintelligence/get-physics-done/blob/main/CITATION.cff). Copy-ready formats:

The same file provides the machine-readable CFF metadata used by GitHub's repository citation UI.

```bibtex
@software{physical_superintelligence_2026_gpd,
  author = {Hernandez-Cuenca, Sergio},
  title = {Get Physics Done (GPD)},
  version = {0.1.5},
  year = {2026},
  url = {https://github.com/physicalsuperintelligence/get-physics-done},
  license = {Apache-2.0}
}
```

```text
Hernandez-Cuenca, S. (2026). Get Physics Done (GPD) (Version 0.1.5) [Computer software]. https://github.com/physicalsuperintelligence/get-physics-done
```

## License

GPD is released under the Apache License 2.0. See [`LICENSE`](https://github.com/physicalsuperintelligence/get-physics-done/blob/main/LICENSE).
