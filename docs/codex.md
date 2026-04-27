# Codex Quickstart for GPD

Use this if you are a physics researcher and want GPD inside the OpenAI Codex
CLI.

This guide uses the simplest path to get started. OpenAI's official Codex docs
may list additional install, auth, or platform-specific options.

Back to the onboarding hub: [GPD Onboarding Hub](./README.md).

## Choose this runtime if

Use Codex if you want GPD inside the OpenAI Codex CLI and are comfortable with
the `$gpd-...` command style.

The official Codex CLI docs list macOS, Windows, and Linux support. On Windows,
run Codex natively in PowerShell with the Windows sandbox for the normal path,
or use WSL2 when your repository or tools need a Linux-native environment.

## What must already be true

- You already have Codex installed and can launch `codex` from your normal
  terminal.
- Node.js 20+ and Python 3.11+ with `venv` are installed.
- You are in the folder where you want this research project to live.
- This guide uses `--local`, so GPD is installed only for the current folder.

## 1) Confirm `codex` works

From your normal terminal:

```bash
codex --help
```

If that prints help text, Codex is installed and launchable.
If `codex` is missing, install the runtime first with:

```bash
npm install -g @openai/codex
```

## 2) Install GPD for Codex

Copy-paste this exact command:

```bash
npx -y get-physics-done --codex --local
```

## 3) Start Codex

From the same project folder:

```bash
codex
```

The first time you run Codex, it should prompt you to sign in with your ChatGPT account or an API key.

## 4) First launch / help / start / tour

Type these inside Codex, not in your normal terminal:

```text
$gpd-help
$gpd-start
$gpd-tour
$gpd-new-project --minimal
$gpd-map-research
$gpd-resume-work
```

If you are not sure what this folder is yet, start with `$gpd-start`.
If you want a read-only walkthrough first, use `$gpd-tour`.

Suggested order for beginners: `$gpd-help`, `$gpd-start`, `$gpd-tour`, then
either `$gpd-new-project --minimal`, `$gpd-map-research`, or
`$gpd-resume-work`.

GPD is designed to favor scientific rigor and critical thinking. Treat preferred answers as hypotheses to test, and if a citation, artifact, or run result is missing, keep that gap explicit instead of inventing it.

## Return to work

- Use `$gpd-resume-work` when this folder already has GPD state and you want to
  continue.
- If you are not sure whether this folder already has GPD state, use
  `$gpd-start` first.
- If you need to reopen the project from your normal terminal first, use
  `gpd resume` or `gpd resume --recent`, then open the right folder and run
  `$gpd-resume-work`.

## Settings

After your first successful start or later, use `$gpd-settings` to review
autonomy, workflow defaults, and model-cost posture. Use `$gpd-set-tier-models`
when you only want to pin concrete `tier-1`, `tier-2`, and `tier-3` model ids.

## 5) What success looks like

You are in the right place when:

- `codex --help` works.
- `npx -y get-physics-done --codex --local` finishes without errors.
- Inside Codex, `$gpd-help` shows the GPD command list.
- `$gpd-start` routes a beginner to the right entry point.
- `$gpd-tour` gives a read-only walkthrough of the main commands.
- `$gpd-new-project --minimal`, `$gpd-map-research`, or `$gpd-resume-work` starts the right GPD flow for new work, existing research, or an existing GPD project.

## 6) Quick troubleshooting

- If a command is missing, make sure you are typing it inside Codex, not in your normal terminal.
- If `codex` is not found, install or relaunch Codex first.
- If Codex says you are not signed in, finish the Codex login flow, then rerun `$gpd-help`.

## Official docs

- OpenAI: [Codex CLI docs](https://developers.openai.com/codex/cli)
- OpenAI: [Codex authentication](https://developers.openai.com/codex/auth)
- OpenAI: [Codex Windows setup](https://developers.openai.com/codex/windows)
