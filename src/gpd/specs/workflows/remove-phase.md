<purpose>
Remove an unstarted future phase from the project roadmap, delete its directory, renumber all subsequent phases to maintain a clean linear sequence, and commit the change. The commit serves as the historical record of removal.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="parse_arguments">
Parse the command arguments:
- Argument is the phase number to remove (integer or decimal)
- Example: `/gpd:remove-phase 17` -> phase = 17
- Example: `/gpd:remove-phase 16.1` -> phase = 16.1

If no argument provided:

```
ERROR: Phase number required
Usage: /gpd:remove-phase <phase-number>
Example: /gpd:remove-phase 17
```

Exit.
</step>

<step name="init_context">
Load phase operation context:

```bash
INIT=$(gpd init phase-op "${target}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract: `phase_found`, `phase_dir`, `phase_number`, `commit_docs`, `roadmap_exists`.

**If `phase_found` is false:**

```
ERROR: Phase not found: ${target}

Available phases:
$(gpd phase list)

Usage: /gpd:remove-phase <phase-number>
```

Exit.

Also read STATE.md and ROADMAP.md content for parsing current position.
</step>

<step name="validate_future_phase">
Verify the phase is a future phase (not started):

1. Compare target phase to current phase from STATE.md
2. Target must be > current phase number

If target <= current phase:

```
ERROR: Cannot remove Phase {target}

Only future phases can be removed:
- Current phase: {current}
- Phase {target} is current or completed

To abandon current work, use /gpd:pause-work instead.
```

Exit.
</step>

<step name="confirm_removal">
Present removal summary and confirm:

```
Removing Phase {target}: {Name}

This will:
- Delete: .gpd/phases/{target}-{slug}/
- Renumber all subsequent phases
- Update: ROADMAP.md, STATE.md

Proceed? (y/n)
```

Wait for confirmation.
</step>

<step name="execute_removal">
**Delegate the entire removal operation to gpd CLI:**

```bash
RESULT=$(gpd phase remove "${target}")
if [ $? -ne 0 ]; then
  echo "Phase removal blocked: $RESULT"
fi
```

If the phase has executed plans (SUMMARY.md files), gpd will error. Use `--force` only if the user confirms:

```bash
RESULT=$(gpd phase remove "${target}" --force)
```

The CLI handles:

- Deleting the phase directory
- Renumbering all subsequent directories (in reverse order to avoid conflicts)
- Renaming all files inside renumbered directories (PLAN.md, SUMMARY.md, etc.)
- Updating ROADMAP.md (removing section, renumbering all phase references, updating dependencies)
- Updating STATE.md (decrementing phase count)

Extract from result: `removed`, `directory_deleted`, `renamed_directories`, `renamed_files`, `roadmap_updated`, `state_updated`.
</step>

<step name="commit">
Stage and commit the removal:

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "chore: remove phase {target} ({original-phase-name})" \
  --files .gpd/phases/ .gpd/ROADMAP.md .gpd/STATE.md .gpd/state.json
```

The commit message preserves the historical record of what was removed.
</step>

<step name="completion">
Present completion summary:

```
Phase {target} ({original-name}) removed.

Changes:
- Deleted: .gpd/phases/{target}-{slug}/
- Renumbered: {N} directories and {M} files
- Updated: ROADMAP.md, STATE.md
- Committed: chore: remove phase {target} ({original-name})

---

## What's Next

Would you like to:
- `/gpd:progress` -- see updated roadmap status
- Continue with current phase
- Review roadmap

---
```

</step>

</process>

<anti_patterns>

- Don't remove completed phases (have SUMMARY.md files) without --force
- Don't remove current or past phases
- Don't manually renumber -- use `gpd phase remove` which handles all renumbering
- Don't add "removed phase" notes to STATE.md -- the commit is the record
- Don't modify completed phase directories

</anti_patterns>

<success_criteria>
Phase removal is complete when:

- [ ] Target phase validated as future/unstarted
- [ ] `gpd phase remove` executed successfully
- [ ] Changes committed with descriptive message
- [ ] User informed of changes

</success_criteria>
