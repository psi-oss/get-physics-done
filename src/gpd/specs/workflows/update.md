<purpose>
Check for GPD updates via npm, display changelog for versions between installed and latest, obtain user confirmation, and execute clean installation with cache clearing.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="get_installed_version">
Detect whether GPD is installed locally or globally by checking both locations:

```bash
# Check local first (takes priority)
if [ -f "./{RUNTIME_CONFIG_DIR}/get-physics-done/VERSION" ]; then
  cat "./{RUNTIME_CONFIG_DIR}/get-physics-done/VERSION"
  echo "LOCAL"
elif [ -f {GPD_INSTALL_DIR}/VERSION ]; then
  cat {GPD_INSTALL_DIR}/VERSION
  echo "GLOBAL"
else
  echo "UNKNOWN"
fi
```

Parse output:

- If last line is "LOCAL": installed version is first line, use `--local` flag for update
- If last line is "GLOBAL": installed version is first line, use `--global` flag for update
- If "UNKNOWN": proceed to install step (treat as version 0.0.0)

**If VERSION file missing:**

```
## GPD Update

**Installed version:** Unknown

Your installation doesn't include version tracking.

Running fresh install...
```

Proceed to install step (treat as version 0.0.0 for comparison).
</step>

<step name="check_latest_version">
Check npm for latest version:

```bash
# gpd is the unified Python package
pip index versions gpd 2>/dev/null
```

**If npm check fails:**

```
Couldn't check for updates (offline or npm unavailable).

To update manually: `gpd install --all --global`
```

Exit.
</step>

<step name="compare_versions">
Compare installed vs latest:

**If installed == latest:**

```
## GPD Update

**Installed:** X.Y.Z
**Latest:** X.Y.Z

You're already on the latest version.
```

Exit.

**If installed > latest:**

```
## GPD Update

**Installed:** X.Y.Z
**Latest:** A.B.C

You're ahead of the latest release (development version?).
```

Exit.
</step>

<step name="show_changes_and_confirm">
**If update available**, fetch and show what's new BEFORE updating:

1. Fetch changelog from GitHub raw URL
2. Extract entries between installed and latest versions
3. Display preview and ask for confirmation:

```
## GPD Update Available

**Installed:** 1.5.10
**Latest:** 1.5.15

### What's New
------------------------------------------------------------

## [1.5.15] - 2026-01-20

### Added
- New physics validation command

## [1.5.14] - 2026-01-18

### Fixed
- Corrected sign convention in template

------------------------------------------------------------

>> **Note:** The installer performs a clean install of GPD folders:
- `commands/gpd/` will be wiped and replaced
- `get-physics-done/` will be wiped and replaced
- `agents/gpd-*` files will be replaced

(Paths are relative to your runtime's config directory)

Your custom files in other locations are preserved:
- Custom commands not in `commands/gpd/` -- preserved
- Custom agents not prefixed with `gpd-` -- preserved
- Custom hooks -- preserved
- Your runtime config files -- preserved

If you've modified any GPD files directly, they'll be automatically backed up to `gpd-local-patches/` and can be reapplied with `$gpd-reapply-patches` after the update.
```

> **Platform note:** If `AskUserQuestion` is not available, present these options in plain text and wait for the user's freeform response.

Use AskUserQuestion:

- Question: "Proceed with update?"
- Options:
  - "Yes, update now"
  - "No, cancel"

**If user cancels:** Exit.
</step>

<step name="run_update">
Run the update using the install type detected in step 1:

**If LOCAL install:**

```bash
gpd install --all --local
```

**If GLOBAL install (or unknown):**

```bash
gpd install --all --global
```

Capture output. If install fails, show error and exit.

Clear the update cache so statusline indicator disappears:

**If LOCAL install:**

```bash
rm -f ~/.gpd/cache/gpd-update-check.json
```

**If GLOBAL install:**

```bash
rm -f ~/.gpd/cache/gpd-update-check.json
```

</step>

<step name="display_result">
Format completion message (changelog was already shown in confirmation step):

```
+===========================================================+
|  GPD Updated: v1.5.10 -> v1.5.15                         |
+===========================================================+

>> Restart your AI coding assistant to pick up the new commands.

[View full changelog](https://github.com/get-physics-done/get-physics-done/blob/main/CHANGELOG.md)
```

</step>

<step name="check_local_patches">
After update completes, check if the installer detected and backed up any locally modified files:

Check for gpd-local-patches/backup-meta.json in the config directory.

**If patches found:**

```
Local patches were backed up before the update.
Run $gpd-reapply-patches to merge your modifications into the new version.
```

**If no patches:** Continue normally.
</step>
</process>

<success_criteria>

- [ ] Installed version read correctly
- [ ] Latest version checked via npm
- [ ] Update skipped if already current
- [ ] Changelog fetched and displayed BEFORE update
- [ ] Clean install warning shown
- [ ] User confirmation obtained
- [ ] Update executed successfully
- [ ] Restart reminder shown

</success_criteria>
