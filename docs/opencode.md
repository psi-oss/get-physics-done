# OpenCode Quickstart for GPD

This guide uses the simplest path to get started. OpenCode's official docs may
list additional install, auth, or platform-specific options.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md).

## Choose this runtime if

Use OpenCode if you want GPD inside OpenCode and prefer the `/gpd-...` command
style.

If you are on Windows, OpenCode's official docs recommend using WSL for the
best experience.

## What must already be true

- You already have OpenCode installed and can launch `opencode` from your
  normal terminal.
- Node.js 20+ and Python 3.11+ with `venv` are installed.
- You are in the folder where you want this research project to live.
- This guide uses `--local`, so GPD is installed only for the current folder.

## 1) Confirm OpenCode works

Run this in your normal terminal:

```bash
opencode --help
```

If you see OpenCode help instead of `command not found`, the CLI is available.
If `opencode` is missing, install the runtime first with:

```bash
npm install -g opencode-ai
```

## 2) Install GPD for OpenCode

Use this exact command for a local install:

```bash
npx -y get-physics-done --opencode --local
```

## 3) Start OpenCode

From the same project folder:

```bash
opencode
```

If you are not signed in yet, run `/connect` inside OpenCode, choose your provider, and finish that provider's API-key or billing setup.

## 4) First launch / help / start / tour

Type these inside OpenCode, not in your normal terminal:

```text
/gpd-help
/gpd-start
/gpd-tour
/gpd-new-project --minimal
/gpd-map-research
/gpd-resume-work
```

If you are not sure what this folder is yet, start with `/gpd-start`.
If you want a read-only walkthrough first, use `/gpd-tour`.
Beginner flow: `/gpd-help` → `/gpd-start` → `/gpd-tour`, then `/gpd-new-project --minimal`, `/gpd-map-research`, or `/gpd-resume-work`.
GPD favors scientific rigor: treat answers as hypotheses and surface gaps instead of inventing them.

## Return to work

- Use `/gpd-resume-work` when this folder already has GPD state; if unsure, start with `/gpd-start`.
- If you need to reopen from your normal terminal, run `gpd resume` or `gpd resume --recent`, then open the folder and use `/gpd-resume-work`.

## Settings

After your first successful start or later, use `/gpd-settings` to review
autonomy, workflow defaults, and model-cost posture. Use `/gpd-set-tier-models`
when you only want to pin concrete `tier-1`, `tier-2`, and `tier-3` model ids.

## Keep GPD current

For normal released updates, use `/gpd-update` inside OpenCode.
Bootstrap `--upgrade` is the dev-only GitHub `main` path, not the normal released update path.

## 5) What success looks like

- `opencode --help` works.
- GPD installation finishes without errors.
- Inside OpenCode, `/gpd-help` returns a GPD help screen.
- `/gpd-start` routes a beginner to the right entry point.
- `/gpd-tour` gives a read-only walkthrough of the main commands.
- `/gpd-new-project --minimal`, `/gpd-map-research`, or `/gpd-resume-work` starts the right GPD flow for new work, an existing research folder, or an existing project.

## 6) Quick troubleshooting

- Missing `opencode`: install OpenCode first or add it to `PATH`, then reopen your terminal.
- Missing `/gpd-...` commands: rerun the install command above, then restart OpenCode.
- Not signed in: start `opencode`, run `/connect`, finish the provider setup, then reopen OpenCode and try `/gpd-help` again.

## Official docs

- OpenCode: [Intro and install](https://opencode.ai/docs/)
- OpenCode: [CLI reference](https://opencode.ai/docs/cli/)
- OpenCode: [Windows with WSL](https://opencode.ai/docs/windows-wsl/)
