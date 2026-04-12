# GPD Onboarding Hub

Use this page as the single first-stop for new users.

Use it to pick one OS guide and one runtime guide. The exact install,
startup, and return-to-work commands live in those guides.
Use the next section for the beginner preflight and caveats before you choose.

## Before you open the guides

Make sure these are already true:

- One supported runtime is already installed and can open from your normal terminal.
- Node.js 20+ is available in that same terminal.
- Python 3.11+ with the standard `venv` module is available there too.
- Use `--local` while learning so GPD only affects the current folder.

<details>
<summary>What this hub does not do</summary>

- GPD is not a standalone app. It installs commands into Claude Code, Gemini CLI, Codex, or OpenCode.
- GPD does not install your runtime for you.
- GPD does not include model access, billing, or API credits.
- If evidence, references, or artifacts are missing, say so explicitly; GPD should not invent them.
- This hub is the beginner path, not the full reference. Use the OS guide, runtime guide, and later `help` / `gpd --help` for the exact commands and deeper diagnostics.

</details>

<details>
<summary>Show the full beginner path on one page</summary>

Use this one-line path:

`help -> start -> tour -> new-project / map-research -> resume-work`

Treat the new-work choice as distinct from the existing-work choice; pick one of them, not both.

Follow one linear path:

1. Open the OS guide for your machine.
2. Open the runtime guide you actually plan to use.
3. Install GPD with the runtime command shown there.
4. Open that runtime from your normal terminal and run `help`.
5. Run `start` if you are not sure what fits this folder.
6. Run `tour` if you want a read-only overview of what GPD can do before choosing.
7. Then choose `new-project`, `map-research`, or `resume-work`.

If you already have a GPD project, `gpd resume` is the normal-terminal,
current-workspace read-only recovery snapshot, and `resume-work` is the
in-runtime continue command after you open the right folder. If you need to
reopen a different workspace first, use `gpd resume --recent`, then come back
into the runtime.

</details>

GPD favors scientific rigor and explicit uncertainty. Treat preferred answers as hypotheses to test, and if a citation, result, or artifact cannot be found or produced, keep that gap explicit instead of guessing.

## First: terminal vs runtime

You will use two different places:

- Your **normal terminal** is where you install GPD and check basic tools like Node and Python.
- Your **runtime** is the AI app where you actually use GPD commands after install.

Use the OS guide that matches your machine for terminal shortcuts and OS-specific tooling recommendations.

## Preflight checks

Run the same commands in your normal terminal before you install GPD or open a runtime:

```bash
node --version
npm --version
npx --version
python3 --version
python3 -m venv --help
```

You want Node `v20` or newer, Python `3.11` or newer, and `python3 -m venv --help` to print usage text (that confirms `venv` is installed).

### Verify your runtime command

Confirm your runtime starts from Terminal before installing GPD:

- Claude Code: `claude --version`
- Codex: `codex --help`
- Gemini CLI: `gemini --help`
- OpenCode: `opencode --help`

If you get an error, fix it via the OS guide for your machine before proceeding.

<details>
<summary>Common beginner terms</summary>

- **Runtime**: the AI terminal app you talk to, such as Claude Code, Gemini CLI, Codex, or OpenCode.
- **API credits**: paid model usage from the provider behind your runtime.
- **`--local`**: install GPD for just this project or folder.
- **`gpd resume`**: the terminal-side recovery step.
- **`resume-work`**: the in-runtime command you use after reopening the right workspace.
- **`settings`**: the guided runtime command for changing autonomy, workflow defaults, and model-cost posture after your first successful start or later.
- **`set-tier-models`**: the direct runtime command for pinning concrete `tier-1`, `tier-2`, and `tier-3` model ids.

</details>

## Choose your OS

Open only the guide that matches your computer.

<details>
<summary>macOS</summary>

Use this if you are on a Mac.

- [macOS guide](./macos.md)

</details>

<details>
<summary>Windows</summary>

Use this if you are on Windows 10 or 11.

- [Windows guide](./windows.md)

</details>

<details>
<summary>Linux</summary>

Use this if you are on Linux.

- [Linux guide](./linux.md)

</details>

## Choose your runtime

Open only the runtime guide you actually plan to use.
Use `--local` while learning so GPD only affects the current folder.

The install flags, command prefixes, and aliases live in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md). Regenerate that file with `python scripts/render_runtime_catalog_table.py` whenever you adjust `src/gpd/adapters/runtime_catalog.json`, keep this the single source of truth, and run `npx -y get-physics-done --<flag> --local` with the `<flag>` shown in the catalog for the runtime you plan to install.

<details>
<summary>Claude Code</summary>

Use this if you want GPD inside Claude Code. The runtime catalog reference and Claude Code quickstart describe how `/gpd:`-prefixed commands work inside the app.

- Install: `npx -y get-physics-done --claude --local` (confirm `--claude` is still the right install flag in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md) and rerun `python scripts/render_runtime_catalog_table.py` whenever `src/gpd/adapters/runtime_catalog.json` changes).
- [Claude Code quickstart](./claude-code.md)

</details>

<details>
<summary>Codex</summary>

Use this if you want GPD inside Codex. The runtime catalog reference and Codex quickstart describe how `$gpd-`-prefixed commands work inside the app.

- Install: `npx -y get-physics-done --codex --local` (confirm `--codex` is still correct in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md) and rerun `python scripts/render_runtime_catalog_table.py` whenever `src/gpd/adapters/runtime_catalog.json` changes).
- [Codex quickstart](./codex.md)

</details>

<details>
<summary>Gemini CLI</summary>

Use this if you want GPD inside Gemini CLI. The runtime catalog reference and Gemini CLI quickstart describe how `/gpd:`-prefixed commands work inside the app.

- Install: `npx -y get-physics-done --gemini --local` (confirm `--gemini` is still correct in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md) and rerun `python scripts/render_runtime_catalog_table.py` whenever `src/gpd/adapters/runtime_catalog.json` changes).
- [Gemini CLI quickstart](./gemini-cli.md)

</details>

<details>
<summary>OpenCode</summary>

Use this if you want GPD inside OpenCode. The runtime catalog reference and OpenCode quickstart describe how `/gpd-`-prefixed commands work inside the app.

- Install: `npx -y get-physics-done --opencode --local` (confirm `--opencode` is still correct in [docs/runtime-catalog-reference.md](./runtime-catalog-reference.md) and rerun `python scripts/render_runtime_catalog_table.py` whenever `src/gpd/adapters/runtime_catalog.json` changes).
- [OpenCode quickstart](./opencode.md)

</details>

## After the guides

1. Finish the OS and runtime guide you opened.
2. Inside the runtime, use `help` for the command menu, `start` if you are not sure what fits this folder, or `tour` if you want a read-only orientation first.
3. Then choose `new-project`, `map-research`, or `resume-work`.
4. After your first successful start or later, use the runtime-specific `settings` command to review autonomy, workflow defaults, and model-cost posture. If you only want to pin concrete `tier-1`, `tier-2`, and `tier-3` model ids, use the runtime-specific `set-tier-models` command instead.
5. Come back to this hub only when you need a different OS guide or runtime guide.

| What you want to do | Claude Code / Gemini CLI | Codex | OpenCode |
|---------------------|--------------------------|-------|----------|
| Not sure which path fits this folder | `/gpd:start` | `$gpd-start` | `/gpd-start` |
| Want a guided overview | `/gpd:tour` | `$gpd-tour` | `/gpd-tour` |
| Start a new project | `/gpd:new-project --minimal` | `$gpd-new-project --minimal` | `/gpd-new-project --minimal` |
| Map an existing folder | `/gpd:map-research` | `$gpd-map-research` | `/gpd-map-research` |
| Rediscover the workspace in your normal terminal | `gpd resume` | `gpd resume` | `gpd resume` |
| Continue in the reopened runtime | `/gpd:resume-work` | `$gpd-resume-work` | `/gpd-resume-work` |

Use `gpd resume` in your normal terminal first. Use `gpd resume --recent` when you need to jump to a different recent workspace before reopening the runtime. After the terminal points you to the right workspace, open your runtime there and use its `resume-work` command to continue inside the project.

## Hooks & advanced overrides

Need deeper insight into how the runtime hooks resolve statuslines, notifications, and telemetry? The [Hook wiring & advanced overrides](./hooks.md) guide walks through the runtime detection flow plus the `GPD_ACTIVE_RUNTIME`, `GPD_DISABLE_CHECKOUT_REEXEC`, and `GPD_DEBUG` overrides so you can pin a runtime, skip checkout re-execs, or turn on hook tracing when you debug.
