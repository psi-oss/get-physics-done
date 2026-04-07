---
name: gpd:derive-equation
description: Perform a rigorous physics derivation with systematic verification at each step
argument-hint: "[equation or topic to derive]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
  - ask_user
---


<objective>
Perform a rigorous physics derivation with systematic verification at each step.

Provide the equation or topic to derive as an argument (e.g., `gpd:derive-equation "effective mass from self-energy"`). If no argument is given, you will be asked what to derive.

- States assumptions explicitly, establishes notation and conventions
- Performs step-by-step derivation with dimensional analysis at each stage
- Verifies intermediate results against known limits and symmetry properties
- Justifies and bounds all approximations with error estimates
- For theorem-bearing derivations, spawns `gpd-check-proof` as a separate proof critic and fails closed without its audit
- Produces a complete, self-contained derivation document with boxed final result
  </objective>

<context>
@GPD/STATE.md
</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/derive-equation.md
</execution_context>

<process>
Execute the derive-equation workflow from @{GPD_INSTALL_DIR}/workflows/derive-equation.md end-to-end.
Preserve all workflow gates (assumption statement, notation, step-by-step derivation, verification, documentation).

The workflow will:
1. Set up the derivation context (conventions, starting point, target), including canonical result lookup via `gpd result search` and direct stored-result inspection via `gpd result show "{result_id}"` when the target already has a known registry entry
2. Guide you through a step-by-step derivation with checkpoints
3. Verify dimensional consistency at each step
4. Check limiting cases of the final result
5. Record the derived equation in the project's `intermediate_results` registry through the executable `gpd result persist-derived` bridge when project state is available; the workflow reuses or carries forward a stable `result_id` request on reruns, preserves the actual canonical `result_id` when the bridge reuses an existing entry, and seeds continuity automatically through the canonical continuation path when an active continuation context exists. standalone runs stop after writing the derivation document and do not write project registry state
</process>
