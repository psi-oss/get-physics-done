---
name: gpd-new-project
description: Initialize a new physics research project with deep context gathering and PROJECT.md
argument-hint: "[--auto] [--minimal [@file.md]]"
allowed-tools:
  - read_file
  - shell
  - write_file
  - ask_user
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for non-Claude runtimes. -->

<context>
**Flags:**
- `--auto` — Automatic mode. After config questions, runs research → requirements → roadmap without further interaction. Expects research proposal document via @ reference.
- `--minimal` — Skip deep questioning, literature survey, requirements elaboration, and roadmapper agent. Creates all `.planning/` artifacts from a single description or input file with sensible defaults. Use for fast bootstrapping when you know your research plan.
- `--minimal @file.md` — Create project directly from a markdown file describing your research and phases. Parses research question, phases, and key parameters from the file.
</context>

<objective>
Initialize a new physics research project through unified flow: questioning → literature survey (optional) → requirements → roadmap.

**Creates:**

- `.planning/PROJECT.md` — research project context
- `.planning/config.json` — workflow preferences
- `.planning/research/` — domain and literature research (optional)
- `.planning/REQUIREMENTS.md` — scoped research requirements
- `.planning/ROADMAP.md` — phase structure
- `.planning/STATE.md` — project memory

**After this command:** Run `$gpd-plan-phase 1` to start execution.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/new-project.md
@{GPD_INSTALL_DIR}/references/questioning.md
@{GPD_INSTALL_DIR}/references/ui-brand.md
@{GPD_INSTALL_DIR}/templates/project.md
@{GPD_INSTALL_DIR}/templates/requirements.md
</execution_context>

<process>
Execute the new-project workflow from @{GPD_INSTALL_DIR}/workflows/new-project.md end-to-end.
Preserve all workflow gates (validation, approvals, commits, routing).

## Flag Detection

Check `$ARGUMENTS` for flags:

- **`--auto`** → Auto mode (skip questioning, synthesize from provided document)
- **`--minimal`** → Minimal mode (fast bootstrapping path)
- **`--minimal @file.md`** → Minimal mode with input file

**If `--minimal` detected:** After Setup, route to the **minimal initialization path** in the workflow. This skips deep questioning and research, replacing them with a streamlined flow that creates the same file set with less content.

**If `--auto` detected:** After Setup, skip questioning. Extract context from provided document. Config questions still required. Then run research → requirements → roadmap automatically with smart defaults.
</process>

<output>

- `.planning/PROJECT.md`
- `.planning/config.json`
- `.planning/research/` (if research selected)
  - `PRIOR-WORK.md`
  - `METHODS.md`
  - `COMPUTATIONAL.md`
  - `PITFALLS.md`
  - `SUMMARY.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/CONVENTIONS.md` (established by gpd-notation-coordinator)

</output>

<success_criteria>

**Full mode success criteria:**
- [ ] .planning/ directory created and git repo initialized
- [ ] Deep questioning completed (research context fully captured)
- [ ] PROJECT.md created with full context -- committed
- [ ] config.json created with workflow settings -- committed
- [ ] Literature survey completed (if selected) -- committed
- [ ] REQUIREMENTS.md created with REQ-IDs -- committed
- [ ] ROADMAP.md created with phases and requirement mappings -- committed
- [ ] STATE.md initialized
- [ ] CONVENTIONS.md created via gpd-notation-coordinator -- committed
- [ ] Convention lock populated via gpd convention set
- [ ] User informed next step is $gpd-discuss-phase 1

**Minimal mode success criteria (if `--minimal`):**

- [ ] .planning/ directory created
- [ ] Git repo initialized
- [ ] PROJECT.md created from single description or input file → **committed**
- [ ] ROADMAP.md created with phases derived from input → **committed**
- [ ] REQUIREMENTS.md created with auto-generated REQ-IDs → **committed**
- [ ] STATE.md initialized → **committed**
- [ ] config.json created with defaults → **committed**
- [ ] All files committed in single commit: "docs: initialize research project (minimal)"
- [ ] Same directory structure and file set as full path
- [ ] User offered "Plan phase 1 now?"

</success_criteria>
