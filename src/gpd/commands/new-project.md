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
- `--minimal` — Fast staged-init mode. Uses one structured intake plus one scoping approval gate, then creates the core project artifacts with lean content. Scope, anchors, and decisive outputs are still required.
- `--minimal @file.md` — Create project directly from a markdown file describing your research and staged continuation path. Parses research question, anchors, and key work chunks from the file.
</context>

<objective>
Initialize a new physics research project through one flow: questioning or structured intake → scoping contract approval → literature survey (optional) → requirements → staged roadmap/conventions handoff when that mode creates them.

If no project config exists yet, start with physics questioning, surface a preset choice before workflow preferences, and ask detailed config questions only after scope approval and before the first project-artifact commit.

**Full mode creates:**

- `GPD/PROJECT.md` — project context
- `GPD/config.json` — workflow preferences
- `GPD/literature/` — optional domain and literature survey
- `GPD/REQUIREMENTS.md` — scoped requirements
- `GPD/ROADMAP.md` — phase structure
- `GPD/STATE.md` — project memory
- `GPD/state.json` `project_contract` — authoritative machine-readable scoping contract
- `GPD/CONVENTIONS.md` — notation conventions, established after the staged roadmap

**Minimal mode creates only the core startup set:** `GPD/PROJECT.md`, `GPD/config.json`, `GPD/REQUIREMENTS.md`, `GPD/ROADMAP.md`, `GPD/STATE.md`, and `GPD/state.json` with the approved `project_contract`. It does not promise `GPD/literature/` or `GPD/CONVENTIONS.md`.

**After this command:** Run `gpd:discuss-phase 1`; show native runtime label.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/new-project.md
</execution_context>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read the included workflow first and follow it exactly.

After that, load late-stage authorities only when the workflow reaches the matching stage:
- Read {GPD_INSTALL_DIR}/references/research/questioning.md only when entering the full questioning path.
- Read {GPD_INSTALL_DIR}/templates/project-contract-schema.md and {GPD_INSTALL_DIR}/templates/project-contract-grounding-linkage.md only when preparing the approval gate and validating the raw scoping contract.
- Read {GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md only when authoring or repairing the scoping contract.
- Read {GPD_INSTALL_DIR}/templates/project.md only when writing `GPD/PROJECT.md`.
- Read {GPD_INSTALL_DIR}/templates/requirements.md only when writing `GPD/REQUIREMENTS.md`.
- Read {GPD_INSTALL_DIR}/templates/state.md only when writing `GPD/STATE.md`.
- Read {GPD_INSTALL_DIR}/references/ui/ui-brand.md only when rendering branded completion or status blocks.

Execute the workflow end-to-end. Preserve all workflow gates (validation, approvals, routing).

## Flag Detection

Check `$ARGUMENTS` for flags:

- **`--auto`** → Structured synthesis + scope approval
- **`--minimal`** → Fast staged-init with scope approval
- **`--minimal @file.md`** → Minimal mode with input file

**If both `--auto` and `--minimal` are detected:** stop before any writes with:

```text
Error: --auto and --minimal cannot be combined.

Choose either `gpd:new-project --auto @proposal.md` for full auto intake or
`gpd:new-project --minimal [@file.md]` for the lean core-artifact path.
```

This conflict stop happens before git initialization, `GPD/` creation, or state/progress writes.

**If `--minimal` detected:** After Setup and existing-work routing, route to the **minimal staged initialization path**. It keeps intake to one response, still requires a scoping contract with decisive outputs and anchors, and creates the lean core artifact set without promising literature or convention files.

**If `--auto` detected:** After Setup, synthesize context from the provided document, repair blocking gaps only, present the scoping contract for approval, then run research → requirements → roadmap with smart defaults.

Do not initialize git in Setup. The workflow initializes git only at its first mutation gate after invalid arguments, existing-work routing, recovery routing, and explicit scope approval have all passed.
</process>

<output>

**Full mode output:**

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
- `GPD/state.json` `project_contract`
- `GPD/CONVENTIONS.md` (established by gpd-notation-coordinator)

**Minimal mode output:**

- `GPD/PROJECT.md`
- `GPD/config.json`
- `GPD/REQUIREMENTS.md`
- `GPD/ROADMAP.md`
- `GPD/STATE.md`
- `GPD/state.json` `project_contract`

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
- [ ] Minimal output is limited to the documented core startup set; no literature or conventions artifact is promised
- [ ] User offered "Discuss phase 1 now?"

</success_criteria>
