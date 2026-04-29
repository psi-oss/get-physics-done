---
template_version: 1
---

<!-- Used by: All agents. Append-only log of project decisions. -->

# Decisions Template

Template for `GPD/DECISIONS.md`, the append-only project memory for significant research choices.

---

## File Template

```markdown
# Decision Log

Cumulative record of research decisions. Append-only — never edit or remove past entries.

| ID  | Decision | Rationale | Alternatives Considered | Phase | Date | Impact |
| --- | -------- | --------- | ----------------------- | ----- | ---- | ------ |
```

<purpose>

DECISIONS.md gives the project one durable place for significant choices that would otherwise be scattered across SUMMARY.md frontmatter, PROJECT.md tables, and STATE.md digests. It:

- Records every significant decision with context (rationale, alternatives, impact)
- Is searchable by phase, keyword, or impact level
- Survives context resets (lives in GPD/, committed to git)
- Feeds into paper writing (Methods section, reviewer responses)

</purpose>

<lifecycle>

**Creation:** During project initialization (after ROADMAP.md is created)

- Create with header row only (no entries yet)
- First entries come from Phase 1 planning decisions

**Appending:** During phase transitions (transition workflow)

- Extract decisions from completed phase's SUMMARY.md files (key-decisions frontmatter field)
- Extract decisions from CONTEXT.md if present
- Assign sequential IDs (DEC-001, DEC-002, ...)
- Never edit or remove existing entries

**Reading:** On demand via `gpd:decisions`

- Display formatted decision log
- Filter by phase number or keyword search
- Used during paper writing for Methods section
- Used when revisiting past choices

</lifecycle>

<entry_format>

Each decision entry is a table row with these fields:

| Field                       | Description                            | Example                                                   |
| --------------------------- | -------------------------------------- | --------------------------------------------------------- |
| **ID**                      | Sequential identifier `DEC-NNN`        | DEC-003                                                   |
| **Decision**                | What was decided (concise, imperative) | Use dimensional regularization                            |
| **Rationale**               | Why this choice was made               | Preserves gauge invariance; cutoff breaks Ward identities |
| **Alternatives Considered** | What else was evaluated                | Cutoff regularization, zeta-function regularization       |
| **Phase**                   | Phase number where decided             | 2                                                         |
| **Date**                    | When decided (YYYY-MM-DD)              | 2026-03-15                                                |
| **Impact**                  | High / Medium / Low                    | High                                                      |

**Impact levels:**

- **High:** Affects multiple phases, changes the approach fundamentally, or is irreversible (e.g., regularization scheme, gauge choice, lattice geometry)
- **Medium:** Affects current phase significantly or constrains future options (e.g., algorithm selection, truncation order, basis set)
- **Low:** Local to one calculation, easily revisited (e.g., numerical tolerance, plot style, variable naming)

</entry_format>

Example rows:

| ID      | Decision                         | Rationale                                       | Alternatives Considered         | Phase | Date       | Impact |
| ------- | -------------------------------- | ----------------------------------------------- | ------------------------------- | ----- | ---------- | ------ |
| DEC-001 | Adopt (+,-,-,-) metric signature | Consistent with core references                 | (-,+,+,+) convention            | 1     | 2026-03-15 | High   |
| DEC-002 | Use Wolff cluster algorithm      | Reduces critical slowing down near T_c          | Metropolis, Swendsen-Wang, HMC  | 2     | 2026-03-15 | Medium |

<id_assignment>

To assign the next ID, count existing entries:

```bash
LAST_ID=$(grep -c '^| DEC-' GPD/DECISIONS.md 2>/dev/null || echo 0)
NEXT_ID=$((LAST_ID + 1))
# Format: DEC-001, DEC-002, etc.
printf "DEC-%03d" "$NEXT_ID"
```

If DECISIONS.md doesn't exist yet, start at DEC-001.

</id_assignment>
