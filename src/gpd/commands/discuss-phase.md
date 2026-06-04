---
name: gpd:discuss-phase
description: Gather phase context through adaptive questioning before planning
argument-hint: "<phase> [--auto|--compact]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
  - ask_user
help:
  group: Planning and execution
  order: 120
  compact_description: Capture phase context before planning
  display_signature: gpd:discuss-phase <number>
---


<objective>
Route phase-context intake to the workflow-owned discussion flow. The wrapper
owns the public entrypoint and late-read template boundary only; the workflow
owns phase validation, `--auto` / `--compact` behavior, gray-area discovery,
question loops, scope guardrails, context writing, and next-step copy.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/discuss-phase.md
</execution_context>

<late_read_authorities>
Read `{GPD_INSTALL_DIR}/templates/context.md` only when writing or updating `{phase}-CONTEXT.md`. Do not load the template during gray-area discovery, user questioning, or compact-form intake.
</late_read_authorities>

<context>
Phase number: $ARGUMENTS (required)
</context>

<process>
Execute the included workflow. Preserve its late-read rule for
`{GPD_INSTALL_DIR}/templates/context.md` only when writing or updating
`{phase}-CONTEXT.md`; do not preload the template during discovery or intake.
  </process>

<success_criteria>

- Gray areas identified through intelligent analysis of the physics
- User chose which areas to discuss
- Each selected area explored until satisfied
- Scope creep redirected to deferred ideas
- CONTEXT.md captures decisions, not vague aspirations
- User knows next steps
  </success_criteria>

<mayfly_maintenance>
**After discussion concludes** — capture key decisions and open questions
in the Mayfly notebook (project_dir=$CWD):

1. For each resolved question or key decision: `gpd_mayfly:upsert_knowledge`.
2. `gpd_mayfly:update_frontier` — update active hypotheses and open directions.
3. `gpd_mayfly:append_journal_row` — outcome=partial or new_best as appropriate.

Skip silently if gpd-mayfly tools are unavailable.
</mayfly_maintenance>
