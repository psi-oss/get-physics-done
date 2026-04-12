---
name: gpd:execute-phase
description: Execute all plans in a phase with wave-based parallelization
argument-hint: "<phase-number> [--gaps-only]"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md"]
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - find_files
  - search_files
  - shell
  - task
  - ask_user
---

<objective>
Execute all phase plans with wave-based parallelization by following `@{GPD_INSTALL_DIR}/workflows/execute-phase.md`.
Context budget: ~15% orchestrator, fresh context per subagent.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/execute-phase.md
</execution_context>

<context>
Phase: $ARGUMENTS

**Flags and cadence:** The workflow linked below defines `--gaps-only`, review cadence values, and their execution consequences.
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

Follow the included workflow file exactly.
</process>
