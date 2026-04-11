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
Track how uncertainties propagate through multi-step calculations across phases. Keep this command wrapper thin; the workflow owns detailed method guidance.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/error-propagation.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Execute the workflow at `@{GPD_INSTALL_DIR}/workflows/error-propagation.md` end-to-end. Do not restate workflow-owned checklists or compatibility policy here.
</process>
