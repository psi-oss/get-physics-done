---
name: gpd:undo
description: Rollback last GPD operation with safety checkpoint
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Safely rollback the last GPD-related git commit. Creates a safety checkpoint tag before reverting so the operation itself is reversible.

Use this when a plan, execution, or verification produced incorrect results and you want to undo cleanly.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/undo.md
</execution_context>

<context>
@.gpd/STATE.md
</context>

<process>
If `--dry-run` flag is present, show the commit that would be reverted and files affected, without actually reverting.

Execute the undo workflow from @{GPD_INSTALL_DIR}/workflows/undo.md end-to-end.
Preserve all safety gates and confirmation steps.

## Step 1: Find Last GPD Commit

Search recent git log for commits with GPD message patterns: `docs(gpd):`, `fix(gpd):`, `feat(gpd):`, `chore(gpd):`, `test(gpd):`, or any commit with `(phase-NN):` scope, plus `undo:` prefixes.

## Step 2: Show What Would Be Undone

Display the commit message, changed files, and diff summary.

## Step 3: Confirm

Ask user for confirmation before proceeding.

## Step 4: Create Safety Checkpoint

Tag the current state so the undo itself can be reversed.

## Step 5: Revert

Use `git revert --no-commit` followed by a commit with "undo: revert [original message]".

## Step 6: Update STATE.md

If the reverted commit affected STATE.md, update it to reflect the rollback.

**SAFETY:** Never undo merge commits. Never force-push. Always create checkpoint first.
</process>

<success_criteria>

- [ ] Last GPD commit identified correctly
- [ ] User shown what will be undone
- [ ] User confirmed before any changes
- [ ] Safety checkpoint tag created
- [ ] Clean revert (no force operations)
- [ ] STATE.md updated if affected
- [ ] Merge commits rejected with explanation
      </success_criteria>
