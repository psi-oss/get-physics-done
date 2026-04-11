---
name: gpd:parameter-sweep
description: Systematic parameter sweep with parallel execution and result aggregation
argument-hint: "[phase] [--param name --range start:end:steps] [--adaptive] [--log]"
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
Systematic parameter sweep with parallel execution and result aggregation. Keep this command wrapper thin; the workflow owns detailed method guidance.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/parameter-sweep.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Execute the workflow at `@{GPD_INSTALL_DIR}/workflows/parameter-sweep.md` end-to-end. Do not restate workflow-owned checklists or compatibility policy here.
</process>
