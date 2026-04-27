---
name: gpd:add-todo
description: Capture idea or task as todo from current research conversation context
argument-hint: "[optional description]"
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
---


<objective>
Capture an idea, task, or issue that surfaces during a GPD session as a structured todo for later work.

Typical physics research todos include:

- "Check limiting case where coupling constant vanishes"
- "Derive equation of motion from the effective Lagrangian"
- "Run simulation with doubled grid resolution for convergence check"
- "Compare with reference [N] Table III values"
- "Verify dimensional consistency of Eq. (17)"
- "Write section on methodology and approximation scheme"
- "Plot dispersion relation for three parameter regimes"
- "Compute error bars using jackknife resampling"
- "Check that result reduces to known expression in non-relativistic limit"
- "Add physical interpretation of the imaginary part of the self-energy"
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/add-todo.md
</execution_context>

<process>
Follow the included add-todo workflow exactly. Let the workflow discover and inspect project state only when the current workspace has one.
   </process>
