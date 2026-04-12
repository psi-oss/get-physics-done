# GPD on macOS

GPD adds structured physics-research commands to Claude Code, Codex, Gemini CLI, or OpenCode.

In these docs, "runtime" means the AI terminal app you talk to.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md). This page contains the shared preflight commands, runtime quickstarts, install flags, and follow-up commands; stay on it for those general steps and return here for macOS-specific tips.

## What you need first

- A Mac with internet access and permission to install software.
- Node.js 20 or newer plus Python 3.11 or newer with `venv`; rerun the Onboarding Hub preflight commands after any install to confirm the versions match.
- A supported runtime that already starts from Terminal: Claude Code, Codex, Gemini CLI, or OpenCode. Use the runtime command checks on the Onboarding Hub before installing GPD.

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
- Once the install succeeds, follow the runtime quickstart linked on the Onboarding Hub for Claude Code, Codex, Gemini CLI, or OpenCode.

## Next steps

- Confirm the installer worked by running `gpd --help` in your normal terminal, then run the runtime-specific commands shown in the Onboarding Hub's "After the guides" table (start, tour, resume-work, etc.).
- Use `gpd resume --recent` only when the terminal lists a different recent workspace; open the runtime next and run the matching `resume-work` command from the table.

## Official docs

- Apple: [Get started with Terminal on Mac](https://support.apple.com/guide/terminal/get-started-pht23b129fed/mac)
- Node.js: [Download Node.js](https://nodejs.org/en/download)
- Python: [Python downloads](https://www.python.org/downloads/)
