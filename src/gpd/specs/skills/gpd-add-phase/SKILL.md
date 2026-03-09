---
name: gpd-add-phase
description: Add research phase to end of current milestone in roadmap
argument-hint: <description>
allowed-tools:
  - read_file
  - write_file
  - shell
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Add a new integer phase to the end of the current milestone in the roadmap.

Routes to the add-phase workflow which handles:

- Phase number calculation (next sequential integer)
- Directory creation with slug generation
- Roadmap structure updates
- STATE.md roadmap evolution tracking

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
@.planning/ROADMAP.md
@.planning/STATE.md
@{GPD_INSTALL_DIR}/workflows/add-phase.md
</execution_context>

<process>
**Follow the add-phase workflow** from `@{GPD_INSTALL_DIR}/workflows/add-phase.md`.

The workflow handles all logic including:

1. Argument parsing and validation
2. Roadmap existence checking
3. Current milestone identification
4. Next phase number calculation (ignoring decimals)
5. Slug generation from description
6. Phase directory creation
7. Roadmap entry insertion
8. STATE.md updates
   </process>
