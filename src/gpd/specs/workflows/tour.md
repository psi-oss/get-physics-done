<purpose>
Provide a beginner-friendly, read-only tour of the core GPD command surface.
Teach what the main commands do, when to use them, and how GPD behaves in plain
language. Make clear that this tour does not create files, change project
state, or route into another workflow.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before
starting.
</required_reading>

<process>

<step name="orient_the_user">
Open with one short sentence:

`This is a read-only tour of the main GPD commands. It will not change your files.`

If `$ARGUMENTS` is non-empty, show it back as one short context line such as
`You asked about: <goal>. I will use that only as context for the tour.`
Do not narrow the command list, select a path, or route based on it.

Then explain the two places beginners will see GPD commands:

- the normal terminal, where you install GPD and run setup / status commands
- the runtime, where you use the GPD command prefix provided for that runtime

When you first use an official GPD term such as `runtime`, `read-only`, or
`resume-work`, explain it in one short plain-English phrase.

Close the opening with one sentence that says this tour explains the common
commands without executing them.
</step>

<step name="explain_the_core_paths">
Use a compact table with four columns:

- Command
- Use this when
- Do not use this when
- Example

Include these entries:

- `/gpd:start`
- `/gpd:new-project --minimal`
- `/gpd:new-project`
- `/gpd:map-research`
- `gpd resume`
- `/gpd:resume-work`
- `/gpd:progress`
- `/gpd:suggest-next`
- `/gpd:explain <topic>`
- `/gpd:quick`
- `/gpd:settings`
- `/gpd:help`

Keep the examples short and concrete, such as `I just opened a folder and do not know what belongs here yet.`
</step>

<step name="distinguish_terminal_and_runtime">
Add a short section titled something like `Normal terminal vs runtime`.

Explain in plain language:

- The normal terminal is where you install GPD, run `gpd --help`, and run
  checks like `gpd doctor`.
- The runtime is the AI terminal app where you use the runtime-specific GPD
  commands.
- `gpd resume` is the normal-terminal recovery step for reopening the right
  workspace.
- `resume-work` is the in-runtime continue command after you are back in the
  right project.
- `settings` is the guided runtime command for changing autonomy,
  permission-sync behavior, and other GPD preferences after install or later.
- `tour` only explains; it does not run `start`, `new-project`, `map-research`,
  `resume-work`, or `settings` for you.

Include one example sentence for each:

- `In your normal terminal, you install GPD and verify it.`
- `Inside your runtime, you ask GPD what to do next.`
- `Use \`gpd resume\` first if you need to reopen the project before using \`/gpd:resume-work\`.`
</step>

<step name="highlight_common_mistakes">
Call out beginner traps in a gentle, plain-English way:

- Use `start` when you are still deciding, not `new-project`
- Use `new-project` when the folder is genuinely new, not when you only want to
  inspect it
- Use `map-research` for an existing folder with papers, notes, or code, not an
  empty folder
- Use `gpd resume` before `resume-work` when you first need to find or reopen
  the right project from your normal terminal
- Use `resume-work` only when the project already has GPD state
- Use `settings` when you want to change autonomy, permissions, or runtime
  preferences, not `help` or `doctor`
- Use `help` when you want the command reference, not a setup wizard

Keep the tone explanatory, not corrective.
</step>

<step name="explain_advanced_terms">
If useful, add a small section titled `A few terms in plain English`.

Define only the terms that beginners are most likely to see:

- `runtime` - the AI terminal app that receives GPD commands
- `GPD project` - a folder where GPD already saved its own project files and state
- `research map` - GPD's summary of an existing research folder before full project setup
- `map-research` - examine an existing research folder before planning
- `phase` - one chunk of the project plan that GPD will organize later
- `resume-work` - continue an existing GPD project from where it left off
- `read-only` - it explains things without making changes

Keep each definition to one sentence.
</step>

<step name="close_with_next_steps">
End with a short wrap-up that says:

- `If you are still unsure, run /gpd:start.`
- `If you want the reference list again later, run /gpd:help.`
- `If you want to change permissions, autonomy, or runtime preferences, run \`/gpd:settings\`.`
- `If you need to reopen the project itself from your normal terminal, use \`gpd resume\` first and then \`/gpd:resume-work\` in the runtime.`
- `If you already know your path, use the matching command from the table
  above.`

Do not ask the user to pick a branch and do not continue into another workflow.
</step>

<success_criteria>
- [ ] The user sees that `tour` is read-only and non-destructive
- [ ] The core GPD entry points are explained in beginner language
- [ ] The difference between `start`, `new-project`, `map-research`, and `resume-work` is clear
- [ ] The tour also surfaces `settings` as the guided configuration path after install or later
- [ ] The response does not silently route into another workflow
- [ ] The response ends with simple next-step guidance
</success_criteria>
