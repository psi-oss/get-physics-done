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

<context>
**Flags:**
- `--auto` — Automatic mode. Synthesizes a scoping contract from the supplied document, asks for one explicit scope approval, then runs research → requirements → roadmap with minimal follow-up interaction. Expects a research proposal document via @ reference.
- `--minimal` — Fast staged-init mode. Uses one structured intake plus one scoping approval gate, then hands the roadmap and conventions to the staged post-scope agents with lean content. Scope, anchors, and decisive outputs are still required.
- `--minimal @file.md` — Create project directly from a markdown file describing your research and staged continuation path. Parses research question, anchors, and key work chunks from the file.
</context>

<objective>
Initialize a new physics research project through one flow: questioning or structured intake → scoping contract approval → literature survey (optional) → requirements → staged roadmap/conventions handoff.

If no project config exists yet, start with physics questioning, surface a preset choice before workflow preferences, and ask detailed config questions only after scope approval and before the first project-artifact commit.

**Creates:**

- `GPD/PROJECT.md` — project context
- `GPD/config.json` — workflow preferences
- `GPD/literature/` — optional domain and literature survey
- `GPD/REQUIREMENTS.md` — scoped requirements
- `GPD/ROADMAP.md` — phase structure
- `GPD/STATE.md` — project memory
- `GPD/state.json` `project_contract` — authoritative machine-readable scoping contract

**After this command:** Run `gpd:discuss-phase 1` to clarify the first phase before planning.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/new-project.md
</execution_context>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read {GPD_INSTALL_DIR}/workflows/new-project.md first and follow it exactly.

After that, load late-stage authorities only when the workflow reaches the matching stage:
- Read {GPD_INSTALL_DIR}/references/research/questioning.md only when entering the full questioning path.
- Read {GPD_INSTALL_DIR}/templates/project-contract-schema.md and {GPD_INSTALL_DIR}/templates/project-contract-grounding-linkage.md only when preparing the approval gate and validating the raw scoping contract.
- Read {GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md only when authoring or repairing the scoping contract.
- Read {GPD_INSTALL_DIR}/templates/project.md only when writing `GPD/PROJECT.md`.
- Read {GPD_INSTALL_DIR}/templates/requirements.md only when writing `GPD/REQUIREMENTS.md`.
- Read {GPD_INSTALL_DIR}/references/ui/ui-brand.md only when rendering branded completion or status blocks.

Execute the workflow end-to-end. Preserve all workflow gates (validation, approvals, routing).

## Flag Detection

Check `$ARGUMENTS` for flags:

- **`--auto`** → Structured synthesis + scope approval
- **`--minimal`** → Fast staged-init with scope approval
- **`--minimal @file.md`** → Minimal mode with input file

**If `--minimal` detected:** After Setup, route to the **minimal staged initialization path**. It keeps intake to one response, still requires a scoping contract with decisive outputs and anchors, and then hands roadmap and conventions creation to the staged post-scope agents instead of building them directly in the main context.

**If `--auto` detected:** After Setup, synthesize context from the provided document, repair blocking gaps only, present the scoping contract for approval, then run research → requirements → roadmap with smart defaults.
</process>

<output>

- `GPD/PROJECT.md`
- `GPD/config.json`
- `GPD/literature/` (if literature survey selected)
  - `PRIOR-WORK.md`
  - `METHODS.md`
  - `COMPUTATIONAL.md`
  - `PITFALLS.md`
  - `SUMMARY.md`
- `GPD/REQUIREMENTS.md`
- `GPD/ROADMAP.md`
- `GPD/STATE.md`
- `GPD/CONVENTIONS.md` (established by gpd-notation-coordinator)

</output>

<success_criteria>

**Full mode success criteria:**
- [ ] `GPD/` exists and the repo is initialized
- [ ] Deep questioning captured the research context
- [ ] Scoping contract captures decisive outputs, anchors, weakest assumptions, and unresolved gaps
- [ ] Scoping contract is explicitly approved before requirements or roadmap generation
- [ ] `PROJECT.md` created and committed
- [ ] `config.json` created and committed
- [ ] Literature survey completed if selected and committed
- [ ] `REQUIREMENTS.md` created with REQ-IDs and committed
- [ ] `ROADMAP.md` created with phases and requirement mappings and committed
- [ ] `STATE.md` initialized
- [ ] `CONVENTIONS.md` created via `gpd-notation-coordinator` and committed
- [ ] Convention lock populated via `gpd convention set`
- [ ] User told the next step is `gpd:discuss-phase 1`

**Minimal mode success criteria (if `--minimal`):**

- [ ] `GPD/` created and the repo initialized
- [ ] Structured intake captured the core question, decisive outputs, anchors, and known gaps
- [ ] Scoping contract approved before requirements or roadmap generation
- [ ] `PROJECT.md` created from one description or input file and committed
- [ ] `ROADMAP.md` created from the input and committed
- [ ] `REQUIREMENTS.md` created with auto-generated REQ-IDs and committed
- [ ] `STATE.md` initialized and committed
- [ ] `config.json` created with defaults and committed
- [ ] All files committed in one commit: `docs: initialize research project (minimal)`
- [ ] Same directory structure and file set as full path
- [ ] User offered "Discuss phase 1 now?"

</success_criteria>
