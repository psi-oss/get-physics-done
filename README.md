# Get Physics Done (GPD)

### Built by physicists, for physicists

<p align="center">
  <a href="https://github.com/psi-oss/get-physics-done/actions/workflows/test.yml"><img alt="CI" src="https://github.com/psi-oss/get-physics-done/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://github.com/psi-oss/get-physics-done/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache_2.0-d4d4d8?style=flat&labelColor=3f3f46"></a>
  <a href="https://www.python.org/downloads/"><img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-ffd43b?style=flat&labelColor=3776ab&logo=python&logoColor=white"></a>
  <a href="https://www.npmjs.com/package/get-physics-done"><img alt="npm" src="https://img.shields.io/npm/v/get-physics-done?style=flat&logo=npm&logoColor=white&labelColor=1f1f1f&color=cb3837"></a>
</p>

<p align="center">
  <a href="#supported-runtimes"><img alt="Claude Code supported" src="https://img.shields.io/badge/Claude%20Code-supported-d97757?style=flat&labelColor=141413&logo=claude&logoColor=faf9f5"></a>
  <a href="#supported-runtimes"><img alt="Codex supported" src="https://img.shields.io/badge/Codex-supported-f5f5f5?style=flat&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyBpZD0iTGF5ZXJfMSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAxNTguNzEyOCAxNTcuMjk2Ij4KICA8IS0tIEdlbmVyYXRvcjogQWRvYmUgSWxsdXN0cmF0b3IgMjkuMi4xLCBTVkcgRXhwb3J0IFBsdWctSW4gLiBTVkcgVmVyc2lvbjogMi4xLjAgQnVpbGQgMTE2KSAgLS0%2BCiAgPHBhdGggZmlsbD0iI0ZGRkZGRiIgZD0iTTYwLjg3MzQsNTcuMjU1NnYtMTQuOTQzMmMwLTEuMjU4Ni40NzIyLTIuMjAyOSwxLjU3MjgtMi44MzE0bDMwLjA0NDMtMTcuMzAyM2M0LjA4OTktMi4zNTkzLDguOTY2Mi0zLjQ1OTksMTMuOTk4OC0zLjQ1OTksMTguODc1OSwwLDMwLjgzMDcsMTQuNjI4OSwzMC44MzA3LDMwLjIwMDYsMCwxLjEwMDcsMCwyLjM1OTMtLjE1OCwzLjYxNzhsLTMxLjE0NDYtMTguMjQ2N2MtMS44ODcyLTEuMTAwNi0zLjc3NTQtMS4xMDA2LTUuNjYyOSwwbC0zOS40ODEyLDIyLjk2NTFaTTEzMS4wMjc2LDExNS40NTYxdi0zNS43MDc0YzAtMi4yMDI4LS45NDQ2LTMuNzc1Ni0yLjgzMTgtNC44NzYzbC0zOS40ODEtMjIuOTY1MSwxMi44OTgyLTcuMzkzNGMxLjEwMDctLjYyODUsMi4wNDUzLS42Mjg1LDMuMTQ1OCwwbDMwLjA0NDEsMTcuMzAyNGM4LjY1MjMsNS4wMzQxLDE0LjQ3MDgsMTUuNzI5NiwxNC40NzA4LDI2LjExMDcsMCwxMS45NTM5LTcuMDc2OSwyMi45NjUtMTguMjQ2MSwyNy41Mjd2LjAwMjFaTTUxLjU5Myw4My45OTY0bC0xMi44OTgyLTcuNTQ5N2MtMS4xMDA3LS42Mjg1LTEuNTcyOC0xLjU3MjgtMS41NzI4LTIuODMxNHYtMzQuNjA0OGMwLTE2LjgzMDMsMTIuODk4Mi0yOS41NzIyLDMwLjM1ODUtMjkuNTcyMiw2LjYwNywwLDEyLjc0MDMsMi4yMDI5LDE3LjkzMjQsNi4xMzQ5bC0zMC45ODcsMTcuOTMyNGMtMS44ODcxLDEuMTAwNy0yLjgzMTQsMi42NzM1LTIuODMxNCw0Ljg3NjR2NDUuNjE1OWwtLjAwMTQtLjAwMTVaTTc5LjM1NjIsMTAwLjA0MDNsLTE4LjQ4MjktMTAuMzgxMXYtMjIuMDIwOWwxOC40ODI5LTEwLjM4MTEsMTguNDgxMiwxMC4zODExdjIyLjAyMDlsLTE4LjQ4MTIsMTAuMzgxMVpNOTEuMjMxOSwxNDcuODU5MWMtNi42MDcsMC0xMi43NDAzLTIuMjAzMS0xNy45MzI0LTYuMTM0NGwzMC45ODY2LTE3LjkzMzNjMS44ODcyLTEuMTAwNSwyLjgzMTgtMi42NzI4LDIuODMxOC00Ljg3NTl2LTQ1LjYxNmwxMy4wNTY0LDcuNTQ5OGMxLjEwMDUuNjI4NSwxLjU3MjMsMS41NzI4LDEuNTcyMywyLjgzMTR2MzQuNjA1MWMwLDE2LjgyOTctMTMuMDU2NCwyOS41NzIzLTMwLjUxNDcsMjkuNTcyM3YuMDAxWk01My45NTIyLDExMi43ODIybC0zMC4wNDQzLTE3LjMwMjRjLTguNjUyLTUuMDM0My0xNC40NzEtMTUuNzI5Ni0xNC40NzEtMjYuMTEwNywwLTEyLjExMTksNy4yMzU2LTIyLjk2NTIsMTguNDAzLTI3LjUyNzJ2MzUuODYzNGMwLDIuMjAyOC45NDQzLDMuNzc1NiwyLjgzMTQsNC44NzYzbDM5LjMyNDgsMjIuODA2OC0xMi44OTgyLDcuMzkzOGMtMS4xMDA3LjYyODctMi4wNDUuNjI4Ny0zLjE0NTYsMFpNNTIuMjIyOSwxMzguNTc5MWMtMTcuNzc0NSwwLTMwLjgzMDYtMTMuMzcxMy0zMC44MzA2LTI5Ljg4NzEsMC0xLjI1ODUuMTU3OC0yLjUxNjkuMzE0My0zLjc3NTRsMzAuOTg3LDE3LjkzMjNjMS44ODcxLDEuMTAwNSwzLjc3NTcsMS4xMDA1LDUuNjYyOCwwbDM5LjQ4MTEtMjIuODA3djE0Ljk0MzVjMCwxLjI1ODUtLjQ3MjEsMi4yMDIxLTEuNTcyOCwyLjgzMDhsLTMwLjA0NDMsMTcuMzAyNWMtNC4wODk4LDIuMzU5LTguOTY2MiwzLjQ2MDUtMTMuOTk4OSwzLjQ2MDVoLjAwMTRaTTkxLjIzMTksMTU3LjI5NmMxOS4wMzI3LDAsMzQuOTE4OC0xMy41MjcyLDM4LjUzODMtMzEuNDU5NCwxNy42MTY0LTQuNTYyLDI4Ljk0MjUtMjEuMDc3OSwyOC45NDI1LTM3LjkwOCwwLTExLjAxMTItNC43MTktMjEuNzA2Ni0xMy4yMTMzLTI5LjQxNDMuNzg2Ny0zLjMwMzUsMS4yNTk1LTYuNjA3LDEuMjU5NS05LjkwOSwwLTIyLjQ5MjktMTguMjQ3MS0zOS4zMjQ3LTM5LjMyNTEtMzkuMzI0Ny00LjI0NjEsMC04LjMzNjMuNjI4NS0xMi40MjYyLDIuMDQ1LTcuMDc5Mi02LjkyMTMtMTYuODMxOC0xMS4zMjU0LTI3LjUyNzEtMTEuMzI1NC0xOS4wMzMxLDAtMzQuOTE5MSwxMy41MjY4LTM4LjUzODQsMzEuNDU5MUMxMS4zMjU1LDM2LjAyMTIsMCw1Mi41MzczLDAsNjkuMzY3NWMwLDExLjAxMTIsNC43MTg0LDIxLjcwNjUsMTMuMjEyNSwyOS40MTQyLS43ODY1LDMuMzAzNS0xLjI1ODYsNi42MDY3LTEuMjU4Niw5LjkwOTIsMCwyMi40OTIzLDE4LjI0NjYsMzkuMzI0MSwzOS4zMjQ4LDM5LjMyNDEsNC4yNDYyLDAsOC4zMzYyLS42Mjc3LDEyLjQyNi0yLjA0NDEsNy4wNzc2LDYuOTIxLDE2LjgzMDIsMTEuMzI1MSwyNy41MjcxLDExLjMyNTFaIi8%2BCjwvc3ZnPg%3D%3D"></a>
  <a href="#supported-runtimes"><img alt="Gemini CLI supported" src="https://img.shields.io/badge/Gemini%20CLI-supported-4285f4?style=flat&labelColor=202124&logo=googlegemini&logoColor=8e75b2"></a>
  <a href="#supported-runtimes"><img alt="OpenCode supported" src="https://img.shields.io/badge/OpenCode-supported-cfcecd?style=flat&labelColor=565656&logo=data%3Aimage%2Fpng%3Bbase64%2CiVBORw0KGgoAAAANSUhEUgAAAGAAAABgCAYAAADimHc4AAABzUlEQVR4AeycQQrCQBAEF1%2Bg6J%2F0o5LPCXmCnnNx0E2nNqGEPciw024VffV0PZ%2FfHo7BqflBCSgAxd%2BaAhQAE4DjbYACYAJwvA1QAEwAjrcBCgAIDBRpA2AZClAATACOtwEKgAnA8TZAATABOD7egNc8tz2ftJ%2B4gPQD9r5fAbDBDQXALx00XgGwGAUoACYAx9sABcAE4HgboACYABxvAxSwJHC7XFryLNP4bzYg7KBar4CKUHiugDDgar0CKkLhuQLCgKv1CqgIhecKCAOu1iugIhSeKyAMuFqvgIpQeK6AMOBq%2FXAC7o9H6z5fdlRAtp4PJ2BrAHSeAmADClAATACOtwEKgAnA8TZAATABON4GKAAmAMev2AD4JTuNVwAsTgEKgAnA8TZAATABON4GKAAmAMfbAAXABOB4G9ApoPe6AnoJdt5XQCfA3uvDCXhOU0ueXmBr3x9OwNoPHH2fAmBDClAATACOtwEKgAnA8TZAAX8QONAVGwDLVIACYAJwfLwByf%2F%2B2WJ32k9cQPoBe9%2BvANigAhQAE4DjbYACYAJw%2FA8NgH%2FpQeMVAItVgAJgAnC8DVAATACOtwEKgAnA8TZAATABON4GFALS4w8AAAD%2F%2Fx7wkLQAAAAGSURBVAMAKj5LkLSa6SQAAAAASUVORK5CYII%3D"></a>
</p>

Get Physics Done is an open-source agentic AI system for physics research from [Physical Superintelligence PBC (PSI)](https://www.psi.inc), released as a community contribution. GPD helps turn a research question into a structured workflow: scope the problem, plan the work, derive results, verify them, and package the output.

https://github.com/user-attachments/assets/e79f8153-c0bd-484f-b69e-da8f142649e0

[Start Here](#start-here) · [Quick Start](#quick-start) · [Supported Runtimes](#supported-runtimes) · [Workflow](#what-gpd-does) · [Commands](#key-in-runtime-commands) · [Models](#optional-model-profiles-and-tier-overrides) · [Advanced CLI](#advanced-cli-utilities) · [System Requirements](#system-requirements)

## Start Here

GPD is not a standalone app. It installs physics-research commands into Claude Code, Codex, Gemini CLI, or OpenCode.

To install GPD, run this in your system terminal:
```bash
# Requires Node.js.
npx -y get-physics-done
```

<details>
<summary><strong>Working from a source checkout?</strong></summary>

If you are developing this repo itself rather than installing the published
bootstrap package, prefer `uv` so the environment is resolved from
`pyproject.toml` and `uv.lock`:

```bash
uv sync --dev
uv run gpd --help
```

After `uv sync --dev`, you can also `source .venv/bin/activate` and run
`gpd ...` directly if you prefer an activated shell. To exercise the public
installer flow from a source checkout, still use the matching `npx -y
get-physics-done` bootstrap command from [Start Here](#start-here).

</details>

<details>
<summary><strong>Need Node.js?</strong></summary>

`npm` and `npx` come with Node.js, so install Node.js first in your normal
system terminal, then come back here.

- Windows: Install Node.js LTS with `winget` (includes `npm` and `npx`): `winget install OpenJS.NodeJS.LTS`
- macOS: Install Node.js with Homebrew (includes `npm` and `npx`): `brew install node`
- Linux (Debian/Ubuntu example): Install Node.js and `npm` from `apt`: `sudo apt-get update && sudo apt-get install -y nodejs npm`

</details>

<details>
<summary><strong>New to terminals?</strong></summary>

If you are new to terminals, start with the [Beginner Onboarding Hub](./docs/README.md).
Use the hub as the single beginner path. It keeps the OS guides, runtime guides,
and post-install checklist in one place, while this README keeps the reference
tables and advanced surfaces.

The hub owns the beginner preflight and caveats: prerequisites, runtime/account
expectations, and the reminder that GPD does not install your runtime or provide
model access, billing, or API credits.

Here, "runtime" means the AI terminal app you talk to, such as Claude Code,
Codex, Gemini CLI, or OpenCode.

There are two places you type commands:

- In your normal system terminal: `npx ...`, `gpd ...`, `claude`, `codex`, `gemini`, `opencode`
- Inside your AI runtime: `/gpd:...`, `$gpd-...`, or `/gpd-...`

</details>


## Who This Is For

GPD is for physics research projects that need more structure than a one-off chat.

It is designed for long-horizon projects that require rigorous verification, structured research memory, multi-step analytical work, complex numerical studies, and manuscript writing or review.

GPD is built to favor scientific rigor and critical thinking over agreeability. Treat preferred explanations as hypotheses to test, and keep missing evidence, failed lookups, and unproduced artifacts explicit instead of inventing them.

We welcome contributions and feedback via GitHub issues or pull requests; if GPD is useful in your work, please star the repo, and share it with colleagues who might benefit.

## Quick Start

If you already know your runtime and are comfortable in a terminal, use this as the fast path. If not, go back to [Start Here](#start-here) and use the [Beginner Onboarding Hub](./docs/README.md) instead.

Use this post-install order:

`help -> start -> tour -> new-project / map-research -> resume-work`

Run its help command first: Claude Code / Gemini CLI use `/gpd:help`. Codex uses `$gpd-help`, and OpenCode uses `/gpd-help`.

Expert fast path:

- From inside the folder where your project should live, install GPD with the matching `npx -y get-physics-done` bootstrap command from [Start Here](#start-here), then launch `claude`, `codex`, `gemini`, or `opencode`.
- Run the matching GPD help command shown in [Supported Runtimes](#supported-runtimes).
- Then use `start` if you are not sure what fits this folder, `tour` for a read-only walkthrough, `new-project --minimal` for new work, `map-research` for existing work, or `resume-work` when you return later.
- Treat the new-work choice as distinct from the existing-work choice; pick one, then follow it through.

The bootstrap installer requires Node.js 20+, Python 3.11+ with `venv`, and one supported runtime (`claude`, `gemini`, `codex`, or `opencode`).

If the install worked, both of these should be true:

1. `gpd --help` works in your normal terminal.
2. Your runtime-specific GPD help command works inside the runtime.

Then choose the path that matches your starting point:

Use the runtime syntax above for the command names below.

| Starting point | Use this |
|----------------|----------|
| Not sure which path fits this folder | `start` |
| Want a guided command walkthrough | `tour` |
| New research project | `new-project --minimal` |
| Existing research folder or codebase | `map-research` |
| Current-workspace recovery snapshot | `gpd resume` |
| Find a workspace to reopen first | `gpd resume --recent`, then `resume-work` |
| Continue in an existing GPD project | `resume-work` |

`gpd resume` is the normal-terminal recovery step; `resume-work` is the in-runtime continue command after the right folder is open.

After resuming, the runtime `suggest-next` command is the fastest post-resume next command when you only need the next action.

<details>
<summary><strong>Optional Terminal-Side Readiness And Troubleshooting Reference</strong></summary>

Use this when you want to verify install health, unattended readiness, paper-toolchain prerequisites, or local CLI surfaces from your normal terminal. If you want the full beginner path, stay with the onboarding hub and your selected OS/runtime guides.

**Bootstrap hard blockers**

- `node` / `npx` work in your normal system terminal
- Python 3.11+ with the standard `venv` module is available in that same terminal
- Your selected runtime is already installed and launchable there (`claude`, `gemini`, `codex`, or `opencode`)

If any of those fail, fix them before troubleshooting GPD itself. These are bootstrap prerequisites for the matching installer command, not a claim that every local `gpd ...` command rechecks them.

**Advisories**

- Choose `--local` or `--global` explicitly if you do not want the installer's default path selection
- Runtime permissions are runtime-owned permission alignment only; use the guided checks after startup to decide whether the runtime is ready.
- Use your runtime-specific `settings` command after the first successful launch as the guided path for unattended configuration. Balanced (`balanced`) is the recommended unattended default.
- For the broader terminal-side diagnostics, readiness, recovery, visibility, cost, and preset surface, start with `gpd --help` from your normal terminal.
- Use `gpd validate unattended-readiness --runtime <runtime> --autonomy balanced` when you want a terminal-side unattended or overnight verdict.
- If you plan paper/manuscript work later, use `gpd doctor --runtime <runtime> --local` for the project-local target or `gpd doctor --runtime <runtime> --global` for the global target first. For the fuller preset catalog, shared Wolfram integration details, and plan-preflight boundaries, use `gpd presets list`, `gpd integrations status wolfram`, and `gpd validate plan-preflight <PLAN.md>` from your normal terminal.
- Provider authentication is checked manually in the runtime itself; GPD will point this out, but it does not hard-block installation readiness on it
- Use `--upgrade` only when you intentionally want the latest unreleased GitHub `main` snapshot

**Quick verification path**

1. Install with an explicit runtime when possible, for example use the matching bootstrap command with `--<runtime-flag> --local`.
2. From the same terminal, run `gpd doctor --runtime <runtime> --local` and `gpd --help`. Add `--live-executable-probes` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`. Here, `gpd doctor --runtime ...` is a runtime-readiness check for the selected runtime target. If you plan to use the paper/manuscript workflow preset later, treat the `Workflow Presets` and `LaTeX Toolchain` rows in this doctor report as paper-toolchain readiness signals for local smoke checks; `write-paper` can still proceed degraded, but `paper-build` is the build truth.
3. Launch your selected runtime and run its GPD help command (`/gpd:help`, `$gpd-help`, or `/gpd-help`).
4. If you want unattended execution, use your runtime-specific `settings` command as the guided configuration path and keep autonomy at Balanced (`balanced`) unless you intentionally want a more hands-off posture.
5. Run `gpd permissions status --runtime <runtime> --autonomy balanced` for the read-only runtime-owned permission snapshot, then run `gpd validate unattended-readiness --runtime <runtime> --autonomy balanced`. If it returns `not-ready`, run `gpd permissions sync --runtime <runtime> --autonomy balanced`; if it returns `relaunch-required`, exit and relaunch the selected runtime before treating unattended use as ready.
6. If those checks pass, continue with the runtime-specific `new-project`, `new-project --minimal`, `resume-work`, or `map-research` command.

**Troubleshooting**

- If the bootstrap installer fails before either `gpd doctor --runtime <runtime> --local` or `gpd doctor --runtime <runtime> --global` can run, fix Node / Python / `venv` bootstrap prerequisites first.
- If the matching `gpd doctor --runtime <runtime> --local` or `gpd doctor --runtime <runtime> --global` command fails, fix the selected runtime's launcher / target / runtime-readiness issue first.
- If that matching doctor command only warns about `Workflow Presets` or `LaTeX Toolchain`, the base install can still be fine; treat that as degraded readiness for `write-paper` and local smoke checks rather than a full install blocker. Use `gpd paper-build` to judge whether the manuscript scaffold is buildable.
- If the runtime launches but GPD commands are missing, rerun the installer with an explicit runtime and explicit scope from your normal system terminal.
- If you want the read-only runtime-owned permission snapshot first, run `gpd permissions status --runtime <runtime> --autonomy balanced`. If `gpd validate unattended-readiness --runtime <runtime> --autonomy balanced` returns `not-ready`, run `gpd permissions sync --runtime <runtime> --autonomy balanced` and check again; if it returns `relaunch-required`, exit and relaunch the runtime before unattended use.
- If the runtime itself cannot launch or is not authenticated, fix the runtime/provider setup outside GPD before retrying the GPD install.

</details>

Typical new-project workflow:

`gpd:new-project -> gpd:discuss-phase 1 -> gpd:plan-phase 1 -> gpd:execute-phase 1 -> gpd:verify-work 1`

<details>
<summary><strong>Install options</strong></summary>

| Flag | Meaning |
|------|---------|
| `--claude`, `--codex`, `--gemini`, `--opencode` | Select one runtime. `--claude-code` and `--gemini-cli` also work. |
| `--all` | Select all supported runtimes. |
| `--local`, `-l` | Use the current project only. |
| `--global`, `-g` | Use the global runtime config dir. |
| `--uninstall` | Uninstall from the selected runtime config instead of installing. |
| `--reinstall` | Reinstall the matching tagged GitHub source into `~/GPD/venv`. |
| `--upgrade` | Upgrade `~/GPD/venv` from the latest GitHub `main` source. |
| `--target-dir <path>` | Override the runtime config directory; defaults to local scope unless the path resolves to that runtime's canonical global config dir. |
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

| Runtime | `npx` flag | Help | Start | Tour | New work | Existing work | Return later |
|---------|------------|------|-------|------|----------|---------------|--------------|
| Claude Code | `--claude` | `/gpd:help` | `/gpd:start` | `/gpd:tour` | `/gpd:new-project --minimal` | `/gpd:map-research` | `/gpd:resume-work` |
| Codex | `--codex` | `$gpd-help` | `$gpd-start` | `$gpd-tour` | `$gpd-new-project --minimal` | `$gpd-map-research` | `$gpd-resume-work` |
| Gemini CLI | `--gemini` | `/gpd:help` | `/gpd:start` | `/gpd:tour` | `/gpd:new-project --minimal` | `/gpd:map-research` | `/gpd:resume-work` |
| OpenCode | `--opencode` | `/gpd-help` | `/gpd-start` | `/gpd-tour` | `/gpd-new-project --minimal` | `/gpd-map-research` | `/gpd-resume-work` |

Each runtime uses its own command prefix, but the workflow is the same across all four. For install-path details, runtime-specific hooks, and launcher notes, use the onboarding hub and the runtime guides in `docs/`.

## What GPD Does

GPD guides research in four stages:

1. **Formulate**: asks targeted questions to pin down scope, assumptions, notation, and verification targets.
2. **Plan**: creates a phased roadmap with concrete tasks, dependencies, and success criteria.
3. **Execute**: runs specialist agents for derivations, numerical checks, literature work, and writing.
4. **Verify**: checks dimensional consistency, limiting cases, symmetry constraints, conservation laws, and numerical stability.

Each phase produces real artifacts such as `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `.tex` derivations, `.py` verification scripts, and figures.

GPD also locks conventions for up to 18 physics fields across a project so notation, sign choices, and verification assumptions stay consistent as phases accumulate.

## How Work Is Structured

GPD's main workflow in `GPD/` is organized like this:

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
gpd:new-project
> Use crossing symmetry and the numerical conformal bootstrap to bound low-lying operator dimensions in the 3D Ising CFT.
```

GPD will:
- ask clarifying questions about the correlator sector, conventions, target observables, numerical precision, and verification strategy
- create `GPD/PROJECT.md`, `GPD/REQUIREMENTS.md`, `GPD/ROADMAP.md`, and `GPD/STATE.md`
- break the work into phases such as crossing-equation setup, derivative-basis construction, semidefinite-program formulation, convergence checks, and interpretation of the resulting bounds

Then continue with:

```text
gpd:plan-phase 1
gpd:execute-phase 1
gpd:verify-work 1
```

Once the relevant phases are complete and verified, continue toward write-up with:

```text
gpd:write-paper "3D Ising bootstrap bounds"
gpd:arxiv-submission
gpd:peer-review
gpd:respond-to-referees
```

Typical artifacts include derivation notes, numerical scripts, convergence studies, and phase-level planning and verification documents under `GPD/`.

</details>

## Key GPD Paths

Most research actions run inside your installed AI runtime after GPD has been installed there. Recovery and diagnostics commands like `gpd resume`, `gpd resume --recent`, and `gpd --help` still run from your normal system terminal. The examples below use Claude Code / Gemini CLI syntax when a runtime command is shown.

### Core Runtime Paths

| Path | Use these commands |
|------|--------------------|
| Start or orient | `start`, `tour` |
| Create or import work | `new-project`, `new-project --minimal`, `map-research` |
| Leave or return after a break | `gpd resume`, `gpd resume --recent`, `resume-work`, `pause-work`, `suggest-next` |
| Run the research loop | `discuss-phase N`, `plan-phase N`, `execute-phase N`, `verify-work`, `progress`, `quick` |
| Write and review | `write-paper`, `peer-review`, `respond-to-referees`, `arxiv-submission` |
| Configure or branch | `settings`, `set-profile`, `set-tier-models`, `tangent`, `branch-hypothesis` |

Typical research loop: `gpd:new-project -> gpd:discuss-phase 1 -> gpd:plan-phase 1 -> gpd:execute-phase 1 -> gpd:verify-work -> repeat -> gpd:complete-milestone`

Typical publication loop: `gpd:write-paper -> gpd:peer-review -> gpd:respond-to-referees -> gpd:arxiv-submission`

Leave / return path: `gpd:pause-work` before leaving mid-phase, `gpd:resume-work` when you return in-runtime, `gpd:suggest-next` when you only need the next action, and `gpd resume` from your normal system terminal for a current-workspace read-only recovery snapshot. Use `gpd resume --recent` first if you need to find the workspace before resuming it, then continue inside that workspace with the runtime `resume-work` command.

### Command Context

Not every GPD command needs the same amount of project state.

| Command type | Meaning | Examples |
|--------------|---------|----------|
| `Projectless` | Can run before `GPD/PROJECT.md` exists | `gpd:start`, `gpd:tour`, `gpd:new-project`, `gpd:map-research`, `gpd:add-todo` |
| `Project-aware` | Uses project context when present, but can also run from explicit standalone inputs | `gpd:discover "finite-temperature RG flow"`, `gpd:explain "Ward identity"`, `gpd:literature-review "axion monodromy"` |
| `Project-required` | Requires initialized GPD project state | `gpd:progress`, `gpd:plan-phase`, `gpd:write-paper`, `gpd:peer-review` |

Passing a manuscript path to a project-required command such as `gpd:peer-review paper/` selects the manuscript target, but does not bypass project initialization.

The full in-runtime reference uses Claude Code / Gemini CLI syntax. Codex uses `$gpd-...` and OpenCode uses `/gpd-...`.

<details>
<summary><strong>Where To Find The Full Runtime Command Reference</strong></summary>

This README is the onboarding and orientation surface, not the complete in-runtime command manual.

- For the full in-runtime command reference, examples, and per-command usage details, run your runtime's help command such as `/gpd:help --all`, `$gpd-help --all`, or `/gpd-help --all`.
- For local CLI commands such as install checks, readiness, validation, permissions, observability, recovery, and diagnostics, run `gpd --help` in your normal system terminal.
Use the runtime-specific `pause-work` command when you want an explicit context handoff to restore on return.

#### Tangents & Hypothesis Branches

Tangents and alternative paths live primarily in `gpd:tangent`, `gpd:branch-hypothesis`, and `gpd:compare-branches`.

| Command | What it does |
|---------|--------------|
| `gpd:tangent [description]` | Choose whether to stay on the main line, run a quick tangent, defer it, or escalate to a git-backed hypothesis branch |
| `gpd:branch-hypothesis <description>` | Create a hypothesis branch for parallel investigation of an alternative approach |
| `gpd:compare-branches` | Compare results across hypothesis branches side-by-side |

- Use the matching `branch-hypothesis` command only when you want the explicit git-backed alternative path.
- If `gpd observe execution` surfaces an alternative-path follow-up or `branch later` recommendation, route it through the runtime `tangent` command first.

</details>

## Optional: Model Profiles And Tier Overrides

GPD maps runtime-specific model names onto three capability tiers. Most users should leave runtime defaults alone and only adjust this if they want to tune planning, execution, or verification behavior.

If you are choosing a posture for the first time:

- `Max quality` means keep the highest-capability options available and pin explicit tiers only when you need consistency.
- `Balanced` means keep the default profile and let the runtime use its own defaults unless you have a reason to override them.
- `Budget-aware` means prefer lighter tiers and only pin explicit runtime models when you need to control cost or access.

Use posture as the starting heuristic, not as a pricing promise. If you need the detailed recorded usage / cost view and advisory USD budget comparison for the workspace, use `gpd cost`.

If you want the simplest direct path for concrete tier ids, use your runtime's `set-tier-models` command. Use `set-profile` for abstract behavior changes, and `settings` for the broader unattended/configuration bundle.

| Tier | Meaning |
|------|---------|
| `tier-1` | Highest capability |
| `tier-2` | Balanced default |
| `tier-3` | Fastest / most economical |

Available profiles are `deep-theory`, `numerical`, `exploratory`, `review`, and `paper-writing`.

| Runtime | Set profile | Set tier models | Open settings |
|---------|-------------|-----------------|---------------|
| Claude Code / Gemini CLI | `/gpd:set-profile review` | `/gpd:set-tier-models` | `/gpd:settings` |
| Codex | `$gpd-set-profile review` | `$gpd-set-tier-models` | `$gpd-settings` |
| OpenCode | `/gpd-set-profile review` | `/gpd-set-tier-models` | `/gpd-settings` |

<details>
<summary><strong>Runtime-specific model string examples</strong></summary>

When you set explicit tier overrides, the model string is runtime-native. GPD passes it through unchanged, so it must match what that runtime already accepts.

- **Claude Code**: use the exact model or deployment identifier accepted by your install.
- **Codex**: use the exact `model` string accepted by your configured provider.
- **Gemini CLI**: use the exact Gemini model name accepted by your install.
- **OpenCode**: use the exact `provider/model` string accepted by your install.

If you are unsure, keep the runtime defaults and tune tiers later through your runtime's `set-tier-models` command.

</details>

<details>
<summary><strong>Manual config example</strong></summary>

Per-project tier settings live in `GPD/config.json` under `model_overrides`:

```json
{
  "model_profile": "review",
  "model_overrides": {
    "codex": {
      "tier-1": "<runtime-native-model-id>",
      "tier-2": "<runtime-native-model-id>",
      "tier-3": "<runtime-native-model-id>"
    },
    "claude-code": {
      "tier-1": "<runtime-native-model-id>",
      "tier-2": "<runtime-native-model-id>",
      "tier-3": "<runtime-native-model-id>"
    },
    "gemini": {
      "tier-1": "<runtime-native-model-id>",
      "tier-2": "<runtime-native-model-id>",
      "tier-3": "<runtime-native-model-id>"
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
| `gpd validate unattended-readiness --runtime <runtime> [--autonomy <mode>]` | Return the unattended or overnight verdict for runtime permission alignment without replacing `gpd doctor` or plan preflight |
| `gpd validate project-contract <file.json or -> [--mode approved|draft]` | Validate a project-scoping contract before downstream artifact generation |
| `gpd validate review-contract <command>` | Show the typed review contract for publication and review workflows |
| `gpd validate review-preflight <command> [subject] --strict` | Check state integrity, manuscript or artifact presence, and review prerequisites |
| `gpd validate paper-quality <file.json>` | Score a structured paper-quality manifest and fail on blocking issues |
| `gpd validate paper-quality --from-project .` | Build paper-quality input from project artifacts, then score it conservatively |
| `gpd validate plan-contract <PLAN.md>` | Validate PLAN frontmatter, including the embedded contract block and ID cross-links |
| `gpd validate plan-preflight <PLAN.md>` | Check optional machine-checkable specialized tool requirements declared by a plan before execution |
| `gpd validate summary-contract <SUMMARY.md>` | Validate summary frontmatter plus contract-result / comparison alignment |
| `gpd validate verification-contract <VERIFICATION.md>` | Validate verification frontmatter plus contract-result / comparison alignment |
| `gpd validate review-ledger <file.json>` | Validate the final staged peer-review issue ledger |
| `gpd validate referee-decision <file.json> [--strict] [--ledger <file.json>]` | Validate a staged peer-review decision against hard recommendation gates and optional ledger consistency |
| `gpd validate reproducibility-manifest <file.json> [--strict] [--kernel-verdict]` | Validate a reproducibility manifest, optionally requiring review-ready coverage or emitting a content-addressed kernel verdict |

</details>

<details>
<summary><strong>Observability and trace inspection</strong></summary>

GPD stores project-local observability under `GPD/observability/` and detailed plan traces under `GPD/traces/`.

| Command | What it does |
|---------|--------------|
| `gpd observe sessions [--status ...] [--command ...] [--last N]` | List recorded observability sessions |
| `gpd observe show [--session ...] [--category ...] [--name ...] [--action ...] [--status ...] [--command ...] [--phase ...] [--plan ...] [--last N]` | Show logged observability events with filters |
| `gpd observe export [--format {jsonl,json,markdown}] [--session ...] [--command ...] [--phase ...] [--last N] [--no-traces] [--output-dir ...]` | Export filtered observability sessions, events, and optional traces to files |
| `gpd observe execution` | Show read-only live execution status for the current workspace, including progress / waiting state, conservative `possibly stalled` wording, and the next read-only checks to run |
| `gpd cost` | Show the read-only machine-local usage / cost summary from recorded local telemetry, optional USD budget guardrails, and the current profile tier mix; advisory only, not live budget enforcement or provider billing truth. If telemetry is missing, the USD view stays partial or estimated rather than exact |
| `gpd observe event <category> <name> [--action ...] [--status ...] [--command ...] [--phase ...] [--plan ...] [--session ...] [--data <json>]` | Append an explicit observability event with optional structured metadata |
| `gpd trace start <phase> <plan>` | Start a plan-local trace session |
| `gpd trace log <event> [--data <json>]` | Append an event to the active trace |
| `gpd trace stop` | Stop the active trace session |
| `gpd trace show [--phase ...] [--plan ...] [--type ...] [--last N]` | Inspect plan-local trace events |

For read-only long-run visibility from your normal system terminal, use `gpd observe execution`.
When the status is uncertain, conservatively say `possibly stalled` instead of relying on runtime hotkeys.
Start with `gpd observe show --last 20` when you need the recent event trail.
If `gpd observe execution` surfaces an alternative-path follow-up or `branch later` recommendation, route it through the runtime `tangent` command first; use the matching `branch-hypothesis` command only when you want the explicit git-backed alternative path.

| Path | What it stores |
|------|----------------|
| `GPD/observability/sessions/*.jsonl` | Per-session event logs |
| `GPD/observability/current-session.json` | Latest session metadata for status and resume tooling |
| `GPD/traces/` | Plan-local execution traces for debugging and post-mortem review |
| `GPD/STATE.md` | Concise human-readable continuity state, not the full event ledger |

Low-level function and span calls are not recorded automatically. Observability is reserved for explicit workflow facts, trace lifecycle, and any agent or subagent events surfaced by the active runtime.

</details>

<details>
<summary><strong>Manuscript build</strong></summary>

| Command | What it does |
|---------|--------------|
| `gpd paper-build [PAPER-CONFIG.json] [--output-dir <dir>]` | Materialize the canonical manuscript scaffold from `paper/PAPER-CONFIG.json`, emit `{topic_specific_stem}.tex`, bibliography artifacts, and the paper artifact manifest |

</details>

## System Requirements

- Node.js with `npm`/`npx` (see the `Need Node.js?` note above if Node.js is missing)
- Python 3.11+ with the standard `venv` module (see the OS guides above for beginner setup steps on macOS, Linux, and Windows)
- Network access to npm and GitHub for the bootstrap installer
- One of: Claude Code, Gemini CLI, Codex, or OpenCode
- API access for the model provider used by your selected runtime

## Known Limitations

- Runtime-internal tool and subagent detail is limited by what the active provider/runtime exposes. GPD records the workflow, session, and trace events it can emit locally, but it does not fabricate opaque provider internals.

## Uninstall

Run the matching uninstall command from [Start Here](#start-here) for interactive uninstall. The equivalent subcommand form also works, and you can add the runtime and scope flags above for a non-interactive uninstall.

Uninstall removes GPD from the selected runtime config only. It does not delete project `GPD/` artifacts or shared files under `~/GPD`; remove `~/GPD/` manually, or `GPD_HOME` if you used it, for a full wipe after uninstalling from all runtimes.

## Inspiration

GPD takes its name in explicit analogy with [GSD (Get Shit Done)](https://github.com/gsd-build/get-shit-done), whose adoption demonstrates how AI-native command workflows can be genuinely useful. GPD takes inspiration from that system to build a sophisticated prompt-engineered agentic system specifically designed for physics research.

## Citation

If GPD contributes to published research, please cite the software using [`CITATION.cff`](https://github.com/psi-oss/get-physics-done/blob/main/CITATION.cff). Copy-ready formats:

```bib
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

If your paper includes an acknowledgements section, use:

```text
This research made use of Get Physics Done (GPD) and was supported in part by a GPD Research Grant from Physical Superintelligence PBC (PSI).
```

## Papers Using GPD

Papers that cite or acknowledge use of GPD. If your paper should be listed here, open a pull request.

- C. Ferko, J. Halverson, V. Jejjala and B. Robinson, *Topological Effects in Neural Network Field Theory* (2026), [arXiv:2604.02313](https://arxiv.org/abs/2604.02313).
- V. G. Filev, *Holographic entanglement entropy, Wilson loops, and neural networks* (2026), [arXiv:2604.05970](https://arxiv.org/abs/2604.05970).

## Star History

<p align="center">
  <a href="https://star-history.com/#psi-oss/get-physics-done&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=psi-oss/get-physics-done&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=psi-oss/get-physics-done&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/image?repos=psi-oss/get-physics-done&type=Date" />
    </picture>
  </a>
</p>

## License

GPD is released under the Apache License 2.0. See [`LICENSE`](https://github.com/psi-oss/get-physics-done/blob/main/LICENSE).
