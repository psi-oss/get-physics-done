---
name: gpd:numerical-convergence
description: Systematic convergence testing for numerical physics computations
argument-hint: "[phase number or file path]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - ask_user
---

<objective>
Systematic convergence testing for numerical physics computations. Keep this command wrapper thin; the workflow owns detailed method guidance.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/numerical-convergence.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Execute the workflow at `@{GPD_INSTALL_DIR}/workflows/numerical-convergence.md` end-to-end. Do not restate workflow-owned checklists or compatibility policy here.
</process>
