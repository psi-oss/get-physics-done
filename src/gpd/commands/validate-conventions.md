---
name: gpd:validate-conventions
description: Validate convention consistency across all phases
argument-hint: "[phase number to limit scope, or empty for all]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
  - task
---


<objective>
Validate that physics conventions are used consistently across completed phases, and detect convention drift where symbols or conventions are redefined without updating earlier references.

The optional scope argument is real: if you pass a phase number, the workflow validates only that phase and fails closed if the phase cannot be resolved. If you pass nothing, it scans all completed phases.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/validate-conventions.md
</execution_context>

<context>
Scope: $ARGUMENTS (optional)
- If a number (e.g., "3"): validate conventions only for that phase
- If empty: validate conventions across all completed phases
- Any other input is rejected by command-context validation instead of being guessed

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/validate-conventions.md` exactly.
</process>
