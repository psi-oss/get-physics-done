---
name: gpd:sensitivity-analysis
description: Systematic sensitivity analysis -- which parameters matter most and how uncertainties propagate
argument-hint: "[--target quantity] [--params p1,p2,...] [--method analytical|numerical]"
context_mode: project-aware
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
Systematic sensitivity analysis -- which parameters matter most and how uncertainties propagate. Keep this command wrapper thin; the workflow owns detailed method guidance.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Run `gpd --raw validate command-context sensitivity-analysis` before execution.

Execute the workflow at `@{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md` end-to-end. Do not restate workflow-owned checklists or compatibility policy here.
</process>
