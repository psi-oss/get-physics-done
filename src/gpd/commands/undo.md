---
name: gpd:undo
description: Rollback last GPD operation with safety checkpoint
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---


<objective>
Safely rollback the last GPD-related git commit. Creates a safety checkpoint tag before reverting so the operation itself is reversible.

Use this when a plan, execution, or verification produced incorrect results and you want to undo cleanly.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/undo.md
</execution_context>

<context>
@GPD/STATE.md
</context>

<process>
This wrapper runs the undo workflow directly. Any stopping points come from the workflow's own safety gates and confirmation steps.

Execute the included undo workflow end-to-end.
Preserve all safety gates and confirmation steps.
The workflow owns commit selection, impact preview, confirmation, checkpointing, revert behavior, state repair, and merge-commit rejection.

After the workflow completes its revert, preserve its record-backtrack offer: Enter = Y invokes the runtime-installed `gpd:record-backtrack` command with structured runtime arguments for `reverted_commit`, `trigger`, and inferable `phase`. The child workflow still collects remaining required row fields before append. `n` skips; `e` opens the form in-place for freeform edits.
Preserve the `[Y/n/e]` prompt shape.

**SAFETY:** Never undo merge commits. Never force-push. Always create checkpoint first.
</process>

<success_criteria>

- [ ] Undo workflow executed as the authority for rollback mechanics
- [ ] Workflow-owned safety gates and confirmation steps preserved
- [ ] Record-backtrack child command described with structured runtime arguments
</success_criteria>
