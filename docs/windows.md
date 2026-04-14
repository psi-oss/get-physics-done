# GPD on Windows

GPD adds structured physics-research commands to Claude Code, Gemini CLI, Codex, or OpenCode.

In these docs, "runtime" means the AI terminal app you talk to.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md). This page collects the shared preflight commands, runtime quickstarts, install flags, and follow-up commands; keep it handy for those general steps and return here for Windows-specific guidance.

## What you need first

- Windows 10 or 11 with internet access and permission to install software.
- Node.js 20 or newer plus Python 3.11 or newer with `venv`; rerun the Onboarding Hub preflight commands after any install to confirm the versions match the requirements.
- A supported runtime that already starts from Terminal: Claude Code, Gemini CLI, Codex, or OpenCode. Use the runtime command checks on the Onboarding Hub before installing GPD.

Once the shared preflight checks succeed, continue with the Windows-specific sections below.

## Open a terminal

Use one of these:

- Open the Start menu, type `PowerShell`, then open **Windows PowerShell** or **Terminal**.
- Right-click the Start button and choose **Terminal**.
- If you have a choice, use PowerShell.

## Install or update missing tools

If Node or Python is missing, the simplest path for most beginners is to use the official installer pages linked below.

If you prefer to install from PowerShell and `winget` is available:

- If Node is missing, run:

```powershell
winget install OpenJS.NodeJS.LTS
```

- If Python is missing, run:

```powershell
winget install Python.Python.3.11
```

After installing either tool, close PowerShell, open a new one, and rerun the Onboarding Hub preflight commands.

## Windows-specific runtime notes

- Claude Code on Windows requires Git for Windows or WSL. If you plan to use Claude Code, install Git for Windows first.
- Codex support on Windows remains experimental; for the smoothest Codex experience, use WSL.
- OpenCode's official docs also recommend WSL for the best Windows experience.
- Install GPD with the runtime flag you plan to use (`npx -y get-physics-done --<flag> --local`) as described on the Onboarding Hub and in `docs/runtime-catalog-reference.md`.
- Once the install succeeds, follow the runtime quickstart linked on the Onboarding Hub for your runtime.

## Install GPD

Confirm your chosen runtime command works before installing. Install GPD with `npx -y get-physics-done --<flag> --local`, substituting `<flag>` with the install flag documented in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md). Replace `<flag>` with the install flag documented in the runtime catalog reference, and rerun `python scripts/render_runtime_catalog_table.py` after editing `src/gpd/adapters/runtime_catalog.json` so the table remains the single source of truth.

## Next steps

- Confirm success by running `gpd --help` in PowerShell, then follow the runtime-specific commands listed in the Onboarding Hub's "After the guides" table (start, tour, resume-work, etc.). Use `gpd resume --recent` only when the terminal points to a different recent workspace; open the runtime there and run the matching `resume-work` command from the table.

The onboarding hub's table lists the same commands below:

- Not sure which path fits this folder? `/gpd:start`, `$gpd-start`, or `/gpd-start`.
- Want a guided overview? `/gpd:tour`, `$gpd-tour`, or `/gpd-tour`.
- Start a new project: `/gpd:new-project --minimal`, `$gpd-new-project --minimal`, or `/gpd-new-project --minimal`.
- Map an existing folder with `/gpd:map-research`, `$gpd-map-research`, or `/gpd-map-research`.
- Rediscover the workspace in your normal terminal with `gpd resume`, or use `gpd resume --recent` before reopening the runtime.
- Continue in the reopened runtime with `/gpd:resume-work`, `$gpd-resume-work`, or `/gpd-resume-work`.

## Runtime quickstarts

- [Claude Code quickstart](./claude-code.md)
- [Codex quickstart](./codex.md)
- [Gemini CLI quickstart](./gemini-cli.md)
- [OpenCode quickstart](./opencode.md)

## Official docs

- Microsoft: [Install Windows Terminal](https://learn.microsoft.com/windows/terminal/install)
- Node.js: [Download Node.js](https://nodejs.org/en/download)
- Python: [Python downloads](https://www.python.org/downloads/)
- Git for Windows: [Download Git for Windows](https://git-scm.com/downloads)
