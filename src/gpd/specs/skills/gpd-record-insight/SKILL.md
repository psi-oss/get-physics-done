---
name: gpd-record-insight
description: Record a project-specific learning or pattern to the insights ledger
argument-hint: "[optional description]"
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for non-Claude runtimes. -->

<objective>
Record a project-specific learning, error pattern, or insight to `.planning/INSIGHTS.md`.

Routes to the record-insight workflow which handles:

- Creating INSIGHTS.md if it doesn't exist
- Duplicate detection
- Category-to-section mapping
- Structured table row creation
- STATE.md updates
- Git commits

Typical insights include:

- "Sign error in Wick contractions when using mostly-minus metric"
- "Finite-size corrections scale as 1/L^2 not 1/L for this geometry"
- "Richardson extrapolation unreliable when convergence order fluctuates"
- "Ward identity check caught missing diagram in self-energy"
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/record-insight.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<process>
**Follow the record-insight workflow** from `@{GPD_INSTALL_DIR}/workflows/record-insight.md`.

The workflow handles all logic including:

1. Checking/creating `.planning/INSIGHTS.md`
2. Duplicate detection
3. Determining the correct section (Debugging Patterns, Verification Lessons, Consistency Issues, Execution Deviations)
4. Appending structured table row with date, phase, category, confidence, description, prevention
5. Git commit
</process>
