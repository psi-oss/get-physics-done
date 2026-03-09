---
name: gpd-derive-equation
description: Perform a rigorous physics derivation with systematic verification at each step
argument-hint: "[equation or topic to derive]"
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
  - grep
  - glob
  - ask_user
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for non-Claude runtimes. -->

<objective>
Perform a rigorous physics derivation with systematic verification at each step.

Provide the equation or topic to derive as an argument (e.g., `$gpd-derive-equation "effective mass from self-energy"`). If no argument is given, you will be asked what to derive.

- States assumptions explicitly, establishes notation and conventions
- Performs step-by-step derivation with dimensional analysis at each stage
- Verifies intermediate results against known limits and symmetry properties
- Justifies and bounds all approximations with error estimates
- Produces a complete, self-contained derivation document with boxed final result
  </objective>

<context>
@.planning/STATE.md
</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/derive-equation.md
</execution_context>

<process>
Execute the derive-equation workflow from @{GPD_INSTALL_DIR}/workflows/derive-equation.md end-to-end.
Preserve all workflow gates (assumption statement, notation, step-by-step derivation, verification, documentation).

The workflow will:
1. Set up the derivation context (conventions, starting point, target)
2. Guide you through a step-by-step derivation with checkpoints
3. Verify dimensional consistency at each step
4. Check limiting cases of the final result
5. Record the derived equation in the project's results
</process>
