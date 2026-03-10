---
name: gpd:insert-phase
description: Insert urgent research work as decimal phase (e.g., 72.1) between existing phases
argument-hint: '<after-phase> "<description>"'
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Insert a decimal phase for urgent research work discovered mid-milestone that must be completed between existing integer phases.

Uses decimal numbering (72.1, 72.2, etc.) to preserve the logical sequence of planned phases while accommodating urgent insertions.

Purpose: Handle urgent research tasks discovered during execution without renumbering entire roadmap. Common triggers include:

- A reviewer pointed out a missing limiting case that must be checked before proceeding
- A numerical instability requires an unplanned convergence study
- New literature surfaced that demands an additional comparison
- A sign error or dimensional inconsistency requires re-deriving intermediate results
- An unexpected physical regime requires additional analytical treatment
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/insert-phase.md
</execution_context>

<context>
Arguments: $ARGUMENTS (format: <after-phase-number> <description>)

@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>
Parse arguments: first token is the phase number, everything after the first space is the description.

Execute the insert-phase workflow from @{GPD_INSTALL_DIR}/workflows/insert-phase.md end-to-end.
Preserve all validation gates (argument parsing, phase verification, decimal calculation, roadmap updates).
</process>
