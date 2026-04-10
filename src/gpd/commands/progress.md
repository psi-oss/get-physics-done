---
name: gpd:progress
description: Check research progress, show context, and route to next action (execute or plan)
argument-hint: "[--brief | --full | --reconcile]"
context_mode: project-required
project_reentry_capable: true
requires:
  files: ["GPD/PROJECT.md"]
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---

<objective>
Check physics research progress and route to the next action.

Runtime note: `--brief`, `--full`, and `--reconcile` are runtime-surface
options for `gpd:progress`. The local CLI `gpd progress` is a separate
read-only renderer that takes `json|bar|table` and does not accept these flags.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/progress.md
</execution_context>

<process>
Read `{GPD_INSTALL_DIR}/workflows/progress.md` with the file-read tool and follow it exactly. Do not duplicate the workflow logic here.
</process>
