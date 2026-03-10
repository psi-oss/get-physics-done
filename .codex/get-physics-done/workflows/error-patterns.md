<purpose>
Display accumulated physics error patterns from `.gpd/ERROR-PATTERNS.md`. Optionally filter by category. Error patterns are recorded by the debugger after confirming root causes, capturing project-specific failure modes so that verifiers, planners, and executors can proactively check for recurrence.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="check_file">
Check if the error patterns file exists:

```bash
test -f .gpd/ERROR-PATTERNS.md && echo "EXISTS" || echo "MISSING"
```

**If MISSING:**

```
No error patterns recorded yet.

Error patterns are captured by $gpd-debug when root causes are confirmed.
They help the verifier and planner proactively check for recurring issues.

---

Start a debugging session with $gpd-debug to begin building the pattern database.
```

Exit.
</step>

<step name="read_patterns">
Read `.gpd/ERROR-PATTERNS.md`.

Parse the patterns table. Each row contains:

| Date | Phase | Category | Severity | Pattern | Root Cause | Prevention |
</step>

<step name="filter_if_requested">
**If $ARGUMENTS provided (category filter):**

Normalize the category argument to match known categories:

| Input           | Matches       |
| --------------- | ------------- |
| `sign`          | sign          |
| `factor`        | factor        |
| `convention`    | convention    |
| `numerical`     | numerical     |
| `approximation` | approximation |
| `boundary`      | boundary      |
| `gauge`         | gauge         |
| `combinatorial` | combinatorial |

**If category not recognized:**

```
Unknown category: "{input}"

Available categories: sign, factor, convention, numerical, approximation, boundary, gauge, combinatorial

Usage: $gpd-error-patterns [category]
```

Exit.

Filter the patterns table to show only rows matching the category.
</step>

<step name="display_filtered">
**If category filter applied:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > ERROR PATTERNS: {CATEGORY}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Date | Phase | Severity | Pattern | Root Cause | Prevention |
|------|-------|----------|---------|------------|------------|
{filtered rows}

---

Showing {N} of {total} patterns. Run `$gpd-error-patterns` to see all.
```

</step>

<step name="display_all">
**If no filter (show all):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > ERROR PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Summary

| Category | Count | Most Recent |
|----------|-------|-------------|
| sign | {N} | {date} |
| factor | {N} | {date} |
| convention | {N} | {date} |
{... for each category with entries}

## All Patterns

| Date | Phase | Category | Severity | Pattern | Root Cause | Prevention |
|------|-------|----------|----------|---------|------------|------------|
{all rows}

---

{total} patterns recorded. Filter by category: `$gpd-error-patterns sign`
```

</step>

<step name="offer_actions">
Present available actions:

```
───────────────────────────────────────────────────────────────

**Also available:**
- `$gpd-error-patterns <category>` -- filter by category
- `$gpd-debug` -- start a debugging session (records new patterns)
- `$gpd-verify-work` -- run verification (checks against known patterns)
- `gpd pattern search "<keyword>"` -- search global cross-project pattern library
- `gpd pattern list` -- list all global patterns (from all projects)

───────────────────────────────────────────────────────────────
```

</step>

</process>

<success_criteria>

- [ ] ERROR-PATTERNS.md existence checked
- [ ] Missing file handled with helpful message
- [ ] Category filter applied correctly (if provided)
- [ ] Unknown categories rejected with available list
- [ ] Patterns displayed in structured table format
- [ ] Summary by category shown (when displaying all)
- [ ] Count and filter instructions provided

</success_criteria>
