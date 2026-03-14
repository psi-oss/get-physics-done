---
template_version: 1
---

<!-- Used by: gpd state compact command (state_compact in gpd.core.state). -->

# State Archive Template

Template for `.gpd/STATE-ARCHIVE.md` - historical state entries archived from STATE.md during compaction.

**Purpose:** When STATE.md exceeds the line budget (1500 lines), `gpd state compact` moves older entries here. This preserves the full decision and metric history while keeping STATE.md focused on the current and recent phases.

**Created by:** `gpd state compact` (automatic). Do not create manually.

---

## File Template

```markdown
# STATE Archive

Historical state entries archived from STATE.md.

## Archived YYYY-MM-DD (from phase N)

### Decisions

- [Phase 1] Decision text from early phases
- [Phase 2] Decision text from early phases

### Resolved Blockers

- ~~Blocker description~~ [resolved]
- ~~Another blocker~~ [resolved]

### Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| Phase 1: Name | 45min | 4 | 6 |
| Phase 2: Name | 1h 10min | 7 | 12 |

### Session Records

**Last session:** YYYY-MM-DD
Context: [what was being worked on]
Next: [what was planned next]

## Archived YYYY-MM-DD (from phase M)

[Subsequent compactions append new sections here]
```

<archive_structure>

### What Gets Archived

| Section | Archive Condition | Retention in STATE.md |
|---------|------------------|----------------------|
| **Decisions** | Phase number < (current phase - 1) | Keep current + previous phase decisions |
| **Resolved Blockers** | Marked `[resolved]` or struck through | Keep only active blockers |
| **Performance Metrics** | Phase number < (current phase - 1) | Keep current + previous phase metrics |
| **Session Records** | All but the 3 most recent | Keep last 3 session records |

### Archive Format

Each compaction creates a dated section header:

```markdown
## Archived YYYY-MM-DD (from phase N)
```

Entries are grouped by type within each archive block. Multiple compactions accumulate — the file is append-only.

</archive_structure>

<guidelines>
- This file is append-only: compactions add new sections, never modify existing ones
- Each archive block is dated and tagged with the phase that triggered compaction
- The file header ("# STATE Archive" + description line) is written on first creation
- Subsequent compactions append after the existing content
- Do not manually edit this file — it is a historical record
- If STATE.md is manually trimmed, the trimmed content should be appended here following the same format
- Compaction triggers when STATE.md exceeds 1500 lines (STATE_LINES_BUDGET in gpd.core.constants)
- A warning is emitted when STATE.md exceeds 150 lines (`STATE_LINES_TARGET`) but does not trigger compaction
</guidelines>
