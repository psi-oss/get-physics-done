# OpenCode Quickstart for GPD

OpenCode is the runtime where GPD adds its commands. In OpenCode, the GPD commands use the `/gpd-...` form.

If you are on Windows, OpenCode's official docs recommend using WSL for the best experience.

## Before you start

Open your normal terminal in the folder where you want this research project to live.
This guide uses `--local`, so GPD is installed only for the current folder.

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

If you are not signed in yet, run `opencode auth login` from your normal terminal and finish the provider setup.

## 4) First commands inside OpenCode

Type these inside OpenCode, not in your normal terminal:

```text
/gpd-help
/gpd-new-project --minimal
```

If you already have a GPD project, use:

```text
/gpd-resume-work
```

If you are bringing in an existing paper, notebook, or codebase, use:

```text
/gpd-map-research
```

## 5) What success looks like

- `opencode --help` works.
- GPD installation finishes without errors.
- Inside OpenCode, `/gpd-help` returns a GPD help screen.
- `/gpd-new-project --minimal`, `/gpd-resume-work`, or `/gpd-map-research` starts the expected workflow instead of saying the command is unknown.

## 6) Quick troubleshooting

- Missing `opencode`: install OpenCode first or add it to `PATH`, then reopen your terminal.
- Missing `/gpd-...` commands: rerun the install command above, then restart OpenCode.
- Not signed in: run `opencode auth login` or follow the in-app provider setup, then reopen OpenCode and try `/gpd-help` again.

## Official docs

- OpenCode: [Intro and install](https://opencode.ai/docs/)
- OpenCode: [CLI reference](https://opencode.ai/docs/cli/)
