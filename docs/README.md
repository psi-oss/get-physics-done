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
- Normal installs and `--reinstall` use the PyPI pinned release first, with tagged GitHub release sources only as fallback. `--upgrade` opts into the latest unreleased GitHub `main` source.

<details>
<summary>What this hub does not do</summary>

- GPD is not a standalone app. It installs commands into Claude Code, Codex, Gemini CLI, or OpenCode.
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

<details>
<summary>Common beginner terms</summary>

- **Runtime**: the AI terminal app you talk to, such as Claude Code, Codex, Gemini CLI, or OpenCode.
- **API credits**: paid model usage from the provider behind your runtime.
- **`--local`**: install GPD for just this project or folder.
- **`gpd resume`**: the terminal-side recovery step.
- **`resume-work`**: the in-runtime command you use after reopening the right workspace.
- **`settings`**: the guided runtime command for changing autonomy, workflow defaults, and model-cost posture after your first successful start or later. GPD is a scalpel, not an autopilot. Supervised mode is the default and gives you the frequent checkpoints that match the advisor/graduate-student role. Graduate to Balanced once you trust GPD's boundary on your specific research.
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

<details>
<summary>Claude Code</summary>

Use this if you want GPD inside Claude Code. Inside the runtime, GPD commands use `/gpd:...`.

- Install: `npx -y get-physics-done --claude --local`
- [Claude Code quickstart](./claude-code.md)

</details>

<details>
<summary>Codex</summary>

Use this if you want GPD inside Codex. Inside the runtime, GPD commands use `$gpd-...`.

- Install: `npx -y get-physics-done --codex --local`
- [Codex quickstart](./codex.md)

</details>

<details>
<summary>Gemini CLI</summary>

Use this if you want GPD inside Gemini CLI. Inside the runtime, GPD commands use `/gpd:...`.

- Install: `npx -y get-physics-done --gemini --local`
- [Gemini CLI quickstart](./gemini-cli.md)

</details>

<details>
<summary>OpenCode</summary>

Use this if you want GPD inside OpenCode. Inside the runtime, GPD commands use `/gpd-...`.

- Install: `npx -y get-physics-done --opencode --local`
- [OpenCode quickstart](./opencode.md)

</details>

## After the guides

1. Finish the OS and runtime guide you opened.
2. Inside the runtime, use `help` for the command menu, `start` if you are not sure what fits this folder, or `tour` if you want a read-only orientation first.
3. Then choose `new-project`, `map-research`, or `resume-work`.
4. After your first successful start or later, use the runtime-specific `settings` command to review autonomy, workflow defaults, and model-cost posture. If you only want to pin concrete `tier-1`, `tier-2`, and `tier-3` model ids, use the runtime-specific `set-tier-models` command instead.
5. Come back to this hub only when you need a different OS guide or runtime guide.
