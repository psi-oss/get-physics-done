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
- `--auto` — Automatic mode: synthesize a scoping contract from one document, ask for a single scope approval, then run research → requirements → roadmap with minimal back-and-forth. Requires a research proposal markdown via `@`.
- `--minimal` — Fast staged-init: one structured intake, one scoping approval gate, then hand the roadmap and conventions over to the post-scope agents with lean content. Decisive scope, anchors, and outputs are still required.
- `--minimal @file.md` — Build the project directly from the supplied markdown description, parsing the research question, anchors, and the continuation plan inside.
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
Follow the workflow file exactly before proceeding.
Read the workflow referenced in `<execution_context>` with `file_read` first.

**Scoping contract visibility:** Before drafting or repairing the scoping contract, The workflow owns the `project-contract-schema.md` and `project-contract-grounding-linkage.md` details. Preserve decisive outputs, anchors, and roadmap generation inputs, and require one explicit scope approval before downstream generation.

**Next-step prompt:** After roadmap creation, ask exactly: "Discuss phase 1 now?"

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
