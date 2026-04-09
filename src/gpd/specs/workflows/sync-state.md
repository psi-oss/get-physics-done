<purpose>
Reconcile diverged `STATE.md` and `state.json` with a deterministic, fail-closed rule set. `state.json` is the authoritative store for structured state; `STATE.md` is the human-readable projection. When both files exist, structured fields follow `state.json` and the markdown view is regenerated from it. Markdown is only used as a recovery source when `state.json` is missing or unreadable.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.

**Schema reference:** `{GPD_INSTALL_DIR}/templates/state-json-schema.md` — Canonical schema for state.json fields, types, defaults, and authoritative-vs-derived status. Consult when resolving conflicts between STATE.md and state.json.
Before deciding any repair, read `{GPD_INSTALL_DIR}/templates/state-json-schema.md` itself and use its authoritative-vs-derived rules as the reconciliation contract rather than guessing from the current file contents.

Canonical reconciliation contract:
@{GPD_INSTALL_DIR}/templates/state-json-schema.md
</required_reading>

<process>

<step name="inspect" priority="first">
**Check both state files exist:**

```bash
STATE_MD="GPD/STATE.md"
STATE_JSON="GPD/state.json"

MD_EXISTS=$(test -f "$STATE_MD" && echo true || echo false)
JSON_EXISTS=$(test -f "$STATE_JSON" && echo true || echo false)
```

**If neither exists:**

```
No state files found. Run gpd:new-project to initialize project state.
```

Exit.

**If only STATE.md exists (state.json missing):**

Recover `state.json` from the markdown recovery source and preserve the JSON-only state on disk by rebuilding the dual-write pair atomically:

```bash
uv run python - <<'PY'
from pathlib import Path
from gpd.core.state import save_state_markdown

cwd = Path(".")
md_path = cwd / "GPD" / "STATE.md"
save_state_markdown(cwd, md_path.read_text(encoding="utf-8"))
PY
```

Then run `gpd --raw state validate`, report the recovery result, and stop. Do not prompt for a merge decision: markdown recovery is the only allowed source when JSON is absent.

**If only state.json exists (STATE.md missing):**

`state.json` is authoritative. Rebuild `STATE.md` directly from it:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from gpd.core.state import save_state_json

cwd = Path(".")
state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
save_state_json(cwd, state)
PY
```

Then run `gpd --raw state validate`, report the regeneration result, and stop.

**If both exist:** Continue to comparison.
</step>

<step name="compare">
**Read both state representations:**

```bash
cat GPD/STATE.md
cat GPD/state.json
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

<step name="classify">
**Classify the relationship between the two files:**

1. If `state.json` is unreadable, invalid JSON, or missing required structured data, use the markdown recovery path and stop treating the pair as a bidirectional merge problem.
2. If `state.json` parses successfully, treat it as the structured source of truth for all mirrored fields.
3. If `STATE.md` contains schema-backed edits that disagree with `state.json` while both files parse, report the drift, but do not invent a field-by-field merge. Regenerate `STATE.md` from `state.json`.
4. Preserve JSON-only fields from `state.json` on every sync path.

state.json is authoritative for structured fields, and STATE.md is regenerated as the markdown projection of that authority.

This workflow is intentionally fail-closed: no recency heuristics, no user prompt, and no silent promotion of markdown-only edits into structured state when `state.json` is still readable.
</step>

<step name="reconcile">
**Rebuild the canonical pair deterministically:**

**If `state.json` is valid:**

Regenerate `STATE.md` from `state.json`:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from gpd.core.state import save_state_json

cwd = Path(".")
state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
save_state_json(cwd, state)
PY
```

**If `state.json` is invalid or unreadable but `STATE.md` is valid:**

Recover `state.json` from `STATE.md` through the authoritative markdown write path:

```bash
uv run python - <<'PY'
from pathlib import Path
from gpd.core.state import save_state_markdown

cwd = Path(".")
md_path = cwd / "GPD" / "STATE.md"
save_state_markdown(cwd, md_path.read_text(encoding="utf-8"))
PY
```

**Verify sync result:**

```bash
gpd --raw state validate
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

If STATE.md and state.json previously diverged, report the mirrored fields that changed and note that JSON-only fields were preserved.
```
</step>

<step name="optional_commit">
**Only if the operator explicitly asks to commit the reconciled state:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/STATE.md GPD/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "fix: reconcile STATE.md and state.json divergence" \
  --files GPD/STATE.md GPD/state.json
```
</step>

</process>

<failure_handling>

- **STATE.md corrupt (unparseable):** If `STATE.md` cannot be parsed, check whether `state.json` is valid and regenerate the markdown view from it. If both are damaged, follow the built-in recovery chain in order: `state.json.bak`, then any surviving valid `STATE.md`, then a controlled regeneration from defaults plus surviving structured artifacts.
- **state.json corrupt (invalid JSON):** Move it aside to `GPD/state.json.bak`, then recover from `STATE.md` through the markdown write path. Do not delete it without keeping a backup first.
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
