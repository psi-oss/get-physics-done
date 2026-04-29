<purpose>
Reconcile diverged `STATE.md` and `state.json` with a deterministic, fail-closed rule set. `state.json` is the authoritative store for structured state; `STATE.md` is the human-readable projection. When both files exist, structured fields follow `state.json` and the markdown view is regenerated from it. Markdown is only used as a recovery source when `state.json` is missing or unreadable.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.

Canonical reconciliation contract: later stages load
`{GPD_INSTALL_DIR}/templates/state-json-schema.md`; do not eager-load it during bootstrap routing.
</required_reading>

<process>

<step name="inspect" priority="first">
Load bootstrap and use returned state-file fields as the routing authority:

```bash
SYNC_BOOTSTRAP_INIT=$(gpd --raw init sync-state --stage sync_bootstrap)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd sync-state bootstrap failed: $SYNC_BOOTSTRAP_INIT"
  # STOP - display the error to the user and do not proceed.
fi
export PROJECT_ROOT
PROJECT_ROOT=$(echo "$SYNC_BOOTSTRAP_INIT" | gpd json get .project_root)
```

Use `sync_bootstrap.required_init_fields` from `SYNC_BOOTSTRAP_INIT`. Use `project_root` from the init payload as the only write/read root; do not use the shell launch directory. Do not re-probe `GPD/STATE.md`, `GPD/state.json`, or `GPD/state.json.bak` by hand during routing.

**If `state_md_exists` and `state_json_exists` are both false:**

```
No state files found. Run gpd:new-project to initialize project state.
```

Exit.

**If exactly one of `state_md_exists` or `state_json_exists` is true:**

Load single-source recovery for the diagnostic context, but do not choose the
recovery source in the prompt. The backend repair command is the source-selection
authority; it uses the recovery-aware state loader, including recovered backup
sources and integrity issues.

```bash
SINGLE_SOURCE_RECOVERY_INIT=$(gpd --raw init sync-state --stage single_source_recovery)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd sync-state recovery init failed: $SINGLE_SOURCE_RECOVERY_INIT"
  exit 1
fi
```

Use `single_source_recovery.required_init_fields` from `SINGLE_SOURCE_RECOVERY_INIT`.

Repair the dual-write pair through the tested backend path:

```bash
SYNC_STATE_REPAIR=$(gpd --raw --cwd "$PROJECT_ROOT" state repair-sync)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd sync-state repair failed: $SYNC_STATE_REPAIR"
  exit 1
fi
```

Report `source_used`, `integrity_issues`, and `validation_status` from
`SYNC_STATE_REPAIR`, then stop. Do not prompt for a merge decision and do not
run raw JSON or markdown parsing from the prompt.

**If `state_md_exists` and `state_json_exists` are both true:** Continue to comparison.
</step>

<step name="compare">
Load conflict analysis and compare the returned state representations:

```bash
CONFLICT_ANALYSIS_INIT=$(gpd --raw init sync-state --stage conflict_analysis)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd sync-state conflict-analysis init failed: $CONFLICT_ANALYSIS_INIT"
  exit 1
fi
```

Use `conflict_analysis.required_init_fields` from `CONFLICT_ANALYSIS_INIT`. Do not re-read the mirrored files by hand for comparison.

**Parse STATE.md into comparable fields:**
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

<step name="classify">
1. If `state.json` is unreadable, invalid JSON, or missing required structured data, use the markdown recovery path and stop treating the pair as a bidirectional merge problem.
2. If `state.json` parses successfully, treat it as the structured source of truth for all mirrored fields.
3. If `STATE.md` contains schema-backed edits that disagree with `state.json` while both files parse, report the drift, but do not invent a field-by-field merge. Regenerate `STATE.md` from `state.json`.
4. Preserve JSON-only fields from `state.json` on every sync path.

state.json is authoritative for structured fields, and STATE.md is regenerated as the markdown projection of that authority.

This workflow is intentionally fail-closed: no recency heuristics, no user prompt, and no silent promotion of markdown-only edits into structured state when `state.json` is still readable.
</step>

<step name="reconcile">
Load reconcile/validate immediately before writing either state file:

```bash
RECONCILE_INIT=$(gpd --raw init sync-state --stage reconcile_and_validate)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd sync-state reconcile init failed: $RECONCILE_INIT"
  exit 1
fi
```

Use `reconcile_and_validate.required_init_fields` as the reconciliation inputs.

Run the backend reconciliation command. It chooses the recovery source from the
loader result, prefers valid backup state over malformed markdown, rejects
malformed markdown-only recovery, preserves JSON-only fields, and writes the
dual state pair atomically.

```bash
SYNC_STATE_REPAIR=$(gpd --raw --cwd "$PROJECT_ROOT" state repair-sync)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd sync-state repair failed: $SYNC_STATE_REPAIR"
  exit 1
fi
```

**Verify sync result:**

```bash
gpd --raw --cwd "$PROJECT_ROOT" state validate
```

If validation fails, report the validation issues and stop. Do not commit a partially reconciled pair.
</step>

<step name="report">
**Report what happened:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > STATE SYNCHRONIZED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Source used:** {state.json | STATE.md recovery}
**Structured fields authoritative:** state.json
**Markdown projection:** regenerated from the authoritative source
**Validation status:** {healthy / warning / degraded}

If they diverged, report changed mirrored fields and note JSON-only fields were preserved.
```
</step>

<step name="optional_commit">
**Only if the operator explicitly asks to commit the reconciled state:**

```bash
PRE_CHECK=$(gpd --cwd "$PROJECT_ROOT" pre-commit-check --files GPD/STATE.md GPD/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd --cwd "$PROJECT_ROOT" commit \
  "fix: reconcile STATE.md and state.json divergence" \
  --files GPD/STATE.md GPD/state.json
```
</step>

</process>

<failure_handling>

- **STATE.md corrupt:** The backend repair path regenerates markdown from valid structured state. If primary JSON is missing or corrupt, it prefers a valid `state.json.bak` before considering markdown. Malformed markdown-only recovery fails closed.
- **state.json corrupt (invalid JSON):** The backend repair path uses the recovery-aware state loader and valid backup state when available. Do not move or delete files from the prompt.
- **Both files exist but disagree:** Treat the mismatch as a reportable drift, not a bidirectional merge request. Use `state.json` for structured fields and regenerate `STATE.md` from it unless `state.json` is unreadable.
- **Regeneration fails validation:** Stop and report the blocking issues. Do not stage or commit the pair.

</failure_handling>

<success_criteria>

- [ ] Both state files checked for existence
- [ ] Missing file regenerated from the other when applicable
- [ ] Shared fields compared between STATE.md and state.json
- [ ] `state.json` precedence applied deterministically for mirrored fields
- [ ] JSON-only fields preserved during sync
- [ ] Validation rerun after regeneration
- [ ] Divergences reported without ad hoc merge heuristics
- [ ] Optional commit kept separate from the core reconcile/validate/report path

</success_criteria>
