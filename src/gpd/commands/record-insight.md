---
name: gpd:record-insight
description: Record a project-specific learning or pattern to the insights ledger
argument-hint: "[optional description]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
---


<objective>
Record a project-specific learning, error pattern, or insight to `GPD/INSIGHTS.md`.

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
@GPD/STATE.md
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

The workflow handles all logic including:

1. Checking/creating `GPD/INSIGHTS.md`
2. Duplicate detection
3. Determining the correct section (Debugging Patterns, Verification Lessons, Consistency Issues, Execution Deviations)
4. Appending structured table row with date, phase, category, confidence, description, prevention
5. Git commit
</process>
