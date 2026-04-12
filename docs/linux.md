# GPD on Linux

GPD adds structured physics-research commands to Claude Code, Gemini CLI, Codex, or OpenCode.

In these docs, "runtime" means the AI terminal app you talk to.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md). This page covers the shared preflight commands, runtime quickstarts, install flags, and post-install commands; keep it open for those steps and return here for Linux-specific guidance.

## What you need first

- A Linux machine with internet access and permission to install software.
- Node.js 20 or newer plus Python 3.11 or newer with `venv`; rerun the Onboarding Hub preflight commands after any install so the versions match the requirements.
- One supported runtime that already starts from your terminal: Claude Code, Gemini CLI, Codex, or OpenCode. Use the runtime command checks on the Onboarding Hub before installing GPD.

Once those shared preflight checks are green, continue with the Linux-specific steps below.

## Open a terminal

Use whichever option matches your desktop:

- On Ubuntu and many GNOME-based desktops, press `Ctrl` + `Alt` + `T`.
- Or open your app launcher, type `Terminal`, and press `Enter`.
- If you already see a shell prompt, you are in the right place.

## Install or update missing tools

Linux distributions vary more than macOS or Windows, so use the section that matches your distribution, then rerun the Onboarding Hub preflight commands above.

Ubuntu or Debian:

```bash
sudo apt update
sudo apt install nodejs npm python3 python3-venv
```

Fedora:

```bash
sudo dnf install nodejs npm python3
```

Other Linux distributions:

- Use your distribution's normal package manager to install Node.js, Python 3, and Python virtual-environment support.
- Then rerun the Onboarding Hub preflight commands above.

After installing anything, open a new terminal and rerun the version checks.

## Linux-specific notes

- Linux package names differ by distribution. If one command here does not match your distro, use the official docs linked below, then come back to the version checks.
- On Ubuntu and Debian, Python is often installed without the `venv` module unless `python3-venv` is installed separately.
- On some distributions, the default `nodejs` package may still be older than Node 20. If that happens, use the official Node.js package-manager guidance linked below and install a newer release before continuing.
- If your distribution packages Python older than 3.11, use a newer distribution release or the official Python downloads page linked below.
- Claude Code's official docs list Ubuntu 20.04+, Debian 10+, and Alpine Linux 3.19+ as supported. If you use Alpine or another musl-based distro, read Anthropic's Linux install notes before continuing.

## Install GPD

Confirm your chosen runtime command works before installing. Install GPD with `npx -y get-physics-done --<flag> --local`, substituting `<flag>` with the install flag documented in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md). Replace `<flag>` with the install flag documented in the runtime catalog reference, and rerun `python scripts/render_runtime_catalog_table.py` after editing `src/gpd/adapters/runtime_catalog.json` so the table remains the single source of truth.

## Next steps

- Confirm success by running `gpd --help` in your normal terminal, then follow the runtime quickstart and the runtime command table in the Onboarding Hub "After the guides" section (start, tour, resume-work, etc.). Use `gpd resume --recent` when you need to jump to a different recent workspace before reopening the runtime; the runtime command table on the Onboarding Hub shows the matching `resume-work` command.

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

- Ubuntu: [Package management](https://ubuntu.com/server/docs/package-management/)
- Node.js: [Download Node.js](https://nodejs.org/en/download)
- Node.js: [Node.js package-manager guidance](https://nodejs.org/en/download/package-manager)
- Python: [Python downloads](https://www.python.org/downloads/)
- Python: [`venv` documentation](https://docs.python.org/3/library/venv.html)
- Anthropic: [Claude Code getting started](https://code.claude.com/docs/en/getting-started)
