---
name: gpd:resume-work
description: Resume research from previous session with full context restoration
context_mode: project-required
project_reentry_capable: true
requires:
  files: ["GPD/ROADMAP.md"]
allowed-tools:
  - file_read
  - shell
  - file_write
  - ask_user
---


<objective>
Resume research from the selected project's canonical state.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/resume-work.md
</execution_context>

<process>
Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/resume-work.md`.
</process>
