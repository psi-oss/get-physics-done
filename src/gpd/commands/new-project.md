---
name: gpd:new-project
description: Initialize a new physics research project with deep context gathering and PROJECT.md
argument-hint: "[--auto] [--minimal [@file.md]]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
  - file_write
  - task
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<context>
**Flags:**
- `--auto` — Automatic mode. Synthesizes a scoping contract from the supplied document, asks for one explicit scope approval, then runs research → requirements → roadmap with minimal follow-up interaction. Expects a research proposal document via @ reference.
- `--minimal` — Fast bootstrapping mode. Uses one structured intake plus one scoping approval gate, then creates all `.gpd/` artifacts with lean content. Scope, anchors, and decisive outputs are still required.
- `--minimal @file.md` — Create project directly from a markdown file describing your research and phases. Parses research question, phases, and key parameters from the file.
</context>

<objective>
Initialize a new physics research project through unified flow: questioning or structured intake → scoping contract approval → literature survey (optional) → requirements → roadmap.

If no project config exists yet, the workflow offers an early interaction-style choice before long setup steps so `babysit` can affect initialization rather than only later phases.

**Creates:**

- `.gpd/PROJECT.md` — research project context
- `.gpd/config.json` — workflow preferences
- `.gpd/research/` — domain and literature research (optional)
- `.gpd/REQUIREMENTS.md` — scoped research requirements
- `.gpd/ROADMAP.md` — phase structure
- `.gpd/STATE.md` — project memory
- `.gpd/state.json` `project_contract` — authoritative machine-readable scoping contract

**After this command:** Run `/gpd:plan-phase 1` to start execution.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/new-project.md
@{GPD_INSTALL_DIR}/references/research/questioning.md
@{GPD_INSTALL_DIR}/references/ui/ui-brand.md
@{GPD_INSTALL_DIR}/templates/project.md
@{GPD_INSTALL_DIR}/templates/requirements.md
@{GPD_INSTALL_DIR}/templates/state-json-schema.md
</execution_context>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read the file at {GPD_INSTALL_DIR}/workflows/new-project.md — this contains the complete step-by-step instructions (1693 lines) for initializing a research project. Do NOT improvise. Follow the workflow file exactly.

Also read these reference files:
- {GPD_INSTALL_DIR}/references/research/questioning.md (questioning protocol)
- {GPD_INSTALL_DIR}/templates/project.md (PROJECT.md template)
- {GPD_INSTALL_DIR}/templates/requirements.md (REQUIREMENTS.md template)
- {GPD_INSTALL_DIR}/templates/state-json-schema.md (project contract object shape and ID linkage rules)

Before synthesizing or revising the raw `project_contract`, use the `project_contract` section of `state-json-schema.md` as the schema source of truth. Do not invent ad-hoc fields, replace object arrays with strings, or create unresolved ID references.

Execute the workflow end-to-end. Preserve all workflow gates (validation, approvals, routing).

## Flag Detection

Check `$ARGUMENTS` for flags:

- **`--auto`** → Auto mode (structured document synthesis + scope approval)
- **`--minimal`** → Minimal mode (fast bootstrapping path with scope approval)
- **`--minimal @file.md`** → Minimal mode with input file

**If `--minimal` detected:** After Setup, route to the **minimal initialization path** in the workflow. This compresses questioning and research, but still requires a scoping contract with decisive outputs, anchors, and explicit approval before downstream artifacts.

**If `--auto` detected:** After Setup, synthesize context from the provided document, repair only blocking gaps, present the scoping contract for approval, then run research → requirements → roadmap automatically with smart defaults.
</process>

<output>

- `.gpd/PROJECT.md`
- `.gpd/config.json`
- `.gpd/research/` (if research selected)
  - `PRIOR-WORK.md`
  - `METHODS.md`
  - `COMPUTATIONAL.md`
  - `PITFALLS.md`
  - `SUMMARY.md`
- `.gpd/REQUIREMENTS.md`
- `.gpd/ROADMAP.md`
- `.gpd/STATE.md`
- `.gpd/CONVENTIONS.md` (established by gpd-notation-coordinator)

</output>

<success_criteria>

**Full mode success criteria:**
- [ ] .gpd/ directory created and git repo initialized
- [ ] Deep questioning completed (research context fully captured)
- [ ] Scoping contract captures decisive outputs, anchors, weakest assumptions, and unresolved gaps
- [ ] Scoping contract explicitly approved before requirements or roadmap generation
- [ ] PROJECT.md created with full context -- committed
- [ ] config.json created with workflow settings -- committed
- [ ] Literature survey completed (if selected) -- committed
- [ ] REQUIREMENTS.md created with REQ-IDs -- committed
- [ ] ROADMAP.md created with phases and requirement mappings -- committed
- [ ] STATE.md initialized
- [ ] CONVENTIONS.md created via gpd-notation-coordinator -- committed
- [ ] Convention lock populated via gpd convention set
- [ ] User informed next step is /gpd:discuss-phase 1

**Minimal mode success criteria (if `--minimal`):**

- [ ] .gpd/ directory created
- [ ] Git repo initialized
- [ ] Structured intake captured core question, decisive outputs, anchors, and known gaps
- [ ] Scoping contract approved before requirements or roadmap generation
- [ ] PROJECT.md created from single description or input file → **committed**
- [ ] ROADMAP.md created with phases derived from input → **committed**
- [ ] REQUIREMENTS.md created with auto-generated REQ-IDs → **committed**
- [ ] STATE.md initialized → **committed**
- [ ] config.json created with defaults → **committed**
- [ ] All files committed in single commit: "docs: initialize research project (minimal)"
- [ ] Same directory structure and file set as full path
- [ ] User offered "Plan phase 1 now?"

</success_criteria>
