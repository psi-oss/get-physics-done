---
name: gpd:sync-state
description: Reconcile diverged STATE.md and state.json after manual edits or corruption
argument-hint: "[--prefer md|json]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
---


<objective>
Reconcile `STATE.md` and `state.json` when they diverge.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/sync-state.md
</execution_context>

<process>
Follow the included workflow file exactly.
</process>

<success_criteria>

- [ ] STATE.md and state.json are consistent after sync
- [ ] All conflicts identified and resolved (automatically or interactively)
- [ ] No data lost from either source during reconciliation
- [ ] Both files pass structural validation
      </success_criteria>
