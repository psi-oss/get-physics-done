---
name: gpd:branch-hypothesis
description: Create a hypothesis branch for parallel investigation of an alternative approach
argument-hint: "<description>"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md", "GPD/STATE.md"]
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
---


<objective>
Create a git branch for investigating an alternative hypothesis or approach in parallel with the main line of research.

Hypothesis branches allow a researcher to explore "what if?" questions without polluting the main research state. Each branch gets its own STATE.md fork and hypothesis documentation, enabling side-by-side comparison later via gpd:compare-branches.

Common triggers:

- Two valid approximation schemes and you want to compare both
- A reviewer suggests an alternative derivation pathway
- Numerical instability might be resolved by a different algorithm
- An alternative physical interpretation needs to be tested
- Different gauge choices or regularization schemes to compare
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/branch-hypothesis.md
</execution_context>

<context>
Arguments: $ARGUMENTS (format: <description of hypothesis>)

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

Preserve all validation gates (argument parsing, git state checks, branch creation, hypothesis documentation).
</process>
