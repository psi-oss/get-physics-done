# Gemini CLI Quickstart

This guide uses the simplest path to get started. Google's official Gemini CLI
docs may list additional install, auth, or platform-specific options.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md).

## Choose this runtime if

Use Gemini CLI if you want GPD inside Google's terminal app and prefer the
`/gpd:...` command style.

## What must already be true

- You already have Gemini CLI installed and can launch `gemini` from your
  normal terminal.
- Node.js 20+ and Python 3.11+ with `venv` are installed.
- You are in the folder where you want this research project to live.
- This guide uses `--local`, so GPD is installed only for the current folder.

## 1) Check that `gemini` works

Run this in your normal terminal:

```bash
gemini --help
```

If that prints help text, Gemini CLI is installed and launchable.
If `gemini` is missing, install the runtime first with:

```bash
npm install -g @google/gemini-cli
```

## 2) Install GPD for Gemini CLI

```bash
npx -y get-physics-done --gemini --local
```

## 3) Start Gemini CLI

From the same project folder:

```bash
gemini
```

If you are not signed in yet, choose **Sign in with Google** and finish the browser login flow.
If you are using a paid Gemini Code Assist license from your organization, set `GOOGLE_CLOUD_PROJECT` before launching `gemini`. For Google Workspace accounts or other auth methods, use the official authentication guide linked below.

## 4) First launch / help / start / tour

Type these inside Gemini CLI, not in your normal terminal:

```text
/gpd:help
/gpd:start
/gpd:tour
/gpd:new-project --minimal
/gpd:map-research
/gpd:resume-work
```

If you are not sure what this folder is yet, start with `/gpd:start`.
If you want a read-only walkthrough first, use `/gpd:tour`.

Suggested order for beginners: `/gpd:help`, `/gpd:start`, `/gpd:tour`, then
either `/gpd:new-project --minimal`, `/gpd:map-research`, or
`/gpd:resume-work`.

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

## Readiness before unattended runs

After `/gpd:settings` changes autonomy, or before an overnight run, check the
active runtime from your normal terminal:

```bash
gpd validate unattended-readiness --runtime gemini --autonomy supervised
```

Use the autonomy mode you selected if it is not `supervised`. If the verdict is
`not-ready`, apply the runtime permission update and check again:

```bash
gpd permissions sync --runtime gemini --autonomy supervised
gpd validate unattended-readiness --runtime gemini --autonomy supervised
```

If the verdict is `relaunch-required`, exit Gemini CLI and relaunch through the
GPD-managed launcher wrapper shown by the command output before treating
unattended use as ready.

## 5) What success looks like

- `gemini --help` works.
- `npx -y get-physics-done --gemini --local` finishes without errors.
- `/gpd:help` shows GPD commands.
- `/gpd:start` routes a beginner to the right entry point.
- `/gpd:tour` gives a read-only walkthrough of the main commands.
- `/gpd:new-project --minimal`, `/gpd:map-research`, or `/gpd:resume-work` starts the right GPD flow for new work, existing research, or an existing GPD project.

## 6) Quick troubleshooting

- `gemini: command not found`: install Gemini CLI, then reopen your terminal.
- GPD commands are missing: rerun `npx -y get-physics-done --gemini --local`.
- Not signed in: start `gemini`, choose `Sign in with Google`, and finish the browser login prompt. If you prefer API-key auth, Gemini CLI's official auth guide covers `GEMINI_API_KEY`.

## Official docs

- Google: [Gemini CLI repository and installation](https://github.com/google-gemini/gemini-cli)
- Google: [Gemini CLI authentication guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/get-started/authentication.md)
