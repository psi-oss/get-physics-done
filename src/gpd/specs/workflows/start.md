<purpose>
Give a first-run chooser for people who may not know GPD yet. Explain the folder state in plain English, offer only the choices that fit that state, and route into the existing workflows instead of creating a separate onboarding flow.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="detect_workspace_state">
Figure out what kind of folder this is before offering any commands. Use the non-staged raw CLI classifier, which delegates to GPD's workspace-bound, read-only classifier instead of hand-rolled current-directory marker checks. The classifier must describe the invoked folder itself; do not let an ancestor or home-directory GPD project claim an unrelated nested checkout.

```bash
START_CONTEXT=$(gpd --raw init new-project)
```

Parse the JSON result and use these fields:

- `project_exists=true` means this folder already has a `GPD project` (a folder where GPD already saved its own project files, notes, and state), such as `GPD/PROJECT.md`.
- `recoverable_project_exists=true` means this folder has GPD state that should not be treated as fresh. If `partial_project_exists=true`, route to recovery/inspection rather than new setup.
- `roadmap_exists=true` means partial state has a roadmap-like recovery anchor.
- `state_exists=true` means partial state has a state file that can be reconciled.
- `has_research_map=true` means this folder already has a `research map` (GPD's summary of an existing research folder before full project setup).
- `has_research_files=true`, `has_project_manifest=true`, or `needs_research_map=true` means this looks like an existing research folder. Example files might be `.tex`, `.py`, `.ipynb`, `.pdf`, or `.csv`.
- `research_file_samples` is a sorted, bounded list of up to 5 project-relative research-looking files noticed by the classifier.
- Otherwise, treat this as a fresh folder with no obvious GPD state yet.

If `$ARGUMENTS` is non-empty, briefly repeat it back as the researcher’s goal, but keep the folder-state routing rules above.
</step>

<step name="explain_current_state">
Give one short summary before asking for a choice.

Use one of these plain-English summaries:

- Existing GPD project:
  `This folder already has a GPD project (GPD's saved project files and working state), so the safest next step is usually to resume it instead of starting over.`
- Recoverable partial GPD state:
  `This folder already has partial GPD state, so the safest next step is to inspect or recover it instead of starting over.`
- Research map only:
  `This folder already has a GPD research map (GPD's summary of the folder before full setup), so you can refresh that map or turn it into a full project.`
- Existing research folder:
  `This folder already looks like real research work, so the safest next step is usually to map it before creating a new project. In GPD terms, \`map-research\` means inspect an existing folder before planning.`
- Fresh folder:
  `This folder does not look like an existing GPD project or research folder yet, so you can start from scratch here. In GPD terms, \`new-project\` creates the project scaffolding GPD will use later.`

If `research_file_samples` is non-empty, show those sample files so the researcher can see what GPD noticed.

If advanced terms appear in the summary, explain them once in parentheses and then keep using the official term consistently.
</step>

<step name="frame_autonomy_posture">
Before offering choices, set expectations for supervision:

@{GPD_INSTALL_DIR}/references/shared/onboarding-command-boundaries.md

Do not write config.json from this workflow. If the researcher wants to change autonomy, point them at `gpd:settings`.
</step>

<step name="offer_relevant_choices">
Offer only the choices that fit the detected state.

@{GPD_INSTALL_DIR}/references/shared/interactive-choice-fallback.md

If choices are rendered as plain text, add: `Reply with the number or the option name.`

Assign one internal `option_id` per choice. Do not route directly on the mutable English label; map input to: `resume_work`, `sync_state`, `progress`, `suggest_next`, `map_research`, `new_project_minimal`, `new_project_full`, `tour`, `quick`, `explain`, `help_all`, `reopen_recent`.

Before listing choices, add one short line in plain English such as:

- `I will show the safest next steps first and the broader options second.`
- `The official GPD command names are included so you can learn them as you go.`

Keep the numbered list short. Put extra capabilities in a separate `Other useful options` block instead of making the user compare too many first choices; this is an internal structuring rule, not a line to show the researcher.

**This folder already has saved GPD work (`GPD project`)**

Recommended next steps:

1. Resume this project (recommended) - use `gpd:resume-work`. This is the in-runtime continue command for an existing GPD project.
2. Review the project status first - use `gpd:progress`.
3. Take a guided tour first - use `gpd:tour`.

Other useful options, only if one of these is what you need:

- Suggest the next best step - use `gpd:suggest-next`.
- Do one small bounded task - use `gpd:quick`.
- Explain one concept - use `gpd:explain`.
- Show all commands - use `gpd:help --all`.

**This folder has partial/recoverable GPD state**

Recommended next steps depend on the recovered artifacts. Only list commands whose command-context preflight can pass for the detected state:

Build the visible numbered list contiguously after filtering by detected fields. Do not leave gaps when only one partial-state command is available.

When `roadmap_exists=true`, include as the next numbered choice:
- Inspect recovery state (recommended) - use `gpd:resume-work`.

When `state_exists=true`, include as the next numbered choice:
- Reconcile state files - use `gpd:sync-state`.

Do not list `gpd:progress` for partial state; reserve it for initialized projects with `project_exists=true`.
Do not offer `gpd:new-project` as a fresh start unless the researcher explicitly says they want to delete or move the existing `GPD/` artifacts first.

**This folder already has GPD's folder summary (`research map`)**

Recommended next steps:

1. Turn this into a full GPD project (recommended) - use `gpd:new-project`. A research map is GPD's summary of an existing folder before full setup.
2. Refresh the research map - use `gpd:map-research`.
3. Take a guided tour first - use `gpd:tour`.

Other useful options, only if one of these is what you need:

- Explain one concept - use `gpd:explain`.
- Show all commands - use `gpd:help --all`.

**This folder already has research files, but GPD is not set up here yet**

Recommended next steps:

1. Map this folder first (recommended) - use `gpd:map-research`.
2. Take a guided tour first - use `gpd:tour`.
3. Start a brand-new GPD project anyway - use `gpd:new-project --minimal`.

Other useful options, only if one of these is what you need:

- Explain one concept - use `gpd:explain`.
- Show all commands - use `gpd:help --all`.

**This folder looks new or mostly empty**

Recommended next steps:

1. Fast start (recommended) - use `gpd:new-project --minimal`.
2. Full guided setup - use `gpd:new-project`.
3. Take a guided tour first - use `gpd:tour`.

Other useful options, only if one of these is what you need:

- Explain one concept - use `gpd:explain`.
- Show all commands - use `gpd:help --all`.

If you need to reopen a different GPD project, use `gpd resume --recent` in your normal terminal first. That is the explicit multi-project picker in the recovery ladder; the rows are advisory, and once you open the selected workspace `gpd:resume-work` reloads its canonical state. If it finds exactly one recoverable project it may auto-select it, otherwise choose from the list. Then open the workspace and continue with `gpd:resume-work`.

Add one final sentence before asking for the choice:

`If you want the broader capability overview before choosing, pick \`tour\`. It will explain later paths such as planning phases, verifying work, writing papers, and handling tangents without changing anything.`

Ask for exactly one choice.
</step>

<step name="route_choice">
Route immediately into the real existing workflow for the chosen path.

Normalize the reply to one stable `option_id`; labels are aliases only.

**If the researcher chooses option_id `resume_work` (`Resume this project (recommended)`, `Continue where I left off`, `Inspect recovery state (recommended)`, or `Inspect recovery state`):**

- Read `{GPD_INSTALL_DIR}/workflows/resume-work.md` with the file-read tool.
- Use `gpd:resume-work` as the selected runtime command label while following that workflow.

**If the researcher chooses option_id `sync_state` (`Reconcile state files`):**

- Read `{GPD_INSTALL_DIR}/workflows/sync-state.md` with the file-read tool.
- Use `gpd:sync-state` as the selected runtime command label while following that workflow.

**If the researcher chooses option_id `progress` (`Review the project status first`, `Review project status first`, or `Review visible progress`):**

- Read `{GPD_INSTALL_DIR}/workflows/progress.md` with the file-read tool.
- Use `gpd:progress` as the selected runtime command label while following that workflow.

**If the researcher chooses option_id `suggest_next` (`Suggest the next best step`):**

- `suggest-next` is a workflow-exempt command, not a shared workflow include.
- Use `gpd:suggest-next` as the selected runtime command label and follow its installed command contract directly.

**If the researcher chooses option_id `map_research` (`Map this folder first (recommended)` or `Refresh the research map`):**

- Read `{GPD_INSTALL_DIR}/workflows/map-research.md` with the file-read tool.
- Use `gpd:map-research` as the selected runtime command label while following that workflow.

**If the researcher chooses option_id `new_project_minimal` (`Fast start (recommended)`, `Fast start`, or `Start a brand-new GPD project anyway`):**

- Use `gpd:new-project --minimal` as the selected runtime command label and follow its installed command contract directly.

**If the researcher chooses option_id `new_project_full` (`Full guided setup`, `Turn this into a full GPD project (recommended)`, or `Turn this into a full GPD project`):**

- Use `gpd:new-project` as the selected runtime command label and follow its installed command contract directly.

**If the researcher chooses option_id `tour` (`Take a guided tour first` or `tour`):**

- Use `gpd:tour` as the selected runtime command label and follow its installed command contract directly.

**If the researcher chooses option_id `quick` (`Do one small bounded task`):**

- Read `{GPD_INSTALL_DIR}/workflows/quick.md` with the file-read tool.
- Use `gpd:quick` as the selected runtime command label while following that workflow.

**If the researcher chooses option_id `explain` (`Explain one concept`):**

- If `$ARGUMENTS` contains a usable concept or question, reuse it.
- Otherwise ask for one short concept or question before continuing.
- Read `{GPD_INSTALL_DIR}/workflows/explain.md` with the file-read tool.
- Use `gpd:explain <topic>` as the selected runtime command label while following that workflow.

**If the researcher chooses option_id `help_all` (`Show all commands`):**

- Use `gpd:help --all` as the selected runtime command label and follow its installed command contract directly.

**If the researcher chooses option_id `reopen_recent` (`Reopen a different GPD project`):**

- Do not silently switch projects from inside the runtime.
- Explain exactly:
  - `Use \`gpd resume --recent\` in your normal terminal to find the project first.`
  - `The recent-project picker is advisory; choose the workspace there, then \`gpd:resume-work\` reloads canonical state for that project.`
  - `If there is exactly one recoverable project, GPD may auto-select it; otherwise choose the project explicitly from the recent-project picker.`
  - `Then open that project folder in the runtime and choose the \`gpd:resume-work\` command.`
  - `In GPD terms, \`resume-work\` is the in-runtime continuation step once the recovery ladder has identified the right project and reopened its workspace.`
- STOP after giving those instructions.
</step>

<step name="guardrails">
Keep the routing strict:

- `gpd:start` is the chooser, not a second implementation of `gpd:new-project`, `gpd:resume-work`, `gpd:map-research`, `gpd:quick`, `gpd:explain`, or `gpd:help`.
- Do not silently create project files from `gpd:start` itself.
- Do not silently switch the user into a different project folder.
- When in doubt between a fresh folder and an existing research folder, prefer `map-research` as the safer recommendation.
- Keep the wording beginner-friendly, but keep the official GPD terms visible in plain-English form so the researcher learns them.
</step>

</process>

<success_criteria>
- [ ] The folder is classified as an existing GPD project, research map only, existing research folder, or fresh folder
- [ ] The researcher sees only the choices that fit that state
- [ ] The chosen path routes into the real existing workflow instead of duplicating it
- [ ] Cross-project recovery stays explicit through `gpd resume --recent` from the normal terminal
- [ ] `gpd:start` stays a beginner-friendly chooser, not a parallel onboarding state machine
</success_criteria>
