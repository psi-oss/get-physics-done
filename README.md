# Get Physics Done (GPD)

[![CI](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml/badge.svg)](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml)

Get Physics Done is an open-source AI copilot for physics research from [Physical Superintelligence](https://github.com/physicalsuperintelligence), released as a community contribution. Built by physicists, for physicists, GPD helps turn a research question into a structured workflow: scope the problem, plan the work, derive results, verify them, and package the output.

This README is the primary public guide for installing and using GPD. Contributor notes live in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Inspiration

GPD takes its name in explicit analogy with [GSD (Get Shit Done)](https://github.com/gsd-build/get-shit-done), whose adoption and companion packages such as `get-shit-done-cc` helped show that AI-native command workflows can be genuinely useful in practice. GPD takes inspiration from that workflow success while focusing the system specifically on physics research.

## Install

Bootstrap prerequisites:

- Node.js with `npm`/`npx`
- Python 3.11+ with `pip`
- Network access to GitHub and PyPI

Install GPD with `npx`:

```bash
npx github:physicalsuperintelligence/get-physics-done
```

That command checks for Python 3.11+ and `pip`, installs the matching `get-physics-done` Python release from PyPI with the unified terminal CLI surface (`gpd session` and `gpd view`), and then runs the runtime installer.

If you want to skip the prompts, pass the runtime and scope directly:

```bash
npx github:physicalsuperintelligence/get-physics-done --claude --global
```

For a project-local install instead of a global one:

```bash
npx github:physicalsuperintelligence/get-physics-done --codex --local
```

## Supported Runtimes

GPD currently installs into four AI runtimes. To preselect one during install, use the matching `npx` flag:

| Runtime | `npx` flag | Help command | Start command |
|---------|------------|--------------|---------------|
| Claude Code | `--claude` | `/gpd:help` | `/gpd:new-project` |
| Gemini CLI | `--gemini` | `/gpd:help` | `/gpd:new-project` |
| Codex | `--codex` | `$gpd-help` | `$gpd-new-project` |
| OpenCode | `--opencode` | `/gpd-help` | `/gpd-new-project` |

Runtime syntax differs slightly, but the workflow is the same across all four.

## What GPD Does

GPD guides research in four stages:

1. **Formulate**: asks targeted questions to pin down scope, assumptions, notation, and verification targets.
2. **Plan**: creates a phased roadmap with concrete tasks, dependencies, and success criteria.
3. **Execute**: runs specialist agents for derivations, numerical checks, literature work, and writing.
4. **Verify**: checks dimensional consistency, limiting cases, symmetry constraints, conservation laws, and numerical stability.

Each phase produces real artifacts such as `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `.tex` derivations, `.py` verification scripts, and figures.

GPD also locks conventions for up to 18 physics fields across a project so notation, sign choices, and verification assumptions stay consistent as phases accumulate.

## How Work Is Structured

GPD's main workflow in `.planning/` is organized like this:

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
- **Plan**: the detailed execution breakdown for a phase, created by `/gpd:plan-phase N`.
- **Wave**: not a separate top-level planning object, but the execution order inside a phase. Plans in the same wave can run in parallel; later waves depend on earlier ones.

Phase numbers continue across the whole project, so a new milestone may start at `Phase 6` rather than resetting to `Phase 1`.

## Example

```text
> /gpd:new-project
> Derive the equations of motion for a double pendulum using Lagrangian mechanics

GPD will:
- Ask clarifying questions about scope, notation, and verification targets
- Create PROJECT.md, REQUIREMENTS.md, ROADMAP.md, and STATE.md
- Break the work into phases such as kinematics, Euler-Lagrange equations, and numerical checks
- Produce derivations and Python verification scripts as artifacts
```

## Key In-Runtime Commands

These commands run inside your installed AI runtime after GPD has been installed there.

| Command | What it does |
|---------|--------------|
| `/gpd:new-project` | Start a new research project |
| `/gpd:plan-phase N` | Plan phase `N` with task breakdown and checkpoints |
| `/gpd:execute-phase N` | Execute all tasks in phase `N` |
| `/gpd:verify-work` | Run verification checks against current work |
| `/gpd:progress` | Show project state and recommend the next step |
| `/gpd:discuss-phase N` | Explore a phase before committing to a plan |
| `/gpd:quick` | Run a smaller task with a lighter workflow |

Use the runtime-specific prefix from the table above if you are on Codex or OpenCode.

## Terminal CLI

The same `gpd` install also includes the session launcher and frame viewer. Use the unified CLI from your shell:

```bash
gpd session
gpd session --history
gpd view
```

`gpd session` launches an interactive Claude Code-backed session from your shell with MCP orchestration and the standard GPD command surface available inside it. `gpd view` remains available as a regular CLI subcommand you can run directly from the terminal.

## Requirements

- Node.js with `npm`/`npx`
- Python 3.11+ with `pip` (install a newer version with `brew install python@3.13` on macOS, `pyenv install 3.13` on Linux, or from [python.org](https://www.python.org/downloads/) on Windows)
- Network access to GitHub and PyPI for the bootstrap installer
- One of: Claude Code, Gemini CLI, Codex, or OpenCode
- API access for the model provider used by your selected runtime

## Known Limitations

- The integrated terminal `gpd session` launcher currently supports Claude Code only.
- On Gemini CLI, Codex, and OpenCode, use the installed in-runtime commands directly.
- `gpd view` remains available from the terminal on any install.

## Citation

If GPD contributes to published research, please cite the software using [`CITATION.cff`](CITATION.cff). Copy-ready formats:

The same file provides the machine-readable CFF metadata used by GitHub's repository citation UI.

```bibtex
@software{hernandez_cuenca_2026_gpd,
  author = {Hernandez-Cuenca, Sergio},
  title = {Get Physics Done (GPD)},
  version = {0.1.0},
  year = {2026},
  url = {https://github.com/physicalsuperintelligence/get-physics-done},
  license = {Apache-2.0}
}
```

```text
Hernandez-Cuenca, S. (2026). Get Physics Done (GPD) (Version 0.1.0) [Computer software]. https://github.com/physicalsuperintelligence/get-physics-done
```

## License

GPD is released under the Apache License 2.0. See [`LICENSE`](LICENSE).