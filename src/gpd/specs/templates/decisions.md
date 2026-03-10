---
template_version: 1
---

<!-- Used by: All agents. Append-only log of project decisions. -->

# Decisions Template

Template for `.gpd/DECISIONS.md` — append-only log of research decisions across all phases.

---

## File Template

```markdown
# Decision Log

Cumulative record of research decisions. Append-only — never edit or remove past entries.

| ID  | Decision | Rationale | Alternatives Considered | Phase | Date | Impact |
| --- | -------- | --------- | ----------------------- | ----- | ---- | ------ |
```

<purpose>

DECISIONS.md is the project's decision memory — a cumulative, append-only log that captures every significant research choice across all phases.

**Problem it solves:** Decisions are scattered across SUMMARY.md frontmatter, PROJECT.md Key Decisions tables, and STATE.md digests. When revisiting a choice months later — or when a referee asks "why did you use method X?" — there's no single place to look.

**Solution:** A single append-only file that:

- Records every significant decision with context (rationale, alternatives, impact)
- Is searchable by phase, keyword, or impact level
- Survives context resets (lives in .gpd/, committed to git)
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

**Reading:** On demand via `/gpd:decisions`

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
| **Date**                    | When decided (YYYY-MM-DD)              | 2026-02-15                                                |
| **Impact**                  | High / Medium / Low                    | High                                                      |

**Impact levels:**

- **High:** Affects multiple phases, changes the approach fundamentally, or is irreversible (e.g., regularization scheme, gauge choice, lattice geometry)
- **Medium:** Affects current phase significantly or constrains future options (e.g., algorithm selection, truncation order, basis set)
- **Low:** Local to one calculation, easily revisited (e.g., numerical tolerance, plot style, variable naming)

</entry_format>

<example>

```markdown
# Decision Log

Cumulative record of research decisions. Append-only — never edit or remove past entries.

| ID      | Decision                                     | Rationale                                                      | Alternatives Considered          | Phase | Date       | Impact |
| ------- | -------------------------------------------- | -------------------------------------------------------------- | -------------------------------- | ----- | ---------- | ------ |
| DEC-001 | Adopt (+,-,-,-) metric signature             | Consistent with Weinberg and Peskin & Schroeder                | (-,+,+,+) (MTW/Wald convention) | 1     | 2026-01-10 | High   |
| DEC-002 | Use Wolff cluster algorithm for MC           | Critical slowing down too severe with Metropolis near T_c      | Metropolis, Swendsen-Wang, HMC   | 2     | 2026-01-18 | Medium |
| DEC-003 | Truncate perturbative series at 2-loop       | 3-loop contribution estimated < 0.1% of leading order          | 1-loop only, 3-loop, resummation | 3     | 2026-02-01 | Medium |
| DEC-004 | Set lattice size to L=64 for production runs | Finite-size effects < 1% for L >= 48; L=64 gives safety margin | L=32, L=48, L=128                | 3     | 2026-02-03 | Low    |
```

</example>

<id_assignment>

To assign the next ID, count existing entries:

```bash
LAST_ID=$(grep -c '^| DEC-' .gpd/DECISIONS.md 2>/dev/null || echo 0)
NEXT_ID=$((LAST_ID + 1))
# Format: DEC-001, DEC-002, etc.
printf "DEC-%03d" "$NEXT_ID"
```

If DECISIONS.md doesn't exist yet, start at DEC-001.

</id_assignment>
