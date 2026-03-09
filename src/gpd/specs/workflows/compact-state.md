<purpose>
Archive historical entries from STATE.md to reduce its size. As research projects grow, STATE.md accumulates decisions, session records, metrics, and resolved blockers from many phases. This workflow archives old entries to STATE-ARCHIVE.md, keeping STATE.md lean and under the target line budget.

Triggered automatically when progress.md detects STATE.md exceeds 1500 lines, or manually via `$gpd-compact-state`.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="init" priority="first">
**Load state and check line count:**

```bash
INIT=$(gpd init progress --include state)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract: `state_exists`, `state_content`.

**If `state_exists` is false:**

```
No STATE.md found. Nothing to compact.
```

Exit.

**Count current lines:**

```bash
STATE_LINES=$(wc -l < .planning/STATE.md)
```

Report: "STATE.md is {STATE_LINES} lines."

**Check thresholds:**

- Under 150 lines: "STATE.md is within target budget. No compaction needed."
- 150-1500 lines: "STATE.md is above target (150 lines) but within emergency budget (1500). Consider manual trimming."
- Over 1500 lines: "STATE.md exceeds emergency budget. Running automatic compaction."

If under 1500 and not forced (`--force` flag absent): offer to compact anyway or exit.
</step>

<step name="run_compact">
**Delegate to gpd state compact:**

The JavaScript implementation handles the detailed archival logic:

```bash
RESULT=$(gpd state compact)
if [ $? -ne 0 ]; then
  echo "ERROR: state compact failed: $RESULT"
  # STOP — STATE.md may be in an inconsistent state.
fi
```

Parse result JSON for: `compacted` (bool), `reason`, `original_lines`, `new_lines`, `archived_lines`, `warn`.

**The tool performs these archival operations:**

1. **Decisions:** Archives decisions from phases older than (current - 1). Keeps current and previous phase decisions.
2. **Resolved blockers:** Archives blockers marked `[resolved]` or struck through (`~~...~~`). Keeps active blockers.
3. **Performance metrics:** Archives metrics from phases older than (current - 1). Keeps recent metrics.
4. **Session records:** Keeps only the last 3 session records. Archives older ones.

All archived content is appended to `.planning/STATE-ARCHIVE.md` with a dated header.

**If `compacted` is false:**

Check `reason`:
- `"within_budget"`: STATE.md is already small enough.
- `"nothing_to_archive"`: STATE.md is large but nothing qualified for archival (all entries are current).

Report and exit.
</step>

<step name="verify_compaction">
**Verify the compacted STATE.md is valid:**

```bash
# Check new line count
NEW_LINES=$(wc -l < .planning/STATE.md)

# Verify STATE.md still has required sections
for SECTION in "Current Position" "Project Reference" "Accumulated Context" "Session"; do
  grep -q "## ${SECTION}" .planning/STATE.md || echo "MISSING: ${SECTION}"
done

# Verify state.json was synced
ls -la .planning/state.json
```

**If required sections are missing:** The compaction was too aggressive. Attempt recovery:

```bash
# First try: regenerate STATE.md from state.json
# Any state-modifying command triggers dual-file write (state.json + STATE.md)
if [ -f .planning/state.json ]; then
  echo "Attempting STATE.md recovery from state.json..."
  # Touch a harmless field to trigger the dual-file write
  gpd state update "Last Activity" "$(date -u +%Y-%m-%d)"
  RECOVERY_METHOD="regenerated from state.json"
else
  # Fallback: restore from git (state.json also missing or corrupt)
  echo "state.json unavailable. Falling back to git restore..."
  git checkout -- .planning/STATE.md
  RECOVERY_METHOD="restored from git"
fi
echo "Recovery method: ${RECOVERY_METHOD}"
```

Report error and recovery method used, then exit.

**If state.json sync failed:** Delete state.json and it will be regenerated from STATE.md on next access by any `gpd state` command.
</step>

<step name="verify_archive">
**Verify STATE-ARCHIVE.md was created/updated:**

```bash
ls -la .planning/STATE-ARCHIVE.md 2>/dev/null
ARCHIVE_LINES=$(wc -l < .planning/STATE-ARCHIVE.md 2>/dev/null || echo 0)
```

Confirm archived content is recoverable.
</step>

<step name="commit">
**Commit compaction results:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .planning/STATE.md .planning/STATE-ARCHIVE.md .planning/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "chore: compact STATE.md (${ORIGINAL_LINES} -> ${NEW_LINES} lines)" \
  --files .planning/STATE.md .planning/STATE-ARCHIVE.md .planning/state.json
```
</step>

<step name="report">
**Present compaction summary:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > STATE COMPACTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Before:** {original_lines} lines
**After:** {new_lines} lines
**Archived:** {archived_lines} lines to STATE-ARCHIVE.md

### What was archived:
- {N} decisions from phases < {keep_phase_min}
- {N} resolved blockers
- {N} performance metrics from old phases
- {N} historical session records

### Archive location:
.planning/STATE-ARCHIVE.md ({archive_lines} total lines)

All archived content is recoverable from STATE-ARCHIVE.md or git history.
```

**If STATE.md is still above 150 lines after compaction:**

```
STATE.md is now {new_lines} lines (target: 150).
Remaining entries are all current-phase content. To further reduce:
- Summarize verbose intermediate results
- Move detailed derivation logs to phase SUMMARY.md files
- Keep only the latest key results, not historical progression
```
</step>

</process>

<failure_handling>

- **STATE.md not found:** Nothing to compact. Exit with message.
- **gpd state compact fails:** Check error output. Common causes: file lock held by another process, corrupt STATE.md parsing. Suggest: `cat .planning/STATE.md | head -5` to verify file is readable.
- **Required sections missing after compaction:** Restore from git immediately. Report the bug.
- **STATE-ARCHIVE.md write fails:** Check disk space and permissions. STATE.md changes are preserved regardless.

</failure_handling>

<success_criteria>

- [ ] STATE.md line count checked against thresholds
- [ ] gpd state compact executed
- [ ] Archived entries moved to STATE-ARCHIVE.md
- [ ] Compacted STATE.md retains all required sections
- [ ] state.json synced after compaction
- [ ] Archive file verified as recoverable
- [ ] Changes committed with line count in message
- [ ] Summary presented with what was archived
</success_criteria>
