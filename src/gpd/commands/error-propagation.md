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
Route an uncertainty-propagation request into the workflow-owned implementation.

This wrapper owns the public command surface and target request. The workflow owns project bootstrap, context validation, dependency tracing, uncertainty classification, sensitivity/error-budget computation, artifact writing, and state updates.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/error-propagation.md
</execution_context>

<context>
Target: $ARGUMENTS

@GPD/ROADMAP.md
@GPD/STATE.md
</context>

<process>
Execute @{GPD_INSTALL_DIR}/workflows/error-propagation.md end-to-end.
Preserve the workflow-owned context preflight, result/dependency lookup, phase-backed output resolution, and canonical uncertainty state updates.
</process>

<success_criteria>

- [ ] Error-propagation workflow executed as the authority for mechanics
- [ ] Target request, phase range, and output path resolved by workflow-owned preflight
- [ ] Error budget and uncertainty state updates follow the workflow contract
      </success_criteria>
