---
name: gpd:reapply-patches
description: Reapply local modifications after a GPD update
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - find_files
  - search_files
  - ask_user
---


<objective>
Route local-patch reapplication into the workflow-owned implementation.

This wrapper owns the public command surface only. The same-named workflow owns patch discovery, merge/conflict handling, cleanup choices, and reporting.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/reapply-patches.md
</execution_context>

<process>
Follow the included reapply-patches workflow.
</process>

<success_criteria>

- [ ] Reapply-patches workflow executed as the authority for mechanics
</success_criteria>
