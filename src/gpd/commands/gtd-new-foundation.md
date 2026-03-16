---
name: gtd:new-foundation
description: Initialize a new foundation with phase tracking
argument-hint: "<foundation-id>"
context_mode: projectless
allowed-tools:
  - shell
  - file_write
  - file_read
---

<objective>
Initialize a new Arkhe(n) foundation (F-001 to F-609) with phase tracking and coherence measurement.
This command uses the `get-arkhe-done` Rust engine to establish a phase-locked foundation.
</objective>

<process>
1. Validate the foundation ID against the 57 foundations catalog.
2. Execute `get-arkhe-done genesis` to initialize the foundation state.
3. Create the standard Arkhe(n) project structure for the foundation.
4. Initialize the `.gpd/` metadata with foundation-specific identifiers.
</process>
