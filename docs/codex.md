# Codex Quickstart for GPD

Use this if you are a physics researcher and want GPD inside the OpenAI Codex CLI.

## What Codex is here

In this project, “Codex” means the Codex CLI runtime that GPD installs into. Once GPD is set up, you run GPD commands inside Codex with the `$gpd-...` syntax.

If you are on Windows, the official Codex docs currently say Windows support is experimental and recommend using Codex in WSL for the best experience.

## 1) Confirm `codex` works

From your normal terminal:

```bash
codex --help
```

If that prints help text, Codex is installed and launchable.

## 2) Install GPD for Codex

Copy-paste this exact command:

```bash
npx -y get-physics-done --codex --local
```

## 3) Start Codex

From your normal terminal:

```bash
codex
```

The first time you run Codex, it should prompt you to sign in with your ChatGPT account or an API key.

## 4) First commands inside Codex

Open Codex, then type these inside Codex, not in your normal terminal:

```text
$gpd-help
```

If you want the fastest new-project start:

```text
$gpd-new-project --minimal
```

If you already have research in this folder:

```text
$gpd-map-research
```

## 5) What success looks like

You are in the right place when:

- `codex --help` works.
- `npx -y get-physics-done --codex --local` finishes without errors.
- Inside Codex, `$gpd-help` shows the GPD command list.
- `$gpd-new-project --minimal` or `$gpd-map-research` starts asking structured research questions instead of failing with “command not found.”

## 6) Quick troubleshooting

- If a command is missing, make sure you are typing it inside Codex, not in your normal terminal.
- If `codex` is not found, install or relaunch Codex first.
- If Codex says you are not signed in, finish the Codex login flow, then rerun `$gpd-help`.

## Official docs

- OpenAI: [Codex CLI docs](https://developers.openai.com/codex/cli)
- OpenAI: [Codex CLI overview](https://developers.openai.com/codex/cli)
