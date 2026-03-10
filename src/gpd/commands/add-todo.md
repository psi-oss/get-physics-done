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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Capture an idea, task, or issue that surfaces during a GPD session as a structured todo for later work.

Routes to the add-todo workflow which handles:

- Directory structure creation
- Content extraction from arguments or conversation
- Area inference from file paths
- Duplicate detection and resolution
- Todo file creation with frontmatter
- STATE.md updates
- Git commits

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
@.gpd/STATE.md
@{GPD_INSTALL_DIR}/workflows/add-todo.md
</execution_context>

<process>
**Follow the add-todo workflow** from `@{GPD_INSTALL_DIR}/workflows/add-todo.md`.

The workflow handles all logic including:

1. Directory ensuring
2. Existing area checking
3. Content extraction (arguments or conversation)
4. Area inference
5. Duplicate checking
6. File creation with slug generation
7. STATE.md updates
8. Git commits
   </process>
