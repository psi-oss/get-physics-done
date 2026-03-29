# GPD on Linux

GPD adds structured physics-research commands to Claude Code, Codex, Gemini CLI, or OpenCode.

In these docs, "runtime" means the AI terminal app you talk to.

## What you need first

- A Linux machine with internet access
- Permission to install software
- Node.js 20 or newer
- Python 3.11 or newer with `venv`
- One supported runtime that already starts from Terminal:
  Claude Code, Codex, Gemini CLI, or OpenCode

## Open a terminal

Use whichever method is easiest on your Linux desktop:

- Search your applications for `Terminal`
- On many Linux desktops, press `Ctrl` + `Alt` + `T`
- If you work on a remote Linux machine, open the shell you normally use there

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

If Python is present but `python3 -m venv --help` fails, your distro may be missing the `venv` package.
On Debian or Ubuntu, that is usually fixed with `python3-venv`.

## Install or update missing tools

Linux package names vary by distro. The simplest safe path is:

- Use your distro's normal software installer or package manager
- If your distro only offers an older Node.js version, use the official Node.js downloads page linked below
- If your distro's Python is too old, use your distro's newer package channel or a tool like `pyenv`

Examples:

- Debian or Ubuntu:

```bash
sudo apt update
sudo apt install nodejs npm python3 python3-venv
```

- Fedora:

```bash
sudo dnf install nodejs npm python3
```

After installing, close Terminal, open it again, and rerun the version checks.

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
That means you should run the install command from inside the folder where you want this research project to live.

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

If both of those work, the install is in good shape.

## Where to go next

Use the exact command for your runtime:

| What you want to do | Claude Code / Gemini CLI | Codex | OpenCode |
|---------------------|--------------------------|-------|----------|
| Start a new project | `/gpd:new-project --minimal` | `$gpd-new-project --minimal` | `/gpd-new-project --minimal` |
| Map an existing folder | `/gpd:map-research` | `$gpd-map-research` | `/gpd-map-research` |
| Reopen work from your normal terminal | `gpd resume` | `gpd resume` | `gpd resume` |

## Official docs

- Ubuntu: [The Linux command line for beginners](https://documentation.ubuntu.com/desktop/en/latest/tutorial/the-linux-command-line-for-beginners/)
- Node.js: [Download Node.js](https://nodejs.org/en/download)
- Python: [Python downloads](https://www.python.org/downloads/)
- Python: [The `venv` module](https://docs.python.org/3/library/venv.html)
