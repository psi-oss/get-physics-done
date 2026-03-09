---
name: gpd:branch-hypothesis
description: Create a hypothesis branch for parallel investigation of an alternative approach
argument-hint: "<description>"
requires:
  files: [".planning/ROADMAP.md", ".planning/STATE.md"]
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Create a git branch for investigating an alternative hypothesis or approach in parallel with the main line of research.

Hypothesis branches allow a researcher to explore "what if?" questions without polluting the main research state. Each branch gets its own STATE.md fork and hypothesis documentation, enabling side-by-side comparison later via /gpd:compare-branches.

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

@.planning/STATE.md
@.planning/ROADMAP.md
</context>

<process>
Execute the branch-hypothesis workflow from @{GPD_INSTALL_DIR}/workflows/branch-hypothesis.md end-to-end.
Preserve all validation gates (argument parsing, git state checks, branch creation, hypothesis documentation).
</process>
