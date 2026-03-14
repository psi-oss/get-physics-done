---
name: gpd:compact-state
description: Archive historical entries from STATE.md to keep it under the 150-line target
argument-hint: "[--force]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Compact STATE.md when it grows too large by archiving historical entries to STATE-ARCHIVE.md.

STATE.md is the project's living memory — it accumulates decisions, insights, and context over the course of a research project. When it exceeds ~150 lines, older entries should be archived to keep the active context window efficient while preserving the full historical record.

Routes to the compact-state workflow which handles:

- Measuring current STATE.md line count
- Identifying archivable entries (completed phases, old decisions, resolved issues)
- Moving historical entries to STATE-ARCHIVE.md
- Preserving recent and actively referenced entries
- Updating cross-references between STATE.md and STATE-ARCHIVE.md
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compact-state.md
</execution_context>

<context>
@.gpd/STATE.md
</context>

<process>
**Follow the compact-state workflow** from `@{GPD_INSTALL_DIR}/workflows/compact-state.md`.

If `--force` flag is present, skip the line-count check and compact regardless of current size.

The workflow handles all logic including:

1. Measuring STATE.md line count against 150-line target
2. Identifying historical entries safe to archive
3. Creating or appending to STATE-ARCHIVE.md
4. Removing archived entries from STATE.md
5. Verifying no data was lost (archived + remaining = original)
6. Updating state.json to reflect compaction
</process>

<success_criteria>

- [ ] STATE.md is under 150 lines after compaction
- [ ] No data lost — all archived entries preserved in STATE-ARCHIVE.md
- [ ] Active context (current phase, recent decisions, open issues) retained in STATE.md
- [ ] Cross-references between STATE.md and STATE-ARCHIVE.md are valid
- [ ] state.json updated to reflect compaction
      </success_criteria>
