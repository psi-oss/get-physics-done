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
Reconcile STATE.md and state.json when they have diverged due to manual edits, partial updates, or corruption.

STATE.md (human-readable) and state.json (machine-readable) should always be consistent. Divergence can occur when:

- A user manually edits STATE.md without updating state.json
- A workflow crashes mid-update, leaving one file stale
- A git merge introduces conflicting state entries
- An external tool modifies state.json directly

Routes to the sync-state workflow which handles conflict detection and resolution.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/sync-state.md
@{GPD_INSTALL_DIR}/templates/state-json-schema.md
</execution_context>

<context>
@GPD/STATE.md
@GPD/state.json
</context>

<process>
**Follow the sync-state workflow** from `@{GPD_INSTALL_DIR}/workflows/sync-state.md`.

Use the included `state.json` schema in that workflow as the reconciliation contract. Do not infer authoritative fields from whichever file happens to look newer.

If `--prefer md` is passed, resolve mirrored-field conflicts in favor of STATE.md while preserving JSON-only authority from state.json.
If `--prefer json` is passed, resolve mirrored-field conflicts in favor of state.json while preserving JSON-only authority from state.json.
If no preference is given, present conflicts interactively for user resolution.

The workflow handles all logic including:

1. Reading both STATE.md and state.json
2. Detecting divergences (missing fields, conflicting values, structural mismatches)
3. Presenting conflicts to the user (unless --prefer flag resolves automatically)
4. Applying resolution to both files
5. Verifying consistency after sync
</process>

<success_criteria>

- [ ] STATE.md and state.json are consistent after sync
- [ ] All conflicts identified and resolved (automatically or interactively)
- [ ] No data lost from either source during reconciliation
- [ ] Both files pass structural validation
      </success_criteria>
