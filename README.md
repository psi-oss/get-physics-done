# Get Physics Done (GPD)

### Built by physicists, for physicists

[![CI](https://github.com/psi-oss/get-physics-done/actions/workflows/test.yml/badge.svg)](https://github.com/psi-oss/get-physics-done/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/psi-oss/get-physics-done/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![npm](https://img.shields.io/npm/v/get-physics-done)](https://www.npmjs.com/package/get-physics-done)

Get Physics Done is an open-source AI copilot for physics research from [Physical Superintelligence PBC (PSI)](https://www.psi.inc), released as a community contribution. GPD helps turn a research question into a structured workflow: scope the problem, plan the work, derive results, verify them, and package the output.

https://github.com/user-attachments/assets/e79f8153-c0bd-484f-b69e-da8f142649e0

[Quick Start](#quick-start) · [Supported Runtimes](#supported-runtimes) · [Workflow](#what-gpd-does) · [Commands](#key-in-runtime-commands) · [Models](#optional-model-profiles-and-tier-overrides) · [Advanced CLI](#advanced-cli-utilities) · [System Requirements](#system-requirements)

## Who This Is For

GPD is for hard physics research problems that cannot be handled reliably with manual prompting.

It is designed for long-horizon projects that require rigorous verification, structured research memory, multi-step analytical work, complex numerical studies, and manuscript writing or review.

We welcome contributions and feedback via GitHub issues or pull requests; if GPD is useful in your work, please star the repo, and share it with colleagues who might benefit.

## Quick Start

Install GPD:

```bash
npx -y get-physics-done
```

**Next steps after install**

The installer adds GPD to your runtime config, but it does not launch the runtime for you.

1. Open your chosen runtime from your normal system terminal (`claude` for Claude Code, `gemini` for Gemini CLI, `codex` for Codex, `opencode` for OpenCode).
2. Run its help command first: Claude Code / Gemini CLI use `/gpd:help`, Codex uses `$gpd-help`, and OpenCode uses `/gpd-help`.
3. Start with `new-project` for a fresh research project or `map-research` for an existing folder or project.

For best performance, run both this install step and your chosen runtime from your normal system terminal, not inside the VS Code, Cursor, or other AI runtime command/chat interface.

Then choose the path that matches your starting point:

| Starting point | First command | What it's for |
|----------------|---------------|----------------|
| New research project | `new-project` | Start a fresh GPD research workflow. |
| Existing research folder or codebase | `map-research` | Map existing work before planning. |
| Configure workflow and model defaults | `settings` | Set workflow toggles, tier models, and research preferences. |

Use the runtime-specific command syntax shown in [Supported Runtimes](#supported-runtimes), for example `/gpd:settings` or `/gpd:set-profile review`.

If you are starting from existing work, run `map-research` first to map the formalism, computations, conventions, validation status, and open questions before `new-project`.

Typical new-project workflow:

`new-project -> plan-phase 1 -> execute-phase 1 -> verify-work 1`

<details>
<summary><strong>Install options</strong></summary>

| Flag | Meaning |
|------|---------|
| `--claude`, `--codex`, `--gemini`, `--opencode` | Select one runtime. `--claude-code` and `--gemini-cli` also work. |
| `--all` | Select all supported runtimes. |
| `--local`, `-l` | Use the current project only. |
| `--global`, `-g` | Use the global runtime config dir. |
| `--uninstall` | Uninstall from the selected runtime config instead of installing. |
| `--reinstall` | Reinstall the matching tagged GitHub source into `~/.gpd/venv`. |
| `--upgrade` | Upgrade `~/.gpd/venv` from the latest GitHub `main` source. |
| `--target-dir <path>` | Override the runtime config directory; implies local scope. |
| `--force-statusline` | Replace an existing runtime statusline during install. |
| `--help`, `-h` | Show bootstrap help. |

Ordinary installs stay pinned to the matching tagged release. Use `--upgrade` only when you intentionally want the latest unreleased `main` source.

Install the unreleased GitHub `main` snapshot explicitly:

```bash
npx -y github:psi-oss/get-physics-done --upgrade
```

</details>

## Supported Runtimes

GPD currently installs into four AI runtimes. To preselect one during install, use the matching `npx` flag, or use `--all` to install everything in one pass:

| Runtime | `npx` flag | Help command | Start command |
|---------|------------|--------------|---------------|
| Claude Code | `--claude` | `/gpd:help` | `/gpd:new-project` |
| Codex | `--codex` | `$gpd-help` | `$gpd-new-project` |
| Gemini CLI | `--gemini` | `/gpd:help` | `/gpd:new-project` |
| OpenCode | `--opencode` | `/gpd-help` | `/gpd-new-project` |

Each runtime uses its own command prefix, but the workflow is the same across all four. After installing GPD, open your chosen runtime normally from your system terminal and use the commands shown above.

Notes:
- Claude Code-specific note: GPD writes `.claude/settings.json` for hooks and statusline. MCP servers are added to project `.mcp.json` for local installs or `~/.claude.json` for global installs.
- Codex-specific note: GPD writes `.codex/config.toml` during install, enables `features.multi_agent = true`, configures the required notify hook and built-in MCP servers, registers GPD agent roles in `[agents.*]`, and for local installs exposes only public `gpd-*` agents there as discoverable skills in repo-scoped `.agents/skills/`; the full agent catalog still installs under `.codex/agents/` for direct invocation.
- Codex global skills use `CODEX_SKILLS_DIR` when set, or `~/.agents/skills/` by default.
- Gemini-specific note: GPD writes `.gemini/settings.json` during install, enables `experimental.enableAgents`, configures the required hooks and built-in MCP servers, and installs `policies/gpd-auto-edit.toml` for Gemini auto-edit shell approvals.
- OpenCode-specific note: GPD writes `.opencode/opencode.json` for local installs or `~/.config/opencode/opencode.json` for global installs, installs flat `command/gpd-*.md` files, configures built-in MCP servers under the `mcp` key, and manages GPD-owned `permission.read` / `permission.external_directory` entries.

<details>
<summary><strong>Config path overrides</strong></summary>

| Runtime | Local config dir | Global config dir | Environment overrides |
|---------|------------------|-------------------|-----------------------|
| Claude Code | `./.claude/` | `~/.claude/` | `CLAUDE_CONFIG_DIR` |
| Gemini CLI | `./.gemini/` | `~/.gemini/` | `GEMINI_CONFIG_DIR` |
| Codex | `./.codex/` | `~/.codex/` | `CODEX_CONFIG_DIR`; discoverable global skills use `CODEX_SKILLS_DIR` |
| OpenCode | `./.opencode/` | `~/.config/opencode/` | `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG`, `XDG_CONFIG_HOME` |

GPD respects these overrides during install, uninstall, and runtime detection.

</details>

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

## Worked Example

<details>
<summary><strong>Conformal bootstrap workflow</strong></summary>

The example below uses Claude Code / Gemini CLI syntax.

Suppose you want to use crossing symmetry and the numerical conformal bootstrap to bound low-lying operator dimensions in the 3D Ising CFT.

```text
/gpd:new-project
> Use crossing symmetry and the numerical conformal bootstrap to bound low-lying operator dimensions in the 3D Ising CFT.
```

GPD will:
- ask clarifying questions about the correlator sector, conventions, target observables, numerical precision, and verification strategy
- create `.gpd/PROJECT.md`, `.gpd/REQUIREMENTS.md`, `.gpd/ROADMAP.md`, and `.gpd/STATE.md`
- break the work into phases such as crossing-equation setup, derivative-basis construction, semidefinite-program formulation, convergence checks, and interpretation of the resulting bounds

Then continue with:

```text
/gpd:plan-phase 1
/gpd:execute-phase 1
/gpd:verify-work 1
```

Once the relevant phases are complete and verified, continue toward write-up with:

```text
/gpd:write-paper "3D Ising bootstrap bounds"
/gpd:arxiv-submission
/gpd:peer-review
/gpd:respond-to-referees
```

Typical artifacts include derivation notes, numerical scripts, convergence studies, and phase-level planning and verification documents under `.gpd/`.

</details>

## Key In-Runtime Commands

These commands run inside your installed AI runtime after GPD has been installed there. The examples below use Claude Code / Gemini CLI syntax.

### Common Starting Points

| Command | What it does |
|---------|--------------|
| `map-research` | Map an existing research project before `new-project` |
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

| Command type | Meaning | Examples |
|--------------|---------|----------|
| `Projectless` | Can run before `.gpd/PROJECT.md` exists | `/gpd:new-project`, `/gpd:map-research`, `/gpd:add-todo` |
| `Project-aware` | Uses project context when present, but can also run from explicit standalone inputs | `/gpd:discover "finite-temperature RG flow"`, `/gpd:explain "Ward identity"`, `/gpd:literature-review "axion monodromy"` |
| `Project-required` | Requires initialized GPD project state | `/gpd:progress`, `/gpd:plan-phase`, `/gpd:write-paper`, `/gpd:peer-review` |

Passing a manuscript path to a project-required command such as `/gpd:peer-review paper/` selects the manuscript target, but does not bypass project initialization.

The full command reference below uses Claude Code / Gemini CLI syntax. Codex uses `$gpd-...` and OpenCode uses `/gpd-...`.

<details>
<summary><strong>Full Command Reference (61 Commands)</strong></summary>

#### Project Initialization

| Command | What it does |
|---------|--------------|
| `/gpd:new-project` | Initialize a new physics research project with deep context gathering and `PROJECT.md` |
| `/gpd:map-research` | Map existing research project — theoretical framework, computations, conventions, and open questions |

#### Phase Planning

| Command | What it does |
|---------|--------------|
| `/gpd:discuss-phase <number>` | Gather phase context through adaptive questioning before planning |
| `/gpd:research-phase <number>` | Research how to tackle a phase (standalone - usually use `/gpd:plan-phase` instead) |
| `/gpd:list-phase-assumptions <number>` | Surface the AI's assumptions about a phase approach before planning |
| `/gpd:discover [phase or topic] [--depth {quick,medium,deep}]` | Run discovery phase to investigate methods, literature, and approaches before planning |
| `/gpd:show-phase <number>` | Inspect a single phase's artifacts, status, and results |
| `/gpd:plan-phase <number>` | Create detailed execution plan for a phase (`PLAN.md`) with verification loop |

#### Execution

| Command | What it does |
|---------|--------------|
| `/gpd:execute-phase <phase-number>` | Execute all plans in a phase with wave-based parallelization |

#### Derivation

| Command | What it does |
|---------|--------------|
| `/gpd:derive-equation` | Perform a rigorous physics derivation with systematic verification at each step |

#### Quick Mode

| Command | What it does |
|---------|--------------|
| `/gpd:quick` | Execute a quick research task with GPD guarantees (atomic commits, state tracking) but skip optional agents |

#### Roadmap Management

| Command | What it does |
|---------|--------------|
| `/gpd:add-phase <description>` | Add research phase to end of current milestone in roadmap |
| `/gpd:insert-phase <after> <description>` | Insert urgent research work as decimal phase (for example, `72.1`) between existing phases |
| `/gpd:remove-phase <number>` | Remove a future phase from roadmap and renumber subsequent phases |
| `/gpd:revise-phase <number> "<reason>"` | Supersede a completed phase and create a replacement for iterative revision |
| `/gpd:merge-phases <source> <target>` | Merge results from one phase into another |

#### Milestone Management

| Command | What it does |
|---------|--------------|
| `/gpd:new-milestone <name>` | Start a new research milestone cycle — update `PROJECT.md` and route to requirements |
| `/gpd:complete-milestone <version>` | Archive completed research milestone and prepare for next phase of investigation |

#### Progress Tracking

| Command | What it does |
|---------|--------------|
| `/gpd:progress` | Check research progress, show context, and route to the next action (execute or plan) |
| `/gpd:suggest-next` | Suggest the most impactful next action based on current project state |

#### Research Support

| Command | What it does |
|---------|--------------|
| `/gpd:explain [concept]` | Explain a physics concept rigorously in the context of the active project or standalone question |

#### Session Management

| Command | What it does |
|---------|--------------|
| `/gpd:resume-work` | Resume research from the previous session with full context restoration |
| `/gpd:pause-work` | Create a context handoff when pausing research mid-phase |

#### Todo Management

| Command | What it does |
|---------|--------------|
| `/gpd:add-todo [description]` | Capture an idea or task as a todo from current research conversation context |
| `/gpd:check-todos [area]` | List pending research todos and select one to work on |

#### Validation

| Command | What it does |
|---------|--------------|
| `/gpd:verify-work [phase]` | Verify research results through physics consistency checks |

#### Debugging

| Command | What it does |
|---------|--------------|
| `/gpd:debug [issue description]` | Systematic debugging of physics calculations with persistent state across context resets |

#### Physics Validation

| Command | What it does |
|---------|--------------|
| `/gpd:dimensional-analysis` | Systematic dimensional analysis audit on all equations in a derivation or phase |
| `/gpd:limiting-cases` | Systematically identify and verify all relevant limiting cases for a result or phase |
| `/gpd:numerical-convergence` | Systematic convergence testing for numerical physics computations |
| `/gpd:compare-experiment` | Systematically compare theoretical predictions with experimental or observational data |
| `/gpd:validate-conventions [phase]` | Validate convention consistency across all phases |
| `/gpd:regression-check [phase]` | Re-verify all previously verified truths to catch regressions after changes |

#### Quantitative Analysis

| Command | What it does |
|---------|--------------|
| `/gpd:parameter-sweep [phase]` | Systematic parameter sweep with parallel execution and result aggregation |
| `/gpd:sensitivity-analysis` | Systematic sensitivity analysis — which parameters matter most and how uncertainties propagate |
| `/gpd:error-propagation` | Track how uncertainties propagate through multi-step calculations across phases |
| `/gpd:compare-results [phase, artifact, or comparison target]` | Compare internal results, baselines, or methods and emit decisive verdicts |

#### Research Publishing

| Command | What it does |
|---------|--------------|
| `/gpd:write-paper [title or topic] [--from-phases 1,2,3]` | Structure and write a physics paper from research results |
| `/gpd:peer-review [paper directory or manuscript path]` | Conduct a staged six-pass peer review of a manuscript and supporting research artifacts in the current GPD project |
| `/gpd:respond-to-referees` | Structure a point-by-point response to referee reports and update the manuscript |
| `/gpd:arxiv-submission` | Prepare a paper for arXiv submission with validation and packaging |
| `/gpd:literature-review [topic]` | Structured literature review for a physics research topic with citation network analysis and open question identification |

#### Hypothesis Branches

| Command | What it does |
|---------|--------------|
| `/gpd:branch-hypothesis <description>` | Create a hypothesis branch for parallel investigation of an alternative approach |
| `/gpd:compare-branches` | Compare results across hypothesis branches side-by-side |

#### Decision Tracking

| Command | What it does |
|---------|--------------|
| `/gpd:decisions [phase or keyword]` | Display and search the cumulative decision log |

#### Visualization & Export

| Command | What it does |
|---------|--------------|
| `/gpd:graph` | Visualize dependency graph across phases and identify gaps |
| `/gpd:slides [topic]` | Create presentation slides from a GPD project or the current folder |
| `/gpd:export [--format {html,latex,zip,all}]` | Export research results to HTML, LaTeX, or ZIP package |
| `/gpd:error-patterns [category]` | View accumulated physics error patterns for this project |
| `/gpd:record-insight [description]` | Record a project-specific learning or pattern to the insights ledger |

#### Milestone Auditing

| Command | What it does |
|---------|--------------|
| `/gpd:audit-milestone [version]` | Audit research milestone completion against original research goals |
| `/gpd:plan-milestone-gaps` | Create phases to close all gaps identified by research milestone audit |

#### Configuration

| Command | What it does |
|---------|--------------|
| `/gpd:settings` | Configure GPD workflow toggles, tier models, and physics research preferences |
| `/gpd:set-profile <profile>` | Switch research profile for GPD agents (`deep-theory`, `numerical`, `exploratory`, `review`, `paper-writing`) |

#### Utility Commands

| Command | What it does |
|---------|--------------|
| `/gpd:compact-state` | Archive historical entries from `STATE.md` to keep it under the 150-line target |
| `/gpd:sync-state` | Reconcile diverged `STATE.md` and `state.json` after manual edits or corruption |
| `/gpd:undo` | Roll back the last GPD operation with a safety checkpoint |
| `/gpd:update` | Update GPD to the latest version with changelog display |
| `/gpd:reapply-patches` | Reapply local modifications after a GPD update |
| `/gpd:health` | Run project health checks and optionally auto-fix issues |
| `/gpd:help` | Show available GPD commands and usage guide |

For full per-command detail and examples inside your runtime, run `/gpd:help --all` or the equivalent runtime-specific help command.

</details>

## Optional: Model Profiles And Tier Overrides

GPD maps runtime-specific model names onto three capability tiers. Most users can leave this at the runtime default and only adjust it if they want to tune planning, execution, or verification behavior.

| Tier | Meaning |
|------|---------|
| `tier-1` | Highest capability |
| `tier-2` | Balanced default |
| `tier-3` | Fastest / most economical |

Available profiles are `deep-theory`, `numerical`, `exploratory`, `review`, and `paper-writing`.

| Runtime | Set profile | Open settings |
|---------|-------------|---------------|
| Claude Code / Gemini CLI | `/gpd:set-profile review` | `/gpd:settings` |
| Codex | `$gpd-set-profile review` | `$gpd-settings` |
| OpenCode | `/gpd-set-profile review` | `/gpd-settings` |

<details>
<summary><strong>Runtime-specific model string examples</strong></summary>

When you set explicit tier overrides, the model string is runtime-native. GPD passes it through unchanged, so it must match what that runtime already accepts:

- **Claude Code**: aliases like `opus`, `sonnet`, `haiku`, `default`, `sonnet[1m]`, or a provider-native pinned model ID. If your Claude Code install is backed by Bedrock, Vertex, or Foundry, use that provider's deployment/version identifier.
- **Codex**: the exact string Codex accepts for its `model` setting. If you configured a non-default Codex `model_provider`, keep that provider's exact model ID format.
- **Gemini CLI**: an exact Gemini model name accepted by your installed Gemini runtime. Prefer exact model names for GPD tier overrides rather than the interactive Auto picker.
- **OpenCode**: a full `provider/model` string such as `anthropic/<model>`, `openai/<model>`, or `google/<model>`.

</details>

<details>
<summary><strong>Manual config example</strong></summary>

Per-project tier settings live in `.gpd/config.json` under `model_overrides`:

```json
{
  "model_profile": "review",
  "model_overrides": {
    "codex": {
      "tier-1": "your-tier-1-codex-model",
      "tier-2": "your-tier-2-codex-model",
      "tier-3": "your-tier-3-codex-model"
    },
    "claude-code": {
      "tier-1": "opus",
      "tier-2": "sonnet",
      "tier-3": "haiku"
    },
    "gemini": {
      "tier-1": "your-tier-1-gemini-model",
      "tier-2": "your-tier-2-gemini-model",
      "tier-3": "your-tier-3-gemini-model"
    }
  }
}
```

Valid runtime keys are `claude-code`, `codex`, `gemini`, and `opencode`. If no override is set for the active runtime, GPD uses that runtime's default model.

</details>

## Advanced CLI Utilities

The `gpd` CLI also includes machine-readable validation, observability, and tracing commands for automation, review-grade checks, and debugging.

<details>
<summary><strong>Validation commands</strong></summary>

| Command | What it does |
|---------|--------------|
| `gpd validate consistency` | Run cross-phase consistency and project health checks for the current workspace |
| `gpd validate command-context <command> [arguments]` | Report whether a command is global, projectless, project-aware, or project-required in the current workspace |
| `gpd validate project-contract <file.json or -> [--mode approved|draft]` | Validate a project-scoping contract before downstream artifact generation |
| `gpd validate review-contract <command>` | Show the typed review contract for publication and review workflows |
| `gpd validate review-preflight <command> [subject] --strict` | Check state integrity, manuscript or artifact presence, and review prerequisites |
| `gpd validate paper-quality <file.json>` | Score a structured paper-quality manifest and fail on blocking issues |
| `gpd validate paper-quality --from-project .` | Build paper-quality input from project artifacts, then score it conservatively |
| `gpd validate plan-contract <PLAN.md>` | Validate PLAN frontmatter, including the embedded contract block and ID cross-links |
| `gpd validate summary-contract <SUMMARY.md>` | Validate summary frontmatter plus contract-result / comparison alignment |
| `gpd validate verification-contract <VERIFICATION.md>` | Validate verification frontmatter plus contract-result / comparison alignment |
| `gpd validate review-ledger <file.json>` | Validate the final staged peer-review issue ledger |
| `gpd validate referee-decision <file.json> [--strict] [--ledger <file.json>]` | Validate a staged peer-review decision against hard recommendation gates and optional ledger consistency |
| `gpd validate reproducibility-manifest <file.json> [--strict] [--kernel-verdict]` | Validate a reproducibility manifest, optionally requiring review-ready coverage or emitting a content-addressed kernel verdict |

</details>

<details>
<summary><strong>Observability and trace inspection</strong></summary>

GPD stores project-local observability under `.gpd/observability/` and detailed plan traces under `.gpd/traces/`.

| Command | What it does |
|---------|--------------|
| `gpd observe sessions [--status ...] [--command ...] [--last N]` | List recorded observability sessions |
| `gpd observe show [--session ...] [--category ...] [--name ...] [--action ...] [--status ...] [--command ...] [--phase ...] [--plan ...] [--last N]` | Show logged observability events with filters |
| `gpd observe event <category> <name> [--action ...] [--status ...] [--command ...] [--phase ...] [--plan ...] [--session ...] [--data <json>]` | Append an explicit observability event with optional structured metadata |
| `gpd trace start <phase> <plan>` | Start a plan-local trace session |
| `gpd trace log <event> [--data <json>]` | Append an event to the active trace |
| `gpd trace stop` | Stop the active trace session |
| `gpd trace show [--phase ...] [--plan ...] [--type ...] [--last N]` | Inspect plan-local trace events |

| Path | What it stores |
|------|----------------|
| `.gpd/observability/sessions/*.jsonl` | Per-session event logs |
| `.gpd/observability/current-session.json` | Latest session metadata for status and resume tooling |
| `.gpd/traces/` | Plan-local execution traces for debugging and post-mortem review |
| `.gpd/STATE.md` | Concise human-readable continuity state, not the full event ledger |

Low-level function and span calls are not recorded automatically. Observability is reserved for explicit workflow facts, trace lifecycle, and any agent or subagent events surfaced by the active runtime.

</details>

<details>
<summary><strong>Manuscript build</strong></summary>

| Command | What it does |
|---------|--------------|
| `gpd paper-build [PAPER-CONFIG.json] [--output-dir <dir>]` | Materialize the canonical manuscript scaffold from `paper/PAPER-CONFIG.json`, emit `main.tex`, bibliography artifacts, and the paper artifact manifest |

</details>

## System Requirements

- Node.js with `npm`/`npx`
- Python 3.11+ with the standard `venv` module (install a newer version with `brew install python@3.13` on macOS, `pyenv install 3.13` on Linux, or from [python.org](https://www.python.org/downloads/) on Windows)
- Network access to npm and GitHub for the bootstrap installer
- One of: Claude Code, Gemini CLI, Codex, or OpenCode
- API access for the model provider used by your selected runtime

## Known Limitations

- Runtime-internal tool and subagent detail is limited by what the active provider/runtime exposes. GPD records the workflow, session, and trace events it can emit locally, but it does not fabricate opaque provider internals.

## Uninstall

Run `npx -y get-physics-done --uninstall` for interactive uninstall. The equivalent subcommand form `npx -y get-physics-done uninstall` also works, and you can add the runtime and scope flags above for a non-interactive uninstall.

Uninstall removes GPD from the selected runtime config only. It does not delete project `.gpd/` artifacts or shared files under `~/.gpd`; remove `~/.gpd/` manually, or `GPD_HOME` if you used it, for a full wipe after uninstalling from all runtimes.

## Inspiration

GPD takes its name in explicit analogy with [GSD (Get Shit Done)](https://github.com/gsd-build/get-shit-done), whose adoption demonstrates how AI-native command workflows can be genuinely useful. GPD takes inspiration from that system to build a sophisticated prompt-engineered agentic system specifically designed for physics research.

## Citation

If GPD contributes to published research, please cite the software using [`CITATION.cff`](https://github.com/psi-oss/get-physics-done/blob/main/CITATION.cff). Copy-ready formats:

```bibtex
@software{physical_superintelligence_2026_gpd,
  author = {{Physical Superintelligence PBC}},
  title = {Get Physics Done (GPD)},
  version = {1.1.0},
  year = {2026},
  url = {https://github.com/psi-oss/get-physics-done},
  license = {Apache-2.0}
}
```

```text
Physical Superintelligence PBC (2026). Get Physics Done (GPD) (Version 1.1.0). https://github.com/psi-oss/get-physics-done
```

## License

GPD is released under the Apache License 2.0. See [`LICENSE`](https://github.com/psi-oss/get-physics-done/blob/main/LICENSE).
