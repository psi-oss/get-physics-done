---
name: gpd:update
description: Update GPD to latest version and show recent release notes
context_mode: global
allowed-tools:
  - file_read
  - shell
  - ask_user
---


<objective>
Check for GPD updates, install if available, and display what changed.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/update.md
</execution_context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

Follow the included workflow file exactly.
Keep all update logic (scope detection, target handling, recent release notes, confirmation, install, cache refresh) inside the workflow.
</process>
