<purpose>
Check for a newer GPD release, show recent release notes, confirm with the user, and reinstall the active runtime with the public bootstrap command.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="detect_current_install">
Detect the currently installed version and the correct runtime/scope to update.

Use the installed runtime files, not Python import location:

```bash
GPD_INSTALL_DIR="{GPD_INSTALL_DIR}"
GPD_CONFIG_DIR="{GPD_CONFIG_DIR}"
GPD_GLOBAL_CONFIG_DIR="{GPD_GLOBAL_CONFIG_DIR}"
INSTALL_SCOPE="{GPD_INSTALL_SCOPE_FLAG}"
UPDATE_COMMAND="{GPD_UPDATE_COMMAND}"
PATCH_META="{GPD_PATCH_META}"
PYTHON_BIN="${GPD_PYTHON:-}"

if [ -z "$PYTHON_BIN" ]; then
  PYTHON_BIN=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
fi
if [ -z "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

if [ -f "$GPD_INSTALL_DIR/VERSION" ]; then
  INSTALLED_VERSION=$(tr -d '\n' < "$GPD_INSTALL_DIR/VERSION")
else
  INSTALLED_VERSION="0.0.0"
fi

printf '%s\n%s\n%s\n%s\n%s\n' \
  "$INSTALLED_VERSION" \
  "$INSTALL_SCOPE" \
  "$UPDATE_COMMAND" \
  "$GPD_CONFIG_DIR" \
  "$PATCH_META"
```

Parse output as:

- line 1: installed version
- line 2: install scope flag (`--local` or `--global`)
- line 3: public update command to run
- line 4: runtime config directory
- line 5: expected local-patch metadata path

If the version file is missing, treat the install as version `0.0.0` and continue.
</step>

<step name="check_latest_version">
Check the canonical release metadata endpoint for the latest released GPD version:

```bash
LATEST_RELEASE_URL="{GPD_RELEASE_LATEST_URL}"
PYTHON_BIN="${GPD_PYTHON:-}"

if [ -z "$PYTHON_BIN" ]; then
  PYTHON_BIN=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
fi
if [ -z "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" - "$LATEST_RELEASE_URL" <<'PY'
import json
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=10) as resp:
    data = json.load(resp)
print(data["version"])
PY
```

If that fails, show:

```text
## GPD Update

Couldn't check for updates (offline or release metadata unavailable).

To update manually, run:
`<UPDATE_COMMAND>`
```

Then exit.
</step>

<step name="compare_versions">
Compare the installed version and the latest version semantically, not lexicographically.

If installed == latest, show:

```text
## GPD Update

**Installed:** X.Y.Z
**Latest:** X.Y.Z

You're already on the latest version.
```

Then exit.

If installed > latest, show:

```text
## GPD Update

**Installed:** X.Y.Z
**Latest:** A.B.C

You're ahead of the latest published release (development build or unreleased source install).
```

Then exit.
</step>

<step name="show_changes_and_confirm">
If an update is available, fetch recent release notes before asking for confirmation.

Preferred source:

- GitHub Releases API: `{GPD_RELEASES_API_URL}`

Show a short preview covering releases newer than the installed version and up to the latest version. If release notes cannot be fetched, say so briefly and continue with the update prompt anyway.

Display the confirmation prompt in this shape:

```text
## GPD Update Available

**Installed:** 1.5.10
**Latest:** 1.5.15

### What's New
[short preview of recent release notes, or a brief fallback note]

>> **Note:** This reinstalls the current runtime's managed GPD files:
- GPD command files for this runtime will be replaced
- `{GPD_INSTALL_ROOT_DIR_NAME}/` will be replaced
- `gpd-*` agent files will be replaced

Custom files outside the managed GPD install are preserved.
If you've modified managed GPD files directly, they will be backed up to `{GPD_PATCHES_DIR_NAME}/` and can be reapplied with `gpd:reapply-patches` after the update.
```

> **Platform note:** If `ask_user` is not available, present the choices in plain text and wait for the user's freeform response.

Use ask_user:

- Question: "Proceed with update?"
- Options:
  - "Yes, update now"
  - "No, cancel"

If the user cancels, exit.
</step>

<step name="run_update">
Run the update with the public bootstrap command from step 1:

```bash
<UPDATE_COMMAND>
```

Capture output. If the update command fails, show the error and exit.

Then clear the configured update caches so indicators disappear immediately:

```bash
rm -f \
  "{GPD_CONFIG_DIR}/cache/gpd-update-check.json" \
  "{GPD_GLOBAL_CONFIG_DIR}/cache/gpd-update-check.json"
```
</step>

<step name="display_result">
Format completion like:

```text
+================================================+
|  GPD Updated: v1.5.10 -> v1.5.15               |
+================================================+

>> Restart your AI agent to pick up the new commands.

[View releases]({GPD_RELEASES_PAGE_URL})
```
</step>

<step name="check_local_patches">
After the update completes, check the patch metadata path captured in step 1.

If patches were backed up, show:

```text
Local patches were backed up before the update.
Run gpd:reapply-patches to merge your modifications into the new version.
```

Otherwise continue normally.
</step>
</process>

<success_criteria>

- [ ] Installed version read from the runtime install
- [ ] Latest released version checked from the canonical release metadata endpoint
- [ ] Update skipped if already current
- [ ] Recent release notes shown before updating when available
- [ ] Clean reinstall warning shown
- [ ] User confirmation obtained
- [ ] Runtime-specific update command executed successfully
- [ ] Update caches cleared
- [ ] Restart reminder shown

</success_criteria>
