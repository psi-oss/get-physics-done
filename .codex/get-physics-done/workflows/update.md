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
# Get installed version from package metadata
INSTALLED_VERSION=$(python3 -c "from gpd.version import __version__; print(__version__)" 2>/dev/null || echo "0.0.0")

# Detect install type from package location
INSTALL_PATH=$(python3 -c "import gpd; print(gpd.__file__)" 2>/dev/null || echo "")
if echo "$INSTALL_PATH" | grep -q "$HOME/.claude"; then
  echo "$INSTALLED_VERSION"
  echo "LOCAL"
elif [ -n "$INSTALL_PATH" ]; then
  echo "$INSTALLED_VERSION"
  echo "GLOBAL"
else
  echo "0.0.0"
  echo "UNKNOWN"
fi
```

Parse output:

- If last line is "LOCAL": installed version is first line, use `--local` flag for update
- If last line is "GLOBAL": installed version is first line, use `--global` flag for update
- If "UNKNOWN": proceed to install step (treat as version 0.0.0)

**If version detection fails:**

```
## GPD Update

**Installed version:** Unknown

Could not detect installed version.

Running fresh install...
```

Proceed to install step (treat as version 0.0.0 for comparison).
</step>

<step name="check_latest_version">
Check PyPI for latest version:

```bash
# gpd is the unified Python package
pip index versions gpd 2>/dev/null
```

**If version check fails:**

```
Couldn't check for updates (offline or PyPI unavailable).

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

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

Use ask_user:

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
rm -f ~/.gpd/cache$gpd-update-check.json
```

**If GLOBAL install:**

```bash
rm -f ~/.gpd/cache$gpd-update-check.json
```

</step>

<step name="display_result">
Format completion message (changelog was already shown in confirmation step):

```
+===========================================================+
|  GPD Updated: v1.5.10 -> v1.5.15                         |
+===========================================================+

>> Restart your AI agent to pick up the new commands.

[View releases](https://github.com/physicalsuperintelligence/get-physics-done/releases)
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
- [ ] Latest version checked via PyPI
- [ ] Update skipped if already current
- [ ] Changelog fetched and displayed BEFORE update
- [ ] Clean install warning shown
- [ ] User confirmation obtained
- [ ] Update executed successfully
- [ ] Restart reminder shown

</success_criteria>
