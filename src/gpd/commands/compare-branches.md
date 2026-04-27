---
name: gpd:compare-branches
description: Compare results across hypothesis branches side-by-side
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---


<objective>
Compare research results across hypothesis branches to determine which approach is more promising.

Builds a structured comparison table from STATE.md and SUMMARY files across all hypothesis/\* branches, assessing key results, verification status, approximation validity, and context usage. Offers to merge the winning branch back to main and clean up.

Use after two or more hypothesis branches have produced results that can be meaningfully compared.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compare-branches.md
</execution_context>

<context>
@GPD/STATE.md
</context>

<process>
Execute the included compare-branches workflow end-to-end.
Preserve all validation gates (branch listing, state extraction, comparison building, merge confirmation).
</process>
