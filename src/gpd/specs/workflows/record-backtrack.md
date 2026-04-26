<purpose>
Record a backtrack event — what went wrong and what got reverted — to `GPD/BACKTRACKS.md`. This is an internal workflow used by agents (or triggered post-`gpd:undo`) so the planner can consult prior backtracks and avoid repeating mistakes.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="parse_prefill_args">
Parse optional prefill inputs from structured runtime args first, then from `$ARGUMENTS` flags for command-line compatibility:

- structured `reverted_commit` or `--reverted-commit=<sha>` -> prefills `reverted_commit`
- structured `trigger` or `--trigger=<text>` -> prefills `trigger`
- structured `phase` or `--phase=<NN-slug>` -> prefills `phase` (for example `03-numerics`; accept `phase-03` only as a source hint and normalize before writing the row)

Any remaining non-flag text is the free-form `description` (used as fallback for the `trigger` field if `--trigger` is not supplied).

Fields not provided by structured args or flags are prompted from the user during `collect_backtrack_fields`. Any prefilled field can still be overridden by the user before duplicate checking and append.
</step>

<step name="check_backtracks_file">
Check if `GPD/BACKTRACKS.md` exists:

```bash
test -f GPD/BACKTRACKS.md && echo "EXISTS" || echo "MISSING"
```

**If MISSING:** Create from template:

```bash
mkdir -p GPD
```

Write `GPD/BACKTRACKS.md`:

```markdown
# Project Backtracks

Backtrack events captured during research. Agents consult this file to avoid repeating mistakes and apply counter-actions learned from past deviations.

| date | phase | stage | trigger | produced | why_wrong | counter_action | category | confidence | promote | reverted_commit |
| ---- | ----- | ----- | ------- | -------- | --------- | -------------- | -------- | ---------- | ------- | --------------- |
```

</step>

<step name="collect_backtrack_fields">
Collect and finalize the row values before any duplicate check. Prompt or infer every missing required field, then show the draft row once and let the user override any prefilled value.

The finalized fields used downstream are:

- `FINAL_DATE`
- `FINAL_PHASE`
- `FINAL_STAGE`
- `FINAL_TRIGGER`
- `FINAL_PRODUCED`
- `FINAL_WHY_WRONG`
- `FINAL_COUNTER_ACTION`
- `FINAL_CATEGORY`
- `FINAL_CONFIDENCE`
- `FINAL_PROMOTE`
- `FINAL_REVERTED_COMMIT`

Do not run dedupe from raw prefill values. The duplicate key is the finalized `phase` + `trigger` + `why_wrong` after user edits, normalization, and inference.
</step>

<step name="check_duplicates">
Read existing `GPD/BACKTRACKS.md` and check whether the finalized backtrack row is already present. Dedupe by exact normalized matching of finalized `phase` + `trigger` + `why_wrong` within the same row (not across rows) using awk against the 11-column pipe-delimited schema:

```bash
DUP=$(awk -F'|' -v ph="$FINAL_PHASE" -v tr="$FINAL_TRIGGER" -v ww="$FINAL_WHY_WRONG" '
  function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
  NR>2 && /^\|/ {
    if (trim($3) == ph && tolower(trim($5)) == tolower(tr) && tolower(trim($7)) == tolower(ww)) print NR
  }
' GPD/BACKTRACKS.md 2>/dev/null)
```

**If `$DUP` is non-empty:** Duplicate detected on line(s) `$DUP`. Refuse with: "Backtrack already recorded on line(s) $DUP." Do nothing else.
**If `$DUP` is empty:** Proceed to append.

The schema's column order — `date | phase | stage | trigger | produced | why_wrong | counter_action | category | confidence | promote | reverted_commit` — puts `phase` at field 3, `trigger` at field 5, and `why_wrong` at field 7. Column-anchoring the match prevents false positives where keywords land in unrelated cells (e.g., "metric" in `counter_action` conflated with "metric" in `trigger`).
</step>

<step name="append_backtrack">
Append the finalized backtrack as a single 11-column table row to `GPD/BACKTRACKS.md`. Any fields prefilled by `parse_prefill_args` (e.g. `reverted_commit`, `trigger`, `phase`) have already passed through `collect_backtrack_fields`, so the row written here must use the finalized `FINAL_*` values.

**Row format:**

```
| {FINAL_DATE} | {FINAL_PHASE} | {FINAL_STAGE} | {FINAL_TRIGGER} | {FINAL_PRODUCED} | {FINAL_WHY_WRONG} | {FINAL_COUNTER_ACTION} | {FINAL_CATEGORY} | {FINAL_CONFIDENCE} | {FINAL_PROMOTE} | {FINAL_REVERTED_COMMIT} |
```

**Field conventions:**

- **date:** ISO `YYYY-MM-DD` of the backtrack event
- **phase:** Phase-id string `NN-slug` (e.g., `03-numerics`; normalize commit/path hints like `phase-03` before writing when the slug is discoverable)
- **stage:** One of `plan | research | execute | verify | consistency`
- **trigger:** Short text describing what caused the backtrack
- **produced:** What the previous run produced (e.g., `03-02-SUMMARY.md (proof for wrong signature)`)
- **why_wrong:** One-sentence explanation of why the previous output was wrong
- **counter_action:** One-sentence fix / future prevention
- **category:** One of `convention-pitfall | approximation-lesson | computational-insight | debugging-pattern | verification-lesson | bad-plan-scope | wrong-approximation-choice | premature-numerics | verification-gap`
- **confidence:** `high` (confirmed with evidence), `medium` (likely based on investigation), `low` (suspected pattern, needs more data)
- **promote:** `true` | `false` — whether this backtrack is a candidate for promotion into the shared INSIGHTS ledger
- **reverted_commit:** Short SHA (7 chars) of the reverted commit, or empty
</step>

<step name="promote_to_insights">
**Conditional on `promote=true`.** If the recorded row's `promote` field is `false`, skip this step entirely.

Check if `GPD/INSIGHTS.md` exists:

```bash
test -f GPD/INSIGHTS.md && echo "EXISTS" || echo "MISSING"
```

**If MISSING:** Bootstrap from the record-insight template:

```bash
mkdir -p GPD
```

Write `GPD/INSIGHTS.md`:

```markdown
# Project Insights

Accumulated project-specific lessons discovered during research. Agents consult this file to avoid repeating mistakes and to apply learned patterns.

## Debugging Patterns

| Date | Phase | Category | Confidence | Description | Prevention |
| ---- | ----- | -------- | ---------- | ----------- | ---------- |

## Verification Lessons

| Date | Phase | Category | Confidence | Description | Prevention |
| ---- | ----- | -------- | ---------- | ----------- | ---------- |

## Consistency Issues

| Date | Phase | Category | Confidence | Description | Prevention |
| ---- | ----- | -------- | ---------- | ----------- | ---------- |

## Execution Deviations

| Date | Phase | Category | Confidence | Description | Prevention |
| ---- | ----- | -------- | ---------- | ----------- | ---------- |
```

Append a parallel row to `GPD/INSIGHTS.md`'s `## Execution Deviations` section using this field mapping (backtrack row → insights row):

| Backtrack field  | INSIGHTS field | Value                             |
| ---------------- | -------------- | --------------------------------- |
| `date`           | `Date`         | `date`                            |
| `phase`          | `Phase`        | `phase`                           |
| *(literal)*      | `Category`     | `execution-deviation`             |
| `confidence`     | `Confidence`   | `confidence`                      |
| `trigger` + `why_wrong` | `Description` | `{trigger} — {why_wrong}`    |
| `counter_action` | `Prevention`   | `counter_action`                  |

The literal `execution-deviation` in the INSIGHTS `Category` column marks the row as `source=backtrack` so downstream review (e.g., `gpd:complete-milestone` → promote_patterns) can trace its origin.

Log the promotion explicitly so downstream review can trace the source, e.g.:

```
Promoted backtrack to INSIGHTS.md (## Execution Deviations): {trigger}
```
</step>

<step name="git_commit">
Commit the backtrack (and the promoted INSIGHTS row if applicable):

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/BACKTRACKS.md GPD/INSIGHTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: record backtrack - {brief description}" --files GPD/BACKTRACKS.md GPD/INSIGHTS.md
```

**If `promote` is `false`:** commit only `GPD/BACKTRACKS.md`:

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/BACKTRACKS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: record backtrack - {brief description}" --files GPD/BACKTRACKS.md
```

Confirm: "Recorded backtrack: {brief description}"
</step>

</process>

<success_criteria>

- [ ] `GPD/BACKTRACKS.md` exists (created if needed)
- [ ] No duplicate backtrack recorded (dedupe on `phase` + `trigger` + `why_wrong`)
- [ ] Backtrack appended as an 11-column table row with all fields populated
- [ ] When `promote=true`, parallel row copied into `GPD/INSIGHTS.md`'s `## Execution Deviations` section
- [ ] Committed to git with descriptive message (both files when promoted, BACKTRACKS.md only otherwise)

**Lifecycle note:** Rows flagged `promote: true` flow through `## Execution Deviations` in INSIGHTS.md and are inherited by `gpd:complete-milestone` → `promote_patterns` unchanged, so the existing manual-review promotion path covers them. Set `promote` and `confidence` accurately — they determine promotion eligibility.

</success_criteria>
