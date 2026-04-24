# Claude Code Quickstart for GPD

Use this if you want to run GPD inside Claude Code.

This guide shows the simplest path to get started. Anthropic's official Claude
Code docs may list additional install and platform-specific options.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md).

## Choose this runtime if

Use Claude Code if you want GPD inside Claude's terminal app and prefer the
direct `/gpd:...` command style.

If you are on Windows, Claude Code's official docs say you need Git for Windows
or WSL. If you are on Linux and `claude` is missing, Anthropic recommends the
native installer. Anthropic's npm install path is now deprecated.

## What must already be true

- You already have Claude Code installed and can launch `claude` from your
  normal terminal.
- Node.js 20+ and Python 3.11+ with `venv` are installed.
- You are in the folder where you want this research project to live.
- This guide uses `--local`, so GPD is installed only for the current folder.

## 1) Confirm `claude` works

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

Claude Code requires a Pro, Max, Teams, Enterprise, or Console account. The free Claude.ai plan does not include Claude Code access.

## 4) First launch / help / start / tour

Type these inside Claude Code, not in your normal terminal:

```text
/gpd:help
/gpd:start
/gpd:tour
/gpd:agentic-discussion
/gpd:new-project --minimal
/gpd:map-research
/gpd:resume-work
```

If you are not sure what this folder is yet, start with `/gpd:start`.
If you want a read-only walkthrough first, use `/gpd:tour`.
If you want to pressure-test a direction before opening durable project work,
use `/gpd:agentic-discussion`.

Suggested order for beginners: `/gpd:help`, `/gpd:start`, `/gpd:tour`, then
optionally `/gpd:agentic-discussion` before either
`/gpd:new-project --minimal`, `/gpd:map-research`, or `/gpd:resume-work` if
this folder already has GPD state.

GPD is designed to favor scientific rigor and critical thinking. Treat preferred answers as hypotheses to test, and if a citation, artifact, or run result is missing, keep that gap explicit instead of inventing it.

## Return to work

- Use `/gpd:resume-work` when this folder already has GPD state and you want to
  continue.
- If you are not sure whether this folder already has GPD state, use
  `/gpd:start` first.
- If you need to reopen the project from your normal terminal first, use
  `gpd resume` or `gpd resume --recent`, then open the right folder and run
  `/gpd:resume-work`.

## Settings

After your first successful start or later, use `/gpd:settings` to review
autonomy, workflow defaults, and model-cost posture. Use `/gpd:set-tier-models`
when you only want to pin concrete `tier-1`, `tier-2`, and `tier-3` model ids.

## What success looks like

- `claude --version` prints a version.
- `npx -y get-physics-done --claude --local` finishes without errors.
- Inside Claude Code, `/gpd:help` shows the GPD commands.
- `/gpd:start` routes a beginner to the right entry point.
- `/gpd:tour` explains the main commands without changing anything.
- `/gpd:agentic-discussion`, `/gpd:new-project --minimal`,
  `/gpd:map-research`, or `/gpd:resume-work` starts the right GPD flow for
  optional pre-project exploration, new work, existing research, or an
  existing GPD project.

## Quick troubleshooting

- `claude: command not found` means Claude Code is not installed or not on your `PATH`. Install Claude Code first, then try `claude --version` again.
- If Claude Code opens but says your account does not have access, make sure you are using a Pro, Max, Teams, Enterprise, or Console account.
- If Claude Code opens but asks you to sign in, finish the sign-in flow, then rerun `claude`.
- If `/gpd:help` is not recognized, rerun `npx -y get-physics-done --claude --local` from your normal terminal, then reopen Claude Code.

## Official docs

- Anthropic: [Claude Code getting started](https://code.claude.com/docs/en/getting-started)
- Anthropic: [Claude Code settings](https://code.claude.com/docs/en/settings)
