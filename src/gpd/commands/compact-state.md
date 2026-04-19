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


<objective>
Compact STATE.md when it grows too large by archiving historical entries to STATE-ARCHIVE.md.

STATE.md is the project's living memory — it accumulates decisions, insights, and context over the course of a research project. When it exceeds ~150 lines, older entries should be archived to keep the active context window efficient while preserving the full historical record.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compact-state.md
</execution_context>

<context>
@GPD/STATE.md
</context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/compact-state.md` exactly.

If `--force` flag is present, skip the line-count check and compact regardless of current size.
</process>

<success_criteria>

- [ ] STATE.md is under 150 lines after compaction
- [ ] No data lost — all archived entries preserved in STATE-ARCHIVE.md
- [ ] Active context (current phase, recent decisions, open issues) retained in STATE.md
- [ ] Cross-references between STATE.md and STATE-ARCHIVE.md are valid
- [ ] state.json updated to reflect compaction
      </success_criteria>
