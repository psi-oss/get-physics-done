---
name: gpd:record-backtrack
description: Record a backtrack event (what went wrong, what got reverted) to the backtracks ledger
argument-hint: "[--reverted-commit=<sha>] [--trigger=<text>] [--phase=<NN-slug>] [description]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - ask_user
---


<objective>
Record a backtrack event (what went wrong, what got reverted) to `GPD/BACKTRACKS.md`.

Typical backtrack events include:

- "Proof used wrong metric convention — lock said +---- but derivation assumed mostly-minus"
- "Exec wave emitted non-load-bearing result that passed verification but failed downstream consistency check"
- "Plan-phase assumed convergence, numerics showed linear scaling in wrong parameter"
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/record-backtrack.md
</execution_context>

<context>
@GPD/STATE.md
</context>

<process>
Follow the included record-backtrack workflow exactly.
</process>
