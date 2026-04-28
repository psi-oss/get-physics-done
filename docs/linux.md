# GPD on Linux

GPD adds structured physics-research commands to Claude Code, Codex, Gemini CLI, or OpenCode.

In these docs, "runtime" means the AI terminal app you talk to.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md).

## What you need first

- A Linux machine with internet access
- Permission to install software
- Node.js 20 or newer
- Python 3.11 or newer with `venv`
- One supported runtime that already starts from your terminal:
  Claude Code, Codex, Gemini CLI, or OpenCode

## Open a terminal

Use whichever option matches your desktop:

- On Ubuntu and many GNOME-based desktops, press `Ctrl` + `Alt` + `T`
- Or open your app launcher, type `Terminal`, and press `Enter`
- If you already see a shell prompt, you are in the right place

## Check Node and Python

Run:

```bash
node --version
npm --version
npx --version
python3 --version
python3 -m venv --help
```

You want:

- Node `v20` or newer
- Python `3.11` or newer
- `python3 -m venv --help` to print help text instead of an error

## Install or update missing tools

Linux distributions vary more than macOS or Windows, so use the section that matches your distribution, then rerun the version checks above. The package names below are not enough by themselves: do not continue unless `node --version` reports `v20` or newer. If your distro package installs an older `nodejs`, use the official Node.js package-manager guidance linked below instead.

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
- Then rerun the version checks above.

After installing anything, open a new terminal and rerun the version checks. Seeing `nodejs`, `npm`, and `npx` on your PATH is not sufficient unless the Node version is 20 or newer.

## Linux-specific notes

- Linux package names differ by distribution. If one command here does not match your distro, use the official docs linked below, then come back to the version checks.
- On Ubuntu and Debian, Python is often installed without the `venv` module unless `python3-venv` is installed separately.
- On some distributions, the default `nodejs` package may still be older than Node 20. If that happens, use the official Node.js package-manager guidance linked below and install a newer release before continuing.
- If your distribution packages Python older than 3.11, use a newer distribution release or the official Python downloads page linked below.
- Claude Code's official docs list Ubuntu 20.04+, Debian 10+, and Alpine Linux 3.19+ as supported. If you use Alpine or another musl-based distro, read Anthropic's Linux install notes before continuing.

## Make sure your runtime works

Before installing GPD, confirm that your runtime starts from Terminal:

- Claude Code: `claude --version`
- Codex: `codex --help`
- Gemini CLI: `gemini --help`
- OpenCode: `opencode --help`

Then use the matching runtime guide:

- [Claude Code quickstart](./claude-code.md)
- [Codex quickstart](./codex.md)
- [Gemini CLI quickstart](./gemini-cli.md)
- [OpenCode quickstart](./opencode.md)

## Install GPD

Most beginners should install GPD into one runtime at a time and use `--local`.

Here, `--local` means "install GPD for this project or folder only," so run the install command from inside the folder where you want this research project to live.

| Runtime | Install command |
|---------|-----------------|
| Claude Code | `npx -y get-physics-done --claude --local` |
| Codex | `npx -y get-physics-done --codex --local` |
| Gemini CLI | `npx -y get-physics-done --gemini --local` |
| OpenCode | `npx -y get-physics-done --opencode --local` |

## Confirm success

1. In Terminal, run:

```bash
gpd --help
```

2. Open your runtime and run its GPD help command:

- Claude Code or Gemini CLI: `/gpd:help`
- Codex: `$gpd-help`
- OpenCode: `/gpd-help`

If that works, the install is in good shape. If you are not sure what fits this folder yet, use the runtime-specific `start` command below. If you want a guided overview first, use the runtime-specific `tour` command below.

## Where to go next

Use the exact command for your runtime:

| What you want to do | Claude Code / Gemini CLI | Codex | OpenCode |
|---------------------|--------------------------|-------|----------|
| Not sure which path fits this folder | `/gpd:start` | `$gpd-start` | `/gpd-start` |
| Want a guided overview | `/gpd:tour` | `$gpd-tour` | `/gpd-tour` |
| Start a new project | `/gpd:new-project --minimal` | `$gpd-new-project --minimal` | `/gpd-new-project --minimal` |
| Map an existing folder | `/gpd:map-research` | `$gpd-map-research` | `/gpd-map-research` |
| Rediscover the workspace in your normal terminal | `gpd resume` | `gpd resume` | `gpd resume` |
| Continue in the reopened runtime | `/gpd:resume-work` | `$gpd-resume-work` | `/gpd-resume-work` |

Use `gpd resume` in your normal terminal first. Use `gpd resume --recent` when you need to jump to a different recent workspace before reopening the runtime. After the terminal points you to the right workspace, open your runtime there and use its `resume-work` command to continue inside the project.

## Official docs

- Ubuntu: [Package management](https://ubuntu.com/server/docs/package-management/)
- Node.js: [Download Node.js](https://nodejs.org/en/download)
- Node.js: [Node.js package-manager guidance](https://nodejs.org/en/download/package-manager)
- Python: [Python downloads](https://www.python.org/downloads/)
- Python: [`venv` documentation](https://docs.python.org/3/library/venv.html)
- Anthropic: [Claude Code getting started](https://code.claude.com/docs/en/getting-started)
