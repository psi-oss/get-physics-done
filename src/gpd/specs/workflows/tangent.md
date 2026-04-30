<purpose>
Choose what to do with a possible side investigation, tangent, or alternative path without silently widening scope. This workflow is proposal-first: it classifies the tangent, asks the researcher for a decision, and only then routes into the existing quick, todo, or hypothesis-branch workflows.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="gather_context">
Load enough project context to frame the tangent:

```bash
INIT=$(gpd --raw init progress --include roadmap,state)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `project_exists`, `planning_exists`, `current_phase`, `state_content`, `roadmap_content`.

Also read the active research mode:

```bash
RESEARCH_MODE=$(gpd --raw config get research_mode | gpd json get .value --default balanced)
```

Detect whether git branching is available:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_AVAILABLE=true
else
  GIT_AVAILABLE=false
fi
```
</step>

<step name="capture_tangent">
Determine the tangent description.

- If `$ARGUMENTS` is non-empty, use it as the tangent description.
- If `$ARGUMENTS` is empty, infer the tangent from the recent conversation if it is obvious.
- If it is still unclear, ask the user for one short description.

> **Platform note:** If `ask_user` is not available, present the prompt in plain text and wait for the user's freeform response.

Example prompt:

```text
ask_user(
  header: "Tangent",
  question: "What possible side investigation or alternative path are you deciding about?",
  followUp: null
)
```

If the description remains too vague to route, STOP and ask for a narrower statement.
</step>

<step name="frame_the_decision">
Present the tangent back to the user in one short summary:

```text
Possible tangent: {description}
```

Then explain the 4-way decision model:

1. `Stay on the main path` — do not widen scope right now.
2. `Run a bounded quick check now` — use `gpd:quick` for a small, self-contained side investigation.
3. `Capture and defer` — use `gpd:add-todo` so the tangent is not lost.
4. `Open a hypothesis branch` — use `gpd:branch-hypothesis` for an explicit git-backed alternative path.

If `RESEARCH_MODE=exploit`, say explicitly that optional tangents are suppressed by default and the recommended choices are usually `Stay on the main path` or `Capture and defer` unless the researcher intentionally wants to explore.
</step>

<step name="ask_for_decision">
Ask the user to choose exactly one of the four options.

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

Until a concrete `$TANGENT_DECISION` is captured, do not name `gpd:quick`, `gpd:add-todo`, `gpd:branch-hypothesis`, `gpd:execute-phase`, or autonomous continuation as the selected next command. The safe stop is the visible four-way choice itself, or re-running `gpd:tangent {description}` with the same tangent description.

Use ask_user:

- header: `Tangent`
- question: `How should GPD handle this tangent right now?`
- options:
  - `Stay on main path` -- Continue the approved mainline without extra side work. Recommended in exploit mode.
  - `Quick check now` -- Run a bounded side investigation through `gpd:quick`.
  - `Capture and defer` -- Record it via `gpd:add-todo` and keep moving.
  - `Open hypothesis branch` -- Route to `gpd:branch-hypothesis` for an explicit git-backed alternative path.

Store the choice as `$TANGENT_DECISION`.
</step>

<step name="route_decision">
Route immediately into the corresponding existing workflow.

**If `Stay on main path`:**

- Confirm the decision briefly.
- Do not mutate state.
- Suggest `gpd:add-todo {description}` only as an optional follow-up if the researcher wants a durable reminder.
- STOP.

**If `Quick check now`:**

- Read `{GPD_INSTALL_DIR}/workflows/quick.md` using the file_read tool.
- Follow that workflow using `{description}` as if the researcher had run `gpd:quick {description}`.
- Do not re-ask for the description unless it is too vague for a bounded quick task.

**If `Capture and defer`:**

- Read `{GPD_INSTALL_DIR}/workflows/add-todo.md` using the file_read tool.
- Follow that workflow using `{description}` as if the researcher had run `gpd:add-todo {description}`.

**If `Open hypothesis branch`:**

- If `GIT_AVAILABLE` is false, STOP and explain that hypothesis branches require a git worktree. Offer the researcher the chance to fall back to `Capture and defer` instead.
- If `GIT_AVAILABLE` is true, read `{GPD_INSTALL_DIR}/workflows/branch-hypothesis.md` using the file_read tool.
- Follow that workflow using `{description}` as if the researcher had run `gpd:branch-hypothesis {description}`.

This workflow must not invent a new tangent state machine or auto-spawn parallel work without the explicit choice above.

It may be the explicit follow-up when a live execution review stop surfaces a tangent proposal or when `gpd observe execution` surfaces a tangent proposal or `branch later` recommendation, but it remains the chooser rather than a persistent execution-state workflow. Do not skip straight from that suggestion to `gpd:branch-hypothesis`; branching stays optional until this chooser explicitly selects it.
Likewise, do not skip straight to `gpd:quick`, `gpd:add-todo`, or `gpd:execute-phase` from a correction/tangent proposal unless the user has already made that exact choice in this tangent workflow.
</step>

<step name="guardrails">
Keep the taxonomy strict:

- `tangent` is the chooser, not the branch itself
- `quick` is the bounded side-investigation path
- `add-todo` is the defer path
- `branch-hypothesis` is the explicit git-backed alternative path

Do not silently convert one category into another.
</step>

</process>

<success_criteria>
- [ ] Tangent description is clear enough to classify
- [ ] The researcher sees the 4-way decision model explicitly
- [ ] The chosen action routes into the real existing workflow, not an invented parallel mechanism
- [ ] `research_mode=exploit` keeps optional tangents suppressed by default
- [ ] No new persistent tangent state or hidden branching behavior is introduced
</success_criteria>
