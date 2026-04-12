<purpose>
After a GPD update wipes and reinstalls files, merge user's previously saved local modifications back into the new version. Uses intelligent comparison to handle cases where the upstream file also changed.

Called from gpd:reapply-patches command. In the physics research context, "patches" include corrections to calculation templates, custom notation conventions, modified validation checks, and personalized workflow adjustments.
</purpose>

<process>

## Step 1: Detect backed-up patches

Check for local patches directory:

```bash
PATCHES_DIR="{GPD_PATCHES_DIR}"
GLOBAL_PATCHES_DIR="{GPD_GLOBAL_PATCHES_DIR}"

if [ ! -d "$PATCHES_DIR" ] && [ "$PATCHES_DIR" != "$GLOBAL_PATCHES_DIR" ]; then
  PATCHES_DIR="$GLOBAL_PATCHES_DIR"
fi
```

Read `backup-meta.json` from the patches directory.

**If no patches found:**

```
No local patches found. Nothing to reapply.

Local patches are automatically saved when you run `gpd:update` after modifying managed GPD files.
```

Exit.

## Step 2: Show patch summary

```
## Local Patches to Reapply

**Backed up from:** v{from_version}
**Current version:** {read VERSION file}
**Files modified:** {count}

| # | File | Type | Status |
|---|------|------|--------|
| 1 | {file_path} | {convention/workflow/template/validation} | Pending |
| 2 | {file_path} | {convention/workflow/template/validation} | Pending |
```

## Step 3: Merge each file

For each file in `backup-meta.json`:

1. **Read the backed-up version** (user's modified copy from `{GPD_PATCHES_DIR_NAME}/`)
2. **Read the newly installed version** (current file after update)
3. **Compare and merge:**

   - If the new file is identical to the backed-up file: skip (modification was incorporated upstream)
   - If the new file differs: identify the user's modifications and apply them to the new version

   **Merge strategy:**

   - Read both versions fully
   - Identify sections the user added or modified (look for additions, not just differences from path replacement)
   - Apply user's additions/modifications to the new version
   - If a section the user modified was also changed upstream: flag as conflict, show both versions, ask user which to keep
   - Pay special attention to physics-specific content: sign conventions, unit definitions, and notation choices should be preserved carefully since silent changes can introduce errors in calculations

4. **Write merged result** to the installed location
5. **Report status:**
   - `Merged` -- user modifications applied cleanly
   - `Skipped` -- modification already in upstream
   - `Conflict` -- user chose resolution

## Step 4: Record modified files

After reapplying, do not invent a manual manifest-regeneration step.
The managed file manifest is rebuilt by the next `gpd:update`; for now, just record which installed files were modified so the user can review what was re-applied.

## Step 5: Cleanup option

Ask user:

- "Keep patch backups for reference?" -> preserve `{GPD_PATCHES_DIR_NAME}/`
- "Clean up patch backups?" -> remove `{GPD_PATCHES_DIR_NAME}/` directory

## Step 6: Report

```
## Patches Reapplied

| # | File | Status |
|---|------|--------|
| 1 | {file_path} | Merged |
| 2 | {file_path} | Skipped (already upstream) |
| 3 | {file_path} | Conflict resolved |

{count} file(s) updated. Your local modifications are active again.
```

</process>

<output>
All backed-up patches processed and merged into the updated GPD installation.
</output>

<success_criteria>

- [ ] All backed-up patches processed
- [ ] User modifications merged into new version
- [ ] Physics-specific content (conventions, signs, units) preserved correctly
- [ ] Conflicts resolved with user input
- [ ] Status reported for each file
</success_criteria>
