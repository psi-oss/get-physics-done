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
Rank parameter influence and uncertainty propagation through the workflow.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md
</execution_context>

<context>
Target: $ARGUMENTS

If the target is empty, ask one concise clarification before proceeding. Otherwise interpret numbers as phase ids and paths as artifact targets.
</context>

<process>
Keep this command wrapper thin; the workflow owns detailed method guidance. Do not restate workflow-owned checklists or compatibility policy here.
Run `gpd --raw validate command-context sensitivity-analysis` before execution, then execute the workflow end-to-end; keep method details in `@{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md`.
</process>
