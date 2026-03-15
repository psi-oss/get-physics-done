<purpose>
Reconcile diverged STATE.md and state.json. These two files represent the same project state in different formats: STATE.md is the human-readable markdown edited by the AI, and state.json is the structured JSON sidecar used by gpd CLI. They can diverge when one is edited directly, when a tool crashes mid-update, or when manual edits are made to STATE.md without running the sync.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.

**Schema reference:** `./.claude/get-physics-done/templates/state-json-schema.md` — Canonical schema for state.json fields, types, defaults, and authoritative-vs-derived status. Consult when resolving conflicts between STATE.md and state.json.
</required_reading>

<process>

<step name="init" priority="first">
**Check both state files exist:**

```bash
STATE_MD=".gpd/STATE.md"
STATE_JSON=".gpd/state.json"

MD_EXISTS=$(test -f "$STATE_MD" && echo true || echo false)
JSON_EXISTS=$(test -f "$STATE_JSON" && echo true || echo false)
```

**If neither exists:**

```
No state files found. Run /gpd:new-project to initialize project state.
```

Exit.

**If only STATE.md exists (state.json missing):**

state.json is derived from STATE.md. Regenerate it by backing up state.json and triggering a state read:

```bash
if [ -f .gpd/state.json ]; then
  mv .gpd/state.json .gpd/state.json.bak
fi

gpd state snapshot --raw > /dev/null
if [ $? -ne 0 ]; then
  echo "WARNING: state-snapshot failed — restoring backup"
  if [ -f .gpd/state.json.bak ]; then
    mv .gpd/state.json.bak .gpd/state.json
  fi
else
  rm -f .gpd/state.json.bak
fi
```

Report: "state.json regenerated from STATE.md." Exit (no divergence to reconcile).

**If only state.json exists (STATE.md missing):**

This is unusual — STATE.md is the primary file. Regenerate:

```bash
# Trigger STATE.md regeneration by reading state.json and writing it back
# (sync_state_json always writes both state.json and STATE.md)
STATUS=$(python3 -c "
import json, pathlib
try:
    s = json.loads(pathlib.Path('.gpd/state.json').read_text())
    print((s.get('position') or {}).get('status', 'Not started') or 'Not started')
except Exception:
    print('Not started')
")
gpd state update "Status" "${STATUS}"
if [ $? -ne 0 ]; then echo "WARNING: state update failed — manual STATE.md repair may be needed"; fi
```

If state.json is also corrupt or empty, re-initialize the project.

Exit.

**If both exist:** Continue to comparison.
</step>

<step name="read_both">
**Read both state representations:**

```bash
# Read STATE.md
cat .gpd/STATE.md

# Read state.json
cat .gpd/state.json
```

**Parse STATE.md into comparable fields:**

Extract from STATE.md (using text parsing):
- Current Phase (number and name)
- Current Plan
- Status
- Last Activity
- Core research question
- Current focus
- Decisions list
- Blockers list
- Session info (last date, stopped at, resume file)

**Parse state.json fields:**

Extract from state.json:
- `position.current_phase`, `position.current_phase_name`
- `position.current_plan`
- `position.status`
- `position.last_activity`
- `project_reference.core_research_question`
- `project_reference.current_focus`
- `decisions[]`
- `blockers[]`
- `session.last_date`, `session.stopped_at`
- `convention_lock` (JSON-only field)
- `intermediate_results` (JSON-only field)
- `approximations` (JSON-only field)
- `propagated_uncertainties` (JSON-only field)
</step>

<step name="compare_fields">
**Compare shared fields between STATE.md and state.json:**

For each shared field, check if values match:

| Field | STATE.md | state.json | Match |
|-------|----------|------------|-------|
| current_phase | {md_value} | {json_value} | {YES/NO} |
| current_plan | {md_value} | {json_value} | {YES/NO} |
| status | {md_value} | {json_value} | {YES/NO} |
| last_activity | {md_value} | {json_value} | {YES/NO} |
| core_research_question | {md_value} | {json_value} | {YES/NO} |
| current_focus | {md_value} | {json_value} | {YES/NO} |
| decision_count | {md_count} | {json_count} | {YES/NO} |
| blocker_count | {md_count} | {json_count} | {YES/NO} |

**If all fields match:**

```
STATE.md and state.json are in sync. No reconciliation needed.
```

Update `_synced_at` timestamp in state.json and exit.

**If divergences found:** Continue to resolution.
</step>

<step name="determine_recency">
**For each divergent field, determine which source is more recent:**

```bash
# File modification times
MD_MOD=$(stat -f %m .gpd/STATE.md 2>/dev/null || stat -c %Y .gpd/STATE.md 2>/dev/null || echo 0)
JSON_MOD=$(stat -f %m .gpd/state.json 2>/dev/null || stat -c %Y .gpd/state.json 2>/dev/null || echo 0)

# Git history for more precise tracking
MD_LAST_COMMIT=$(git log -1 --format="%H %ai" -- .gpd/STATE.md 2>/dev/null)
JSON_LAST_COMMIT=$(git log -1 --format="%H %ai" -- .gpd/state.json 2>/dev/null)
```

**Recency rules:**

1. **STATE.md is the primary source of truth** for human-readable fields (position, decisions, blockers, session).
2. **state.json is authoritative** for JSON-only fields (convention_lock, intermediate_results, approximations, propagated_uncertainties).
3. For shared fields with divergence: prefer the more recently modified file (by git commit timestamp).
4. If timestamps are equal or ambiguous: prefer STATE.md (it is the primary).
</step>

<step name="present_divergences">
**Present divergences to user for confirmation:**

```
## State Divergence Detected

| Field | STATE.md | state.json | Preferred | Reason |
|-------|----------|------------|-----------|--------|
| current_phase | 5 | 4 | STATE.md | More recent commit |
| status | "Executing" | "Ready to plan" | STATE.md | Primary source |
| decision_count | 12 | 10 | STATE.md | MD has 2 newer decisions |

### JSON-only fields (no divergence possible):
- convention_lock: {count} fields locked
- intermediate_results: {count} results
- approximations: {count} entries

### Proposed resolution:
- Update state.json position fields from STATE.md
- Preserve state.json-only fields as-is
- Sync timestamps

Proceed with reconciliation? (y/n)
```

Wait for user confirmation.
</step>

<step name="reconcile">
**Merge into consistent state:**

**Strategy:** Apply the preferred value for each divergent field, then sync both files.

**For STATE.md-preferred fields:**

Regenerate state.json from STATE.md by backing it up and triggering a state read (which merges parsed markdown fields INTO existing JSON backup, preserving `convention_lock`, `intermediate_results`, `approximations`, and `propagated_uncertainties`):

```bash
if [ -f .gpd/state.json ]; then
  mv .gpd/state.json .gpd/state.json.bak
fi

gpd state snapshot --raw > /dev/null
if [ $? -ne 0 ]; then
  echo "WARNING: state-snapshot failed — restoring backup"
  if [ -f .gpd/state.json.bak ]; then
    mv .gpd/state.json.bak .gpd/state.json
  fi
else
  rm -f .gpd/state.json.bak
fi
```

**For state.json-preferred fields (rare — only when JSON was updated more recently):**

Update STATE.md to match state.json for the specific divergent fields, then re-sync:

```bash
# Example: if state.json has more recent position
gpd state patch \
  "--Current Phase" "${JSON_PHASE}" \
  --Status "${JSON_STATUS}"
```

**Verify sync result:**

```bash
# Re-read both files and confirm no remaining divergences
python3 -c "
import json, pathlib
try:
    j = json.loads(pathlib.Path('.gpd/state.json').read_text())
    pos = j.get('position') or {}
    print('Phase:', pos.get('current_phase', 'unknown'))
    print('Status:', pos.get('status', 'unknown'))
    print('Synced:', j.get('_synced_at', 'not set'))
except Exception as e:
    print('ERROR: state.json is not valid JSON:', e)
"
```
</step>

<step name="commit">
**Commit reconciled state:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/STATE.md .gpd/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "fix: reconcile STATE.md and state.json divergence" \
  --files .gpd/STATE.md .gpd/state.json
```
</step>

<step name="report">
**Report what was reconciled:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > STATE SYNCHRONIZED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Divergences resolved:** {count}

| Field | Old (diverged) | New (reconciled) | Source |
|-------|----------------|------------------|--------|
| current_phase | 4 (json) -> 5 (md) | 5 | STATE.md |
| status | "Ready to plan" -> "Executing" | "Executing" | STATE.md |

**JSON-only fields preserved:**
- convention_lock: {count} fields
- intermediate_results: {count} results

**Synced at:** {timestamp}

Both files are now consistent.
```
</step>

</process>

<failure_handling>

- **STATE.md corrupt (unparseable):** If STATE.md cannot be parsed, check if state.json is valid and offer to regenerate STATE.md from it. If both are corrupt, suggest restoring from git: `git checkout HEAD~1 -- .gpd/STATE.md .gpd/state.json`
- **state.json corrupt (invalid JSON):** Delete state.json — it will be regenerated automatically from STATE.md on next access (any `gpd state` command triggers the fallback parser).
- **Regeneration still fails:** Fall back to manual reconciliation — read STATE.md, write state.json directly using `gpd state` subcommands.
- **Both files very old (neither recently committed):** Warn user that both files may be stale. Suggest checking git log for the most recent good state.

</failure_handling>

<success_criteria>

- [ ] Both state files checked for existence
- [ ] Missing file regenerated from the other (if applicable)
- [ ] All shared fields compared between STATE.md and state.json
- [ ] Divergences identified with recency analysis
- [ ] User confirmed reconciliation plan
- [ ] Preferred values applied to both files
- [ ] JSON-only fields preserved during sync
- [ ] Both files verified as consistent after reconciliation
- [ ] Changes committed
- [ ] Report presented with what was reconciled
</success_criteria>
