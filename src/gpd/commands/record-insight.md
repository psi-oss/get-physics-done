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
Follow the included record-insight workflow exactly.
</process>
