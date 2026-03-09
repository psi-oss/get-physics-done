---
name: gpd-compare-branches
description: Compare results across hypothesis branches side-by-side
argument-hint: ""
allowed-tools:
  - read_file
  - shell
  - grep
  - glob
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Compare research results across hypothesis branches to determine which approach is more promising.

Builds a structured comparison table from STATE.md and SUMMARY files across all hypothesis/\* branches, assessing key results, verification status, approximation validity, and context usage. Offers to merge the winning branch back to main and clean up.

Use after two or more hypothesis branches have produced results that can be meaningfully compared.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compare-branches.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<process>
Execute the compare-branches workflow from @{GPD_INSTALL_DIR}/workflows/compare-branches.md end-to-end.
Preserve all validation gates (branch listing, state extraction, comparison building, merge confirmation).
</process>
