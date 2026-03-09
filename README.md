# Get Physics Done (GPD)

[![CI](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml/badge.svg)](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml)

Get Physics Done is an open-source AI copilot for physics research from [Physical Superintelligence (PSI)](https://www.psi.inc), released as a community contribution. Built by physicists, for physicists, GPD helps turn a research question into a structured workflow: scope the problem, plan the work, derive results, verify them, and package the output.

For day-to-day usage, see [`docs/USER-GUIDE.md`](docs/USER-GUIDE.md). For package internals, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Inspiration

GPD takes its name in explicit analogy with [GSD (Get Shit Done)](https://github.com/gsd-build/get-shit-done), whose adoption helped show that AI-native command workflows can be genuinely useful in practice. GPD takes inspiration from that workflow success while focusing the system specifically on physics research.

## Install

Install GPD with `npx`:

```bash
npx github:physicalsuperintelligence/get-physics-done
```

That command checks for Python 3.11+, installs the GPD Python package with the full unified CLI surface (`gpd session`, `gpd pipeline`, and `gpd view`), and then runs the runtime installer.

If you want to skip the prompts, pass the runtime and scope directly:

```bash
npx github:physicalsuperintelligence/get-physics-done --claude --global
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

Each phase produces real artifacts such as `PROJECT.md`, `ROADMAP.md`, `.tex` derivations, `.py` verification scripts, and figures.

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

## Key Commands

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

## Integrated Session And Pipeline

The same `gpd` install also includes the session, MCP pipeline, and frame-viewer features. Use the unified CLI from your shell:

```bash
gpd session
gpd session --history
gpd pipeline discover "lattice QCD phase transition"
gpd view
```

`gpd session` launches an interactive Claude Code session with MCP orchestration and the standard GPD command surface available inside it. `gpd pipeline` and `gpd view` are regular CLI subcommands you can run directly from the terminal.

## Requirements

- Python 3.11+
- One of: Claude Code, Gemini CLI, Codex, or OpenCode
- API access for the model provider used by your selected runtime

## Citation

If GPD contributes to published research, please cite the software using [`CITATION.cff`](CITATION.cff). Copy-ready formats:

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

## Security

To report a security issue, email [security@getphysicsdone.com](mailto:security@getphysicsdone.com). Public vulnerability disclosure guidance lives in [`SECURITY.md`](SECURITY.md).
