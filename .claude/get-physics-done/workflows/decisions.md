<purpose>
Display and search the cumulative decision log from .gpd/DECISIONS.md. Supports filtering by phase number or keyword, and presents formatted output with summary statistics.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="check_existence">
Check if the decision log exists:

```bash
cat .gpd/DECISIONS.md 2>/dev/null
```

**If file doesn't exist or has no entries (only header row):**

```
No decisions logged yet.

Decisions are recorded automatically during phase transitions (/gpd:progress).
You can also add entries manually to .gpd/DECISIONS.md.

---

Would you like to:

1. Check project progress (/gpd:progress)
2. View current phase (/gpd:show-phase)
```

Exit.
</step>

<step name="parse_arguments">
Determine filter mode from arguments:

- `/gpd:decisions` -> show all entries
- `/gpd:decisions 3` (number) -> filter to Phase 3 only
- `/gpd:decisions regularization` (text) -> keyword search across all fields
- `/gpd:decisions high` -> filter by impact level

**Detection logic:**

- If argument is a number (integer or decimal like 2.1): phase filter
- If argument matches `high`, `medium`, or `low` (case-insensitive): impact filter
- Otherwise: keyword search
  </step>

<step name="parse_table">
Parse the markdown table from DECISIONS.md.

Extract each row into fields: ID, Decision, Rationale, Alternatives Considered, Phase, Date, Impact.

Skip the header row and separator row.
</step>

<step name="apply_filter">
**Phase filter:** Keep rows where Phase field matches the requested phase number.

**Keyword filter:** Keep rows where any field contains the keyword (case-insensitive).

**Impact filter:** Keep rows where Impact field matches (case-insensitive).

**No filter:** Keep all rows.
</step>

<step name="display_results">
**If filter returned results:**

Present filtered entries in a readable format:

```
## Decision Log{filter_suffix}

{filter_suffix examples: " — Phase 3", " — matching 'regularization'", " — High Impact"}

| ID | Decision | Phase | Date | Impact |
| --- | --- | --- | --- | --- |
| DEC-001 | Adopt (-,+,+,+) metric signature | 1 | 2026-01-10 | High |
| DEC-003 | Truncate series at 2-loop | 3 | 2026-02-01 | Medium |

---

**{N} decisions** shown{filter_note}. {M} total in log.
```

For the compact table, show ID, Decision, Phase, Date, Impact.

To see full details (rationale and alternatives) for a specific decision, the user can ask: "Show details for DEC-003".

**If showing details for one decision:**

```
## DEC-003: Truncate perturbative series at 2-loop

**Phase:** 3 | **Date:** 2026-02-01 | **Impact:** Medium

**Rationale:** 3-loop contribution estimated < 0.1% of leading order

**Alternatives Considered:** 1-loop only, 3-loop, resummation
```

**If filter returned no results:**

```
No decisions match {filter description}.

Try:
- `/gpd:decisions` — show all
- `/gpd:decisions <phase>` — filter by phase
- `/gpd:decisions <keyword>` — search by keyword
```

</step>

<step name="summary_stats">
After the table, show a brief summary:

```
**Summary:** {total} decisions across {phase_count} phases | High: {h} | Medium: {m} | Low: {l}
```

Only show this for unfiltered or phase-filtered views (skip for keyword searches with few results).
</step>

</process>

<success_criteria>

- [ ] Decision log loaded from .gpd/DECISIONS.md
- [ ] Arguments parsed correctly (phase number vs keyword vs impact)
- [ ] Filter applied to table rows
- [ ] Filtered results displayed in compact table
- [ ] Summary statistics shown
- [ ] Helpful guidance if no decisions exist or no matches found

</success_criteria>
