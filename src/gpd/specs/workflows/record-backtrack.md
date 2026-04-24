<purpose>
Record a backtrack event — what went wrong and what got reverted — to `GPD/BACKTRACKS.md`. This is an internal workflow used by agents (or triggered post-`gpd:undo`) so the planner can consult prior backtracks and avoid repeating mistakes.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

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

<step name="check_duplicates">
Read existing `GPD/BACKTRACKS.md` and check whether the backtrack to be recorded is already present. Dedupe by `grep -i` over the concatenation of the `trigger` and `why_wrong` keywords:

```bash
grep -i "{trigger_keyword}" GPD/BACKTRACKS.md 2>/dev/null
grep -i "{why_wrong_keyword}" GPD/BACKTRACKS.md 2>/dev/null
```

**If both keyword sets match the same existing row:** Do not duplicate. Refuse with: "Backtrack already recorded." Do nothing else.
**If not found:** Proceed to append.
</step>

<step name="append_backtrack">
Append the new backtrack as a single 11-column table row to `GPD/BACKTRACKS.md`.

**Row format:**

```
| {date} | {phase} | {stage} | {trigger} | {produced} | {why_wrong} | {counter_action} | {category} | {confidence} | {promote} | {reverted_commit} |
```

**Field conventions:**

- **date:** ISO `YYYY-MM-DD` of the backtrack event
- **phase:** Phase-id string `NN-slug` (e.g., `03-numerics`)
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
- [ ] No duplicate backtrack recorded (dedupe on `trigger` + `why_wrong`)
- [ ] Backtrack appended as an 11-column table row with all fields populated
- [ ] When `promote=true`, parallel row copied into `GPD/INSIGHTS.md`'s `## Execution Deviations` section
- [ ] Committed to git with descriptive message (both files when promoted, BACKTRACKS.md only otherwise)

**Lifecycle note:** Rows flagged `promote: true` flow through `## Execution Deviations` in INSIGHTS.md and are inherited by `gpd:complete-milestone` → `promote_patterns` unchanged, so the existing manual-review promotion path covers them. Set `promote` and `confidence` accurately — they determine promotion eligibility.

</success_criteria>
