# Claude Code Quickstart for GPD

Use this if you want to run GPD inside Claude Code.

## What Claude Code is here

Claude Code is the terminal app you talk to. GPD adds physics-research commands to it, so you can ask Claude to help scope, plan, derive, and verify work in a structured way.

If you are on Windows, Claude Code's official docs say you need Git for Windows or WSL.

## Before you start

Open your normal terminal in the folder where you want this research project to live.
This guide uses `--local`, so GPD is installed only for the current folder.

## 1) Check that `claude` works

From your normal terminal, run:

```bash
claude --version
```

If it prints a version number, Claude Code is installed and available on your `PATH`.

If it does not, use Anthropic's getting-started guide linked below, then come back here.

## 2) Install GPD for Claude Code

Run this from your normal terminal:

```bash
npx -y get-physics-done --claude --local
```

## 3) Start Claude Code

Open Claude Code from the terminal in the folder where you want to work:

```bash
claude
```

## 4) First commands inside Claude Code

Type these inside Claude Code, not in your normal terminal:

```text
/gpd:help
/gpd:new-project --minimal
```

If you already have research in this folder, use:

```text
/gpd:map-research
```

## What success looks like

- `claude --version` prints a version.
- `npx -y get-physics-done --claude --local` finishes without errors.
- Inside Claude Code, `/gpd:help` shows the GPD commands.
- `/gpd:new-project --minimal` or `/gpd:map-research` starts a guided physics workflow instead of saying the command is unknown.

## Quick troubleshooting

- `claude: command not found` means Claude Code is not installed or not on your `PATH`. Install Claude Code first, then try `claude --version` again.
- If Claude Code opens but asks you to sign in, finish the sign-in flow, then rerun `claude`.
- If `/gpd:help` is not recognized, rerun `npx -y get-physics-done --claude --local` from your normal terminal, then reopen Claude Code.

## Official docs

- Anthropic: [Claude Code getting started](https://code.claude.com/docs/en/getting-started)
- Anthropic: [Claude Code settings](https://code.claude.com/docs/en/settings)
