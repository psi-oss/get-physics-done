<purpose>
After a GPD update wipes and reinstalls files, merge user's previously saved local modifications back into the new version. Uses intelligent comparison to handle cases where the upstream file also changed.

Called from /gpd:reapply-patches command. In the physics research context, "patches" include corrections to calculation templates, custom notation conventions, modified validation checks, and personalized workflow adjustments.
</purpose>

<process>

## Step 1: Detect backed-up patches

Check for local patches directory:

```bash
PATCHES_DIR="{GPD_CONFIG_DIR}/gpd-local-patches"
GLOBAL_PATCHES_DIR="{GPD_GLOBAL_CONFIG_DIR}/gpd-local-patches"

if [ ! -d "$PATCHES_DIR" ] && [ "$PATCHES_DIR" != "$GLOBAL_PATCHES_DIR" ]; then
  PATCHES_DIR="$GLOBAL_PATCHES_DIR"
fi
```

Read `backup-meta.json` from the patches directory.

**If no patches found:**

```
No local patches found. Nothing to reapply.

Local patches are automatically saved when you run /gpd:update
after modifying any GPD workflow, command, or agent files.
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

1. **Read the backed-up version** (user's modified copy from `gpd-local-patches/`)
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

## Step 4: Update manifest

After reapplying, regenerate the file manifest so future updates correctly detect these as user modifications:

```bash
# The manifest will be regenerated on next /gpd:update
# For now, just note which files were modified
```

## Step 5: Cleanup option

Ask user:

- "Keep patch backups for reference?" -> preserve `gpd-local-patches/`
- "Clean up patch backups?" -> remove `gpd-local-patches/` directory

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
