# GPD on Windows

GPD adds structured physics-research commands to Claude Code, Codex, Gemini CLI, or OpenCode.

In these docs, "runtime" means the AI terminal app you talk to.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md).

## What you need first

- Windows 10 or 11
- Internet access
- Permission to install software
- Node.js 20 or newer
- Python 3.11 or newer with `venv`
- One supported runtime that already starts from Terminal:
  Claude Code, Codex, Gemini CLI, or OpenCode

## Open a terminal

Use one of these:

- Open the Start menu, type `PowerShell`, then open **Windows PowerShell** or **Terminal**
- Right-click the Start button and choose **Terminal**

If you have a choice, use PowerShell.

## Check Node and Python

Run:

```powershell
node --version
npm --version
npx --version
python --version
py --version
python -m venv --help
```

You want:

- Node `20` or newer
- Python `3.11` or newer
- `python -m venv --help` to print help text instead of an error

If `python` is not recognized, try `py`.

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

After installing either tool, close PowerShell, open a new one, and rerun the version checks.

## Windows-specific runtime notes

- Claude Code on Windows requires Git for Windows or WSL. If you plan to use Claude Code, install Git for Windows first.
- Codex CLI is available on macOS, Windows, and Linux. On Windows, use native PowerShell with the Windows sandbox by default; use WSL2 when your workflow needs Linux-native tools or already lives in WSL2.
- OpenCode's official docs also recommend WSL for the best Windows experience.

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

| Runtime | Install command |
|---------|-----------------|
| Claude Code | `npx -y get-physics-done --claude --local` |
| Codex | `npx -y get-physics-done --codex --local` |
| Gemini CLI | `npx -y get-physics-done --gemini --local` |
| OpenCode | `npx -y get-physics-done --opencode --local` |

## Confirm success

1. In PowerShell, run:

```powershell
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

- Microsoft: [Install Windows Terminal](https://learn.microsoft.com/windows/terminal/install)
- Node.js: [Download Node.js](https://nodejs.org/en/download)
- Python: [Python downloads](https://www.python.org/downloads/)
- Git for Windows: [Download Git for Windows](https://git-scm.com/downloads/win)
- OpenAI: [Codex Windows setup](https://developers.openai.com/codex/windows)
