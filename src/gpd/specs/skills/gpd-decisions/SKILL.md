---
name: gpd-decisions
description: Display and search the cumulative decision log
argument-hint: "[phase number or keyword]"
requires:
  files: [".planning/STATE.md"]
allowed-tools:
  - read_file
  - shell
  - grep
  - glob
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for non-Claude runtimes. -->

<objective>
Display the cumulative decision log from .planning/DECISIONS.md with optional filtering by phase number or keyword search.

Routes to the decisions workflow which handles:

- Loading and parsing the decision log table
- Filtering by phase number (e.g., `$gpd-decisions 3`)
- Keyword search across all fields (e.g., `$gpd-decisions regularization`)
- Formatted display with summary statistics
  </objective>

<execution_context>
@.planning/STATE.md
@{GPD_INSTALL_DIR}/workflows/decisions.md
</execution_context>

<process>
**Follow the decisions workflow** from `@{GPD_INSTALL_DIR}/workflows/decisions.md`.

The workflow handles all logic including:

1. Decision log existence checking
2. Argument parsing (phase number vs keyword)
3. Table filtering and display
4. Summary statistics
   </process>
