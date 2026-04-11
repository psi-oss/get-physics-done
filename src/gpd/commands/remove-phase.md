---
name: gpd:remove-phase
description: Remove a future research phase from roadmap and renumber subsequent phases
argument-hint: <phase-number>
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
---


<objective>
Remove an unstarted future phase from the roadmap and renumber all subsequent phases to maintain a clean, linear sequence.

Purpose: Clean removal of research work you have decided not to pursue, without polluting context with cancelled/deferred markers. Common reasons include:

- A calculation turned out to be analytically tractable, eliminating the need for a planned numerical phase
- A validation step became redundant after finding an exact solution
- Scope reduction after realizing a particular physical regime is outside the problem domain
- Consolidation of multiple small phases into a single phase

Output: Phase deleted, all subsequent phases renumbered, gpd commit as historical record.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/remove-phase.md
</execution_context>

<context>
Phase: $ARGUMENTS

@GPD/ROADMAP.md
@GPD/STATE.md
</context>

<process>
This wrapper runs the remove-phase workflow directly. Any stopping points come from the workflow's own validation gates.

Execute the remove-phase workflow from @{GPD_INSTALL_DIR}/workflows/remove-phase.md end-to-end.
Preserve all validation gates (future phase check, work check), renumbering logic, and commit.
</process>
