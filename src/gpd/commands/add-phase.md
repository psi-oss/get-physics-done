---
name: gpd:add-phase
description: Add research phase to end of current milestone in roadmap
argument-hint: <description>
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
---


<objective>
Add a new integer phase to the end of the current milestone in the roadmap.
Delegate numbering, slug creation, directory scaffolding, and roadmap/state updates to the workflow described in `@{GPD_INSTALL_DIR}/workflows/add-phase.md`.
</objective>

<execution_context>
@GPD/ROADMAP.md
@GPD/STATE.md
@{GPD_INSTALL_DIR}/workflows/add-phase.md
</execution_context>

<process>
Follow the add-phase workflow in `@{GPD_INSTALL_DIR}/workflows/add-phase.md`, which covers argument validation, the delegated `gpd phase add` call, roadmap insertion, and STATE.md/state.json bookkeeping.

The workflow also emits the completion summary with the new phase number, directory path, and a reminder to plan the phase before moving on.
</process>

<success_criteria>
- `gpd phase add` or equivalent workflow step completed successfully.
- `GPD/phases/{NN}-{slug}/` directory exists and is listed in `GPD/ROADMAP.md` with the new phase entry.
- `gpd state add-decision` (or equivalent) recorded the new phase and updated the last activity timestamp so STATE.md/state.json stay in sync.
- The completion summary points the user to planning the new phase (e.g., `gpd:plan-phase {NN}`).
</success_criteria>
