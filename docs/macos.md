# GPD on macOS

GPD adds structured physics-research commands to Claude Code, Gemini CLI, Codex, or OpenCode.

In these docs, "runtime" means the AI terminal app you talk to.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md). This page contains the shared preflight commands, runtime quickstarts, install flags, and follow-up commands; stay on it for those general steps and return here for macOS-specific tips.

## What you need first

- A Mac with internet access and permission to install software.
- Node.js 20 or newer plus Python 3.11 or newer with `venv`; rerun the Onboarding Hub preflight commands after any install to confirm the versions match.
- A supported runtime that already starts from Terminal: Claude Code, Gemini CLI, Codex, or OpenCode. Use the runtime command checks on the Onboarding Hub before installing GPD.

Once the shared preflight checks pass, continue with the macOS-specific steps below.

## Open Terminal

1. Press `Command` + `Space`.
2. Type `Terminal`.
3. Press `Return`.

You can also open `Applications > Utilities > Terminal`.

## Install or update missing tools

If Node or Python is missing, the simplest path for most beginners is to use the official installer pages linked below.

If you already use Homebrew, you can also install from Terminal:

```bash
brew install node
brew install python
```

After installing, close Terminal, open it again, and rerun the Onboarding Hub preflight commands.

## macOS runtime notes

- If the runtime command from the Onboarding Hub fails (e.g., `claude --version`), reinstall it or fix the PATH before continuing.
- Install GPD with the runtime flag you plan to use (`npx -y get-physics-done --<flag> --local`) as described on the Onboarding Hub and in `docs/runtime-catalog-reference.md`.
- Once the install succeeds, follow the runtime quickstart linked on the Onboarding Hub for Claude Code, Gemini CLI, Codex, or OpenCode.

## Install GPD

Confirm your chosen runtime command works before installing. Install GPD with `npx -y get-physics-done --<flag> --local`, substituting `<flag>` with the install flag documented in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md). Replace `<flag>` with the install flag documented in the runtime catalog reference, and rerun `python scripts/render_runtime_catalog_table.py` after editing `src/gpd/adapters/runtime_catalog.json` so the table remains the single source of truth.

## Next steps

- Confirm success by running `gpd --help` in your normal terminal, then run the runtime-specific commands shown in the Onboarding Hub's "After the guides" table (start, tour, resume-work, etc.). Use `gpd resume --recent` only when the terminal lists a different recent workspace; open the runtime next and run the matching `resume-work` command from the table.

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

- Apple: [Get started with Terminal on Mac](https://support.apple.com/guide/terminal/get-started-pht23b129fed/mac)
- Node.js: [Download Node.js](https://nodejs.org/en/download)
- Python: [Python downloads](https://www.python.org/downloads/)
