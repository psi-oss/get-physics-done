---
name: gpd:revise-phase
description: Supersede a completed phase and create a replacement for iterative revision
argument-hint: '<phase-number> <reason for revision>'
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Supersede a completed research phase and create a replacement phase for iterative revision. Preserves the original phase as historical record while creating a new phase that inherits valid decisions and addresses what needs to change.

Purpose: Support non-linear research where earlier results must be revisited after new insights. Common reasons include:

- A later calculation revealed a flawed assumption in an earlier phase
- Referee feedback requires reworking a derivation with a different method
- New experimental data invalidates a key result
- A sign error or approximation breakdown was discovered downstream
- A better approach became apparent after completing subsequent phases

Output: Original phase marked as superseded, replacement phase created with inherited context, downstream dependencies updated, git commit as historical record.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/revise-phase.md
</execution_context>

<context>
Arguments: $ARGUMENTS (format: <phase-number> "<reason for revision>")

@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>
Parse arguments: the phase number is the first token, everything after the first space is the reason for revision.

Execute the revise-phase workflow from @{GPD_INSTALL_DIR}/workflows/revise-phase.md end-to-end.
Preserve all validation gates (completed phase check, scope analysis, supersession marking, dependency updates) and commit.
</process>
