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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Merge the results, artifacts, and state updates from a source phase into a target phase. Useful when phases are reorganized, when a decimal phase (e.g., 2.1) needs to be folded back into its parent, or when parallel investigation branches converge.

Routes to the merge-phases workflow which handles:

- Validating both phases exist
- Copying artifacts (summaries, plans, data files)
- Merging intermediate results and decisions
- Updating the roadmap to reflect the merge
- Updating STATE.md with merge record
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/merge-phases.md
</execution_context>

<context>
Format: `<source-phase> <target-phase>` — first argument is the source phase, second is the target phase.
Source phase: first argument (e.g., "2.1")
Target phase: second argument (e.g., "2")

@.gpd/STATE.md
@.gpd/ROADMAP.md
</context>

<process>
Execute the merge-phases workflow from @{GPD_INSTALL_DIR}/workflows/merge-phases.md end-to-end.

If `--dry-run` flag is present, show the merge plan (which artifacts would move, which results would combine) without executing any changes.

The workflow handles:

1. **Validation** -- Both phases exist, source has completed work, target is compatible
2. **Artifact merge** -- Copy summaries, plans, data files from source to target
3. **Result merge** -- Combine intermediate results, avoiding duplicates
4. **Decision merge** -- Merge decisions with phase attribution preserved
5. **Roadmap update** -- Mark source phase as merged, update target description
6. **State update** -- Record the merge as a decision in STATE.md
</process>
