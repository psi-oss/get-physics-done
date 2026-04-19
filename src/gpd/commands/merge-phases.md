---
name: gpd:merge-phases
description: Merge results from one phase into another
argument-hint: "<source-phase> <target-phase>"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
---


<objective>
Merge results, artifacts, and state updates from a source phase into a target phase.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/merge-phases.md
</execution_context>

<context>
Format: `<source-phase> <target-phase>` — first argument is the source phase, second is the target phase.
Source phase: first argument (e.g., "2.1")
Target phase: second argument (e.g., "2")

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
This wrapper runs the merge workflow directly. Follow `@{GPD_INSTALL_DIR}/workflows/merge-phases.md` exactly; any stopping points come from that workflow's validation gates.
</process>
