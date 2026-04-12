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
Run a systematic parameter sweep with parallel execution and result aggregation through the workflow.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/parameter-sweep.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

Keep this command wrapper thin; the workflow owns detailed method guidance. Do not restate workflow-owned checklists or compatibility policy here.
</process>
