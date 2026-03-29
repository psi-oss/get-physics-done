# GPD Onboarding Hub

Use this page as the single first-stop for new users.

Use it to pick one OS guide and one runtime guide. The exact install,
startup, and return-to-work commands live in those guides.

<details>
<summary>Show the full beginner path on one page</summary>

Use this one-line path:

`help -> start -> tour -> new-project / map-research -> resume-work`

Follow one linear path:

1. Open the OS guide for your machine.
2. Open the runtime guide you actually plan to use.
3. Install GPD with the runtime command shown there.
4. Open that runtime from your normal terminal and run `help`.
5. Run `start` if you are not sure what fits this folder.
6. Run `tour` if you want a read-only overview of what GPD can do before choosing.
7. Then choose `new-project`, `map-research`, or `resume-work`.

If you already have a GPD project, `resume-work` is the in-runtime return path
after you open the right folder. If you need to reopen from your normal
terminal first, use `gpd resume` or `gpd resume --recent`, then come back into
the runtime.

</details>

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
4. Come back to this hub only when you need a different OS guide or runtime guide.
