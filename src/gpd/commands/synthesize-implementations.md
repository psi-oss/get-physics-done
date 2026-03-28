---
name: gpd:synthesize-implementations
description: Compare N independent implementations and compose a unified solution from the best parts of each
argument-hint: "[directory or list of implementation paths]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - ask_user
---

<objective>
Given N independent implementations of the same simulation or computation, produce a unified implementation that cherry-picks the best components from each. The output is a single working codebase with a provenance table mapping every module to its source implementation.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/synthesize-implementations.md
</execution_context>

<process>

1. Confirm with the user which implementations to compare and where they live
2. Follow the workflow in `synthesize-implementations.md` — inventory, convention audit, score, compose, validate, document provenance
3. At the scoring step, present the comparison matrix to the user and confirm the selection before composing
4. After validation, present the provenance table and verification results

</process>
