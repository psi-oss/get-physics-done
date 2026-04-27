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
Execute phase plans through the workflow-owned wave executor.

The workflow owns plan discovery, wave grouping, subagent dispatch, checkpoint routing, verification gates, state updates, and resumption.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/execute-phase.md
</execution_context>

<arguments>
Phase: $ARGUMENTS

- `--gaps-only` executes only gap-closure plans (`gap_closure: true`).
</arguments>

<process>
Read `{GPD_INSTALL_DIR}/workflows/execute-phase.md` first and follow it end-to-end.
</process>
