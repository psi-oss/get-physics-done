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
Run systematic convergence testing for numerical physics computations through the workflow.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/numerical-convergence.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

Keep this command wrapper thin; the workflow owns detailed method guidance. Do not restate workflow-owned checklists or compatibility policy here.
</process>
