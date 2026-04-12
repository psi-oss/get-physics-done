---
name: gpd:error-propagation
description: Track how uncertainties propagate through multi-step calculations across phases
argument-hint: "[--target quantity] [--phase-range start:end]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - find_files
  - search_files
  - task
  - ask_user
---

<objective>
Track uncertainty propagation through multi-step calculations across phases via the workflow.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/error-propagation.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Keep this command wrapper thin; the workflow owns detailed method guidance. Do not restate workflow-owned checklists or compatibility policy here.
Execute the workflow end-to-end; keep method details in `@{GPD_INSTALL_DIR}/workflows/error-propagation.md`.
</process>
