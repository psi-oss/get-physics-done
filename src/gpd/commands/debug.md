---
name: gpd:debug
description: Systematic debugging of physics calculations with persistent state across context resets
argument-hint: "[issue description]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - task
  - ask_user
---
<objective>
Orchestrate the systematic debugging workflow described in `@{GPD_INSTALL_DIR}/workflows/debug.md` to diagnose physics calculation issues.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/debug.md
</execution_context>

<context>
User's issue: $ARGUMENTS
</context>

<process>
Read the workflow referenced in `<execution_context>` first and treat it as the authoritative behavior spec. Keep `GPD/debug/{slug}.md` (goal: `find_root_cause_only`) as the session artifact, obey the typed `gpd_return.status` values for continuations, and spawn fresh continuation runs whenever a checkpoint returns. Do not branch on headings or attachments; the workflow-owned typed child-return contract and artifact gate remain the guiding source of truth.
</process>
