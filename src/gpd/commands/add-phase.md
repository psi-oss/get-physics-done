---
name: gpd:add-phase
description: Add research phase to end of current milestone in roadmap
argument-hint: <description>
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
---


<objective>
Add a new integer phase to the end of the current milestone in the roadmap.

Typical research phases include:

- Literature review (survey existing results, identify gaps)
- Formalism development (define notation, establish framework)
- Analytical calculation (derive key results, check limiting cases)
- Numerical implementation (code up simulations, set parameters)
- Validation (compare with known results, verify dimensional consistency)
- Interpretation (extract physical meaning, identify novel predictions)
- Paper writing (draft manuscript, prepare figures)
  </objective>

<execution_context>
@GPD/ROADMAP.md
@GPD/STATE.md
@{GPD_INSTALL_DIR}/workflows/add-phase.md
</execution_context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/add-phase.md` exactly.
   </process>
