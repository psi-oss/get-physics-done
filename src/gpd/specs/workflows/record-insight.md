<purpose>
Record a project-specific learning insight to `.gpd/INSIGHTS.md`. This is an internal workflow used by agents after discovering patterns worth preserving for the project.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="check_insights_file">
Check if `.gpd/INSIGHTS.md` exists:

```bash
test -f .gpd/INSIGHTS.md && echo "EXISTS" || echo "MISSING"
```

**If MISSING:** Create from template:

```bash
mkdir -p .gpd
```

Write `.gpd/INSIGHTS.md`:

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

</step>

<step name="check_duplicates">
Read existing `.gpd/INSIGHTS.md` and check whether the insight to be recorded is already present.

```bash
grep -i "{brief_description_keyword}" .gpd/INSIGHTS.md 2>/dev/null
```

**If found:** Do not duplicate. Report: "Insight already recorded."
**If not found:** Proceed to append.
</step>

<step name="determine_section">
Map the insight category to the appropriate section:

| Category              | Section              |
| --------------------- | -------------------- |
| error-pattern         | Debugging Patterns   |
| debugging-pattern     | Debugging Patterns   |
| convention-pitfall    | Consistency Issues   |
| approximation-lesson  | Verification Lessons |
| computational-insight | Execution Deviations |
| verification-lesson   | Verification Lessons |

</step>

<step name="append_insight">
Append the new insight as a table row to the appropriate section in `.gpd/INSIGHTS.md`.

**Row format:**

```
| {YYYY-MM-DD} | {phase-id} | {category} | {high/medium/low} | {concise description of the lesson} | {how to prevent recurrence} |
```

**Field guidelines:**

- **Date:** ISO date of discovery
- **Phase:** Phase where the insight was discovered (e.g., `03-numerics`)
- **Category:** One of: `error-pattern`, `convention-pitfall`, `approximation-lesson`, `computational-insight`, `debugging-pattern`, `verification-lesson`
- **Confidence:** `high` (confirmed with evidence), `medium` (likely based on investigation), `low` (suspected pattern, needs more data)
- **Description:** One sentence capturing the lesson. Be specific: "Sign error in Wick contractions when using mostly-minus metric" not "sign errors happen"
- **Prevention:** One sentence on how to avoid this in future phases
  </step>

<step name="git_commit">
Commit the insight:

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/INSIGHTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: record project insight - {brief description}" --files .gpd/INSIGHTS.md
```

Confirm: "Recorded insight: {brief description}"
</step>

</process>

<success_criteria>

- [ ] `.gpd/INSIGHTS.md` exists (created if needed)
- [ ] No duplicate insight recorded
- [ ] Insight appended to correct section with all fields populated
- [ ] Committed to git with descriptive message

**Lifecycle note:** High-confidence insights confirmed across 2+ phases are candidates for promotion to the global pattern library at milestone completion (`/gpd:complete-milestone` → promote_patterns step). Set confidence accurately — it determines promotion eligibility.

</success_criteria>
